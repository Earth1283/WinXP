"""The palettes.

Photoshop 7 docks its palettes in tabbed groups with a collapse arrow and a
close box: Navigator/Info, Color/Swatches/Styles, History/Actions,
Layers/Channels/Paths, Character/Paragraph, Brushes, Tool Presets. Each one
here is a real working panel over the live document.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter, QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QSlider,
    QSpinBox, QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from ... import theme
from . import brushes as brush_engine, pc_icons
from .model import BLEND_MODES

PALETTE_BG = "#ece9d8"
PALETTE_QSS = f"""
QWidget#pcPalette {{ background: {PALETTE_BG}; }}
QLabel {{ background: transparent; font-size: 11px; }}
QCheckBox {{ background: transparent; font-size: 11px; }}
QComboBox {{ font-size: 11px; }}
QListWidget, QTreeWidget {{ background: white; font-size: 11px; }}
QPushButton#palBtn {{
    border: 1px solid #9a9a8a; background: #f2f0e6; padding: 0px;
}}
QPushButton#palBtn:hover {{ background: #ffffff; }}
QPushButton#palBtn:pressed {{ background: #d8d5c8; }}
"""


def _mini_button(text, tip, slot=None, width=22):
    btn = QPushButton(text)
    btn.setObjectName("palBtn")
    btn.setToolTip(tip)
    btn.setFixedSize(width, 18)
    btn.setStyleSheet("font-size: 10px;")
    if slot:
        btn.clicked.connect(slot)
    return btn


class PaletteTitleBar(QWidget):
    """The grey strip with the collapse arrow, tabs and close box."""

    def __init__(self, group):
        super().__init__()
        self.group = group
        self.setFixedHeight(18)
        self._press = None

    def paintEvent(self, ev):
        p = QPainter(self)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor("#f6f5ee"))
        grad.setColorAt(1, QColor("#d6d3c4"))
        p.fillRect(self.rect(), QBrush(grad))
        p.setPen(QPen(QColor("#9a9a8a"), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        # collapse arrow
        p.setBrush(QColor("#4a4a4a"))
        p.setPen(Qt.PenStyle.NoPen)
        cx, cy = 8, self.height() // 2
        if self.group.collapsed:
            p.drawPolygon(QPoint(cx - 2, cy - 3), QPoint(cx + 3, cy), QPoint(cx - 2, cy + 3))
        else:
            p.drawPolygon(QPoint(cx - 3, cy - 2), QPoint(cx + 3, cy - 2), QPoint(cx, cy + 3))
        # close box
        p.setPen(QPen(QColor("#4a4a4a"), 1))
        r = QRect(self.width() - 14, cy - 4, 9, 9)
        p.drawRect(r)
        p.drawLine(r.topLeft() + QPoint(2, 2), r.bottomRight() - QPoint(2, 2))
        p.drawLine(r.topRight() + QPoint(-2, 2), r.bottomLeft() + QPoint(2, -2))
        p.end()

    def mousePressEvent(self, ev):
        if ev.position().x() > self.width() - 16:
            self.group.hide()
        elif ev.position().x() < 18:
            self.group.toggle_collapsed()


class PaletteTabs(QWidget):
    """The file-folder tabs PS uses to stack palettes in one group."""
    changed = pyqtSignal(int)

    def __init__(self, names):
        super().__init__()
        self.names = names
        self.current = 0
        self.setFixedHeight(19)
        self._rects = []

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setFont(QFont(theme.FONT_FAMILY, 7))
        p.fillRect(self.rect(), QColor(PALETTE_BG))
        x = 2
        self._rects = []
        for i, name in enumerate(self.names):
            w = p.fontMetrics().horizontalAdvance(name) + 16
            r = QRect(x, 0, w, self.height())
            self._rects.append(r)
            active = i == self.current
            p.setBrush(QColor("#ece9d8" if active else "#d6d3c4"))
            p.setPen(QPen(QColor("#9a9a8a"), 1))
            p.drawRoundedRect(QRectF(r.adjusted(0, 2 if not active else 0, 0, 2)), 3, 3)
            p.setPen(QColor("#1a1a1a" if active else "#555555"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, name)
            x += w + 2
        p.setPen(QPen(QColor("#9a9a8a"), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        if self._rects:
            r = self._rects[self.current]
            p.setPen(QPen(QColor(PALETTE_BG), 1))
            p.drawLine(r.left() + 1, self.height() - 1, r.right() - 1, self.height() - 1)
        p.end()

    def mousePressEvent(self, ev):
        for i, r in enumerate(self._rects):
            if r.contains(ev.position().toPoint()):
                self.current = i
                self.changed.emit(i)
                self.update()
                return


class PaletteGroup(QFrame):
    def __init__(self, palettes: list[tuple[str, QWidget]]):
        super().__init__()
        self.setObjectName("pcPalette")
        self.setStyleSheet(PALETTE_QSS)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.collapsed = False
        self.setMinimumHeight(74)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.title = PaletteTitleBar(self)
        layout.addWidget(self.title)
        self.tabs = PaletteTabs([n for n, _ in palettes])
        layout.addWidget(self.tabs)
        self.stack = QStackedWidget()
        # let the group shrink: without this the tallest palette in the stack
        # sets a floor on the whole window's minimum height
        self.stack.setMinimumHeight(36)
        self.stack.setSizePolicy(QSizePolicy.Policy.Preferred,
                                 QSizePolicy.Policy.Ignored)
        for _, widget in palettes:
            self.stack.addWidget(widget)
        layout.addWidget(self.stack, 1)
        self.tabs.changed.connect(self.stack.setCurrentIndex)

    def toggle_collapsed(self):
        self.collapsed = not self.collapsed
        self.stack.setVisible(not self.collapsed)
        self.title.update()

    def show_palette(self, name):
        for i in range(self.tabs.names.__len__()):
            if self.tabs.names[i] == name:
                self.tabs.current = i
                self.stack.setCurrentIndex(i)
                self.tabs.update()
                self.show()
                if self.collapsed:
                    self.toggle_collapsed()
                return True
        return False


# ---------------------------------------------------------------- layers ---

class LayerRow(QWidget):
    """One row: eye, link, thumbnail, mask thumbnail, name, effects marker."""

    def __init__(self, palette, index):
        super().__init__()
        self.palette = palette
        self.index = index
        self.setFixedHeight(34)
        self.setStyleSheet("background: transparent;")

    def layer(self):
        return self.palette.doc().layers[self.index]

    def paintEvent(self, ev):
        layer = self.layer()
        p = QPainter(self)
        active = self.palette.doc().active_index == self.index
        p.fillRect(self.rect(), QColor("#316ac5") if active else QColor("white"))
        text_colour = QColor("white") if active else QColor("black")

        # eye column
        p.setPen(QPen(QColor("#808080"), 1))
        p.drawLine(20, 0, 20, self.height())
        p.drawLine(38, 0, 38, self.height())
        if layer.visible:
            _draw_eye(p, QRect(3, 10, 15, 12))
        if layer.mask is not None and layer.mask_linked:
            _draw_link(p, QRect(24, 12, 11, 10))

        # pixel thumbnail
        thumb_rect = QRect(42, 3, 30, 28)
        p.setBrush(Qt.BrushStyle.NoBrush)   # the eye left a dark brush behind
        p.fillRect(thumb_rect, QColor("#ffffff"))
        thumb = layer.image.scaled(28, 26, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.FastTransformation)
        p.drawImage(thumb_rect.topLeft() + QPoint(1, 1), thumb)
        p.setPen(QPen(QColor("#606060"), 1))
        p.drawRect(thumb_rect)
        x = 76

        if layer.mask is not None:
            mask_rect = QRect(x, 3, 30, 28)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.fillRect(mask_rect, QColor("#ffffff"))
            p.drawImage(mask_rect.topLeft() + QPoint(1, 1),
                        layer.mask.scaled(28, 26, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.FastTransformation))
            p.setPen(QPen(QColor("#606060"), 1))
            p.drawRect(mask_rect)
            x += 34

        p.setPen(text_colour)
        f = p.font()
        f.setPointSize(8)
        f.setItalic(layer.kind == "adjustment")
        p.setFont(f)
        name = layer.name
        if layer.clipping:
            name = "    " + name
        p.drawText(QRect(x + 2, 0, self.width() - x - 24, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, name)
        if layer.has_style():
            p.setPen(text_colour)
            f.setItalic(True)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRect(self.width() - 22, 0, 18, self.height()),
                       Qt.AlignmentFlag.AlignCenter, "f")
        if layer.locked_all or layer.locked_pixels or layer.locked_transparency:
            _draw_lock(p, QRect(self.width() - 36, 12, 8, 11), text_colour)
        p.end()

    def mousePressEvent(self, ev):
        x = ev.position().x()
        if x < 20:
            self.layer().visible = not self.layer().visible
            self.palette.win.doc.invalidate()
            self.palette.win.refresh_all()
            return
        if 20 <= x < 38 and self.layer().mask is not None:
            self.layer().mask_linked = not self.layer().mask_linked
            self.update()
            return
        self.palette.doc().active_index = self.index
        self.palette.win.refresh_all()

    def mouseDoubleClickEvent(self, ev):
        if ev.position().x() > 40:
            self.palette.win.layer_properties()


def _draw_eye(p, r: QRect):
    p.setPen(QPen(QColor("#303030"), 1))
    p.setBrush(QColor("#ffffff"))
    path_rect = QRectF(r)
    p.drawEllipse(path_rect)
    p.setBrush(QColor("#303030"))
    c = path_rect.center()
    p.drawEllipse(c, 2.2, 2.2)


def _draw_link(p, r: QRect):
    p.setPen(QPen(QColor("#303030"), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(r.x(), r.y() + 2, 7, 5), 2, 2)
    p.drawRoundedRect(QRectF(r.x() + 4, r.y() + 3, 7, 5), 2, 2)


def _draw_lock(p, r: QRect, colour):
    p.setPen(QPen(colour, 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(r.x() + 1, r.y(), 6, 6), 0, 180 * 16)
    p.setBrush(colour)
    p.drawRect(QRectF(r.x(), r.y() + 4, 8, 6))


class LayersPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 4)
        root.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(4)
        self.blend = QComboBox()
        for mode in BLEND_MODES:
            if mode == "-":
                self.blend.insertSeparator(self.blend.count())
            else:
                self.blend.addItem(mode)
        self.blend.setFixedWidth(104)
        self.blend.currentTextChanged.connect(self._blend_changed)
        top.addWidget(self.blend)
        top.addStretch(1)
        top.addWidget(QLabel("Opacity:"))
        self.opacity = QSpinBox()
        self.opacity.setRange(0, 100)
        self.opacity.setValue(100)
        self.opacity.setSuffix("%")
        self.opacity.setFixedWidth(56)
        self.opacity.valueChanged.connect(self._opacity_changed)
        top.addWidget(self.opacity)
        root.addLayout(top)

        lock_row = QHBoxLayout()
        lock_row.setSpacing(3)
        lock_row.addWidget(QLabel("Lock:"))
        self.lock_boxes = {}
        for key, glyph, tip in (
                ("locked_transparency", "lock_transparent", "Lock transparent pixels"),
                ("locked_pixels", "lock_pixels", "Lock image pixels"),
                ("locked_position", "lock_position", "Lock position"),
                ("locked_all", "lock_all", "Lock all")):
            box = QToolButton()
            box.setCheckable(True)
            box.setIcon(pc_icons.icon(glyph, 14))
            box.setIconSize(QSize(14, 14))
            box.setFixedSize(18, 18)
            box.setToolTip(tip)
            box.toggled.connect(lambda v, k=key: self._lock_changed(k, v))
            self.lock_boxes[key] = box
            lock_row.addWidget(box)
        lock_row.addStretch(1)
        lock_row.addWidget(QLabel("Fill:"))
        self.fill = QSpinBox()
        self.fill.setRange(0, 100)
        self.fill.setValue(100)
        self.fill.setSuffix("%")
        self.fill.setFixedWidth(56)
        self.fill.valueChanged.connect(self._fill_changed)
        lock_row.addWidget(self.fill)
        root.addLayout(lock_row)

        self.list = QListWidget()
        self.list.setMinimumHeight(28)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list.setStyleSheet("QListWidget { border: 1px solid #808080; }")
        root.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for text, tip, slot in (
                ("f", "Add a layer style", win.layer_style),
                ("[]", "Add layer mask", win.add_layer_mask),
                ("[+]", "Create a new set", win.new_layer_set),
                ("(/)", "Create new fill or adjustment layer", win.new_adjustment_layer),
                ("+", "Create a new layer", win.new_layer),
                ("X", "Delete layer", win.delete_layer)):
            buttons.addWidget(_mini_button(text, tip, slot))
        buttons.addStretch(1)
        root.addLayout(buttons)
        self._syncing = False

    def doc(self):
        return self.win.doc

    def refresh(self):
        self._syncing = True
        self.list.clear()
        for i in range(len(self.doc().layers) - 1, -1, -1):
            item = QListWidgetItem()
            item.setSizeHint(QSize(10, 34))
            row = LayerRow(self, i)
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        layer = self.doc().active
        self.blend.setCurrentText(layer.blend)
        self.opacity.setValue(int(layer.opacity * 100))
        self.fill.setValue(int(layer.fill_opacity * 100))
        for key, box in self.lock_boxes.items():
            box.setChecked(getattr(layer, key))
        self._syncing = False

    def _blend_changed(self, name):
        if self._syncing or name == "":
            return
        self.doc().active.blend = name
        self.doc().invalidate()
        self.win.refresh_canvas()

    def _opacity_changed(self, value):
        if self._syncing:
            return
        self.doc().active.opacity = value / 100.0
        self.doc().invalidate()
        self.win.refresh_canvas()

    def _fill_changed(self, value):
        if self._syncing:
            return
        self.doc().active.fill_opacity = value / 100.0
        self.doc().invalidate()
        self.win.refresh_canvas()

    def _lock_changed(self, key, value):
        if self._syncing:
            return
        setattr(self.doc().active, key, value)
        if key == "locked_all" and value:
            for k in ("locked_transparency", "locked_pixels", "locked_position"):
                setattr(self.doc().active, k, True)
        self.refresh()


# -------------------------------------------------------------- channels ---

class ChannelsPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 4)
        root.setSpacing(4)
        self.list = QListWidget()
        self.list.setMinimumHeight(28)
        self.list.setStyleSheet("QListWidget { border: 1px solid #808080; }")
        self.list.setIconSize(QSize(34, 26))
        root.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for text, tip, slot in (
                ("()", "Load channel as selection", win.load_channel_selection),
                ("[]", "Save selection as channel", win.save_selection_channel),
                ("+", "Create new channel", win.new_alpha_channel),
                ("X", "Delete current channel", win.delete_alpha_channel)):
            buttons.addWidget(_mini_button(text, tip, slot))
        buttons.addStretch(1)
        root.addLayout(buttons)

    def refresh(self):
        doc = self.win.doc
        self.list.clear()
        composite = doc.composite()
        from . import imageops as ops
        buf, w, h = ops.to_buf(composite)
        entries = [("RGB", composite)]
        for label, channel in (("Red", ops.R), ("Green", ops.G), ("Blue", ops.B)):
            plane = ops.plane(buf, channel)
            grey = bytearray(w * h * 4)
            grey[0::4] = plane
            grey[1::4] = plane
            grey[2::4] = plane
            grey[3::4] = b"\xff" * (w * h)
            entries.append((label, ops.from_buf(grey, w, h)))
        for name, img in doc.alpha_channels:
            entries.append((name, img))
        for name, img in entries:
            item = QListWidgetItem(name)
            item.setIcon(_thumb_icon(img))
            self.list.addItem(item)


def _thumb_icon(img: QImage) -> "QIcon":
    from PyQt6.QtGui import QIcon
    return QIcon(QPixmap.fromImage(img.scaled(
        34, 26, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation)))


# ----------------------------------------------------------------- paths ---

class PathsPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 4)
        root.setSpacing(4)
        self.list = QListWidget()
        self.list.setMinimumHeight(28)
        self.list.setStyleSheet("QListWidget { border: 1px solid #808080; }")
        root.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for text, tip, slot in (
                ("F", "Fill path with foreground color", win.fill_path),
                ("O", "Stroke path with brush", win.stroke_path),
                ("()", "Load path as selection", win.path_to_selection),
                ("^", "Make work path from selection", win.selection_to_path),
                ("+", "Create new path", win.new_path),
                ("X", "Delete current path", win.delete_path)):
            buttons.addWidget(_mini_button(text, tip, slot))
        buttons.addStretch(1)
        root.addLayout(buttons)

    def refresh(self):
        self.list.clear()
        for name, _ in self.win.doc.paths:
            self.list.addItem(name)


# --------------------------------------------------------------- history ---

class HistoryPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 4)
        root.setSpacing(3)
        self.snapshots = QListWidget()
        self.snapshots.setFixedHeight(34)
        self.snapshots.setStyleSheet("QListWidget { border: 1px solid #808080; }")
        self.snapshots.itemClicked.connect(self._snapshot_clicked)
        root.addWidget(self.snapshots)
        self.list = QListWidget()
        self.list.setMinimumHeight(28)
        self.list.setStyleSheet("QListWidget { border: 1px solid #808080; }")
        self.list.itemClicked.connect(self._state_clicked)
        root.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for text, tip, slot in (
                ("[]", "Create new document from current state", win.duplicate_document),
                ("O", "Create new snapshot", win.new_snapshot),
                ("X", "Delete current state", win.delete_history_state)):
            buttons.addWidget(_mini_button(text, tip, slot))
        buttons.addStretch(1)
        root.addLayout(buttons)
        self._syncing = False

    def refresh(self):
        self._syncing = True
        hist = self.win.doc.history
        self.snapshots.clear()
        for snap in hist.snapshots:
            self.snapshots.addItem(snap.name)
        self.list.clear()
        for i, state in enumerate(hist.states):
            item = QListWidgetItem(state.name)
            if i > hist.index:
                item.setForeground(QColor("#a0a0a0"))
            self.list.addItem(item)
        if 0 <= hist.index < self.list.count():
            self.list.setCurrentRow(hist.index)
        self._syncing = False

    def _state_clicked(self, item):
        if self._syncing:
            return
        self.win.doc.history.step_to(self.list.row(item))
        self.win.refresh_all()

    def _snapshot_clicked(self, item):
        if self._syncing:
            return
        idx = self.snapshots.row(item)
        hist = self.win.doc.history
        if 0 <= idx < len(hist.snapshots):
            hist.restore_snapshot(hist.snapshots[idx])
            self.win.refresh_all()


# --------------------------------------------------------------- actions ---

DEFAULT_ACTIONS = {
    "Default Actions.atn": [
        ("Vignette (selection)", "F1"), ("Frame Channel - 50 pixel", ""),
        ("Wood Frame - 50 pixel", ""), ("Cast Shadow (type)", ""),
        ("Water Reflection (type)", ""), ("Custom RGB to Grayscale", ""),
        ("Molten Lead", ""), ("Make Clip Path (selection)", ""),
        ("Sepia Toning (layer)", ""), ("Quadrant Colors", ""),
        ("Save As Photoshop PDF", ""), ("Gradient Map", ""),
    ],
}


class ActionsPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 4)
        root.setSpacing(4)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("QTreeWidget { border: 1px solid #808080; }")
        for set_name, actions in DEFAULT_ACTIONS.items():
            root_item = QTreeWidgetItem([set_name])
            for name, key in actions:
                child = QTreeWidgetItem([name + (f"   {key}" if key else "")])
                child.setCheckState(0, Qt.CheckState.Checked)
                root_item.addChild(child)
            self.tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)
        root.addWidget(self.tree, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for text, tip, slot in (
                ("[]", "Stop playing/recording", None),
                ("O", "Begin recording", win.record_action),
                (">", "Play selection", win.play_action),
                ("[+]", "Create new set", None),
                ("+", "Create new action", win.record_action),
                ("X", "Delete", None)):
            buttons.addWidget(_mini_button(text, tip, slot))
        buttons.addStretch(1)
        root.addLayout(buttons)

    def refresh(self):
        pass

    def current_action(self):
        item = self.tree.currentItem()
        return item.text(0).split("   ")[0] if item and item.parent() else None


# ------------------------------------------------------------- navigator ---

class NavigatorPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 4)
        root.setSpacing(4)
        self.view = _NavigatorView(win)
        root.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.zoom_field = QLineEdit("100%")
        self.zoom_field.setFixedWidth(52)
        self.zoom_field.returnPressed.connect(self._zoom_typed)
        row.addWidget(self.zoom_field)
        row.addStretch(1)
        out = _mini_button("-", "Zoom out", win.canvas_zoom_out, 18)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setFixedWidth(90)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.sliderMoved.connect(self._slider_moved)
        in_btn = _mini_button("+", "Zoom in", win.canvas_zoom_in, 18)
        row.addWidget(out)
        row.addWidget(self.slider)
        row.addWidget(in_btn)
        root.addLayout(row)

    def refresh(self):
        zoom = self.win.canvas.zoom
        pct = zoom * 100
        self.zoom_field.setText(f"{pct:.2f}%".rstrip("0").rstrip(".") + "%"
                                if False else f"{pct:.1f}%")
        import math
        t = (math.log(max(0.005, zoom), 2) + 8) / 12 * 100
        self.slider.blockSignals(True)
        self.slider.setValue(int(max(0, min(100, t))))
        self.slider.blockSignals(False)
        self.view.update()

    def _slider_moved(self, v):
        zoom = 2 ** (v / 100 * 12 - 8)
        self.win.canvas.set_zoom(zoom)

    def _zoom_typed(self):
        try:
            value = float(self.zoom_field.text().strip().rstrip("%"))
            self.win.canvas.set_zoom(max(0.33, value) / 100.0)
        except ValueError:
            pass


class _NavigatorView(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setMinimumHeight(96)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ffffff"))
        doc = self.win.doc
        img = doc.composite()
        scaled = img.scaled(self.width() - 8, self.height() - 8,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        ox = (self.width() - scaled.width()) // 2
        oy = (self.height() - scaled.height()) // 2
        p.drawImage(ox, oy, scaled)
        p.setPen(QPen(QColor("#808080"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRect(ox, oy, scaled.width(), scaled.height()))

        canvas = self.win.canvas
        if canvas.zoom > 0 and scaled.width():
            k = scaled.width() / doc.width
            view_w = canvas.width() / canvas.zoom * k
            view_h = canvas.height() / canvas.zoom * k
            cx = ox + (doc.width / 2 + canvas.pan.x()) * k
            cy = oy + (doc.height / 2 + canvas.pan.y()) * k
            p.setPen(QPen(QColor("#e02020"), 1))
            p.setClipRect(QRect(ox, oy, scaled.width(), scaled.height()))
            p.drawRect(QRectF(cx - view_w / 2, cy - view_h / 2, view_w, view_h))
            p.setClipping(False)
        p.end()

    def mousePressEvent(self, ev):
        self._recentre(ev.position())

    def mouseMoveEvent(self, ev):
        self._recentre(ev.position())

    def _recentre(self, pos):
        doc = self.win.doc
        scaled_w = self.width() - 8
        k = scaled_w / doc.width
        ox = (self.width() - scaled_w) // 2
        oy = (self.height() - doc.height * k) // 2
        self.win.canvas.pan = QPointF((pos.x() - ox) / k - doc.width / 2,
                                      (pos.y() - oy) / k - doc.height / 2)
        self.win.canvas.update()
        self.update()


# ------------------------------------------------------------------ info ---

class InfoPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        grid = QGridLayout(self)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(3)
        self.rgb = QLabel("R :\nG :\nB :")
        self.cmyk = QLabel("C :\nM :\nY :\nK :")
        self.pos = QLabel("X :\nY :")
        self.dim = QLabel("W :\nH :")
        for w in (self.rgb, self.cmyk, self.pos, self.dim):
            w.setStyleSheet("background: transparent; font-size: 10px;")
        grid.addWidget(self.rgb, 0, 0)
        grid.addWidget(self.cmyk, 0, 1)
        grid.addWidget(self.pos, 1, 0)
        grid.addWidget(self.dim, 1, 1)
        self.samplers = QLabel("")
        self.samplers.setStyleSheet("background: transparent; font-size: 10px;")
        grid.addWidget(self.samplers, 2, 0, 1, 2)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("background: transparent; font-size: 10px; color: #444;")
        grid.addWidget(self.hint, 3, 0, 1, 2)
        grid.setRowStretch(3, 1)

    def refresh(self):
        pass

    def set_pixel(self, pos, colour: QColor | None):
        if pos is None or colour is None:
            self.rgb.setText("R :\nG :\nB :")
            self.cmyk.setText("C :\nM :\nY :\nK :")
            self.pos.setText("X :\nY :")
            return
        r, g, b = colour.red(), colour.green(), colour.blue()
        self.rgb.setText(f"R : {r}\nG : {g}\nB : {b}")
        c, m, y = 255 - r, 255 - g, 255 - b
        k = min(c, m, y)
        denom = max(1, 255 - k)
        self.cmyk.setText(
            f"C : {int((c - k) * 100 / denom)}%\nM : {int((m - k) * 100 / denom)}%\n"
            f"Y : {int((y - k) * 100 / denom)}%\nK : {int(k * 100 / 255)}%")
        self.pos.setText(f"X : {pos.x()}\nY : {pos.y()}")

    def set_dimensions(self, w, h):
        self.dim.setText(f"W : {w}\nH : {h}")

    def set_samplers(self, points):
        lines = []
        img = self.win.doc.composite()
        for i, pt in enumerate(points, 1):
            c = img.pixelColor(int(pt.x()), int(pt.y()))
            lines.append(f"#{i} R:{c.red()} G:{c.green()} B:{c.blue()}")
        self.samplers.setText("\n".join(lines))

    def set_hint(self, text):
        self.hint.setText(text)


# ----------------------------------------------------------------- color ---

class ColorPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 4)
        root.setSpacing(4)
        top = QHBoxLayout()
        self.swatches = _FgBgSwatch(win)
        top.addWidget(self.swatches)
        sliders = QVBoxLayout()
        sliders.setSpacing(2)
        self.sliders = {}
        for name in ("R", "G", "B"):
            row = QHBoxLayout()
            row.setSpacing(4)
            label = QLabel(name)
            label.setFixedWidth(10)
            row.addWidget(label)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 255)
            slider.valueChanged.connect(self._changed)
            row.addWidget(slider, 1)
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setFixedWidth(46)
            spin.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(spin.setValue)
            row.addWidget(spin)
            sliders.addLayout(row)
            self.sliders[name] = slider
        top.addLayout(sliders, 1)
        root.addLayout(top)
        self.ramp = _SpectrumRamp(win)
        root.addWidget(self.ramp)
        self._syncing = False

    def refresh(self):
        self._syncing = True
        c = self.win.fg_color
        self.sliders["R"].setValue(c.red())
        self.sliders["G"].setValue(c.green())
        self.sliders["B"].setValue(c.blue())
        self.swatches.update()
        self._syncing = False

    def _changed(self, _):
        if self._syncing:
            return
        self.win.set_fg_color(QColor(self.sliders["R"].value(),
                                     self.sliders["G"].value(),
                                     self.sliders["B"].value()))


class _FgBgSwatch(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedSize(42, 42)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setPen(QPen(QColor("#606060"), 1))
        p.setBrush(self.win.bg_color)
        p.drawRect(14, 14, 26, 26)
        p.setBrush(self.win.fg_color)
        p.drawRect(1, 1, 26, 26)
        p.end()

    def mousePressEvent(self, ev):
        if ev.position().x() > 20 and ev.position().y() > 20:
            self.win.pick_bg_color()
        else:
            self.win.pick_fg_color()


class _SpectrumRamp(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self, ev):
        p = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        for i in range(13):
            grad.setColorAt(i / 12, QColor.fromHsv(int(i * 30) % 360, 255, 255))
        p.fillRect(QRect(0, 0, self.width(), self.height() - 6), QBrush(grad))
        grey = QLinearGradient(0, 0, self.width(), 0)
        grey.setColorAt(0, QColor("black"))
        grey.setColorAt(1, QColor("white"))
        p.fillRect(QRect(0, self.height() - 6, self.width(), 6), QBrush(grey))
        p.end()

    def mousePressEvent(self, ev):
        pm = self.grab().toImage()
        colour = pm.pixelColor(int(ev.position().x()), int(ev.position().y()))
        if ev.button() == Qt.MouseButton.RightButton:
            self.win.set_bg_color(colour)
        else:
            self.win.set_fg_color(colour)


# -------------------------------------------------------------- swatches ---

SWATCH_COLORS = [
    "#000000", "#404040", "#808080", "#c0c0c0", "#ffffff", "#7f0000", "#ff0000",
    "#ff7f7f", "#7f3f00", "#ff7f00", "#ffbf7f", "#7f7f00", "#ffff00", "#ffff7f",
    "#007f00", "#00ff00", "#7fff7f", "#007f7f", "#00ffff", "#7fffff", "#00007f",
    "#0000ff", "#7f7fff", "#3f007f", "#7f00ff", "#bf7fff", "#7f007f", "#ff00ff",
    "#ff7fff", "#3f2000", "#7f5020", "#bf8040", "#402000", "#c08040", "#e0c0a0",
    "#1a3d1a", "#2d5f2d", "#5f9f5f", "#1a2d5f", "#2d4f9f", "#5f7fbf", "#5f1a1a",
]


class SwatchesPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)
        grid = QGridLayout()
        grid.setSpacing(1)
        for i, colour in enumerate(SWATCH_COLORS):
            btn = _SwatchButton(win, colour)
            grid.addWidget(btn, i // 14, i % 14)
        root.addLayout(grid)
        root.addStretch(1)

    def refresh(self):
        pass


class _SwatchButton(QWidget):
    def __init__(self, win, colour):
        super().__init__()
        self.win = win
        self.colour = QColor(colour)
        self.setFixedSize(13, 13)
        self.setToolTip(colour)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), self.colour)
        p.setPen(QPen(QColor("#808080"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            self.win.set_bg_color(self.colour)
        else:
            self.win.set_fg_color(self.colour)


# ---------------------------------------------------------------- styles ---

PRESET_STYLES = [
    ("Default Style (None)", {}),
    ("Drop Shadow", {"Drop Shadow": dict(enabled=True, color="#000000", opacity=75,
                                         angle=120, distance=5, spread=0, size=5)}),
    ("Basic Drop Shadow", {"Drop Shadow": dict(enabled=True, color="#000000", opacity=60,
                                               angle=120, distance=9, spread=0, size=9)}),
    ("Outer Glow", {"Outer Glow": dict(enabled=True, color="#ffffbe", opacity=75,
                                       spread=0, size=9)}),
    ("Blue Glass", {"Bevel and Emboss": dict(enabled=True, style="Inner Bevel", depth=140,
                                             direction="Up", size=7, soften=2, angle=120,
                                             altitude=30),
                    "Color Overlay": dict(enabled=True, color="#3a6ea5", opacity=55)}),
    ("Chiselled Metal", {"Bevel and Emboss": dict(enabled=True, style="Emboss", depth=220,
                                                  direction="Up", size=4, soften=0,
                                                  angle=120, altitude=30),
                         "Gradient Overlay": dict(enabled=True, start="#5a5a5a",
                                                  end="#e8e8e8", opacity=70, angle=90)}),
    ("Sunset Sky", {"Gradient Overlay": dict(enabled=True, start="#ff7e5f",
                                             end="#feb47b", opacity=100, angle=90)}),
    ("Red Stroke", {"Stroke": dict(enabled=True, color="#c02020", size=3,
                                   position="Outside", opacity=100)}),
    ("Puffy Type", {"Bevel and Emboss": dict(enabled=True, style="Pillow Emboss", depth=100,
                                             direction="Up", size=9, soften=3, angle=120,
                                             altitude=30),
                    "Drop Shadow": dict(enabled=True, color="#000000", opacity=50,
                                        angle=120, distance=4, spread=0, size=6)}),
]


class StylesPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(38, 38))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setSpacing(2)
        self.list.setStyleSheet("QListWidget { border: 1px solid #808080; }")
        self.list.itemClicked.connect(self._apply)
        for name, style in PRESET_STYLES:
            item = QListWidgetItem()
            item.setToolTip(name)
            item.setIcon(_style_thumb(style))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list.addItem(item)
        root.addWidget(self.list, 1)

    def refresh(self):
        pass

    def _apply(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        style = dict(next(s for n, s in PRESET_STYLES if n == name))
        self.win.apply_preset_style(style)


def _style_thumb(style) -> "QIcon":
    from PyQt6.QtGui import QIcon
    from .model import default_style
    from .layer_styles import render_style
    base = QImage(38, 38, QImage.Format.Format_ARGB32_Premultiplied)
    base.fill(Qt.GlobalColor.transparent)
    p = QPainter(base)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#b0b0b0"))
    p.drawRoundedRect(QRectF(7, 7, 24, 24), 4, 4)
    p.end()
    merged = default_style()
    for key, cfg in (style or {}).items():
        merged[key] = dict(cfg)
    out = render_style(base, merged) if style else base
    return QIcon(QPixmap.fromImage(out))


# ------------------------------------------------------------- character ---

class CharacterPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        grid = QGridLayout(self)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(3)
        self.family = QComboBox()
        self.family.addItems(QFontDatabase.families()[:80])
        self.family.setCurrentText("Tahoma")
        self.style = QComboBox()
        self.style.addItems(["Regular", "Italic", "Bold", "Bold Italic"])
        self.size = QComboBox()
        self.size.setEditable(True)
        self.size.addItems([str(s) for s in (6, 8, 9, 10, 11, 12, 14, 18, 24, 30, 36,
                                             48, 60, 72)])
        self.size.setCurrentText("24")
        self.leading = QComboBox()
        self.leading.setEditable(True)
        self.leading.addItems(["Auto", "12", "14", "18", "24", "30", "36"])
        self.tracking = QSpinBox()
        self.tracking.setRange(-1000, 1000)
        self.anti = QComboBox()
        self.anti.addItems(["None", "Sharp", "Crisp", "Strong", "Smooth"])
        self.anti.setCurrentText("Crisp")
        grid.addWidget(self.family, 0, 0, 1, 2)
        grid.addWidget(self.style, 1, 0, 1, 2)
        grid.addWidget(QLabel("Size"), 2, 0)
        grid.addWidget(self.size, 2, 1)
        grid.addWidget(QLabel("Leading"), 3, 0)
        grid.addWidget(self.leading, 3, 1)
        grid.addWidget(QLabel("Tracking"), 4, 0)
        grid.addWidget(self.tracking, 4, 1)
        grid.addWidget(QLabel("a a"), 5, 0)
        grid.addWidget(self.anti, 5, 1)
        grid.setRowStretch(6, 1)
        for w in (self.family, self.style, self.size, self.anti):
            w.currentTextChanged.connect(self._changed)
        self.tracking.valueChanged.connect(self._changed)

    def refresh(self):
        font = self.win.options.get("font", {})
        self.family.setCurrentText(font.get("family", "Tahoma"))
        self.size.setCurrentText(str(font.get("size", 24)))

    def _changed(self, *_):
        font = dict(self.win.options.get("font", {}))
        font["family"] = self.family.currentText()
        font["style"] = self.style.currentText()
        try:
            font["size"] = int(self.size.currentText())
        except ValueError:
            pass
        font["antialias"] = self.anti.currentText()
        font["tracking"] = self.tracking.value()
        self.win.options["font"] = font
        self.win.sync_options_bar()


class ParagraphPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        grid = QGridLayout(self)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(3)
        row = QHBoxLayout()
        self.align = {}
        for key, label in (("left", "≡L"), ("center", "≡C"), ("right", "≡R")):
            btn = QPushButton(label)
            btn.setObjectName("palBtn")
            btn.setCheckable(True)
            btn.setFixedSize(26, 18)
            btn.clicked.connect(lambda _, k=key: self._set_align(k))
            self.align[key] = btn
            row.addWidget(btn)
        self.align["left"].setChecked(True)
        row.addStretch(1)
        grid.addLayout(row, 0, 0, 1, 2)
        self.indent = QSpinBox()
        self.indent.setRange(0, 400)
        self.space_before = QSpinBox()
        self.space_before.setRange(0, 400)
        grid.addWidget(QLabel("Indent"), 1, 0)
        grid.addWidget(self.indent, 1, 1)
        grid.addWidget(QLabel("Space"), 2, 0)
        grid.addWidget(self.space_before, 2, 1)
        self.hyphenate = QCheckBox("Hyphenate")
        grid.addWidget(self.hyphenate, 3, 0, 1, 2)
        grid.setRowStretch(4, 1)

    def refresh(self):
        pass

    def _set_align(self, key):
        for k, btn in self.align.items():
            btn.setChecked(k == key)
        font = dict(self.win.options.get("font", {}))
        font["align"] = key
        self.win.options["font"] = font


# --------------------------------------------------------------- brushes ---

class BrushesPalette(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)
        self.list = QListWidget()
        self.list.setMinimumHeight(28)
        self.list.setStyleSheet("QListWidget { border: 1px solid #808080; }")
        self.list.setIconSize(QSize(40, 22))
        self.list.itemClicked.connect(self._pick)
        for name, size, hardness in brush_engine.BRUSH_PRESETS:
            item = QListWidgetItem(f"  {size}")
            item.setIcon(_brush_icon(size, hardness))
            item.setData(Qt.ItemDataRole.UserRole, (name, size, hardness))
            item.setToolTip(name)
            self.list.addItem(item)
        root.addWidget(self.list, 1)

        self.size = QSlider(Qt.Orientation.Horizontal)
        self.size.setRange(1, 300)
        self.size.setValue(13)
        self.size.valueChanged.connect(self._size_changed)
        self.hardness = QSlider(Qt.Orientation.Horizontal)
        self.hardness.setRange(0, 100)
        self.hardness.setValue(100)
        self.hardness.valueChanged.connect(self._hardness_changed)
        self.spacing = QSlider(Qt.Orientation.Horizontal)
        self.spacing.setRange(1, 200)
        self.spacing.setValue(25)
        self.spacing.valueChanged.connect(self._spacing_changed)
        for label, widget in (("Master Diameter", self.size), ("Hardness", self.hardness),
                              ("Spacing", self.spacing)):
            root.addWidget(QLabel(label))
            root.addWidget(widget)

    def refresh(self):
        brush = self.win.options.get("brush", {})
        for slider, key, default in ((self.size, "size", 13),
                                     (self.hardness, "hardness", 100),
                                     (self.spacing, "spacing", 25)):
            slider.blockSignals(True)
            slider.setValue(int(brush.get(key, default)))
            slider.blockSignals(False)

    def _pick(self, item):
        name, size, hardness = item.data(Qt.ItemDataRole.UserRole)
        brush = dict(self.win.options.get("brush", {}))
        brush.update(preset=name, size=size, hardness=hardness)
        self.win.options["brush"] = brush
        self.refresh()
        self.win.sync_options_bar()

    def _update(self, key, value):
        brush = dict(self.win.options.get("brush", {}))
        brush[key] = value
        self.win.options["brush"] = brush
        self.win.sync_options_bar()

    def _size_changed(self, v):
        self._update("size", v)

    def _hardness_changed(self, v):
        self._update("hardness", v)

    def _spacing_changed(self, v):
        self._update("spacing", v)


def _brush_icon(size, hardness) -> "QIcon":
    from PyQt6.QtGui import QIcon
    pm = QPixmap(40, 22)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    dab = brush_engine.coloured_stamp(min(20, max(2, size)), hardness, QColor("black"))
    p.drawImage(QPoint(20 - dab.width() // 2, 11 - dab.height() // 2), dab)
    p.end()
    return QIcon(pm)


class ToolPresetsPalette(QWidget):
    PRESETS = [
        ("Crop 4 inch x 6 inch 300 ppi", "crop"),
        ("Crop 5 inch x 3 inch 300 ppi", "crop"),
        ("Magnetic Lasso 24 pixels", "magnetic_lasso"),
        ("Type Tahoma 24 pt", "type_h"),
        ("Soft Round 45 Brush", "brush"),
        ("Healing Brush 21", "healing"),
        ("Fill with Bubbles Pattern", "bucket"),
        ("Airbrush Soft Round 65", "brush"),
    ]

    def __init__(self, win):
        super().__init__()
        self.win = win
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget()
        self.list.setMinimumHeight(28)
        self.list.setStyleSheet("QListWidget { border: 1px solid #808080; }")
        self.list.itemClicked.connect(self._pick)
        for name, tool in self.PRESETS:
            item = QListWidgetItem(name)
            item.setIcon(pc_icons.icon(_tool_icon_name(tool), 16))
            item.setData(Qt.ItemDataRole.UserRole, tool)
            self.list.addItem(item)
        root.addWidget(self.list, 1)
        self.current_only = QCheckBox("Current Tool Only")
        root.addWidget(self.current_only)

    def refresh(self):
        pass

    def _pick(self, item):
        self.win.select_tool(item.data(Qt.ItemDataRole.UserRole))


def _tool_icon_name(tool_id):
    from .tools import ALL_TOOLS
    spec = ALL_TOOLS.get(tool_id)
    return spec.icon if spec else "brush"
