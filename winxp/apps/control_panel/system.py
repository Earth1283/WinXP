from __future__ import annotations

import platform
import random

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from ... import icons
from ...window_manager import XPWindow

ADJECTIVES = ["QUANTUM", "TURBO", "CURSED", "LEGACY", "FERAL", "HAUNTED", "BUDGET", "UNSTABLE"]
NOUNS = ["WORKSTATION", "MAINFRAME", "TOASTER", "PENTIUM", "MACHINE", "RIG", "BOX"]


def _random_hostname():
    return f"{random.choice(ADJECTIVES)}-{random.choice(NOUNS)}-{random.randint(10, 99)}"


class SystemWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="System Properties", icon_key="cp_system",
                          size=QSize(440, 380), resizable=False)

        root = QVBoxLayout()
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(icons.icon("my_computer", 48).pixmap(48, 48))
        header.addWidget(icon_label)
        title = QLabel("Microsoft Windows XP\nVersion 2002, Service Pack 3 (definitely)")
        header.addWidget(title, 1)
        root.addLayout(header)

        form = QFormLayout()
        form.addRow("Registered to:", QLabel("Administrator"))
        form.addRow("CPU:", QLabel(f"{platform.processor() or 'Generic x86'} (probably)"))
        form.addRow("Memory:", QLabel("640 KB (ought to be enough)"))
        form.addRow("Python runtime:", QLabel(platform.python_version()))

        self.hostname_edit = QLineEdit(_random_hostname())
        form.addRow("Computer name:", self.hostname_edit)

        reroll = QPushButton("Generate New Name")
        reroll.clicked.connect(self._reroll)
        form.addRow("", reroll)

        root.addLayout(form)
        root.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        perf_btn = QPushButton("Performance...")
        perf_btn.clicked.connect(self._open_task_manager)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        btn_row.addWidget(perf_btn)
        btn_row.addWidget(close)
        root.addLayout(btn_row)

        self.set_content_layout(root)

    def _reroll(self):
        self.hostname_edit.setText(_random_hostname())

    def _open_task_manager(self):
        from .. import launch
        launch(self.wm, "app:task_manager")
