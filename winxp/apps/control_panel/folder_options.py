from __future__ import annotations

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ...settings import settings
from ...window_manager import XPWindow


class FolderOptionsWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Folder Options", icon_key="cp_folder_options",
                          size=QSize(380, 260), resizable=False)

        root = QVBoxLayout()
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Hidden files and folders")
        title.setStyleSheet("font-weight: bold;")
        root.addWidget(title)

        self.hidden_check = QCheckBox("Show hidden files and folders")
        self.hidden_check.setChecked(settings.show_hidden)
        root.addWidget(self.hidden_check)

        ext_title = QLabel("File types")
        ext_title.setStyleSheet("font-weight: bold; margin-top: 6px;")
        root.addWidget(ext_title)

        self.ext_check = QCheckBox("Hide extensions for known file types")
        self.ext_check.setChecked(not settings.show_extensions)
        root.addWidget(self.ext_check)

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

    def _apply(self):
        settings.set_show_hidden(self.hidden_check.isChecked())
        settings.set_show_extensions(not self.ext_check.isChecked())

    def _apply_and_close(self):
        self._apply()
        self.close()
