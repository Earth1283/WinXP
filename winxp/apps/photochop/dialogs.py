"""Dialog furniture.

Photoshop dialogs have a shape of their own: controls on the left, an OK /
Cancel column pinned top-right, a Preview checkbox under it, and a small
proof box that shows the result at 100% while you drag sliders. PCDialog
supplies that layout so 60-odd dialogs don't each reinvent it.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QPlainTextEdit, QPushButton,
    QRadioButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from ... import theme
from ...color_dialog import XPColorDialog
from ...xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame

GROUP_QSS = """
QFrame#pcGroup { border: 1px solid #a0a0a0; background: transparent; }
QLabel { background: transparent; }
"""


class PCDialog(QDialog):
    def __init__(self, parent, title, width=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        outer = build_dialog_frame(self, title)
        body = QWidget()
        body.setStyleSheet(
            f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS} {GROUP_QSS}")
        self._root = QHBoxLayout(body)
        self._root.setContentsMargins(12, 10, 12, 10)
        self._root.setSpacing(12)

        self.content = QVBoxLayout()
        self.content.setSpacing(8)
        self._root.addLayout(self.content, 1)

        self.side = QVBoxLayout()
        self.side.setSpacing(5)
        self._root.addLayout(self.side, 0)

        outer.addWidget(body)
        if width:
            self.setFixedWidth(width)
        self._preview_check = None
        self._buttons_added = False

    # -- side column ---------------------------------------------------

    def add_button(self, label, slot=None, default=False, width=76):
        btn = QPushButton(label)
        btn.setMinimumWidth(width)
        if default:
            btn.setDefault(True)
            f = btn.font()
            f.setBold(True)
            btn.setFont(f)
        if slot:
            btn.clicked.connect(slot)
        self.side.addWidget(btn)
        return btn

    def add_ok_cancel(self, ok_label="OK"):
        self.add_button(ok_label, self.accept, default=True)
        self.add_button("Cancel", self.reject)
        self._buttons_added = True

    def add_preview_check(self, on_toggle=None, checked=True):
        self.side.addSpacing(4)
        self._preview_check = QCheckBox("Preview")
        self._preview_check.setChecked(checked)
        self._preview_check.setStyleSheet("background: transparent;")
        if on_toggle:
            self._preview_check.toggled.connect(on_toggle)
        self.side.addWidget(self._preview_check)
        return self._preview_check

    def preview_on(self) -> bool:
        return self._preview_check is None or self._preview_check.isChecked()

    def finish_side(self):
        self.side.addStretch(1)


def group_box(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("pcGroup")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(5)
    if title:
        label = QLabel(title)
        f = label.font()
        f.setBold(True)
        label.setFont(f)
        layout.addWidget(label)
    return frame, layout


class SliderRow(QWidget):
    """Label + numeric field + slider, the way every PS filter dialog does it."""
    changed = pyqtSignal()

    def __init__(self, label, minimum, maximum, value, suffix="", decimals=0):
        super().__init__()
        self.decimals = decimals
        row = QVBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.label = QLabel(label)
        self.label.setStyleSheet("background: transparent;")
        top.addWidget(self.label)
        top.addStretch(1)
        if decimals:
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(decimals)
            self.spin.setRange(float(minimum), float(maximum))
            self.spin.setValue(float(value))
        else:
            self.spin = QSpinBox()
            self.spin.setRange(int(minimum), int(maximum))
            self.spin.setValue(int(value))
        self.spin.setSuffix(suffix)
        self.spin.setFixedWidth(78)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(self.spin)
        row.addLayout(top)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self._scale = 10 ** decimals
        self.slider.setRange(int(minimum * self._scale), int(maximum * self._scale))
        self.slider.setValue(int(value * self._scale))
        row.addWidget(self.slider)

        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)
        self._syncing = False

    def _from_slider(self, v):
        if self._syncing:
            return
        self._syncing = True
        try:
            value = v / self._scale if self.decimals else v
            self.spin.setValue(value)
        finally:
            self._syncing = False
        self.changed.emit()

    def _from_spin(self, v):
        if self._syncing:
            return
        self._syncing = True
        try:
            self.slider.setValue(int(v * self._scale))
        finally:
            self._syncing = False
        self.changed.emit()

    def value(self):
        v = self.spin.value()
        return v if self.decimals else int(v)

    def set_value(self, v):
        self.spin.setValue(v)


class AngleDial(QWidget):
    """The little angle wheel from Motion Blur / Emboss / Drop Shadow."""
    changed = pyqtSignal()

    def __init__(self, label="Angle", value=0):
        super().__init__()
        self._angle = value
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.label = QLabel(label + ":")
        self.label.setStyleSheet("background: transparent;")
        row.addWidget(self.label)
        self.spin = QSpinBox()
        self.spin.setRange(-360, 360)
        self.spin.setValue(int(value))
        self.spin.setSuffix("°")
        self.spin.setFixedWidth(62)
        self.spin.valueChanged.connect(self._from_spin)
        row.addWidget(self.spin)
        self.dial = _DialWidget(self)
        row.addWidget(self.dial)
        row.addStretch(1)

    def _from_spin(self, v):
        self._angle = v
        self.dial.update()
        self.changed.emit()

    def set_angle(self, a):
        self.spin.setValue(int(a))

    def value(self):
        return self._angle


class _DialWidget(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setFixedSize(38, 38)

    def paintEvent(self, ev):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(2, 2, -2, -2)
        p.setPen(QPen(QColor("#808080"), 1))
        p.setBrush(QColor("#f4f4f4"))
        p.drawEllipse(r)
        c = r.center()
        rad = math.radians(-self.owner.value())
        p.setPen(QPen(QColor("#202020"), 2))
        p.drawLine(c, QPoint(int(c.x() + math.cos(rad) * r.width() / 2 * 0.8),
                             int(c.y() + math.sin(rad) * r.height() / 2 * 0.8)))
        p.end()

    def mousePressEvent(self, ev):
        self._set_from(ev.position())

    def mouseMoveEvent(self, ev):
        self._set_from(ev.position())

    def _set_from(self, pos):
        import math
        c = QPointF(self.width() / 2, self.height() / 2)
        ang = -math.degrees(math.atan2(pos.y() - c.y(), pos.x() - c.x()))
        self.owner.set_angle(round(ang))


class PreviewBox(QWidget):
    """The proof window: shows the result at a chosen zoom, draggable to pan."""

    def __init__(self, size=132):
        super().__init__()
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.image: QImage | None = None
        self.origin = QPoint(0, 0)
        self.zoom = 1.0
        self._drag = None

    def set_image(self, img: QImage, recentre=False):
        first = self.image is None
        self.image = img
        if img is not None and (first or recentre):
            self.origin = QPoint(max(0, (img.width() - self.width()) // 2),
                                 max(0, (img.height() - self.height()) // 2))
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ffffff"))
        if self.image is not None:
            side = int(self.width() / self.zoom)
            src = QRect(self.origin, QSize(side, side))
            p.drawImage(self.rect(), self.image, src)
        p.setPen(QPen(QColor("#808080"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

    def mousePressEvent(self, ev):
        self._drag = (ev.position(), QPoint(self.origin))
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, ev):
        if self._drag is None or self.image is None:
            return
        start, base = self._drag
        d = ev.position() - start
        side = int(self.width() / self.zoom)
        self.origin = QPoint(
            max(0, min(max(0, self.image.width() - side), base.x() - int(d.x() / self.zoom))),
            max(0, min(max(0, self.image.height() - side), base.y() - int(d.y() / self.zoom))))
        self.update()

    def mouseReleaseEvent(self, ev):
        self._drag = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class ZoomRow(QWidget):
    changed = pyqtSignal()

    def __init__(self, preview: PreviewBox):
        super().__init__()
        self.preview = preview
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        minus = QPushButton("-")
        minus.setFixedSize(18, 18)
        minus.clicked.connect(lambda: self._zoom(0.5))
        plus = QPushButton("+")
        plus.setFixedSize(18, 18)
        plus.clicked.connect(lambda: self._zoom(2.0))
        self.label = QLabel("100%")
        self.label.setStyleSheet("background: transparent;")
        row.addStretch(1)
        row.addWidget(minus)
        row.addWidget(self.label)
        row.addWidget(plus)
        row.addStretch(1)

    def _zoom(self, factor):
        self.preview.zoom = max(0.125, min(8.0, self.preview.zoom * factor))
        pct = self.preview.zoom * 100
        self.label.setText(f"{pct:.0f}%" if pct >= 1 else f"{pct:.1f}%")
        self.preview.update()


# ------------------------------------------------------- generic filter ----

class FilterDialog(PCDialog):
    """Builds itself from a filter's param schema and previews live."""

    def __init__(self, parent, title, params, apply_fn, source: QImage):
        super().__init__(parent, title)
        self.apply_fn = apply_fn
        self.source = source
        self.widgets = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._refresh)

        top = QHBoxLayout()
        top.setSpacing(12)
        preview_col = QVBoxLayout()
        preview_col.setSpacing(3)
        self.preview = PreviewBox()
        preview_col.addWidget(self.preview)
        self.zoom_row = ZoomRow(self.preview)
        preview_col.addWidget(self.zoom_row)
        top.addLayout(preview_col)

        controls = QVBoxLayout()
        controls.setSpacing(8)
        for spec in params:
            widget = self._build(spec)
            if widget is not None:
                controls.addWidget(widget)
        controls.addStretch(1)
        top.addLayout(controls, 1)
        self.content.addLayout(top)

        self.add_ok_cancel()
        self.add_preview_check(lambda _: self._refresh())
        self.finish_side()
        self._refresh()

    def _build(self, spec):
        kind, key = spec[0], spec[1]
        if kind == "slider":
            _, key, label, lo, hi, default, suffix = spec
            w = SliderRow(label, lo, hi, default, suffix)
            w.changed.connect(self._queue)
        elif kind == "dslider":
            _, key, label, lo, hi, default, decimals, suffix = spec
            w = SliderRow(label, lo, hi, default, suffix, decimals)
            w.changed.connect(self._queue)
        elif kind == "angle":
            _, key, label, default = spec
            w = AngleDial(label, default)
            w.changed.connect(self._queue)
        elif kind == "check":
            _, key, label, default = spec
            w = QCheckBox(label)
            w.setChecked(bool(default))
            w.setStyleSheet("background: transparent;")
            w.toggled.connect(self._queue)
        elif kind == "combo":
            _, key, label, choices, default = spec
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            if label:
                lbl = QLabel(label + ":")
                lbl.setStyleSheet("background: transparent;")
                row.addWidget(lbl)
            combo = QComboBox()
            self._combo_values = getattr(self, "_combo_values", {})
            values = []
            for choice in choices:
                if isinstance(choice, tuple):
                    values.append(choice[0])
                    combo.addItem(str(choice[1]))
                else:
                    values.append(choice)
                    combo.addItem(str(choice))
            self._combo_values[key] = values
            if default in values:
                combo.setCurrentIndex(values.index(default))
            combo.currentIndexChanged.connect(self._queue)
            row.addWidget(combo, 1)
            self.widgets[key] = combo
            return holder
        else:
            return None
        self.widgets[key] = w
        return w

    def _queue(self, *_):
        self._timer.start(120)

    def values(self) -> dict:
        out = {}
        for key, w in self.widgets.items():
            if isinstance(w, (SliderRow, AngleDial)):
                out[key] = w.value()
            elif isinstance(w, QCheckBox):
                out[key] = w.isChecked()
            elif isinstance(w, QComboBox):
                out[key] = getattr(self, "_combo_values", {}).get(
                    key, [w.currentText()])[w.currentIndex()]
        return out

    def _refresh(self):
        if not self.preview_on():
            self.preview.set_image(self.source)
            return
        try:
            self.preview.set_image(self.apply_fn(self.values()))
        except Exception:
            self.preview.set_image(self.source)

    @staticmethod
    def run(parent, title, params, apply_fn, source):
        dlg = FilterDialog(parent, title, params, apply_fn, source)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.values()
        return None


# --------------------------------------------------------- file/document ---

DOC_PRESETS = {
    "Custom": None,
    "Default Photoshop Size": (504, 360, 72),
    "Letter": (612, 792, 72),
    "Legal": (612, 1008, 72),
    "Tabloid": (792, 1224, 72),
    "2x3": (144, 216, 72),
    "4x6": (288, 432, 72),
    "5x7": (360, 504, 72),
    "8x10": (576, 720, 72),
    "640 x 480": (640, 480, 72),
    "800 x 600": (800, 600, 72),
    "1024 x 768": (1024, 768, 72),
    "468 x 60 (Web Banner)": (468, 60, 72),
    "NTSC DV 720 x 480": (720, 480, 72),
    "PAL D1/DV 720 x 576": (720, 576, 72),
}


class NewDocumentDialog(PCDialog):
    def __init__(self, parent, default_name="Untitled-1", width=560, height=380):
        super().__init__(parent, "New")
        name_row = QHBoxLayout()
        name_row.addWidget(_lbl("Name:"))
        self.name = QLineEdit(default_name)
        name_row.addWidget(self.name, 1)
        self.content.addLayout(name_row)

        preset_row = QHBoxLayout()
        preset_row.addWidget(_lbl("Preset Sizes:"))
        self.preset = QComboBox()
        self.preset.addItems(list(DOC_PRESETS))
        self.preset.currentTextChanged.connect(self._preset_changed)
        preset_row.addWidget(self.preset, 1)
        self.content.addLayout(preset_row)

        frame, box = group_box("Image Size")
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        self.width_spin = _spin(1, 30000, width, " pixels")
        self.height_spin = _spin(1, 30000, height, " pixels")
        self.res_spin = _spin(1, 1200, 72, " pixels/inch")
        self.mode = QComboBox()
        self.mode.addItems(["Bitmap", "Grayscale", "RGB Color", "CMYK Color", "Lab Color"])
        self.mode.setCurrentText("RGB Color")
        for r, (label, w) in enumerate((("Width:", self.width_spin),
                                        ("Height:", self.height_spin),
                                        ("Resolution:", self.res_spin),
                                        ("Mode:", self.mode))):
            grid.addWidget(_lbl(label), r, 0)
            grid.addWidget(w, r, 1)
        box.addLayout(grid)
        self.size_label = QLabel("Image Size: 623K")
        self.size_label.setStyleSheet("background: transparent; color: #444;")
        box.addWidget(self.size_label)
        self.content.addWidget(frame)

        frame2, box2 = group_box("Contents")
        self.bg_group = QButtonGroup(self)
        for i, label in enumerate(("White", "Background Color", "Transparent")):
            rb = QRadioButton(label)
            rb.setStyleSheet("background: transparent;")
            if i == 0:
                rb.setChecked(True)
            self.bg_group.addButton(rb, i)
            box2.addWidget(rb)
        self.content.addWidget(frame2)

        self.width_spin.valueChanged.connect(self._update_size)
        self.height_spin.valueChanged.connect(self._update_size)
        self._update_size()
        self.add_ok_cancel()
        self.finish_side()

    def _preset_changed(self, name):
        spec = DOC_PRESETS.get(name)
        if spec:
            self.width_spin.setValue(spec[0])
            self.height_spin.setValue(spec[1])
            self.res_spin.setValue(spec[2])

    def _update_size(self):
        kb = self.width_spin.value() * self.height_spin.value() * 3 / 1024
        self.size_label.setText(f"Image Size: {kb:.0f}K" if kb < 1024
                                else f"Image Size: {kb / 1024:.1f}M")

    def result(self):
        return dict(name=self.name.text() or "Untitled-1",
                    width=self.width_spin.value(), height=self.height_spin.value(),
                    resolution=self.res_spin.value(), mode=self.mode.currentText(),
                    background=("white", "bg", "transparent")[self.bg_group.checkedId()])


class ImageSizeDialog(PCDialog):
    def __init__(self, parent, width, height, resolution=72):
        super().__init__(parent, "Image Size")
        self._ratio = width / max(1, height)
        self._updating = False

        frame, box = group_box("Pixel Dimensions")
        self.current_label = QLabel()
        self.current_label.setStyleSheet("background: transparent; color: #444;")
        box.addWidget(self.current_label)
        grid = QGridLayout()
        self.width_spin = _spin(1, 30000, width, " pixels")
        self.height_spin = _spin(1, 30000, height, " pixels")
        grid.addWidget(_lbl("Width:"), 0, 0)
        grid.addWidget(self.width_spin, 0, 1)
        grid.addWidget(_lbl("Height:"), 1, 0)
        grid.addWidget(self.height_spin, 1, 1)
        box.addLayout(grid)
        self.content.addWidget(frame)

        frame2, box2 = group_box("Document Size")
        grid2 = QGridLayout()
        self.res_spin = _spin(1, 1200, resolution, " pixels/inch")
        self.print_w = QLabel()
        self.print_h = QLabel()
        for w in (self.print_w, self.print_h):
            w.setStyleSheet("background: transparent;")
        grid2.addWidget(_lbl("Width:"), 0, 0)
        grid2.addWidget(self.print_w, 0, 1)
        grid2.addWidget(_lbl("Height:"), 1, 0)
        grid2.addWidget(self.print_h, 1, 1)
        grid2.addWidget(_lbl("Resolution:"), 2, 0)
        grid2.addWidget(self.res_spin, 2, 1)
        box2.addLayout(grid2)
        self.content.addWidget(frame2)

        self.constrain = QCheckBox("Constrain Proportions")
        self.constrain.setChecked(True)
        self.constrain.setStyleSheet("background: transparent;")
        self.resample = QCheckBox("Resample Image:")
        self.resample.setChecked(True)
        self.resample.setStyleSheet("background: transparent;")
        self.method = QComboBox()
        self.method.addItems(["Nearest Neighbor", "Bilinear", "Bicubic"])
        self.method.setCurrentText("Bicubic")
        self.content.addWidget(self.constrain)
        row = QHBoxLayout()
        row.addWidget(self.resample)
        row.addWidget(self.method, 1)
        self.content.addLayout(row)

        self.width_spin.valueChanged.connect(self._w_changed)
        self.height_spin.valueChanged.connect(self._h_changed)
        self.res_spin.valueChanged.connect(self._refresh_labels)
        self._orig = (width, height)
        self._refresh_labels()
        self.add_ok_cancel()
        self.add_button("Auto...", self._auto)
        self.finish_side()

    def _auto(self):
        XPMessageBox.information(
            self, "Auto Resolution",
            "Screen frequency and print quality would go here.\n"
            "PhotoChop has picked 72 pixels/inch, as it always does.")
        self.res_spin.setValue(72)

    def _w_changed(self, v):
        if self._updating:
            return
        if self.constrain.isChecked():
            self._updating = True
            self.height_spin.setValue(max(1, int(round(v / self._ratio))))
            self._updating = False
        self._refresh_labels()

    def _h_changed(self, v):
        if self._updating:
            return
        if self.constrain.isChecked():
            self._updating = True
            self.width_spin.setValue(max(1, int(round(v * self._ratio))))
            self._updating = False
        self._refresh_labels()

    def _refresh_labels(self):
        w, h, res = self.width_spin.value(), self.height_spin.value(), self.res_spin.value()
        kb = w * h * 3 / 1024
        old = self._orig[0] * self._orig[1] * 3 / 1024
        self.current_label.setText(
            f"Current: {_size_text(old)}    New: {_size_text(kb)}")
        self.print_w.setText(f"{w / res:.3f} inches")
        self.print_h.setText(f"{h / res:.3f} inches")

    def result(self):
        return dict(width=self.width_spin.value(), height=self.height_spin.value(),
                    resolution=self.res_spin.value(),
                    resample=self.resample.isChecked(),
                    smooth=self.method.currentText() != "Nearest Neighbor")


class CanvasSizeDialog(PCDialog):
    ANCHORS = [("top-left", "top", "top-right"),
               ("left", "center", "right"),
               ("bottom-left", "bottom", "bottom-right")]

    def __init__(self, parent, width, height):
        super().__init__(parent, "Canvas Size")
        self.anchor = "center"
        current = QLabel(f"Current Size: {_size_text(width * height * 3 / 1024)}\n"
                         f"        Width: {width} pixels\n"
                         f"        Height: {height} pixels")
        current.setStyleSheet("background: transparent; color: #444;")
        self.content.addWidget(current)

        frame, box = group_box("New Size")
        grid = QGridLayout()
        self.width_spin = _spin(1, 30000, width, " pixels")
        self.height_spin = _spin(1, 30000, height, " pixels")
        grid.addWidget(_lbl("Width:"), 0, 0)
        grid.addWidget(self.width_spin, 0, 1)
        grid.addWidget(_lbl("Height:"), 1, 0)
        grid.addWidget(self.height_spin, 1, 1)
        box.addLayout(grid)

        anchor_grid = QGridLayout()
        anchor_grid.setSpacing(1)
        self._anchor_buttons = {}
        for r, row in enumerate(self.ANCHORS):
            for c, key in enumerate(row):
                btn = QPushButton()
                btn.setFixedSize(22, 22)
                btn.setCheckable(True)
                btn.setChecked(key == "center")
                btn.clicked.connect(lambda _, k=key: self._set_anchor(k))
                self._anchor_buttons[key] = btn
                anchor_grid.addWidget(btn, r, c)
        holder = QHBoxLayout()
        holder.addWidget(_lbl("Anchor:"))
        wrap = QWidget()
        wrap.setLayout(anchor_grid)
        holder.addWidget(wrap)
        holder.addStretch(1)
        box.addLayout(holder)
        self.content.addWidget(frame)

        self.add_ok_cancel()
        self.finish_side()

    def _set_anchor(self, key):
        self.anchor = key
        for k, btn in self._anchor_buttons.items():
            btn.setChecked(k == key)

    def result(self):
        return dict(width=self.width_spin.value(), height=self.height_spin.value(),
                    anchor=self.anchor)


class RotateCanvasDialog(PCDialog):
    def __init__(self, parent):
        super().__init__(parent, "Rotate Canvas")
        row = QHBoxLayout()
        row.addWidget(_lbl("Angle:"))
        self.angle = QDoubleSpinBox()
        self.angle.setRange(-359.99, 359.99)
        self.angle.setDecimals(2)
        self.angle.setValue(0)
        row.addWidget(self.angle)
        self.cw = QRadioButton("°CW")
        self.cw.setChecked(True)
        self.ccw = QRadioButton("°CCW")
        for w in (self.cw, self.ccw):
            w.setStyleSheet("background: transparent;")
            row.addWidget(w)
        self.content.addLayout(row)
        self.add_ok_cancel()
        self.finish_side()

    def result(self):
        a = self.angle.value()
        return a if self.cw.isChecked() else -a


# ------------------------------------------------------------ edit menu ----

class FillDialog(PCDialog):
    def __init__(self, parent):
        super().__init__(parent, "Fill")
        frame, box = group_box("Contents")
        row = QHBoxLayout()
        row.addWidget(_lbl("Use:"))
        self.use = QComboBox()
        self.use.addItems(["Foreground Color", "Background Color", "Pattern",
                           "History", "Black", "50% Gray", "White"])
        row.addWidget(self.use, 1)
        box.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(_lbl("Custom Pattern:"))
        self.pattern = QComboBox()
        self.pattern.addItems(["Checkerboard", "Diagonal Lines", "Bubbles", "Woven"])
        row2.addWidget(self.pattern, 1)
        box.addLayout(row2)
        self.content.addWidget(frame)

        frame2, box2 = group_box("Blending")
        row3 = QHBoxLayout()
        row3.addWidget(_lbl("Mode:"))
        self.mode = QComboBox()
        from .model import BLEND_MODES
        self.mode.addItems([m for m in BLEND_MODES if m != "-"])
        row3.addWidget(self.mode, 1)
        box2.addLayout(row3)
        row4 = QHBoxLayout()
        row4.addWidget(_lbl("Opacity:"))
        self.opacity = _spin(0, 100, 100, "%")
        row4.addWidget(self.opacity)
        row4.addStretch(1)
        box2.addLayout(row4)
        self.preserve = QCheckBox("Preserve Transparency")
        self.preserve.setStyleSheet("background: transparent;")
        box2.addWidget(self.preserve)
        self.content.addWidget(frame2)
        self.add_ok_cancel()
        self.finish_side()

    def result(self):
        return dict(use=self.use.currentText(), pattern=self.pattern.currentText(),
                    mode=self.mode.currentText(), opacity=self.opacity.value(),
                    preserve=self.preserve.isChecked())


class StrokeDialog(PCDialog):
    def __init__(self, parent, colour=QColor("black")):
        super().__init__(parent, "Stroke")
        self.colour = QColor(colour)
        frame, box = group_box("Stroke")
        row = QHBoxLayout()
        row.addWidget(_lbl("Width:"))
        self.width = _spin(1, 250, 3, " px")
        row.addWidget(self.width)
        row.addSpacing(10)
        row.addWidget(_lbl("Color:"))
        self.swatch = QPushButton()
        self.swatch.setFixedSize(40, 18)
        self.swatch.clicked.connect(self._pick)
        self._paint_swatch()
        row.addWidget(self.swatch)
        row.addStretch(1)
        box.addLayout(row)
        self.content.addWidget(frame)

        frame2, box2 = group_box("Location")
        self.loc = QButtonGroup(self)
        row2 = QHBoxLayout()
        for i, name in enumerate(("Inside", "Center", "Outside")):
            rb = QRadioButton(name)
            rb.setStyleSheet("background: transparent;")
            if name == "Inside":
                rb.setChecked(True)
            self.loc.addButton(rb, i)
            row2.addWidget(rb)
        box2.addLayout(row2)
        self.content.addWidget(frame2)

        frame3, box3 = group_box("Blending")
        row3 = QHBoxLayout()
        row3.addWidget(_lbl("Opacity:"))
        self.opacity = _spin(0, 100, 100, "%")
        row3.addWidget(self.opacity)
        row3.addStretch(1)
        box3.addLayout(row3)
        self.content.addWidget(frame3)
        self.add_ok_cancel()
        self.finish_side()

    def _paint_swatch(self):
        self.swatch.setStyleSheet(
            f"background: {self.colour.name()}; border: 1px solid #555;")

    def _pick(self):
        c = XPColorDialog.get_color(self, self.colour)
        if c:
            self.colour = c
            self._paint_swatch()

    def result(self):
        return dict(width=self.width.value(), color=self.colour,
                    location=("Inside", "Center", "Outside")[self.loc.checkedId()],
                    opacity=self.opacity.value())


# ---------------------------------------------------------- select menu ----

class FeatherDialog(PCDialog):
    def __init__(self, parent):
        super().__init__(parent, "Feather Selection")
        row = QHBoxLayout()
        row.addWidget(_lbl("Feather Radius:"))
        self.radius = _spin(0, 250, 5, " pixels")
        row.addWidget(self.radius)
        self.content.addLayout(row)
        self.add_ok_cancel()
        self.finish_side()

    def result(self):
        return self.radius.value()


class ValueDialog(PCDialog):
    """One labelled number -- Border, Smooth, Expand, Contract, Posterize."""

    def __init__(self, parent, title, label, value, minimum=1, maximum=250, suffix=" pixels"):
        super().__init__(parent, title)
        row = QHBoxLayout()
        row.addWidget(_lbl(label))
        self.spin = _spin(minimum, maximum, value, suffix)
        row.addWidget(self.spin)
        row.addStretch(1)
        self.content.addLayout(row)
        self.add_ok_cancel()
        self.finish_side()

    def result(self):
        return self.spin.value()

    @staticmethod
    def get(parent, title, label, value, minimum=1, maximum=250, suffix=" pixels"):
        dlg = ValueDialog(parent, title, label, value, minimum, maximum, suffix)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.result()
        return None


# ----------------------------------------------------------- layer menu ----

class NewLayerDialog(PCDialog):
    def __init__(self, parent, default_name="Layer 1", show_clipping=True):
        super().__init__(parent, "New Layer")
        grid = QGridLayout()
        grid.addWidget(_lbl("Name:"), 0, 0)
        self.name = QLineEdit(default_name)
        grid.addWidget(self.name, 0, 1)
        self.clipping = QCheckBox("Group With Previous Layer")
        self.clipping.setStyleSheet("background: transparent;")
        if show_clipping:
            grid.addWidget(self.clipping, 1, 1)
        grid.addWidget(_lbl("Mode:"), 2, 0)
        self.mode = QComboBox()
        from .model import BLEND_MODES
        self.mode.addItems([m for m in BLEND_MODES if m != "-"])
        grid.addWidget(self.mode, 2, 1)
        grid.addWidget(_lbl("Opacity:"), 3, 0)
        self.opacity = _spin(0, 100, 100, "%")
        grid.addWidget(self.opacity, 3, 1)
        self.content.addLayout(grid)
        self.add_ok_cancel()
        self.finish_side()

    def result(self):
        return dict(name=self.name.text(), mode=self.mode.currentText(),
                    opacity=self.opacity.value(), clipping=self.clipping.isChecked())


class LayerPropertiesDialog(PCDialog):
    def __init__(self, parent, name):
        super().__init__(parent, "Layer Properties")
        row = QHBoxLayout()
        row.addWidget(_lbl("Name:"))
        self.name = QLineEdit(name)
        row.addWidget(self.name, 1)
        self.content.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(_lbl("Color:"))
        self.colour = QComboBox()
        self.colour.addItems(["None", "Red", "Orange", "Yellow", "Green", "Blue",
                              "Violet", "Gray"])
        row2.addWidget(self.colour, 1)
        self.content.addLayout(row2)
        self.add_ok_cancel()
        self.finish_side()

    def result(self):
        return self.name.text()


# ---------------------------------------------------------------- notes ----

class NoteDialog(PCDialog):
    def __init__(self, parent, author="You"):
        super().__init__(parent, f"Note - {author}")
        self.edit = QPlainTextEdit()
        self.edit.setFixedSize(280, 130)
        self.content.addWidget(self.edit)
        self.add_ok_cancel()
        self.finish_side()

    @staticmethod
    def get_text(parent, author="You"):
        dlg = NoteDialog(parent, author)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.edit.toPlainText()
        return None


# -------------------------------------------------------------- helpers ----

def _lbl(text):
    label = QLabel(text)
    label.setStyleSheet("background: transparent;")
    return label


def _spin(minimum, maximum, value, suffix=""):
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    spin.setSuffix(suffix)
    spin.setAlignment(Qt.AlignmentFlag.AlignRight)
    spin.setFixedWidth(110)
    return spin


def _size_text(kb):
    return f"{kb:.0f}K" if kb < 1024 else f"{kb / 1024:.1f}M"
