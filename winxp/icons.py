"""Procedurally-drawn XP-style icons (no external image assets needed)."""
from __future__ import annotations

import os

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QPolygon, QPolygonF,
)
from PyQt6.QtCore import QPoint, QPointF

_CACHE: dict[tuple, QIcon] = {}


def _pix(size=32):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def icon(name: str, size: int = 32) -> QIcon:
    key = (name, size)
    if key in _CACHE:
        return _CACHE[key]
    pm = _draw(name, size)
    ic = QIcon(pm)
    _CACHE[key] = ic
    return ic


def _grad(rect, c1, c2, vertical=True):
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft() if vertical else rect.topRight())
    g.setColorAt(0, QColor(c1))
    g.setColorAt(1, QColor(c2))
    return QBrush(g)


def _draw(name: str, size: int) -> QPixmap:
    pm = _pix(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size

    if name == "folder":
        _draw_folder(p, s)
    elif name == "folder_open":
        _draw_folder(p, s, open_=True)
    elif name in ("my_computer",):
        _draw_computer(p, s)
    elif name == "my_documents":
        _draw_docfolder(p, s)
    elif name == "recycle_bin":
        _draw_recycle(p, s, full=False)
    elif name == "recycle_bin_full":
        _draw_recycle(p, s, full=True)
    elif name in ("text_file", "notepad"):
        _draw_textfile(p, s, notepad=(name == "notepad"))
    elif name == "wordpad":
        _draw_textfile(p, s, notepad=False, blue=True)
    elif name == "mword":
        _draw_mword(p, s)
    elif name == "ie":
        _draw_ie(p, s)
    elif name == "minesweeper":
        _draw_minesweeper(p, s)
    elif name == "calculator":
        _draw_calculator(p, s)
    elif name == "control_panel":
        _draw_control_panel(p, s)
    elif name == "paint":
        _draw_paint(p, s)
    elif name == "photochop":
        _draw_photochop(p, s)
    elif name == "run":
        _draw_run(p, s)
    elif name == "shutdown":
        _draw_shutdown(p, s)
    elif name == "logoff":
        _draw_logoff(p, s)
    elif name == "task_manager":
        _draw_task_manager(p, s)
    elif name == "vscode":
        _draw_vscode(p, s)
    elif name == "cp_display":
        _draw_cp_display(p, s)
    elif name == "cp_appearance":
        _draw_cp_appearance(p, s)
    elif name == "cp_programs":
        _draw_cp_programs(p, s)
    elif name == "cp_screensaver":
        _draw_cp_screensaver(p, s)
    elif name == "cp_system":
        _draw_cp_system(p, s)
    elif name == "cp_folder_options":
        _draw_cp_folder_options(p, s)
    elif name == "msg_warning":
        _draw_msg_warning(p, s)
    elif name == "msg_error":
        _draw_msg_error(p, s)
    elif name == "msg_info":
        _draw_msg_info(p, s)
    elif name == "msg_question":
        _draw_msg_question(p, s)
    elif name == "bitmap_file":
        _draw_bitmap_file(p, s)
    elif name == "audio_file":
        _draw_audio_file(p, s)
    elif name == "video_file":
        _draw_video_file(p, s)
    elif name == "wmp":
        _draw_wmp(p, s)
    elif name == "volume":
        _draw_volume(p, s)
    elif name == "volume_mute":
        _draw_volume(p, s, muted=True)
    elif name == "tool_pencil":
        _draw_tool_pencil(p, s)
    elif name == "tool_brush":
        _draw_tool_brush(p, s)
    elif name == "tool_eraser":
        _draw_tool_eraser(p, s)
    elif name == "tool_fill":
        _draw_tool_fill(p, s)
    elif name == "tool_eyedropper":
        _draw_tool_eyedropper(p, s)
    elif name == "tool_line":
        _draw_tool_line(p, s)
    elif name == "tool_rect":
        _draw_tool_rect(p, s)
    elif name == "tool_ellipse":
        _draw_tool_ellipse(p, s)
    elif name == "tool_text":
        _draw_tool_text(p, s)
    elif name == "tool_select":
        _draw_tool_select(p, s)
    elif name == "allprograms":
        _draw_allprograms(p, s)
    elif name == "xp_flag":
        _draw_xp_flag(p, s)
    elif name in _SHELL_DRAWERS:
        _SHELL_DRAWERS[name](p, s)
    else:
        p.setBrush(QColor("#cccccc"))
        p.drawRect(2, 2, s - 4, s - 4)
    p.end()
    return pm


def _draw_folder(p, s, open_=False):
    body = QRectF(s * 0.06, s * 0.32, s * 0.88, s * 0.55)
    tab = QRectF(s * 0.06, s * 0.20, s * 0.42, s * 0.16)
    p.setPen(QPen(QColor("#8a6d1f"), 1))
    p.setBrush(_grad(body, "#ffe28a", "#ffb92e"))
    p.drawRoundedRect(tab, 2, 2)
    p.setBrush(_grad(body, "#ffd35c", "#ffa713"))
    p.drawRoundedRect(body, 2, 2)
    if open_:
        front = QRectF(s * 0.02, s * 0.46, s * 0.96, s * 0.42)
        p.setBrush(_grad(front, "#fff0c0", "#ffc957"))
        p.drawRoundedRect(front, 2, 2)


def _draw_docfolder(p, s):
    _draw_folder(p, s)
    p.setBrush(QColor("white"))
    p.setPen(QPen(QColor("#557"), 1))
    r = QRectF(s * 0.32, s * 0.10, s * 0.4, s * 0.32)
    p.drawRect(r)
    for i in range(3):
        y = r.top() + 5 + i * 5
        p.drawLine(QPoint(int(r.left() + 4), int(y)), QPoint(int(r.right() - 4), int(y)))


def _draw_computer(p, s):
    mon = QRectF(s * 0.10, s * 0.10, s * 0.80, s * 0.50)
    p.setPen(QPen(QColor("#2a3a55"), 1))
    p.setBrush(_grad(mon, "#c9d6ea", "#7f97bd"))
    p.drawRoundedRect(mon, 3, 3)
    screen = mon.adjusted(s * 0.08, s * 0.08, -s * 0.08, -s * 0.12)
    p.setBrush(QColor("#123a7a"))
    p.drawRect(screen)
    base = QRectF(s * 0.30, s * 0.62, s * 0.40, s * 0.08)
    p.setBrush(QColor("#8493ab"))
    p.drawRect(base)
    foot = QRectF(s * 0.16, s * 0.72, s * 0.68, s * 0.10)
    p.setBrush(_grad(foot, "#c9d6ea", "#7f97bd"))
    p.drawRoundedRect(foot, 2, 2)


def _draw_recycle(p, s, full):
    body = QRectF(s * 0.24, s * 0.30, s * 0.52, s * 0.58)
    p.setPen(QPen(QColor("#2a5a2a"), 1))
    p.setBrush(_grad(body, "#eafbea", "#a9d9a4") if not full else _grad(body, "#dff0d0", "#8fc98a"))
    p.drawRoundedRect(body, 3, 3)
    lid = QRectF(s * 0.16, s * 0.20, s * 0.68, s * 0.12)
    p.setBrush(QColor("#6fae63"))
    p.drawRoundedRect(lid, 2, 2)
    p.setPen(QPen(QColor("#2a5a2a"), 1))
    for i in range(3):
        x = body.left() + body.width() * (i + 1) / 4
        p.drawLine(QPoint(int(x), int(body.top() + 6)), QPoint(int(x), int(body.bottom() - 4)))
    if full:
        p.setBrush(QColor("#ffffff"))
        p.drawRect(QRectF(s * 0.40, s * 0.10, s * 0.20, s * 0.14))


def _draw_textfile(p, s, notepad=False, blue=False):
    r = QRectF(s * 0.20, s * 0.06, s * 0.60, s * 0.86)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("white") if not blue else QColor("#eef3ff"))
    poly = QPolygon([
        QPoint(int(r.left()), int(r.top())),
        QPoint(int(r.right() - s * 0.14), int(r.top())),
        QPoint(int(r.right()), int(r.top() + s * 0.14)),
        QPoint(int(r.right()), int(r.bottom())),
        QPoint(int(r.left()), int(r.bottom())),
    ])
    p.drawPolygon(poly)
    p.setBrush(QColor("#c8c8c8") if not blue else QColor("#3355bb"))
    p.drawPolygon(QPolygon([
        QPoint(int(r.right() - s * 0.14), int(r.top())),
        QPoint(int(r.right()), int(r.top() + s * 0.14)),
        QPoint(int(r.right() - s * 0.14), int(r.top() + s * 0.14)),
    ]))
    p.setPen(QPen(QColor("#334") if not blue else QColor("#224"), 1))
    for i in range(4):
        y = r.top() + s * 0.28 + i * s * 0.13
        p.drawLine(QPoint(int(r.left() + 5), int(y)), QPoint(int(r.right() - 5), int(y)))


def _draw_mword(p, s):
    """Word 2003's icon: a white sheet with the blue W and the blue spine."""
    page = QRectF(s * 0.16, s * 0.06, s * 0.70, s * 0.88)
    fold = s * 0.22
    path = QPainterPath()
    path.moveTo(page.left(), page.top())
    path.lineTo(page.right() - fold, page.top())
    path.lineTo(page.right(), page.top() + fold)
    path.lineTo(page.right(), page.bottom())
    path.lineTo(page.left(), page.bottom())
    path.closeSubpath()
    p.setPen(QPen(QColor("#7f8c9b"), max(1.0, s * 0.03)))
    p.setBrush(QColor("#ffffff"))
    p.drawPath(path)
    p.setPen(QPen(QColor("#7f8c9b"), max(1.0, s * 0.025)))
    p.drawPolyline(QPolygonF([
        QPointF(page.right() - fold, page.top()),
        QPointF(page.right() - fold, page.top() + fold),
        QPointF(page.right(), page.top() + fold)]))

    # ruled lines behind the letter
    p.setPen(QPen(QColor("#b9c6d6"), max(1.0, s * 0.025)))
    for i in range(3):
        y = page.top() + s * (0.52 + i * 0.13)
        p.drawLine(QPointF(page.left() + s * 0.09, y),
                   QPointF(page.right() - s * 0.09, y))

    # the blue spine and the W
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_grad(QRectF(0, 0, 1, s), "#4a7fc1", "#22508f"))
    p.drawRect(QRectF(s * 0.04, s * 0.16, s * 0.30, s * 0.68))
    f = p.font()
    f.setBold(True)
    f.setPixelSize(max(6, int(s * 0.42)))
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(QRectF(s * 0.04, s * 0.16, s * 0.30, s * 0.68),
               Qt.AlignmentFlag.AlignCenter, "W")


def _draw_photochop(p, s):
    path = os.path.join(os.path.dirname(__file__), "assets", "MonaLisa.jpg")
    img = QImage(path)
    rect = QRectF(1, 1, s - 2, s - 2)
    clip = QPainterPath()
    clip.addRoundedRect(rect, s * 0.12, s * 0.12)
    if img.isNull():
        p.setPen(QPen(QColor("#5a4326"), 1))
        p.setBrush(QColor("#8a6a4a"))
        p.drawRoundedRect(rect, s * 0.12, s * 0.12)
        return
    side = min(img.width(), img.height())
    x0 = (img.width() - side) // 2
    y0 = (img.height() - side) // 2
    cropped = img.copy(x0, y0, side, side).scaled(
        s, s, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    p.save()
    p.setClipPath(clip)
    p.drawImage(0, 0, cropped)
    p.restore()
    p.setPen(QPen(QColor("#5a4326"), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(rect, s * 0.12, s * 0.12)


def _draw_ie(p, s):
    p.setPen(QPen(QColor("#1a3d8f"), s * 0.08))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88), 30 * 16, 300 * 16)
    p.setPen(QPen(QColor("#e8b800"), s * 0.10))
    p.drawArc(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72), 200 * 16, 150 * 16)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#f5c400"))
    p.drawEllipse(QRectF(s * 0.50, s * 0.10, s * 0.22, s * 0.22))


def _draw_minesweeper(p, s):
    r = QRectF(s * 0.08, s * 0.08, s * 0.84, s * 0.84)
    p.setPen(QPen(QColor("#808080"), 1))
    p.setBrush(QColor("#c0c0c0"))
    p.drawRect(r)
    p.setBrush(QColor("black"))
    p.setPen(Qt.PenStyle.NoPen)
    cx, cy = s * 0.5, s * 0.5
    rad = s * 0.16
    p.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))
    p.setPen(QPen(QColor("black"), max(1, int(s * 0.05))))
    for ang in range(0, 360, 45):
        import math
        rx = cx + math.cos(math.radians(ang)) * rad * 1.7
        ry = cy + math.sin(math.radians(ang)) * rad * 1.7
        p.drawLine(QPoint(int(cx), int(cy)), QPoint(int(rx), int(ry)))
    p.setBrush(QColor(255, 255, 255, 180))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(cx - rad * 0.5, cy - rad * 0.7, rad * 0.5, rad * 0.4))


def _draw_calculator(p, s):
    r = QRectF(s * 0.16, s * 0.06, s * 0.68, s * 0.88)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("#e4e4e4"))
    p.drawRoundedRect(r, 3, 3)
    screen = QRectF(r.left() + 4, r.top() + 5, r.width() - 8, s * 0.16)
    p.setBrush(QColor("#c9e2b3"))
    p.drawRect(screen)
    p.setBrush(QColor("#5577cc"))
    btn_top = screen.bottom() + 4
    bw = (r.width() - 10) / 3
    bh = s * 0.11
    for row in range(4):
        for col in range(3):
            bx = r.left() + 4 + col * (bw + 1)
            by = btn_top + row * (bh + 2)
            p.drawRoundedRect(QRectF(bx, by, bw, bh), 1, 1)


def _draw_vscode(p, s):
    r = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_grad(r, "#1f9cf0", "#0058c8"))
    p.drawRoundedRect(r, s * 0.16, s * 0.16)
    p.setPen(QPen(QColor("white"), max(1, s * 0.09), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    # "<" chevron
    p.drawPolyline(QPolygon([
        QPoint(int(s * 0.46), int(s * 0.28)),
        QPoint(int(s * 0.26), int(s * 0.5)),
        QPoint(int(s * 0.46), int(s * 0.72)),
    ]))
    # ">" chevron
    p.drawPolyline(QPolygon([
        QPoint(int(s * 0.54), int(s * 0.28)),
        QPoint(int(s * 0.74), int(s * 0.5)),
        QPoint(int(s * 0.54), int(s * 0.72)),
    ]))


def _draw_cp_display(p, s):
    r = QRectF(s * 0.08, s * 0.10, s * 0.84, s * 0.60)
    p.setPen(QPen(QColor("#444"), 1))
    p.setBrush(QColor("#2a2a2a"))
    p.drawRoundedRect(r, 3, 3)
    screen = r.adjusted(4, 4, -4, -4)
    p.setBrush(_grad(screen, "#3a6ea5", "#1a4a80"))
    p.drawRect(screen)
    p.setBrush(QColor("#888"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRect(QRectF(s * 0.42, r.bottom(), s * 0.16, s * 0.10))
    p.drawRoundedRect(QRectF(s * 0.22, r.bottom() + s * 0.08, s * 0.56, s * 0.08), 2, 2)


def _draw_cp_appearance(p, s):
    swatches = ["#e35c5c", "#5c9ee3", "#e3c95c", "#5ce38f"]
    half = s * 0.42
    for i, c in enumerate(swatches):
        cx = s * 0.08 + (i % 2) * half
        cy = s * 0.08 + (i // 2) * half
        p.setPen(QPen(QColor("#555"), 1))
        p.setBrush(QColor(c))
        p.drawRoundedRect(QRectF(cx, cy, half - s * 0.04, half - s * 0.04), 3, 3)


def _draw_cp_programs(p, s):
    r = QRectF(s * 0.14, s * 0.10, s * 0.72, s * 0.60)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(_grad(r, "#f0d878", "#c8a020"))
    p.drawRect(r)
    p.setPen(QPen(QColor("#8a6a10"), 1))
    p.drawLine(int(r.left()), int(r.top() + r.height() / 2), int(r.right()), int(r.top() + r.height() / 2))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3fa129"))
    cx, cy, rad = s * 0.5, s * 0.82, s * 0.14
    p.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))
    p.setPen(QPen(QColor("white"), max(1, s * 0.045)))
    p.drawLine(int(cx - rad * 0.4), int(cy), int(cx + rad * 0.4), int(cy))
    p.drawLine(int(cx), int(cy - rad * 0.4), int(cx), int(cy + rad * 0.4))


def _draw_cp_screensaver(p, s):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#0a1a3a"))
    p.drawRoundedRect(QRectF(s * 0.06, s * 0.10, s * 0.88, s * 0.68), 4, 4)
    p.setBrush(QColor("#ffe89a"))
    moon_r = s * 0.16
    p.drawEllipse(QRectF(s * 0.6, s * 0.2, moon_r * 2, moon_r * 2))
    p.setBrush(QColor("#0a1a3a"))
    p.drawEllipse(QRectF(s * 0.66, s * 0.2, moon_r * 2, moon_r * 2))
    p.setBrush(QColor("white"))
    for x, y, r in [(0.18, 0.28, 0.02), (0.28, 0.45, 0.015), (0.14, 0.55, 0.018)]:
        p.drawEllipse(QRectF(s * x, s * y, s * r * 2, s * r * 2))


def _draw_cp_system(p, s):
    r = QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("#c8c4b0"))
    p.drawRoundedRect(r, 3, 3)
    inner = r.adjusted(s * 0.14, s * 0.14, -s * 0.14, -s * 0.14)
    p.setBrush(QColor("#3a9e5f"))
    p.drawRect(inner)
    p.setPen(QPen(QColor("#c8c4b0"), max(1, s * 0.035)))
    for i in range(3):
        off = inner.height() * (i + 1) / 4
        p.drawLine(int(r.left()), int(inner.top() + off), int(inner.left()), int(inner.top() + off))
        p.drawLine(int(inner.right()), int(inner.top() + off), int(r.right()), int(inner.top() + off))


def _draw_cp_folder_options(p, s):
    _draw_folder(p, s)
    cx, cy, rad = s * 0.72, s * 0.7, s * 0.22
    p.setPen(QPen(QColor("#444"), 1))
    p.setBrush(QColor("#e4e4e4"))
    p.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))
    p.setPen(QPen(QColor("#444"), max(1, s * 0.035)))
    p.drawLine(int(cx - rad * 0.4), int(cy), int(cx + rad * 0.4), int(cy))
    p.drawLine(int(cx - rad * 0.15), int(cy - rad * 0.35), int(cx - rad * 0.4), int(cy))
    p.drawLine(int(cx - rad * 0.15), int(cy + rad * 0.35), int(cx - rad * 0.4), int(cy))


def _draw_control_panel(p, s):
    r = QRectF(s * 0.10, s * 0.10, s * 0.80, s * 0.80)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("#dfe6f2"))
    p.drawRoundedRect(r, 4, 4)
    colors = ["#e35c5c", "#5c9ee3", "#5ce38f", "#e3c95c"]
    half = r.width() / 2
    for i, c in enumerate(colors):
        cx = r.left() + (i % 2) * half
        cy = r.top() + (i // 2) * half
        p.setBrush(QColor(c))
        p.drawRoundedRect(QRectF(cx + 3, cy + 3, half - 6, half - 6), 3, 3)


def _draw_paint(p, s):
    r = QRectF(s * 0.12, s * 0.12, s * 0.70, s * 0.70)
    p.setPen(QPen(QColor("#444"), 1))
    p.setBrush(QColor("white"))
    p.drawRect(r)
    colors = ["#e33", "#3a3", "#33e", "#ee3"]
    for i, c in enumerate(colors):
        p.setBrush(QColor(c))
        p.drawRect(QRectF(r.left() + (i % 2) * r.width() / 2, r.top() + (i // 2) * r.height() / 2,
                           r.width() / 2, r.height() / 2))
    p.setPen(QPen(QColor("#663311"), s * 0.06))
    p.drawLine(QPoint(int(r.right() - 2), int(r.top() + 2)), QPoint(int(s * 0.92), int(s * 0.08)))


def _draw_run(p, s):
    p.setPen(QPen(QColor("#333"), 1))
    p.setBrush(QColor("#f4f4f4"))
    p.drawRoundedRect(QRectF(s * 0.1, s * 0.35, s * 0.8, s * 0.35), 3, 3)


def _draw_shutdown(p, s):
    p.setPen(QPen(QColor("#c33"), s * 0.09))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(s * 0.15, s * 0.15, s * 0.7, s * 0.7), -60 * 16, 300 * 16)
    p.drawLine(QPoint(int(s * 0.5), int(s * 0.08)), QPoint(int(s * 0.5), int(s * 0.45)))


def _draw_msg_warning(p, s):
    poly = QPolygon([
        QPoint(int(s * 0.5), int(s * 0.06)),
        QPoint(int(s * 0.96), int(s * 0.90)),
        QPoint(int(s * 0.04), int(s * 0.90)),
    ])
    p.setPen(QPen(QColor("#8a6a00"), max(1, int(s * 0.03))))
    p.setBrush(_grad(QRectF(0, 0, s, s), "#ffe680", "#ffc61a"))
    p.drawPolygon(poly)
    p.setPen(QPen(QColor("#4a3a00"), max(2, int(s * 0.09))))
    p.drawLine(QPoint(int(s * 0.5), int(s * 0.38)), QPoint(int(s * 0.5), int(s * 0.64)))
    p.setBrush(QColor("#4a3a00"))
    p.setPen(Qt.PenStyle.NoPen)
    r = s * 0.05
    p.drawEllipse(QPoint(int(s * 0.5), int(s * 0.76)), int(r), int(r))


def _draw_msg_error(p, s):
    r = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)
    p.setPen(QPen(QColor("#8a1a1a"), 1))
    p.setBrush(_grad(r, "#ff7a6e", "#d81f1f"))
    p.drawEllipse(r)
    p.setPen(QPen(QColor("white"), max(2, int(s * 0.10))))
    inset = s * 0.30
    p.drawLine(QPoint(int(inset), int(inset)), QPoint(int(s - inset), int(s - inset)))
    p.drawLine(QPoint(int(s - inset), int(inset)), QPoint(int(inset), int(s - inset)))


def _draw_msg_info(p, s):
    r = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)
    p.setPen(QPen(QColor("#1a3d8a"), 1))
    p.setBrush(_grad(r, "#7fb3ff", "#1a5fd8"))
    p.drawEllipse(r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("white"))
    p.drawEllipse(QPoint(int(s * 0.5), int(s * 0.27)), int(s * 0.07), int(s * 0.07))
    p.drawRoundedRect(QRectF(s * 0.42, s * 0.42, s * 0.16, s * 0.38), s * 0.04, s * 0.04)


def _draw_msg_question(p, s):
    r = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)
    p.setPen(QPen(QColor("#1a3d8a"), 1))
    p.setBrush(_grad(r, "#7fb3ff", "#1a5fd8"))
    p.drawEllipse(r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("white"))
    f = p.font()
    f.setBold(True)
    f.setPixelSize(int(s * 0.55))
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "?")


def _draw_audio_file(p, s):
    r = QRectF(s * 0.20, s * 0.06, s * 0.60, s * 0.86)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("white"))
    poly = QPolygon([
        QPoint(int(r.left()), int(r.top())),
        QPoint(int(r.right() - s * 0.14), int(r.top())),
        QPoint(int(r.right()), int(r.top() + s * 0.14)),
        QPoint(int(r.right()), int(r.bottom())),
        QPoint(int(r.left()), int(r.bottom())),
    ])
    p.drawPolygon(poly)
    p.setBrush(QColor("#c8c8c8"))
    p.drawPolygon(QPolygon([
        QPoint(int(r.right() - s * 0.14), int(r.top())),
        QPoint(int(r.right()), int(r.top() + s * 0.14)),
        QPoint(int(r.right() - s * 0.14), int(r.top() + s * 0.14)),
    ]))
    p.setPen(QPen(QColor("#7a3fbf"), max(1, int(s * 0.045))))
    p.setBrush(QColor("#7a3fbf"))
    stem_x1 = r.left() + r.width() * 0.36
    stem_x2 = r.left() + r.width() * 0.62
    head_y = r.top() + r.height() * 0.62
    p.drawLine(QPoint(int(stem_x1), int(head_y)), QPoint(int(stem_x1), int(r.top() + r.height() * 0.28)))
    p.drawLine(QPoint(int(stem_x2), int(head_y - r.height() * 0.05)),
               QPoint(int(stem_x2), int(r.top() + r.height() * 0.20)))
    p.drawLine(QPoint(int(stem_x1), int(r.top() + r.height() * 0.28)),
               QPoint(int(stem_x2), int(r.top() + r.height() * 0.20)))
    p.setPen(Qt.PenStyle.NoPen)
    note_r = s * 0.06
    p.drawEllipse(QPoint(int(stem_x1), int(head_y)), int(note_r), int(note_r * 0.8))
    p.drawEllipse(QPoint(int(stem_x2), int(head_y - r.height() * 0.05)), int(note_r), int(note_r * 0.8))


def _draw_video_file(p, s):
    r = QRectF(s * 0.20, s * 0.06, s * 0.60, s * 0.86)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("white"))
    poly = QPolygon([
        QPoint(int(r.left()), int(r.top())),
        QPoint(int(r.right() - s * 0.14), int(r.top())),
        QPoint(int(r.right()), int(r.top() + s * 0.14)),
        QPoint(int(r.right()), int(r.bottom())),
        QPoint(int(r.left()), int(r.bottom())),
    ])
    p.drawPolygon(poly)
    p.setBrush(QColor("#c8c8c8"))
    p.drawPolygon(QPolygon([
        QPoint(int(r.right() - s * 0.14), int(r.top())),
        QPoint(int(r.right()), int(r.top() + s * 0.14)),
        QPoint(int(r.right() - s * 0.14), int(r.top() + s * 0.14)),
    ]))
    screen = QRectF(r.left() + s * 0.06, r.top() + s * 0.30, r.width() - s * 0.12, s * 0.34)
    p.setPen(QPen(QColor("#333"), 1))
    p.setBrush(QColor("#222"))
    p.drawRoundedRect(screen, s * 0.02, s * 0.02)
    tri = QPolygon([
        QPoint(int(screen.left() + screen.width() * 0.38), int(screen.top() + screen.height() * 0.25)),
        QPoint(int(screen.left() + screen.width() * 0.38), int(screen.bottom() - screen.height() * 0.25)),
        QPoint(int(screen.left() + screen.width() * 0.68), int(screen.top() + screen.height() * 0.5)),
    ])
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#7fd0ff"))
    p.drawPolygon(tri)


def _draw_volume(p, s, muted=False):
    body = QPolygon([
        QPoint(int(s * 0.10), int(s * 0.38)),
        QPoint(int(s * 0.32), int(s * 0.38)),
        QPoint(int(s * 0.54), int(s * 0.18)),
        QPoint(int(s * 0.54), int(s * 0.82)),
        QPoint(int(s * 0.32), int(s * 0.62)),
        QPoint(int(s * 0.10), int(s * 0.62)),
    ])
    p.setPen(QPen(QColor("#333"), 1))
    p.setBrush(QColor("#333"))
    p.drawPolygon(body)
    if muted:
        p.setPen(QPen(QColor("#c33"), max(1, int(s * 0.09)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPoint(int(s * 0.62), int(s * 0.34)), QPoint(int(s * 0.90), int(s * 0.66)))
        p.drawLine(QPoint(int(s * 0.90), int(s * 0.34)), QPoint(int(s * 0.62), int(s * 0.66)))
    else:
        p.setPen(QPen(QColor("#333"), max(1, int(s * 0.06)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(s * 0.58, s * 0.28, s * 0.20, s * 0.44), -50 * 16, 100 * 16)
        p.drawArc(QRectF(s * 0.68, s * 0.16, s * 0.26, s * 0.68), -50 * 16, 100 * 16)


def _draw_wmp(p, s):
    r = QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88)
    p.setPen(QPen(QColor("#274a6e"), 1))
    p.setBrush(_grad(r, "#bcd6f0", "#5f8fc4"))
    p.drawEllipse(r)
    inner = r.adjusted(s * 0.10, s * 0.10, -s * 0.10, -s * 0.10)
    p.setPen(QPen(QColor("#1a3a5c"), 1))
    p.setBrush(QColor("#0d2338"))
    p.drawEllipse(inner)
    tri = QPolygon([
        QPoint(int(inner.left() + inner.width() * 0.38), int(inner.top() + inner.height() * 0.28)),
        QPoint(int(inner.left() + inner.width() * 0.38), int(inner.bottom() - inner.height() * 0.28)),
        QPoint(int(inner.left() + inner.width() * 0.72), int(inner.top() + inner.height() * 0.5)),
    ])
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#7fd0ff"))
    p.drawPolygon(tri)


def _draw_task_manager(p, s):
    r = QRectF(s * 0.08, s * 0.08, s * 0.84, s * 0.84)
    p.setPen(QPen(QColor("#444"), 1))
    p.setBrush(QColor("black"))
    p.drawRoundedRect(r, 2, 2)
    p.setPen(QPen(QColor("#33e33d"), max(1, int(s * 0.07))))
    bars = [0.3, 0.55, 0.4, 0.75, 0.5]
    bw = r.width() / (len(bars) + 1)
    for i, h in enumerate(bars):
        x = r.left() + bw * (i + 0.7)
        p.drawLine(QPoint(int(x), int(r.bottom() - 3)), QPoint(int(x), int(r.bottom() - 3 - r.height() * h)))


def _draw_logoff(p, s):
    p.setPen(QPen(QColor("#3366cc"), s * 0.08))
    p.drawRect(QRectF(s * 0.2, s * 0.2, s * 0.35, s * 0.6))
    p.drawLine(QPoint(int(s * 0.45), int(s * 0.5)), QPoint(int(s * 0.85), int(s * 0.5)))
    p.drawLine(QPoint(int(s * 0.7), int(s * 0.35)), QPoint(int(s * 0.85), int(s * 0.5)))
    p.drawLine(QPoint(int(s * 0.7), int(s * 0.65)), QPoint(int(s * 0.85), int(s * 0.5)))


def _draw_bitmap_file(p, s):
    r = QRectF(s * 0.20, s * 0.06, s * 0.60, s * 0.86)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("white"))
    poly = QPolygon([
        QPoint(int(r.left()), int(r.top())),
        QPoint(int(r.right() - s * 0.14), int(r.top())),
        QPoint(int(r.right()), int(r.top() + s * 0.14)),
        QPoint(int(r.right()), int(r.bottom())),
        QPoint(int(r.left()), int(r.bottom())),
    ])
    p.drawPolygon(poly)
    p.setBrush(QColor("#c8c8c8"))
    p.drawPolygon(QPolygon([
        QPoint(int(r.right() - s * 0.14), int(r.top())),
        QPoint(int(r.right()), int(r.top() + s * 0.14)),
        QPoint(int(r.right() - s * 0.14), int(r.top() + s * 0.14)),
    ]))
    pic = QRectF(r.left() + s * 0.06, r.top() + s * 0.30, r.width() - s * 0.12, s * 0.34)
    p.setPen(QPen(QColor("#888"), 1))
    p.setBrush(QColor("#bfe2ff"))
    p.drawRect(pic)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffd23f"))
    p.drawEllipse(QPoint(int(pic.left() + pic.width() * 0.25), int(pic.top() + pic.height() * 0.3)),
                  int(s * 0.05), int(s * 0.05))
    p.setBrush(QColor("#3a8f3a"))
    p.drawPolygon(QPolygon([
        QPoint(int(pic.left()), int(pic.bottom())),
        QPoint(int(pic.left() + pic.width() * 0.45), int(pic.top() + pic.height() * 0.35)),
        QPoint(int(pic.left() + pic.width() * 0.75), int(pic.bottom())),
    ]))
    p.setBrush(QColor("#2a6e2a"))
    p.drawPolygon(QPolygon([
        QPoint(int(pic.left() + pic.width() * 0.4), int(pic.bottom())),
        QPoint(int(pic.left() + pic.width() * 0.75), int(pic.top() + pic.height() * 0.25)),
        QPoint(int(pic.right()), int(pic.bottom())),
    ]))


def _draw_tool_pencil(p, s):
    p.save()
    p.translate(s * 0.5, s * 0.5)
    p.rotate(45)
    body = QRectF(-s * 0.09, -s * 0.42, s * 0.18, s * 0.66)
    p.setPen(QPen(QColor("#8a6a1a"), 1))
    p.setBrush(QColor("#ffd23f"))
    p.drawRect(body)
    tip = QPolygon([
        QPoint(int(-s * 0.09), int(body.bottom())),
        QPoint(int(s * 0.09), int(body.bottom())),
        QPoint(0, int(body.bottom() + s * 0.14)),
    ])
    p.setBrush(QColor("#e8c495"))
    p.drawPolygon(tip)
    p.setBrush(QColor("#333"))
    p.drawRect(QRectF(-s * 0.02, body.bottom() + s * 0.08, s * 0.04, s * 0.05))
    eraser = QRectF(-s * 0.09, -s * 0.50, s * 0.18, s * 0.09)
    p.setBrush(QColor("#ff8fa3"))
    p.drawRect(eraser)
    p.restore()


def _draw_tool_brush(p, s):
    p.save()
    p.translate(s * 0.5, s * 0.5)
    p.rotate(45)
    p.setPen(QPen(QColor("#7a4a1a"), s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPoint(0, int(-s * 0.1)), QPoint(0, int(s * 0.38)))
    p.setPen(QPen(QColor("#c8c8c8"), 1))
    p.setBrush(QColor("#dcdcdc"))
    p.drawRect(QRectF(-s * 0.09, -s * 0.30, s * 0.18, s * 0.14))
    bristles = QPolygon([
        QPoint(int(-s * 0.09), int(-s * 0.30)),
        QPoint(int(s * 0.09), int(-s * 0.30)),
        QPoint(int(s * 0.05), int(-s * 0.46)),
        QPoint(int(-s * 0.05), int(-s * 0.46)),
    ])
    p.setBrush(QColor("#e33"))
    p.drawPolygon(bristles)
    p.restore()


def _draw_tool_eraser(p, s):
    p.save()
    p.translate(s * 0.5, s * 0.5)
    p.rotate(-20)
    r = QRectF(-s * 0.28, -s * 0.18, s * 0.56, s * 0.36)
    p.setPen(QPen(QColor("#a34a6a"), 1))
    p.setBrush(_grad(r, "#ff9fb8", "#e0567f"))
    p.drawRoundedRect(r, s * 0.05, s * 0.05)
    p.setPen(QPen(QColor("#a3a3a3"), max(1, int(s * 0.02))))
    p.drawLine(QPoint(int(-s * 0.04), int(r.top())), QPoint(int(-s * 0.04), int(r.bottom())))
    p.restore()


def _draw_tool_fill(p, s):
    p.save()
    p.translate(s * 0.46, s * 0.5)
    p.rotate(-30)
    body = QRectF(-s * 0.20, -s * 0.28, s * 0.40, s * 0.32)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("#c3c3c3"))
    p.drawRoundedRect(body, s * 0.03, s * 0.03)
    lid = QRectF(-s * 0.20, -s * 0.34, s * 0.40, s * 0.09)
    p.setBrush(QColor("#8f8f8f"))
    p.drawRoundedRect(lid, s * 0.02, s * 0.02)
    spout = QPolygon([
        QPoint(int(s * 0.20), int(-s * 0.06)),
        QPoint(int(s * 0.36), int(s * 0.02)),
        QPoint(int(s * 0.20), int(s * 0.02)),
    ])
    p.setBrush(QColor("#8f8f8f"))
    p.drawPolygon(spout)
    p.restore()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffc61a"))
    drop = QPolygon([
        QPoint(int(s * 0.66), int(s * 0.58)),
        QPoint(int(s * 0.78), int(s * 0.74)),
        QPoint(int(s * 0.66), int(s * 0.86)),
        QPoint(int(s * 0.54), int(s * 0.74)),
    ])
    p.drawPolygon(drop)


def _draw_tool_eyedropper(p, s):
    p.save()
    p.translate(s * 0.5, s * 0.5)
    p.rotate(45)
    p.setPen(QPen(QColor("#555"), 1))
    p.setBrush(QColor("#dcdcdc"))
    p.drawRect(QRectF(-s * 0.08, -s * 0.42, s * 0.16, s * 0.22))
    p.setBrush(QColor("#3a8f3a"))
    p.drawRect(QRectF(-s * 0.06, -s * 0.20, s * 0.12, s * 0.42))
    tip = QPolygon([
        QPoint(int(-s * 0.06), int(s * 0.22)),
        QPoint(int(s * 0.06), int(s * 0.22)),
        QPoint(0, int(s * 0.34)),
    ])
    p.setBrush(QColor("#245524"))
    p.drawPolygon(tip)
    p.restore()


def _draw_tool_line(p, s):
    p.setPen(QPen(QColor("#222"), max(1, int(s * 0.09)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPoint(int(s * 0.18), int(s * 0.82)), QPoint(int(s * 0.82), int(s * 0.18)))


def _draw_tool_rect(p, s):
    p.setPen(QPen(QColor("#222"), max(1, int(s * 0.08))))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRectF(s * 0.16, s * 0.24, s * 0.68, s * 0.52))


def _draw_tool_ellipse(p, s):
    p.setPen(QPen(QColor("#222"), max(1, int(s * 0.08))))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(s * 0.14, s * 0.22, s * 0.72, s * 0.56))


def _draw_tool_text(p, s):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#222"))
    f = p.font()
    f.setBold(True)
    f.setPixelSize(int(s * 0.62))
    p.setFont(f)
    p.setPen(QColor("#222"))
    p.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "A")


def _draw_tool_select(p, s):
    pen = QPen(QColor("#222"), max(1, int(s * 0.055)))
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72))


#  Explorer shell glyphs 
# Toolbar / task-pane / drive icons. Registered through _SHELL_DRAWERS at the
# bottom rather than another 20 elif branches in _draw().

def _page(p, s, r=None, fill="white"):
    """The dog-eared white sheet every document-ish glyph is built on."""
    r = r or QRectF(s * 0.20, s * 0.08, s * 0.56, s * 0.82)
    fold = r.width() * 0.28
    p.setPen(QPen(QColor("#6b6b6b"), 1))
    p.setBrush(QColor(fill))
    p.drawPolygon(QPolygon([
        QPoint(int(r.left()), int(r.top())),
        QPoint(int(r.right() - fold), int(r.top())),
        QPoint(int(r.right()), int(r.top() + fold)),
        QPoint(int(r.right()), int(r.bottom())),
        QPoint(int(r.left()), int(r.bottom())),
    ]))
    p.setBrush(QColor("#d4d4d4"))
    p.drawPolygon(QPolygon([
        QPoint(int(r.right() - fold), int(r.top())),
        QPoint(int(r.right()), int(r.top() + fold)),
        QPoint(int(r.right() - fold), int(r.top() + fold)),
    ]))
    return r


def _mini_folder(p, s, rect):
    p.setPen(QPen(QColor("#8a6d1f"), 1))
    p.setBrush(_grad(rect, "#ffe28a", "#ffb92e"))
    p.drawRoundedRect(QRectF(rect.left(), rect.top() - rect.height() * 0.22,
                             rect.width() * 0.48, rect.height() * 0.3), 1, 1)
    p.setBrush(_grad(rect, "#ffd35c", "#ffa713"))
    p.drawRoundedRect(rect, 1, 1)


def _fat_arrow(p, s, rect, direction, c1, c2, outline):
    """Chunky Luna navigation arrow: shaft + head, gradient filled."""
    w, h = rect.width(), rect.height()
    cx, cy = rect.center().x(), rect.center().y()
    pts = [
        QPointF(-w * 0.5, 0.0), QPointF(-w * 0.05, -h * 0.5), QPointF(-w * 0.05, -h * 0.2),
        QPointF(w * 0.5, -h * 0.2), QPointF(w * 0.5, h * 0.2), QPointF(-w * 0.05, h * 0.2),
        QPointF(-w * 0.05, h * 0.5),
    ]
    rot = {"left": (1, 1, False), "right": (-1, 1, False), "up": (1, 1, True), "down": (-1, 1, True)}
    sx, sy, swap = rot[direction]
    poly = QPolygonF([
        QPointF(cx + (pt.y() if swap else pt.x()) * sx,
                cy + (pt.x() if swap else pt.y()) * sy)
        for pt in pts
    ])
    p.setPen(QPen(QColor(outline), 1))
    p.setBrush(_grad(rect, c1, c2))
    p.drawPolygon(poly)


def _draw_nav_back(p, s):
    _fat_arrow(p, s, QRectF(s * 0.10, s * 0.20, s * 0.80, s * 0.60), "left",
               "#a6ea7d", "#2f8f16", "#1d5a0c")


def _draw_nav_forward(p, s):
    _fat_arrow(p, s, QRectF(s * 0.10, s * 0.20, s * 0.80, s * 0.60), "right",
               "#a6ea7d", "#2f8f16", "#1d5a0c")


def _draw_nav_up(p, s):
    _mini_folder(p, s, QRectF(s * 0.06, s * 0.56, s * 0.88, s * 0.36))
    _fat_arrow(p, s, QRectF(s * 0.22, s * 0.02, s * 0.56, s * 0.50), "up",
               "#a6ea7d", "#2f8f16", "#1d5a0c")


def _draw_allprograms(p, s):
    """Two overlapping fat green chevrons -- the Start Menu's All Programs glyph."""
    _fat_arrow(p, s, QRectF(s * 0.02, s * 0.24, s * 0.50, s * 0.52), "right",
               "#c9f7a8", "#3fa129", "#1a6e0a")
    _fat_arrow(p, s, QRectF(s * 0.32, s * 0.24, s * 0.50, s * 0.52), "right",
               "#c9f7a8", "#3fa129", "#1a6e0a")


def _draw_xp_flag(p, s):
    """Simplified four-pane waving-flag mark used on the Start button."""
    cx, cy = s * 0.5, s * 0.5
    gap, pane = s * 0.045, s * 0.40
    panes = [
        ("#f6552b", QPointF(cx - gap - pane, cy - gap - pane), QPointF(cx - gap, cy - gap)),
        ("#7cb92e", QPointF(cx + gap, cy - gap - pane), QPointF(cx + gap + pane, cy - gap)),
        ("#1f8ee8", QPointF(cx - gap - pane, cy + gap), QPointF(cx - gap, cy + gap + pane)),
        ("#ffc20e", QPointF(cx + gap, cy + gap), QPointF(cx + gap + pane, cy + gap + pane)),
    ]
    p.setPen(Qt.PenStyle.NoPen)
    for color, top_left, bottom_right in panes:
        rect = QRectF(top_left, bottom_right)
        skew = rect.height() * 0.16
        poly = QPolygonF([
            QPointF(rect.left() + skew * 0.4, rect.top()),
            QPointF(rect.right(), rect.top() + skew * 0.2),
            QPointF(rect.right() - skew * 0.4, rect.bottom()),
            QPointF(rect.left(), rect.bottom() - skew * 0.2),
        ])
        p.setBrush(_grad(rect, QColor(color).lighter(122).name(), color, vertical=False))
        p.drawPolygon(poly)


def _draw_shell_search(p, s):
    lens = QRectF(s * 0.12, s * 0.10, s * 0.58, s * 0.58)
    p.setPen(QPen(QColor("#3a4a63"), max(2, int(s * 0.09))))
    p.setBrush(_grad(lens, "#dff0ff", "#8fc4f0"))
    p.drawEllipse(lens)
    p.setPen(QPen(QColor("#3a4a63"), max(2, int(s * 0.13)), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(lens.right() - s * 0.06, lens.bottom() - s * 0.06),
               QPointF(s * 0.90, s * 0.90))


def _draw_shell_folders(p, s):
    _mini_folder(p, s, QRectF(s * 0.04, s * 0.30, s * 0.42, s * 0.34))
    p.setPen(QPen(QColor("#7f7f7f"), 1))
    x = s * 0.50
    p.drawLine(QPointF(x, s * 0.24), QPointF(x, s * 0.80))
    for y in (0.24, 0.52, 0.80):
        p.drawLine(QPointF(x, s * y), QPointF(s * 0.62, s * y))
        _mini_folder(p, s, QRectF(s * 0.64, s * (y - 0.10), s * 0.30, s * 0.20))


def _draw_shell_views(p, s):
    p.setPen(QPen(QColor("#4a6a95"), 1))
    for row in range(2):
        for col in range(2):
            cell = QRectF(s * (0.12 + col * 0.42), s * (0.12 + row * 0.42), s * 0.32, s * 0.32)
            p.setBrush(_grad(cell, "#eaf3ff", "#7fb0e8"))
            p.drawRect(cell)


def _drive_body(p, s, front_color, led):
    top = QPolygon([
        QPoint(int(s * 0.10), int(s * 0.42)), QPoint(int(s * 0.28), int(s * 0.24)),
        QPoint(int(s * 0.94), int(s * 0.24)), QPoint(int(s * 0.76), int(s * 0.42)),
    ])
    p.setPen(QPen(QColor("#5c6472"), 1))
    p.setBrush(QColor("#e2e6ee"))
    p.drawPolygon(top)
    side = QPolygon([
        QPoint(int(s * 0.76), int(s * 0.42)), QPoint(int(s * 0.94), int(s * 0.24)),
        QPoint(int(s * 0.94), int(s * 0.58)), QPoint(int(s * 0.76), int(s * 0.76)),
    ])
    p.setBrush(QColor("#9aa3b2"))
    p.drawPolygon(side)
    front = QRectF(s * 0.10, s * 0.42, s * 0.66, s * 0.34)
    p.setBrush(_grad(front, "#f2f4f8", front_color))
    p.drawRect(front)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(led))
    p.drawRect(QRectF(s * 0.16, s * 0.62, s * 0.08, s * 0.06))
    return front


def _draw_drive_fixed(p, s):
    _drive_body(p, s, "#b8bfcc", "#3fbf3f")


def _draw_drive_cdrom(p, s):
    front = _drive_body(p, s, "#b8bfcc", "#e0a020")
    p.setPen(QPen(QColor("#7a8291"), 1))
    p.setBrush(QColor("#d6dae2"))
    p.drawRect(QRectF(front.left() + s * 0.22, front.top() + s * 0.06, s * 0.40, s * 0.07))
    disc = QRectF(s * 0.30, s * 0.02, s * 0.52, s * 0.30)
    p.setBrush(_grad(disc, "#f0f4ff", "#9fb6d8"))
    p.drawEllipse(disc)
    p.setBrush(QColor("#ffffff"))
    p.drawEllipse(disc.adjusted(disc.width() * 0.38, disc.height() * 0.38,
                                -disc.width() * 0.38, -disc.height() * 0.38))


def _draw_drive_floppy(p, s):
    body = QRectF(s * 0.12, s * 0.12, s * 0.76, s * 0.76)
    p.setPen(QPen(QColor("#1c2530"), 1))
    p.setBrush(_grad(body, "#4c5766", "#212a36"))
    p.drawRoundedRect(body, 2, 2)
    shutter = QRectF(s * 0.34, s * 0.14, s * 0.34, s * 0.28)
    p.setBrush(QColor("#c8ccd4"))
    p.drawRect(shutter)
    p.setBrush(QColor("#8f96a2"))
    p.drawRect(QRectF(shutter.left() + shutter.width() * 0.55, shutter.top(),
                      shutter.width() * 0.45, shutter.height()))
    label = QRectF(s * 0.22, s * 0.50, s * 0.56, s * 0.34)
    p.setBrush(QColor("#eceff4"))
    p.drawRect(label)


def _draw_shared_docs(p, s):
    _draw_docfolder(p, s)
    _hand(p, s, QRectF(s * 0.02, s * 0.52, s * 0.46, s * 0.44))


def _hand(p, s, r):
    p.setPen(QPen(QColor("#a9762f"), 1))
    p.setBrush(_grad(r, "#ffdcae", "#e8b070"))
    palm = QRectF(r.left() + r.width() * 0.18, r.top() + r.height() * 0.42,
                  r.width() * 0.72, r.height() * 0.54)
    p.drawRoundedRect(palm, r.width() * 0.16, r.width() * 0.16)
    for i in range(3):
        finger = QRectF(palm.left() + i * palm.width() * 0.26,
                        r.top() + r.height() * (0.10 + i * 0.05),
                        palm.width() * 0.24, palm.height() * 0.80)
        p.drawRoundedRect(finger, finger.width() * 0.45, finger.width() * 0.45)


def _globe(p, s, r):
    p.setPen(QPen(QColor("#1f4f8f"), 1))
    p.setBrush(_grad(r, "#bfe4ff", "#2f7ad0"))
    p.drawEllipse(r)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))
    p.drawEllipse(QRectF(r.center().x() - r.width() * 0.22, r.top(),
                         r.width() * 0.44, r.height()))


def _draw_my_network(p, s):
    _globe(p, s, QRectF(s * 0.08, s * 0.06, s * 0.56, s * 0.56))
    mon = QRectF(s * 0.42, s * 0.46, s * 0.50, s * 0.34)
    p.setPen(QPen(QColor("#2a3a55"), 1))
    p.setBrush(_grad(mon, "#c9d6ea", "#7f97bd"))
    p.drawRoundedRect(mon, 2, 2)
    p.setBrush(QColor("#123a7a"))
    p.drawRect(mon.adjusted(s * 0.05, s * 0.05, -s * 0.05, -s * 0.08))
    p.setPen(QPen(QColor("#6a7488"), 1))
    p.drawLine(QPointF(s * 0.30, s * 0.62), QPointF(s * 0.44, s * 0.62))


def _draw_task_newfolder(p, s):
    _mini_folder(p, s, QRectF(s * 0.06, s * 0.34, s * 0.70, s * 0.50))
    _sparkle(p, s, QPointF(s * 0.78, s * 0.24), s * 0.22)


def _sparkle(p, s, center, radius):
    p.setPen(QPen(QColor("#e8a800"), max(1, int(s * 0.07)), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    for dx, dy in ((1, 0), (0, 1), (0.7, 0.7), (-0.7, 0.7)):
        p.drawLine(QPointF(center.x() - dx * radius, center.y() - dy * radius),
                   QPointF(center.x() + dx * radius, center.y() + dy * radius))


def _draw_task_rename(p, s):
    r = _page(p, s, QRectF(s * 0.08, s * 0.08, s * 0.52, s * 0.78))
    p.setPen(QPen(QColor("#4a4a4a"), 1))
    for i in range(3):
        y = r.top() + r.height() * (0.34 + i * 0.18)
        p.drawLine(QPointF(r.left() + s * 0.08, y), QPointF(r.right() - s * 0.08, y))
    shaft = QRectF(s * 0.46, s * 0.40, s * 0.16, s * 0.46)
    p.setPen(QPen(QColor("#7a5a10"), 1))
    p.setBrush(_grad(shaft, "#ffe07a", "#e0a800"))
    p.save()
    p.translate(s * 0.62, s * 0.30)
    p.rotate(35)
    p.drawRect(QRectF(0, 0, s * 0.16, s * 0.44))
    p.setBrush(QColor("#f5d6a0"))
    p.drawPolygon(QPolygonF([QPointF(0, s * 0.44), QPointF(s * 0.16, s * 0.44),
                             QPointF(s * 0.08, s * 0.60)]))
    p.restore()


def _draw_task_move(p, s):
    _mini_folder(p, s, QRectF(s * 0.44, s * 0.36, s * 0.52, s * 0.48))
    _page(p, s, QRectF(s * 0.04, s * 0.06, s * 0.34, s * 0.50))
    _fat_arrow(p, s, QRectF(s * 0.30, s * 0.52, s * 0.40, s * 0.34), "right",
               "#a6ea7d", "#2f8f16", "#1d5a0c")


def _draw_task_copy(p, s):
    _page(p, s, QRectF(s * 0.06, s * 0.06, s * 0.50, s * 0.70), fill="#f4f4f4")
    _page(p, s, QRectF(s * 0.34, s * 0.24, s * 0.50, s * 0.70))


def _draw_task_delete(p, s):
    _page(p, s, QRectF(s * 0.10, s * 0.06, s * 0.54, s * 0.74))
    p.setPen(QPen(QColor("#c01818"), max(2, int(s * 0.13)), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    a, b = s * 0.48, s * 0.94
    p.drawLine(QPointF(a, a), QPointF(b, b))
    p.drawLine(QPointF(b, a), QPointF(a, b))


def _draw_task_publish(p, s):
    _page(p, s, QRectF(s * 0.06, s * 0.06, s * 0.50, s * 0.70))
    _globe(p, s, QRectF(s * 0.40, s * 0.40, s * 0.54, s * 0.54))


def _draw_task_share(p, s):
    _draw_folder(p, s)
    _hand(p, s, QRectF(s * 0.02, s * 0.50, s * 0.48, s * 0.46))


def _draw_task_email(p, s):
    body = QRectF(s * 0.06, s * 0.22, s * 0.88, s * 0.58)
    p.setPen(QPen(QColor("#6b6b6b"), 1))
    p.setBrush(QColor("white"))
    p.drawRect(body)
    p.setBrush(QColor("#dfe6f2"))
    p.drawPolygon(QPolygonF([body.topLeft(),
                             QPointF(body.center().x(), body.center().y() + s * 0.06),
                             body.topRight()]))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(body.bottomLeft(), QPointF(body.center().x(), body.center().y() + s * 0.06))
    p.drawLine(body.bottomRight(), QPointF(body.center().x(), body.center().y() + s * 0.06))


def _draw_task_print(p, s):
    paper = QRectF(s * 0.24, s * 0.04, s * 0.52, s * 0.34)
    p.setPen(QPen(QColor("#6b6b6b"), 1))
    p.setBrush(QColor("white"))
    p.drawRect(paper)
    body = QRectF(s * 0.08, s * 0.34, s * 0.84, s * 0.36)
    p.setPen(QPen(QColor("#4a4f58"), 1))
    p.setBrush(_grad(body, "#eef1f6", "#a8b0bd"))
    p.drawRoundedRect(body, 2, 2)
    p.setBrush(QColor("#3fbf3f"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRect(QRectF(s * 0.14, s * 0.42, s * 0.10, s * 0.06))
    out = QRectF(s * 0.24, s * 0.62, s * 0.52, s * 0.32)
    p.setPen(QPen(QColor("#6b6b6b"), 1))
    p.setBrush(QColor("white"))
    p.drawRect(out)


def _draw_task_restore(p, s):
    _mini_folder(p, s, QRectF(s * 0.06, s * 0.44, s * 0.60, s * 0.44))
    _fat_arrow(p, s, QRectF(s * 0.34, s * 0.06, s * 0.58, s * 0.42), "up",
               "#a6ea7d", "#2f8f16", "#1d5a0c")


def _draw_task_empty(p, s):
    _draw_recycle(p, s, full=False)
    _sparkle(p, s, QPointF(s * 0.84, s * 0.22), s * 0.16)


_SHELL_DRAWERS = {
    "nav_back": _draw_nav_back, "nav_forward": _draw_nav_forward, "nav_up": _draw_nav_up,
    "shell_search": _draw_shell_search, "shell_folders": _draw_shell_folders,
    "shell_views": _draw_shell_views,
    "drive_fixed": _draw_drive_fixed, "drive_cdrom": _draw_drive_cdrom,
    "drive_floppy": _draw_drive_floppy,
    "shared_docs": _draw_shared_docs, "my_network": _draw_my_network,
    "task_newfolder": _draw_task_newfolder, "task_rename": _draw_task_rename,
    "task_move": _draw_task_move, "task_copy": _draw_task_copy,
    "task_delete": _draw_task_delete, "task_publish": _draw_task_publish,
    "task_share": _draw_task_share, "task_email": _draw_task_email,
    "task_print": _draw_task_print, "task_restore": _draw_task_restore,
    "task_empty": _draw_task_empty,
}


def shortcut_icon(name: str, size: int = 32) -> QIcon:
    """Any icon with the shell's shortcut overlay -- the little white box with
    a black arrow that XP stamps on the bottom-left corner of every .lnk."""
    key = ("__shortcut__", name, size)
    if key in _CACHE:
        return _CACHE[key]
    pm = QPixmap(_draw(name, size))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = QRectF(0, size * 0.62, size * 0.38, size * 0.38)
    p.setPen(QPen(QColor("#5a5a5a"), 1))
    p.setBrush(QColor("white"))
    p.drawRect(box)
    p.setPen(QPen(QColor("#101010"), max(1, int(size * 0.06)), Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    tail = QPointF(box.left() + box.width() * 0.26, box.bottom() - box.height() * 0.24)
    head = QPointF(box.right() - box.width() * 0.22, box.top() + box.height() * 0.24)
    p.drawLine(tail, head)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#101010"))
    p.drawPolygon(QPolygonF([
        head,
        QPointF(head.x() - box.width() * 0.34, head.y() + box.height() * 0.06),
        QPointF(head.x() - box.width() * 0.06, head.y() + box.height() * 0.34),
    ]))
    p.end()
    ic = QIcon(pm)
    _CACHE[key] = ic
    return ic
