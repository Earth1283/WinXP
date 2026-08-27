"""PhotoChop -- MacroHard's answer to pre-subscription Photoshop. Real layers,
real blend modes, a fake serial number that "validates" almost anything, and
a splash screen starring a cursed Mona Lisa.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from PyQt6.QtCore import QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from .. import image_codec, theme, vfs as vfs_mod
from ..vfs_dialog import VfsFileDialog
from ..window_manager import XPWindow
from ..xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame
from .paint import PALETTE_ROW, TOOL_BTN_QSS, ColorIndicator, PaletteSwatch, ToolButton, _width_icon
from ..color_dialog import XPColorDialog

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
MONA_LISA_PATH = os.path.join(ASSETS_DIR, "MonaLisa.jpg")

TOOLS = [
    ("pencil", "tool_pencil", "Pencil"),
    ("brush", "tool_brush", "Brush"),
    ("eraser", "tool_eraser", "Eraser"),
    ("fill", "tool_fill", "Fill With Color"),
    ("eyedropper", "tool_eyedropper", "Pick Color"),
    ("line", "tool_line", "Line"),
    ("rect", "tool_rect", "Rectangle"),
    ("ellipse", "tool_ellipse", "Ellipse"),
]
WIDTHS = (1, 3, 5, 8)

BLEND_MODES = {
    "Normal": QPainter.CompositionMode.CompositionMode_SourceOver,
    "Multiply": QPainter.CompositionMode.CompositionMode_Multiply,
    "Screen": QPainter.CompositionMode.CompositionMode_Screen,
    "Darken": QPainter.CompositionMode.CompositionMode_Darken,
    "Lighten": QPainter.CompositionMode.CompositionMode_Lighten,
    "Difference": QPainter.CompositionMode.CompositionMode_Difference,
}
BLEND_NAMES_BY_MODE = {v: k for k, v in BLEND_MODES.items()}

CANVAS_W, CANVAS_H = 560, 380

_activated_this_session = False

LOADING_LINES = [
    "Loading brushes...", "Compressing serial number...", "Optimizing regret...",
    "Indexing filters nobody uses...", "Preparing disappointment...", "Almost there...",
]


def _blank_layer_image() -> QImage:
    img = QImage(CANVAS_W, CANVAS_H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    return img


@dataclass
class Layer:
    name: str
    image: QImage
    visible: bool = True
    opacity: float = 1.0
    blend: QPainter.CompositionMode = field(
        default=QPainter.CompositionMode.CompositionMode_SourceOver
    )


class SplashScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self._line_index = 0

        image = QImage(MONA_LISA_PATH)
        w = 380
        h = int(w * image.height() / image.width()) if image.width() else 480
        self.resize(w, h)

        self.bg_label = QLabel(self)
        self.bg_label.setGeometry(0, 0, w, h)
        if not image.isNull():
            pm = QPixmap.fromImage(image).scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.bg_label.setPixmap(pm)

        title = QLabel("PhotoChop 7.0", self)
        title.setGeometry(0, 14, w, 34)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-weight: bold; font-size: 20px; background: transparent;")

        subtitle = QLabel("Professional", self)
        subtitle.setGeometry(0, 46, w, 20)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #e0d0a0; font-size: 12px; background: transparent;")

        self.status = QLabel(LOADING_LINES[0], self)
        self.status.setGeometry(0, h - 30, w, 24)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(
            "color: white; font-size: 11px; background: rgba(0,0,0,150); padding: 4px;"
        )

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_line)
        self._timer.start(280)

        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.accept)
        self._close_timer.start(1700)

    def _next_line(self):
        self._line_index = (self._line_index + 1) % len(LOADING_LINES)
        self.status.setText(LOADING_LINES[self._line_index])

    def mousePressEvent(self, ev):
        self.accept()


class SerialActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.accepted_activation = False

        inner = build_dialog_frame(self, "PhotoChop 7.0 - Product Activation")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        msg = QLabel(
            "Thank you for choosing PhotoChop 7.0 Professional.\n"
            "Please enter your serial number to activate this installation."
        )
        msg.setWordWrap(True)
        msg.setStyleSheet("background: transparent;")
        root.addWidget(msg)

        self.serial_edit = QLineEdit()
        self.serial_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        root.addWidget(self.serial_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        activate_btn = QPushButton("Activate")
        activate_btn.clicked.connect(self._activate)
        later_btn = QPushButton("Activate Later")
        later_btn.clicked.connect(self._later)
        btn_row.addWidget(activate_btn)
        btn_row.addWidget(later_btn)
        root.addLayout(btn_row)

        inner.addWidget(body)
        self.setFixedWidth(360)
        self.serial_edit.setFocus()

    def _activate(self):
        if not self.serial_edit.text().strip():
            XPMessageBox.warning(self, "PhotoChop", "Please enter a serial number. Any will do.")
            return
        self.accepted_activation = True
        XPMessageBox.information(
            self, "PhotoChop",
            "Congratulations! Your installation of PhotoChop is now genuine(-ish).",
        )
        self.accept()

    def _later(self):
        XPMessageBox.information(
            self, "PhotoChop",
            "PhotoChop will remind you again never, because we forgot to wire that up.",
        )
        self.accept()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        inner = build_dialog_frame(self, "About PhotoChop")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(12)
        pic = QLabel()
        pm = QPixmap(MONA_LISA_PATH).scaled(
            80, 106, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        pic.setPixmap(pm)
        pic.setStyleSheet("border: 1px solid #555; background: transparent;")
        top.addWidget(pic, 0, Qt.AlignmentFlag.AlignTop)

        text = QLabel(
            "PhotoChop 7.0 Professional\n\n"
            "Not affiliated with any real photo editing software, real or imagined.\n\n"
            "Your activation is genuine(-ish)."
        )
        text.setWordWrap(True)
        text.setStyleSheet("background: transparent;")
        top.addWidget(text, 1)
        root.addLayout(top)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("OK")
        ok_btn.setMinimumWidth(75)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

        inner.addWidget(body)
        self.setFixedWidth(340)


class PhotoChopCanvas(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(CANVAS_W, CANVAS_H)
        self.fg = QColor("black")
        self.bg = QColor("white")
        self.tool = "pencil"
        self.pen_width = 3
        self._last = None
        self._drawing_color = None
        self._shape_start = None
        self._pre_shape_image = None

    def active_layer(self) -> Layer:
        return self.win.layers[self.win.active_layer_index]

    def composite(self) -> QImage:
        result = QImage(CANVAS_W, CANVAS_H, QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.white)
        p = QPainter(result)
        for layer in self.win.layers:
            if not layer.visible:
                continue
            p.setOpacity(layer.opacity)
            p.setCompositionMode(layer.blend)
            p.drawImage(0, 0, layer.image)
        p.end()
        return result

    def set_tool(self, tool):
        self.tool = tool

    def set_width(self, w):
        self.pen_width = w

    def paintEvent(self, ev):
        p = QPainter(self)
        p.drawImage(0, 0, self.composite())
        p.end()

    def mousePressEvent(self, ev):
        if ev.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            return
        pos = ev.position().toPoint()
        color = self.fg if ev.button() == Qt.MouseButton.LeftButton else self.bg
        self._drawing_color = color

        if self.tool in ("pencil", "brush", "eraser"):
            self._last = pos
            self._stroke_to(pos, pos)
        elif self.tool == "fill":
            self._flood_fill(pos, color)
        elif self.tool == "eyedropper":
            sampled = self.composite().pixelColor(pos)
            if ev.button() == Qt.MouseButton.LeftButton:
                self.fg = sampled
            else:
                self.bg = sampled
            self.win.on_color_picked()
        elif self.tool in ("line", "rect", "ellipse"):
            self._shape_start = pos
            self._pre_shape_image = self.active_layer().image.copy()

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()
        if self.tool in ("pencil", "brush", "eraser") and self._last is not None \
                and (ev.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)):
            self._stroke_to(self._last, pos)
            self._last = pos
        elif self.tool in ("line", "rect", "ellipse") and self._shape_start is not None:
            self._preview_shape(pos)

    def mouseReleaseEvent(self, ev):
        if self.tool in ("line", "rect", "ellipse") and self._shape_start is not None:
            self._preview_shape(ev.position().toPoint())
            self._shape_start = None
            self._pre_shape_image = None
            self.win.mark_dirty()
            self.win.refresh_thumbnail()
        self._last = None
        self._drawing_color = None

    def _stroke_to(self, a, b):
        layer = self.active_layer()
        painter = QPainter(layer.image)
        if self.tool == "eraser":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setPen(QPen(Qt.GlobalColor.black, max(8, self.pen_width * 3), Qt.PenStyle.SolidLine,
                                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        else:
            width = 1 if self.tool == "pencil" else self.pen_width
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, self.tool != "pencil")
            painter.setPen(QPen(self._drawing_color, width, Qt.PenStyle.SolidLine,
                                 Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(a, b)
        painter.drawPoint(b)  # QPainter.drawLine(a, a) is a no-op, so a lone click needs an explicit dot
        painter.end()
        self.win.mark_dirty()
        self.update()

    def _preview_shape(self, current):
        layer = self.active_layer()
        layer.image = self._pre_shape_image.copy()
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._drawing_color, self.pen_width, Qt.PenStyle.SolidLine,
                             Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        rect = QRect(self._shape_start, current).normalized()
        if self.tool == "line":
            painter.drawLine(self._shape_start, current)
        elif self.tool == "rect":
            painter.drawRect(rect)
        elif self.tool == "ellipse":
            painter.drawEllipse(rect)
        painter.end()
        self.update()

    def _flood_fill(self, pos, color):
        layer = self.active_layer()
        img = layer.image
        w, h = img.width(), img.height()
        x0, y0 = pos.x(), pos.y()
        if not (0 <= x0 < w and 0 <= y0 < h):
            return
        target = img.pixelColor(x0, y0)
        replacement = QColor(color)
        if target.rgba() == replacement.rgba():
            return
        seen = bytearray(w * h)
        stack = [(x0, y0)]
        while stack:
            x, y = stack.pop()
            if x < 0 or x >= w or y < 0 or y >= h:
                continue
            idx = y * w + x
            if seen[idx]:
                continue
            if img.pixelColor(x, y).rgba() != target.rgba():
                continue
            seen[idx] = 1
            img.setPixelColor(x, y, replacement)
            stack.append((x + 1, y))
            stack.append((x - 1, y))
            stack.append((x, y + 1))
            stack.append((x, y - 1))
        self.win.mark_dirty()
        self.win.refresh_thumbnail()
        self.update()


class PhotoChopWindow(XPWindow):
    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Untitled - PhotoChop", icon_key="photochop", size=QSize(880, 560))
        global _activated_this_session
        self.node_id = node_id

        if not _activated_this_session:
            splash = SplashScreen(self)
            splash.exec()
            serial = SerialActivationDialog(self)
            serial.exec()
            _activated_this_session = True

        self.layers: list[Layer] = [Layer("Background", _blank_layer_image())]
        self.active_layer_index = 0
        self.canvas = PhotoChopCanvas(self)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setMenuBar(self._build_menu())

        body = QHBoxLayout()
        body.setContentsMargins(4, 4, 4, 0)
        body.setSpacing(4)
        body.addWidget(self._build_toolbox())

        canvas_wrap = QWidget()
        canvas_wrap.setStyleSheet("background: #808080;")
        wrap_l = QVBoxLayout(canvas_wrap)
        wrap_l.setContentsMargins(8, 8, 8, 8)
        wrap_l.addWidget(self.canvas, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        wrap_l.addStretch(1)
        body.addWidget(canvas_wrap, 1)

        body.addWidget(self._build_layers_panel())
        root.addLayout(body, 1)

        root.addWidget(self._build_palette())
        self.set_content_layout(root)

        self._refresh_layer_list()

        if node_id:
            self.node_id = node_id
            self._load_node(node_id)

    # -- chrome ---------------------------------------------------------

    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar
        bar = QMenuBar()
        theme.style_menubar(bar)

        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._act("&New", self.new_file))
        file_menu.addAction(self._act("&Open...", self.open_file))
        file_menu.addAction(self._act("&Save", self.save_file))
        file_menu.addAction(self._act("Save &As...", self.save_file_as))
        file_menu.addSeparator()
        file_menu.addAction(self._act("E&xit", self.close))

        layer_menu = bar.addMenu("&Layer")
        layer_menu.addAction(self._act("&New Layer", self.new_layer))
        layer_menu.addAction(self._act("&Duplicate Layer", self.duplicate_layer))
        layer_menu.addAction(self._act("&Delete Layer", self.delete_layer))
        layer_menu.addSeparator()
        layer_menu.addAction(self._act("Move Layer &Up", self.move_layer_up))
        layer_menu.addAction(self._act("Move Layer &Down", self.move_layer_down))
        layer_menu.addSeparator()
        layer_menu.addAction(self._act("Merge &Down", self.merge_down))
        layer_menu.addAction(self._act("&Flatten Image", self.flatten_image))

        image_menu = bar.addMenu("&Image")
        image_menu.addAction(self._act("&Clear Layer", self.clear_layer))

        colors_menu = bar.addMenu("&Colors")
        colors_menu.addAction(self._act("&Edit Colors...", self._edit_colors))

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self._act("&About PhotoChop...", self._about))
        help_menu.addAction(self._act("&Deactivate PhotoChop...", self._deactivate))
        return bar

    def _act(self, text, slot):
        from PyQt6.QtGui import QAction
        act = QAction(text, self)
        act.triggered.connect(slot)
        return act

    def _build_toolbox(self):
        panel = QWidget()
        panel.setFixedWidth(64)
        panel.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; border: 1px solid #aca998;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        grid = QGridLayout()
        grid.setSpacing(2)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for i, (key, icon_key, tip) in enumerate(TOOLS):
            btn = ToolButton(icon_key, tip)
            btn.clicked.connect(lambda _, k=key: self.canvas.set_tool(k))
            self.tool_group.addButton(btn)
            grid.addWidget(btn, i // 2, i % 2)
        self.tool_group.buttons()[0].setChecked(True)
        layout.addLayout(grid)

        layout.addSpacing(8)
        width_label = QLabel("Width")
        width_label.setStyleSheet("background: transparent; font-size: 11px;")
        layout.addWidget(width_label)

        self.width_group = QButtonGroup(self)
        for w in WIDTHS:
            wbtn = QPushButton()
            wbtn.setCheckable(True)
            wbtn.setFixedSize(52, 20)
            wbtn.setIcon(_width_icon(w))
            wbtn.setIconSize(QSize(44, 16))
            wbtn.setStyleSheet(TOOL_BTN_QSS)
            wbtn.clicked.connect(lambda _, w=w: self.canvas.set_width(w))
            self.width_group.addButton(wbtn)
            layout.addWidget(wbtn)
        self.width_group.buttons()[1].setChecked(True)
        self.canvas.set_width(WIDTHS[1])

        layout.addStretch(1)
        return panel

    def _build_layers_panel(self):
        panel = QWidget()
        panel.setFixedWidth(180)
        panel.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; border: 1px solid #aca998; {DIALOG_BUTTON_QSS}")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        label = QLabel("Layers")
        label.setStyleSheet("background: transparent; font-weight: bold;")
        layout.addWidget(label)

        self.layer_list = QListWidget()
        self.layer_list.itemChanged.connect(self._on_layer_item_changed)
        self.layer_list.currentRowChanged.connect(self._on_layer_selected)
        layout.addWidget(self.layer_list, 1)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("New")
        new_btn.clicked.connect(self.new_layer)
        dup_btn = QPushButton("Dup")
        dup_btn.clicked.connect(self.duplicate_layer)
        del_btn = QPushButton("Del")
        del_btn.clicked.connect(self.delete_layer)
        btn_row.addWidget(new_btn)
        btn_row.addWidget(dup_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        move_row = QHBoxLayout()
        up_btn = QPushButton("Up")
        up_btn.clicked.connect(self.move_layer_up)
        down_btn = QPushButton("Down")
        down_btn.clicked.connect(self.move_layer_down)
        move_row.addWidget(up_btn)
        move_row.addWidget(down_btn)
        layout.addLayout(move_row)

        blend_label = QLabel("Blend Mode")
        blend_label.setStyleSheet("background: transparent; font-size: 11px;")
        layout.addWidget(blend_label)
        self.blend_combo = QComboBox()
        self.blend_combo.addItems(list(BLEND_MODES.keys()))
        self.blend_combo.currentTextChanged.connect(self._on_blend_changed)
        layout.addWidget(self.blend_combo)

        opacity_label = QLabel("Opacity")
        opacity_label.setStyleSheet("background: transparent; font-size: 11px;")
        layout.addWidget(opacity_label)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        layout.addWidget(self.opacity_slider)

        return panel

    def _build_palette(self):
        panel = QWidget()
        panel.setFixedHeight(40)
        panel.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; border-top: 1px solid #aca998;")
        row = QHBoxLayout(panel)
        row.setContentsMargins(6, 4, 10, 4)
        row.setSpacing(10)

        self.indicator = ColorIndicator(
            lambda: self.canvas.fg, lambda: self.canvas.bg, self._set_fg, self._set_bg,
        )
        row.addWidget(self.indicator)

        grid = QGridLayout()
        grid.setSpacing(2)
        for i, c in enumerate(PALETTE_ROW):
            sw = PaletteSwatch(c, self._set_fg, self._set_bg)
            grid.addWidget(sw, i // 10, i % 10)
        row.addLayout(grid)
        row.addStretch(1)
        return panel

    # -- color state ------------------------------------------------------

    def _set_fg(self, color):
        self.canvas.fg = QColor(color)
        self.indicator.refresh()

    def _set_bg(self, color):
        self.canvas.bg = QColor(color)
        self.indicator.refresh()

    def on_color_picked(self):
        self.indicator.refresh()

    def _edit_colors(self):
        c = XPColorDialog.get_color(self, self.canvas.fg)
        if c:
            self._set_fg(c)

    # -- layer management ---------------------------------------------------

    def _refresh_layer_list(self):
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for layer in reversed(self.layers):
            item = QListWidgetItem(layer.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
            self.layer_list.addItem(item)
        row_from_top = len(self.layers) - 1 - self.active_layer_index
        self.layer_list.setCurrentRow(row_from_top)
        self.layer_list.blockSignals(False)
        self._sync_layer_controls()

    def _sync_layer_controls(self):
        layer = self.layers[self.active_layer_index]
        self.blend_combo.blockSignals(True)
        self.blend_combo.setCurrentText(BLEND_NAMES_BY_MODE.get(layer.blend, "Normal"))
        self.blend_combo.blockSignals(False)
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(int(layer.opacity * 100))
        self.opacity_slider.blockSignals(False)

    def _list_row_to_layer_index(self, row):
        return len(self.layers) - 1 - row

    def _on_layer_selected(self, row):
        if row < 0:
            return
        self.active_layer_index = self._list_row_to_layer_index(row)
        self._sync_layer_controls()

    def _on_layer_item_changed(self, item):
        row = self.layer_list.row(item)
        index = self._list_row_to_layer_index(row)
        self.layers[index].visible = item.checkState() == Qt.CheckState.Checked
        self.canvas.update()

    def _on_blend_changed(self, name):
        self.layers[self.active_layer_index].blend = BLEND_MODES.get(name, BLEND_MODES["Normal"])
        self.canvas.update()
        self.mark_dirty()

    def _on_opacity_changed(self, value):
        self.layers[self.active_layer_index].opacity = value / 100.0
        self.canvas.update()
        self.mark_dirty()

    def new_layer(self):
        self.layers.insert(self.active_layer_index + 1, Layer(f"Layer {len(self.layers) + 1}", _blank_layer_image()))
        self.active_layer_index += 1
        self._refresh_layer_list()
        self.canvas.update()
        self.mark_dirty()

    def duplicate_layer(self):
        src = self.layers[self.active_layer_index]
        copy = Layer(f"{src.name} copy", src.image.copy(), src.visible, src.opacity, src.blend)
        self.layers.insert(self.active_layer_index + 1, copy)
        self.active_layer_index += 1
        self._refresh_layer_list()
        self.canvas.update()
        self.mark_dirty()

    def delete_layer(self):
        if len(self.layers) <= 1:
            XPMessageBox.warning(
                self, "PhotoChop", "PhotoChop requires at least one layer. Even a bad idea needs a canvas."
            )
            return
        del self.layers[self.active_layer_index]
        self.active_layer_index = max(0, self.active_layer_index - 1)
        self._refresh_layer_list()
        self.canvas.update()
        self.mark_dirty()

    def move_layer_up(self):
        i = self.active_layer_index
        if i >= len(self.layers) - 1:
            return
        self.layers[i], self.layers[i + 1] = self.layers[i + 1], self.layers[i]
        self.active_layer_index = i + 1
        self._refresh_layer_list()
        self.canvas.update()
        self.mark_dirty()

    def move_layer_down(self):
        i = self.active_layer_index
        if i <= 0:
            return
        self.layers[i], self.layers[i - 1] = self.layers[i - 1], self.layers[i]
        self.active_layer_index = i - 1
        self._refresh_layer_list()
        self.canvas.update()
        self.mark_dirty()

    def merge_down(self):
        i = self.active_layer_index
        if i <= 0:
            XPMessageBox.warning(self, "PhotoChop", "There's no layer below this one to merge into.")
            return
        upper = self.layers[i]
        lower = self.layers[i - 1]
        painter = QPainter(lower.image)
        painter.setOpacity(upper.opacity if upper.visible else 0.0)
        painter.setCompositionMode(upper.blend)
        painter.drawImage(0, 0, upper.image)
        painter.end()
        del self.layers[i]
        self.active_layer_index = i - 1
        self._refresh_layer_list()
        self.canvas.update()
        self.mark_dirty()

    def flatten_image(self):
        flat = self.canvas.composite()
        self.layers = [Layer("Background", flat)]
        self.active_layer_index = 0
        self._refresh_layer_list()
        self.canvas.update()
        self.mark_dirty()

    def clear_layer(self):
        self.layers[self.active_layer_index].image = _blank_layer_image()
        self.canvas.update()
        self.mark_dirty()

    def refresh_thumbnail(self):
        pass  # layer_list shows names only -- no per-item thumbnails in this cut

    # -- dirty / title ------------------------------------------------------

    def mark_dirty(self):
        title = self.windowTitle()
        if not title.startswith("*"):
            self.setWindowTitle("*" + title)

    def _retitle(self, name):
        self.setWindowTitle(f"{name} - PhotoChop")

    # -- file I/O ---------------------------------------------------------

    def new_file(self):
        self.layers = [Layer("Background", _blank_layer_image())]
        self.active_layer_index = 0
        self._refresh_layer_list()
        self.canvas.update()
        self.node_id = None
        self.setWindowTitle("Untitled - PhotoChop")

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.IMAGE,), title="Open")
        if node_id:
            self.node_id = node_id
            self._load_node(node_id)

    def save_file(self):
        if self.node_id:
            vfs_mod.vfs.write_blob(self.node_id, image_codec.to_bytes(self._flat_pixmap()))
            self._retitle(vfs_mod.vfs.get(self.node_id).name)
        else:
            self.save_file_as()

    def save_file_as(self):
        folder_id, name = VfsFileDialog.get_save_target(
            self, kinds=(vfs_mod.IMAGE,), title="Save As", default_name="Untitled.png"
        )
        if not folder_id:
            return
        existing = next((c for c in vfs_mod.vfs.children_of(folder_id)
                          if c.name == name and c.kind == vfs_mod.IMAGE), None)
        data = image_codec.to_bytes(self._flat_pixmap())
        if existing:
            vfs_mod.vfs.write_blob(existing.id, data)
            self.node_id = existing.id
        else:
            node = vfs_mod.vfs.create_image_file(folder_id, name, data)
            self.node_id = node.id
        self._retitle(vfs_mod.vfs.get(self.node_id).name)

    def _flat_pixmap(self):
        return QPixmap.fromImage(self.canvas.composite())

    def _load_node(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        img = image_codec.from_bytes(vfs_mod.vfs.read_blob(node_id)).toImage()
        if not img.isNull():
            img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied).scaled(
                CANVAS_W, CANVAS_H, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            canvas_img = _blank_layer_image()
            painter = QPainter(canvas_img)
            painter.drawImage(0, 0, img)
            painter.end()
            self.layers = [Layer("Background", canvas_img)]
            self.active_layer_index = 0
            self._refresh_layer_list()
            self.canvas.update()
        self._retitle(node.name)

    def _about(self):
        AboutDialog(self).exec()

    def _deactivate(self):
        XPMessageBox.information(
            self, "PhotoChop",
            "You have used 1 of 2 activations.\n\nDeactivating will let you activate "
            "PhotoChop on another computer. There is no other computer.",
        )
