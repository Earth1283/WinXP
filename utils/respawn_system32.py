#!/usr/bin/env python3
"""Self-service system file repair: puts missing C:\\WINDOWS\\system32 files
back after you (or the BSOD that followed) took one out for real.

Deleting a protected system32 file (winxp/vfs.py's SYSTEM32_SEED_FILES) is a
real, supported feature -- Properties clears the Read-only flag, and once
it's actually gone, corruption.guard_system_file() BSODs the machine on the
spot. This is the "sfc /scannow, but it actually works" self-service ticket,
same shape as utils/reinstall_apps.py for apps.

Usage:
    python3 utils/respawn_system32.py                # interactive picker
    python3 utils/respawn_system32.py csrss.exe hal.dll
    python3 utils/respawn_system32.py --all
"""
from __future__ import annotations

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from winxp import vfs as vfs_mod
from winxp.vfs import SYSTEM32_SEED_FILES, vfs

console = Console()


def _fake_progress(label: str):
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(label, total=100)
        pct = 0
        while pct < 100:
            pct = min(100, pct + random.randint(4, 14))
            progress.update(task, completed=pct)
            time.sleep(random.uniform(0.03, 0.09))


def _is_installed():
    """system32 only counts as installed if its ancestor chain reaches My
    Computer WITHOUT passing through the Recycle Bin. Reaching root_id alone
    proves nothing -- the Recycle Bin itself lives under Desktop under root,
    so an orphaned system32 (deleting the WINDOWS folder relinks it into the
    Recycle Bin instead of erasing it -- node and children survive untouched)
    still walks all the way up to root_id, which used to read as "installed"."""
    node = vfs.get(vfs.system32_id)
    seen = set()
    while node is not None and node.id not in seen:
        if node.id == vfs.recycle_id:
            return False
        if node.id == vfs.root_id:
            return True
        seen.add(node.id)
        node = vfs.get(node.parent) if node.parent else None
    return False


def _ensure_system32_folder():
    if _is_installed():
        return
    console.print("[yellow]C:\\WINDOWS\\system32 isn't reachable from My Computer.[/yellow] Rebuilding the whole folder.")
    root = vfs.get(vfs.root_id)
    vfs._seed_system32(root)
    vfs.save()


def _present_names():
    if not _is_installed():
        return set()
    sys32 = vfs.get(vfs.system32_id)
    return {vfs.get(c).name for c in sys32.children if vfs.get(c)}


def _status_table():
    present = _present_names()
    table = Table(title="System File Checker :: system32 Repair", header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("File", style="bold")
    table.add_column("Status")
    for i, name in enumerate(sorted(SYSTEM32_SEED_FILES), 1):
        status = "[green]Present[/green]" if name in present else "[red]Missing[/red]"
        table.add_row(str(i), name, status)
    return table


def _respawn(name: str) -> bool:
    if name not in SYSTEM32_SEED_FILES:
        console.print(f"[red]No such protected system32 file:[/red] {name}")
        return False
    if name in _present_names():
        console.print(f"[dim]{name} is already present. Closing ticket, no charge.[/dim]")
        return False
    _fake_progress(f"Restoring {name}...")
    node = vfs.create_text_file(vfs.system32_id, name, SYSTEM32_SEED_FILES[name])
    vfs.set_attributes(node.id, read_only=True)
    console.print(f"[green]Restored[/green] {name}")
    return True


def main():
    vfs.load_or_init()
    _ensure_system32_folder()
    args = sys.argv[1:]
    names = sorted(SYSTEM32_SEED_FILES)

    if "--all" in args:
        missing = [n for n in names if n not in _present_names()]
        if not missing:
            console.print("[dim]Nothing's missing. Ticket auto-resolved.[/dim]")
            return
        for name in missing:
            _respawn(name)
        console.print(f"\n[bold]{len(missing)} file(s) restored.[/bold]")
        return

    if args:
        changed = sum(_respawn(a) for a in args)
        console.print(f"\n[bold]{changed} file(s) restored.[/bold]")
        return

    console.print(_status_table())
    missing = [n for n in names if n not in _present_names()]
    if not missing:
        console.print("\n[dim]Nothing's missing. Ticket auto-resolved.[/dim]")
        return

    console.print(
        "\nEnter row numbers or filenames to restore (comma-separated), "
        "[bold]all[/bold], or blank to cancel."
    )
    choice = Prompt.ask("Restore", default="")
    if not choice.strip():
        console.print("[dim]Cancelled. Ticket left open.[/dim]")
        return

    if choice.strip().lower() == "all":
        targets = missing
    else:
        targets = []
        for token in choice.split(","):
            token = token.strip()
            if not token:
                continue
            if token.isdigit() and 1 <= int(token) <= len(names):
                targets.append(names[int(token) - 1])
            else:
                targets.append(token)

    changed = sum(_respawn(name) for name in targets)
    console.print(f"\n[bold]{changed} file(s) restored.[/bold]")


if __name__ == "__main__":
    main()
