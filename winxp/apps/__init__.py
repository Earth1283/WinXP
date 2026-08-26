from __future__ import annotations

from ..app_registry import BY_ID
from ..corruption import health
from ..vfs import vfs


def launch(wm, target: str):
    if health.is_dead("smss.exe") and not target.startswith("system:"):
        return None

    if target.startswith("app:"):
        target = target[4:]

    if target.startswith("explorer:"):
        ref = target[len("explorer:"):]
        node_id = {"root": vfs.root_id, "mydocs": vfs.my_docs_id, "recycle": vfs.recycle_id}.get(ref, ref)
        from .explorer import ExplorerWindow
        window = ExplorerWindow(wm, node_id)
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

    window = spec.factory(wm, node_id or None)
    window._app_key = spec.id
    wm.open(window)
    return window


def _system_action(wm, action):
    from .power_screen import PowerScreen
    PowerScreen(action).show_fullscreen_on(wm)
