from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, QTime, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QMenu, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from . import icons, theme
from .settings import settings


class StartButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(94, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._flag = icons.icon("xp_flag", 18).pixmap(18, 18)
        self._path = self._build_path()

    def _build_path(self):
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        h = r.height()
        mid = r.left() + h / 2
        tail = 7.0

        cap = QPainterPath()
        cap.addEllipse(QRectF(r.left(), r.top(), h, h))

        body = QPainterPath()
        body.moveTo(mid, r.top())
        body.lineTo(r.right() - tail, r.top())
        body.lineTo(r.right(), r.top() + tail)
        body.lineTo(r.right(), r.bottom() - tail)
        body.lineTo(r.right() - tail, r.bottom())
        body.lineTo(mid, r.bottom())
        body.closeSubpath()

        return cap.united(body)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        pressed = self.isDown()
        scheme = theme.current_scheme()
        top = QColor(scheme["start_top"]) if not pressed else QColor(scheme["start_bot"]).darker(115)
        bot = QColor(scheme["start_bot"]) if not pressed else QColor(scheme["start_bot"]).darker(140)

        p.setClipPath(self._path)
        for y in range(r.height()):
            t = y / max(1, r.height() - 1)
            c = QColor(
                int(top.red() + (bot.red() - top.red()) * t),
                int(top.green() + (bot.green() - top.green()) * t),
                int(top.blue() + (bot.blue() - top.blue()) * t),
            )
            p.setPen(c)
            p.drawLine(0, y, r.width(), y)
        if not pressed:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 70))
            p.drawRect(0, 0, r.width(), int(r.height() * 0.42))
        p.setClipping(False)

        p.setPen(QColor(bot).darker(150))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(self._path)

        p.drawPixmap(9, (r.height() - 18) // 2 + 1, self._flag)
        f = p.font()
        f.setBold(True)
        f.setItalic(True)
        f.setPixelSize(15)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(r.adjusted(30, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter, "start")


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


class VolumePopup(QWidget):
    def __init__(self, anchor):
        super().__init__(anchor.window(), Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setFixedSize(64, 150)
        self.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; border: 1px solid #716f64;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(4)

        label = QLabel("Volume")
        label.setStyleSheet("background: transparent; font-size: 11px;")
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setRange(0, 100)
        self.slider.setValue(settings.volume)
        self.slider.valueChanged.connect(settings.set_volume)
        layout.addWidget(self.slider, 1, Qt.AlignmentFlag.AlignHCenter)

        self.mute_check = QCheckBox("Mute")
        self.mute_check.setStyleSheet("background: transparent; font-size: 10px;")
        self.mute_check.setChecked(settings.muted)
        self.mute_check.toggled.connect(settings.set_muted)
        layout.addWidget(self.mute_check, 0, Qt.AlignmentFlag.AlignHCenter)


class SpeakerButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 20)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(16, 16))
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")
        self._popup = None
        self.clicked.connect(self._toggle_popup)
        settings.volume_changed.connect(self._refresh_icon)
        self._refresh_icon()

    def _refresh_icon(self):
        key = "volume_mute" if settings.muted or settings.volume == 0 else "volume"
        self.setIcon(icons.icon(key, 16))

    def _toggle_popup(self):
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._popup = VolumePopup(self)
        pos = self.mapToGlobal(QPoint(self.width() - self._popup.width(), -self._popup.height()))
        self._popup.move(pos)
        self._popup.show()


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


class Groove(QWidget):
    """A carved-in divider line -- dark edge then a light highlight, the way
    Luna separates the Start button/tray from the rest of the taskbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(3)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setPen(QColor("#0a1f5c"))
        p.drawLine(0, 2, 0, self.height() - 2)
        p.setPen(QColor("#4a7fd6"))
        p.drawLine(1, 2, 1, self.height() - 2)


class TrayBox(QWidget):
    """System tray well with a hand-painted sunken (inset) bevel."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paintEvent(self, ev):
        p = QPainter(self)
        r = self.rect().adjusted(0, 3, 0, -3)
        p.fillRect(r, QColor("#123a8f"))
        p.setPen(QColor("#0a1f5c"))
        p.drawLine(r.left(), r.top(), r.right(), r.top())
        p.drawLine(r.left(), r.top(), r.left(), r.bottom())
        p.setPen(QColor("#5a8fe0"))
        p.drawLine(r.left(), r.bottom(), r.right(), r.bottom())
        p.drawLine(r.right(), r.top(), r.right(), r.bottom())


class Taskbar(QWidget):
    start_clicked = pyqtSignal()
    task_clicked = pyqtSignal(object)
    task_manager_requested = pyqtSignal()

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

        layout.addWidget(Groove())

        self.task_area = QWidget()
        self.task_layout = QHBoxLayout(self.task_area)
        self.task_layout.setContentsMargins(2, 0, 2, 0)
        self.task_layout.setSpacing(3)
        self.task_layout.addStretch(1)
        layout.addWidget(self.task_area, 1)

        layout.addWidget(Groove())

        tray = TrayBox()
        tray_l = QHBoxLayout(tray)
        tray_l.setContentsMargins(6, 3, 6, 3)
        self.speaker = SpeakerButton()
        tray_l.addWidget(self.speaker)
        self.clock = Clock()
        tray_l.addWidget(self.clock)
        layout.addWidget(tray)

    def paintEvent(self, ev):
        p = QPainter(self)
        scheme = theme.current_scheme()
        top = QColor(scheme["taskbar_top"])
        bot = QColor(scheme["taskbar_bot"])
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

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            act = menu.addAction("Task Manager")
            act.triggered.connect(self.task_manager_requested.emit)
            menu.exec(ev.globalPosition().toPoint())
        else:
            super().mousePressEvent(ev)
