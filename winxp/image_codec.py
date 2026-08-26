"""PNG byte <-> QPixmap helpers for Paint's file format (vfs IMAGE nodes)."""
from __future__ import annotations

from PyQt6.QtCore import QBuffer, Qt
from PyQt6.QtGui import QPixmap


def to_bytes(pixmap: QPixmap) -> bytes:
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    return bytes(buf.data())


def from_bytes(data: bytes) -> QPixmap:
    pm = QPixmap()
    if data:
        pm.loadFromData(data, "PNG")
    return pm


def blank(width=560, height=380) -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(Qt.GlobalColor.white)
    return pm
