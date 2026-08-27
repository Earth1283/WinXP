"""Layer Style -- the Blending Options dialog.

Effects list on the left (each with its own checkbox), the selected effect's
controls in the middle, buttons and a live proof on the right. Turning an
effect on immediately repaints the document behind the dialog, because the
effects are rendered at composite time rather than baked in.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from ...color_dialog import XPColorDialog
from ...xp_dialog import XPMessageBox
from .dialogs import AngleDial, PCDialog, SliderRow, _lbl, group_box
from .model import BLEND_MODES, default_style

EFFECTS = ["Drop Shadow", "Inner Shadow", "Outer Glow", "Inner Glow",
           "Bevel and Emboss", "Satin", "Color Overlay", "Gradient Overlay",
           "Pattern Overlay", "Stroke"]

# (kind, key, label, extra) per effect. Mirrors the real panels closely enough
# that muscle memory works.
PANELS = {
    "Drop Shadow": [
        ("blend", "blend_mode", "Blend Mode:", None),
        ("color", "color", "", None),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
        ("angle", "angle", "Angle", None),
        ("slider", "distance", "Distance:", 0, 250, " px"),
        ("slider", "spread", "Spread:", 0, 100, "%"),
        ("slider", "size", "Size:", 0, 250, " px"),
    ],
    "Inner Shadow": [
        ("blend", "blend_mode", "Blend Mode:", None),
        ("color", "color", "", None),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
        ("angle", "angle", "Angle", None),
        ("slider", "distance", "Distance:", 0, 250, " px"),
        ("slider", "choke", "Choke:", 0, 100, "%"),
        ("slider", "size", "Size:", 0, 250, " px"),
    ],
    "Outer Glow": [
        ("blend", "blend_mode", "Blend Mode:", None),
        ("color", "color", "", None),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
        ("slider", "spread", "Spread:", 0, 100, "%"),
        ("slider", "size", "Size:", 0, 250, " px"),
    ],
    "Inner Glow": [
        ("blend", "blend_mode", "Blend Mode:", None),
        ("color", "color", "", None),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
        ("slider", "choke", "Choke:", 0, 100, "%"),
        ("slider", "size", "Size:", 0, 250, " px"),
    ],
    "Bevel and Emboss": [
        ("combo", "style", "Style:", ("Outer Bevel", "Inner Bevel", "Emboss",
                                      "Pillow Emboss", "Stroke Emboss")),
        ("combo", "technique", "Technique:", ("Smooth", "Chisel Hard", "Chisel Soft")),
        ("slider", "depth", "Depth:", 1, 1000, "%"),
        ("combo", "direction", "Direction:", ("Up", "Down")),
        ("slider", "size", "Size:", 0, 250, " px"),
        ("slider", "soften", "Soften:", 0, 16, " px"),
        ("angle", "angle", "Angle", None),
        ("slider", "altitude", "Altitude:", 0, 90, "°"),
    ],
    "Satin": [
        ("blend", "blend_mode", "Blend Mode:", None),
        ("color", "color", "", None),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
        ("angle", "angle", "Angle", None),
        ("slider", "distance", "Distance:", 1, 250, " px"),
        ("slider", "size", "Size:", 0, 250, " px"),
        ("check", "invert", "Invert", None),
    ],
    "Color Overlay": [
        ("blend", "blend_mode", "Blend Mode:", None),
        ("color", "color", "", None),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
    ],
    "Gradient Overlay": [
        ("color", "start", "Start:", None),
        ("color", "end", "End:", None),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
        ("angle", "angle", "Angle", None),
    ],
    "Pattern Overlay": [
        ("combo", "pattern", "Pattern:", ("Checkerboard", "Diagonal Lines",
                                          "Bubbles", "Woven")),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
        ("slider", "scale", "Scale:", 10, 400, "%"),
    ],
    "Stroke": [
        ("slider", "size", "Size:", 1, 250, " px"),
        ("combo", "position", "Position:", ("Outside", "Inside", "Center")),
        ("slider", "opacity", "Opacity:", 0, 100, "%"),
        ("color", "color", "", None),
    ],
}


class LayerStyleDialog(PCDialog):
    def __init__(self, parent, layer, focus_effect=None):
        super().__init__(parent, f"Layer Style")
        self.win = parent
        self.layer = layer
        self.style = {k: dict(v) for k, v in layer.style.items()}
        self._backup = {k: dict(v) for k, v in layer.style.items()}
        self._widgets = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._apply_live)

        body = QHBoxLayout()
        body.setSpacing(10)

        # -- effects list
        left = QVBoxLayout()
        left.setSpacing(4)
        header = QLabel("Styles")
        f = header.font()
        f.setBold(True)
        header.setFont(f)
        header.setStyleSheet("background: transparent;")
        left.addWidget(header)
        self.list = QListWidget()
        self.list.setFixedWidth(148)
        self.list.currentRowChanged.connect(self._row_changed)
        self.list.itemChanged.connect(self._item_toggled)
        blending = QListWidgetItem("Blending Options: Default")
        self.list.addItem(blending)
        for name in EFFECTS:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if self.style[name].get("enabled")
                               else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        left.addWidget(self.list, 1)
        body.addLayout(left)

        # -- parameter panels
        self.stack = QStackedWidget()
        self.stack.setFixedWidth(320)
        self.stack.addWidget(self._blending_panel())
        for name in EFFECTS:
            self.stack.addWidget(self._effect_panel(name))
        body.addWidget(self.stack)
        self.content.addLayout(body)

        self.add_ok_cancel()
        self.add_button("New Style...", self._new_style)
        self.add_preview_check(lambda _: self._apply_live())
        self.finish_side()

        start = EFFECTS.index(focus_effect) + 1 if focus_effect in EFFECTS else 0
        self.list.setCurrentRow(start)
        if focus_effect in EFFECTS:
            self.style[focus_effect]["enabled"] = True
            self.list.item(start).setCheckState(Qt.CheckState.Checked)
        self._apply_live()

    # -- panels --------------------------------------------------------

    def _blending_panel(self):
        panel = QWidget()
        outer = QVBoxLayout(panel)
        frame, box = group_box("General Blending")
        row = QHBoxLayout()
        row.addWidget(_lbl("Blend Mode:"))
        self.doc_blend = QComboBox()
        for mode in BLEND_MODES:
            if mode == "-":
                self.doc_blend.insertSeparator(self.doc_blend.count())
            else:
                self.doc_blend.addItem(mode)
        self.doc_blend.setCurrentText(self.layer.blend)
        self.doc_blend.currentTextChanged.connect(self._blend_changed)
        row.addWidget(self.doc_blend, 1)
        box.addLayout(row)
        self.doc_opacity = SliderRow("Opacity:", 0, 100, int(self.layer.opacity * 100), "%")
        self.doc_opacity.changed.connect(self._opacity_changed)
        box.addWidget(self.doc_opacity)
        outer.addWidget(frame)

        frame2, box2 = group_box("Advanced Blending")
        self.doc_fill = SliderRow("Fill Opacity:", 0, 100,
                                  int(self.layer.fill_opacity * 100), "%")
        self.doc_fill.changed.connect(self._fill_changed)
        box2.addWidget(self.doc_fill)
        for label in ("Blend Interior Effects as Group",
                      "Blend Clipped Layers as Group",
                      "Transparency Shapes Layer"):
            box = QCheckBox(label)
            box.setChecked(True)
            box.setStyleSheet("background: transparent;")
            box2.addWidget(box)
        outer.addWidget(frame2)
        outer.addStretch(1)
        return panel

    def _effect_panel(self, name):
        panel = QWidget()
        outer = QVBoxLayout(panel)
        frame, box = group_box(name)
        cfg = self.style[name]
        for spec in PANELS[name]:
            kind, key, label, extra = spec[0], spec[1], spec[2], spec[3] if len(spec) > 3 else None
            widget = None
            if kind == "slider":
                _, key, label, lo, hi, suffix = spec
                widget = SliderRow(label, lo, hi, cfg.get(key, lo), suffix)
                widget.changed.connect(lambda n=name, k=key: self._slider_changed(n, k))
                box.addWidget(widget)
            elif kind == "angle":
                widget = AngleDial(label, cfg.get(key, 120))
                widget.changed.connect(lambda n=name, k=key: self._slider_changed(n, k))
                box.addWidget(widget)
            elif kind == "check":
                widget = QCheckBox(label)
                widget.setChecked(bool(cfg.get(key)))
                widget.setStyleSheet("background: transparent;")
                widget.toggled.connect(
                    lambda v, n=name, k=key: self._set(n, k, v))
                box.addWidget(widget)
            elif kind == "combo":
                row = QHBoxLayout()
                row.addWidget(_lbl(label))
                widget = QComboBox()
                widget.addItems(list(extra))
                if cfg.get(key) in extra:
                    widget.setCurrentText(cfg[key])
                widget.currentTextChanged.connect(
                    lambda v, n=name, k=key: self._set(n, k, v))
                row.addWidget(widget, 1)
                box.addLayout(row)
            elif kind == "blend":
                row = QHBoxLayout()
                row.addWidget(_lbl(label))
                widget = QComboBox()
                for mode in BLEND_MODES:
                    if mode == "-":
                        widget.insertSeparator(widget.count())
                    else:
                        widget.addItem(mode)
                widget.setCurrentText(cfg.get(key, "Normal"))
                widget.currentTextChanged.connect(
                    lambda v, n=name, k=key: self._set(n, k, v))
                row.addWidget(widget, 1)
                box.addLayout(row)
            elif kind == "color":
                row = QHBoxLayout()
                row.addWidget(_lbl(label or "Color:"))
                widget = QPushButton()
                widget.setFixedSize(46, 18)
                widget.setStyleSheet(
                    f"background: {cfg.get(key, '#000000')}; border: 1px solid #555;")
                widget.clicked.connect(
                    lambda _, n=name, k=key, b=None: self._pick_color(n, k))
                self._widgets[(name, key)] = widget
                row.addWidget(widget)
                row.addStretch(1)
                box.addLayout(row)
            if widget is not None:
                self._widgets[(name, key)] = widget
        outer.addWidget(frame)
        outer.addStretch(1)
        return panel

    # -- interaction ---------------------------------------------------

    def _row_changed(self, row):
        self.stack.setCurrentIndex(max(0, row))

    def _item_toggled(self, item):
        name = item.text()
        if name in self.style:
            self.style[name]["enabled"] = item.checkState() == Qt.CheckState.Checked
            self._timer.start(60)

    def _set(self, effect, key, value):
        self.style[effect][key] = value
        self._timer.start(90)

    def _slider_changed(self, effect, key):
        widget = self._widgets.get((effect, key))
        if widget is not None:
            self.style[effect][key] = widget.value()
        self._timer.start(140)

    def _pick_color(self, effect, key):
        button = self._widgets.get((effect, key))
        current = QColor(self.style[effect].get(key, "#000000"))
        c = XPColorDialog.get_color(self, current)
        if c:
            self.style[effect][key] = c.name()
            if button is not None:
                button.setStyleSheet(f"background: {c.name()}; border: 1px solid #555;")
            self._timer.start(60)

    def _blend_changed(self, name):
        self.layer.blend = name
        self._apply_live()

    def _opacity_changed(self):
        self.layer.opacity = self.doc_opacity.value() / 100.0
        self._timer.start(90)

    def _fill_changed(self):
        self.layer.fill_opacity = self.doc_fill.value() / 100.0
        self._timer.start(90)

    def _apply_live(self):
        self.layer.style = ({k: dict(v) for k, v in self.style.items()}
                            if self.preview_on() else self._backup)
        self.win.doc.invalidate()
        self.win.canvas.update()

    def _new_style(self):
        XPMessageBox.information(
            self, "New Style",
            "Style added to the Styles palette, where it will sit forever "
            "between 'Blue Glass' and something you did not make.")

    def reject(self):
        self.layer.style = self._backup
        self.win.doc.invalidate()
        self.win.canvas.update()
        super().reject()

    def result(self):
        return {k: dict(v) for k, v in self.style.items()}
