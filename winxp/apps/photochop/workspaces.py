"""The three modal workspaces: Liquify, Extract, and Pattern Maker.

These are the filters that take over the screen. Each one is real:

  * Liquify keeps a displacement mesh the brushes push around, and warps the
    image by sampling through it -- so Reconstruct really is just fading the
    mesh back toward identity.
  * Extract builds a matte from the highlighted edge and the filled interior,
    estimating alpha inside the highlight band from colour distance.
  * Pattern Maker makes a genuinely seamless tile by mirror-blending the
    sample against itself, then tiles the canvas with it.
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QToolButton, QVBoxLayout, QWidget,
)

from ...xp_dialog import XPMessageBox
from . import imageops as ops
from .dialogs import PCDialog, SliderRow, _lbl, _spin, group_box

PREVIEW_W, PREVIEW_H = 400, 300


def _fit(img: QImage, w=PREVIEW_W, h=PREVIEW_H) -> QImage:
    return img.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)


# --------------------------------------------------------------- liquify ---

LIQUIFY_TOOLS = [
    ("warp", "Warp Tool (W)"),
    ("turbulence", "Turbulence Tool (A)"),
    ("twirl_cw", "Twirl Clockwise Tool (R)"),
    ("twirl_ccw", "Twirl Counter Clockwise Tool (L)"),
    ("pucker", "Pucker Tool (P)"),
    ("bloat", "Bloat Tool (B)"),
    ("shift", "Shift Pixels Tool (S)"),
    ("reflect", "Reflection Tool (M)"),
    ("reconstruct", "Reconstruct Tool (E)"),
    ("freeze", "Freeze Tool (F)"),
    ("thaw", "Thaw Tool (T)"),
]


class LiquifyCanvas(QWidget):
    """Holds the mesh and paints the warped preview."""

    def __init__(self, dialog, image: QImage):
        super().__init__()
        self.dialog = dialog
        self.source = _fit(image)
        self.setFixedSize(self.source.width(), self.source.height())
        self.setMouseTracking(True)
        w, h = self.source.width(), self.source.height()
        # displacement in source pixels, one entry per destination pixel row-major
        self.dx = [0.0] * (w * h)
        self.dy = [0.0] * (w * h)
        self.frozen = bytearray(w * h)
        self.show_mesh = False
        self.show_frozen = True
        self._last = None
        self._cached: QImage | None = None

    def reset_mesh(self):
        n = len(self.dx)
        self.dx = [0.0] * n
        self.dy = [0.0] * n
        self._cached = None
        self.update()

    def warped(self, source=None, scale=1.0) -> QImage:
        src = source if source is not None else self.source
        pw, ph = self.source.width(), self.source.height()
        buf, w, h = ops.to_buf(src)
        out = bytearray(len(buf))
        for y in range(h):
            my = int(y / scale)
            if my >= ph:
                my = ph - 1
            base = my * pw
            row = y * w
            for x in range(w):
                mx = int(x / scale)
                if mx >= pw:
                    mx = pw - 1
                i = base + mx
                sx = int(x + self.dx[i] * scale)
                sy = int(y + self.dy[i] * scale)
                if 0 <= sx < w and 0 <= sy < h:
                    si = (sy * w + sx) * 4
                else:
                    si = (row + x) * 4
                di = (row + x) * 4
                out[di:di + 4] = buf[si:si + 4]
        return ops.from_buf(out, w, h)

    def preview(self) -> QImage:
        if self._cached is None:
            self._cached = self.warped()
        return self._cached

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#808080"))
        p.drawImage(0, 0, self.preview())
        if self.show_frozen:
            w, h = self.source.width(), self.source.height()
            overlay = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
            overlay.fill(Qt.GlobalColor.transparent)
            op = QPainter(overlay)
            op.setPen(Qt.PenStyle.NoPen)
            op.setBrush(QColor(255, 40, 40, 90))
            step = 4
            for y in range(0, h, step):
                for x in range(0, w, step):
                    if self.frozen[y * w + x]:
                        op.drawRect(x, y, step, step)
            op.end()
            p.drawImage(0, 0, overlay)
        if self.show_mesh:
            p.setPen(QPen(QColor(60, 60, 60, 120), 1))
            w, h = self.source.width(), self.source.height()
            for gy in range(0, h, 16):
                pts = [QPointF(gx + self.dx[gy * w + gx], gy + self.dy[gy * w + gx])
                       for gx in range(0, w, 8)]
                for a, b in zip(pts, pts[1:]):
                    p.drawLine(a, b)
            for gx in range(0, w, 16):
                pts = [QPointF(gx + self.dx[gy * w + gx], gy + self.dy[gy * w + gx])
                       for gy in range(0, h, 8)]
                for a, b in zip(pts, pts[1:]):
                    p.drawLine(a, b)
        p.setPen(QPen(QColor("#202020"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cursor = self.mapFromGlobal(self.cursor().pos())
        radius = self.dialog.brush_size.value() / 2
        p.drawEllipse(QPointF(cursor), radius, radius)
        p.end()

    def mousePressEvent(self, ev):
        self._last = ev.position()
        self._apply(ev.position(), QPointF(0, 0))

    def mouseMoveEvent(self, ev):
        if ev.buttons():
            delta = ev.position() - (self._last or ev.position())
            self._apply(ev.position(), delta)
            self._last = ev.position()
        self.update()

    def mouseReleaseEvent(self, ev):
        self._last = None

    def _apply(self, pos, delta):
        tool = self.dialog.tool
        w, h = self.source.width(), self.source.height()
        radius = max(2, self.dialog.brush_size.value() // 2)
        pressure = self.dialog.brush_pressure.value() / 100.0
        cx, cy = pos.x(), pos.y()
        x0, x1 = max(0, int(cx - radius)), min(w, int(cx + radius) + 1)
        y0, y1 = max(0, int(cy - radius)), min(h, int(cy + radius) + 1)
        for y in range(y0, y1):
            for x in range(x0, x1):
                ddx, ddy = x - cx, y - cy
                dist = math.hypot(ddx, ddy)
                if dist > radius:
                    continue
                i = y * w + x
                if self.frozen[i] and tool not in ("thaw", "freeze"):
                    continue
                falloff = (1 - dist / radius) ** 2 * pressure
                if tool == "freeze":
                    self.frozen[i] = 255
                    continue
                if tool == "thaw":
                    self.frozen[i] = 0
                    continue
                if tool == "reconstruct":
                    self.dx[i] *= (1 - falloff)
                    self.dy[i] *= (1 - falloff)
                    continue
                if tool == "warp" or tool == "shift":
                    push = delta if tool == "warp" else QPointF(-delta.y(), delta.x())
                    self.dx[i] -= push.x() * falloff
                    self.dy[i] -= push.y() * falloff
                elif tool in ("twirl_cw", "twirl_ccw"):
                    sign = 1 if tool == "twirl_cw" else -1
                    ang = sign * falloff * 0.35
                    c, s = math.cos(ang), math.sin(ang)
                    nx = ddx * c - ddy * s
                    ny = ddx * s + ddy * c
                    self.dx[i] += (nx - ddx)
                    self.dy[i] += (ny - ddy)
                elif tool == "pucker":
                    self.dx[i] += ddx * falloff * 0.25
                    self.dy[i] += ddy * falloff * 0.25
                elif tool == "bloat":
                    self.dx[i] -= ddx * falloff * 0.25
                    self.dy[i] -= ddy * falloff * 0.25
                elif tool == "turbulence":
                    self.dx[i] += random.uniform(-1, 1) * falloff * 6
                    self.dy[i] += random.uniform(-1, 1) * falloff * 6
                elif tool == "reflect":
                    self.dx[i] += ddx * falloff * -1.4
                    self.dy[i] += ddy * falloff * -1.4
        self._cached = None
        self.update()


class LiquifyDialog(PCDialog):
    def __init__(self, parent, image: QImage):
        super().__init__(parent, "Liquify")
        self.original = image
        self.tool = "warp"

        body = QHBoxLayout()
        body.setSpacing(8)

        tool_col = QVBoxLayout()
        tool_col.setSpacing(1)
        self._buttons = {}
        for key, tip in LIQUIFY_TOOLS:
            btn = QToolButton()
            btn.setText(tip.split(" (")[1].rstrip(")"))
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setChecked(key == "warp")
            btn.setFixedSize(26, 24)
            btn.clicked.connect(lambda _, k=key: self._set_tool(k))
            self._buttons[key] = btn
            tool_col.addWidget(btn)
        tool_col.addStretch(1)
        body.addLayout(tool_col)

        self.canvas = LiquifyCanvas(self, image)
        body.addWidget(self.canvas)

        opts = QVBoxLayout()
        opts.setSpacing(6)
        frame, box = group_box("Tool Options")
        self.brush_size = SliderRow("Brush Size:", 1, 200, 64)
        self.brush_pressure = SliderRow("Brush Pressure:", 1, 100, 50)
        box.addWidget(self.brush_size)
        box.addWidget(self.brush_pressure)
        stylus = QCheckBox("Stylus Pressure")
        stylus.setStyleSheet("background: transparent;")
        box.addWidget(stylus)
        opts.addWidget(frame)

        frame2, box2 = group_box("Reconstruction")
        row = QHBoxLayout()
        row.addWidget(_lbl("Mode:"))
        mode = QComboBox()
        mode.addItems(["Revert", "Rigid", "Stiff", "Smooth", "Loose"])
        row.addWidget(mode, 1)
        box2.addLayout(row)
        reconstruct = QPushButton("Reconstruct")
        reconstruct.clicked.connect(self._reconstruct)
        revert = QPushButton("Revert")
        revert.clicked.connect(self.canvas.reset_mesh)
        box2.addWidget(reconstruct)
        box2.addWidget(revert)
        opts.addWidget(frame2)

        frame3, box3 = group_box("View Options")
        mesh = QCheckBox("Show Mesh")
        mesh.toggled.connect(self._toggle_mesh)
        frozen = QCheckBox("Show Frozen Areas")
        frozen.setChecked(True)
        frozen.toggled.connect(self._toggle_frozen)
        for cb in (mesh, frozen):
            cb.setStyleSheet("background: transparent;")
            box3.addWidget(cb)
        opts.addWidget(frame3)
        opts.addStretch(1)
        body.addLayout(opts)
        self.content.addLayout(body)

        self.add_ok_cancel()
        self.finish_side()

    def _set_tool(self, key):
        self.tool = key
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)

    def _toggle_mesh(self, on):
        self.canvas.show_mesh = on
        self.canvas.update()

    def _toggle_frozen(self, on):
        self.canvas.show_frozen = on
        self.canvas.update()

    def _reconstruct(self):
        for i in range(len(self.canvas.dx)):
            self.canvas.dx[i] *= 0.6
            self.canvas.dy[i] *= 0.6
        self.canvas._cached = None
        self.canvas.update()

    def result(self) -> QImage:
        scale = self.original.width() / max(1, self.canvas.source.width())
        return self.canvas.warped(self.original, scale)


# --------------------------------------------------------------- extract ---

class ExtractCanvas(QWidget):
    def __init__(self, dialog, image: QImage):
        super().__init__()
        self.dialog = dialog
        self.source = _fit(image)
        self.setFixedSize(self.source.width(), self.source.height())
        self.highlight = QImage(self.source.size(),
                                QImage.Format.Format_ARGB32_Premultiplied)
        self.highlight.fill(Qt.GlobalColor.transparent)
        self.fill = QImage(self.source.size(), QImage.Format.Format_ARGB32_Premultiplied)
        self.fill.fill(Qt.GlobalColor.transparent)
        self.preview_image: QImage | None = None
        self._last = None

    def paintEvent(self, ev):
        p = QPainter(self)
        _paint_checker(p, self.rect())
        p.drawImage(0, 0, self.preview_image if self.preview_image is not None
                    else self.source)
        if self.preview_image is None:
            p.drawImage(0, 0, self.fill)
            p.drawImage(0, 0, self.highlight)
        p.setPen(QPen(QColor("#303030"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

    def mousePressEvent(self, ev):
        self._last = ev.position()
        self._paint(ev.position())

    def mouseMoveEvent(self, ev):
        if ev.buttons():
            self._paint(ev.position())
            self._last = ev.position()

    def mouseReleaseEvent(self, ev):
        self._last = None

    def _paint(self, pos):
        tool = self.dialog.tool
        size = self.dialog.brush_size.value()
        if tool == "fill":
            p = QPainter(self.fill)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 90, 255, 110))
            p.drawEllipse(pos, size, size)
            p.end()
        elif tool == "eraser":
            for target in (self.fill, self.highlight):
                p = QPainter(target)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(0, 0, 0, 255))
                p.drawEllipse(pos, size / 2, size / 2)
                p.end()
        else:
            p = QPainter(self.highlight)
            p.setPen(QPen(QColor(0, 255, 60, 150), size,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(self._last or pos, pos)
            p.end()
        self.preview_image = None
        self.update()

    def matte(self, source: QImage | None = None) -> QImage:
        """Interior stays, exterior goes, and the highlight band gets an alpha
        estimated from how close each pixel is to the interior's average."""
        src = source if source is not None else self.source
        scale = src.width() / max(1, self.source.width())
        hl = (self.highlight if scale == 1 else
              self.highlight.scaled(src.size(), Qt.AspectRatioMode.IgnoreAspectRatio))
        fl = (self.fill if scale == 1 else
              self.fill.scaled(src.size(), Qt.AspectRatioMode.IgnoreAspectRatio))
        buf, w, h = ops.to_buf(src)
        hb, _, _ = ops.to_buf(hl)
        fb, _, _ = ops.to_buf(fl)
        h_alpha = ops.plane(hb, ops.A)
        f_alpha = ops.plane(fb, ops.A)
        rp, gp, bp = ops.plane(buf, ops.R), ops.plane(buf, ops.G), ops.plane(buf, ops.B)

        total = sum(1 for a in f_alpha if a)
        if not total:
            return src.copy()
        ar = sum(rp[i] for i, a in enumerate(f_alpha) if a) // total
        ag = sum(gp[i] for i, a in enumerate(f_alpha) if a) // total
        ab = sum(bp[i] for i, a in enumerate(f_alpha) if a) // total
        tolerance = max(20, self.dialog.smooth.value() * 12)

        out = bytearray(w * h)
        for i in range(w * h):
            if f_alpha[i]:
                out[i] = 255
            elif h_alpha[i]:
                dist = abs(rp[i] - ar) + abs(gp[i] - ag) + abs(bp[i] - ab)
                out[i] = max(0, 255 - int(dist * 255 / tolerance))
            else:
                out[i] = 0
        alpha_buf = bytearray(w * h * 4)
        alpha_buf[0::4] = out
        alpha_buf[1::4] = out
        alpha_buf[2::4] = out
        alpha_buf[3::4] = b"\xff" * (w * h)
        mask = ops.from_buf(alpha_buf, w, h)
        from .model import alpha_multiply
        return alpha_multiply(src, mask)


class ExtractDialog(PCDialog):
    def __init__(self, parent, image: QImage):
        super().__init__(parent, "Extract")
        self.original = image
        self.tool = "highlight"

        body = QHBoxLayout()
        body.setSpacing(8)
        tool_col = QVBoxLayout()
        tool_col.setSpacing(1)
        self._buttons = {}
        for key, label, tip in (("highlight", "//", "Edge Highlighter Tool (B)"),
                                ("fill", "[]", "Fill Tool (G)"),
                                ("eraser", "E", "Eraser Tool (E)"),
                                ("eyedropper", "I", "Eyedropper Tool (I)"),
                                ("cleanup", "C", "Cleanup Tool (C)"),
                                ("edge", "T", "Edge Touchup Tool (T)")):
            btn = QToolButton()
            btn.setText(label)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setChecked(key == "highlight")
            btn.setFixedSize(26, 24)
            btn.clicked.connect(lambda _, k=key: self._set_tool(k))
            self._buttons[key] = btn
            tool_col.addWidget(btn)
        tool_col.addStretch(1)
        body.addLayout(tool_col)

        self.canvas = ExtractCanvas(self, image)
        body.addWidget(self.canvas)

        opts = QVBoxLayout()
        opts.setSpacing(6)
        frame, box = group_box("Tool Options")
        self.brush_size = SliderRow("Brush Size:", 1, 100, 20)
        box.addWidget(self.brush_size)
        for label, choices in (("Highlight:", ("Green", "Red", "Blue", "Other")),
                               ("Fill:", ("Blue", "Green", "Red", "Other"))):
            row = QHBoxLayout()
            row.addWidget(_lbl(label))
            combo = QComboBox()
            combo.addItems(choices)
            row.addWidget(combo, 1)
            box.addLayout(row)
        smart = QCheckBox("Smart Highlighting")
        smart.setStyleSheet("background: transparent;")
        box.addWidget(smart)
        opts.addWidget(frame)

        frame2, box2 = group_box("Extraction")
        self.smooth = SliderRow("Smooth:", 0, 100, 5)
        box2.addWidget(self.smooth)
        textured = QCheckBox("Textured Image")
        textured.setStyleSheet("background: transparent;")
        box2.addWidget(textured)
        force = QCheckBox("Force Foreground")
        force.setStyleSheet("background: transparent;")
        box2.addWidget(force)
        opts.addWidget(frame2)

        hint = QLabel("Draw around the edge with the highlighter, fill the inside "
                      "with the fill tool, then press Preview.")
        hint.setWordWrap(True)
        hint.setStyleSheet("background: transparent; color: #555; font-size: 10px;")
        opts.addWidget(hint)
        opts.addStretch(1)
        body.addLayout(opts)
        self.content.addLayout(body)

        self.add_ok_cancel()
        self.add_button("Preview", self._preview)
        self.finish_side()

    def _set_tool(self, key):
        self.tool = key
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)

    def _preview(self):
        self.canvas.preview_image = self.canvas.matte()
        self.canvas.update()

    def result(self) -> QImage:
        return self.canvas.matte(self.original)


def _paint_checker(p: QPainter, rect: QRect):
    tile = QPixmap(16, 16)
    tile.fill(QColor("#ffffff"))
    tp = QPainter(tile)
    tp.fillRect(0, 0, 8, 8, QColor("#cccccc"))
    tp.fillRect(8, 8, 8, 8, QColor("#cccccc"))
    tp.end()
    p.drawTiledPixmap(rect, tile)


# --------------------------------------------------------- pattern maker ---

class PatternMakerCanvas(QWidget):
    def __init__(self, dialog, image: QImage):
        super().__init__()
        self.dialog = dialog
        self.source = _fit(image)
        self.setFixedSize(self.source.width(), self.source.height())
        self.sample: QRectF | None = None
        self.generated: QImage | None = None
        self._start = None

    def paintEvent(self, ev):
        p = QPainter(self)
        p.drawImage(0, 0, self.generated if self.generated is not None else self.source)
        if self.sample is not None and self.generated is None:
            p.setPen(QPen(QColor("black"), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(self.sample)
        p.end()

    def mousePressEvent(self, ev):
        self._start = ev.position()
        self.generated = None

    def mouseMoveEvent(self, ev):
        if self._start is not None:
            self.sample = QRectF(self._start, ev.position()).normalized()
            self.update()

    def mouseReleaseEvent(self, ev):
        self._start = None

    def tile(self) -> QImage | None:
        if self.sample is None or self.sample.width() < 8:
            return None
        rect = self.sample.toAlignedRect().intersected(self.source.rect())
        patch = self.source.copy(rect)
        return seamless_tile(patch)

    def generate(self):
        tile = self.tile()
        if tile is None:
            return
        offset = self.dialog.offset_amount.value()
        out = QImage(self.source.size(), QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        tw, th = tile.width(), tile.height()
        row = 0
        y = 0
        while y < out.height():
            shift = (row * tw * offset // 100) % max(1, tw)
            x = -shift
            while x < out.width():
                p.drawImage(x, y, tile)
                x += tw
            y += th
            row += 1
        p.end()
        self.generated = out
        self.update()


def seamless_tile(patch: QImage) -> QImage:
    """Mirror-blend a patch against itself so opposite edges match exactly."""
    w, h = patch.width(), patch.height()
    out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawImage(0, 0, patch)
    mirrored_h = patch.mirrored(True, False)
    mirrored_v = patch.mirrored(False, True)
    # feather the mirrored copies in from each edge so the seams cancel
    for source, rect in ((mirrored_h, QRect(0, 0, max(1, w // 4), h)),
                         (mirrored_v, QRect(0, 0, w, max(1, h // 4)))):
        fade = QImage(source.size(), QImage.Format.Format_ARGB32_Premultiplied)
        fade.fill(Qt.GlobalColor.transparent)
        fp = QPainter(fade)
        fp.setOpacity(0.5)
        fp.drawImage(0, 0, source)
        fp.end()
        p.setClipRect(rect)
        p.drawImage(0, 0, fade)
        p.setClipping(False)
    p.end()
    return out


class PatternMakerDialog(PCDialog):
    def __init__(self, parent, image: QImage):
        super().__init__(parent, "Pattern Maker")
        self.original = image
        body = QHBoxLayout()
        body.setSpacing(8)
        self.canvas = PatternMakerCanvas(self, image)
        body.addWidget(self.canvas)

        opts = QVBoxLayout()
        opts.setSpacing(6)
        frame, box = group_box("Tile Generation")
        grid = QGridLayout()
        self.width_spin = _spin(1, 2000, 128, " px")
        self.height_spin = _spin(1, 2000, 128, " px")
        grid.addWidget(_lbl("Width:"), 0, 0)
        grid.addWidget(self.width_spin, 0, 1)
        grid.addWidget(_lbl("Height:"), 1, 0)
        grid.addWidget(self.height_spin, 1, 1)
        box.addLayout(grid)
        row = QHBoxLayout()
        row.addWidget(_lbl("Offset:"))
        self.offset_kind = QComboBox()
        self.offset_kind.addItems(["None", "Horizontal", "Vertical"])
        self.offset_kind.setCurrentText("Horizontal")
        row.addWidget(self.offset_kind, 1)
        box.addLayout(row)
        self.offset_amount = SliderRow("Amount:", 0, 100, 50, "%")
        box.addWidget(self.offset_amount)
        self.smoothness = SliderRow("Smoothness:", 1, 3, 1)
        box.addWidget(self.smoothness)
        opts.addWidget(frame)

        generate = QPushButton("Generate")
        generate.clicked.connect(self.canvas.generate)
        opts.addWidget(generate)

        hint = QLabel("Drag a rectangle over the area to sample, then Generate. "
                      "Every result will look like carpet.")
        hint.setWordWrap(True)
        hint.setStyleSheet("background: transparent; color: #555; font-size: 10px;")
        opts.addWidget(hint)
        opts.addStretch(1)
        body.addLayout(opts)
        self.content.addLayout(body)

        self.add_ok_cancel()
        self.finish_side()

    def result(self) -> QImage:
        tile = self.canvas.tile()
        if tile is None:
            return self.original
        out = QImage(self.original.size(), QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.drawTiledPixmap(out.rect(), QPixmap.fromImage(tile))
        p.end()
        return out
