from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTime, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from . import icons


class StartButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(94, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(icons.icon("shutdown", 20))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        pressed = self.isDown()
        top = QColor("#8fe36a") if not pressed else QColor("#3c8c25")
        bot = QColor("#1a6e0a") if not pressed else QColor("#0f4d06")
        for y in range(r.height()):
            t = y / max(1, r.height() - 1)
            c = QColor(
                int(top.red() + (bot.red() - top.red()) * t),
                int(top.green() + (bot.green() - top.green()) * t),
                int(top.blue() + (bot.blue() - top.blue()) * t),
            )
            p.setPen(c)
            p.drawLine(r.left(), r.top() + y, r.right(), r.top() + y)
        p.setPen(Qt.PenStyle.NoPen)
        f = p.font()
        f.setBold(True)
        f.setItalic(True)
        f.setPixelSize(15)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(r.adjusted(28, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, "start")


class TaskButton(QPushButton):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.setCheckable(True)
        self.setFixedHeight(26)
        self.setMinimumWidth(140)
        self.setMaximumWidth(200)
        self.setIcon(window._icon)
        self.setIconSize(QSize(16, 16))
        self.setText(self._elide(window.windowTitle()))
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 6px;
                color: white;
                border: 1px solid #1941b8;
                border-radius: 3px;
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #4a86e8, stop:1 #2f5fc9);
            }
            QPushButton:checked {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #123a8f, stop:1 #1c4bc9);
                border: 1px solid #0a1f5c;
            }
        """)

    def _elide(self, text):
        return text if len(text) <= 22 else text[:19] + "..."

    def refresh_title(self, text):
        self.setText(self._elide(text))


class Clock(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("color: white; font-weight: bold; padding: 0 10px;")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self):
        self.setText(QTime.currentTime().toString("h:mm AP"))


class Taskbar(QWidget):
    start_clicked = pyqtSignal()
    task_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self._buttons: dict[object, TaskButton] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 4, 2)
        layout.setSpacing(4)

        self.start_btn = StartButton()
        self.start_btn.clicked.connect(self.start_clicked.emit)
        layout.addWidget(self.start_btn)

        sep = QLabel()
        sep.setFixedWidth(2)
        sep.setStyleSheet("background: #123a8f;")
        layout.addWidget(sep)

        self.task_area = QWidget()
        self.task_layout = QHBoxLayout(self.task_area)
        self.task_layout.setContentsMargins(2, 0, 2, 0)
        self.task_layout.setSpacing(3)
        self.task_layout.addStretch(1)
        layout.addWidget(self.task_area, 1)

        tray = QWidget()
        tray.setStyleSheet("background: #123a8f; border: 1px inset #0a1f5c; border-radius: 2px;")
        tray_l = QHBoxLayout(tray)
        tray_l.setContentsMargins(4, 0, 4, 0)
        self.clock = Clock()
        tray_l.addWidget(self.clock)
        layout.addWidget(tray)

    def paintEvent(self, ev):
        p = QPainter(self)
        top = QColor("#3f8cf3")
        bot = QColor("#1941b8")
        for y in range(self.height()):
            t = y / max(1, self.height() - 1)
            c = QColor(
                int(top.red() + (bot.red() - top.red()) * t),
                int(top.green() + (bot.green() - top.green()) * t),
                int(top.blue() + (bot.blue() - top.blue()) * t),
            )
            p.setPen(c)
            p.drawLine(0, y, self.width(), y)
        p.setPen(QColor("#7fb3ff"))
        p.drawLine(0, 0, self.width(), 0)

    def add_window(self, window):
        btn = TaskButton(window)
        btn.clicked.connect(lambda: self.task_clicked.emit(window))
        window.titleChanged.connect(lambda w, t: btn.refresh_title(t))
        self._buttons[window] = btn
        self.task_layout.insertWidget(self.task_layout.count() - 1, btn)
        self.set_checked(window)

    def remove_window(self, window):
        btn = self._buttons.pop(window, None)
        if btn:
            self.task_layout.removeWidget(btn)
            btn.deleteLater()

    def set_checked(self, window):
        for w, b in self._buttons.items():
            b.setChecked(w is window and w.isVisible())
