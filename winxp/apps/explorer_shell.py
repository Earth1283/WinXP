"""Shell-level naming, formatting and sorting rules shared by every Explorer
surface (icon views, Details columns, task pane, status bar, folder tree).

Windows Explorer never showed a raw node the way the vfs stores it -- names,
type strings, sizes, dates and group headings all go through the shell first.
Keeping that translation in one module means the Details view, the Tiles view
and the Properties-style task pane can't drift from each other.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap

from .. import icons, vfs as vfs_mod

NODE_MIME = "application/x-winxp-node-ids"

KIND_ICONS = {
    vfs_mod.FOLDER: "folder",
    vfs_mod.TEXT: "text_file",
    vfs_mod.RICH: "mword",
    vfs_mod.IMAGE: "bitmap_file",
    vfs_mod.AUDIO: "audio_file",
    vfs_mod.VIDEO: "video_file",
}

DRIVE_ICONS = {
    vfs_mod.DRIVE_FIXED: "drive_fixed",
    vfs_mod.DRIVE_FLOPPY: "drive_floppy",
    vfs_mod.DRIVE_CDROM: "drive_cdrom",
}

KIND_TYPES = {
    vfs_mod.FOLDER: "File Folder",
    vfs_mod.TEXT: "Text Document",
    vfs_mod.RICH: "Rich Text Document",
    vfs_mod.IMAGE: "Bitmap Image",
    vfs_mod.AUDIO: "Audio File",
    vfs_mod.VIDEO: "Video Clip",
    vfs_mod.SHORTCUT: "Shortcut",
}

# XP resolved the type string from the extension, not from what wrote the file.
EXT_TYPES = {
    ".txt": "Text Document", ".log": "Text Document", ".ini": "Configuration Settings",
    ".rtf": "Rich Text Document", ".doc": "Microsoft Word Document",
    ".bmp": "Bitmap Image", ".png": "PNG Image", ".jpg": "JPEG Image",
    ".jpeg": "JPEG Image", ".gif": "GIF Image",
    ".wav": "Wave Sound", ".mp3": "MP3 Format Sound", ".wma": "Windows Media Audio file",
    ".mid": "MIDI Sequence",
    ".avi": "Video Clip", ".mpg": "Movie Clip", ".mpeg": "Movie Clip",
    ".wmv": "Windows Media Audio/Video file", ".mp4": "Video Clip",
    ".exe": "Application", ".dll": "Application Extension", ".sys": "System file",
    ".lnk": "Shortcut", ".html": "HTML Document", ".htm": "HTML Document",
}

_THUMB_CACHE: dict[tuple, QPixmap] = {}


def is_drive(node) -> bool:
    return bool(node) and bool(node.drive)


def has_media(node) -> bool:
    """A removable volume with nothing in the bay -- opening it is an error."""
    return not (node.drive in (vfs_mod.DRIVE_FLOPPY, vfs_mod.DRIVE_CDROM))


def icon_key(node) -> str:
    if node.drive:
        return DRIVE_ICONS.get(node.drive, "drive_fixed")
    if node.kind == vfs_mod.SHORTCUT:
        return node.icon or "text_file"
    if node.id == vfs_mod.vfs.root_id:
        return "my_computer"
    if node.id == vfs_mod.vfs.my_docs_id:
        return "my_documents"
    if node.id == vfs_mod.vfs.recycle_id:
        return "recycle_bin_full" if vfs_mod.vfs.children_of(node.id) else "recycle_bin"
    return KIND_ICONS.get(node.kind, "text_file")


def shell_icon(node, size: int = 32) -> QIcon:
    if node.kind == vfs_mod.SHORTCUT:
        return icons.shortcut_icon(icon_key(node), size)
    return icons.icon(icon_key(node), size)


def thumbnail(node, size: int = 96) -> QPixmap:
    """Thumbnails view: real pixels for image files, the plain shell icon for
    everything else -- exactly what XP fell back to when it had no preview."""
    key = (node.id, size, node.modified)
    cached = _THUMB_CACHE.get(key)
    if cached is not None:
        return cached
    pm = QPixmap()
    if node.kind == vfs_mod.IMAGE:
        pm.loadFromData(vfs_mod.vfs.read_blob(node.id))
    if pm.isNull():
        pm = shell_icon(node, size).pixmap(size, size)
    else:
        from PyQt6.QtCore import Qt
        pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    _THUMB_CACHE[key] = pm
    return pm


def type_label(node) -> str:
    if node.drive:
        return vfs_mod.DRIVE_TYPE_LABELS.get(node.drive, "Local Disk")
    if node.kind == vfs_mod.FOLDER:
        return "File Folder"
    if node.kind == vfs_mod.SHORTCUT:
        return "Shortcut"
    dot = node.name.rfind(".")
    if dot > 0:
        label = EXT_TYPES.get(node.name[dot:].lower())
        if label:
            return label
        return node.name[dot + 1:].upper() + " File"
    return KIND_TYPES.get(node.kind, "File")


def size_of(node) -> int:
    """Folders and drives report no size in Details, same as the real shell."""
    if node.kind in (vfs_mod.FOLDER, vfs_mod.SHORTCUT) or node.drive:
        return 0
    return vfs_mod.vfs.size_of(node.id)


def format_kb(n: int) -> str:
    """Details' Size column: whole kilobytes, rounded up, never bytes."""
    return f"{(n + 1023) // 1024:,} KB"


def format_bytes(n: int) -> str:
    """Status bar / task pane: the friendly unit XP picked per magnitude."""
    if n < 1024:
        return "1 byte" if n == 1 else f"{n} bytes"
    for unit, div in (("KB", 1024), ("MB", 1024 ** 2), ("GB", 1024 ** 3)):
        if n < div * 1024 or unit == "GB":
            value = n / div
            return f"{value:,.0f} {unit}" if value >= 100 else f"{value:,.2f} {unit}"
    return f"{n} bytes"


def format_date(ts: float) -> str:
    if not ts:
        return ""
    t = time.localtime(ts)
    hour = t.tm_hour % 12 or 12
    ampm = "AM" if t.tm_hour < 12 else "PM"
    return f"{t.tm_mon}/{t.tm_mday}/{t.tm_year} {hour}:{t.tm_min:02d} {ampm}"


def shell_path(node_id) -> str:
    r"""What the Address bar shows. Anything on a volume gets a real path
    (C:\WINDOWS\system32); the shell-only folders above the drives show their
    display name alone (My Documents), which is what XP did rather than
    exposing Desktop\My Documents."""
    vfs = vfs_mod.vfs
    node = vfs.get(node_id)
    if not node:
        return ""
    if node_id == vfs.root_id:
        return "My Computer"
    parts = []
    n = node
    while n:
        if n.drive:
            letter = n.name[n.name.rfind("(") + 1: n.name.rfind(")")] if "(" in n.name else "C:"
            return letter + "\\" + "\\".join(reversed(parts))
        if n.id in (vfs.desktop_id, vfs.root_id):
            break
        parts.append(n.name)
        n = vfs.get(n.parent) if n.parent else None
    return "\\".join(reversed(parts)) or node.name


# -- sorting & grouping ---------------------------------------------------
# Column ids are stable strings so the View menu, the Details header and the
# "Arrange Icons by" menu can all talk about the same sort without a lookup.
COL_NAME = "name"
COL_SIZE = "size"
COL_TYPE = "type"
COL_MODIFIED = "modified"
COL_ORIGIN = "origin"
COL_DELETED = "deleted"
COL_TOTAL = "total"
COL_FREE = "free"
COL_COMMENTS = "comments"
COL_INFOLDER = "infolder"

COLUMN_LABELS = {
    COL_NAME: "Name", COL_SIZE: "Size", COL_TYPE: "Type",
    COL_MODIFIED: "Date Modified", COL_ORIGIN: "Original Location",
    COL_DELETED: "Date Deleted", COL_TOTAL: "Total Size", COL_FREE: "Free Space",
    COL_COMMENTS: "Comments", COL_INFOLDER: "In Folder",
}

COLUMN_WIDTHS = {
    COL_NAME: 190, COL_SIZE: 70, COL_TYPE: 130, COL_MODIFIED: 125,
    COL_ORIGIN: 175, COL_DELETED: 125, COL_TOTAL: 80, COL_FREE: 80,
    COL_COMMENTS: 160, COL_INFOLDER: 175,
}

SIZE_BANDS = [
    (10 * 1024, "Tiny (0 - 10 KB)"),
    (100 * 1024, "Small (10 - 100 KB)"),
    (1024 ** 2, "Medium (100 KB - 1 MB)"),
    (16 * 1024 ** 2, "Large (1 - 16 MB)"),
    (128 * 1024 ** 2, "Huge (16 - 128 MB)"),
]


def column_text(node, column) -> str:
    if column == COL_NAME:
        return vfs_mod.display_name(node)
    if column == COL_SIZE:
        n = size_of(node)
        return format_kb(n) if n or node.kind not in (vfs_mod.FOLDER, vfs_mod.SHORTCUT) else ""
    if column == COL_TYPE:
        return type_label(node)
    if column == COL_MODIFIED:
        return format_date(node.modified)
    if column == COL_ORIGIN:
        parent = vfs_mod.vfs.get(node.deleted_from)
        return shell_path(parent.id) if parent else ""
    if column == COL_INFOLDER:
        parent = vfs_mod.vfs.get(node.parent) if node.parent else None
        return shell_path(parent.id) if parent else ""
    if column == COL_DELETED:
        return format_date(node.deleted_at)
    if column in (COL_TOTAL, COL_FREE):
        used, total = vfs_mod.vfs.drive_usage(node.id)
        if not total:
            return ""
        return format_bytes(total if column == COL_TOTAL else total - used)
    return ""


def sort_key(node, column):
    """Folders always sort above files, ascending or descending -- the shell
    sorted within groups of kind, it never interleaved them."""
    folder_first = 0 if node.kind == vfs_mod.FOLDER or node.drive else 1
    if column == COL_SIZE:
        return (folder_first, size_of(node), node.name.lower())
    if column == COL_TYPE:
        return (folder_first, type_label(node).lower(), node.name.lower())
    if column == COL_MODIFIED:
        return (folder_first, node.modified, node.name.lower())
    if column == COL_DELETED:
        return (folder_first, node.deleted_at, node.name.lower())
    if column in (COL_ORIGIN, COL_INFOLDER):
        return (folder_first, column_text(node, column).lower(), node.name.lower())
    if column in (COL_TOTAL, COL_FREE):
        used, total = vfs_mod.vfs.drive_usage(node.id)
        return (folder_first, total - used if column == COL_FREE else total, node.name.lower())
    return (folder_first, node.name.lower())


def group_heading(node, column) -> str:
    if column == COL_TYPE:
        return type_label(node)
    if column == COL_SIZE:
        if node.kind == vfs_mod.FOLDER or node.drive:
            return "Folders"
        n = size_of(node)
        for limit, label in SIZE_BANDS:
            if n < limit:
                return label
        return "Gigantic (>128 MB)"
    if column in (COL_MODIFIED, COL_DELETED):
        ts = node.modified if column == COL_MODIFIED else node.deleted_at
        return _age_heading(ts)
    first = vfs_mod.display_name(node)[:1].upper()
    if first.isdigit():
        return "0 - 9"
    return first if first.isalpha() else "Other"


def _age_heading(ts: float) -> str:
    if not ts:
        return "Unspecified"
    now = time.time()
    days = (now - ts) / 86400
    today = time.localtime(now).tm_yday
    if days < 1:
        return "Today"
    if days < 2:
        return "Yesterday"
    if days < 7:
        return "Last week"
    if days < 14:
        return "Two weeks ago"
    if days < 21:
        return "Three weeks ago"
    if time.localtime(ts).tm_mon == time.localtime(now).tm_mon and days < today:
        return "Earlier this month"
    if time.localtime(ts).tm_year == time.localtime(now).tm_year:
        return "Earlier this year"
    return "A long time ago"


def visible_children(folder_id, sort_column=COL_NAME, descending=False):
    from ..settings import settings
    children = [n for n in vfs_mod.vfs.children_of(folder_id)
                if not n.hidden or settings.show_hidden]
    children.sort(key=lambda n: sort_key(n, sort_column), reverse=descending)
    if descending:
        # Reversing flips the folders-first rule back on its head; re-apply it.
        children.sort(key=lambda n: 0 if (n.kind == vfs_mod.FOLDER or n.drive) else 1)
    return children


class _ShellNotifier(QObject):
    """One shell, many views. Any window that changes the vfs emits changed;
    every Explorer window and the desktop itself repaint from it, so a file
    created in one window shows up everywhere without polling."""
    changed = pyqtSignal()


shell_notifier = _ShellNotifier()
