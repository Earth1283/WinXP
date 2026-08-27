from __future__ import annotations

from PyQt6.QtCore import QBuffer, QIODevice, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction, QActionGroup, QColor, QFont, QKeySequence, QTextCharFormat, QTextCursor,
    QTextDocument, QTextListFormat,
)
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFontComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
    QToolBar, QVBoxLayout, QWidget,
)

from .. import theme, vfs as vfs_mod
from ..color_dialog import XPColorDialog
from ..vfs_dialog import VfsFileDialog
from ..window_manager import XPWindow
from ..xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame

BRAND_GREEN = "#2d5c1f"
AUTOSAVE_MS = 20_000


def _image_to_html(image) -> str:
    """Embed a QImage as a base64 data URI so it survives toHtml()/setHtml()
    round trips -- QTextCursor.insertImage() alone only registers an in-memory
    resource-cache key that doesn't exist anymore once the HTML is reloaded."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    b64 = bytes(buffer.data().toBase64()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" width="{image.width()}" height="{image.height()}">'


class MWordWindow(XPWindow):
    """MacroHard Word -- a shameless, embarrassingly overboard WordPad clone."""

    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Document1 - MacroHard Word", icon_key="mword", size=QSize(700, 520))
        self.node_id = node_id
        self._find_dialog = None
        self._support_dialog = None
        self._zoom_steps = 0
        self._autocorrect_enabled = True
        self._autocorrecting = False

        self.editor = QTextEdit()
        self.editor.setStyleSheet("background: white; border: none;")
        self.editor.setFont(QFont("Times New Roman", 12))
        self.editor.cursorPositionChanged.connect(self._sync_format_actions)
        self.editor.cursorPositionChanged.connect(self._update_status)
        self.editor.textChanged.connect(self._update_status)
        self.editor.textChanged.connect(self._autocorrect_check)
        self.editor.document().modificationChanged.connect(self._on_modified)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setMenuBar(self._build_menu())
        layout.addWidget(self._build_banner())
        self.toolbar = self._build_toolbar()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.editor, 1)
        self.status_bar_widget = self._build_status_bar()
        layout.addWidget(self.status_bar_widget)
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

        view_menu = bar.addMenu("&View")
        view_menu.addAction(self._act("Zoom &In", self._zoom_in, QKeySequence.StandardKey.ZoomIn))
        view_menu.addAction(self._act("Zoom &Out", self._zoom_out, QKeySequence.StandardKey.ZoomOut))
        view_menu.addAction(self._act("&Reset Zoom", self._zoom_reset, "Ctrl+0"))
        view_menu.addSeparator()
        view_menu.addAction(self._act("Formatting &Toolbar", self._toggle_toolbar, checkable=True, checked=True))
        view_menu.addAction(self._act("&Status Bar", self._toggle_statusbar, checkable=True, checked=True))

        insert_menu = bar.addMenu("&Insert")
        insert_menu.addAction(self._act("&Date", self._insert_date))
        insert_menu.addAction(self._act("Date and &Time", self._insert_datetime))
        insert_menu.addSeparator()
        insert_menu.addAction(self._act("&Horizontal Line", self._insert_hr))
        insert_menu.addAction(self._act("Page &Break", self._insert_page_break))
        symbol_menu = insert_menu.addMenu("&Symbol")
        for sym in ["©", "®", "™", "→", "•", "★", "§", "¶"]:
            symbol_menu.addAction(self._act(sym, lambda checked=False, s=sym: self._insert_symbol(s)))
        insert_menu.addSeparator()
        insert_menu.addAction(self._act("&WordArt (3D)...", self._insert_wordart))

        format_menu = bar.addMenu("F&ormat")
        self.strike_act = self._act(
            "&Strikethrough", lambda c: self.editor.setFontStrikeOut(c), checkable=True
        )
        self.super_act = self._act("Su&perscript", self._toggle_super, checkable=True)
        self.sub_act = self._act("Su&bscript", self._toggle_sub, checkable=True)
        format_menu.addAction(self.strike_act)
        format_menu.addAction(self.super_act)
        format_menu.addAction(self.sub_act)
        format_menu.addSeparator()
        format_menu.addAction(self._act("&Increase Indent", self._increase_indent))
        format_menu.addAction(self._act("&Decrease Indent", self._decrease_indent))
        format_menu.addSeparator()
        format_menu.addAction(self._act("&Highlight Color...", self._pick_highlight))
        format_menu.addAction(self._act("&Clear Formatting", self._clear_formatting, "Ctrl+Space"))
        format_menu.addSeparator()
        format_menu.addAction(self._act("&Word Wrap...", self._word_wrap))

        tools_menu = bar.addMenu("&Tools")
        self.autocorrect_act = self._act(
            "Auto&Correct as You Type", self._toggle_autocorrect, checkable=True, checked=True
        )
        tools_menu.addAction(self.autocorrect_act)
        tools_menu.addSeparator()
        tools_menu.addAction(self._act("&Word Count...", self._show_word_count))
        tools_menu.addAction(self._act("&Clippy Enterprise Assistant...", self._clippy))
        tools_menu.addAction(self._act("&Macro Recorder...", self._macro_recorder))

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self._act("MacroHard Word &Help", self._help_topics, "F1"))
        help_menu.addAction(self._act("Check for &Updates...", self._check_updates))
        help_menu.addSeparator()
        help_menu.addAction(self._act("&Get Help From Support...", self._get_support))
        help_menu.addSeparator()
        help_menu.addAction(self._act("&About MacroHard Word...", self._about))
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

    def _act(self, text, slot, shortcut=None, checkable=False, checked=False):
        act = QAction(text, self)
        if checkable:
            act.setCheckable(True)
            act.setChecked(checked)
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
        color = XPColorDialog.get_color(self, self.editor.textColor())
        if color is not None:
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
        text = self.editor.toPlainText()
        words = len(text.split())
        chars = len(text)
        chars_no_space = len(text.replace(" ", "").replace("\n", ""))
        lines = text.count("\n") + 1
        XPMessageBox.information(
            self, "Word Count",
            f"Words: {words}\nCharacters (with spaces): {chars}\n"
            f"Characters (no spaces): {chars_no_space}\nLines: {lines}",
        )

    def _insert_wordart(self):
        from .wordart_3d import WordArt3DDialog
        dialog = WordArt3DDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_image is not None:
            cursor = self.editor.textCursor()
            cursor.insertHtml(_image_to_html(dialog.result_image))
            self.editor.setTextCursor(cursor)

    # -- view -----------------------------------------------------------------

    def _zoom_in(self):
        self.editor.zoomIn(1)
        self._zoom_steps += 1

    def _zoom_out(self):
        self.editor.zoomOut(1)
        self._zoom_steps -= 1

    def _zoom_reset(self):
        if self._zoom_steps > 0:
            self.editor.zoomOut(self._zoom_steps)
        elif self._zoom_steps < 0:
            self.editor.zoomIn(-self._zoom_steps)
        self._zoom_steps = 0

    def _toggle_toolbar(self, checked):
        self.toolbar.setVisible(checked)

    def _toggle_statusbar(self, checked):
        self.status_bar_widget.setVisible(checked)

    # -- insert -----------------------------------------------------------------

    def _insert_date(self):
        from datetime import date
        self.editor.insertPlainText(date.today().strftime("%B %d, %Y"))

    def _insert_datetime(self):
        from datetime import datetime
        self.editor.insertPlainText(datetime.now().strftime("%B %d, %Y %I:%M %p"))

    def _insert_hr(self):
        self.editor.insertHtml("<hr>")

    def _insert_page_break(self):
        self.editor.insertHtml(
            '<div style="border-top:2px dashed #999; margin:14px 0; padding-top:4px; '
            'color:#999; font-size:10px;">-- Page Break --</div>'
        )

    def _insert_symbol(self, symbol):
        self.editor.insertPlainText(symbol)

    # -- format -----------------------------------------------------------------

    def _toggle_super(self, checked):
        if checked:
            self.sub_act.blockSignals(True)
            self.sub_act.setChecked(False)
            self.sub_act.blockSignals(False)
        self._apply_vertical_align()

    def _toggle_sub(self, checked):
        if checked:
            self.super_act.blockSignals(True)
            self.super_act.setChecked(False)
            self.super_act.blockSignals(False)
        self._apply_vertical_align()

    def _apply_vertical_align(self):
        fmt = QTextCharFormat()
        if self.super_act.isChecked():
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSuperScript)
        elif self.sub_act.isChecked():
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSubScript)
        else:
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignNormal)
        self.editor.mergeCurrentCharFormat(fmt)

    def _increase_indent(self):
        cursor = self.editor.textCursor()
        fmt = cursor.blockFormat()
        fmt.setIndent(fmt.indent() + 1)
        cursor.setBlockFormat(fmt)

    def _decrease_indent(self):
        cursor = self.editor.textCursor()
        fmt = cursor.blockFormat()
        fmt.setIndent(max(0, fmt.indent() - 1))
        cursor.setBlockFormat(fmt)

    def _pick_highlight(self):
        color = XPColorDialog.get_color(self, self.editor.textBackgroundColor())
        if color is not None:
            self.editor.setTextBackgroundColor(color)

    def _clear_formatting(self):
        empty = QTextCharFormat()
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.setCharFormat(empty)
        self.editor.setCurrentCharFormat(empty)

    def _word_wrap(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText().replace("\u2029", " ")
            fmt_cursor = QTextCursor(self.editor.document())
            fmt_cursor.setPosition(cursor.selectionStart())
            fmt_cursor.setPosition(cursor.selectionStart() + 1, QTextCursor.MoveMode.KeepAnchor)
            fmt = fmt_cursor.charFormat()
        else:
            block = cursor.block()
            text = block.text()
            fmt_cursor = QTextCursor(block)
            fmt = fmt_cursor.charFormat()

        text = text.strip()
        if not text:
            XPMessageBox.warning(self, "MacroHard Word", "There's no paragraph here to wrap.")
            return

        font = fmt.font()
        brush = fmt.foreground()
        color = brush.color() if brush.style() != Qt.BrushStyle.NoBrush else QColor("black")

        from .word_wrap import render_word_wrap
        image = render_word_wrap(text, font, color)
        insert_cursor = self.editor.textCursor()
        insert_cursor.insertHtml(_image_to_html(image))
        self.editor.setTextCursor(insert_cursor)
        XPMessageBox.information(self, "Word Wrap", "This paragraph has been word wrapped.")

    # -- tools -----------------------------------------------------------------

    AUTOCORRECT_MAP = {
        "teh": "the", "adn": "and", "recieve": "receive", "seperate": "separate",
        "definately": "definitely", "occured": "occurred", "wierd": "weird",
        "thier": "their", "alot": "a lot", "wich": "which",
    }

    def _toggle_autocorrect(self, checked):
        self._autocorrect_enabled = checked

    def _autocorrect_check(self):
        if not self._autocorrect_enabled or self._autocorrecting:
            return
        cursor = self.editor.textCursor()
        pos = cursor.position()
        if pos == 0:
            return
        text_before = self.editor.document().toPlainText()[:pos]
        if not text_before or text_before[-1] not in " \n\t.,!?;:":
            return
        trimmed = text_before[:-1]
        words = trimmed.split()
        if not words:
            return
        word = words[-1]
        replacement = self.AUTOCORRECT_MAP.get(word.lower())
        if replacement is None:
            return
        if word[0].isupper():
            replacement = replacement.capitalize()
        start = pos - 1 - len(word)
        self._autocorrecting = True
        fix_cursor = self.editor.textCursor()
        fix_cursor.setPosition(start)
        fix_cursor.setPosition(start + len(word), QTextCursor.MoveMode.KeepAnchor)
        fix_cursor.insertText(replacement)
        self._autocorrecting = False

    def _macro_recorder(self):
        XPMessageBox.information(
            self, "Macro Recorder",
            "MacroHard Legal has not yet approved end users running their own code "
            "on this software.\n\nRecording cancelled.",
        )

    # -- help -----------------------------------------------------------------

    def _help_topics(self):
        XPMessageBox.information(
            self, "MacroHard Word Help", "Have you tried Clippy?\n\n(That's it. That's the help.)"
        )

    def _check_updates(self):
        XPMessageBox.information(
            self, "MacroHard Update", "No updates found.\n\nYou are already embarrassingly overboard."
        )

    def _about(self):
        XPMessageBox.information(
            self, "About MacroHard Word",
            "MacroHard Word\nVersion 1.0 (Embarrassingly Overboard Edition)\n\n"
            "Not affiliated with any other software company, real or imagined.",
        )

    def _get_support(self):
        from .bofh_support import SupportChatDialog
        if self._support_dialog is not None:
            self._support_dialog.close()
        self._support_dialog = SupportChatDialog(self)
        self._support_dialog.show()
        self._support_dialog.raise_()

    def _clippy(self):
        XPMessageBox.information(
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
        super().__init__(owner, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.owner = owner
        self.setModal(False)

        inner = build_dialog_frame(self, "Replace" if replace else "Find")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        inner.addWidget(body)

        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 10, 12, 10)

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
            XPMessageBox.information(self, "MacroHard Word", "Finished searching the document.")

    def _replace(self):
        self.owner.replace_current(self.find_edit.text(), self.replace_edit.text())

    def _replace_all(self):
        count = self.owner.replace_all(self.find_edit.text(), self.replace_edit.text())
        XPMessageBox.information(self, "MacroHard Word", f"Replaced {count} occurrence(s).")
