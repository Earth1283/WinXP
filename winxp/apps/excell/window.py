"""MacroHard Office Ex-Cell 2003."""
from __future__ import annotations

import re

from PyQt6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QMenu, QMenuBar, QTabBar, QToolButton,
    QVBoxLayout, QWidget,
)

from ... import corruption, theme, vfs as vfs_mod
from ...vfs_dialog import VfsFileDialog
from ...window_manager import XPWindow
from ...xp_dialog import XPMessageBox
from ..mword.widgets import TOOLBAR_QSS, ColorPickerButton, toolbar_button
from . import dialogs as dlg, formulas as fx
from .grid import SheetModel, SheetView
from .model import DEFAULT_COL_WIDTH, Sheet, Workbook, format_value, settings
from .pi import PiAssistant

STATUS_QSS = """
QWidget#statusBar { background: #ece9d8; border-top: 1px solid #aca998; }
QLabel { background: transparent; font-size: 11px; color: #1a1a1a; }
QLabel#panel { border: 1px solid #b7b4a5; border-right-color: #fff;
    border-bottom-color: #fff; padding: 0px 6px; }
"""

FORMULA_QSS = """
QWidget#formulaBar { background: #ece9d8; border-bottom: 1px solid #aca998; }
QLineEdit { background: white; border: 1px solid #7f9db9; font-family: Arial;
    font-size: 10pt; padding: 0px 2px; }
QToolButton { border: 1px solid transparent; background: transparent; font-style: italic;
    font-family: 'Times New Roman'; font-size: 11pt; padding: 0px 3px; }
QToolButton:hover { border: 1px solid #b6c8e2; background: #dfeaf8; }
"""

TABS_QSS = """
QWidget#tabRow { background: #ece9d8; border-top: 1px solid #aca998; }
QTabBar::tab { background: #f4f3ee; border: 1px solid #8a8778; border-top: none;
    padding: 1px 12px; margin-right: -1px; font-family: Arial; font-size: 8pt;
    border-bottom-left-radius: 3px; border-bottom-right-radius: 3px; }
QTabBar::tab:selected { background: white; font-weight: bold; }
QToolButton { border: none; background: transparent; font-size: 8pt; padding: 0px 2px; }
QToolButton:hover { background: #dfeaf8; }
"""

TEXT_BUTTON_QSS = "QToolButton { font-family: Arial; font-size: 9pt; font-weight: bold; }"

MAX_FORMAT_CELLS = 200_000
CIRCULAR_TICK_MS = 120
CIRCULAR_HEALTH_TICKS = 375

_untitled = 0


def _next_untitled() -> str:
    global _untitled
    _untitled += 1
    return f"Book{_untitled}"


class _F4Filter(QObject):
    """F4 in the cell editor or formula bar cycles $A$1 / A$1 / $A1 / A1."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.KeyPress and ev.key() == Qt.Key.Key_F4 \
                and isinstance(obj, QLineEdit):
            text, cur = obj.text(), obj.cursorPosition()
            for m in re.finditer(r"\$?[A-Za-z]{1,2}\$?\d{1,5}", text):
                if m.start() <= cur <= m.end():
                    new = fx.cycle_reference_style(m.group())
                    obj.setText(text[:m.start()] + new + text[m.end():])
                    obj.setCursorPosition(m.start() + len(new))
                    obj.textEdited.emit(obj.text())
                    return True
        return False


class ExCellWindow(XPWindow):
    """MacroHard Office Ex-Cell 2003. Clippy's ex."""

    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="MacroHard Ex-Cell", icon_key="excell",
                         size=QSize(920, 660))
        self.node_id = None
        self.doc_name = _next_untitled()
        self.book = Workbook()
        self.cpu_load = 0
        self._dirty = False
        self._clipboard = None
        self._find_dialog = None
        self._circular_warned = False
        self._circular_ticks = 0
        self._health_taken = False
        self._f4 = _F4Filter(self)

        self.model = SheetModel(self.book)
        self.model.entry_committed.connect(self.commit_entry)
        self.view = SheetView(self.model)
        self.view.delegate.on_editor = lambda editor: editor.installEventFilter(self._f4)
        self.view.clear_requested.connect(lambda: self.clear_selection(contents=True))
        self.view.fill_requested.connect(self._fill_handle)
        self.view.editing_changed.connect(self._on_editing)
        self.view.delegate.editor_text.connect(self._mirror_editor)
        self.view.selectionModel().currentChanged.connect(lambda *_: self._sync_formula_bar())
        self.view.selectionModel().selectionChanged.connect(lambda *_: self._update_status())
        self.view.horizontalHeader().sectionResized.connect(self._column_resized)

        self._build_ui()

        self.circular_timer = QTimer(self)
        self.circular_timer.timeout.connect(self._circular_tick)

        if node_id:
            self._load_node(node_id)
        self._retitle()
        self._apply_view_options()
        self.view.go_to(0, 0)
        self._sync_formula_bar()
        self._update_status()

        self.assistant = PiAssistant(self)
        self.assistant.choice_made.connect(self._assistant_choice)
        if settings.options["assistant_enabled"]:
            QTimer.singleShot(700, self._greet)
        else:
            self.assistant.hide()

    # -------------------------------------------------------------- layout

    def _build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setMenuBar(self._build_menu())
        self.standard_bar = self._build_standard_toolbar()
        self.formatting_bar = self._build_formatting_toolbar()
        root.addWidget(self.standard_bar)
        root.addWidget(self.formatting_bar)
        self.formula_bar = self._build_formula_bar()
        root.addWidget(self.formula_bar)
        root.addWidget(self.view, 1)
        root.addWidget(self._build_tab_row())
        self.status_bar = self._build_status_bar()
        root.addWidget(self.status_bar)
        self.set_content_layout(root)

    def _toolbar_shell(self):
        bar = QWidget()
        bar.setObjectName("mwToolbar")
        bar.setStyleSheet(TOOLBAR_QSS + TEXT_BUTTON_QSS)
        bar.setFixedHeight(26)
        row = QHBoxLayout(bar)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(1)
        grip = QWidget()
        grip.setFixedWidth(7)
        grip.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                           " stop:0 #ece9d8, stop:0.4 #a8a594, stop:0.6 #ece9d8);"
                           " margin: 3px 2px;")
        row.addWidget(grip)
        return bar, row

    @staticmethod
    def _separator():
        line = QWidget()
        line.setFixedWidth(6)
        line.setStyleSheet("background: transparent; border-left: 1px solid #b0ad9c;"
                           " margin: 3px 0px 3px 3px;")
        return line

    @staticmethod
    def _text_button(text, tooltip, slot, width=22):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(QSize(width, 22))
        btn.clicked.connect(slot)
        return btn

    def _build_standard_toolbar(self):
        bar, row = self._toolbar_shell()
        for glyph, tip, slot in (("new", "New (Ctrl+N)", self.new_file),
                                 ("open", "Open (Ctrl+O)", self.open_file),
                                 ("save", "Save (Ctrl+S)", self.save_file),
                                 ("print", "Print", self.print_document),
                                 ("print_preview", "Print Preview", self.print_document),
                                 ("spelling", "Spelling (F7)", self.spelling)):
            row.addWidget(toolbar_button(glyph, tip, slot))
        row.addWidget(self._separator())
        for glyph, tip, slot in (("cut", "Cut (Ctrl+X)", self.cut),
                                 ("copy", "Copy (Ctrl+C)", self.copy),
                                 ("paste", "Paste (Ctrl+V)", self.paste)):
            row.addWidget(toolbar_button(glyph, tip, slot))
        row.addWidget(self._separator())
        row.addWidget(toolbar_button("undo", "Undo (Ctrl+Z)", self.undo))
        row.addWidget(toolbar_button("redo", "Redo (Ctrl+Y)", self.redo))
        row.addWidget(self._separator())
        row.addWidget(self._text_button("Σ", "AutoSum", self.autosum))
        row.addWidget(self._text_button("fx", "Insert Function", self.insert_function))
        row.addWidget(self._text_button("A↓", "Sort Ascending", lambda: self.sort(False), 26))
        row.addWidget(self._text_button("Z↓", "Sort Descending", lambda: self.sort(True), 26))
        row.addWidget(self._separator())
        row.addWidget(self._text_button("📊", "Chart Wizard", self.chart_wizard))
        row.addStretch(1)
        return bar

    def _build_formatting_toolbar(self):
        bar, row = self._toolbar_shell()
        self.bold_btn = toolbar_button("bold", "Bold (Ctrl+B)",
                                       lambda: self.toggle_style("bold"))
        self.italic_btn = toolbar_button("italic", "Italic (Ctrl+I)",
                                         lambda: self.toggle_style("italic"))
        self.underline_btn = toolbar_button("underline", "Underline (Ctrl+U)",
                                            lambda: self.toggle_style("underline"))
        for btn in (self.bold_btn, self.italic_btn, self.underline_btn):
            row.addWidget(btn)
        row.addWidget(self._separator())
        for glyph, tip, align in (("align_left", "Align Left", "left"),
                                  ("align_center", "Center", "center"),
                                  ("align_right", "Align Right", "right")):
            row.addWidget(toolbar_button(glyph, tip, lambda _=False, a=align: self.set_align(a)))
        row.addWidget(self._separator())
        row.addWidget(self._text_button("$", "Currency Style",
                                        lambda: self.format_selection(num="Currency", dec=2)))
        row.addWidget(self._text_button("%", "Percent Style",
                                        lambda: self.format_selection(num="Percent", dec=0)))
        row.addWidget(self._text_button(",", "Comma Style", lambda: self.format_selection(
            num="Number", dec=2, thousands=True)))
        row.addWidget(self._text_button(".0→", "Increase Decimal",
                                        lambda: self.bump_decimals(1), 30))
        row.addWidget(self._text_button("←.0", "Decrease Decimal",
                                        lambda: self.bump_decimals(-1), 30))
        row.addWidget(self._separator())
        row.addWidget(toolbar_button("borders", "Borders",
                                     lambda: self.toggle_style("border")))
        self.fill_btn = ColorPickerButton("highlight", QColor("#ffff00"),
                                          automatic_label="No Fill",
                                          automatic_color=QColor(0, 0, 0, 0),
                                          tooltip="Fill Color")
        self.fill_btn.color_selected.connect(
            lambda c: self.format_selection(fill="" if c.alpha() == 0 else c.name()))
        row.addWidget(self.fill_btn)
        self.color_btn = ColorPickerButton("font_color", QColor("#ff0000"),
                                           tooltip="Font Color")
        self.color_btn.color_selected.connect(
            lambda c: self.format_selection(color="" if c == QColor("black") else c.name()))
        row.addWidget(self.color_btn)
        row.addStretch(1)
        return bar

    def _build_formula_bar(self):
        bar = QWidget()
        bar.setObjectName("formulaBar")
        bar.setStyleSheet(FORMULA_QSS)
        bar.setFixedHeight(26)
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)
        self.name_box = QLineEdit()
        self.name_box.setFixedWidth(90)
        self.name_box.returnPressed.connect(self._name_box_go)
        row.addWidget(self.name_box)
        fx_btn = QToolButton()
        fx_btn.setText("fx")
        fx_btn.setToolTip("Insert Function")
        fx_btn.clicked.connect(self.insert_function)
        row.addWidget(fx_btn)
        self.formula_edit = QLineEdit()
        self.formula_edit.installEventFilter(self._f4)
        self.formula_edit.returnPressed.connect(self._formula_bar_commit)
        self.formula_edit.installEventFilter(self)
        row.addWidget(self.formula_edit, 1)
        return bar

    def _build_tab_row(self):
        row_widget = QWidget()
        row_widget.setObjectName("tabRow")
        row_widget.setStyleSheet(TABS_QSS)
        row_widget.setFixedHeight(20)
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(0)
        for text, step in (("|◀", "first"), ("◀", -1), ("▶", 1), ("▶|", "last")):
            btn = QToolButton()
            btn.setText(text)
            btn.clicked.connect(lambda _=False, s=step: self._tab_nav(s))
            row.addWidget(btn)
        self.tabs = QTabBar()
        self.tabs.setShape(QTabBar.Shape.RoundedSouth)
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.currentChanged.connect(self._switch_sheet)
        self.tabs.tabBarDoubleClicked.connect(lambda i: self.rename_sheet(i))
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._tab_menu)
        row.addWidget(self.tabs)
        row.addStretch(1)
        self._rebuild_tabs()
        return row_widget

    def _build_status_bar(self):
        bar = QWidget()
        bar.setObjectName("statusBar")
        bar.setStyleSheet(STATUS_QSS)
        bar.setFixedHeight(21)
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 1, 6, 1)
        row.setSpacing(6)
        self.status_mode = QLabel("Ready")
        row.addWidget(self.status_mode)
        row.addStretch(1)
        self.status_sum = QLabel("")
        self.status_sum.setObjectName("panel")
        self.status_sum.setMinimumWidth(120)
        row.addWidget(self.status_sum)
        num = QLabel("NUM")
        num.setObjectName("panel")
        row.addWidget(num)
        return bar

    # ---------------------------------------------------------------- menus

    def _act(self, menu, text, slot=None, shortcut=None, checkable=False, checked=False):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.triggered.connect(slot if slot else
                                 (lambda _=False, t=text: self._not_implemented(t)))
        menu.addAction(action)
        self.addAction(action)
        return action

    def _not_implemented(self, label):
        XPMessageBox.warning(
            self, "MacroHard Ex-Cell",
            "Ex-Cell cannot complete this task with available resources. Choose less "
            "data or close other applications.")

    def _build_menu(self):
        bar = QMenuBar()
        theme.style_menubar(bar)

        m = bar.addMenu("&File")
        self._act(m, "&New...", self.new_file, "Ctrl+N")
        self._act(m, "&Open...", self.open_file, "Ctrl+O")
        self._act(m, "&Close", self.close)
        m.addSeparator()
        self._act(m, "&Save", self.save_file, "Ctrl+S")
        self._act(m, "Save &As...", self.save_file_as)
        self._act(m, "Save as Web Pa&ge...")
        self._act(m, "Restore Previous &Relationship...", self.restore_relationship)
        m.addSeparator()
        self._act(m, "Page Set&up...")
        self._act(m, "Print Pre&view", self.print_document)
        self._act(m, "&Print...", self.print_document, "Ctrl+P")
        m.addSeparator()
        self._act(m, "Propert&ies", self.properties)
        m.addSeparator()
        self._act(m, "E&xit", self.close)

        m = bar.addMenu("&Edit")
        self.undo_action = self._act(m, "&Undo", self.undo, "Ctrl+Z")
        self._act(m, "&Redo", self.redo, "Ctrl+Y")
        m.addSeparator()
        self._act(m, "Cu&t", self.cut, "Ctrl+X")
        self._act(m, "&Copy", self.copy, "Ctrl+C")
        self._act(m, "&Paste", self.paste, "Ctrl+V")
        self._act(m, "Paste &Special...")
        m.addSeparator()
        fill = m.addMenu("F&ill")
        self._act(fill, "&Down", lambda: self.fill("down"), "Ctrl+D")
        self._act(fill, "&Right", lambda: self.fill("right"), "Ctrl+R")
        self._act(fill, "&Series...")
        clear = m.addMenu("Cle&ar")
        self._act(clear, "&All", lambda: self.clear_selection(True, True))
        self._act(clear, "&Formats", lambda: self.clear_selection(False, True))
        self._act(clear, "&Contents", lambda: self.clear_selection(True, False))
        self._act(m, "&Delete...", self.delete_dialog)
        self._act(m, "De&lete Sheet", self.delete_sheet)
        m.addSeparator()
        self._act(m, "&Find...", lambda: self.show_find(False), "Ctrl+F")
        self._act(m, "R&eplace...", lambda: self.show_find(True), "Ctrl+H")
        self._act(m, "&Go To...", self.go_to_dialog, "Ctrl+G")

        m = bar.addMenu("&View")
        self._act(m, "&Normal", lambda: None, checkable=True, checked=True)
        self._act(m, "&Page Break Preview")
        m.addSeparator()
        self.formula_act = self._act(m, "&Formula Bar", self._toggle_formula_bar,
                                     checkable=True, checked=True)
        self.status_act = self._act(m, "&Status Bar", self._toggle_status_bar,
                                    checkable=True, checked=True)
        m.addSeparator()
        self._act(m, "&Header and Footer...")
        self._act(m, "&Comments")
        self._act(m, "&Zoom...")

        m = bar.addMenu("&Insert")
        self._act(m, "&Rows", lambda: self.insert_cells("row"))
        self._act(m, "&Columns", lambda: self.insert_cells("col"))
        self._act(m, "&Worksheet", self.insert_sheet)
        self._act(m, "C&hart...", self.chart_wizard)
        m.addSeparator()
        self._act(m, "&Function...", self.insert_function, "Shift+F3")
        self._act(m, "&Name")
        self._act(m, "Co&mment")
        self._act(m, "&Picture")
        self._act(m, "Hyperl&ink...", shortcut="Ctrl+K")

        m = bar.addMenu("F&ormat")
        self._act(m, "C&ells...", self.format_cells, "Ctrl+1")
        col = m.addMenu("&Column")
        self._act(col, "&Width...", self.column_width)
        self._act(col, "&AutoFit Selection", self.autofit_columns)
        self._act(col, "&Standard Width...", self.standard_width)
        sheet = m.addMenu("S&heet")
        self._act(sheet, "&Rename", lambda: self.rename_sheet(self.book.active))
        self._act(sheet, "&Hide")
        self._act(m, "&AutoFormat...")
        self._act(m, "Con&ditional Formatting...")
        self._act(m, "&Style...")

        m = bar.addMenu("&Tools")
        self._act(m, "&Spelling...", self.spelling, "F7")
        self._act(m, "&Error Checking...", self.error_checking)
        auditing = m.addMenu("Formula A&uditing")
        self._act(auditing, "Circular Reference", self.show_circular)
        self._act(auditing, "Trace Precedents")
        self._act(auditing, "Trace Dependents")
        m.addSeparator()
        self._act(m, "&Goal Seek...")
        self._act(m, "S&cenarios...")
        self._act(m, "&Macro")
        m.addSeparator()
        self._act(m, "&Options...", self.options_dialog)

        m = bar.addMenu("&Data")
        self._act(m, "&Sort Ascending", lambda: self.sort(False))
        self._act(m, "Sort &Descending", lambda: self.sort(True))
        self._act(m, "&Filter")
        self._act(m, "F&orm...")
        self._act(m, "Su&btotals...")
        self._act(m, "Va&lidation...")
        self._act(m, "Te&xt to Columns...")
        m.addSeparator()
        self._act(m, "&PivotTable and PivotChart Report...", self.pivot_table)

        m = bar.addMenu("&Window")
        self._act(m, "&New Window", self.new_window)
        self._act(m, "&Arrange...")
        self._act(m, "&Freeze Panes")

        m = bar.addMenu("&Help")
        self._act(m, "MacroHard Ex-Cell &Help", self.help_contents, "F1")
        self._act(m, "&Show the Office Assistant", self.show_assistant)
        self._act(m, "&About MacroHard Office Ex-Cell", self.about)
        return bar

    # -------------------------------------------------------------- editing

    @property
    def sheet(self) -> Sheet:
        return self.book.sheet

    def commit_entry(self, r, c, text):
        if text.startswith("=") and len(text) > 1:
            try:
                fx.parse(text[1:])
            except fx.FormulaError:
                XPMessageBox.critical(
                    self, "MacroHard Ex-Cell",
                    "The formula you typed contains an error.\n\n"
                    "For information about fixing common formula problems, click Help.")
                QTimer.singleShot(0, lambda: (self.view.go_to(r, c),
                                              self.view.start_edit(text)))
                return
        self.book.begin("Typing")
        self.book.set_entry(self.sheet, r, c, text)
        self.book.commit()
        self._changed()

    def _changed(self):
        self._dirty = True
        self.book.recalc_changed()
        self.model.refresh()
        self._sync_formula_bar()
        self._update_status()
        self._check_circular()
        self._retitle()

    def _mirror_editor(self, text):
        if not self.formula_edit.hasFocus():
            self.formula_edit.setText(text)

    def _on_editing(self, editing):
        self.status_mode.setText("Enter" if editing else self._mode_text())
        if not editing:
            self._sync_formula_bar()

    def eventFilter(self, obj, ev):
        if obj is self.formula_edit and ev.type() == QEvent.Type.KeyPress \
                and ev.key() == Qt.Key.Key_Escape:
            self._sync_formula_bar()
            self.view.setFocus()
            return True
        return super().eventFilter(obj, ev)

    def _formula_bar_commit(self):
        idx = self.view.currentIndex()
        self.commit_entry(idx.row(), idx.column(), self.formula_edit.text())
        self.view.setFocus()
        self.view.move_cursor(1, 0)

    def _sync_formula_bar(self):
        idx = self.view.currentIndex()
        if not idx.isValid():
            return
        cell = self.sheet.get(idx.row(), idx.column())
        if not self.view.is_editing():
            self.formula_edit.setText(cell.raw if cell else "")
        r1, c1, r2, c2 = self.view.selection_rect()
        if (r1, c1) == (r2, c2) or not self.view.selectionModel().hasSelection():
            self.name_box.setText(fx.cell_name(idx.row(), idx.column()))
        else:
            self.name_box.setText(f"{r2 - r1 + 1}R x {c2 - c1 + 1}C")

    def _name_box_go(self):
        text = self.name_box.text().strip().replace("$", "")
        parts = text.split(":")
        a = fx.parse_cell(parts[0])
        b = fx.parse_cell(parts[-1])
        if a is None or b is None:
            XPMessageBox.critical(self, "MacroHard Ex-Cell",
                                  "Reference is not valid.")
            self._sync_formula_bar()
            return
        self.view.select_rect(min(a[0], b[0]), min(a[1], b[1]),
                              max(a[0], b[0]), max(a[1], b[1]))
        self.view.setFocus()

    def _selection_cells(self, limit=MAX_FORMAT_CELLS):
        r1, c1, r2, c2 = self.view.selection_rect()
        if (r2 - r1 + 1) * (c2 - c1 + 1) > limit:
            self._not_implemented("")
            return None
        return [(r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]

    def format_selection(self, **changes):
        cells = self._selection_cells()
        if cells is None:
            return
        self.book.begin("Format Cells")
        for r, c in cells:
            self.book.set_format(self.sheet, r, c, **changes)
        self.book.commit()
        self._dirty = True
        self.model.refresh()
        self._update_status()
        self._retitle()

    def toggle_style(self, key):
        idx = self.view.currentIndex()
        cell = self.sheet.get(idx.row(), idx.column())
        self.format_selection(**{key: not (cell.style(key) if cell else False)})

    def set_align(self, align):
        idx = self.view.currentIndex()
        cell = self.sheet.get(idx.row(), idx.column())
        current = cell.style("align") if cell else ""
        self.format_selection(align="" if current == align else align)

    def bump_decimals(self, delta):
        idx = self.view.currentIndex()
        cell = self.sheet.get(idx.row(), idx.column())
        num = cell.style("num") if cell else "General"
        dec = int(cell.style("dec")) if cell and num != "General" else 0
        changes = {"dec": max(0, min(30, dec + delta))}
        if num == "General":
            changes["num"] = "Number"
        self.format_selection(**changes)

    def format_cells(self):
        idx = self.view.currentIndex()
        dialog = dlg.FormatCellsDialog(self, self.sheet.get(idx.row(), idx.column()))
        if dialog.exec():
            self.format_selection(**dialog.changes())

    def clear_selection(self, contents=True, formats=False):
        r1, c1, r2, c2 = self.view.selection_rect()
        self.book.begin("Clear")
        for (r, c) in list(self.sheet.cells):
            if r1 <= r <= r2 and c1 <= c <= c2:
                self.book.clear(self.sheet, r, c, contents, formats)
        self.book.commit()
        self._changed()

    def undo(self):
        if self.view.is_editing():
            return
        if self.book.undo() is None:
            return
        self._rebuild_tabs()
        self._changed()

    def redo(self):
        if self.book.redo() is None:
            return
        self._rebuild_tabs()
        self._changed()

    def cut(self):
        self.copy()
        if self._clipboard:
            self._clipboard["cut"] = True

    def copy(self):
        r1, c1, r2, c2 = self.view.selection_rect()
        if (r2 - r1 + 1) * (c2 - c1 + 1) > MAX_FORMAT_CELLS:
            self._not_implemented("")
            return
        self._clipboard = self.book.copy_block(self.sheet, r1, c1, r2, c2)
        self._clipboard["sheet"] = self.sheet
        self._clipboard["rect"] = (r1, c1, r2, c2)
        lines = ["\t".join(format_value(self.book.value(self.sheet, r, c),
                                        self.sheet.get(r, c), settings.options["hexcel"])
                           for c in range(c1, c2 + 1)) for r in range(r1, r2 + 1)]
        self._clipboard["text"] = "\n".join(lines)
        QApplication.clipboard().setText(self._clipboard["text"])

    def paste(self):
        r0, c0, _, _ = self.view.selection_rect()
        self.book.begin("Paste")
        text = QApplication.clipboard().text()
        if self._clipboard and text == self._clipboard["text"]:
            clip = self._clipboard
            if clip.get("cut"):
                r1, c1, r2, c2 = clip["rect"]
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        self.book.clear(clip["sheet"], r, c, True, True)
                self._clipboard = None
            self.book.paste_block(self.sheet, r0, c0, clip)
            height, width = len(clip["cells"]), len(clip["cells"][0])
        elif text:
            # From outside Ex-Cell: one cell per tab, one row per line, and
            # every entry gets the full date-conversion treatment.
            rows = [line.split("\t") for line in text.splitlines()]
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.book.set_entry(self.sheet, r0 + i, c0 + j, value.strip())
            height, width = len(rows), max(len(r) for r in rows) if rows else 1
        else:
            self.book.commit()
            return
        self.book.commit()
        self.view.select_rect(r0, c0, min(fx.MAX_ROWS - 1, r0 + height - 1),
                              min(fx.MAX_COLS - 1, c0 + width - 1))
        self._changed()

    def fill(self, direction):
        r1, c1, r2, c2 = self.view.selection_rect()
        if (r1 == r2 and direction == "down") or (c1 == c2 and direction == "right"):
            if direction == "down" and r1 > 0:
                r1 -= 1
            elif direction == "right" and c1 > 0:
                c1 -= 1
            else:
                return
        self.book.begin("Fill")
        self.book.fill(self.sheet, r1, c1, r2, c2, direction)
        self.book.commit()
        self._changed()

    def _fill_handle(self, source, target):
        self.book.begin("Auto Fill")
        self.book.fill_series(self.sheet, source, target)
        self.book.commit()
        self._changed()

    def autosum(self):
        idx = self.view.currentIndex()
        r, c = idx.row(), idx.column()
        top = r - 1
        while top >= 0 and isinstance(self.book.value(self.sheet, top, c), float):
            top -= 1
        if top < r - 1:
            formula = f"=SUM({fx.cell_name(top + 1, c)}:{fx.cell_name(r - 1, c)})"
        else:
            left = c - 1
            while left >= 0 and isinstance(self.book.value(self.sheet, r, left), float):
                left -= 1
            formula = (f"=SUM({fx.cell_name(r, left + 1)}:{fx.cell_name(r, c - 1)})"
                       if left < c - 1 else "=SUM()")
        self.view.start_edit(formula)

    def insert_function(self):
        name = dlg.InsertFunctionDialog.get(self)
        if name:
            self.view.setFocus()
            self.view.start_edit(f"={name}(")

    def sort(self, descending):
        r1, c1, r2, c2 = self.view.selection_rect()
        if r1 == r2:
            r1, r2 = self._current_region_rows(r1, c1)
            used_rows, used_cols = self.sheet.used_bounds()
            c1, c2 = 0, max(c2, used_cols - 1)
        self.book.begin("Sort")
        self.book.sort_rows(self.sheet, r1, c1, r2, c2,
                            self.view.currentIndex().column(), descending)
        self.book.commit()
        self._changed()

    def _current_region_rows(self, r, c):
        top = r
        while top > 0 and self.sheet.get(top - 1, c):
            top -= 1
        bottom = r
        while self.sheet.get(bottom + 1, c):
            bottom += 1
        return top, bottom

    def insert_cells(self, axis):
        r1, c1, r2, c2 = self.view.selection_rect()
        at, count = (r1, r2 - r1 + 1) if axis == "row" else (c1, c2 - c1 + 1)
        self.book.shift_cells(self.sheet, axis, at, count)
        self._after_structure()

    def delete_dialog(self):
        r1, c1, r2, c2 = self.view.selection_rect()
        choice = XPMessageBox._show(self, "question", "Delete", "Delete entire:",
                                    ("Row", "Column", "Cancel"), default="Cancel")
        if choice == "Row":
            self.book.shift_cells(self.sheet, "row", r1, -(r2 - r1 + 1))
        elif choice == "Column":
            self.book.shift_cells(self.sheet, "col", c1, -(c2 - c1 + 1))
        else:
            return
        self._after_structure()

    def _after_structure(self):
        self._apply_widths()
        self._changed()

    # --------------------------------------------------------------- sheets

    def _rebuild_tabs(self):
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        for sheet in self.book.sheets:
            self.tabs.addTab(sheet.name)
        self.tabs.setCurrentIndex(self.book.active)
        self.tabs.blockSignals(False)
        self._apply_widths()

    def _switch_sheet(self, index):
        if index < 0 or index >= len(self.book.sheets):
            return
        self.book.active = index
        self._apply_widths()
        self.model.refresh()
        self.view.go_to(0, 0)
        self._sync_formula_bar()
        self._update_status()

    def _tab_nav(self, step):
        count = self.tabs.count()
        target = {"first": 0, "last": count - 1}.get(step, self.tabs.currentIndex()
                                                     + (step if isinstance(step, int) else 0))
        self.tabs.setCurrentIndex(max(0, min(count - 1, target)))

    def _tab_menu(self, pos):
        index = self.tabs.tabAt(pos)
        if index >= 0:
            self.tabs.setCurrentIndex(index)
        menu = QMenu(self)
        menu.setStyleSheet(theme.MENU_QSS)
        for label, slot in (("&Insert...", self.insert_sheet),
                            ("&Delete", self.delete_sheet),
                            ("&Rename", lambda: self.rename_sheet(self.book.active)),
                            ("&Move or Copy...", None),
                            ("&Select All Sheets", None),
                            ("&Tab Color...", None)):
            act = QAction(label, menu)
            act.triggered.connect(slot or (lambda _=False, l=label: self._not_implemented(l)))
            menu.addAction(act)
        menu.exec(self.tabs.mapToGlobal(pos))

    def insert_sheet(self):
        self.book.snapshot("Insert Worksheet")
        self.book.sheets.insert(self.book.active, Sheet(self.book.unique_sheet_name()))
        self.book.reindex()
        self._rebuild_tabs()
        self._switch_sheet(self.book.active)
        self._changed()

    def delete_sheet(self):
        if len(self.book.sheets) == 1:
            XPMessageBox.critical(self, "MacroHard Ex-Cell",
                                  "A workbook must contain at least one visible worksheet.")
            return
        if self.sheet.cells and not XPMessageBox.confirm(
                self, "MacroHard Ex-Cell",
                "The selected sheet(s) will be permanently deleted.\n\n"
                "  • To delete the selected sheets, click Delete.\n"
                "  • To cancel the deletion, click Cancel.",
                kind="warning", yes_label="Delete", no_label="Cancel"):
            return
        self.book.snapshot("Delete Sheet")
        del self.book.sheets[self.book.active]
        self.book.active = min(self.book.active, len(self.book.sheets) - 1)
        self.book.reindex()
        self._rebuild_tabs()
        self._switch_sheet(self.book.active)
        self._changed()

    def rename_sheet(self, index):
        if index < 0:
            return
        sheet = self.book.sheets[index]
        name = dlg.TextPrompt.get(self, "Rename Sheet", "Name:", sheet.name)
        if name is None or name == sheet.name:
            return
        name = name.strip()
        if not name or len(name) > 31 or re.search(r"[:\\/?*\[\]]", name) or \
                any(s is not sheet and s.name.lower() == name.lower() for s in self.book.sheets):
            XPMessageBox.critical(
                self, "MacroHard Ex-Cell",
                "While renaming a sheet or chart, you entered an invalid name. Try one of "
                "the following:\n\n"
                "  • Make sure the name you entered does not exceed 31 characters.\n"
                "  • Make sure the name does not contain any of the following characters:"
                " : \\ / ? * [ or ]\n"
                "  • Make sure you did not leave the name blank.")
            return
        self.book.rename_sheet(sheet, name)
        self._rebuild_tabs()
        self._changed()

    # -------------------------------------------------------------- columns

    def _column_resized(self, col, _old, new):
        if self._applying_widths:
            return
        if new == DEFAULT_COL_WIDTH:
            self.sheet.col_widths.pop(col, None)
        else:
            self.sheet.col_widths[col] = new
        self._dirty = True
        self._retitle()

    _applying_widths = False

    def _apply_widths(self):
        header = self.view.horizontalHeader()
        self._applying_widths = True
        for c in range(fx.MAX_COLS):
            want = self.sheet.col_widths.get(c, DEFAULT_COL_WIDTH)
            if header.sectionSize(c) != want:
                header.resizeSection(c, want)
        self._applying_widths = False

    def column_width(self):
        idx = self.view.currentIndex()
        current = self.view.horizontalHeader().sectionSize(idx.column())
        value = dlg.TextPrompt.get(self, "Column Width", "Column width:",
                                   f"{current / 7:.2f}")
        try:
            width = int(float(value) * 7) if value is not None else None
        except ValueError:
            width = None
        if width is None:
            return
        r1, c1, r2, c2 = self.view.selection_rect()
        for c in range(c1, c2 + 1):
            self.view.horizontalHeader().resizeSection(c, max(0, min(1785, width)))

    def standard_width(self):
        r1, c1, r2, c2 = self.view.selection_rect()
        for c in range(c1, c2 + 1):
            self.view.horizontalHeader().resizeSection(c, DEFAULT_COL_WIDTH)

    def autofit_columns(self):
        r1, c1, r2, c2 = self.view.selection_rect()
        for c in range(c1, c2 + 1):
            self.view.resizeColumnToContents(c)

    # ------------------------------------------------------------- circular

    def _check_circular(self):
        if self.book.circular:
            if not self._circular_warned:
                self._circular_warned = True
                XPMessageBox.warning(
                    self, "MacroHard Ex-Cell",
                    "Ex-Cell cannot calculate a formula. Cell references in the formula "
                    "refer to the formula's result, creating a circular reference.\n\n"
                    "Ex-Cell will calculate it anyway.")
            if not self.circular_timer.isActive():
                self._circular_ticks = 0
                self.circular_timer.start(CIRCULAR_TICK_MS)
        elif self.circular_timer.isActive():
            self.circular_timer.stop()
            self.cpu_load = 0
            self._update_status()

    def _circular_tick(self):
        if not self.book.circular:
            self._check_circular()
            return
        recomputed = self.book.iterate_circular()
        self._circular_ticks += 1
        self.cpu_load = min(99, 40 + self._circular_ticks)
        self.model.refresh_cells(recomputed)
        self._sync_formula_bar()
        self._update_status()
        if self._circular_ticks == CIRCULAR_HEALTH_TICKS and not self._health_taken:
            self._health_taken = True
            corruption.health.kill("excel.exe (circular reference)")
            XPMessageBox.critical(
                self, "MacroHard Ex-Cell",
                "Ex-Cell has used all available system resources to calculate a circular "
                "reference.\n\nWindows has been informed.")

    def show_circular(self):
        if not self.book.circular:
            XPMessageBox.information(self, "Circular Reference",
                                     "There are no circular references in this workbook.")
            return
        name, r, c = self.book.circular[0]
        index = next(i for i, s in enumerate(self.book.sheets) if s.name == name)
        self.tabs.setCurrentIndex(index)
        self.view.go_to(r, c)

    # --------------------------------------------------------------- status

    def _mode_text(self):
        if self.book.circular:
            name, r, c = self.book.circular[0]
            prefix = "" if name == self.sheet.name else f"{name}!"
            return f"Ready        Circular: {prefix}{fx.cell_name(r, c)}"
        return "Ready"

    def _update_status(self):
        if not self.view.is_editing():
            self.status_mode.setText(self._mode_text())
        r1, c1, r2, c2 = self.view.selection_rect()
        total, count = 0.0, 0
        for (r, c), cell in self.sheet.cells.items():
            if r1 <= r <= r2 and c1 <= c <= c2 and isinstance(cell.value, float) \
                    and not isinstance(cell.value, bool):
                total += cell.value
                count += 1
        if count > 1 or (count == 1 and (r1, c1) != (r2, c2)):
            self.status_sum.setText("Sum=" + format_value(total, None, settings.options["hexcel"]))
        else:
            self.status_sum.setText("")
        self._sync_formula_bar()

    def _retitle(self):
        self.setWindowTitle(f"MacroHard Ex-Cell - {self.doc_name}")

    def _apply_view_options(self):
        self.formula_bar.setVisible(settings.options["formula_bar"])
        self.formula_act.setChecked(settings.options["formula_bar"])
        self.status_bar.setVisible(settings.options["status_bar"])
        self.status_act.setChecked(settings.options["status_bar"])
        self.view.setShowGrid(settings.options["gridlines"])
        self.model.refresh()
        self._update_status()

    def _toggle_formula_bar(self, on):
        settings.options["formula_bar"] = on
        settings.save()
        self._apply_view_options()

    def _toggle_status_bar(self, on):
        settings.options["status_bar"] = on
        settings.save()
        self._apply_view_options()

    # ------------------------------------------------------------- dialogs

    def show_find(self, replace):
        if self._find_dialog is None:
            self._find_dialog = dlg.FindDialog(self, self, replace)
        self._find_dialog.show()
        self._find_dialog.raise_()

    def find_next(self, matches):
        idx = self.view.currentIndex()
        start = (idx.row(), idx.column())
        hexcel = settings.options["hexcel"]
        ordered = sorted(self.sheet.cells.items())
        after = [item for item in ordered if item[0] > start] + \
                [item for item in ordered if item[0] <= start]
        for (r, c), cell in after:
            if matches(cell.raw) or matches(format_value(cell.value, cell, hexcel)):
                self.view.go_to(r, c)
                return
        XPMessageBox.information(self, "MacroHard Ex-Cell",
                                 "Ex-Cell cannot find the data you're searching for.")

    def replace_all(self, needle, replacement, case, whole):
        if not needle:
            return 0
        count = 0
        self.book.begin("Replace")
        flags = 0 if case else re.I
        for (r, c), cell in list(self.sheet.cells.items()):
            raw = cell.raw
            if whole:
                hit = raw == needle if case else raw.lower() == needle.lower()
                new = replacement if hit else raw
            else:
                new, hits = re.subn(re.escape(needle), lambda _m: replacement, raw, flags=flags)
                hit = hits > 0
            if hit:
                count += 1
                self.book.set_entry(self.sheet, r, c, new)
        self.book.commit()
        self._changed()
        return count

    def go_to_dialog(self):
        ref = dlg.TextPrompt.get(self, "Go To", "Reference:")
        if ref:
            self.name_box.setText(ref)
            self._name_box_go()

    def options_dialog(self):
        if dlg.OptionsDialog(self).exec():
            self._apply_view_options()
            if settings.options["assistant_enabled"]:
                self.assistant.show()
            else:
                self.assistant.hide()
        self.model.refresh()
        self._update_status()

    def spelling(self):
        texts = sum(1 for cell in self.sheet.cells.values()
                    if isinstance(cell.value, str) and not cell.is_formula)
        XPMessageBox.information(
            self, "MacroHard Ex-Cell",
            f"The spelling check is complete for the entire sheet.\n\n"
            f"{texts} text cell{'s' if texts != 1 else ''} checked. Numbers were not "
            f"checked, because they are in hexadecimal and could be words.")

    def error_checking(self):
        errors = [(r, c) for (r, c), cell in sorted(self.sheet.cells.items())
                  if isinstance(cell.value, fx.XLError)]
        if not errors:
            XPMessageBox.information(self, "MacroHard Ex-Cell",
                                     "The error check is complete for the entire sheet.")
            return
        r, c = errors[0]
        self.view.go_to(r, c)
        cell = self.sheet.get(r, c)
        XPMessageBox.warning(
            self, "Error Checking",
            f"Error in cell {fx.cell_name(r, c)}\n{cell.raw}\n\n"
            f"{len(errors)} cell{'s' if len(errors) != 1 else ''} on this sheet "
            f"contain{'s' if len(errors) == 1 else ''} errors. This one is {cell.value}.")

    def chart_wizard(self):
        XPMessageBox.information(
            self, "Chart Wizard - Step 1 of 4 - Chart Type",
            "The Chart Wizard is still choosing a chart type.\n\n"
            "It has narrowed it down to 3-D Pie.")

    def pivot_table(self):
        XPMessageBox.warning(
            self, "PivotTable and PivotChart Wizard",
            "Nobody in this office knows how to make a PivotTable.\n\n"
            "The person who did has left the company.")

    def print_document(self):
        XPMessageBox.critical(
            self, "MacroHard Ex-Cell",
            "Ex-Cell could not print because no printer is installed.\n\n"
            "The printout would have been 1 column wide and 214 pages long.")

    def properties(self):
        rows, cols = self.sheet.used_bounds()
        formulas = sum(1 for s in self.book.sheets for c in s.cells.values() if c.is_formula)
        XPMessageBox.information(
            self, f"{self.doc_name} Properties",
            f"Sheets: {len(self.book.sheets)}\n"
            f"Used range on {self.sheet.name}: "
            f"{'A1:' + fx.cell_name(rows - 1, cols - 1) if rows else '(empty)'}\n"
            f"Formulas: {formulas}\n"
            f"Number base: {'16' if settings.options['hexcel'] else '10 (legacy)'}")

    def help_contents(self):
        XPMessageBox.information(
            self, "MacroHard Ex-Cell Help",
            "Type a question for help.\n\n"
            "Searched for: (nothing)\n"
            "Results: 0 of 0, shown in hexadecimal.")

    def about(self):
        XPMessageBox.information(
            self, "About MacroHard Office Ex-Cell",
            "MacroHard® Office Ex-Cell 2003 (11.5612.5606)\n"
            "Part of MacroHard Office Professional Edition 2003\n\n"
            "Copyright © 1985-2003 MacroHard Corporation.\n\n"
            "This product is licensed to: MacroHard User\n"
            "Product ID: 0x1D4F-0xOEM-0xBEEF")

    # ---------------------------------------------------------------- files

    def _load_node(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if node is None:
            return
        self.node_id = node_id
        self.doc_name = node.name
        self.book = Workbook.from_text(vfs_mod.vfs.read_content(node_id))
        self.model.set_book(self.book)
        self._rebuild_tabs()
        self._dirty = False
        self._check_circular()

    def new_file(self):
        self.new_window(None)

    def new_window(self, node_id=None):
        window = ExCellWindow(self.wm, node_id)
        window._app_key = "excell"
        self.wm.open(window)
        return window

    def open_file(self):
        node_id = VfsFileDialog.get_open_filename(self, kinds=(vfs_mod.TEXT,), title="Open")
        if not node_id:
            return
        if not self._dirty and self.node_id is None and not any(
                s.cells for s in self.book.sheets):
            self._load_node(node_id)
            self._retitle()
            self.view.go_to(0, 0)
            self._update_status()
        else:
            self.new_window(node_id)

    def save_file(self) -> bool:
        if self.node_id is None or vfs_mod.vfs.get(self.node_id) is None:
            return self.save_file_as()
        vfs_mod.vfs.write_content(self.node_id, self.book.to_json())
        self._dirty = False
        self._retitle()
        return True

    def save_file_as(self) -> bool:
        default = self.doc_name if self.doc_name.lower().endswith(".xls") \
            else f"{self.doc_name}.xls"
        folder_id, name = VfsFileDialog.get_save_target(
            self, kinds=(vfs_mod.TEXT,), title="Save As", default_name=default)
        if not folder_id:
            return False
        if not name.lower().endswith(".xls"):
            name += ".xls"
        existing = next((c for c in vfs_mod.vfs.children_of(folder_id)
                         if c.name == name and c.kind == vfs_mod.TEXT), None)
        content = self.book.to_json()
        if existing:
            vfs_mod.vfs.write_content(existing.id, content)
            self.node_id = existing.id
        else:
            self.node_id = vfs_mod.vfs.create_text_file(folder_id, name, content).id
        self.doc_name = vfs_mod.vfs.get(self.node_id).name
        self._dirty = False
        self._retitle()
        return True

    def restore_relationship(self):
        last = settings.last_closed
        node = vfs_mod.vfs.get(last["id"]) if last else None
        if node is None:
            XPMessageBox.information(self, "Restore Previous Relationship",
                                     "You have no previous relationships to restore.")
            return
        XPMessageBox.information(
            self, "Restore Previous Relationship",
            f"Ex-Cell is restoring your previous relationship with {node.name}.\n\n"
            "This was not a request.")
        self.new_window(node.id)

    # ------------------------------------------------------------- assistant

    def _assistant_home(self) -> QPoint:
        right = self.content.width() - self.assistant.width() - 24
        return QPoint(max(8, right), max(8, self.content.height() - 250))

    def _greet(self):
        self.assistant.move(self._assistant_home())
        self.assistant.say("Hi, I'm Pi. I'm 100% here for you. Well, 45%.",
                           ["Get help with Ex-Cell", "Just let me type",
                            "Don't show me this tip again"])

    def show_assistant(self):
        settings.options["assistant_enabled"] = True
        settings.save()
        self.assistant.move(self._assistant_home())
        self.assistant.say("What would you like to do?",
                           ["Make a chart", "Fix a circular reference", "Options..."])

    def assistant_options(self):
        if XPMessageBox.confirm(self, "Office Assistant",
                                "Hide Pi until you ask for it from the Help menu?",
                                yes_label="OK", no_label="Cancel"):
            settings.options["assistant_enabled"] = False
            settings.save()
            self.assistant.hide()

    def choose_assistant(self):
        XPMessageBox.information(
            self, "Office Assistant",
            "Gallery:\n\n"
            "  Pi (installed)\n"
            "  Clippit (installed in Word. Please don't.)\n"
            "  Rocky (not installed)")

    def _assistant_choice(self, choice):
        if choice == "Get help with Ex-Cell":
            self.help_contents()
        elif choice == "Make a chart":
            self.chart_wizard()
        elif choice == "Fix a circular reference":
            self.show_circular()
        elif choice.startswith("Options"):
            self.options_dialog()
        elif choice.startswith("Don't show"):
            self.assistant.say("Okay. I'll be in the corner. Clippy never offers that.",
                               ["OK"])
            settings.options["assistant_enabled"] = False
            settings.save()
            QTimer.singleShot(3500, self.assistant.hide)

    # ---------------------------------------------------------------- close

    def closeEvent(self, event):
        if self._dirty:
            answer = XPMessageBox._show(
                self, "question", "MacroHard Ex-Cell",
                f"Do you want to save the changes you made to '{self.doc_name}'?",
                ("Yes", "No", "Cancel"), default="Cancel")
            if answer == "Cancel" or (answer == "Yes" and not self.save_file()):
                event.ignore()
                return
        self.circular_timer.stop()
        self.cpu_load = 0
        if self.node_id:
            settings.last_closed = {"id": self.node_id, "name": self.doc_name}
        settings.save()
        super().closeEvent(event)
