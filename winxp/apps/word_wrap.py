"""Word Wrap -- MacroHard Word never got told what to wrap text around, so it
guessed: upright letters, standing with real thickness and depth, arranged in
a ring in 3D space. We take a "photo" of the scene and paste that into the doc.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen, QPolygonF, QTransform,
)

CANVAS_SIZE = 560
RADIUS = 1.5
DIST = 5.0
PITCH_DEG = -18.0

TEXTURE_PIXEL_SIZE = 64     # glyph raster resolution -- also the em-square that world scale is anchored to
WORLD_PER_PIXEL = 0.55 / TEXTURE_PIXEL_SIZE   # world units per texture pixel
LETTER_THICKNESS = 0.05     # world units, front-to-back depth


def _glyph_image(ch: str, font: QFont, color: QColor):
    """Render `ch` cropped tight to its own ink -- no font-cell padding, no
    box for whitespace (returns None so callers skip it entirely)."""
    if ch.isspace():
        return None
    metrics = QFontMetrics(font)
    tight = metrics.tightBoundingRect(ch)
    if tight.isEmpty():
        return None
    pad = 1
    width_px = tight.width() + pad * 2
    height_px = tight.height() + pad * 2
    baseline_x = -tight.left() + pad
    baseline_y = -tight.top() + pad

    img = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(baseline_x, baseline_y, ch)
    p.end()
    return img, baseline_y, height_px - baseline_y


def render_word_wrap(text: str, font: QFont, color: QColor) -> QImage:
    """Rasterize `text` as upright, extruded letter cards standing on a ring."""
    chars = list(text)
    n = max(len(chars), 1)

    render_font = QFont(font)
    render_font.setPixelSize(TEXTURE_PIXEL_SIZE)

    image = QImage(CANVAS_SIZE, CANVAS_SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pitch = math.radians(PITCH_DEG)
    cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
    cx = cy = CANVAS_SIZE / 2
    proj_scale = CANVAS_SIZE * 0.30

    def project(x, y, z):
        y1 = y * cos_pitch - z * sin_pitch
        z1 = y * sin_pitch + z * cos_pitch
        depth = max(z1 + DIST, 0.1)
        f = DIST / depth
        return QPointF(cx + x * proj_scale * f, cy - y1 * proj_scale * f), depth

    # faint ring guide on the ground plane the letters stand on.
    guide = QPainterPath()
    steps = 96
    for i in range(steps + 1):
        theta = 2 * math.pi * i / steps
        pt, _ = project(RADIUS * math.cos(theta), 0.0, RADIUS * math.sin(theta))
        guide.moveTo(pt) if i == 0 else guide.lineTo(pt)
    painter.setPen(QPen(QColor(160, 160, 160, 140), 1, Qt.PenStyle.DashLine))
    painter.drawPath(guide)

    side_color = QColor(color).darker(170)
    letters = []
    for i, ch in enumerate(chars):
        theta = 2 * math.pi * i / n
        right = (-math.sin(theta), 0.0, math.cos(theta))
        up = (0.0, 1.0, 0.0)
        normal = (math.cos(theta), 0.0, math.sin(theta))
        base = (RADIUS * math.cos(theta), 0.0, RADIUS * math.sin(theta))

        glyph = _glyph_image(ch, render_font, color)
        if glyph is None:
            continue
        glyph_img, above_baseline_px, below_baseline_px = glyph
        half_w = (glyph_img.width() * WORLD_PER_PIXEL) / 2
        top_v = above_baseline_px * WORLD_PER_PIXEL
        bottom_v = -below_baseline_px * WORLD_PER_PIXEL
        corners_local = [(-half_w, top_v), (half_w, top_v), (half_w, bottom_v), (-half_w, bottom_v)]

        def world_point(u, v, t):
            return (
                base[0] + u * right[0] + v * up[0] + t * normal[0],
                base[1] + u * right[1] + v * up[1] + t * normal[1],
                base[2] + u * right[2] + v * up[2] + t * normal[2],
            )

        half_t = LETTER_THICKNESS / 2
        front3d = [world_point(u, v, -half_t) for u, v in corners_local]
        back3d = [world_point(u, v, half_t) for u, v in corners_local]

        front_proj = [project(*p) for p in front3d]
        back_proj = [project(*p) for p in back3d]
        front_pts = [p for p, _d in front_proj]
        back_pts = [p for p, _d in back_proj]
        avg_depth = sum(d for _p, d in front_proj + back_proj) / 8.0

        letters.append((avg_depth, glyph_img, front_pts, back_pts))

    letters.sort(key=lambda item: -item[0])

    for _depth, glyph_img, front_pts, back_pts in letters:
        for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
            wall = QPainterPath()
            wall.moveTo(front_pts[a])
            wall.lineTo(front_pts[b])
            wall.lineTo(back_pts[b])
            wall.lineTo(back_pts[a])
            wall.closeSubpath()
            painter.setPen(QPen(side_color.darker(110), 1))
            painter.setBrush(side_color)
            painter.drawPath(wall)

        src_quad = QPolygonF([
            QPointF(0, 0), QPointF(glyph_img.width(), 0),
            QPointF(glyph_img.width(), glyph_img.height()), QPointF(0, glyph_img.height()),
        ])
        dst_quad = QPolygonF(front_pts)
        transform = QTransform()
        if QTransform.quadToQuad(src_quad, dst_quad, transform):
            painter.save()
            painter.setTransform(transform, True)
            painter.drawImage(0, 0, glyph_img)
            painter.restore()

    painter.end()
    return image
