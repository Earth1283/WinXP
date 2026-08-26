from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from ... import theme
from ...settings import settings
from ...window_manager import XPWindow


class SchemePreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(220, 130)
        self.scheme_name = theme.current_scheme_name()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scheme = theme.SCHEMES[self.scheme_name]
        r = self.rect().adjusted(4, 4, -4, -4)
        p.setPen(QColor("#444"))
        p.setBrush(QColor("#ece9d8"))
        p.drawRect(r)

        title_r = QRectF(r.left(), r.top(), r.width(), 22)
        top, mid, bot = QColor(scheme["title_top"]), QColor(scheme["title_mid"]), QColor(scheme["title_bot"])
        for y in range(int(title_r.height())):
            t = y / max(1, title_r.height() - 1)
            c = self._lerp(top, mid, t * 2) if t < 0.5 else self._lerp(mid, bot, (t - 0.5) * 2)
            p.setPen(c)
            p.drawLine(int(title_r.left()), int(title_r.top() + y), int(title_r.right()), int(title_r.top() + y))
        p.setPen(QColor("white"))
        p.drawText(title_r.adjusted(6, 0, 0, 0).toRect(),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Active Window")

        taskbar_r = QRectF(r.left(), r.bottom() - 18, r.width(), 18)
        tt, tb = QColor(scheme["taskbar_top"]), QColor(scheme["taskbar_bot"])
        for y in range(int(taskbar_r.height())):
            t = y / max(1, taskbar_r.height() - 1)
            c = self._lerp(tt, tb, t)
            p.setPen(c)
            p.drawLine(int(taskbar_r.left()), int(taskbar_r.top() + y), int(taskbar_r.right()), int(taskbar_r.top() + y))
        p.setPen(QColor(scheme["start_bot"]))
        p.setBrush(QColor(scheme["start_top"]))
        p.drawRoundedRect(QRectF(taskbar_r.left() + 3, taskbar_r.top() + 2, 44, 14), 3, 3)

    @staticmethod
    def _lerp(c1, c2, t):
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue() + (c2.blue() - c1.blue()) * t),
        )


class AppearanceWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Display Properties", icon_key="cp_appearance",
                          size=QSize(420, 340), resizable=False)

        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Windows and Buttons")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        root.addWidget(title)

        body = QHBoxLayout()
        self.preview = SchemePreview()
        body.addWidget(self.preview)

        self.list = QListWidget()
        for name in theme.SCHEMES:
            item = QListWidgetItem(name)
            self.list.addItem(item)
            if name == theme.current_scheme_name():
                self.list.setCurrentItem(item)
        self.list.currentTextChanged.connect(self._on_select)
        body.addWidget(self.list, 1)
        root.addLayout(body)

        root.addStretch(1)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok = QPushButton("OK")
        apply_btn = QPushButton("Apply")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self._apply_and_close)
        apply_btn.clicked.connect(self._apply)
        cancel.clicked.connect(self.close)
        btn_row.addWidget(ok)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(cancel)
        root.addLayout(btn_row)

        self.set_content_layout(root)

    def _on_select(self, name):
        self.preview.scheme_name = name
        self.preview.update()

    def _apply(self):
        settings.set_scheme(self.preview.scheme_name)

    def _apply_and_close(self):
        self._apply()
        self.close()
