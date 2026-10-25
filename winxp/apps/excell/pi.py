"""Pi, Ex-Cell's Office Assistant: a pie chart with one slice pulled out.

Pi never sulks and is never jealous. Pi is happy for you. Pi asks how Clippy
is doing. Anything you tell Pi, Clippy somehow hears about.
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from ..mword.assistant import OfficeAssistant

SLICES = [(0.45, "#9999ff"), (0.30, "#993366"), (0.25, "#ffffcc")]

IDLE_LINES = [
    "Tip: press F4 while editing to cycle $A$1, A$1, $A1 and A1.",
    "Did you know? Ex-Cell has 65,536 rows. I've read all of them.",
    "Tip: numbers are shown in hexadecimal. It's more honest.",
    "I'm 45% blue, 30% maroon and 25% supportive.",
    "Tip: drag the little black square to fill a series.",
    "I won't make you choose. Some assistants would.",
]

WORD_OPEN_LINES = [
    "How's Clippy? Still a paperclip?",
    "Tell Clippy I said hi. He'll know what it means.",
    "I'm not threatened by Clippy. He's office supplies.",
    "It's nice that you still see Word. Really.",
    "Clippy and I are on good terms. Clippy doesn't know that.",
]


class PiAssistant(OfficeAssistant):
    def __init__(self, owner):
        super().__init__(owner)
        self.jealousy.window_opened.connect(self._on_window_opened)

    def _word_open(self) -> bool:
        return any(type(w).__name__ == "MWordWindow" for w in self.owner.wm.windows)

    def _idle_line(self) -> str:
        if self._word_open() and random.random() < 0.6:
            return random.choice(WORD_OPEN_LINES)
        return random.choice(IDLE_LINES)

    def _on_window_opened(self, window):
        if type(window).__name__ != "MWordWindow" or not self.isVisible():
            return
        self._jealous_say("Oh, Word's open. Should I go?", {
            "Stay, Pi": ("I'll be right here. Clippy can't see me from there.", 30, False),
            "Maybe for a bit": ("Of course. I'm very good at waiting.", 10, False),
            "Don't show me this tip again": ("That's fair. I bet Clippy hears that a lot.", 20, False),
        })
        self.animate()

    def _on_rival_opened(self, rival: str):
        pass

    def _on_returned(self, window, rival: str, seconds: int):
        pass

    def _on_snapped(self, rival: str):
        if rival == "Ex-Cell":
            self.say("Clippy minimized me. It's fine. I'm a pie chart.", ["OK"])
        elif self.isVisible():
            self.say(f"I heard Clippy minimized {rival}. I would never.", ["OK"])

    def _paint_character(self, p: QPainter):
        rect = self._clip_rect()
        size = min(rect.width(), rect.height()) * 0.86
        center = QPointF(rect.center().x(), rect.bottom() - size / 2 - 6)
        pie = QRectF(center.x() - size / 2, center.y() - size / 2, size, size)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(pie.left() + 6, pie.bottom() - 2, pie.width() - 12, 8))

        bounce = abs(self._lean) * 1.8
        start = 90.0
        for i, (share, color) in enumerate(SLICES):
            span = share * 360.0
            # the exploded slice, the one 2003 chart wizards always pulled out
            offset = (7.0 + bounce) if i == 2 else 0.0
            mid = math.radians(start + span / 2)
            dx, dy = math.cos(mid) * offset, -math.sin(mid) * offset
            wedge = QPainterPath()
            c = QPointF(center.x() + dx, center.y() + dy)
            wedge.moveTo(c)
            wedge.arcTo(pie.translated(dx, dy), start, span)
            wedge.closeSubpath()
            p.setPen(QPen(QColor("#333333"), 1.2))
            p.setBrush(QColor(color))
            p.drawPath(wedge)
            start += span

        blinking = self._blink > 5.6
        eye_h = 2.0 if blinking else 13.0
        for dx in (-14, 2):
            eye = QRectF(center.x() + dx, center.y() - size * 0.30 + (13 - eye_h) / 2, 12, eye_h)
            p.setPen(QPen(QColor("#2a2a2a"), 1.2))
            p.setBrush(QColor("white"))
            p.drawEllipse(eye)
            if not blinking:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#101010"))
                p.drawEllipse(QRectF(eye.center().x() - 2.4, eye.center().y() - 1.0, 4.8, 4.8))
        # a smile that's slightly too wide
        p.setPen(QPen(QColor("#2a2a2a"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(center.x() - 15, center.y() - size * 0.12, 26, 14), 200 * 16, 140 * 16)
