"""Procedurally drawn MacroHard Word toolbar icons.

Word 2003's toolbars are the last generation of the 16x16 "Office XP" glyph
set: flat colour blocks with a single dark outline, a white page as the
recurring motif, and exactly one saturated accent per button. Everything is
drawn to a 16-unit grid and scaled, so the same source works for the 16px
toolbars and the 24px dialog headers.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
)

INK = "#3b3b3b"
PAGE = "#ffffff"
PAGE_EDGE = "#8a8a8a"
TEXT_LINE = "#8f9dae"
OFFICE_BLUE = "#3a5f9e"
OFFICE_YELLOW = "#f5c34a"
OFFICE_RED = "#c0392b"
OFFICE_GREEN = "#4a8b3a"

_CACHE: dict = {}


def icon(name: str, size: int = 16) -> QIcon:
    key = (name, size)
    if key not in _CACHE:
        _CACHE[key] = QIcon(pixmap(name, size))
    return _CACHE[key]


def pixmap(name: str, size: int = 16) -> QPixmap:
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


# ------------------------------------------------------------- primitives ---

def _pen(p, width=1.0, color=INK, cap=Qt.PenCapStyle.RoundCap):
    p.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine, cap,
                  Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _fill(p, color, outline=None, width=1.0):
    p.setBrush(QColor(color))
    if outline:
        p.setPen(QPen(QColor(outline), width))
    else:
        p.setPen(Qt.PenStyle.NoPen)


def _poly(*pts):
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _grad(x1, y1, x2, y2, c1, c2):
    g = QLinearGradient(x1, y1, x2, y2)
    g.setColorAt(0, QColor(c1))
    g.setColorAt(1, QColor(c2))
    return g


def _page(p, x=2.5, y=1.5, w=10, h=13, fold=3.5):
    """The white sheet with a dog-eared corner that half of Word's icons use."""
    path = QPainterPath()
    path.moveTo(x, y)
    path.lineTo(x + w - fold, y)
    path.lineTo(x + w, y + fold)
    path.lineTo(x + w, y + h)
    path.lineTo(x, y + h)
    path.closeSubpath()
    p.setBrush(QColor(PAGE))
    p.setPen(QPen(QColor(PAGE_EDGE), 1))
    p.drawPath(path)
    p.setPen(QPen(QColor(PAGE_EDGE), 0.8))
    p.drawPolyline(_poly((x + w - fold, y), (x + w - fold, y + fold), (x + w, y + fold)))


def _text_lines(p, x, y, w, count=4, gap=2.0, color=TEXT_LINE, short_last=True):
    p.setPen(QPen(QColor(color), 1))
    for i in range(count):
        run = w * 0.6 if (short_last and i == count - 1) else w
        p.drawLine(QPointF(x, y + i * gap), QPointF(x + run, y + i * gap))


# ------------------------------------------------------------------- file ---

def _new(p):
    _page(p)
    _text_lines(p, 4.5, 6.0, 6.0, 4)


def _open(p):
    _fill(p, "#d7a13c", "#8a6420")
    p.drawPolygon(_poly((1, 4), (6.5, 4), (7.8, 5.6), (14.5, 5.6), (14.5, 13), (1, 13)))
    p.setBrush(_grad(0, 6, 0, 13, "#ffe9a8", "#e8b64c"))
    p.setPen(QPen(QColor("#8a6420"), 1))
    p.drawPolygon(_poly((3.2, 13), (15, 13), (15.5, 6.8), (4.6, 6.8)))


def _save(p):
    # 3.5" floppy: dark blue shell, white shutter, pale label
    _fill(p, "#3f6fb5", "#22406e")
    p.drawRoundedRect(QRectF(1.5, 1.5, 13, 13), 1.0, 1.0)
    _fill(p, "#e8ecf2", "#5f7fa8")
    p.drawRect(QRectF(4.5, 2, 7, 4.5))
    _fill(p, "#2a4a7c")
    p.drawRect(QRectF(9, 2.5, 1.8, 3.5))
    _fill(p, "#f4f2e6", "#8a8f96")
    p.drawRect(QRectF(3.5, 8.5, 9, 6))


def _print(p):
    _fill(p, PAGE, PAGE_EDGE)
    p.drawRect(QRectF(4, 1.5, 8, 4))
    p.setBrush(_grad(0, 6, 0, 12, "#d9dde3", "#9aa2ad"))
    p.setPen(QPen(QColor("#5a616b"), 1))
    p.drawRoundedRect(QRectF(1.5, 5.5, 13, 6), 1.0, 1.0)
    _fill(p, "#3a5f9e")
    p.drawRect(QRectF(11.5, 7, 2, 1.4))
    _fill(p, PAGE, PAGE_EDGE)
    p.drawRect(QRectF(4, 10.5, 8, 4.5))
    _text_lines(p, 5.2, 12.0, 5.6, 2, 1.8)


def _print_preview(p):
    _page(p, 1.5, 1.0, 9.5, 12, 3)
    _text_lines(p, 3.2, 4.5, 5.6, 4)
    _pen(p, 1.4, "#2b4a7a")
    p.drawEllipse(QRectF(7.5, 6.5, 6.5, 6.5))
    _pen(p, 1.8, "#2b4a7a")
    p.drawLine(QPointF(13.2, 12.2), QPointF(15.4, 14.6))


def _mail(p):
    _fill(p, "#f6f4ec", "#6d7480")
    p.drawRect(QRectF(1, 3.5, 14, 9.5))
    _pen(p, 1.0, "#6d7480")
    p.drawPolyline(_poly((1, 3.5), (8, 9), (15, 3.5)))
    p.drawLine(QPointF(1, 13), QPointF(6, 8.4))
    p.drawLine(QPointF(15, 13), QPointF(10, 8.4))


# ------------------------------------------------------------------- edit ---

def _cut(p):
    _pen(p, 1.3, "#5a6470")
    p.drawLine(QPointF(4.5, 1.5), QPointF(10, 10.5))
    p.drawLine(QPointF(11.5, 1.5), QPointF(6, 10.5))
    _fill(p, "#e6eaf0", "#5a6470")
    p.drawEllipse(QRectF(3, 10.5, 4, 4))
    p.drawEllipse(QRectF(9, 10.5, 4, 4))


def _copy(p):
    _page(p, 1.5, 1.5, 8.5, 10.5, 2.5)
    _page(p, 5.5, 4.5, 8.5, 10.5, 2.5)
    _text_lines(p, 7.2, 8.0, 4.6, 3)


def _paste(p):
    _fill(p, "#c8a05a", "#7a5a20")
    p.drawRoundedRect(QRectF(1.5, 2, 10, 12.5), 1.0, 1.0)
    _fill(p, "#e8e2cf", "#9a8a60")
    p.drawRect(QRectF(3, 4, 7.5, 9.5))
    _fill(p, "#8a8a8a", "#5a5a5a")
    p.drawRect(QRectF(4.6, 1, 4.3, 2.4))
    _page(p, 6.5, 5.5, 8, 9.5, 2.5)
    _text_lines(p, 7.8, 8.6, 4.6, 3)


def _format_painter(p):
    _fill(p, "#d9dde3", "#5a616b")
    p.drawRect(QRectF(5.5, 1.2, 5, 4.2))
    _fill(p, OFFICE_YELLOW, "#8a6a20")
    p.drawRect(QRectF(5, 5.4, 6, 2.6))
    _pen(p, 1.2, "#5a616b")
    p.drawLine(QPointF(8, 8), QPointF(8, 10.5))
    _fill(p, "#f0f0f0", "#5a616b")
    p.drawRoundedRect(QRectF(6.4, 10.3, 3.2, 4.5), 0.8, 0.8)


def _undo(p, mirror=False):
    if mirror:
        p.save()
        p.translate(16, 0)
        p.scale(-1, 1)
    path = QPainterPath()
    path.moveTo(2.5, 12.5)
    path.cubicTo(3.5, 5.5, 11.5, 4.0, 13.5, 7.0)
    p.setPen(QPen(QColor("#2f6bbf"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    _fill(p, "#2f6bbf")
    p.drawPolygon(_poly((1.0, 8.0), (6.4, 8.0), (3.2, 13.6)))
    if mirror:
        p.restore()


def _redo(p):
    _undo(p, mirror=True)


# ------------------------------------------------------------- formatting ---

def _letter(p, ch, color=INK, size=11.5, bold=True, italic=False, underline=False,
            strike=False, rect=QRectF(0, -0.5, 16, 16)):
    f = p.font()
    f.setFamily("Times New Roman")
    f.setPixelSize(int(size))
    f.setBold(bold)
    f.setItalic(italic)
    f.setUnderline(underline)
    f.setStrikeOut(strike)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, ch)


def _bold(p):
    _letter(p, "B", size=13)


def _italic(p):
    _letter(p, "I", size=13, bold=False, italic=True)


def _underline(p):
    _letter(p, "U", size=12, rect=QRectF(0, -2, 16, 16))
    _pen(p, 1.4)
    p.drawLine(QPointF(3.5, 13.5), QPointF(12.5, 13.5))


def _strike(p):
    _letter(p, "S", size=12, strike=True)


def _align(p, mode):
    _pen(p, 1.3, "#4a4a4a", cap=Qt.PenCapStyle.FlatCap)
    widths = {
        "left":    [12, 8, 12, 7, 12],
        "center":  [12, 8, 12, 8, 12],
        "right":   [12, 8, 12, 7, 12],
        "justify": [12, 12, 12, 12, 12],
    }[mode]
    y = 2.0
    for w in widths:
        if mode == "left" or mode == "justify":
            x = 2.0
        elif mode == "right":
            x = 14.0 - w
        else:
            x = 8.0 - w / 2
        p.drawLine(QPointF(x, y), QPointF(x + w, y))
        y += 2.75


def _align_left(p):
    _align(p, "left")


def _align_center(p):
    _align(p, "center")


def _align_right(p):
    _align(p, "right")


def _align_justify(p):
    _align(p, "justify")


def _line_spacing(p):
    _pen(p, 1.2, "#4a4a4a", cap=Qt.PenCapStyle.FlatCap)
    for i, y in enumerate((2.5, 6.0, 9.5, 13.0)):
        p.drawLine(QPointF(6.0, y), QPointF(14.0, y))
    _fill(p, "#2f6bbf")
    p.drawPolygon(_poly((3.0, 2.0), (0.6, 5.0), (5.4, 5.0)))
    p.drawPolygon(_poly((3.0, 13.6), (0.6, 10.6), (5.4, 10.6)))
    _pen(p, 1.2, "#2f6bbf", cap=Qt.PenCapStyle.FlatCap)
    p.drawLine(QPointF(3.0, 4.6), QPointF(3.0, 11.0))


def _bullets(p):
    _fill(p, "#2b2b2b")
    for y in (3.0, 7.5, 12.0):
        p.drawEllipse(QRectF(1.2, y - 1.3, 2.6, 2.6))
    _pen(p, 1.2, "#4a4a4a", cap=Qt.PenCapStyle.FlatCap)
    for y in (3.0, 7.5, 12.0):
        p.drawLine(QPointF(5.6, y), QPointF(14.5, y))


def _numbering(p):
    f = p.font()
    f.setFamily("Tahoma")
    f.setPixelSize(6)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#2b2b2b"))
    for i, y in enumerate((3.0, 7.5, 12.0), start=1):
        p.drawText(QRectF(0, y - 4, 5, 8), Qt.AlignmentFlag.AlignCenter, f"{i}.")
    _pen(p, 1.2, "#4a4a4a", cap=Qt.PenCapStyle.FlatCap)
    for y in (3.0, 7.5, 12.0):
        p.drawLine(QPointF(5.6, y), QPointF(14.5, y))


def _indent(p, decrease=False):
    _pen(p, 1.2, "#4a4a4a", cap=Qt.PenCapStyle.FlatCap)
    p.drawLine(QPointF(1.5, 2.0), QPointF(14.5, 2.0))
    p.drawLine(QPointF(1.5, 14.0), QPointF(14.5, 14.0))
    for y in (5.5, 8.0, 10.5):
        p.drawLine(QPointF(7.0, y), QPointF(14.5, y))
    _fill(p, "#2f6bbf")
    if decrease:
        p.drawPolygon(_poly((1.2, 8.0), (5.0, 5.0), (5.0, 11.0)))
    else:
        p.drawPolygon(_poly((5.0, 8.0), (1.2, 5.0), (1.2, 11.0)))


def _indent_more(p):
    _indent(p, decrease=False)


def _indent_less(p):
    _indent(p, decrease=True)


def _font_color(p):
    _letter(p, "A", size=11, rect=QRectF(0, -3.5, 16, 16))
    _fill(p, OFFICE_RED, "#7a2018")
    p.drawRect(QRectF(1.5, 11.5, 13, 3.5))


def _highlight(p):
    _fill(p, "#f2e08a", "#8a7a30")
    p.drawPolygon(_poly((3.5, 9.5), (8.5, 2.0), (13.0, 5.0), (8.0, 12.5)))
    _fill(p, "#d8d4c4", "#7a7666")
    p.drawPolygon(_poly((3.5, 9.5), (8.0, 12.5), (6.0, 13.5), (2.5, 11.0)))
    _fill(p, "#f3d33a", "#8a7a20")
    p.drawRect(QRectF(1.5, 13.5, 13, 2))


def _borders(p):
    _pen(p, 0.9, "#a8a8a8")
    for i in range(1, 3):
        p.drawLine(QPointF(1.5, 1.5 + i * 4.3), QPointF(14.5, 1.5 + i * 4.3))
        p.drawLine(QPointF(1.5 + i * 4.3, 1.5), QPointF(1.5 + i * 4.3, 14.5))
    _pen(p, 1.6, "#2b2b2b", cap=Qt.PenCapStyle.SquareCap)
    p.drawRect(QRectF(1.5, 1.5, 13, 13))


def _styles(p):
    _letter(p, "A", size=13, rect=QRectF(-2, -1, 16, 16))
    _fill(p, OFFICE_YELLOW, "#8a6a20")
    p.drawPolygon(_poly((10.5, 2.0), (15.0, 2.0), (15.0, 7.0)))
    _fill(p, OFFICE_BLUE)
    p.drawRect(QRectF(9.5, 12.5, 6, 2))


def _para_marks(p):
    f = p.font()
    f.setFamily("Times New Roman")
    f.setPixelSize(15)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(OFFICE_BLUE))
    p.drawText(QRectF(0, -1, 16, 16), Qt.AlignmentFlag.AlignCenter, "¶")


# ------------------------------------------------------------------ tools ---

def _spelling(p):
    f = p.font()
    f.setFamily("Times New Roman")
    f.setPixelSize(9)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#2b2b2b"))
    p.drawText(QRectF(0, -3, 16, 12), Qt.AlignmentFlag.AlignCenter, "ABC")
    _pen(p, 1.7, OFFICE_GREEN)
    p.drawPolyline(_poly((3.0, 11.5), (6.0, 14.5), (13.5, 6.5)))


def _research(p):
    _fill(p, "#3a5f9e", "#22406e")
    p.drawPolygon(_poly((1.5, 2.5), (7.5, 4.0), (7.5, 13.5), (1.5, 12.0)))
    _fill(p, "#6f8fc4", "#22406e")
    p.drawPolygon(_poly((13.5, 2.5), (7.5, 4.0), (7.5, 13.5), (13.5, 12.0)))
    _pen(p, 1.3, "#2b4a7a")
    p.drawEllipse(QRectF(8.0, 7.0, 5.5, 5.5))
    _pen(p, 1.7, "#2b4a7a")
    p.drawLine(QPointF(12.8, 11.8), QPointF(15.2, 14.4))


def _table(p):
    _fill(p, PAGE, "#5a616b")
    p.drawRect(QRectF(1.5, 2.5, 13, 11))
    _fill(p, "#7f9dc9", "#5a616b")
    p.drawRect(QRectF(1.5, 2.5, 13, 3))
    _pen(p, 0.9, "#8a9099")
    p.drawLine(QPointF(1.5, 9.0), QPointF(14.5, 9.0))
    p.drawLine(QPointF(5.8, 5.5), QPointF(5.8, 13.5))
    p.drawLine(QPointF(10.2, 5.5), QPointF(10.2, 13.5))
    _pen(p, 1.1, "#5a616b")
    p.drawRect(QRectF(1.5, 2.5, 13, 11))


def _tables_borders(p):
    _table(p)
    _fill(p, "#d9a86a", "#7a5a20")
    p.drawPolygon(_poly((9.0, 15.0), (10.5, 9.0), (13.0, 10.0), (11.0, 15.5)))
    _fill(p, "#f0d0a0")
    p.drawPolygon(_poly((10.5, 9.0), (13.0, 10.0), (11.9, 7.4)))


def _columns(p):
    _fill(p, PAGE, "#5a616b")
    p.drawRect(QRectF(1.5, 1.5, 13, 13))
    _text_lines(p, 3.0, 4.0, 4.2, 5, 2.0)
    _text_lines(p, 9.0, 4.0, 4.2, 5, 2.0)
    _pen(p, 0.9, "#b0b0b0")
    p.drawLine(QPointF(8.0, 2.5), QPointF(8.0, 13.5))


def _hyperlink(p):
    _fill(p, "#8fc0e8", "#2b5a8a")
    p.drawEllipse(QRectF(1.0, 1.0, 10, 10))
    _pen(p, 0.8, "#2b5a8a")
    p.drawLine(QPointF(1.0, 6.0), QPointF(11.0, 6.0))
    p.drawEllipse(QRectF(4.0, 1.0, 4, 10))
    _pen(p, 1.9, "#c8a13c", cap=Qt.PenCapStyle.RoundCap)
    p.drawLine(QPointF(8.5, 13.0), QPointF(11.0, 10.5))
    p.drawLine(QPointF(11.5, 13.5), QPointF(14.0, 11.0))
    _pen(p, 1.4, "#e8c66a")
    p.drawLine(QPointF(10.2, 12.2), QPointF(12.3, 11.6))


def _drawing(p):
    _fill(p, "#8fb8e0", "#3a5f9e")
    p.drawEllipse(QRectF(1.0, 6.0, 8, 8))
    _fill(p, "#f2c96a", "#8a6a20")
    p.drawRect(QRectF(6.5, 2.0, 8, 7))
    _fill(p, "#a8d49a", "#4a8b3a")
    p.drawPolygon(_poly((10.5, 8.0), (15.0, 15.0), (6.0, 15.0)))


def _doc_map(p):
    _fill(p, "#dce6f2", "#5a7fa8")
    p.drawRect(QRectF(1.5, 1.5, 5.5, 13))
    _pen(p, 1.0, "#5a7fa8")
    for y in (4.0, 7.0, 10.0, 13.0):
        p.drawLine(QPointF(2.6, y), QPointF(6.0, y))
    _fill(p, PAGE, "#5a616b")
    p.drawRect(QRectF(8.0, 1.5, 6.5, 13))
    _text_lines(p, 9.0, 4.0, 4.5, 5, 2.0)


def _zoom(p):
    _pen(p, 1.5, "#2b4a7a")
    p.drawEllipse(QRectF(1.5, 1.5, 9.5, 9.5))
    _pen(p, 2.1, "#2b4a7a")
    p.drawLine(QPointF(10.5, 10.5), QPointF(14.8, 14.8))


def _help(p):
    _fill(p, "#f2c94a", "#8a6a20")
    p.drawEllipse(QRectF(1.0, 1.0, 14, 14))
    f = p.font()
    f.setFamily("Tahoma")
    f.setPixelSize(11)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#4a3a10"))
    p.drawText(QRectF(0, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, "?")


def _assistant(p):
    """Clippy: a paperclip with eyes, exactly as feared."""
    _pen(p, 1.6, "#9aa6b4")
    path = QPainterPath()
    path.moveTo(5.0, 14.0)
    path.lineTo(5.0, 5.0)
    path.cubicTo(5.0, 1.5, 10.5, 1.5, 10.5, 5.0)
    path.lineTo(10.5, 12.0)
    path.cubicTo(10.5, 14.5, 7.0, 14.5, 7.0, 12.0)
    path.lineTo(7.0, 6.0)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    _fill(p, PAGE, "#3b3b3b")
    p.drawEllipse(QRectF(5.2, 4.2, 2.6, 2.8))
    p.drawEllipse(QRectF(8.0, 4.2, 2.6, 2.8))
    _fill(p, "#1a1a1a")
    p.drawEllipse(QRectF(6.1, 5.2, 1.2, 1.3))
    p.drawEllipse(QRectF(8.9, 5.2, 1.2, 1.3))


def _wordart(p):
    f = p.font()
    f.setFamily("Times New Roman")
    f.setPixelSize(13)
    f.setBold(True)
    p.setFont(f)
    for dx, col in ((1.4, "#1b3f7a"), (0.7, "#2f6bbf"), (0, "#8fc0e8")):
        p.setPen(QColor(col))
        p.drawText(QRectF(dx, dx - 1, 16, 16), Qt.AlignmentFlag.AlignCenter, "A")


def _symbol(p):
    f = p.font()
    f.setFamily("Times New Roman")
    f.setPixelSize(14)
    p.setFont(f)
    p.setPen(QColor("#2b2b2b"))
    p.drawText(QRectF(0, -1, 16, 16), Qt.AlignmentFlag.AlignCenter, "Ω")


def _date(p):
    _fill(p, PAGE, "#5a616b")
    p.drawRect(QRectF(1.5, 2.5, 13, 12))
    _fill(p, OFFICE_RED, "#7a2018")
    p.drawRect(QRectF(1.5, 2.5, 13, 3.5))
    _fill(p, "#8a8a8a")
    p.drawRect(QRectF(4.0, 0.8, 1.4, 3))
    p.drawRect(QRectF(10.6, 0.8, 1.4, 3))
    _pen(p, 0.9, "#9aa2ad")
    for y in (9.0, 11.5):
        p.drawLine(QPointF(2.5, y), QPointF(13.5, y))
    for x in (5.2, 8.0, 10.8):
        p.drawLine(QPointF(x, 6.5), QPointF(x, 14.0))


def _break_glyph(p):
    _page(p, 2.5, 1.0, 11, 14, 0)
    _text_lines(p, 4.0, 3.5, 8.0, 2, 2.0)
    _pen(p, 1.2, OFFICE_BLUE)
    p.setPen(QPen(QColor(OFFICE_BLUE), 1.2, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(2.5, 8.5), QPointF(13.5, 8.5))
    _text_lines(p, 4.0, 11.0, 8.0, 2, 2.0)


def _picture(p):
    _fill(p, PAGE, "#5a616b")
    p.drawRect(QRectF(1.0, 3.0, 14, 10))
    _fill(p, "#9fd4f2")
    p.drawRect(QRectF(1.8, 3.8, 12.4, 8.4))
    _fill(p, "#f2d24a")
    p.drawEllipse(QRectF(3.0, 5.0, 2.8, 2.8))
    _fill(p, "#4a8b3a")
    p.drawPolygon(_poly((5.5, 12.2), (9.5, 6.0), (13.5, 12.2)))
    _fill(p, "#6aa858")
    p.drawPolygon(_poly((2.0, 12.2), (5.5, 7.6), (9.0, 12.2)))


def _textbox(p):
    _pen(p, 1.0, "#5a616b")
    p.setBrush(QColor(PAGE))
    p.drawRect(QRectF(1.5, 3.5, 13, 9))
    _text_lines(p, 3.0, 6.0, 10.0, 3, 2.2)
    _fill(p, PAGE, "#2b2b2b")
    for x, y in ((1.5, 3.5), (8, 3.5), (14.5, 3.5), (1.5, 8), (14.5, 8),
                 (1.5, 12.5), (8, 12.5), (14.5, 12.5)):
        p.drawRect(QRectF(x - 1, y - 1, 2, 2))


def _track_changes(p):
    _page(p, 1.5, 1.0, 10, 14, 2.5)
    p.setPen(QPen(QColor(TEXT_LINE), 1))
    p.drawLine(QPointF(3.0, 4.5), QPointF(9.5, 4.5))
    p.setPen(QPen(QColor(OFFICE_RED), 1))
    p.drawLine(QPointF(3.0, 7.0), QPointF(9.5, 7.0))
    p.drawLine(QPointF(3.0, 7.0), QPointF(9.5, 7.0))
    _pen(p, 1.4, OFFICE_RED)
    p.drawLine(QPointF(3.0, 8.6), QPointF(9.5, 8.6))
    _fill(p, "#d9a86a", "#7a5a20")
    p.drawPolygon(_poly((10.5, 15.0), (12.0, 8.0), (14.5, 9.0), (12.5, 15.5)))


def _macro(p):
    _fill(p, "#e8e4d8", "#5a616b")
    p.drawRect(QRectF(1.0, 2.0, 14, 12))
    _fill(p, OFFICE_BLUE)
    p.drawRect(QRectF(1.0, 2.0, 14, 2.5))
    f = p.font()
    f.setFamily("Tahoma")
    f.setPixelSize(8)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#2b2b2b"))
    p.drawText(QRectF(1, 4, 14, 10), Qt.AlignmentFlag.AlignCenter, "VB")


def _options(p):
    _fill(p, "#c8ccd2", "#5a616b")
    p.save()
    p.translate(8, 8)
    for _ in range(8):
        p.rotate(45)
        p.drawRoundedRect(QRectF(-1.5, -7.4, 3.0, 3.4), 0.6, 0.6)
    p.restore()
    _fill(p, "#c8ccd2", "#5a616b")
    p.drawEllipse(QRectF(2.5, 2.5, 11, 11))
    _fill(p, "#f2f2f2", "#5a616b")
    p.drawEllipse(QRectF(5.5, 5.5, 5, 5))


def _word_doc(p):
    """The .doc file icon: page plus the blue W."""
    _page(p, 2.0, 1.0, 11, 14, 3)
    f = p.font()
    f.setFamily("Times New Roman")
    f.setPixelSize(9)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(OFFICE_BLUE))
    p.drawText(QRectF(2, 4, 11, 10), Qt.AlignmentFlag.AlignCenter, "W")


_GLYPHS = {
    "new": _new, "open": _open, "save": _save, "print": _print,
    "print_preview": _print_preview, "mail": _mail,
    "cut": _cut, "copy": _copy, "paste": _paste, "format_painter": _format_painter,
    "undo": _undo, "redo": _redo,
    "bold": _bold, "italic": _italic, "underline": _underline, "strike": _strike,
    "align_left": _align_left, "align_center": _align_center,
    "align_right": _align_right, "align_justify": _align_justify,
    "line_spacing": _line_spacing, "bullets": _bullets, "numbering": _numbering,
    "indent_more": _indent_more, "indent_less": _indent_less,
    "font_color": _font_color, "highlight": _highlight, "borders": _borders,
    "styles": _styles, "para_marks": _para_marks,
    "spelling": _spelling, "research": _research, "table": _table,
    "tables_borders": _tables_borders, "columns": _columns, "hyperlink": _hyperlink,
    "drawing": _drawing, "doc_map": _doc_map, "zoom": _zoom, "help": _help,
    "assistant": _assistant, "wordart": _wordart, "symbol": _symbol, "date": _date,
    "break": _break_glyph, "picture": _picture, "textbox": _textbox,
    "track_changes": _track_changes, "macro": _macro, "options": _options,
    "word_doc": _word_doc,
}
