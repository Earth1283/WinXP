from __future__ import annotations

from ..vfs import vfs

BLANK_APPS = ("ie", "notepad", "wordpad", "calculator", "paint", "minesweeper", "control_panel")


def launch(wm, target: str):
    name = target[4:] if target.startswith("app:") else target

    if name in BLANK_APPS:
        window = _create_blank(wm, name)
        wm.open(window)
        return window

    if target.startswith("explorer:"):
        ref = target[len("explorer:"):]
        node_id = {"root": vfs.root_id, "mydocs": vfs.my_docs_id, "recycle": vfs.recycle_id}.get(ref, ref)
        from .explorer import ExplorerWindow
        window = ExplorerWindow(wm, node_id)
        wm.open(window)
        return window

    if target.startswith("notepad:"):
        from .notepad import NotepadWindow
        window = NotepadWindow(wm, target[len("notepad:"):])
        wm.open(window)
        return window

    if target.startswith("wordpad:"):
        from .wordpad import WordPadWindow
        window = WordPadWindow(wm, target[len("wordpad:"):])
        wm.open(window)
        return window

    if target.startswith("system:"):
        _system_action(wm, target[len("system:"):])
        return None

    return None


def _create_blank(wm, name):
    if name == "ie":
        from .ie import IEWindow
        return IEWindow(wm)
    if name == "notepad":
        from .notepad import NotepadWindow
        return NotepadWindow(wm)
    if name == "wordpad":
        from .wordpad import WordPadWindow
        return WordPadWindow(wm)
    if name == "calculator":
        from .calculator import CalculatorWindow
        return CalculatorWindow(wm)
    if name == "paint":
        from .paint import PaintWindow
        return PaintWindow(wm)
    if name == "minesweeper":
        from .minesweeper import MinesweeperWindow
        return MinesweeperWindow(wm)
    if name == "control_panel":
        from .control_panel import ControlPanelWindow
        return ControlPanelWindow(wm)
    raise ValueError(name)


def _system_action(wm, action):
    from .power_screen import PowerScreen
    PowerScreen(action).show_fullscreen_on(wm)
