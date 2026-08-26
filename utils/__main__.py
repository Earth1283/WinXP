#!/usr/bin/env python3
"""Central self-service hub for utils/ -- one directory, one entry point,
for managing and running every recovery tool without memorizing filenames.

Usage:
    python3 -m utils                        # interactive menu
    python3 -m utils <tool> [args...]        # run one directly, e.g.:
        python3 -m utils reinstall_apps calculator
        python3 -m utils respawn_system32 --all
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

HERE = os.path.dirname(os.path.abspath(__file__))
console = Console()

TOOLS = [
    ("reinstall_apps", "Reinstall Programs",
     "Put back apps removed via Add or Remove Programs."),
    ("respawn_system32", "Repair system32",
     "Restore missing/deleted C:\\WINDOWS\\system32 files."),
    ("respawn_recycle_bin", "Respawn Recycle Bin",
     "Recreate the Recycle Bin after you've deleted it (again)."),
    ("restore_os", "Factory Reset",
     "Wipe the whole sim profile and reinitialize from scratch. Destructive."),
    ("import_file", "Import a Real File",
     "Bring a file from your actual filesystem into the sim."),
]
NAMES = {name for name, _, _ in TOOLS}


def _run(name, extra_args=None):
    script = os.path.join(HERE, f"{name}.py")
    subprocess.run([sys.executable, script, *(extra_args or [])])


def _print_menu():
    table = Table(title="Self-Service Portal :: Recovery Tools", header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Tool", style="bold")
    table.add_column("Description")
    for i, (_, title, desc) in enumerate(TOOLS, 1):
        table.add_row(str(i), title, desc)
    console.print(table)


def _interactive():
    while True:
        _print_menu()
        choice = Prompt.ask("\nRun which tool (number, or blank to quit)", default="")
        if not choice.strip():
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(TOOLS)):
            console.print("[red]Invalid choice.[/red]\n")
            continue
        name, title, _ = TOOLS[int(choice) - 1]
        console.print(f"\n[bold]-- {title} --[/bold]\n")
        _run(name)
        console.print()


def main():
    args = sys.argv[1:]
    if args:
        name, extra = args[0], args[1:]
        if name not in NAMES:
            console.print(f"[red]Unknown tool:[/red] {name}")
            console.print(f"Available: {', '.join(sorted(NAMES))}")
            sys.exit(1)
        _run(name, extra)
        return
    _interactive()


if __name__ == "__main__":
    main()
