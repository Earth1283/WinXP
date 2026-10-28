"""Small widgets used by the PhotoChop window: toolbox buttons, rulers, pickers."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QToolButton, QWidget,
)

from .... import theme
from .. import brushes, dialogs as dlg, pc_icons
from ..canvas import GRADIENT_PRESETS
from ..model import BLEND_MODES


class PaletteScrollArea(QScrollArea):
    """A narrow palette viewport with conventional Shift+wheel scrolling."""

    def wheelEvent(self, ev):
        delta = ev.angleDelta().x()
        if not delta and ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            delta = ev.angleDelta().y()
        if delta:
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            ev.accept()
            return
        super().wheelEvent(ev)


class ToolButton(QToolButton):
    """Toolbox button. Right-click (or press-and-hold) opens the flyout, and
    the little corner triangle marks slots that have one."""

    def __init__(self, win, group, index):
        super().__init__()
        self.win = win
        self.group_tools = group
        self.slot_index = index
        self.current = group[0]
        self.setCheckable(True)
        self.setFixedSize(26, 26)
        self.setIconSize(QSize(20, 20))
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self.show_flyout)
        self.refresh()

    def refresh(self):
        self.setIcon(pc_icons.icon(self.current.icon, 20))
        shortcut = f" ({self.current.shortcut})" if self.current.shortcut else ""
        self.setToolTip(f"{self.current.name}{shortcut}")

    def set_current(self, tool):
        self.current = tool
        self.refresh()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if len(self.group_tools) > 1:
            p = QPainter(self)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#303030"))
            w, h = self.width(), self.height()
            p.drawPolygon(QPoint(w - 3, h - 3), QPoint(w - 7, h - 3), QPoint(w - 3, h - 7))
            p.end()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            self.show_flyout()
            return
        self._hold.start(420)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._hold.stop()
        super().mouseReleaseEvent(ev)
        if ev.button() == Qt.MouseButton.LeftButton:
            self.win.select_tool(self.current.id)

    def show_flyout(self):
        self._hold.stop()
        if len(self.group_tools) < 2:
            return
        menu = QMenu(self)
        theme.style_menu(menu) if hasattr(theme, "style_menu") else None
        for tool in self.group_tools:
            act = QAction(pc_icons.icon(tool.icon, 16), tool.name
                          + (f"     {tool.shortcut}" if tool.shortcut else ""), menu)
            act.triggered.connect(lambda _, t=tool: self.win.select_tool(t.id))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(QPoint(self.width(), 0)))


class ColorSwatchWidget(QWidget):
    """Foreground/background swatches with the reset and swap glyphs."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(56, 52)
        self.setToolTip("Set foreground / background color (D resets, X swaps)")

    def paintEvent(self, ev):
        p = QPainter(self)
        p.drawPixmap(0, 0, pc_icons.pixmap("default_colors", 14))
        p.drawPixmap(40, 0, pc_icons.pixmap("swap_colors", 14))
        p.setPen(QPen(QColor("#606060"), 1))
        p.setBrush(self.win.bg_color)
        p.drawRect(20, 20, 28, 28)
        p.setBrush(self.win.fg_color)
        p.drawRect(6, 14, 28, 28)
        p.end()

    def mousePressEvent(self, ev):
        x, y = ev.position().x(), ev.position().y()
        if x < 15 and y < 15:
            self.win.reset_colors()
        elif x > 38 and y < 15:
            self.win.swap_colors()
        elif x > 32 and y > 30:
            self.win.pick_bg_color()
        else:
            self.win.pick_fg_color()


class FadeDialog(dlg.PCDialog):
    def __init__(self, parent, last_name, apply_fn):
        super().__init__(parent, "Fade")
        self.apply_fn = apply_fn
        label = QLabel(f"Fade: {last_name}")
        label.setStyleSheet("background: transparent;")
        self.content.addWidget(label)
        self.opacity = dlg.SliderRow("Opacity:", 0, 100, 100, "%")
        self.opacity.changed.connect(self._refresh)
        self.content.addWidget(self.opacity)
        row = QHBoxLayout()
        row.addWidget(dlg._lbl("Mode:"))
        self.mode = QComboBox()
        for mode in BLEND_MODES:
            if mode == "-":
                self.mode.insertSeparator(self.mode.count())
            else:
                self.mode.addItem(mode)
        self.mode.currentTextChanged.connect(lambda _: self._refresh())
        row.addWidget(self.mode, 1)
        self.content.addLayout(row)
        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()
        self._refresh()

    def values(self):
        return dict(opacity=self.opacity.value(), mode=self.mode.currentText())

    def _refresh(self):
        self.apply_fn(self.values() if self.preview_on() else None)


class Ruler(QWidget):
    """Ruler with tick marks and the cursor tracker line. Drag one out to
    create a guide, the way PS does."""

    def __init__(self, win, horizontal=True):
        super().__init__()
        self.win = win
        self.horizontal = horizontal
        self.cursor_pos = None
        if horizontal:
            self.setFixedHeight(18)
        else:
            self.setFixedWidth(18)
        self.setStyleSheet("background: #ece9d8;")

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ece9d8"))
        p.setPen(QPen(QColor("#9a9a8a"), 1))
        if self.horizontal:
            p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        canvas = self.win.canvas
        r = canvas.view_rect()
        zoom = canvas.zoom
        step = 50
        while step * zoom < 40:
            step *= 2
        while step * zoom > 160:
            step //= 2
        step = max(1, step)
        p.setFont(QFont(theme.FONT_FAMILY, 6))
        p.setPen(QPen(QColor("#404040"), 1))
        doc_span = self.win.doc.width if self.horizontal else self.win.doc.height
        value = 0
        while value <= doc_span:
            pos = (r.x() + value * zoom) if self.horizontal else (r.y() + value * zoom)
            if self.horizontal:
                p.drawLine(int(pos), 12, int(pos), 17)
                p.drawText(int(pos) + 2, 9, str(value))
                for sub in range(1, 5):
                    sp = pos + step * zoom * sub / 5
                    p.drawLine(int(sp), 14, int(sp), 17)
            else:
                p.drawLine(12, int(pos), 17, int(pos))
                p.save()
                p.translate(9, int(pos) + 2)
                p.rotate(-90)
                p.drawText(0, 0, str(value))
                p.restore()
                for sub in range(1, 5):
                    sp = pos + step * zoom * sub / 5
                    p.drawLine(14, int(sp), 17, int(sp))
            value += step

        if self.cursor_pos is not None:
            p.setPen(QPen(QColor("#202020"), 1))
            if self.horizontal:
                x = r.x() + self.cursor_pos.x() * zoom
                p.drawLine(int(x), 0, int(x), self.height())
            else:
                y = r.y() + self.cursor_pos.y() * zoom
                p.drawLine(0, int(y), self.width(), int(y))
        p.end()

    def mousePressEvent(self, ev):
        self._dragging = True

    def mouseReleaseEvent(self, ev):
        canvas = self.win.canvas
        r = canvas.view_rect()
        if self.horizontal:
            pos = (ev.position().y() - r.y()) / max(0.01, canvas.zoom)
            self.win.add_guide(True, max(0, pos))
        else:
            pos = (ev.position().x() - r.x()) / max(0.01, canvas.zoom)
            self.win.add_guide(False, max(0, pos))


class BrushPickerButton(QPushButton):
    """The brush preview button that drops down the preset picker."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(56, 22)
        self.clicked.connect(self._show_picker)
        self.refresh()

    def refresh(self):
        brush = self.win.options.get("brush", {})
        self.setText(str(brush.get("size", 13)))
        self.setToolTip(brush.get("preset", "Brush"))

    def _show_picker(self):
        menu = QMenu(self)
        for name, size, hardness in brushes.BRUSH_PRESETS:
            act = QAction(f"{name}", menu)
            act.triggered.connect(
                lambda _, n=name, s=size, h=hardness: self._pick(n, s, h))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def _pick(self, name, size, hardness):
        brush = dict(self.win.options.get("brush", {}))
        brush.update(preset=name, size=size, hardness=hardness)
        self.win.options["brush"] = brush
        self.win.brushes_palette.refresh()
        self.refresh()


class GradientPickerButton(QPushButton):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(76, 20)
        self.clicked.connect(self._show_picker)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        from PyQt6.QtGui import QLinearGradient
        p = QPainter(self)
        name = self.win.options.get("gradient", "Foreground to Background")
        stops = GRADIENT_PRESETS.get(name)
        grad = QLinearGradient(3, 0, self.width() - 3, 0)
        if stops:
            for pos, colour in stops:
                grad.setColorAt(pos, QColor(colour))
        else:
            grad.setColorAt(0, self.win.fg_color)
            grad.setColorAt(1, self.win.bg_color)
        p.fillRect(QRect(3, 3, self.width() - 6, self.height() - 6), grad)
        p.setPen(QPen(QColor("#606060"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRect(3, 3, self.width() - 7, self.height() - 7))
        p.end()

    def _show_picker(self):
        menu = QMenu(self)
        for name in GRADIENT_PRESETS:
            act = QAction(name, menu)
            act.triggered.connect(lambda _, n=name: self._pick(n))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def _pick(self, name):
        self.win.options["gradient"] = name
        self.update()
