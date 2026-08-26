from __future__ import annotations

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget

from . import icons
from .app_registry import APPS


class StartMenuItem(QPushButton):
    def __init__(self, text, icon_key, size=24, bold=False, parent=None):
        super().__init__(parent)
        self.setText("  " + text)
        self.setIcon(icons.icon(icon_key, size))
        self.setIconSize(QSize(size, size))
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        weight = "bold" if bold else "normal"
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 4px 8px;
                border: none;
                background: transparent;
                font-weight: {weight};
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: #2f71e6;
                color: white;
                border-radius: 2px;
            }}
        """)
        self.setMinimumHeight(size + 10)


class StartMenu(QWidget):
    app_chosen = pyqtSignal(str)

    def __init__(self, parent_desktop):
        super().__init__(parent_desktop, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setFixedSize(380, 480)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1657d6, stop:1 #3f8cf6); border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 8, 10, 8)
        avatar = QLabel()
        avatar.setFixedSize(40, 40)
        avatar.setStyleSheet("background: #ffd35c; border: 2px solid white; border-radius: 4px;")
        hl.addWidget(avatar)
        name = QLabel("Administrator")
        name.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background: transparent;")
        hl.addWidget(name)
        hl.addStretch(1)
        root.addWidget(header)

        body = QWidget()
        body.setStyleSheet("background: white;")
        body_l = QHBoxLayout(body)
        body_l.setContentsMargins(0, 0, 0, 0)
        body_l.setSpacing(0)
        root.addWidget(body, 1)

        left = QWidget()
        left.setStyleSheet("background: white;")
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(6, 8, 6, 8)
        left_l.setSpacing(2)

        for spec in APPS:
            if not spec.pinned:
                continue
            btn = StartMenuItem(spec.title, spec.icon, size=28)
            btn.clicked.connect(lambda _, a=spec.id: self._choose(a))
            left_l.addWidget(btn)

        left_l.addStretch(1)
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #cfd8e8;")
        left_l.addWidget(sep)

        allprog = StartMenuItem("All Programs", "control_panel", size=20, bold=True)
        allprog.clicked.connect(lambda: self._show_all_programs(allprog))
        left_l.addWidget(allprog)

        body_l.addWidget(left, 1)

        right = QWidget()
        right.setFixedWidth(150)
        right.setStyleSheet("background: #d7e2f7;")
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(6, 8, 6, 8)
        right_l.setSpacing(2)

        entries = [
            ("My Documents", "explorer:mydocs", "my_documents"),
            ("My Computer", "explorer:root", "my_computer"),
            ("Recycle Bin", "explorer:recycle", "recycle_bin"),
            ("Control Panel", "control_panel", "control_panel"),
        ]
        for label, app_id, ic in entries:
            btn = StartMenuItem(label, ic, size=22)
            btn.clicked.connect(lambda _, a=app_id: self._choose(a))
            right_l.addWidget(btn)
        right_l.addStretch(1)
        body_l.addWidget(right)

        footer = QWidget()
        footer.setFixedHeight(44)
        footer.setStyleSheet("background: #d7e2f7; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(8, 6, 8, 6)
        logoff = StartMenuItem("Log Off", "logoff", size=22)
        shutdown = StartMenuItem("Turn Off Computer", "shutdown", size=22)
        logoff.clicked.connect(lambda: self._choose("system:logoff"))
        shutdown.clicked.connect(lambda: self._choose("system:shutdown"))
        fl.addWidget(logoff)
        fl.addWidget(shutdown)
        root.addWidget(footer)

    def _show_all_programs(self, anchor):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid #716f64; }"
            "QMenu::item { padding: 4px 24px 4px 12px; }"
            "QMenu::item:selected { background: #2f71e6; color: white; }"
        )
        seen_unpinned = False
        for spec in APPS:
            if not spec.all_programs:
                continue
            if not spec.pinned and not seen_unpinned:
                menu.addSeparator()
                seen_unpinned = True
            act = menu.addAction(icons.icon(spec.icon, 18), spec.title)
            act.triggered.connect(lambda _, a=spec.id: self._choose(a))
        pos = anchor.mapToGlobal(QPoint(anchor.width(), 0))
        menu.exec(pos)

    def _choose(self, app_id):
        self.hide()
        self.app_chosen.emit(app_id)

    def show_above(self, anchor_widget):
        pos = anchor_widget.mapToGlobal(QPoint(0, 0))
        self.move(pos.x(), pos.y() - self.height())
        self.show()
