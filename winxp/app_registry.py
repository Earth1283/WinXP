"""Single source of truth for every launchable application.

To add a new app, append one AppSpec to APPS below — nothing else needs
touching. Start Menu (pinned column + All Programs), Task Manager's process
list, and the launch dispatcher in winxp/apps/__init__.py all read from this
list instead of hardcoding their own copy.

See docs/adding_apps.md for the full walkthrough.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class AppSpec:
    id: str                      # stable key: "app:<id>" launch target, e.g. "notepad"
    title: str                   # window title / menu label, e.g. "Notepad"
    icon: str                    # key into winxp.icons.icon(...)
    module: str                  # submodule of winxp.apps, e.g. "notepad"
    class_name: str              # window class in that module, e.g. "NotepadWindow"
    exe_name: str = ""           # fake process name in Task Manager (defaults to f"{id}.exe")
    pinned: bool = False         # show in the Start Menu's left pinned column
    all_programs: bool = True    # show in the Start Menu's All Programs flyout
    takes_node_id: bool = False  # True if the window can open an existing vfs file,
                                  # e.g. "notepad:<node_id>" — window.__init__(wm, node_id=None)

    def exe(self) -> str:
        return self.exe_name or f"{self.id}.exe"

    def factory(self, wm, node_id=None):
        mod = importlib.import_module(f"winxp.apps.{self.module}")
        cls = getattr(mod, self.class_name)
        return cls(wm, node_id) if self.takes_node_id else cls(wm)


APPS = [
    AppSpec("ie", "Internet Explorer", "ie", "ie", "IEWindow",
            pinned=True, exe_name="iexplore.exe"),
    AppSpec("notepad", "Notepad", "notepad", "notepad", "NotepadWindow",
            pinned=True, takes_node_id=True),
    AppSpec("wordpad", "WordPad", "wordpad", "wordpad", "WordPadWindow",
            pinned=True, takes_node_id=True),
    AppSpec("mword", "MacroHard Word", "mword", "mword", "MWordWindow",
            pinned=True, exe_name="mword.exe", takes_node_id=True),
    AppSpec("calculator", "Calculator", "calculator", "calculator", "CalculatorWindow",
            pinned=True, exe_name="calc.exe"),
    AppSpec("paint", "Paint", "paint", "paint", "PaintWindow",
            pinned=True, exe_name="mspaint.exe", takes_node_id=True),
    AppSpec("photochop", "Adobo PhotoChop 7.0", "photochop", "photochop", "PhotoChopWindow",
            pinned=True, exe_name="photochop.exe", takes_node_id=True),
    AppSpec("minesweeper", "Minesweeper", "minesweeper", "minesweeper", "MinesweeperWindow",
            pinned=True, exe_name="winmine.exe"),
    AppSpec("control_panel", "Control Panel", "control_panel", "control_panel", "ControlPanelWindow",
            exe_name="control.exe"),
    AppSpec("task_manager", "Windows Task Manager", "task_manager", "task_manager", "TaskManagerWindow",
            exe_name="taskmgr.exe"),
    AppSpec("wmp", "Windows Media Player", "wmp", "wmp", "WindowsMediaPlayerWindow",
            pinned=True, exe_name="wmplayer.exe", takes_node_id=True),
    AppSpec("vscode", "Visual XP Code", "vscode", "visual_xp_code", "VisualXPCodeWindow",
            pinned=True, exe_name="Code.exe", takes_node_id=True),
]

BY_ID = {spec.id: spec for spec in APPS}
