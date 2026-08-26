"""Classic XP-style boot screen -- black background, centered wordmark,
animated segmented progress bar. Shown once at startup before the desktop
appears, same fixed-timer pattern as PowerScreen's shutdown/logoff screens."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

DURATION_MS = 2800
SEGMENT_COUNT = 3
SEGMENT_WIDTH = 34
TRACK_WIDTH = 160
TRACK_HEIGHT = 14


class _ProgressBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(TRACK_WIDTH, TRACK_HEIGHT)
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        self._offset = (self._offset + 4) % (TRACK_WIDTH + SEGMENT_WIDTH * SEGMENT_COUNT)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, 0, self.width(), self.height())
        p.setPen(QColor("#3355aa"))
        p.setBrush(QColor("#000814"))
        p.drawRoundedRect(track, 3, 3)
        p.setClipRect(track.adjusted(1, 1, -1, -1))

        gap = 6
        x = -SEGMENT_COUNT * (SEGMENT_WIDTH + gap) + self._offset
        p.setPen(Qt.PenStyle.NoPen)
        while x < self.width():
            grad = QLinearGradient(x, 0, x + SEGMENT_WIDTH, 0)
            grad.setColorAt(0, QColor("#1c4fd1"))
            grad.setColorAt(0.5, QColor("#8fb8ff"))
            grad.setColorAt(1, QColor("#1c4fd1"))
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(x, 2, SEGMENT_WIDTH, self.height() - 4), 2, 2)
            x += SEGMENT_WIDTH + gap


class BootScreen(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background: black;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(28)

        title = QLabel("Windows XP")
        title.setStyleSheet("color: white; background: transparent;")
        font = QFont("Tahoma", 30)
        font.setBold(True)
        font.setItalic(True)
        title.setFont(font)
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)

        self.bar = _ProgressBar()
        layout.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignHCenter)

    def show_fullscreen(self, on_done):
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.show()
        self.raise_()
        QTimer.singleShot(DURATION_MS, on_done)
