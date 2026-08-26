#!/usr/bin/env python3
"""Factory reset: wipes the entire simulated install (~/.winxp_sim -- vfs
tree, all file content, and settings.json) so the next launch reinitializes
from scratch, same as a first run.

This is the nuclear option. Deleting the Recycle Bin has its own targeted
fix (utils/respawn_recycle_bin.py) -- reach for that first. Use this when
things are wrong enough that starting over is easier than repairing state.

Usage:
    python3 utils/restore_os.py
"""
from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.prompt import Confirm

from winxp.vfs import STORE_DIR

console = Console()


def main():
    console.print("[bold]Windows Recovery Console[/bold]")
    console.print(f"Install directory: [cyan]{STORE_DIR}[/cyan]")

    if not os.path.exists(STORE_DIR):
        console.print("[green]Nothing to restore -- no install found (already factory-fresh).[/green]")
        return

    console.print(
        "[yellow]This permanently deletes every file, folder, and setting in the "
        "sim[/yellow] -- desktop, My Documents, My Music, Recycle Bin, wallpaper, "
        "sound scheme, all of it. This cannot be undone."
    )
    if not Confirm.ask("Continue?", default=False):
        console.print("Cancelled. Nothing was touched.")
        return

    shutil.rmtree(STORE_DIR)
    console.print(f"[green]Wiped {STORE_DIR}.[/green] Next launch reinitializes a fresh install.")


if __name__ == "__main__":
    main()
