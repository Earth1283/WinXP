from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from .. import icons, image_codec, theme, vfs as vfs_mod
from ..color_dialog import XPColorDialog
from ..vfs_dialog import VfsFileDialog
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox

TOOLS = [
    ("pencil", "tool_pencil", "Pencil"),
    ("brush", "tool_brush", "Brush"),
    ("eraser", "tool_eraser", "Eraser"),
    ("fill", "tool_fill", "Fill With Color"),
    ("eyedropper", "tool_eyedropper", "Pick Color"),
    ("text", "tool_text", "Text"),
    ("line", "tool_line", "Line"),
    ("rect", "tool_rect", "Rectangle"),
    ("ellipse", "tool_ellipse", "Ellipse"),
]

WIDTHS = (1, 3, 5, 8)

# Default quick-access palette (matches the classic MS Paint bottom row).
PALETTE_ROW = [
    "#000000", "#7f7f7f", "#880015", "#ed1c24", "#ff7f27", "#fff200", "#22b14c", "#00a2e8",
    "#3f48cc", "#a349a4", "#ffffff", "#c3c3c3", "#b97a57", "#ffaec9", "#ffc90e", "#efe4b0",
    "#b5e61d", "#99d9ea", "#7092be", "#c8bfe7",
]

TOOL_BTN_QSS = """
    QPushButton { border: 1px solid transparent; border-radius: 2px; background: transparent; }
    QPushButton:hover { border: 1px solid #7da2ce; background: #eaf3ff; }
    QPushButton:checked { border: 1px solid #3169c6; background: #c2ddfc; }
"""


def _width_icon(thickness, w=44, h=16):
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("black"), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(4, h // 2, w - 4, h // 2)
    p.end()
    return QIcon(pm)


class ToolButton(QPushButton):
    def __init__(self, icon_key, tooltip, size=28):
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(size, size)
        self.setIcon(icons.icon(icon_key, 18))
        self.setIconSize(QSize(18, 18))
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(TOOL_BTN_QSS)


class PaletteSwatch(QPushButton):
    def __init__(self, color, set_fg, set_bg):
        super().__init__()
        self.color = color
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"background: {color}; border: 1px solid #808080;")
        self._set_fg = set_fg
        self._set_bg = set_bg

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._set_fg(self.color)
        elif ev.button() == Qt.MouseButton.RightButton:
            self._set_bg(self.color)


class ColorIndicator(QWidget):
    """Overlapping fg/bg swatches, like the one next to MS Paint's palette."""

    def __init__(self, get_fg, get_bg, set_fg, set_bg):
        super().__init__()
        self.setFixedSize(38, 34)
        self.get_fg = get_fg
        self.get_bg = get_bg
        self.set_fg = set_fg
        self.set_bg = set_bg

        self.bg_btn = QPushButton(self)
        self.bg_btn.setGeometry(14, 14, 20, 20)
        self.bg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bg_btn.clicked.connect(self._pick_bg)

        self.fg_btn = QPushButton(self)
        self.fg_btn.setGeometry(0, 0, 20, 20)
        self.fg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fg_btn.clicked.connect(self._pick_fg)
        self.fg_btn.raise_()

        self.refresh()

    def refresh(self):
        self.bg_btn.setStyleSheet(f"background: {self.get_bg().name()}; border: 1px solid #555;")
        self.fg_btn.setStyleSheet(f"background: {self.get_fg().name()}; border: 1px solid #555;")

    def _pick_fg(self):
        c = XPColorDialog.get_color(self, self.get_fg())
        if c:
            self.set_fg(c)

    def _pick_bg(self):
        c = XPColorDialog.get_color(self, self.get_bg())
        if c:
            self.set_bg(c)


class Canvas(QWidget):
    def __init__(self, width=560, height=380):
        super().__init__()
        self.setFixedSize(width, height)
        self.pixmap = image_codec.blank(width, height)
        self.tool = "pencil"
        self.fg = QColor("black")
        self.bg = QColor("white")
        self.pen_width = 3
        self.dirty = False
        self.on_dirty = None
        self.on_color_picked = None

        self._last = None
        self._drawing_color = None
        self._shape_start = None
        self._pre_shape_pixmap = None
        self._text_edit = None
        self._text_pos = None
        self._text_color = None

    def load_pixmap(self, pixmap: QPixmap):
        self.pixmap = pixmap
        self.setFixedSize(pixmap.size())
        self.update()

    def clear(self, color=None):
        self.pixmap.fill(color or Qt.GlobalColor.white)
        self._mark_dirty()
        self.update()

    def set_tool(self, tool):
        self._commit_text()
        self.tool = tool

    def set_width(self, w):
        self.pen_width = w

    def _mark_dirty(self):
        self.dirty = True
        if self.on_dirty:
            self.on_dirty()

    def mousePressEvent(self, ev):
        if self.tool != "text":
            self._commit_text()
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
            sampled = self.pixmap.toImage().pixelColor(pos)
            if ev.button() == Qt.MouseButton.LeftButton:
                self.fg = sampled
            else:
                self.bg = sampled
            if self.on_color_picked:
                self.on_color_picked()
        elif self.tool in ("line", "rect", "ellipse"):
            self._shape_start = pos
            self._pre_shape_pixmap = self.pixmap.copy()
        elif self.tool == "text":
            self._start_text(pos, color)

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
            self._pre_shape_pixmap = None
            self._mark_dirty()
        self._last = None
        self._drawing_color = None

    def _stroke_to(self, a, b):
        if self.tool == "eraser":
            color, width = self.bg, max(8, self.pen_width * 3)
        elif self.tool == "pencil":
            color, width = self._drawing_color, 1
        else:
            color, width = self._drawing_color, self.pen_width
        painter = QPainter(self.pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, self.tool != "pencil")
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                             Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(a, b)
        painter.end()
        self._mark_dirty()
        self.update()

    def _preview_shape(self, current):
        self.pixmap = self._pre_shape_pixmap.copy()
        painter = QPainter(self.pixmap)
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
        img = self.pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        w, h = img.width(), img.height()
        x0, y0 = pos.x(), pos.y()
        if not (0 <= x0 < w and 0 <= y0 < h):
            return
        target = img.pixelColor(x0, y0)
        replacement = QColor(color)
        if target.rgb() == replacement.rgb():
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
            if img.pixelColor(x, y).rgb() != target.rgb():
                continue
            seen[idx] = 1
            img.setPixelColor(x, y, replacement)
            stack.append((x + 1, y))
            stack.append((x - 1, y))
            stack.append((x, y + 1))
            stack.append((x, y - 1))
        self.pixmap = QPixmap.fromImage(img)
        self._mark_dirty()
        self.update()

    def _start_text(self, pos, color):
        self._commit_text()
        edit = QLineEdit(self)
        edit.move(pos)
        edit.resize(180, 24)
        edit.setStyleSheet(
            f"background: transparent; border: 1px dashed #555; color: {color.name()}; font-size: 14px;"
        )
        edit.show()
        edit.setFocus()
        edit.editingFinished.connect(self._commit_text)
        self._text_edit = edit
        self._text_pos = pos
        self._text_color = color

    def _commit_text(self):
        edit = self._text_edit
        if edit is None:
            return
        self._text_edit = None
        text = edit.text()
        edit.deleteLater()
        if not text:
            return
        painter = QPainter(self.pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self._text_color)
        font = painter.font()
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(self._text_pos.x(), self._text_pos.y() + 16, text)
        painter.end()
        self._mark_dirty()
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.pixmap)


class PaintWindow(XPWindow):
    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="untitled - Paint", icon_key="paint", size=QSize(700, 560))
        self.node_id = None

        self.canvas = Canvas()
        self.canvas.on_dirty = self._on_dirty
        self.canvas.on_color_picked = self._sync_indicator

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
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
        root.addLayout(body, 1)

        root.addWidget(self._build_palette())
        self.set_content_layout(root)

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

        bar.addMenu("&Edit")
        bar.addMenu("&View")

        image_menu = bar.addMenu("&Image")
        image_menu.addAction(self._act("&Clear Image", self._clear_image))

        colors_menu = bar.addMenu("&Colors")
        colors_menu.addAction(self._act("&Edit Colors...", self._edit_colors))

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self._act("&About Paint", self._about))
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

    def _sync_indicator(self):
        self.indicator.refresh()

    def _edit_colors(self):
        c = XPColorDialog.get_color(self, self.canvas.fg)
        if c:
            self._set_fg(c)

    def _clear_image(self):
        self.canvas.clear()

    # -- dirty / title ------------------------------------------------------
    def _on_dirty(self):
        title = self.windowTitle()
        if not title.startswith("*"):
            self.setWindowTitle("*" + title)

    def _retitle(self, name):
        self.setWindowTitle(f"{name} - Paint")

    # -- file I/O ---------------------------------------------------------
    def new_file(self):
        self.canvas.clear()
        self.node_id = None
        self.setWindowTitle("untitled - Paint")

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.IMAGE,), title="Open")
        if node_id:
            self.node_id = node_id
            self._load_node(node_id)

    def save_file(self):
        if self.node_id:
            vfs_mod.vfs.write_blob(self.node_id, image_codec.to_bytes(self.canvas.pixmap))
            self.canvas.dirty = False
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
        data = image_codec.to_bytes(self.canvas.pixmap)
        if existing:
            vfs_mod.vfs.write_blob(existing.id, data)
            self.node_id = existing.id
        else:
            node = vfs_mod.vfs.create_image_file(folder_id, name, data)
            self.node_id = node.id
        self.canvas.dirty = False
        self._retitle(vfs_mod.vfs.get(self.node_id).name)

    def _load_node(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        pm = image_codec.from_bytes(vfs_mod.vfs.read_blob(node_id))
        if not pm.isNull():
            self.canvas.load_pixmap(pm)
        self._retitle(node.name)

    def _about(self):
        XPMessageBox.information(
            self, "About Paint",
            "Paint\nVersion 5.1 (Build 2600.xpsp_sp3)\n\n"
            "© Microsoft Corporation. All rights reserved."
        )
