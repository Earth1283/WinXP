from __future__ import annotations

import math

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QActionGroup, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenuBar,
    QPushButton, QVBoxLayout,
)

from .. import theme
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox


OPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
}

BUTTON_QSS = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:0.48 #f5f4ef, stop:1 #dedbd0);
    border-top: 1px solid #ffffff;
    border-left: 1px solid #ffffff;
    border-right: 1px solid #404040;
    border-bottom: 1px solid #404040;
    border-radius: 2px;
    padding: 0;
    font: 11px 'Tahoma';
}
QPushButton:hover {
    border: 1px solid #316ac5;
    background: #f7f6f0;
}
QPushButton:pressed {
    background: #d8d4c7;
    border-top: 1px solid #404040;
    border-left: 1px solid #404040;
    border-right: 1px solid #ffffff;
    border-bottom: 1px solid #ffffff;
    padding-left: 1px;
    padding-top: 1px;
}
"""


class CalculatorWindow(XPWindow):
    """Windows XP's compact Standard Calculator."""

    def __init__(self, wm):
        super().__init__(
            wm, title="Calculator", icon_key="calculator",
            size=QSize(262, 277), resizable=False,
        )
        self.acc = 0.0
        self.pending_op: str | None = None
        self.fresh = True
        self.operator_just_pressed = False
        self.memory = 0.0
        self.has_memory = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.display = QLineEdit("0")
        self.display.setReadOnly(True)
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.display.setMaxLength(32)
        self.display.setFixedHeight(25)
        self.display.setFont(QFont("Tahoma", 12))
        self.display.setStyleSheet(
            "QLineEdit { background: white; color: black; border: 2px inset #808080; "
            "padding: 0 3px; selection-background-color: #316ac5; }"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setSpacing(6)
        layout.setMenuBar(self._build_menu())
        layout.addWidget(self.display)
        layout.addLayout(self._build_clear_row())
        layout.addLayout(self._build_keypad())
        self.set_content_layout(layout)

    def _build_menu(self):
        bar = QMenuBar()
        theme.style_menubar(bar)

        edit = bar.addMenu("&Edit")
        copy = QAction("&Copy", self)
        copy.setShortcut(QKeySequence.StandardKey.Copy)
        copy.triggered.connect(self.copy)
        edit.addAction(copy)
        paste = QAction("&Paste", self)
        paste.setShortcut(QKeySequence.StandardKey.Paste)
        paste.triggered.connect(self.paste)
        edit.addAction(paste)

        view = bar.addMenu("&View")
        modes = QActionGroup(self)
        modes.setExclusive(True)
        standard = QAction("&Standard", self, checkable=True, checked=True)
        scientific = QAction("&Scientific", self, checkable=True)
        scientific.setEnabled(False)
        modes.addAction(standard)
        modes.addAction(scientific)
        view.addActions((standard, scientific))
        view.addSeparator()
        grouping = QAction("Digit grouping", self, checkable=True)
        grouping.setEnabled(False)
        view.addAction(grouping)

        help_menu = bar.addMenu("&Help")
        help_menu.addAction("&Help Topics", self._show_help)
        help_menu.addSeparator()
        help_menu.addAction("&About Calculator", self._show_about)
        return bar

    def _build_clear_row(self):
        row = QHBoxLayout()
        row.setSpacing(6)

        self.memory_indicator = QLabel("")
        self.memory_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.memory_indicator.setFixedSize(32, 26)
        self.memory_indicator.setStyleSheet(
            "background: #ece9d8; color: #0000ff; border: 2px inset #808080; "
            "font: 11px 'Tahoma';"
        )
        row.addWidget(self.memory_indicator)
        row.addWidget(self._button("Backspace", self.backspace, "#ff0000", 57))
        row.addWidget(self._button("CE", self.clear_entry, "#ff0000", 57))
        row.addWidget(self._button("C", self.clear, "#ff0000", 58))
        return row

    def _build_keypad(self):
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        rows = [
            [("MC", self.memory_clear, "#ff0000"), ("7", lambda: self.digit("7"), "#0000ff"),
             ("8", lambda: self.digit("8"), "#0000ff"), ("9", lambda: self.digit("9"), "#0000ff"),
             ("/", lambda: self.op("/"), "#ff0000"), ("sqrt", self.square_root, "#0000ff")],
            [("MR", self.memory_recall, "#ff0000"), ("4", lambda: self.digit("4"), "#0000ff"),
             ("5", lambda: self.digit("5"), "#0000ff"), ("6", lambda: self.digit("6"), "#0000ff"),
             ("*", lambda: self.op("*"), "#ff0000"), ("%", self.percent, "#0000ff")],
            [("MS", self.memory_store, "#ff0000"), ("1", lambda: self.digit("1"), "#0000ff"),
             ("2", lambda: self.digit("2"), "#0000ff"), ("3", lambda: self.digit("3"), "#0000ff"),
             ("-", lambda: self.op("-"), "#ff0000"), ("1/x", self.reciprocal, "#0000ff")],
            [("M+", self.memory_add, "#ff0000"), ("0", lambda: self.digit("0"), "#0000ff"),
             ("+/-", self.negate, "#0000ff"), (".", self.decimal, "#0000ff"),
             ("+", lambda: self.op("+"), "#ff0000"), ("=", self.equals, "#ff0000")],
        ]
        for row_index, row in enumerate(rows):
            for column, (label, slot, color) in enumerate(row):
                grid.addWidget(self._button(label, slot, color, 32), row_index, column)
        return grid

    def _button(self, label, slot, color, width):
        button = QPushButton(label)
        button.setFixedSize(width, 26)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setStyleSheet(BUTTON_QSS + f"QPushButton {{ color: {color}; }}")
        button.clicked.connect(slot)
        return button

    def digit(self, digit):
        current = self.display.text()
        if self.fresh or current == "0" or not self._is_number(current):
            self.display.setText(digit)
        elif len(current) < 30:
            self.display.setText(current + digit)
        self.fresh = False
        self.operator_just_pressed = False

    def decimal(self):
        current = self.display.text()
        if self.fresh or not self._is_number(current):
            self.display.setText("0.")
            self.fresh = False
        elif "." not in current:
            self.display.setText(current + ".")
        self.operator_just_pressed = False

    def negate(self):
        value = self._value()
        if value is not None and value != 0:
            self._show_value(-value)
            self.fresh = False
            self.operator_just_pressed = False

    def clear(self):
        self.acc = 0.0
        self.pending_op = None
        self.display.setText("0")
        self.fresh = True
        self.operator_just_pressed = False

    def clear_entry(self):
        self.display.setText("0")
        self.fresh = True
        self.operator_just_pressed = False

    def backspace(self):
        if self.fresh:
            return
        current = self.display.text()
        if len(current) <= 1 or (len(current) == 2 and current.startswith("-")):
            self.display.setText("0")
            self.fresh = True
        else:
            self.display.setText(current[:-1])

    def op(self, symbol):
        if not self.operator_just_pressed:
            if not self._commit():
                return
        self.pending_op = symbol
        self.fresh = True
        self.operator_just_pressed = True

    def equals(self):
        if not self._commit():
            return
        self.pending_op = None
        self.fresh = True
        self.operator_just_pressed = False

    def square_root(self):
        value = self._value()
        if value is None:
            return
        if value < 0:
            self._show_error("Invalid input")
            return
        self._show_value(math.sqrt(value))
        self.fresh = True
        self.operator_just_pressed = False

    def reciprocal(self):
        value = self._value()
        if value is None:
            return
        if value == 0:
            self._show_error("Cannot divide by zero.")
            return
        self._show_value(1 / value)
        self.fresh = True
        self.operator_just_pressed = False

    def percent(self):
        value = self._value()
        if value is None:
            return
        if self.pending_op in ("+", "-"):
            value = self.acc * value / 100
        else:
            value /= 100
        self._show_value(value)
        self.fresh = True
        self.operator_just_pressed = False

    def memory_clear(self):
        self.memory = 0.0
        self.has_memory = False
        self.memory_indicator.clear()

    def memory_recall(self):
        self._show_value(self.memory)
        self.fresh = True
        self.operator_just_pressed = False

    def memory_store(self):
        value = self._value()
        if value is None:
            return
        self.memory = value
        self.has_memory = True
        self.memory_indicator.setText("M")
        self.fresh = True

    def memory_add(self):
        value = self._value()
        if value is None:
            return
        self.memory += value
        self.has_memory = True
        self.memory_indicator.setText("M")
        self.fresh = True

    def _commit(self):
        value = self._value()
        if value is None:
            return False
        if self.pending_op is None:
            result = value
        elif self.pending_op == "/" and value == 0:
            self._show_error("Cannot divide by zero.")
            return False
        else:
            result = OPS[self.pending_op](self.acc, value)
        self.acc = result
        self._show_value(result)
        return True

    def _value(self):
        try:
            return float(self.display.text())
        except ValueError:
            return None

    @staticmethod
    def _is_number(text):
        try:
            float(text)
            return True
        except ValueError:
            return False

    def _show_value(self, value):
        if not math.isfinite(value):
            self._show_error("Overflow")
            return
        if value == 0:
            value = 0.0
        self.display.setText(f"{value:.12g}")

    def _show_error(self, message):
        self.display.setText(message)
        self.acc = 0.0
        self.pending_op = None
        self.fresh = True
        self.operator_just_pressed = False

    def copy(self):
        QApplication.clipboard().setText(self.display.text())

    def paste(self):
        text = QApplication.clipboard().text().strip().replace(",", "")
        try:
            value = float(text)
        except ValueError:
            return
        self._show_value(value)
        self.fresh = True
        self.operator_just_pressed = False

    def _show_help(self):
        XPMessageBox.information(
            self, "Calculator Help",
            "Enter numbers with the keyboard or click the calculator buttons.\n\n"
            "Use Esc for C, Del for CE, and Backspace to remove a digit.",
        )

    def _show_about(self):
        XPMessageBox.information(
            self, "About Calculator",
            "Microsoft® Calculator\nWindows XP\n\nClassic Standard mode",
        )

    def keyPressEvent(self, event):
        text = event.text()
        if text.isdigit():
            self.digit(text)
        elif text in OPS:
            self.op(text)
        elif text == ".":
            self.decimal()
        elif text == "%":
            self.percent()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Equal):
            self.equals()
        elif event.key() == Qt.Key.Key_Escape:
            self.clear()
        elif event.key() == Qt.Key.Key_Delete:
            self.clear_entry()
        elif event.key() == Qt.Key.Key_Backspace:
            self.backspace()
        elif event.key() == Qt.Key.Key_F9:
            self.negate()
        else:
            super().keyPressEvent(event)
