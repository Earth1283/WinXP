"""Shared controls: the Office colour dropdown, measurement spin boxes, the
preview panes Word puts in half its dialogs, and the toolbar button styling.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen
from PyQt6.QtWidgets import (
    QDoubleSpinBox, QMenu, QToolButton, QWidget, QWidgetAction,
)

from ... import theme
from ...color_dialog import XPColorDialog
from . import mw_icons
from .model import UNITS

TOOLBAR_QSS = """
QWidget#mwToolbar { background: #ece9d8; }
QToolButton {
    border: 1px solid transparent; background: transparent; padding: 1px;
    border-radius: 2px;
}
QToolButton:hover { border: 1px solid #b6c8e2; background: #dfeaf8; }
QToolButton:pressed, QToolButton:checked {
    border: 1px solid #93a9c8; background: #c5d8ef;
}
QToolButton::menu-indicator { image: none; width: 0px; }
QComboBox { font-size: 11px; background: white; }
QLabel { background: transparent; font-size: 11px; }
"""

#: The Office XP palette: eight columns of five, in the order the dropdown
#: lays them out (dark to light down each column).
OFFICE_COLORS = [
    "#000000", "#993300", "#333300", "#003300", "#003366", "#000080", "#333399", "#333333",
    "#800000", "#ff6600", "#808000", "#008000", "#008080", "#0000ff", "#666699", "#808080",
    "#ff0000", "#ff9900", "#99cc00", "#339966", "#33cccc", "#3366ff", "#800080", "#969696",
    "#ff00ff", "#ffcc00", "#ffff00", "#00ff00", "#00ffff", "#00ccff", "#993366", "#c0c0c0",
    "#ff99cc", "#ffcc99", "#ffff99", "#ccffcc", "#ccffff", "#99ccff", "#cc99ff", "#ffffff",
]

COLOR_NAMES = {
    "#000000": "Black", "#ff0000": "Red", "#0000ff": "Blue", "#008000": "Green",
    "#ffff00": "Yellow", "#ffffff": "White", "#808080": "Gray-50%",
    "#c0c0c0": "Gray-25%", "#800000": "Dark Red", "#000080": "Dark Blue",
    "#ff9900": "Orange", "#00ffff": "Turquoise", "#ff00ff": "Pink",
}

HIGHLIGHT_COLORS = [
    "#ffff00", "#00ff00", "#00ffff", "#ff00ff", "#0000ff", "#ff0000",
    "#000080", "#008080", "#008000", "#800080", "#800000", "#808000",
    "#808080", "#c0c0c0", "#000000",
]


def color_name(hex_value: str) -> str:
    return COLOR_NAMES.get(hex_value.lower(), hex_value.upper())


class ColorGrid(QWidget):
    """The 8x5 swatch grid inside the colour dropdown."""

    picked = pyqtSignal(str)

    def __init__(self, colors=None, columns=8, cell=17):
        super().__init__()
        self.colors = colors or OFFICE_COLORS
        self.columns = columns
        self.cell = cell
        rows = (len(self.colors) + columns - 1) // columns
        self.setFixedSize(columns * cell + 6, rows * cell + 6)
        self.setMouseTracking(True)
        self._hover = -1

    def _index_at(self, pos) -> int:
        col = int((pos.x() - 3) // self.cell)
        row = int((pos.y() - 3) // self.cell)
        if 0 <= col < self.columns and row >= 0:
            index = row * self.columns + col
            if index < len(self.colors):
                return index
        return -1

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ece9d8"))
        for index, value in enumerate(self.colors):
            row, col = divmod(index, self.columns)
            rect = QRectF(3 + col * self.cell, 3 + row * self.cell,
                          self.cell - 2, self.cell - 2)
            p.setPen(QPen(QColor("#7f7f7f"), 1))
            p.setBrush(QColor(value))
            p.drawRect(rect)
            if index == self._hover:
                p.setPen(QPen(QColor("#316ac5"), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(rect.adjusted(-1.5, -1.5, 1.5, 1.5))
        p.end()

    def mouseMoveEvent(self, ev):
        index = self._index_at(ev.position())
        if index != self._hover:
            self._hover = index
            if index >= 0:
                self.setToolTip(color_name(self.colors[index]))
            self.update()

    def leaveEvent(self, ev):
        self._hover = -1
        self.update()

    def mouseReleaseEvent(self, ev):
        index = self._index_at(ev.position())
        if index >= 0:
            self.picked.emit(self.colors[index])


class ColorPickerButton(QToolButton):
    """A toolbar split button: the glyph applies the current colour, the arrow
    opens the Office palette with its Automatic entry and More Colors escape."""

    color_selected = pyqtSignal(QColor)

    def __init__(self, glyph: str, color: QColor, automatic_label="Automatic",
                 automatic_color=QColor("black"), colors=None, tooltip=""):
        super().__init__()
        self.glyph = glyph
        self.color = QColor(color)
        self.automatic_label = automatic_label
        self.automatic_color = QColor(automatic_color)
        self.palette_colors = colors
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.setFixedSize(QSize(30, 22))
        self.setIconSize(QSize(16, 16))
        self.setToolTip(tooltip)
        self.clicked.connect(lambda: self.color_selected.emit(self.color))
        self._build_menu()
        self._refresh()

    def _build_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(theme.MENU_QSS)
        auto = QAction(self.automatic_label, menu)
        auto.triggered.connect(lambda: self._choose(self.automatic_color, automatic=True))
        menu.addAction(auto)
        menu.addSeparator()
        grid = ColorGrid(self.palette_colors)
        grid.picked.connect(lambda value: (self._choose(QColor(value)), menu.close()))
        holder = QWidgetAction(menu)
        holder.setDefaultWidget(grid)
        menu.addAction(holder)
        menu.addSeparator()
        more = QAction("More Colors...", menu)
        more.triggered.connect(self._more_colors)
        menu.addAction(more)
        self.setMenu(menu)

    def _more_colors(self):
        chosen = XPColorDialog.get_color(self.window(), self.color)
        if chosen is not None:
            self._choose(chosen)

    def _choose(self, color: QColor, automatic=False):
        self.color = QColor(color)
        self._automatic = automatic
        self._refresh()
        self.color_selected.emit(self.color)

    def set_color(self, color: QColor):
        self.color = QColor(color)
        self._refresh()

    def _refresh(self):
        pm = mw_icons.pixmap(self.glyph, 16)
        p = QPainter(pm)
        p.fillRect(QRectF(1.5, 11.5, 13, 3.5), self.color)
        p.setPen(QPen(QColor("#5a5a5a"), 1))
        p.drawRect(QRectF(1.5, 11.5, 13, 3.5))
        p.end()
        self.setIcon(QIcon(pm))


class MeasureBox(QDoubleSpinBox):
    """A spin box that speaks Word's units: shows 1.25" or 3.17 cm, stores px."""

    def __init__(self, unit="Inches", minimum=-22.0, maximum=22.0, step=0.1):
        super().__init__()
        self.unit = unit
        self.setDecimals(2)
        self.setSingleStep(step)
        self.setRange(minimum, maximum)
        self.setSuffix(UNITS[unit][2])
        self.setFixedWidth(74)

    def set_px(self, px: float):
        self.setValue(UNITS[self.unit][1](px))

    def px(self) -> float:
        return UNITS[self.unit][0](self.value())


class SamplePreview(QWidget):
    """The sunken 'Preview' pane. Draws the grey filler lines Word uses to
    stand in for surrounding paragraphs, with the live sample in the middle."""

    def __init__(self, height=112, mode="paragraph"):
        super().__init__()
        self.setFixedHeight(height)
        self.setMinimumWidth(300)
        self.mode = mode
        self.sample_text = "Times New Roman"
        self.font_spec = QFont("Times New Roman", 12)
        self.text_color = QColor("black")
        self.align = Qt.AlignmentFlag.AlignLeft
        self.left_indent = 0.0
        self.right_indent = 0.0
        self.first_indent = 0.0
        self.space_before = 0.0
        self.space_after = 0.0
        self.line_height = 100.0
        self.highlight = None

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        p.setPen(QPen(QColor("#8a8a7a"), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self.mode == "font":
            self._paint_font(p)
        else:
            self._paint_paragraph(p)
        p.end()

    def _paint_font(self, p: QPainter):
        if self.highlight:
            p.fillRect(self.rect().adjusted(1, 1, -1, -1), QColor(self.highlight))
        p.setFont(self.font_spec)
        p.setPen(self.text_color)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.sample_text)

    def _paint_paragraph(self, p: QPainter):
        scale = 0.24
        w = self.width()
        margin = 14
        content_w = w - margin * 2
        y = 12.0
        p.setPen(QPen(QColor("#c4c4c4"), 1.6))

        def filler(count):
            nonlocal y
            for _ in range(count):
                p.drawLine(QPointF(margin, y), QPointF(margin + content_w, y))
                y += 7.0

        filler(3)
        y += self.space_before * scale
        left = margin + self.left_indent * scale
        right = margin + content_w - self.right_indent * scale
        first = left + self.first_indent * scale
        p.setPen(QPen(QColor("#3a3a3a"), 1.8))
        line_gap = 7.0 * max(0.7, self.line_height / 100.0)
        for index in range(5):
            x0 = first if index == 0 else left
            x1 = right if index < 4 else left + (right - left) * 0.55
            if self.align == Qt.AlignmentFlag.AlignHCenter:
                span = x1 - x0
                centre = (left + right) / 2
                x0, x1 = centre - span / 2, centre + span / 2
            elif self.align == Qt.AlignmentFlag.AlignRight:
                span = x1 - x0
                x0, x1 = right - span, right
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
            y += line_gap
        y += self.space_after * scale
        p.setPen(QPen(QColor("#c4c4c4"), 1.6))
        filler(3)


def toolbar_button(glyph: str, tooltip: str, slot=None, checkable=False, size=22) -> QToolButton:
    btn = QToolButton()
    btn.setIcon(mw_icons.icon(glyph, 16))
    btn.setIconSize(QSize(16, 16))
    btn.setFixedSize(QSize(size, size))
    btn.setToolTip(tooltip)
    btn.setCheckable(checkable)
    if slot:
        (btn.toggled if checkable else btn.clicked).connect(slot)
    return btn
