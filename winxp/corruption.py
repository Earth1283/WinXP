"""Global 'system health' state — cursed Task Manager kills degrade this instead
of crashing outright, so the OS limps along until it finally can't."""
from __future__ import annotations

import random

from PyQt6.QtCore import QObject, pyqtSignal


class SystemHealth(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.dead_procs: set[str] = set()

    @property
    def level(self) -> int:
        return len(self.dead_procs)

    def kill(self, name: str):
        self.dead_procs.add(name)
        self.changed.emit()

    def is_dead(self, name: str) -> bool:
        return name in self.dead_procs

    def reset(self):
        self.dead_procs.clear()
        self.changed.emit()


health = SystemHealth()

# Filenames under C:\WINDOWS\system32 (see vfs.SYSTEM32_SEED_FILES) that map
# straight to a bsod.STOP_CODES entry. These start read-only -- Properties
# has to clear that box first -- but once they're actually deleted, it's a
# real kernel/shell file gone, not just a process you can end and restart.
SYSTEM32_STOP_MAP = {
    "csrss.exe", "winlogon.exe", "smss.exe", "services.exe", "lsass.exe",
    "explorer.exe", "ntoskrnl.exe", "hal.dll", "kernel32.dll", "ntdll.dll",
    "win32k.sys",
    # The containers, not just the files inside -- batch-deleting the whole
    # WINDOWS folder (or system32, or the drive itself) takes every protected
    # file with it in one shot and is worse, not a loophole around them.
    "system32", "WINDOWS", "Local Disk (C:)",
}


def guard_system_file(wm, node) -> bool:
    """Call AFTER the delete already went through, with the node you just
    deleted. True means it was a protected system32 file and the OS just
    BSODed for real -- no cascading health check, straight to crash."""
    if node.name not in SYSTEM32_STOP_MAP:
        return False
    from .apps.bsod import crash
    crash(wm, node.name)
    return True


def guard_fs(wm) -> bool:
    """explorer.exe IS the shell -- once it's dead, any filesystem operation
    (opening a folder, new/rename/delete/move/properties) is blocked. Callers
    do `if corruption.guard_fs(self.wm): return` at the top of each
    fs-touching method; True means the operation didn't happen.

    Mostly this just freezes a window (same "Not Responding" limp as
    services.exe dying) rather than a guaranteed crash -- only a small,
    rising-with-damage chance actually BSODs, same ambient-odds shape as
    desktop.py's _glitch_tick for the other critical procs."""
    if not health.is_dead("explorer.exe"):
        return False
    if random.random() < 0.1 + 0.05 * health.level:
        from .apps.bsod import crash
        crash(wm, "explorer.exe")
        return True
    candidates = [
        w for w in wm.windows
        if w.isVisible() and getattr(w, "_app_key", None) != "task_manager"
    ]
    if candidates:
        random.choice(candidates).freeze(random.randint(1500, 3500))
    return True
