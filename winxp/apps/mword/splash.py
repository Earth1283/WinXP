"""Startup theatre and About.

Office 2003 opened with a flat blue panel, the product name in a very large
light weight, the licensee underneath, and a status line that scrolled through
things it claimed to be loading.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ... import theme
from ...xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame
from . import mw_icons

VERSION = "11.5604.5606"
BUILD = "MacroHard Office Word 2003 (11.5604.5606) SP3"

LOADING_LINES = [
    "Loading Normal.dot...",
    "Registering fonts...",
    "Starting the Office Assistant...",
    "Checking for a printer that isn't there...",
    "Rebuilding the AutoCorrect table...",
    "Repaginating in the background...",
    "Preparing the task pane nobody closes...",
]


class SplashScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self._line = 0
        self.resize(400, 232)

        self.status = QLabel("", self)
        self.status.setGeometry(18, 196, 364, 16)
        self.status.setStyleSheet("color: #dbe6f7; font-size: 10px; background: transparent;")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(230)

    def _advance(self):
        if self._line >= len(LOADING_LINES):
            self._timer.stop()
            self.accept()
            return
        self.status.setText(LOADING_LINES[self._line])
        self._line += 1

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor("#2b579a"))
        grad.setColorAt(1.0, QColor("#173a6d"))
        p.fillRect(self.rect(), grad)
        p.setPen(QPen(QColor("#0e2547"), 2))
        p.drawRect(self.rect().adjusted(1, 1, -1, -1))

        p.setPen(QColor("#c9d8ee"))
        p.setFont(QFont("Tahoma", 9))
        p.drawText(QRectF(20, 22, 360, 16), 0, "MacroHard® Office")

        font = QFont("Tahoma", 34)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("white"))
        p.drawText(QRectF(20, 40, 360, 58), 0, "Word 2003")

        p.setPen(QColor("#9fb8dc"))
        p.setFont(QFont("Tahoma", 8))
        p.drawText(QRectF(20, 106, 360, 14), 0,
                   "Professional Edition — Embarrassingly Overboard Edition")

        p.setPen(QPen(QColor("#4a76b8"), 1))
        p.drawLine(20, 130, 380, 130)
        p.setPen(QColor("#dbe6f7"))
        p.setFont(QFont("Tahoma", 8))
        p.drawText(QRectF(20, 138, 360, 14), 0, "MacroHard User")
        p.drawText(QRectF(20, 154, 360, 14), 0, "MacroHard Corporation")

        pm = mw_icons.pixmap("word_doc", 56)
        p.drawPixmap(322, 150, pm)
        p.end()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        inner = build_dialog_frame(self, "About MacroHard Office Word")
        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }}"
                           f"{DIALOG_BUTTON_QSS} QLabel {{ background: transparent; }}")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        row = QHBoxLayout()
        glyph = QLabel()
        glyph.setPixmap(mw_icons.pixmap("word_doc", 48))
        row.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        text = QLabel(
            f"<b>MacroHard® Office Word 2003</b><br>"
            f"{BUILD}<br><br>"
            "Copyright © 1983-2003 MacroHard Corporation. "
            "All rights reserved.<br><br>"
            "This product is licensed to:<br>"
            "&nbsp;&nbsp;MacroHard User<br>"
            "&nbsp;&nbsp;MacroHard Corporation<br><br>"
            "Product ID: 73931-640-0000106-57342<br><br>"
            "<i>Warning: This computer program is protected by copyright law "
            "and international treaties, and by a paperclip.</i>")
        text.setWordWrap(True)
        text.setMinimumWidth(320)
        row.addWidget(text, 1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for label, slot in (("System Info...", self._system_info),
                            ("Tech Support", self._tech_support),
                            ("Disabled Items...", self._disabled_items),
                            ("OK", self.accept)):
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setMinimumWidth(92)
            btn.clicked.connect(slot)
            buttons.addWidget(btn)
        layout.addLayout(buttons)
        inner.addWidget(body)
        self.setFixedWidth(470)

    def _system_info(self):
        XPMessageBox.information(
            self, "System Information",
            "OS Name: Microhard Windows XP Professional\n"
            "Version: 5.1.2600 Service Pack 3 Build 2600\n"
            "System Type: X86-based PC\n"
            "Total Physical Memory: 256.00 MB\n"
            "Available Physical Memory: 11.04 MB\n"
            "Page File Space: 620.00 MB")

    def _tech_support(self):
        XPMessageBox.information(
            self, "Technical Support",
            "For technical support, please consult the paperclip.")

    def _disabled_items(self):
        XPMessageBox.information(
            self, "Disabled Items",
            "The following items were disabled because they prevented Word "
            "from functioning correctly:\n\n"
            "  (none, yet)")
