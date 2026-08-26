"""System sound effects (startup/shutdown/error chimes) with a master
volume control. Sound files live in winxp/assets/ -- this module only ever
plays them by local file path, same mechanism as Media Player."""
from __future__ import annotations

import os

from PyQt6.QtCore import QUrl

from .settings import SOUND_SCHEMES, settings

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

SOUNDS = {
    "startup": os.path.join(ASSETS_DIR, "startup.mp3"),
    "shutdown": os.path.join(ASSETS_DIR, "shutdown.mp3"),
    "error": os.path.join(ASSETS_DIR, "error.mp3"),
}


class SoundManager:
    """Lazy-inits its QMediaPlayer/QAudioOutput on first use -- constructing
    Qt multimedia objects at import time (before QApplication exists) would
    crash, same reasoning as winxp/icons.py's lazy icon cache."""

    def __init__(self):
        self._player = None
        self._output = None

    def _ensure(self):
        if self._player is None:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._player = QMediaPlayer()
            self._output = QAudioOutput()
            self._player.setAudioOutput(self._output)
        self._output.setMuted(settings.muted)
        self._output.setVolume(settings.volume / 100)

    def play(self, key):
        scheme = SOUND_SCHEMES.get(settings.sound_scheme, {})
        mapped = scheme.get(key, key) if key in scheme else key
        if mapped is None:
            return
        path = SOUNDS.get(mapped)
        if not path or not os.path.exists(path):
            return
        self._ensure()
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()


sounds = SoundManager()
