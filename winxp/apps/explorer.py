"""Windows Explorer for the XP simulator.

Modelled on Explorer as it actually shipped in XP SP2 rather than on "a file
browser": one window hosts a menu bar, a Standard Buttons band, an Address
band, one Explorer Bar (common tasks / Folders / Search / Favorites /
History), one of five view modes, and a three-panel status bar. Everything
that mutates the vfs goes through a command method here so the confirmation
prompts, the shell-wide refresh and the undo stack stay in one place.

Supporting modules: explorer_shell (naming/format/sort rules),
explorer_views (the five view modes), explorer_panes (the Explorer Bar).
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QActionGroup, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMenuBar,
    QPushButton, QSizePolicy, QSplitter, QStackedWidget, QStatusBar, QToolButton,
    QVBoxLayout, QWidget,
)

from .. import corruption, icons, theme, vfs as vfs_mod
from ..properties_dialog import PropertiesDialog
from ..settings import settings
from ..window_manager import XPWindow
from ..xp_dialog import DIALOG_BUTTON_QSS, XPMessageBox, build_dialog_frame
from . import explorer_shell as shell
from .explorer_panes import (
    BrowseForFolderDialog, FoldersPane, LinkListPane, SearchPane, TaskPane,
)
from .explorer_views import (
    MODE_DETAILS, MODE_ICONS, MODE_LABELS, MODE_LIST, MODE_ORDER, ShellDetailsView,
    ShellIconView,
)
from .ie_widgets import RebarGrip

# The clipboard and the undo stack are shell-wide, not per-window: cutting in
# one Explorer window and pasting in another is the whole point of them.
_CLIPBOARD = {"ids": [], "cut": False}
_UNDO: list = []
_UNDO_LIMIT = 20

BAR_TASKS = "tasks"
BAR_FOLDERS = "folders"
BAR_SEARCH = "search"
BAR_FAVORITES = "favorites"
BAR_HISTORY = "history"
BAR_NONE = "none"

REBAR_QSS = """
QWidget#shellRebar { background: #ece9d8; }
QWidget#shellBand { background: #ece9d8; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 3px;
              padding: 2px 5px; color: #111111; }
QToolButton:hover { background: #f4f3ee; border-color: #b6b2a4; }
QToolButton:pressed, QToolButton:checked { background: #d8d5c8; border-color: #716f64; }
QToolButton:disabled { color: #8a897f; }
QToolButton::menu-button { border: 0; width: 12px; }
QComboBox { background: white; border: 1px solid #7f9db9; padding: 1px 3px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #316ac5;
                              selection-color: white; }
QLabel { background: transparent; }
"""

STATUS_QSS = """
QStatusBar { background: #ece9d8; border-top: 1px solid white; }
QStatusBar::item { border: 0; }
QLabel#statusPanel { border-left: 1px solid #aca899; padding: 1px 8px; }
"""


def _record_undo(label, undo_fn):
    _UNDO.append((label, undo_fn))
    del _UNDO[:-_UNDO_LIMIT]


class ChooseDetailsDialog(QDialog):
    """View > Choose Details... -- pick which columns the Details view shows."""

    def __init__(self, parent, available, active):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.columns = list(active)
        inner = build_dialog_frame(self, "Choose Details")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        hint = QLabel("Select the details you want to display for the files in this folder.")
        hint.setWordWrap(True)
        hint.setStyleSheet("background: transparent;")
        root.addWidget(hint)

        self.boxes = {}
        for col in available:
            box = QCheckBox(shell.COLUMN_LABELS[col])
            box.setChecked(col in active)
            box.setEnabled(col != shell.COL_NAME)
            box.setStyleSheet("background: transparent;")
            self.boxes[col] = box
            root.addWidget(box)
        root.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton("OK")
        ok.setFixedWidth(75)
        ok.clicked.connect(self._accept)
        cancel = QPushButton("Cancel")
        cancel.setFixedWidth(75)
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        root.addLayout(row)

        inner.addWidget(body)
        self.resize(300, 320)

    def _accept(self):
        self.columns = [col for col, box in self.boxes.items() if box.isChecked()]
        self.accept()

    @staticmethod
    def choose(parent, available, active):
        dlg = ChooseDetailsDialog(parent, available, active)
        center = parent.frameGeometry().center()
        dlg.move(center.x() - dlg.width() // 2, center.y() - dlg.height() // 2)
        return dlg.columns if dlg.exec() == QDialog.DialogCode.Accepted else None


class ExplorerWindow(XPWindow):
    def __init__(self, wm, start_node_id, explorer_bar=None):
        super().__init__(wm, title="Windows Explorer", icon_key="my_computer",
                         size=QSize(760, 520))
        self.current = start_node_id
        self.history = [start_node_id]
        self.hist_index = 0
        self.view_mode = settings.explorer_view if settings.explorer_view in MODE_ORDER else MODE_ICONS
        self.sort_column = settings.explorer_sort
        self.sort_desc = False
        self.show_groups = settings.explorer_groups
        self.detail_columns = None
        self.search_results = None
        self.search_label = ""
        self.explorer_bar = explorer_bar or BAR_TASKS

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setMenuBar(self._build_menu())
        root.addWidget(self._build_rebar())
        root.addWidget(self._build_body(), 1)
        self.status = self._build_status_bar()
        root.addWidget(self.status)
        self.set_content_layout(root)

        settings.folder_options_changed.connect(self._on_shell_changed)
        shell.shell_notifier.changed.connect(self._on_shell_changed)
        self._navigate(start_node_id, push=False)

    # ---------------------------------------------------------------- chrome
    def _act(self, menu, text, slot=None, shortcut=None, checkable=False,
             checked=False, enabled=True, icon_key=""):
        # These menus are rebuilt on every aboutToShow, so the accelerator is
        # only ever *shown* here (Qt right-aligns whatever follows a tab); the
        # working shortcuts are registered once in _build_menu.
        action = QAction(f"{text}\t{shortcut}" if shortcut else text, self)
        if icon_key:
            action.setIcon(icons.icon(icon_key, 16))
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.setEnabled(enabled and slot is not None)
        if slot:
            action.triggered.connect(lambda _=False: slot())
        menu.addAction(action)
        return action

    def _build_menu(self):
        bar = QMenuBar()
        theme.style_menubar(bar)
        self.file_menu = bar.addMenu("&File")
        self.file_menu.aboutToShow.connect(self._fill_file_menu)
        self.edit_menu = bar.addMenu("&Edit")
        self.edit_menu.aboutToShow.connect(self._fill_edit_menu)
        self.view_menu = bar.addMenu("&View")
        self.view_menu.aboutToShow.connect(self._fill_view_menu)
        self.fav_menu = bar.addMenu("F&avorites")
        self.fav_menu.aboutToShow.connect(self._fill_favorites_menu)
        tools = bar.addMenu("&Tools")
        self._act(tools, "&Map Network Drive...", self._map_network_drive)
        self._act(tools, "&Disconnect Network Drive...", enabled=False)
        tools.addSeparator()
        self._act(tools, "S&ynchronize...", self._synchronize)
        tools.addSeparator()
        self._act(tools, "F&older Options...", self._folder_options)
        help_menu = bar.addMenu("&Help")
        self._act(help_menu, "&Help and Support Center", self._help_center)
        help_menu.addSeparator()
        self._act(help_menu, "&Is This Copy of Windows Legal?", self._windows_legal)
        self._act(help_menu, "&About Windows", self._about)
        # Shortcuts that have no menu home of their own.
        for key, slot in (("F2", self.rename_selected), ("F5", self.refresh),
                          ("Del", self.delete_selected),
                          ("Shift+Del", lambda: self.delete_selected(permanent=True)),
                          ("Alt+Left", self.go_back), ("Alt+Right", self.go_forward),
                          ("Alt+Up", self.go_up), ("Ctrl+N", self.new_window),
                          ("Ctrl+X", self.cut_selection), ("Ctrl+C", self.copy_selection),
                          ("Ctrl+V", self.paste), ("Ctrl+Z", self.undo),
                          ("Ctrl+A", self.select_all), ("Backspace", self.go_up)):
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.triggered.connect(lambda _=False, s=slot: s())
            self.addAction(action)
        return bar

    def _tool_button(self, icon_key, text, slot, menu=None):
        btn = QToolButton()
        btn.setIcon(icons.icon(icon_key, 16))
        if text:
            btn.setText(text)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.clicked.connect(lambda: slot())
        if menu is not None:
            btn.setMenu(menu)
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        return btn

    def _build_rebar(self):
        wrap = QWidget()
        wrap.setObjectName("shellRebar")
        wrap.setStyleSheet(REBAR_QSS)
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.standard_band = self._build_standard_band()
        self.address_band = self._build_address_band()
        self.links_band = self._build_links_band()
        outer.addWidget(self.standard_band)
        outer.addWidget(self.address_band)
        outer.addWidget(self.links_band)
        self.links_band.hide()
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #aca899;")
        outer.addWidget(line)
        return wrap

    def _band(self):
        band = QWidget()
        band.setObjectName("shellBand")
        row = QHBoxLayout(band)
        row.setContentsMargins(0, 2, 4, 2)
        row.setSpacing(2)
        row.addWidget(RebarGrip())
        return band, row

    def _build_standard_band(self):
        band, row = self._band()
        self.back_menu = QMenu(self)
        self.back_menu.aboutToShow.connect(lambda: self._fill_history_menu(self.back_menu, -1))
        self.forward_menu = QMenu(self)
        self.forward_menu.aboutToShow.connect(lambda: self._fill_history_menu(self.forward_menu, 1))
        self.back_btn = self._tool_button("nav_back", "Back", self.go_back, self.back_menu)
        self.forward_btn = self._tool_button("nav_forward", "", self.go_forward, self.forward_menu)
        self.up_btn = self._tool_button("nav_up", "", self.go_up)
        self.up_btn.setToolTip("Up One Level")
        row.addWidget(self.back_btn)
        row.addWidget(self.forward_btn)
        row.addWidget(self.up_btn)
        row.addWidget(self._separator())
        self.search_btn = self._tool_button(
            "shell_search", "Search", lambda: self.toggle_explorer_bar(BAR_SEARCH))
        self.folders_btn = self._tool_button(
            "shell_folders", "Folders", lambda: self.toggle_explorer_bar(BAR_FOLDERS))
        self.search_btn.setCheckable(True)
        self.folders_btn.setCheckable(True)
        row.addWidget(self.search_btn)
        row.addWidget(self.folders_btn)
        row.addWidget(self._separator())
        self.views_menu = QMenu(self)
        self.views_menu.aboutToShow.connect(lambda: self._fill_views_menu(self.views_menu))
        views_btn = QToolButton()
        views_btn.setIcon(icons.icon("shell_views", 16))
        views_btn.setMenu(self.views_menu)
        views_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        views_btn.setToolTip("Views")
        row.addWidget(views_btn)
        row.addStretch(1)
        return band

    def _separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet("color: #aca899;")
        line.setFixedWidth(2)
        return line

    def _build_address_band(self):
        band, row = self._band()
        row.addWidget(QLabel("Address"))
        self.address = QComboBox()
        self.address.setEditable(True)
        self.address.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.address.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.address.activated.connect(self._on_address_activated)
        self.address.lineEdit().returnPressed.connect(self._on_address_entered)
        row.addWidget(self.address, 1)
        go = self._tool_button("nav_forward", "Go", self._on_address_entered)
        row.addWidget(go)
        return band

    def _build_links_band(self):
        band, row = self._band()
        row.addWidget(QLabel("Links"))
        for label, provider in (("My Documents", lambda: vfs_mod.vfs.my_docs_id),
                                 ("My Music", lambda: vfs_mod.vfs.my_music_id),
                                 ("My Computer", lambda: vfs_mod.vfs.root_id)):
            btn = QToolButton()
            btn.setText(label)
            btn.clicked.connect(lambda _=False, p=provider: self._navigate(p()))
            row.addWidget(btn)
        row.addStretch(1)
        return band

    def _build_body(self):
        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        self.task_pane = TaskPane()
        self.folders_pane = FoldersPane()
        self.folders_pane.folderSelected.connect(self._on_tree_selected)
        self.folders_pane.closeClicked.connect(lambda: self.set_explorer_bar(BAR_TASKS))
        self.folders_pane.dropped.connect(self.perform_drop)
        self.search_pane = SearchPane(lambda: self.current)
        self.search_pane.searchRequested.connect(self.run_search)
        self.search_pane.closeClicked.connect(lambda: self.set_explorer_bar(BAR_TASKS))
        self.favorites_pane = LinkListPane("Favorites")
        self.favorites_pane.itemChosen.connect(self._navigate)
        self.favorites_pane.closeClicked.connect(lambda: self.set_explorer_bar(BAR_TASKS))
        self.history_pane = LinkListPane("History")
        self.history_pane.itemChosen.connect(self._navigate)
        self.history_pane.closeClicked.connect(lambda: self.set_explorer_bar(BAR_TASKS))

        self.bar_stack = QStackedWidget()
        self._bar_index = {}
        for key, widget in ((BAR_TASKS, self.task_pane), (BAR_FOLDERS, self.folders_pane),
                            (BAR_SEARCH, self.search_pane), (BAR_FAVORITES, self.favorites_pane),
                            (BAR_HISTORY, self.history_pane)):
            self._bar_index[key] = self.bar_stack.addWidget(widget)
        # Width is the splitter's to hand out (the divider is draggable, as it
        # was in XP); a hard max here would leave dead space in the slot.
        self.bar_stack.setMinimumWidth(120)

        self.icon_view = ShellIconView(lambda: self.current)
        self.details_view = ShellDetailsView(lambda: self.current)
        for view in (self.icon_view, self.details_view):
            view.openRequested.connect(self.open_node)
            view.contextRequested.connect(self._on_context_menu)
            view.renameCommitted.connect(self._on_rename_committed)
            view.dropped.connect(self.perform_drop)
            view.backRequested.connect(self.go_back)
            view.itemSelectionChanged.connect(self._on_selection_changed)
        self.details_view.sortRequested.connect(self.set_sort)

        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.icon_view)
        self.view_stack.addWidget(self.details_view)

        splitter.addWidget(self.bar_stack)
        splitter.addWidget(self.view_stack)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 560])
        return splitter

    def _build_status_bar(self):
        bar = QStatusBar()
        bar.setStyleSheet(STATUS_QSS)
        bar.setSizeGripEnabled(False)
        self.status_objects = QLabel()
        self.status_objects.setObjectName("statusPanel")
        self.status_size = QLabel()
        self.status_size.setObjectName("statusPanel")
        self.status_size.setMinimumWidth(110)
        self.status_zone = QLabel("My Computer")
        self.status_zone.setObjectName("statusPanel")
        self.status_zone.setMinimumWidth(110)
        bar.addWidget(self.status_objects, 1)
        bar.addPermanentWidget(self.status_size)
        bar.addPermanentWidget(self.status_zone)
        return bar

    # ------------------------------------------------------------ navigation
    @property
    def in_search(self):
        return self.search_results is not None

    def _navigate(self, node_id, push=True):
        if corruption.guard_fs(self.wm):
            return
        node = vfs_mod.vfs.get(node_id)
        if node is None:
            return
        self.search_results = None
        self.current = node_id
        if push and (not self.history or self.history[self.hist_index] != node_id):
            del self.history[self.hist_index + 1:]
            self.history.append(node_id)
            self.hist_index = len(self.history) - 1
        self.setWindowTitle(node.name)
        self.titlebar.set_icon(shell.shell_icon(node, 16))
        self._refresh_address()
        self.refresh()

    def go_back(self):
        if self.hist_index > 0:
            self.hist_index -= 1
            self._navigate(self.history[self.hist_index], push=False)

    def go_forward(self):
        if self.hist_index < len(self.history) - 1:
            self.hist_index += 1
            self._navigate(self.history[self.hist_index], push=False)

    def go_up(self):
        node = vfs_mod.vfs.get(self.current)
        if node and node.parent:
            self._navigate(node.parent)

    def new_window(self):
        from . import launch
        launch(self.wm, f"explorer:{self.current}")

    def _on_tree_selected(self, node_id):
        if node_id != self.current:
            self._navigate(node_id)

    def _fill_history_menu(self, menu, direction):
        menu.clear()
        indices = (range(self.hist_index - 1, -1, -1) if direction < 0
                   else range(self.hist_index + 1, len(self.history)))
        for i in indices:
            node = vfs_mod.vfs.get(self.history[i])
            if not node:
                continue
            action = menu.addAction(shell.shell_icon(node, 16), node.name)
            action.triggered.connect(lambda _=False, idx=i: self._goto_history(idx))
        if menu.isEmpty():
            menu.addAction("(none)").setEnabled(False)

    def _goto_history(self, index):
        self.hist_index = index
        self._navigate(self.history[index], push=False)

    # -------------------------------------------------------------- address
    def _refresh_address(self):
        self.address.blockSignals(True)
        self.address.clear()
        places = [vfs_mod.vfs.root_id, vfs_mod.vfs.desktop_id, vfs_mod.vfs.my_docs_id,
                  vfs_mod.vfs.my_music_id, vfs_mod.vfs.recycle_id]
        places += [d.id for d in vfs_mod.vfs.drives()]
        if self.current not in places:
            places.append(self.current)
        for node_id in places:
            node = vfs_mod.vfs.get(node_id)
            if node:
                self.address.addItem(shell.shell_icon(node, 16),
                                     shell.shell_path(node_id), node_id)
        text = self.search_label if self.in_search else shell.shell_path(self.current)
        index = self.address.findData(self.current)
        if index >= 0 and not self.in_search:
            self.address.setCurrentIndex(index)
        self.address.setEditText(text)
        self.address.blockSignals(False)

    def _on_address_activated(self, index):
        node_id = self.address.itemData(index)
        if node_id:
            self._navigate(node_id)

    def _on_address_entered(self):
        text = self.address.currentText().strip()
        if not text:
            return
        node_id = self._resolve_path(text)
        if node_id:
            self._navigate(node_id)
        else:
            XPMessageBox.critical(
                self, "Windows Explorer",
                f"Windows cannot find '{text}'. Check the spelling and try again, "
                "or try searching for the item by clicking the Start button and "
                "then clicking Search."
            )
            self._refresh_address()

    def _resolve_path(self, text):
        wanted = text.rstrip("\\").lower()
        for node_id, node in vfs_mod.vfs.nodes.items():
            if node.kind != vfs_mod.FOLDER:
                continue
            if shell.shell_path(node_id).rstrip("\\").lower() == wanted:
                return node_id
            if node.name.lower() == wanted and node.parent == self.current:
                return node_id
        return None

    # -------------------------------------------------------------- refresh
    def refresh(self):
        try:
            self._refresh_view()
            self._refresh_bar()
            self._refresh_status()
        except RuntimeError:
            pass  # window closed while a shell-wide refresh was in flight

    def _on_shell_changed(self):
        self.refresh()

    def _columns_for_current(self):
        if self.detail_columns:
            return self.detail_columns
        if self.in_search:
            return [shell.COL_NAME, shell.COL_INFOLDER, shell.COL_SIZE, shell.COL_TYPE,
                    shell.COL_MODIFIED]
        if self.current == vfs_mod.vfs.root_id:
            return [shell.COL_NAME, shell.COL_TYPE, shell.COL_TOTAL, shell.COL_FREE]
        if self.current == vfs_mod.vfs.recycle_id:
            return [shell.COL_NAME, shell.COL_ORIGIN, shell.COL_DELETED, shell.COL_SIZE,
                    shell.COL_TYPE]
        return [shell.COL_NAME, shell.COL_SIZE, shell.COL_TYPE, shell.COL_MODIFIED]

    def _current_nodes(self):
        if self.in_search:
            nodes = list(self.search_results)
            nodes.sort(key=lambda n: shell.sort_key(n, self.sort_column), reverse=self.sort_desc)
            return nodes
        return shell.visible_children(self.current, self.sort_column, self.sort_desc)

    def _entries(self, nodes):
        if self.current == vfs_mod.vfs.root_id and not self.in_search:
            return self._root_entries(nodes)
        if not self.show_groups or self.view_mode == MODE_LIST:
            return [("node", n) for n in nodes]
        entries = []
        heading = None
        for node in nodes:
            group = shell.group_heading(node, self.sort_column)
            if group != heading:
                heading = group
                entries.append(("header", group))
            entries.append(("node", node))
        return entries

    def _root_entries(self, nodes):
        """My Computer always groups, regardless of Show in Groups -- the
        drive list was a special view, not an ordinary folder."""
        buckets = [("Files Stored on This Computer", []), ("Hard Disk Drives", []),
                   ("Devices with Removable Storage", [])]
        for node in nodes:
            if node.drive == vfs_mod.DRIVE_FIXED:
                buckets[1][1].append(node)
            elif node.drive:
                buckets[2][1].append(node)
            else:
                buckets[0][1].append(node)
        entries = []
        for title, group in buckets:
            if not group:
                continue
            entries.append(("header", title))
            entries.extend(("node", n) for n in group)
        return entries

    def _refresh_view(self):
        nodes = self._current_nodes()
        selected = set(self._selection_ids())
        cut_ids = set(_CLIPBOARD["ids"]) if _CLIPBOARD["cut"] else set()
        entries = self._entries(nodes)
        if self.view_mode == MODE_DETAILS:
            self.details_view.set_columns(self._columns_for_current())
            self.details_view.set_entries(entries, cut_ids)
            self.view_stack.setCurrentWidget(self.details_view)
        else:
            if self.icon_view.mode != self.view_mode:
                self.icon_view.set_mode(self.view_mode)
            self.icon_view.set_entries(entries, cut_ids)
            self.view_stack.setCurrentWidget(self.icon_view)
        if selected:
            self.view().select_ids(selected)
        self.search_btn.setChecked(self.explorer_bar == BAR_SEARCH)
        self.folders_btn.setChecked(self.explorer_bar == BAR_FOLDERS)
        self.back_btn.setEnabled(self.hist_index > 0)
        self.forward_btn.setEnabled(self.hist_index < len(self.history) - 1)
        node = vfs_mod.vfs.get(self.current)
        self.up_btn.setEnabled(bool(node and node.parent))

    def view(self):
        return self.details_view if self.view_mode == MODE_DETAILS else self.icon_view

    def _refresh_status(self):
        nodes = self._current_nodes()
        selected = self.selected_nodes()
        if selected:
            self.status_objects.setText(f"{len(selected)} objects selected")
            total = sum(shell.size_of(n) for n in selected)
        else:
            self.status_objects.setText(f"{len(nodes)} objects")
            total = sum(shell.size_of(n) for n in nodes)
        self.status_size.setText(shell.format_bytes(total) if total else "")

    def _on_selection_changed(self):
        self._refresh_status()
        if self.explorer_bar == BAR_TASKS:
            self._refresh_bar()

    # ---------------------------------------------------------- explorer bar
    def set_explorer_bar(self, kind):
        self.explorer_bar = kind
        if kind == BAR_NONE:
            self.bar_stack.hide()
        else:
            self.bar_stack.show()
            self.bar_stack.setCurrentIndex(self._bar_index[kind])
        self.refresh()

    def toggle_explorer_bar(self, kind):
        self.set_explorer_bar(BAR_TASKS if self.explorer_bar == kind else kind)

    def _refresh_bar(self):
        if self.explorer_bar == BAR_TASKS:
            self.task_pane.rebuild(self._task_groups())
        elif self.explorer_bar == BAR_FOLDERS:
            self.folders_pane.rebuild(self.current)
        elif self.explorer_bar == BAR_SEARCH:
            self.search_pane.refresh_scope()
        elif self.explorer_bar == BAR_FAVORITES:
            self.favorites_pane.set_places(settings.explorer_favorites)
        elif self.explorer_bar == BAR_HISTORY:
            self.history_pane.set_places(list(dict.fromkeys(reversed(self.history))))

    def _task_groups(self):
        selected = self.selected_nodes()
        groups = []
        if self.current == vfs_mod.vfs.recycle_id:
            links = [("task_empty", "Empty the Recycle Bin", self.empty_recycle_bin)]
            if len(selected) == 1:
                links.append(("task_restore", "Restore this item", self.restore_selected))
            elif selected:
                links.append(("task_restore", "Restore the selected items", self.restore_selected))
            else:
                links.append(("task_restore", "Restore all items", self.restore_all))
            groups.append(("Recycle Bin Tasks", links))
        elif self.current == vfs_mod.vfs.root_id:
            groups.append(("System Tasks", [
                ("cp_system", "View system information", lambda: self._launch_applet("system")),
                ("cp_programs", "Add or remove programs", lambda: self._launch_applet("programs")),
                ("control_panel", "Change a setting", lambda: self._launch("control_panel")),
            ]))
        else:
            groups.append(("File and Folder Tasks", self._file_task_links(selected)))
        groups.append(("Other Places", self._other_places_links()))
        groups.append(("Details", [self._details_widget(selected)]))
        return groups

    def _file_task_links(self, selected):
        if not selected:
            return [
                ("task_newfolder", "Make a new folder", self.new_folder),
                ("task_publish", "Publish this folder to the Web", self.publish_to_web),
                ("task_share", "Share this folder", lambda: self.show_properties(self.current)),
            ]
        if len(selected) > 1:
            return [
                ("task_move", "Move the selected items", self.move_to_folder),
                ("task_copy", "Copy the selected items", self.copy_to_folder),
                ("task_publish", "Publish the selected items to the Web", self.publish_to_web),
                ("task_email", "E-mail the selected items", self.email_selection),
                ("task_delete", "Delete the selected items", self.delete_selected),
            ]
        node = selected[0]
        noun = "folder" if node.kind == vfs_mod.FOLDER else "file"
        links = [
            ("task_rename", f"Rename this {noun}", self.rename_selected),
            ("task_move", f"Move this {noun}", self.move_to_folder),
            ("task_copy", f"Copy this {noun}", self.copy_to_folder),
            ("task_publish", f"Publish this {noun} to the Web", self.publish_to_web),
        ]
        if node.kind == vfs_mod.FOLDER:
            links.append(("task_share", "Share this folder", lambda: self.show_properties(node.id)))
            links.append(("task_email", "E-mail this folder's files", self.email_selection))
        else:
            links.append(("task_email", "E-mail this file", self.email_selection))
            if node.kind in (vfs_mod.TEXT, vfs_mod.RICH, vfs_mod.IMAGE):
                links.append(("task_print", "Print this file", self.print_selection))
        links.append(("task_delete", f"Delete this {noun}", self.delete_selected))
        return links

    def _other_places_links(self):
        node = vfs_mod.vfs.get(self.current)
        links = []
        parent = vfs_mod.vfs.get(node.parent) if node and node.parent else None
        if parent:
            links.append((shell.icon_key(parent), parent.name,
                          lambda pid=parent.id: self._navigate(pid)))
        for node_id, icon_key in ((vfs_mod.vfs.my_docs_id, "my_documents"),
                                   (vfs_mod.vfs.my_music_id, "folder"),
                                   (vfs_mod.vfs.root_id, "my_computer")):
            place = vfs_mod.vfs.get(node_id)
            if place and node_id != self.current and (not parent or node_id != parent.id):
                links.append((icon_key, place.name, lambda pid=node_id: self._navigate(pid)))
        links.append(("shared_docs", "Shared Documents", self.no_shared_documents))
        links.append(("my_network", "My Network Places", self.no_network_places))
        return links

    def _details_widget(self, selected):
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        node = selected[0] if len(selected) == 1 else vfs_mod.vfs.get(self.current)
        if node is None:
            return box
        title = QLabel(vfs_mod.display_name(node))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: bold; background: transparent;")
        lay.addWidget(title)
        rows = [shell.type_label(node)]
        if len(selected) > 1:
            rows = [f"{len(selected)} items selected"]
            total = sum(shell.size_of(n) for n in selected)
            if total:
                rows.append(f"Total File Size: {shell.format_bytes(total)}")
        else:
            if node.drive:
                used, total = vfs_mod.vfs.drive_usage(node.id)
                if total:
                    rows.append(f"Free Space: {shell.format_bytes(total - used)}")
                    rows.append(f"Total Size: {shell.format_bytes(total)}")
            else:
                rows.append(f"Date Modified: {shell.format_date(node.modified)}")
                size = shell.size_of(node)
                if size:
                    rows.append(f"Size: {shell.format_bytes(size)}")
            if node.kind == vfs_mod.IMAGE:
                pm = QPixmap()
                pm.loadFromData(vfs_mod.vfs.read_blob(node.id))
                if not pm.isNull():
                    rows.append(f"Dimensions: {pm.width()} x {pm.height()}")
        for text in rows:
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet("background: transparent; color: #1a1a1a;")
            lay.addWidget(label)
        if node.kind == vfs_mod.IMAGE:
            preview = QLabel()
            preview.setPixmap(shell.thumbnail(node, 90))
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setStyleSheet("background: transparent; padding-top: 4px;")
            lay.addWidget(preview)
        return box

    # ------------------------------------------------------------- selection
    def _selection_ids(self):
        try:
            return self.view().selected_ids()
        except RuntimeError:
            return []

    def selected_nodes(self):
        return [n for n in (vfs_mod.vfs.get(i) for i in self._selection_ids()) if n]

    def select_all(self):
        self.view().selectAll()

    def invert_selection(self):
        self.view().invert_selection()

    # ---------------------------------------------------------------- open
    def open_node(self, node_id):
        if corruption.guard_fs(self.wm):
            return
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        if node.drive and not shell.has_media(node):
            letter = node.name[node.name.rfind("(") + 1: node.name.rfind(")")]
            XPMessageBox.critical(self, node.name,
                                  f"Please insert a disk into drive {letter}")
            return
        if node.parent == vfs_mod.vfs.recycle_id:
            # Items in the bin aren't launchable until they're restored; XP
            # opened their Properties instead of the file itself.
            self.show_properties(node_id)
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

    def explore_node(self, node_id):
        from . import launch
        window = launch(self.wm, f"explorer:{node_id}")
        if window is not None:
            window.set_explorer_bar(BAR_FOLDERS)

    def _launch(self, app_id):
        from . import launch
        launch(self.wm, f"app:{app_id}")

    def _launch_applet(self, module):
        import importlib
        from .control_panel import APPLETS
        for name, class_name, _icon, _title, _tip in APPLETS:
            if name == module:
                mod = importlib.import_module(f"winxp.apps.control_panel.{module}")
                self.wm.open(getattr(mod, class_name)(self.wm))
                return

    # ------------------------------------------------------------- menu fill
    def _fill_file_menu(self):
        menu = self.file_menu
        menu.clear()
        selected = self.selected_nodes()
        one = selected[0] if len(selected) == 1 else None
        if one is not None and (one.kind == vfs_mod.FOLDER or one.drive):
            self._act(menu, "&Open", lambda: self.open_node(one.id))
            self._act(menu, "&Explore", lambda: self.explore_node(one.id))
            self._act(menu, "&Search...", lambda: self.set_explorer_bar(BAR_SEARCH))
            menu.addSeparator()
        elif one is not None:
            self._act(menu, "&Open", lambda: self.open_node(one.id))
            self._act(menu, "P&rint", self.print_selection)
            menu.addSeparator()
        self._fill_new_menu(menu.addMenu("Ne&w"))
        menu.addSeparator()
        self._act(menu, "Create &Shortcut", self.create_shortcut_selected,
                  enabled=bool(selected))
        self._act(menu, "&Delete", self.delete_selected, enabled=bool(selected))
        self._act(menu, "Rena&me", self.rename_selected, enabled=len(selected) == 1)
        menu.addSeparator()
        self._act(menu, "P&roperties", self.properties_selected)
        menu.addSeparator()
        self._act(menu, "&Close", self.close)

    def _fill_new_menu(self, menu):
        self._act(menu, "&Folder", self.new_folder, icon_key="folder")
        self._act(menu, "&Shortcut", self.new_shortcut, icon_key="text_file")
        menu.addSeparator()
        self._act(menu, "&Text Document", self.new_text, icon_key="text_file")
        self._act(menu, "&Rich Text Document", self.new_rich, icon_key="mword")
        self._act(menu, "&Bitmap Image", self.new_image, icon_key="bitmap_file")
        self._act(menu, "&Wave Sound", self.new_wave, icon_key="audio_file")
        return menu

    def _fill_edit_menu(self):
        menu = self.edit_menu
        menu.clear()
        selected = self.selected_nodes()
        label = f"&Undo {_UNDO[-1][0]}" if _UNDO else "Can't &Undo"
        self._act(menu, label, self.undo if _UNDO else None, "Ctrl+Z")
        menu.addSeparator()
        self._act(menu, "Cu&t", self.cut_selection, "Ctrl+X", enabled=bool(selected))
        self._act(menu, "&Copy", self.copy_selection, "Ctrl+C", enabled=bool(selected))
        self._act(menu, "&Paste", self.paste, "Ctrl+V", enabled=bool(_CLIPBOARD["ids"]))
        self._act(menu, "Paste &Shortcut", self.paste_shortcut,
                  enabled=bool(_CLIPBOARD["ids"]))
        menu.addSeparator()
        self._act(menu, "Copy To Folder...", self.copy_to_folder, enabled=bool(selected))
        self._act(menu, "Move To Folder...", self.move_to_folder, enabled=bool(selected))
        menu.addSeparator()
        self._act(menu, "Select &All", self.select_all, "Ctrl+A")
        self._act(menu, "&Invert Selection", self.invert_selection)

    def _fill_view_menu(self):
        menu = self.view_menu
        menu.clear()
        toolbars = menu.addMenu("&Toolbars")
        self._act(toolbars, "&Standard Buttons",
                  lambda: self._toggle_band(self.standard_band), checkable=True,
                  checked=self.standard_band.isVisible())
        self._act(toolbars, "&Address Bar", lambda: self._toggle_band(self.address_band),
                  checkable=True, checked=self.address_band.isVisible())
        self._act(toolbars, "&Links", lambda: self._toggle_band(self.links_band),
                  checkable=True, checked=self.links_band.isVisible())
        toolbars.addSeparator()
        self._act(toolbars, "Loc&k the Toolbars", lambda: None, checkable=True, checked=True)
        self._act(toolbars, "&Customize...")
        self._act(menu, "Status &Bar", lambda: self.status.setVisible(not self.status.isVisible()),
                  checkable=True, checked=self.status.isVisible())
        bars = menu.addMenu("E&xplorer Bar")
        for key, text in ((BAR_SEARCH, "&Search"), (BAR_FAVORITES, "&Favorites"),
                          (BAR_HISTORY, "&History"), (BAR_FOLDERS, "F&olders")):
            self._act(bars, text, lambda k=key: self.set_explorer_bar(k),
                      checkable=True, checked=self.explorer_bar == key)
        bars.addSeparator()
        self._act(bars, "&Tip of the Day")
        menu.addSeparator()
        group = QActionGroup(self)
        for mode in MODE_ORDER:
            action = self._act(menu, MODE_LABELS[mode], lambda m=mode: self.set_view_mode(m),
                               checkable=True, checked=self.view_mode == mode)
            group.addAction(action)
        menu.addSeparator()
        self._fill_arrange_menu(menu.addMenu("Arrange &Icons by"))
        self._act(menu, "C&hoose Details...", self.choose_details)
        menu.addSeparator()
        goto = menu.addMenu("&Go To")
        self._act(goto, "&Back", self.go_back, "Alt+Left", enabled=self.hist_index > 0)
        self._act(goto, "&Forward", self.go_forward, "Alt+Right",
                  enabled=self.hist_index < len(self.history) - 1)
        self._act(goto, "&Up One Level", self.go_up)
        goto.addSeparator()
        self._act(goto, "&Home Page", lambda: self._launch("ie"))
        menu.addSeparator()
        self._act(menu, "R&efresh", self.refresh, "F5")

    def _fill_arrange_menu(self, menu):
        group = QActionGroup(self)
        for column in (shell.COL_NAME, shell.COL_SIZE, shell.COL_TYPE, shell.COL_MODIFIED):
            action = self._act(menu, shell.COLUMN_LABELS[column],
                               lambda c=column: self.set_sort(c, keep_direction=True),
                               checkable=True, checked=self.sort_column == column)
            group.addAction(action)
        menu.addSeparator()
        self._act(menu, "Show in &Groups", self.toggle_groups, checkable=True,
                  checked=self.show_groups, enabled=self.view_mode != MODE_LIST)
        self._act(menu, "Auto &Arrange", lambda: None, checkable=True, checked=True)
        self._act(menu, "Align to &Grid", lambda: None, checkable=True, checked=True)

    def _fill_favorites_menu(self):
        menu = self.fav_menu
        menu.clear()
        self._act(menu, "&Add to Favorites...", self.add_to_favorites)
        self._act(menu, "&Organize Favorites...", self.organize_favorites,
                  enabled=bool(settings.explorer_favorites))
        menu.addSeparator()
        for node_id in settings.explorer_favorites:
            node = vfs_mod.vfs.get(node_id)
            if not node:
                continue
            action = menu.addAction(shell.shell_icon(node, 16), node.name)
            action.triggered.connect(lambda _=False, nid=node_id: self._navigate(nid))
        if not settings.explorer_favorites:
            menu.addAction("(Empty)").setEnabled(False)

    def _fill_views_menu(self, menu):
        menu.clear()
        for mode in MODE_ORDER:
            action = menu.addAction(MODE_LABELS[mode].replace("&", ""))
            action.setCheckable(True)
            action.setChecked(self.view_mode == mode)
            action.triggered.connect(lambda _=False, m=mode: self.set_view_mode(m))

    def _toggle_band(self, band):
        band.setVisible(not band.isVisible())

    # ---------------------------------------------------------- context menu
    def _on_context_menu(self, pos):
        view = self.view()
        menu = QMenu(self)
        selected = self.selected_nodes()
        if selected:
            one = selected[0] if len(selected) == 1 else None
            if one is not None:
                bold = self._act(menu, "&Open", lambda: self.open_node(one.id))
                font = bold.font()
                font.setBold(True)
                bold.setFont(font)
                if one.kind == vfs_mod.FOLDER or one.drive:
                    self._act(menu, "&Explore", lambda: self.explore_node(one.id))
                    self._act(menu, "&Search...", lambda: self.set_explorer_bar(BAR_SEARCH))
                menu.addSeparator()
            if self.current == vfs_mod.vfs.recycle_id:
                self._act(menu, "R&estore", self.restore_selected)
                menu.addSeparator()
            self._act(menu, "Cu&t", self.cut_selection)
            self._act(menu, "&Copy", self.copy_selection)
            menu.addSeparator()
            self._act(menu, "Create &Shortcut", self.create_shortcut_selected)
            self._act(menu, "&Delete", self.delete_selected)
            self._act(menu, "Rena&me", self.rename_selected, enabled=one is not None)
            menu.addSeparator()
            self._act(menu, "P&roperties", self.properties_selected)
        else:
            view_menu = menu.addMenu("&View")
            for mode in MODE_ORDER:
                action = view_menu.addAction(MODE_LABELS[mode].replace("&", ""))
                action.setCheckable(True)
                action.setChecked(self.view_mode == mode)
                action.triggered.connect(lambda _=False, m=mode: self.set_view_mode(m))
            self._fill_arrange_menu(menu.addMenu("Arrange &Icons by"))
            self._act(menu, "Re&fresh", self.refresh)
            menu.addSeparator()
            self._act(menu, "&Paste", self.paste, enabled=bool(_CLIPBOARD["ids"]))
            self._act(menu, "Paste &Shortcut", self.paste_shortcut,
                      enabled=bool(_CLIPBOARD["ids"]))
            menu.addSeparator()
            if self.current == vfs_mod.vfs.recycle_id:
                self._act(menu, "&Empty Recycle Bin", self.empty_recycle_bin)
                menu.addSeparator()
            self._fill_new_menu(menu.addMenu("Ne&w"))
            menu.addSeparator()
            self._act(menu, "P&roperties", lambda: self.show_properties(self.current))
        menu.exec(view.viewport().mapToGlobal(pos))

    # -------------------------------------------------------------- view ops
    def set_view_mode(self, mode):
        self.view_mode = mode
        if mode == MODE_LIST:
            self.show_groups = False
        settings.set_explorer_view(mode, self.sort_column, self.show_groups)
        self.refresh()

    def set_sort(self, column, keep_direction=False):
        if column == self.sort_column and not keep_direction:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_desc = False
        self.sort_column = column
        settings.set_explorer_view(self.view_mode, column, self.show_groups)
        self.refresh()

    def toggle_groups(self):
        self.show_groups = not self.show_groups
        settings.set_explorer_view(self.view_mode, self.sort_column, self.show_groups)
        self.refresh()

    def choose_details(self):
        available = [shell.COL_NAME, shell.COL_SIZE, shell.COL_TYPE, shell.COL_MODIFIED,
                     shell.COL_ORIGIN, shell.COL_DELETED, shell.COL_TOTAL, shell.COL_FREE,
                     shell.COL_INFOLDER, shell.COL_COMMENTS]
        chosen = ChooseDetailsDialog.choose(self, available, self._columns_for_current())
        if chosen:
            self.detail_columns = chosen
            self.set_view_mode(MODE_DETAILS)

    # -------------------------------------------------------------- file ops
    def _notify(self):
        shell.shell_notifier.changed.emit()

    def _new_node(self, factory, label):
        if corruption.guard_fs(self.wm):
            return
        node = factory()
        if node is None:
            return
        _record_undo(label, lambda nid=node.id: vfs_mod.vfs.delete(nid, permanent=True))
        self._notify()
        self.view().select_ids([node.id])
        self.rename_selected()

    def new_folder(self):
        self._new_node(lambda: vfs_mod.vfs.create_folder(self.current), "New")

    def new_text(self):
        self._new_node(lambda: vfs_mod.vfs.create_text_file(self.current), "New")

    def new_rich(self):
        self._new_node(lambda: vfs_mod.vfs.create_rich_file(self.current), "New")

    def new_image(self):
        from .. import image_codec
        self._new_node(lambda: vfs_mod.vfs.create_image_file(
            self.current, data=image_codec.to_bytes(image_codec.blank())), "New")

    def new_wave(self):
        self._new_node(lambda: vfs_mod.vfs.create_audio_file(
            self.current, "New Wave Sound.wav", b"", ".wav"), "New")

    def new_shortcut(self):
        self._new_node(lambda: vfs_mod.vfs.create_shortcut(
            self.current, "New Shortcut", "explorer:mydocs", "my_documents"), "New")

    def create_shortcut_selected(self):
        if corruption.guard_fs(self.wm):
            return
        created = []
        for node in self.selected_nodes():
            target = node.target if node.kind == vfs_mod.SHORTCUT else f"explorer:{node.id}"
            if node.kind not in (vfs_mod.FOLDER, vfs_mod.SHORTCUT):
                target = f"{self._app_for(node)}:{node.id}"
            new = vfs_mod.vfs.create_shortcut(self.current, f"Shortcut to {node.name}",
                                              target, shell.icon_key(node))
            created.append(new.id)
        if created:
            _record_undo("Create Shortcut", lambda ids=created: [
                vfs_mod.vfs.delete(i, permanent=True) for i in ids])
            self._notify()

    @staticmethod
    def _app_for(node):
        return {vfs_mod.TEXT: "notepad", vfs_mod.RICH: "mword", vfs_mod.IMAGE: "paint",
                vfs_mod.AUDIO: "wmp", vfs_mod.VIDEO: "wmp"}.get(node.kind, "notepad")

    def rename_selected(self):
        if corruption.guard_fs(self.wm):
            return
        ids = self._selection_ids()
        if len(ids) == 1:
            self.view().begin_rename(ids[0])

    def _on_rename_committed(self, node_id, text):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        new_name = text.strip()
        if (new_name and "." not in new_name and not settings.show_extensions
                and node.kind in vfs_mod.EXTENSIONED_KINDS and "." in node.name):
            # Extensions-hidden mode edits only the stem; put the real
            # extension back so committing can't silently drop it.
            new_name += node.name[node.name.rfind("."):]
        if not new_name or new_name == node.name:
            self.refresh()
            return
        if any(c.name.lower() == new_name.lower() and c.id != node_id
               for c in vfs_mod.vfs.children_of(node.parent)):
            XPMessageBox.critical(
                self, "Error Renaming File or Folder",
                f"Cannot rename {vfs_mod.display_name(node)}: A file with the name you "
                "specified already exists. Specify a different file name."
            )
            self.refresh()
            return
        old_name = node.name
        vfs_mod.vfs.rename(node_id, new_name)
        _record_undo("Rename", lambda nid=node_id, n=old_name: vfs_mod.vfs.rename(nid, n))
        self._notify()

    def delete_selected(self, permanent=False):
        if corruption.guard_fs(self.wm):
            return
        nodes = self.selected_nodes()
        if not nodes:
            return
        blocked = [n for n in nodes if n.read_only]
        if blocked:
            XPMessageBox.critical(
                self, "Error Deleting File or Folder",
                f"Cannot delete {blocked[0].name}: It is being used by another person "
                "or program, or it is Read-only.\n\nClear the Read-only attribute from "
                "its Properties and try again."
            )
            return
        in_bin = all(n.parent == vfs_mod.vfs.recycle_id for n in nodes)
        permanent = permanent or in_bin
        if not self._confirm_delete(nodes, permanent):
            return
        recycled = []
        for node in nodes:
            vfs_mod.vfs.delete(node.id, permanent=permanent)
            if corruption.guard_system_file(self.wm, node):
                return
            if not permanent:
                recycled.append(node.id)
        if recycled:
            _record_undo("Delete", lambda ids=recycled: [
                vfs_mod.vfs.restore(i) for i in ids])
        self._notify()

    def _confirm_delete(self, nodes, permanent):
        if len(nodes) > 1:
            verb = "delete these" if permanent else "send these"
            tail = "" if permanent else " to the Recycle Bin"
            return XPMessageBox.confirm(
                self, "Confirm Multiple File Delete",
                f"Are you sure you want to {verb} {len(nodes)} items{tail}?")
        node = nodes[0]
        name = vfs_mod.display_name(node)
        if node.kind == vfs_mod.FOLDER:
            title = "Confirm Folder Delete"
            text = (f"Are you sure you want to remove the folder '{name}' and move all "
                    "its contents to the Recycle Bin?") if not permanent else (
                    f"Are you sure you want to remove the folder '{name}' and all its contents?")
        else:
            title = "Confirm File Delete"
            text = (f"Are you sure you want to send '{name}' to the Recycle Bin?"
                    if not permanent else f"Are you sure you want to delete '{name}'?")
        return XPMessageBox.confirm(self, title, text)

    def restore_selected(self):
        if corruption.guard_fs(self.wm):
            return
        for node_id in self._selection_ids():
            vfs_mod.vfs.restore(node_id)
        self._notify()

    def restore_all(self):
        if corruption.guard_fs(self.wm):
            return
        for child in list(vfs_mod.vfs.children_of(vfs_mod.vfs.recycle_id)):
            vfs_mod.vfs.restore(child.id)
        self._notify()

    def empty_recycle_bin(self):
        if corruption.guard_fs(self.wm):
            return
        items = vfs_mod.vfs.children_of(vfs_mod.vfs.recycle_id)
        if not items:
            return
        text = (f"Are you sure you want to delete these {len(items)} items?"
                if len(items) > 1 else
                f"Are you sure you want to delete '{items[0].name}'?")
        if XPMessageBox.confirm(self, "Confirm Multiple File Delete", text):
            vfs_mod.vfs.empty_recycle_bin()
            self._notify()

    def properties_selected(self):
        ids = self._selection_ids()
        self.show_properties(ids[0] if ids else self.current)

    def show_properties(self, node_id):
        if corruption.guard_fs(self.wm):
            return
        PropertiesDialog.show_for(self, node_id)
        self._notify()

    # ------------------------------------------------------------- clipboard
    def cut_selection(self):
        ids = self._selection_ids()
        if ids:
            _CLIPBOARD.update(ids=ids, cut=True)
            self._notify()

    def copy_selection(self):
        ids = self._selection_ids()
        if ids:
            _CLIPBOARD.update(ids=ids, cut=False)
            self._notify()

    def paste(self):
        if corruption.guard_fs(self.wm):
            return
        ids = [i for i in _CLIPBOARD["ids"] if vfs_mod.vfs.get(i)]
        if not ids:
            return
        if _CLIPBOARD["cut"]:
            self._move_nodes(ids, self.current, "Move")
            _CLIPBOARD.update(ids=[], cut=False)
        else:
            self._copy_nodes(ids, self.current)
        self._notify()

    def paste_shortcut(self):
        if corruption.guard_fs(self.wm):
            return
        created = []
        for node_id in _CLIPBOARD["ids"]:
            node = vfs_mod.vfs.get(node_id)
            if not node:
                continue
            target = node.target if node.kind == vfs_mod.SHORTCUT else (
                f"explorer:{node.id}" if node.kind == vfs_mod.FOLDER
                else f"{self._app_for(node)}:{node.id}")
            created.append(vfs_mod.vfs.create_shortcut(
                self.current, f"Shortcut to {node.name}", target, shell.icon_key(node)).id)
        if created:
            _record_undo("Paste Shortcut", lambda c=created: [
                vfs_mod.vfs.delete(i, permanent=True) for i in c])
            self._notify()

    def _copy_nodes(self, node_ids, target_id):
        created = []
        for node_id in node_ids:
            node = vfs_mod.vfs.get(node_id)
            if not node:
                continue
            if node.kind == vfs_mod.FOLDER and self._is_ancestor(node_id, target_id):
                XPMessageBox.critical(
                    self, "Error Copying File or Folder",
                    f"Cannot copy {node.name}: The destination folder is a subfolder "
                    "of the source folder.")
                continue
            # Pasting into the folder it came from is XP's "Copy of ..." case.
            name = f"Copy of {node.name}" if node.parent == target_id else node.name
            new = vfs_mod.vfs.copy(node_id, target_id, name)
            if new:
                created.append(new.id)
        if created:
            _record_undo("Copy", lambda c=created: [
                vfs_mod.vfs.delete(i, permanent=True) for i in c])

    def _move_nodes(self, node_ids, target_id, label="Move"):
        target = vfs_mod.vfs.get(target_id)
        if not target or (target.kind != vfs_mod.FOLDER and not target.drive):
            return
        if target_id == vfs_mod.vfs.recycle_id:
            for node_id in node_ids:
                vfs_mod.vfs.delete(node_id)
            _record_undo("Delete", lambda ids=list(node_ids): [
                vfs_mod.vfs.restore(i) for i in ids])
            return
        moved = []
        for node_id in node_ids:
            node = vfs_mod.vfs.get(node_id)
            if not node or node_id == target_id or node.parent == target_id:
                continue
            if node.kind == vfs_mod.FOLDER and self._is_ancestor(node_id, target_id):
                XPMessageBox.critical(
                    self, "Error Moving File or Folder",
                    f"Cannot move {node.name}: The destination folder is a subfolder "
                    "of the source folder.")
                continue
            moved.append((node_id, node.parent))
            vfs_mod.vfs.move(node_id, target_id)
        if moved:
            _record_undo(label, lambda pairs=moved: [
                vfs_mod.vfs.move(nid, old) for nid, old in pairs])

    def _is_ancestor(self, node_id, maybe_descendant_id):
        cur = vfs_mod.vfs.get(maybe_descendant_id)
        while cur:
            if cur.id == node_id:
                return True
            cur = vfs_mod.vfs.get(cur.parent) if cur.parent else None
        return False

    def perform_drop(self, node_ids, target_id, copy=False):
        if corruption.guard_fs(self.wm):
            return
        if copy:
            self._copy_nodes(node_ids, target_id)
        else:
            self._move_nodes(node_ids, target_id)
        self._notify()

    def move_to_folder(self):
        self._to_folder("Move Items", "Move")

    def copy_to_folder(self):
        self._to_folder("Copy Items", "Copy")

    def _to_folder(self, title, verb):
        if corruption.guard_fs(self.wm):
            return
        nodes = self.selected_nodes()
        if not nodes:
            return
        what = f"'{nodes[0].name}'" if len(nodes) == 1 else f"these {len(nodes)} items"
        target = BrowseForFolderDialog.choose(
            self, title,
            f"Select the place where you want to {verb.lower()} {what}. "
            f"Then click the {verb} button.", verb)
        if not target:
            return
        ids = [n.id for n in nodes]
        if verb == "Move":
            self._move_nodes(ids, target)
        else:
            self._copy_nodes(ids, target)
        self._notify()

    def undo(self):
        if corruption.guard_fs(self.wm) or not _UNDO:
            return
        _label, action = _UNDO.pop()
        action()
        self._notify()

    # ----------------------------------------------------------------- search
    def run_search(self, name, text, scope_id, subfolders):
        if corruption.guard_fs(self.wm):
            return
        needle = name.lower()
        phrase = text.lower()
        results = []

        def walk(folder_id):
            for child in shell.visible_children(folder_id):
                if child.kind == vfs_mod.FOLDER and subfolders:
                    walk(child.id)
                if needle and needle not in child.name.lower():
                    continue
                if phrase:
                    if child.kind not in (vfs_mod.TEXT, vfs_mod.RICH):
                        continue
                    if phrase not in vfs_mod.vfs.read_content(child.id).lower():
                        continue
                results.append(child)

        walk(scope_id or self.current)
        self.search_results = results
        self.search_label = "Search Results"
        self.setWindowTitle("Search Results")
        self._refresh_address()
        self.refresh()

    # ------------------------------------------------------------- favorites
    def add_to_favorites(self):
        settings.add_explorer_favorite(self.current)
        node = vfs_mod.vfs.get(self.current)
        XPMessageBox.information(self, "Add Favorite",
                                 f"'{node.name}' has been added to your Favorites.")

    def organize_favorites(self):
        OrganizeFavoritesDialog.run(self)

    # -------------------------------------------------- shell stubs & dialogs
    def publish_to_web(self):
        XPMessageBox.critical(
            self, "Web Publishing Wizard",
            "Windows cannot connect to the Internet to complete this task. "
            "Check your Internet connection and try again.")

    def email_selection(self):
        XPMessageBox.critical(
            self, "Send Mail",
            "Either there is no default mail client or the current mail client "
            "cannot fulfill the messaging request. Please run Microsoft Outlook "
            "and set it as the default mail client.")

    def print_selection(self):
        XPMessageBox.warning(
            self, "Printers and Faxes",
            "Before you can perform printer-related tasks, you need to install a "
            "printer. Do you want to install a printer now?")

    def no_shared_documents(self):
        if vfs_mod.vfs.get(vfs_mod.vfs.shared_docs_id):
            self._navigate(vfs_mod.vfs.shared_docs_id)

    def no_network_places(self):
        XPMessageBox.critical(
            self, "My Network Places",
            "Windows cannot find the network. The network may be temporarily "
            "unavailable, or the network components are not installed.")

    def _map_network_drive(self):
        XPMessageBox.critical(
            self, "Map Network Drive",
            "No network provider accepted the given network path.")

    def _synchronize(self):
        XPMessageBox.information(
            self, "Items to Synchronize",
            "There are no items to synchronize. To make a file or folder "
            "available offline, right-click it and then click Make Available Offline.")

    def _folder_options(self):
        from .control_panel.folder_options import FolderOptionsWindow
        self.wm.open(FolderOptionsWindow(self.wm))

    def _help_center(self):
        from . import launch
        launch(self.wm, "app:ie")

    def _windows_legal(self):
        XPMessageBox.information(
            self, "Windows Genuine Advantage",
            "This copy of Windows is not genuine, but it is entirely virtual, so "
            "no license was harmed in its creation.")

    def _about(self):
        XPMessageBox.information(
            self, "About Windows",
            "Microsoft(R) Windows\n"
            "Version 5.1 (Build 2600.xpsp_sp3.080413-2111 : Service Pack 3)\n"
            "Copyright (C) 1985-2001 Microsoft Corporation\n\n"
            "This product is licensed under the terms of the End-User License "
            "Agreement to:\n    Owner")


class OrganizeFavoritesDialog(QDialog):
    """Favorites > Organize Favorites... -- the favorites list with a Remove
    button, which is all this shell's version of it can meaningfully offer."""

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        inner = build_dialog_frame(self, "Organize Favorites")

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {theme.XP_WINDOW_BG}; }} {DIALOG_BUTTON_QSS}")
        root = QVBoxLayout(body)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        hint = QLabel("Select a favorite, then click Remove to take it off the "
                      "Favorites menu.")
        hint.setWordWrap(True)
        hint.setStyleSheet("background: transparent;")
        root.addWidget(hint)

        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget { background: white; border: 1px solid #7f9db9; }")
        self._item_class = QListWidgetItem
        root.addWidget(self.list, 1)
        self._reload()

        row = QHBoxLayout()
        remove = QPushButton("Remove")
        remove.setFixedWidth(80)
        remove.clicked.connect(self._remove)
        row.addWidget(remove)
        row.addStretch(1)
        close = QPushButton("Close")
        close.setFixedWidth(80)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        root.addLayout(row)

        inner.addWidget(body)
        self.resize(320, 320)

    def _reload(self):
        self.list.clear()
        for node_id in settings.explorer_favorites:
            node = vfs_mod.vfs.get(node_id)
            if not node:
                continue
            item = self._item_class(shell.shell_icon(node, 16), node.name)
            item.setData(Qt.ItemDataRole.UserRole, node_id)
            self.list.addItem(item)

    def _remove(self):
        item = self.list.currentItem()
        if item:
            settings.remove_explorer_favorite(item.data(Qt.ItemDataRole.UserRole))
            self._reload()

    @staticmethod
    def run(parent):
        dlg = OrganizeFavoritesDialog(parent)
        center = parent.frameGeometry().center()
        dlg.move(center.x() - dlg.width() // 2, center.y() - dlg.height() // 2)
        dlg.exec()
