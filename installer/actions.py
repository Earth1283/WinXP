"""Install/Reinstall/Wipe/Repair -- a real standalone installer with no
static dependency on the winxp package, because it doesn't exist on disk
yet when this runs. Fetches the actual sim straight from GitHub
(Earth1283/WinXP, main branch) as a zip via stdlib urllib -- no git, no pip
install, matching the eventual Nuitka-compiled native binary having zero
runtime dependencies beyond PyQt6 itself.
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

import components

REPO_ZIP_URL = "https://github.com/Earth1283/WinXP/archive/refs/heads/main.zip"
INSTALL_DIR = os.path.expanduser("~/WindowsXP")
PROFILE_DIR = os.path.expanduser("~/.winxp_sim")  # matches winxp.vfs.STORE_DIR
MARKER = "main.py"  # its presence at INSTALL_DIR's root means "app is installed"


def has_app_files() -> bool:
    return os.path.exists(os.path.join(INSTALL_DIR, MARKER))


def has_profile_data() -> bool:
    """True if ~/.winxp_sim holds real user data (vfs.json). Running main.py
    straight from a git checkout -- common on macOS/Linux dev setups --
    populates this without ever creating INSTALL_DIR, so it has to be
    checked independently of has_app_files()."""
    return os.path.exists(os.path.join(PROFILE_DIR, "vfs.json"))


def is_installed() -> bool:
    return has_app_files() or has_profile_data()


def _download(url, dest_path, on_progress=None):
    req = urllib.request.Request(url, headers={"User-Agent": "WinXP-Installer"})
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        read = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out.write(chunk)
            read += len(chunk)
            if on_progress:
                if total:
                    on_progress(min(99, int(read * 100 / total)))
                else:
                    # GitHub's codeload zip is chunked, no Content-Length --
                    # fake an asymptotic creep so the bar visibly moves
                    # instead of sitting frozen for however long this takes.
                    on_progress(min(99, int(99 * (1 - math.exp(-read / 300_000)))))
    if on_progress:
        on_progress(100)


def _download_and_extract(dest: str, on_progress=None, on_file=None):
    """Downloads the repo zip and unpacks it straight into dest (dest ends
    up holding main.py, winxp/, utils/, etc. directly -- not nested inside
    the extra WinXP-main/ folder GitHub's zip wraps everything in).

    Files are copied one at a time rather than moved wholesale so Setup can
    name each one as it lands, the way the file-copy phase always did."""
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "winxp.zip")
        _download(REPO_ZIP_URL, zip_path, on_progress)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        extracted = next(
            os.path.join(tmp, d) for d in os.listdir(tmp)
            if os.path.isdir(os.path.join(tmp, d))
        )
        os.makedirs(dest, exist_ok=True)
        for name in os.listdir(extracted):
            _copy_tree(os.path.join(extracted, name), os.path.join(dest, name),
                       dest, on_file)


def _copy_tree(src, dst, root, on_file=None):
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for name in sorted(os.listdir(src)):
            _copy_tree(os.path.join(src, name), os.path.join(dst, name), root, on_file)
        return
    if os.path.exists(dst) or os.path.islink(dst):
        if os.path.isdir(dst) and not os.path.islink(dst):
            shutil.rmtree(dst)
        else:
            os.remove(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    if on_file:
        on_file(os.path.relpath(dst, root))


def count_files(dest: str) -> int:
    return sum(len(files) for _, _, files in os.walk(dest))


def _resolve_selection(selection):
    if selection is None:
        selection = components.read_manifest(INSTALL_DIR) or components.default_selection()
    return components.prune_orphans(selection)


def install(selection=None, on_progress=None, on_file=None):
    """Fetches the app when it's missing -- or when the selection asks for a
    component that isn't on disk -- then makes the tree match the selection.

    Adding a component back needs its source files, which a stub replaced, so
    that case re-fetches too. ~/.winxp_sim is left alone either way; the app
    initializes its own profile the first time main.py actually runs."""
    selection = _resolve_selection(selection)
    stored = components.read_manifest(INSTALL_DIR)
    adding = stored is None or not selection.issubset(stored)
    if not has_app_files() or adding:
        _download_and_extract(INSTALL_DIR, on_progress, on_file)
    return _configure(selection, on_file)


def reinstall(selection=None, on_progress=None, on_file=None):
    """Wipe app + data, fetch fresh. Destructive."""
    selection = _resolve_selection(selection)
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    shutil.rmtree(PROFILE_DIR, ignore_errors=True)
    _download_and_extract(INSTALL_DIR, on_progress, on_file)
    return _configure(selection, on_file)


def wipe():
    """Remove the app and all data. Nothing gets fetched back -- a real
    uninstall, not a reset. Destructive."""
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    shutil.rmtree(PROFILE_DIR, ignore_errors=True)


def _configure(selection, on_file=None):
    """Apply a component selection to the freshly-laid-down tree."""
    return components.apply_selection(INSTALL_DIR, _resolve_selection(selection),
                                      on_step=on_file)


def repair(selection=None, on_progress=None, on_file=None) -> list[str]:
    """Re-fetches app code over the existing install (fixes missing or
    hand-edited files) without touching ~/.winxp_sim, then -- once the app
    is back on disk -- dynamically imports the freshly repaired winxp
    package to patch up cursed vfs state: a missing/orphaned system32,
    missing protected files, a missing Recycle Bin. Same checks as
    utils/respawn_system32.py and utils/respawn_recycle_bin.py, just
    reachable before the app has ever been run."""
    fixed = []
    was_installed = is_installed()
    _download_and_extract(INSTALL_DIR, on_progress, on_file)
    if not was_installed:
        fixed.append("Windows XP (app files were missing entirely)")
    else:
        fixed.append("Application files (re-fetched from source)")
    # re-fetching restores every module, including ones that had been stubbed
    # out as uninstalled components, so the selection has to be re-applied.
    fixed.extend(_configure(_resolve_selection(selection), on_file))
    fixed.extend(_repair_vfs())
    return fixed


def _repair_vfs() -> list[str]:
    if not os.path.exists(PROFILE_DIR):
        return []  # no profile yet -- nothing to repair, first launch will create one
    if INSTALL_DIR not in sys.path:
        sys.path.insert(0, INSTALL_DIR)
    from winxp import vfs as vfs_mod
    from winxp.vfs import SYSTEM32_SEED_FILES, vfs

    vfs.load_or_init()
    fixed = []

    def _is_system32_installed():
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

    if not _is_system32_installed():
        vfs._seed_system32(vfs.get(vfs.root_id))
        vfs.save()
        fixed.append("C:\\WINDOWS\\system32 (whole folder)")
    else:
        sys32 = vfs.get(vfs.system32_id)
        present = {vfs.get(c).name for c in sys32.children if vfs.get(c)}
        for name, content in SYSTEM32_SEED_FILES.items():
            if name not in present:
                node = vfs.create_text_file(vfs.system32_id, name, content)
                vfs.set_attributes(node.id, read_only=True)
                fixed.append(name)

    if vfs.get(vfs.recycle_id) is None:
        orphan = next(
            (c for c in vfs.children_of(vfs.desktop_id)
             if c.name == "Recycle Bin" and c.kind == vfs_mod.FOLDER),
            None,
        )
        if orphan:
            vfs.recycle_id = orphan.id
        else:
            node = vfs.create_folder(vfs.desktop_id, "Recycle Bin")
            vfs.recycle_id = node.id
        vfs.save()
        fixed.append("Recycle Bin")

    return fixed
