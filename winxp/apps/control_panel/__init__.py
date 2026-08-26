"""Control Panel -- an icon-grid launcher, real XP layout. Double-click an
applet to open its own window. Each applet is its own module in this
package; add a new one by dropping a file here and adding a row to APPLETS.
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout

from ... import icons
from ...window_manager import XPWindow

APPLETS = [
    ("display", "DisplayWindow", "cp_display", "Display",
     "Change your desktop background"),
    ("appearance", "AppearanceWindow", "cp_appearance", "Appearance",
     "Change the color scheme of windows and buttons"),
    ("sounds", "SoundsWindow", "volume", "Sounds and Audio Devices",
     "Change sound scheme and volume"),
    ("programs", "ProgramsWindow", "cp_programs", "Add or Remove Programs",
     "Install or remove programs"),
    ("screensaver", "ScreenSaverWindow", "cp_screensaver", "Screen Saver",
     "Change your screen saver"),
    ("system", "SystemWindow", "cp_system", "System",
     "View system information"),
    ("folder_options", "FolderOptionsWindow", "cp_folder_options", "Folder Options",
     "Show hidden files, file extensions"),
]


class ControlPanelWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Control Panel", icon_key="control_panel",
                          size=QSize(460, 380))

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(32, 32))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setSpacing(14)
        self.list.setMovement(QListWidget.Movement.Static)
        for module, class_name, icon_key, title, tip in APPLETS:
            item = QListWidgetItem(icons.icon(icon_key, 32), title)
            item.setData(Qt.ItemDataRole.UserRole, (module, class_name))
            item.setToolTip(tip)
            self.list.addItem(item)
        self.list.itemDoubleClicked.connect(self._open_applet)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.list)
        self.set_content_layout(root)

    def _open_applet(self, item):
        module, class_name = item.data(Qt.ItemDataRole.UserRole)
        import importlib
        mod = importlib.import_module(f"winxp.apps.control_panel.{module}")
        cls = getattr(mod, class_name)
        window = cls(self.wm)
        self.wm.open(window)
