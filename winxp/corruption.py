"""Global 'system health' state — cursed Task Manager kills degrade this instead
of crashing outright, so the OS limps along until it finally can't."""
from __future__ import annotations

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
