"""MacroHard Office Word 2003 -- the application window.

Layout follows Word 2003 exactly: menu bar, Standard toolbar, Formatting
toolbar, horizontal ruler, then the vertical ruler and the document surface
with the task pane docked right, and the status bar underneath carrying the
page/section readout and the REC TRK EXT OVR indicators.

The document itself is a real paginated QTextDocument (see pageview.py), so
page counts, the "At" measurement, Print Preview and the printed output all
come from one source of truth instead of being faked separately.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from PyQt6.QtCore import QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction, QActionGroup, QColor, QFont, QKeySequence, QTextBlockFormat,
    QTextCharFormat, QTextCursor, QTextDocument, QTextFrameFormat, QTextLength,
    QTextListFormat, QTextTableFormat,
)
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFontComboBox, QHBoxLayout, QLabel, QMenu, QMenuBar,
    QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from ... import theme, vfs as vfs_mod
from ...vfs_dialog import VfsFileDialog
from ...window_manager import XPWindow
from ...xp_dialog import XPMessageBox
from . import dialogs as dlg, more_dialogs as mdlg, mw_icons, spelling as spell_mod
from .assistant import OfficeAssistant
from .model import (
    BUILTIN_STYLES, DocumentProperties, STYLES_BY_NAME, STYLE_PROPERTY, fmt_measure,
    inches, settings,
)
from .pageview import HorizontalRuler, PageTextEdit, VerticalRuler
from .printpreview import PrintPreview
from .splash import AboutDialog, SplashScreen
from .taskpane import TaskPane
from .widgets import (
    HIGHLIGHT_COLORS, TOOLBAR_QSS, ColorPickerButton, toolbar_button,
)

PROPS_MARKER = "<!--MWPROPS "
PROPS_RE = re.compile(r"<!--MWPROPS (.*?)-->", re.DOTALL)

STATUS_QSS = """
QWidget#statusBar { background: #ece9d8; border-top: 1px solid #aca998; }
QLabel { background: transparent; font-size: 11px; color: #1a1a1a; }
QLabel#dim { color: #9a9a9a; }
"""

_splash_shown = False


class MWordWindow(XPWindow):
    """MacroHard Office Word 2003, Professional Edition."""

    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Document1 - MacroHard Word",
                         icon_key="mword", size=QSize(940, 700))
        global _splash_shown
        if not _splash_shown:
            SplashScreen(self).exec()
            _splash_shown = True

        self.node_id = node_id
        self.doc_props = DocumentProperties(
            author="MacroHard User",
            created=datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p"))
        self.checker = spell_mod.SpellChecker()
        self.clipboard_items: list[str] = []
        self._find_dialog = None
        self._support_dialog = None
        self._loading = False
        self._autocorrecting = False
        self._painter_format: QTextCharFormat | None = None
        self._painter_sticky = False
        self._issue_cursor = 0
        self._doc_number = 1
        self._track_changes = False
        self._recording = False
        self._extend = False
        self._tab_type = "Left"
        self._preview_widget = None

        self.editor = PageTextEdit(self)
        self.editor.setFont(QFont("Times New Roman", 12))
        self.editor.cursorPositionChanged.connect(self._on_cursor_moved)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.selectionChanged.connect(self._sync_reveal)
        self.editor.document().modificationChanged.connect(self._on_modified)
        self.editor.document().contentsChange.connect(self._on_contents_change)
        self.editor.zoom_changed.connect(self._on_zoom_changed)
        self.editor.verticalScrollBar().valueChanged.connect(self._on_scrolled)
        self.editor.horizontalScrollBar().valueChanged.connect(lambda _: self.sync_ruler())

        self.highlighter = spell_mod.WordHighlighter(self.editor.document(), self.checker)

        self._build_ui()
        self.apply_options()
        self._apply_style_to_cursor("Normal", whole_paragraph=False)

        if node_id:
            self._load_node(node_id)
        else:
            self._retitle("Document1")

        self.assistant = OfficeAssistant(self)
        self.assistant.choice_made.connect(self._assistant_choice)
        if settings.options.get("assistant_enabled", True):
            QTimer.singleShot(700, self._greet)
        else:
            self.assistant.hide()

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave)
        self._restart_autosave()

        self._edit_clock = QTimer(self)
        self._edit_clock.timeout.connect(self._tick_editing_time)
        self._edit_clock.start(60_000)

        QTimer.singleShot(0, self._first_layout)

    # ================================================================= build

    def _build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setMenuBar(self._build_menu())

        self.standard_bar = self._build_standard_toolbar()
        self.formatting_bar = self._build_formatting_toolbar()
        root.addWidget(self.standard_bar)
        root.addWidget(self.formatting_bar)

        # The ruler has to live inside the document column, not across the whole
        # window: its x axis must agree with the editor's viewport exactly, so
        # it sits to the right of the vertical ruler and stops short of the
        # scroll bar, the same way Word's does.
        self.ruler = HorizontalRuler(self, self.editor)
        ruler_row = QWidget()
        ruler_row.setStyleSheet("background: #c9c6b8;")
        ruler_layout = QHBoxLayout(ruler_row)
        ruler_layout.setContentsMargins(0, 0, 0, 0)
        ruler_layout.setSpacing(0)
        self.ruler_corner = QWidget()
        self.ruler_corner.setFixedSize(VerticalRuler.WIDTH, HorizontalRuler.HEIGHT)
        self.ruler_corner.setStyleSheet("background: #c9c6b8; border-right: 1px solid #8a8778;")
        ruler_layout.addWidget(self.ruler_corner)
        ruler_layout.addWidget(self.ruler, 1)
        self.ruler_gap = QWidget()
        self.ruler_gap.setFixedWidth(self.editor.verticalScrollBar().sizeHint().width())
        self.ruler_gap.setStyleSheet("background: #ece9d8;")
        ruler_layout.addWidget(self.ruler_gap)
        self.ruler_row = ruler_row

        editor_row = QWidget()
        editor_layout = QHBoxLayout(editor_row)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        self.vruler = VerticalRuler(self, self.editor)
        editor_layout.addWidget(self.vruler)
        editor_layout.addWidget(self.editor, 1)

        document_column = QVBoxLayout()
        document_column.setContentsMargins(0, 0, 0, 0)
        document_column.setSpacing(0)
        document_column.addWidget(ruler_row)
        document_column.addWidget(editor_row, 1)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addLayout(document_column, 1)
        self.task_pane = TaskPane(self)
        self.task_pane.closed.connect(lambda: self._toggle_task_pane(False))
        body_layout.addWidget(self.task_pane)

        self.stack = QStackedWidget()
        self.stack.addWidget(body)
        root.addWidget(self.stack, 1)
        self.document_body = body

        self.status_bar = self._build_status_bar()
        root.addWidget(self.status_bar)
        self.set_content_layout(root)

    def _first_layout(self):
        self.editor.relayout()
        self.sync_ruler()
        self._update_status()

    # ------------------------------------------------------------- menu bar

    def _act(self, menu, text, slot=None, shortcut=None, icon=None, checkable=False,
             checked=False, enabled=True):
        action = QAction(text, self)
        if icon:
            action.setIcon(mw_icons.icon(icon, 16))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.setEnabled(enabled)
        action.triggered.connect(slot if slot else
                                 (lambda _=False, t=text: self._not_implemented(t)))
        menu.addAction(action)
        self.addAction(action)
        return action

    def _not_implemented(self, label):
        clean = label.replace("&", "").rstrip(".")
        XPMessageBox.information(
            self, "MacroHard Word",
            f"This feature is not installed. To install {clean}, run Setup again "
            f"and choose Add or Remove Features.\n\n"
            f"Setup could not be located.")

    def _build_menu(self):
        bar = QMenuBar()
        theme.style_menubar(bar)

        # ---- File
        m = bar.addMenu("&File")
        self._act(m, "&New...", self.new_file, "Ctrl+N", icon="new")
        self._act(m, "&Open...", self.open_file, "Ctrl+O", icon="open")
        self._act(m, "&Close", self.close_document)
        m.addSeparator()
        self._act(m, "&Save", self.save_file, "Ctrl+S", icon="save")
        self._act(m, "Save &As...", self.save_file_as)
        self._act(m, "Save as Web Pa&ge...", self.save_as_web_page)
        self._act(m, "File Searc&h...")
        self._act(m, "Ver&sions...")
        m.addSeparator()
        self._act(m, "Web Page Pre&view")
        self._act(m, "Page Set&up...", self.page_setup)
        self._act(m, "Print Pre&view", self.print_preview, "Ctrl+F2", icon="print_preview")
        self._act(m, "&Print...", self.print_document, "Ctrl+P", icon="print")
        send = m.addMenu("Sen&d To")
        self._act(send, "Mail Recipient", self.mail_recipient, icon="mail")
        self._act(send, "Mail Recipient (for Review)...")
        self._act(send, "Fax Recipient...")
        m.addSeparator()
        self._act(m, "Propert&ies", self.show_properties)
        m.addSeparator()
        self.mru_separator = m.addSeparator()
        self.file_menu = m
        self._mru_actions: list[QAction] = []
        self._rebuild_mru()
        self._act(m, "E&xit", self.close)

        # ---- Edit
        m = bar.addMenu("&Edit")
        self.undo_act = self._act(m, "&Undo", self.editor.undo, "Ctrl+Z", icon="undo")
        self.redo_act = self._act(m, "&Redo", self.editor.redo, "Ctrl+Y", icon="redo")
        self.undo_act.setEnabled(False)
        self.redo_act.setEnabled(False)
        self.editor.document().undoAvailable.connect(self.undo_act.setEnabled)
        self.editor.document().redoAvailable.connect(self.redo_act.setEnabled)
        m.addSeparator()
        self._act(m, "Cu&t", self.cut, "Ctrl+X", icon="cut")
        self._act(m, "&Copy", self.copy, "Ctrl+C", icon="copy")
        self._act(m, "Office Clip&board...",
                  lambda: self.show_task_pane("Clipboard"), icon="paste")
        self._act(m, "&Paste", self.editor.paste, "Ctrl+V", icon="paste")
        self._act(m, "Paste &Special...", self.paste_special)
        self._act(m, "Paste as &Hyperlink", self.paste_as_hyperlink)
        clear = m.addMenu("Cle&ar")
        self._act(clear, "Formats", self.clear_formatting)
        self._act(clear, "Contents", lambda: self.editor.textCursor().removeSelectedText())
        self._act(m, "Select A&ll", self.editor.selectAll, "Ctrl+A")
        m.addSeparator()
        self._act(m, "&Find...", lambda: self.show_find(0), "Ctrl+F")
        self._act(m, "R&eplace...", lambda: self.show_find(1), "Ctrl+H")
        self._act(m, "&Go To...", lambda: self.show_find(2), "Ctrl+G")
        m.addSeparator()
        self._act(m, "Lin&ks...")
        self._act(m, "&Object")

        # ---- View
        m = bar.addMenu("&View")
        self.view_group = QActionGroup(self)
        for label, mode in (("&Normal", "normal"), ("&Web Layout", "web"),
                            ("&Print Layout", "print"), ("Reading La&yout", "reading"),
                            ("&Outline", "outline")):
            action = self._act(m, label, lambda _=False, v=mode: self.set_view_mode(v),
                               checkable=True, checked=(mode == "print"))
            self.view_group.addAction(action)
        m.addSeparator()
        self.task_pane_act = self._act(m, "Tas&k Pane", self._toggle_task_pane, "Ctrl+F1",
                                       checkable=True, checked=True)
        toolbars = m.addMenu("&Toolbars")
        self.standard_act = self._act(toolbars, "Standard", self._toggle_standard,
                                      checkable=True, checked=True)
        self.formatting_act = self._act(toolbars, "Formatting", self._toggle_formatting,
                                        checkable=True, checked=True)
        for name in ("AutoText", "Control Toolbox", "Database", "Drawing", "Forms",
                     "Frames", "Mail Merge", "Outlining", "Picture", "Reviewing",
                     "Tables and Borders", "Web", "WordArt"):
            self._act(toolbars, name, checkable=True)
        toolbars.addSeparator()
        self._act(toolbars, "&Customize...")
        self.ruler_act = self._act(m, "&Ruler", self._toggle_ruler,
                                   checkable=True, checked=True)
        self._act(m, "Document &Map", lambda: self.show_task_pane("Reveal Formatting"),
                  icon="doc_map")
        self._act(m, "T&humbnails")
        m.addSeparator()
        self._act(m, "&Header and Footer", self.header_and_footer)
        self._act(m, "Foot&notes")
        self._act(m, "Mar&kup", checkable=True)
        self._act(m, "&Full Screen", self.full_screen)
        self._act(m, "&Zoom...", self.zoom_dialog, icon="zoom")

        # ---- Insert
        m = bar.addMenu("&Insert")
        self._act(m, "&Break...", self.insert_break, icon="break")
        self._act(m, "Page N&umbers...", self.insert_page_numbers)
        self._act(m, "&Date and Time...", self.insert_date_time, icon="date")
        autotext = m.addMenu("&AutoText")
        self._act(autotext, "AutoText...")
        for entry in ("Sincerely,", "Best regards,", "To Whom It May Concern:",
                      "CONFIDENTIAL", "Page X of Y"):
            self._act(autotext, entry,
                      lambda _=False, e=entry: self.editor.insertPlainText(e))
        self._act(m, "&Field...")
        self._act(m, "&Symbol...", self.insert_symbol, icon="symbol")
        self._act(m, "Co&mment", self.insert_comment)
        reference = m.addMenu("&Reference")
        for entry in ("Footnote...", "Caption...", "Cross-reference...", "Index and Tables..."):
            self._act(reference, entry)
        m.addSeparator()
        picture = m.addMenu("&Picture")
        self._act(picture, "&Clip Art...")
        self._act(picture, "&From File...", self.insert_picture, icon="picture")
        self._act(picture, "&AutoShapes")
        self._act(picture, "&WordArt (3D)...", self.insert_wordart, icon="wordart")
        self._act(picture, "C&hart")
        self._act(m, "Dia&gram...")
        self._act(m, "Te&xt Box", self.insert_text_box, icon="textbox")
        self._act(m, "F&ile...")
        self._act(m, "&Object...")
        m.addSeparator()
        self._act(m, "Book&mark...")
        self._act(m, "H&yperlink...", self.insert_hyperlink, "Ctrl+K", icon="hyperlink")

        # ---- Format
        m = bar.addMenu("F&ormat")
        self._act(m, "&Font...", self.font_dialog, "Ctrl+D")
        self._act(m, "&Paragraph...", self.paragraph_dialog)
        self._act(m, "Bullets and &Numbering...", self.bullets_dialog, icon="bullets")
        self._act(m, "&Borders and Shading...", self.borders_dialog, icon="borders")
        self._act(m, "&Columns...", self.columns_dialog, icon="columns")
        self._act(m, "&Tabs...", self.open_tabs_dialog)
        self._act(m, "&Drop Cap...", self.drop_cap_dialog)
        self._act(m, "Te&xt Direction...")
        self._act(m, "Change Cas&e...", self.change_case_dialog)
        m.addSeparator()
        background = m.addMenu("Bac&kground")
        self._act(background, "No Fill", lambda: self.set_background(None))
        for name, value in (("Light Yellow", "#ffffcc"), ("Pale Blue", "#dceaf7"),
                            ("Light Green", "#e6f2e0"), ("Parchment", "#f5f0e1")):
            self._act(background, name, lambda _=False, v=value: self.set_background(v))
        self._act(m, "T&heme...")
        frames = m.addMenu("F&rames")
        self._act(frames, "New Frames Page")
        self._act(m, "&AutoFormat...", self.autoformat_document)
        self._act(m, "&Styles and Formatting...",
                  lambda: self.show_task_pane("Styles and Formatting"), icon="styles")
        self._act(m, "&Reveal Formatting...",
                  lambda: self.show_task_pane("Reveal Formatting"), "Shift+F1")
        m.addSeparator()
        self._act(m, "&Word Wrap...", self.word_wrap)

        # ---- Tools
        m = bar.addMenu("&Tools")
        self._act(m, "&Spelling and Grammar...", self.spelling_and_grammar, "F7",
                  icon="spelling")
        self._act(m, "&Research...", self.research, "Alt+Click", icon="research")
        language = m.addMenu("&Language")
        self._act(language, "Set Language...")
        self._act(language, "Translate...")
        self._act(language, "Thesaurus...", self.thesaurus, "Shift+F7")
        self._act(language, "Hyphenation...")
        self._act(m, "&Word Count...", self.word_count)
        self._act(m, "AutoSu&mmarize...", self.autosummarize)
        self._act(m, "Spee&ch")
        m.addSeparator()
        self._act(m, "Shared Work&space...")
        self.track_act = self._act(m, "Track Chan&ges", self.toggle_track_changes,
                                   "Ctrl+Shift+E", icon="track_changes", checkable=True)
        self._act(m, "Compare and Merge Documents...")
        self._act(m, "&Protect Document...", self.protect_document)
        m.addSeparator()
        mailings = m.addMenu("Letters and &Mailings")
        self._act(mailings, "Mail Merge...")
        self._act(mailings, "Envelopes and Labels...")
        self._act(mailings, "Letter Wizard...", self.letter_wizard)
        macro = m.addMenu("Macr&o")
        self._act(macro, "Macros...", self.macros, "Alt+F8", icon="macro")
        self._act(macro, "Record New Macro...", self.record_macro)
        self._act(macro, "Security...")
        self._act(macro, "Visual Basic Editor", self.vb_editor, "Alt+F11")
        m.addSeparator()
        self._act(m, "&Templates and Add-Ins...")
        self._act(m, "&AutoCorrect Options...", self.autocorrect_options)
        self._act(m, "&Customize...")
        self._act(m, "&Options...", self.options_dialog, icon="options")

        # ---- Table
        m = bar.addMenu("T&able")
        self._act(m, "&Draw Table", self.insert_table, icon="tables_borders")
        insert = m.addMenu("&Insert")
        self._act(insert, "Table...", self.insert_table, icon="table")
        self._act(insert, "Columns to the Left",
                  lambda: self.table_insert("column", before=True))
        self._act(insert, "Columns to the Right",
                  lambda: self.table_insert("column", before=False))
        self._act(insert, "Rows Above", lambda: self.table_insert("row", before=True))
        self._act(insert, "Rows Below", lambda: self.table_insert("row", before=False))
        self._act(insert, "Cells...", lambda: self.table_insert("row", before=False))
        delete = m.addMenu("&Delete")
        self._act(delete, "Table", lambda: self.table_delete("table"))
        self._act(delete, "Columns", lambda: self.table_delete("column"))
        self._act(delete, "Rows", lambda: self.table_delete("row"))
        self._act(delete, "Cells...", lambda: self.table_delete("row"))
        select = m.addMenu("Se&lect")
        self._act(select, "Table", lambda: self.table_select("table"))
        self._act(select, "Column", lambda: self.table_select("column"))
        self._act(select, "Row", lambda: self.table_select("row"))
        self._act(select, "Cell", lambda: self.table_select("cell"))
        m.addSeparator()
        self._act(m, "&Merge Cells", self.table_merge)
        self._act(m, "Split C&ells...", self.table_split)
        self._act(m, "Split &Table", self.table_split_table)
        m.addSeparator()
        self._act(m, "Table Auto&Format...", self.table_autoformat)
        autofit = m.addMenu("Auto&Fit")
        self._act(autofit, "AutoFit to Contents", lambda: self.table_autofit("contents"))
        self._act(autofit, "AutoFit to Window", lambda: self.table_autofit("window"))
        self._act(autofit, "Fixed Column Width", lambda: self.table_autofit("fixed"))
        self._act(m, "&Heading Rows Repeat", checkable=True)
        convert = m.addMenu("Con&vert")
        self._act(convert, "Text to Table...", self.text_to_table)
        self._act(convert, "Table to Text...", self.table_to_text)
        self._act(m, "&Sort...", self.table_sort)
        self._act(m, "F&ormula...", self.table_formula)
        self.gridlines_act = self._act(m, "Show &Gridlines", self.toggle_gridlines,
                                       checkable=True, checked=True)
        m.addSeparator()
        self._act(m, "Table P&roperties...", self.table_properties)

        # ---- Window
        m = bar.addMenu("&Window")
        self._act(m, "&New Window", self.new_window)
        self._act(m, "&Arrange All", self.arrange_all)
        self._act(m, "&Split")
        m.addSeparator()
        self.window_list_action = self._act(m, "&1 Document1", self.raise_and_activate,
                                            checkable=True, checked=True)

        # ---- Help
        m = bar.addMenu("&Help")
        self._act(m, "MacroHard Office Word &Help", self.help_contents, "F1", icon="help")
        self._act(m, "&Show the Office Assistant", self.show_assistant, icon="assistant")
        self._act(m, "MacroHard Office &Online", self.office_online)
        self._act(m, "&Contact Us", self.get_support)
        m.addSeparator()
        self._act(m, "&WordPerfect Help...", self.wordperfect_help)
        self._act(m, "Check for &Updates", self.check_updates)
        self._act(m, "&Detect and Repair...", self.detect_and_repair)
        self._act(m, "&Activate Product...", self.activate_product)
        m.addSeparator()
        self._act(m, "&About MacroHard Office Word", self.about)
        return bar

    def _rebuild_mru(self):
        for action in self._mru_actions:
            self.file_menu.removeAction(action)
        self._mru_actions.clear()
        for index, entry in enumerate(settings.recent(), start=1):
            action = QAction(f"&{index} {entry['name']}", self)
            action.triggered.connect(lambda _=False, e=entry: self.open_recent(e))
            self.file_menu.insertAction(self.mru_separator, action)
            self._mru_actions.append(action)
        if self._mru_actions:
            separator = QAction(self)
            separator.setSeparator(True)
            self.file_menu.insertAction(self.mru_separator, separator)
            self._mru_actions.append(separator)

    # ------------------------------------------------------------- toolbars

    def _toolbar_shell(self) -> tuple[QWidget, QHBoxLayout]:
        bar = QWidget()
        bar.setObjectName("mwToolbar")
        bar.setStyleSheet(TOOLBAR_QSS)
        bar.setFixedHeight(26)
        row = QHBoxLayout(bar)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(1)
        row.addWidget(self._gripper())
        return bar, row

    def _gripper(self) -> QWidget:
        """The dotted handle at the left of every Office toolbar."""
        grip = QWidget()
        grip.setFixedWidth(7)
        grip.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #ece9d8, stop:0.35 #ffffff, stop:0.5 #a0a0a0, stop:1 #ece9d8);")
        grip.setCursor(Qt.CursorShape.SizeAllCursor)
        return grip

    def _separator(self) -> QWidget:
        line = QWidget()
        line.setFixedWidth(6)
        line.setStyleSheet("background: transparent; border-left: 1px solid #b0ad9c;"
                           " margin: 3px 0px 3px 3px;")
        return line

    def _build_standard_toolbar(self):
        bar, row = self._toolbar_shell()
        for glyph, tip, slot in (
                ("new", "New Blank Document (Ctrl+N)", self.new_file),
                ("open", "Open (Ctrl+O)", self.open_file),
                ("save", "Save (Ctrl+S)", self.save_file),
                ("mail", "E-mail", self.mail_recipient),
                ("print", "Print (Ctrl+P)", self.print_now),
                ("print_preview", "Print Preview", self.print_preview),
                ("spelling", "Spelling and Grammar (F7)", self.spelling_and_grammar),
                ("research", "Research (Alt+Click)", self.research),
        ):
            row.addWidget(toolbar_button(glyph, tip, slot))
        row.addWidget(self._separator())
        for glyph, tip, slot in (
                ("cut", "Cut (Ctrl+X)", self.cut),
                ("copy", "Copy (Ctrl+C)", self.copy),
                ("paste", "Paste (Ctrl+V)", self.editor.paste),
        ):
            row.addWidget(toolbar_button(glyph, tip, slot))
        self.painter_btn = toolbar_button("format_painter", "Format Painter",
                                          self.toggle_format_painter, checkable=True)
        row.addWidget(self.painter_btn)
        row.addWidget(self._separator())
        row.addWidget(toolbar_button("undo", "Undo (Ctrl+Z)", self.editor.undo))
        row.addWidget(toolbar_button("redo", "Redo (Ctrl+Y)", self.editor.redo))
        row.addWidget(self._separator())
        for glyph, tip, slot in (
                ("hyperlink", "Insert Hyperlink (Ctrl+K)", self.insert_hyperlink),
                ("tables_borders", "Tables and Borders", self.borders_dialog),
                ("table", "Insert Table", self.insert_table_grid),
                ("columns", "Columns", self.columns_dialog),
                ("drawing", "Drawing", self.toggle_drawing_toolbar),
                ("doc_map", "Document Map", lambda: self.show_task_pane("Reveal Formatting")),
        ):
            row.addWidget(toolbar_button(glyph, tip, slot))
        self.marks_btn = toolbar_button("para_marks", "Show/Hide ¶ (Ctrl+*)",
                                        self.toggle_formatting_marks, checkable=True)
        row.addWidget(self.marks_btn)
        row.addWidget(self._separator())

        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.addItems(["500%", "200%", "150%", "100%", "75%", "50%", "25%",
                                  "10%", "Page Width", "Text Width", "Whole Page",
                                  "Two Pages"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setFixedWidth(74)
        self.zoom_combo.setToolTip("Zoom")
        self.zoom_combo.activated.connect(self._zoom_from_combo)
        self.zoom_combo.lineEdit().returnPressed.connect(
            lambda: self._zoom_from_combo(-1))
        row.addWidget(self.zoom_combo)
        row.addWidget(toolbar_button("help", "MacroHard Office Word Help",
                                     self.help_contents))
        row.addStretch(1)
        row.addWidget(self._overflow_button("Standard"))
        return bar

    def _build_formatting_toolbar(self):
        bar, row = self._toolbar_shell()
        row.addWidget(toolbar_button("styles", "Styles and Formatting",
                                     lambda: self.show_task_pane("Styles and Formatting")))

        self.style_combo = QComboBox()
        self.style_combo.setFixedWidth(120)
        self.style_combo.setToolTip("Style")
        for style in BUILTIN_STYLES:
            self.style_combo.addItem(style.name)
        self.style_combo.activated.connect(
            lambda _: self.apply_style(self.style_combo.currentText()))
        row.addWidget(self.style_combo)

        self.font_combo = QFontComboBox()
        self.font_combo.setFixedWidth(140)
        self.font_combo.setToolTip("Font")
        self.font_combo.setCurrentFont(QFont("Times New Roman"))
        self.font_combo.activated.connect(
            lambda _: self.set_font_family(self.font_combo.currentFont().family()))
        row.addWidget(self.font_combo)

        self.size_combo = QComboBox()
        self.size_combo.setEditable(True)
        self.size_combo.setFixedWidth(46)
        self.size_combo.setToolTip("Font Size")
        self.size_combo.addItems(dlg.FONT_SIZES)
        self.size_combo.setCurrentText("12")
        self.size_combo.activated.connect(
            lambda _: self.set_font_size(self.size_combo.currentText()))
        self.size_combo.lineEdit().returnPressed.connect(
            lambda: self.set_font_size(self.size_combo.currentText()))
        row.addWidget(self.size_combo)
        row.addWidget(self._separator())

        self.bold_btn = toolbar_button("bold", "Bold (Ctrl+B)", self.set_bold, checkable=True)
        self.italic_btn = toolbar_button("italic", "Italic (Ctrl+I)", self.set_italic,
                                         checkable=True)
        self.underline_btn = toolbar_button("underline", "Underline (Ctrl+U)",
                                            self.set_underline, checkable=True)
        for btn in (self.bold_btn, self.italic_btn, self.underline_btn):
            row.addWidget(btn)
        row.addWidget(self._separator())

        self.align_buttons = {}
        for glyph, tip, flag, shortcut in (
                ("align_left", "Align Left", Qt.AlignmentFlag.AlignLeft, "Ctrl+L"),
                ("align_center", "Center", Qt.AlignmentFlag.AlignHCenter, "Ctrl+E"),
                ("align_right", "Align Right", Qt.AlignmentFlag.AlignRight, "Ctrl+R"),
                ("align_justify", "Justify", Qt.AlignmentFlag.AlignJustify, "Ctrl+J"),
        ):
            btn = toolbar_button(glyph, f"{tip} ({shortcut})", None, checkable=True)
            btn.clicked.connect(lambda _=False, f=flag: self.set_alignment(f))
            self.align_buttons[flag] = btn
            row.addWidget(btn)
        row.addWidget(self._separator())

        spacing_btn = QToolButton()
        spacing_btn.setIcon(mw_icons.icon("line_spacing", 16))
        spacing_btn.setIconSize(QSize(16, 16))
        spacing_btn.setFixedSize(QSize(26, 22))
        spacing_btn.setToolTip("Line Spacing")
        spacing_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(spacing_btn)
        menu.setStyleSheet(theme.MENU_QSS)
        for label, value in (("1.0", 100), ("1.5", 150), ("2.0", 200),
                             ("2.5", 250), ("3.0", 300)):
            action = QAction(label, menu)
            action.triggered.connect(lambda _=False, v=value: self.set_line_spacing(v))
            menu.addAction(action)
        menu.addSeparator()
        more = QAction("More...", menu)
        more.triggered.connect(self.paragraph_dialog)
        menu.addAction(more)
        spacing_btn.setMenu(menu)
        row.addWidget(spacing_btn)

        row.addWidget(toolbar_button("numbering", "Numbering",
                                     lambda: self.toggle_list(QTextListFormat.Style.ListDecimal)))
        row.addWidget(toolbar_button("bullets", "Bullets",
                                     lambda: self.toggle_list(QTextListFormat.Style.ListDisc)))
        row.addWidget(toolbar_button("indent_less", "Decrease Indent", self.decrease_indent))
        row.addWidget(toolbar_button("indent_more", "Increase Indent", self.increase_indent))
        row.addWidget(self._separator())

        borders_btn = toolbar_button("borders", "Outside Border", self.borders_dialog)
        row.addWidget(borders_btn)
        self.highlight_btn = ColorPickerButton(
            "highlight", QColor("#ffff00"), automatic_label="None",
            automatic_color=QColor(), colors=HIGHLIGHT_COLORS, tooltip="Highlight")
        self.highlight_btn.color_selected.connect(self.set_highlight)
        row.addWidget(self.highlight_btn)
        self.font_color_btn = ColorPickerButton(
            "font_color", QColor("#c00000"), tooltip="Font Color")
        self.font_color_btn.color_selected.connect(self.set_font_color)
        row.addWidget(self.font_color_btn)
        row.addStretch(1)
        row.addWidget(self._overflow_button("Formatting"))
        return bar

    def _overflow_button(self, which: str) -> QToolButton:
        """The » chevron Office puts at the end of a docked toolbar."""
        btn = QToolButton()
        btn.setText("»")
        btn.setFixedSize(QSize(14, 22))
        btn.setToolTip("Toolbar Options")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(btn)
        menu.setStyleSheet(theme.MENU_QSS)
        action = QAction("Show Buttons on Two Rows", menu)
        action.setEnabled(False)
        menu.addAction(action)
        menu.addSeparator()
        add_remove = menu.addMenu("Add or Remove Buttons")
        for name in (which, "Customize..."):
            entry = QAction(name, add_remove)
            entry.triggered.connect(lambda _=False, n=name: self._not_implemented(n))
            add_remove.addAction(entry)
        btn.setMenu(menu)
        return btn

    # ----------------------------------------------------------- status bar

    def _build_status_bar(self):
        bar = QWidget()
        bar.setObjectName("statusBar")
        bar.setStyleSheet(STATUS_QSS)
        bar.setFixedHeight(21)
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(10)

        self.status_page = QLabel("Page 1")
        self.status_section = QLabel("Sec 1")
        self.status_pages = QLabel("1/1")
        self.status_at = QLabel('At 1"')
        self.status_line = QLabel("Ln 1")
        self.status_col = QLabel("Col 1")
        for label in (self.status_page, self.status_section, self.status_pages,
                      self.status_at, self.status_line, self.status_col):
            row.addWidget(label)
        row.addSpacing(6)

        self.indicators = {}
        for key, tip in (("REC", "Macro recording (double-click to start)"),
                         ("TRK", "Track changes (double-click to turn on)"),
                         ("EXT", "Extend selection (double-click, or press F8)"),
                         ("OVR", "Overtype (double-click, or press Insert)")):
            label = QLabel(key)
            label.setObjectName("dim")
            label.setToolTip(tip)
            label.mouseDoubleClickEvent = (
                lambda _ev, k=key: self._indicator_double_clicked(k))
            self.indicators[key] = label
            row.addWidget(label)

        row.addStretch(1)
        self.status_language = QLabel("English (U.S.)")
        row.addWidget(self.status_language)
        self.status_spell = QLabel()
        self.status_spell.setPixmap(mw_icons.pixmap("spelling", 15))
        self.status_spell.setToolTip("Spelling and Grammar Status")
        row.addWidget(self.status_spell)
        self.status_saved = QLabel("")
        self.status_saved.setFixedWidth(60)
        row.addWidget(self.status_saved)

        for label, slot in ((self.status_page, lambda: self.show_find(2)),
                            (self.status_pages, lambda: self.show_find(2)),
                            (self.status_line, lambda: self.show_find(2))):
            label.mouseDoubleClickEvent = lambda _ev, s=slot: s()
        self.status_spell.mouseDoubleClickEvent = (
            lambda _ev: self.spelling_and_grammar())
        return bar

    def _indicator_double_clicked(self, key: str):
        if key == "REC":
            self.record_macro()
        elif key == "TRK":
            self.track_act.setChecked(not self._track_changes)
            self.toggle_track_changes(not self._track_changes)
        elif key == "EXT":
            self._extend = not self._extend
            self._sync_indicators()
        elif key == "OVR":
            self.toggle_overtype()

    def _sync_indicators(self):
        states = {"REC": self._recording, "TRK": self._track_changes,
                  "EXT": self._extend, "OVR": self.editor.overtype}
        for key, label in self.indicators.items():
            label.setObjectName("" if states[key] else "dim")
            label.setStyleSheet("")
            label.style().unpolish(label)
            label.style().polish(label)

    # ============================================================ live state

    def _on_cursor_moved(self):
        self._update_status()
        self._sync_format_controls()
        self.ruler.update()
        if self._painter_format is not None and self.editor.textCursor().hasSelection():
            self._apply_painter()

    def _on_text_changed(self):
        self._update_status()

    def _on_scrolled(self, _value):
        self.vruler.update()
        self.ruler.update()

    def _on_zoom_changed(self, percent):
        self.zoom_combo.setCurrentText(f"{percent}%")
        self.ruler.update()
        self.vruler.update()

    def _on_modified(self, modified):
        if modified:
            self.status_saved.setText("")

    def _update_status(self):
        cursor = self.editor.textCursor()
        page = self.editor.page_of_cursor()
        self.status_page.setText(f"Page {page}")
        self.status_pages.setText(f"{page}/{self.editor.page_count()}")
        self.status_at.setText(
            "At " + fmt_measure(self.editor.cursor_offset_from_page_top(),
                                settings.options["units"]))
        self.status_line.setText(f"Ln {cursor.blockNumber() + 1}")
        self.status_col.setText(f"Col {cursor.positionInBlock() + 1}")

    def _sync_format_controls(self):
        fmt = self.editor.currentCharFormat()
        font = fmt.font()
        self.bold_btn.blockSignals(True)
        self.italic_btn.blockSignals(True)
        self.underline_btn.blockSignals(True)
        self.bold_btn.setChecked(font.bold())
        self.italic_btn.setChecked(font.italic())
        self.underline_btn.setChecked(font.underline())
        for btn in (self.bold_btn, self.italic_btn, self.underline_btn):
            btn.blockSignals(False)

        self.font_combo.blockSignals(True)
        self.font_combo.setCurrentFont(font)
        self.font_combo.blockSignals(False)
        size = font.pointSizeF()
        if size > 0:
            self.size_combo.blockSignals(True)
            self.size_combo.setCurrentText(f"{size:g}")
            self.size_combo.blockSignals(False)

        alignment = self.editor.alignment()
        for flag, btn in self.align_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(bool(alignment & flag))
            btn.blockSignals(False)

        name = self.current_style_name()
        self.style_combo.blockSignals(True)
        index = self.style_combo.findText(name)
        if index >= 0:
            self.style_combo.setCurrentIndex(index)
        self.style_combo.blockSignals(False)
        self.task_pane.set_current_style(name)

    def current_style_name(self) -> str:
        block_fmt = self.editor.textCursor().blockFormat()
        value = block_fmt.property(STYLE_PROPERTY)
        return value if isinstance(value, str) else "Normal"

    def sync_ruler(self):
        self.ruler.update()
        self.vruler.update()

    def _sync_reveal(self):
        if self.task_pane.title_label.text() != "Reveal Formatting":
            return
        cursor = self.editor.textCursor()
        fmt = cursor.charFormat()
        font = fmt.font()
        block = cursor.blockFormat()
        unit = settings.options["units"]
        alignment = ("Centered" if block.alignment() & Qt.AlignmentFlag.AlignHCenter else
                     "Right" if block.alignment() & Qt.AlignmentFlag.AlignRight else
                     "Justified" if block.alignment() & Qt.AlignmentFlag.AlignJustify else
                     "Left")
        groups = {
            "Font": [
                ("Font", font.family()),
                ("Size", f"{font.pointSizeF():g} pt"),
                ("Style", "Bold" if font.bold() else "Italic" if font.italic() else "Regular"),
                ("Color", fmt.foreground().color().name()
                 if fmt.foreground().style() != Qt.BrushStyle.NoBrush else "Automatic"),
            ],
            "Paragraph": [
                ("Alignment", alignment),
                ("Left indent", fmt_measure(block.leftMargin(), unit)),
                ("Right indent", fmt_measure(block.rightMargin(), unit)),
                ("Space before", fmt_measure(block.topMargin(), unit)),
                ("Space after", fmt_measure(block.bottomMargin(), unit)),
                ("Style", self.current_style_name()),
            ],
            "Section": [
                ("Paper", self.editor.page_setup.paper),
                ("Left margin", fmt_measure(self.editor.page_setup.left, unit)),
                ("Right margin", fmt_measure(self.editor.page_setup.right, unit)),
            ],
        }
        sample = cursor.selectedText()[:60] or cursor.block().text()[:60]
        self.task_pane.refresh_reveal(sample, groups)

    # ========================================================== character fmt

    def _merge_char(self, fmt: QTextCharFormat):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            if not cursor.hasSelection():
                self.editor.mergeCurrentCharFormat(fmt)
                return
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)

    def set_bold(self, on: bool):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if on else QFont.Weight.Normal)
        self._merge_char(fmt)

    def set_italic(self, on: bool):
        fmt = QTextCharFormat()
        fmt.setFontItalic(on)
        self._merge_char(fmt)

    def set_underline(self, on: bool):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(on)
        self._merge_char(fmt)

    def set_font_family(self, family: str):
        fmt = QTextCharFormat()
        fmt.setFontFamilies([family])
        fmt.setFontFamily(family)
        self._merge_char(fmt)
        self.editor.setFocus()

    def set_font_size(self, text: str):
        try:
            size = float(text)
        except ValueError:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self._merge_char(fmt)
        self.editor.setFocus()

    def grow_font(self, step: float):
        cursor = self.editor.textCursor()
        size = cursor.charFormat().font().pointSizeF() or 12.0
        self.set_font_size(f"{max(1.0, size + step):g}")

    def set_font_color(self, color: QColor):
        fmt = QTextCharFormat()
        fmt.setForeground(color if color.isValid() else QColor("black"))
        self._merge_char(fmt)

    def set_highlight(self, color: QColor):
        fmt = QTextCharFormat()
        if color.isValid():
            fmt.setBackground(color)
        else:
            fmt.setBackground(Qt.BrushStyle.NoBrush)
        self._merge_char(fmt)

    def clear_formatting(self):
        cursor = self.editor.textCursor()
        empty = QTextCharFormat()
        empty.setFont(QFont("Times New Roman", 12))
        if cursor.hasSelection():
            cursor.setCharFormat(empty)
        self.editor.setCurrentCharFormat(empty)
        self._apply_style_to_cursor("Normal")

    def toggle_format_painter(self, on: bool):
        if on:
            self._painter_format = QTextCharFormat(self.editor.currentCharFormat())
            self.editor.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._painter_format = None
            self._painter_sticky = False
            self.editor.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    def _apply_painter(self):
        cursor = self.editor.textCursor()
        cursor.mergeCharFormat(self._painter_format)
        if not self._painter_sticky:
            self.painter_btn.setChecked(False)
            self.toggle_format_painter(False)

    # ========================================================== paragraph fmt

    def _merge_block(self, fmt: QTextBlockFormat):
        cursor = self.editor.textCursor()
        cursor.mergeBlockFormat(fmt)
        self.editor.setTextCursor(cursor)
        self.sync_ruler()

    def set_alignment(self, flag):
        self.editor.setAlignment(flag)
        self._sync_format_controls()

    def set_line_spacing(self, percent: int):
        fmt = QTextBlockFormat()
        fmt.setLineHeight(
            percent, int(QTextBlockFormat.LineHeightTypes.ProportionalHeight.value))
        self._merge_block(fmt)

    def increase_indent(self):
        self._shift_indent(inches(0.5))

    def decrease_indent(self):
        self._shift_indent(-inches(0.5))

    def _shift_indent(self, delta: float):
        cursor = self.editor.textCursor()
        if cursor.currentList():
            list_fmt = cursor.currentList().format()
            list_fmt.setIndent(max(1, list_fmt.indent() + (1 if delta > 0 else -1)))
            cursor.createList(list_fmt)
            return
        fmt = QTextBlockFormat()
        fmt.setLeftMargin(max(0.0, cursor.blockFormat().leftMargin() + delta))
        self._merge_block(fmt)

    def set_indent_from_ruler(self, marker: int, value: float):
        """Called live while a ruler triangle is being dragged."""
        cursor = self.editor.textCursor()
        block = cursor.blockFormat()
        fmt = QTextBlockFormat()
        if marker == HorizontalRuler.MARKER_FIRST:
            fmt.setTextIndent(value - block.leftMargin())
        elif marker == HorizontalRuler.MARKER_LEFT:
            keep = block.textIndent()
            fmt.setLeftMargin(max(0.0, value))
            fmt.setTextIndent(keep)
        elif marker == HorizontalRuler.MARKER_RIGHT:
            width = self.editor.page_setup.text_width
            fmt.setRightMargin(max(0.0, width - value))
        else:
            return
        cursor.mergeBlockFormat(fmt)

    def add_tab_stop_at(self, position: float):
        cursor = self.editor.textCursor()
        block = cursor.blockFormat()
        tabs = list(block.tabPositions())
        from PyQt6.QtGui import QTextOption
        tab = QTextOption.Tab()
        tab.position = max(0.0, position)
        tab.type = {"Left": QTextOption.TabType.LeftTab,
                    "Center": QTextOption.TabType.CenterTab,
                    "Right": QTextOption.TabType.RightTab,
                    "Decimal": QTextOption.TabType.DelimiterTab}[self._tab_type]
        tab.delimiter = "."
        tabs.append(tab)
        fmt = QTextBlockFormat()
        fmt.setTabPositions(tabs)
        cursor.mergeBlockFormat(fmt)
        self.sync_ruler()

    def toggle_list(self, style):
        cursor = self.editor.textCursor()
        current = cursor.currentList()
        if current and current.format().style() == style:
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            block_fmt.setObjectIndex(-1)
            cursor.setBlockFormat(block_fmt)
            return
        list_fmt = QTextListFormat()
        list_fmt.setStyle(style)
        list_fmt.setIndent(1)
        cursor.beginEditBlock()
        cursor.createList(list_fmt)
        cursor.endEditBlock()

    # -------------------------------------------------------------- styles

    def apply_style(self, name: str):
        self._apply_style_to_cursor(name)
        self.editor.setFocus()

    def _apply_style_to_cursor(self, name: str, whole_paragraph=True):
        style = STYLES_BY_NAME.get(name)
        if style is None:
            return
        char = QTextCharFormat()
        font = QFont(style.family)
        font.setPointSizeF(style.size)
        font.setBold(style.bold)
        font.setItalic(style.italic)
        char.setFont(font)
        char.setForeground(QColor(style.color))

        block = QTextBlockFormat()
        block.setAlignment(Qt.AlignmentFlag(style.align))
        block.setTopMargin(style.space_before)
        block.setBottomMargin(style.space_after)
        block.setLineHeight(
            style.line_height, int(QTextBlockFormat.LineHeightTypes.ProportionalHeight.value))
        block.setHeadingLevel(style.outline_level + 1 if style.outline_level < 9 else 0)
        block.setProperty(STYLE_PROPERTY, style.name)

        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        if whole_paragraph:
            if not cursor.hasSelection():
                start = QTextCursor(cursor)
                start.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                start.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                                   QTextCursor.MoveMode.KeepAnchor)
                start.setCharFormat(char)
            else:
                cursor.setCharFormat(char)
        cursor.setBlockFormat(block)
        cursor.endEditBlock()
        self.editor.setCurrentCharFormat(char)
        self._sync_format_controls()

    def new_style(self):
        XPMessageBox.information(
            self, "New Style",
            "New styles are stored in the attached template.\n\n"
            "The attached template (Normal.dot) is read-only.")

    # ========================================================= context menus

    def _menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setStyleSheet(theme.MENU_QSS)
        return menu

    def _menu_act(self, menu, text, slot, icon=None, enabled=True, checkable=False,
                  checked=False):
        action = QAction(text, menu)
        if icon:
            action.setIcon(mw_icons.icon(icon, 16))
        action.setEnabled(enabled)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def show_editor_context_menu(self, event):
        cursor = self.editor.cursorForPosition(event.pos())
        issue = self._issue_at(cursor.position())
        menu = self._menu()

        if issue is not None:
            kind, position, length, word, label = issue
            if kind == "spelling":
                suggestions = self.checker.suggest(word, 5)
                if suggestions:
                    for suggestion in suggestions:
                        action = QAction(suggestion, menu)
                        bold = action.font()
                        bold.setBold(True)
                        action.setFont(bold)
                        action.triggered.connect(
                            lambda _=False, s=suggestion, i=issue: self.apply_correction(i, s))
                        menu.addAction(action)
                else:
                    none_action = QAction("(No Spelling Suggestions)", menu)
                    none_action.setEnabled(False)
                    menu.addAction(none_action)
                menu.addSeparator()
                self._menu_act(menu, "Ignore All", lambda: self._ignore_word(word))
                self._menu_act(menu, "Add to Dictionary", lambda: self._add_word(word))
                auto = menu.addMenu("AutoCorrect")
                for suggestion in suggestions[:5]:
                    entry = QAction(suggestion, auto)
                    entry.triggered.connect(
                        lambda _=False, s=suggestion, w=word, i=issue:
                        self._autocorrect_entry(w, s, i))
                    auto.addAction(entry)
            else:
                header = QAction(label, menu)
                header.setEnabled(False)
                menu.addAction(header)
                for suggestion in self.grammar_suggestions(word, label):
                    entry = QAction(suggestion, menu)
                    entry.setEnabled(False)
                    menu.addAction(entry)
                menu.addSeparator()
                self._menu_act(menu, "Ignore Once", lambda: None)
                self._menu_act(menu, "Grammar...", self.spelling_and_grammar)
            menu.addSeparator()
            self._menu_act(menu, "Spelling...", self.spelling_and_grammar, icon="spelling")
            self._menu_act(menu, "Look Up...", lambda: self.research(word), icon="research")
            menu.exec(event.globalPos())
            return

        has_selection = self.editor.textCursor().hasSelection()
        self._menu_act(menu, "Cu&t", self.cut, icon="cut", enabled=has_selection)
        self._menu_act(menu, "&Copy", self.copy, icon="copy", enabled=has_selection)
        self._menu_act(menu, "&Paste", self.editor.paste, icon="paste")
        menu.addSeparator()
        self._menu_act(menu, "&Font...", self.font_dialog)
        self._menu_act(menu, "&Paragraph...", self.paragraph_dialog)
        self._menu_act(menu, "Bullets and &Numbering...", self.bullets_dialog,
                       icon="bullets")
        menu.addSeparator()
        if self.editor.textCursor().currentTable() is not None:
            self._menu_act(menu, "&Insert Rows Below",
                           lambda: self.table_insert("row", before=False), icon="table")
            self._menu_act(menu, "&Delete Rows", lambda: self.table_delete("row"))
            self._menu_act(menu, "&Merge Cells", self.table_merge)
            self._menu_act(menu, "Table &Properties...", self.table_properties)
            menu.addSeparator()
        self._menu_act(menu, "&Hyperlink...", self.insert_hyperlink, icon="hyperlink")
        word_here = self._word_at(cursor)
        synonyms = menu.addMenu("S&ynonyms")
        for entry in self.thesaurus_entries(word_here):
            action = QAction(entry, synonyms)
            action.triggered.connect(
                lambda _=False, e=entry, c=cursor: self._replace_word(c, e))
            synonyms.addAction(action)
        synonyms.addSeparator()
        thesaurus = QAction("Thesaurus...", synonyms)
        thesaurus.triggered.connect(self.thesaurus)
        synonyms.addAction(thesaurus)
        self._menu_act(menu, "&Translate...", lambda: self.research(word_here))
        self._menu_act(menu, "&Look Up...", lambda: self.research(word_here),
                       icon="research")
        menu.exec(event.globalPos())

    def show_ruler_context_menu(self, event):
        menu = self._menu()
        for label in ("Left Tab", "Center Tab", "Right Tab", "Decimal Tab"):
            kind = label.split()[0]
            self._menu_act(menu, label, lambda _=False, k=kind: setattr(self, "_tab_type", k),
                           checkable=True, checked=(kind == self._tab_type))
        menu.addSeparator()
        self._menu_act(menu, "&Paragraph...", self.paragraph_dialog)
        self._menu_act(menu, "&Tabs...", self.open_tabs_dialog)
        menu.addSeparator()
        self._menu_act(menu, "Page Set&up...", self.page_setup)
        menu.exec(event.globalPosition().toPoint())

    def _word_at(self, cursor: QTextCursor) -> str:
        picker = QTextCursor(cursor)
        picker.select(QTextCursor.SelectionType.WordUnderCursor)
        return picker.selectedText()

    def _replace_word(self, cursor: QTextCursor, replacement: str):
        picker = QTextCursor(cursor)
        picker.select(QTextCursor.SelectionType.WordUnderCursor)
        picker.insertText(replacement)

    # ============================================================ clipboard

    def cut(self):
        text = self.editor.textCursor().selectedText()
        if text:
            self._collect_clipboard(text)
        self.editor.cut()

    def copy(self):
        text = self.editor.textCursor().selectedText()
        if text:
            self._collect_clipboard(text)
        self.editor.copy()

    def _collect_clipboard(self, text: str):
        self.clipboard_items.insert(0, text.replace(" ", "\n"))
        del self.clipboard_items[24:]
        self.task_pane.refresh_clipboard(self.clipboard_items)

    def paste_clipboard_item(self, index: int):
        if 0 <= index < len(self.clipboard_items):
            self.editor.insertPlainText(self.clipboard_items[index])

    def paste_all_clipboard(self):
        for text in reversed(self.clipboard_items):
            self.editor.insertPlainText(text)

    def clear_clipboard(self):
        self.clipboard_items.clear()
        self.task_pane.refresh_clipboard(self.clipboard_items)

    def paste_special(self):
        XPMessageBox.information(
            self, "Paste Special",
            "Source: Unknown\n\nAs:\n  Formatted Text (RTF)\n  Unformatted Text\n"
            "  Picture (Enhanced Metafile)\n  HTML Format\n\n"
            "Inserts the contents of the Clipboard as text without any formatting.")
        self.editor.insertPlainText(
            self.clipboard_items[0] if self.clipboard_items else "")

    def paste_as_hyperlink(self):
        if self.clipboard_items:
            text = self.clipboard_items[0]
            self.editor.insertHtml(f'<a href="{text}">{text}</a>')

    # ========================================================== autocorrect

    ORDINAL_RE = re.compile(r"\b(\d+)(st|nd|rd|th)$", re.IGNORECASE)

    def _on_contents_change(self, position, removed, added):
        """AutoCorrect and AutoFormat As You Type.

        Word does this work as the character lands, not on a timer, which is
        why the correction appears the instant you press space. contentsChange
        is the equivalent hook: it reports exactly what was inserted."""
        if self._loading or self._autocorrecting or added != 1 or removed:
            return
        options = settings.autocorrect_options
        doc = self.editor.document()
        char = doc.characterAt(position)
        block = doc.findBlock(position)
        text = block.text()
        offset = position - block.position()

        self._autocorrecting = True
        try:
            if char in ('"', "'") and options.smart_quotes:
                self._smart_quote(position, char, text, offset)
            elif char in " \t " or char in ".,!?;:)":
                self._autocorrect_word(position, text, offset, options)
            if char == " " and options.symbol_dashes:
                self._dash_fix(position, text, offset)
            if char == " " and offset <= 6:
                self._auto_list(block, text, options)
        finally:
            self._autocorrecting = False

    def _cursor_over(self, start: int, end: int) -> QTextCursor:
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        return cursor

    def _smart_quote(self, position, char, text, offset):
        before = text[offset - 1] if offset > 0 else ""
        opening = not before or before.isspace() or before in "([{-—"
        pairs = {'"': ("“", "”"), "'": ("‘", "’")}
        replacement = pairs[char][0 if opening else 1]
        cursor = self._cursor_over(position, position + 1)
        cursor.insertText(replacement)

    DASH_RE = re.compile(r"(?<=\w)--(?=\w)")

    def _dash_fix(self, position, text, offset):
        """Word turns word--word into word—word once the following word is
        finished, not the moment the second hyphen lands."""
        prefix = text[:offset]
        start_of_word = max(prefix.rfind(" "), prefix.rfind("\t")) + 1
        chunk = prefix[start_of_word:]
        match = self.DASH_RE.search(chunk)
        if match is None:
            return
        base = position - len(prefix) + start_of_word
        cursor = self._cursor_over(base + match.start(), base + match.end())
        cursor.insertText("—")

    def _autocorrect_word(self, position, text, offset, options):
        prefix = text[:offset]
        stripped = prefix.rstrip()
        if not stripped:
            return
        parts = stripped.split()
        word = parts[-1]
        start = position - (len(prefix) - prefix.rfind(word))

        replacement = None
        if options.replace_text:
            replacement = settings.autocorrect.get(word.lower())
            if replacement and word[:1].isupper():
                replacement = replacement[:1].upper() + replacement[1:]

        if replacement is None and options.two_initial_caps and len(word) > 2 \
                and word[0].isupper() and word[1].isupper() and word[2:].islower():
            replacement = word[0] + word[1].lower() + word[2:]

        if replacement is None and options.ordinals_superscript:
            match = self.ORDINAL_RE.search(word)
            if match:
                self._superscript_ordinal(start + match.start(2), len(match.group(2)))
                return

        if replacement is None and options.capitalize_days:
            days = {"monday", "tuesday", "wednesday", "thursday", "friday",
                    "saturday", "sunday", "january", "february", "march", "april",
                    "june", "july", "august", "september", "october", "november",
                    "december"}
            if word.lower() in days and word[0].islower():
                replacement = word.capitalize()

        # Sentence capitalization runs *after* the replacement table, not
        # instead of it: typing "teh cat" at the start of a sentence gives
        # "The cat" in Word, not "the cat".
        candidate = replacement if replacement is not None else word
        if options.capitalize_sentences and candidate[:1].islower():
            head = text[:offset - len(word) - (len(prefix) - len(stripped))].rstrip()
            if not head or head[-1] in ".!?":
                candidate = candidate[0].upper() + candidate[1:]
        if candidate != word:
            cursor = self._cursor_over(start, start + len(word))
            cursor.insertText(candidate)

    def _superscript_ordinal(self, start: int, length: int):
        cursor = self._cursor_over(start, start + length)
        fmt = QTextCharFormat()
        fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSuperScript)
        cursor.mergeCharFormat(fmt)

    def _auto_list(self, block, text, options):
        head = text.strip()
        cursor = QTextCursor(block)
        if options.auto_bullets and head in ("*", "-", "•"):
            self._replace_block_with_list(cursor, QTextListFormat.Style.ListDisc)
        elif options.auto_numbers and re.fullmatch(r"1[.)]", head):
            self._replace_block_with_list(cursor, QTextListFormat.Style.ListDecimal)

    def _replace_block_with_list(self, cursor: QTextCursor, style):
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                            QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        list_fmt = QTextListFormat()
        list_fmt.setStyle(style)
        list_fmt.setIndent(1)
        cursor.createList(list_fmt)
        self.assistant.offer_tip("list")

    def autocorrect_options(self):
        dialog = mdlg.AutoCorrectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.apply()

    def autoformat_document(self):
        if not XPMessageBox.confirm(
                self, "AutoFormat",
                "Word will automatically format the document 'Document1'.\n\n"
                "AutoFormat now?", yes_label="OK", no_label="Cancel"):
            return
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        block = self.editor.document().firstBlock()
        while block.isValid():
            text = block.text().strip()
            if text and len(text) < 60 and not text.endswith(".") and text[:1].isupper():
                pick = QTextCursor(block)
                self.editor.setTextCursor(pick)
                self._apply_style_to_cursor("Heading 2")
            block = block.next()
        cursor.endEditBlock()
        self.assistant.offer_tip("headings")

    # ============================================================= spelling

    def apply_options(self):
        self.highlighter.set_enabled(
            spelling=bool(settings.options.get("check_spelling", True)),
            grammar=bool(settings.options.get("check_grammar", True)))
        self.editor.show_boundaries = bool(settings.options.get("layout_boundaries", False))
        self.editor.show_marks = bool(settings.options.get("show_formatting_marks", False))
        self.marks_btn.setChecked(self.editor.show_marks)
        self._sync_ruler_visibility()
        self._restart_autosave()
        self.editor.viewport().update()

    def rehighlight(self):
        self.highlighter.rehighlight()

    def _all_issues(self, grammar=True):
        return list(spell_mod.scan_document(
            self.editor.document(), self.checker,
            check_spelling=bool(settings.options.get("check_spelling", True)),
            check_grammar=grammar and bool(settings.options.get("check_grammar", True))))

    def _issue_at(self, position: int):
        for issue in self._all_issues():
            _kind, start, length, _word, _label = issue
            if start <= position <= start + length:
                return issue
        return None

    def next_spelling_issue(self, grammar=True):
        for issue in self._all_issues(grammar):
            if issue[1] >= self._issue_cursor:
                return issue
        return None

    def advance_issue(self):
        issue = self.next_spelling_issue()
        if issue:
            self._issue_cursor = issue[1] + issue[2]

    def apply_correction(self, issue, replacement: str, everywhere=False):
        kind, position, length, word, _label = issue
        cursor = self._cursor_over(position, position + length)
        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()
        self._issue_cursor = position + len(replacement)
        if everywhere and kind == "spelling":
            self.replace_all(word, replacement,
                             QTextDocument.FindFlag.FindWholeWords)
        self.rehighlight()

    def issue_context_html(self, position: int, length: int, kind: str) -> str:
        doc = self.editor.document()
        block = doc.findBlock(position)
        text = block.text()
        offset = position - block.position()
        colour = "#e01b1b" if kind == "spelling" else "#1f9d3a"
        before = text[max(0, offset - 120):offset]
        target = text[offset:offset + length]
        after = text[offset + length:offset + length + 120]
        return (f'<span style="font-family:Times New Roman; font-size:11pt;">'
                f'{before}<span style="color:{colour}; font-weight:bold;">{target}</span>'
                f'{after}</span>')

    def grammar_suggestions(self, phrase: str, label: str) -> list[str]:
        if label == "Repeated Word":
            words = phrase.split()
            return [words[0]] if words else ["Delete repeated word"]
        if label == "Extra Space Between Words":
            return ["Delete the extra space"]
        if label == "Space Before Punctuation":
            return [phrase.strip()]
        if label == "Commonly Confused Words":
            return [phrase.replace(" of", " have").replace(" Of", " have")]
        if label == "Capitalization":
            return [phrase[:-1] + phrase[-1].upper()]
        if label == "Article Use":
            head = phrase.strip().lower()
            return ["an " if head.startswith("a") else "a "]
        return ["(no suggestions)"]

    def _ignore_word(self, word: str):
        self.checker.ignore_all(word)
        self.rehighlight()

    def _add_word(self, word: str):
        settings.add_word(word)
        self.rehighlight()

    def _autocorrect_entry(self, word: str, replacement: str, issue):
        settings.autocorrect[word.lower()] = replacement
        settings.save()
        self.apply_correction(issue, replacement)

    def spelling_and_grammar(self):
        self._issue_cursor = 0
        if not self._all_issues():
            XPMessageBox.information(
                self, "MacroHard Word",
                "The spelling and grammar check is complete.")
            return
        mdlg.SpellingDialog(self).exec()

    def thesaurus_entries(self, word: str) -> list[str]:
        """A tiny synonym table -- enough that the Synonyms submenu is real."""
        table = {
            "good": ["fine", "decent", "satisfactory", "worthy"],
            "bad": ["poor", "inferior", "substandard", "unsatisfactory"],
            "big": ["large", "substantial", "considerable", "sizeable"],
            "small": ["little", "compact", "modest", "slight"],
            "make": ["create", "produce", "construct", "form"],
            "important": ["significant", "crucial", "vital", "essential"],
            "help": ["assist", "aid", "support", "facilitate"],
            "show": ["display", "demonstrate", "present", "reveal"],
            "use": ["utilize", "employ", "apply", "operate"],
            "document": ["file", "paper", "record", "report"],
            "write": ["compose", "draft", "pen", "author"],
            "change": ["alter", "modify", "revise", "amend"],
        }
        entries = table.get(word.lower().strip())
        if not entries:
            return ["(no suggestions)"]
        if word[:1].isupper():
            entries = [e.capitalize() for e in entries]
        return entries

    def thesaurus(self):
        word = self._word_at(self.editor.textCursor())
        entries = self.thesaurus_entries(word)
        XPMessageBox.information(
            self, "Thesaurus: English (U.S.)",
            f"Looked Up: {word or '(nothing)'}\n\nMeanings:\n  " +
            "\n  ".join(entries))

    def research(self, term=""):
        if not isinstance(term, str) or not term:
            term = self._word_at(self.editor.textCursor())
        self.show_task_pane("Help")
        XPMessageBox.information(
            self, "Research",
            f"Search for: {term or '(nothing selected)'}\n\n"
            "All Reference Books\n\n"
            "No results were found. Try a different search term, or check your "
            "network connection, which does not exist.")

    def word_count(self) -> None:
        mdlg.WordCountDialog(self, self.document_stats()).exec()

    def document_stats(self) -> dict:
        doc = self.editor.document()
        text = doc.toPlainText()
        lines = 0
        block = doc.firstBlock()
        while block.isValid():
            lines += max(1, block.layout().lineCount())
            block = block.next()
        return {
            "pages": self.editor.page_count(),
            "words": len(text.split()),
            "chars": len(text),
            "chars_no_spaces": len(re.sub(r"\s", "", text)),
            "paragraphs": doc.blockCount(),
            "lines": lines,
        }

    def autosummarize(self):
        stats = self.document_stats()
        XPMessageBox.information(
            self, "AutoSummarize",
            f"Word examined the document and picked the sentences most relevant "
            f"to the main theme.\n\n"
            f"Original document: {stats['words']} words\n"
            f"Summary: {max(0, stats['words'] // 4)} words (25%)\n\n"
            "Word could not determine a main theme.")

    # ============================================================ file / vfs

    def _retitle(self, name: str):
        self.setWindowTitle(f"{name} - MacroHard Word")
        if hasattr(self, "window_list_action"):
            self.window_list_action.setText(f"&1 {name}")

    def _document_name(self) -> str:
        if self.node_id:
            node = vfs_mod.vfs.get(self.node_id)
            if node:
                return node.name
        return f"Document{self._doc_number}"

    def _serialize(self) -> str:
        payload = json.dumps(vars(self.doc_props))
        return self.editor.toHtml() + f"\n{PROPS_MARKER}{payload}-->"

    def _deserialize(self, content: str):
        match = PROPS_RE.search(content)
        if match:
            try:
                data = json.loads(match.group(1))
                for key, value in data.items():
                    if hasattr(self.doc_props, key):
                        setattr(self.doc_props, key, value)
            except ValueError:
                pass
            content = PROPS_RE.sub("", content)
        self._loading = True
        self.editor.setHtml(content)
        self._loading = False
        self.editor.document().setModified(False)
        self.editor.relayout()

    def _load_node(self, node_id: str):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        self.node_id = node_id
        self._deserialize(vfs_mod.vfs.read_content(node_id))
        self._retitle(node.name)
        settings.push_recent(node_id, node.name)
        self._rebuild_mru()
        self.task_pane.refresh_recent()
        self._update_status()

    def new_file(self):
        if not self._confirm_discard():
            return
        self.node_id = None
        self._doc_number += 1
        self._loading = True
        self.editor.clear()
        self._loading = False
        self.doc_props = DocumentProperties(
            author="MacroHard User",
            created=datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p"))
        self._apply_style_to_cursor("Normal")
        self.editor.document().setModified(False)
        self._retitle(f"Document{self._doc_number}")
        self.editor.relayout()

    def new_from_template(self):
        if not self._confirm_discard():
            return
        self.new_file()
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        self._apply_style_to_cursor("Title")
        cursor.insertText("Your Title Here")
        cursor.insertBlock()
        self._apply_style_to_cursor("Subtitle")
        cursor.insertText("A subtitle nobody will read")
        cursor.insertBlock()
        self._apply_style_to_cursor("Heading 1")
        cursor.insertText("Introduction")
        cursor.insertBlock()
        self._apply_style_to_cursor("Normal")
        cursor.insertText("Start typing here. This template was supplied by "
                          "MacroHard and cannot be modified.")
        cursor.endEditBlock()
        self.editor.document().setModified(False)

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(
            self, kinds=(vfs_mod.RICH,), title="Open")
        if node_id:
            self._load_node(node_id)

    def open_recent(self, entry: dict):
        node = vfs_mod.vfs.get(entry.get("id"))
        if node is None:
            if XPMessageBox.confirm(
                    self, "MacroHard Word",
                    f"The document name or path is not valid. Try one or more of "
                    f"the following:\n\n"
                    f"* Check the path to make sure it was typed correctly.\n"
                    f"* On the File menu, click Open, and browse to the document.\n\n"
                    f"Remove '{entry.get('name')}' from the recent file list?",
                    yes_label="Yes", no_label="No"):
                settings.recent_files = [
                    r for r in settings.recent_files if r.get("id") != entry.get("id")]
                settings.save()
                self._rebuild_mru()
                self.task_pane.refresh_recent()
            return
        self._load_node(entry["id"])

    def save_file(self):
        if self.node_id:
            self.doc_props.modified = datetime.now().strftime(
                "%A, %B %d, %Y %I:%M:%S %p")
            self.doc_props.revision += 1
            vfs_mod.vfs.write_content(self.node_id, self._serialize())
            self.editor.document().setModified(False)
            name = vfs_mod.vfs.get(self.node_id).name
            self._retitle(name)
            settings.push_recent(self.node_id, name)
            self._rebuild_mru()
            self.status_saved.setText("Saved")
        else:
            self.save_file_as()

    def save_file_as(self):
        default = self._document_name()
        if not default.lower().endswith(".doc"):
            default += ".doc"
        folder_id, name = VfsFileDialog.get_save_target(
            self, kinds=(vfs_mod.RICH,), title="Save As", default_name=default)
        if not folder_id:
            return
        self.doc_props.modified = datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")
        content = self._serialize()
        existing = next((c for c in vfs_mod.vfs.children_of(folder_id)
                         if c.name == name and c.kind == vfs_mod.RICH), None)
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
        saved_name = vfs_mod.vfs.get(self.node_id).name
        self._retitle(saved_name)
        settings.push_recent(self.node_id, saved_name)
        self._rebuild_mru()
        self.task_pane.refresh_recent()
        self.status_saved.setText("Saved")

    def save_as_web_page(self):
        XPMessageBox.information(
            self, "MacroHard Word",
            "Saving as a Web page will produce 41 files, a folder, and markup "
            "that only MacroHard Internet Explorer can render.\n\n"
            "Proceeding anyway.")
        self.save_file_as()

    def close_document(self):
        if self._confirm_discard():
            self.new_file()

    def _confirm_discard(self) -> bool:
        if not self.editor.document().isModified():
            return True
        answer = XPMessageBox.confirm(
            self, "MacroHard Word",
            f"Do you want to save the changes you made to "
            f"{self._document_name()}?", yes_label="Yes", no_label="No")
        if answer:
            self.save_file()
        return True

    def _restart_autosave(self):
        timer = getattr(self, "autosave_timer", None)
        if timer is None:
            return
        minutes = int(settings.options.get("autosave_minutes", 10))
        timer.stop()
        if minutes > 0:
            timer.start(minutes * 60_000)

    def _autosave(self):
        if self.node_id and self.editor.document().isModified():
            vfs_mod.vfs.write_content(self.node_id, self._serialize())
            self.editor.document().setModified(False)
            self.status_saved.setText("Autosaved")

    def _tick_editing_time(self):
        self.doc_props.editing_minutes += 1

    def show_properties(self):
        dialog = mdlg.DocPropertiesDialog(
            self, self.doc_props, self.document_stats(), self._document_name())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.apply_to(self.doc_props)

    def mail_recipient(self):
        XPMessageBox.critical(
            self, "MacroHard Word",
            "Word could not send the message because MacroHard Outlook is "
            "either not installed or is not your default e-mail client.\n\n"
            "It is installed. It is your default e-mail client.")

    # ========================================================= find/replace

    def show_find(self, tab=0):
        if self._find_dialog is not None:
            self._find_dialog.close()
        self._find_dialog = mdlg.FindReplaceDialog(self, tab)
        self._find_dialog.show()
        self._find_dialog.raise_()

    def find_text(self, term: str, flags=QTextDocument.FindFlag(0)) -> bool:
        if not term:
            return False
        if self.editor.find(term, flags):
            return True
        cursor = self.editor.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.End
            if flags & QTextDocument.FindFlag.FindBackward
            else QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        return self.editor.find(term, flags)

    def replace_once(self, term: str, replacement: str, flags=QTextDocument.FindFlag(0)):
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == term:
            cursor.insertText(replacement)
        self.find_text(term, flags)

    def replace_all(self, term: str, replacement: str,
                    flags=QTextDocument.FindFlag(0)) -> int:
        if not term:
            return 0
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        count = 0
        edit = self.editor.textCursor()
        edit.beginEditBlock()
        while self.editor.find(term, flags & ~QTextDocument.FindFlag.FindBackward):
            self.editor.textCursor().insertText(replacement)
            count += 1
        edit.endEditBlock()
        return count

    def go_to(self, kind: str, value: str):
        value = value.strip()
        if kind == "Page":
            try:
                page = int(value.lstrip("+-")) if value else 1
            except ValueError:
                page = 1
            if value.startswith("+"):
                page = self.editor.page_of_cursor() + page
            elif value.startswith("-"):
                page = self.editor.page_of_cursor() - page
            page = max(1, min(self.editor.page_count(), page))
            _, page_h = self.editor.page_pixel_size()
            self.editor.verticalScrollBar().setValue(int((page - 1) * page_h))
        elif kind == "Line":
            try:
                line = int(value) - 1
            except ValueError:
                return
            block = self.editor.document().findBlockByLineNumber(max(0, line))
            cursor = QTextCursor(block)
            self.editor.setTextCursor(cursor)
        elif kind == "Table":
            cursor = self.editor.textCursor()
            block = cursor.block()
            while block.isValid():
                probe = QTextCursor(block)
                if probe.currentTable() is not None:
                    self.editor.setTextCursor(probe)
                    return
                block = block.next()

    # ================================================================ insert

    def insert_break(self):
        dialog = mdlg.BreakDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cursor = self.editor.textCursor()
        cursor.insertBlock()
        fmt = cursor.blockFormat()
        fmt.setPageBreakPolicy(QTextBlockFormat.PageBreakFlag.PageBreak_AlwaysBefore)
        cursor.setBlockFormat(fmt)
        self.editor.setTextCursor(cursor)
        self.editor.relayout()

    def insert_page_numbers(self):
        dialog = mdlg.PageNumbersDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        XPMessageBox.information(
            self, "MacroHard Word",
            "Page numbers were added to the footer.\n\n"
            "Footers are only visible in Print Layout view and Print Preview.")

    def insert_date_time(self):
        dialog = mdlg.DateTimeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.editor.insertPlainText(dialog.text())

    def insert_symbol(self):
        dialog = mdlg.SymbolDialog(self, self.editor.insertPlainText)
        dialog.exec()

    def insert_comment(self):
        cursor = self.editor.textCursor()
        text = cursor.selectedText() or self._word_at(cursor)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#fff2b2"))
        fmt.setToolTip("Comment [MU1]: ")
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        XPMessageBox.information(
            self, "MacroHard Word",
            f"Comment [MU1] added to “{text or 'the insertion point'}”.")

    def insert_picture(self):
        node_id = VfsFileDialog.get_open_filename(
            self, kinds=(vfs_mod.IMAGE,), title="Insert Picture")
        if not node_id:
            return
        from PyQt6.QtGui import QImage
        data = vfs_mod.vfs.read_blob(node_id)
        image = QImage.fromData(data)
        if image.isNull():
            XPMessageBox.critical(self, "MacroHard Word",
                                  "The picture could not be inserted.")
            return
        width = min(int(self.editor.page_setup.text_width), image.width())
        if image.width() > width:
            image = image.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        self._insert_image(image)

    def _insert_image(self, image):
        from PyQt6.QtCore import QBuffer, QIODevice
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        b64 = bytes(buffer.data().toBase64()).decode("ascii")
        cursor = self.editor.textCursor()
        cursor.insertHtml(
            f'<img src="data:image/png;base64,{b64}" '
            f'width="{image.width()}" height="{image.height()}">')
        self.editor.setTextCursor(cursor)

    def insert_text_box(self):
        cursor = self.editor.textCursor()
        table = cursor.insertTable(1, 1, self._table_format(border=1.0))
        table.cellAt(0, 0).firstCursorPosition().insertText("Text Box")

    def insert_hyperlink(self):
        cursor = self.editor.textCursor()
        dialog = mdlg.HyperlinkDialog(self, cursor.selectedText())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        address = dialog.address()
        label = dialog.display_text() or address
        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(address)
        fmt.setForeground(QColor("#0000ee"))
        fmt.setFontUnderline(True)
        fmt.setToolTip(address)
        cursor.insertText(label, fmt)

    def insert_wordart(self):
        """Easter egg, preserved: Insert > Picture > WordArt (3D)."""
        from ..wordart_3d import WordArt3DDialog
        dialog = WordArt3DDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_image is not None:
            self._insert_image(dialog.result_image)

    def word_wrap(self):
        """Easter egg, preserved: Format > Word Wrap."""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText().replace(" ", " ")
            probe = QTextCursor(self.editor.document())
            probe.setPosition(cursor.selectionStart())
            probe.setPosition(cursor.selectionStart() + 1,
                              QTextCursor.MoveMode.KeepAnchor)
            fmt = probe.charFormat()
        else:
            block = cursor.block()
            text = block.text()
            fmt = QTextCursor(block).charFormat()
        text = text.strip()
        if not text:
            XPMessageBox.warning(self, "MacroHard Word",
                                 "There's no paragraph here to wrap.")
            return
        brush = fmt.foreground()
        color = brush.color() if brush.style() != Qt.BrushStyle.NoBrush else QColor("black")
        from ..word_wrap import render_word_wrap
        self._insert_image(render_word_wrap(text, fmt.font(), color))
        XPMessageBox.information(self, "Word Wrap",
                                 "This paragraph has been word wrapped.")

    # ====================================================== format dialogs

    def font_dialog(self):
        dialog = dlg.FontDialog(self, self.editor.currentCharFormat())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._merge_char(dialog.format())
            self._sync_format_controls()

    def paragraph_dialog(self):
        cursor = self.editor.textCursor()
        dialog = dlg.ParagraphDialog(self, cursor.blockFormat(), self.editor.alignment())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._merge_block(dialog.block_format())
            self.editor.setAlignment(dialog.alignment())
            self._sync_format_controls()

    def bullets_dialog(self):
        dialog = dlg.BulletsNumberingDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        choice = dialog.selection()
        if choice is None:
            cursor = self.editor.textCursor()
            fmt = cursor.blockFormat()
            fmt.setObjectIndex(-1)
            fmt.setIndent(0)
            cursor.setBlockFormat(fmt)
            return
        kind, value = choice
        if kind == "bullet":
            style = {"•": QTextListFormat.Style.ListDisc,
                     "○": QTextListFormat.Style.ListCircle,
                     "▪": QTextListFormat.Style.ListSquare}.get(
                value, QTextListFormat.Style.ListDisc)
        else:
            style = {"1.": QTextListFormat.Style.ListDecimal,
                     "1)": QTextListFormat.Style.ListDecimal,
                     "I.": QTextListFormat.Style.ListUpperRoman,
                     "i.": QTextListFormat.Style.ListLowerRoman,
                     "A.": QTextListFormat.Style.ListUpperAlpha,
                     "a)": QTextListFormat.Style.ListLowerAlpha}.get(
                value, QTextListFormat.Style.ListDecimal)
        list_fmt = QTextListFormat()
        list_fmt.setStyle(style)
        list_fmt.setIndent(1)
        if kind == "number" and value.endswith(")"):
            list_fmt.setNumberSuffix(")")
        self.editor.textCursor().createList(list_fmt)

    def borders_dialog(self):
        """Format > Borders and Shading.

        Qt has no per-paragraph border property, so a bordered paragraph is a
        one-paragraph QTextFrame -- which is what a bordered paragraph is in
        the underlying file format anyway. Re-running the dialog inside an
        existing frame edits that frame instead of nesting another."""
        dialog = dlg.BordersShadingDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        setting = dialog.border_setting()
        shade = dialog.shading()
        cursor = self.editor.textCursor()
        frame = cursor.currentFrame()
        root = self.editor.document().rootFrame()

        if setting == "None" and (frame is None or frame == root):
            if shade:
                char = QTextCharFormat()
                char.setBackground(QColor(shade))
                self._merge_char(char)
            return

        fmt = QTextFrameFormat()
        width = 0.0 if setting == "None" else dialog.border_width()
        fmt.setBorder(width)
        fmt.setBorderBrush(dialog.border_color())
        fmt.setBorderStyle(
            QTextFrameFormat.BorderStyle.BorderStyle_None if setting == "None"
            else QTextFrameFormat.BorderStyle.BorderStyle_Outset if setting == "3-D"
            else QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        fmt.setPadding(inches(0.04))
        fmt.setMargin(inches(0.02) if setting != "Shadow" else inches(0.05))
        if shade:
            fmt.setBackground(QColor(shade))

        if frame is not None and frame != root:
            frame.setFrameFormat(fmt)
            return
        cursor.beginEditBlock()
        if not cursor.hasSelection():
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                                QTextCursor.MoveMode.KeepAnchor)
        cursor.insertFrame(fmt)
        cursor.endEditBlock()

    def columns_dialog(self):
        dialog = dlg.ColumnsDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        count = dialog.column_count()
        cursor = self.editor.textCursor()
        if count <= 1:
            return
        text = cursor.selectedText() or self.editor.document().toPlainText()
        chunks = self._split_into_columns(text, count)
        fmt = self._table_format(border=0.0)
        fmt.setCellPadding(0)
        fmt.setCellSpacing(dialog.spacing() / 2.0)
        cursor.beginEditBlock()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.removeSelectedText()
        table = cursor.insertTable(1, count, fmt)
        for index, chunk in enumerate(chunks):
            table.cellAt(0, index).firstCursorPosition().insertText(chunk)
        cursor.endEditBlock()

    @staticmethod
    def _split_into_columns(text: str, count: int) -> list[str]:
        words = text.split()
        if not words:
            return [""] * count
        per = max(1, len(words) // count)
        chunks = [" ".join(words[i * per:(i + 1) * per]) for i in range(count)]
        leftover = " ".join(words[count * per:])
        if leftover:
            chunks[-1] += " " + leftover
        return chunks

    def open_tabs_dialog(self):
        cursor = self.editor.textCursor()
        dialog = dlg.TabsDialog(self, cursor.blockFormat())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            fmt = QTextBlockFormat()
            fmt.setTabPositions(dialog.tab_positions())
            cursor.mergeBlockFormat(fmt)
            self.editor.setTabStopDistance(dialog.default_stop() * self.editor.zoom)
            self.sync_ruler()

    def drop_cap_dialog(self):
        dialog = dlg.DropCapDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.position() == 0:
            return
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.NextCharacter,
                            QTextCursor.MoveMode.KeepAnchor)
        if not cursor.hasSelection():
            return
        fmt = QTextCharFormat()
        base = self.editor.currentCharFormat().font().pointSizeF() or 12.0
        font = QFont(dialog.font_family())
        font.setPointSizeF(base * dialog.lines() * 1.35)
        fmt.setFont(font)
        cursor.mergeCharFormat(fmt)

    def change_case_dialog(self):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        if not cursor.hasSelection():
            return
        dialog = dlg.ChangeCaseDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        text = cursor.selectedText()
        cursor.insertText(dlg.ChangeCaseDialog.convert(text, dialog.choice()))

    def set_background(self, color):
        """Word's page background is a screen-only tint -- it is deliberately
        not printed, which is why the Print Preview clone never gets it."""
        self.editor.page_color = QColor(color) if color else QColor("white")
        self.editor.viewport().update()

    def page_setup(self):
        dialog = dlg.PageSetupDialog(self, self.editor.page_setup)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.editor.set_page_setup(dialog.page_setup())
            self.sync_ruler()
            self._update_status()

    def options_dialog(self):
        dialog = mdlg.OptionsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.apply()
            self.apply_options()
            self._update_status()

    # ================================================================ tables

    def _table_format(self, border=1.0) -> QTextTableFormat:
        fmt = QTextTableFormat()
        fmt.setBorder(border)
        fmt.setBorderBrush(QColor("#000000"))
        fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        fmt.setCellPadding(inches(0.08))
        fmt.setCellSpacing(0)
        fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        return fmt

    def insert_table(self):
        dialog = mdlg.InsertTableDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._create_table(dialog.rows(), dialog.columns(), dialog.style)

    def insert_table_grid(self):
        """The toolbar button's drag-out grid, condensed to a quick 2x5."""
        self._create_table(2, 5, "Table Grid")

    def _create_table(self, rows: int, cols: int, style_name="Table Grid"):
        from .more_dialogs import TABLE_STYLES
        style = TABLE_STYLES.get(style_name, TABLE_STYLES["Table Grid"])
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        table = cursor.insertTable(rows, cols, self._table_format(style["border"]))
        if style["header"]:
            for col in range(cols):
                cell = table.cellAt(0, col)
                fmt = cell.format()
                fmt.setBackground(QColor(style["header"]))
                cell.setFormat(fmt)
                char = QTextCharFormat()
                char.setFontWeight(QFont.Weight.Bold)
                if QColor(style["header"]).lightness() < 128:
                    char.setForeground(QColor("white"))
                cell.firstCursorPosition().setCharFormat(char)
        if style["shade"]:
            for row in range(1, rows, 2):
                for col in range(cols):
                    cell = table.cellAt(row, col)
                    fmt = cell.format()
                    fmt.setBackground(QColor(style["shade"]))
                    cell.setFormat(fmt)
        cursor.endEditBlock()
        self.editor.setTextCursor(table.cellAt(0, 0).firstCursorPosition())

    def _require_table(self):
        table = self.editor.textCursor().currentTable()
        if table is None:
            XPMessageBox.information(
                self, "MacroHard Word",
                "The insertion point must be inside a table for this command "
                "to be available.")
        return table

    def table_insert(self, what: str, before=True):
        table = self._require_table()
        if table is None:
            return
        cell = table.cellAt(self.editor.textCursor())
        if what == "row":
            index = cell.row() + (0 if before else 1)
            table.insertRows(index, 1)
        else:
            index = cell.column() + (0 if before else 1)
            table.insertColumns(index, 1)

    def table_delete(self, what: str):
        table = self._require_table()
        if table is None:
            return
        cursor = self.editor.textCursor()
        cell = table.cellAt(cursor)
        if what == "table":
            select = QTextCursor(self.editor.document())
            select.setPosition(table.firstPosition() - 1)
            select.setPosition(table.lastPosition() + 1,
                               QTextCursor.MoveMode.KeepAnchor)
            select.removeSelectedText()
        elif what == "row":
            table.removeRows(cell.row(), 1)
        else:
            table.removeColumns(cell.column(), 1)

    def table_select(self, what: str):
        table = self._require_table()
        if table is None:
            return
        cursor = self.editor.textCursor()
        cell = table.cellAt(cursor)
        if what == "table":
            select = QTextCursor(self.editor.document())
            select.setPosition(table.firstPosition())
            select.setPosition(table.lastPosition(), QTextCursor.MoveMode.KeepAnchor)
        elif what == "row":
            first = table.cellAt(cell.row(), 0).firstCursorPosition()
            last = table.cellAt(cell.row(), table.columns() - 1).lastCursorPosition()
            select = QTextCursor(first)
            select.setPosition(last.position(), QTextCursor.MoveMode.KeepAnchor)
        elif what == "column":
            first = table.cellAt(0, cell.column()).firstCursorPosition()
            last = table.cellAt(table.rows() - 1, cell.column()).lastCursorPosition()
            select = QTextCursor(first)
            select.setPosition(last.position(), QTextCursor.MoveMode.KeepAnchor)
        else:
            select = QTextCursor(cell.firstCursorPosition())
            select.setPosition(cell.lastCursorPosition().position(),
                               QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(select)

    def table_merge(self):
        table = self._require_table()
        if table is None:
            return
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            table.mergeCells(cursor)
        else:
            XPMessageBox.information(
                self, "MacroHard Word", "Select two or more cells to merge.")

    def table_split(self):
        table = self._require_table()
        if table is None:
            return
        cell = table.cellAt(self.editor.textCursor())
        table.splitCell(cell.row(), cell.column(), 1, 2)

    def table_split_table(self):
        table = self._require_table()
        if table is None:
            return
        cell = table.cellAt(self.editor.textCursor())
        if cell.row() == 0:
            return
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(table.cellAt(cell.row(), 0).firstPosition() - 1)
        cursor.insertBlock()

    def table_autoformat(self):
        table = self._require_table()
        if table is None:
            return
        dialog = mdlg.TableAutoFormatDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        from .more_dialogs import TABLE_STYLES
        style = TABLE_STYLES.get(dialog.style(), TABLE_STYLES["Table Grid"])
        fmt = table.format()
        fmt.setBorder(style["border"])
        table.setFormat(fmt)
        for col in range(table.columns()):
            cell = table.cellAt(0, col)
            cell_fmt = cell.format()
            cell_fmt.setBackground(QColor(style["header"]) if style["header"]
                                   else QColor(Qt.GlobalColor.transparent))
            cell.setFormat(cell_fmt)

    def table_autofit(self, mode: str):
        table = self._require_table()
        if table is None:
            return
        fmt = table.format()
        if mode == "window":
            fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        elif mode == "contents":
            fmt.setWidth(QTextLength(QTextLength.Type.VariableLength, 0))
        else:
            fmt.setWidth(QTextLength(QTextLength.Type.FixedLength,
                                     self.editor.page_setup.text_width))
        table.setFormat(fmt)

    def text_to_table(self):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            XPMessageBox.information(self, "MacroHard Word",
                                     "Select the text you want to convert.")
            return
        rows = cursor.selectedText().split(" ")
        columns = max(len(row.split("\t")) for row in rows) or 1
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        table = cursor.insertTable(len(rows), columns, self._table_format())
        for r, row in enumerate(rows):
            for c, value in enumerate(row.split("\t")):
                table.cellAt(r, c).firstCursorPosition().insertText(value)
        cursor.endEditBlock()

    def table_to_text(self):
        table = self._require_table()
        if table is None:
            return
        lines = []
        for row in range(table.rows()):
            cells = []
            for col in range(table.columns()):
                cell = table.cellAt(row, col)
                picker = QTextCursor(cell.firstCursorPosition())
                picker.setPosition(cell.lastCursorPosition().position(),
                                   QTextCursor.MoveMode.KeepAnchor)
                cells.append(picker.selectedText().replace(" ", " "))
            lines.append("\t".join(cells))
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(table.firstPosition() - 1)
        cursor.setPosition(table.lastPosition() + 1, QTextCursor.MoveMode.KeepAnchor)
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText("\n".join(lines))
        cursor.endEditBlock()

    def table_sort(self):
        table = self._require_table()
        if table is None:
            return
        rows = []
        for row in range(1, table.rows()):
            cells = []
            for col in range(table.columns()):
                cell = table.cellAt(row, col)
                picker = QTextCursor(cell.firstCursorPosition())
                picker.setPosition(cell.lastCursorPosition().position(),
                                   QTextCursor.MoveMode.KeepAnchor)
                cells.append(picker.selectedText().replace(" ", " "))
            rows.append(cells)
        rows.sort(key=lambda r: r[0].lower())
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        for index, values in enumerate(rows, start=1):
            for col, value in enumerate(values):
                cell = table.cellAt(index, col)
                picker = QTextCursor(cell.firstCursorPosition())
                picker.setPosition(cell.lastCursorPosition().position(),
                                   QTextCursor.MoveMode.KeepAnchor)
                picker.insertText(value)
        cursor.endEditBlock()

    def table_formula(self):
        table = self._require_table()
        if table is None:
            return
        cell = table.cellAt(self.editor.textCursor())
        total = 0.0
        for row in range(table.rows()):
            if row == cell.row():
                continue
            probe = table.cellAt(row, cell.column())
            picker = QTextCursor(probe.firstCursorPosition())
            picker.setPosition(probe.lastCursorPosition().position(),
                               QTextCursor.MoveMode.KeepAnchor)
            try:
                total += float(picker.selectedText().replace(",", "").strip())
            except ValueError:
                continue
        cell.firstCursorPosition().insertText(f"{total:g}")

    def table_properties(self):
        mdlg.TablePropertiesDialog(self, self._require_table()).exec()

    def toggle_gridlines(self, on: bool):
        self.editor.viewport().update()

    # ================================================================= view

    def _sync_ruler_visibility(self):
        """isVisible() is false for everything until the window is shown, so the
        three ruler widgets are switched from the same computed booleans."""
        show = self.ruler_act.isChecked()
        mode = self.editor.view_mode
        horizontal = show and mode in ("print", "normal", "web")
        vertical = (show and mode == "print"
                    and bool(settings.options.get("layout_vruler", True)))
        self.ruler_row.setVisible(horizontal)
        self.vruler.setVisible(vertical)
        self.ruler_corner.setVisible(vertical)
        self.ruler_gap.setVisible(True)

    def set_view_mode(self, mode: str):
        self.editor.set_view_mode(mode)
        self._sync_ruler_visibility()
        settings.options["view_mode"] = mode
        self.sync_ruler()
        self._update_status()

    def _toggle_task_pane(self, on: bool):
        self.task_pane.setVisible(on)
        self.task_pane_act.setChecked(on)
        settings.options["show_task_pane"] = on

    def show_task_pane(self, name: str):
        self._toggle_task_pane(True)
        self.task_pane.show_pane(name)
        if name == "Reveal Formatting":
            self._sync_reveal()
        elif name == "Clipboard":
            self.task_pane.refresh_clipboard(self.clipboard_items)

    def _toggle_standard(self, on: bool):
        self.standard_bar.setVisible(on)

    def _toggle_formatting(self, on: bool):
        self.formatting_bar.setVisible(on)

    def _toggle_ruler(self, on: bool):
        self._sync_ruler_visibility()

    def toggle_formatting_marks(self, on: bool):
        self.editor.show_marks = on
        settings.options["show_formatting_marks"] = on
        self.editor.viewport().update()

    def toggle_drawing_toolbar(self):
        XPMessageBox.information(
            self, "MacroHard Word",
            "The Drawing toolbar has been docked at the bottom of the window, "
            "where it will remain for the rest of your life.")

    def toggle_overtype(self):
        self.editor.overtype = not self.editor.overtype
        self._sync_indicators()

    def toggle_track_changes(self, on: bool):
        self._track_changes = bool(on)
        self.track_act.setChecked(self._track_changes)
        self._sync_indicators()

    def _zoom_from_combo(self, _index):
        text = self.zoom_combo.currentText().strip()
        if text.endswith("%"):
            try:
                self.editor.set_zoom(int(float(text[:-1])))
            except ValueError:
                pass
        elif text == "Page Width":
            width = self.editor.viewport().width() - 24
            self.editor.set_zoom(int(width / self.editor.page_setup.page_width * 100))
        elif text == "Text Width":
            width = self.editor.viewport().width() - 24
            self.editor.set_zoom(int(width / self.editor.page_setup.text_width * 100))
        elif text == "Whole Page":
            height = self.editor.viewport().height() - 20
            self.editor.set_zoom(int(height / self.editor.page_setup.page_height * 100))
        elif text == "Two Pages":
            height = self.editor.viewport().height() - 20
            self.editor.set_zoom(int(height / self.editor.page_setup.page_height * 100 / 2))
        self.editor.setFocus()

    def zoom_dialog(self):
        dialog = mdlg.ZoomDialog(self, int(self.editor.zoom * 100))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        mode = dialog.mode()
        if mode == "percent":
            self.editor.set_zoom(dialog.zoom())
        else:
            self.zoom_combo.setCurrentText(
                {"page_width": "Page Width", "text_width": "Text Width",
                 "whole_page": "Whole Page"}[mode])
            self._zoom_from_combo(-1)

    def full_screen(self):
        self.toggle_maximize()

    def header_and_footer(self):
        XPMessageBox.information(
            self, "Header and Footer",
            "The header and footer areas are outside the text boundaries.\n\n"
            "Click inside the dashed rectangle at the top of the page to edit "
            "the header. There isn't one. There has never been one.")

    # ================================================================ print

    def print_preview(self):
        if self._preview_widget is None:
            self._preview_widget = PrintPreview(self)
            self._preview_widget.closed.connect(self.close_preview)
            self._preview_widget.print_requested.connect(self.print_document)
            self._preview_widget.shrink_requested.connect(self.shrink_to_fit)
            self.stack.addWidget(self._preview_widget)
        self._preview_widget.load(self._printable_document(), self.editor.page_setup)
        self.stack.setCurrentWidget(self._preview_widget)
        self.standard_bar.setVisible(False)
        self.formatting_bar.setVisible(False)
        self.ruler_row.setVisible(False)
        self.status_bar.setVisible(False)

    def close_preview(self):
        self.stack.setCurrentWidget(self.document_body)
        self.standard_bar.setVisible(self.standard_act.isChecked())
        self.formatting_bar.setVisible(self.formatting_act.isChecked())
        self.ruler_row.setVisible(self.ruler_act.isChecked())
        self.status_bar.setVisible(True)

    def _printable_document(self) -> QTextDocument:
        """A clone laid out for paper, not for the window."""
        from PyQt6.QtCore import QSizeF
        clone = self.editor.document().clone(self)
        ps = self.editor.page_setup
        clone.setDocumentMargin(0)
        root = clone.rootFrame()
        fmt = root.frameFormat()
        fmt.setLeftMargin(ps.left)
        fmt.setRightMargin(ps.right)
        fmt.setTopMargin(ps.top)
        fmt.setBottomMargin(ps.bottom)
        root.setFrameFormat(fmt)
        clone.setPageSize(QSizeF(ps.page_width, ps.page_height))
        return clone

    def shrink_to_fit(self):
        """Word's one-click "make it fit on one fewer page" -- it really did
        walk the font sizes down until the page count dropped."""
        target = max(1, self.editor.page_count() - 1)
        cursor = QTextCursor(self.editor.document())
        for _ in range(12):
            if self.editor.page_count() <= target:
                break
            cursor.select(QTextCursor.SelectionType.Document)
            fmt = QTextCharFormat()
            block = self.editor.document().firstBlock()
            size = block.charFormat().font().pointSizeF() or 12.0
            fmt.setFontPointSize(max(6.0, size - 0.5))
            cursor.mergeCharFormat(fmt)
            self.editor.relayout()
        if self._preview_widget is not None:
            self._preview_widget.load(self._printable_document(), self.editor.page_setup)

    def print_document(self):
        dialog = mdlg.PrintDialog(self, self.editor.page_count(),
                                  self.editor.page_of_cursor())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._spool(dialog.printer(),
                    self.editor.page_count() * dialog.copies())

    def print_now(self):
        self._spool("HP LaserJet 4000 Series PCL", self.editor.page_count())

    def _spool(self, printer: str, pages: int):
        self.doc_props.last_printed = datetime.now().strftime(
            "%A, %B %d, %Y %I:%M:%S %p")
        progress = mdlg.PrintProgressDialog(self, printer, max(1, pages))
        if progress.exec() == QDialog.DialogCode.Accepted:
            XPMessageBox.warning(
                self, "MacroHard Word",
                f"The document was sent to {printer}.\n\n"
                "The printer is out of paper, out of toner, and out of range.")

    # ============================================================ tools/help

    def macros(self):
        XPMessageBox.information(
            self, "Macros",
            "Macro name:\n  (none)\n\n"
            "Macros in: All active templates and documents\n\n"
            "No macros are available. Macros have been disabled by your "
            "administrator, who is you.")

    def record_macro(self):
        self._recording = not self._recording
        self._sync_indicators()
        if self._recording:
            XPMessageBox.information(
                self, "Record Macro",
                "Macro name: Macro1\n\nRecording has started.\n\n"
                "MacroHard Legal has not approved end users running their own "
                "code on this software, so the recording will be discarded.")
        else:
            XPMessageBox.information(self, "Record Macro", "Recording discarded.")

    def vb_editor(self):
        XPMessageBox.critical(
            self, "MacroHard Visual Basic",
            "Visual Basic for Applications could not be loaded.\n\n"
            "This is, on balance, for the best.")

    def protect_document(self):
        XPMessageBox.information(
            self, "Protect Document",
            "Formatting restrictions:\n"
            "  Limit formatting to a selection of styles\n\n"
            "Editing restrictions:\n"
            "  Allow only this type of editing in the document: No changes "
            "(Read only)\n\n"
            "Protection cannot be applied. The password would be 'password'.")

    def letter_wizard(self):
        self.assistant.offer_tip("letter")

    def new_window(self):
        window = MWordWindow(self.wm, self.node_id)
        self.wm.open(window)

    def arrange_all(self):
        XPMessageBox.information(
            self, "MacroHard Word", "There is only one window to arrange.")

    def help_contents(self):
        XPMessageBox.information(
            self, "MacroHard Office Word Help",
            "Table of Contents\n\n"
            "  Getting Started\n"
            "  Creating Documents\n"
            "  Formatting Text\n"
            "  Working with the Office Assistant\n"
            "  Turning off the Office Assistant\n"
            "  Turning off the Office Assistant (advanced)\n\n"
            "Select a topic. (Topic selection is not installed.)")

    def search_help(self, query: str):
        self.show_task_pane("Help")
        XPMessageBox.information(
            self, "Search Results",
            f"No results were found for \"{query}\".\n\n"
            "Try rephrasing your question, checking your spelling, or asking "
            "the paperclip.")

    def office_online(self):
        XPMessageBox.critical(
            self, "MacroHard Office Online",
            "Internet Explorer cannot display the webpage.\n\n"
            "Most likely causes:\n"
            "  You are not connected to the Internet.\n"
            "  The website is encountering problems.\n"
            "  There might be a typing error in the address.\n"
            "  It is 2003.")

    def wordperfect_help(self):
        XPMessageBox.information(
            self, "Help for WordPerfect Users",
            "Command: Reveal Codes\n\n"
            "MacroHard Word does not have codes to reveal. Word has moods.")

    def check_updates(self):
        XPMessageBox.information(
            self, "MacroHard Office Update",
            "No updates are available for MacroHard Office Word 2003.\n\n"
            "You are already embarrassingly overboard.")

    def detect_and_repair(self):
        XPMessageBox.information(
            self, "Detect and Repair",
            "Detect and Repair will find and fix errors in this application.\n\n"
            "Detect and Repair detected 1 error and repaired 0 of them.")

    def activate_product(self):
        XPMessageBox.information(
            self, "Activate Product",
            "This product has already been activated.\n\n"
            "Product ID: 73931-640-0000106-57342")

    def get_support(self):
        from ..bofh_support import SupportChatDialog
        if self._support_dialog is not None:
            self._support_dialog.close()
        self._support_dialog = SupportChatDialog(self)
        self._support_dialog.show()
        self._support_dialog.raise_()

    def about(self):
        AboutDialog(self).exec()

    # =========================================================== assistant

    def _assistant_home(self) -> QPoint:
        right = self.content.width() - self.assistant.width() - 12
        if self.task_pane.isVisible():
            right -= self.task_pane.width()
        return QPoint(max(8, right), max(8, self.content.height() - 268))

    def _greet(self):
        self.assistant.move(self._assistant_home())
        self.assistant.say(
            "It looks like you're opening MacroHard Word.",
            ["Get help with using Word", "Just let me type",
             "Don't show me this tip again"])

    def show_assistant(self):
        settings.options["assistant_enabled"] = True
        self.assistant.move(self._assistant_home())
        self.assistant.say("What would you like to do?",
                           ["Write a letter", "Check spelling", "Print", "Options..."])

    def assistant_options(self):
        if XPMessageBox.confirm(
                self, "Office Assistant",
                "Use the Office Assistant?\n\n"
                "Clearing this box hides the Assistant until you ask for it "
                "from the Help menu.", yes_label="OK", no_label="Cancel"):
            settings.options["assistant_enabled"] = False
            settings.save()
            self.assistant.hide()

    def choose_assistant(self):
        XPMessageBox.information(
            self, "Office Assistant",
            "Gallery:\n\n"
            "  Clippit (installed)\n"
            "  The Dot (not installed)\n"
            "  F1 the Robot (not installed)\n"
            "  Links the Cat (not installed)\n"
            "  Rocky (not installed)\n\n"
            "Insert the Office CD-ROM to install another Assistant.")

    def _assistant_choice(self, choice: str):
        if choice.startswith("Get help with writing"):
            self.new_from_template()
        elif choice.startswith("Get help with using"):
            self.help_contents()
        elif choice == "Check spelling":
            self.spelling_and_grammar()
        elif choice == "Print":
            self.print_document()
        elif choice == "Write a letter":
            self.assistant.offer_tip("letter")
        elif choice == "Save the document now":
            self.save_file()
        elif choice == "Format the list automatically":
            self.toggle_list(QTextListFormat.Style.ListDisc)
        elif choice == "Apply Heading 1 automatically":
            self.apply_style("Heading 1")
        elif choice.startswith("Options"):
            self.assistant_options()
        elif choice.startswith("Don't show"):
            settings.options["assistant_enabled"] = False
            settings.save()
            self.assistant.hide()

    # ================================================================ close

    def closeEvent(self, event):
        if self.editor.document().isModified():
            answer = XPMessageBox._show(
                self, "question", "MacroHard Word",
                f"Do you want to save the changes you made to "
                f"{self._document_name()}?", ("Yes", "No", "Cancel"), default="Cancel")
            if answer == "Cancel":
                event.ignore()
                return
            if answer == "Yes":
                self.save_file()
        settings.save()
        super().closeEvent(event)
