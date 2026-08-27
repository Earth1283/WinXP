"""Startup theatre: the splash screen, the serial-number gate, and About.

The splash is modelled on the real 7.0 one -- artwork, version, and a credits
scroll of names nobody reads -- with a cursed Mona Lisa standing in for the
feather.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from ... import theme
from ...xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets")
MONA_LISA_PATH = os.path.join(ASSETS_DIR, "MonaLisa.jpg")

LOADING_LINES = [
    "Initializing plug-ins...",
    "Reading brush presets...",
    "Loading Scripting Support...",
    "Reading fonts (2,417 of 41)...",
    "Initializing scratch disk...",
    "Compressing serial number...",
    "Indexing filters nobody uses...",
    "Optimizing regret...",
    "Preparing disappointment...",
    "Almost there...",
]

CREDITS = (
    "Adobo PhotoChop 7.0    "
    "Engineering: a man who left in 1998 · a contractor · the intern who wrote the "
    "gradient tool · Quality Assurance: nobody · Special thanks: the scratch disk, "
    "for holding on · In memory of: your unsaved work    "
)


class SplashScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self._line_index = 0
        self._credit_offset = 0

        w, h = 420, 300
        self.resize(w, h)

        self.bg_label = QLabel(self)
        self.bg_label.setGeometry(0, 0, w, h)
        image = QImage(MONA_LISA_PATH)
        if not image.isNull():
            pm = QPixmap.fromImage(image).scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            self.bg_label.setPixmap(pm)

        veil = QLabel(self)
        veil.setGeometry(0, 0, w, h)
        veil.setStyleSheet("background: rgba(10, 20, 40, 90);")

        title = QLabel("PhotoChop", self)
        title.setGeometry(0, 26, w, 46)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-weight: bold; font-size: 34px;"
                            "background: transparent; letter-spacing: 2px;")

        version = QLabel("7.0", self)
        version.setGeometry(0, 70, w, 30)
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("color: #ffd88a; font-size: 22px; background: transparent;")

        edition = QLabel("Professional", self)
        edition.setGeometry(0, 98, w, 20)
        edition.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edition.setStyleSheet("color: #dfe8f5; font-size: 12px; background: transparent;"
                              "letter-spacing: 6px;")

        legal = QLabel("© 1990-2002 Adobo Systems Incorporated. All rights reserved.\n"
                       "Adobo and PhotoChop are trademarks that would not survive review.",
                       self)
        legal.setGeometry(12, h - 74, w - 24, 30)
        legal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        legal.setStyleSheet("color: #c8d4e4; font-size: 9px; background: transparent;")

        self.credits = QLabel(CREDITS, self)
        self.credits.setGeometry(12, h - 44, w - 24, 14)
        self.credits.setStyleSheet("color: #9fb4cf; font-size: 9px; background: transparent;")

        self.status = QLabel(LOADING_LINES[0], self)
        self.status.setGeometry(0, h - 26, w, 22)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(
            "color: white; font-size: 10px; background: rgba(0,0,0,150); padding: 3px;")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_line)
        self._timer.start(260)

        self._scroll = QTimer(self)
        self._scroll.timeout.connect(self._scroll_credits)
        self._scroll.start(60)

        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.accept)
        self._close_timer.start(2600)

    def _next_line(self):
        self._line_index = (self._line_index + 1) % len(LOADING_LINES)
        self.status.setText(LOADING_LINES[self._line_index])

    def _scroll_credits(self):
        self._credit_offset = (self._credit_offset + 1) % len(CREDITS)
        text = CREDITS[self._credit_offset:] + CREDITS[:self._credit_offset]
        self.credits.setText(text)

    def mousePressEvent(self, ev):
        self.accept()


class SerialActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.accepted_activation = False

        inner = build_dialog_frame(self, "PhotoChop 7.0 - Product Activation")
        body = QWidget()
        body.setStyleSheet(
            f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        msg = QLabel(
            "Thank you for choosing PhotoChop 7.0 Professional.\n"
            "Please enter the serial number found on the back of the CD sleeve, "
            "which you have already thrown away.")
        msg.setWordWrap(True)
        msg.setStyleSheet("background: transparent;")
        root.addWidget(msg)

        self.serial_edit = QLineEdit()
        self.serial_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        root.addWidget(self.serial_edit)

        note = QLabel("PhotoChop will validate this serial number against nothing.")
        note.setStyleSheet("background: transparent; color: #666; font-size: 10px;")
        root.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        activate = QPushButton("Activate")
        activate.clicked.connect(self._activate)
        later = QPushButton("Activate Later")
        later.clicked.connect(self._later)
        btn_row.addWidget(activate)
        btn_row.addWidget(later)
        root.addLayout(btn_row)

        inner.addWidget(body)
        self.setFixedWidth(400)
        self.serial_edit.setFocus()

    def _activate(self):
        if not self.serial_edit.text().strip():
            XPMessageBox.warning(self, "PhotoChop",
                                 "Please enter a serial number. Any will do.")
            return
        self.accepted_activation = True
        XPMessageBox.information(
            self, "PhotoChop",
            "Congratulations! Your installation of PhotoChop is now genuine(-ish).")
        self.accept()

    def _later(self):
        XPMessageBox.information(
            self, "PhotoChop",
            "PhotoChop will remind you again never, because we forgot to wire that up.")
        self.accept()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        inner = build_dialog_frame(self, "About PhotoChop")

        body = QWidget()
        body.setStyleSheet(
            f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(14, 16, 14, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(12)
        pic = QLabel()
        pic.setPixmap(QPixmap(MONA_LISA_PATH).scaled(
            84, 112, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        pic.setStyleSheet("border: 1px solid #555; background: transparent;")
        top.addWidget(pic, 0, Qt.AlignmentFlag.AlignTop)

        text = QLabel(
            "Adobo PhotoChop 7.0 Professional\n\n"
            "Serial number: 1045-1234-5678-9012-3456-7890\n"
            "Licensed to: whoever is sitting here\n\n"
            "Not affiliated with any photo editing software, real or imagined.\n\n"
            "Your activation is genuine(-ish).")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignTop)
        text.setStyleSheet("background: transparent;")
        top.addWidget(text, 1)
        root.addLayout(top)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok = QPushButton("OK")
        ok.setMinimumWidth(75)
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        root.addLayout(btn_row)

        inner.addWidget(body)
        self.setFixedWidth(400)
