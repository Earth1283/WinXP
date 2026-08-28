from __future__ import annotations

from ..app_registry import BY_ID
from ..corruption import guard_fs, health
from ..settings import settings
from ..vfs import vfs


def launch(wm, target: str):
    if health.is_dead("smss.exe") and not target.startswith("system:"):
        return None

    if target.startswith("app:"):
        target = target[4:]

    if target.startswith("explorer:"):
        if guard_fs(wm):
            return None
        ref = target[len("explorer:"):]
        search = ref == "search"
        node_id = vfs.root_id if search else \
            {"root": vfs.root_id, "mydocs": vfs.my_docs_id, "recycle": vfs.recycle_id}.get(ref, ref)
        if vfs.get(node_id) is None:
            # Cursed: the folder being opened (e.g. Recycle Bin) got deleted out
            # from under us. Don't crash the whole process -- crash the "OS" instead.
            from .bsod import crash
            crash(wm, "explorer.exe")
            return None
        from .explorer import BAR_SEARCH, ExplorerWindow
        window = ExplorerWindow(wm, node_id, explorer_bar=BAR_SEARCH if search else None)
        window._app_key = "explorer"
        wm.open(window)
        return window

    if target.startswith("system:"):
        _system_action(wm, target[len("system:"):])
        return None

    app_id, _, node_id = target.partition(":")
    spec = BY_ID.get(app_id)
    if spec is None:
        return None

    if not settings.is_installed(app_id):
        # Add or Remove Programs actually removes it -- the shortcut's still
        # there, the .exe just isn't anymore. Classic XP missing-file dialog.
        from ..xp_dialog import XPMessageBox
        XPMessageBox.critical(
            None, spec.exe(),
            f"Windows cannot find '{spec.exe()}'. Make sure you typed the name "
            "correctly, and then try again.",
        )
        return None

    window = spec.factory(wm, node_id or None)
    window._app_key = spec.id
    wm.open(window)
    return window


def _system_action(wm, action):
    from .power_screen import PowerScreen
    PowerScreen(action).show_fullscreen_on(wm)
