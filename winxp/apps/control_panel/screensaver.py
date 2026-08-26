"""Screen Saver applet, plus the real idle-triggered fullscreen overlay.

Desktop installs an event filter and idle timer (see desktop.py) that
constructs ScreenSaverOverlay when nothing's touched the mouse/keyboard for
settings.screensaver_wait_minutes -- this isn't just a settings toggle, the
starfield actually kicks in.
"""
from __future__ import annotations

import random

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ...settings import SCREENSAVERS, settings
from ...window_manager import XPWindow

STAR_COUNT = 90


class Starfield(QWidget):
    def __init__(self, running=True):
        super().__init__()
        self.setStyleSheet("background: black;")
        self._stars = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        if running:
            self._timer.start(30)

    def start(self):
        self._timer.start(30)

    def stop(self):
        self._timer.stop()

    def _reset_star(self):
        return [0.0, random.uniform(0, 6.28), random.uniform(1.5, 4.0)]

    def _ensure_stars(self):
        while len(self._stars) < STAR_COUNT:
            self._stars.append(self._reset_star())

    def _tick(self):
        self._ensure_stars()
        cx, cy = self.width() / 2, self.height() / 2
        max_dist = (cx ** 2 + cy ** 2) ** 0.5
        for i, s in enumerate(self._stars):
            s[0] += s[2]
            if s[0] > max_dist:
                self._stars[i] = self._reset_star()
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("black"))
        cx, cy = self.width() / 2, self.height() / 2
        self._ensure_stars()
        p.setPen(Qt.PenStyle.NoPen)
        for dist, angle, speed in self._stars:
            x = cx + dist * (speed / 4.0) * _cos(angle)
            y = cy + dist * (speed / 4.0) * _sin(angle)
            size = min(4, 1 + dist / 120)
            brightness = min(255, int(120 + dist / 3))
            p.setBrush(QColor(brightness, brightness, 255))
            p.drawEllipse(int(x), int(y), int(size), int(size))


def _cos(a):
    import math
    return math.cos(a)


def _sin(a):
    import math
    return math.sin(a)


class ScreenSaverOverlay(QWidget):
    """Real fullscreen screensaver -- shown by Desktop after idle timeout,
    dismissed on any key press or mouse movement."""

    def __init__(self, on_dismiss):
        super().__init__(None, Qt.WindowType.FramelessWindowHint)
        self.on_dismiss = on_dismiss
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.field = Starfield(running=True)
        self.field.setMouseTracking(True)
        layout.addWidget(self.field)

        self._start_pos = None

    def show_fullscreen_on_primary(self):
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def keyPressEvent(self, ev):
        self._dismiss()

    def mousePressEvent(self, ev):
        self._dismiss()

    def mouseMoveEvent(self, ev):
        pos = ev.globalPosition().toPoint()
        if self._start_pos is None:
            self._start_pos = pos
            return
        if (pos - self._start_pos).manhattanLength() > 8:
            self._dismiss()

    def _dismiss(self):
        self.field.stop()
        self.close()
        self.on_dismiss()


class ScreenSaverWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Screen Saver Properties", icon_key="cp_screensaver",
                          size=QSize(400, 340), resizable=False)

        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.preview = Starfield(running=(settings.screensaver != "(None)"))
        self.preview.setFixedSize(370, 160)
        root.addWidget(self.preview)

        row = QHBoxLayout()
        row.addWidget(QLabel("Screen saver:"))
        self.combo = QComboBox()
        self.combo.addItems(SCREENSAVERS)
        self.combo.setCurrentText(settings.screensaver)
        self.combo.currentTextChanged.connect(self._on_saver_changed)
        row.addWidget(self.combo, 1)
        root.addLayout(row)

        wait_row = QHBoxLayout()
        wait_row.addWidget(QLabel("Wait:"))
        self.wait_spin = QSpinBox()
        self.wait_spin.setRange(1, 60)
        self.wait_spin.setValue(settings.screensaver_wait_minutes)
        wait_row.addWidget(self.wait_spin)
        wait_row.addWidget(QLabel("minutes before starting"))
        wait_row.addStretch(1)
        root.addLayout(wait_row)

        preview_btn = QPushButton("Preview Now")
        preview_btn.clicked.connect(self._preview_now)
        root.addWidget(preview_btn)

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

    def _on_saver_changed(self, name):
        if name == "(None)":
            self.preview.stop()
        else:
            self.preview.start()

    def _preview_now(self):
        overlay = ScreenSaverOverlay(lambda: None)
        overlay.show_fullscreen_on_primary()
        self._overlay_ref = overlay  # keep alive

    def _apply(self):
        settings.set_screensaver(self.combo.currentText())
        settings.set_screensaver_wait(self.wait_spin.value())

    def _apply_and_close(self):
        self._apply()
        self.close()
