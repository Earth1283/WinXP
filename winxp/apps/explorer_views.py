"""The five Windows Explorer view modes.

Thumbnails, Tiles, Icons and List are one QListWidget driven by a delegate --
Qt has no built-in equivalent of a Tile (48px icon left, three stacked lines
right) or of XP's group headings, so the cells are drawn rather than composed
from item widgets. Details is a QTreeWidget because it needs real sortable
columns. Both views speak the same small API to ExplorerWindow so it never
has to care which one is on screen.
"""
from __future__ import annotations

import json

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QDrag, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QLineEdit, QListWidget, QListWidgetItem, QStyle,
    QStyledItemDelegate, QTreeWidget, QTreeWidgetItem,
)
from PyQt6.QtCore import QMimeData

from .. import vfs as vfs_mod
from . import explorer_shell as shell

MODE_THUMBNAILS = "thumbnails"
MODE_TILES = "tiles"
MODE_ICONS = "icons"
MODE_LIST = "list"
MODE_DETAILS = "details"

MODE_LABELS = {
    MODE_THUMBNAILS: "Thumb&nails", MODE_TILES: "Tile&s", MODE_ICONS: "Ic&ons",
    MODE_LIST: "&List", MODE_DETAILS: "&Details",
}
MODE_ORDER = [MODE_THUMBNAILS, MODE_TILES, MODE_ICONS, MODE_LIST, MODE_DETAILS]

ROLE_NODE = Qt.ItemDataRole.UserRole
ROLE_HEADER = Qt.ItemDataRole.UserRole + 1
ROLE_CUT = Qt.ItemDataRole.UserRole + 2

# Icon cells: 5px lead-in, a 32px icon, then a 4px gap before the caption.
ICON_TEXT_TOP = 41

# WrapAnywhere is what saves a name with no spaces in it: TextWordWrap alone
# has no break opportunity in "RickAstleyNeverGonnaGiveYouUp.wav", so the line
# runs straight over the neighbouring cells. Together they map to Qt's
# WrapAtWordBoundaryOrAnywhere -- break on spaces where there are any, mid-word
# only where one word can't fit on its own.
CAPTION_FLAGS = (Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                 | Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere)

SEL_ACTIVE = "#316ac5"
SEL_INACTIVE = "#d8e4f8"
HEADER_TEXT = "#1a3e8c"

VIEW_QSS = """
QAbstractItemView { background: white; border: 1px solid #7f9db9; font-size: 11px;
                    outline: 0; }
QHeaderView::section { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                          stop:0 #ffffff, stop:1 #e3e0d3);
                       border: 0; border-right: 1px solid #c4c1b4;
                       border-bottom: 1px solid #aca899; padding: 3px 5px; }
QHeaderView::section:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                          stop:0 #ffffff, stop:1 #d4e6fb); }
"""


def _line_height(fm, flags):
    """What one laid-out line actually costs. QFontMetrics.lineSpacing() is a
    pixel short of what boundingRect() reports per line, and budgeting by the
    short number rejects a legitimate second line."""
    return fm.boundingRect(QRect(0, 0, 1 << 16, 0), flags, "Xg").height()


def _elide_to_lines(fm, text, rect, flags, max_lines):
    """Trim a caption until it fits max_lines, with an ellipsis to say so.
    Elided-by-width isn't enough here: the text wraps, so what has to fit is a
    height, and the cut point depends on where the wrap lands."""
    limit = _line_height(fm, flags) * max_lines
    if fm.boundingRect(rect, flags, text).height() <= limit:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if fm.boundingRect(rect, flags, text[:mid] + "...").height() <= limit:
            low = mid
        else:
            high = mid - 1
    return text[:low] + "..."


def ghost(pixmap: QPixmap) -> QPixmap:
    """Cut items stay visible at half strength until the Paste lands, exactly
    like the shell's clipboard feedback."""
    out = QPixmap(pixmap.size())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setOpacity(0.45)
    p.drawPixmap(0, 0, pixmap)
    p.end()
    return out


class _StemEditDelegate(QStyledItemDelegate):
    """Rename selects the name but not the extension -- XP never made you
    re-type '.txt' just to fix a typo in the stem."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(True)
        editor.setStyleSheet("QLineEdit { background: white; border: 1px solid #316ac5; "
                             "selection-background-color: #316ac5; selection-color: white; }")
        return editor

    def setEditorData(self, editor, index):
        text = index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole) or ""
        editor.setText(text)
        dot = text.rfind(".")
        # The view gives the editor focus after this returns, and QLineEdit
        # selects everything on focus-in -- so stake the claim one turn later.
        QTimer.singleShot(0, lambda: self._select_stem(editor, dot))

    @staticmethod
    def _select_stem(editor, dot):
        try:
            if dot > 0:
                editor.setSelection(0, dot)
            else:
                editor.selectAll()
        except RuntimeError:
            pass  # editor closed before the timer fired


class ShellItemDelegate(_StemEditDelegate):
    def __init__(self, view):
        super().__init__(view)
        self.view = view

    # -- metrics ----------------------------------------------------------
    def sizeHint(self, option, index):
        mode = self.view.mode
        if index.data(ROLE_HEADER):
            # Full-bleed so the flow layout breaks the row, but short enough
            # that claiming it can never itself provoke a scrollbar.
            width = self.view.viewport().width() - 2 * self.view.spacing() - 22
            return QSize(max(120, width), 26)
        if mode == MODE_THUMBNAILS:
            return QSize(116, 132)
        if mode == MODE_TILES:
            return QSize(232, 58)
        if mode == MODE_ICONS:
            fm = QFontMetrics(self.view.font())
            return QSize(76, ICON_TEXT_TOP + 2 * _line_height(fm, CAPTION_FLAGS) + 5)
        fm = QFontMetrics(self.view.font())
        return QSize(fm.horizontalAdvance(index.data() or "") + 30, 18)

    # -- painting ---------------------------------------------------------
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        header = index.data(ROLE_HEADER)
        if header:
            self._paint_header(painter, option, header)
        elif self.view.mode == MODE_TILES:
            self._paint_tile(painter, option, index)
        elif self.view.mode == MODE_THUMBNAILS:
            self._paint_thumbnail(painter, option, index)
        elif self.view.mode == MODE_LIST:
            self._paint_list(painter, option, index)
        else:
            self._paint_icon(painter, option, index)
        painter.restore()

    def _paint_header(self, painter, option, title):
        r = option.rect
        font = QFont(painter.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(HEADER_TEXT))
        text_rect = QRect(r.left() + 4, r.top() + 2, r.width() - 8, r.height() - 8)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        y = r.bottom() - 4
        width = QFontMetrics(font).horizontalAdvance(title)
        painter.setPen(QPen(QColor("#9bb6de"), 1))
        painter.drawLine(r.left() + 4, y, r.left() + 10 + width, y)
        painter.setPen(QPen(QColor("#cfdcef"), 1))
        painter.drawLine(r.left() + 12 + width, y, r.right() - 6, y)

    def _fill_selection(self, painter, rect, option):
        if not (option.state & QStyle.StateFlag.State_Selected):
            return False
        active = self.view.hasFocus()
        painter.fillRect(rect, QColor(SEL_ACTIVE if active else SEL_INACTIVE))
        return active

    def _text_pen(self, painter, option, selection_active):
        if (option.state & QStyle.StateFlag.State_Selected) and selection_active:
            painter.setPen(QColor("white"))
        else:
            painter.setPen(QColor("black"))

    def _pixmap(self, index, size):
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        pm = icon.pixmap(size, size) if isinstance(icon, QIcon) else QPixmap()
        return ghost(pm) if index.data(ROLE_CUT) else pm

    def _paint_icon(self, painter, option, index):
        r = option.rect
        pm = self._pixmap(index, 32)
        painter.drawPixmap(r.left() + (r.width() - pm.width()) // 2, r.top() + 5, pm)
        label = index.data() or ""
        fm = QFontMetrics(painter.font())
        avail = QRect(r.left() + 3, r.top() + ICON_TEXT_TOP, r.width() - 6,
                      2 * _line_height(fm, CAPTION_FLAGS))
        label = _elide_to_lines(fm, label, avail, CAPTION_FLAGS, 2)
        bounds = fm.boundingRect(avail, CAPTION_FLAGS, label)
        width = min(bounds.width(), avail.width())
        box = QRect(r.left() + (r.width() - width) // 2 - 2, avail.top() - 1,
                    width + 4, min(bounds.height(), avail.height()) + 2)
        active = self._fill_selection(painter, box, option)
        self._text_pen(painter, option, active)
        painter.drawText(avail, CAPTION_FLAGS, label)

    def _paint_tile(self, painter, option, index):
        r = option.rect.adjusted(1, 1, -1, -1)
        active = self._fill_selection(painter, r, option)
        pm = self._pixmap(index, 48)
        painter.drawPixmap(r.left() + 4, r.top() + (r.height() - pm.height()) // 2, pm)
        node = self.view.node_for(index)
        if node is not None and node.drive:
            self._paint_drive_tile(painter, option, r, node, active, index.data() or "")
            return
        lines = [index.data() or ""]
        if node is not None:
            lines.append(shell.type_label(node))
            size = shell.size_of(node)
            if size:
                lines.append(shell.format_bytes(size))
        self._text_pen(painter, option, active)
        fm = QFontMetrics(painter.font())
        x = r.left() + 58
        width = r.width() - 62
        y = r.top() + (r.height() - len(lines) * (fm.height() + 1)) // 2
        for i, line in enumerate(lines):
            if i and not active:
                painter.setPen(QColor("#3f3f3f"))
            painter.drawText(QRect(x, y, width, fm.height()),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             fm.elidedText(line, Qt.TextElideMode.ElideRight, width))
            y += fm.height() + 1

    def _paint_drive_tile(self, painter, option, r, node, active, label):
        """My Computer's drive tiles carry a capacity bar, not a file size."""
        used, total = vfs_mod.vfs.drive_usage(node.id)
        fm = QFontMetrics(painter.font())
        x = r.left() + 58
        width = r.width() - 62
        y = r.top() + 6
        self._text_pen(painter, option, active)
        painter.drawText(QRect(x, y, width, fm.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         fm.elidedText(label, Qt.TextElideMode.ElideRight, width))
        y += fm.height() + 2
        if not total:
            if not active:
                painter.setPen(QColor("#3f3f3f"))
            painter.drawText(QRect(x, y, width, fm.height()),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             shell.type_label(node))
            return
        bar = QRect(x, y, min(120, width), 10)
        painter.fillRect(bar, QColor("#ffffff"))
        fill = QRect(bar.left() + 1, bar.top() + 1,
                     int((bar.width() - 2) * used / total), bar.height() - 2)
        low = (total - used) / total < 0.12
        painter.fillRect(fill, QColor("#c62b2b" if low else "#3f8cf6"))
        painter.setPen(QPen(QColor("#808080"), 1))
        painter.drawRect(bar.adjusted(0, 0, -1, -1))
        y += bar.height() + 3
        if not active:
            painter.setPen(QColor("#3f3f3f"))
        painter.drawText(QRect(x, y, width, fm.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         f"{shell.format_bytes(total - used)} free of "
                         f"{shell.format_bytes(total)}")

    def _paint_thumbnail(self, painter, option, index):
        r = option.rect
        node = self.view.node_for(index)
        frame = QRect(r.left() + (r.width() - 100) // 2, r.top() + 6, 100, 100)
        painter.fillRect(frame, QColor("white"))
        painter.setPen(QPen(QColor("#a0a0a0"), 1))
        painter.drawRect(frame.adjusted(0, 0, -1, -1))
        if node is not None:
            pm = shell.thumbnail(node, 92)
            if index.data(ROLE_CUT):
                pm = ghost(pm)
            painter.drawPixmap(frame.left() + (frame.width() - pm.width()) // 2,
                               frame.top() + (frame.height() - pm.height()) // 2, pm)
        label = index.data() or ""
        fm = QFontMetrics(painter.font())
        label = fm.elidedText(label, Qt.TextElideMode.ElideRight, r.width() - 8)
        width = fm.horizontalAdvance(label)
        box = QRect(r.left() + (r.width() - width) // 2 - 2, frame.bottom() + 4, width + 4, fm.height() + 2)
        active = self._fill_selection(painter, box, option)
        self._text_pen(painter, option, active)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, label)

    def _paint_list(self, painter, option, index):
        r = option.rect
        pm = self._pixmap(index, 16)
        fm = QFontMetrics(painter.font())
        # Elide against the cell first, then size the highlight to whatever
        # survived -- sizing the box first leaves no room for the text that
        # measured exactly to its width, and elides names that already fit.
        label = fm.elidedText(index.data() or "", Qt.TextElideMode.ElideRight,
                              max(0, r.width() - 24))
        box = QRect(r.left() + 20, r.top(), fm.horizontalAdvance(label) + 5, r.height())
        active = self._fill_selection(painter, box, option)
        painter.drawPixmap(r.left() + 1, r.top() + (r.height() - 16) // 2, pm)
        self._text_pen(painter, option, active)
        painter.drawText(box.adjusted(2, 0, -2, 0),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

    def updateEditorGeometry(self, editor, option, index):
        r = option.rect
        if self.view.mode in (MODE_ICONS, MODE_THUMBNAILS):
            editor.setGeometry(QRect(r.left() + 2, r.bottom() - 22, r.width() - 4, 20))
        elif self.view.mode == MODE_TILES:
            editor.setGeometry(QRect(r.left() + 56, r.top() + 4, r.width() - 60, 20))
        else:
            editor.setGeometry(QRect(r.left() + 20, r.top(), r.width() - 22, r.height()))


class _NodeDragDrop:
    """Shared vfs drag source / drop target. Ctrl held at drop time copies
    instead of moving, same modifier contract as the real shell."""

    def _install_dnd(self):
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def startDrag(self, supported_actions):
        node_ids = self.selected_ids()
        if not node_ids:
            return
        mime = QMimeData()
        mime.setData(shell.NODE_MIME, json.dumps(node_ids).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        node = vfs_mod.vfs.get(node_ids[0])
        if node:
            pm = shell.shell_icon(node, 32).pixmap(32, 32)
            drag.setPixmap(pm)
            drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)

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
        node_ids = json.loads(bytes(ev.mimeData().data(shell.NODE_MIME)).decode())
        target = self.drop_target_at(ev.position().toPoint())
        if target:
            copy = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self.dropped.emit(node_ids, target, copy)
        ev.acceptProposedAction()


class ShellIconView(_NodeDragDrop, QListWidget):
    openRequested = pyqtSignal(str)
    contextRequested = pyqtSignal(QPoint)
    renameCommitted = pyqtSignal(str, str)
    dropped = pyqtSignal(list, str, bool)
    backRequested = pyqtSignal()

    def __init__(self, folder_provider):
        super().__init__()
        self.mode = MODE_ICONS
        self._folder_provider = folder_provider
        self._nodes: dict[str, object] = {}
        self._renaming = None
        self.setStyleSheet(VIEW_QSS)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionRectVisible(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setUniformItemSizes(False)
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setItemDelegate(ShellItemDelegate(self))
        self._install_dnd()
        self.customContextMenuRequested.connect(self.contextRequested)
        self.itemDoubleClicked.connect(self._on_double_clicked)
        self.itemChanged.connect(self._on_item_changed)
        self.set_mode(MODE_ICONS)

    # -- configuration ----------------------------------------------------
    def set_mode(self, mode):
        self.mode = mode
        if mode == MODE_LIST:
            self.setViewMode(QListWidget.ViewMode.ListMode)
            self.setFlow(QListWidget.Flow.TopToBottom)
            self.setWrapping(True)
            self.setSpacing(0)
        else:
            self.setViewMode(QListWidget.ViewMode.IconMode)
            self.setFlow(QListWidget.Flow.LeftToRight)
            self.setWrapping(True)
            self.setSpacing(4 if mode != MODE_TILES else 2)
        self.setMovement(QListWidget.Movement.Static)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setDragEnabled(True)  # Movement.Static clears this as a side effect
        self.reset()

    def node_for(self, index):
        return self._nodes.get(index.data(ROLE_NODE))

    # -- population -------------------------------------------------------
    def set_entries(self, entries, cut_ids=frozenset()):
        self.blockSignals(True)
        self.clear()
        self._nodes = {}
        icon_size = {MODE_TILES: 48, MODE_LIST: 16, MODE_THUMBNAILS: 96}.get(self.mode, 32)
        for kind, payload in entries:
            if kind == "header":
                item = QListWidgetItem("")
                item.setData(ROLE_HEADER, payload)
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.addItem(item)
                continue
            node = payload
            self._nodes[node.id] = node
            item = QListWidgetItem(shell.shell_icon(node, icon_size), vfs_mod.display_name(node))
            item.setData(ROLE_NODE, node.id)
            item.setData(ROLE_CUT, node.id in cut_ids)
            self.addItem(item)
        self.blockSignals(False)

    def selected_ids(self):
        return [i.data(ROLE_NODE) for i in self.selectedItems() if i.data(ROLE_NODE)]

    def all_ids(self):
        return [self.item(i).data(ROLE_NODE) for i in range(self.count())
                if self.item(i).data(ROLE_NODE)]

    def select_ids(self, node_ids):
        wanted = set(node_ids)
        self.clearSelection()
        for i in range(self.count()):
            item = self.item(i)
            if item.data(ROLE_NODE) in wanted:
                item.setSelected(True)
                self.setCurrentItem(item)

    def invert_selection(self):
        for i in range(self.count()):
            item = self.item(i)
            if item.data(ROLE_NODE):
                item.setSelected(not item.isSelected())

    def drop_target_at(self, pos):
        item = self.itemAt(pos)
        if item:
            node = self._nodes.get(item.data(ROLE_NODE))
            if node is not None and node.kind == vfs_mod.FOLDER:
                return node.id
        return self._folder_provider()

    # -- interaction ------------------------------------------------------
    def _on_double_clicked(self, item):
        node_id = item.data(ROLE_NODE)
        if node_id:
            self.openRequested.emit(node_id)

    def begin_rename(self, node_id):
        for i in range(self.count()):
            item = self.item(i)
            if item.data(ROLE_NODE) == node_id:
                self._renaming = node_id
                # setFlags emits itemChanged, which the rename-commit handler
                # is listening for -- unblocked, arming the edit would instantly
                # "commit" it and tear the item down under us.
                self.blockSignals(True)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.blockSignals(False)
                self.editItem(item)
                return

    def _on_item_changed(self, item):
        node_id = item.data(ROLE_NODE)
        if node_id is None or self._renaming != node_id:
            return
        self._renaming = None
        self.blockSignals(True)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.blockSignals(False)
        self.renameCommitted.emit(node_id, item.text())

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            for node_id in self.selected_ids():
                self.openRequested.emit(node_id)
            return
        if ev.key() == Qt.Key.Key_Backspace:
            self.backRequested.emit()
            return
        super().keyPressEvent(ev)


class ShellDetailsView(_NodeDragDrop, QTreeWidget):
    openRequested = pyqtSignal(str)
    contextRequested = pyqtSignal(QPoint)
    renameCommitted = pyqtSignal(str, str)
    dropped = pyqtSignal(list, str, bool)
    sortRequested = pyqtSignal(str)
    backRequested = pyqtSignal()

    def __init__(self, folder_provider):
        super().__init__()
        self.mode = MODE_DETAILS
        self._folder_provider = folder_provider
        self._nodes: dict[str, object] = {}
        self._columns = [shell.COL_NAME]
        self._renaming = None
        self.setStyleSheet(VIEW_QSS)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setIndentation(0)
        self.setAllColumnsShowFocus(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setItemDelegate(_StemEditDelegate(self))
        self.header().setSectionsClickable(True)
        self.header().setStretchLastSection(True)
        self.header().sectionClicked.connect(self._on_header_clicked)
        self._install_dnd()
        self.customContextMenuRequested.connect(self.contextRequested)
        self.itemDoubleClicked.connect(self._on_double_clicked)
        self.itemChanged.connect(self._on_item_changed)

    def set_columns(self, columns):
        self._columns = list(columns)
        self.setColumnCount(len(columns))
        self.setHeaderLabels([shell.COLUMN_LABELS[c] for c in columns])
        for i, col in enumerate(columns):
            self.setColumnWidth(i, shell.COLUMN_WIDTHS.get(col, 110))

    def node_for(self, index):
        return self._nodes.get(index.data(ROLE_NODE))

    def set_entries(self, entries, cut_ids=frozenset()):
        self.blockSignals(True)
        self.clear()
        self._nodes = {}
        group = None
        for kind, payload in entries:
            if kind == "header":
                group = QTreeWidgetItem([payload])
                group.setData(0, ROLE_HEADER, payload)
                group.setFlags(Qt.ItemFlag.ItemIsEnabled)
                font = group.font(0)
                font.setBold(True)
                group.setFont(0, font)
                group.setForeground(0, QColor(HEADER_TEXT))
                self.addTopLevelItem(group)
                group.setFirstColumnSpanned(True)
                group.setExpanded(True)
                continue
            node = payload
            self._nodes[node.id] = node
            item = QTreeWidgetItem([shell.column_text(node, c) for c in self._columns])
            icon = shell.shell_icon(node, 16)
            item.setIcon(0, QIcon(ghost(icon.pixmap(16, 16))) if node.id in cut_ids else icon)
            item.setData(0, ROLE_NODE, node.id)
            for i, col in enumerate(self._columns):
                if col in (shell.COL_SIZE, shell.COL_TOTAL, shell.COL_FREE):
                    item.setTextAlignment(i, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            if group is not None:
                group.addChild(item)
            else:
                self.addTopLevelItem(item)
        self.blockSignals(False)

    def _iter_node_items(self):
        stack = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        while stack:
            item = stack.pop()
            stack.extend(item.child(i) for i in range(item.childCount()))
            if item.data(0, ROLE_NODE):
                yield item

    def selected_ids(self):
        return [i.data(0, ROLE_NODE) for i in self.selectedItems() if i.data(0, ROLE_NODE)]

    def all_ids(self):
        return [i.data(0, ROLE_NODE) for i in self._iter_node_items()]

    def select_ids(self, node_ids):
        wanted = set(node_ids)
        self.clearSelection()
        for item in self._iter_node_items():
            if item.data(0, ROLE_NODE) in wanted:
                item.setSelected(True)
                self.setCurrentItem(item)

    def invert_selection(self):
        for item in self._iter_node_items():
            item.setSelected(not item.isSelected())

    def drop_target_at(self, pos):
        item = self.itemAt(pos)
        if item:
            node = self._nodes.get(item.data(0, ROLE_NODE))
            if node is not None and node.kind == vfs_mod.FOLDER:
                return node.id
        return self._folder_provider()

    def _on_header_clicked(self, section):
        if 0 <= section < len(self._columns):
            self.sortRequested.emit(self._columns[section])

    def _on_double_clicked(self, item, column):
        node_id = item.data(0, ROLE_NODE)
        if node_id:
            self.openRequested.emit(node_id)

    def begin_rename(self, node_id):
        for item in self._iter_node_items():
            if item.data(0, ROLE_NODE) == node_id:
                self._renaming = node_id
                self.blockSignals(True)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.blockSignals(False)
                self.editItem(item, 0)
                return

    def _on_item_changed(self, item, column):
        node_id = item.data(0, ROLE_NODE)
        if column != 0 or node_id is None or self._renaming != node_id:
            return
        self._renaming = None
        self.blockSignals(True)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.blockSignals(False)
        self.renameCommitted.emit(node_id, item.text(0))

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            for node_id in self.selected_ids():
                self.openRequested.emit(node_id)
            return
        if ev.key() == Qt.Key.Key_Backspace:
            self.backRequested.emit()
            return
        super().keyPressEvent(ev)
