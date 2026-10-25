"""Everything Setup draws instead of loading from an image file.

The installer is compiled into a single binary and fetches the rest of
winxp later, so it cannot borrow the app's icons -- these are painted in
code, at the sizes Setup actually used them.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QConicalGradient, QFont, QFontMetricsF, QLinearGradient, QPainter,
    QPainterPath, QPen, QPolygonF, QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from style import LOGO_FONT_FAMILIES, MONO_FONT_FAMILY, ui_font

# (shadow, highlight) for each pane, reading order.
FLAG_PANES = [("#e8410f", "#ff9a6a"), ("#6aab12", "#b8e45a"),
              ("#0a8ee0", "#6ccaff"), ("#f2a900", "#ffdd6e")]
XP_ORANGE = "#ff7b00"


def _wave(t: float) -> float:
    """Vertical offset of the flag's cloth at fraction t of its width."""
    return math.sin(t * math.pi * 1.25 - 0.35)


def draw_flag(p: QPainter, rect: QRectF, trail: bool = True):
    """The four-pane waving flag, with the fading squares streaming off its
    left edge the way the XP mark has them."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    gap = rect.width() * 0.045
    pane_w = (rect.width() - gap) / 2
    pane_h = (rect.height() - gap) / 2
    amp = rect.height() * 0.07
    for i, (dark, light) in enumerate(FLAG_PANES):
        col, row = i % 2, i // 2
        x0 = rect.left() + col * (pane_w + gap)
        y0 = rect.top() + row * (pane_h + gap) + amp
        steps = 10
        top, bottom = [], []
        for s in range(steps + 1):
            x = x0 + pane_w * s / steps
            t = (x - rect.left()) / rect.width()
            dy = amp * _wave(t)
            top.append(QPointF(x, y0 + dy))
            bottom.append(QPointF(x, y0 + pane_h + dy))
        grad = QLinearGradient(x0, y0, x0 + pane_w, y0 + pane_h)
        grad.setColorAt(0, QColor(light))
        grad.setColorAt(1, QColor(dark))
        p.setBrush(grad)
        p.drawPolygon(QPolygonF(top + bottom[::-1]))

        if trail and col == 0:
            # Bits of the flag streaming off to the left, smaller and fainter
            # the further they get.
            size = pane_h * 0.30
            x = x0
            for k in range(3):
                x -= size * 1.55
                c = QColor(dark)
                c.setAlphaF(0.75 - k * 0.22)
                p.setBrush(c)
                cy = y0 + pane_h * 0.5 + amp * _wave(0) - size / 2
                p.drawRect(QRectF(x, cy, size, size))
                size *= 0.72
    p.restore()


def logo_font(px: float, bold=True, italic=False) -> QFont:
    font = QFont()
    font.setFamilies(LOGO_FONT_FAMILIES)
    font.setPixelSize(max(1, int(px)))
    font.setBold(bold)
    font.setItalic(italic)
    return font


def draw_logo(p: QPainter, x: float, y: float, height: float,
              color: QColor | str = "white"):
    """Flag, then 'Microsloth(R) Windows(R) xp' set beside it."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    flag_w = height * 1.05
    draw_flag(p, QRectF(x, y, flag_w, height))
    tx = x + flag_w + height * 0.18
    p.setPen(QColor(color))
    p.setFont(logo_font(height * 0.24, bold=False))
    p.drawText(QPointF(tx + 2, y + height * 0.24), "Microsloth®")
    big = logo_font(height * 0.66)
    p.setFont(big)
    baseline = y + height * 0.90
    p.drawText(QPointF(tx, baseline), "Windows")
    adv = p.fontMetrics().horizontalAdvance("Windows")
    p.setFont(logo_font(height * 0.22, bold=False))
    p.drawText(QPointF(tx + adv + 1, baseline - height * 0.42), "®")
    p.setPen(QColor(XP_ORANGE))
    p.setFont(logo_font(height * 0.58, italic=True))
    p.drawText(QPointF(tx + adv + height * 0.22, baseline - height * 0.02), "xp")
    p.restore()


def logo_width(height: float) -> float:
    """How wide draw_logo() comes out, for anything that needs to centre it."""
    adv = QFontMetricsF(logo_font(height * 0.66)).horizontalAdvance("Windows")
    xp = QFontMetricsF(logo_font(height * 0.58, italic=True)).horizontalAdvance("xp")
    return height * 1.05 + height * 0.18 + adv + height * 0.22 + xp


class HeaderIcon(QWidget):
    """The 49x49 picture in the top-right of a Wizard97 header: a computer
    with the Setup CD leaning against it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(49, 49)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outline = QPen(QColor("#4a4a4a"), 1)

        # monitor
        p.setPen(outline)
        case = QLinearGradient(0, 4, 0, 34)
        case.setColorAt(0, QColor("#f4f1e8"))
        case.setColorAt(1, QColor("#bdb6a0"))
        p.setBrush(case)
        p.drawRoundedRect(QRectF(4.5, 4.5, 34, 28), 2.5, 2.5)
        screen = QLinearGradient(0, 8, 0, 28)
        screen.setColorAt(0, QColor("#3d72d8"))
        screen.setColorAt(1, QColor("#0d2f8c"))
        p.setBrush(screen)
        p.setPen(QPen(QColor("#6b6b6b"), 1))
        p.drawRect(QRectF(8.5, 8.5, 26, 19))
        draw_flag(p, QRectF(16, 12, 12, 11), trail=False)
        # stand
        p.setPen(outline)
        p.setBrush(QColor("#c9c2ad"))
        p.drawPolygon(QPolygonF([QPointF(16, 32.5), QPointF(27, 32.5),
                                 QPointF(29, 37.5), QPointF(14, 37.5)]))
        p.drawRoundedRect(QRectF(9.5, 37.5, 24, 4), 1.5, 1.5)

        # CD
        disc = QRectF(25.5, 24.5, 22, 22)
        p.setPen(QPen(QColor("#7a7f88"), 1))
        sheen = QConicalGradient(disc.center(), 30)
        for stop, color in ((0.0, "#f2f4f8"), (0.15, "#c9e8ff"), (0.3, "#f5d6f0"),
                            (0.45, "#dfe3ea"), (0.6, "#fff4c4"), (0.75, "#cfeccf"),
                            (0.9, "#e9ecf2"), (1.0, "#f2f4f8")):
            sheen.setColorAt(stop, QColor(color))
        p.setBrush(sheen)
        p.drawEllipse(disc)
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor("#9aa0aa"), 1))
        p.drawEllipse(disc.center(), 4, 4)
        p.setBrush(QColor("#d4d0c8"))
        p.drawEllipse(disc.center(), 1.6, 1.6)
        p.end()


class WarningIcon(QWidget):
    """The classic yellow triangle, as on a Windows 2000 message box."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tri = QPolygonF([QPointF(16, 2), QPointF(30.5, 29), QPointF(1.5, 29)])
        p.setPen(QPen(QColor("#000000"), 1.2))
        grad = QLinearGradient(0, 2, 0, 29)
        grad.setColorAt(0, QColor("#ffff80"))
        grad.setColorAt(1, QColor("#f0c800"))
        p.setBrush(grad)
        p.drawPolygon(tri)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#000000"))
        p.drawPolygon(QPolygonF([QPointF(14.2, 10), QPointF(17.8, 10),
                                 QPointF(16.9, 21), QPointF(15.1, 21)]))
        p.drawEllipse(QPointF(16, 25), 1.9, 1.9)
        p.end()


class Watermark(QWidget):
    """The tall picture down the left of the Welcome and Completing pages:
    a small Bliss, with the logo in the sky."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(164)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        sky = QLinearGradient(0, 0, 0, h * 0.75)
        sky.setColorAt(0, QColor("#0c4ec4"))
        sky.setColorAt(0.6, QColor("#4f8de8"))
        sky.setColorAt(1, QColor("#a8c9f4"))
        p.fillRect(self.rect(), sky)

        p.setPen(Qt.PenStyle.NoPen)
        for cx, cy, rx, ry, a in ((30, 0.50, 46, 11, 0.55), (120, 0.56, 54, 9, 0.45),
                                  (90, 0.46, 30, 7, 0.35), (10, 0.62, 40, 7, 0.30)):
            cloud = QRadialGradient(QPointF(cx, h * cy), rx)
            cloud.setColorAt(0, QColor(255, 255, 255, int(255 * a)))
            cloud.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(cloud)
            p.drawEllipse(QPointF(cx, h * cy), rx, ry * 1.6)

        hill = QPainterPath()
        hill.moveTo(0, h * 0.74)
        hill.cubicTo(w * 0.35, h * 0.64, w * 0.75, h * 0.66, w, h * 0.76)
        hill.lineTo(w, h)
        hill.lineTo(0, h)
        hill.closeSubpath()
        grass = QLinearGradient(0, h * 0.64, 0, h)
        grass.setColorAt(0, QColor("#7dc443"))
        grass.setColorAt(0.4, QColor("#4f9a26"))
        grass.setColorAt(1, QColor("#2f6d14"))
        p.setBrush(grass)
        p.drawPath(hill)

        height = 34
        lw = logo_width(height)
        scale = min(1.0, (w - 16) / lw)
        p.save()
        p.translate((w - lw * scale) / 2 + 6, 30)
        p.scale(scale, scale)
        draw_logo(p, 0, 0, height)
        p.restore()
        p.end()


class KeySticker(QWidget):
    """The yellow Certificate of Authenticity sticker, so you know what to
    look for on the CD sleeve you threw away."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(172, 64)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0, QColor("#fff6b0"))
        grad.setColorAt(1, QColor("#f2cf48"))
        p.setPen(QPen(QColor("#b08d14"), 1))
        p.setBrush(grad)
        p.drawRoundedRect(body, 4, 4)

        p.setPen(QColor("#5a4600"))
        p.setFont(ui_font(9, bold=True))
        p.drawText(QPointF(8, 14), "Product Key:")
        draw_flag(p, QRectF(150, 5, 14, 12), trail=False)

        # barcode
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2a2200"))
        x = 8.0
        for i in range(34):
            bar = 1.0 + (i * 7 % 3) * 0.6
            p.drawRect(QRectF(x, 20, bar, 18))
            x += bar + 1.2 + (i * 5 % 2) * 0.8
            if x > self.width() - 12:
                break

        key = "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
        mono = QFont(MONO_FONT_FAMILY)
        mono.setBold(True)
        px = 10
        mono.setPixelSize(px)
        while px > 6 and QFontMetricsF(mono).horizontalAdvance(key) > self.width() - 12:
            px -= 1
            mono.setPixelSize(px)
        p.setFont(mono)
        p.setPen(QColor("#2a2200"))
        p.drawText(QRectF(4, 42, self.width() - 8, 16), Qt.AlignmentFlag.AlignCenter, key)
        p.end()

