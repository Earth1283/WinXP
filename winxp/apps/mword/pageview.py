"""Print Layout: the white page on the grey desk, and the two rulers.

This is the part of Word that makes it feel like Word. The editor is a plain
QTextEdit whose document has a *page size*, so Qt's layout engine paginates
for real -- the page count in the status bar and the breaks you scroll past
are the document's own, not decoration. Everything the widget paints under
the text (desk, sheet, shadow, the grey gutter between pages, text
boundaries, formatting marks) is drawn here.

Zoom is real too: the document layout is pointed at an off-screen paint
device whose reported DPI is 96 x the zoom factor, which is the same
mechanism Qt uses to lay a document out for a printer. Point sizes, page
geometry and the rulers all scale together instead of drifting apart.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRect, QRectF, QSizeF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QImage, QKeyEvent, QPainter, QPen, QTextCursor,
    QTextOption,
)
from PyQt6.QtWidgets import QTextEdit, QWidget

from .model import DPI, PageSetup, inches

DESK = "#7f8a99"          # Word 2003's blue-grey "outside the page" desk
DESK_DARK = "#6b7583"
PAGE_EDGE = "#4d4d4d"
SHADOW = "#5c6675"
BOUNDARY = "#9aa4b0"
RULER_BG = "#f4f2e8"
RULER_MARGIN_BG = "#c9c6b8"
RULER_EDGE = "#8a8778"
MARK_COLOR = "#5a7fb0"


class PageTextEdit(QTextEdit):
    """The document surface. Draws the sheet; the text is drawn by Qt on top."""

    zoom_changed = pyqtSignal(int)

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.page_setup = PageSetup()
        self.zoom = 1.0
        self.view_mode = "print"
        self.show_marks = False
        self.show_boundaries = False
        self.overtype = False
        self.page_color = QColor("white")   # Format > Background (screen only)

        self.setFrameShape(QTextEdit.Shape.NoFrame)
        # NoWrap keeps QTextEdit from overwriting the document's text width on
        # every resize -- pagination lives on QTextDocument.pageSize() and would
        # be wiped out by setTextWidth(). The wrap mode itself has to be put
        # back on the document afterwards, or nothing wraps at all.
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        option = self.document().defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(option)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QTextEdit { background: transparent; border: none; }")
        self.setCursorWidth(1)
        self.setTabStopDistance(inches(0.5))

        # Off-screen device whose DPI is what the layout scales point sizes by.
        self._scale_device = QImage(1, 1, QImage.Format.Format_ARGB32)
        self._apply_zoom_device()

        self.document().setDocumentMargin(0)
        # Qt stops scrolling at the last line of text; Word keeps scrolling to
        # the bottom edge of the last sheet, so the range is extended to cover
        # the whole final page.
        self._adjusting_range = False
        self.verticalScrollBar().rangeChanged.connect(self._extend_scroll_range)
        self.relayout()

    # ------------------------------------------------------------ geometry

    def _apply_zoom_device(self):
        dpm = int(round(DPI * self.zoom / 0.0254))
        self._scale_device.setDotsPerMeterX(dpm)
        self._scale_device.setDotsPerMeterY(dpm)
        layout = self.document().documentLayout()
        if layout is not None:
            layout.setPaintDevice(self._scale_device)

    def page_pixel_size(self) -> tuple[float, float]:
        ps = self.page_setup
        return ps.page_width * self.zoom, ps.page_height * self.zoom

    def page_origin_x(self) -> float:
        """Left edge of the sheet in document coordinates."""
        page_w, _ = self.page_pixel_size()
        avail = self.viewport().width()
        return max(0.0, (avail - page_w) / 2.0)

    def relayout(self):
        """Re-apply page size and margins after a zoom, resize or Page Setup."""
        doc = self.document()
        ps = self.page_setup
        page_w, page_h = self.page_pixel_size()
        avail = self.viewport().width()
        origin = self.page_origin_x()
        width = max(page_w, float(avail))

        if self.view_mode in ("normal", "web", "outline"):
            # Normal view drops the sheet: one continuous galley, wrapped to
            # the text column, with no pagination other than explicit breaks.
            text_w = ps.text_width * self.zoom if self.view_mode != "web" else avail - 24
            width = max(float(avail), text_w + 24)
            doc.setPageSize(QSizeF(width, 0))
            side = max(12.0, (width - text_w) / 2.0)
            self._set_frame_margins(side, side, inches(0.15), inches(0.15))
        else:
            doc.setPageSize(QSizeF(width, page_h))
            self._set_frame_margins(
                origin + ps.left * self.zoom,
                (width - origin - page_w) + ps.right * self.zoom,
                ps.top * self.zoom,
                ps.bottom * self.zoom,
            )
        self.setTabStopDistance(inches(0.5) * self.zoom)
        option = doc.defaultTextOption()
        if option.wrapMode() != QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere:
            option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            doc.setDefaultTextOption(option)
        self.viewport().update()

    def _extend_scroll_range(self, _minimum, maximum):
        if self._adjusting_range or self.view_mode not in ("print", "reading"):
            return
        _, page_h = self.page_pixel_size()
        wanted = int(self.page_count() * page_h) - self.viewport().height()
        if wanted > maximum:
            self._adjusting_range = True
            self.verticalScrollBar().setMaximum(wanted)
            self._adjusting_range = False

    def _set_frame_margins(self, left, right, top, bottom):
        root = self.document().rootFrame()
        fmt = root.frameFormat()
        fmt.setLeftMargin(max(0.0, left))
        fmt.setRightMargin(max(0.0, right))
        fmt.setTopMargin(max(0.0, top))
        fmt.setBottomMargin(max(0.0, bottom))
        root.setFrameFormat(fmt)

    def set_zoom(self, percent: int):
        percent = max(10, min(500, int(percent)))
        self.zoom = percent / 100.0
        self._apply_zoom_device()
        self.relayout()
        self.zoom_changed.emit(percent)

    def set_view_mode(self, mode: str):
        self.view_mode = mode
        self.relayout()

    def set_page_setup(self, ps: PageSetup):
        self.page_setup = ps
        self.relayout()

    def page_count(self) -> int:
        if self.view_mode not in ("print", "reading"):
            return 1
        return max(1, self.document().pageCount())

    def page_of_cursor(self, cursor: QTextCursor | None = None) -> int:
        cursor = cursor or self.textCursor()
        if self.view_mode not in ("print", "reading"):
            return 1
        _, page_h = self.page_pixel_size()
        rect = self.document().documentLayout().blockBoundingRect(cursor.block())
        line = cursor.block().layout().lineForTextPosition(
            cursor.position() - cursor.block().position())
        y = rect.top() + (line.y() if line.isValid() else 0)
        return int(y // page_h) + 1

    def cursor_offset_from_page_top(self) -> float:
        """The "At 2.5cm" reading in the status bar."""
        cursor = self.textCursor()
        rect = self.document().documentLayout().blockBoundingRect(cursor.block())
        line = cursor.block().layout().lineForTextPosition(
            cursor.position() - cursor.block().position())
        y = rect.top() + (line.y() if line.isValid() else 0)
        if self.view_mode in ("print", "reading"):
            _, page_h = self.page_pixel_size()
            y = y % page_h
        return y / self.zoom

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.relayout()

    # ---------------------------------------------------------------- keys

    def keyPressEvent(self, ev: QKeyEvent):
        if self.overtype and ev.text() and ev.text().isprintable() and \
                not (ev.modifiers() & (Qt.KeyboardModifier.ControlModifier |
                                       Qt.KeyboardModifier.AltModifier |
                                       Qt.KeyboardModifier.MetaModifier)):
            cursor = self.textCursor()
            if not cursor.hasSelection() and not cursor.atBlockEnd():
                cursor.deleteChar()
                self.setTextCursor(cursor)
        if ev.key() == Qt.Key.Key_Insert and not ev.modifiers():
            self.owner.toggle_overtype()
            return
        super().keyPressEvent(ev)

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step = 10 if ev.angleDelta().y() > 0 else -10
            self.set_zoom(int(round(self.zoom * 100)) + step)
            return
        super().wheelEvent(ev)

    def contextMenuEvent(self, ev):
        self.owner.show_editor_context_menu(ev)

    # --------------------------------------------------------------- paint

    def paintEvent(self, ev):
        painter = QPainter(self.viewport())
        if self.view_mode in ("print", "reading"):
            self._paint_pages(painter, ev.rect())
        else:
            painter.fillRect(ev.rect(), self.page_color)
            if self.view_mode == "normal":
                self._paint_normal_breaks(painter)
        painter.end()
        super().paintEvent(ev)
        if self.show_marks:
            painter = QPainter(self.viewport())
            self._paint_formatting_marks(painter)
            painter.end()

    def _content_offset(self) -> QPointF:
        return QPointF(-self.horizontalScrollBar().value(),
                       -self.verticalScrollBar().value())

    def _paint_pages(self, p: QPainter, clip: QRect):
        p.fillRect(clip, QColor(DESK))
        page_w, page_h = self.page_pixel_size()
        off = self._content_offset()
        origin_x = self.page_origin_x() + off.x()
        first = max(0, int((-off.y()) // page_h))
        last = min(self.page_count() - 1, int((-off.y() + self.viewport().height()) // page_h))
        gap = 9.0

        for index in range(first, last + 1):
            top = index * page_h + off.y()
            rect = QRectF(origin_x, top, page_w, page_h - gap)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(SHADOW))
            p.drawRect(QRectF(rect.left() + 3, rect.top() + 3, rect.width(), rect.height()))
            p.setBrush(self.page_color)
            p.setPen(QPen(QColor(PAGE_EDGE), 1))
            p.drawRect(rect)
            if self.show_boundaries:
                self._paint_boundaries(p, rect)

        # Word draws the page number in the gutter when you scroll fast; the
        # gutter itself is just the desk showing through between sheets.
        p.setPen(QPen(QColor(DESK_DARK), 1))
        for index in range(first, last + 1):
            y = (index + 1) * page_h + off.y() - gap
            p.drawLine(QPointF(0, y), QPointF(self.viewport().width(), y))

    def _paint_boundaries(self, p: QPainter, page_rect: QRectF):
        ps = self.page_setup
        z = self.zoom
        inner = QRectF(
            page_rect.left() + ps.left * z,
            page_rect.top() + ps.top * z,
            ps.text_width * z,
            (ps.page_height - ps.top - ps.bottom) * z,
        )
        pen = QPen(QColor(BOUNDARY), 1, Qt.PenStyle.DotLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(inner)

    def _paint_normal_breaks(self, p: QPainter):
        p.setPen(QPen(QColor("#9aa4b0"), 1, Qt.PenStyle.DashLine))
        # Normal view marks soft page breaks with a dotted rule across the page.
        _, page_h = self.page_pixel_size()
        off = self._content_offset()
        doc_h = self.document().size().height()
        y = page_h
        while y < doc_h:
            vy = y + off.y()
            if 0 <= vy <= self.viewport().height():
                p.drawLine(QPointF(0, vy), QPointF(self.viewport().width(), vy))
            y += page_h

    # -- formatting marks -------------------------------------------------

    def _paint_formatting_marks(self, p: QPainter):
        """Show/Hide ¶: pilcrows at paragraph ends, dots for spaces, arrows
        for tabs. Painted over the text so nothing in the document changes."""
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        off = self._content_offset()
        doc = self.document()
        layout_engine = doc.documentLayout()
        view_h = self.viewport().height()
        block = doc.firstBlock()
        while block.isValid():
            rect = layout_engine.blockBoundingRect(block)
            top = rect.top() + off.y()
            if top > view_h:
                break
            if top + rect.height() < 0:
                block = block.next()
                continue
            layout = block.layout()
            text = block.text()
            fmt_font = QFont(block.charFormat().font())
            metrics = QFontMetricsF(fmt_font)
            p.setPen(QColor(MARK_COLOR))
            p.setFont(fmt_font)
            for i in range(layout.lineCount()):
                line = layout.lineAt(i)
                base_y = rect.top() + line.y() + line.ascent() + off.y()
                start, length = line.textStart(), line.textLength()
                for pos in range(start, min(start + length, len(text))):
                    ch = text[pos]
                    if ch == " ":
                        x = rect.left() + line.cursorToX(pos)[0] + off.x()
                        w = metrics.horizontalAdvance(" ")
                        p.drawText(QPointF(x + w / 2 - metrics.horizontalAdvance("·") / 2,
                                           base_y), "·")
                    elif ch == "\t":
                        x = rect.left() + line.cursorToX(pos)[0] + off.x()
                        x2 = rect.left() + line.cursorToX(pos + 1)[0] + off.x()
                        mid = base_y - metrics.xHeight() / 2
                        p.drawLine(QPointF(x + 2, mid), QPointF(x2 - 3, mid))
                        p.drawPolyline([QPointF(x2 - 6, mid - 3), QPointF(x2 - 3, mid),
                                        QPointF(x2 - 6, mid + 3)])
                if i == layout.lineCount() - 1:
                    x = rect.left() + line.cursorToX(start + length)[0] + off.x()
                    p.drawText(QPointF(x + 1, base_y), "¶")
            block = block.next()


# ------------------------------------------------------------------ rulers ---

class HorizontalRuler(QWidget):
    """Word's top ruler: the white text column between grey margin bands, the
    inch scale, the four indent markers, and click-to-place tab stops."""

    HEIGHT = 19
    MARKER_NONE, MARKER_FIRST, MARKER_HANGING, MARKER_LEFT, MARKER_RIGHT = range(5)
    MARKER_MARGIN_L, MARKER_MARGIN_R = 5, 6

    def __init__(self, owner, editor: PageTextEdit):
        super().__init__()
        self.owner = owner
        self.editor = editor
        self.setFixedHeight(self.HEIGHT)
        self.setMouseTracking(True)
        self._drag = self.MARKER_NONE
        self._drag_origin = 0.0

    # -- geometry ---------------------------------------------------------

    def _zoom(self) -> float:
        return self.editor.zoom

    def _page_left(self) -> float:
        return self.editor.page_origin_x() - self.editor.horizontalScrollBar().value()

    def _margin_left_x(self) -> float:
        return self._page_left() + self.editor.page_setup.left * self._zoom()

    def _margin_right_x(self) -> float:
        ps = self.editor.page_setup
        return self._page_left() + (ps.page_width - ps.right) * self._zoom()

    def _block_format(self):
        return self.editor.textCursor().blockFormat()

    def _indent_positions(self) -> tuple[float, float, float]:
        fmt = self._block_format()
        left = fmt.leftMargin() + fmt.indent() * inches(0.5)
        first = left + fmt.textIndent()
        right = self._margin_right_x() - fmt.rightMargin() * self._zoom()
        return (self._margin_left_x() + first * self._zoom(),
                self._margin_left_x() + left * self._zoom(),
                right)

    # -- painting ---------------------------------------------------------

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(RULER_MARGIN_BG))
        left, right = self._margin_left_x(), self._margin_right_x()
        page_l, page_r = self._page_left(), self._page_left() + self.editor.page_pixel_size()[0]
        p.fillRect(QRectF(page_l, 0, page_r - page_l, self.height() - 3),
                   QColor(RULER_MARGIN_BG))
        p.fillRect(QRectF(left, 0, right - left, self.height() - 3), QColor(RULER_BG))
        p.setPen(QPen(QColor(RULER_EDGE), 1))
        p.drawRect(QRectF(page_l, 0, page_r - page_l, self.height() - 3))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        self._paint_scale(p, left, right, page_l, page_r)
        self._paint_tabs(p, left)
        self._paint_markers(p)
        p.end()

    def _paint_scale(self, p: QPainter, left, right, page_l, page_r):
        z = self._zoom()
        font = QFont("Tahoma", 6)
        p.setFont(font)
        step = inches(0.125) * z
        mid = (self.height() - 3) / 2
        i = 0
        x = left
        # Numbers count outward from the left margin, restarting at 0 there,
        # exactly like Word -- the margin bands carry the negative side.
        while x <= page_r + 1:
            self._tick(p, x, i, mid, left, right, page_l, page_r)
            i += 1
            x = left + i * step
        i = -1
        x = left - step
        while x >= page_l - 1:
            self._tick(p, x, i, mid, left, right, page_l, page_r)
            i -= 1
            x = left + i * step

    def _tick(self, p, x, i, mid, left, right, page_l, page_r):
        if x < page_l - 0.5 or x > page_r + 0.5:
            return
        inside = left - 0.5 <= x <= right + 0.5
        if i % 8 == 0:
            inches_from_margin = abs(i) // 8
            if inches_from_margin and inside:
                p.setPen(QColor("#333333"))
                label = str(inches_from_margin)
                fm = QFontMetricsF(p.font())
                p.drawText(QPointF(x - fm.horizontalAdvance(label) / 2, mid + 3), label)
            elif not inside:
                p.setPen(QColor("#6a6a5a"))
                p.drawLine(QPointF(x, mid - 2), QPointF(x, mid + 2))
        elif i % 4 == 0:
            p.setPen(QColor("#5a5a4a"))
            p.drawLine(QPointF(x, mid - 2.5), QPointF(x, mid + 2.5))
        else:
            p.setPen(QColor("#8a8a7a"))
            p.drawLine(QPointF(x, mid - 1), QPointF(x, mid + 1))

    def _paint_tabs(self, p: QPainter, left):
        z = self._zoom()
        p.setPen(QColor("#2b2b2b"))
        p.setBrush(QColor("#2b2b2b"))
        for tab in self._block_format().tabPositions():
            x = left + tab.position * z
            y = self.height() - 5
            kind = tab.type
            if kind == QTextOption.TabType.LeftTab:
                p.drawLine(QPointF(x, y - 5), QPointF(x, y))
                p.drawLine(QPointF(x, y), QPointF(x + 4, y))
            elif kind == QTextOption.TabType.RightTab:
                p.drawLine(QPointF(x, y - 5), QPointF(x, y))
                p.drawLine(QPointF(x - 4, y), QPointF(x, y))
            elif kind == QTextOption.TabType.CenterTab:
                p.drawLine(QPointF(x, y - 5), QPointF(x, y))
                p.drawLine(QPointF(x - 3, y), QPointF(x + 3, y))
            else:
                p.drawLine(QPointF(x, y - 5), QPointF(x, y))
                p.drawLine(QPointF(x - 3, y), QPointF(x + 3, y))
                p.drawEllipse(QRectF(x + 3, y - 1.5, 1.6, 1.6))

    def _paint_markers(self, p: QPainter):
        first_x, left_x, right_x = self._indent_positions()
        p.setPen(QPen(QColor("#4a4a4a"), 1))
        p.setBrush(QColor("#e8e6da"))
        h = self.height() - 3
        # first-line indent: downward triangle at the top
        p.drawPolygon(QPointF(first_x - 4, 1), QPointF(first_x + 4, 1),
                      QPointF(first_x, 6))
        # hanging indent: upward triangle just above the left-indent box
        p.drawPolygon(QPointF(left_x - 4, h - 6), QPointF(left_x + 4, h - 6),
                      QPointF(left_x, h - 11))
        p.drawRect(QRectF(left_x - 4, h - 5, 8, 4))
        # right indent
        p.drawPolygon(QPointF(right_x - 4, h - 6), QPointF(right_x + 4, h - 6),
                      QPointF(right_x, h - 11))

    # -- interaction ------------------------------------------------------

    def _hit(self, x: float) -> int:
        first_x, left_x, right_x = self._indent_positions()
        for marker, mx in ((self.MARKER_FIRST, first_x),
                           (self.MARKER_LEFT, left_x),
                           (self.MARKER_RIGHT, right_x)):
            if abs(x - mx) <= 5:
                return marker
        if abs(x - self._margin_left_x()) <= 3:
            return self.MARKER_MARGIN_L
        if abs(x - self._margin_right_x()) <= 3:
            return self.MARKER_MARGIN_R
        return self.MARKER_NONE

    def mouseMoveEvent(self, ev):
        x = ev.position().x()
        if self._drag == self.MARKER_NONE:
            hit = self._hit(x)
            if hit in (self.MARKER_MARGIN_L, self.MARKER_MARGIN_R):
                self.setCursor(Qt.CursorShape.SplitHCursor)
            elif hit != self.MARKER_NONE:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        self._apply_drag(x, ev.modifiers())

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            self.owner.show_ruler_context_menu(ev)
            return
        x = ev.position().x()
        self._drag = self._hit(x)
        if self._drag == self.MARKER_NONE and ev.position().y() > 6:
            # A click in the ruler body drops a tab stop of the current type.
            self.owner.add_tab_stop_at(self._to_indent(x))

    def mouseReleaseEvent(self, ev):
        self._drag = self.MARKER_NONE
        self.owner.sync_ruler()

    def mouseDoubleClickEvent(self, ev):
        self.owner.open_tabs_dialog()

    def _to_indent(self, x: float) -> float:
        """Viewport x -> offset from the left margin, in unscaled pixels."""
        return (x - self._margin_left_x()) / self._zoom()

    def _apply_drag(self, x: float, modifiers):
        value = self._to_indent(x)
        snap = inches(0.0625)
        if not (modifiers & Qt.KeyboardModifier.AltModifier):
            value = round(value / snap) * snap
        if self._drag in (self.MARKER_MARGIN_L, self.MARKER_MARGIN_R):
            ps = self.editor.page_setup
            if self._drag == self.MARKER_MARGIN_L:
                ps.left = max(0.0, min(ps.page_width - ps.right - inches(0.5),
                                       (x - self._page_left()) / self._zoom()))
            else:
                ps.right = max(0.0, min(ps.page_width - ps.left - inches(0.5),
                                        ps.page_width - (x - self._page_left()) / self._zoom()))
            self.editor.relayout()
            self.update()
            return
        self.owner.set_indent_from_ruler(self._drag, value)
        self.update()


class VerticalRuler(QWidget):
    """The left-hand ruler, present only in Print Layout."""

    WIDTH = 17

    def __init__(self, owner, editor: PageTextEdit):
        super().__init__()
        self.owner = owner
        self.editor = editor
        self.setFixedWidth(self.WIDTH)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(RULER_MARGIN_BG))
        ps = self.editor.page_setup
        z = self.editor.zoom
        _, page_h = self.editor.page_pixel_size()
        off = -self.editor.verticalScrollBar().value()
        p.setPen(QPen(QColor(RULER_EDGE), 1))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        pages = self.editor.page_count()
        font = QFont("Tahoma", 6)
        p.setFont(font)
        for index in range(pages):
            top = index * page_h + off
            if top > self.height() or top + page_h < 0:
                continue
            text_top = top + ps.top * z
            text_h = (ps.page_height - ps.top - ps.bottom) * z
            p.fillRect(QRectF(0, top, self.width() - 1, page_h), QColor(RULER_MARGIN_BG))
            p.fillRect(QRectF(0, text_top, self.width() - 1, text_h), QColor(RULER_BG))
            p.setPen(QPen(QColor(RULER_EDGE), 1))
            p.drawRect(QRectF(0, top, self.width() - 2, page_h - 9))
            step = inches(0.125) * z
            i = 0
            while True:
                y = text_top + i * step
                if y > text_top + text_h:
                    break
                if 0 <= y <= self.height():
                    if i % 8 == 0 and i:
                        p.setPen(QColor("#333333"))
                        label = str(i // 8)
                        fm = QFontMetricsF(p.font())
                        p.drawText(QPointF((self.width() - fm.horizontalAdvance(label)) / 2,
                                           y + 2.5), label)
                    elif i % 4 == 0:
                        p.setPen(QColor("#5a5a4a"))
                        p.drawLine(QPointF(6, y), QPointF(11, y))
                    else:
                        p.setPen(QColor("#8a8a7a"))
                        p.drawLine(QPointF(7.5, y), QPointF(9.5, y))
                i += 1
        p.end()
