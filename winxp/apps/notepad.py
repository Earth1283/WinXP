from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import QPlainTextEdit, QVBoxLayout

from .. import theme, vfs as vfs_mod
from ..vfs_dialog import VfsFileDialog
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox


class NotepadWindow(XPWindow):
    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Untitled - Notepad", icon_key="notepad", size=QSize(560, 420))
        self.node_id = node_id
        self.dirty = False

        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Courier New", 10))
        self.editor.setStyleSheet("background: white; border: none;")
        self.editor.textChanged.connect(self._on_change)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setMenuBar(self._build_menu())
        layout.addWidget(self.editor)
        self.set_content_layout(layout)

        if node_id:
            node = vfs_mod.vfs.get(node_id)
            if node:
                self.editor.setPlainText(vfs_mod.vfs.read_content(node_id))
                self.dirty = False
                self._retitle(node.name)

    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar
        bar = QMenuBar()
        theme.style_menubar(bar)

        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._act("&New", self.new_file))
        file_menu.addAction(self._act("&Open...", self.open_file))
        file_menu.addAction(self._act("&Save", self.save_file))
        file_menu.addAction(self._act("Save &As...", self.save_file_as))
        file_menu.addSeparator()
        file_menu.addAction(self._act("E&xit", self.close))

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addAction(self._act("&Undo", self.editor.undo))
        edit_menu.addSeparator()
        edit_menu.addAction(self._act("Cu&t", self.editor.cut))
        edit_menu.addAction(self._act("&Copy", self.editor.copy))
        edit_menu.addAction(self._act("&Paste", self.editor.paste))
        edit_menu.addSeparator()
        edit_menu.addAction(self._act("Select &All", self.editor.selectAll))

        fmt_menu = bar.addMenu("F&ormat")
        wrap_act = self._act("&Word Wrap", self._toggle_wrap)
        wrap_act.setCheckable(True)
        wrap_act.setChecked(True)
        fmt_menu.addAction(wrap_act)

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self._act("&About Notepad", self._about))
        return bar

    def _act(self, text, slot):
        act = QAction(text, self)
        act.triggered.connect(slot)
        return act

    def _toggle_wrap(self, checked):
        self.editor.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth if checked else QPlainTextEdit.LineWrapMode.NoWrap
        )

    def _on_change(self):
        self.dirty = True
        title = self.windowTitle()
        if not title.startswith("*"):
            self.setWindowTitle("*" + title)

    def _retitle(self, name):
        self.setWindowTitle(f"{name} - Notepad")

    def new_file(self):
        self.node_id = None
        self.editor.setPlainText("")
        self.dirty = False
        self.setWindowTitle("Untitled - Notepad")

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.TEXT,), title="Open")
        if node_id:
            node = vfs_mod.vfs.get(node_id)
            self.node_id = node_id
            self.editor.setPlainText(vfs_mod.vfs.read_content(node_id))
            self.dirty = False
            self._retitle(node.name)

    def save_file(self):
        if self.node_id:
            vfs_mod.vfs.write_content(self.node_id, self.editor.toPlainText())
            self.dirty = False
            node = vfs_mod.vfs.get(self.node_id)
            self._retitle(node.name)
        else:
            self.save_file_as()

    def save_file_as(self):
        folder_id, name = VfsFileDialog.get_save_target(
            self, kinds=(vfs_mod.TEXT,), title="Save As", default_name="Untitled.txt"
        )
        if not folder_id:
            return
        existing = next((c for c in vfs_mod.vfs.children_of(folder_id)
                          if c.name == name and c.kind == vfs_mod.TEXT), None)
        content = self.editor.toPlainText()
        if existing:
            vfs_mod.vfs.write_content(existing.id, content)
            self.node_id = existing.id
        else:
            node = vfs_mod.vfs.create_text_file(folder_id, name, content)
            self.node_id = node.id
        self.dirty = False
        self._retitle(vfs_mod.vfs.get(self.node_id).name)

    def _about(self):
        XPMessageBox.information(
            self, "About Notepad",
            "Notepad\nVersion 5.1 (Build 2600.xpsp_sp3)\n\n"
            "© Microsoft Corporation. All rights reserved."
        )
