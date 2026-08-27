"""The Select Components catalogue.

Setup runs before the winxp package exists on disk, so this file is
stdlib-only and describes the product as data rather than importing anything
from it.

A component is honest: clearing one really does change what lands on disk.
There are three ways that happens, and which one a component uses depends
only on how the app loads it:

  ``apps``    ids written into ~/.winxp_sim/settings.json as uninstalled.
              The sim already honours that list -- Start Menu hides them and
              launching one raises the real "Windows cannot find 'winmine.exe'"
              dialog -- because Add or Remove Programs uses the same mechanism.

  ``stub``    modules the app imports lazily get replaced by a generated
              placeholder that answers with "this feature was not installed"
              instead of vanishing. That is what an optional component did in
              2003, and it keeps the menu item present but inert.

  ``creates`` files Setup writes itself (the colour profiles), which exist
              only if you asked for them.

Deleting a module outright is deliberately never an option: an ImportError at
launch is a crash, not a missing feature.
"""
from __future__ import annotations

import json
import os
import shutil

SETTINGS_PATH = os.path.expanduser("~/.winxp_sim/settings.json")
MANIFEST_NAME = ".setup_manifest.json"

# The message a stubbed-out feature puts up when you reach for it.
NOT_INSTALLED_TEXT = (
    "{feature} is not currently installed.\n\n"
    "This feature was not selected when Windows XP was installed. Run Setup "
    "again and choose Custom to add it."
)


class Component:
    def __init__(self, cid, label, size_mb, *, required=False, default=True,
                 children=(), apps=(), stub=None, creates=(), note=""):
        self.id = cid
        self.label = label
        self.size_mb = size_mb
        self.required = required
        self.default = True if required else default
        self.children = list(children)
        self.apps = list(apps)
        self.stub = stub or {}
        self.creates = list(creates)
        self.note = note

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def own_size(self):
        return self.size_mb

    def total_size(self):
        return self.size_mb + sum(c.total_size() for c in self.children)


# --- the stubs -------------------------------------------------------------
# Each entry names the module to replace and the attributes the rest of the
# app imports from it, so the placeholder can answer to the same names.

_PHOTOCHOP = "winxp/apps/photochop"

STUB_FILE_BROWSER = {
    f"{_PHOTOCHOP}/filebrowser.py": {
        "feature": "The PhotoChop File Browser",
        "dialogs": ["FileBrowserDialog"],
    }
}
STUB_WORKSPACES = {
    f"{_PHOTOCHOP}/workspaces.py": {
        "feature": "Liquify, Extract and Pattern Maker",
        "dialogs": ["LiquifyDialog", "ExtractDialog", "PatternMakerDialog"],
    }
}
STUB_EXTRAS = {
    f"{_PHOTOCHOP}/misc_dialogs.py": {
        "feature": "PhotoChop Help and Presets",
        "dialogs": ["PreferencesDialog", "ColorSettingsDialog", "SaveForWebDialog",
                    "PrintDialog", "PageSetupDialog", "FileInfoDialog",
                    "HistogramDialog", "PresetManagerDialog", "HelpDialog"],
    },
    f"{_PHOTOCHOP}/style_dialog.py": {
        "feature": "PhotoChop Layer Styles",
        "dialogs": ["LayerStyleDialog"],
    },
}
STUB_FILTERS = {
    f"{_PHOTOCHOP}/filters.py": {
        "feature": "The PhotoChop production filters",
        "dialogs": [],
        # window.py reads FILTER_MENU to build the menu and calls run() to
        # apply one; an empty menu is exactly "no filters installed".
        "extra": (
            "FILTER_MENU = []\n"
            "\n"
            "\n"
            "def run(key, img, params=None, ctx=None):\n"
            "    _complain()\n"
            "    return img\n"
            "\n"
            "\n"
            "def resolve(key):\n"
            "    return None\n"
            "\n"
            "\n"
            "def __getattr__(name):\n"
            "    # every filter is a function of an image; hand back one that\n"
            "    # gives the image straight back rather than raising.\n"
            "    def _identity(img, *args, **kwargs):\n"
            "        return img\n"
            "    return _identity\n"
        ),
    }
}

ICC_PROFILES = [
    ("sRGB Color Space Profile.icm", "sRGB IEC61966-2.1"),
    ("AdoboRGB1998.icc", "Adobo RGB (1998)"),
    ("AppleRGB.icc", "Apple RGB"),
    ("ColorMatchRGB.icc", "ColorMatch RGB"),
    ("USWebCoatedSWOP.icc", "U.S. Web Coated (SWOP) v2"),
    ("EuroscaleCoated.icc", "Euroscale Coated v2"),
    ("JapanStandard.icc", "Japan Standard v2"),
    ("WideGamutRGB.icc", "Wide Gamut RGB"),
]

CATALOGUE = [
    Component(
        "winxp", "Windows XP Professional", 0, required=True, children=[
            Component("core", "Core System Files", 248, required=True,
                      note="Windows itself. Cannot be deselected."),
            Component("ie", "Internet Explorer 6", 42, required=True,
                      note="Internet Explorer is an integral part of Windows "
                           "and cannot be removed."),
            Component("accessories", "Accessories and Utilities", 0, children=[
                Component("notepad", "Notepad", 2, apps=["notepad"]),
                Component("wordpad", "WordPad", 4, apps=["wordpad"]),
                Component("calculator", "Calculator", 1, apps=["calculator"]),
                Component("paint", "Paint", 6, apps=["paint"]),
            ]),
            Component("games", "Games", 3, apps=["minesweeper"],
                      note="Minesweeper."),
            Component("wmp", "Windows Media Player 8", 28, apps=["wmp"]),
            Component("mword", "MacroHard Word", 62, apps=["mword"]),
            Component("vscode", "Visual XP Code", 88, default=False, apps=["vscode"]),
        ]),
    Component(
        "photochop", "Adobo PhotoChop 7.0", 0, apps=["photochop"], children=[
            Component("pc_core", "Program Files", 74, required=True,
                      note="The application, its tools and its adjustments."),
            Component("pc_filters", "Production Filters", 41, stub=STUB_FILTERS,
                      note="All 100 filters across the fourteen Filter submenus."),
            Component("pc_browser", "File Browser", 3, stub=STUB_FILE_BROWSER),
            Component("pc_liquify", "Liquify, Extract and Pattern Maker", 12,
                      default=False, stub=STUB_WORKSPACES,
                      note="The three full-screen filter workspaces."),
            Component("pc_extras", "Presets, Colour Settings and Help", 18,
                      stub=STUB_EXTRAS,
                      note="Preferences, Save for Web, Print with Preview, "
                           "Layer Styles, Help."),
            Component("pc_icc", "Color Profiles (ICC)", 22, default=False,
                      creates=[("winxp/assets/icc/" + name, text)
                               for name, text in ICC_PROFILES]),
        ]),
]

BY_ID = {c.id: c for root in CATALOGUE for c in root.walk()}


def default_selection() -> set[str]:
    return {c.id for c in BY_ID.values() if c.default}


def typical_selection() -> set[str]:
    """What Typical installs: everything except the components real Setup also
    left out of a Typical run."""
    return default_selection()


def complete_selection() -> set[str]:
    return set(BY_ID)


def selected_size_mb(selected) -> int:
    return sum(c.size_mb for cid, c in BY_ID.items() if cid in selected)


def available_mb(path=None) -> int:
    """Free space on the volume Setup is installing to."""
    target = path or os.path.expanduser("~")
    while target and not os.path.exists(target):
        target = os.path.dirname(target)
    try:
        return int(shutil.disk_usage(target).free / (1024 * 1024))
    except OSError:
        return 0


# --- applying a selection --------------------------------------------------

def _stub_source(module_path: str, spec: dict) -> str:
    feature = spec["feature"]
    lines = [
        '"""Placeholder written by Windows XP Setup.',
        "",
        f"The {feature} component was not selected when Windows XP was",
        "installed. This module stands in for it so the rest of the",
        "application keeps working -- the menu commands are still there, they",
        "just tell you the feature is missing, the way an optional component",
        "did in 2003.",
        "",
        "Run Setup again and choose Custom to install it properly.",
        '"""',
        "from __future__ import annotations",
        "",
        f"_FEATURE = {feature!r}",
        f"_MESSAGE = {NOT_INSTALLED_TEXT.format(feature=feature)!r}",
        "",
        "",
        "def _complain(parent=None):",
        "    try:",
        "        from winxp.xp_dialog import XPMessageBox",
        "        XPMessageBox.warning(parent, 'PhotoChop', _MESSAGE)",
        "    except Exception:",
        "        pass",
        "",
        "",
        "class _NotInstalled:",
        '    """Answers to the dialog protocol, then declines to be a dialog."""',
        "",
        "    def __init__(self, *args, **kwargs):",
        "        _complain(args[0] if args else None)",
        "",
        "    def exec(self):",
        "        return 0",
        "",
        "    def show(self):",
        "        pass",
        "",
        "    def result(self):",
        "        return None",
        "",
        "    def mask(self):",
        "        return None",
        "",
        "    @staticmethod",
        "    def pick(*args, **kwargs):",
        "        _complain(args[0] if args else None)",
        "        return None",
        "",
        "    @staticmethod",
        "    def get_text(*args, **kwargs):",
        "        _complain(args[0] if args else None)",
        "        return None",
        "",
    ]
    for name in spec.get("dialogs", []):
        lines.append(f"{name} = _NotInstalled")
    if spec.get("extra"):
        lines.append("")
        lines.append("")
        lines.append(spec["extra"].rstrip("\n"))
    return "\n".join(lines) + "\n"


def _icc_source(profile_name: str) -> str:
    return (
        "ICC profile placeholder written by Windows XP Setup.\n"
        f"Profile: {profile_name}\n"
        "Class: Display Device\n"
        "Color Space: RGB\n"
        "PCS: XYZ\n"
        "Rendering Intent: Perceptual\n"
        "Creator: Adobo Systems Incorporated\n"
    )


def prune_orphans(selected) -> set:
    """A child component is only installed if its parent is."""
    selected = set(selected)

    def walk(component):
        if component.id not in selected:
            for descendant in component.walk():
                selected.discard(descendant.id)
            return
        for child in component.children:
            walk(child)

    for root in CATALOGUE:
        walk(root)
    return selected


def apply_selection(dest: str, selected, on_step=None) -> list[str]:
    """Make the tree on disk match the selection. Returns a human-readable log."""
    log = []
    selected = prune_orphans(selected)

    for cid, comp in BY_ID.items():
        chosen = cid in selected
        for module_path, spec in comp.stub.items():
            target = os.path.join(dest, *module_path.split("/"))
            if chosen:
                continue
            if not os.path.exists(os.path.dirname(target)):
                continue
            if on_step:
                on_step(module_path)
            with open(target, "w", encoding="utf-8") as f:
                f.write(_stub_source(module_path, spec))
            entry = f"{comp.label} - not installed"
            if entry not in log:
                log.append(entry)

        for rel_path, profile_name in comp.creates:
            target = os.path.join(dest, *rel_path.split("/"))
            if chosen:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                if on_step:
                    on_step(rel_path)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(_icc_source(profile_name))
            elif os.path.exists(target):
                os.remove(target)
        if comp.creates and chosen:
            log.append(f"{comp.label} - {len(comp.creates)} profiles installed")

    uninstalled = sorted({app for cid, comp in BY_ID.items()
                          for app in comp.apps if cid not in selected})
    _write_uninstalled_apps(uninstalled)
    for cid, comp in BY_ID.items():
        if comp.apps and cid not in selected:
            log.append(f"{comp.label} - not installed")

    write_manifest(dest, selected)
    return log


def _write_uninstalled_apps(app_ids):
    """Merge into ~/.winxp_sim/settings.json without importing winxp."""
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    data = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH) as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
    data["uninstalled_apps"] = list(app_ids)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def write_manifest(dest: str, selected):
    path = os.path.join(dest, MANIFEST_NAME)
    try:
        with open(path, "w") as f:
            json.dump({"components": sorted(selected)}, f, indent=2)
    except OSError:
        pass


def read_manifest(dest: str):
    """What the last run of Setup installed, so Repair can restore it."""
    path = os.path.join(dest, MANIFEST_NAME)
    try:
        with open(path) as f:
            stored = set(json.load(f).get("components", []))
    except (OSError, ValueError):
        return None
    return stored & set(BY_ID) or None
