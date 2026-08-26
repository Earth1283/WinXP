"""In-memory virtual filesystem for the XP simulator, persisted to disk in
the user's home dir so state survives restarts.

vfs.json holds only the tree structure (names, kinds, parent/child links) --
it stays tiny no matter how much is saved. Actual file content (Notepad text,
WordPad HTML, Paint PNGs) lives as individual files in ntfs/<node_id>.<ext>,
one per node, so saving one file never rewrites every other file's data.

This is a *simulated* filesystem entirely separate from the host OS's real
files -- apps inside the sim only ever read/write nodes in this tree.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

STORE_DIR = os.path.expanduser("~/.winxp_sim")
STORE_PATH = os.path.join(STORE_DIR, "vfs.json")
CONTENT_DIR = os.path.join(STORE_DIR, "ntfs")

FOLDER = "folder"
TEXT = "text"          # Notepad plain text file
RICH = "rich"          # WordPad rich text (HTML) file
IMAGE = "image"        # Paint bitmap file (PNG)
AUDIO = "audio"        # Media Player track (extension varies per imported file)
VIDEO = "video"        # Media Player clip (extension varies per imported file)
SHORTCUT = "shortcut"  # desktop shortcut to an app

CONTENT_EXT = {TEXT: ".txt", RICH: ".html", IMAGE: ".png"}


@dataclass
class Node:
    id: str
    name: str
    kind: str
    parent: Optional[str] = None
    children: list = field(default_factory=list)   # for folders: list of ids
    icon: str = ""                                   # icon key
    target: str = ""                                  # for shortcuts: app id
    ext: str = ""                                      # content file extension override (AUDIO)
    created: float = field(default_factory=time.time)
    modified: float = field(default_factory=time.time)

    def to_dict(self):
        return dict(
            id=self.id, name=self.name, kind=self.kind, parent=self.parent,
            children=list(self.children), icon=self.icon, target=self.target,
            ext=self.ext, created=self.created, modified=self.modified,
        )

    @staticmethod
    def from_dict(d):
        d.setdefault("ext", "")
        return Node(**d)


class VFS:
    """A simple tree filesystem with folders and files, backed by dict of id->Node.

    File content is not held in memory or in the tree JSON -- it's read from
    / written to CONTENT_DIR on demand via read_content/write_content
    (text) or read_blob/write_blob (binary).
    """

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.root_id: str = ""
        self.desktop_id: str = ""
        self.my_docs_id: str = ""
        self.my_music_id: str = ""
        self.recycle_id: str = ""

    # -- bootstrap ---------------------------------------------------
    def load_or_init(self):
        if os.path.exists(STORE_PATH):
            try:
                self._load()
                return
            except Exception:
                pass
        self._init_default()
        self.save()

    def _init_default(self):
        self.nodes = {}
        root = self._new(FOLDER, "My Computer", None)
        self.root_id = root.id

        desktop = self._new(FOLDER, "Desktop", root.id)
        self.desktop_id = desktop.id
        root.children.append(desktop.id)

        my_docs = self._new(FOLDER, "My Documents", desktop.id)
        self.my_docs_id = my_docs.id
        desktop.children.append(my_docs.id)

        my_music = self._new(FOLDER, "My Music", desktop.id)
        self.my_music_id = my_music.id
        desktop.children.append(my_music.id)

        recycle = self._new(FOLDER, "Recycle Bin", desktop.id)
        self.recycle_id = recycle.id
        desktop.children.append(recycle.id)

        readme = self._new(TEXT, "Welcome.txt", my_docs.id)
        my_docs.children.append(readme.id)
        self.write_content(readme.id, (
            "Welcome to Microsoft Windows XP\r\n\r\n"
            "Tips for getting started:\r\n"
            "  - Double-click an icon to open it.\r\n"
            "  - Right-click the desktop or any file for more options.\r\n"
            "  - Click Start to browse your programs and files.\r\n\r\n"
            "Thank you for choosing Windows XP.\r\n"
        ))

        # Desktop shortcuts
        for name, target, icon in [
            ("My Computer", "explorer:root", "my_computer"),
            ("Internet Explorer", "app:ie", "ie"),
            ("Minesweeper", "app:minesweeper", "minesweeper"),
            ("Notepad", "app:notepad", "notepad"),
        ]:
            sc = self._new(SHORTCUT, name, desktop.id, target=target, icon=icon)
            desktop.children.append(sc.id)

        self._seed_sample_media()

    def _new(self, kind, name, parent, icon="", target="", ext=""):
        node = Node(id=str(uuid.uuid4())[:8], name=name, kind=kind,
                    parent=parent, icon=icon, target=target, ext=ext)
        self.nodes[node.id] = node
        return node

    # -- persistence ---------------------------------------------------
    def save(self):
        os.makedirs(STORE_DIR, exist_ok=True)
        data = {
            "root_id": self.root_id,
            "desktop_id": self.desktop_id,
            "my_docs_id": self.my_docs_id,
            "my_music_id": self.my_music_id,
            "recycle_id": self.recycle_id,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
        }
        tmp = STORE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, STORE_PATH)

    def _load(self):
        with open(STORE_PATH) as f:
            data = json.load(f)
        self.root_id = data["root_id"]
        self.desktop_id = data["desktop_id"]
        self.my_docs_id = data["my_docs_id"]
        self.my_music_id = data.get("my_music_id", "")
        self.recycle_id = data["recycle_id"]
        self.nodes = {}
        migrated = False
        for k, v in data["nodes"].items():
            legacy_content = v.pop("content", None)
            node = Node.from_dict(v)
            self.nodes[k] = node
            if legacy_content:
                self._migrate_legacy_content(node, legacy_content)
                migrated = True
        if not self.my_music_id:
            # migrating from a version without a My Music folder
            music = self._new(FOLDER, "My Music", self.desktop_id)
            self.my_music_id = music.id
            self.get(self.desktop_id).children.append(music.id)
            migrated = True
        if migrated:
            self.save()
        self._seed_sample_media()

    def _seed_sample_media(self):
        """Give Media Player something real to play without ever reaching
        outside ~/.winxp_sim -- no-ops once My Music already has content."""
        if any(c.kind in (AUDIO, VIDEO) for c in self.children_of(self.my_music_id)):
            return
        from . import sample_media
        for name, make in (("Chimes.wav", sample_media.chime),
                            ("Sample Music.wav", sample_media.sample_tune)):
            self.create_audio_file(self.my_music_id, name, make(), ".wav")

    def _migrate_legacy_content(self, node, legacy_content):
        """One-time upgrade from the old scheme where content lived inline
        in vfs.json (as plain text, or base64 PNG for images)."""
        os.makedirs(CONTENT_DIR, exist_ok=True)
        if node.kind == IMAGE:
            import base64
            try:
                data = base64.b64decode(legacy_content)
            except Exception:
                return
            self.write_blob(node.id, data)
        else:
            self.write_content(node.id, legacy_content)

    # -- content store ---------------------------------------------------
    def content_path(self, node_id) -> str:
        """Real path on disk holding this node's content -- usable directly
        by things that need a real file path, like QMediaPlayer."""
        node = self.get(node_id)
        ext = (node.ext if node else "") or CONTENT_EXT.get(node.kind if node else "", ".dat")
        return os.path.join(CONTENT_DIR, node_id + ext)

    def read_content(self, node_id) -> str:
        try:
            with open(self.content_path(node_id), "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def write_content(self, node_id, content: str):
        node = self.get(node_id)
        if not node:
            return
        os.makedirs(CONTENT_DIR, exist_ok=True)
        with open(self.content_path(node_id), "w", encoding="utf-8") as f:
            f.write(content)
        node.modified = time.time()
        self.save()

    def read_blob(self, node_id) -> bytes:
        try:
            with open(self.content_path(node_id), "rb") as f:
                return f.read()
        except FileNotFoundError:
            return b""

    def write_blob(self, node_id, data: bytes):
        node = self.get(node_id)
        if not node:
            return
        os.makedirs(CONTENT_DIR, exist_ok=True)
        with open(self.content_path(node_id), "wb") as f:
            f.write(data)
        node.modified = time.time()
        self.save()

    def _delete_content_file(self, node_id):
        try:
            os.remove(self.content_path(node_id))
        except FileNotFoundError:
            pass

    # -- operations ---------------------------------------------------
    def get(self, node_id) -> Optional[Node]:
        return self.nodes.get(node_id)

    def children_of(self, node_id) -> list[Node]:
        node = self.get(node_id)
        if not node:
            return []
        return [self.nodes[c] for c in node.children if c in self.nodes]

    def path_of(self, node_id) -> str:
        parts = []
        n = self.get(node_id)
        while n and n.parent:
            parts.append(n.name)
            n = self.get(n.parent)
        parts.append("My Computer")
        return " \\ ".join(reversed(parts))

    def create_folder(self, parent_id, name="New Folder"):
        parent = self.get(parent_id)
        name = self._unique_name(parent_id, name)
        node = self._new(FOLDER, name, parent_id)
        parent.children.append(node.id)
        self.save()
        return node

    def create_text_file(self, parent_id, name="New Text Document.txt", content=""):
        parent = self.get(parent_id)
        name = self._unique_name(parent_id, name)
        node = self._new(TEXT, name, parent_id)
        parent.children.append(node.id)
        self.save()
        if content:
            self.write_content(node.id, content)
        return node

    def create_image_file(self, parent_id, name="Untitled.png", data: bytes = b""):
        parent = self.get(parent_id)
        name = self._unique_name(parent_id, name)
        node = self._new(IMAGE, name, parent_id)
        parent.children.append(node.id)
        self.save()
        if data:
            self.write_blob(node.id, data)
        return node

    def create_audio_file(self, parent_id, name, data: bytes, ext):
        return self._create_media_file(AUDIO, parent_id, name, data, ext)

    def create_video_file(self, parent_id, name, data: bytes, ext):
        return self._create_media_file(VIDEO, parent_id, name, data, ext)

    def _create_media_file(self, kind, parent_id, name, data: bytes, ext):
        parent = self.get(parent_id)
        name = self._unique_name(parent_id, name)
        node = self._new(kind, name, parent_id, ext=ext)
        parent.children.append(node.id)
        self.save()
        if data:
            self.write_blob(node.id, data)
        return node

    def _unique_name(self, parent_id, name):
        existing = {c.name for c in self.children_of(parent_id)}
        if name not in existing:
            return name
        base, dot, ext = name.partition(".")
        i = 2
        while True:
            candidate = f"{base} ({i}){dot}{ext}"
            if candidate not in existing:
                return candidate
            i += 1

    def rename(self, node_id, new_name):
        node = self.get(node_id)
        if node:
            node.name = new_name
            node.modified = time.time()
            self.save()

    def delete(self, node_id, permanent=False):
        node = self.get(node_id)
        if not node:
            return
        if not permanent and node.parent != self.recycle_id and node_id != self.recycle_id:
            self.move(node_id, self.recycle_id)
            return
        parent = self.get(node.parent) if node.parent else None
        if parent and node_id in parent.children:
            parent.children.remove(node_id)

        def _rm(nid):
            n = self.nodes.get(nid)
            if n:
                self._delete_content_file(nid)
                self.nodes.pop(nid, None)
                for c in list(n.children):
                    _rm(c)
        _rm(node_id)
        self.save()

    def move(self, node_id, new_parent_id):
        node = self.get(node_id)
        old_parent = self.get(node.parent) if node.parent else None
        if old_parent and node_id in old_parent.children:
            old_parent.children.remove(node_id)
        new_parent = self.get(new_parent_id)
        node.name = self._unique_name(new_parent_id, node.name)
        new_parent.children.append(node_id)
        node.parent = new_parent_id
        node.modified = time.time()
        self.save()


vfs = VFS()
