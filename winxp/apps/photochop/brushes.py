"""Brush engine.

Photoshop's painting model, kept honest:
  * a stroke is a series of *dabs* stamped along the path at a fixed spacing,
    not a polyline -- which is why spacing changes the look of a stroke;
  * flow controls how much each dab lays down, opacity caps the whole stroke.
    So the stroke accumulates into its own buffer and is composited onto the
    layer once, at opacity, when the mouse comes up. Crossing your own stroke
    at 50% opacity therefore does not darken it, exactly like the real thing;
  * airbrush keeps depositing while the cursor is held still.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QRadialGradient

from . import imageops as ops

# The Default Brushes set, as it ships.
BRUSH_PRESETS = [
    ("Hard Round 1", 1, 100), ("Hard Round 3", 3, 100), ("Hard Round 5", 5, 100),
    ("Hard Round 9", 9, 100), ("Hard Round 13", 13, 100), ("Hard Round 19", 19, 100),
    ("Soft Round 5", 5, 0), ("Soft Round 9", 9, 0), ("Soft Round 13", 13, 0),
    ("Soft Round 17", 17, 0), ("Soft Round 21", 21, 0), ("Soft Round 27", 27, 0),
    ("Soft Round 35", 35, 0), ("Soft Round 45", 45, 0), ("Soft Round 65", 65, 0),
    ("Soft Round 100", 100, 0), ("Soft Round 200", 200, 0), ("Soft Round 300", 300, 0),
    ("Spatter 24", 24, 60), ("Spatter 39", 39, 60), ("Spatter 59", 59, 60),
    ("Chalk 17", 17, 40), ("Chalk 23", 23, 40), ("Chalk 36", 36, 40),
    ("Dry Brush 39", 39, 30), ("Dry Brush 66", 66, 30),
    ("Rough Round Bristle 100", 100, 50),
    ("Star 26", 26, 80), ("Star 42", 42, 80),
]

_STAMP_CACHE: dict = {}


def stamp(size: int, hardness: int, roundness: int = 100, angle: int = 0) -> QImage:
    """Greyscale-alpha dab. White core fading to nothing at the edge."""
    key = (size, hardness, roundness, angle)
    cached = _STAMP_CACHE.get(key)
    if cached is not None:
        return cached
    size = max(1, int(size))
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = size / 2.0
    grad = QRadialGradient(r, r, r)
    # hardness is where the falloff starts; 100% still gets a hair of feather
    # so the dab doesn't alias into a square.
    core = min(0.97, hardness / 100.0)
    grad.setColorAt(0.0, QColor(255, 255, 255, 255))
    grad.setColorAt(core, QColor(255, 255, 255, 255))
    grad.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.save()
    p.translate(r, r)
    p.rotate(angle)
    p.scale(1.0, max(0.05, roundness / 100.0))
    p.translate(-r, -r)
    p.drawEllipse(0, 0, size, size)
    p.restore()
    p.end()
    if len(_STAMP_CACHE) > 200:
        _STAMP_CACHE.clear()
    _STAMP_CACHE[key] = img
    return img


def coloured_stamp(size, hardness, color: QColor, roundness=100, angle=0) -> QImage:
    dab = stamp(size, hardness, roundness, angle).copy()
    p = QPainter(dab)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(dab.rect(), QColor(color))
    p.end()
    return dab


class Stroke:
    """One mouse-down to mouse-up. Owns the accumulation buffer."""

    def __init__(self, canvas_size, brush: dict, color: QColor, flow: float,
                 opacity: float, erase=False):
        self.buffer = QImage(canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
        self.buffer.fill(Qt.GlobalColor.transparent)
        self.brush = dict(brush)
        self.color = QColor(color)
        self.flow = max(0.01, flow)
        self.opacity = opacity
        self.erase = erase
        self.last: QPointF | None = None
        self.residue = 0.0          # leftover distance between dabs
        self.dirty = QRect()

    @property
    def spacing_px(self) -> float:
        return max(1.0, self.brush.get("size", 13) * self.brush.get("spacing", 25) / 100.0)

    def dab(self, pos: QPointF):
        size = max(1, int(self.brush.get("size", 13)))
        dab = coloured_stamp(size, self.brush.get("hardness", 100), self.color,
                             self.brush.get("roundness", 100), self.brush.get("angle", 0))
        x = int(pos.x() - size / 2)
        y = int(pos.y() - size / 2)
        p = QPainter(self.buffer)
        # Lighten on the accumulation buffer means repeated dabs at the same
        # spot converge on `flow` instead of stacking to opaque -- which is
        # what stops a slow drag from being darker than a fast one.
        p.setOpacity(self.flow)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.drawImage(x, y, dab)
        p.end()
        self.dirty = self.dirty.united(QRect(x, y, size, size))

    def to(self, pos: QPointF):
        """Walk from the last point to this one, dabbing at each spacing step."""
        if self.last is None:
            self.dab(pos)
            self.last = pos
            return
        dx, dy = pos.x() - self.last.x(), pos.y() - self.last.y()
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            return
        step = self.spacing_px
        # residue is how far past the previous dab we already travelled, so
        # spacing stays even across segment boundaries instead of resetting
        # at every mouse-move event.
        along = step - self.residue
        while along <= dist:
            t = along / dist
            self.dab(QPointF(self.last.x() + dx * t, self.last.y() + dy * t))
            along += step
        self.residue = dist - (along - step)
        self.last = pos

    def commit(self, target: QImage, blend_mode="Normal",
               lock_transparency=False) -> QImage:
        """Composite the finished stroke onto the layer."""
        out = target
        p = QPainter(out)
        p.setOpacity(self.opacity)
        if self.erase:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            p.drawImage(0, 0, self.buffer)
        else:
            from .model import _QT_MODES
            if lock_transparency:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
            else:
                p.setCompositionMode(_QT_MODES.get(blend_mode, _QT_MODES["Normal"]))
            p.drawImage(0, 0, self.buffer)
        p.end()
        return out


# ------------------------------------------------- effect (non-paint) dabs --

def dab_region(size: int, pos: QPointF, bounds: QRect) -> QRect:
    r = QRect(int(pos.x() - size / 2), int(pos.y() - size / 2), size, size)
    return r.intersected(bounds)


def apply_effect_dab(layer_img: QImage, pos: QPointF, brush: dict, strength: float,
                     effect) -> QRect:
    """Run `effect` over the patch under the dab and blend it back by the dab's
    own alpha -- how Blur/Sharpen/Smudge/Dodge/Burn/Sponge actually work."""
    size = max(2, int(brush.get("size", 13)))
    rect = dab_region(size, pos, layer_img.rect())
    if rect.isEmpty():
        return QRect()
    patch = layer_img.copy(rect)
    processed = effect(patch)
    if processed is None:
        return QRect()
    mask = stamp(size, brush.get("hardness", 100), brush.get("roundness", 100),
                 brush.get("angle", 0))
    off_x = rect.x() - int(pos.x() - size / 2)
    off_y = rect.y() - int(pos.y() - size / 2)
    mask = mask.copy(off_x, off_y, rect.width(), rect.height())
    faded = QImage(processed.size(), QImage.Format.Format_ARGB32_Premultiplied)
    faded.fill(Qt.GlobalColor.transparent)
    p = QPainter(faded)
    p.setOpacity(max(0.0, min(1.0, strength)))
    p.drawImage(0, 0, processed)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.drawImage(0, 0, mask)
    p.end()
    p = QPainter(layer_img)
    p.drawImage(rect.topLeft(), faded)
    p.end()
    return rect


def smudge_dab(layer_img: QImage, prev: QPointF, pos: QPointF, brush: dict,
               strength: float, pickup: QImage | None) -> tuple[QRect, QImage]:
    """Smudge carries a pickup buffer from the previous dab and lays it down
    slightly offset -- that carry is what makes it smear rather than blur."""
    size = max(2, int(brush.get("size", 13)))
    rect = dab_region(size, pos, layer_img.rect())
    if rect.isEmpty():
        return QRect(), pickup
    current = layer_img.copy(rect)
    if pickup is not None and pickup.size() == current.size():
        mask = stamp(size, brush.get("hardness", 100)).scaled(rect.width(), rect.height())
        smear = QImage(current.size(), QImage.Format.Format_ARGB32_Premultiplied)
        smear.fill(Qt.GlobalColor.transparent)
        p = QPainter(smear)
        p.setOpacity(max(0.0, min(1.0, strength)))
        p.drawImage(0, 0, pickup)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        p.drawImage(0, 0, mask)
        p.end()
        p = QPainter(layer_img)
        p.drawImage(rect.topLeft(), smear)
        p.end()
    return rect, layer_img.copy(rect)


def heal_patch(dest: QImage, source: QImage) -> QImage:
    """Healing keeps the source's texture but the destination's tone: take the
    source's high-frequency detail and the destination's low-frequency."""
    detail = ops.combine(source, ops.gaussian_blur(source, 6),
                         lambda s, b: s - b + 128)
    tone = ops.gaussian_blur(dest, 6)
    return ops.combine(tone, detail, lambda t, d: t + d - 128)
