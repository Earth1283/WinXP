"""In-memory virtual filesystem for the XP simulator, persisted to a JSON
file on the real disk (in the user's home dir) so state survives restarts.

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

STORE_PATH = os.path.expanduser("~/.winxp_sim/vfs.json")

FOLDER = "folder"
TEXT = "text"          # Notepad plain text file
RICH = "rich"          # WordPad rich text file
SHORTCUT = "shortcut"  # desktop shortcut to an app


@dataclass
class Node:
    id: str
    name: str
    kind: str
    parent: Optional[str] = None
    children: list = field(default_factory=list)   # for folders: list of ids
    content: str = ""                               # for text/rich files
    icon: str = ""                                   # icon key
    target: str = ""                                  # for shortcuts: app id
    created: float = field(default_factory=time.time)
    modified: float = field(default_factory=time.time)

    def to_dict(self):
        return dict(
            id=self.id, name=self.name, kind=self.kind, parent=self.parent,
            children=list(self.children), content=self.content,
            icon=self.icon, target=self.target,
            created=self.created, modified=self.modified,
        )

    @staticmethod
    def from_dict(d):
        return Node(**d)


class VFS:
    """A simple tree filesystem with folders and files, backed by dict of id->Node."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.root_id: str = ""
        self.desktop_id: str = ""
        self.my_docs_id: str = ""
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

        recycle = self._new(FOLDER, "Recycle Bin", desktop.id)
        self.recycle_id = recycle.id
        desktop.children.append(recycle.id)

        readme = self._new(
            TEXT, "Welcome.txt", my_docs.id,
            content=(
                "Welcome to Windows XP (Simulated Edition)!\r\n\r\n"
                "This is a fully playable desktop environment built with PyQt.\r\n"
                "Double-click icons to open them, right click for context menus,\r\n"
                "and explore the Start Menu for more applications.\r\n\r\n"
                "Have fun!\r\n"
            ),
        )
        my_docs.children.append(readme.id)

        # Desktop shortcuts
        for name, target, icon in [
            ("My Computer", "explorer:root", "my_computer"),
            ("Internet Explorer", "app:ie", "ie"),
            ("Minesweeper", "app:minesweeper", "minesweeper"),
            ("Notepad", "app:notepad", "notepad"),
        ]:
            sc = self._new(SHORTCUT, name, desktop.id, target=target, icon=icon)
            desktop.children.append(sc.id)

    def _new(self, kind, name, parent, content="", icon="", target=""):
        node = Node(id=str(uuid.uuid4())[:8], name=name, kind=kind,
                    parent=parent, content=content, icon=icon, target=target)
        self.nodes[node.id] = node
        return node

    # -- persistence ---------------------------------------------------
    def save(self):
        os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
        data = {
            "root_id": self.root_id,
            "desktop_id": self.desktop_id,
            "my_docs_id": self.my_docs_id,
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
        self.recycle_id = data["recycle_id"]
        self.nodes = {k: Node.from_dict(v) for k, v in data["nodes"].items()}

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
        node = self._new(TEXT, name, parent_id, content=content)
        parent.children.append(node.id)
        self.save()
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
            n = self.nodes.pop(nid, None)
            if n:
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

    def write_content(self, node_id, content):
        node = self.get(node_id)
        if node:
            node.content = content
            node.modified = time.time()
            self.save()


vfs = VFS()
