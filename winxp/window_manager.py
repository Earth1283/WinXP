from __future__ import annotations

import random

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QIcon, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget,
)

from . import theme

EDGE = 6


class TitleButton(QPushButton):
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(21, 19)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        hovered = self.underMouse()
        pressed = self.isDown()
        if self.kind == "close":
            base = QColor("#e24b3c") if not pressed else QColor("#b8382b")
            top = QColor("#f9968a") if hovered else QColor("#ef7060")
        else:
            base = QColor("#3f7fe0") if not pressed else QColor("#2f5fb0")
            top = QColor("#8fb8f5") if hovered else QColor("#5f96e8")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base)
        p.drawRoundedRect(r, 3, 3)
        p.setBrush(top)
        p.drawRoundedRect(QRect(r.x() + 1, r.y() + 1, r.width() - 2, r.height() // 2), 2, 2)
        p.setPen(QColor("white"))
        f = p.font()
        f.setBold(True)
        f.setPixelSize(11)
        p.setFont(f)
        glyph = {"close": "✕", "min": "–", "max": "□"}[self.kind]
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, glyph)


class TitleBar(QWidget):
    doubleClicked = pyqtSignal()

    def __init__(self, window: "XPWindow"):
        super().__init__(window)
        self.window_ = window
        self.setFixedHeight(28)
        self.setAutoFillBackground(False)
        self._drag_pos = None
        self._glitch = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 3, 0)
        layout.setSpacing(4)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(window.windowTitle())
        self.title_label.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        self.btn_min = TitleButton("min")
        self.btn_max = TitleButton("max")
        self.btn_close = TitleButton("close")
        self.btn_min.clicked.connect(window.minimize)
        self.btn_max.clicked.connect(window.toggle_maximize)
        self.btn_close.clicked.connect(window.close)
        for b in (self.btn_min, self.btn_max, self.btn_close):
            layout.addWidget(b)

    def set_icon(self, icon: QIcon):
        self.icon_label.setPixmap(icon.pixmap(16, 16))

    def set_title(self, text):
        self.title_label.setText(text)

    def flash_glitch(self):
        """Cursed: csrss.exe is dead, titlebar rendering briefly corrupts."""
        self._glitch = True
        self.update()
        QTimer.singleShot(220, self._clear_glitch)

    def _clear_glitch(self):
        try:
            self._glitch = False
            self.update()
        except RuntimeError:
            pass  # window was closed before the timer fired

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height() + 6, 5, 5)
        p.setClipPath(path)
        if self._glitch:
            glitch_colors = ["#ff00ff", "#00ffff", "#000000", "#ffffff", "#ff2020"]
            for y in range(self.height()):
                c = QColor(random.choice(glitch_colors)) if random.random() < 0.55 else QColor("#3f8cf6")
                p.setPen(c)
                p.drawLine(0, y, self.width(), y)
            return
        active = self.window_.is_active
        grad_top = QColor("#0a58f2") if active else QColor("#8296b8")
        grad_mid = QColor("#3f8cf6") if active else QColor("#94a8c9")
        grad_bot = QColor("#0058e6") if active else QColor("#7f93b5")
        for y in range(self.height()):
            t = y / max(1, self.height() - 1)
            if t < 0.5:
                c = self._lerp(grad_top, grad_mid, t * 2)
            else:
                c = self._lerp(grad_mid, grad_bot, (t - 0.5) * 2)
            p.setPen(c)
            p.drawLine(0, y, self.width(), y)

    @staticmethod
    def _lerp(c1, c2, t):
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue() + (c2.blue() - c1.blue()) * t),
        )

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.window_.pos()
            self.window_.raise_and_activate()

    def mouseMoveEvent(self, ev):
        if self._drag_pos is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            if self.window_.is_maximized:
                return
            self.window_.move(ev.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, ev):
        self.window_.toggle_maximize()


class XPWindow(QWidget):
    closed = pyqtSignal(object)
    minimized = pyqtSignal(object)
    activated = pyqtSignal(object)
    titleChanged = pyqtSignal(object, str)

    def __init__(self, wm: "WindowManager", title="Window", icon_key="my_computer",
                 size=QSize(640, 460), resizable=True):
        super().__init__(None, Qt.WindowType.FramelessWindowHint)
        self.wm = wm
        self.resizable = resizable
        self.is_active = True
        self.is_maximized = False
        self._normal_geom = None
        self._resize_edge = None

        from . import icons
        self._icon = icons.icon(icon_key, 16)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.resize(size)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 12)
        outer.setSpacing(0)

        self._frame = QWidget()
        self._frame.setObjectName("frame")
        self._frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._frame.setStyleSheet(
            "#frame { background: %s; border: 1px solid #0047ba; "
            "border-top-left-radius: 7px; border-top-right-radius: 7px; }" % theme.XP_WINDOW_BG
        )
        outer.addWidget(self._frame)

        self._frozen = False
        self._apply_shadow()

        inner = QVBoxLayout(self._frame)
        inner.setContentsMargins(2, 2, 2, 2)
        inner.setSpacing(0)

        self.titlebar = TitleBar(self)
        self.titlebar.set_icon(self._icon)
        self.titlebar.set_title(title)
        inner.addWidget(self.titlebar)

        self.content = QWidget()
        self.content.setStyleSheet(f"background: {theme.XP_WINDOW_BG};")
        inner.addWidget(self.content, 1)

        self.setWindowTitle(title)
        self.setMouseTracking(True)
        self._frame.setMouseTracking(True)

    def set_content_layout(self, layout):
        self.content.setLayout(layout)

    def _apply_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 140))
        self._frame.setGraphicsEffect(shadow)

    def freeze(self, ms=4000):
        """Cursed: services.exe is dead, this window hangs like a real 'Not Responding' app."""
        if self._frozen:
            return
        self._frozen = True
        effect = QGraphicsOpacityEffect(self._frame)
        effect.setOpacity(0.55)
        self._frame.setGraphicsEffect(effect)
        self.setEnabled(False)
        orig = self.windowTitle()
        self.titlebar.set_title(orig + " (Not Responding)")

        def _restore():
            try:
                self._apply_shadow()
                self.setEnabled(True)
                self.titlebar.set_title(orig)
                self._frozen = False
            except RuntimeError:
                pass  # window was closed (e.g. by a crash/reboot) before the timer fired

        QTimer.singleShot(ms, _restore)

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, "titlebar"):
            self.titlebar.set_title(title)
        self.titleChanged.emit(self, title)

    def raise_and_activate(self):
        self.raise_()
        self.activateWindow()
        self.wm.set_active(self)

    def minimize(self):
        self.hide()
        self.minimized.emit(self)

    def toggle_maximize(self):
        if not self.resizable:
            return
        if self.is_maximized:
            if self._normal_geom:
                self.setGeometry(self._normal_geom)
            self.is_maximized = False
        else:
            self._normal_geom = self.geometry()
            avail = self.wm.desktop_rect()
            self.setGeometry(avail)
            self.is_maximized = True

    def closeEvent(self, ev):
        self.closed.emit(self)
        super().closeEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self.resizable:
            self._resize_edge = self._edge_at(ev.position().toPoint())
        self.raise_and_activate()

    def mouseMoveEvent(self, ev):
        if not self.resizable:
            return
        if ev.buttons() & Qt.MouseButton.LeftButton and self._resize_edge:
            self._do_resize(ev.globalPosition().toPoint())
        else:
            edge = self._edge_at(ev.position().toPoint())
            self.setCursor(self._cursor_for(edge))

    def mouseReleaseEvent(self, ev):
        self._resize_edge = None

    def _edge_at(self, pos):
        if self.is_maximized:
            return None
        r = self.rect()
        left = pos.x() <= EDGE
        right = pos.x() >= r.width() - EDGE
        top = pos.y() <= EDGE
        bottom = pos.y() >= r.height() - EDGE
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if top:
            return "t"
        if bottom:
            return "b"
        return None

    def _cursor_for(self, edge):
        return {
            None: Qt.CursorShape.ArrowCursor,
            "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
            "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
            "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
        }[edge]

    def _do_resize(self, global_pos):
        g = self.geometry()
        min_w, min_h = 200, 120
        e = self._resize_edge
        if "l" in e:
            new_left = min(global_pos.x(), g.right() - min_w)
            g.setLeft(new_left)
        if "r" in e:
            new_right = max(global_pos.x(), g.left() + min_w)
            g.setRight(new_right)
        if "t" in e:
            new_top = min(global_pos.y(), g.bottom() - min_h)
            g.setTop(new_top)
        if "b" in e:
            new_bottom = max(global_pos.y(), g.top() + min_h)
            g.setBottom(new_bottom)
        self.setGeometry(g)


class WindowManager:
    def __init__(self, desktop_widget_provider):
        self._desktop_widget_provider = desktop_widget_provider
        self.windows: list[XPWindow] = []
        self.active: XPWindow | None = None
        self.on_window_added = None
        self.on_window_removed = None
        self.on_window_state = None

    def desktop_rect(self) -> QRect:
        return self._desktop_widget_provider()

    def open(self, window: XPWindow, pos: QPoint | None = None):
        self.windows.append(window)
        if pos is None:
            n = len(self.windows) - 1
            avail = self.desktop_rect()
            x = avail.x() + 40 + (n % 6) * 28
            y = avail.y() + 30 + (n % 6) * 28
            window.move(x, y)
        else:
            window.move(pos)
        window.closed.connect(self._on_closed)
        window.minimized.connect(self._on_minimized)
        window.show()
        window.raise_and_activate()
        if self.on_window_added:
            self.on_window_added(window)

    def set_active(self, window):
        if self.active is window:
            return
        prev = self.active
        self.active = window
        if prev is not None:
            prev.is_active = False
            prev.titlebar.update()
        window.is_active = True
        window.titlebar.update()
        if self.on_window_state:
            self.on_window_state()

    def _on_closed(self, window):
        if window in self.windows:
            self.windows.remove(window)
        if self.active is window:
            self.active = None
        if self.on_window_removed:
            self.on_window_removed(window)

    def _on_minimized(self, window):
        if self.on_window_state:
            self.on_window_state()

    def restore(self, window):
        window.show()
        window.raise_and_activate()
        if self.on_window_state:
            self.on_window_state()
