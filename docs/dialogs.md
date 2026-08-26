# DIY dialog chrome

Every popup in the simulator — message boxes, the file picker, the color
picker — is drawn by us, not the host OS. This matters more than it sounds:
Qt's default `QDialog`/`QMessageBox`/`QColorDialog` render with the *real*
OS window frame. On macOS that means an actual native titlebar with real
traffic-light buttons around what's supposed to be a Windows XP dialog —
immersion-breaking in a very literal way.

## `winxp/xp_dialog.py` — the shared chrome

`build_dialog_frame(dialog, title)` is the one place this is implemented:
frameless + translucent window, rounded top corners, a drop shadow, and a
`DialogTitleBar` (gradient titlebar + a single close button, draggable) —
the same visual language as `winxp/window_manager.py`'s `XPWindow`/`TitleBar`
for real app windows, just without minimize/maximize since dialogs don't
need them. It returns the inner layout; callers add their body content to
it. `DIALOG_BUTTON_QSS` is the shared glossy-button styling so OK/Cancel
etc. look like every other button in the shell.

Three things are built on top of it:

- **`XPMessageBox`** (same file) — replacement for `QMessageBox`. Static
  methods `information/critical/warning/confirm` mirror the
  `QMessageBox.information/critical/warning/question` API so call sites read
  the same way. Icons (`msg_warning`/`msg_error`/`msg_info`/`msg_question`)
  are procedurally drawn in `winxp/icons.py`, not system glyphs.
- **`VfsFileDialog`** (`winxp/vfs_dialog.py`) — replacement for
  `QFileDialog`, but browses the *simulated* filesystem (`winxp/vfs.py`),
  not the real one. Used by Notepad/WordPad/Paint's Open and Save As.
- **`XPColorDialog`** (`winxp/color_dialog.py`) — replacement for
  `QColorDialog`. 48-swatch basic-colors grid + RGB spinboxes + live
  preview, used by Paint's color picker and "Edit Colors...".

## The one deliberate exception

`winxp/apps/wmp.py`'s "Import from Computer..." uses a real, native
`QFileDialog`. This is intentional, not an oversight: it's reaching into
the *actual* host filesystem to pull in a real audio/video file, and no
custom-drawn fake-XP dialog can browse folders it has no knowledge of. Every
other dialog in the app browses the simulated vfs tree and is fully custom;
this one bridges to reality and a real picker is the honest tool for that.

## The menu bar native-chrome bug

A related but separate issue: `QMenuBar` defaults to
`setNativeMenuBar(True)`, which on macOS pulls File/Edit/etc. into the *real*
system menu bar at the top of the screen — completely outside the frameless
app window they're supposed to belong to. Two fixes were needed together:

1. `theme.style_menubar(bar)` calls `bar.setNativeMenuBar(False)` (plus
   applies `MENU_QSS`, the Luna-styled menu look) on every `QMenuBar` the
   apps build.
2. `main.py` sets the *application-wide* attribute
   `Qt.ApplicationAttribute.AA_DontUseNativeMenuBar` before constructing
   `QApplication`. The per-instance flag alone wasn't reliable on macOS —
   this is the one that actually fixed it in practice.

Both are kept: the app-wide attribute is the fix that matters, the
per-instance call is defensive and gives every menu bar its Luna QSS.
