from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QPushButton, QVBoxLayout,
)

from ... import icons
from ...app_registry import APPS
from ...settings import settings
from ...window_manager import XPWindow
from ...xp_dialog import XPMessageBox


class ProgramsWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Add or Remove Programs", icon_key="cp_programs",
                          size=QSize(440, 380), resizable=False)

        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("Currently installed programs:")
        title.setStyleSheet("font-weight: bold;")
        root.addWidget(title)

        self.list = QListWidget()
        self.list.setIconSize(icons.icon("text_file", 24).availableSizes()[0])
        for spec in APPS:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, spec.id)
            self.list.addItem(item)
        self._refresh_items()
        self.list.currentItemChanged.connect(self._update_button_label)
        root.addWidget(self.list, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.remove_btn = QPushButton("Change/Remove")
        self.remove_btn.clicked.connect(self._remove_selected)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        btn_row.addWidget(self.remove_btn)
        btn_row.addWidget(close)
        root.addLayout(btn_row)

        self.set_content_layout(root)
        self._pending_spec = None
        self._pending_install = False
        self._update_button_label()

    def _refresh_items(self):
        for i in range(self.list.count()):
            item = self.list.item(i)
            app_id = item.data(Qt.ItemDataRole.UserRole)
            spec = next((a for a in APPS if a.id == app_id), None)
            installed = settings.is_installed(app_id)
            item.setIcon(icons.icon(spec.icon, 24))
            suffix = "" if installed else "  (Not Installed)"
            item.setText(f"  {spec.title}{suffix}")

    def _update_button_label(self, *_):
        item = self.list.currentItem()
        if not item:
            self.remove_btn.setText("Change/Remove")
            return
        app_id = item.data(Qt.ItemDataRole.UserRole)
        self.remove_btn.setText("Install" if not settings.is_installed(app_id) else "Change/Remove")

    def _remove_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        app_id = item.data(Qt.ItemDataRole.UserRole)
        spec = next((a for a in APPS if a.id == app_id), None)
        if not spec:
            return

        install = not settings.is_installed(app_id)
        if install:
            verb, ing = "install", "Installing"
        else:
            if not XPMessageBox.confirm(
                self, "Confirm Uninstall",
                f"Are you sure you want to remove '{spec.title}' from your computer?",
                kind="warning",
            ):
                return
            verb, ing = "remove", "Removing"

        self._pending_spec = spec
        self._pending_install = install
        self.remove_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick_uninstall)
        self._tick_timer.start(60)

    def _tick_uninstall(self):
        self.progress.setValue(min(100, self.progress.value() + 7))
        if self.progress.value() >= 100:
            self._tick_timer.stop()
            self._finish_uninstall()

    def _finish_uninstall(self):
        spec = self._pending_spec
        install = self._pending_install
        self.progress.setVisible(False)
        self.remove_btn.setEnabled(True)

        if install:
            settings.set_app_installed(spec.id, True)
            self._refresh_items()
            self._update_button_label()
            XPMessageBox.information(
                self, "Add or Remove Programs",
                f"'{spec.title}' has been successfully installed.",
            )
            return

        # close any running instances of it
        for window in list(self.wm.windows):
            if getattr(window, "_app_key", None) == spec.id:
                window.close()

        if spec.id == "ie":
            # Internet Explorer is woven into the shell. Removing it takes
            # the shell with it -- the classic real-XP horror story, but real.
            from ..bsod import crash
            crash(self.wm, "iexplore.exe")
            return

        settings.set_app_installed(spec.id, False)
        self._refresh_items()
        self._update_button_label()
        XPMessageBox.information(
            self, "Add or Remove Programs",
            f"'{spec.title}' has been successfully removed from your computer.",
        )
