"""The Explorer Bar: everything that can occupy the left-hand pane.

XP shipped one pane slot with several tenants -- the blue "common tasks"
webview, the Folders tree, Search Companion, Favorites and History -- and
exactly one of them was visible at a time. That mutual exclusion is modelled
here as a stack of panes rather than as separate always-present widgets.
"""
from __future__ import annotations

import json

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import icons, theme, vfs as vfs_mod
from ..xp_dialog import DIALOG_BUTTON_QSS, build_dialog_frame
from . import explorer_shell as shell

PANE_HEADER_QSS = "background: #0a5bc4;"


class TaskLink(QWidget):
    def __init__(self, icon_key, text, slot, enabled=True):
        super().__init__()
        self._slot = slot if enabled else None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(6)
        glyph = QLabel()
        glyph.setFixedSize(16, 16)
        if icon_key:
            glyph.setPixmap(icons.icon(icon_key, 16).pixmap(16, 16))
        glyph.setStyleSheet("background: transparent;")
        row.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setMinimumWidth(1)
        row.addWidget(self.label, 1)
        self._style(False)

    def _style(self, hovered):
        color = "#2a5ec9" if hovered else "#215dc6"
        if self._slot is None:
            color = "#8f96a5"
        underline = "underline" if hovered and self._slot else "none"
        self.label.setStyleSheet(
            f"background: transparent; color: {color}; text-decoration: {underline};")

    def enterEvent(self, ev):
        self._style(True)

    def leaveEvent(self, ev):
        self._style(False)

    def mouseReleaseEvent(self, ev):
        if self._slot and self.rect().contains(ev.position().toPoint()):
            self._slot()


class TaskGroup(QWidget):
    """One collapsible band of the task pane: rounded header with a chevron,
    white-blue body underneath."""
    toggled = pyqtSignal(str, bool)

    def __init__(self, title, collapsed=False):
        super().__init__()
        self.title = title
        self.collapsed = collapsed
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = _TaskGroupHeader(self)
        root.addWidget(self.header)

        self.body = QWidget()
        self.body.setObjectName("taskBody")
        self.body.setStyleSheet(
            "#taskBody { background: #f4f8fe; border: 1px solid #ffffff; border-top: 0; }")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(10, 6, 8, 8)
        self.body_layout.setSpacing(3)
        root.addWidget(self.body)
        self.body.setVisible(not collapsed)

    def add(self, widget):
        self.body_layout.addWidget(widget)

    def toggle(self):
        self.collapsed = not self.collapsed
        self.body.setVisible(not self.collapsed)
        self.header.update()
        self.toggled.emit(self.title, self.collapsed)


class _TaskGroupHeader(QWidget):
    def __init__(self, group):
        super().__init__(group)
        self.group = group
        self.setFixedHeight(23)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height() + 8), 4, 4)
        p.setClipPath(path)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0.0, QColor("#f8fbff"))
        grad.setColorAt(1.0, QColor("#c1d3f0"))
        p.fillRect(self.rect(), grad)
        font = QFont(self.font())
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#0c327d"))
        p.drawText(QRect(8, 0, self.width() - 30, self.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.group.title)
        self._draw_chevron(p)

    def _draw_chevron(self, p):
        box = QRectF(self.width() - 21, 4, 15, 15)
        p.setPen(QPen(QColor("#5e83c0"), 1))
        grad = QLinearGradient(box.topLeft(), box.bottomLeft())
        grad.setColorAt(0, QColor("#ffffff"))
        grad.setColorAt(1, QColor("#a9c2e8"))
        p.setBrush(grad)
        p.drawEllipse(box)
        p.setPen(QPen(QColor("#1e4c96"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx, cy = box.center().x(), box.center().y()
        if self.group.collapsed:
            p.drawLine(QPoint(int(cx - 3), int(cy - 1)), QPoint(int(cx), int(cy + 2)))
            p.drawLine(QPoint(int(cx), int(cy + 2)), QPoint(int(cx + 3), int(cy - 1)))
        else:
            p.drawLine(QPoint(int(cx - 3), int(cy + 2)), QPoint(int(cx), int(cy - 1)))
            p.drawLine(QPoint(int(cx), int(cy - 1)), QPoint(int(cx + 3), int(cy + 2)))

    def mousePressEvent(self, ev):
        self.group.toggle()


class TaskPane(QScrollArea):
    """The blue "webview" pane. Its contents are rebuilt from scratch on every
    selection change, which is exactly how the real one behaved -- the link
    list is a function of what's selected, not a fixed menu."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self._collapsed: set[str] = set()
        self._body = _TaskPaneBody()
        self.layout_ = QVBoxLayout(self._body)
        self.layout_.setContentsMargins(8, 8, 8, 8)
        self.layout_.setSpacing(10)
        self.layout_.addStretch(1)
        self.setWidget(self._body)

    def rebuild(self, groups):
        while self.layout_.count():
            item = self.layout_.takeAt(0)
            widget = item.widget()
            if widget:
                # Reparent first: a deleteLater'd widget keeps painting at its
                # old geometry until the event loop gets around to it.
                widget.setParent(None)
                widget.deleteLater()
        for title, rows in groups:
            if not rows:
                continue
            group = TaskGroup(title, collapsed=title in self._collapsed)
            group.toggled.connect(self._on_toggled)
            for row in rows:
                group.add(row if isinstance(row, QWidget) else TaskLink(*row))
            self.layout_.addWidget(group)
        self.layout_.addStretch(1)

    def _on_toggled(self, title, collapsed):
        self._collapsed.add(title) if collapsed else self._collapsed.discard(title)


class _TaskPaneBody(QWidget):
    def paintEvent(self, ev):
        p = QPainter(self)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor("#7ba2e7"))
        grad.setColorAt(1.0, QColor("#6172d5"))
        p.fillRect(self.rect(), grad)


class PaneHeader(QWidget):
    """The 'Folders' / 'Search' / 'History' caption strip with its close box."""
    closeClicked = pyqtSignal()

    def __init__(self, title):
        super().__init__()
        self.setFixedHeight(22)
        self.setStyleSheet(PANE_HEADER_QSS)
        row = QHBoxLayout(self)
        row.setContentsMargins(7, 0, 3, 0)
        self.label = QLabel(title)
        self.label.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        row.addWidget(self.label)
        row.addStretch(1)
        close = QToolButton()
        close.setText("×")
        close.setFixedSize(17, 17)
        close.setStyleSheet("color: white; font-weight: bold; background: transparent; border: 0;")
        close.clicked.connect(self.closeClicked)
        row.addWidget(close)

    def set_title(self, title):
        self.label.setText(title)


class FoldersPane(QWidget):
    """The Folders tree. Drop target, never a drag source -- same as XP, where
    you could drop onto a tree node but dragged items out of the file pane."""
    folderSelected = pyqtSignal(str)
    closeClicked = pyqtSignal()
    dropped = pyqtSignal(list, str, bool)

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = PaneHeader("Folders")
        header.closeClicked.connect(self.closeClicked)
        root.addWidget(header)
        self.tree = _FolderTree(self)
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("QTreeWidget { background: white; border: 0; font-size: 11px; }")
        self.tree.itemSelectionChanged.connect(self._on_selection)
        root.addWidget(self.tree, 1)
        self._expanded: set[str] = set()

    def _on_selection(self):
        item = self.tree.currentItem()
        if item:
            node_id = item.data(0, Qt.ItemDataRole.UserRole)
            if node_id:
                self.folderSelected.emit(node_id)

    def rebuild(self, current_id):
        self._expanded = {item.data(0, Qt.ItemDataRole.UserRole)
                          for item in self._iter_items() if item.isExpanded()}
        self.tree.blockSignals(True)
        self.tree.clear()
        root_node = vfs_mod.vfs.get(vfs_mod.vfs.root_id)
        if root_node is None:
            self.tree.blockSignals(False)
            return
        root_item = QTreeWidgetItem([root_node.name])
        root_item.setIcon(0, icons.icon("my_computer", 16))
        root_item.setData(0, Qt.ItemDataRole.UserRole, root_node.id)
        self.tree.addTopLevelItem(root_item)
        self._populate(root_item, root_node.id)
        root_item.setExpanded(True)
        self._restore_expansion(current_id)
        self.tree.blockSignals(False)

    def _populate(self, parent_item, node_id):
        for child in shell.visible_children(node_id):
            if child.kind != vfs_mod.FOLDER:
                continue
            item = QTreeWidgetItem([child.name])
            item.setIcon(0, shell.shell_icon(child, 16))
            item.setData(0, Qt.ItemDataRole.UserRole, child.id)
            parent_item.addChild(item)
            self._populate(item, child.id)

    def _iter_items(self):
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            stack.extend(item.child(i) for i in range(item.childCount()))
            yield item

    def _restore_expansion(self, current_id):
        chain = set()
        node = vfs_mod.vfs.get(current_id)
        while node:
            chain.add(node.id)
            node = vfs_mod.vfs.get(node.parent) if node.parent else None
        for item in self._iter_items():
            node_id = item.data(0, Qt.ItemDataRole.UserRole)
            if node_id in self._expanded or node_id in chain:
                item.setExpanded(True)
            if node_id == current_id:
                self.tree.setCurrentItem(item)
                node = vfs_mod.vfs.get(node_id)
                if node and node.kind == vfs_mod.FOLDER and not node.drive:
                    item.setIcon(0, icons.icon("folder_open", 16))


class _FolderTree(QTreeWidget):
    def __init__(self, pane):
        super().__init__()
        self.pane = pane
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat(shell.NODE_MIME):
            ev.acceptProposedAction()
        else:
            super().dragEnterEvent(ev)

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasFormat(shell.NODE_MIME):
            ev.acceptProposedAction()
        else:
            super().dragMoveEvent(ev)

    def dropEvent(self, ev):
        if not ev.mimeData().hasFormat(shell.NODE_MIME):
            return super().dropEvent(ev)
        item = self.itemAt(ev.position().toPoint())
        if not item:
            return
        node_ids = json.loads(bytes(ev.mimeData().data(shell.NODE_MIME)).decode())
        target = item.data(0, Qt.ItemDataRole.UserRole)
        copy = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self.pane.dropped.emit(node_ids, target, copy)
        ev.acceptProposedAction()


class SearchPane(QWidget):
    """Search Companion, minus the animated dog. Name and content matching,
    scoped to a folder subtree, results shown in the main file pane."""
    searchRequested = pyqtSignal(str, str, str, bool)
    closeClicked = pyqtSignal()

    def __init__(self, current_provider):
        super().__init__()
        self._current_provider = current_provider
        self.setStyleSheet("background: white; font-size: 11px;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = PaneHeader("Search")
        header.closeClicked.connect(self.closeClicked)
        root.addWidget(header)

        body = QWidget()
        body.setStyleSheet("background: white;")
        form = QVBoxLayout(body)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(4)
        title = QLabel("Search Companion")
        title.setStyleSheet("font-weight: bold; color: #0c327d;")
        form.addWidget(title)
        form.addWidget(self._caption("All or part of the file name:"))
        self.name_edit = QLineEdit()
        form.addWidget(self.name_edit)
        form.addWidget(self._caption("A word or phrase in the file:"))
        self.text_edit = QLineEdit()
        form.addWidget(self.text_edit)
        form.addWidget(self._caption("Look in:"))
        self.scope = QComboBox()
        self.scope.setMinimumContentsLength(10)
        self.scope.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        form.addWidget(self.scope)
        self.subfolders = QCheckBox("Search subfolders")
        self.subfolders.setChecked(True)
        form.addWidget(self.subfolders)
        form.addSpacing(6)
        search = QPushButton("Search")
        search.setFixedWidth(80)
        search.clicked.connect(self._emit)
        form.addWidget(search, 0, Qt.AlignmentFlag.AlignRight)
        self.name_edit.returnPressed.connect(self._emit)
        self.text_edit.returnPressed.connect(self._emit)
        form.addStretch(1)
        root.addWidget(body, 1)

    @staticmethod
    def _caption(text):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(1)
        return label

    def refresh_scope(self):
        current = self._current_provider()
        self.scope.clear()
        seen = []
        for node_id in (current, vfs_mod.vfs.my_docs_id, vfs_mod.vfs.desktop_id,
                        vfs_mod.vfs.root_id):
            if node_id and node_id not in seen and vfs_mod.vfs.get(node_id):
                seen.append(node_id)
                self.scope.addItem(shell.shell_path(node_id) or
                                   vfs_mod.vfs.get(node_id).name, node_id)

    def _emit(self):
        scope_id = self.scope.currentData() or self._current_provider()
        self.searchRequested.emit(self.name_edit.text().strip(),
                                  self.text_edit.text().strip(),
                                  scope_id, self.subfolders.isChecked())


class LinkListPane(QWidget):
    """Favorites and History -- both are just a captioned list of places."""
    itemChosen = pyqtSignal(str)
    closeClicked = pyqtSignal()

    def __init__(self, title):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = PaneHeader(title)
        header.closeClicked.connect(self.closeClicked)
        root.addWidget(header)
        self.list = QListWidget()
        self.list.setStyleSheet(
            "QListWidget { background: white; border: 0; font-size: 11px; }"
            "QListWidget::item { padding: 3px; }")
        self.list.itemClicked.connect(self._on_click)
        root.addWidget(self.list, 1)

    def set_places(self, node_ids):
        self.list.clear()
        for node_id in node_ids:
            node = vfs_mod.vfs.get(node_id)
            if not node:
                continue
            item = QListWidgetItem(shell.shell_icon(node, 16), node.name)
            item.setData(Qt.ItemDataRole.UserRole, node_id)
            self.list.addItem(item)

    def _on_click(self, item):
        self.itemChosen.emit(item.data(Qt.ItemDataRole.UserRole))


class BrowseForFolderDialog(QDialog):
    """Edit > Move To Folder / Copy To Folder. XP's version is a folder tree
    with a Make New Folder button and a verb-specific action button."""

    def __init__(self, parent, title, prompt, action_label):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.selected_id = None
        inner = build_dialog_frame(self, title)

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        label = QLabel(prompt)
        label.setWordWrap(True)
        label.setStyleSheet("background: transparent;")
        root.addWidget(label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("QTreeWidget { background: white; border: 1px solid #7f9db9; }")
        self.tree.itemSelectionChanged.connect(self._on_selection)
        root.addWidget(self.tree, 1)

        row = QHBoxLayout()
        new_folder = QPushButton("Make New Folder")
        new_folder.clicked.connect(self._make_folder)
        row.addWidget(new_folder)
        row.addStretch(1)
        self.action_btn = QPushButton(action_label)
        self.action_btn.setFixedWidth(80)
        self.action_btn.setEnabled(False)
        self.action_btn.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.setFixedWidth(80)
        cancel.clicked.connect(self.reject)
        row.addWidget(self.action_btn)
        row.addWidget(cancel)
        root.addLayout(row)

        inner.addWidget(body)
        self.resize(340, 400)
        self._rebuild()

    def _rebuild(self, select_id=None):
        self.tree.clear()
        root_node = vfs_mod.vfs.get(vfs_mod.vfs.root_id)
        root_item = QTreeWidgetItem([root_node.name])
        root_item.setIcon(0, icons.icon("my_computer", 16))
        root_item.setData(0, Qt.ItemDataRole.UserRole, root_node.id)
        self.tree.addTopLevelItem(root_item)
        self._populate(root_item, root_node.id, select_id)
        root_item.setExpanded(True)

    def _populate(self, parent_item, node_id, select_id):
        for child in shell.visible_children(node_id):
            if child.kind != vfs_mod.FOLDER:
                continue
            item = QTreeWidgetItem([child.name])
            item.setIcon(0, shell.shell_icon(child, 16))
            item.setData(0, Qt.ItemDataRole.UserRole, child.id)
            parent_item.addChild(item)
            if child.id == select_id:
                self.tree.setCurrentItem(item)
                parent_item.setExpanded(True)
            self._populate(item, child.id, select_id)

    def _on_selection(self):
        item = self.tree.currentItem()
        self.selected_id = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.action_btn.setEnabled(self.selected_id is not None)

    def _make_folder(self):
        if not self.selected_id:
            return
        node = vfs_mod.vfs.create_folder(self.selected_id)
        self._rebuild(select_id=node.id)

    @staticmethod
    def choose(parent, title, prompt, action_label):
        dlg = BrowseForFolderDialog(parent, title, prompt, action_label)
        anchor = parent.frameGeometry().center() if parent is not None else QPoint(400, 300)
        dlg.move(anchor.x() - dlg.width() // 2, anchor.y() - dlg.height() // 2)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.selected_id
        return None
