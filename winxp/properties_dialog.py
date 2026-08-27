"""DIY Luna-styled file/folder Properties dialog (right-click > Properties)."""
from __future__ import annotations

import os
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from . import icons, vfs as vfs_mod
from .xp_dialog import DIALOG_BUTTON_QSS, build_dialog_frame
from . import theme

TYPE_LABELS = {
    vfs_mod.FOLDER: "File Folder",
    vfs_mod.TEXT: "Text Document",
    vfs_mod.RICH: "Rich Text Document",
    vfs_mod.IMAGE: "Bitmap Image",
    vfs_mod.AUDIO: "Audio File",
    vfs_mod.VIDEO: "Video File",
    vfs_mod.SHORTCUT: "Shortcut",
}

ICON_KEYS = {
    vfs_mod.FOLDER: "folder", vfs_mod.TEXT: "text_file", vfs_mod.RICH: "mword",
    vfs_mod.IMAGE: "bitmap_file", vfs_mod.AUDIO: "audio_file", vfs_mod.VIDEO: "video_file",
}


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n:,} bytes"
    for unit, div in (("KB", 1024), ("MB", 1024 ** 2), ("GB", 1024 ** 3)):
        if n < div * 1024 or unit == "GB":
            return f"{n / div:,.1f} {unit} ({n:,} bytes)"
    return f"{n:,} bytes"


def _folder_stats(node_id):
    """Recursively sum file sizes and count files/folders under node_id."""
    total = 0
    files = 0
    folders = 0
    for child in vfs_mod.vfs.children_of(node_id):
        if child.kind == vfs_mod.FOLDER:
            folders += 1
            t, f, d = _folder_stats(child.id)
            total += t
            files += f
            folders += d
        else:
            files += 1
            try:
                total += os.path.getsize(vfs_mod.vfs.content_path(child.id))
            except OSError:
                pass
    return total, files, folders


class PropertiesDialog(QDialog):
    def __init__(self, parent, node_id):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.node_id = node_id
        node = vfs_mod.vfs.get(node_id)

        inner = build_dialog_frame(self, f"{node.name} Properties")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(10, 10, 10, 10)
        body_l.setSpacing(10)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(node), "General")
        body_l.addWidget(tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.setSpacing(6)
        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(75, 23)
        ok_btn.clicked.connect(self._accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(75, 23)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        body_l.addLayout(btn_row)

        inner.addWidget(body)
        self.setFixedSize(340, 380)

    def _build_general_tab(self, node):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(14, 14, 14, 10)
        lay.setSpacing(10)

        header = QHBoxLayout()
        icon_label = QLabel()
        icon_key = "folder" if node.kind == vfs_mod.FOLDER else ICON_KEYS.get(node.kind, "text_file")
        icon_label.setPixmap(icons.icon(icon_key, 32).pixmap(32, 32))
        header.addWidget(icon_label)
        self.name_edit = QLineEdit(node.name)
        header.addWidget(self.name_edit, 1)
        lay.addLayout(header)

        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #aca998;")
        lay.addWidget(line)

        form = QFormLayout()
        form.setSpacing(6)
        form.addRow("Type:", QLabel(TYPE_LABELS.get(node.kind, "File")))
        form.addRow("Location:", QLabel(vfs_mod.vfs.path_of(node.parent) if node.parent else "My Computer"))

        self.size_label = QLabel("Calculating...")
        form.addRow("Size:", self.size_label)
        if node.kind == vfs_mod.FOLDER:
            QTimer.singleShot(280, self._fill_folder_size)
        else:
            try:
                n = os.path.getsize(vfs_mod.vfs.content_path(node.id))
            except OSError:
                n = 0
            self.size_label.setText(_human_size(n))

        form.addRow("Created:", QLabel(time.strftime("%A, %B %d, %Y, %I:%M:%S %p",
                                                       time.localtime(node.created))))
        form.addRow("Modified:", QLabel(time.strftime("%A, %B %d, %Y, %I:%M:%S %p",
                                                        time.localtime(node.modified))))
        lay.addLayout(form)
        lay.addStretch(1)

        attr_line = QLabel()
        attr_line.setFixedHeight(1)
        attr_line.setStyleSheet("background: #aca998;")
        lay.addWidget(attr_line)

        attrs = QHBoxLayout()
        attrs.addWidget(QLabel("Attributes:"))
        self.readonly_check = QCheckBox("Read-only")
        self.readonly_check.setChecked(node.read_only)
        self.hidden_check = QCheckBox("Hidden")
        self.hidden_check.setChecked(node.hidden)
        attrs.addWidget(self.readonly_check)
        attrs.addWidget(self.hidden_check)
        attrs.addStretch(1)
        lay.addLayout(attrs)
        return tab

    def _fill_folder_size(self):
        total, files, folders = _folder_stats(self.node_id)
        contains = []
        if files:
            contains.append(f"{files} Files")
        if folders:
            contains.append(f"{folders} Folders")
        suffix = f", {', '.join(contains)}" if contains else ""
        self.size_label.setText(_human_size(total) + suffix)

    def _accept(self):
        new_name = self.name_edit.text().strip()
        node = vfs_mod.vfs.get(self.node_id)
        if new_name and node and new_name != node.name:
            vfs_mod.vfs.rename(self.node_id, new_name)
        vfs_mod.vfs.set_attributes(
            self.node_id,
            hidden=self.hidden_check.isChecked(),
            read_only=self.readonly_check.isChecked(),
        )
        self.accept()

    @staticmethod
    def show_for(parent, node_id):
        dlg = PropertiesDialog(parent, node_id)
        anchor = parent.frameGeometry() if parent is not None else None
        from PyQt6.QtWidgets import QApplication
        center = anchor.center() if anchor is not None and parent.isVisible() \
            else QApplication.primaryScreen().geometry().center()
        dlg.move(center.x() - dlg.width() // 2, center.y() - dlg.height() // 2)
        dlg.exec()
