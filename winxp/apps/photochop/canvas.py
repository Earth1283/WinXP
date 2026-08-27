"""The image view: zoom, pan, marching ants, guides, and every tool's
interaction behaviour.

Coordinates: `doc_pos()` converts widget pixels to image pixels. Everything
below the event handlers works in image space, so a tool never has to know
what zoom level it is being used at.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QLineF, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QCursor, QFont, QImage, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from . import brushes, imageops as ops
from .model import Layer, Selection, alpha_multiply

# The zoom stops PS 7 steps through with Ctrl+= / Ctrl+-.
ZOOM_LEVELS = [0.0033, 0.005, 0.0067, 0.0083, 0.0125, 0.0167, 0.025, 0.0333, 0.05,
               0.0667, 0.1, 0.125, 0.1667, 0.25, 0.3333, 0.5, 0.6667, 1.0, 2.0, 3.0,
               4.0, 5.0, 6.67, 8.0, 12.0, 16.0]

GRADIENT_PRESETS = {
    "Foreground to Background": None,   # resolved live from the colour swatches
    "Foreground to Transparent": None,
    "Black, White": [(0.0, "#000000"), (1.0, "#ffffff")],
    "Red, Green": [(0.0, "#ff0000"), (1.0, "#00ff00")],
    "Violet, Orange": [(0.0, "#8e44ad"), (1.0, "#e67e22")],
    "Blue, Red, Yellow": [(0.0, "#1e3fd8"), (0.5, "#d81e1e"), (1.0, "#f2d024")],
    "Blue, Yellow, Blue": [(0.0, "#1e3fd8"), (0.5, "#f2d024"), (1.0, "#1e3fd8")],
    "Orange, Yellow, Orange": [(0.0, "#e67e22"), (0.5, "#f7e08a"), (1.0, "#e67e22")],
    "Violet, Green, Orange": [(0.0, "#8e44ad"), (0.5, "#27ae60"), (1.0, "#e67e22")],
    "Yellow, Violet, Orange, Blue": [(0.0, "#f2d024"), (0.33, "#8e44ad"),
                                     (0.66, "#e67e22"), (1.0, "#1e3fd8")],
    "Copper": [(0.0, "#4a2a12"), (0.5, "#d98d44"), (1.0, "#6b3f1d")],
    "Chrome": [(0.0, "#2b3d4f"), (0.35, "#e8f0f6"), (0.55, "#5d7285"), (1.0, "#f2f7fb")],
    "Spectrum": [(0.0, "#ff0000"), (0.17, "#ffff00"), (0.33, "#00ff00"),
                 (0.5, "#00ffff"), (0.67, "#0000ff"), (0.83, "#ff00ff"), (1.0, "#ff0000")],
    "Transparent Rainbow": [(0.0, "#ff0000"), (0.25, "#ffff00"), (0.5, "#00ff00"),
                            (0.75, "#00ffff"), (1.0, "#0000ff")],
    "Transparent Stripes": None,
}

CUSTOM_SHAPES = ["Heart", "Star", "Arrow", "Lightning", "Flower", "Spiral",
                 "Talk Bubble", "Sun", "Crescent", "Paw Print", "Check Mark"]


class Canvas(QWidget):
    position_changed = pyqtSignal(object)     # QPoint in image space or None
    zoom_changed = pyqtSignal(float)
    status_message = pyqtSignal(str)
    document_changed = pyqtSignal()
    color_sampled = pyqtSignal()
    type_committed = pyqtSignal()

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.zoom = 1.0
        self.pan = QPointF(0, 0)          # image-space point pinned to view centre
        self.show_rulers = True
        self.show_grid = False
        self.show_guides = True
        self.snap = True

        self._ants_offset = 0
        self._ants = QTimer(self)
        self._ants.timeout.connect(self._march)
        self._ants.start(110)

        # transient tool state
        self._drag_start: QPointF | None = None
        self._drag_now: QPointF | None = None
        self._dragging = False
        self._button = None
        self._stroke: brushes.Stroke | None = None
        self._lasso_points: list[QPointF] = []
        self._poly_points: list[QPointF] = []
        self._clone_src: QPointF | None = None
        self._clone_offset: QPointF | None = None
        self._smudge_pickup: QImage | None = None
        self._pre_stroke: QImage | None = None
        self._crop_rect: QRectF | None = None
        self._crop_handle = None
        self._transform: dict | None = None
        self._measure: tuple | None = None
        self._samplers: list[QPointF] = []
        self._notes: list[dict] = []
        self._slices: list[QRectF] = []
        self._pen_points: list[dict] = []
        self._type_editor = None
        self._shift = False
        self._alt = False
        self._ctrl = False
        self._effect_fn = None
        self._effect_name = ""
        self._pattern_img = None
        self._space_pan = False
        self._pan_anchor = None
        self._history_source: QImage | None = None
        self._layer_drag_origin: QPoint | None = None

    # -- convenience ---------------------------------------------------

    @property
    def doc(self):
        return self.win.doc

    @property
    def opts(self):
        return self.win.options

    def tool(self) -> str:
        return self.win.current_tool

    def _record(self, name):
        self.doc.history.record(name)

    # -- view geometry -------------------------------------------------

    def view_rect(self) -> QRectF:
        """Where the document lands inside this widget, in widget pixels."""
        w = self.doc.width * self.zoom
        h = self.doc.height * self.zoom
        cx = self.width() / 2 - self.pan.x() * self.zoom
        cy = self.height() / 2 - self.pan.y() * self.zoom
        return QRectF(cx - w / 2, cy - h / 2, w, h)

    def doc_pos(self, pos) -> QPointF:
        r = self.view_rect()
        if self.zoom == 0:
            return QPointF(0, 0)
        return QPointF((pos.x() - r.x()) / self.zoom, (pos.y() - r.y()) / self.zoom)

    def view_pos(self, doc_point: QPointF) -> QPointF:
        r = self.view_rect()
        return QPointF(r.x() + doc_point.x() * self.zoom, r.y() + doc_point.y() * self.zoom)

    def set_zoom(self, z, focus: QPointF | None = None):
        z = max(ZOOM_LEVELS[0], min(ZOOM_LEVELS[-1], z))
        if focus is not None:
            before = self.doc_pos(focus)
            self.zoom = z
            after = self.doc_pos(focus)
            self.pan += before - after
        else:
            self.zoom = z
        self.zoom_changed.emit(self.zoom)
        self.update()

    def zoom_in(self, focus=None):
        for level in ZOOM_LEVELS:
            if level > self.zoom + 1e-6:
                self.set_zoom(level, focus)
                return
        self.set_zoom(ZOOM_LEVELS[-1], focus)

    def zoom_out(self, focus=None):
        for level in reversed(ZOOM_LEVELS):
            if level < self.zoom - 1e-6:
                self.set_zoom(level, focus)
                return
        self.set_zoom(ZOOM_LEVELS[0], focus)

    def fit_on_screen(self):
        if not self.width() or not self.height():
            return
        margin = 40
        z = min((self.width() - margin) / self.doc.width,
                (self.height() - margin) / self.doc.height)
        self.pan = QPointF(0, 0)
        self.set_zoom(z)

    def actual_pixels(self):
        self.pan = QPointF(0, 0)
        self.set_zoom(1.0)

    # -- painting ------------------------------------------------------

    def _march(self):
        if self.doc.has_selection() or self._crop_rect or self._transform:
            self._ants_offset = (self._ants_offset + 1) % 8
            self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#808080"))
        r = self.view_rect()

        p.fillRect(r.adjusted(3, 3, 3, 3), QColor(0, 0, 0, 60))
        from .model import checker_pixmap
        p.save()
        p.setClipRect(r)
        p.drawTiledPixmap(r, checker_pixmap())
        p.restore()
        composite = self.doc.composite()
        preview = self._live_preview(composite)

        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.zoom < 1.0)
        p.drawImage(r, preview)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        if self.doc.quick_mask and self.doc.has_selection():
            self._paint_quick_mask(p, r)

        p.setPen(QPen(QColor("#3a3a3a"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r.adjusted(-0.5, -0.5, 0.5, 0.5))

        if self.show_grid:
            self._paint_grid(p, r)
        if self.show_guides:
            self._paint_guides(p, r)
        if self.doc.has_selection() and not self.doc.quick_mask:
            self._paint_ants(p, self.doc.selection.path)
        self._paint_tool_overlay(p, r)
        p.end()

    def _live_preview(self, composite: QImage) -> QImage:
        """Layer in whatever the current gesture is doing but hasn't committed."""
        if self._stroke is None and self._transform is None:
            return composite
        out = composite.copy()
        if self._transform is not None:
            t = self._transform
            painter = QPainter(out)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.drawImage(0, 0, t["remainder"])
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            quad = t.get("quad")
            if quad:
                from PyQt6.QtGui import QTransform
                src = t["source"]
                src_quad = QPolygonF([QPointF(0, 0), QPointF(src.width(), 0),
                                      QPointF(src.width(), src.height()),
                                      QPointF(0, src.height())])
                tr = QTransform()
                if QTransform.quadToQuad(src_quad, QPolygonF(quad), tr):
                    painter.setTransform(tr)
                    painter.drawImage(0, 0, src)
                    painter.resetTransform()
            else:
                painter.drawImage(t["rect"], t["source"])
            painter.end()
        if self._stroke is not None and getattr(self._stroke, "quick_mask", False):
            painter = QPainter(out)
            painter.setOpacity(0.5)
            painter.drawImage(0, 0, self._stroke.buffer)
            painter.end()
        elif self._stroke is not None:
            layer = self.doc.active
            painter = QPainter(out)
            painter.setOpacity(self._stroke.opacity * layer.opacity)
            if self._stroke.erase:
                painter.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_DestinationOut)
            buf = self._stroke.buffer
            if self.doc.has_selection():
                buf = alpha_multiply(buf, self.doc.selection.mask)
            painter.drawImage(0, 0, buf)
            painter.end()
        return out

    def _paint_quick_mask(self, p, r):
        mask = ops.invert(self.doc.selection.mask)
        overlay = QImage(mask.size(), QImage.Format.Format_ARGB32_Premultiplied)
        overlay.fill(Qt.GlobalColor.transparent)
        painter = QPainter(overlay)
        painter.fillRect(overlay.rect(), QColor(255, 0, 0, 128))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, _grey_to_alpha(mask))
        painter.end()
        p.drawImage(r, overlay)

    def _paint_grid(self, p, r):
        p.setPen(QPen(QColor(120, 120, 160, 160), 1, Qt.PenStyle.DotLine))
        step = 25 * self.zoom
        if step < 4:
            return
        x = r.left()
        i = 0
        while x < r.right():
            p.setPen(QPen(QColor(110, 110, 170, 200 if i % 4 == 0 else 110), 1,
                          Qt.PenStyle.SolidLine if i % 4 == 0 else Qt.PenStyle.DotLine))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            x += step
            i += 1
        y = r.top()
        i = 0
        while y < r.bottom():
            p.setPen(QPen(QColor(110, 110, 170, 200 if i % 4 == 0 else 110), 1,
                          Qt.PenStyle.SolidLine if i % 4 == 0 else Qt.PenStyle.DotLine))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            y += step
            i += 1

    def _paint_guides(self, p, r):
        p.setPen(QPen(QColor("#00c8ff"), 1))
        for gy in self.doc.guides_h:
            y = r.top() + gy * self.zoom
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        for gx in self.doc.guides_v:
            x = r.left() + gx * self.zoom
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))

    def _paint_ants(self, p, path: QPainterPath | None):
        if path is None or path.isEmpty():
            return
        p.save()
        r = self.view_rect()
        p.translate(r.topLeft())
        p.scale(self.zoom, self.zoom)
        white = QPen(QColor("white"), 1 / max(0.05, self.zoom))
        black = QPen(QColor("black"), 1 / max(0.05, self.zoom))
        black.setStyle(Qt.PenStyle.CustomDashLine)
        black.setDashPattern([4, 4])
        black.setDashOffset(self._ants_offset)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(white)
        p.drawPath(path)
        p.setPen(black)
        p.drawPath(path)
        p.restore()

    def _paint_tool_overlay(self, p, r):
        tool = self.tool()
        if self._crop_rect is not None:
            self._paint_crop(p, r)
        if self._transform is not None:
            self._paint_transform(p)
        if tool in ("lasso", "magnetic_lasso") and self._lasso_points:
            self._paint_polyline(p, self._lasso_points, close=False)
        if tool == "poly_lasso" and self._poly_points:
            pts = list(self._poly_points)
            if self._drag_now is not None:
                pts.append(self._drag_now)
            self._paint_polyline(p, pts, close=False)
        if tool in ("marquee_rect", "marquee_ellipse") and self._dragging and self._drag_start:
            self._paint_marquee_preview(p)
        if tool.startswith("shape_") and self._dragging and self._drag_start:
            self._paint_shape_preview(p)
        if tool == "gradient" and self._dragging and self._drag_start and self._drag_now:
            p.setPen(QPen(QColor("black"), 1))
            a, b = self.view_pos(self._drag_start), self.view_pos(self._drag_now)
            p.drawLine(a, b)
            p.setPen(QPen(QColor("white"), 1, Qt.PenStyle.DotLine))
            p.drawLine(a, b)
        if tool == "measure" and self._measure:
            self._paint_measure(p)
        if self._pen_points:
            self._paint_pen_path(p)
        for pt in self._samplers:
            v = self.view_pos(pt)
            p.setPen(QPen(QColor("white"), 3))
            p.drawLine(QPointF(v.x() - 5, v.y()), QPointF(v.x() + 5, v.y()))
            p.setPen(QPen(QColor("black"), 1))
            p.drawLine(QPointF(v.x() - 5, v.y()), QPointF(v.x() + 5, v.y()))
            p.drawLine(QPointF(v.x(), v.y() - 5), QPointF(v.x(), v.y() + 5))
        for note in self._notes:
            v = self.view_pos(note["pos"])
            p.setPen(QPen(QColor("#8a7a20"), 1))
            p.setBrush(QColor(note.get("color", "#f5e04a")))
            p.drawRect(QRectF(v.x(), v.y() - 12, 14, 12))
            p.setPen(QPen(QColor("#8a7a20"), 1))
            for i in range(3):
                p.drawLine(QPointF(v.x() + 2, v.y() - 9 + i * 3),
                           QPointF(v.x() + 12, v.y() - 9 + i * 3))
        for sl in self._slices:
            v = QRectF(self.view_pos(sl.topLeft()), self.view_pos(sl.bottomRight()))
            p.setPen(QPen(QColor("#3a6ea5"), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(v)
        if self._clone_src is not None and self.tool() in ("clone_stamp", "healing"):
            v = self.view_pos(self._clone_src)
            p.setPen(QPen(QColor("black"), 1))
            p.drawLine(QPointF(v.x() - 6, v.y()), QPointF(v.x() + 6, v.y()))
            p.drawLine(QPointF(v.x(), v.y() - 6), QPointF(v.x(), v.y() + 6))

    def _paint_polyline(self, p, pts, close):
        if len(pts) < 2:
            return
        poly = QPolygonF([self.view_pos(q) for q in pts])
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("black"), 1, Qt.PenStyle.DashLine))
        p.drawPolyline(poly)

    def _paint_marquee_preview(self, p):
        rect = self._normalised_drag()
        if rect is None:
            return
        v = QRectF(self.view_pos(rect.topLeft()), self.view_pos(rect.bottomRight()))
        path = QPainterPath()
        if self.tool() == "marquee_ellipse":
            path.addEllipse(v)
        else:
            path.addRect(v)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("white"), 1))
        p.drawPath(path)
        pen = QPen(QColor("black"), 1, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([4, 4])
        pen.setDashOffset(self._ants_offset)
        p.setPen(pen)
        p.drawPath(path)

    def _paint_shape_preview(self, p):
        rect = self._normalised_drag()
        if rect is None:
            return
        v = QRectF(self.view_pos(rect.topLeft()), self.view_pos(rect.bottomRight()))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("black"), 1, Qt.PenStyle.DashLine))
        p.drawPath(self._shape_path(v))

    def _paint_crop(self, p, r):
        v = QRectF(self.view_pos(self._crop_rect.topLeft()),
                   self.view_pos(self._crop_rect.bottomRight())).normalized()
        if self.opts.get("shield", True):
            shield = QPainterPath()
            shield.addRect(r)
            inner = QPainterPath()
            inner.addRect(v)
            p.fillPath(shield.subtracted(inner), QColor(0, 0, 0, 190))
        p.setPen(QPen(QColor("black"), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(v)
        p.setBrush(QColor("white"))
        p.setPen(QPen(QColor("black"), 1))
        for hx, hy in self._handle_points(v):
            p.drawRect(QRectF(hx - 3, hy - 3, 6, 6))

    def _paint_transform(self, p):
        t = self._transform
        v = QRectF(self.view_pos(t["rect"].topLeft()), self.view_pos(t["rect"].bottomRight()))
        quad = t.get("quad")
        p.setPen(QPen(QColor("#4a4a4a"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if quad:
            p.drawPolygon(QPolygonF([self.view_pos(q) for q in quad]))
            pts = [(self.view_pos(q).x(), self.view_pos(q).y()) for q in quad]
        else:
            p.drawRect(v)
            pts = self._handle_points(v)
        p.setBrush(QColor("white"))
        for hx, hy in pts:
            p.drawRect(QRectF(hx - 3.5, hy - 3.5, 7, 7))
        c = v.center()
        p.setPen(QPen(QColor("#4a4a4a"), 1))
        p.drawEllipse(c, 5, 5)
        p.drawLine(QPointF(c.x() - 7, c.y()), QPointF(c.x() + 7, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - 7), QPointF(c.x(), c.y() + 7))

    def _paint_measure(self, p):
        a, b = self._measure
        va, vb = self.view_pos(a), self.view_pos(b)
        p.setPen(QPen(QColor("black"), 1))
        p.drawLine(va, vb)
        p.setPen(QPen(QColor("white"), 1, Qt.PenStyle.DotLine))
        p.drawLine(va, vb)
        for v in (va, vb):
            p.setBrush(QColor("white"))
            p.setPen(QPen(QColor("black"), 1))
            p.drawRect(QRectF(v.x() - 2.5, v.y() - 2.5, 5, 5))

    def _paint_pen_path(self, p):
        pts = [self.view_pos(a["pos"]) for a in self._pen_points]
        p.setPen(QPen(QColor("black"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if len(pts) > 1:
            p.drawPolyline(QPolygonF(pts))
        for i, v in enumerate(pts):
            p.setBrush(QColor("white") if i else QColor("#3a6ea5"))
            p.drawRect(QRectF(v.x() - 2.5, v.y() - 2.5, 5, 5))

    def _hit_handle(self, rect: QRectF, pos: QPointF):
        v = QRectF(self.view_pos(rect.topLeft()),
                   self.view_pos(rect.bottomRight())).normalized()
        vp = self.view_pos(pos)
        for i, (hx, hy) in enumerate(self._handle_points(v)):
            if abs(hx - vp.x()) <= 5 and abs(hy - vp.y()) <= 5:
                return i
        return None

    @staticmethod
    def _handle_points(v: QRectF):
        return [(v.left(), v.top()), (v.center().x(), v.top()), (v.right(), v.top()),
                (v.right(), v.center().y()), (v.right(), v.bottom()),
                (v.center().x(), v.bottom()), (v.left(), v.bottom()),
                (v.left(), v.center().y())]

    # -- mouse ---------------------------------------------------------

    def _normalised_drag(self) -> QRectF | None:
        if self._drag_start is None or self._drag_now is None:
            return None
        rect = QRectF(self._drag_start, self._drag_now).normalized()
        style = self.opts.get("style", "Normal")
        if style == "Fixed Size":
            rect = QRectF(self._drag_start, QSizeF_safe(self.opts.get("fixed_w", 64),
                                                        self.opts.get("fixed_h", 64)))
        elif style == "Fixed Aspect Ratio":
            ratio = max(0.01, self.opts.get("fixed_w", 1) / max(1, self.opts.get("fixed_h", 1)))
            rect.setHeight(rect.width() / ratio)
        if self._shift:
            side = max(rect.width(), rect.height())
            rect.setWidth(side)
            rect.setHeight(side)
        return rect

    def mousePressEvent(self, ev):
        self.setFocus()
        pos = self.doc_pos(ev.position())
        self._button = ev.button()
        self._shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self._alt = bool(ev.modifiers() & Qt.KeyboardModifier.AltModifier)
        self._ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self._drag_start = pos
        self._drag_now = pos
        self._dragging = True

        if self._space_pan or ev.button() == Qt.MouseButton.MiddleButton:
            self._pan_anchor = (ev.position(), QPointF(self.pan))
            return
        if self._transform is not None:
            self._transform_press(pos)
            return
        handler = getattr(self, f"_press_{self.tool()}", None)
        if handler:
            handler(pos, ev)
        else:
            self._press_generic(pos, ev)
        self.update()

    def mouseMoveEvent(self, ev):
        pos = self.doc_pos(ev.position())
        self._drag_now = pos
        self._shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        inside = QRectF(0, 0, self.doc.width, self.doc.height).contains(pos)
        self.position_changed.emit(pos.toPoint() if inside else None)

        if self._pan_anchor is not None:
            start, base = self._pan_anchor
            delta = (ev.position() - start) / max(0.01, self.zoom)
            self.pan = base - QPointF(delta.x(), delta.y())
            self.update()
            return
        if self._transform is not None and self._dragging:
            self._transform_move(pos)
            self.update()
            return
        if self._dragging:
            handler = getattr(self, f"_move_{self.tool()}", None)
            if handler:
                handler(pos, ev)
        elif self.tool() == "poly_lasso" and self._poly_points:
            self.update()
        self._update_cursor()
        if self._dragging:
            self.update()

    def mouseReleaseEvent(self, ev):
        pos = self.doc_pos(ev.position())
        if self._pan_anchor is not None:
            self._pan_anchor = None
            self._dragging = False
            return
        if self._transform is not None:
            self._transform_release()
            self._dragging = False
            return
        if self._dragging:
            handler = getattr(self, f"_release_{self.tool()}", None)
            if handler:
                handler(pos, ev)
        self._dragging = False
        self._button = None
        self.update()

    def mouseDoubleClickEvent(self, ev):
        if self.tool() == "poly_lasso" and self._poly_points:
            self._close_poly_lasso()
        elif self.tool() == "crop" and self._crop_rect:
            self.commit_crop()
        elif self._transform is not None:
            self.commit_transform()

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if ev.angleDelta().y() > 0:
                self.zoom_in(ev.position())
            else:
                self.zoom_out(ev.position())
            return
        step = 40 / max(0.05, self.zoom)
        if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.pan += QPointF(-ev.angleDelta().y() / 120 * step, 0)
        else:
            self.pan += QPointF(0, -ev.angleDelta().y() / 120 * step)
        self.update()

    def _update_cursor(self):
        tool = self.tool()
        if self._space_pan:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        spec = self.win.tool_spec(tool)
        shape = {
            "move": Qt.CursorShape.SizeAllCursor,
            "hand": Qt.CursorShape.OpenHandCursor,
            "ibeam": Qt.CursorShape.IBeamCursor,
            "arrow": Qt.CursorShape.ArrowCursor,
            "zoom": Qt.CursorShape.PointingHandCursor,
        }.get(spec.cursor if spec else "cross", Qt.CursorShape.CrossCursor)
        self.setCursor(shape)

    # -- generic fallbacks ---------------------------------------------

    def _press_generic(self, pos, ev):
        pass

    # ============================================================ tools ==
    # -- selection ------------------------------------------------------

    def _selop(self, ev=None):
        mode = {"new": "replace", "add": "add", "subtract": "subtract",
                "intersect": "intersect"}[self.opts.get("selop", "new")]
        if ev is not None:
            if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier and mode == "replace":
                mode = "add"
            elif ev.modifiers() & Qt.KeyboardModifier.AltModifier and mode == "replace":
                mode = "subtract"
        return mode

    def _commit_selection_path(self, path, mode):
        sel = self.doc.ensure_selection()
        sel.set_path(path, mode, self.opts.get("antialias", True))
        feather = self.opts.get("feather", 0)
        if feather:
            sel.feather(feather)
        self._record("Marquee" if "marquee" in self.tool() else "Lasso")
        self.document_changed.emit()

    def _release_marquee_rect(self, pos, ev):
        rect = self._normalised_drag()
        if rect is None or rect.width() < 1 or rect.height() < 1:
            self.deselect()
            return
        path = QPainterPath()
        path.addRect(rect)
        self._commit_selection_path(path, self._selop(ev))

    def _release_marquee_ellipse(self, pos, ev):
        rect = self._normalised_drag()
        if rect is None or rect.width() < 1 or rect.height() < 1:
            self.deselect()
            return
        path = QPainterPath()
        path.addEllipse(rect)
        self._commit_selection_path(path, self._selop(ev))

    def _press_marquee_row(self, pos, ev):
        path = QPainterPath()
        path.addRect(QRectF(0, int(pos.y()), self.doc.width, 1))
        self._commit_selection_path(path, self._selop(ev))

    def _press_marquee_col(self, pos, ev):
        path = QPainterPath()
        path.addRect(QRectF(int(pos.x()), 0, 1, self.doc.height))
        self._commit_selection_path(path, self._selop(ev))

    def _press_lasso(self, pos, ev):
        self._lasso_points = [pos]

    def _move_lasso(self, pos, ev):
        self._lasso_points.append(pos)

    def _release_lasso(self, pos, ev):
        if len(self._lasso_points) < 3:
            self._lasso_points = []
            self.deselect()
            return
        path = QPainterPath(self._lasso_points[0])
        for q in self._lasso_points[1:]:
            path.lineTo(q)
        path.closeSubpath()
        self._lasso_points = []
        self._commit_selection_path(path, self._selop(ev))

    def _press_magnetic_lasso(self, pos, ev):
        self._lasso_points = [self._snap_to_edge(pos)]

    def _move_magnetic_lasso(self, pos, ev):
        snapped = self._snap_to_edge(pos)
        if not self._lasso_points or QLineF(self._lasso_points[-1], snapped).length() > 3:
            self._lasso_points.append(snapped)

    _release_magnetic_lasso = _release_lasso

    def _snap_to_edge(self, pos: QPointF) -> QPointF:
        """Look inside the tool's Width for the strongest local contrast and
        pull the point onto it -- the honest version of 'magnetic'."""
        radius = max(2, int(self.opts.get("width", 10)))
        img = self.doc.composite()
        best, best_score = pos, -1.0
        cx, cy = int(pos.x()), int(pos.y())
        for dy in range(-radius, radius + 1, 2):
            for dx in range(-radius, radius + 1, 2):
                x, y = cx + dx, cy + dy
                if not (1 <= x < img.width() - 1 and 1 <= y < img.height() - 1):
                    continue
                c0 = img.pixelColor(x - 1, y)
                c1 = img.pixelColor(x + 1, y)
                c2 = img.pixelColor(x, y - 1)
                c3 = img.pixelColor(x, y + 1)
                score = (abs(c0.red() - c1.red()) + abs(c0.green() - c1.green())
                         + abs(c0.blue() - c1.blue()) + abs(c2.red() - c3.red())
                         + abs(c2.green() - c3.green()) + abs(c2.blue() - c3.blue()))
                score -= math.hypot(dx, dy) * 2
                if score > best_score:
                    best_score, best = score, QPointF(x, y)
        return best

    def _press_poly_lasso(self, pos, ev):
        if self._poly_points and QLineF(self._poly_points[0], pos).length() < 6:
            self._close_poly_lasso()
            return
        self._poly_points.append(pos)
        self._dragging = False

    def _close_poly_lasso(self):
        if len(self._poly_points) < 3:
            self._poly_points = []
            return
        path = QPainterPath(self._poly_points[0])
        for q in self._poly_points[1:]:
            path.lineTo(q)
        path.closeSubpath()
        self._poly_points = []
        self._commit_selection_path(path, self._selop())

    def _press_wand(self, pos, ev):
        source = (self.doc.composite() if self.opts.get("sample_merged")
                  else self.doc.active.image)
        mask = magic_wand_mask(source, pos.toPoint(), self.opts.get("tolerance", 32),
                               self.opts.get("contiguous", True))
        if mask is None:
            return
        sel = self.doc.ensure_selection()
        sel.set_mask(mask, self._selop(ev))
        if self.opts.get("feather", 0):
            sel.feather(self.opts["feather"])
        self._record("Magic Wand")
        self.document_changed.emit()

    def deselect(self):
        if self.doc.selection:
            self.doc.selection.clear()
        self.doc.selection = None
        self.update()
        self.document_changed.emit()

    # -- move -----------------------------------------------------------

    def _press_move(self, pos, ev):
        self._pre_stroke = self.doc.active.image.copy()
        self._layer_drag_origin = pos

    def _move_move(self, pos, ev):
        if self._layer_drag_origin is None or self._pre_stroke is None:
            return
        dx = int(pos.x() - self._layer_drag_origin.x())
        dy = int(pos.y() - self._layer_drag_origin.y())
        layer = self.doc.active
        if layer.locked_position or layer.locked_all:
            self.status_message.emit("Could not move: the layer is locked.")
            return
        moved = self.doc.blank_image()
        p = QPainter(moved)
        if self.doc.has_selection():
            floating = alpha_multiply(self._pre_stroke, self.doc.selection.mask)
            rest = self._pre_stroke.copy()
            pr = QPainter(rest)
            pr.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            pr.drawImage(0, 0, _grey_to_alpha(self.doc.selection.mask))
            pr.end()
            p.drawImage(0, 0, rest)
            p.drawImage(dx, dy, floating)
        else:
            p.drawImage(dx, dy, self._pre_stroke)
        p.end()
        layer.image = moved
        self.doc.invalidate()

    def _release_move(self, pos, ev):
        if self._pre_stroke is not None:
            self._record("Move")
            self.document_changed.emit()
        self._pre_stroke = None
        self._layer_drag_origin = None

    # -- crop / slice ---------------------------------------------------

    def _press_crop(self, pos, ev):
        if self._crop_rect is not None:
            self._crop_handle = self._hit_handle(self._crop_rect, pos)
            if self._crop_handle is not None:
                return
        self._crop_rect = QRectF(pos, pos)

    def _move_crop(self, pos, ev):
        if self._crop_rect is None:
            return
        if self._crop_handle is not None:
            self._crop_rect = _resize_rect(self._crop_rect, self._crop_handle, pos)
        else:
            self._crop_rect = QRectF(self._drag_start, pos).normalized()

    def _release_crop(self, pos, ev):
        self._crop_handle = None
        if self._crop_rect and (self._crop_rect.width() < 2 or self._crop_rect.height() < 2):
            self._crop_rect = None
        self.status_message.emit("Press Enter to crop, or Esc to cancel.")

    def commit_crop(self):
        if self._crop_rect is None:
            return
        rect = self._crop_rect.toAlignedRect().intersected(
            QRect(0, 0, self.doc.width, self.doc.height))
        if rect.isEmpty():
            self._crop_rect = None
            return
        for layer in self.doc.layers:
            layer.image = layer.image.copy(rect)
            if layer.mask is not None:
                layer.mask = layer.mask.copy(rect)
        self.doc.width, self.doc.height = rect.width(), rect.height()
        self.doc.selection = None
        self.doc.invalidate()
        self._crop_rect = None
        self._record("Crop")
        self.document_changed.emit()

    def cancel_crop(self):
        self._crop_rect = None
        self.update()

    def _press_slice(self, pos, ev):
        self._slices.append(QRectF(pos, pos))

    def _move_slice(self, pos, ev):
        if self._slices:
            self._slices[-1] = QRectF(self._drag_start, pos).normalized()

    def _release_slice(self, pos, ev):
        if self._slices and (self._slices[-1].width() < 3 or self._slices[-1].height() < 3):
            self._slices.pop()
        self.status_message.emit(f"{len(self._slices)} user slice(s) defined.")

    # -- painting -------------------------------------------------------

    def _begin_stroke(self, erase=False, color=None, flow_key="flow"):
        if self.doc.quick_mask:
            return self._begin_quick_mask_stroke(flow_key)
        layer = self.doc.active
        if layer.locked_pixels or layer.locked_all:
            self.status_message.emit("Could not use the tool: the layer is locked.")
            return None
        if layer.kind in ("adjustment", "type"):
            self.status_message.emit(
                "Could not use the tool because the layer is not a pixel layer.")
            return None
        brush = dict(self.opts.get("brush", {}))
        if self.tool() == "pencil":
            brush["hardness"] = 100
        self._pre_stroke = layer.image.copy()
        col = color if color is not None else (
            self.win.fg_color if self._button == Qt.MouseButton.LeftButton
            else self.win.bg_color)
        stroke = brushes.Stroke(
            QSize(self.doc.width, self.doc.height), brush, col,
            self.opts.get(flow_key, 100) / 100.0,
            self.opts.get("opacity", 100) / 100.0, erase=erase)
        self._stroke = stroke
        return stroke

    def _begin_quick_mask_stroke(self, flow_key):
        """In Quick Mask mode the brushes edit the selection itself: black
        masks, white selects, exactly as if the mask were a greyscale layer."""
        self.doc.ensure_selection()
        if self.doc.selection.mask is None:
            self.doc.selection.select_all()
        brush = dict(self.opts.get("brush", {}))
        colour = (self.win.fg_color if self._button == Qt.MouseButton.LeftButton
                  else self.win.bg_color)
        lum = (colour.red() * 77 + colour.green() * 151 + colour.blue() * 28) >> 8
        stroke = brushes.Stroke(
            QSize(self.doc.width, self.doc.height), brush, QColor(lum, lum, lum),
            self.opts.get(flow_key, 100) / 100.0,
            self.opts.get("opacity", 100) / 100.0)
        stroke.quick_mask = True
        self._stroke = stroke
        return stroke

    def _finish_quick_mask_stroke(self):
        sel = self.doc.selection
        painter = QPainter(sel.mask)
        painter.setOpacity(self._stroke.opacity)
        painter.drawImage(0, 0, self._stroke.buffer)
        painter.end()
        sel.path = sel._path_from_mask(sel.mask)
        self._stroke = None
        self._record("Quick Mask")
        self.document_changed.emit()

    def _press_brush(self, pos, ev):
        if self._begin_stroke():
            self._stroke.to(pos)

    def _move_brush(self, pos, ev):
        if self._stroke:
            self._stroke.to(pos)

    def _release_brush(self, pos, ev):
        self._finish_stroke("Brush Tool")

    def _press_pencil(self, pos, ev):
        col = None
        if self.opts.get("auto_erase"):
            under = _pixel_at(self.doc.active.image, pos)
            if under is not None and under.rgb() == self.win.fg_color.rgb():
                col = self.win.bg_color
        if self._begin_stroke(color=col):
            self._stroke.to(pos)

    _move_pencil = _move_brush

    def _release_pencil(self, pos, ev):
        self._finish_stroke("Pencil Tool")

    def _press_eraser(self, pos, ev):
        layer = self.doc.active
        # On the locked Background layer PS erases to the background colour
        # instead of to transparency.
        erase_to_bg = layer.locked_all and layer.name == "Background"
        if self._begin_stroke(erase=not erase_to_bg,
                              color=self.win.bg_color if erase_to_bg else None):
            self._stroke.to(pos)

    _move_eraser = _move_brush

    def _release_eraser(self, pos, ev):
        self._finish_stroke("Eraser")

    def _press_magic_eraser(self, pos, ev):
        mask = magic_wand_mask(self.doc.active.image, pos.toPoint(),
                               self.opts.get("tolerance", 32),
                               self.opts.get("contiguous", True))
        if mask is None:
            return
        layer = self.doc.active
        p = QPainter(layer.image)
        p.setOpacity(self.opts.get("opacity", 100) / 100.0)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        p.drawImage(0, 0, _grey_to_alpha(mask))
        p.end()
        layer.locked_all = False
        self.doc.invalidate()
        self._record("Magic Eraser")
        self.document_changed.emit()

    def _press_bg_eraser(self, pos, ev):
        self._bg_target = _pixel_at(self.doc.active.image, pos)
        if self._begin_stroke(erase=True):
            self._stroke.to(pos)

    _move_bg_eraser = _move_brush
    _release_bg_eraser = _release_eraser

    def _finish_stroke(self, name):
        if self._stroke is None:
            return
        if getattr(self._stroke, "quick_mask", False):
            self._finish_quick_mask_stroke()
            return
        layer = self.doc.active
        buf = self._stroke.buffer
        if self.doc.has_selection():
            buf = alpha_multiply(buf, self.doc.selection.mask)
            self._stroke.buffer = buf
        layer.image = self._stroke.commit(
            layer.image, self.opts.get("mode", "Normal"), layer.locked_transparency)
        self._stroke = None
        self._pre_stroke = None
        self.doc.invalidate()
        self._record(name)
        self.document_changed.emit()

    # -- stamps / healing -----------------------------------------------

    def _press_clone_stamp(self, pos, ev):
        if ev.modifiers() & Qt.KeyboardModifier.AltModifier:
            self._clone_src = pos
            self._clone_offset = None
            self.status_message.emit("Clone source set.")
            self._dragging = False
            return
        if self._clone_src is None:
            self.status_message.emit(
                "Could not use the clone stamp: Alt-click to define a source point.")
            self._dragging = False
            return
        if self._clone_offset is None or not self.opts.get("aligned", True):
            self._clone_offset = pos - self._clone_src
        self._pre_stroke = self.doc.active.image.copy()
        self._clone_dab(pos)

    def _move_clone_stamp(self, pos, ev):
        if self._clone_offset is not None and self._pre_stroke is not None:
            self._clone_dab(pos)

    def _release_clone_stamp(self, pos, ev):
        if self._pre_stroke is not None:
            self._pre_stroke = None
            self._record("Clone Stamp")
            self.document_changed.emit()

    def _clone_dab(self, pos):
        source = (self.doc.composite() if self.opts.get("sample_merged")
                  else self._pre_stroke)
        src_pt = pos - self._clone_offset
        self._stamp_from(source, src_pt, pos)

    def _stamp_from(self, source: QImage, src_pt: QPointF, dst_pt: QPointF, heal=False):
        brush = self.opts.get("brush", {})
        size = max(1, int(brush.get("size", 13)))
        src_rect = QRect(int(src_pt.x() - size / 2), int(src_pt.y() - size / 2), size, size)
        patch = source.copy(src_rect)
        if heal:
            dst_rect = QRect(int(dst_pt.x() - size / 2), int(dst_pt.y() - size / 2), size, size)
            patch = brushes.heal_patch(self.doc.active.image.copy(dst_rect), patch)
        mask = brushes.stamp(size, brush.get("hardness", 100))
        p = QPainter(patch)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        p.drawImage(0, 0, mask)
        p.end()
        target = QPainter(self.doc.active.image)
        target.setOpacity(self.opts.get("opacity", 100) / 100.0)
        if self.doc.has_selection():
            target.setClipPath(self.doc.selection.path or QPainterPath())
        target.drawImage(QPointF(dst_pt.x() - size / 2, dst_pt.y() - size / 2), patch)
        target.end()
        self.doc.invalidate()

    def _press_pattern_stamp(self, pos, ev):
        from .layer_styles import _pattern_tile
        self._pattern_img = _tile_to_full(_pattern_tile(self.opts.get("pattern", "Checkerboard")),
                                          self.doc.width, self.doc.height)
        self._pre_stroke = self.doc.active.image.copy()
        self._stamp_from(self._pattern_img, pos, pos)

    def _move_pattern_stamp(self, pos, ev):
        if getattr(self, "_pattern_img", None) is not None:
            self._stamp_from(self._pattern_img, pos, pos)

    def _release_pattern_stamp(self, pos, ev):
        self._pre_stroke = None
        self._record("Pattern Stamp")
        self.document_changed.emit()

    def _press_healing(self, pos, ev):
        if ev.modifiers() & Qt.KeyboardModifier.AltModifier:
            self._clone_src = pos
            self._clone_offset = None
            self.status_message.emit("Healing source set.")
            self._dragging = False
            return
        if self._clone_src is None:
            self.status_message.emit(
                "Could not use the healing brush: Alt-click to define a source point.")
            self._dragging = False
            return
        if self._clone_offset is None or not self.opts.get("aligned", True):
            self._clone_offset = pos - self._clone_src
        self._pre_stroke = self.doc.active.image.copy()
        self._stamp_from(self._pre_stroke, pos - self._clone_offset, pos, heal=True)

    def _move_healing(self, pos, ev):
        if self._clone_offset is not None and self._pre_stroke is not None:
            self._stamp_from(self._pre_stroke, pos - self._clone_offset, pos, heal=True)

    def _release_healing(self, pos, ev):
        if self._pre_stroke is not None:
            self._pre_stroke = None
            self._record("Healing Brush")
            self.document_changed.emit()

    def _press_patch(self, pos, ev):
        self._lasso_points = [pos]

    def _move_patch(self, pos, ev):
        self._lasso_points.append(pos)

    def _release_patch(self, pos, ev):
        if len(self._lasso_points) < 3:
            self._lasso_points = []
            return
        path = QPainterPath(self._lasso_points[0])
        for q in self._lasso_points[1:]:
            path.lineTo(q)
        path.closeSubpath()
        self._lasso_points = []
        sel = self.doc.ensure_selection()
        sel.set_path(path, "replace", True)
        self.status_message.emit(
            "Drag the patch selection over the area to sample from.")
        self._record("Patch Selection")
        self.document_changed.emit()

    # -- history brushes -------------------------------------------------

    def _history_state_image(self) -> QImage | None:
        hist = self.doc.history
        src = hist.snapshots[0] if hist.snapshots else None
        if src is None:
            return None
        img = QImage(self.doc.width, self.doc.height,
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        for layer in src.layers:
            if layer.visible and layer.kind == "pixel":
                p.setOpacity(layer.opacity)
                p.drawImage(0, 0, layer.image)
        p.end()
        return img

    def _press_history_brush(self, pos, ev):
        self._history_source = self._history_state_image()
        if self._history_source is None:
            self.status_message.emit("Could not use the history brush: no history state is set.")
            self._dragging = False
            return
        self._pre_stroke = self.doc.active.image.copy()
        self._stamp_from(self._history_source, pos, pos)

    def _move_history_brush(self, pos, ev):
        if self._history_source is not None:
            self._stamp_from(self._history_source, pos, pos)

    def _release_history_brush(self, pos, ev):
        if self._history_source is not None:
            self._history_source = None
            self._pre_stroke = None
            self._record("History Brush")
            self.document_changed.emit()

    def _press_art_history(self, pos, ev):
        self._history_source = self._history_state_image()
        if self._history_source is None:
            self._dragging = False
            return
        self._pre_stroke = self.doc.active.image.copy()
        self._art_dab(pos)

    def _move_art_history(self, pos, ev):
        if self._history_source is not None:
            self._art_dab(pos)

    _release_art_history = _release_history_brush

    def _art_dab(self, pos):
        import random
        style = self.opts.get("art_style", "Tight Short")
        length = {"Tight Short": 4, "Tight Medium": 8, "Loose Medium": 14,
                  "Dab": 1, "Tight Curl": 10, "Loose Curl": 18}.get(style, 6)
        for _ in range(3):
            ang = random.uniform(0, math.tau)
            for step in range(length):
                jitter = QPointF(pos.x() + math.cos(ang) * step,
                                 pos.y() + math.sin(ang) * step)
                ang += random.uniform(-0.4, 0.4) if "Curl" in style else 0
                self._stamp_from(self._history_source, jitter, jitter)

    # -- gradient / bucket ----------------------------------------------

    def _release_gradient(self, pos, ev):
        if self._drag_start is None:
            return
        layer = self.doc.active
        if layer.locked_all or layer.locked_pixels:
            self.status_message.emit("Could not use the gradient tool: the layer is locked.")
            return
        start, end = self._drag_start, pos
        if self._shift:
            end = _constrain_45(start, end)
        grad = self._build_gradient(start, end)
        fill = self.doc.blank_image()
        p = QPainter(fill)
        p.fillRect(fill.rect(), QBrush(grad))
        p.end()
        if self.opts.get("dither"):
            fill = ops.add_noise(fill, 1.5, monochromatic=True)
        if self.doc.has_selection():
            fill = alpha_multiply(fill, self.doc.selection.mask)
        p = QPainter(layer.image)
        p.setOpacity(self.opts.get("opacity", 100) / 100.0)
        from .model import _QT_MODES
        if layer.locked_transparency:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        else:
            p.setCompositionMode(_QT_MODES.get(self.opts.get("mode", "Normal"),
                                               _QT_MODES["Normal"]))
        p.drawImage(0, 0, fill)
        p.end()
        self.doc.invalidate()
        self._record("Gradient")
        self.document_changed.emit()

    def _gradient_stops(self):
        name = self.opts.get("gradient", "Foreground to Background")
        preset = GRADIENT_PRESETS.get(name)
        if preset:
            return [(pos, QColor(c)) for pos, c in preset]
        if name == "Foreground to Transparent":
            transparent = QColor(self.win.fg_color)
            transparent.setAlpha(0)
            return [(0.0, QColor(self.win.fg_color)), (1.0, transparent)]
        if name == "Transparent Stripes":
            out = []
            for i in range(6):
                t = i / 5.0
                c = QColor(self.win.fg_color)
                c.setAlpha(0 if i % 2 else 255)
                out.append((t, c))
            return out
        return [(0.0, QColor(self.win.fg_color)), (1.0, QColor(self.win.bg_color))]

    def _build_gradient(self, start: QPointF, end: QPointF):
        stops = self._gradient_stops()
        if self.opts.get("reverse"):
            stops = [(1.0 - pos, c) for pos, c in reversed(stops)]
        kind = self.opts.get("gradient_type", "Linear")
        if kind == "Radial":
            grad = QRadialGradient(start, max(1.0, QLineF(start, end).length()))
        elif kind == "Angle":
            grad = QConicalGradient(start, -QLineF(start, end).angle())
        elif kind == "Reflected":
            mirrored = QPointF(start.x() - (end.x() - start.x()),
                               start.y() - (end.y() - start.y()))
            grad = QLinearGradient(mirrored, end)
            stops = ([(0.5 - pos / 2, c) for pos, c in reversed(stops)]
                     + [(0.5 + pos / 2, c) for pos, c in stops])
        elif kind == "Diamond":
            grad = QRadialGradient(start, max(1.0, QLineF(start, end).length()))
        else:
            grad = QLinearGradient(start, end)
        for pos, colour in stops:
            grad.setColorAt(max(0.0, min(1.0, pos)), colour)
        return grad

    def _press_bucket(self, pos, ev):
        layer = self.doc.active
        if layer.locked_all or layer.locked_pixels:
            self.status_message.emit("Could not use the paint bucket: the layer is locked.")
            return
        source = (self.doc.composite() if self.opts.get("sample_merged") else layer.image)
        mask = magic_wand_mask(source, pos.toPoint(), self.opts.get("tolerance", 32),
                               self.opts.get("contiguous", True))
        if mask is None:
            return
        if self.doc.has_selection():
            mask = _intersect_masks(mask, self.doc.selection.mask)
        fill = self.doc.blank_image()
        p = QPainter(fill)
        if self.opts.get("fill_source") == "Pattern":
            from .layer_styles import _pattern_tile
            p.drawTiledPixmap(fill.rect(),
                              QPixmap.fromImage(_pattern_tile(self.opts.get("pattern",
                                                                            "Checkerboard"))))
        else:
            colour = (self.win.fg_color if self._button == Qt.MouseButton.LeftButton
                      else self.win.bg_color)
            p.fillRect(fill.rect(), colour)
        p.end()
        fill = alpha_multiply(fill, mask)
        p = QPainter(layer.image)
        p.setOpacity(self.opts.get("opacity", 100) / 100.0)
        from .model import _QT_MODES
        if layer.locked_transparency:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        else:
            p.setCompositionMode(_QT_MODES.get(self.opts.get("mode", "Normal"),
                                               _QT_MODES["Normal"]))
        p.drawImage(0, 0, fill)
        p.end()
        self.doc.invalidate()
        self._record("Paint Bucket")
        self.document_changed.emit()

    # -- focus / toning tools -------------------------------------------

    def _effect_press(self, pos, effect_fn, name):
        layer = self.doc.active
        if layer.locked_all or layer.locked_pixels:
            self.status_message.emit("Could not use the tool: the layer is locked.")
            return False
        self._pre_stroke = layer.image.copy()
        self._effect_fn = effect_fn
        self._effect_name = name
        brushes.apply_effect_dab(layer.image, pos, self.opts.get("brush", {}),
                                 self.opts.get("strength", 50) / 100.0, effect_fn)
        self.doc.invalidate()
        return True

    def _effect_move(self, pos):
        if self._pre_stroke is None:
            return
        brushes.apply_effect_dab(self.doc.active.image, pos, self.opts.get("brush", {}),
                                 self.opts.get("strength", 50) / 100.0, self._effect_fn)
        self.doc.invalidate()

    def _effect_release(self):
        if self._pre_stroke is not None:
            self._pre_stroke = None
            self._record(self._effect_name)
            self.document_changed.emit()

    def _press_blur(self, pos, ev):
        self._effect_press(pos, lambda img: ops.gaussian_blur(img, 2.0), "Blur Tool")

    def _move_blur(self, pos, ev):
        self._effect_move(pos)

    def _release_blur(self, pos, ev):
        self._effect_release()

    def _press_sharpen(self, pos, ev):
        self._effect_press(pos, lambda img: ops.unsharp_mask(img, 90, 1.2, 0), "Sharpen Tool")

    _move_sharpen = _move_blur
    _release_sharpen = _release_blur

    def _press_dodge(self, pos, ev):
        rng = self.opts.get("range", "Midtones")
        exposure = self.opts.get("exposure", 50) / 100.0
        self._strength_override = exposure
        self._effect_press(pos, lambda img: _tone(img, rng, +exposure), "Dodge Tool")

    _move_dodge = _move_blur
    _release_dodge = _release_blur

    def _press_burn(self, pos, ev):
        rng = self.opts.get("range", "Midtones")
        exposure = self.opts.get("exposure", 50) / 100.0
        self._effect_press(pos, lambda img: _tone(img, rng, -exposure), "Burn Tool")

    _move_burn = _move_blur
    _release_burn = _release_blur

    def _press_sponge(self, pos, ev):
        direction = -40 if self.opts.get("sponge_mode") == "Desaturate" else 40
        self._effect_press(pos, lambda img: ops.hue_saturation(img, 0, direction, 0),
                           "Sponge Tool")

    _move_sponge = _move_blur
    _release_sponge = _release_blur

    def _press_smudge(self, pos, ev):
        layer = self.doc.active
        if layer.locked_all or layer.locked_pixels:
            return
        self._pre_stroke = layer.image.copy()
        _, self._smudge_pickup = brushes.smudge_dab(
            layer.image, pos, pos, self.opts.get("brush", {}),
            self.opts.get("strength", 50) / 100.0, None)

    def _move_smudge(self, pos, ev):
        if self._pre_stroke is None:
            return
        _, self._smudge_pickup = brushes.smudge_dab(
            self.doc.active.image, self._drag_start, pos, self.opts.get("brush", {}),
            self.opts.get("strength", 50) / 100.0, self._smudge_pickup)
        self.doc.invalidate()

    def _release_smudge(self, pos, ev):
        self._smudge_pickup = None
        if self._pre_stroke is not None:
            self._pre_stroke = None
            self._record("Smudge Tool")
            self.document_changed.emit()

    # -- shapes ----------------------------------------------------------

    def _shape_path(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        tool = self.tool()
        if tool == "shape_rect":
            path.addRect(rect)
        elif tool == "shape_round":
            r = self.opts.get("radius", 10)
            path.addRoundedRect(rect, r, r)
        elif tool == "shape_ellipse":
            path.addEllipse(rect)
        elif tool == "shape_poly":
            sides = max(3, self.opts.get("sides", 5))
            cx, cy = rect.center().x(), rect.center().y()
            rx, ry = rect.width() / 2, rect.height() / 2
            pts = []
            for i in range(sides):
                a = -math.pi / 2 + i * math.tau / sides
                pts.append(QPointF(cx + math.cos(a) * rx, cy + math.sin(a) * ry))
            path.addPolygon(QPolygonF(pts))
            path.closeSubpath()
        elif tool == "shape_line":
            w = max(1, self.opts.get("weight", 1))
            line = QLineF(self._drag_start, self._drag_now or self._drag_start)
            normal = line.normalVector().unitVector()
            off = QPointF(normal.dx() * w / 2, normal.dy() * w / 2)
            path.addPolygon(QPolygonF([line.p1() + off, line.p2() + off,
                                       line.p2() - off, line.p1() - off]))
            path.closeSubpath()
        else:
            path = custom_shape_path(self.opts.get("custom_shape", "Heart"), rect)
        return path

    def _release_shape_common(self, pos, ev):
        rect = self._normalised_drag()
        if rect is None or rect.width() < 1:
            return
        path = self._shape_path(rect)
        kind = self.opts.get("shape_kind", "Fill Pixels")
        if kind == "Paths":
            self.doc.paths.append((f"Path {len(self.doc.paths) + 1}", path))
            self.status_message.emit("Work path created.")
        elif kind == "Shape Layers":
            layer = Layer(f"Shape {len(self.doc.layers)}", self.doc.blank_image(), kind="shape")
            p = QPainter(layer.image)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, self.opts.get("antialias", True))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.win.fg_color)
            p.drawPath(path)
            p.end()
            self.doc.add_layer(layer)
        else:
            layer = self.doc.active
            p = QPainter(layer.image)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, self.opts.get("antialias", True))
            p.setOpacity(self.opts.get("opacity", 100) / 100.0)
            if self.doc.has_selection():
                p.setClipPath(self.doc.selection.path or QPainterPath())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.win.fg_color)
            p.drawPath(path)
            p.end()
        self.doc.invalidate()
        self._record("Shape Tool")
        self.document_changed.emit()

    for _name in ("shape_rect", "shape_round", "shape_ellipse", "shape_poly",
                  "shape_line", "shape_custom"):
        locals()[f"_release_{_name}"] = _release_shape_common
    del _name

    # -- pen / paths ------------------------------------------------------

    def _press_pen(self, pos, ev):
        if self._pen_points and QLineF(self._pen_points[0]["pos"], pos).length() < 6:
            self._close_path()
            return
        self._pen_points.append({"pos": pos})
        self._dragging = False

    def _close_path(self):
        if len(self._pen_points) < 2:
            self._pen_points = []
            return
        path = QPainterPath(self._pen_points[0]["pos"])
        for a in self._pen_points[1:]:
            path.lineTo(a["pos"])
        path.closeSubpath()
        self.doc.paths.append((f"Path {len(self.doc.paths) + 1}", path))
        self._pen_points = []
        self.status_message.emit("Work path created.")
        self.document_changed.emit()

    def _press_freeform_pen(self, pos, ev):
        self._lasso_points = [pos]

    def _move_freeform_pen(self, pos, ev):
        self._lasso_points.append(pos)

    def _release_freeform_pen(self, pos, ev):
        if len(self._lasso_points) < 3:
            self._lasso_points = []
            return
        path = QPainterPath(self._lasso_points[0])
        for q in self._lasso_points[1:]:
            path.lineTo(q)
        self.doc.paths.append((f"Path {len(self.doc.paths) + 1}", path))
        self._lasso_points = []
        self.status_message.emit("Work path created.")
        self.document_changed.emit()

    # -- sampling / measuring ---------------------------------------------

    def _sample_color(self, pos) -> QColor:
        img = self.doc.composite()
        size = {"Point Sample": 1, "3 by 3 Average": 3,
                "5 by 5 Average": 5}.get(self.opts.get("sample_size", "Point Sample"), 1)
        x, y = int(pos.x()), int(pos.y())
        if size == 1:
            if 0 <= x < img.width() and 0 <= y < img.height():
                return img.pixelColor(x, y)
            return QColor("black")
        r = g = b = n = 0
        half = size // 2
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                if 0 <= x + dx < img.width() and 0 <= y + dy < img.height():
                    c = img.pixelColor(x + dx, y + dy)
                    r += c.red()
                    g += c.green()
                    b += c.blue()
                    n += 1
        n = max(1, n)
        return QColor(r // n, g // n, b // n)

    def _press_eyedropper(self, pos, ev):
        colour = self._sample_color(pos)
        if ev.button() == Qt.MouseButton.RightButton or self._alt:
            self.win.set_bg_color(colour)
        else:
            self.win.set_fg_color(colour)
        self.color_sampled.emit()

    _move_eyedropper = _press_eyedropper

    def _press_color_sampler(self, pos, ev):
        if len(self._samplers) >= 4:
            self._samplers.pop(0)
        self._samplers.append(pos)
        self.win.update_samplers(self._samplers)

    def _press_measure(self, pos, ev):
        self._measure = (pos, pos)

    def _move_measure(self, pos, ev):
        if self._measure:
            self._measure = (self._measure[0], pos)
            a, b = self._measure
            line = QLineF(a, b)
            self.win.update_measure(line)

    # -- notes -------------------------------------------------------------

    def _press_notes(self, pos, ev):
        from .dialogs import NoteDialog
        text = NoteDialog.get_text(self, self.opts.get("author", "You"))
        if text is not None:
            self._notes.append({"pos": pos, "text": text,
                                "author": self.opts.get("author", "You"),
                                "color": self.opts.get("note_color", "#f5e04a")})
        self._dragging = False

    def _press_audio_note(self, pos, ev):
        from ...xp_dialog import XPMessageBox
        XPMessageBox.information(
            self, "PhotoChop",
            "No sound input device was detected.\n\nThe annotation has been recorded anyway.")
        self._notes.append({"pos": pos, "text": "[audio annotation]",
                            "author": self.opts.get("author", "You"), "color": "#a0d0f0"})
        self._dragging = False

    # -- navigation ---------------------------------------------------------

    def _press_hand(self, pos, ev):
        self._pan_anchor = (ev.position(), QPointF(self.pan))

    def _press_zoom(self, pos, ev):
        if ev.modifiers() & Qt.KeyboardModifier.AltModifier:
            self.zoom_out(ev.position())
        else:
            self.zoom_in(ev.position())
        self._dragging = False

    # -- type ---------------------------------------------------------------

    def _press_type_h(self, pos, ev):
        self.win.begin_type(pos, vertical=False, mask=False)
        self._dragging = False

    def _press_type_v(self, pos, ev):
        self.win.begin_type(pos, vertical=True, mask=False)
        self._dragging = False

    def _press_type_mask_h(self, pos, ev):
        self.win.begin_type(pos, vertical=False, mask=True)
        self._dragging = False

    def _press_type_mask_v(self, pos, ev):
        self.win.begin_type(pos, vertical=True, mask=True)
        self._dragging = False

    # -- free transform -----------------------------------------------------

    def begin_transform(self, mode="Free Transform"):
        layer = self.doc.active
        if layer.locked_all:
            self.status_message.emit("Could not transform: the layer is locked.")
            return
        if self.doc.has_selection():
            rect = QRectF(self.doc.selection.bounds())
            source = alpha_multiply(layer.image, self.doc.selection.mask)
            remainder = layer.image.copy()
            p = QPainter(remainder)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            p.drawImage(0, 0, _grey_to_alpha(self.doc.selection.mask))
            p.end()
        else:
            rect = QRectF(0, 0, self.doc.width, self.doc.height)
            source = layer.image.copy()
            remainder = self.doc.blank_image()
        self._transform = {
            "mode": mode, "rect": QRectF(rect), "orig": QRectF(rect),
            "source": source.copy(rect.toAlignedRect()), "remainder": remainder,
            "quad": None, "handle": None, "angle": 0.0,
        }
        self.status_message.emit(
            "Press Enter to apply the transformation, or Esc to cancel.")
        self.update()

    def _transform_press(self, pos):
        t = self._transform
        quad = t.get("quad") or _rect_quad(t["rect"])
        idx, dist = None, 12 / max(0.05, self.zoom)
        for i, q in enumerate(quad):
            if QLineF(q, pos).length() < dist:
                idx = i
                break
        t["handle"] = idx
        t["grab"] = pos
        t["quad_at_grab"] = [QPointF(q) for q in quad]
        t["rect_at_grab"] = QRectF(t["rect"])

    def _transform_move(self, pos):
        t = self._transform
        mode = t["mode"]
        delta = pos - t["grab"]
        if t["handle"] is None:
            t["rect"] = t["rect_at_grab"].translated(delta)
            if t.get("quad"):
                t["quad"] = [q + delta for q in t["quad_at_grab"]]
            return
        if mode in ("Distort", "Perspective", "Skew"):
            quad = [QPointF(q) for q in t["quad_at_grab"]]
            i = t["handle"]
            if mode == "Distort":
                quad[i] = quad[i] + delta
            elif mode == "Skew":
                if i in (0, 1):
                    quad[0] = quad[0] + QPointF(delta.x(), 0)
                    quad[1] = quad[1] + QPointF(delta.x(), 0)
                else:
                    quad[2] = quad[2] + QPointF(delta.x(), 0)
                    quad[3] = quad[3] + QPointF(delta.x(), 0)
            else:  # Perspective -- move the handle and mirror its neighbour
                quad[i] = quad[i] + delta
                mirror = {0: 1, 1: 0, 2: 3, 3: 2}[i]
                quad[mirror] = quad[mirror] - QPointF(delta.x(), 0)
            t["quad"] = quad
            return
        if mode == "Rotate":
            c = t["rect"].center()
            a0 = math.atan2(t["grab"].y() - c.y(), t["grab"].x() - c.x())
            a1 = math.atan2(pos.y() - c.y(), pos.x() - c.x())
            t["angle"] = math.degrees(a1 - a0)
            t["quad"] = _rotate_quad(_rect_quad(t["rect_at_grab"]), c, t["angle"])
            return
        # Scale from the grabbed corner
        r = QRectF(t["rect_at_grab"])
        i = t["handle"]
        if i == 0:
            r.setTopLeft(r.topLeft() + delta)
        elif i == 1:
            r.setTopRight(r.topRight() + delta)
        elif i == 2:
            r.setBottomRight(r.bottomRight() + delta)
        else:
            r.setBottomLeft(r.bottomLeft() + delta)
        if self._shift and r.height():
            ratio = t["orig"].width() / max(1.0, t["orig"].height())
            r.setWidth(r.height() * ratio)
        t["rect"] = r.normalized()
        t["quad"] = None

    def _transform_release(self):
        if self._transform:
            self._transform["handle"] = None

    def commit_transform(self):
        t = self._transform
        if t is None:
            return
        layer = self.doc.active
        out = self.doc.blank_image()
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(0, 0, t["remainder"])
        quad = t.get("quad")
        src = t["source"]
        if quad:
            from PyQt6.QtGui import QTransform
            src_quad = QPolygonF([QPointF(0, 0), QPointF(src.width(), 0),
                                  QPointF(src.width(), src.height()), QPointF(0, src.height())])
            dst_quad = QPolygonF(quad)
            tr = QTransform()
            if QTransform.quadToQuad(src_quad, dst_quad, tr):
                p.setTransform(tr)
                p.drawImage(0, 0, src)
                p.resetTransform()
        else:
            p.drawImage(t["rect"], src)
        p.end()
        layer.image = out
        self._transform = None
        self.doc.invalidate()
        self._record("Free Transform")
        self.document_changed.emit()
        self.status_message.emit("")

    def cancel_transform(self):
        self._transform = None
        self.update()

    def transform_numeric(self, fn):
        """Apply a one-shot transform (Rotate 90, Flip, ...) to the active layer."""
        layer = self.doc.active
        if self.doc.has_selection():
            floating = alpha_multiply(layer.image, self.doc.selection.mask)
            bounds = self.doc.selection.bounds()
            piece = fn(floating.copy(bounds))
            out = layer.image.copy()
            p = QPainter(out)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            p.drawImage(0, 0, _grey_to_alpha(self.doc.selection.mask))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.drawImage(bounds.center() - QPoint(piece.width() // 2, piece.height() // 2), piece)
            p.end()
            layer.image = out
        else:
            transformed = fn(layer.image)
            out = self.doc.blank_image()
            p = QPainter(out)
            p.drawImage((self.doc.width - transformed.width()) // 2,
                        (self.doc.height - transformed.height()) // 2, transformed)
            p.end()
            layer.image = out
        self.doc.invalidate()
        self._record("Transform")
        self.document_changed.emit()

    # -- keyboard --------------------------------------------------------

    def keyPressEvent(self, ev):
        key = ev.key()
        if key == Qt.Key.Key_Space and not ev.isAutoRepeat():
            self._space_pan = True
            self._update_cursor()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._crop_rect is not None:
                self.commit_crop()
                return
            if self._transform is not None:
                self.commit_transform()
                return
        if key == Qt.Key.Key_Escape:
            if self._crop_rect is not None:
                self.cancel_crop()
                return
            if self._transform is not None:
                self.cancel_transform()
                return
            if self._poly_points or self._pen_points:
                self._poly_points = []
                self._pen_points = []
                self.update()
                return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.win.clear_selection_pixels()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if self.tool() == "move":
                step = 10 if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
                dx = -step if key == Qt.Key.Key_Left else (step if key == Qt.Key.Key_Right else 0)
                dy = -step if key == Qt.Key.Key_Up else (step if key == Qt.Key.Key_Down else 0)
                self.nudge(dx, dy)
                return
        super().keyPressEvent(ev)

    def nudge(self, dx, dy):
        layer = self.doc.active
        if layer.locked_position or layer.locked_all:
            self.status_message.emit("Could not move: the layer is locked.")
            return
        self._pre_stroke = layer.image.copy()
        self._layer_drag_origin = QPointF(0, 0)
        self._move_move(QPointF(dx, dy), None)
        self._pre_stroke = None
        self._layer_drag_origin = None
        self._record("Move")
        self.document_changed.emit()

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key.Key_Space and not ev.isAutoRepeat():
            self._space_pan = False
            self._pan_anchor = None
            self._update_cursor()
            return
        super().keyReleaseEvent(ev)

    def leaveEvent(self, ev):
        self.position_changed.emit(None)


# ------------------------------------------------------------- helpers -----

def QSizeF_safe(w, h):
    from PyQt6.QtCore import QSizeF
    return QSizeF(float(w), float(h))


def _pixel_at(img: QImage, pos: QPointF):
    """pixelColor() warns and returns garbage off-image, so ask first."""
    x, y = int(pos.x()), int(pos.y())
    if 0 <= x < img.width() and 0 <= y < img.height():
        return img.pixelColor(x, y)
    return None


def _grey_to_alpha(grey: QImage) -> QImage:
    from .model import mask_to_alpha
    return mask_to_alpha(grey)


def _intersect_masks(a: QImage, b: QImage) -> QImage:
    out = a.copy()
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Darken)
    p.drawImage(0, 0, b)
    p.end()
    return out


def _tile_to_full(tile: QImage, w, h) -> QImage:
    out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawTiledPixmap(out.rect(), QPixmap.fromImage(tile))
    p.end()
    return out


def _tone(img: QImage, tonal_range: str, amount: float) -> QImage:
    """Dodge/Burn: push a tonal band, leaving the others alone."""
    lut = []
    for i in range(256):
        t = i / 255.0
        if tonal_range == "Shadows":
            weight = max(0.0, 1.0 - t * 2.2)
        elif tonal_range == "Highlights":
            weight = max(0.0, t * 2.2 - 1.2)
        else:
            weight = 1.0 - abs(t - 0.5) * 2
        delta = amount * 90 * weight
        lut.append(max(0, min(255, int(i + delta))))
    return ops.apply_lut(img, lut)


def _constrain_45(a: QPointF, b: QPointF) -> QPointF:
    dx, dy = b.x() - a.x(), b.y() - a.y()
    ang = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
    length = math.hypot(dx, dy)
    return QPointF(a.x() + math.cos(ang) * length, a.y() + math.sin(ang) * length)


def _rect_quad(r: QRectF):
    return [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]


def _rotate_quad(quad, centre: QPointF, degrees: float):
    rad = math.radians(degrees)
    c, s = math.cos(rad), math.sin(rad)
    out = []
    for q in quad:
        dx, dy = q.x() - centre.x(), q.y() - centre.y()
        out.append(QPointF(centre.x() + dx * c - dy * s, centre.y() + dx * s + dy * c))
    return out


def _resize_rect(rect: QRectF, handle: int, pos: QPointF) -> QRectF:
    r = QRectF(rect)
    setters = [r.setTopLeft, lambda p: r.setTop(p.y()), r.setTopRight,
               lambda p: r.setRight(p.x()), r.setBottomRight,
               lambda p: r.setBottom(p.y()), r.setBottomLeft,
               lambda p: r.setLeft(p.x())]
    setters[handle](pos)
    return r.normalized()


def magic_wand_mask(img: QImage, seed: QPoint, tolerance: int, contiguous: bool):
    """Flood (or global) select by colour distance. Returns a white-on-black mask."""
    w, h = img.width(), img.height()
    x0, y0 = seed.x(), seed.y()
    if not (0 <= x0 < w and 0 <= y0 < h):
        return None
    buf, _, _ = ops.to_buf(img)
    rp, gp, bp = ops.plane(buf, ops.R), ops.plane(buf, ops.G), ops.plane(buf, ops.B)
    idx0 = y0 * w + x0
    tr, tg, tb = rp[idx0], gp[idx0], bp[idx0]
    tol = tolerance * 3
    out = bytearray(w * h)
    if not contiguous:
        for i in range(w * h):
            if abs(rp[i] - tr) + abs(gp[i] - tg) + abs(bp[i] - tb) <= tol:
                out[i] = 255
    else:
        seen = bytearray(w * h)
        stack = [idx0]
        while stack:
            i = stack.pop()
            if seen[i]:
                continue
            seen[i] = 1
            if abs(rp[i] - tr) + abs(gp[i] - tg) + abs(bp[i] - tb) > tol:
                continue
            out[i] = 255
            x, y = i % w, i // w
            if x > 0:
                stack.append(i - 1)
            if x < w - 1:
                stack.append(i + 1)
            if y > 0:
                stack.append(i - w)
            if y < h - 1:
                stack.append(i + w)
    mask_buf = bytearray(w * h * 4)
    mask_buf[0::4] = out
    mask_buf[1::4] = out
    mask_buf[2::4] = out
    mask_buf[3::4] = b"\xff" * (w * h)
    return ops.from_buf(mask_buf, w, h)


def custom_shape_path(name: str, rect: QRectF) -> QPainterPath:
    """The handful of Custom Shapes worth having, drawn to fit `rect`."""
    path = QPainterPath()
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    def P(u, v):
        return QPointF(x + u * w, y + v * h)

    if name == "Heart":
        path.moveTo(P(0.5, 1.0))
        path.cubicTo(P(-0.15, 0.55), P(0.1, 0.0), P(0.5, 0.28))
        path.cubicTo(P(0.9, 0.0), P(1.15, 0.55), P(0.5, 1.0))
    elif name == "Star":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = 0.5 if i % 2 == 0 else 0.21
            pts.append(P(0.5 + math.cos(a) * r, 0.5 + math.sin(a) * r))
        path.addPolygon(QPolygonF(pts))
        path.closeSubpath()
    elif name == "Arrow":
        path.addPolygon(QPolygonF([P(0, 0.35), P(0.6, 0.35), P(0.6, 0.12), P(1, 0.5),
                                   P(0.6, 0.88), P(0.6, 0.65), P(0, 0.65)]))
        path.closeSubpath()
    elif name == "Lightning":
        path.addPolygon(QPolygonF([P(0.55, 0), P(0.2, 0.55), P(0.45, 0.55), P(0.35, 1),
                                   P(0.8, 0.4), P(0.52, 0.4), P(0.72, 0)]))
        path.closeSubpath()
    elif name == "Flower":
        for i in range(6):
            a = i * math.tau / 6
            c = P(0.5 + math.cos(a) * 0.27, 0.5 + math.sin(a) * 0.27)
            petal = QPainterPath()
            petal.addEllipse(c, w * 0.2, h * 0.2)
            path = path.united(petal)
    elif name == "Spiral":
        pts = []
        for i in range(160):
            t = i / 160.0
            a = t * math.tau * 3
            r = t * 0.48
            pts.append(P(0.5 + math.cos(a) * r, 0.5 + math.sin(a) * r))
        path.moveTo(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
    elif name == "Talk Bubble":
        path.addRoundedRect(QRectF(x, y, w, h * 0.75), w * 0.12, h * 0.12)
        tail = QPainterPath()
        tail.addPolygon(QPolygonF([P(0.25, 0.72), P(0.2, 1.0), P(0.45, 0.72)]))
        path = path.united(tail)
    elif name == "Sun":
        path.addEllipse(QRectF(x + w * 0.28, y + h * 0.28, w * 0.44, h * 0.44))
        for i in range(12):
            a = i * math.tau / 12
            ray = QPainterPath()
            ray.addPolygon(QPolygonF([
                P(0.5 + math.cos(a) * 0.28, 0.5 + math.sin(a) * 0.28),
                P(0.5 + math.cos(a + 0.1) * 0.5, 0.5 + math.sin(a + 0.1) * 0.5),
                P(0.5 + math.cos(a - 0.1) * 0.5, 0.5 + math.sin(a - 0.1) * 0.5)]))
            path = path.united(ray)
    elif name == "Crescent":
        outer = QPainterPath()
        outer.addEllipse(rect)
        inner = QPainterPath()
        inner.addEllipse(QRectF(x + w * 0.28, y, w, h))
        path = outer.subtracted(inner)
    elif name == "Paw Print":
        path.addEllipse(QRectF(x + w * 0.22, y + h * 0.42, w * 0.56, h * 0.5))
        for u in (0.1, 0.36, 0.62, 0.86):
            toe = QPainterPath()
            toe.addEllipse(QRectF(x + u * w - w * 0.09, y + h * 0.1, w * 0.18, h * 0.26))
            path = path.united(toe)
    else:  # Check Mark
        path.addPolygon(QPolygonF([P(0.05, 0.5), P(0.22, 0.34), P(0.4, 0.58),
                                   P(0.8, 0.1), P(0.96, 0.26), P(0.4, 0.92)]))
        path.closeSubpath()
    return path
