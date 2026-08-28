# Documentation

- **[adding_apps.md](adding_apps.md)** — how the app registry works; how to
  add a new launchable app in one place instead of touching four files.
- **[storage.md](storage.md)** — why `vfs.json` stays tiny no matter how
  much you save, how content files in `ntfs/` are keyed and extended, and
  how old stores migrate forward automatically.
- **[dialogs.md](dialogs.md)** — the DIY message box / file picker / color
  picker chrome and why native `QDialog`/`QMenuBar` chrome leaks the host OS.
- **[task_manager.md](task_manager.md)** — Task Manager's End Process,
  the system-health/corruption model, and how a killed critical process
  degrades the shell instead of just disappearing.
- **[explorer.md](explorer.md)** — the shell: the five view modes and why
  they're delegate-painted, the context-sensitive task pane, the shell-wide
  clipboard/undo, Recycle Bin restore, and the drive/volume model.
- **[media_player.md](media_player.md)** — real audio/video playback via
  Qt Multimedia, the WMP8 shell, and the `AUDIO`/`VIDEO` vfs kinds.
