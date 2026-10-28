"""Tool selection and the context-sensitive options bar -- mixin for PhotoChopWindow."""
from __future__ import annotations

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSpinBox, QToolButton,
    QWidget,
)

from ....color_dialog import XPColorDialog
from .. import pc_icons, tools as tool_defs
from ..canvas import CUSTOM_SHAPES
from ..model import BLEND_MODES
from .widgets import BrushPickerButton, GradientPickerButton


class ToolOptionsMixin:
    """Tool selection and the context-sensitive options bar."""

    def tool_spec(self, tool_id):
        return tool_defs.ALL_TOOLS.get(tool_id)

    def select_tool(self, tool_id):
        spec = tool_defs.ALL_TOOLS.get(tool_id)
        if spec is None:
            return
        self.current_tool = tool_id
        for btn in self._tool_buttons:
            in_group = any(t.id == tool_id for t in btn.group_tools)
            btn.setChecked(in_group)
            if in_group:
                btn.set_current(spec)
        self._tool_icon_label.setPixmap(pc_icons.pixmap(spec.icon, 22))
        self._rebuild_options(spec)
        self._set_hint(spec.hint)
        self.canvas._update_cursor()
        self.canvas.update()

    def _rebuild_options(self, spec):
        while self._options_host_layout.count():
            item = self._options_host_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_widgets = {}
        for control in spec.options:
            widget = self._build_option(control)
            if widget is not None:
                self._options_host_layout.addWidget(widget)
        self._options_host_layout.addStretch(1)

    def _build_option(self, control):
        kind, key, label, extra = control
        if kind == "sep":
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setStyleSheet("color: #b0b0a0;")
            return line
        if kind == "selops":
            return self._build_selops()
        if kind == "label":
            return QLabel(label)
        holder = QWidget()
        holder.setObjectName("optHolder")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        if label and kind not in ("check",):
            row.addWidget(QLabel(label))
        widget = None
        if kind == "check":
            widget = QCheckBox(label)
            widget.setChecked(bool(self.options.get(key)))
            widget.toggled.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "spin":
            lo, hi, suffix = extra
            widget = QSpinBox()
            widget.setRange(lo, hi)
            widget.setValue(int(self.options.get(key, lo)))
            widget.setSuffix(suffix)
            widget.setFixedWidth(64 if hi < 1000 else 74)
            widget.valueChanged.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "pct":
            widget = QSpinBox()
            widget.setRange(0, 100)
            widget.setValue(int(self.options.get(key, extra or 100)))
            widget.setSuffix("%")
            widget.setFixedWidth(56)
            widget.valueChanged.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "combo":
            widget = QComboBox()
            widget.addItems([str(c) for c in extra])
            current = str(self.options.get(key, extra[0]))
            if current in [str(c) for c in extra]:
                widget.setCurrentText(current)
            widget.currentTextChanged.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "blend":
            widget = QComboBox()
            for mode in BLEND_MODES:
                if mode == "-":
                    widget.insertSeparator(widget.count())
                else:
                    widget.addItem(mode)
            widget.setCurrentText(self.options.get(key, "Normal"))
            widget.setFixedWidth(98)
            widget.currentTextChanged.connect(lambda v, k=key: self._set_option(k, v))
        elif kind == "brush":
            widget = BrushPickerButton(self)
        elif kind == "gradient":
            widget = GradientPickerButton(self)
        elif kind == "shape":
            widget = QComboBox()
            widget.addItems(CUSTOM_SHAPES)
            widget.setCurrentText(self.options.get("custom_shape", "Heart"))
            widget.currentTextChanged.connect(lambda v: self._set_option("custom_shape", v))
        elif kind == "color":
            widget = QPushButton()
            widget.setFixedSize(34, 18)
            colour = self.options.get(key, "#f5e04a")
            widget.setStyleSheet(f"background: {colour}; border: 1px solid #555;")
            widget.clicked.connect(lambda _, k=key, b=widget: self._pick_option_color(k, b))
        elif kind == "font":
            return self._build_font_options()
        if widget is None:
            return None
        self._option_widgets[key] = widget
        row.addWidget(widget)
        return holder

    def _build_selops(self):
        holder = QWidget()
        holder.setObjectName("optHolder")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(1)
        self._selop_buttons = {}
        for key, glyph, tip in (("new", "sel_new", "New selection"),
                                ("add", "sel_add", "Add to selection"),
                                ("subtract", "sel_subtract", "Subtract from selection"),
                                ("intersect", "sel_intersect", "Intersect with selection")):
            btn = QToolButton()
            btn.setIcon(pc_icons.icon(glyph, 16))
            btn.setIconSize(QSize(16, 16))
            btn.setCheckable(True)
            btn.setChecked(self.options.get("selop", "new") == key)
            btn.setFixedSize(22, 22)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _, k=key: self._set_selop(k))
            self._selop_buttons[key] = btn
            row.addWidget(btn)
        return holder

    def _build_font_options(self):
        holder = QWidget()
        holder.setObjectName("optHolder")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        font = self.options.get("font", {})
        from PyQt6.QtGui import QFontDatabase
        family = QComboBox()
        family.addItems(QFontDatabase.families()[:80])
        family.setCurrentText(font.get("family", "Tahoma"))
        family.setFixedWidth(120)
        family.currentTextChanged.connect(lambda v: self._set_font("family", v))
        style = QComboBox()
        style.addItems(["Regular", "Italic", "Bold", "Bold Italic"])
        style.setCurrentText(font.get("style", "Regular"))
        style.setFixedWidth(76)
        style.currentTextChanged.connect(lambda v: self._set_font("style", v))
        size = QComboBox()
        size.setEditable(True)
        size.addItems([str(s) for s in (6, 8, 10, 12, 14, 18, 24, 30, 36, 48, 60, 72)])
        size.setCurrentText(str(font.get("size", 24)))
        size.setFixedWidth(58)
        size.currentTextChanged.connect(
            lambda v: self._set_font("size", int(v) if v.isdigit() else 24))
        anti = QComboBox()
        anti.addItems(["None", "Sharp", "Crisp", "Strong", "Smooth"])
        anti.setCurrentText(font.get("antialias", "Crisp"))
        anti.setFixedWidth(66)
        anti.currentTextChanged.connect(lambda v: self._set_font("antialias", v))
        colour = QPushButton()
        colour.setFixedSize(34, 18)
        colour.setStyleSheet(f"background: {font.get('color', '#000000')};"
                             f"border: 1px solid #555;")
        colour.clicked.connect(lambda: self._pick_font_color(colour))
        for w in (family, style, size, anti):
            row.addWidget(w)
        row.addWidget(colour)
        return holder

    def _set_font(self, key, value):
        font = dict(self.options.get("font", {}))
        font[key] = value
        self.options["font"] = font
        if self._type_editor is not None:
            self._apply_type_font()

    def _pick_font_color(self, button):
        font = dict(self.options.get("font", {}))
        c = XPColorDialog.get_color(self, QColor(font.get("color", "#000000")))
        if c:
            font["color"] = c.name()
            self.options["font"] = font
            button.setStyleSheet(f"background: {c.name()}; border: 1px solid #555;")
            if self._type_editor is not None:
                self._apply_type_font()

    def _pick_option_color(self, key, button):
        c = XPColorDialog.get_color(self, QColor(self.options.get(key, "#f5e04a")))
        if c:
            self.options[key] = c.name()
            button.setStyleSheet(f"background: {c.name()}; border: 1px solid #555;")

    def _set_selop(self, key):
        self.options["selop"] = key
        for k, btn in self._selop_buttons.items():
            btn.setChecked(k == key)

    def _set_option(self, key, value):
        self.options[key] = value

    def sync_options_bar(self):
        spec = tool_defs.ALL_TOOLS.get(self.current_tool)
        if spec:
            self._rebuild_options(spec)
