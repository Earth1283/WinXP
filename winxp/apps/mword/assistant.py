"""The Office Assistant.

Clippit -- "Clippy" -- was a floating window that sat on top of the document,
watched what you typed, and offered help nobody asked for. It is reproduced
here with the parts that made it infamous: it appears uninvited, it has an
opinion about your letter, it can be dragged around, it animates, and closing
it takes two steps.
"""
from __future__ import annotations

import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QMenu, QWidget

from ... import theme

BALLOON_BG = "#ffffcc"
BALLOON_EDGE = "#666633"

TIPS = [
    ("letter", "It looks like you're writing a letter.",
     ["Get help with writing the letter", "Just type the letter without help",
      "Don't show me this tip again"]),
    ("list", "It looks like you're making a list.",
     ["Format the list automatically", "Leave it exactly as I typed it",
      "Don't show me this tip again"]),
    ("resume", "It looks like you're writing a résumé.",
     ["Get help formatting the résumé", "Type it myself",
      "Don't show me this tip again"]),
    ("long", "You've been typing for a while without saving.",
     ["Save the document now", "Live dangerously", "Don't show me this tip again"]),
    ("headings", "It looks like you're using headings.",
     ["Apply Heading 1 automatically", "Leave my formatting alone",
      "Don't show me this tip again"]),
]

IDLE_LINES = [
    "Did you know? Pressing F7 checks spelling.",
    "Tip: hold Alt while dragging a ruler marker for finer control.",
    "Tip: Ctrl+Shift+> grows the selected text one size.",
    "Tip: double-click a status bar indicator to switch it on.",
    "I am legally required to be here.",
    "You can drag me somewhere less useful if you like.",
]


class OfficeAssistant(QWidget):
    """Clippit himself: a paperclip, a pair of eyes, and a balloon."""

    choice_made = pyqtSignal(str)

    def __init__(self, owner):
        super().__init__(owner.content)
        self.owner = owner
        self.setFixedSize(224, 190)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.message = ""
        self.choices: list[str] = []
        self.balloon_visible = False
        self._drag = None
        self._blink = 0.0
        self._lean = 0.0
        self._animating = 0
        self._hover_choice = -1
        self._shown_tips: set[str] = set()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(90)

        self._idle = QTimer(self)
        self._idle.timeout.connect(self._idle_tip)
        self._idle.start(95_000)

    # -- behaviour --------------------------------------------------------

    def say(self, message: str, choices=None):
        self.message = message
        self.choices = list(choices or ["OK"])
        self.balloon_visible = True
        self._animating = 14
        self.show()
        self.raise_()
        self.update()

    def offer_tip(self, key: str):
        """Fire a context tip at most once per session, as Word did."""
        if key in self._shown_tips:
            return
        for tip_key, message, choices in TIPS:
            if tip_key == key:
                self._shown_tips.add(key)
                self.say(message, choices)
                return

    def _idle_tip(self):
        if self.isVisible() and not self.balloon_visible:
            self.say(random.choice(IDLE_LINES), ["OK"])

    def dismiss(self):
        self.balloon_visible = False
        self.update()

    def _tick(self):
        self._blink = (self._blink + 0.09) % 6.0
        if self._animating > 0:
            self._animating -= 1
            self._lean = (self._animating % 4 - 1.5) * 1.6
        else:
            self._lean *= 0.7
        self.update()

    def animate(self):
        self._animating = 24

    # -- geometry ---------------------------------------------------------

    def _clip_rect(self) -> QRectF:
        return QRectF(self.width() - 84, self.height() - 96, 76, 92)

    def _balloon_rect(self) -> QRectF:
        return QRectF(2, 2, self.width() - 8, self.height() - 104)

    def _choice_rects(self) -> list[QRectF]:
        balloon = self._balloon_rect()
        rects = []
        y = balloon.top() + 34
        for _ in self.choices:
            rects.append(QRectF(balloon.left() + 10, y, balloon.width() - 20, 17))
            y += 19
        return rects

    # -- painting ---------------------------------------------------------

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.balloon_visible:
            self._paint_balloon(p)
        self._paint_clippy(p)
        p.end()

    def _paint_balloon(self, p: QPainter):
        rect = self._balloon_rect()
        path = QPainterPath()
        path.addRoundedRect(rect, 9, 9)
        tail = QPainterPath()
        tail.moveTo(rect.right() - 40, rect.bottom() - 2)
        tail.lineTo(rect.right() - 18, rect.bottom() + 16)
        tail.lineTo(rect.right() - 16, rect.bottom() - 2)
        tail.closeSubpath()
        path = path.united(tail)
        p.setPen(QPen(QColor(BALLOON_EDGE), 1))
        p.setBrush(QColor(BALLOON_BG))
        p.drawPath(path)

        p.setPen(QColor("#1a1a00"))
        font = QFont("Tahoma", 8)
        p.setFont(font)
        p.drawText(QRectF(rect.left() + 8, rect.top() + 6, rect.width() - 16, 28),
                   int(Qt.TextFlag.TextWordWrap), self.message)

        for index, (choice, box) in enumerate(zip(self.choices, self._choice_rects())):
            if index == self._hover_choice:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#ffe680"))
                p.drawRoundedRect(box, 3, 3)
            p.setPen(QColor("#1a3a8a"))
            p.setBrush(QColor("#1a3a8a"))
            p.drawEllipse(QRectF(box.left(), box.center().y() - 2, 4, 4))
            p.setPen(QColor("#000066"))
            p.drawText(QRectF(box.left() + 9, box.top(), box.width() - 9, box.height()),
                       int(Qt.AlignmentFlag.AlignVCenter), choice)

    def _paint_clippy(self, p: QPainter):
        rect = self._clip_rect()
        p.save()
        p.translate(rect.center())
        p.rotate(self._lean)
        p.translate(-rect.center())

        # shadow on the page
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(rect.left() + 8, rect.bottom() - 8, rect.width() - 16, 9))

        w, h = rect.width(), rect.height()
        x, y = rect.left(), rect.top()
        body = QPainterPath()
        body.moveTo(x + w * 0.30, y + h * 0.96)
        body.lineTo(x + w * 0.30, y + h * 0.30)
        body.cubicTo(x + w * 0.30, y - h * 0.03,
                     x + w * 0.82, y - h * 0.03,
                     x + w * 0.82, y + h * 0.30)
        body.lineTo(x + w * 0.82, y + h * 0.80)
        body.cubicTo(x + w * 0.82, y + h * 1.02,
                     x + w * 0.50, y + h * 1.02,
                     x + w * 0.50, y + h * 0.80)
        body.lineTo(x + w * 0.50, y + h * 0.36)

        pen = QPen(QColor("#8d99a8"), 8.0, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pen)
        p.drawPath(body)
        pen.setColor(QColor("#c8d2dd"))
        pen.setWidthF(3.4)
        p.setPen(pen)
        p.drawPath(body)

        blinking = self._blink > 5.6
        eye_h = 2.0 if blinking else 15.0
        for dx in (0.34, 0.58):
            eye = QRectF(x + w * dx, y + h * 0.16 + (15 - eye_h) / 2, 13, eye_h)
            p.setPen(QPen(QColor("#2a2a2a"), 1.2))
            p.setBrush(QColor("white"))
            p.drawEllipse(eye)
            if not blinking:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#101010"))
                p.drawEllipse(QRectF(eye.center().x() - 2.6, eye.center().y() - 1.4, 5.2, 5.2))
        # the eyebrows that made him look permanently concerned
        p.setPen(QPen(QColor("#5a6470"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(x + w * 0.33, y + h * 0.11), QPointF(x + w * 0.46, y + h * 0.07))
        p.drawLine(QPointF(x + w * 0.57, y + h * 0.07), QPointF(x + w * 0.70, y + h * 0.11))
        p.restore()

    # -- interaction ------------------------------------------------------

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            self._context_menu(ev)
            return
        if self.balloon_visible:
            for index, box in enumerate(self._choice_rects()):
                if box.contains(ev.position()):
                    self._choose(self.choices[index])
                    return
        if self._clip_rect().contains(ev.position()):
            if self.balloon_visible:
                self.dismiss()
            else:
                self.say(random.choice(IDLE_LINES), ["OK"])
            self.animate()
            return
        self._drag = ev.position()

    def mouseMoveEvent(self, ev):
        if self._drag is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            delta = ev.position() - self._drag
            self.move(int(self.x() + delta.x()), int(self.y() + delta.y()))
            return
        hover = -1
        if self.balloon_visible:
            for index, box in enumerate(self._choice_rects()):
                if box.contains(ev.position()):
                    hover = index
                    break
        if hover != self._hover_choice:
            self._hover_choice = hover
            self.setCursor(Qt.CursorShape.PointingHandCursor if hover >= 0
                           else Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def _choose(self, choice: str):
        self.dismiss()
        if choice.startswith("Don't show"):
            pass
        self.choice_made.emit(choice)

    def _context_menu(self, ev):
        menu = QMenu(self)
        menu.setStyleSheet(theme.MENU_QSS)
        for label, slot in (("Hide", self.hide),
                            ("Options...", self.owner.assistant_options),
                            ("Choose Assistant...", self.owner.choose_assistant),
                            ("Animate!", self.animate)):
            action = QAction(label, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        menu.exec(ev.globalPosition().toPoint())
