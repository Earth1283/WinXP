from __future__ import annotations

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from ...settings import WALLPAPERS, settings
from ...window_manager import XPWindow


class Preview(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(220, 150)
        self.wallpaper_name = settings.wallpaper

    def paintEvent(self, ev):
        p = QPainter(self)
        kind, c1, c2 = WALLPAPERS[self.wallpaper_name]
        r = self.rect().adjusted(10, 10, -10, -40)
        if kind == "solid":
            p.fillRect(r, QColor(c1))
        else:
            top, bot = QColor(c1), QColor(c2)
            for y in range(r.height()):
                t = y / max(1, r.height() - 1)
                c = QColor(
                    int(top.red() + (bot.red() - top.red()) * t),
                    int(top.green() + (bot.green() - top.green()) * t),
                    int(top.blue() + (bot.blue() - top.blue()) * t),
                )
                p.setPen(c)
                p.drawLine(r.left(), r.top() + y, r.right(), r.top() + y)
        monitor = self.rect().adjusted(0, 0, 0, -20)
        p.setPen(QColor("#444"))
        p.drawRect(monitor)
        p.fillRect(0, monitor.bottom(), self.width(), 20, QColor("#888"))


class DisplayWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Display Properties", icon_key="cp_display",
                          size=QSize(480, 360), resizable=False)

        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Desktop Background")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        root.addWidget(title)

        body = QHBoxLayout()
        self.preview = Preview()
        body.addWidget(self.preview)

        self.list = QListWidget()
        for name in WALLPAPERS:
            item = QListWidgetItem(name)
            self.list.addItem(item)
            if name == settings.wallpaper:
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
        self.preview.wallpaper_name = name
        self.preview.update()

    def _apply(self):
        settings.set_wallpaper(self.preview.wallpaper_name)

    def _apply_and_close(self):
        self._apply()
        self.close()
