"""The task pane.

Office 2003's docked right-hand panel, with its own little navigation bar and
a drop-down that switches between panes. Getting Started, New Document, Styles
and Formatting, Clipboard and Reveal Formatting are all live -- the styles
pane applies real styles, the clipboard pane collects real cuts.
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
    QPushButton, QScrollArea, QStackedWidget, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ... import theme
from . import mw_icons
from .model import BUILTIN_STYLES, settings

PANE_BG = "#e8eef7"
PANE_HEADER = "#b7c9e2"
PANE_QSS = f"""
QWidget#taskPane {{ background: {PANE_BG}; }}
QLabel {{ background: transparent; font-size: 11px; }}
QLabel#paneTitle {{ font-weight: bold; font-size: 12px; color: #17365d; }}
QLabel#sectionTitle {{
    font-weight: bold; color: #17365d; background: #d3e0f0;
    padding: 3px 6px; border: 1px solid #b7c9e2;
}}
QPushButton#link {{
    background: transparent; border: none; color: #0033aa; text-align: left;
    padding: 1px 2px; font-size: 11px;
}}
QPushButton#link:hover {{ color: #cc4400; text-decoration: underline; }}
QListWidget, QTreeWidget {{ background: white; border: 1px solid #9ab0cd; font-size: 11px; }}
QComboBox {{ background: white; font-size: 11px; }}
"""


def _link(text, slot=None, icon=None) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("link")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon:
        btn.setIcon(mw_icons.icon(icon, 16))
        btn.setIconSize(QSize(16, 16))
    if slot:
        btn.clicked.connect(slot)
    return btn


class StylePreviewList(QListWidget):
    """"Pick formatting to apply" -- each row is drawn in the style it names,
    which is the whole point of the pane."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet("QListWidget::item { padding: 3px; }")

    def load(self, styles):
        self.clear()
        for style in styles:
            item = QListWidgetItem(style.name)
            font = QFont(style.family, int(min(14, max(8, style.size))))
            font.setBold(style.bold)
            font.setItalic(style.italic)
            item.setFont(font)
            item.setForeground(QColor(style.color))
            item.setData(Qt.ItemDataRole.UserRole, style.name)
            self.addItem(item)


class TaskPane(QWidget):
    """The pane frame: title bar with back/forward/home and the pane menu."""

    PANES = [
        "Getting Started", "Help", "Search Results", "Clip Art", "Research",
        "Clipboard", "New Document", "Shared Workspace", "Document Updates",
        "Protect Document", "Styles and Formatting", "Reveal Formatting",
        "Mail Merge", "XML Structure",
    ]

    closed = pyqtSignal()

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setObjectName("taskPane")
        self.setStyleSheet(PANE_QSS)
        self.setFixedWidth(212)
        self._history: list[str] = []
        self._forward: list[str] = []
        self.pages: dict[str, QWidget] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = self._build_header()

        self.stack = QStackedWidget()
        for name, builder in (
                ("Getting Started", self._build_getting_started),
                ("New Document", self._build_new_document),
                ("Styles and Formatting", self._build_styles),
                ("Clipboard", self._build_clipboard),
                ("Reveal Formatting", self._build_reveal),
                ("Help", self._build_help),
        ):
            page = builder()
            self.pages[name] = page
            self.stack.addWidget(page)
        for action in self._pane_actions:
            action.setEnabled(action.text() in self.pages)
        root.addWidget(header)
        root.addWidget(self.stack, 1)
        self.show_pane("Getting Started", record=False)

    # -- chrome ----------------------------------------------------------

    def _build_header(self):
        bar = QWidget()
        bar.setFixedHeight(26)
        bar.setStyleSheet(f"background: {PANE_HEADER}; border-bottom: 1px solid #8fa6c4;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 0, 4, 0)
        row.setSpacing(2)

        for glyph, tip, slot in (("◀", "Back", self.go_back),
                                 ("▶", "Forward", self.go_forward),
                                 ("⌂", "Home", lambda: self.show_pane("Getting Started"))):
            btn = QToolButton()
            btn.setText(glyph)
            btn.setFixedSize(16, 16)
            btn.setToolTip(tip)
            btn.setStyleSheet("QToolButton { border: none; background: transparent;"
                              " color: #17365d; font-size: 9px; }"
                              "QToolButton:hover { background: #cfdcee; }")
            btn.clicked.connect(slot)
            row.addWidget(btn)

        self.title_label = QLabel("Getting Started")
        self.title_label.setObjectName("paneTitle")
        row.addWidget(self.title_label, 1)

        menu_btn = QToolButton()
        menu_btn.setText("▾")
        menu_btn.setFixedSize(14, 16)
        menu_btn.setStyleSheet("QToolButton { border: none; background: transparent;"
                               " color: #17365d; }")
        menu = QMenu(menu_btn)
        menu.setStyleSheet(theme.MENU_QSS)
        self._pane_actions = []
        for name in self.PANES:
            action = QAction(name, menu)
            action.triggered.connect(lambda _, n=name: self.show_pane(n))
            menu.addAction(action)
            self._pane_actions.append(action)
        menu_btn.setMenu(menu)
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        row.addWidget(menu_btn)

        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet("QToolButton { border: none; background: transparent;"
                                " color: #17365d; font-size: 9px; }"
                                "QToolButton:hover { background: #e0a0a0; }")
        close_btn.clicked.connect(self.closed.emit)
        row.addWidget(close_btn)
        return bar

    def _scroll_page(self) -> tuple[QWidget, QVBoxLayout]:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setStyleSheet(f"background: {PANE_BG};")
        inner = QWidget()
        inner.setStyleSheet(f"background: {PANE_BG};")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        area.setWidget(inner)
        return area, layout

    # -- panes -----------------------------------------------------------

    def _build_getting_started(self):
        page, layout = self._scroll_page()
        heading = QLabel("MacroHard Office Online")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        for label in ("Connect to MacroHard Office Online",
                      "Get the latest news about using Word",
                      "Automatically update this list",
                      "More..."):
            layout.addWidget(_link(label, self.owner.office_online))
        layout.addSpacing(6)

        heading = QLabel("Search for:")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        from PyQt6.QtWidgets import QLineEdit
        self.search_edit = QLineEdit()
        self.search_edit.returnPressed.connect(
            lambda: self.owner.search_help(self.search_edit.text()))
        layout.addWidget(self.search_edit)
        layout.addSpacing(6)

        heading = QLabel("Open")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(2)
        layout.addLayout(self.recent_box)
        layout.addWidget(_link("More...", self.owner.open_file, icon="open"))
        layout.addWidget(_link("Create a new document...", self.owner.new_file, icon="new"))
        layout.addStretch(1)
        self.refresh_recent()
        return page

    def refresh_recent(self):
        if not hasattr(self, "recent_box"):
            return
        while self.recent_box.count():
            item = self.recent_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        entries = settings.recent()
        if not entries:
            self.recent_box.addWidget(QLabel("    (no recent documents)"))
            return
        for entry in entries:
            self.recent_box.addWidget(
                _link(entry["name"], lambda _=False, e=entry: self.owner.open_recent(e),
                      icon="word_doc"))

    def _build_new_document(self):
        page, layout = self._scroll_page()
        for title, links in (
                ("New", [("Blank document", self.owner.new_file, "new"),
                         ("XML document", self.owner.new_file, "new"),
                         ("Web page", self.owner.new_file, "new"),
                         ("E-mail message", self.owner.new_file, "mail")]),
                ("Templates", [("Search online for:", None, None),
                               ("On my computer...", self.owner.new_from_template, None),
                               ("On my Web sites...", None, None)]),
                ("Recently used templates", [("Normal.dot", self.owner.new_file, "word_doc"),
                                             ("Elegant Letter.dot", self.owner.new_file,
                                              "word_doc"),
                                             ("Contemporary Resume.dot", self.owner.new_file,
                                              "word_doc")]),
        ):
            heading = QLabel(title)
            heading.setObjectName("sectionTitle")
            layout.addWidget(heading)
            for label, slot, icon in links:
                layout.addWidget(_link(label, slot, icon))
            layout.addSpacing(6)
        layout.addStretch(1)
        return page

    def _build_styles(self):
        page, layout = self._scroll_page()
        layout.addWidget(QLabel("Formatting of selected text"))
        self.current_style_label = QLabel("Normal")
        self.current_style_label.setStyleSheet(
            "background: white; border: 1px solid #9ab0cd; padding: 4px;")
        layout.addWidget(self.current_style_label)
        new_style = QPushButton("New Style...")
        new_style.setFixedHeight(22)
        new_style.clicked.connect(self.owner.new_style)
        layout.addWidget(new_style)
        layout.addSpacing(4)
        layout.addWidget(QLabel("Pick formatting to apply"))
        self.style_list = StylePreviewList()
        self.style_list.load(BUILTIN_STYLES)
        self.style_list.itemClicked.connect(
            lambda item: self.owner.apply_style(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.style_list, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Show:"))
        self.show_combo = QComboBox()
        self.show_combo.addItems(["Available formatting", "Formatting in use",
                                  "Available styles", "All styles"])
        row.addWidget(self.show_combo, 1)
        layout.addLayout(row)
        return page

    def _build_clipboard(self):
        page, layout = self._scroll_page()
        self.clipboard_count = QLabel("1 of 24 - Clipboard")
        layout.addWidget(self.clipboard_count)
        row = QHBoxLayout()
        paste_all = QPushButton("Paste All")
        paste_all.setFixedHeight(22)
        paste_all.clicked.connect(self.owner.paste_all_clipboard)
        clear_all = QPushButton("Clear All")
        clear_all.setFixedHeight(22)
        clear_all.clicked.connect(self.owner.clear_clipboard)
        row.addWidget(paste_all)
        row.addWidget(clear_all)
        layout.addLayout(row)
        layout.addWidget(QLabel("Click an item to paste:"))
        self.clipboard_list = QListWidget()
        self.clipboard_list.itemClicked.connect(
            lambda item: self.owner.paste_clipboard_item(
                item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.clipboard_list, 1)
        return page

    def refresh_clipboard(self, items: list[str]):
        if not hasattr(self, "clipboard_list"):
            return
        self.clipboard_list.clear()
        for index, text in enumerate(items):
            preview = text.strip().replace("\n", " ")[:60] or "(empty)"
            item = QListWidgetItem(preview)
            item.setIcon(mw_icons.icon("paste", 16))
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.clipboard_list.addItem(item)
        self.clipboard_count.setText(f"{len(items)} of 24 - Clipboard")

    def _build_reveal(self):
        page, layout = self._scroll_page()
        layout.addWidget(QLabel("Selected text"))
        self.reveal_sample = QLabel("Sample Text")
        self.reveal_sample.setStyleSheet(
            "background: white; border: 1px solid #9ab0cd; padding: 4px;")
        layout.addWidget(self.reveal_sample)
        layout.addWidget(QLabel("Formatting of selected text"))
        self.reveal_tree = QTreeWidget()
        self.reveal_tree.setHeaderHidden(True)
        layout.addWidget(self.reveal_tree, 1)
        return page

    def refresh_reveal(self, sample: str, groups: dict[str, list[tuple[str, str]]]):
        if not hasattr(self, "reveal_tree"):
            return
        self.reveal_sample.setText(sample or "(no selection)")
        self.reveal_tree.clear()
        for name, rows in groups.items():
            parent = QTreeWidgetItem([name])
            for label, value in rows:
                parent.addChild(QTreeWidgetItem([f"{label}: {value}"]))
            self.reveal_tree.addTopLevelItem(parent)
            parent.setExpanded(True)

    def _build_help(self):
        page, layout = self._scroll_page()
        heading = QLabel("Assistance")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        from PyQt6.QtWidgets import QLineEdit
        self.help_search = QLineEdit()
        self.help_search.returnPressed.connect(
            lambda: self.owner.search_help(self.help_search.text()))
        layout.addWidget(self.help_search)
        layout.addWidget(_link("Table of Contents", self.owner.help_contents))
        layout.addSpacing(6)
        heading = QLabel("MacroHard Office Online")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        for label in ("Assistance", "Training", "Communities", "Downloads"):
            layout.addWidget(_link(label, self.owner.office_online))
        layout.addSpacing(6)
        heading = QLabel("See also")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        layout.addWidget(_link("What's New", self.owner.help_contents))
        layout.addWidget(_link("Contact Us", self.owner.get_support))
        layout.addWidget(_link("Check for Updates", self.owner.check_updates))
        layout.addStretch(1)
        return page

    # -- navigation ------------------------------------------------------

    def show_pane(self, name: str, record=True):
        if name not in self.pages:
            return
        if record and self.title_label.text() != name:
            self._history.append(self.title_label.text())
            self._forward.clear()
        self.title_label.setText(name)
        self.stack.setCurrentWidget(self.pages[name])
        if name == "Getting Started":
            self.refresh_recent()

    def go_back(self):
        if self._history:
            self._forward.append(self.title_label.text())
            self.show_pane(self._history.pop(), record=False)

    def go_forward(self):
        if self._forward:
            self._history.append(self.title_label.text())
            self.show_pane(self._forward.pop(), record=False)

    def set_current_style(self, name: str):
        if hasattr(self, "current_style_label"):
            self.current_style_label.setText(name)
