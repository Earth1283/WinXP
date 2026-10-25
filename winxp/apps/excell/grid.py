"""The worksheet grid: a Qt model over the active sheet, the cell delegate, and
the view with Excel's keyboard habits, active-cell border and fill handle."""
from __future__ import annotations

from PyQt6.QtCore import (
    QAbstractTableModel, QItemSelection, QItemSelectionModel, QModelIndex, QRect, Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemDelegate, QAbstractItemView, QHeaderView, QLineEdit, QStyle,
    QStyledItemDelegate, QTableView,
)

from . import formulas as fx
from .formulas import XLError
from .model import (
    DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT, Workbook, format_value, settings, to_hex,
)

GRID_QSS = """
QTableView {
    background: white; gridline-color: #d0d0d0; border: none;
    selection-background-color: #c6d3ef; selection-color: black;
    font-family: Arial; font-size: 10pt;
}
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fbfaf6, stop:1 #e4e2d6);
    border: none; border-right: 1px solid #b7b4a5; border-bottom: 1px solid #b7b4a5;
    font-family: Arial; font-size: 8pt; color: #222; padding: 0px 2px;
}
QHeaderView::section:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fde7b4, stop:1 #f8c66c);
    font-weight: normal;
}
QTableCornerButton::section { background: #e4e2d6; border: none;
    border-right: 1px solid #b7b4a5; border-bottom: 1px solid #b7b4a5; }
"""

FILL_HANDLE = 5
SELECTION = QColor("#c6d3ef")
_BOTTOM = Qt.AlignmentFlag.AlignBottom
ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft | _BOTTOM
ALIGN_CENTER = Qt.AlignmentFlag.AlignHCenter | _BOTTOM
ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight | _BOTTOM
_ALIGN_BY_NAME = {"left": ALIGN_LEFT, "center": ALIGN_CENTER, "right": ALIGN_RIGHT}
_ALIGN_INT = {ALIGN_LEFT: int(ALIGN_LEFT.value), ALIGN_CENTER: int(ALIGN_CENTER.value),
              ALIGN_RIGHT: int(ALIGN_RIGHT.value)}
_SELECTED = QStyle.StateFlag.State_Selected
BORDER_PEN = QPen(QColor("black"), 1)


class SheetModel(QAbstractTableModel):
    """Reads straight from the workbook; nothing is copied into Qt."""

    entry_committed = pyqtSignal(int, int, str)

    def __init__(self, book: Workbook):
        super().__init__()
        self.book = book
        self._fonts: dict[tuple, tuple[QFont, QFontMetrics]] = {}
        self._display: dict[tuple[int, int], tuple[str, int]] = {}

    def set_book(self, book: Workbook):
        self.beginResetModel()
        self.book = book
        self._display.clear()
        self.endResetModel()

    def refresh(self):
        """Repaint without resetting the view (keeps selection and scroll)."""
        self._display.clear()
        self.dataChanged.emit(self.index(0, 0),
                              self.index(fx.MAX_ROWS - 1, fx.MAX_COLS - 1))

    def refresh_cells(self, keys):
        """Repaint just these (id(sheet), r, c) cells, if they're on screen."""
        sid = id(self.book.sheet)
        cells = [(r, c) for s, r, c in keys if s == sid]
        if not cells:
            return
        for pos in cells:
            self._display.pop(pos, None)
        rows = [r for r, _ in cells]
        cols = [c for _, c in cells]
        self.dataChanged.emit(self.index(min(rows), min(cols)),
                              self.index(max(rows), max(cols)))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else fx.MAX_ROWS

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else fx.MAX_COLS

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return fx.col_name(section)
            return str(section + 1)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def flags(self, index):
        return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable)

    def font_and_metrics(self, cell) -> tuple[QFont, QFontMetrics]:
        fmt = cell.fmt
        key = (fmt.get("bold", False), fmt.get("italic", False), fmt.get("underline", False))
        entry = self._fonts.get(key)
        if entry is None:
            font = QFont("Arial", 10)
            font.setBold(key[0])
            font.setItalic(key[1])
            font.setUnderline(key[2])
            entry = self._fonts[key] = (font, QFontMetrics(font))
        return entry

    def display(self, r, c, cell) -> str:
        return self.display_and_width(r, c, cell)[0]

    def display_and_width(self, r, c, cell) -> tuple[str, int]:
        entry = self._display.get((r, c))
        if entry is None:
            text = format_value(cell.value, cell, settings.options["hexcel"])
            entry = self._display[(r, c)] = (
                text, self.font_and_metrics(cell)[1].horizontalAdvance(text) if text else 0)
        return entry

    @staticmethod
    def alignment(cell):
        align = _ALIGN_BY_NAME.get(cell.fmt.get("align", ""))
        if align is None:
            v = cell.value
            if isinstance(v, (bool, XLError)):
                align = ALIGN_CENTER
            elif isinstance(v, float):
                align = ALIGN_RIGHT
            else:
                align = ALIGN_LEFT
        return align

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        cell = self.book.sheet.get(index.row(), index.column())
        if cell is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.display(index.row(), index.column(), cell)
        if role == Qt.ItemDataRole.EditRole:
            return cell.raw
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self.alignment(cell)
        if role == Qt.ItemDataRole.FontRole:
            return self.font_and_metrics(cell)[0]
        if role == Qt.ItemDataRole.BackgroundRole:
            fill = cell.style("fill")
            return QBrush(QColor(fill)) if fill else None
        if role == Qt.ItemDataRole.ForegroundRole:
            color = cell.style("color")
            return QBrush(QColor(color)) if color else None
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole:
            return False
        self.entry_committed.emit(index.row(), index.column(), str(value))
        return True


class CellDelegate(QStyledItemDelegate):
    editor_text = pyqtSignal(str)

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.replace_next = False
        self.seed_text = ""
        self.on_editor = None
        self.current_editor = None

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setStyleSheet("QLineEdit { background: white; border: none; padding: 0px 1px;"
                             " font-family: Arial; font-size: 10pt; }")
        editor.textEdited.connect(self.editor_text)
        self.current_editor = editor
        if self.on_editor:
            self.on_editor(editor)
        return editor

    def setEditorData(self, editor, index):
        # Qt re-primes open editors on every dataChanged; a recalc must never
        # wipe out what's being typed.
        if editor.property("primed"):
            return
        editor.setProperty("primed", True)
        if self.replace_next:
            editor.setText(self.seed_text)
            self.replace_next = False
        else:
            editor.setText(index.data(Qt.ItemDataRole.EditRole) or "")
        self.editor_text.emit(editor.text())

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)

    def paint(self, painter: QPainter, option, index):
        """Painted by hand: Qt's generic item styling costs ~0.3ms a cell,
        and a full screen is a thousand cells."""
        model = self.view.model()
        r, c = index.row(), index.column()
        cell = model.book.sheet.get(r, c)
        rect = option.rect
        if option.state & _SELECTED:
            painter.fillRect(rect, SELECTION)
        elif cell is not None and cell.fmt.get("fill"):
            painter.fillRect(rect, QColor(cell.fmt["fill"]))
        if cell is None:
            return
        text, width = model.display_and_width(r, c, cell)
        if text:
            font, metrics = model.font_and_metrics(cell)
            painter.setFont(font)
            color = cell.fmt.get("color")
            painter.setPen(QColor(color) if color else Qt.GlobalColor.black)
            align = model.alignment(cell)
            box = rect.adjusted(2, 0, -2, -1)
            if width > box.width():
                if isinstance(cell.value, float) and not isinstance(cell.value, bool):
                    # Numbers never spill into the next cell. General rounds
                    # until it fits; anything else turns into hashes.
                    text = fit_general(cell, box.width(), metrics) or \
                        "#" * max(1, box.width() // max(1, metrics.horizontalAdvance("#")))
                elif align is ALIGN_LEFT:
                    box = self._spill(box, r, c, width, model)
            painter.drawText(box, _ALIGN_INT[align], text)
        if cell.fmt.get("border"):
            painter.setPen(BORDER_PEN)
            painter.drawRect(rect.adjusted(-1, -1, -1, -1))

    def _spill(self, box, r, c, width, model):
        """Long text runs on across empty neighbours, as far as it needs."""
        sheet = model.book.sheet
        header = self.view.horizontalHeader()
        right = box.right()
        nc = c + 1
        while right - box.left() < width and nc < fx.MAX_COLS:
            neighbour = sheet.get(r, nc)
            if neighbour is not None and neighbour.raw:
                break
            right += header.sectionSize(nc)
            nc += 1
        box.setRight(right)
        return box


def fit_general(cell, width, metrics) -> str | None:
    if cell.fmt.get("num", "General") != "General":
        return None
    value = cell.value
    for places in range(9, -1, -1):
        if settings.options["hexcel"]:
            text = to_hex(value, places)
            if "." in text:
                text = text.rstrip("0").rstrip(".")
        else:
            text = f"{value:.{places}f}"
            if "." in text:
                text = text.rstrip("0").rstrip(".")
        if metrics.horizontalAdvance(text) <= width:
            return text
    return None


class SheetView(QTableView):
    """Enter moves down, typing replaces, Delete clears, and the little black
    square in the corner of the selection really does fill."""

    clear_requested = pyqtSignal()
    fill_requested = pyqtSignal(object, object)   # source (r1,c1,r2,c2), target rect
    editing_changed = pyqtSignal(bool)

    def __init__(self, model: SheetModel):
        super().__init__()
        self.setModel(model)
        self.delegate = CellDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setStyleSheet(GRID_QSS)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                             | QAbstractItemView.EditTrigger.EditKeyPressed
                             | QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.setWordWrap(False)
        self.setCornerButtonEnabled(True)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)

        rows = self.verticalHeader()
        rows.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        rows.setDefaultSectionSize(DEFAULT_ROW_HEIGHT)
        rows.setMinimumWidth(34)
        rows.setHighlightSections(True)
        cols = self.horizontalHeader()
        cols.setDefaultSectionSize(DEFAULT_COL_WIDTH)
        cols.setFixedHeight(18)
        cols.setHighlightSections(True)
        cols.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self._editing = False
        self._fill_from: tuple | None = None
        self._fill_to: tuple | None = None
        self.setMouseTracking(True)

    # -- selection helpers -----------------------------------------------

    def selection_rect(self) -> tuple[int, int, int, int]:
        ranges = self.selectionModel().selection()
        if ranges.isEmpty():
            idx = self.currentIndex()
            r, c = max(0, idx.row()), max(0, idx.column())
            return r, c, r, c
        rng = ranges[0]
        return rng.top(), rng.left(), rng.bottom(), rng.right()

    def select_rect(self, r1, c1, r2, c2, current=None):
        model = self.model()
        selection = QItemSelection(model.index(r1, c1), model.index(r2, c2))
        cur = model.index(*(current or (r1, c1)))
        self.selectionModel().setCurrentIndex(cur, QItemSelectionModel.SelectionFlag.NoUpdate)
        self.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.scrollTo(cur)

    def go_to(self, r, c):
        self.select_rect(r, c, r, c)

    def is_editing(self):
        return self.state() == QAbstractItemView.State.EditingState

    # -- editing ----------------------------------------------------------

    def edit(self, index, trigger=None, event=None):
        if trigger is None:
            return super().edit(index)
        typed = trigger == QAbstractItemView.EditTrigger.AnyKeyPressed
        if typed:
            text = event.text() if event is not None else ""
            if not text or not text.isprintable():
                return False
            # Typing replaces the cell: start empty and let Qt forward the key.
            self.delegate.replace_next = True
            self.delegate.seed_text = ""
        ok = super().edit(index, trigger, event)
        if ok:
            if not typed:
                self._cursor_to_end()
            self.editing_changed.emit(True)
        return ok

    def start_edit(self, seed: str | None = None):
        index = self.currentIndex()
        if seed is not None:
            self.delegate.replace_next = True
            self.delegate.seed_text = seed
        if super().edit(index):
            self._cursor_to_end()
            self.editing_changed.emit(True)

    def _cursor_to_end(self):
        editor = self.delegate.current_editor
        if editor is not None:
            editor.deselect()
            editor.end(False)

    def closeEditor(self, editor, hint):
        submit = hint == QAbstractItemDelegate.EndEditHint.SubmitModelCache
        super().closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint
                            if submit else hint)
        self.editing_changed.emit(False)
        if submit:
            self.move_cursor(1, 0)

    def move_cursor(self, dr, dc):
        idx = self.currentIndex()
        r = min(fx.MAX_ROWS - 1, max(0, idx.row() + dr))
        c = min(fx.MAX_COLS - 1, max(0, idx.column() + dc))
        self.go_to(r, c)

    def keyPressEvent(self, ev):
        key, mods = ev.key(), ev.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        if not self.is_editing():
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.move_cursor(-1 if shift else 1, 0)
                return
            if key == Qt.Key.Key_Tab:
                self.move_cursor(0, 1)
                return
            if key == Qt.Key.Key_Backtab:
                self.move_cursor(0, -1)
                return
            if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not ctrl:
                self.clear_requested.emit()
                if key == Qt.Key.Key_Backspace:
                    self.start_edit("")
                return
            if ctrl and key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Left,
                                Qt.Key.Key_Right):
                self._jump(key, shift)
                return
            if ctrl and key == Qt.Key.Key_Home:
                self.go_to(0, 0)
                return
        super().keyPressEvent(ev)

    def _jump(self, key, extend):
        """Ctrl+arrow: to the edge of the current block of data, or to the
        very last row of the sheet if there isn't one. Row 65,536 is real."""
        sheet = self.model().book.sheet
        idx = self.currentIndex()
        r, c = idx.row(), idx.column()
        dr, dc = {Qt.Key.Key_Down: (1, 0), Qt.Key.Key_Up: (-1, 0),
                  Qt.Key.Key_Left: (0, -1), Qt.Key.Key_Right: (0, 1)}[key]

        def filled(rr, cc):
            cell = sheet.get(rr, cc)
            return cell is not None and cell.raw != ""

        def inside(rr, cc):
            return 0 <= rr < fx.MAX_ROWS and 0 <= cc < fx.MAX_COLS

        if dr:
            line = sorted(rr for (rr, cc) in sheet.cells if cc == c and filled(rr, cc))
        else:
            line = sorted(cc for (rr, cc) in sheet.cells if rr == r and filled(rr, cc))
        pos = r if dr else c
        step = dr or dc
        limit = (fx.MAX_ROWS - 1 if dr else fx.MAX_COLS - 1) if step > 0 else 0
        here = filled(r, c)
        nxt = (r + dr, c + dc)
        if here and inside(*nxt) and filled(*nxt):
            p = pos
            while inside(*((p + step, c) if dr else (r, p + step))) and \
                    filled(*((p + step, c) if dr else (r, p + step))):
                p += step
            target = p
        else:
            ahead = [p for p in line if (p > pos if step > 0 else p < pos)]
            target = (ahead[0] if step > 0 else ahead[-1]) if ahead else limit
        tr, tc = (target, c) if dr else (r, target)
        if extend:
            r1, c1, r2, c2 = self.selection_rect()
            anchor = (r1 if r1 != r else r2, c1 if c1 != c else c2)
            self.select_rect(min(anchor[0], tr), min(anchor[1], tc),
                             max(anchor[0], tr), max(anchor[1], tc), current=(tr, tc))
        else:
            self.go_to(tr, tc)

    # -- painting ---------------------------------------------------------

    def _rect_for(self, r1, c1, r2, c2) -> QRect:
        model = self.model()
        a = self.visualRect(model.index(r1, c1))
        b = self.visualRect(model.index(r2, c2))
        return a.united(b)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self.viewport())
        r1, c1, r2, c2 = self.selection_rect()
        if self._fill_to:
            p.setPen(QPen(QColor("#808080"), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(self._rect_for(*self._fill_to).adjusted(-1, -1, -1, -1))
        rect = self._rect_for(r1, c1, r2, c2)
        p.setPen(QPen(QColor("black"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect.adjusted(0, 0, -1, -1))
        if not self.is_editing():
            handle = self._handle_rect(rect)
            p.setPen(QPen(QColor("white"), 1))
            p.setBrush(QColor("black"))
            p.drawRect(handle)
        p.end()

    @staticmethod
    def _handle_rect(rect: QRect) -> QRect:
        return QRect(rect.right() - FILL_HANDLE // 2 - 1, rect.bottom() - FILL_HANDLE // 2 - 1,
                     FILL_HANDLE + 1, FILL_HANDLE + 1)

    def selectionChanged(self, selected, deselected):
        super().selectionChanged(selected, deselected)
        self.viewport().update()

    def currentChanged(self, current, previous):
        super().currentChanged(current, previous)
        self.viewport().update()

    # -- fill handle ------------------------------------------------------

    def _over_handle(self, pos) -> bool:
        rect = self._rect_for(*self.selection_rect())
        return self._handle_rect(rect).adjusted(-2, -2, 2, 2).contains(pos)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and not self.is_editing() \
                and self._over_handle(ev.position().toPoint()):
            self._fill_from = self.selection_rect()
            self._fill_to = self._fill_from
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()
        if self._fill_from is not None:
            idx = self.indexAt(pos)
            if idx.isValid():
                r1, c1, r2, c2 = self._fill_from
                r, c = idx.row(), idx.column()
                # Fill goes one way only: whichever direction you dragged further.
                if max(r - r2, r1 - r) >= max(c - c2, c1 - c):
                    self._fill_to = (min(r1, r), c1, max(r2, r), c2)
                else:
                    self._fill_to = (r1, min(c1, c), r2, max(c2, c))
                self.viewport().update()
            return
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if self._over_handle(pos)
                                  else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._fill_from is not None:
            source, target = self._fill_from, self._fill_to
            self._fill_from = self._fill_to = None
            if target and target != source:
                self.fill_requested.emit(source, target)
                self.select_rect(*target)
            self.viewport().update()
            return
        super().mouseReleaseEvent(ev)
