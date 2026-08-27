"""Format menu dialogs: Font, Paragraph, Bullets and Numbering, Tabs,
Borders and Shading, Columns, Drop Cap, Change Case -- plus Page Setup.

Word's dialogs share a shape: a tab strip, a stack of grouped controls, a
sunken Preview pane that updates live, and OK/Cancel pinned bottom right.
MWDialog supplies that so each dialog only has to describe its own controls.
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QTextBlockFormat, QTextCharFormat, QTextOption,
)
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QRadioButton,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ... import theme
from ...xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame
from .model import (
    PAPER_SIZES, PageSetup, STYLES_BY_NAME, fmt_measure, inches, settings,
)
from .widgets import OFFICE_COLORS, SamplePreview, color_name

DIALOG_QSS = """
QWidget { font-size: 11px; }
QLabel { background: transparent; }
QGroupBox {
    border: 1px solid #a6a6a0; margin-top: 7px; padding-top: 6px;
    background: transparent;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 8px; padding: 0 3px; background: #ece9d8;
}
QListWidget, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: white; border: 1px solid #7f9db9;
}
QListWidget { outline: none; }
QTabWidget::pane { border: 1px solid #919b9c; background: #ece9d8; top: -1px; }
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #e2dfd0);
    border: 1px solid #919b9c; border-bottom: none;
    border-top-left-radius: 3px; border-top-right-radius: 3px;
    padding: 3px 10px; margin-right: 2px; color: black;
}
QTabBar::tab:selected { background: #ece9d8; margin-bottom: -1px; padding-bottom: 4px; }
QTabBar::tab:!selected { margin-top: 2px; }
"""


class MWDialog(QDialog):
    """Frameless Luna chrome, a content column, and the OK/Cancel row."""

    def __init__(self, parent, title, width=None, modal=True):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(modal)
        outer = build_dialog_frame(self, title)
        body = QWidget()
        body.setStyleSheet(
            f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS} {DIALOG_QSS}")
        self._root = QVBoxLayout(body)
        self._root.setContentsMargins(10, 8, 10, 10)
        self._root.setSpacing(8)
        self.content = QVBoxLayout()
        self.content.setSpacing(8)
        self._root.addLayout(self.content, 1)
        self.button_row = QHBoxLayout()
        self.button_row.setSpacing(6)
        self._root.addLayout(self.button_row)
        outer.addWidget(body)
        if width:
            self.setFixedWidth(width)

    def add_tabs(self, *names) -> dict[str, QVBoxLayout]:
        tabs = QTabWidget()
        self.tabs = tabs
        pages = {}
        for name in names:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(8)
            tabs.addTab(page, name)
            pages[name] = layout
        self.content.addWidget(tabs)
        return pages

    def add_buttons(self, ok="OK", cancel="Cancel", extra=()):
        for label, slot in extra:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setMinimumWidth(78)
            btn.clicked.connect(slot)
            self.button_row.addWidget(btn)
        self.button_row.addStretch(1)
        if ok:
            self.ok_button = QPushButton(ok)
            self.ok_button.setFixedHeight(22)
            self.ok_button.setMinimumWidth(75)
            self.ok_button.setDefault(True)
            self.ok_button.clicked.connect(self.accept)
            self.button_row.addWidget(self.ok_button)
        if cancel:
            btn = QPushButton(cancel)
            btn.setFixedHeight(22)
            btn.setMinimumWidth(75)
            btn.clicked.connect(self.reject)
            self.button_row.addWidget(btn)


def _labelled(label, widget, width=None):
    row = QHBoxLayout()
    lbl = QLabel(label)
    if width:
        lbl.setFixedWidth(width)
    row.addWidget(lbl)
    row.addWidget(widget)
    return row


def _group(title) -> tuple[QGroupBox, QGridLayout]:
    box = QGroupBox(title)
    grid = QGridLayout(box)
    grid.setContentsMargins(8, 6, 8, 8)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(5)
    return box, grid


def _color_combo(current: QColor | None, automatic="Automatic") -> QComboBox:
    combo = QComboBox()
    combo.addItem(automatic, None)
    for value in OFFICE_COLORS:
        pm = _swatch(value)
        combo.addItem(pm, color_name(value), value)
    if current is not None and current.isValid():
        name = current.name()
        index = combo.findData(name)
        combo.setCurrentIndex(index if index >= 0 else 0)
    combo.setIconSize(QSize(40, 10))
    return combo


def _swatch(value: str):
    from PyQt6.QtGui import QIcon, QPainter, QPen, QPixmap
    pm = QPixmap(40, 10)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setPen(QPen(QColor("#7f7f7f"), 1))
    p.setBrush(QColor(value))
    p.drawRect(0, 0, 39, 9)
    p.end()
    return QIcon(pm)


# ------------------------------------------------------------------- font ---

UNDERLINE_STYLES = [
    ("(none)", QTextCharFormat.UnderlineStyle.NoUnderline),
    ("Single", QTextCharFormat.UnderlineStyle.SingleUnderline),
    ("Words only", QTextCharFormat.UnderlineStyle.SingleUnderline),
    ("Double", QTextCharFormat.UnderlineStyle.DashUnderline),
    ("Dotted", QTextCharFormat.UnderlineStyle.DotLine),
    ("Dashed", QTextCharFormat.UnderlineStyle.DashUnderline),
    ("Dot dash", QTextCharFormat.UnderlineStyle.DashDotLine),
    ("Dot dot dash", QTextCharFormat.UnderlineStyle.DashDotDotLine),
    ("Wave", QTextCharFormat.UnderlineStyle.WaveUnderline),
]

FONT_SIZES = ["8", "9", "10", "11", "12", "14", "16", "18", "20", "22", "24",
              "26", "28", "36", "48", "72"]


class FontDialog(MWDialog):
    """Format > Font. Three tabs, live preview, and a Default... button that
    threatens to change Normal.dot exactly as the real one does."""

    def __init__(self, parent, char_format: QTextCharFormat):
        super().__init__(parent, "Font", width=520)
        self.result_format = QTextCharFormat()
        source = QTextCharFormat(char_format)
        font = source.font()

        pages = self.add_tabs("Font", "Character Spacing", "Text Effects")
        self._build_font_page(pages["Font"], source, font)
        self._build_spacing_page(pages["Character Spacing"], source)
        self._build_effects_page(pages["Text Effects"])
        self.add_buttons(extra=[("Default...", self._make_default)])
        self._update_preview()

    # -- Font tab ------------------------------------------------------

    def _build_font_page(self, layout, source, font):
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.addWidget(QLabel("Font:"), 0, 0)
        grid.addWidget(QLabel("Font style:"), 0, 1)
        grid.addWidget(QLabel("Size:"), 0, 2)

        self.family_edit = QLineEdit(font.family())
        self.family_list = QListWidget()
        self.family_list.addItems(QFontDatabase.families())
        self._select(self.family_list, font.family())
        self.family_list.setFixedHeight(96)
        self.family_list.currentTextChanged.connect(self.family_edit.setText)
        self.family_list.currentTextChanged.connect(lambda _: self._update_preview())
        self.family_edit.textEdited.connect(lambda t: self._select(self.family_list, t))

        self.style_edit = QLineEdit()
        self.style_list = QListWidget()
        self.style_list.addItems(["Regular", "Italic", "Bold", "Bold Italic"])
        current_style = ("Bold Italic" if font.bold() and font.italic() else
                         "Bold" if font.bold() else
                         "Italic" if font.italic() else "Regular")
        self.style_edit.setText(current_style)
        self._select(self.style_list, current_style)
        self.style_list.setFixedHeight(96)
        self.style_list.currentTextChanged.connect(self.style_edit.setText)
        self.style_list.currentTextChanged.connect(lambda _: self._update_preview())

        size = font.pointSizeF() if font.pointSizeF() > 0 else 12.0
        self.size_edit = QLineEdit(f"{size:g}")
        self.size_list = QListWidget()
        self.size_list.addItems(FONT_SIZES)
        self._select(self.size_list, f"{size:g}")
        self.size_list.setFixedHeight(96)
        self.size_list.currentTextChanged.connect(self.size_edit.setText)
        self.size_list.currentTextChanged.connect(lambda _: self._update_preview())
        self.size_edit.textEdited.connect(lambda _: self._update_preview())

        for col, (edit, lst, width) in enumerate((
                (self.family_edit, self.family_list, 170),
                (self.style_edit, self.style_list, 100),
                (self.size_edit, self.size_list, 56))):
            edit.setFixedWidth(width)
            lst.setFixedWidth(width)
            grid.addWidget(edit, 1, col)
            grid.addWidget(lst, 2, col)
        layout.addLayout(grid)

        row = QGridLayout()
        row.setHorizontalSpacing(10)
        self.color_combo = _color_combo(source.foreground().color()
                                        if source.foreground().style() != Qt.BrushStyle.NoBrush
                                        else None)
        self.color_combo.currentIndexChanged.connect(lambda _: self._update_preview())
        self.underline_combo = QComboBox()
        for name, _style in UNDERLINE_STYLES:
            self.underline_combo.addItem(name)
        if source.fontUnderline():
            self.underline_combo.setCurrentText("Single")
        self.underline_combo.currentIndexChanged.connect(lambda _: self._update_preview())
        self.underline_color = _color_combo(None)
        for column, (label, widget) in enumerate((
                ("Font color:", self.color_combo),
                ("Underline style:", self.underline_combo),
                ("Underline color:", self.underline_color))):
            widget.setMinimumWidth(148)
            row.addWidget(QLabel(label), 0, column)
            row.addWidget(widget, 1, column)
        layout.addLayout(row)

        box, grid2 = _group("Effects")
        self.effects = {}
        names = [
            ("Strikethrough", "strike"), ("Shadow", "shadow"), ("Small caps", "smallcaps"),
            ("Double strikethrough", "dstrike"), ("Outline", "outline"), ("All caps", "allcaps"),
            ("Superscript", "super"), ("Emboss", "emboss"), ("Hidden", "hidden"),
            ("Subscript", "sub"), ("Engrave", "engrave"), ("", ""),
        ]
        for index, (label, key) in enumerate(names):
            if not key:
                continue
            check = QCheckBox(label)
            check.stateChanged.connect(lambda _: self._update_preview())
            self.effects[key] = check
            grid2.addWidget(check, index // 3, index % 3)
        self.effects["strike"].setChecked(source.fontStrikeOut())
        vertical = source.verticalAlignment()
        self.effects["super"].setChecked(
            vertical == QTextCharFormat.VerticalAlignment.AlignSuperScript)
        self.effects["sub"].setChecked(
            vertical == QTextCharFormat.VerticalAlignment.AlignSubScript)
        caps = source.font().capitalization()
        self.effects["smallcaps"].setChecked(caps == QFont.Capitalization.SmallCaps)
        self.effects["allcaps"].setChecked(caps == QFont.Capitalization.AllUppercase)
        self.effects["super"].toggled.connect(
            lambda on: on and self.effects["sub"].setChecked(False))
        self.effects["sub"].toggled.connect(
            lambda on: on and self.effects["super"].setChecked(False))
        layout.addWidget(box)

        prev_box, prev_grid = _group("Preview")
        self.preview = SamplePreview(60, mode="font")
        prev_grid.addWidget(self.preview, 0, 0)
        layout.addWidget(prev_box)
        layout.addWidget(QLabel(
            "This is a TrueType font. This font will be used on both printer and screen."))

    def _build_spacing_page(self, layout, source):
        box, grid = _group("Character spacing")
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["100%", "200%", "150%", "90%", "80%", "66%", "50%", "33%"])
        self.spacing_combo = QComboBox()
        self.spacing_combo.addItems(["Normal", "Expanded", "Condensed"])
        self.spacing_by = QSpinBox()
        self.spacing_by.setRange(0, 100)
        self.spacing_by.setSuffix(" pt")
        self.spacing_by.setValue(1)
        self.position_combo = QComboBox()
        self.position_combo.addItems(["Normal", "Raised", "Lowered"])
        self.position_by = QSpinBox()
        self.position_by.setRange(0, 100)
        self.position_by.setSuffix(" pt")
        self.position_by.setValue(3)
        self.kerning = QCheckBox("Kerning for fonts:")
        grid.addWidget(QLabel("Scale:"), 0, 0)
        grid.addWidget(self.scale_combo, 0, 1)
        grid.addWidget(QLabel("Spacing:"), 1, 0)
        grid.addWidget(self.spacing_combo, 1, 1)
        grid.addWidget(QLabel("By:"), 1, 2)
        grid.addWidget(self.spacing_by, 1, 3)
        grid.addWidget(QLabel("Position:"), 2, 0)
        grid.addWidget(self.position_combo, 2, 1)
        grid.addWidget(QLabel("By:"), 2, 2)
        grid.addWidget(self.position_by, 2, 3)
        grid.addWidget(self.kerning, 3, 0, 1, 2)
        for widget in (self.spacing_combo, self.position_combo):
            widget.currentIndexChanged.connect(lambda _: self._update_preview())
        self.spacing_by.valueChanged.connect(lambda _: self._update_preview())
        layout.addWidget(box)
        layout.addStretch(1)
        prev_box, prev_grid = _group("Preview")
        self.preview2 = SamplePreview(56, mode="font")
        prev_grid.addWidget(self.preview2, 0, 0)
        layout.addWidget(prev_box)

    def _build_effects_page(self, layout):
        box, grid = _group("Animations")
        self.animation_list = QListWidget()
        self.animation_list.addItems([
            "(none)", "Blinking Background", "Las Vegas Lights", "Marching Black Ants",
            "Marching Red Ants", "Shimmer", "Sparkle Text",
        ])
        self.animation_list.setCurrentRow(0)
        grid.addWidget(self.animation_list, 0, 0)
        layout.addWidget(box)
        layout.addWidget(QLabel(
            "Text animations are displayed on the screen but are not printed."))
        layout.addStretch(1)

    # -- helpers -------------------------------------------------------

    @staticmethod
    def _select(widget: QListWidget, text: str):
        items = widget.findItems(text, Qt.MatchFlag.MatchFixedString)
        if items:
            widget.setCurrentItem(items[0])

    def _chosen_font(self) -> QFont:
        font = QFont(self.family_edit.text() or "Times New Roman")
        try:
            font.setPointSizeF(float(self.size_edit.text()))
        except ValueError:
            font.setPointSizeF(12.0)
        style = self.style_edit.text()
        font.setBold("Bold" in style)
        font.setItalic("Italic" in style)
        font.setStrikeOut(self.effects["strike"].isChecked()
                          or self.effects["dstrike"].isChecked())
        font.setUnderline(self.underline_combo.currentText() != "(none)")
        if self.effects["smallcaps"].isChecked():
            font.setCapitalization(QFont.Capitalization.SmallCaps)
        elif self.effects["allcaps"].isChecked():
            font.setCapitalization(QFont.Capitalization.AllUppercase)
        expand = {"Expanded": 1, "Condensed": -1}.get(self.spacing_combo.currentText(), 0)
        if expand:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,
                                  expand * self.spacing_by.value())
        return font

    def _update_preview(self):
        font = self._chosen_font()
        for preview in (getattr(self, "preview", None), getattr(self, "preview2", None)):
            if preview is None:
                continue
            preview.font_spec = font
            preview.sample_text = self.family_edit.text() or "Sample"
            data = self.color_combo.currentData()
            preview.text_color = QColor(data) if data else QColor("black")
            preview.update()

    def _make_default(self):
        if XPMessageBox.confirm(
                self, "MacroHard Word",
                "Do you want to change the default font to "
                f"{self.family_edit.text()}, {self.style_edit.text()}, "
                f"{self.size_edit.text()} pt?\n\n"
                "This change will affect all new documents based on the "
                "NORMAL template.", yes_label="Yes", no_label="No"):
            style = STYLES_BY_NAME["Normal"]
            style.family = self.family_edit.text()
            try:
                style.size = float(self.size_edit.text())
            except ValueError:
                pass
            style.bold = "Bold" in self.style_edit.text()
            style.italic = "Italic" in self.style_edit.text()

    def format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFont(self._chosen_font())
        data = self.color_combo.currentData()
        fmt.setForeground(QColor(data) if data else QColor("black"))
        name = self.underline_combo.currentText()
        for label, style in UNDERLINE_STYLES:
            if label == name:
                fmt.setUnderlineStyle(style)
                break
        under_data = self.underline_color.currentData()
        if under_data:
            fmt.setUnderlineColor(QColor(under_data))
        if self.effects["super"].isChecked():
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSuperScript)
        elif self.effects["sub"].isChecked():
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSubScript)
        else:
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignNormal)
        return fmt


# -------------------------------------------------------------- paragraph ---

ALIGN_CHOICES = [
    ("Left", Qt.AlignmentFlag.AlignLeft),
    ("Centered", Qt.AlignmentFlag.AlignHCenter),
    ("Right", Qt.AlignmentFlag.AlignRight),
    ("Justified", Qt.AlignmentFlag.AlignJustify),
]

LINE_SPACING = ["Single", "1.5 lines", "Double", "At least", "Exactly", "Multiple"]


class ParagraphDialog(MWDialog):
    """Format > Paragraph, with the indentation and spacing that the ruler
    manipulates directly."""

    def __init__(self, parent, block_format: QTextBlockFormat, alignment):
        super().__init__(parent, "Paragraph", width=486)
        unit = settings.options["units"]
        self.unit = unit
        pages = self.add_tabs("Indents and Spacing", "Line and Page Breaks")
        self._build_indents(pages["Indents and Spacing"], block_format, alignment)
        self._build_breaks(pages["Line and Page Breaks"], block_format)
        self.add_buttons(extra=[("Tabs...", self._open_tabs)])
        self._sync_preview()

    def _build_indents(self, layout, fmt, alignment):
        box, grid = _group("General")
        self.align_combo = QComboBox()
        for label, _flag in ALIGN_CHOICES:
            self.align_combo.addItem(label)
        for index, (_label, flag) in enumerate(ALIGN_CHOICES):
            if alignment & flag:
                self.align_combo.setCurrentIndex(index)
                break
        self.outline_combo = QComboBox()
        self.outline_combo.addItems(["Body text"] + [f"Level {i}" for i in range(1, 10)])
        self.outline_combo.setCurrentIndex(0 if fmt.headingLevel() == 0 else fmt.headingLevel())
        self.align_combo.currentIndexChanged.connect(self._sync_preview)
        grid.addWidget(QLabel("Alignment:"), 0, 0)
        grid.addWidget(self.align_combo, 0, 1)
        grid.addWidget(QLabel("Outline level:"), 0, 2)
        grid.addWidget(self.outline_combo, 0, 3)
        layout.addWidget(box)

        box, grid = _group("Indentation")
        from .widgets import MeasureBox
        self.left_box = MeasureBox(self.unit)
        self.left_box.set_px(fmt.leftMargin() + fmt.indent() * inches(0.5))
        self.right_box = MeasureBox(self.unit)
        self.right_box.set_px(fmt.rightMargin())
        self.special_combo = QComboBox()
        self.special_combo.addItems(["(none)", "First line", "Hanging"])
        self.special_by = MeasureBox(self.unit, minimum=0.0)
        indent = fmt.textIndent()
        if indent > 0.01:
            self.special_combo.setCurrentText("First line")
            self.special_by.set_px(indent)
        elif indent < -0.01:
            self.special_combo.setCurrentText("Hanging")
            self.special_by.set_px(-indent)
        else:
            self.special_by.set_px(inches(0.5))
        self.mirror_check = QCheckBox("Mirror indents")
        grid.addWidget(QLabel("Left:"), 0, 0)
        grid.addWidget(self.left_box, 0, 1)
        grid.addWidget(QLabel("Special:"), 0, 2)
        grid.addWidget(self.special_combo, 0, 3)
        grid.addWidget(QLabel("By:"), 0, 4)
        grid.addWidget(self.special_by, 0, 5)
        grid.addWidget(QLabel("Right:"), 1, 0)
        grid.addWidget(self.right_box, 1, 1)
        grid.addWidget(self.mirror_check, 1, 2, 1, 4)
        layout.addWidget(box)

        box, grid = _group("Spacing")
        self.before_box = MeasureBox(self.unit, minimum=0.0)
        self.before_box.set_px(fmt.topMargin())
        self.after_box = MeasureBox(self.unit, minimum=0.0)
        self.after_box.set_px(fmt.bottomMargin())
        self.spacing_combo = QComboBox()
        self.spacing_combo.addItems(LINE_SPACING)
        height = fmt.lineHeight()
        rule = fmt.lineHeightType()
        if rule == QTextBlockFormat.LineHeightTypes.ProportionalHeight and height:
            self.spacing_combo.setCurrentText(
                "Double" if abs(height - 200) < 1 else
                "1.5 lines" if abs(height - 150) < 1 else
                "Single" if abs(height - 100) < 1 else "Multiple")
        self.spacing_at = QSpinBox()
        self.spacing_at.setRange(1, 132)
        self.spacing_at.setValue(12)
        self.spacing_at.setSuffix(" pt")
        self.no_space_same = QCheckBox("Don't add space between paragraphs "
                                       "of the same style")
        for widget in (self.before_box, self.after_box):
            widget.valueChanged.connect(self._sync_preview)
        self.spacing_combo.currentIndexChanged.connect(self._sync_preview)
        self.left_box.valueChanged.connect(self._sync_preview)
        self.right_box.valueChanged.connect(self._sync_preview)
        self.special_combo.currentIndexChanged.connect(self._sync_preview)
        self.special_by.valueChanged.connect(self._sync_preview)
        grid.addWidget(QLabel("Before:"), 0, 0)
        grid.addWidget(self.before_box, 0, 1)
        grid.addWidget(QLabel("Line spacing:"), 0, 2)
        grid.addWidget(self.spacing_combo, 0, 3)
        grid.addWidget(QLabel("At:"), 0, 4)
        grid.addWidget(self.spacing_at, 0, 5)
        grid.addWidget(QLabel("After:"), 1, 0)
        grid.addWidget(self.after_box, 1, 1)
        grid.addWidget(self.no_space_same, 2, 0, 1, 6)
        layout.addWidget(box)

        box, grid = _group("Preview")
        self.preview = SamplePreview(112)
        grid.addWidget(self.preview, 0, 0)
        layout.addWidget(box)

    def _build_breaks(self, layout, fmt):
        box, grid = _group("Pagination")
        self.widow_check = QCheckBox("Widow/Orphan control")
        self.widow_check.setChecked(True)
        self.keep_next = QCheckBox("Keep with next")
        self.keep_lines = QCheckBox("Keep lines together")
        self.page_before = QCheckBox("Page break before")
        for index, widget in enumerate((self.widow_check, self.keep_next,
                                        self.keep_lines, self.page_before)):
            grid.addWidget(widget, index // 2, index % 2)
        layout.addWidget(box)
        box, grid = _group("Formatting exceptions")
        self.suppress_numbers = QCheckBox("Suppress line numbers")
        self.no_hyphenate = QCheckBox("Don't hyphenate")
        grid.addWidget(self.suppress_numbers, 0, 0)
        grid.addWidget(self.no_hyphenate, 0, 1)
        layout.addWidget(box)
        layout.addStretch(1)

    def _open_tabs(self):
        dialog = TabsDialog(self, self.block_format())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._tab_format = dialog.tab_positions()

    def _sync_preview(self):
        self.preview.align = ALIGN_CHOICES[self.align_combo.currentIndex()][1]
        self.preview.left_indent = self.left_box.px()
        self.preview.right_indent = self.right_box.px()
        special = self.special_combo.currentText()
        by = self.special_by.px()
        self.preview.first_indent = by if special == "First line" else -by if special == "Hanging" else 0
        self.preview.space_before = self.before_box.px()
        self.preview.space_after = self.after_box.px()
        self.preview.line_height = {
            "Single": 100.0, "1.5 lines": 150.0, "Double": 200.0}.get(
            self.spacing_combo.currentText(), 100.0)
        self.preview.update()

    def alignment(self):
        return ALIGN_CHOICES[self.align_combo.currentIndex()][1]

    def block_format(self) -> QTextBlockFormat:
        fmt = QTextBlockFormat()
        fmt.setLeftMargin(max(0.0, self.left_box.px()))
        fmt.setRightMargin(max(0.0, self.right_box.px()))
        fmt.setTopMargin(self.before_box.px())
        fmt.setBottomMargin(self.after_box.px())
        special = self.special_combo.currentText()
        by = self.special_by.px()
        fmt.setTextIndent(by if special == "First line" else -by if special == "Hanging" else 0.0)
        fmt.setAlignment(self.alignment())
        spacing = self.spacing_combo.currentText()
        percent = {"Single": 100, "1.5 lines": 150, "Double": 200}.get(spacing)
        if percent:
            fmt.setLineHeight(percent, int(QTextBlockFormat.LineHeightTypes.ProportionalHeight.value))
        elif spacing == "Exactly":
            fmt.setLineHeight(self.spacing_at.value() * 96 / 72,
                              int(QTextBlockFormat.LineHeightTypes.FixedHeight.value))
        elif spacing == "At least":
            fmt.setLineHeight(self.spacing_at.value() * 96 / 72,
                              int(QTextBlockFormat.LineHeightTypes.MinimumHeight.value))
        level = self.outline_combo.currentIndex()
        fmt.setHeadingLevel(level if level else 0)
        fmt.setPageBreakPolicy(
            QTextBlockFormat.PageBreakFlag.PageBreak_AlwaysBefore if self.page_before.isChecked()
            else QTextBlockFormat.PageBreakFlag.PageBreak_Auto)
        return fmt


# ---------------------------------------------------------------- numbers ---

BULLET_CHARS = ["•", "○", "▪", "❖", "➢", "✓"]
NUMBER_FORMATS = ["1.", "1)", "I.", "A.", "a)", "i."]


class BulletsNumberingDialog(MWDialog):
    """The gallery. Eight boxes per tab, the first of which is always None."""

    def __init__(self, parent, current_style=None):
        super().__init__(parent, "Bullets and Numbering", width=400)
        self.chosen = None
        pages = self.add_tabs("Bulleted", "Numbered", "Outline Numbered", "List Styles")
        self._bullet_group = self._gallery(
            pages["Bulleted"],
            [("None", None)] + [(ch, ("bullet", ch)) for ch in BULLET_CHARS])
        self._number_group = self._gallery(
            pages["Numbered"],
            [("None", None)] + [(fmt, ("number", fmt)) for fmt in NUMBER_FORMATS])
        self._outline_group = self._gallery(
            pages["Outline Numbered"],
            [("None", None)] + [(f"{fmt}\n  {fmt}", ("outline", fmt))
                                for fmt in NUMBER_FORMATS[:5]])
        layout = pages["List Styles"]
        layout.addWidget(QLabel("List styles are defined in the attached template."))
        layout.addStretch(1)
        self.add_buttons(extra=[("Customize...", self._customize),
                                ("Reset", lambda: None)])

    def _gallery(self, layout, entries):
        grid = QGridLayout()
        grid.setSpacing(6)
        group = QButtonGroup(self)
        for index, (label, value) in enumerate(entries):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(84, 66)
            btn.setProperty("value", value)
            btn.setStyleSheet(
                "QPushButton { background: white; border: 1px solid #a0a0a0; text-align: left;"
                " padding-left: 10px; font-size: 12px; }"
                "QPushButton:checked { border: 2px solid #316ac5; }")
            group.addButton(btn, index)
            grid.addWidget(btn, index // 4, index % 4)
            btn.clicked.connect(lambda _, v=value: setattr(self, "chosen", v))
        layout.addLayout(grid)
        layout.addStretch(1)
        return group

    def _customize(self):
        XPMessageBox.information(
            self, "Customize", "Customize is available once a gallery position is selected.")

    def selection(self):
        return self.chosen


# ------------------------------------------------------------------- tabs ---

class TabsDialog(MWDialog):
    """Format > Tabs. Positions live on the paragraph's QTextBlockFormat and
    show up as markers on the ruler."""

    def __init__(self, parent, block_format: QTextBlockFormat):
        super().__init__(parent, "Tabs", width=360)
        self.unit = settings.options["units"]
        from .widgets import MeasureBox
        self._tabs = list(block_format.tabPositions())

        grid = QGridLayout()
        grid.addWidget(QLabel("Tab stop position:"), 0, 0)
        grid.addWidget(QLabel("Default tab stops:"), 0, 1)
        self.position_edit = QLineEdit()
        self.default_box = MeasureBox(self.unit, minimum=0.05)
        self.default_box.set_px(inches(0.5))
        grid.addWidget(self.position_edit, 1, 0)
        grid.addWidget(self.default_box, 1, 1)
        self.list = QListWidget()
        self.list.setFixedHeight(110)
        self._refresh_list()
        self.list.currentTextChanged.connect(self.position_edit.setText)
        grid.addWidget(self.list, 2, 0)
        cleared = QLabel("Tab stops to be cleared:")
        grid.addWidget(cleared, 2, 1, Qt.AlignmentFlag.AlignTop)
        self.content.addLayout(grid)

        box, align_grid = _group("Alignment")
        self.align_group = QButtonGroup(self)
        for index, label in enumerate(["Left", "Center", "Right", "Decimal", "Bar"]):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            self.align_group.addButton(radio, index)
            align_grid.addWidget(radio, index // 3, index % 3)
        self.content.addWidget(box)

        box, leader_grid = _group("Leader")
        self.leader_group = QButtonGroup(self)
        for index, label in enumerate(["1 None", "2 ....", "3 ----", "4 ____"]):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            self.leader_group.addButton(radio, index)
            leader_grid.addWidget(radio, 0, index)
        self.content.addWidget(box)

        self.add_buttons(ok="OK", cancel="Cancel",
                         extra=[("Set", self._set), ("Clear", self._clear),
                                ("Clear All", self._clear_all)])

    def _refresh_list(self):
        self.list.clear()
        for tab in sorted(self._tabs, key=lambda t: t.position):
            self.list.addItem(fmt_measure(tab.position, self.unit))

    def _set(self):
        from .model import parse_measure
        value = parse_measure(self.position_edit.text(), self.unit, -1)
        if value < 0:
            return
        types = [QTextOption.TabType.LeftTab, QTextOption.TabType.CenterTab,
                 QTextOption.TabType.RightTab, QTextOption.TabType.DelimiterTab,
                 QTextOption.TabType.LeftTab]
        tab = QTextOption.Tab()
        tab.position = value
        tab.type = types[self.align_group.checkedId()]
        tab.delimiter = "."
        self._tabs = [t for t in self._tabs if abs(t.position - value) > 0.5] + [tab]
        self._refresh_list()

    def _clear(self):
        from .model import parse_measure
        value = parse_measure(self.position_edit.text(), self.unit, -1)
        self._tabs = [t for t in self._tabs if abs(t.position - value) > 0.5]
        self._refresh_list()

    def _clear_all(self):
        self._tabs = []
        self._refresh_list()

    def tab_positions(self):
        return sorted(self._tabs, key=lambda t: t.position)

    def default_stop(self) -> float:
        return self.default_box.px()


# --------------------------------------------------------------- borders ----

BORDER_STYLES = ["None", "Solid", "Dotted", "Dashed", "Dash dot", "Double", "Wave"]


class BordersShadingDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Borders and Shading", width=430)
        pages = self.add_tabs("Borders", "Page Border", "Shading")
        self.setting = "None"
        self._build_border_page(pages["Borders"])
        self._build_border_page(pages["Page Border"], page=True)
        self._build_shading_page(pages["Shading"])
        self.add_buttons(extra=[("Horizontal Line...", lambda: None)])

    def _build_border_page(self, layout, page=False):
        row = QHBoxLayout()
        box, grid = _group("Setting:")
        group = QButtonGroup(self)
        options = ["None", "Box", "Shadow", "3-D", "Custom"]
        for index, label in enumerate(options):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            group.addButton(radio, index)
            grid.addWidget(radio, index, 0)
            if not page:
                radio.toggled.connect(
                    lambda on, l=label: on and setattr(self, "setting", l))
        row.addWidget(box)

        box, grid = _group("Style:")
        style_list = QListWidget()
        style_list.addItems(BORDER_STYLES)
        style_list.setCurrentRow(1)
        style_list.setFixedWidth(120)
        grid.addWidget(style_list, 0, 0, 1, 2)
        grid.addWidget(QLabel("Color:"), 1, 0)
        color_combo = _color_combo(QColor("black"))
        grid.addWidget(color_combo, 1, 1)
        grid.addWidget(QLabel("Width:"), 2, 0)
        width_combo = QComboBox()
        width_combo.addItems(["¼ pt", "½ pt", "¾ pt", "1 pt",
                              "1 ½ pt", "2 ¼ pt", "3 pt", "4 ½ pt", "6 pt"])
        width_combo.setCurrentIndex(3)
        grid.addWidget(width_combo, 2, 1)
        row.addWidget(box)

        box, grid = _group("Preview")
        preview = SamplePreview(120)
        grid.addWidget(preview, 0, 0)
        row.addWidget(box)
        layout.addLayout(row)
        if not page:
            self.style_list = style_list
            self.color_combo = color_combo
            self.width_combo = width_combo
        apply_row = QHBoxLayout()
        apply_row.addStretch(1)
        apply_row.addWidget(QLabel("Apply to:"))
        apply_combo = QComboBox()
        apply_combo.addItems(["Paragraph", "Text"] if not page
                             else ["Whole document", "This section"])
        apply_row.addWidget(apply_combo)
        layout.addLayout(apply_row)

    def _build_shading_page(self, layout):
        row = QHBoxLayout()
        box, grid = _group("Fill")
        from .widgets import ColorGrid
        grid_widget = ColorGrid()
        self.shading_color = None
        grid_widget.picked.connect(lambda value: setattr(self, "shading_color", value))
        grid.addWidget(grid_widget, 0, 0)
        no_fill = QPushButton("No Fill")
        no_fill.clicked.connect(lambda: setattr(self, "shading_color", None))
        grid.addWidget(no_fill, 1, 0)
        row.addWidget(box)
        box, grid = _group("Preview")
        grid.addWidget(SamplePreview(120), 0, 0)
        row.addWidget(box)
        layout.addLayout(row)

    def border_setting(self) -> str:
        return self.setting

    def border_color(self) -> QColor:
        data = self.color_combo.currentData()
        return QColor(data) if data else QColor("black")

    def border_width(self) -> float:
        text = self.width_combo.currentText()
        table = {"¼ pt": 0.25, "½ pt": 0.5, "¾ pt": 0.75, "1 pt": 1.0,
                 "1 ½ pt": 1.5, "2 ¼ pt": 2.25, "3 pt": 3.0,
                 "4 ½ pt": 4.5, "6 pt": 6.0}
        return table.get(text, 1.0)

    def shading(self) -> str | None:
        return self.shading_color


# ---------------------------------------------------------------- columns ---

class ColumnsDialog(MWDialog):
    """Format > Columns. Qt's text engine has no true multi-column flow, so
    applying this drops the text into a borderless table -- which is how
    every word processor faked columns before frames existed."""

    def __init__(self, parent):
        super().__init__(parent, "Columns", width=400)
        self.content.addWidget(QLabel("Presets"))
        row = QHBoxLayout()
        self.preset_group = QButtonGroup(self)
        for index, label in enumerate(["One", "Two", "Three", "Left", "Right"]):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(64, 54)
            if index == 0:
                btn.setChecked(True)
            self.preset_group.addButton(btn, index)
            row.addWidget(btn)
        self.content.addLayout(row)
        self.preset_group.idClicked.connect(self._preset)

        grid = QGridLayout()
        grid.addWidget(QLabel("Number of columns:"), 0, 0)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 12)
        grid.addWidget(self.count_spin, 0, 1)
        self.line_between = QCheckBox("Line between")
        grid.addWidget(self.line_between, 0, 2)
        self.content.addLayout(grid)

        box, group_grid = _group("Width and spacing")
        from .widgets import MeasureBox
        self.width_box = MeasureBox(settings.options["units"], minimum=0.2)
        self.width_box.set_px(inches(6.0))
        self.spacing_box = MeasureBox(settings.options["units"], minimum=0.0)
        self.spacing_box.set_px(inches(0.5))
        group_grid.addWidget(QLabel("Width:"), 0, 0)
        group_grid.addWidget(self.width_box, 0, 1)
        group_grid.addWidget(QLabel("Spacing:"), 0, 2)
        group_grid.addWidget(self.spacing_box, 0, 3)
        self.equal_check = QCheckBox("Equal column width")
        self.equal_check.setChecked(True)
        group_grid.addWidget(self.equal_check, 1, 0, 1, 4)
        self.content.addWidget(box)

        box, group_grid = _group("Preview")
        group_grid.addWidget(SamplePreview(90), 0, 0)
        self.content.addWidget(box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Apply to:"))
        self.apply_combo = QComboBox()
        self.apply_combo.addItems(["Whole document", "This point forward", "Selected text"])
        row.addWidget(self.apply_combo)
        row.addStretch(1)
        self.content.addLayout(row)
        self.add_buttons()

    def _preset(self, index):
        self.count_spin.setValue({0: 1, 1: 2, 2: 3, 3: 2, 4: 2}[index])

    def column_count(self) -> int:
        return self.count_spin.value()

    def spacing(self) -> float:
        return self.spacing_box.px()

    def has_line(self) -> bool:
        return self.line_between.isChecked()


# --------------------------------------------------------------- drop cap ---

class DropCapDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Drop Cap", width=330)
        self.content.addWidget(QLabel("Position"))
        row = QHBoxLayout()
        self.group = QButtonGroup(self)
        for index, label in enumerate(["None", "Dropped", "In margin"]):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(80, 62)
            if index == 0:
                btn.setChecked(True)
            self.group.addButton(btn, index)
            row.addWidget(btn)
        self.content.addLayout(row)

        box, grid = _group("Options")
        self.font_combo = QComboBox()
        self.font_combo.addItems(QFontDatabase.families()[:200])
        self.lines_spin = QSpinBox()
        self.lines_spin.setRange(1, 10)
        self.lines_spin.setValue(3)
        from .widgets import MeasureBox
        self.distance_box = MeasureBox(settings.options["units"], minimum=0.0)
        grid.addWidget(QLabel("Font:"), 0, 0)
        grid.addWidget(self.font_combo, 0, 1)
        grid.addWidget(QLabel("Lines to drop:"), 1, 0)
        grid.addWidget(self.lines_spin, 1, 1)
        grid.addWidget(QLabel("Distance from text:"), 2, 0)
        grid.addWidget(self.distance_box, 2, 1)
        self.content.addWidget(box)
        self.add_buttons()

    def position(self) -> int:
        return self.group.checkedId()

    def lines(self) -> int:
        return self.lines_spin.value()

    def font_family(self) -> str:
        return self.font_combo.currentText()


# ------------------------------------------------------------ change case ---

class ChangeCaseDialog(MWDialog):
    CASES = ["Sentence case.", "lowercase", "UPPERCASE", "Title Case", "tOGGLE cASE"]

    def __init__(self, parent):
        super().__init__(parent, "Change Case", width=250)
        self.group = QButtonGroup(self)
        for index, label in enumerate(self.CASES):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            self.group.addButton(radio, index)
            self.content.addWidget(radio)
        self.add_buttons()

    def choice(self) -> str:
        return self.CASES[self.group.checkedId()]

    @staticmethod
    def convert(text: str, mode: str) -> str:
        if mode == "lowercase":
            return text.lower()
        if mode == "UPPERCASE":
            return text.upper()
        if mode == "Title Case":
            return " ".join(w[:1].upper() + w[1:].lower() if w else w
                            for w in text.split(" "))
        if mode == "tOGGLE cASE":
            return "".join(c.lower() if c.isupper() else c.upper() for c in text)
        out, capitalize = [], True
        for ch in text:
            if capitalize and ch.isalpha():
                out.append(ch.upper())
                capitalize = False
            else:
                out.append(ch.lower())
            if ch in ".!?":
                capitalize = True
        return "".join(out)


# ------------------------------------------------------------- page setup ---

class PageSetupDialog(MWDialog):
    def __init__(self, parent, setup: PageSetup):
        super().__init__(parent, "Page Setup", width=400)
        self.unit = settings.options["units"]
        self.setup = PageSetup(**vars(setup))
        pages = self.add_tabs("Margins", "Paper", "Layout")
        self._build_margins(pages["Margins"])
        self._build_paper(pages["Paper"])
        self._build_layout(pages["Layout"])
        self.add_buttons(extra=[("Default...", self._default)])

    def _build_margins(self, layout):
        from .widgets import MeasureBox
        box, grid = _group("Margins")
        self.top_box = MeasureBox(self.unit, minimum=0.0)
        self.bottom_box = MeasureBox(self.unit, minimum=0.0)
        self.left_box = MeasureBox(self.unit, minimum=0.0)
        self.right_box = MeasureBox(self.unit, minimum=0.0)
        self.gutter_box = MeasureBox(self.unit, minimum=0.0)
        self.top_box.set_px(self.setup.top)
        self.bottom_box.set_px(self.setup.bottom)
        self.left_box.set_px(self.setup.left)
        self.right_box.set_px(self.setup.right)
        self.gutter_box.set_px(self.setup.gutter)
        self.gutter_position = QComboBox()
        self.gutter_position.addItems(["Left", "Top"])
        for index, (label, widget) in enumerate((
                ("Top:", self.top_box), ("Bottom:", self.bottom_box),
                ("Left:", self.left_box), ("Right:", self.right_box),
                ("Gutter:", self.gutter_box))):
            grid.addWidget(QLabel(label), index // 2, (index % 2) * 2)
            grid.addWidget(widget, index // 2, (index % 2) * 2 + 1)
        grid.addWidget(QLabel("Gutter position:"), 2, 2)
        grid.addWidget(self.gutter_position, 2, 3)
        layout.addWidget(box)

        box, grid = _group("Orientation")
        self.portrait = QRadioButton("Portrait")
        self.landscape = QRadioButton("Landscape")
        (self.landscape if self.setup.landscape else self.portrait).setChecked(True)
        grid.addWidget(self.portrait, 0, 0)
        grid.addWidget(self.landscape, 0, 1)
        layout.addWidget(box)

        box, grid = _group("Pages")
        self.multiple_combo = QComboBox()
        self.multiple_combo.addItems(["Normal", "Mirror margins", "2 pages per sheet",
                                      "Book fold"])
        grid.addWidget(QLabel("Multiple pages:"), 0, 0)
        grid.addWidget(self.multiple_combo, 0, 1)
        layout.addWidget(box)

        box, grid = _group("Preview")
        self.preview = SamplePreview(90)
        grid.addWidget(self.preview, 0, 0)
        layout.addWidget(box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Apply to:"))
        self.apply_combo = QComboBox()
        self.apply_combo.addItems(["Whole document", "This point forward"])
        row.addWidget(self.apply_combo)
        row.addStretch(1)
        layout.addLayout(row)

    def _build_paper(self, layout):
        from .widgets import MeasureBox
        box, grid = _group("Paper size")
        self.paper_combo = QComboBox()
        self.paper_combo.addItems(list(PAPER_SIZES) + ["Custom size"])
        self.paper_combo.setCurrentText(self.setup.paper)
        self.paper_width = MeasureBox(self.unit, minimum=1.0, maximum=40.0)
        self.paper_height = MeasureBox(self.unit, minimum=1.0, maximum=40.0)
        self.paper_width.set_px(self.setup.page_width)
        self.paper_height.set_px(self.setup.page_height)
        self.paper_combo.currentTextChanged.connect(self._paper_changed)
        grid.addWidget(QLabel("Paper size:"), 0, 0)
        grid.addWidget(self.paper_combo, 0, 1, 1, 3)
        grid.addWidget(QLabel("Width:"), 1, 0)
        grid.addWidget(self.paper_width, 1, 1)
        grid.addWidget(QLabel("Height:"), 1, 2)
        grid.addWidget(self.paper_height, 1, 3)
        layout.addWidget(box)

        box, grid = _group("Paper source")
        first = QListWidget()
        first.addItems(["Default tray (Automatically Select)", "Manual Feed",
                        "Upper Tray", "Lower Tray", "Envelope Feed"])
        first.setCurrentRow(0)
        other = QListWidget()
        other.addItems(["Default tray (Automatically Select)", "Manual Feed",
                        "Upper Tray", "Lower Tray", "Envelope Feed"])
        other.setCurrentRow(0)
        grid.addWidget(QLabel("First page:"), 0, 0)
        grid.addWidget(QLabel("Other pages:"), 0, 1)
        grid.addWidget(first, 1, 0)
        grid.addWidget(other, 1, 1)
        layout.addWidget(box)
        layout.addStretch(1)

    def _build_layout(self, layout):
        from .widgets import MeasureBox
        box, grid = _group("Section")
        combo = QComboBox()
        combo.addItems(["New page", "Continuous", "New column", "Even page", "Odd page"])
        grid.addWidget(QLabel("Section start:"), 0, 0)
        grid.addWidget(combo, 0, 1)
        layout.addWidget(box)

        box, grid = _group("Headers and footers")
        self.different_odd = QCheckBox("Different odd and even")
        self.different_first = QCheckBox("Different first page")
        self.header_box = MeasureBox(self.unit, minimum=0.0)
        self.footer_box = MeasureBox(self.unit, minimum=0.0)
        self.header_box.set_px(self.setup.header_from_edge)
        self.footer_box.set_px(self.setup.footer_from_edge)
        grid.addWidget(self.different_odd, 0, 0, 1, 2)
        grid.addWidget(self.different_first, 1, 0, 1, 2)
        grid.addWidget(QLabel("Header:"), 2, 0)
        grid.addWidget(self.header_box, 2, 1)
        grid.addWidget(QLabel("Footer:"), 3, 0)
        grid.addWidget(self.footer_box, 3, 1)
        layout.addWidget(box)

        box, grid = _group("Page")
        vertical = QComboBox()
        vertical.addItems(["Top", "Center", "Justified", "Bottom"])
        grid.addWidget(QLabel("Vertical alignment:"), 0, 0)
        grid.addWidget(vertical, 0, 1)
        layout.addWidget(box)
        layout.addStretch(1)

    def _paper_changed(self, name):
        if name in PAPER_SIZES:
            w, h = PAPER_SIZES[name]
            self.paper_width.set_px(inches(w))
            self.paper_height.set_px(inches(h))

    def _default(self):
        XPMessageBox.confirm(
            self, "MacroHard Word",
            "Do you want to change the default settings for page setup?\n\n"
            "This change will affect all new documents based on the NORMAL template.")

    def page_setup(self) -> PageSetup:
        setup = PageSetup()
        setup.paper = self.paper_combo.currentText()
        if setup.paper not in PAPER_SIZES:
            setup.paper = self.setup.paper
        setup.landscape = self.landscape.isChecked()
        setup.top = self.top_box.px()
        setup.bottom = self.bottom_box.px()
        setup.left = self.left_box.px()
        setup.right = self.right_box.px()
        setup.gutter = self.gutter_box.px()
        setup.header_from_edge = self.header_box.px()
        setup.footer_from_edge = self.footer_box.px()
        return setup
