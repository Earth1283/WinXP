"""Ex-Cell's dialogs, on Word's Luna dialog chrome."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QRadioButton, QSpinBox, QVBoxLayout,
)

from ...xp_dialog import XPMessageBox
from ..mword.dialogs import MWDialog
from ..mword.widgets import ColorPickerButton
from . import formulas as fx
from .model import DEFAULT_FORMAT, format_value, settings

FUNCTION_HELP = {
    "SUM": ("number1,number2,...", "Adds all the numbers in a range of cells."),
    "AVERAGE": ("number1,number2,...", "Returns the average (arithmetic mean) of its arguments."),
    "IF": ("logical_test,value_if_true,value_if_false",
           "Checks whether a condition is met, and returns one value if TRUE, and another if FALSE."),
    "VLOOKUP": ("lookup_value,table_array,col_index_num,range_lookup",
                "Looks for a value in the leftmost column of a table. You will get the column "
                "number wrong at least once."),
    "COUNTIF": ("range,criteria", "Counts the number of cells within a range that meet the condition."),
    "IFERROR": ("value,value_if_error", "Available in a later version. This is not that version."),
    "RAND": ("", "Returns a random number. A different one every time you look."),
    "NOW": ("", "Returns the current date and time, formatted as a number you won't recognise."),
}


class TextPrompt(MWDialog):
    def __init__(self, parent, title, label, value=""):
        super().__init__(parent, title, width=300)
        self.content.addWidget(QLabel(label))
        self.edit = QLineEdit(value)
        self.edit.selectAll()
        self.content.addWidget(self.edit)
        self.add_buttons()

    @classmethod
    def get(cls, parent, title, label, value="") -> str | None:
        dialog = cls(parent, title, label, value)
        if dialog.exec():
            return dialog.edit.text()
        return None


class LegacyDialog(MWDialog):
    """Where the off switch for Hexcel lives."""

    def __init__(self, parent):
        super().__init__(parent, "Advanced International Options", width=360)
        group = QGroupBox("Legacy")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("These settings are provided for compatibility with\n"
                                "spreadsheets created before 2003."))
        self.lotus = QCheckBox("Transition formula evaluation (Lotus 1-2-3)")
        self.lotus.setEnabled(False)
        layout.addWidget(self.lotus)
        self.decimal = QCheckBox("Display numbers as numbers (not recommended)")
        self.decimal.setChecked(not settings.options["hexcel"])
        layout.addWidget(self.decimal)
        self.content.addWidget(group)
        self.add_buttons()

    def accept(self):
        want_decimal = self.decimal.isChecked()
        if want_decimal and settings.options["hexcel"]:
            if not XPMessageBox.confirm(
                    self, "MacroHard Ex-Cell",
                    "Numbers displayed as numbers can be read by anyone looking at "
                    "your screen.\n\nDo you want to continue?"):
                return
        elif not want_decimal and not settings.options["hexcel"]:
            XPMessageBox.information(self, "MacroHard Ex-Cell", "Welcome back.")
        settings.options["hexcel"] = not want_decimal
        settings.save()
        super().accept()


class OptionsDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Options", width=440)
        pages = self.add_tabs("View", "Calculation", "Edit", "General", "International")

        show = QGroupBox("Show")
        grid = QVBoxLayout(show)
        self.formula_bar = QCheckBox("Formula bar")
        self.formula_bar.setChecked(settings.options["formula_bar"])
        self.status_bar = QCheckBox("Status bar")
        self.status_bar.setChecked(settings.options["status_bar"])
        self.assistant = QCheckBox("Office Assistant (Pi)")
        self.assistant.setChecked(settings.options["assistant_enabled"])
        for box in (self.formula_bar, self.status_bar, self.assistant):
            grid.addWidget(box)
        pages["View"].addWidget(show)
        window = QGroupBox("Window options")
        wgrid = QVBoxLayout(window)
        self.gridlines = QCheckBox("Gridlines")
        self.gridlines.setChecked(settings.options["gridlines"])
        wgrid.addWidget(self.gridlines)
        pages["View"].addWidget(window)
        pages["View"].addStretch(1)

        calc = QGroupBox("Calculation")
        cgrid = QVBoxLayout(calc)
        auto = QRadioButton("Automatic")
        auto.setChecked(True)
        manual = QRadioButton("Manual")
        manual.setEnabled(False)
        cgrid.addWidget(auto)
        cgrid.addWidget(manual)
        iteration = QCheckBox("Iteration")
        iteration.setChecked(True)
        iteration.setEnabled(False)
        cgrid.addWidget(iteration)
        note = QLabel("Ex-Cell iterates circular references whether or not this box is "
                      "checked. Maximum iterations: unlimited.")
        note.setWordWrap(True)
        cgrid.addWidget(note)
        pages["Calculation"].addWidget(calc)
        pages["Calculation"].addStretch(1)

        edit = QGroupBox("Settings")
        egrid = QVBoxLayout(edit)
        for label, checked in (("Edit directly in cell", True),
                               ("Allow cell drag and drop", True),
                               ("Move selection after Enter", True),
                               ("Enable automatic percent entry", True),
                               ("Convert entries that look like dates to dates", True)):
            box = QCheckBox(label)
            box.setChecked(checked)
            box.setEnabled(not label.startswith("Convert"))
            egrid.addWidget(box)
        pages["Edit"].addWidget(edit)
        pages["Edit"].addStretch(1)

        general = QGroupBox("Settings")
        ggrid = QGridLayout(general)
        ggrid.addWidget(QLabel("Sheets in new workbook:"), 0, 0)
        sheets = QSpinBox()
        sheets.setValue(3)
        sheets.setEnabled(False)
        ggrid.addWidget(sheets, 0, 1)
        ggrid.addWidget(QLabel("User name:"), 1, 0)
        ggrid.addWidget(QLineEdit("MacroHard User"), 1, 1)
        pages["General"].addWidget(general)
        pages["General"].addStretch(1)

        number = QGroupBox("Number handling")
        ngrid = QGridLayout(number)
        ngrid.addWidget(QLabel("Decimal separator:"), 0, 0)
        ngrid.addWidget(QLineEdit("."), 0, 1)
        ngrid.addWidget(QLabel("Thousands separator:"), 1, 0)
        ngrid.addWidget(QLineEdit(","), 1, 1)
        ngrid.addWidget(QLabel("Number base:"), 2, 0)
        base = QLabel("16 (set by Ex-Cell)")
        ngrid.addWidget(base, 2, 1)
        pages["International"].addWidget(number)
        row = QHBoxLayout()
        row.addStretch(1)
        advanced = QPushButton("Advanced...")
        advanced.setFixedHeight(22)
        advanced.clicked.connect(lambda: LegacyDialog(self).exec())
        row.addWidget(advanced)
        pages["International"].addLayout(row)
        pages["International"].addStretch(1)

        self.add_buttons()

    def accept(self):
        settings.options["formula_bar"] = self.formula_bar.isChecked()
        settings.options["status_bar"] = self.status_bar.isChecked()
        settings.options["assistant_enabled"] = self.assistant.isChecked()
        settings.options["gridlines"] = self.gridlines.isChecked()
        settings.save()
        super().accept()


class InsertFunctionDialog(MWDialog):
    def __init__(self, parent):
        super().__init__(parent, "Insert Function", width=420)
        self.content.addWidget(QLabel("Or select a category:"))
        self.category = QComboBox()
        self.category.addItems(list(fx.CATEGORIES) + ["All"])
        self.content.addWidget(self.category)
        self.content.addWidget(QLabel("Select a function:"))
        self.list = QListWidget()
        self.list.setMinimumHeight(150)
        self.content.addWidget(self.list)
        self.signature = QLabel()
        self.signature.setStyleSheet("font-weight: bold;")
        self.content.addWidget(self.signature)
        self.help = QLabel()
        self.help.setWordWrap(True)
        self.help.setMinimumHeight(32)
        self.content.addWidget(self.help)
        self.category.currentTextChanged.connect(self._fill)
        self.list.currentTextChanged.connect(self._describe)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        self._fill(self.category.currentText())
        self.add_buttons()

    def _fill(self, category):
        names = sorted(fx.FUNCTIONS) if category == "All" else fx.CATEGORIES[category]
        self.list.clear()
        self.list.addItems(names)
        self.list.setCurrentRow(0)

    def _describe(self, name):
        if not name:
            return
        args, text = FUNCTION_HELP.get(name, ("...", ""))
        if name not in fx.FUNCTIONS:
            text = "This function is listed here because you used it recently. You didn't."
        self.signature.setText(f"{name}({args})")
        self.help.setText(text or f"Returns the result of {name}.")

    @classmethod
    def get(cls, parent) -> str | None:
        dialog = cls(parent)
        if dialog.exec() and dialog.list.currentItem():
            return dialog.list.currentItem().text()
        return None


NUMBER_CATEGORIES = ["General", "Number", "Currency", "Date", "Time", "Percent",
                     "Scientific", "Text"]
DATE_TYPES = ["d-mmm", "m/d/yyyy", "d-mmm-yy", "mmm-yy", "mmmm d, yyyy"]


class FormatCellsDialog(MWDialog):
    def __init__(self, parent, cell):
        super().__init__(parent, "Format Cells", width=440)
        self.cell = cell
        style = cell.style if cell else (lambda k: DEFAULT_FORMAT[k])
        pages = self.add_tabs("Number", "Alignment", "Font", "Border", "Patterns")

        row = QHBoxLayout()
        self.category = QListWidget()
        self.category.addItems(NUMBER_CATEGORIES)
        self.category.setFixedWidth(110)
        self.category.setCurrentRow(NUMBER_CATEGORIES.index(style("num")))
        row.addWidget(self.category)
        side = QVBoxLayout()
        self.sample = QLabel()
        self.sample.setStyleSheet("background: white; border: 1px solid #7f9db9; padding: 3px;")
        side.addWidget(QLabel("Sample"))
        side.addWidget(self.sample)
        dec_row = QHBoxLayout()
        dec_row.addWidget(QLabel("Decimal places:"))
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 30)
        self.decimals.setValue(int(style("dec")))
        dec_row.addWidget(self.decimals)
        side.addLayout(dec_row)
        self.thousands = QCheckBox("Use 1000 Separator (,)")
        self.thousands.setChecked(bool(style("thousands")))
        side.addWidget(self.thousands)
        side.addWidget(QLabel("Type:"))
        self.date_type = QComboBox()
        self.date_type.addItems(DATE_TYPES)
        self.date_type.setCurrentText(style("date"))
        side.addWidget(self.date_type)
        self.hex_note = QLabel()
        self.hex_note.setWordWrap(True)
        side.addWidget(self.hex_note)
        side.addStretch(1)
        row.addLayout(side, 1)
        pages["Number"].addLayout(row)

        self.align = QComboBox()
        self.align.addItems(["General", "Left", "Center", "Right"])
        self.align.setCurrentText((style("align") or "general").title())
        pages["Alignment"].addWidget(QLabel("Horizontal:"))
        pages["Alignment"].addWidget(self.align)
        pages["Alignment"].addStretch(1)

        self.bold = QCheckBox("Bold")
        self.bold.setChecked(bool(style("bold")))
        self.italic = QCheckBox("Italic")
        self.italic.setChecked(bool(style("italic")))
        self.underline = QCheckBox("Single underline")
        self.underline.setChecked(bool(style("underline")))
        for box in (self.bold, self.italic, self.underline):
            pages["Font"].addWidget(box)
        self.font_color = ColorPickerButton("font_color", QColor(style("color") or "black"),
                                            tooltip="Color")
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        color_row.addWidget(self.font_color)
        color_row.addStretch(1)
        pages["Font"].addLayout(color_row)
        pages["Font"].addStretch(1)

        self.border = QCheckBox("Outline")
        self.border.setChecked(bool(style("border")))
        pages["Border"].addWidget(self.border)
        pages["Border"].addStretch(1)

        self.fill = ColorPickerButton("highlight", QColor(style("fill") or "#ffffff"),
                                      automatic_label="No Color",
                                      automatic_color=QColor(0, 0, 0, 0), tooltip="Cell shading")
        fill_row = QHBoxLayout()
        fill_row.addWidget(QLabel("Cell shading:"))
        fill_row.addWidget(self.fill)
        fill_row.addStretch(1)
        pages["Patterns"].addLayout(fill_row)
        pages["Patterns"].addStretch(1)

        for signal in (self.category.currentRowChanged, self.decimals.valueChanged,
                       self.thousands.toggled, self.date_type.currentTextChanged):
            signal.connect(self._update_sample)
        self._update_sample()
        self.add_buttons()

    def changes(self) -> dict:
        align = self.align.currentText().lower()
        fill = self.fill.color
        return {
            "num": self.category.currentItem().text(),
            "dec": self.decimals.value(),
            "thousands": self.thousands.isChecked(),
            "date": self.date_type.currentText(),
            "align": "" if align == "general" else align,
            "bold": self.bold.isChecked(),
            "italic": self.italic.isChecked(),
            "underline": self.underline.isChecked(),
            "color": "" if self.font_color.color == QColor("black")
            else self.font_color.color.name(),
            "border": self.border.isChecked(),
            "fill": "" if fill.alpha() == 0 or fill == QColor("#ffffff") else fill.name(),
        }

    def _update_sample(self):
        from .model import Cell
        probe = Cell(fmt={k: v for k, v in self.changes().items() if k in
                          ("num", "dec", "thousands", "date")})
        value = self.cell.value if self.cell and isinstance(self.cell.value, float) else 1234.5
        self.sample.setText(format_value(value, probe, settings.options["hexcel"]))
        self.hex_note.setText("Numbers are displayed in hexadecimal. To change this, see "
                              "Tools > Options > International > Advanced."
                              if settings.options["hexcel"] else "")


class FindDialog(MWDialog):
    def __init__(self, parent, window, replace=False):
        super().__init__(parent, "Find and Replace", width=380, modal=False)
        self.window_ = window
        grid = QGridLayout()
        grid.addWidget(QLabel("Find what:"), 0, 0)
        self.find_edit = QLineEdit()
        grid.addWidget(self.find_edit, 0, 1)
        grid.addWidget(QLabel("Replace with:"), 1, 0)
        self.replace_edit = QLineEdit()
        grid.addWidget(self.replace_edit, 1, 1)
        self.content.addLayout(grid)
        self.case = QCheckBox("Match case")
        self.whole = QCheckBox("Match entire cell contents")
        self.content.addWidget(self.case)
        self.content.addWidget(self.whole)
        self.add_buttons(ok=None, cancel="Close", extra=(
            ("Replace All", self._replace_all), ("Find Next", self._find_next)))
        self.replace_edit.setEnabled(True)
        if not replace:
            self.find_edit.setFocus()

    def _matches(self, text: str) -> bool:
        needle = self.find_edit.text()
        if not needle:
            return False
        a, b = (text, needle) if self.case.isChecked() else (text.lower(), needle.lower())
        return a == b if self.whole.isChecked() else b in a

    def _find_next(self):
        self.window_.find_next(self._matches)

    def _replace_all(self):
        count = self.window_.replace_all(self.find_edit.text(), self.replace_edit.text(),
                                         self.case.isChecked(), self.whole.isChecked())
        XPMessageBox.information(self, "MacroHard Ex-Cell",
                                 f"Ex-Cell has completed its search and has made "
                                 f"{count} replacement{'s' if count != 1 else ''}.")
