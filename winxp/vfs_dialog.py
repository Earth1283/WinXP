from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout,
)

from . import icons, theme, vfs as vfs_mod


class VfsFileDialog(QDialog):
    def __init__(self, parent, title, save_mode=False, kinds=(vfs_mod.TEXT,), default_name=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(theme.WINDOW_QSS)
        self.resize(480, 380)
        self.save_mode = save_mode
        self.kinds = kinds
        self.result_node_id = None
        self.result_name = default_name
        self.current_folder = vfs_mod.vfs.my_docs_id

        root = QVBoxLayout(self)

        self.path_label = QLabel()
        root.addWidget(self.path_label)

        self.list = QListWidget()
        self.list.setIconSize(icons.icon("folder", 24).availableSizes()[0] if icons.icon("folder", 24).availableSizes() else self.list.iconSize())
        self.list.itemDoubleClicked.connect(self._on_double)
        self.list.itemClicked.connect(self._on_click)
        root.addWidget(self.list, 1)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("File name:"))
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setEnabled(save_mode)
        name_row.addWidget(self.name_edit, 1)
        root.addLayout(name_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_text = "Save" if save_mode else "Open"
        self.ok_btn = QPushButton(ok_text)
        self.ok_btn.clicked.connect(self._accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

        self._refresh()

    def _refresh(self):
        self.path_label.setText("Look in: " + vfs_mod.vfs.path_of(self.current_folder))
        self.list.clear()
        node = vfs_mod.vfs.get(self.current_folder)
        if node.parent:
            up = QListWidgetItem(icons.icon("folder", 20), "..")
            up.setData(Qt.ItemDataRole.UserRole, ("up", None))
            self.list.addItem(up)
        for child in sorted(vfs_mod.vfs.children_of(self.current_folder), key=lambda n: (n.kind != vfs_mod.FOLDER, n.name.lower())):
            if child.kind == vfs_mod.FOLDER:
                item = QListWidgetItem(icons.icon("folder", 20), child.name)
                item.setData(Qt.ItemDataRole.UserRole, ("folder", child.id))
                self.list.addItem(item)
            elif child.kind in self.kinds:
                key = "text_file" if child.kind == vfs_mod.TEXT else "wordpad"
                item = QListWidgetItem(icons.icon(key, 20), child.name)
                item.setData(Qt.ItemDataRole.UserRole, ("file", child.id))
                self.list.addItem(item)

    def _on_click(self, item):
        kind, ref = item.data(Qt.ItemDataRole.UserRole)
        if kind == "file" and self.save_mode:
            node = vfs_mod.vfs.get(ref)
            self.name_edit.setText(node.name)

    def _on_double(self, item):
        kind, ref = item.data(Qt.ItemDataRole.UserRole)
        if kind == "up":
            parent = vfs_mod.vfs.get(self.current_folder).parent
            if parent:
                self.current_folder = parent
                self._refresh()
        elif kind == "folder":
            self.current_folder = ref
            self._refresh()
        elif kind == "file":
            if self.save_mode:
                node = vfs_mod.vfs.get(ref)
                self.name_edit.setText(node.name)
            else:
                self.result_node_id = ref
                self.accept()

    def _accept(self):
        if self.save_mode:
            name = self.name_edit.text().strip()
            if not name:
                return
            self.result_name = name
            self.result_node_id = self.current_folder
            self.accept()
        else:
            item = self.list.currentItem()
            if not item:
                return
            kind, ref = item.data(Qt.ItemDataRole.UserRole)
            if kind == "file":
                self.result_node_id = ref
                self.accept()

    @staticmethod
    def get_open_filename(parent, kinds=(vfs_mod.TEXT,), title="Open"):
        dlg = VfsFileDialog(parent, title, save_mode=False, kinds=kinds)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.result_node_id
        return None

    @staticmethod
    def get_save_target(parent, kinds=(vfs_mod.TEXT,), title="Save As", default_name="Untitled.txt"):
        dlg = VfsFileDialog(parent, title, save_mode=True, kinds=kinds, default_name=default_name)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.result_node_id, dlg.result_name
        return None, None
