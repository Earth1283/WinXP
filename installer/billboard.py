"""The screen GUI-mode Setup paints behind everything.

Dark band with the logo across the top, the five stages and the famously
optimistic time estimate down the left, and -- while files are copying and
no dialog is up -- the marketing slides on the right. The wizard pages sit
on top of it in a Windows Classic dialog frame, which is also drawn here.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QRadialGradient
from PyQt6.QtWidgets import QVBoxLayout, QWidget

import artwork
from style import (
    BACKDROP_BLUE, BACKDROP_GLOW, BAND_BLUE, BAND_LINE_LIGHT, BAND_LINE_ORANGE,
    DARK_SHADOW, FACE, HILIGHT, SHADOW, STAGE_DIM, TITLE_LEFT, TITLE_RIGHT, ui_font,
)

# The five stages down the left of real Setup.
STAGES = ["Collecting information", "Dynamic Update", "Preparing installation",
          "Installing Windows", "Finalizing installation"]

TOP_BAND = 70
BOTTOM_BAND = 44
COLUMN_X = 30
COLUMN_W = 196

SLIDES = [
    ("The most dependable Windows yet",
     "Windows XP is built on proven technology, so your computer runs more "
     "reliably than ever before.\n\nOn the rare occasion that it doesn't, a "
     "friendly blue screen will explain exactly what went wrong, in "
     "hexadecimal."),
    ("Get more done with MacroHard Office",
     "Word 2003 and Ex-Cell 2003 work together to help you create "
     "great-looking documents and spreadsheets.\n\nAn animated assistant is "
     "standing by to ask whether you are writing a letter."),
    ("Have fun with digital pictures",
     "Adobo PhotoChop 7.0 makes it easy to crop, retouch and share the "
     "photos from your digital camera.\n\nYour scratch disk is already full, "
     "which saves you the trouble of filling it."),
    ("Explore the Internet",
     "Internet Explorer 6 brings the World Wide Web to your desktop, "
     "complete with pop-up windows you never asked for and toolbars you do "
     "not remember installing."),
    ("Music, video and more",
     "Windows Media Player 8 plays your favourite songs and videos, burns "
     "CDs, and changes its skin to something you will not be able to change "
     "back."),
    ("Take a break",
     "Minesweeper is included with every copy of Windows XP.\n\nSetup will "
     "be finished long before your best time is."),
]
SLIDE_INTERVAL_MS = 9000


class Billboard(QWidget):
    def __init__(self):
        super().__init__()
        self.stage_index = 0
        self.minutes_left = 39
        self.progress = None         # None = no progress bar on screen
        self.status = ""
        self.detail = ""
        self.slides_on = False
        self.slide = 0
        self._slide_timer = QTimer(self)
        self._slide_timer.timeout.connect(self._next_slide)

    # -- state -----------------------------------------------------------

    def set_stage(self, index):
        self.stage_index = index
        self.update()

    def set_minutes(self, minutes):
        self.minutes_left = minutes
        self.update()

    def set_progress(self, value):
        self.progress = value
        self.update()

    def set_status(self, text):
        self.status = text
        self.update()

    def set_detail(self, text):
        self.detail = text
        self.update(self._progress_rect())

    def show_slides(self, on: bool):
        self.slides_on = on
        if on:
            self.slide = 0
            self._slide_timer.start(SLIDE_INTERVAL_MS)
        else:
            self._slide_timer.stop()
        self.update()

    def _next_slide(self):
        self.slide = (self.slide + 1) % len(SLIDES)
        self.update()

    # -- painting --------------------------------------------------------

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self._paint_backdrop(p)
        artwork.draw_logo(p, 34, 15, 40)
        self._paint_stages(p)
        self._paint_estimate(p)
        if self.progress is not None:
            self._paint_progress(p)
        if self.slides_on:
            self._paint_slide(p)
        p.end()

    def _paint_backdrop(self, p):
        w, h = self.width(), self.height()
        body = QRect(0, TOP_BAND, w, h - TOP_BAND - BOTTOM_BAND)
        p.fillRect(body, QColor(BACKDROP_BLUE))
        glow = QRadialGradient(QPointF(w * 0.12, TOP_BAND + 40), w * 0.75)
        glow.setColorAt(0, QColor(BACKDROP_GLOW))
        glow.setColorAt(1, QColor(BACKDROP_BLUE))
        p.fillRect(body, glow)

        # a faint rule between the stage column and the rest
        rule = QLinearGradient(0, TOP_BAND, 0, h - BOTTOM_BAND)
        for stop, alpha in ((0, 0), (0.25, 110), (0.75, 110), (1, 0)):
            rule.setColorAt(stop, QColor(255, 255, 255, alpha))
        p.fillRect(QRectF(COLUMN_X + COLUMN_W + 10, TOP_BAND, 1,
                          h - TOP_BAND - BOTTOM_BAND), rule)

        p.fillRect(QRect(0, 0, w, TOP_BAND), QColor(BAND_BLUE))
        p.fillRect(QRect(0, h - BOTTOM_BAND, w, BOTTOM_BAND), QColor(BAND_BLUE))
        self._band_line(p, TOP_BAND - 2, BAND_LINE_LIGHT, 0.3)
        self._band_line(p, h - BOTTOM_BAND, BAND_LINE_ORANGE, 0.5)

    def _band_line(self, p, y, color, peak):
        line = QLinearGradient(0, 0, self.width(), 0)
        c = QColor(color)
        edge = QColor(c)
        edge.setAlpha(0)
        line.setColorAt(0, edge)
        line.setColorAt(peak, c)
        line.setColorAt(1, edge)
        p.fillRect(QRectF(0, y, self.width(), 2), line)

    def _paint_stages(self, p):
        y = TOP_BAND + 42
        for i, stage in enumerate(STAGES):
            done = i < self.stage_index
            current = i == self.stage_index
            self._paint_orb(p, QPointF(COLUMN_X + 6, y), done, current)
            p.setFont(ui_font(12, bold=current))
            p.setPen(QColor("white") if current or done else QColor(STAGE_DIM))
            p.drawText(QRectF(COLUMN_X + 20, y - 10, COLUMN_W - 20, 20),
                       Qt.AlignmentFlag.AlignVCenter, stage)
            y += 30

    @staticmethod
    def _paint_orb(p, centre, done, current):
        """The little glass bead beside each stage: green and lit for the one
        Setup is on, pale for the ones behind it, dull for the ones ahead."""
        if current:
            halo = QRadialGradient(centre, 11)
            halo.setColorAt(0, QColor(190, 255, 120, 150))
            halo.setColorAt(1, QColor(190, 255, 120, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(centre, 11, 11)
            hi, lo, rim = "#e6ffb0", "#3c9a12", "#2a6e0a"
        elif done:
            hi, lo, rim = "#ffffff", "#9db6e8", "#5a7bc8"
        else:
            hi, lo, rim = "#a9bff0", "#3155b8", "#2a4aa6"
        bead = QRadialGradient(QPointF(centre.x() - 2, centre.y() - 2), 8)
        bead.setColorAt(0, QColor(hi))
        bead.setColorAt(1, QColor(lo))
        p.setPen(QColor(rim))
        p.setBrush(bead)
        p.drawEllipse(centre, 5.5, 5.5)

    def _paint_estimate(self, p):
        top = TOP_BAND + 42 + 30 * len(STAGES) + 20
        p.setPen(QColor("white"))
        p.setFont(ui_font(12))
        p.drawText(QRectF(COLUMN_X, top, COLUMN_W, 40), Qt.TextFlag.TextWordWrap,
                   "Setup will complete in\napproximately:")
        p.setFont(ui_font(12, bold=True))
        unit = "minute" if self.minutes_left == 1 else "minutes"
        p.drawText(QRectF(COLUMN_X, top + 36, COLUMN_W, 20), 0,
                   f"{self.minutes_left} {unit}")

    def _progress_rect(self):
        return QRect(COLUMN_X - 2, self.height() - BOTTOM_BAND - 96,
                     COLUMN_W + 4, 76)

    def _paint_progress(self, p):
        area = self._progress_rect()
        x, y = COLUMN_X, area.top()
        p.setPen(QColor("white"))
        p.setFont(ui_font(11))
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(x, y, COLUMN_W, 16), 0,
                   fm.elidedText(self.status, Qt.TextElideMode.ElideRight, COLUMN_W))

        bar = QRectF(x + 0.5, y + 22.5, COLUMN_W - 1, 15)
        p.setPen(QColor("#1c3c94"))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(bar, 2.5, 2.5)
        # Luna-style green blocks
        inner = bar.adjusted(2.5, 2.5, -2, -2)
        filled = inner.width() * max(0, min(100, self.progress)) / 100
        block, gap = 7, 2
        grad = QLinearGradient(0, inner.top(), 0, inner.bottom())
        grad.setColorAt(0, QColor("#d0f7a8"))
        grad.setColorAt(0.45, QColor("#33b51b"))
        grad.setColorAt(1, QColor("#90e05c"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        bx = inner.left()
        while bx + block <= inner.left() + filled + 0.5:
            p.drawRect(QRectF(bx, inner.top(), block, inner.height()))
            bx += block + gap

        if self.detail:
            p.setPen(QColor(STAGE_DIM))
            p.setFont(ui_font(10))
            fm = QFontMetrics(p.font())
            p.drawText(QRectF(x, y + 44, COLUMN_W, 14), 0,
                       fm.elidedText(self.detail, Qt.TextElideMode.ElideMiddle, COLUMN_W))

    def _paint_slide(self, p):
        title, text = SLIDES[self.slide]
        left = COLUMN_X + COLUMN_W + 52
        width = self.width() - left - 48
        top = TOP_BAND + 60
        p.setPen(QColor("white"))
        p.setFont(artwork.logo_font(24))
        p.drawText(QRectF(left, top, width, 70), Qt.TextFlag.TextWordWrap, title)
        title_h = p.fontMetrics().boundingRect(
            QRect(0, 0, int(width), 200), Qt.TextFlag.TextWordWrap, title).height()
        p.setFont(ui_font(14))
        p.drawText(QRectF(left, top + title_h + 22, width, 260),
                   Qt.TextFlag.TextWordWrap, text)

        # which slide this is, as a row of small dots
        dots_y = self.height() - BOTTOM_BAND - 34
        for i in range(len(SLIDES)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 230 if i == self.slide else 90))
            p.drawEllipse(QPointF(left + 4 + i * 14, dots_y), 3, 3)


class ClassicDialog(QWidget):
    """A Windows 2000 dialog frame: two-pixel bevel, gradient caption with
    no buttons on it (Setup never had any), grey client area. Put the
    content in ``body``."""

    BORDER = 3
    CAPTION = 18

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.setAutoFillBackground(False)
        self.body = QVBoxLayout(self)
        top = self.BORDER + self.CAPTION + 1
        self.body.setContentsMargins(self.BORDER, top, self.BORDER, self.BORDER)
        self.body.setSpacing(0)

    def paintEvent(self, ev):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(FACE))
        # outer: face / dark shadow, inner: highlight / shadow
        self._bevel(p, QRect(0, 0, w, h), FACE, DARK_SHADOW)
        self._bevel(p, QRect(1, 1, w - 2, h - 2), HILIGHT, SHADOW)

        b = self.BORDER
        caption = QRect(b, b, w - 2 * b, self.CAPTION)
        grad = QLinearGradient(caption.left(), 0, caption.right(), 0)
        grad.setColorAt(0, QColor(TITLE_LEFT))
        grad.setColorAt(1, QColor(TITLE_RIGHT))
        p.fillRect(caption, grad)
        p.setPen(QColor("white"))
        p.setFont(ui_font(11, bold=True))
        p.drawText(caption.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter,
                   self.title)
        p.end()

    @staticmethod
    def _bevel(p, r, top_left, bottom_right):
        p.setPen(QColor(top_left))
        p.drawLine(r.left(), r.top(), r.right() - 1, r.top())
        p.drawLine(r.left(), r.top(), r.left(), r.bottom() - 1)
        p.setPen(QColor(bottom_right))
        p.drawLine(r.left(), r.bottom(), r.right(), r.bottom())
        p.drawLine(r.right(), r.top(), r.right(), r.bottom())
