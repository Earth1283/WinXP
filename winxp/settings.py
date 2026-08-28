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


SOUND_SCHEMES = {
    "Windows Default": {"startup": "startup", "shutdown": "shutdown", "error": "error"},
    "No Sounds": {"startup": None, "shutdown": None, "error": None},
}

SCREENSAVERS = ["Starfield", "(None)"]


class Settings(QObject):
    wallpaper_changed = pyqtSignal()
    volume_changed = pyqtSignal()
    scheme_changed = pyqtSignal()
    folder_options_changed = pyqtSignal()
    apps_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.wallpaper = "Bliss (default)"
        self.volume = 70
        self.muted = False
        self.scheme = "Windows XP (Blue)"
        self.sound_scheme = "Windows Default"
        self.show_hidden = False
        self.show_extensions = True
        self.screensaver = "Starfield"
        self.screensaver_wait_minutes = 5
        # Add or Remove Programs actually removes things: uninstalled app ids
        # persist here, and Start Menu / New Task / launch() all honor it.
        self.uninstalled_apps: set[str] = set()
        # Explorer's Favorites menu -- vfs node ids, in the order added.
        self.explorer_favorites: list[str] = []
        # Last view mode / sort Explorer was left in; XP remembered these too.
        self.explorer_view = "icons"
        self.explorer_sort = "name"
        self.explorer_groups = False
        self.load()

    def load(self):
        if os.path.exists(STORE_PATH):
            try:
                with open(STORE_PATH) as f:
                    data = json.load(f)
                self.wallpaper = data.get("wallpaper", self.wallpaper)
                self.volume = data.get("volume", self.volume)
                self.muted = data.get("muted", self.muted)
                self.scheme = data.get("scheme", self.scheme)
                self.sound_scheme = data.get("sound_scheme", self.sound_scheme)
                self.show_hidden = data.get("show_hidden", self.show_hidden)
                self.show_extensions = data.get("show_extensions", self.show_extensions)
                self.screensaver = data.get("screensaver", self.screensaver)
                self.screensaver_wait_minutes = data.get(
                    "screensaver_wait_minutes", self.screensaver_wait_minutes)
                self.uninstalled_apps = set(data.get("uninstalled_apps", []))
                self.explorer_favorites = list(data.get("explorer_favorites", []))
                self.explorer_view = data.get("explorer_view", self.explorer_view)
                self.explorer_sort = data.get("explorer_sort", self.explorer_sort)
                self.explorer_groups = data.get("explorer_groups", self.explorer_groups)
            except Exception:
                pass
        from . import theme
        theme.set_scheme(self.scheme)

    def save(self):
        os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
        with open(STORE_PATH, "w") as f:
            json.dump({
                "wallpaper": self.wallpaper, "volume": self.volume, "muted": self.muted,
                "scheme": self.scheme, "sound_scheme": self.sound_scheme,
                "show_hidden": self.show_hidden, "show_extensions": self.show_extensions,
                "screensaver": self.screensaver,
                "screensaver_wait_minutes": self.screensaver_wait_minutes,
                "uninstalled_apps": sorted(self.uninstalled_apps),
                "explorer_favorites": list(self.explorer_favorites),
                "explorer_view": self.explorer_view,
                "explorer_sort": self.explorer_sort,
                "explorer_groups": self.explorer_groups,
            }, f)

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

    def set_scheme(self, name):
        if name not in ("Windows XP (Blue)", "Olive Green", "Silver"):
            return
        from . import theme
        self.scheme = name
        theme.set_scheme(name)
        self.save()
        self.scheme_changed.emit()

    def set_sound_scheme(self, name):
        if name in SOUND_SCHEMES:
            self.sound_scheme = name
            self.save()

    def set_show_hidden(self, value):
        self.show_hidden = bool(value)
        self.save()
        self.folder_options_changed.emit()

    def set_show_extensions(self, value):
        self.show_extensions = bool(value)
        self.save()
        self.folder_options_changed.emit()

    def set_screensaver(self, name):
        if name in SCREENSAVERS:
            self.screensaver = name
            self.save()

    def set_screensaver_wait(self, minutes):
        self.screensaver_wait_minutes = max(1, int(minutes))
        self.save()

    def set_explorer_view(self, mode, sort_column, groups):
        self.explorer_view = mode
        self.explorer_sort = sort_column
        self.explorer_groups = bool(groups)
        self.save()

    def add_explorer_favorite(self, node_id):
        if node_id not in self.explorer_favorites:
            self.explorer_favorites.append(node_id)
            self.save()

    def remove_explorer_favorite(self, node_id):
        if node_id in self.explorer_favorites:
            self.explorer_favorites.remove(node_id)
            self.save()

    def is_installed(self, app_id):
        return app_id not in self.uninstalled_apps

    def set_app_installed(self, app_id, installed):
        if installed:
            self.uninstalled_apps.discard(app_id)
        else:
            self.uninstalled_apps.add(app_id)
        self.save()
        self.apps_changed.emit()


settings = Settings()
