from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction, QActionGroup, QFont, QKeySequence, QTextCursor, QTextDocument, QTextListFormat,
)
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFontComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
    QToolBar, QVBoxLayout, QWidget,
)

from .. import theme, vfs as vfs_mod
from ..vfs_dialog import VfsFileDialog
from ..window_manager import XPWindow

BRAND_GREEN = "#2d5c1f"
AUTOSAVE_MS = 20_000


class MWordWindow(XPWindow):
    """MacroHard Word -- a shameless, embarrassingly overboard WordPad clone."""

    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Document1 - MacroHard Word", icon_key="mword", size=QSize(700, 520))
        self.node_id = node_id
        self._find_dialog = None

        self.editor = QTextEdit()
        self.editor.setStyleSheet("background: white; border: none;")
        self.editor.setFont(QFont("Times New Roman", 12))
        self.editor.cursorPositionChanged.connect(self._sync_format_actions)
        self.editor.cursorPositionChanged.connect(self._update_status)
        self.editor.textChanged.connect(self._update_status)
        self.editor.document().modificationChanged.connect(self._on_modified)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setMenuBar(self._build_menu())
        layout.addWidget(self._build_banner())
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self.editor, 1)
        layout.addWidget(self._build_status_bar())
        self.set_content_layout(layout)

        if node_id:
            node = vfs_mod.vfs.get(node_id)
            if node:
                self.editor.setHtml(vfs_mod.vfs.read_content(node_id))
                self.editor.document().setModified(False)
                self._retitle(node.name)

        self._update_status()

        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(AUTOSAVE_MS)

    # -- chrome ------------------------------------------------------------

    def _build_banner(self):
        w = QWidget()
        w.setStyleSheet(f"background: {BRAND_GREEN};")
        l = QHBoxLayout(w)
        l.setContentsMargins(10, 6, 10, 6)
        wordmark = QLabel("MacroHard Word")
        wordmark.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        tagline = QLabel("  --  Where do you want to type today?")
        tagline.setStyleSheet("color: #c8e6b8; font-size: 11px;")
        l.addWidget(wordmark)
        l.addWidget(tagline)
        l.addStretch(1)
        return w

    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar
        bar = QMenuBar()
        theme.style_menubar(bar)
        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._act("&New", self.new_file, QKeySequence.StandardKey.New))
        file_menu.addAction(self._act("&Open...", self.open_file, QKeySequence.StandardKey.Open))
        file_menu.addAction(self._act("&Save", self.save_file, QKeySequence.StandardKey.Save))
        file_menu.addAction(self._act("Save &As...", self.save_file_as))
        file_menu.addSeparator()
        file_menu.addAction(self._act("E&xit", self.close))

        edit_menu = bar.addMenu("&Edit")
        self.undo_act = self._act("&Undo", self.editor.undo, QKeySequence.StandardKey.Undo)
        self.redo_act = self._act("&Redo", self.editor.redo, QKeySequence.StandardKey.Redo)
        self.undo_act.setEnabled(False)
        self.redo_act.setEnabled(False)
        self.editor.document().undoAvailable.connect(self.undo_act.setEnabled)
        self.editor.document().redoAvailable.connect(self.redo_act.setEnabled)
        edit_menu.addAction(self.undo_act)
        edit_menu.addAction(self.redo_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self._act("Cu&t", self.editor.cut, QKeySequence.StandardKey.Cut))
        edit_menu.addAction(self._act("&Copy", self.editor.copy, QKeySequence.StandardKey.Copy))
        edit_menu.addAction(self._act("&Paste", self.editor.paste, QKeySequence.StandardKey.Paste))
        edit_menu.addSeparator()
        edit_menu.addAction(self._act("&Find...", self.show_find, QKeySequence.StandardKey.Find))
        edit_menu.addAction(self._act("&Replace...", self.show_replace, QKeySequence.StandardKey.Replace))

        bar.addMenu("&View")
        bar.addMenu("&Insert")
        bar.addMenu("F&ormat")

        tools_menu = bar.addMenu("&Tools")
        tools_menu.addAction(self._act("&Word Count...", self._show_word_count))
        tools_menu.addAction(self._act("&Clippy Enterprise Assistant...", self._clippy))

        bar.addMenu("&Help")
        return bar

    def _build_toolbar(self):
        bar = QToolBar()
        bar.setMovable(False)

        font_box = QFontComboBox()
        font_box.setCurrentFont(self.editor.font())
        font_box.currentFontChanged.connect(self.editor.setCurrentFont)
        bar.addWidget(font_box)

        self.size_box = QComboBox()
        self.size_box.addItems(["8", "10", "12", "14", "18", "24", "36", "48", "72"])
        self.size_box.setCurrentText("12")
        self.size_box.setEditable(True)
        self.size_box.currentTextChanged.connect(self._set_font_size)
        bar.addWidget(self.size_box)

        bar.addSeparator()

        self.bold_act = self._toggle_act(
            "B", lambda c: self.editor.setFontWeight(QFont.Weight.Bold if c else QFont.Weight.Normal), bold=True
        )
        bar.addAction(self.bold_act)
        self.italic_act = self._toggle_act("I", self.editor.setFontItalic, italic=True)
        bar.addAction(self.italic_act)
        self.underline_act = self._toggle_act("U", self.editor.setFontUnderline, underline=True)
        bar.addAction(self.underline_act)

        color_btn = QPushButton("A")
        color_btn.setFixedWidth(28)
        color_btn.setStyleSheet("color: #c33; font-weight: bold;")
        color_btn.clicked.connect(self._pick_color)
        bar.addWidget(color_btn)

        bar.addSeparator()

        align_group = QActionGroup(self)
        align_group.setExclusive(True)
        self.align_left = self._toggle_act("L", lambda c: self.editor.setAlignment(Qt.AlignmentFlag.AlignLeft))
        self.align_center = self._toggle_act("C", lambda c: self.editor.setAlignment(Qt.AlignmentFlag.AlignCenter))
        self.align_right = self._toggle_act("R", lambda c: self.editor.setAlignment(Qt.AlignmentFlag.AlignRight))
        self.align_justify = self._toggle_act("J", lambda c: self.editor.setAlignment(Qt.AlignmentFlag.AlignJustify))
        for a in (self.align_left, self.align_center, self.align_right, self.align_justify):
            align_group.addAction(a)
            bar.addAction(a)
        self.align_left.setChecked(True)

        bar.addSeparator()

        bullets = QAction("• List", self)
        bullets.triggered.connect(lambda: self._toggle_list(QTextListFormat.Style.ListDisc))
        bar.addAction(bullets)

        numbers = QAction("1. List", self)
        numbers.triggered.connect(lambda: self._toggle_list(QTextListFormat.Style.ListDecimal))
        bar.addAction(numbers)

        return bar

    def _build_status_bar(self):
        w = QWidget()
        w.setStyleSheet("background: #ece9d8; border-top: 1px solid #999;")
        l = QHBoxLayout(w)
        l.setContentsMargins(8, 2, 8, 2)
        self.status_words = QLabel("Words: 0")
        self.status_chars = QLabel("Characters: 0")
        self.status_pos = QLabel("Ln 1, Col 1")
        self.status_saved = QLabel("")
        for lbl in (self.status_words, self.status_chars, self.status_pos):
            lbl.setStyleSheet("font-size: 11px; color: #333;")
        self.status_saved.setStyleSheet("font-size: 11px; color: #2d5c1f;")
        l.addWidget(self.status_words)
        l.addWidget(self.status_chars)
        l.addWidget(self.status_pos)
        l.addStretch(1)
        l.addWidget(self.status_saved)
        return w

    # -- helpers -------------------------------------------------------------

    def _act(self, text, slot, shortcut=None):
        act = QAction(text, self)
        act.triggered.connect(slot)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        return act

    def _toggle_act(self, label, slot, bold=False, italic=False, underline=False):
        act = QAction(label, self)
        act.setCheckable(True)
        f = act.font()
        f.setBold(bold or f.bold())
        f.setItalic(italic)
        f.setUnderline(underline)
        act.setFont(f)
        act.triggered.connect(slot)
        return act

    def _set_font_size(self, text):
        try:
            self.editor.setFontPointSize(float(text))
        except ValueError:
            pass

    def _pick_color(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self.editor.textColor(), self, "Text Color")
        if color.isValid():
            self.editor.setTextColor(color)

    def _toggle_list(self, style):
        cursor = self.editor.textCursor()
        current = cursor.currentList()
        if current and current.format().style() == style:
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            cursor.setBlockFormat(block_fmt)
            current.remove(cursor.block())
        else:
            cursor.createList(style)

    def _sync_format_actions(self):
        fmt = self.editor.currentCharFormat()
        self.bold_act.setChecked(fmt.font().bold())
        self.italic_act.setChecked(fmt.fontItalic())
        self.underline_act.setChecked(fmt.fontUnderline())
        align = self.editor.alignment()
        self.align_left.setChecked(bool(align & Qt.AlignmentFlag.AlignLeft))
        self.align_center.setChecked(bool(align & Qt.AlignmentFlag.AlignCenter))
        self.align_right.setChecked(bool(align & Qt.AlignmentFlag.AlignRight))
        self.align_justify.setChecked(bool(align & Qt.AlignmentFlag.AlignJustify))

    def _update_status(self):
        text = self.editor.toPlainText()
        words = len(text.split())
        chars = len(text)
        cursor = self.editor.textCursor()
        self.status_words.setText(f"Words: {words}")
        self.status_chars.setText(f"Characters: {chars}")
        self.status_pos.setText(f"Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}")

    def _show_word_count(self):
        from PyQt6.QtWidgets import QMessageBox
        text = self.editor.toPlainText()
        words = len(text.split())
        chars = len(text)
        chars_no_space = len(text.replace(" ", "").replace("\n", ""))
        lines = text.count("\n") + 1
        QMessageBox.information(
            self, "Word Count",
            f"Words: {words}\nCharacters (with spaces): {chars}\n"
            f"Characters (no spaces): {chars_no_space}\nLines: {lines}",
        )

    def _clippy(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Clippy Enterprise Assistant",
            "It looks like you're writing a document.\n\nWould you like help embarrassing yourself?",
        )

    def _retitle(self, name):
        self.setWindowTitle(f"{name} - MacroHard Word")

    def _on_modified(self, modified):
        if modified:
            self.status_saved.setText("")

    # -- find / replace -------------------------------------------------------

    def show_find(self):
        self._open_find_dialog(replace=False)

    def show_replace(self):
        self._open_find_dialog(replace=True)

    def _open_find_dialog(self, replace):
        if self._find_dialog is not None:
            self._find_dialog.close()
        self._find_dialog = _FindReplaceDialog(self, replace=replace)
        self._find_dialog.show()
        self._find_dialog.raise_()

    def find_text(self, text, backward=False):
        if not text:
            return False
        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        found = self.editor.find(text, flags)
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(
                QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start
            )
            self.editor.setTextCursor(cursor)
            found = self.editor.find(text, flags)
        return found

    def replace_current(self, find_text_, replace_text):
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == find_text_:
            cursor.insertText(replace_text)
        self.find_text(find_text_)

    def replace_all(self, find_text_, replace_text):
        if not find_text_:
            return 0
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        count = 0
        while self.editor.find(find_text_):
            self.editor.textCursor().insertText(replace_text)
            count += 1
        return count

    # -- file operations -------------------------------------------------------

    def new_file(self):
        self.node_id = None
        self.editor.setHtml("")
        self.editor.document().setModified(False)
        self.setWindowTitle("Document1 - MacroHard Word")

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.RICH,), title="Open")
        if node_id:
            node = vfs_mod.vfs.get(node_id)
            self.node_id = node_id
            self.editor.setHtml(vfs_mod.vfs.read_content(node_id))
            self.editor.document().setModified(False)
            self._retitle(node.name)

    def save_file(self):
        if self.node_id:
            vfs_mod.vfs.write_content(self.node_id, self.editor.toHtml())
            self.editor.document().setModified(False)
            self._retitle(vfs_mod.vfs.get(self.node_id).name)
            self.status_saved.setText("Saved")
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
            node = vfs_mod.vfs._new(vfs_mod.RICH, name, folder_id)
            parent.children.append(node.id)
            vfs_mod.vfs.save()
            vfs_mod.vfs.write_content(node.id, content)
            self.node_id = node.id
        self.editor.document().setModified(False)
        self._retitle(vfs_mod.vfs.get(self.node_id).name)
        self.status_saved.setText("Saved")

    def _autosave(self):
        if self.node_id and self.editor.document().isModified():
            vfs_mod.vfs.write_content(self.node_id, self.editor.toHtml())
            self.editor.document().setModified(False)
            self.status_saved.setText("Autosaved")


class _FindReplaceDialog(QDialog):
    def __init__(self, owner: MWordWindow, replace: bool):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Replace" if replace else "Find")
        self.setModal(False)

        layout = QVBoxLayout(self)

        find_row = QHBoxLayout()
        find_row.addWidget(QLabel("Find what:"))
        self.find_edit = QLineEdit()
        find_row.addWidget(self.find_edit)
        layout.addLayout(find_row)

        self.replace_edit = None
        if replace:
            replace_row = QHBoxLayout()
            replace_row.addWidget(QLabel("Replace with:"))
            self.replace_edit = QLineEdit()
            replace_row.addWidget(self.replace_edit)
            layout.addLayout(replace_row)

        btn_row = QHBoxLayout()
        find_next_btn = QPushButton("Find Next")
        find_next_btn.clicked.connect(self._find_next)
        btn_row.addWidget(find_next_btn)

        if replace:
            replace_btn = QPushButton("Replace")
            replace_btn.clicked.connect(self._replace)
            btn_row.addWidget(replace_btn)

            replace_all_btn = QPushButton("Replace All")
            replace_all_btn.clicked.connect(self._replace_all)
            btn_row.addWidget(replace_all_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.find_edit.returnPressed.connect(self._find_next)
        self.find_edit.setFocus()

    def _find_next(self):
        if not self.owner.find_text(self.find_edit.text()):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "MacroHard Word", "Finished searching the document.")

    def _replace(self):
        self.owner.replace_current(self.find_edit.text(), self.replace_edit.text())

    def _replace_all(self):
        count = self.owner.replace_all(self.find_edit.text(), self.replace_edit.text())
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "MacroHard Word", f"Replaced {count} occurrence(s).")
