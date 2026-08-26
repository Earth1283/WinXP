#!/usr/bin/env python3
"""Self-service reinstall kiosk: put back apps you uninstalled from Add or
Remove Programs, one at a time or all at once, without reopening the sim.

Uninstalling in-app (winxp/apps/control_panel/programs.py) really removes
the app -- it's blocked in launch() and hidden from the Start Menu until
reinstalled. This is the "just fix it yourself" self-service ticket instead
of filing an IT request and waiting.

Usage:
    python3 utils/reinstall_apps.py                 # interactive picker
    python3 utils/reinstall_apps.py calculator paint # reinstall by id
    python3 utils/reinstall_apps.py --all            # reinstall everything
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

from winxp.app_registry import APPS, BY_ID
from winxp.settings import settings

console = Console()


def _fake_progress(label: str):
    # Cosmetic only -- the actual reinstall is one dict write. Nobody trusts
    # a fix that happens instantly.
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

TICKET = "SR-{:05d}".format(hash(tuple(sorted(settings.uninstalled_apps))) % 90000 + 10000)


def _status_table():
    table = Table(title="Self-Service Portal :: Application Reinstall", header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("App", style="bold")
    table.add_column("Id")
    table.add_column("Status")
    for i, spec in enumerate(APPS, 1):
        installed = settings.is_installed(spec.id)
        status = "[green]Installed[/green]" if installed else "[red]Not Installed[/red]"
        table.add_row(str(i), spec.title, spec.id, status)
    return table


def _reinstall(app_id: str) -> bool:
    spec = BY_ID.get(app_id)
    if spec is None:
        console.print(f"[red]No such app id:[/red] {app_id}")
        return False
    if settings.is_installed(app_id):
        console.print(f"[dim]{spec.title} is already installed. Closing ticket, no charge.[/dim]")
        return False
    _fake_progress(f"Reinstalling {spec.title}...")
    settings.set_app_installed(app_id, True)
    console.print(f"[green]Reinstalled[/green] {spec.title} ({spec.exe()})")
    return True


def main():
    args = sys.argv[1:]

    if "--all" in args:
        missing = [s.id for s in APPS if not settings.is_installed(s.id)]
        if not missing:
            console.print("[dim]Nothing's missing. Ticket auto-resolved.[/dim]")
            return
        for app_id in missing:
            _reinstall(app_id)
        console.print(f"\n[bold]Ticket {TICKET} closed.[/bold] {len(missing)} app(s) restored.")
        return

    if args:
        changed = 0
        for app_id in args:
            if _reinstall(app_id):
                changed += 1
        console.print(f"\n[bold]Ticket {TICKET} closed.[/bold] {changed} app(s) restored.")
        return

    console.print(_status_table())
    missing = [s for s in APPS if not settings.is_installed(s.id)]
    if not missing:
        console.print("\n[dim]Nothing's missing. Ticket auto-resolved.[/dim]")
        return

    console.print(
        "\nEnter row numbers or ids to reinstall (comma-separated), "
        "[bold]all[/bold], or blank to cancel."
    )
    choice = Prompt.ask("Reinstall", default="")
    if not choice.strip():
        console.print("[dim]Cancelled. Ticket left open.[/dim]")
        return

    if choice.strip().lower() == "all":
        targets = [s.id for s in missing]
    else:
        targets = []
        for token in choice.split(","):
            token = token.strip()
            if not token:
                continue
            if token.isdigit() and 1 <= int(token) <= len(APPS):
                targets.append(APPS[int(token) - 1].id)
            else:
                targets.append(token)

    changed = sum(_reinstall(app_id) for app_id in targets)
    console.print(f"\n[bold]Ticket {TICKET} closed.[/bold] {changed} app(s) restored.")


if __name__ == "__main__":
    main()
