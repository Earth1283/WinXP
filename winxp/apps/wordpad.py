from __future__ import annotations

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QAction, QFont, QTextCharFormat
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QMessageBox, QTextEdit, QToolBar, QVBoxLayout, QWidget

from .. import vfs as vfs_mod
from ..vfs_dialog import VfsFileDialog
from ..window_manager import XPWindow


class WordPadWindow(XPWindow):
    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Document - WordPad", icon_key="wordpad", size=QSize(620, 460))
        self.node_id = node_id

        self.editor = QTextEdit()
        self.editor.setStyleSheet("background: white; border: none;")
        self.editor.setFont(QFont("Times New Roman", 12))

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setMenuBar(self._build_menu())
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self.editor)
        self.set_content_layout(layout)

        if node_id:
            node = vfs_mod.vfs.get(node_id)
            if node:
                self.editor.setHtml(node.content)
                self._retitle(node.name)

    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar
        bar = QMenuBar()
        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._act("&New", self.new_file))
        file_menu.addAction(self._act("&Open...", self.open_file))
        file_menu.addAction(self._act("&Save", self.save_file))
        file_menu.addAction(self._act("Save &As...", self.save_file_as))
        file_menu.addSeparator()
        file_menu.addAction(self._act("E&xit", self.close))

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addAction(self._act("&Undo", self.editor.undo))
        edit_menu.addAction(self._act("Cu&t", self.editor.cut))
        edit_menu.addAction(self._act("&Copy", self.editor.copy))
        edit_menu.addAction(self._act("&Paste", self.editor.paste))
        return bar

    def _build_toolbar(self):
        bar = QToolBar()
        bar.setMovable(False)

        bold = QAction("B", self)
        bold.setCheckable(True)
        f = bold.font()
        f.setBold(True)
        bold.setFont(f)
        bold.triggered.connect(lambda c: self.editor.setFontWeight(
            QFont.Weight.Bold if c else QFont.Weight.Normal))
        bar.addAction(bold)

        italic = QAction("I", self)
        italic.setCheckable(True)
        f2 = italic.font()
        f2.setItalic(True)
        italic.setFont(f2)
        italic.triggered.connect(self.editor.setFontItalic)
        bar.addAction(italic)

        underline = QAction("U", self)
        underline.setCheckable(True)
        f3 = underline.font()
        f3.setUnderline(True)
        underline.setFont(f3)
        underline.triggered.connect(self.editor.setFontUnderline)
        bar.addAction(underline)

        bar.addSeparator()
        size_box = QComboBox()
        size_box.addItems(["8", "10", "12", "14", "18", "24", "36"])
        size_box.setCurrentText("12")
        size_box.currentTextChanged.connect(lambda t: self.editor.setFontPointSize(float(t)))
        bar.addWidget(size_box)
        return bar

    def _act(self, text, slot):
        act = QAction(text, self)
        act.triggered.connect(slot)
        return act

    def _retitle(self, name):
        self.setWindowTitle(f"{name} - WordPad")

    def new_file(self):
        self.node_id = None
        self.editor.setHtml("")
        self.setWindowTitle("Document - WordPad")

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.RICH,), title="Open")
        if node_id:
            node = vfs_mod.vfs.get(node_id)
            self.node_id = node_id
            self.editor.setHtml(node.content)
            self._retitle(node.name)

    def save_file(self):
        if self.node_id:
            vfs_mod.vfs.write_content(self.node_id, self.editor.toHtml())
            self._retitle(vfs_mod.vfs.get(self.node_id).name)
        else:
            self.save_file_as()

    def save_file_as(self):
        folder_id, name = VfsFileDialog.get_save_target(
            self, kinds=(vfs_mod.RICH,), title="Save As", default_name="Document.rtf"
        )
        if not folder_id:
            return
        existing = next((c for c in vfs_mod.vfs.children_of(folder_id)
                          if c.name == name and c.kind == vfs_mod.RICH), None)
        content = self.editor.toHtml()
        if existing:
            vfs_mod.vfs.write_content(existing.id, content)
            self.node_id = existing.id
        else:
            parent = vfs_mod.vfs.get(folder_id)
            node = vfs_mod.vfs._new(vfs_mod.RICH, name, folder_id, content=content)
            parent.children.append(node.id)
            vfs_mod.vfs.save()
            self.node_id = node.id
        self._retitle(vfs_mod.vfs.get(self.node_id).name)
