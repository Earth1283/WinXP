# Windows Explorer

Explorer is the largest single app in the sim because in XP it wasn't an
app — it was the shell. The window you get from `explorer:<node_id>` hosts a
menu bar, two rebar bands, one Explorer Bar, one of five view modes and a
three-panel status bar, and every one of those pieces is context-sensitive
to what folder you're in and what's selected.

## Module split

| Module | Holds |
|---|---|
| `winxp/apps/explorer.py` | the window: chrome, menus, commands, history, clipboard, undo |
| `winxp/apps/explorer_shell.py` | naming/format/sort rules (type strings, sizes, dates, group headings, address paths) |
| `winxp/apps/explorer_views.py` | the five view modes and their item delegate |
| `winxp/apps/explorer_panes.py` | the Explorer Bar tenants and the Browse For Folder dialog |

The split exists because the same translation gets asked for from four
places at once. "How big is this?" is answered in the Details column, the
Tiles subtitle, the status bar and the task pane's Details group; if each
computed it locally they would drift. `explorer_shell` owns every one of
those answers, so `column_text(node, COL_SIZE)` and the status bar cannot
disagree.

## The five view modes

Thumbnails, Tiles, Icons and List are one `QListWidget` (`ShellIconView`)
driven by `ShellItemDelegate`. Details is a separate `QTreeWidget`
(`ShellDetailsView`) because it needs real sortable column headers.

Everything except Details is custom-painted rather than composed from item
widgets, because Qt has no built-in equivalent of:

- a **Tile** — 48px icon on the left, name/type/size stacked to its right,
  whole cell highlighted on selection
- a **group heading** — bold blue caption with a rule that runs to the edge
  of the view, occupying a full row inside a flow layout
- a **drive tile** — name, capacity bar, "2.50 GB free of 4.00 GB", with the
  bar turning red under 12% free
- **cut feedback** — the icon at 45% opacity from the moment you press
  Ctrl+X until the paste lands

Group headings get a `sizeHint` a couple of pixels narrower than the
viewport. Full-bleed makes the flow layout break the row (which is what
puts each group on its own line), and the couple of pixels of slack stop the
heading from being the thing that provokes a scrollbar.

Both views expose the same small API — `set_entries`, `selected_ids`,
`select_ids`, `begin_rename`, `drop_target_at` — so `ExplorerWindow` never
branches on which one is on screen. `self.view()` returns whichever is
current.

### Renaming

Rename selects the stem and leaves the extension alone, which means two
things had to be handled:

- The view gives the editor focus *after* `setEditorData` returns, and
  `QLineEdit` selects everything on focus-in, so the stem selection is staked
  one event-loop turn later via `QTimer.singleShot(0, ...)`.
- Arming the edit sets `ItemIsEditable`, and `setFlags` emits `itemChanged`,
  which is the same signal the commit handler listens for. Unblocked, that
  instantly "commits" a rename that never happened and tears the item down
  underneath `editItem`. `begin_rename` blocks signals across the flag change.

With "Hide extensions for known file types" on you're editing a stem that
has no extension in it, so the commit handler reattaches the real one before
saving — otherwise confirming a rename would silently drop `.txt`.

## The task pane

The blue "common tasks" webview is rebuilt from scratch on every selection
change, because in XP its contents were a function of the selection rather
than a fixed menu: no selection offers *Make a new folder*, one file offers
*Rename this file* / *Move this file* / *Delete this file*, and several
offer *Move the selected items*. The Recycle Bin swaps the whole group for
*Empty the Recycle Bin* / *Restore this item*, and My Computer swaps it for
*System Tasks*.

Rebuilding means the old group widgets go away every time. They are
reparented to `None` *before* `deleteLater()` — a widget that has only been
scheduled for deletion keeps painting at its old geometry until the event
loop gets to it, which shows up as ghost text over the new pane.

Task links wrap to a second line rather than eliding. A `QPushButton` with
"Publish this folder to the Web" on it reports a minimum width wide enough
to hold that string, and inside a fixed-width pane that pushes the whole
pane past its slot; a wrapping `QLabel` has no such opinion.

## Clipboard and undo are shell-wide

`_CLIPBOARD` and `_UNDO` are module-level, not per-window. Cutting in one
Explorer window and pasting in another is the entire point of a clipboard,
and XP's Edit > Undo likewise undid the last shell operation regardless of
which window performed it. Undo entries are `(label, callable)` pairs, so
the Edit menu can render "Undo Move" / "Undo Delete" / "Can't Undo" the way
XP did, and the stack is capped at 20.

Paste into the folder something was copied from produces `Copy of <name>`,
matching the shell. Pasting a *cut* clears the clipboard; pasting a copy
does not.

## Recycle Bin

`Node.deleted_from` and `Node.deleted_at` are recorded at the moment
something moves to the bin — the equivalent of the real bin's `INFO2`
record. Without them Restore has nowhere to put things back, and the bin's
"Original Location" / "Date Deleted" columns have nothing to show.

If the original folder has since been deleted itself, real XP recreates the
path. There's nothing here to recreate, so `VFS.restore()` falls back to the
Desktop rather than failing.

Double-clicking an item in the bin opens its Properties instead of launching
it, same as the real shell — the file isn't in a place where opening it
means anything yet.

## Drives and My Computer

`Node.drive` marks a root-level volume (`DRIVE_FIXED` / `DRIVE_FLOPPY` /
`DRIVE_CDROM`). It changes three things: the icon, the Details column set
(Type / Total Size / Free Space instead of Size / Type / Modified), and the
Tiles rendering (capacity bar).

`Local Disk (C:)` reports `DRIVE_BASE_USED` plus the real summed size of
everything under it — without a baseline the bar would read 100% free
forever, since Windows itself occupies most of a real C: before the user
saves a single file. `3½ Floppy (A:)` and `CD Drive (D:)` are seeded empty
and report *no* capacity at all, because that's what an empty bay does;
opening either raises the genuine "Please insert a disk into drive A:".

My Computer always renders in groups (Files Stored on This Computer / Hard
Disk Drives / Devices with Removable Storage) regardless of the Show in
Groups setting, because it was a special view rather than an ordinary
folder.

## Address paths

`shell_path()` reproduces what the Address bar actually showed. Anything on
a volume gets a real path (`C:\WINDOWS\system32`); the shell-only folders
above the drives show their display name alone (`My Documents`), which is
what XP did rather than exposing `Desktop\My Documents`. Typing a path back
into the bar resolves against the same function, and anything unresolvable
gets the real "Windows cannot find..." error.

Note that this vfs roots the tree at My Computer with Desktop *underneath*
it, which is the inverse of XP's Desktop-rooted namespace. The Folders tree
follows the vfs rather than faking XP's ordering, so `path_of` and
`shell_path` stay honest about where a node actually lives.

## Shell notifications

`explorer_shell.shell_notifier` is a single `QObject` with a `changed`
signal. Every window that mutates the vfs emits it; every Explorer window
and the desktop itself repaint from it. That's why a folder created in an
Explorer window pointed at the Desktop appears on the actual desktop
immediately, and why two windows on the same folder stay in sync — without
anything polling.

## What the sim can't have

Publishing to the Web, e-mailing a selection, printing, mapping a network
drive and synchronizing offline files all exist in the menus and the task
pane, and all report the genuine Windows failure for a machine with no
network, no mail client and no printer — "Either there is no default mail
client...", "No network provider accepted the given network path.", and so
on. They're stubs, but they're the stubs XP itself would have shown you on
that machine, which is a more honest answer than greying the items out.

Everything else in the menus is wired: File > New (Folder, Shortcut, Text
Document, Rich Text Document, Bitmap Image, Wave Sound), Create Shortcut,
the full Edit menu including Copy/Move To Folder, every View submenu
including Choose Details and Arrange Icons by, Favorites with Add and
Organize, Tools > Folder Options, and the keyboard set (F2, F5, Del,
Shift+Del, Backspace, Alt+Left/Right/Up, Ctrl+X/C/V/Z/A/N).
