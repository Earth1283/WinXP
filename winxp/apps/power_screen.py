from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class PowerScreen(QWidget):
    def __init__(self, action):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.action = action
        self.setStyleSheet("background: #0a2a6e;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = "Windows is shutting down..." if action == "shutdown" else "Logging off..."
        label = QLabel(text)
        label.setStyleSheet("color: white; font-size: 22px; font-family: Tahoma;")
        layout.addWidget(label)

    def show_fullscreen_on(self, wm):
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.show()
        self.raise_()
        if self.action == "shutdown":
            QTimer.singleShot(2200, QApplication.instance().quit)
        else:
            QTimer.singleShot(1800, lambda: self._finish_logoff(wm))

    def _finish_logoff(self, wm):
        for window in list(wm.windows):
            window.close()
        from ..corruption import health
        health.reset()
        self.close()
