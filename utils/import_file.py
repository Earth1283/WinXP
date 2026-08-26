#!/usr/bin/env python3
"""Interactive importer: bring a real file from your actual filesystem into
the WinXP sim's vfs, without hand-editing ~/.winxp_sim/vfs.json.

Usage:
    python3 utils/import_file.py [path]

If path is omitted, you'll be prompted for one. Supports text files,
images (png/jpg/jpeg/bmp/gif -- converted to PNG, matching Paint's format),
and audio/video (copied as-is, original extension preserved).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from winxp import vfs as vfs_mod
from winxp.vfs import vfs

console = Console()

TEXT_EXTS = {".txt", ".md", ".log", ".ini", ".cfg", ".csv", ".json", ".py",
             ".c", ".cpp", ".h", ".js", ".html", ".xml", ".yaml", ".yml"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"}

KIND_LABELS = {
    vfs_mod.TEXT: "Text Document (Notepad)",
    vfs_mod.IMAGE: "Bitmap Image (Paint)",
    vfs_mod.AUDIO: "Audio (Media Player)",
    vfs_mod.VIDEO: "Video (Media Player)",
}


def detect_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTS:
        return vfs_mod.TEXT
    if ext in IMAGE_EXTS:
        return vfs_mod.IMAGE
    if ext in AUDIO_EXTS:
        return vfs_mod.AUDIO
    if ext in VIDEO_EXTS:
        return vfs_mod.VIDEO
    return None


def pick_folder(start_id):
    """Interactive folder browser rooted at start_id. Returns a folder id,
    or None if the user cancels."""
    current = start_id
    while True:
        node = vfs.get(current)
        children = [c for c in vfs.children_of(current) if c.kind == vfs_mod.FOLDER]

        console.print()
        console.print(Panel(f"[bold]{vfs.path_of(current)}[/bold]", style="blue", expand=False))
        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        table.add_column("#", width=3, justify="right")
        table.add_column("Folder")
        for i, c in enumerate(children, 1):
            table.add_row(str(i), f"[yellow]\U0001F4C1[/yellow] {c.name}")
        if children:
            console.print(table)
        else:
            console.print("[dim](no subfolders here)[/dim]")

        console.print(
            "[dim]number = open folder    s = import HERE    "
            "u = up a level    q = cancel[/dim]"
        )
        choices = [str(i) for i in range(1, len(children) + 1)] + ["s", "u", "q"]
        choice = Prompt.ask("Choice", choices=choices, show_choices=False)

        if choice == "q":
            return None
        if choice == "s":
            return current
        if choice == "u":
            if node.parent:
                current = node.parent
            continue
        current = children[int(choice) - 1].id


def import_text(path, folder_id, name):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return vfs.create_text_file(folder_id, name, content)


def import_image(path, folder_id, name):
    from PyQt6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])  # noqa: F841 -- must stay alive
    from PyQt6.QtGui import QPixmap
    pixmap = QPixmap(path)
    if pixmap.isNull():
        console.print("[bold red]Could not decode that image file.[/bold red]")
        sys.exit(1)
    from winxp import image_codec
    return vfs.create_image_file(folder_id, name, image_codec.to_bytes(pixmap))


def import_media(path, folder_id, name, kind):
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        data = f.read()
    if kind == vfs_mod.AUDIO:
        return vfs.create_audio_file(folder_id, name, data, ext)
    return vfs.create_video_file(folder_id, name, data, ext)


def main():
    vfs.load_or_init()

    console.rule("[bold blue]WinXP Sim — Import File[/bold blue]")

    raw_path = sys.argv[1] if len(sys.argv) > 1 else Prompt.ask("Real file path to import")
    path = os.path.abspath(os.path.expanduser(raw_path.strip()))

    if not os.path.isfile(path):
        console.print(f"[bold red]Not a file:[/bold red] {path}")
        sys.exit(1)

    kind = detect_kind(path)
    if kind is None:
        console.print(f"[bold red]Unrecognized extension:[/bold red] {os.path.splitext(path)[1] or '(none)'}")
        console.print("[dim]Supported: text, image (png/jpg/jpeg/bmp/gif), audio, video[/dim]")
        sys.exit(1)

    size = os.path.getsize(path)
    console.print(Panel.fit(
        f"[bold]{os.path.basename(path)}[/bold]\n"
        f"Kind: {KIND_LABELS[kind]}\n"
        f"Size: {size:,} bytes",
        title="File", style="green",
    ))

    name = Prompt.ask("Name in the sim", default=os.path.basename(path))

    console.print("\n[bold]Choose a destination folder:[/bold]")
    folder_id = pick_folder(vfs.desktop_id)
    if folder_id is None:
        console.print("[yellow]Cancelled.[/yellow]")
        return

    if not Confirm.ask(f"Import '{name}' into {vfs.path_of(folder_id)}?", default=True):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    if kind == vfs_mod.TEXT:
        node = import_text(path, folder_id, name)
    elif kind == vfs_mod.IMAGE:
        node = import_image(path, folder_id, name)
    else:
        node = import_media(path, folder_id, name, kind)

    console.print(Panel.fit(
        f"[bold green]Imported![/bold green]\n{vfs.path_of(folder_id)} \\ {node.name}",
        style="green",
    ))


if __name__ == "__main__":
    main()
