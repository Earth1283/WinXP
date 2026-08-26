from __future__ import annotations

import json
import os

from PyQt6.QtCore import QObject, pyqtSignal

STORE_PATH = os.path.expanduser("~/.winxp_sim/settings.json")

WALLPAPERS = {
    "Bliss (default)": ("gradient", "#3a6ea5", "#1a4a80"),
    "Azul": ("gradient", "#0b3d91", "#06213f"),
    "Autumn": ("gradient", "#8a5a2b", "#4a2f14"),
    "Solid Teal": ("solid", "#008080", None),
    "Solid Black": ("solid", "#000000", None),
    "Red Rocks": ("gradient", "#8a2b2b", "#4a1414"),
}


class Settings(QObject):
    wallpaper_changed = pyqtSignal()
    volume_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.wallpaper = "Bliss (default)"
        self.volume = 70
        self.muted = False
        self.load()

    def load(self):
        if os.path.exists(STORE_PATH):
            try:
                with open(STORE_PATH) as f:
                    data = json.load(f)
                self.wallpaper = data.get("wallpaper", self.wallpaper)
                self.volume = data.get("volume", self.volume)
                self.muted = data.get("muted", self.muted)
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
        with open(STORE_PATH, "w") as f:
            json.dump({"wallpaper": self.wallpaper, "volume": self.volume, "muted": self.muted}, f)

    def set_wallpaper(self, name):
        if name in WALLPAPERS:
            self.wallpaper = name
            self.save()
            self.wallpaper_changed.emit()

    def set_volume(self, value):
        self.volume = max(0, min(100, value))
        self.save()
        self.volume_changed.emit()

    def set_muted(self, muted):
        self.muted = muted
        self.save()
        self.volume_changed.emit()


settings = Settings()
