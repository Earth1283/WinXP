# Adding a new application

Every launchable app is described in one place: `winxp/app_registry.py`.
The Start Menu (pinned column + All Programs), Task Manager's process list,
and the launch dispatcher in `winxp/apps/__init__.py` all read from that
list — you don't touch any of them to add an app.

## Steps

1. Write the window class, same as any existing app (e.g. `winxp/apps/calculator.py`):

   ```python
   from ..window_manager import XPWindow

   class WidgetsWindow(XPWindow):
       def __init__(self, wm):
           super().__init__(wm, title="Widgets", icon_key="widgets", size=QSize(400, 300))
           ...
   ```

   Constructor must accept `(self, wm)`, or `(self, wm, node_id=None)` if the
   app can open an existing virtual-filesystem file (like Notepad/WordPad).

2. If the app needs a taskbar/Start Menu icon that doesn't exist yet, add a
   `_draw_*` function to `winxp/icons.py` and register it in `_draw()`'s
   dispatch — icons are drawn procedurally, no image assets.

3. Append one `AppSpec` to the `APPS` list in `winxp/app_registry.py`:

   ```python
   AppSpec("widgets", "Widgets", "widgets", "widgets", "WidgetsWindow",
           pinned=True)
   ```

   That's it. The app now:
   - launches via `apps.launch(wm, "app:widgets")`
   - appears in the Start Menu's pinned column (because `pinned=True`) and
     in the All Programs flyout (default `all_programs=True`)
   - shows up in Task Manager's Applications/Processes tabs as
     `widgets.exe` (the default `exe_name`) whenever a window is open
   - is typeable in Task Manager's "New Task..." dialog as `widgets` or
     `widgets.exe`

## AppSpec fields

| Field           | Required | Meaning                                                                 |
|-----------------|----------|--------------------------------------------------------------------------|
| `id`            | yes      | Stable key. Launch target is `"app:<id>"`.                              |
| `title`         | yes      | Window title / Start Menu label.                                        |
| `icon`          | yes      | Key into `winxp.icons.icon(...)`.                                       |
| `module`        | yes      | Submodule of `winxp.apps`, e.g. `"calculator"`.                         |
| `class_name`    | yes      | Window class in that module, e.g. `"CalculatorWindow"`.                 |
| `exe_name`      | no       | Fake process name in Task Manager. Defaults to `f"{id}.exe"`.           |
| `pinned`        | no       | Show in the Start Menu's left pinned column. Default `False`.           |
| `all_programs`  | no       | Show in the Start Menu's All Programs flyout. Default `True`.           |
| `takes_node_id` | no       | `True` if the window can open an existing vfs file (Notepad/WordPad).   |

## What's deliberately *not* in the registry

- **Explorer** — its launch target (`explorer:<ref>`) resolves special refs
  (`root` / `mydocs` / `recycle`) to virtual-filesystem node ids, and it's
  core shell chrome rather than an "app" a user would add. It's launched
  directly in `apps/__init__.py`'s `launch()` and given `_app_key = "explorer"`
  by hand, but Task Manager still recognizes and labels it correctly.
- **The shell itself** (Desktop, Taskbar, Start Menu, Control Panel's
  sub-panels, power screen, BSOD) — these aren't launchable apps.
- **Legacy Task Manager "New Task" aliases** that don't match an app's `id`
  or `exe_name` (e.g. typing `write` or `write.exe` to launch WordPad,
  matching real Windows' historical executable name) live in
  `EXTRA_NEW_TASK_ALIASES` in `winxp/apps/task_manager.py`, since they're
  Task-Manager-specific flavor rather than facts about the app itself.
