"""Procedurally-drawn XP-style icons (no external image assets needed)."""
from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QPolygon
from PyQt6.QtCore import QPoint

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
    elif name == "run":
        _draw_run(p, s)
    elif name == "shutdown":
        _draw_shutdown(p, s)
    elif name == "logoff":
        _draw_logoff(p, s)
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


def _draw_logoff(p, s):
    p.setPen(QPen(QColor("#3366cc"), s * 0.08))
    p.drawRect(QRectF(s * 0.2, s * 0.2, s * 0.35, s * 0.6))
    p.drawLine(QPoint(int(s * 0.45), int(s * 0.5)), QPoint(int(s * 0.85), int(s * 0.5)))
    p.drawLine(QPoint(int(s * 0.7), int(s * 0.35)), QPoint(int(s * 0.85), int(s * 0.5)))
    p.drawLine(QPoint(int(s * 0.7), int(s * 0.65)), QPoint(int(s * 0.85), int(s * 0.5)))
