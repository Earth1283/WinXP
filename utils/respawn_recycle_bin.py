#!/usr/bin/env python3
"""PEBKAC recovery tool: respawns the Recycle Bin after you delete it (again).

Deleting the Recycle Bin is a real, supported (if cursed) feature of this
sim -- vfs.py won't stop you, and apps/__init__.py now BSODs instead of
crashing the process when something tries to open it afterward. This is the
"turn it off and on again" fix: point recycle_id at an orphaned "Recycle
Bin" folder if one's still sitting on the Desktop unlinked, or requisition
a fresh one from the storage pool if it's really gone.

Usage:
    python3 utils/respawn_recycle_bin.py
"""
from __future__ import annotations

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console

from winxp import vfs as vfs_mod
from winxp.vfs import vfs

console = Console()

EXCUSES = [
    "PSU couldn't supply enough inodes",
    "the bin was using the printer's SCSI terminator",
    "cosmic ray flipped a bit in the parent pointer",
    "someone in Marketing asked for it in Comic Sans",
    "backup was scheduled, tape robot was on lunch",
    "it's stuck in the upgrade to the new filing system",
]


def _bofh_log(msg, delay=0.35):
    console.print(msg)
    time.sleep(delay)


def main():
    vfs.load_or_init()
    _bofh_log("[bold]RECYCLE.SYS[/bold] :: incident ticket auto-filed.")
    _bofh_log(f"[dim]Root cause (per user): PEBKAC. Root cause (per BOFH): "
              f"{random.choice(EXCUSES)}.[/dim]")

    if vfs.get(vfs.recycle_id) is not None:
        _bofh_log("[green]Bin's actually fine.[/green] Have you tried closing "
                   "the ticket and not bothering me?")
        return

    orphan = next(
        (c for c in vfs.children_of(vfs.desktop_id)
         if c.name == "Recycle Bin" and c.kind == vfs_mod.FOLDER),
        None,
    )
    if orphan:
        vfs.recycle_id = orphan.id
        vfs.save()
        _bofh_log(f"[yellow]Found the old one behind the Desktop node[/yellow] "
                   f"({orphan.id}) -- reattaching it. This is coming out of "
                   f"your budget for next quarter.")
        return

    node = vfs.create_folder(vfs.desktop_id, "Recycle Bin")
    vfs.recycle_id = node.id
    vfs.save()
    _bofh_log(f"[cyan]Requisitioned a new bin from storage[/cyan] ({node.id}). "
              f"It is empty, unlike your excuse.")
    _bofh_log("Don't let it happen again. I've made a note of your name.")


if __name__ == "__main__":
    main()
