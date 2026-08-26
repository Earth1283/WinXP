"""DIY Luna-styled message boxes — no native OS dialog chrome."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication, QDialog, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from . import icons, theme

_ICON_KEYS = {
    "warning": "msg_warning", "critical": "msg_error",
    "information": "msg_info", "question": "msg_question",
}


def _lerp(c1, c2, t):
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
    )


class DialogTitleBar(QWidget):
    def __init__(self, dialog, title):
        super().__init__(dialog)
        self.dialog = dialog
        self.setFixedHeight(26)
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 3, 0)
        layout.setSpacing(4)
        label = QLabel(title)
        label.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        layout.addWidget(label)
        layout.addStretch(1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 18)
        close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        close_btn.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                              stop:0 #ef7060, stop:1 #e24b3c);
                          border: 1px solid #7a1f14; border-radius: 3px;
                          color: white; font-weight: bold; }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                              stop:0 #f9968a, stop:1 #e24b3c); }
            QPushButton:pressed { background: #b8382b; }
        """)
        close_btn.clicked.connect(dialog.reject)
        layout.addWidget(close_btn)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height() + 6, 5, 5)
        p.setClipPath(path)
        top, mid, bot = QColor("#0a58f2"), QColor("#3f8cf6"), QColor("#0058e6")
        for y in range(self.height()):
            t = y / max(1, self.height() - 1)
            c = _lerp(top, mid, t * 2) if t < 0.5 else _lerp(mid, bot, (t - 0.5) * 2)
            p.setPen(c)
            p.drawLine(0, y, self.width(), y)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.dialog.pos()

    def mouseMoveEvent(self, ev):
        if self._drag_pos is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            self.dialog.move(ev.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None


DIALOG_BUTTON_QSS = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #ffffff, stop:0.5 #ece9d8, stop:1 #d6d2c2);
        border: 1px solid #716f64;
        border-radius: 3px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #fff7d6, stop:0.5 #ffe89a, stop:1 #ffce4d);
        border: 1px solid #cc9933;
    }
    QPushButton:pressed { background: #ffce4d; }
"""


def build_dialog_frame(dialog, title):
    """Sets up frameless, translucent Luna dialog chrome (rounded top corners,
    drop shadow, gradient titlebar with a close button) on any QDialog and
    returns the inner QVBoxLayout to add body content to — the DIY
    replacement for a native QDialog's OS-drawn window frame."""
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(10, 8, 10, 12)
    outer.setSpacing(0)

    frame = QWidget()
    frame.setObjectName("frame")
    frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    frame.setStyleSheet(
        "#frame { background: %s; border: 1px solid #0047ba; "
        "border-top-left-radius: 7px; border-top-right-radius: 7px; }" % theme.XP_WINDOW_BG
    )
    outer.addWidget(frame)

    shadow = QGraphicsDropShadowEffect(dialog)
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(0, 0, 0, 140))
    frame.setGraphicsEffect(shadow)

    inner = QVBoxLayout(frame)
    inner.setContentsMargins(2, 2, 2, 2)
    inner.setSpacing(0)
    inner.addWidget(DialogTitleBar(dialog, title))
    return inner


class XPMessageBox(QDialog):
    def __init__(self, parent, kind, title, text, buttons):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self._result_button = None

        inner = build_dialog_frame(self, title)

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(16, 16, 16, 12)
        body_l.setSpacing(16)

        row = QHBoxLayout()
        row.setSpacing(14)
        icon_key = _ICON_KEYS.get(kind)
        if icon_key:
            icon_label = QLabel()
            icon_label.setFixedSize(32, 32)
            icon_label.setPixmap(icons.icon(icon_key, 32).pixmap(32, 32))
            row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("background: transparent;")
        text_label.setMinimumWidth(230)
        row.addWidget(text_label, 1)
        body_l.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.setSpacing(6)
        for label in buttons:
            btn = QPushButton(label)
            btn.setMinimumWidth(75)
            btn.setFixedHeight(23)
            btn.clicked.connect(lambda _, l=label: self._choose(l))
            btn_row.addWidget(btn)
        body_l.addLayout(btn_row)

        inner.addWidget(body)
        self.setFixedWidth(370)

    def _choose(self, label):
        self._result_button = label
        self.accept()

    def result_button(self):
        return self._result_button

    @staticmethod
    def _show(parent, kind, title, text, buttons, default=None):
        box = XPMessageBox(parent, kind, title, text, buttons)
        box.adjustSize()
        anchor = parent.frameGeometry() if parent is not None else None
        if anchor is not None and parent.isVisible():
            center = anchor.center()
        else:
            center = QApplication.primaryScreen().geometry().center()
        box.move(center.x() - box.width() // 2, center.y() - box.height() // 2)
        if kind in ("critical", "warning"):
            from . import audio
            audio.sounds.play("error")
        box.exec()
        result = box.result_button()
        return result if result is not None else (default if default is not None else buttons[-1])

    @staticmethod
    def information(parent, title, text):
        XPMessageBox._show(parent, "information", title, text, ("OK",))

    @staticmethod
    def critical(parent, title, text):
        XPMessageBox._show(parent, "critical", title, text, ("OK",))

    @staticmethod
    def warning(parent, title, text):
        XPMessageBox._show(parent, "warning", title, text, ("OK",))

    @staticmethod
    def confirm(parent, title, text, kind="question", yes_label="Yes", no_label="No"):
        result = XPMessageBox._show(parent, kind, title, text, (yes_label, no_label), default=no_label)
        return result == yes_label
