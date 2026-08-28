from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QDialog, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPushButton, QVBoxLayout, QWidget,
)

from . import icons, theme
from . import vfs as vfs_mod
from .app_registry import APPS
from .settings import settings
from .xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame

TOP_PINNED_ID = "ie"


def _lerp(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
    )


def _paint_vgradient(p, rect, c1, c2):
    top, bot = QColor(c1), QColor(c2)
    for y in range(int(rect.height())):
        t = y / max(1, int(rect.height()) - 1)
        p.setPen(_lerp(top, bot, t))
        p.drawLine(int(rect.left()), int(rect.top()) + y, int(rect.right()), int(rect.top()) + y)


class StartMenuItem(QPushButton):
    """One clickable row: icon + label, with a live-themed Luna hover pill."""

    def __init__(self, text, icon_key, size=24, bold=False, dark=False,
                 trailing_arrow=False, parent=None):
        super().__init__(parent)
        self._icon_pix = icons.icon(icon_key, size).pixmap(size, size)
        self._size = size
        self._bold = bold
        self._dark = dark
        self._trailing_arrow = trailing_arrow
        self._hover = False
        self.setText(text)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(size + 8)
        self.setStyleSheet("QPushButton { border: none; background: transparent; text-align: left; }")

    def enterEvent(self, ev):
        self._hover = True
        self.update()

    def leaveEvent(self, ev):
        self._hover = False
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        if self._hover:
            scheme = theme.current_scheme()
            pill = QRectF(r.x() + 1, r.y() + 1, r.width() - 2, r.height() - 2)
            path = QPainterPath()
            path.addRoundedRect(pill, 3, 3)
            p.setClipPath(path)
            _paint_vgradient(p, pill, scheme["header_right"], scheme["header_left"])
            p.setClipping(False)
            p.setPen(QPen(QColor(scheme["header_left"]).darker(115), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(pill.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)

        icon_x = 8
        icon_y = (r.height() - self._size) // 2
        p.drawPixmap(icon_x, icon_y, self._icon_pix)

        text_x = icon_x + self._size + 8
        font = QFont(self.font())
        font.setBold(self._bold)
        font.setPixelSize(12)
        p.setFont(font)
        color = "white" if (self._hover or self._dark) else "black"
        p.setPen(QColor(color))
        text_rect = r.adjusted(text_x, 0, -18 if self._trailing_arrow else -4, 0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

        if self._trailing_arrow:
            ax = r.right() - 12
            ay = r.center().y()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("white" if self._hover else "#5a5a5a"))
            p.drawPolygon([
                QPoint(ax - 3, ay - 4), QPoint(ax + 3, ay), QPoint(ax - 3, ay + 4),
            ])


class PinnedTopItem(QWidget):
    """The browser's oversized top-of-menu slot: caption + bold title, big icon."""

    clicked = pyqtSignal()

    def __init__(self, caption, title, icon_key, parent=None):
        super().__init__(parent)
        self._icon_pix = icons.icon(icon_key, 32).pixmap(32, 32)
        self._caption = caption
        self._title = title
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)

    def enterEvent(self, ev):
        self._hover = True
        self.update()

    def leaveEvent(self, ev):
        self._hover = False
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        if self._hover:
            scheme = theme.current_scheme()
            pill = QRectF(r.x() + 1, r.y() + 1, r.width() - 2, r.height() - 2)
            path = QPainterPath()
            path.addRoundedRect(pill, 3, 3)
            p.setClipPath(path)
            _paint_vgradient(p, pill, scheme["header_right"], scheme["header_left"])
            p.setClipping(False)

        p.drawPixmap(8, (r.height() - 32) // 2, self._icon_pix)

        caption_color = QColor("white") if self._hover else QColor("#5f6a80")
        title_color = QColor("white") if self._hover else QColor("black")

        cap_font = QFont(self.font())
        cap_font.setPixelSize(10)
        p.setFont(cap_font)
        p.setPen(caption_color)
        p.drawText(QRectF(48, 5, r.width() - 56, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._caption)

        title_font = QFont(self.font())
        title_font.setBold(True)
        title_font.setPixelSize(13)
        p.setFont(title_font)
        p.setPen(title_color)
        p.drawText(QRectF(48, 20, r.width() - 56, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)


class MenuHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 12, 8)
        layout.setSpacing(10)

        self.avatar = QLabel()
        self.avatar.setFixedSize(42, 42)
        layout.addWidget(self.avatar)

        self.name = QLabel("Administrator")
        name_font = QFont(theme.FONT_FAMILY)
        name_font.setPixelSize(15)
        name_font.setBold(True)
        self.name.setFont(name_font)
        self.name.setStyleSheet("color: white; background: transparent;")
        shadow = QGraphicsDropShadowEffect(self.name)
        shadow.setBlurRadius(3)
        shadow.setOffset(1, 1)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.name.setGraphicsEffect(shadow)
        layout.addWidget(self.name)
        layout.addStretch(1)

        self._paint_avatar()

    def _paint_avatar(self):
        pm = self.avatar
        img = QPixmap(42, 42)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(0, 0, 42, 42)
        p.setPen(QPen(QColor("white"), 2))
        p.setBrush(QColor("#ffd35c"))
        p.drawRoundedRect(outer.adjusted(1, 1, -1, -1), 4, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e8a52a"))
        head = QRectF(14, 9, 14, 14)
        p.drawEllipse(head)
        body = QPainterPath()
        body.moveTo(9, 36)
        body.cubicTo(9, 24, 33, 24, 33, 36)
        p.drawPath(body)
        p.setPen(QPen(QColor(255, 255, 255, 90), 1))
        p.drawLine(3, 3, 39, 3)
        p.end()
        pm.setPixmap(img)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scheme = theme.current_scheme()
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 8, 8)
        path.addRect(QRectF(0, self.height() - 8, self.width(), 8))
        p.setClipPath(path.simplified())
        _paint_vgradient(p, QRectF(self.rect()), scheme["header_left"], scheme["header_right"])
        p.setClipping(False)
        super().paintEvent(ev)


class MenuFooter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)

    def paintEvent(self, ev):
        p = QPainter(self)
        scheme = theme.current_scheme()
        top = QColor(scheme["header_right"]).lighter(112)
        bot = QColor(scheme["header_left"])
        _paint_vgradient(p, QRectF(self.rect()), top, bot)
        p.setPen(QColor(bot).darker(120))
        p.drawLine(0, 0, self.width(), 0)


class RunDialog(QDialog):
    """A working Run box -- type an exe name (or app id) and it launches for real."""

    def __init__(self, parent, on_launch):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self._on_launch = on_launch
        inner = build_dialog_frame(self, "Run")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(16, 16, 16, 12)
        body_l.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(12)
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setPixmap(icons.icon("run", 32).pixmap(32, 32))
        row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        text = QLabel(
            "Type the name of a program, folder, document, or Internet "
            "resource, and Windows will open it for you."
        )
        text.setWordWrap(True)
        text.setStyleSheet("background: transparent;")
        text.setMinimumWidth(260)
        row.addWidget(text, 1)
        body_l.addLayout(row)

        field_row = QHBoxLayout()
        field_row.setSpacing(8)
        field_row.addWidget(QLabel("Open:"))
        self.field = QLineEdit()
        self.field.setStyleSheet(
            "QLineEdit { background: white; border: 1px solid #7f9db9; padding: 2px 4px; }"
        )
        self.field.returnPressed.connect(self._run)
        field_row.addWidget(self.field, 1)
        body_l.addLayout(field_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch(1)
        ok = QPushButton("OK")
        ok.setFixedWidth(75)
        ok.clicked.connect(self._run)
        cancel = QPushButton("Cancel")
        cancel.setFixedWidth(75)
        cancel.clicked.connect(self.reject)
        browse = QPushButton("Browse...")
        browse.setFixedWidth(85)
        browse.setEnabled(False)
        for b in (ok, cancel, browse):
            btn_row.addWidget(b)
        body_l.addLayout(btn_row)

        inner.addWidget(body)
        self.setFixedWidth(360)
        self.field.setFocus()

    def _run(self):
        query = self.field.text().strip()
        if not query:
            return
        key = query.lower().removesuffix(".exe")
        match = None
        for spec in APPS:
            if spec.id.lower() == key or spec.exe().lower().removesuffix(".exe") == key:
                match = spec
                break
        if match is None:
            self.accept()
            XPMessageBox.critical(
                self.parent(), "Run",
                f"Windows cannot find '{query}'. Make sure you typed the name "
                "correctly, and then try again.\n\nTo search for a file, click "
                "Start, and then click Search."
            )
            return
        self.accept()
        self._on_launch(f"app:{match.id}")


class StartMenu(QWidget):
    app_chosen = pyqtSignal(str)

    def __init__(self, parent_desktop):
        super().__init__(parent_desktop, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(400)
        self._build()

    def refresh_scheme(self):
        self.header.update()
        self.footer.update()

    def _rebuild_pinned(self):
        while self.pinned_l.count():
            item = self.pinned_l.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        while self.top_pinned_l.count():
            item = self.top_pinned_l.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        installed = [s for s in APPS if s.pinned and settings.is_installed(s.id)]
        top_spec = next((s for s in installed if s.id == TOP_PINNED_ID), None)
        rest = [s for s in installed if s is not top_spec]

        if top_spec is not None:
            top = PinnedTopItem("Internet", top_spec.title, top_spec.icon)
            top.clicked.connect(lambda a=top_spec.id: self._choose(a))
            self.top_pinned_l.addWidget(top)
            self.top_sep.show()
        else:
            self.top_sep.hide()

        for spec in rest:
            btn = StartMenuItem(spec.title, spec.icon, size=24)
            btn.clicked.connect(lambda _, a=spec.id: self._choose(a))
            self.pinned_l.addWidget(btn)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 12)
        root.setSpacing(0)

        frame = QWidget()
        frame.setObjectName("frame")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        frame.setStyleSheet(
            "#frame { background: white; border: 1px solid #0047ba; "
            "border-top-left-radius: 8px; border-top-right-radius: 8px; }"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 150))
        frame.setGraphicsEffect(shadow)
        root.addWidget(frame)

        frame_l = QVBoxLayout(frame)
        frame_l.setContentsMargins(1, 1, 1, 1)
        frame_l.setSpacing(0)

        self.header = MenuHeader()
        frame_l.addWidget(self.header)

        body = QWidget()
        body.setStyleSheet("background: white;")
        body_l = QHBoxLayout(body)
        body_l.setContentsMargins(0, 0, 0, 0)
        body_l.setSpacing(0)
        frame_l.addWidget(body)

        left = QWidget()
        left.setFixedWidth(240)
        left.setStyleSheet("background: white;")
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 6, 0, 6)
        left_l.setSpacing(0)

        self.top_pinned_l = QVBoxLayout()
        self.top_pinned_l.setContentsMargins(0, 0, 0, 2)
        self.top_pinned_l.setSpacing(0)
        left_l.addLayout(self.top_pinned_l)

        self.top_sep = self._separator()
        left_l.addWidget(self.top_sep)

        self.pinned_l = QVBoxLayout()
        self.pinned_l.setContentsMargins(0, 4, 0, 4)
        self.pinned_l.setSpacing(0)
        left_l.addLayout(self.pinned_l)

        self._rebuild_pinned()

        left_l.addStretch(1)
        left_l.addWidget(self._separator())

        allprog = StartMenuItem("All Programs", "allprograms", size=22, bold=True, trailing_arrow=True)
        allprog.setMinimumHeight(30)
        allprog.clicked.connect(lambda: self._show_all_programs(allprog))
        left_l.addWidget(allprog)

        body_l.addWidget(left)
        body_l.addWidget(self._vseparator())

        right = QWidget()
        right.setFixedWidth(160)
        right.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #e8eefb, stop:1 #cfdcf5);"
        )
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 6, 0, 6)
        right_l.setSpacing(0)

        def add_right(label, target, ic):
            btn = StartMenuItem(label, ic, size=20)
            btn.setMinimumHeight(24)
            btn.clicked.connect(lambda _, a=target: self._choose(a))
            right_l.addWidget(btn)

        add_right("My Documents", "explorer:mydocs", "my_documents")
        add_right("My Music", f"explorer:{vfs_mod.vfs.my_music_id}", "folder")
        add_right("My Computer", "explorer:root", "my_computer")

        network = StartMenuItem("My Network Places", "my_network", size=20)
        network.setMinimumHeight(24)
        network.clicked.connect(self._no_network_places)
        right_l.addWidget(network)

        right_l.addWidget(self._separator(margin=8))
        add_right("Control Panel", "control_panel", "control_panel")

        right_l.addWidget(self._separator(margin=8))
        help_btn = StartMenuItem("Help and Support", "msg_question", size=20)
        help_btn.setMinimumHeight(24)
        help_btn.clicked.connect(self._help_and_support)
        right_l.addWidget(help_btn)
        add_right("Search", "explorer:search", "shell_search")

        run_btn = StartMenuItem("Run...", "run", size=20)
        run_btn.setMinimumHeight(24)
        run_btn.clicked.connect(self._open_run)
        right_l.addWidget(run_btn)

        right_l.addStretch(1)
        body_l.addWidget(right)

        self.footer = MenuFooter()
        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(10, 6, 10, 6)
        fl.setSpacing(4)
        logoff = StartMenuItem("Log Off", "logoff", size=22, dark=True)
        shutdown = StartMenuItem("Turn Off Computer", "shutdown", size=22, dark=True)
        logoff.clicked.connect(lambda: self._choose("system:logoff"))
        shutdown.clicked.connect(lambda: self._choose("system:shutdown"))
        fl.addWidget(logoff)
        fl.addWidget(shutdown)
        frame_l.addWidget(self.footer)

    def _separator(self, margin=6):
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #cfd8e8;")
        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(margin, 3, margin, 3)
        wl.addWidget(sep)
        return wrapper

    def _vseparator(self):
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #b9c7e8;")
        return sep

    def _show_all_programs(self, anchor):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid #716f64; padding: 2px 0; }"
            "QMenu::item { padding: 4px 26px 4px 8px; }"
            "QMenu::item:selected { background: #2f71e6; color: white; }"
            "QMenu::separator { height: 1px; background: #d4d0c8; margin: 3px 4px; }"
        )
        seen_unpinned = False
        for spec in APPS:
            if not spec.all_programs or not settings.is_installed(spec.id):
                continue
            if not spec.pinned and not seen_unpinned:
                menu.addSeparator()
                seen_unpinned = True
            act = menu.addAction(icons.icon(spec.icon, 18), spec.title)
            act.triggered.connect(lambda _, a=spec.id: self._choose(a))
        pos = anchor.mapToGlobal(QPoint(anchor.width(), 0))
        menu.exec(pos)

    def _no_network_places(self):
        self.hide()
        XPMessageBox.critical(
            self.window(), "My Network Places",
            "Windows cannot find the network. The network may be temporarily "
            "unavailable, or the network components are not installed."
        )

    def _help_and_support(self):
        self.hide()
        XPMessageBox.information(
            self.window(), "Help and Support Center",
            "Help and Support Center cannot be started.\n\n"
            "A required service is not running."
        )

    def _open_run(self):
        self.hide()
        RunDialog(self.window(), self._choose).exec()

    def _choose(self, app_id):
        self.hide()
        self.app_chosen.emit(app_id)

    def show_above(self, anchor_widget):
        self._rebuild_pinned()
        self.adjustSize()
        pos = anchor_widget.mapToGlobal(QPoint(0, 0))
        self.move(pos.x() - 8, pos.y() - self.height() + 12)
        self.show()
