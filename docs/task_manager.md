# Task Manager: kill, limp along, or BSOD

`winxp/apps/task_manager.py` is a real Applications/Processes/Performance
Task Manager (open windows + fake system processes, End Task/End Process,
Set Priority, Debug, Create Dump File — all through the DIY dialog chrome in
`docs/dialogs.md`). The Processes tab is where it gets cursed on purpose:
killing certain fake processes has consequences instead of just vanishing
the row.

## `winxp/corruption.py` — global system health

A tiny singleton (`corruption.health`) tracking which critical process
names have been "killed" this session:

```python
health.kill(name)       # mark a critical proc dead
health.is_dead(name)    # bool
health.level            # len(dead_procs) -- overall severity
health.reset()          # wipe it (called on reboot/logoff)
```

`CRITICAL_PROCS` in `task_manager.py` is
`{csrss.exe, winlogon.exe, smss.exe, services.exe, lsass.exe, System}`.
`PROTECTED_PROCS` is just `System Idle Process` — real XP won't let you
touch it either, so `_end_process()` refuses with "Access is denied"
instead of anything happening.

## Limping along instead of instant death

Killing `System` is instant — real XP does not survive that, so neither
does this. Every other critical process just gets marked dead via
`health.kill(name)`, and the desktop (`winxp/desktop.py`) starts reacting to
that on a 3-second ambient timer (`_glitch_tick`):

| Dead process     | Symptom                                                                 |
|-------------------|--------------------------------------------------------------------------|
| `csrss.exe`       | Random open windows' titlebars glitch (`TitleBar.flash_glitch()`)        |
| `winlogon.exe`     | Wallpaper gets random static-noise bursts (`Desktop.flash_wallpaper_glitch()`) |
| `services.exe`     | Random windows freeze — `XPWindow.freeze()`: dimmed, disabled, titled "(Not Responding)", for a few seconds |
| `lsass.exe`        | Periodic fake "Access is denied" security alerts |
| `smss.exe`         | `apps.launch()` silently refuses to open anything new (except `system:` actions, so you can still log off/shut down) |

Each tick also rolls `random() < health.level * 0.05` — the more things
you've broken, the better the odds of a full crash even without killing
everything. Killing all five non-`System` criticals guarantees it
(`health.level >= len(CRITICAL_PROCS) - 1`).

## `winxp/apps/bsod.py` — the actual crash

`crash(wm, proc_name)` builds a `BSOD` (fullscreen frameless widget, classic
blue-screen copy, a proc-specific STOP code from `STOP_CODES`, and an
animated "Physical memory dump: NN% complete" counter) and stores it on
`wm._bsod_ref` so nothing garbage-collects it mid-animation. When the dump
finishes, `_reboot()` closes every open window and calls `health.reset()` —
a fresh boot really does fix everything, same as it would on a real machine.

`XPWindow.freeze()`'s delayed restore and `TitleBar`'s glitch-clear timers
both guard with `try/except RuntimeError` — if the crash/reboot closes a
window while one of those `QTimer.singleShot` callbacks is still pending,
the underlying Qt object is already deleted by the time it fires. This was
a real crash caught during testing, not a defensive guess.
