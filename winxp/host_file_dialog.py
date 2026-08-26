"""DIY file picker that browses the REAL host filesystem with Luna chrome --
for the one place the sim needs to reach outside itself (Media Player's
"Import from Computer"). Same look as VfsFileDialog, but lists real
directories via os.listdir instead of vfs nodes."""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget,
)

from . import icons, theme
from .xp_dialog import DIALOG_BUTTON_QSS, build_dialog_frame

DRIVE_ROOT = os.path.expanduser("~")
DRIVE_LABEL = "Local Disk (C:)"


class HostFileDialog(QDialog):
    def __init__(self, parent, title, extensions, filter_label, icon_resolver=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.resize(480, 380)
        self.extensions = {e.lower() for e in extensions}
        self.icon_resolver = icon_resolver or (lambda name: "text_file")
        self.current_dir = DRIVE_ROOT
        self.result_path = None
        self._selected_path = None

        inner = build_dialog_frame(self, title)

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(12, 10, 12, 10)

        self.path_label = QLabel()
        self.path_label.setStyleSheet("background: transparent;")
        root.addWidget(self.path_label)

        self.list = QListWidget()
        self.list.setStyleSheet("background: white;")
        self.list.itemDoubleClicked.connect(self._on_double)
        self.list.itemClicked.connect(self._on_click)
        root.addWidget(self.list, 1)

        name_row = QHBoxLayout()
        name_label = QLabel("File name:")
        name_label.setStyleSheet("background: transparent;")
        name_row.addWidget(name_label)
        self.name_display = QLabel("")
        self.name_display.setStyleSheet("background: white; border: 1px solid #7f9db9; padding: 2px 4px;")
        name_row.addWidget(self.name_display, 1)
        root.addLayout(name_row)

        type_row = QHBoxLayout()
        type_label = QLabel("Files of type:")
        type_label.setStyleSheet("background: transparent;")
        type_row.addWidget(type_label)
        filt = QLabel(filter_label)
        filt.setStyleSheet("background: white; border: 1px solid #7f9db9; padding: 2px 4px;")
        type_row.addWidget(filt, 1)
        root.addLayout(type_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.ok_btn = QPushButton("Open")
        self.ok_btn.setMinimumWidth(75)
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self._accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(75)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        inner.addWidget(body)
        self._refresh()

    def _display_path(self):
        rel = os.path.relpath(self.current_dir, DRIVE_ROOT)
        if rel == ".":
            return DRIVE_LABEL
        return DRIVE_LABEL + "\\" + rel.replace(os.sep, "\\")

    def _refresh(self):
        self.path_label.setText("Look in: " + self._display_path())
        self.list.clear()
        self._selected_path = None
        self.name_display.setText("")
        self.ok_btn.setEnabled(False)

        if os.path.normpath(self.current_dir) != os.path.normpath(DRIVE_ROOT):
            up = QListWidgetItem(icons.icon("folder", 20), "..")
            up.setData(Qt.ItemDataRole.UserRole, ("up", None))
            self.list.addItem(up)

        try:
            entries = sorted(os.listdir(self.current_dir), key=str.lower)
        except OSError:
            entries = []

        dirs, files = [], []
        for name in entries:
            if name.startswith("."):
                continue
            full = os.path.join(self.current_dir, name)
            if os.path.isdir(full):
                dirs.append(name)
            elif not self.extensions or os.path.splitext(name)[1].lower() in self.extensions:
                files.append(name)

        for name in dirs:
            item = QListWidgetItem(icons.icon("folder", 20), name)
            item.setData(Qt.ItemDataRole.UserRole, ("dir", os.path.join(self.current_dir, name)))
            self.list.addItem(item)
        for name in files:
            item = QListWidgetItem(icons.icon(self.icon_resolver(name), 20), name)
            item.setData(Qt.ItemDataRole.UserRole, ("file", os.path.join(self.current_dir, name)))
            self.list.addItem(item)

    def _on_click(self, item):
        kind, path = item.data(Qt.ItemDataRole.UserRole)
        if kind == "file":
            self._selected_path = path
            self.name_display.setText(os.path.basename(path))
            self.ok_btn.setEnabled(True)
        else:
            self._selected_path = None
            self.name_display.setText("")
            self.ok_btn.setEnabled(False)

    def _on_double(self, item):
        kind, path = item.data(Qt.ItemDataRole.UserRole)
        if kind == "up":
            self.current_dir = os.path.dirname(self.current_dir)
            self._refresh()
        elif kind == "dir":
            self.current_dir = path
            self._refresh()
        elif kind == "file":
            self.result_path = path
            self.accept()

    def _accept(self):
        if self._selected_path:
            self.result_path = self._selected_path
            self.accept()

    @staticmethod
    def get_open_filename(parent, title, extensions, filter_label, icon_resolver=None):
        dlg = HostFileDialog(parent, title, extensions, filter_label, icon_resolver)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.result_path
        return None
