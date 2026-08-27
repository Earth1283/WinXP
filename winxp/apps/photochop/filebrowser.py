"""The File Browser -- PhotoChop 7.0's headline feature.

Folder tree on the left, a thumbnail grid in the middle, and the metadata
panel underneath the tree that is always, always still building thumbnails.
"""
from __future__ import annotations

import os
import time

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ... import icons, image_codec, vfs as vfs_mod
from .dialogs import PCDialog, _lbl


class FileBrowserDialog(PCDialog):
    def __init__(self, parent):
        super().__init__(parent, "File Browser")
        self.selected_node = None

        top = QHBoxLayout()
        top.addWidget(_lbl("Look in:"))
        self.location = QComboBox()
        self.location.setFixedWidth(220)
        top.addWidget(self.location)
        top.addStretch(1)
        self.sort = QComboBox()
        self.sort.addItems(["Filename", "Date Created", "Date Modified", "File Size",
                            "Rank", "Resolution"])
        top.addWidget(_lbl("Sort By:"))
        top.addWidget(self.sort)
        self.view_mode = QComboBox()
        self.view_mode.addItems(["Small Thumbnail", "Medium Thumbnail",
                                 "Large Thumbnail", "Details"])
        self.view_mode.setCurrentText("Medium Thumbnail")
        self.view_mode.currentTextChanged.connect(lambda _: self._load_folder())
        top.addWidget(self.view_mode)
        self.content.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(6)

        left = QVBoxLayout()
        left.setSpacing(4)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setFixedWidth(190)
        self.tree.setFixedHeight(200)
        self.tree.currentItemChanged.connect(self._tree_changed)
        left.addWidget(self.tree)

        self.preview = QLabel()
        self.preview.setFixedSize(190, 130)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("border: 1px solid #808080; background: #ffffff;")
        left.addWidget(self.preview)

        self.metadata = QLabel()
        self.metadata.setWordWrap(True)
        self.metadata.setFixedWidth(190)
        self.metadata.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.metadata.setStyleSheet("background: white; border: 1px solid #808080;"
                                    "font-size: 10px; padding: 3px;")
        left.addWidget(self.metadata, 1)
        body.addLayout(left)

        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setSpacing(6)
        self.grid.setFixedSize(420, 360)
        self.grid.setStyleSheet("QListWidget { border: 1px solid #808080; background: white; }")
        self.grid.currentItemChanged.connect(self._grid_changed)
        self.grid.itemDoubleClicked.connect(self._open)
        body.addWidget(self.grid)
        self.content.addLayout(body)

        self.status = QLabel("Building thumbnail cache...")
        self.status.setStyleSheet("background: transparent; color: #555; font-size: 10px;")
        self.content.addWidget(self.status)

        self.add_button("Open", self._open, default=True)
        self.add_button("Cancel", self.reject)
        self.finish_side()

        self._build_tree()
        self._load_folder()
        # PS 7's browser announced its thumbnail cache constantly. So does this.
        self._nag = QTimer(self)
        self._nag.timeout.connect(self._nag_status)
        self._nag.start(4000)

    def _nag_status(self):
        count = self.grid.count()
        self.status.setText(f"Building thumbnail cache... {count} of {count} items"
                            if count else "No items to display.")

    # -- tree ----------------------------------------------------------

    def _build_tree(self):
        vfs = vfs_mod.vfs
        self.tree.clear()
        roots = [("Desktop", vfs.desktop_id), ("My Documents", vfs.my_docs_id),
                 ("My Computer", vfs.root_id)]
        for label, node_id in roots:
            if not node_id:
                continue
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.ItemDataRole.UserRole, node_id)
            item.setIcon(0, icons.icon("folder", 16))
            self._add_children(item, node_id, depth=0)
            self.tree.addTopLevelItem(item)
            item.setExpanded(True)
            self.location.addItem(label, node_id)
        self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _add_children(self, parent_item, node_id, depth):
        if depth > 3:
            return
        for child in vfs_mod.vfs.children_of(node_id):
            if child.kind != vfs_mod.FOLDER or child.hidden:
                continue
            item = QTreeWidgetItem([child.name])
            item.setData(0, Qt.ItemDataRole.UserRole, child.id)
            item.setIcon(0, icons.icon("folder", 16))
            self._add_children(item, child.id, depth + 1)
            parent_item.addChild(item)

    def _tree_changed(self, current, _previous):
        if current is not None:
            self._load_folder(current.data(0, Qt.ItemDataRole.UserRole))

    # -- grid ----------------------------------------------------------

    def _thumb_size(self):
        return {"Small Thumbnail": 48, "Medium Thumbnail": 76,
                "Large Thumbnail": 112, "Details": 32}[self.view_mode.currentText()]

    def _load_folder(self, node_id=None):
        vfs = vfs_mod.vfs
        if node_id is None:
            item = self.tree.currentItem()
            node_id = item.data(0, Qt.ItemDataRole.UserRole) if item else vfs.desktop_id
        self._folder_id = node_id
        size = self._thumb_size()
        self.grid.setIconSize(QSize(size, size))
        self.grid.setGridSize(QSize(size + 22, size + 34))
        self.grid.clear()
        if not node_id:
            return
        for child in vfs.children_of(node_id):
            if child.kind == vfs_mod.FOLDER:
                item = QListWidgetItem(child.name)
                item.setIcon(icons.icon("folder", size))
            elif child.kind == vfs_mod.IMAGE:
                item = QListWidgetItem(child.name)
                item.setIcon(self._thumbnail(child.id, size))
            else:
                continue
            item.setData(Qt.ItemDataRole.UserRole, child.id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.grid.addItem(item)
        self._nag_status()

    def _thumbnail(self, node_id, size) -> QIcon:
        pixmap = image_codec.from_bytes(vfs_mod.vfs.read_blob(node_id))
        if pixmap.isNull():
            return icons.icon("bitmap_file", size)
        return QIcon(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation))

    def _grid_changed(self, current, _previous):
        if current is None:
            return
        node_id = current.data(Qt.ItemDataRole.UserRole)
        node = vfs_mod.vfs.get(node_id)
        if node is None:
            return
        if node.kind == vfs_mod.IMAGE:
            self.selected_node = node_id
            pixmap = image_codec.from_bytes(vfs_mod.vfs.read_blob(node_id))
            if not pixmap.isNull():
                self.preview.setPixmap(pixmap.scaled(
                    186, 126, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                self.metadata.setText(
                    f"<b>File Properties</b><br>"
                    f"Filename: {node.name}<br>"
                    f"Date Created: {time.strftime('%m/%d/%Y %I:%M %p', time.localtime(node.created))}<br>"
                    f"Date Modified: {time.strftime('%m/%d/%Y %I:%M %p', time.localtime(node.modified))}<br>"
                    f"Image Format: PNG<br>"
                    f"Width: {pixmap.width()} pixels<br>"
                    f"Height: {pixmap.height()} pixels<br>"
                    f"Color Mode: RGB Color<br>"
                    f"Resolution: 72 ppi<br>"
                    f"<br><b>EXIF</b><br>Nothing to see here.")
        else:
            self.selected_node = None
            self.preview.clear()
            self.metadata.setText(f"<b>Folder</b><br>{node.name}")

    def _open(self, *_):
        if self.selected_node:
            self.accept()
        else:
            item = self.grid.currentItem()
            if item is not None:
                node = vfs_mod.vfs.get(item.data(Qt.ItemDataRole.UserRole))
                if node and node.kind == vfs_mod.FOLDER:
                    self._load_folder(node.id)

    @staticmethod
    def pick(parent):
        dialog = FileBrowserDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_node
        return None
