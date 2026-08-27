from __future__ import annotations

import json

from PyQt6.QtCore import QMimeData, QPoint, QSize, Qt
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QPushButton, QSplitter, QStatusBar, QToolBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import corruption, icons, vfs as vfs_mod
from ..properties_dialog import PropertiesDialog
from ..settings import settings
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox

FILE_ICONS = {
    vfs_mod.TEXT: "text_file", vfs_mod.RICH: "mword",
    vfs_mod.IMAGE: "bitmap_file", vfs_mod.AUDIO: "audio_file",
    vfs_mod.VIDEO: "video_file",
}

NODE_MIME = "application/x-winxp-node-ids"


class ExplorerIconView(QListWidget):
    """IconMode list with XP-style rubber-band rect select (built in via
    ExtendedSelection) and drag-out / drop-in of vfs nodes."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionRectVisible(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)  # only via editItem()

    def startDrag(self, supportedActions):
        node_ids = [it.data(Qt.ItemDataRole.UserRole) for it in self.selectedItems()]
        if not node_ids:
            return
        mime = QMimeData()
        mime.setData(NODE_MIME, json.dumps(node_ids).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        first = self.selectedItems()[0]
        pm = first.icon().pixmap(32, 32)
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat(NODE_MIME):
            ev.acceptProposedAction()
        else:
            super().dragEnterEvent(ev)

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasFormat(NODE_MIME):
            ev.acceptProposedAction()
        else:
            super().dragMoveEvent(ev)

    def dropEvent(self, ev):
        if not ev.mimeData().hasFormat(NODE_MIME):
            return super().dropEvent(ev)
        node_ids = json.loads(bytes(ev.mimeData().data(NODE_MIME)).decode())
        item = self.itemAt(ev.position().toPoint())
        target = None
        if item:
            tid = item.data(Qt.ItemDataRole.UserRole)
            tnode = vfs_mod.vfs.get(tid)
            if tnode and tnode.kind == vfs_mod.FOLDER:
                target = tid
        if target is None:
            target = self.window.current
        self.window.perform_move(node_ids, target)
        ev.acceptProposedAction()


class ExplorerTreeWidget(QTreeWidget):
    """Folder tree — drop target only (drags don't originate from here)."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat(NODE_MIME):
            ev.acceptProposedAction()
        else:
            super().dragEnterEvent(ev)

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasFormat(NODE_MIME):
            ev.acceptProposedAction()
        else:
            super().dragMoveEvent(ev)

    def dropEvent(self, ev):
        if not ev.mimeData().hasFormat(NODE_MIME):
            return super().dropEvent(ev)
        item = self.itemAt(ev.position().toPoint())
        if not item:
            return
        node_ids = json.loads(bytes(ev.mimeData().data(NODE_MIME)).decode())
        target = item.data(0, Qt.ItemDataRole.UserRole)
        self.window.perform_move(node_ids, target)
        ev.acceptProposedAction()


class ExplorerWindow(XPWindow):
    def __init__(self, wm, start_node_id):
        super().__init__(wm, title="Windows Explorer", icon_key="my_computer", size=QSize(700, 480))
        self.current = start_node_id
        self.history = [start_node_id]
        self.hist_index = 0

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._build_toolbar())

        self.tree = ExplorerTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setFixedWidth(200)
        self.tree.itemClicked.connect(self._on_tree_click)

        self.list = ExplorerIconView(self)
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(icons.icon("folder", 32).availableSizes()[0])
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setSpacing(10)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setDragEnabled(True)  # Movement.Static resets this as a side effect
        self.list.itemDoubleClicked.connect(self._on_open)
        self.list.itemChanged.connect(self._on_item_renamed)
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
        settings.folder_options_changed.connect(self._on_folder_options_changed)

    def _on_folder_options_changed(self):
        try:
            self._refresh_list()
            self._rebuild_tree()
        except RuntimeError:
            pass  # window was closed before settings changed

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
            if child.hidden and not settings.show_hidden:
                continue
            item = QTreeWidgetItem([child.name])
            item.setIcon(0, icons.icon("folder", 18))
            item.setData(0, Qt.ItemDataRole.UserRole, child.id)
            parent_item.addChild(item)
            self._populate_tree(item, child.id)

    def _on_tree_click(self, item, col):
        if corruption.guard_fs(self.wm):
            return
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
            (n for n in vfs_mod.vfs.children_of(self.current)
             if not n.hidden or settings.show_hidden),
            key=lambda n: (n.kind != vfs_mod.FOLDER, n.name.lower()),
        )
        for child in children:
            key = "folder" if child.kind == vfs_mod.FOLDER else FILE_ICONS.get(child.kind, "text_file")
            if child.kind == "shortcut":
                key = child.icon or "text_file"
            item = QListWidgetItem(icons.icon(key, 32), vfs_mod.display_name(child))
            item.setData(Qt.ItemDataRole.UserRole, child.id)
            self.list.addItem(item)
        self.status.showMessage(f"{len(children)} object(s)")

    def _on_open(self, item):
        node_id = item.data(Qt.ItemDataRole.UserRole)
        self.open_node(node_id)

    def open_node(self, node_id):
        if corruption.guard_fs(self.wm):
            return
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        from . import launch
        if node.kind == vfs_mod.FOLDER:
            self._navigate(node_id)
        elif node.kind == vfs_mod.TEXT:
            launch(self.wm, f"notepad:{node_id}")
        elif node.kind == vfs_mod.RICH:
            launch(self.wm, f"mword:{node_id}")
        elif node.kind == vfs_mod.IMAGE:
            launch(self.wm, f"paint:{node_id}")
        elif node.kind in (vfs_mod.AUDIO, vfs_mod.VIDEO):
            launch(self.wm, f"wmp:{node_id}")
        elif node.kind == vfs_mod.SHORTCUT:
            launch(self.wm, node.target)

    def _go_back(self):
        if corruption.guard_fs(self.wm):
            return
        if self.hist_index > 0:
            self.hist_index -= 1
            self._navigate(self.history[self.hist_index], push=False)

    def _go_up(self):
        if corruption.guard_fs(self.wm):
            return
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
            menu.addSeparator()
            props_act = menu.addAction("Properties")
            props_act.triggered.connect(lambda: self._show_properties(node_id))
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
            menu.addSeparator()
            props_act = menu.addAction("Properties")
            props_act.triggered.connect(lambda: self._show_properties(self.current))
        menu.exec(self.list.mapToGlobal(pos))

    def _show_properties(self, node_id):
        if corruption.guard_fs(self.wm):
            return
        PropertiesDialog.show_for(self, node_id)
        self._refresh_list()
        self._rebuild_tree()

    # ---------- drag & drop ----------

    def perform_move(self, node_ids, target_folder_id):
        if corruption.guard_fs(self.wm):
            return
        target = vfs_mod.vfs.get(target_folder_id)
        if not target or target.kind != vfs_mod.FOLDER:
            return
        moved_any = False
        for node_id in node_ids:
            node = vfs_mod.vfs.get(node_id)
            if not node or node_id == target_folder_id or node.parent == target_folder_id:
                continue
            if node.kind == vfs_mod.FOLDER and self._is_ancestor(node_id, target_folder_id):
                continue  # can't drop a folder into its own descendant
            vfs_mod.vfs.move(node_id, target_folder_id)
            moved_any = True
        if moved_any:
            self._broadcast_refresh()

    def _is_ancestor(self, node_id, maybe_descendant_id):
        cur = vfs_mod.vfs.get(maybe_descendant_id)
        while cur and cur.parent:
            if cur.parent == node_id:
                return True
            cur = vfs_mod.vfs.get(cur.parent)
        return False

    def _broadcast_refresh(self):
        for w in list(self.wm.windows):
            if isinstance(w, ExplorerWindow):
                w._refresh_list()
                w._rebuild_tree()

    def _new_folder(self):
        if corruption.guard_fs(self.wm):
            return
        vfs_mod.vfs.create_folder(self.current)
        self._refresh_list()
        self._rebuild_tree()

    def _new_text(self):
        if corruption.guard_fs(self.wm):
            return
        vfs_mod.vfs.create_text_file(self.current)
        self._refresh_list()

    def _new_image(self):
        if corruption.guard_fs(self.wm):
            return
        from .. import image_codec
        vfs_mod.vfs.create_image_file(self.current, data=image_codec.to_bytes(image_codec.blank()))
        self._refresh_list()

    def _rename(self, node_id):
        if corruption.guard_fs(self.wm):
            return
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == node_id:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.list.editItem(item)
                return

    def _on_item_renamed(self, item):
        # setFlags()/setText() below both fire itemChanged again -- block signals
        # while touching the item or this recurses until the stack blows up.
        node_id = item.data(Qt.ItemDataRole.UserRole)
        node = vfs_mod.vfs.get(node_id) if node_id else None
        self.list.blockSignals(True)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.list.blockSignals(False)
        if not node:
            return
        new_name = item.text().strip()
        # Extensions-hidden mode edits just the stem -- reattach the real
        # extension so committing doesn't silently drop it (matches XP).
        if (new_name and "." not in new_name and not settings.show_extensions
                and node.kind in vfs_mod.EXTENSIONED_KINDS and "." in node.name):
            new_name += node.name[node.name.rfind("."):]
        if new_name and new_name != node.name:
            vfs_mod.vfs.rename(node_id, new_name)
            self._rebuild_tree()
        else:
            self.list.blockSignals(True)
            item.setText(vfs_mod.display_name(node))
            self.list.blockSignals(False)

    def _delete(self, node_id):
        if corruption.guard_fs(self.wm):
            return
        node = vfs_mod.vfs.get(node_id)
        if node.read_only:
            XPMessageBox.critical(
                self, "Confirm File Delete",
                f"Cannot delete '{node.name}': it is Read-only.\n\n"
                "Clear the Read-only attribute from its Properties first."
            )
            return
        permanent = node.parent == vfs_mod.vfs.recycle_id
        msg = "Permanently delete" if permanent else "Move to Recycle Bin:"
        if XPMessageBox.confirm(self, "Confirm Delete", f"{msg} '{node.name}'?"):
            vfs_mod.vfs.delete(node_id, permanent=permanent)
            if corruption.guard_system_file(self.wm, node):
                return
            self._refresh_list()
            self._rebuild_tree()
