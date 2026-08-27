"""The rest of the dialogs: Insert, Table, Tools and File.

Find and Replace, Spelling and Grammar, Word Count, Zoom, Symbol, Print --
the ones people actually opened, reproduced control for control.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QTextDocument
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton, QRadioButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from ... import theme
from ...xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame
from . import mw_icons
from .dialogs import MWDialog, _group, _labelled
from .model import DocumentProperties, inches, settings
from .widgets import SamplePreview


# ----------------------------------------------------------------- symbol ---

SYMBOL_SUBSETS = {
    "Basic Latin": (0x0020, 0x007E),
    "Latin-1 Supplement": (0x00A0, 0x00FF),
    "Latin Extended-A": (0x0100, 0x017F),
    "Greek and Coptic": (0x0370, 0x03FF),
    "Cyrillic": (0x0400, 0x045F),
    "General Punctuation": (0x2000, 0x206F),
    "Currency Symbols": (0x20A0, 0x20BF),
    "Letterlike Symbols": (0x2100, 0x214F),
    "Number Forms": (0x2150, 0x218F),
    "Arrows": (0x2190, 0x21FF),
    "Mathematical Operators": (0x2200, 0x22FF),
    "Box Drawing": (0x2500, 0x257F),
    "Geometric Shapes": (0x25A0, 0x25FF),
    "Miscellaneous Symbols": (0x2600, 0x26FF),
    "Dingbats": (0x2700, 0x27BF),
}

SPECIAL_CHARACTERS = [
    ("Em Dash", "\u2014", "Alt+Ctrl+Num -"),
    ("En Dash", "\u2013", "Ctrl+Num -"),
    ("Nonbreaking Hyphen", "\u2011", "Ctrl+_"),
    ("Optional Hyphen", "\u00ad", "Ctrl+-"),
    ("Em Space", "\u2003", ""),
    ("En Space", "\u2002", ""),
    ("1/4 Em Space", "\u2005", ""),
    ("Nonbreaking Space", "\u00a0", "Ctrl+Shift+Space"),
    ("Copyright", "\u00a9", "Alt+Ctrl+C"),
    ("Registered", "\u00ae", "Alt+Ctrl+R"),
    ("Trademark", "\u2122", "Alt+Ctrl+T"),
    ("Section", "\u00a7", ""),
    ("Paragraph", "\u00b6", ""),
    ("Ellipsis", "\u2026", "Alt+Ctrl+."),
    ("Single Opening Quote", "\u2018", "Ctrl+`,`"),
    ("Single Closing Quote", "\u2019", "Ctrl+','"),
    ("Double Opening Quote", "\u201c", 'Ctrl+`,"'),
    ("Double Closing Quote", "\u201d", "Ctrl+',\""),
]

RECENT_SYMBOLS: list[str] = ["\u20ac", "\u00a3", "\u00a5", "\u00a9", "\u00ae",
                             "\u2122", "\u00b1", "\u2260", "\u2264", "\u2265",
                             "\u00f7", "\u00d7", "\u221e", "\u03bc", "\u03b1", "\u03b2"]


class SymbolGrid(QWidget):
    """The scrolling character map. Word draws it as a plain grid of cells with
    a blue selection box and a double-click that inserts."""

    activated = pyqtSignal(str)
    hovered = pyqtSignal(str)

    COLS = 16
    ROWS = 8

    def __init__(self):
        super().__init__()
        self.cell = 24
        self.chars: list[str] = []
        self.offset = 0
        self.selected = 0
        self.font_family = "Times New Roman"
        self.setFixedSize(self.COLS * self.cell + 1, self.ROWS * self.cell + 1)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_chars(self, chars: list[str]):
        self.chars = chars
        self.offset = 0
        self.selected = 0
        self.update()

    def visible(self) -> list[str]:
        return self.chars[self.offset:self.offset + self.COLS * self.ROWS]

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("white"))
        p.setFont(QFont(self.font_family, 12))
        p.setPen(QPen(QColor("#c0c0c0"), 1))
        for col in range(self.COLS + 1):
            p.drawLine(col * self.cell, 0, col * self.cell, self.ROWS * self.cell)
        for row in range(self.ROWS + 1):
            p.drawLine(0, row * self.cell, self.COLS * self.cell, row * self.cell)
        for index, ch in enumerate(self.visible()):
            row, col = divmod(index, self.COLS)
            rect = self.rect().adjusted(col * self.cell + 1, row * self.cell + 1, 0, 0)
            rect.setSize(QSize(self.cell - 1, self.cell - 1))
            if self.offset + index == self.selected:
                p.fillRect(rect, QColor("#316ac5"))
                p.setPen(QColor("white"))
            else:
                p.setPen(QColor("black"))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, ch)
        p.end()

    def _index_at(self, pos) -> int:
        col = int(pos.x() // self.cell)
        row = int(pos.y() // self.cell)
        index = self.offset + row * self.COLS + col
        return index if 0 <= index < len(self.chars) else -1

    def mousePressEvent(self, ev):
        index = self._index_at(ev.position())
        if index >= 0:
            self.selected = index
            self.hovered.emit(self.chars[index])
            self.update()

    def mouseDoubleClickEvent(self, ev):
        index = self._index_at(ev.position())
        if index >= 0:
            self.activated.emit(self.chars[index])

    def wheelEvent(self, ev):
        rows = -ev.angleDelta().y() // 40
        self.offset = max(0, min(max(0, len(self.chars) - self.COLS),
                                 self.offset + rows * self.COLS))
        self.update()

    def current(self) -> str:
        return self.chars[self.selected] if self.chars else ""


class SymbolDialog(MWDialog):
    def __init__(self, parent, insert_callback):
        super().__init__(parent, "Symbol", width=440)
        self.insert_callback = insert_callback
        pages = self.add_tabs("Symbols", "Special Characters")
        self._build_symbols(pages["Symbols"])
        self._build_special(pages["Special Characters"])
        self.add_buttons(ok=None, cancel="Cancel",
                         extra=[("Insert", self._insert_current)])

    def _build_symbols(self, layout):
        row = QHBoxLayout()
        self.font_combo = QComboBox()
        self.font_combo.addItems(["(normal text)"] + QFontDatabase.families())
        self.subset_combo = QComboBox()
        self.subset_combo.addItems(list(SYMBOL_SUBSETS))
        row.addLayout(_labelled("Font:", self.font_combo))
        row.addLayout(_labelled("Subset:", self.subset_combo))
        layout.addLayout(row)

        self.grid = SymbolGrid()
        layout.addWidget(self.grid, 0, Qt.AlignmentFlag.AlignHCenter)
        self.grid.activated.connect(self._insert)
        self.grid.hovered.connect(lambda _: self._sync_labels())

        layout.addWidget(QLabel("Recently used symbols:"))
        self.recent = SymbolGrid()
        self.recent.ROWS = 1
        self.recent.setFixedSize(self.recent.COLS * self.recent.cell + 1,
                                 self.recent.cell + 1)
        self.recent.set_chars(RECENT_SYMBOLS)
        self.recent.activated.connect(self._insert)
        layout.addWidget(self.recent, 0, Qt.AlignmentFlag.AlignHCenter)

        info = QHBoxLayout()
        self.name_label = QLabel()
        self.code_edit = QLineEdit()
        self.code_edit.setFixedWidth(70)
        self.from_combo = QComboBox()
        self.from_combo.addItems(["Unicode (hex)", "ASCII (decimal)", "ASCII (hex)"])
        info.addLayout(_labelled("Character code:", self.code_edit))
        info.addLayout(_labelled("from:", self.from_combo))
        layout.addWidget(self.name_label)
        layout.addLayout(info)

        self.subset_combo.currentTextChanged.connect(self._load_subset)
        self.font_combo.currentTextChanged.connect(self._font_changed)
        self._load_subset(self.subset_combo.currentText())

    def _build_special(self, layout):
        self.special_list = QListWidget()
        for name, ch, shortcut in SPECIAL_CHARACTERS:
            item = QListWidgetItem(f"{ch}\t{name}\t{shortcut}")
            item.setData(Qt.ItemDataRole.UserRole, ch)
            self.special_list.addItem(item)
        self.special_list.setCurrentRow(0)
        self.special_list.itemDoubleClicked.connect(
            lambda item: self._insert(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.special_list)

    def _font_changed(self, name):
        self.grid.font_family = "Times New Roman" if name.startswith("(") else name
        self.recent.font_family = self.grid.font_family
        self.grid.update()
        self.recent.update()

    def _load_subset(self, name):
        start, end = SYMBOL_SUBSETS.get(name, (0x20, 0x7E))
        chars = []
        for code in range(start, end + 1):
            ch = chr(code)
            if unicodedata.category(ch)[0] not in ("C", "Z") or ch == " ":
                chars.append(ch)
        self.grid.set_chars(chars)
        self._sync_labels()

    def _sync_labels(self):
        ch = self.grid.current()
        if not ch:
            return
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = "UNKNOWN"
        self.name_label.setText(name.title())
        self.code_edit.setText(f"{ord(ch):04X}")

    def _insert_current(self):
        if self.tabs.currentIndex() == 0:
            self._insert(self.grid.current())
        else:
            item = self.special_list.currentItem()
            if item:
                self._insert(item.data(Qt.ItemDataRole.UserRole))

    def _insert(self, ch: str):
        if not ch:
            return
        if ch in RECENT_SYMBOLS:
            RECENT_SYMBOLS.remove(ch)
        RECENT_SYMBOLS.insert(0, ch)
        del RECENT_SYMBOLS[16:]
        self.recent.set_chars(RECENT_SYMBOLS)
        self.insert_callback(ch)


# ------------------------------------------------------------------ break ---

class BreakDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Break", width=260)
        box, grid = _group("Break types")
        self.break_group = QButtonGroup(self)
        for index, label in enumerate(["Page break", "Column break",
                                       "Text wrapping break"]):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            self.break_group.addButton(radio, index)
            grid.addWidget(radio, index, 0)
        self.content.addWidget(box)

        box, grid = _group("Section break types")
        for index, label in enumerate(["Next page", "Continuous", "Even page", "Odd page"]):
            radio = QRadioButton(label)
            self.break_group.addButton(radio, index + 3)
            grid.addWidget(radio, index, 0)
        self.content.addWidget(box)
        self.add_buttons()

    def kind(self) -> int:
        return self.break_group.checkedId()


# ----------------------------------------------------------- page numbers ---

class PageNumbersDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Page Numbers", width=340)
        grid = QGridLayout()
        self.position_combo = QComboBox()
        self.position_combo.addItems(["Bottom of page (Footer)", "Top of page (Header)"])
        self.align_combo = QComboBox()
        self.align_combo.addItems(["Right", "Left", "Center", "Inside", "Outside"])
        grid.addWidget(QLabel("Position:"), 0, 0)
        grid.addWidget(self.position_combo, 0, 1)
        grid.addWidget(QLabel("Alignment:"), 1, 0)
        grid.addWidget(self.align_combo, 1, 1)
        self.show_first = QCheckBox("Show number on first page")
        self.show_first.setChecked(True)
        grid.addWidget(self.show_first, 2, 0, 1, 2)
        self.content.addLayout(grid)
        box, box_grid = _group("Preview")
        box_grid.addWidget(SamplePreview(90), 0, 0)
        self.content.addWidget(box)
        self.add_buttons(extra=[("Format...", lambda: None)])

    def alignment(self) -> str:
        return self.align_combo.currentText()


# --------------------------------------------------------- date and time ----

DATE_FORMATS = [
    "%m/%d/%Y", "%A, %B %d, %Y", "%B %d, %Y", "%m/%d/%y", "%Y-%m-%d",
    "%d-%b-%y", "%B %y", "%b-%y", "%m/%d/%Y %I:%M %p", "%m/%d/%Y %I:%M:%S %p",
    "%I:%M %p", "%I:%M:%S %p", "%H:%M", "%H:%M:%S",
]


class DateTimeDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Date and Time", width=340)
        self.content.addWidget(QLabel("Available formats:"))
        self.list = QListWidget()
        now = datetime.now()
        for spec in DATE_FORMATS:
            item = QListWidgetItem(now.strftime(spec))
            item.setData(Qt.ItemDataRole.UserRole, spec)
            self.list.addItem(item)
        self.list.setCurrentRow(1)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        self.content.addWidget(self.list)
        row = QHBoxLayout()
        self.language = QComboBox()
        self.language.addItems(["English (U.S.)", "English (U.K.)", "French (France)"])
        row.addLayout(_labelled("Language:", self.language))
        row.addStretch(1)
        self.content.addLayout(row)
        self.auto_update = QCheckBox("Update automatically")
        self.content.addWidget(self.auto_update)
        self.add_buttons(extra=[("Default...", lambda: None)])

    def text(self) -> str:
        item = self.list.currentItem()
        if not item:
            return ""
        return datetime.now().strftime(item.data(Qt.ItemDataRole.UserRole))


# -------------------------------------------------------------- hyperlink ---

class HyperlinkDialog(MWDialog):
    def __init__(self, parent, display_text=""):
        super().__init__(parent, "Insert Hyperlink", width=430)
        row = QHBoxLayout()
        row.addWidget(QLabel("Text to display:"))
        self.text_edit = QLineEdit(display_text)
        row.addWidget(self.text_edit, 1)
        tip = QPushButton("ScreenTip...")
        tip.setFixedHeight(22)
        row.addWidget(tip)
        self.content.addLayout(row)

        body = QHBoxLayout()
        self.places = QListWidget()
        self.places.setFixedWidth(110)
        for label in ["Existing File or\nWeb Page", "Place in This\nDocument",
                      "Create New\nDocument", "E-mail Address"]:
            self.places.addItem(label)
        self.places.setCurrentRow(0)
        body.addWidget(self.places)

        right = QVBoxLayout()
        self.address_edit = QLineEdit("http://")
        right.addLayout(_labelled("Address:", self.address_edit))
        self.browsed = QListWidget()
        self.browsed.addItems([
            "http://www.macrohard.com/", "http://www.macrohard.com/office/",
            "file:///C:/My Documents/", "http://search.macrohard.com/",
        ])
        self.browsed.itemClicked.connect(
            lambda item: self.address_edit.setText(item.text()))
        right.addWidget(self.browsed)
        body.addLayout(right, 1)
        self.content.addLayout(body)
        self.add_buttons(extra=[("Bookmark...", lambda: None),
                                ("Target Frame...", lambda: None)])

    def address(self) -> str:
        return self.address_edit.text()

    def display_text(self) -> str:
        return self.text_edit.text()


# ------------------------------------------------------------ insert table ---

class InsertTableDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Insert Table", width=330)
        box, grid = _group("Table size")
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 63)
        self.cols_spin.setValue(5)
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 200)
        self.rows_spin.setValue(2)
        grid.addWidget(QLabel("Number of columns:"), 0, 0)
        grid.addWidget(self.cols_spin, 0, 1)
        grid.addWidget(QLabel("Number of rows:"), 1, 0)
        grid.addWidget(self.rows_spin, 1, 1)
        self.content.addWidget(box)

        box, grid = _group("AutoFit behavior")
        self.fit_group = QButtonGroup(self)
        for index, label in enumerate(["Fixed column width:", "AutoFit to contents",
                                       "AutoFit to window"]):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            self.fit_group.addButton(radio, index)
            grid.addWidget(radio, index, 0)
        self.width_combo = QComboBox()
        self.width_combo.setEditable(True)
        self.width_combo.addItems(["Auto", '0.5"', '1"', '1.5"'])
        grid.addWidget(self.width_combo, 0, 1)
        self.content.addWidget(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Table style: Table Grid"))
        row.addStretch(1)
        autoformat = QPushButton("AutoFormat...")
        autoformat.setFixedHeight(22)
        autoformat.clicked.connect(self._autoformat)
        row.addWidget(autoformat)
        self.content.addLayout(row)
        self.style = "Table Grid"

        self.remember = QCheckBox("Remember dimensions for new tables")
        self.content.addWidget(self.remember)
        self.add_buttons()

    def _autoformat(self):
        dialog = TableAutoFormatDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.style = dialog.style()

    def rows(self) -> int:
        return self.rows_spin.value()

    def columns(self) -> int:
        return self.cols_spin.value()

    def autofit(self) -> int:
        return self.fit_group.checkedId()


TABLE_STYLES = {
    "Table Grid": {"border": 1.0, "header": None, "shade": None},
    "Table Normal": {"border": 0.0, "header": None, "shade": None},
    "Table Simple 1": {"border": 1.0, "header": "#e8e8e8", "shade": None},
    "Table Classic 1": {"border": 1.5, "header": "#3a5f9e", "shade": "#eef2f8"},
    "Table Colorful 1": {"border": 1.0, "header": "#c0504d", "shade": "#f7e4e2"},
    "Table Colorful 2": {"border": 1.0, "header": "#4a8b3a", "shade": "#e8f2e4"},
    "Table List 3": {"border": 1.0, "header": "#333399", "shade": None},
    "Table Professional": {"border": 1.5, "header": "#333333", "shade": "#f0f0f0"},
}


class TableAutoFormatDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Table AutoFormat", width=380)
        row = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("Table styles:"))
        self.list = QListWidget()
        self.list.addItems(list(TABLE_STYLES))
        self.list.setCurrentRow(0)
        left.addWidget(self.list)
        row.addLayout(left)
        right = QVBoxLayout()
        right.addWidget(QLabel("Preview"))
        right.addWidget(SamplePreview(120))
        row.addLayout(right, 1)
        self.content.addLayout(row)
        box, grid = _group("Apply special formats to")
        for index, label in enumerate(["Heading rows", "First column",
                                       "Last row", "Last column"]):
            check = QCheckBox(label)
            check.setChecked(index < 2)
            grid.addWidget(check, index // 2, index % 2)
        self.content.addWidget(box)
        self.add_buttons()

    def style(self) -> str:
        item = self.list.currentItem()
        return item.text() if item else "Table Grid"


class TablePropertiesDialog(MWDialog):
    def __init__(self, parent, table=None):
        super().__init__(parent, "Table Properties", width=380)
        pages = self.add_tabs("Table", "Row", "Column", "Cell")
        layout = pages["Table"]
        box, grid = _group("Size")
        self.preferred = QCheckBox("Preferred width:")
        grid.addWidget(self.preferred, 0, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 100)
        self.width_spin.setValue(100)
        self.width_spin.setSuffix(" %")
        grid.addWidget(self.width_spin, 0, 1)
        layout.addWidget(box)
        box, grid = _group("Alignment")
        self.align_group = QButtonGroup(self)
        for index, label in enumerate(["Left", "Center", "Right"]):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            self.align_group.addButton(radio, index)
            grid.addWidget(radio, 0, index)
        layout.addWidget(box)
        box, grid = _group("Text wrapping")
        for index, label in enumerate(["None", "Around"]):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            grid.addWidget(radio, 0, index)
        layout.addWidget(box)
        row = QHBoxLayout()
        row.addStretch(1)
        for label in ("Borders and Shading...", "Options..."):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            row.addWidget(btn)
        layout.addLayout(row)
        for name in ("Row", "Column", "Cell"):
            pages[name].addWidget(QLabel(f"{name} settings apply to the current selection."))
            pages[name].addStretch(1)
        self.add_buttons()

    def cell_padding(self) -> float:
        return inches(0.08)


# ------------------------------------------------------------------- zoom ---

class ZoomDialog(MWDialog):
    def __init__(self, parent, current=100):
        super().__init__(parent, "Zoom", width=360)
        row = QHBoxLayout()
        box, grid = _group("Zoom to")
        self.group = QButtonGroup(self)
        presets = ["200%", "100%", "75%", "Page width", "Text width", "Whole page",
                   "Many pages:"]
        for index, label in enumerate(presets):
            radio = QRadioButton(label)
            self.group.addButton(radio, index)
            grid.addWidget(radio, index, 0)
        grid.addWidget(QLabel("Percent:"), len(presets), 0)
        self.percent = QSpinBox()
        self.percent.setRange(10, 500)
        self.percent.setValue(current)
        self.percent.setSuffix(" %")
        grid.addWidget(self.percent, len(presets), 1)
        self.group.idClicked.connect(self._preset)
        row.addWidget(box)

        right = QVBoxLayout()
        right.addWidget(QLabel("Preview"))
        self.preview = SamplePreview(150)
        right.addWidget(self.preview)
        self.font_label = QLabel("Times New Roman 12 pt")
        right.addWidget(self.font_label)
        row.addLayout(right, 1)
        self.content.addLayout(row)
        self.add_buttons()

    def _preset(self, index):
        mapping = {0: 200, 1: 100, 2: 75}
        if index in mapping:
            self.percent.setValue(mapping[index])
        elif index == 3:
            self.percent.setValue(-1)
        elif index == 4:
            self.percent.setValue(-2)
        elif index == 5:
            self.percent.setValue(-3)

    def zoom(self) -> int:
        return self.percent.value()

    def mode(self) -> str:
        return {3: "page_width", 4: "text_width", 5: "whole_page"}.get(
            self.group.checkedId(), "percent")


# ------------------------------------------------------------- word count ---

class WordCountDialog(MWDialog):
    def __init__(self, parent, stats: dict):
        super().__init__(parent, "Word Count", width=300)
        box, grid = _group("Statistics:")
        rows = [
            ("Pages", stats["pages"]),
            ("Words", stats["words"]),
            ("Characters (no spaces)", stats["chars_no_spaces"]),
            ("Characters (with spaces)", stats["chars"]),
            ("Paragraphs", stats["paragraphs"]),
            ("Lines", stats["lines"]),
        ]
        for index, (label, value) in enumerate(rows):
            grid.addWidget(QLabel(label), index, 0)
            value_label = QLabel(f"{value:,}")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(value_label, index, 1)
        self.content.addWidget(box)
        self.include = QCheckBox("Include footnotes and endnotes")
        self.content.addWidget(self.include)
        self.add_buttons(ok=None, cancel="Close",
                         extra=[("Show Toolbar", lambda: None)])


# ------------------------------------------------------------- properties ---

class DocPropertiesDialog(MWDialog):
    def __init__(self, parent, props: DocumentProperties, stats: dict, filename: str):
        super().__init__(parent, f"{filename} Properties", width=380)
        self.props = props
        pages = self.add_tabs("General", "Summary", "Statistics", "Contents", "Custom")

        layout = pages["General"]
        grid = QGridLayout()
        rows = [
            ("Type:", "MacroHard Word Document"),
            ("Location:", "C:\\My Documents"),
            ("Size:", f"{stats['chars'] * 2 + 9216:,} bytes"),
            ("MS-DOS name:", filename.upper()[:8].replace(" ", "~")[:8] + ".DOC"),
            ("Created:", props.created or "—"),
            ("Modified:", props.modified or "—"),
            ("Accessed:", datetime.now().strftime("%A, %B %d, %Y")),
            ("Attributes:", "Archive"),
        ]
        for index, (label, value) in enumerate(rows):
            grid.addWidget(QLabel(label), index, 0)
            grid.addWidget(QLabel(value), index, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

        layout = pages["Summary"]
        grid = QGridLayout()
        self.fields = {}
        for index, (label, attr) in enumerate([
                ("Title:", "title"), ("Subject:", "subject"), ("Author:", "author"),
                ("Manager:", "manager"), ("Company:", "company"),
                ("Category:", "category"), ("Keywords:", "keywords"),
                ("Comments:", "comments")]):
            grid.addWidget(QLabel(label), index, 0)
            edit = QLineEdit(getattr(props, attr))
            self.fields[attr] = edit
            grid.addWidget(edit, index, 1)
        layout.addLayout(grid)
        self.save_preview = QCheckBox("Save preview picture")
        layout.addWidget(self.save_preview)

        layout = pages["Statistics"]
        grid = QGridLayout()
        stat_rows = [
            ("Created:", props.created or "—"),
            ("Modified:", props.modified or "—"),
            ("Accessed:", datetime.now().strftime("%A, %B %d, %Y")),
            ("Printed:", props.last_printed or "—"),
            ("Last saved by:", props.author or "MacroHard User"),
            ("Revision number:", str(props.revision)),
            ("Total editing time:", f"{props.editing_minutes} Minutes"),
        ]
        for index, (label, value) in enumerate(stat_rows):
            grid.addWidget(QLabel(label), index, 0)
            grid.addWidget(QLabel(value), index, 1)
        layout.addLayout(grid)
        layout.addWidget(QLabel("Statistics:"))
        table = QTableWidget(6, 2)
        table.setHorizontalHeaderLabels(["Statistic name", "Value"])
        table.verticalHeader().setVisible(False)
        for index, (name, value) in enumerate([
                ("Pages", stats["pages"]), ("Paragraphs", stats["paragraphs"]),
                ("Lines", stats["lines"]), ("Words", stats["words"]),
                ("Characters", stats["chars"]),
                ("Characters (with spaces)", stats["chars"])]):
            table.setItem(index, 0, QTableWidgetItem(name))
            table.setItem(index, 1, QTableWidgetItem(f"{value:,}"))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        pages["Contents"].addWidget(QLabel("Document contents:"))
        contents = QListWidget()
        contents.addItem("Title: " + (props.title or "(none)"))
        pages["Contents"].addWidget(contents)
        pages["Custom"].addWidget(QLabel("No custom properties are defined."))
        pages["Custom"].addStretch(1)
        self.add_buttons()

    def apply_to(self, props: DocumentProperties):
        for attr, edit in self.fields.items():
            setattr(props, attr, edit.text())


# ------------------------------------------------------------ autocorrect ---

class AutoCorrectDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "AutoCorrect", width=420)
        opts = settings.autocorrect_options
        pages = self.add_tabs("AutoCorrect", "AutoFormat As You Type",
                              "AutoText", "AutoFormat")
        layout = pages["AutoCorrect"]
        self.checks = {}
        for label, attr in [
                ("Correct TWo INitial CApitals", "two_initial_caps"),
                ("Capitalize first letter of sentences", "capitalize_sentences"),
                ("Capitalize names of days", "capitalize_days"),
                ("Correct accidental usage of cAPS LOCK key", "correct_caps_lock"),
        ]:
            check = QCheckBox(label)
            check.setChecked(getattr(opts, attr))
            self.checks[attr] = check
            layout.addWidget(check)

        self.replace_check = QCheckBox("Replace text as you type")
        self.replace_check.setChecked(opts.replace_text)
        self.checks["replace_text"] = self.replace_check
        layout.addWidget(self.replace_check)

        row = QHBoxLayout()
        self.replace_edit = QLineEdit()
        self.with_edit = QLineEdit()
        row.addLayout(_labelled("Replace:", self.replace_edit))
        row.addLayout(_labelled("With:", self.with_edit))
        layout.addLayout(row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Replace", "With"])
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(160)
        self._reload_table()
        self.table.itemSelectionChanged.connect(self._select_entry)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        row.addStretch(1)
        add = QPushButton("Add")
        add.clicked.connect(self._add)
        delete = QPushButton("Delete")
        delete.clicked.connect(self._delete)
        for btn in (add, delete):
            btn.setFixedHeight(22)
            row.addWidget(btn)
        layout.addLayout(row)
        layout.addWidget(QCheckBox("Automatically use suggestions from the spelling checker"))

        layout = pages["AutoFormat As You Type"]
        layout.addWidget(QLabel("Replace as you type"))
        for label, attr in [
                ('"Straight quotes" with "smart quotes"', "smart_quotes"),
                ("Ordinals (1st) with superscript", "ordinals_superscript"),
                ("Fractions (1/2) with fraction character (½)", "fractions"),
                ("Hyphens (--) with dash (—)", "symbol_dashes"),
                ("Internet and network paths with hyperlinks", "internet_hyperlinks"),
        ]:
            check = QCheckBox(label)
            check.setChecked(getattr(opts, attr))
            self.checks[attr] = check
            layout.addWidget(check)
        layout.addWidget(QLabel("Apply as you type"))
        for label, attr in [
                ("Automatic bulleted lists", "auto_bullets"),
                ("Automatic numbered lists", "auto_numbers"),
        ]:
            check = QCheckBox(label)
            check.setChecked(getattr(opts, attr))
            self.checks[attr] = check
            layout.addWidget(check)
        layout.addStretch(1)

        pages["AutoText"].addWidget(QLabel("Show AutoComplete suggestions"))
        pages["AutoText"].addWidget(QListWidget())
        pages["AutoFormat"].addWidget(QLabel(
            "AutoFormat applies these changes when you run Format > AutoFormat."))
        pages["AutoFormat"].addStretch(1)
        self.add_buttons()

    def _reload_table(self):
        entries = sorted(settings.autocorrect.items())
        self.table.setRowCount(len(entries))
        for row, (key, value) in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(key))
            self.table.setItem(row, 1, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    def _select_entry(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.replace_edit.setText(self.table.item(row, 0).text())
        self.with_edit.setText(self.table.item(row, 1).text())

    def _add(self):
        key = self.replace_edit.text().strip()
        value = self.with_edit.text()
        if key and value:
            settings.autocorrect[key.lower()] = value
            self._reload_table()

    def _delete(self):
        key = self.replace_edit.text().strip().lower()
        if key in settings.autocorrect:
            del settings.autocorrect[key]
            self._reload_table()

    def apply(self):
        opts = settings.autocorrect_options
        for attr, check in self.checks.items():
            setattr(opts, attr, check.isChecked())
        settings.save()


# ---------------------------------------------------------------- options ---

class OptionsDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Options", width=430)
        self.checks: dict[str, QCheckBox] = {}
        pages = self.add_tabs("View", "General", "Edit", "Print", "Save",
                              "Spelling & Grammar")
        self._view(pages["View"])
        self._general(pages["General"])
        self._edit(pages["Edit"])
        self._print(pages["Print"])
        self._save(pages["Save"])
        self._spelling(pages["Spelling & Grammar"])
        self.add_buttons()

    def _check(self, layout, label, key):
        check = QCheckBox(label)
        check.setChecked(bool(settings.options.get(key)))
        self.checks[key] = check
        layout.addWidget(check)
        return check

    def _view(self, layout):
        box, grid = _group("Show")
        for index, (label, key) in enumerate([
                ("Status bar", "show_status_bar"), ("Startup Task Pane", "show_task_pane"),
                ("Highlight", "view_highlight"), ("Bookmarks", "view_bookmarks"),
                ("Smart tags", "view_smart_tags"), ("Animated text", "view_animated"),
                ("Windows in Taskbar", "view_taskbar"), ("Field codes", "view_fields")]):
            check = QCheckBox(label)
            check.setChecked(settings.options.get(key, index < 2))
            self.checks[key] = check
            grid.addWidget(check, index // 2, index % 2)
        layout.addWidget(box)

        box, grid = _group("Formatting marks")
        for index, (label, key) in enumerate([
                ("Tab characters", "marks_tabs"), ("Spaces", "marks_spaces"),
                ("Paragraph marks", "marks_paragraphs"), ("Hidden text", "marks_hidden"),
                ("Optional hyphens", "marks_hyphens"), ("All", "show_formatting_marks")]):
            check = QCheckBox(label)
            check.setChecked(settings.options.get(key, False))
            self.checks[key] = check
            grid.addWidget(check, index // 2, index % 2)
        layout.addWidget(box)

        box, grid = _group("Print and Web Layout options")
        for index, (label, key) in enumerate([
                ("Drawings", "layout_drawings"), ("Object anchors", "layout_anchors"),
                ("Text boundaries", "layout_boundaries"), ("White space between pages",
                                                            "layout_whitespace"),
                ("Vertical ruler (Print view)", "layout_vruler")]):
            check = QCheckBox(label)
            check.setChecked(settings.options.get(key, key in ("layout_drawings",
                                                               "layout_whitespace",
                                                               "layout_vruler")))
            self.checks[key] = check
            grid.addWidget(check, index // 2, index % 2)
        layout.addWidget(box)
        layout.addStretch(1)

    def _general(self, layout):
        for label, key in [
                ("Background repagination", "background_repagination"),
                ("Blue background, white text", "general_blue_background"),
                ("Provide feedback with sound", "general_sound"),
                ("Provide feedback with animation", "general_animation"),
                ("Confirm conversion at Open", "general_confirm_conversion"),
                ("Update automatic links at Open", "general_update_links"),
                ("Mail as attachment", "general_mail_attachment"),
                ("Allow background open of web pages", "general_bg_open")]:
            check = QCheckBox(label)
            check.setChecked(settings.options.get(key, key == "background_repagination"))
            self.checks[key] = check
            layout.addWidget(check)
        row = QHBoxLayout()
        self.mru_spin = QSpinBox()
        self.mru_spin.setRange(0, 9)
        self.mru_spin.setValue(int(settings.options.get("recently_used_count", 4)))
        row.addWidget(QCheckBox("Recently used file list:"))
        row.addWidget(self.mru_spin)
        row.addWidget(QLabel("entries"))
        row.addStretch(1)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.units_combo = QComboBox()
        self.units_combo.addItems(["Inches", "Centimeters", "Points"])
        self.units_combo.setCurrentText(settings.options.get("units", "Inches"))
        row.addLayout(_labelled("Measurement units:", self.units_combo))
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _edit(self, layout):
        for label, key in [
                ("Typing replaces selection", "typing_replaces_selection"),
                ("Drag-and-drop text editing", "drag_and_drop"),
                ("Use the INS key for paste", "edit_ins_paste"),
                ("Overtype mode", "edit_overtype"),
                ("Use smart cursoring", "edit_smart_cursor"),
                ("When selecting, automatically select entire word", "edit_whole_word"),
                ("Prompt to update style", "edit_prompt_style"),
                ("Smart cut and paste", "smart_cut_paste")]:
            check = QCheckBox(label)
            check.setChecked(settings.options.get(
                key, key in ("typing_replaces_selection", "drag_and_drop",
                             "smart_cut_paste", "edit_whole_word")))
            self.checks[key] = check
            layout.addWidget(check)
        layout.addStretch(1)

    def _print(self, layout):
        box, grid = _group("Printing options")
        for index, (label, key) in enumerate([
                ("Draft output", "print_draft"), ("Update fields", "print_update_fields"),
                ("Reverse print order", "print_reverse"), ("Background printing",
                                                            "print_background"),
                ("Print PostScript over text", "print_postscript")]):
            check = QCheckBox(label)
            check.setChecked(settings.options.get(key, key == "print_background"))
            self.checks[key] = check
            grid.addWidget(check, index // 2, index % 2)
        layout.addWidget(box)
        box, grid = _group("Include with document")
        for index, (label, key) in enumerate([
                ("Document properties", "print_props"), ("Field codes", "print_fields"),
                ("Hidden text", "print_hidden"), ("Drawing objects", "print_drawings")]):
            check = QCheckBox(label)
            check.setChecked(settings.options.get(key, key == "print_drawings"))
            self.checks[key] = check
            grid.addWidget(check, index // 2, index % 2)
        layout.addWidget(box)
        layout.addStretch(1)

    def _save(self, layout):
        for label, key in [
                ("Always create backup copy", "save_backup"),
                ("Allow fast saves", "save_fast"),
                ("Prompt for document properties", "save_prompt_props"),
                ("Prompt to save Normal template", "save_prompt_normal"),
                ("Embed TrueType fonts", "save_embed_fonts"),
                ("Make local copy of files stored on network", "save_local_copy")]:
            check = QCheckBox(label)
            check.setChecked(settings.options.get(key, key == "save_fast"))
            self.checks[key] = check
            layout.addWidget(check)
        row = QHBoxLayout()
        self.autosave_check = QCheckBox("Save AutoRecover info every:")
        self.autosave_check.setChecked(int(settings.options.get("autosave_minutes", 10)) > 0)
        self.autosave_spin = QSpinBox()
        self.autosave_spin.setRange(1, 120)
        self.autosave_spin.setValue(max(1, int(settings.options.get("autosave_minutes", 10))))
        row.addWidget(self.autosave_check)
        row.addWidget(self.autosave_spin)
        row.addWidget(QLabel("minutes"))
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _spelling(self, layout):
        box, grid = _group("Spelling")
        self.spell_check = QCheckBox("Check spelling as you type")
        self.spell_check.setChecked(bool(settings.options.get("check_spelling", True)))
        grid.addWidget(self.spell_check, 0, 0)
        for index, (label, key) in enumerate([
                ("Hide spelling errors in this document", "spell_hide"),
                ("Always suggest corrections", "spell_suggest"),
                ("Ignore words in UPPERCASE", "spell_ignore_upper"),
                ("Ignore words with numbers", "spell_ignore_numbers"),
                ("Ignore Internet and file addresses", "spell_ignore_urls")], start=1):
            check = QCheckBox(label)
            check.setChecked(settings.options.get(key, key != "spell_hide"))
            self.checks[key] = check
            grid.addWidget(check, index, 0)
        layout.addWidget(box)

        box, grid = _group("Grammar")
        self.grammar_check = QCheckBox("Check grammar as you type")
        self.grammar_check.setChecked(bool(settings.options.get("check_grammar", True)))
        grid.addWidget(self.grammar_check, 0, 0)
        self.grammar_with_spelling = QCheckBox("Check grammar with spelling")
        self.grammar_with_spelling.setChecked(True)
        grid.addWidget(self.grammar_with_spelling, 1, 0)
        style_combo = QComboBox()
        style_combo.addItems(["Grammar Only", "Grammar & Style", "Casual", "Formal",
                              "Technical", "Custom"])
        grid.addWidget(QLabel("Writing style:"), 2, 0)
        grid.addWidget(style_combo, 2, 1)
        layout.addWidget(box)
        row = QHBoxLayout()
        row.addStretch(1)
        recheck = QPushButton("Recheck Document")
        recheck.setFixedHeight(22)
        row.addWidget(recheck)
        layout.addLayout(row)
        layout.addStretch(1)

    def apply(self):
        for key, check in self.checks.items():
            settings.options[key] = check.isChecked()
        settings.options["check_spelling"] = self.spell_check.isChecked()
        settings.options["check_grammar"] = self.grammar_check.isChecked()
        settings.options["units"] = self.units_combo.currentText()
        settings.options["recently_used_count"] = self.mru_spin.value()
        settings.options["autosave_minutes"] = (
            self.autosave_spin.value() if self.autosave_check.isChecked() else 0)
        settings.save()


# --------------------------------------------------------- find / replace ---

class FindReplaceDialog(MWDialog):
    """Modeless, as Word's is, with the More >> panel that doubles its height."""

    def __init__(self, owner, tab=0):
        super().__init__(owner, "Find and Replace", width=430, modal=False)
        self.owner = owner
        self._expanded = False
        pages = self.add_tabs("Find", "Replace", "Go To")
        self._build_find(pages["Find"])
        self._build_replace(pages["Replace"])
        self._build_goto(pages["Go To"])
        self.tabs.setCurrentIndex(tab)
        self.tabs.currentChanged.connect(self._sync_tab)

    def _options_panel(self, prefix):
        box, grid = _group("Search Options")
        box.setVisible(False)
        direction = QComboBox()
        direction.addItems(["All", "Down", "Up"])
        grid.addWidget(QLabel("Search:"), 0, 0)
        grid.addWidget(direction, 0, 1)
        checks = {}
        for index, (label, key) in enumerate([
                ("Match case", "case"), ("Find whole words only", "whole"),
                ("Use wildcards", "wildcards"), ("Sounds like (English)", "sounds"),
                ("Find all word forms (English)", "forms")]):
            check = QCheckBox(label)
            checks[key] = check
            grid.addWidget(check, 1 + index // 2, index % 2)
        setattr(self, f"{prefix}_direction", direction)
        setattr(self, f"{prefix}_checks", checks)
        return box

    def _build_find(self, layout):
        self.find_edit = QLineEdit()
        layout.addLayout(_labelled("Find what:", self.find_edit, 70))
        self.find_highlight = QCheckBox("Highlight all items found in:")
        layout.addWidget(self.find_highlight)
        self.find_options = self._options_panel("find")
        layout.addWidget(self.find_options)
        layout.addStretch(1)
        row = QHBoxLayout()
        self.find_more = QPushButton("More \u2193")
        self.find_more.setFixedHeight(22)
        self.find_more.clicked.connect(lambda: self._toggle_more(self.find_options,
                                                                 self.find_more))
        row.addWidget(self.find_more)
        row.addStretch(1)
        for label, slot in (("Find Next", self._find_next), ("Cancel", self.close)):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setMinimumWidth(84)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        layout.addLayout(row)
        self.find_edit.returnPressed.connect(self._find_next)

    def _build_replace(self, layout):
        self.replace_find_edit = QLineEdit()
        self.replace_with_edit = QLineEdit()
        layout.addLayout(_labelled("Find what:", self.replace_find_edit, 70))
        layout.addLayout(_labelled("Replace with:", self.replace_with_edit, 70))
        self.replace_options = self._options_panel("replace")
        layout.addWidget(self.replace_options)
        layout.addStretch(1)
        row = QHBoxLayout()
        self.replace_more = QPushButton("More \u2193")
        self.replace_more.setFixedHeight(22)
        self.replace_more.clicked.connect(
            lambda: self._toggle_more(self.replace_options, self.replace_more))
        row.addWidget(self.replace_more)
        row.addStretch(1)
        for label, slot in (("Replace", self._replace), ("Replace All", self._replace_all),
                            ("Find Next", self._find_next), ("Cancel", self.close)):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setMinimumWidth(76)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        layout.addLayout(row)

    def _build_goto(self, layout):
        row = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("Go to what:"))
        self.goto_list = QListWidget()
        self.goto_list.addItems(["Page", "Section", "Line", "Bookmark", "Comment",
                                 "Footnote", "Endnote", "Field", "Table", "Graphic",
                                 "Equation", "Object", "Heading"])
        self.goto_list.setCurrentRow(0)
        self.goto_list.setFixedWidth(130)
        left.addWidget(self.goto_list)
        row.addLayout(left)
        right = QVBoxLayout()
        right.addWidget(QLabel("Enter page number:"))
        self.goto_edit = QLineEdit()
        right.addWidget(self.goto_edit)
        right.addWidget(QLabel("Enter + and - to move relative to the current location.\n"
                               "Example: +4 will move forward four items."))
        right.addStretch(1)
        row.addLayout(right, 1)
        layout.addLayout(row)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for label, slot in (("Next", self._goto), ("Close", self.close)):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setMinimumWidth(80)
            btn.clicked.connect(slot)
            buttons.addWidget(btn)
        layout.addLayout(buttons)
        self.goto_edit.returnPressed.connect(self._goto)

    def _toggle_more(self, panel, button):
        visible = not panel.isVisible()
        panel.setVisible(visible)
        button.setText("Less \u2191" if visible else "More \u2193")
        self.adjustSize()

    def _sync_tab(self, index):
        if index == 1 and self.find_edit.text():
            self.replace_find_edit.setText(self.find_edit.text())

    def _flags(self, prefix):
        checks = getattr(self, f"{prefix}_checks")
        flags = QTextDocument.FindFlag(0)
        if checks["case"].isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if checks["whole"].isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        if getattr(self, f"{prefix}_direction").currentText() == "Up":
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def _active_terms(self):
        if self.tabs.currentIndex() == 1:
            return (self.replace_find_edit.text(), self.replace_with_edit.text(), "replace")
        return (self.find_edit.text(), "", "find")

    def _find_next(self):
        term, _, prefix = self._active_terms()
        if not self.owner.find_text(term, self._flags(prefix)):
            XPMessageBox.information(
                self, "MacroHard Word",
                "MacroHard Word has finished searching the document. "
                "The search item was not found.")

    def _replace(self):
        term, replacement, prefix = self._active_terms()
        self.owner.replace_once(term, replacement, self._flags(prefix))

    def _replace_all(self):
        term, replacement, prefix = self._active_terms()
        count = self.owner.replace_all(term, replacement, self._flags(prefix))
        XPMessageBox.information(
            self, "MacroHard Word", f"Word has completed its search of the document and "
                                    f"has made {count} replacements.")

    def _goto(self):
        kind = self.goto_list.currentItem().text()
        self.owner.go_to(kind, self.goto_edit.text())


# ---------------------------------------------------- spelling and grammar ---

class SpellingDialog(MWDialog):
    """Tools > Spelling and Grammar. Steps through the same issue list the
    squiggles come from, and every button does what its label says."""

    def __init__(self, owner):
        super().__init__(owner, "Spelling and Grammar: English (U.S.)", width=420)
        self.owner = owner
        self.current = None

        self.header = QLabel("Not in Dictionary:")
        self.content.addWidget(self.header)
        self.context = QTextEdit()
        self.context.setFixedHeight(64)
        self.context.setReadOnly(True)
        self.content.addWidget(self.context)

        self.content.addWidget(QLabel("Suggestions:"))
        self.suggestions = QListWidget()
        self.suggestions.setFixedHeight(90)
        self.content.addWidget(self.suggestions)

        row = QHBoxLayout()
        left = QVBoxLayout()
        for label, slot in (("Ignore Once", self._ignore_once),
                            ("Ignore All", self._ignore_all),
                            ("Add to Dictionary", self._add_word)):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.clicked.connect(slot)
            left.addWidget(btn)
        right = QVBoxLayout()
        for label, slot in (("Change", self._change),
                            ("Change All", self._change_all),
                            ("AutoCorrect", self._autocorrect)):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.clicked.connect(slot)
            right.addWidget(btn)
        row.addLayout(left)
        row.addLayout(right)
        self.content.addLayout(row)

        bottom = QHBoxLayout()
        self.dictionary_combo = QComboBox()
        self.dictionary_combo.addItems(["English (U.S.)", "English (U.K.)",
                                        "French (France)", "German (Germany)"])
        bottom.addLayout(_labelled("Dictionary language:", self.dictionary_combo))
        self.content.addLayout(bottom)
        self.grammar_check = QCheckBox("Check grammar")
        self.grammar_check.setChecked(bool(settings.options.get("check_grammar", True)))
        self.grammar_check.toggled.connect(lambda _: self.next_issue())
        self.content.addWidget(self.grammar_check)

        self.add_buttons(ok=None, cancel="Cancel",
                         extra=[("Options...", self._options), ("Undo", self._undo)])
        QTimer.singleShot(0, self.next_issue)

    # -- flow ------------------------------------------------------------

    def next_issue(self):
        issue = self.owner.next_spelling_issue(self.grammar_check.isChecked())
        self.current = issue
        if issue is None:
            self.close()
            XPMessageBox.information(
                self, "MacroHard Word",
                "The spelling and grammar check is complete.")
            return
        kind, position, length, word, label = issue
        self.header.setText(f"{label}:")
        self.setWindowTitle("Spelling and Grammar: English (U.S.)")
        self.context.setHtml(self.owner.issue_context_html(position, length, kind))
        self.suggestions.clear()
        if kind == "spelling":
            options = self.owner.checker.suggest(word)
            self.suggestions.addItems(options or ["(no spelling suggestions)"])
        else:
            self.suggestions.addItems(self.owner.grammar_suggestions(word, label))
        self.suggestions.setCurrentRow(0)

    def _selected(self) -> str:
        item = self.suggestions.currentItem()
        return item.text() if item else ""

    def _ignore_once(self):
        self.owner.advance_issue()
        self.next_issue()

    def _ignore_all(self):
        if self.current:
            self.owner.checker.ignore_all(self.current[3])
            self.owner.rehighlight()
        self.owner.advance_issue()
        self.next_issue()

    def _add_word(self):
        if self.current:
            settings.add_word(self.current[3])
            self.owner.rehighlight()
        self.owner.advance_issue()
        self.next_issue()

    def _change(self):
        text = self._selected()
        if self.current and text and not text.startswith("("):
            self.owner.apply_correction(self.current, text)
        else:
            self.owner.advance_issue()
        self.next_issue()

    def _change_all(self):
        text = self._selected()
        if self.current and text and not text.startswith("("):
            self.owner.apply_correction(self.current, text, everywhere=True)
        self.next_issue()

    def _autocorrect(self):
        text = self._selected()
        if self.current and text and not text.startswith("("):
            settings.autocorrect[self.current[3].lower()] = text
            settings.save()
            self.owner.apply_correction(self.current, text)
        self.next_issue()

    def _options(self):
        dialog = OptionsDialog(self)
        dialog.tabs.setCurrentIndex(5)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.apply()
            self.owner.apply_options()

    def _undo(self):
        self.owner.editor.undo()
        self.next_issue()


# ------------------------------------------------------------------ print ---

PRINTERS = [
    ("HP LaserJet 4000 Series PCL", "Ready", "LPT1:"),
    ("MacroHard Document Image Writer", "Ready", "Local Port"),
    ("Acrobat Distiller", "Ready", "Documents\\*.pdf"),
    ("Generic / Text Only", "Offline", "LPT2:"),
    ("Fax", "Ready", "SHRFAX:"),
]


class PrintDialog(MWDialog):
    def __init__(self, parent, page_count=1, current_page=1):
        super().__init__(parent, "Print", width=440)
        self.page_count = page_count

        box, grid = _group("Printer")
        self.printer_combo = QComboBox()
        for name, _status, _port in PRINTERS:
            self.printer_combo.addItem(name)
        grid.addWidget(QLabel("Name:"), 0, 0)
        grid.addWidget(self.printer_combo, 0, 1, 1, 2)
        properties = QPushButton("Properties")
        properties.setFixedHeight(22)
        grid.addWidget(properties, 0, 3)
        self.status_label = QLabel()
        self.where_label = QLabel()
        grid.addWidget(QLabel("Status:"), 1, 0)
        grid.addWidget(self.status_label, 1, 1)
        grid.addWidget(QLabel("Type:"), 2, 0)
        grid.addWidget(QLabel("PCL 6 Driver"), 2, 1)
        grid.addWidget(QLabel("Where:"), 3, 0)
        grid.addWidget(self.where_label, 3, 1)
        grid.addWidget(QLabel("Comment:"), 4, 0)
        self.to_file = QCheckBox("Print to file")
        grid.addWidget(self.to_file, 4, 3)
        self.printer_combo.currentIndexChanged.connect(self._sync_printer)
        self._sync_printer(0)
        self.content.addWidget(box)

        row = QHBoxLayout()
        box, grid = _group("Page range")
        self.range_group = QButtonGroup(self)
        for index, label in enumerate(["All", "Current page", "Selection", "Pages:"]):
            radio = QRadioButton(label)
            if index == 0:
                radio.setChecked(True)
            self.range_group.addButton(radio, index)
            grid.addWidget(radio, index, 0)
        self.pages_edit = QLineEdit()
        self.pages_edit.setPlaceholderText(f"1-{page_count}")
        grid.addWidget(self.pages_edit, 3, 1)
        row.addWidget(box)

        box, grid = _group("Copies")
        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 999)
        grid.addWidget(QLabel("Number of copies:"), 0, 0)
        grid.addWidget(self.copies_spin, 0, 1)
        self.collate = QCheckBox("Collate")
        self.collate.setChecked(True)
        grid.addWidget(self.collate, 1, 0)
        row.addWidget(box)
        self.content.addLayout(row)

        row = QHBoxLayout()
        box, grid = _group("Print what")
        self.what_combo = QComboBox()
        self.what_combo.addItems(["Document", "Document properties", "Document showing markup",
                                  "List of markup", "Styles", "AutoText entries",
                                  "Key assignments"])
        grid.addWidget(self.what_combo, 0, 0)
        self.print_combo = QComboBox()
        self.print_combo.addItems(["All pages in range", "Odd pages", "Even pages"])
        grid.addWidget(QLabel("Print:"), 1, 0)
        grid.addWidget(self.print_combo, 2, 0)
        row.addWidget(box)

        box, grid = _group("Zoom")
        self.per_sheet = QComboBox()
        self.per_sheet.addItems(["1 page", "2 pages", "4 pages", "6 pages",
                                 "8 pages", "16 pages"])
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["No Scaling", "Letter", "Legal", "A4"])
        grid.addWidget(QLabel("Pages per sheet:"), 0, 0)
        grid.addWidget(self.per_sheet, 0, 1)
        grid.addWidget(QLabel("Scale to paper size:"), 1, 0)
        grid.addWidget(self.scale_combo, 1, 1)
        row.addWidget(box)
        self.content.addLayout(row)
        self.add_buttons(extra=[("Options...", lambda: None)])

    def _sync_printer(self, index):
        _name, status, port = PRINTERS[index]
        self.status_label.setText(status)
        self.where_label.setText(port)

    def copies(self) -> int:
        return self.copies_spin.value()

    def printer(self) -> str:
        return self.printer_combo.currentText()


class PrintProgressDialog(QDialog):
    """The little spooler box with the sheet-flying-into-the-printer animation."""

    def __init__(self, parent, printer: str, pages: int):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        inner = build_dialog_frame(self, "Printing")
        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }}"
                           f"{DIALOG_BUTTON_QSS} QLabel {{ background: transparent; }}")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)
        row = QHBoxLayout()
        glyph = QLabel()
        glyph.setPixmap(mw_icons.pixmap("print", 32))
        row.addWidget(glyph)
        self.label = QLabel(f"Now printing page 1 of {pages}\non {printer}")
        row.addWidget(self.label, 1)
        layout.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, pages)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(22)
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        layout.addLayout(row)
        inner.addWidget(body)
        self.setFixedWidth(320)

        self.page = 0
        self.pages = pages
        self.printer = printer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(360)

    def _tick(self):
        self.page += 1
        if self.page > self.pages:
            self.timer.stop()
            self.accept()
            return
        self.bar.setValue(self.page)
        self.label.setText(f"Now printing page {self.page} of {self.pages}\n"
                           f"on {self.printer}")
