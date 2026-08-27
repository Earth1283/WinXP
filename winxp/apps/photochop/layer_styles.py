"""Layer effects -- the Photoshop 7 "Blending Options" set, rendered live.

Effects are never baked into the layer's pixels: render_style() runs on every
composite so turning an effect off puts the layer back exactly as it was.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPen

from . import imageops as ops

# Drawing order matches the real Effects list: things behind the layer first,
# then the layer, then everything that sits on top of it.
STYLE_ORDER = [
    "Drop Shadow", "Outer Glow", "_LAYER_", "Inner Shadow", "Inner Glow",
    "Satin", "Color Overlay", "Gradient Overlay", "Pattern Overlay",
    "Bevel and Emboss", "Stroke",
]


def _blank(img: QImage) -> QImage:
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    return out


def silhouette(img: QImage, color: QColor) -> QImage:
    """A flat-coloured copy of the layer's alpha."""
    out = _blank(img)
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QColor(color))
    p.end()
    return out


def alpha_as_grey(img: QImage) -> QImage:
    """Alpha channel promoted to an opaque greyscale image."""
    buf, w, h = ops.to_buf(img)
    a = ops.plane(buf, ops.A)
    out = bytearray(w * h * 4)
    out[0::4] = a
    out[1::4] = a
    out[2::4] = a
    out[3::4] = b"\xff" * (w * h)
    return ops.from_buf(out, w, h)


def grey_as_alpha(grey: QImage, color: QColor) -> QImage:
    """Greyscale -> a coloured image whose alpha is that grey."""
    buf, w, h = ops.to_buf(grey)
    lum = ops.plane(buf, ops.R)
    out = bytearray(w * h * 4)
    out[0::4] = bytes(color.blue() * v // 255 for v in lum)
    out[1::4] = bytes(color.green() * v // 255 for v in lum)
    out[2::4] = bytes(color.red() * v // 255 for v in lum)
    out[3::4] = lum
    return ops.from_buf(out, w, h)


def _angle_offset(angle, distance):
    rad = math.radians(angle)
    return math.cos(rad) * distance, -math.sin(rad) * distance


def _clip_to_layer(effect: QImage, layer: QImage) -> QImage:
    """Keep only the part of an effect that lands on the layer itself."""
    out = effect.copy()
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.drawImage(0, 0, layer)
    p.end()
    return out


def _knockout(effect: QImage, layer: QImage) -> QImage:
    """Remove the part of an effect the layer would cover (outer glow etc.)."""
    out = effect.copy()
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
    p.drawImage(0, 0, layer)
    p.end()
    return out


# --------------------------------------------------------------- effects ---

def drop_shadow(layer: QImage, cfg) -> QImage:
    dx, dy = _angle_offset(cfg["angle"], cfg["distance"])
    sil = silhouette(layer, QColor(cfg["color"]))
    if cfg.get("spread"):
        sil = ops.maximum(sil, max(1, int(cfg["spread"] / 25)))
    blurred = ops.gaussian_blur(sil, cfg["size"]) if cfg["size"] else sil
    out = _blank(layer)
    p = QPainter(out)
    p.setOpacity(cfg["opacity"] / 100.0)
    p.drawImage(QPointF(dx, dy), blurred)
    p.end()
    return _knockout(out, layer)


def outer_glow(layer: QImage, cfg) -> QImage:
    sil = silhouette(layer, QColor(cfg["color"]))
    if cfg.get("spread"):
        sil = ops.maximum(sil, max(1, int(cfg["spread"] / 20)))
    glow = ops.gaussian_blur(sil, max(1.0, cfg["size"]))
    out = _blank(layer)
    p = QPainter(out)
    p.setOpacity(cfg["opacity"] / 100.0)
    # a couple of passes so the glow reads as a glow and not a soft shadow
    for _ in range(2):
        p.drawImage(0, 0, glow)
    p.end()
    return _knockout(out, layer)


def inner_shadow(layer: QImage, cfg) -> QImage:
    dx, dy = _angle_offset(cfg["angle"], cfg["distance"])
    grey = alpha_as_grey(layer)
    inverted = ops.invert(grey)
    shifted = ops.offset(inverted, int(dx), int(dy), wrap=False)
    soft = ops.gaussian_blur(shifted, max(0.5, cfg["size"]))
    shade = grey_as_alpha(soft, QColor(cfg["color"]))
    out = _blank(layer)
    p = QPainter(out)
    p.setOpacity(cfg["opacity"] / 100.0)
    p.drawImage(0, 0, shade)
    p.end()
    return _clip_to_layer(out, layer)


def inner_glow(layer: QImage, cfg) -> QImage:
    grey = alpha_as_grey(layer)
    edge = ops.combine(grey, ops.minimum(grey, max(1, int(cfg["size"] / 2) or 1)),
                       lambda a, b: max(0, a - b))
    soft = ops.gaussian_blur(edge, max(0.5, cfg["size"] / 2))
    glow = grey_as_alpha(soft, QColor(cfg["color"]))
    out = _blank(layer)
    p = QPainter(out)
    p.setOpacity(cfg["opacity"] / 100.0)
    p.drawImage(0, 0, glow)
    p.end()
    return _clip_to_layer(out, layer)


def bevel_emboss(layer: QImage, cfg) -> QImage:
    """Emboss the alpha channel, then split the result into a highlight pass
    and a shadow pass -- which is all Bevel and Emboss has ever been."""
    grey = alpha_as_grey(layer)
    soft = ops.gaussian_blur(grey, max(1.0, cfg["size"] / 2))
    embossed = ops.emboss(soft, cfg["angle"], max(1, int(cfg["size"] / 2)), cfg["depth"])
    if cfg.get("soften"):
        embossed = ops.gaussian_blur(embossed, cfg["soften"])
    up = cfg.get("direction", "Up") == "Up"
    hi_lut = [min(255, max(0, (i - 128) * 2)) for i in range(256)]
    lo_lut = [min(255, max(0, (128 - i) * 2)) for i in range(256)]
    if not up:
        hi_lut, lo_lut = lo_lut, hi_lut
    highlight = grey_as_alpha(ops.apply_lut(embossed, hi_lut), QColor("white"))
    shadow = grey_as_alpha(ops.apply_lut(embossed, lo_lut), QColor("black"))
    out = _blank(layer)
    p = QPainter(out)
    p.setOpacity(0.75)
    p.drawImage(0, 0, shadow)
    p.drawImage(0, 0, highlight)
    p.end()
    style = cfg.get("style", "Inner Bevel")
    if style in ("Inner Bevel", "Emboss", "Pillow Emboss"):
        return _clip_to_layer(out, layer)
    return out


def satin(layer: QImage, cfg) -> QImage:
    dx, dy = _angle_offset(cfg["angle"], cfg["distance"])
    grey = alpha_as_grey(layer)
    a = ops.offset(grey, int(dx), int(dy), wrap=False)
    b = ops.offset(grey, int(-dx), int(-dy), wrap=False)
    mixed = ops.combine(a, b, lambda x, y: abs(x - y))
    if cfg.get("invert"):
        mixed = ops.invert(mixed)
    mixed = ops.gaussian_blur(mixed, max(0.5, cfg["size"] / 2))
    tinted = grey_as_alpha(mixed, QColor(cfg["color"]))
    out = _blank(layer)
    p = QPainter(out)
    p.setOpacity(cfg["opacity"] / 100.0)
    p.drawImage(0, 0, tinted)
    p.end()
    return _clip_to_layer(out, layer)


def color_overlay(layer: QImage, cfg) -> QImage:
    out = silhouette(layer, QColor(cfg["color"]))
    faded = _blank(layer)
    p = QPainter(faded)
    p.setOpacity(cfg["opacity"] / 100.0)
    p.drawImage(0, 0, out)
    p.end()
    return faded


def gradient_overlay(layer: QImage, cfg) -> QImage:
    w, h = layer.width(), layer.height()
    fill = _blank(layer)
    p = QPainter(fill)
    rad = math.radians(cfg.get("angle", 90))
    cx, cy = w / 2, h / 2
    ext = max(w, h)
    g = QLinearGradient(cx - math.cos(rad) * ext / 2, cy + math.sin(rad) * ext / 2,
                        cx + math.cos(rad) * ext / 2, cy - math.sin(rad) * ext / 2)
    g.setColorAt(0.0, QColor(cfg["start"]))
    g.setColorAt(1.0, QColor(cfg["end"]))
    p.setOpacity(cfg["opacity"] / 100.0)
    p.fillRect(fill.rect(), QBrush(g))
    p.end()
    return _clip_to_layer(fill, layer)


def _pattern_tile(name: str) -> QImage:
    tile = QImage(16, 16, QImage.Format.Format_ARGB32_Premultiplied)
    tile.fill(QColor("#ffffff"))
    p = QPainter(tile)
    if name == "Checkerboard":
        p.fillRect(0, 0, 8, 8, QColor("#808080"))
        p.fillRect(8, 8, 8, 8, QColor("#808080"))
    elif name == "Diagonal Lines":
        p.setPen(QPen(QColor("#909090"), 2))
        for i in range(-16, 32, 6):
            p.drawLine(i, 0, i + 16, 16)
    elif name == "Bubbles":
        p.setPen(QPen(QColor("#a0c0e0"), 1))
        p.drawEllipse(QRectF(2, 2, 7, 7))
        p.drawEllipse(QRectF(9, 9, 5, 5))
    else:  # Woven
        p.setPen(QPen(QColor("#b0a080"), 3))
        p.drawLine(0, 4, 16, 4)
        p.drawLine(4, 0, 4, 16)
    p.end()
    return tile


def pattern_overlay(layer: QImage, cfg) -> QImage:
    from PyQt6.QtGui import QPixmap
    tile = _pattern_tile(cfg.get("pattern", "Checkerboard"))
    scale = max(10, cfg.get("scale", 100)) / 100.0
    if scale != 1.0:
        tile = tile.scaled(max(2, int(16 * scale)), max(2, int(16 * scale)))
    fill = _blank(layer)
    p = QPainter(fill)
    p.setOpacity(cfg["opacity"] / 100.0)
    p.drawTiledPixmap(fill.rect(), QPixmap.fromImage(tile))
    p.end()
    return _clip_to_layer(fill, layer)


def stroke(layer: QImage, cfg) -> QImage:
    size = max(1, int(cfg["size"]))
    grey = alpha_as_grey(layer)
    position = cfg.get("position", "Outside")
    if position == "Outside":
        band = ops.combine(ops.maximum(grey, size), grey, lambda a, b: max(0, a - b))
    elif position == "Inside":
        band = ops.combine(grey, ops.minimum(grey, size), lambda a, b: max(0, a - b))
    else:  # Center
        half = max(1, size // 2)
        band = ops.combine(ops.maximum(grey, half), ops.minimum(grey, half),
                           lambda a, b: max(0, a - b))
    coloured = grey_as_alpha(band, QColor(cfg["color"]))
    out = _blank(layer)
    p = QPainter(out)
    p.setOpacity(cfg.get("opacity", 100) / 100.0)
    p.drawImage(0, 0, coloured)
    p.end()
    return out


_RENDERERS = {
    "Drop Shadow": drop_shadow,
    "Outer Glow": outer_glow,
    "Inner Shadow": inner_shadow,
    "Inner Glow": inner_glow,
    "Bevel and Emboss": bevel_emboss,
    "Satin": satin,
    "Color Overlay": color_overlay,
    "Gradient Overlay": gradient_overlay,
    "Pattern Overlay": pattern_overlay,
    "Stroke": stroke,
}


def render_style(layer: QImage, style: dict, fill_opacity: float = 1.0) -> QImage:
    out = _blank(layer)
    p = QPainter(out)
    for name in STYLE_ORDER:
        if name == "_LAYER_":
            p.setOpacity(fill_opacity)
            p.drawImage(0, 0, layer)
            p.setOpacity(1.0)
            continue
        cfg = style.get(name)
        if not cfg or not cfg.get("enabled"):
            continue
        p.drawImage(0, 0, _RENDERERS[name](layer, cfg))
    p.end()
    return out
