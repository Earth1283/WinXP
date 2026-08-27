"""Document model: layers, blend modes, selections, history, channels.

Deliberately mirrors how Photoshop 7 actually behaves rather than what is
convenient -- history is snapshot-based with a state cap, selections are
8-bit masks (so feathering is real), and layer styles live on the layer
instead of being baked into its pixels.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QRegion

from . import imageops as ops

# Photoshop 7's Layers palette, in its own order, separators included so the
# combo box can draw them the way the real one does.
BLEND_MODES = [
    "Normal", "Dissolve", "-",
    "Darken", "Multiply", "Color Burn", "Linear Burn", "-",
    "Lighten", "Screen", "Color Dodge", "Linear Dodge", "-",
    "Overlay", "Soft Light", "Hard Light", "Vivid Light", "Linear Light", "Pin Light", "-",
    "Difference", "Exclusion", "-",
    "Hue", "Saturation", "Color", "Luminosity",
]

_QT_MODES = {
    "Normal": QPainter.CompositionMode.CompositionMode_SourceOver,
    "Multiply": QPainter.CompositionMode.CompositionMode_Multiply,
    "Screen": QPainter.CompositionMode.CompositionMode_Screen,
    "Overlay": QPainter.CompositionMode.CompositionMode_Overlay,
    "Darken": QPainter.CompositionMode.CompositionMode_Darken,
    "Lighten": QPainter.CompositionMode.CompositionMode_Lighten,
    "Color Dodge": QPainter.CompositionMode.CompositionMode_ColorDodge,
    "Color Burn": QPainter.CompositionMode.CompositionMode_ColorBurn,
    "Hard Light": QPainter.CompositionMode.CompositionMode_HardLight,
    "Soft Light": QPainter.CompositionMode.CompositionMode_SoftLight,
    "Difference": QPainter.CompositionMode.CompositionMode_Difference,
    "Exclusion": QPainter.CompositionMode.CompositionMode_Exclusion,
    "Linear Dodge": QPainter.CompositionMode.CompositionMode_Plus,
}


def _color_burn(a, b):
    return 255 - min(255, (255 - a) * 255 / max(1, b))


def _color_dodge(a, b):
    return min(255, a * 255 / max(1, 255 - b))


# base byte, blend byte -> result byte. Only the modes Qt has no raster mode
# for; everything else goes through _QT_MODES.
_BYTE_BLENDS = {
    "Linear Burn": lambda a, b: a + b - 255,
    "Linear Light": lambda a, b: a + 2 * b - 255,
    "Vivid Light": lambda a, b: (_color_burn(a, 2 * b) if b < 128
                                 else _color_dodge(a, 2 * (b - 128))),
    "Pin Light": lambda a, b: (min(a, 2 * b) if b < 128 else max(a, 2 * b - 255)),
}

_HSL_BLENDS = ("Hue", "Saturation", "Color", "Luminosity")


def blend_layer(base: QImage, layer: QImage, mode: str, opacity: float) -> QImage:
    """Composite one layer onto a base image, honouring every PS 7 mode."""
    if opacity <= 0:
        return base
    out = base
    if mode == "Dissolve":
        layer = _dissolve(layer, opacity)
        opacity = 1.0
        mode = "Normal"
    if mode in _BYTE_BLENDS or mode in _HSL_BLENDS:
        if mode in _BYTE_BLENDS:
            blended = ops.combine(base, layer, _BYTE_BLENDS[mode])
        else:
            blended = _hsl_blend(base, layer, mode)
        blended = _reapply_alpha(blended, layer)
        layer = blended
        mode = "Normal"
    p = QPainter(out)
    p.setOpacity(opacity)
    p.setCompositionMode(_QT_MODES.get(mode, _QT_MODES["Normal"]))
    p.drawImage(0, 0, layer)
    p.end()
    return out


def _reapply_alpha(blended: QImage, layer: QImage) -> QImage:
    """Byte blends ignore alpha, so put the layer's own alpha back."""
    bb, w, h = ops.to_buf(blended)
    lb, _, _ = ops.to_buf(layer)
    ops.set_plane(bb, ops.A, ops.plane(lb, ops.A))
    return ops.from_buf(bb, w, h)


def _dissolve(layer: QImage, opacity: float) -> QImage:
    """Per-pixel coin flip against the layer opacity -- the actual algorithm,
    which is why Dissolve looks like static instead of a fade."""
    buf, w, h = ops.to_buf(layer)
    alpha = ops.plane(buf, ops.A)
    cutoff = int(opacity * 255)
    noise = random.randbytes(w * h)
    ops.set_plane(buf, ops.A, bytes(
        a if noise[i] < cutoff else 0 for i, a in enumerate(alpha)))
    return ops.from_buf(buf, w, h)


def _hsl_blend(base: QImage, layer: QImage, mode: str) -> QImage:
    bb, w, h = ops.to_buf(base)
    lb, _, _ = ops.to_buf(layer)
    br, bg, bl = ops.plane(bb, ops.R), ops.plane(bb, ops.G), ops.plane(bb, ops.B)
    lr, lg, ll = ops.plane(lb, ops.R), ops.plane(lb, ops.G), ops.plane(lb, ops.B)
    orr, og, ob = bytearray(len(br)), bytearray(len(br)), bytearray(len(br))
    memo: dict = {}
    for i in range(len(br)):
        key = (br[i], bg[i], bl[i], lr[i], lg[i], ll[i])
        got = memo.get(key)
        if got is None:
            bh, bs, blum = ops._rgb_to_hsl(key[0], key[1], key[2])
            sh, ss, slum = ops._rgb_to_hsl(key[3], key[4], key[5])
            if mode == "Hue":
                got = ops._hsl_to_rgb(sh, bs, blum)
            elif mode == "Saturation":
                got = ops._hsl_to_rgb(bh, ss, blum)
            elif mode == "Color":
                got = ops._hsl_to_rgb(sh, ss, blum)
            else:  # Luminosity
                got = ops._hsl_to_rgb(bh, bs, slum)
            memo[key] = got
        orr[i], og[i], ob[i] = got
    ops.set_plane(bb, ops.R, orr)
    ops.set_plane(bb, ops.G, og)
    ops.set_plane(bb, ops.B, ob)
    return ops.from_buf(bb, w, h)


# ---------------------------------------------------------------- layers ---

DEFAULT_STYLE = {
    "Drop Shadow": dict(enabled=False, color="#000000", opacity=75, angle=120,
                        distance=5, spread=0, size=5),
    "Inner Shadow": dict(enabled=False, color="#000000", opacity=75, angle=120,
                         distance=5, choke=0, size=5),
    "Outer Glow": dict(enabled=False, color="#ffffbe", opacity=75, spread=0, size=5),
    "Inner Glow": dict(enabled=False, color="#ffffbe", opacity=75, choke=0, size=5),
    "Bevel and Emboss": dict(enabled=False, style="Inner Bevel", depth=100,
                             direction="Up", size=5, soften=0, angle=120, altitude=30),
    "Satin": dict(enabled=False, color="#000000", opacity=50, angle=19,
                  distance=11, size=14, invert=True),
    "Color Overlay": dict(enabled=False, color="#ff0000", opacity=100),
    "Gradient Overlay": dict(enabled=False, start="#000000", end="#ffffff",
                             opacity=100, angle=90),
    "Pattern Overlay": dict(enabled=False, pattern="Checkerboard", opacity=100, scale=100),
    "Stroke": dict(enabled=False, color="#000000", size=3, position="Outside", opacity=100),
}


def default_style():
    return {k: dict(v) for k, v in DEFAULT_STYLE.items()}


@dataclass
class Layer:
    name: str
    image: QImage
    visible: bool = True
    opacity: float = 1.0
    fill_opacity: float = 1.0
    blend: str = "Normal"
    kind: str = "pixel"            # pixel | type | adjustment | shape | group
    mask: QImage | None = None     # 8-bit-ish greyscale, white = shows
    mask_linked: bool = True
    mask_enabled: bool = True
    locked_transparency: bool = False
    locked_pixels: bool = False
    locked_position: bool = False
    locked_all: bool = False
    clipping: bool = False         # clipped to the layer beneath (PS 7: grouped)
    style: dict = field(default_factory=default_style)
    text: dict | None = None       # type layers: string, font, size, colour, ...
    adjustment: dict | None = None  # adjustment layers: kind + params
    group_open: bool = True
    indent: int = 0                # layer-set nesting depth

    def copy(self) -> "Layer":
        return Layer(
            self.name, self.image.copy(), self.visible, self.opacity, self.fill_opacity,
            self.blend, self.kind, self.mask.copy() if self.mask else None,
            self.mask_linked, self.mask_enabled, self.locked_transparency,
            self.locked_pixels, self.locked_position, self.locked_all, self.clipping,
            {k: dict(v) for k, v in self.style.items()},
            dict(self.text) if self.text else None,
            dict(self.adjustment) if self.adjustment else None,
            self.group_open, self.indent,
        )

    def has_style(self) -> bool:
        return any(v.get("enabled") for v in self.style.values())

    def thumbnail(self, w=32, h=32) -> QImage:
        return self.image.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)


# ------------------------------------------------------------- selection ---

class Selection:
    """8-bit mask plus the path it came from.

    The mask is what pixels actually get judged against (so Feather is a real
    blur, not an outline trick); the path is what the marching ants trace.
    """

    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.mask: QImage | None = None
        self.path: QPainterPath | None = None
        self.feather_radius = 0.0

    def is_empty(self) -> bool:
        return self.mask is None

    def clear(self):
        self.mask = None
        self.path = None
        self.feather_radius = 0.0

    def _blank(self) -> QImage:
        img = QImage(self.w, self.h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        return img

    @staticmethod
    def _mask_from_path(w, h, path: QPainterPath, antialias=True) -> QImage:
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.black)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, antialias)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(Qt.GlobalColor.white)
        p.drawPath(path)
        p.end()
        return img

    def set_path(self, path: QPainterPath, mode="replace", antialias=True):
        new_mask = self._mask_from_path(self.w, self.h, path, antialias)
        self.combine_mask(new_mask, mode)
        if mode == "replace" or self.path is None:
            self.path = QPainterPath(path)
        elif mode == "add":
            self.path = self.path.united(path)
        elif mode == "subtract":
            self.path = self.path.subtracted(path)
        elif mode == "intersect":
            self.path = self.path.intersected(path)
        self.feather_radius = 0.0

    def combine_mask(self, new_mask: QImage, mode="replace"):
        if self.mask is None or mode == "replace":
            self.mask = new_mask
            return
        p = QPainter(self.mask)
        if mode == "add":
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Lighten)
        elif mode == "subtract":
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
        else:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Darken)
        p.drawImage(0, 0, new_mask)
        p.end()

    def set_mask(self, mask: QImage, mode="replace"):
        self.combine_mask(mask, mode)
        self.path = self._path_from_mask(self.mask)

    @staticmethod
    def _path_from_mask(mask: QImage) -> QPainterPath:
        """Trace the mask into a region so the ants have an outline to walk."""
        bitmap = mask.convertToFormat(QImage.Format.Format_Mono,
                                      Qt.ImageConversionFlag.MonoOnly)
        from PyQt6.QtGui import QBitmap
        region = QRegion(QBitmap.fromImage(bitmap))
        path = QPainterPath()
        path.addRegion(region)
        return path

    def select_all(self):
        path = QPainterPath()
        path.addRect(0, 0, self.w, self.h)
        self.set_path(path, "replace", antialias=False)

    def invert(self):
        if self.mask is None:
            self.select_all()
            return
        self.mask = ops.invert(self.mask)
        full = QPainterPath()
        full.addRect(0, 0, self.w, self.h)
        self.path = full.subtracted(self.path) if self.path else full

    def feather(self, radius: float):
        if self.mask is None or radius <= 0:
            return
        self.mask = ops.gaussian_blur(self.mask, radius)
        self.feather_radius = radius

    def expand(self, pixels: int):
        if self.mask is None:
            return
        self.mask = ops.maximum(self.mask, max(1, pixels))
        self.path = self._path_from_mask(self.mask)

    def contract(self, pixels: int):
        if self.mask is None:
            return
        self.mask = ops.minimum(self.mask, max(1, pixels))
        self.path = self._path_from_mask(self.mask)

    def smooth(self, radius: int):
        if self.mask is None:
            return
        self.mask = ops.threshold(ops.gaussian_blur(self.mask, radius), 128)
        self.path = self._path_from_mask(self.mask)

    def border(self, width: int):
        if self.mask is None:
            return
        outer = ops.maximum(self.mask, max(1, width // 2 or 1))
        inner = ops.minimum(self.mask, max(1, width // 2 or 1))
        self.mask = ops.combine(outer, inner, lambda a, b: max(0, a - b))
        self.path = self._path_from_mask(self.mask)

    def bounds(self) -> QRect:
        if self.mask is None:
            return QRect(0, 0, self.w, self.h)
        if self.path is not None and not self.path.isEmpty():
            return self.path.boundingRect().toAlignedRect().intersected(
                QRect(0, 0, self.w, self.h))
        return QRect(0, 0, self.w, self.h)

    def contains(self, pos: QPoint) -> bool:
        if self.mask is None:
            return True
        if not (0 <= pos.x() < self.w and 0 <= pos.y() < self.h):
            return False
        return self.mask.pixelColor(pos).red() > 127

    def apply(self, original: QImage, modified: QImage) -> QImage:
        """Blend a processed image back through the mask."""
        if self.mask is None:
            return modified
        masked = alpha_multiply(modified, self.mask)
        out = original.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(out)
        p.drawImage(0, 0, masked)
        p.end()
        return out

    def copy(self) -> "Selection":
        s = Selection(self.w, self.h)
        s.mask = self.mask.copy() if self.mask else None
        s.path = QPainterPath(self.path) if self.path else None
        s.feather_radius = self.feather_radius
        return s


# --------------------------------------------------------------- history ---

@dataclass
class HistoryState:
    name: str
    layers: list
    active_index: int
    selection: Selection | None
    is_snapshot: bool = False


class History:
    """Snapshot history with a hard state cap, the way PS 7 does it -- and,
    like PS 7, taking a new action after stepping back throws away the future."""

    def __init__(self, doc, max_states=20):
        self.doc = doc
        self.max_states = max_states
        self.states: list[HistoryState] = []
        self.snapshots: list[HistoryState] = []
        self.index = -1

    def _capture(self, name, snapshot=False) -> HistoryState:
        return HistoryState(
            name,
            [l.copy() for l in self.doc.layers],
            self.doc.active_index,
            self.doc.selection.copy() if self.doc.selection else None,
            snapshot,
        )

    def record(self, name: str):
        if self.index < len(self.states) - 1:
            del self.states[self.index + 1:]
        self.states.append(self._capture(name))
        while len(self.states) > self.max_states:
            self.states.pop(0)
        self.index = len(self.states) - 1

    def take_snapshot(self, name=None):
        snap = self._capture(name or f"Snapshot {len(self.snapshots) + 1}", snapshot=True)
        self.snapshots.append(snap)
        return snap

    def can_undo(self) -> bool:
        return self.index > 0

    def can_redo(self) -> bool:
        return self.index < len(self.states) - 1

    def undo_name(self) -> str:
        return self.states[self.index].name if self.index >= 0 else ""

    def step_to(self, index: int):
        if not (0 <= index < len(self.states)):
            return
        self.index = index
        self._restore(self.states[index])

    def restore_snapshot(self, snap: HistoryState):
        self._restore(snap)
        self.record(f"Snapshot: {snap.name}")

    def _restore(self, state: HistoryState):
        self.doc.layers = [l.copy() for l in state.layers]
        self.doc.active_index = min(state.active_index, len(self.doc.layers) - 1)
        self.doc.selection = state.selection.copy() if state.selection else None
        self.doc.invalidate()

    def undo(self):
        if self.can_undo():
            self.step_to(self.index - 1)

    def redo(self):
        if self.can_redo():
            self.step_to(self.index + 1)

    def clear(self):
        self.states.clear()
        self.snapshots.clear()
        self.index = -1


# -------------------------------------------------------------- document ---

MODES = ["Bitmap", "Grayscale", "Duotone", "Indexed Color", "RGB Color",
         "CMYK Color", "Lab Color", "Multichannel"]


class Document:
    def __init__(self, width=560, height=380, resolution=72, mode="RGB Color",
                 background="white", name="Untitled-1"):
        self.width = width
        self.height = height
        self.resolution = resolution
        self.mode = mode
        self.name = name
        self.bits_per_channel = 8
        self.layers: list[Layer] = []
        self.active_index = 0
        self.selection: Selection | None = None
        self.alpha_channels: list[tuple[str, QImage]] = []   # saved selections
        self.paths: list[tuple[str, QPainterPath]] = []
        self.guides_h: list[int] = []
        self.guides_v: list[int] = []
        self.quick_mask = False
        self.dirty = False
        self._composite_cache: QImage | None = None
        self.history = History(self)

        base = self.blank_image()
        if background == "white":
            base.fill(Qt.GlobalColor.white)
        elif background != "transparent":
            base.fill(QColor(background))
        first = Layer("Background", base)
        first.locked_all = True
        first.locked_transparency = True
        self.layers.append(first)
        self.history.record("New")
        self.history.take_snapshot(name)

    # -- basics --------------------------------------------------------

    def blank_image(self) -> QImage:
        img = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        return img

    @property
    def active(self) -> Layer:
        self.active_index = max(0, min(self.active_index, len(self.layers) - 1))
        return self.layers[self.active_index]

    def invalidate(self):
        self._composite_cache = None

    def ensure_selection(self) -> Selection:
        if self.selection is None:
            self.selection = Selection(self.width, self.height)
        return self.selection

    def has_selection(self) -> bool:
        return self.selection is not None and not self.selection.is_empty()

    # -- compositing ---------------------------------------------------

    def composite(self) -> QImage:
        """Stack the layers onto transparency.

        Adjustment layers are applied where they sit rather than at the end,
        so they affect exactly the layers below them, and a clipped layer is
        masked by the alpha of the base layer of its clipping group -- both
        the way PS does it, and both visible the moment you use them.
        """
        if self._composite_cache is not None:
            return self._composite_cache
        result = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.transparent)
        clip_base: QImage | None = None
        for i, layer in enumerate(self.layers):
            if not layer.visible:
                continue
            if layer.kind == "adjustment":
                processed = apply_adjustment_layer(result, layer)
                if layer.clipping and clip_base is not None:
                    processed = _blend_through_alpha(result, processed, clip_base)
                result = blend_layer(result, processed, layer.blend, layer.opacity)
                continue
            img = self.rendered_layer(layer)
            if layer.clipping and clip_base is not None:
                img = alpha_multiply(img, alpha_as_mask(clip_base))
            else:
                clip_base = img
            result = blend_layer(result, img, layer.blend, layer.opacity)
        self._composite_cache = result
        return result

    def rendered_layer(self, layer: Layer) -> QImage:
        """Layer pixels with its mask and its live effects applied."""
        img = layer.image
        if layer.mask is not None and layer.mask_enabled:
            img = _apply_mask(img, layer.mask)
        if layer.has_style():
            from .layer_styles import render_style
            img = render_style(img, layer.style, layer.fill_opacity)
        elif layer.fill_opacity < 1.0:
            faded = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
            faded.fill(Qt.GlobalColor.transparent)
            p = QPainter(faded)
            p.setOpacity(layer.fill_opacity)
            p.drawImage(0, 0, img)
            p.end()
            img = faded
        return img

    def flattened(self, white_background=True) -> QImage:
        out = QImage(self.width, self.height, QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(Qt.GlobalColor.white if white_background else Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.drawImage(0, 0, self.composite())
        p.end()
        return out

    # -- layer ops -----------------------------------------------------

    def add_layer(self, layer: Layer, above=True):
        idx = self.active_index + 1 if above else self.active_index
        self.layers.insert(idx, layer)
        self.active_index = idx
        self.invalidate()

    def remove_active(self):
        if len(self.layers) <= 1:
            return False
        del self.layers[self.active_index]
        self.active_index = max(0, self.active_index - 1)
        self.invalidate()
        return True

    def merge_down(self) -> bool:
        i = self.active_index
        if i <= 0:
            return False
        upper, lower = self.layers[i], self.layers[i - 1]
        merged = lower.image.copy()
        merged = blend_layer(merged, self.rendered_layer(upper), upper.blend,
                             upper.opacity if upper.visible else 0.0)
        lower.image = merged
        lower.kind = "pixel"
        del self.layers[i]
        self.active_index = i - 1
        self.invalidate()
        return True

    def flatten(self):
        flat = self.flattened(white_background=True)
        bg = Layer("Background", flat)
        bg.locked_all = True
        self.layers = [bg]
        self.active_index = 0
        self.invalidate()

    def resize_canvas(self, new_w, new_h, anchor="center"):
        ox, oy = _anchor_offset(anchor, new_w - self.width, new_h - self.height)
        for layer in self.layers:
            img = QImage(new_w, new_h, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            p = QPainter(img)
            p.drawImage(ox, oy, layer.image)
            p.end()
            layer.image = img
            if layer.mask is not None:
                m = QImage(new_w, new_h, QImage.Format.Format_ARGB32_Premultiplied)
                m.fill(Qt.GlobalColor.white)
                p = QPainter(m)
                p.drawImage(ox, oy, layer.mask)
                p.end()
                layer.mask = m
        self.width, self.height = new_w, new_h
        if self.selection:
            self.selection = Selection(new_w, new_h)
        self.invalidate()

    def resize_image(self, new_w, new_h, smooth=True):
        mode = (Qt.TransformationMode.SmoothTransformation if smooth
                else Qt.TransformationMode.FastTransformation)
        for layer in self.layers:
            layer.image = layer.image.scaled(new_w, new_h,
                                             Qt.AspectRatioMode.IgnoreAspectRatio, mode)
            if layer.mask is not None:
                layer.mask = layer.mask.scaled(new_w, new_h,
                                               Qt.AspectRatioMode.IgnoreAspectRatio, mode)
        self.width, self.height = new_w, new_h
        if self.selection:
            self.selection = Selection(new_w, new_h)
        self.invalidate()

    def transform_all(self, fn):
        for layer in self.layers:
            layer.image = fn(layer.image)
            if layer.mask is not None:
                layer.mask = fn(layer.mask)
        self.width = self.layers[0].image.width()
        self.height = self.layers[0].image.height()
        if self.selection:
            self.selection = Selection(self.width, self.height)
        self.invalidate()

    def memory_size(self) -> int:
        return self.width * self.height * 4 * max(1, len(self.layers))


def _anchor_offset(anchor, dw, dh):
    xs = {"left": 0, "center": dw // 2, "right": dw}
    ys = {"top": 0, "center": dh // 2, "bottom": dh}
    if anchor == "center":
        return dw // 2, dh // 2
    parts = anchor.split("-")
    ax = xs.get(parts[-1], dw // 2)
    ay = ys.get(parts[0], dh // 2)
    return ax, ay


def mask_to_alpha(mask: QImage) -> QImage:
    """Greyscale mask -> premultiplied black whose alpha is the mask value.

    Drawn with DestinationIn this multiplies whatever it lands on, which is
    how masking stays a raster op instead of a per-pixel Python loop.
    """
    mb, w, h = ops.to_buf(mask)
    out = bytearray(w * h * 4)
    out[3::4] = ops.plane(mb, ops.R)
    return ops.from_buf(out, w, h)


def alpha_multiply(img: QImage, mask: QImage) -> QImage:
    out = img.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.drawImage(0, 0, mask_to_alpha(mask))
    p.end()
    return out


def _apply_mask(img: QImage, mask: QImage) -> QImage:
    return alpha_multiply(img, mask)


def alpha_as_mask(img: QImage) -> QImage:
    """Promote an image's alpha to a greyscale mask."""
    buf, w, h = ops.to_buf(img)
    a = ops.plane(buf, ops.A)
    out = bytearray(w * h * 4)
    out[0::4] = a
    out[1::4] = a
    out[2::4] = a
    out[3::4] = b"\xff" * (w * h)
    return ops.from_buf(out, w, h)


def _blend_through_alpha(base: QImage, modified: QImage, clip_source: QImage) -> QImage:
    return _blend_through_mask(base, modified, alpha_as_mask(clip_source))


_CHECKER = None


def checker_pixmap():
    """The grey checkerboard PS shows through transparency."""
    global _CHECKER
    if _CHECKER is None:
        from PyQt6.QtGui import QPixmap
        pm = QPixmap(16, 16)
        pm.fill(QColor("#ffffff"))
        p = QPainter(pm)
        p.fillRect(0, 0, 8, 8, QColor("#cccccc"))
        p.fillRect(8, 8, 8, 8, QColor("#cccccc"))
        p.end()
        _CHECKER = pm
    return _CHECKER


# ------------------------------------------------- adjustment layers ------

def apply_adjustment_layer(base: QImage, layer: Layer) -> QImage:
    adj = layer.adjustment or {}
    kind = adj.get("kind", "Levels")
    params = adj.get("params", {})
    out = _run_adjustment(base, kind, params)
    if layer.mask is not None and layer.mask_enabled:
        out = _blend_through_mask(base, out, layer.mask)
    return out


def _run_adjustment(img: QImage, kind: str, params: dict) -> QImage:
    if kind == "Levels":
        return ops.levels(img, params.get("in_black", 0), params.get("gamma", 1.0),
                          params.get("in_white", 255), params.get("out_black", 0),
                          params.get("out_white", 255), params.get("channel", "RGB"))
    if kind == "Curves":
        return ops.curves(img, params.get("points", [(0, 0), (255, 255)]),
                          params.get("channel", "RGB"))
    if kind == "Brightness/Contrast":
        return ops.brightness_contrast(img, params.get("brightness", 0),
                                       params.get("contrast", 0))
    if kind == "Hue/Saturation":
        return ops.hue_saturation(img, params.get("hue", 0), params.get("saturation", 0),
                                  params.get("lightness", 0), params.get("colorize", False))
    if kind == "Color Balance":
        return ops.color_balance(img, params.get("shadows", (0, 0, 0)),
                                 params.get("midtones", (0, 0, 0)),
                                 params.get("highlights", (0, 0, 0)))
    if kind == "Invert":
        return ops.invert(img)
    if kind == "Threshold":
        return ops.threshold(img, params.get("level", 128))
    if kind == "Posterize":
        return ops.posterize(img, params.get("levels", 4))
    if kind == "Channel Mixer":
        return ops.channel_mixer(img, params.get("matrix", [[100, 0, 0], [0, 100, 0], [0, 0, 100]]),
                                 params.get("constants", (0, 0, 0)),
                                 params.get("monochrome", False))
    if kind == "Gradient Map":
        return ops.gradient_map(img, params.get("stops", [(0, QColor("black")),
                                                          (1, QColor("white"))]))
    if kind == "Selective Color":
        return ops.selective_color(img, params.get("target", "Reds"),
                                   params.get("cmyk", (0, 0, 0, 0)))
    return img


def _blend_through_mask(base: QImage, modified: QImage, mask: QImage) -> QImage:
    out = base.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.drawImage(0, 0, alpha_multiply(modified, mask))
    p.end()
    return out
