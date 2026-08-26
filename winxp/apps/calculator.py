from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QGridLayout, QLineEdit, QPushButton, QVBoxLayout

from ..window_manager import XPWindow

OPS = {"+": lambda a, b: a + b, "-": lambda a, b: a - b,
       "*": lambda a, b: a * b, "/": lambda a, b: a / b if b != 0 else float("nan")}


class CalculatorWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Calculator", icon_key="calculator", size=QSize(230, 300), resizable=False)
        self.acc = 0.0
        self.pending_op = None
        self.fresh = True

        self.display = QLineEdit("0")
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setStyleSheet(
            "background: #c9e2b3; border: 2px inset #6a8a55; font-size: 20px; padding: 4px;"
        )
        self.display.setFixedHeight(34)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.display)
        layout.addLayout(self._build_grid())
        self.set_content_layout(layout)

    def _build_grid(self):
        grid = QGridLayout()
        grid.setSpacing(4)
        rows = [
            [("C", self.clear), ("CE", self.clear_entry), ("←", self.backspace), ("/", lambda: self.op("/"))],
            [("7", lambda: self.digit("7")), ("8", lambda: self.digit("8")), ("9", lambda: self.digit("9")), ("*", lambda: self.op("*"))],
            [("4", lambda: self.digit("4")), ("5", lambda: self.digit("5")), ("6", lambda: self.digit("6")), ("-", lambda: self.op("-"))],
            [("1", lambda: self.digit("1")), ("2", lambda: self.digit("2")), ("3", lambda: self.digit("3")), ("+", lambda: self.op("+"))],
            [("+/-", self.negate), ("0", lambda: self.digit("0")), (".", self.decimal), ("=", self.equals)],
        ]
        for r, row in enumerate(rows):
            for c, (label, slot) in enumerate(row):
                btn = QPushButton(label)
                btn.setFixedHeight(36)
                btn.clicked.connect(slot)
                grid.addWidget(btn, r, c)
        return grid

    def digit(self, d):
        cur = self.display.text()
        if self.fresh or cur == "0":
            self.display.setText(d)
            self.fresh = False
        else:
            self.display.setText(cur + d)

    def decimal(self):
        cur = self.display.text()
        if self.fresh:
            self.display.setText("0.")
            self.fresh = False
        elif "." not in cur:
            self.display.setText(cur + ".")

    def negate(self):
        cur = self.display.text()
        if cur.startswith("-"):
            self.display.setText(cur[1:])
        elif cur != "0":
            self.display.setText("-" + cur)

    def clear(self):
        self.acc = 0.0
        self.pending_op = None
        self.display.setText("0")
        self.fresh = True

    def clear_entry(self):
        self.display.setText("0")
        self.fresh = True

    def backspace(self):
        cur = self.display.text()
        if len(cur) <= 1 or (len(cur) == 2 and cur.startswith("-")):
            self.display.setText("0")
            self.fresh = True
        else:
            self.display.setText(cur[:-1])

    def op(self, symbol):
        self._commit()
        self.pending_op = symbol
        self.fresh = True

    def equals(self):
        self._commit()
        self.pending_op = None
        self.fresh = True

    def _commit(self):
        try:
            value = float(self.display.text())
        except ValueError:
            value = 0.0
        if self.pending_op is None:
            self.acc = value
        else:
            self.acc = OPS[self.pending_op](self.acc, value)
        text = f"{self.acc:.10g}"
        self.display.setText(text if text else "0")
