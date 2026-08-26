# Documentation

- **[adding_apps.md](adding_apps.md)** — how the app registry works; how to
  add a new launchable app in one place instead of touching four files.
- **[storage.md](storage.md)** — why `vfs.json` stays tiny no matter how
  much you save, how content files in `ntfs/` are keyed and extended, and
  how old stores migrate forward automatically.
- **[dialogs.md](dialogs.md)** — the DIY message box / file picker / color
  picker chrome, why native `QDialog`/`QMenuBar` chrome leaks the host OS,
  and the one deliberate exception (importing real files into Media Player).
- **[task_manager.md](task_manager.md)** — Task Manager's End Process,
  the system-health/corruption model, and how a killed critical process
  degrades the shell instead of just disappearing.
- **[media_player.md](media_player.md)** — real audio/video playback via
  Qt Multimedia, the `AUDIO`/`VIDEO` vfs kinds, and how import works.
