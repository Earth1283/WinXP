from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QSplitter, QStatusBar, QToolBar, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import icons, vfs as vfs_mod
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox

FILE_ICONS = {
    vfs_mod.TEXT: "text_file", vfs_mod.RICH: "wordpad",
    vfs_mod.IMAGE: "bitmap_file", vfs_mod.AUDIO: "audio_file",
    vfs_mod.VIDEO: "video_file",
}


class ExplorerWindow(XPWindow):
    def __init__(self, wm, start_node_id):
        super().__init__(wm, title="Windows Explorer", icon_key="my_computer", size=QSize(700, 480))
        self.current = start_node_id
        self.history = [start_node_id]
        self.hist_index = 0

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._build_toolbar())

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setFixedWidth(200)
        self.tree.itemClicked.connect(self._on_tree_click)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(icons.icon("folder", 32).availableSizes()[0])
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setSpacing(10)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.itemDoubleClicked.connect(self._on_open)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)

        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(self.list)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.status = QStatusBar()
        root.addWidget(self.status)

        self.set_content_layout(root)
        self._rebuild_tree()
        self._navigate(start_node_id, push=False)

    def _build_toolbar(self):
        bar = QToolBar()
        bar.setMovable(False)
        back = QPushButton("◀ Back")
        up = QPushButton("Up")
        back.clicked.connect(self._go_back)
        up.clicked.connect(self._go_up)
        bar.addWidget(back)
        bar.addWidget(up)

        self.address = QLineEdit()
        self.address.setReadOnly(True)

        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(4, 4, 4, 4)
        l.addWidget(bar)
        l.addWidget(QLabel("Address"))
        l.addWidget(self.address, 1)
        return w

    def _rebuild_tree(self):
        self.tree.clear()
        root_node = vfs_mod.vfs.get(vfs_mod.vfs.root_id)
        root_item = QTreeWidgetItem([root_node.name])
        root_item.setIcon(0, icons.icon("my_computer", 18))
        root_item.setData(0, Qt.ItemDataRole.UserRole, root_node.id)
        self.tree.addTopLevelItem(root_item)
        self._populate_tree(root_item, root_node.id)
        root_item.setExpanded(True)

    def _populate_tree(self, parent_item, node_id):
        for child in vfs_mod.vfs.children_of(node_id):
            if child.kind != vfs_mod.FOLDER:
                continue
            item = QTreeWidgetItem([child.name])
            item.setIcon(0, icons.icon("folder", 18))
            item.setData(0, Qt.ItemDataRole.UserRole, child.id)
            parent_item.addChild(item)
            self._populate_tree(item, child.id)

    def _on_tree_click(self, item, col):
        node_id = item.data(0, Qt.ItemDataRole.UserRole)
        self._navigate(node_id)

    def _navigate(self, node_id, push=True):
        self.current = node_id
        if push:
            self.history = self.history[: self.hist_index + 1]
            self.history.append(node_id)
            self.hist_index = len(self.history) - 1
        self._refresh_list()
        node = vfs_mod.vfs.get(node_id)
        self.setWindowTitle(node.name)
        self.address.setText(vfs_mod.vfs.path_of(node_id))

    def _refresh_list(self):
        self.list.clear()
        children = sorted(
            vfs_mod.vfs.children_of(self.current),
            key=lambda n: (n.kind != vfs_mod.FOLDER, n.name.lower()),
        )
        for child in children:
            key = "folder" if child.kind == vfs_mod.FOLDER else FILE_ICONS.get(child.kind, "text_file")
            if child.kind == "shortcut":
                key = child.icon or "text_file"
            item = QListWidgetItem(icons.icon(key, 32), child.name)
            item.setData(Qt.ItemDataRole.UserRole, child.id)
            self.list.addItem(item)
        self.status.showMessage(f"{len(children)} object(s)")

    def _on_open(self, item):
        node_id = item.data(Qt.ItemDataRole.UserRole)
        self.open_node(node_id)

    def open_node(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        from . import launch
        if node.kind == vfs_mod.FOLDER:
            self._navigate(node_id)
        elif node.kind == vfs_mod.TEXT:
            launch(self.wm, f"notepad:{node_id}")
        elif node.kind == vfs_mod.RICH:
            launch(self.wm, f"wordpad:{node_id}")
        elif node.kind == vfs_mod.IMAGE:
            launch(self.wm, f"paint:{node_id}")
        elif node.kind in (vfs_mod.AUDIO, vfs_mod.VIDEO):
            launch(self.wm, f"wmp:{node_id}")
        elif node.kind == vfs_mod.SHORTCUT:
            launch(self.wm, node.target)

    def _go_back(self):
        if self.hist_index > 0:
            self.hist_index -= 1
            self._navigate(self.history[self.hist_index], push=False)

    def _go_up(self):
        node = vfs_mod.vfs.get(self.current)
        if node and node.parent:
            self._navigate(node.parent)

    def _on_context_menu(self, pos):
        item = self.list.itemAt(pos)
        menu = QMenu(self)
        if item:
            node_id = item.data(Qt.ItemDataRole.UserRole)
            open_act = menu.addAction("Open")
            open_act.triggered.connect(lambda: self.open_node(node_id))
            rename_act = menu.addAction("Rename")
            rename_act.triggered.connect(lambda: self._rename(node_id))
            delete_act = menu.addAction("Delete")
            delete_act.triggered.connect(lambda: self._delete(node_id))
        else:
            new_menu = menu.addMenu("New")
            folder_act = new_menu.addAction("Folder")
            folder_act.triggered.connect(self._new_folder)
            text_act = new_menu.addAction("Text Document")
            text_act.triggered.connect(self._new_text)
            image_act = new_menu.addAction("Bitmap Image")
            image_act.triggered.connect(self._new_image)
            refresh_act = menu.addAction("Refresh")
            refresh_act.triggered.connect(self._refresh_list)
        menu.exec(self.list.mapToGlobal(pos))

    def _new_folder(self):
        vfs_mod.vfs.create_folder(self.current)
        self._refresh_list()
        self._rebuild_tree()

    def _new_text(self):
        vfs_mod.vfs.create_text_file(self.current)
        self._refresh_list()

    def _new_image(self):
        from .. import image_codec
        vfs_mod.vfs.create_image_file(self.current, data=image_codec.to_bytes(image_codec.blank()))
        self._refresh_list()

    def _rename(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=node.name)
        if ok and name.strip():
            vfs_mod.vfs.rename(node_id, name.strip())
            self._refresh_list()
            self._rebuild_tree()

    def _delete(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        permanent = node.parent == vfs_mod.vfs.recycle_id
        msg = "Permanently delete" if permanent else "Move to Recycle Bin:"
        if XPMessageBox.confirm(self, "Confirm Delete", f"{msg} '{node.name}'?"):
            vfs_mod.vfs.delete(node_id, permanent=permanent)
            self._refresh_list()
            self._rebuild_tree()
