"""Print Preview.

Word doesn't open a preview window -- it takes over the one you're in, swaps
the toolbars for a single preview bar, and shows the sheets at whatever
multiple-page arrangement you pick. Same here: the window's stack switches to
this widget and back.

The pages are rendered from a *clone* of the live document, sized to the real
paper rather than the on-screen viewport, so the preview shows what would
actually come out of the printer instead of what the editor happens to be
showing.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QTextDocument
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMenu, QScrollArea, QToolButton, QVBoxLayout,
    QWidget, QWidgetAction,
)

from ... import theme
from . import mw_icons
from .model import PageSetup
from .widgets import TOOLBAR_QSS, toolbar_button

DESK = "#7f8a99"


class PageGridPicker(QWidget):
    """The little 4x6 grid the Multiple Pages button drops down."""

    picked = pyqtSignal(int, int)

    def __init__(self, rows=4, cols=6, cell=16):
        super().__init__()
        self.rows, self.cols, self.cell = rows, cols, cell
        self.hover = (0, 0)
        self.setFixedSize(cols * cell + 8, rows * cell + 22)
        self.setMouseTracking(True)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ece9d8"))
        for row in range(self.rows):
            for col in range(self.cols):
                rect = QRectF(4 + col * self.cell, 4 + row * self.cell,
                              self.cell - 2, self.cell - 2)
                lit = row < self.hover[0] and col < self.hover[1]
                p.setBrush(QColor("#316ac5") if lit else QColor("white"))
                p.setPen(QPen(QColor("#7f7f7f"), 1))
                p.drawRect(rect)
        p.setPen(QColor("black"))
        p.setFont(QFont("Tahoma", 7))
        label = (f"{self.hover[0]} x {self.hover[1]} Pages" if self.hover[0]
                 else "Cancel")
        p.drawText(QRectF(0, self.rows * self.cell + 5, self.width(), 14),
                   int(Qt.AlignmentFlag.AlignCenter), label)
        p.end()

    def mouseMoveEvent(self, ev):
        col = int((ev.position().x() - 4) // self.cell) + 1
        row = int((ev.position().y() - 4) // self.cell) + 1
        self.hover = (max(0, min(self.rows, row)), max(0, min(self.cols, col)))
        self.update()

    def mouseReleaseEvent(self, ev):
        if self.hover[0] and self.hover[1]:
            self.picked.emit(*self.hover)


class PreviewCanvas(QWidget):
    """Lays the sheets out in a grid and paints them from a cloned document."""

    page_clicked = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.document: QTextDocument | None = None
        self.page_setup = PageSetup()
        self.rows = 1
        self.cols = 1
        self.zoom = 0.0            # 0 = fit the arrangement
        self.first_page = 0
        self.magnifier = True
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)

    def set_document(self, document: QTextDocument, page_setup: PageSetup):
        self.document = document
        self.page_setup = page_setup
        self.updateGeometry()
        self.update()

    def page_count(self) -> int:
        return max(1, self.document.pageCount()) if self.document else 1

    def _scale(self) -> float:
        if self.zoom > 0:
            return self.zoom
        page_w, page_h = self.page_setup.page_width, self.page_setup.page_height
        margin = 14
        avail_w = (self.width() - margin * (self.cols + 1)) / self.cols
        avail_h = (self.height() - margin * (self.rows + 1)) / self.rows
        return max(0.05, min(avail_w / page_w, avail_h / page_h))

    def sizeHint(self) -> QSize:
        return QSize(700, 520)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(DESK))
        if self.document is None:
            p.end()
            return
        scale = self._scale()
        page_w = self.page_setup.page_width * scale
        page_h = self.page_setup.page_height * scale
        margin_x = max(8.0, (self.width() - self.cols * page_w) / (self.cols + 1))
        margin_y = 12.0
        total = self.page_count()

        for slot in range(self.rows * self.cols):
            index = self.first_page + slot
            if index >= total:
                break
            row, col = divmod(slot, self.cols)
            x = margin_x + col * (page_w + margin_x)
            y = margin_y + row * (page_h + margin_y)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#5c6675"))
            p.drawRect(QRectF(x + 3, y + 3, page_w, page_h))
            p.setBrush(QColor("white"))
            p.setPen(QPen(QColor("#3a3a3a"), 1))
            p.drawRect(QRectF(x, y, page_w, page_h))

            p.save()
            p.translate(x, y)
            p.scale(scale, scale)
            p.setClipRect(QRectF(0, 0, self.page_setup.page_width,
                                 self.page_setup.page_height))
            p.translate(0, -index * self.page_setup.page_height)
            self.document.drawContents(
                p, QRectF(0, index * self.page_setup.page_height,
                          self.page_setup.page_width, self.page_setup.page_height))
            p.restore()
        p.end()

    def mouseReleaseEvent(self, ev):
        if not self.magnifier:
            return
        self.zoom = 0.0 if self.zoom > 0 else 1.0
        self.updateGeometry()
        self.update()
        self.page_clicked.emit(self.first_page)


class PrintPreview(QWidget):
    """Preview bar plus canvas -- the whole Print Preview mode."""

    closed = pyqtSignal()
    print_requested = pyqtSignal()
    shrink_requested = pyqtSignal()

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        # The canvas exists before the bar: the Magnifier button starts checked
        # and its toggled handler talks to the canvas straight away.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.canvas = PreviewCanvas()
        self.scroll.setWidget(self.canvas)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_bar())
        root.addWidget(self.scroll, 1)
        root.addWidget(self._build_status())

    def _build_bar(self):
        bar = QWidget()
        bar.setObjectName("mwToolbar")
        bar.setStyleSheet(TOOLBAR_QSS)
        bar.setFixedHeight(26)
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(2)

        row.addWidget(toolbar_button("print", "Print (Ctrl+P)",
                                     self.print_requested.emit))
        self.magnifier_btn = toolbar_button("zoom", "Magnifier", self._toggle_magnifier,
                                            checkable=True)
        self.magnifier_btn.setChecked(True)
        row.addWidget(self.magnifier_btn)
        row.addWidget(toolbar_button("new", "One Page", lambda: self.set_grid(1, 1)))

        multi = QToolButton()
        multi.setIcon(mw_icons.icon("table", 16))
        multi.setIconSize(QSize(16, 16))
        multi.setFixedSize(QSize(22, 22))
        multi.setToolTip("Multiple Pages")
        multi.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(multi)
        menu.setStyleSheet(theme.MENU_QSS)
        picker = PageGridPicker()
        picker.picked.connect(lambda r, c: (self.set_grid(r, c), menu.close()))
        holder = QWidgetAction(menu)
        holder.setDefaultWidget(picker)
        menu.addAction(holder)
        multi.setMenu(menu)
        row.addWidget(multi)

        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.addItems(["500%", "200%", "150%", "100%", "75%", "50%", "25%",
                                  "10%", "Page Width", "Text Width", "Whole Page",
                                  "Two Pages"])
        self.zoom_combo.setCurrentText("Whole Page")
        self.zoom_combo.setFixedWidth(104)
        self.zoom_combo.activated.connect(self._zoom_chosen)
        row.addWidget(self.zoom_combo)

        row.addWidget(toolbar_button("para_marks", "View Ruler", lambda: None,
                                     checkable=True))
        row.addWidget(toolbar_button("format_painter", "Shrink to Fit",
                                     self.shrink_requested.emit))
        row.addWidget(toolbar_button("doc_map", "Full Screen", lambda: None))

        close = QToolButton()
        close.setText("Close")
        close.setFixedHeight(20)
        close.clicked.connect(self.closed.emit)
        row.addWidget(close)
        row.addStretch(1)
        row.addWidget(toolbar_button("help", "Microsoft Word Help", self.owner.help_contents))
        return bar

    def _build_status(self):
        bar = QWidget()
        bar.setFixedHeight(20)
        bar.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; border-top: 1px solid #aca998;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 0, 6, 0)
        self.status_label = QLabel("Page 1")
        self.status_label.setStyleSheet("font-size: 11px; background: transparent;")
        row.addWidget(self.status_label)
        row.addStretch(1)
        return bar

    # -- api ---------------------------------------------------------------

    def load(self, document: QTextDocument, page_setup: PageSetup):
        self.canvas.set_document(document, page_setup)
        self.canvas.first_page = 0
        self._sync_status()

    def set_grid(self, rows: int, cols: int):
        self.canvas.rows = rows
        self.canvas.cols = cols
        self.canvas.zoom = 0.0
        self.canvas.update()
        self.zoom_combo.setCurrentText("Whole Page" if rows * cols == 1
                                       else f"{rows} x {cols} Pages")
        self._sync_status()

    def _toggle_magnifier(self, on: bool):
        self.canvas.magnifier = on
        self.canvas.setCursor(Qt.CursorShape.WhatsThisCursor if on
                              else Qt.CursorShape.IBeamCursor)

    def _zoom_chosen(self, _index):
        text = self.zoom_combo.currentText().strip()
        if text.endswith("%"):
            try:
                self.canvas.zoom = float(text[:-1]) / 100.0
            except ValueError:
                self.canvas.zoom = 1.0
            self.canvas.rows = self.canvas.cols = 1
        elif text == "Two Pages":
            self.set_grid(1, 2)
            return
        else:
            self.canvas.zoom = 0.0
            self.canvas.rows = self.canvas.cols = 1
        self.canvas.update()
        self._sync_status()

    def _sync_status(self):
        first = self.canvas.first_page + 1
        last = min(self.canvas.page_count(),
                   self.canvas.first_page + self.canvas.rows * self.canvas.cols)
        label = f"Page {first}" if first == last else f"Pages {first}-{last}"
        self.status_label.setText(f"{label}    {self.canvas.page_count()} page(s)")

    def wheelEvent(self, ev):
        step = self.canvas.rows * self.canvas.cols
        delta = -1 if ev.angleDelta().y() > 0 else 1
        new_first = self.canvas.first_page + delta * step
        self.canvas.first_page = max(0, min(max(0, self.canvas.page_count() - 1), new_first))
        self.canvas.update()
        self._sync_status()
