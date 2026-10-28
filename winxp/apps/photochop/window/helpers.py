"""Pixel helpers used by the PhotoChop window commands."""
from __future__ import annotations

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QImage, QPainter

from .. import imageops as ops


def _content_bounds(img: QImage) -> QRect:
    buf, w, h = ops.to_buf(img)
    alpha = ops.plane(buf, ops.A)
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        row = y * w
        for x in range(w):
            if alpha[row + x] > 8:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < 0:
        return QRect()
    return QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def _vignette(img: QImage) -> QImage:
    from PyQt6.QtGui import QRadialGradient
    overlay = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    overlay.fill(Qt.GlobalColor.transparent)
    p = QPainter(overlay)
    grad = QRadialGradient(img.width() / 2, img.height() / 2,
                           max(img.width(), img.height()) * 0.62)
    grad.setColorAt(0.55, QColor(0, 0, 0, 0))
    grad.setColorAt(1.0, QColor(0, 0, 0, 210))
    p.fillRect(overlay.rect(), grad)
    p.end()
    out = img.copy()
    p = QPainter(out)
    p.drawImage(0, 0, overlay)
    p.end()
    return out
