"""Procedurally drawn PhotoChop tool icons.

Photoshop 7's toolbox glyphs are near-monochrome line art on the button face,
with a colour accent on only a handful of tools. These are drawn to a 16-unit
grid and scaled, so they stay crisp at the 20px the toolbox actually uses.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QPolygonF,
)

INK = "#1c1c1c"
_CACHE: dict = {}


def icon(name: str, size: int = 20) -> QIcon:
    key = (name, size)
    if key not in _CACHE:
        _CACHE[key] = QIcon(pixmap(name, size))
    return _CACHE[key]


def pixmap(name: str, size: int = 20) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 16.0, size / 16.0)
    fn = _GLYPHS.get(name)
    if fn:
        fn(p)
    p.end()
    return pm


def _pen(p, width=1.0, color=INK, cap=Qt.PenCapStyle.RoundCap, style=Qt.PenStyle.SolidLine):
    pen = QPen(QColor(color), width, style, cap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    return pen


def _fill(p, color=INK):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))


def _poly(*pts):
    return QPolygonF([QPointF(x, y) for x, y in pts])


# ------------------------------------------------------------- selection ---

def _marquee_rect(p):
    pen = _pen(p, 1.0)
    pen.setStyle(Qt.PenStyle.CustomDashLine)
    pen.setDashPattern([2, 2])
    p.setPen(pen)
    p.drawRect(QRectF(2.5, 3.5, 11, 9))


def _marquee_ellipse(p):
    pen = _pen(p, 1.0)
    pen.setStyle(Qt.PenStyle.CustomDashLine)
    pen.setDashPattern([2, 2])
    p.setPen(pen)
    p.drawEllipse(QRectF(2.0, 3.5, 12, 9))


def _marquee_row(p):
    _fill(p)
    p.drawRect(QRectF(1, 7, 14, 2))
    _pen(p, 0.8)
    p.drawLine(QPointF(1, 4), QPointF(15, 4))
    p.drawLine(QPointF(1, 12), QPointF(15, 12))


def _marquee_col(p):
    _fill(p)
    p.drawRect(QRectF(7, 1, 2, 14))
    _pen(p, 0.8)
    p.drawLine(QPointF(4, 1), QPointF(4, 15))
    p.drawLine(QPointF(12, 1), QPointF(12, 15))


def _move(p):
    _pen(p, 1.2)
    p.drawLine(QPointF(8, 2), QPointF(8, 14))
    p.drawLine(QPointF(2, 8), QPointF(14, 8))
    _fill(p)
    for pts in (((8, 1), (5.6, 4), (10.4, 4)), ((8, 15), (5.6, 12), (10.4, 12)),
                ((1, 8), (4, 5.6), (4, 10.4)), ((15, 8), (12, 5.6), (12, 10.4))):
        p.drawPolygon(_poly(*pts))


def _lasso(p):
    _pen(p, 1.2)
    path = QPainterPath(QPointF(4, 12))
    path.cubicTo(0.5, 8, 3, 2.5, 8, 2.5)
    path.cubicTo(13, 2.5, 15, 7, 11.5, 9.5)
    path.cubicTo(9, 11.2, 6.5, 10, 7.5, 12.5)
    p.drawPath(path)
    p.drawLine(QPointF(7.5, 12.5), QPointF(6.5, 15))


def _poly_lasso(p):
    _pen(p, 1.1)
    p.drawPolyline(_poly((2, 12), (3.5, 4), (9, 2.5), (13.5, 7), (10, 12), (5, 14.5)))
    _fill(p)
    for x, y in ((3.5, 4), (9, 2.5), (13.5, 7), (10, 12)):
        p.drawRect(QRectF(x - 1, y - 1, 2, 2))


def _magnetic_lasso(p):
    _lasso(p)
    _pen(p, 1.0, "#c02020")
    p.drawArc(QRectF(9, 8.5, 6, 6), 0, 180 * 16)
    _fill(p, "#c02020")
    p.drawRect(QRectF(9, 11.2, 1.8, 2.4))
    p.drawRect(QRectF(13.2, 11.2, 1.8, 2.4))


def _wand(p):
    _pen(p, 1.6)
    p.drawLine(QPointF(3, 13), QPointF(10, 6))
    _fill(p)
    p.drawPolygon(_poly((10.5, 5.5), (13, 3), (11.5, 6.5)))
    _pen(p, 0.9)
    for x, y, r in ((12.5, 8, 1.6), (8, 3, 1.3), (14, 12, 1.2)):
        p.drawLine(QPointF(x - r, y), QPointF(x + r, y))
        p.drawLine(QPointF(x, y - r), QPointF(x, y + r))


def _crop(p):
    _pen(p, 1.3)
    p.drawLine(QPointF(4, 1), QPointF(4, 12))
    p.drawLine(QPointF(1, 4), QPointF(12, 4))
    p.drawLine(QPointF(11, 4), QPointF(11, 15))
    p.drawLine(QPointF(4, 11), QPointF(15, 11))


def _slice(p):
    _pen(p, 1.0)
    p.drawRect(QRectF(1.5, 2.5, 13, 11))
    pen = _pen(p, 0.9)
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.drawLine(QPointF(8, 2.5), QPointF(8, 13.5))
    _fill(p, "#3a6ea5")
    p.drawRect(QRectF(1.5, 2.5, 3, 2.4))


def _slice_select(p):
    _slice(p)
    _fill(p)
    p.drawPolygon(_poly((9, 7), (9, 14), (11, 12), (12.5, 15), (14, 14), (12.5, 11), (15, 11)))


# ------------------------------------------------------------- retouching --

def _healing(p):
    _pen(p, 1.3)
    p.drawLine(QPointF(4, 12), QPointF(10.5, 5.5))
    _fill(p)
    p.drawEllipse(QRectF(9.5, 2.5, 5, 5))
    _pen(p, 1.0, "#ffffff")
    p.drawLine(QPointF(12, 3.8), QPointF(12, 6.2))
    p.drawLine(QPointF(10.8, 5), QPointF(13.2, 5))
    _fill(p)
    p.drawPolygon(_poly((2, 14.5), (3, 11), (5.5, 13.5)))


def _patch(p):
    _pen(p, 1.1)
    path = QPainterPath(QPointF(3, 9))
    path.cubicTo(2, 4, 7, 2, 9.5, 4)
    path.cubicTo(13, 6, 12, 12, 7, 13)
    path.cubicTo(4.5, 13.5, 3.5, 11.5, 3, 9)
    p.drawPath(path)
    pen = _pen(p, 0.9)
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    p.drawLine(QPointF(6, 3), QPointF(6, 13))


def _brush(p):
    _pen(p, 1.1)
    p.setBrush(QColor("#d8d8d8"))
    p.save()
    p.translate(8, 8)
    p.rotate(-45)
    p.drawRect(QRectF(-1.6, -6, 3.2, 7))
    _fill(p, INK)
    p.drawPolygon(_poly((-1.6, 1), (1.6, 1), (0.9, 5.5), (-0.9, 5.5)))
    p.restore()


def _pencil(p):
    p.save()
    p.translate(8, 8)
    p.rotate(-45)
    _pen(p, 0.9)
    p.setBrush(QColor("#f0c33c"))
    p.drawRect(QRectF(-1.8, -6.5, 3.6, 8.5))
    _fill(p, "#e8c495")
    p.drawPolygon(_poly((-1.8, 2), (1.8, 2), (0, 5.6)))
    _fill(p, INK)
    p.drawPolygon(_poly((-0.7, 4.2), (0.7, 4.2), (0, 5.6)))
    _fill(p, "#e07a90")
    p.drawRect(QRectF(-1.8, -6.5, 3.6, 1.6))
    p.restore()


def _clone_stamp(p):
    _fill(p)
    p.drawRect(QRectF(6.6, 5, 2.8, 6))
    p.drawPolygon(_poly((3.5, 4.6), (12.5, 4.6), (10.5, 2.4), (5.5, 2.4)))
    p.drawRect(QRectF(4.2, 11, 7.6, 2.2))


def _pattern_stamp(p):
    _clone_stamp(p)
    _pen(p, 0.8, "#ffffff")
    p.drawLine(QPointF(4.6, 12), QPointF(11.4, 12))


def _history_brush(p):
    _brush(p)
    _pen(p, 1.1, "#2a5aa8")
    p.drawArc(QRectF(8.5, 1.5, 6.5, 6.5), 40 * 16, 280 * 16)
    _fill(p, "#2a5aa8")
    p.drawPolygon(_poly((13.6, 1.2), (15.4, 3.6), (12.4, 3.8)))


def _art_history(p):
    _history_brush(p)
    _pen(p, 0.9, "#2a5aa8")
    p.drawArc(QRectF(1.5, 9, 5, 5), 0, 200 * 16)


def _eraser(p):
    p.save()
    p.translate(8, 8)
    p.rotate(-30)
    _pen(p, 0.9)
    p.setBrush(QColor("#f2f2f2"))
    p.drawRect(QRectF(-5.5, -3, 11, 6))
    p.setBrush(QColor("#c8c8c8"))
    p.drawRect(QRectF(0.5, -3, 5, 6))
    p.restore()


def _bg_eraser(p):
    _eraser(p)
    _pen(p, 0.9, "#c02020")
    p.drawLine(QPointF(2, 13.5), QPointF(14, 13.5))


def _magic_eraser(p):
    _eraser(p)
    _pen(p, 0.9, "#2a5aa8")
    for x, y in ((13, 3), (11, 6)):
        p.drawLine(QPointF(x - 1.4, y), QPointF(x + 1.4, y))
        p.drawLine(QPointF(x, y - 1.4), QPointF(x, y + 1.4))


def _gradient(p):
    g = QLinearGradient(2, 0, 14, 0)
    g.setColorAt(0, QColor("#1c1c1c"))
    g.setColorAt(1, QColor("#ffffff"))
    p.setPen(QPen(QColor(INK), 0.9))
    p.setBrush(QBrush(g))
    p.drawRect(QRectF(2, 4.5, 12, 7))


def _bucket(p):
    p.save()
    p.translate(7, 8)
    p.rotate(-30)
    _pen(p, 0.9)
    p.setBrush(QColor("#d0d0d0"))
    p.drawPolygon(_poly((-4, -3.5), (4, -3.5), (3, 3.5), (-3, 3.5)))
    p.drawLine(QPointF(-4, -3.5), QPointF(-6, -6))
    p.restore()
    _fill(p, "#2a5aa8")
    p.drawPolygon(_poly((12.5, 8), (14.6, 11.5), (12.5, 14), (10.4, 11.5)))


def _blur_tool(p):
    _fill(p, "#6a90c0")
    path = QPainterPath(QPointF(8, 2))
    path.cubicTo(12.5, 7, 13, 9, 11.5, 11.5)
    path.cubicTo(9.8, 14.2, 6.2, 14.2, 4.5, 11.5)
    path.cubicTo(3, 9, 3.5, 7, 8, 2)
    p.drawPath(path)


def _sharpen_tool(p):
    _pen(p, 1.1)
    p.setBrush(QColor("#d0d0d0"))
    p.drawPolygon(_poly((8, 1.5), (12.5, 13), (8, 10.5), (3.5, 13)))


def _smudge(p):
    _pen(p, 1.2)
    path = QPainterPath(QPointF(2, 13))
    path.cubicTo(5, 13, 4, 8, 7, 8)
    path.cubicTo(10, 8, 9, 4, 12, 4)
    p.drawPath(path)
    _fill(p)
    p.drawEllipse(QRectF(11, 2.4, 3.4, 3.4))


def _dodge(p):
    _pen(p, 1.3)
    p.drawEllipse(QRectF(3, 3, 7, 7))
    p.drawLine(QPointF(9, 9.5), QPointF(14, 14))


def _burn(p):
    _pen(p, 1.2)
    path = QPainterPath(QPointF(6, 14))
    path.cubicTo(2.5, 11, 5, 8, 7, 2)
    path.cubicTo(9, 7, 13.5, 9, 10.5, 13)
    p.drawPath(path)
    p.drawLine(QPointF(6, 14), QPointF(10.5, 13))


def _sponge(p):
    _pen(p, 1.0)
    p.setBrush(QColor("#e8e0c8"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(2.5, 4, 11, 8), 3, 3)
    p.drawPath(path)
    _fill(p, "#a09878")
    for x, y in ((5, 6.5), (8.5, 8.5), (11, 6), (6.5, 10), (10.5, 10)):
        p.drawEllipse(QPointF(x, y), 0.9, 0.9)


# ------------------------------------------------------------ vector/type --

def _path_select(p):
    _fill(p)
    p.drawPolygon(_poly((4, 1.5), (4, 13), (7, 10), (9, 14.5), (11, 13.5), (9, 9.5), (12.5, 9.5)))


def _direct_select(p):
    p.setPen(QPen(QColor(INK), 1.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolygon(_poly((4, 1.5), (4, 13), (7, 10), (9, 14.5), (11, 13.5), (9, 9.5), (12.5, 9.5)))


def _type_h(p):
    f = p.font()
    f.setPixelSize(13)
    f.setBold(True)
    f.setFamily("Times New Roman")
    p.setFont(f)
    p.setPen(QColor(INK))
    p.drawText(QRectF(0, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, "T")


def _type_v(p):
    p.save()
    p.translate(16, 0)
    p.rotate(90)
    _type_h(p)
    p.restore()


def _type_mask_h(p):
    pen = _pen(p, 0.9)
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    p.drawRect(QRectF(1, 2, 14, 12))
    _type_h(p)


def _type_mask_v(p):
    pen = _pen(p, 0.9)
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    p.drawRect(QRectF(1, 2, 14, 12))
    _type_v(p)


def _pen_tool(p):
    _fill(p)
    p.drawPolygon(_poly((7.5, 1.5), (11.5, 8), (10, 11), (5, 11), (3.5, 8)))
    _fill(p, "#ffffff")
    p.drawPolygon(_poly((7.5, 4), (9.6, 8), (5.4, 8)))
    _fill(p, INK)
    p.drawPolygon(_poly((5, 11.5), (10, 11.5), (7.5, 15)))


def _freeform_pen(p):
    _pen_tool(p)
    _pen(p, 0.9)
    path = QPainterPath(QPointF(1.5, 14))
    path.cubicTo(3, 11, 5, 15, 7, 13)
    p.drawPath(path)


def _add_anchor(p):
    _pen_tool(p)
    _pen(p, 1.2, "#2a7a2a")
    p.drawLine(QPointF(12.5, 11), QPointF(15.5, 11))
    p.drawLine(QPointF(14, 9.5), QPointF(14, 12.5))


def _del_anchor(p):
    _pen_tool(p)
    _pen(p, 1.2, "#c02020")
    p.drawLine(QPointF(12.5, 11), QPointF(15.5, 11))


def _convert_point(p):
    _pen(p, 1.0)
    path = QPainterPath(QPointF(2, 13))
    path.cubicTo(2, 5, 9, 3, 14, 3)
    p.drawPath(path)
    _fill(p)
    p.drawPolygon(_poly((2, 13), (5.5, 11.5), (4, 15)))
    p.drawRect(QRectF(12.8, 1.8, 2.4, 2.4))


def _shape_rect(p):
    _fill(p)
    p.drawRect(QRectF(2.5, 4, 11, 8))


def _shape_round(p):
    _fill(p)
    path = QPainterPath()
    path.addRoundedRect(QRectF(2.5, 4, 11, 8), 2.6, 2.6)
    p.drawPath(path)


def _shape_ellipse(p):
    _fill(p)
    p.drawEllipse(QRectF(2, 4, 12, 8))


def _shape_poly(p):
    _fill(p)
    pts = []
    for i in range(5):
        a = math.radians(-90 + i * 72)
        pts.append((8 + math.cos(a) * 6.4, 8 + math.sin(a) * 6.4))
    p.drawPolygon(_poly(*pts))


def _shape_line(p):
    _fill(p)
    p.save()
    p.translate(8, 8)
    p.rotate(-30)
    p.drawRect(QRectF(-7, -0.9, 14, 1.8))
    p.restore()


def _shape_custom(p):
    _fill(p)
    path = QPainterPath(QPointF(8, 14))
    path.cubicTo(1, 9, 2, 3, 5.5, 3)
    path.cubicTo(7, 3, 8, 4.4, 8, 5.4)
    path.cubicTo(8, 4.4, 9, 3, 10.5, 3)
    path.cubicTo(14, 3, 15, 9, 8, 14)
    p.drawPath(path)


def _notes(p):
    _pen(p, 0.9)
    p.setBrush(QColor("#fdf6c8"))
    p.drawRect(QRectF(2.5, 2.5, 11, 11))
    _pen(p, 0.8, "#8a8a6a")
    for y in (5.5, 7.5, 9.5):
        p.drawLine(QPointF(4.5, y), QPointF(11.5, y))


def _audio_note(p):
    _fill(p)
    p.drawEllipse(QRectF(3, 10, 4, 3.6))
    p.drawRect(QRectF(6.4, 3, 1.2, 9))
    p.drawPolygon(_poly((6.4, 3), (13, 1.5), (13, 4), (6.4, 5.5)))


def _eyedropper(p):
    p.save()
    p.translate(8, 8)
    p.rotate(45)
    _pen(p, 0.9)
    p.setBrush(QColor("#d8d8d8"))
    p.drawRect(QRectF(-1.6, -7, 3.2, 3))
    p.setBrush(QColor("#8fb8e0"))
    p.drawRect(QRectF(-1.1, -4, 2.2, 8))
    _fill(p, INK)
    p.drawPolygon(_poly((-1.1, 4), (1.1, 4), (0, 6.6)))
    p.restore()


def _color_sampler(p):
    _eyedropper(p)
    _pen(p, 0.9, "#c02020")
    p.drawLine(QPointF(10.5, 13), QPointF(15, 13))
    p.drawLine(QPointF(12.7, 10.8), QPointF(12.7, 15.2))


def _measure(p):
    _pen(p, 1.0)
    p.save()
    p.translate(8, 8)
    p.rotate(-20)
    p.drawRect(QRectF(-7, -2.4, 14, 4.8))
    for x in (-4.5, -2, 0.5, 3, 5.5):
        p.drawLine(QPointF(x, -2.4), QPointF(x, -0.4))
    p.restore()


def _hand(p):
    _pen(p, 0.9)
    p.setBrush(QColor("#f0e0c8"))
    path = QPainterPath(QPointF(4, 14))
    path.lineTo(3, 8.5)
    path.cubicTo(2.4, 6.6, 4.4, 6, 4.9, 7.6)
    path.lineTo(5.3, 8.6)
    path.lineTo(5.3, 3.2)
    path.cubicTo(5.3, 1.6, 7.3, 1.6, 7.3, 3.2)
    path.lineTo(7.3, 7.4)
    path.lineTo(7.8, 2.6)
    path.cubicTo(7.9, 1.1, 9.9, 1.3, 9.8, 2.8)
    path.lineTo(9.5, 7.5)
    path.lineTo(10.5, 3.6)
    path.cubicTo(10.8, 2.2, 12.7, 2.6, 12.4, 4)
    path.lineTo(11.6, 9.4)
    path.cubicTo(11.2, 12.6, 10.4, 14, 8.6, 14)
    path.closeSubpath()
    p.drawPath(path)


def _zoom(p):
    _pen(p, 1.4)
    p.drawEllipse(QRectF(2.5, 2.5, 8.5, 8.5))
    p.drawLine(QPointF(10.5, 10.5), QPointF(14.5, 14.5))
    _pen(p, 1.0)
    p.drawLine(QPointF(4.8, 6.75), QPointF(8.7, 6.75))
    p.drawLine(QPointF(6.75, 4.8), QPointF(6.75, 8.7))


# ---------------------------------------------------------------- chrome ---

def _quick_mask_off(p):
    _pen(p, 1.0)
    p.setBrush(QColor("#f4f4f4"))
    p.drawRect(QRectF(1.5, 3.5, 13, 9))
    _fill(p)
    p.drawEllipse(QRectF(5.5, 5.5, 5, 5))


def _quick_mask_on(p):
    _pen(p, 1.0)
    p.setBrush(QColor("#f4f4f4"))
    p.drawRect(QRectF(1.5, 3.5, 13, 9))
    _fill(p, "#e04040")
    p.drawRect(QRectF(1.5, 3.5, 13, 9))
    _fill(p, "#f4f4f4")
    p.drawEllipse(QRectF(5.5, 5.5, 5, 5))


def _screen_standard(p):
    _pen(p, 1.0)
    p.setBrush(QColor("#f4f4f4"))
    p.drawRect(QRectF(1.5, 2.5, 13, 11))
    _fill(p, "#7a7a7a")
    p.drawRect(QRectF(1.5, 2.5, 13, 2))


def _screen_full(p):
    _fill(p, "#7a7a7a")
    p.drawRect(QRectF(0.5, 0.5, 15, 15))
    _fill(p, "#f4f4f4")
    p.drawRect(QRectF(3.5, 4.5, 9, 7))


def _screen_full_menu(p):
    _screen_full(p)
    _fill(p, "#2a2a2a")
    p.drawRect(QRectF(0.5, 0.5, 15, 2))


def _imageready(p):
    g = QLinearGradient(0, 0, 0, 16)
    g.setColorAt(0, QColor("#4a86d8"))
    g.setColorAt(1, QColor("#1d4a8c"))
    p.setPen(QPen(QColor("#123056"), 1))
    p.setBrush(QBrush(g))
    p.drawRect(QRectF(1.5, 1.5, 13, 13))
    f = p.font()
    f.setPixelSize(9)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#ffffff"))
    p.drawText(QRectF(0, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, "IR")


def _sel_marks(p, mode):
    """The four selection-interaction buttons from the options bar."""
    pen = _pen(p, 1.0)
    pen.setStyle(Qt.PenStyle.CustomDashLine)
    pen.setDashPattern([2, 2])
    a = QRectF(2.5, 3.5, 8, 8)
    b = QRectF(6.5, 5.5, 8, 8)
    if mode == "new":
        p.setPen(pen)
        p.setBrush(QColor("#b8b8b8"))
        p.drawRect(QRectF(3.5, 3.5, 9, 9))
        return
    if mode == "add":
        p.setBrush(QColor("#b8b8b8"))
        p.setPen(pen)
        p.drawRect(a)
        p.drawRect(b)
    elif mode == "subtract":
        p.setBrush(QColor("#b8b8b8"))
        p.setPen(pen)
        p.drawRect(a)
        p.setBrush(QColor("#ffffff"))
        p.drawRect(b)
    else:  # intersect
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pen)
        p.drawRect(a)
        p.drawRect(b)
        p.setBrush(QColor("#b8b8b8"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(a.intersected(b))


def _lock_transparent(p):
    _fill(p, "#c8c8c8")
    p.drawRect(QRectF(2, 2, 6, 6))
    p.drawRect(QRectF(8, 8, 6, 6))
    _fill(p, "#f4f4f4")
    p.drawRect(QRectF(8, 2, 6, 6))
    p.drawRect(QRectF(2, 8, 6, 6))
    _pen(p, 0.8, "#707070")
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRectF(2, 2, 12, 12))


def _lock_pixels(p):
    p.save()
    p.translate(8, 8)
    p.rotate(-45)
    _pen(p, 0.8)
    p.setBrush(QColor("#d8d8d8"))
    p.drawRect(QRectF(-1.4, -6, 2.8, 7))
    _fill(p, INK)
    p.drawPolygon(_poly((-1.4, 1), (1.4, 1), (0.8, 5), (-0.8, 5)))
    p.restore()


def _lock_position(p):
    _pen(p, 1.0)
    p.drawLine(QPointF(8, 3), QPointF(8, 13))
    p.drawLine(QPointF(3, 8), QPointF(13, 8))
    _fill(p)
    for pts in (((8, 1.5), (6, 4), (10, 4)), ((8, 14.5), (6, 12), (10, 12)),
                ((1.5, 8), (4, 6), (4, 10)), ((14.5, 8), (12, 6), (12, 10))):
        p.drawPolygon(_poly(*pts))


def _lock_all(p):
    _pen(p, 1.2)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(4.5, 2, 7, 8), 0, 180 * 16)
    _fill(p, "#f0c33c")
    p.setPen(QPen(QColor(INK), 0.8))
    p.drawRect(QRectF(3.5, 7, 9, 7))
    _fill(p, INK)
    p.drawEllipse(QPointF(8, 10.5), 1.1, 1.1)


def _default_colors(p):
    p.setPen(QPen(QColor("#5a5a5a"), 0.8))
    p.setBrush(QColor("#ffffff"))
    p.drawRect(QRectF(5, 5, 9, 9))
    p.setBrush(QColor("#000000"))
    p.drawRect(QRectF(2, 2, 9, 9))


def _swap_colors(p):
    _pen(p, 1.1)
    p.drawLine(QPointF(3, 11), QPointF(3, 4))
    p.drawLine(QPointF(3, 4), QPointF(12, 4))
    _fill(p)
    p.drawPolygon(_poly((12, 1.5), (15, 4), (12, 6.5)))
    p.drawPolygon(_poly((0.5, 11), (5.5, 11), (3, 14.5)))


_GLYPHS = {
    "marquee_rect": _marquee_rect, "marquee_ellipse": _marquee_ellipse,
    "marquee_row": _marquee_row, "marquee_col": _marquee_col,
    "move": _move,
    "lasso": _lasso, "poly_lasso": _poly_lasso, "magnetic_lasso": _magnetic_lasso,
    "wand": _wand, "crop": _crop, "slice": _slice, "slice_select": _slice_select,
    "healing": _healing, "patch": _patch,
    "brush": _brush, "pencil": _pencil,
    "clone_stamp": _clone_stamp, "pattern_stamp": _pattern_stamp,
    "history_brush": _history_brush, "art_history": _art_history,
    "eraser": _eraser, "bg_eraser": _bg_eraser, "magic_eraser": _magic_eraser,
    "gradient": _gradient, "bucket": _bucket,
    "blur": _blur_tool, "sharpen": _sharpen_tool, "smudge": _smudge,
    "dodge": _dodge, "burn": _burn, "sponge": _sponge,
    "path_select": _path_select, "direct_select": _direct_select,
    "type_h": _type_h, "type_v": _type_v,
    "type_mask_h": _type_mask_h, "type_mask_v": _type_mask_v,
    "pen": _pen_tool, "freeform_pen": _freeform_pen,
    "add_anchor": _add_anchor, "del_anchor": _del_anchor, "convert_point": _convert_point,
    "shape_rect": _shape_rect, "shape_round": _shape_round, "shape_ellipse": _shape_ellipse,
    "shape_poly": _shape_poly, "shape_line": _shape_line, "shape_custom": _shape_custom,
    "notes": _notes, "audio_note": _audio_note,
    "eyedropper": _eyedropper, "color_sampler": _color_sampler, "measure": _measure,
    "hand": _hand, "zoom": _zoom,
    "quick_mask_off": _quick_mask_off, "quick_mask_on": _quick_mask_on,
    "screen_standard": _screen_standard, "screen_full": _screen_full,
    "screen_full_menu": _screen_full_menu, "imageready": _imageready,
    "default_colors": _default_colors, "swap_colors": _swap_colors,
    "lock_transparent": _lock_transparent, "lock_pixels": _lock_pixels,
    "lock_position": _lock_position, "lock_all": _lock_all,
    "sel_new": lambda p: _sel_marks(p, "new"),
    "sel_add": lambda p: _sel_marks(p, "add"),
    "sel_subtract": lambda p: _sel_marks(p, "subtract"),
    "sel_intersect": lambda p: _sel_marks(p, "intersect"),
}
