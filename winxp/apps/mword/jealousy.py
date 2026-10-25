"""Clippy's jealousy: one shared score per window manager, so every open
Word window's Clippy agrees on how much time you've spent elsewhere."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# class name -> (display name, score per second spent in it)
RIVALS = {
    "ExCellWindow": ("Ex-Cell", 3.0),
    "PhotoChopWindow": ("PhotoChop", 2.0),
    "VisualXPCodeWindow": ("Visual XP Code", 1.5),
    "WordPadWindow": ("WordPad", 1.5),
    "NotepadWindow": ("Notepad", 1.0),
    "PaintWindow": ("Paint", 0.5),
}

SUSPICIOUS = 30
HURT = 120
SNAPPED = 300
FORGIVENESS_PER_SECOND = 0.5

ABSENCE_SECONDS = 20


def rival_name(window) -> str | None:
    entry = RIVALS.get(type(window).__name__)
    return entry[0] if entry else None


class JealousyTracker(QObject):
    """Polls the window manager once a second."""

    window_opened = pyqtSignal(object)
    rival_opened = pyqtSignal(str)
    # (Word window, rival, seconds away)
    returned = pyqtSignal(object, str, int)
    # emitted after the rival window has been minimized
    snapped = pyqtSignal(str)

    def __init__(self, wm):
        super().__init__()
        self.wm = wm
        self.score = 0.0
        self.time_with: dict[str, int] = {}
        self._seen: set[int] = set()
        self._away_with: str | None = None
        self._away_seconds = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    @property
    def mood(self) -> str:
        if self.score >= SNAPPED:
            return "snapped"
        if self.score >= HURT:
            return "hurt"
        if self.score >= SUSPICIOUS:
            return "suspicious"
        return "fine"

    def _tick(self):
        alive = {id(w) for w in self.wm.windows}
        self._seen &= alive
        for window in list(self.wm.windows):
            if id(window) in self._seen:
                continue
            self._seen.add(id(window))
            self.window_opened.emit(window)
            name = rival_name(window)
            if name:
                self.rival_opened.emit(name)

        active = self.wm.active
        if active is None or not active.isVisible():
            return
        name = rival_name(active)
        if name:
            self.score += RIVALS[type(active).__name__][1]
            self.time_with[name] = self.time_with.get(name, 0) + 1
            if self._away_with != name:
                self._away_with, self._away_seconds = name, 0
            self._away_seconds += 1
            if self.score >= SNAPPED and self._away_seconds % 45 == 0:
                active.minimize()
                self.snapped.emit(name)
        elif type(active).__name__ == "MWordWindow":
            if self._away_with and self._away_seconds >= ABSENCE_SECONDS:
                self.returned.emit(active, self._away_with, self._away_seconds)
            self._away_with, self._away_seconds = None, 0
            self.score = max(0.0, self.score - FORGIVENESS_PER_SECOND)

    def forgive(self, amount: float):
        self.score = max(0.0, self.score - amount)

    def wound(self, amount: float):
        self.score += amount


_trackers: dict[int, JealousyTracker] = {}


def tracker_for(wm) -> JealousyTracker:
    tracker = _trackers.get(id(wm))
    if tracker is None:
        tracker = _trackers[id(wm)] = JealousyTracker(wm)
    return tracker
