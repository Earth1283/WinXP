# Windows Media Player 8

`winxp/apps/wmp.py` recreates the Windows XP release of Windows Media Player
8 in full mode. It keeps real media playback through `QMediaPlayer` and
`QAudioOutput`; the shell is not a decorative transport bar.

The player includes the original task-oriented sections: Now Playing, Media
Guide, Copy from CD, Media Library, Radio Tuner, Copy to CD or Device, and
Skin Chooser. The shared transport supports play/pause, stop, previous, next,
seek, volume, mute, shuffle, and repeat. Full mode and compact skin mode are
available from View, alongside a ten-band equalizer and three animated
visualization collections.

## vfs kinds

`AUDIO` and `VIDEO` (`winxp/vfs.py`) both store their real file extension on
`Node.ext` rather than a fixed per-kind extension, since an imported file
could be `.mp3`, `.wav`, `.mp4`, `.mkv`, whatever the user picked — see
`docs/storage.md` for why that field exists. Both kinds share one creation
path, `VFS._create_media_file(kind, parent_id, name, data, ext)`, called by
the thin `create_audio_file`/`create_video_file` wrappers.

Tracks live in a single library folder, `VFS.my_music_id` ("My Music",
created at bootstrap, migrated in for older stores). Despite the name it
holds both audio and video — real WMP mixes both in one "Now Playing"
library too, and adding a second special folder just for video wasn't worth
the extra scope.

## Playback

- `QMediaPlayer.setSource(QUrl.fromLocalFile(vfs.content_path(node_id)))` —
  this is exactly why the storage rewrite in `docs/storage.md` mattered:
  `content_path()` returns a real file on disk, which is what a real media
  backend needs. There's no way to hand `QMediaPlayer` a base64 blob.
- Transport (play/pause/stop/prev/next), the seek slider, and volume are all
  generic — they don't care whether the loaded track is audio or video.
- `on_media_status()` watches for `QMediaPlayer.MediaStatus.EndOfMedia` and
  advances the Now Playing queue automatically.

## Audio vs. video display

A `QStackedLayout` holds two widgets in the same spot: `Visualizer` (a
decorative animated bar graph — it does not analyze the real audio signal,
Qt Multimedia doesn't expose spectrum data without considerably more
plumbing than this warrants) and a `QVideoWidget`. `play_track()` checks
`node.kind == vfs_mod.VIDEO` and calls `stack.setCurrentWidget(...)`
accordingly. `player.setVideoOutput(video_widget)` is wired once up front
and is harmless when the loaded source has no video stream.

## Sample content (`winxp/sample_media.py`)

Since Media Player can't import anything, it needs *something* to play out
of the box. `sample_media.py` procedurally synthesizes two short WAV tracks
using only stdlib `wave`/`math`/`struct` — plain sine-tone sequences, not
derived from or resembling any real recording, same "no external assets"
approach as `winxp/icons.py`'s procedural icon drawing.

`VFS._seed_sample_media()` writes them into `My Music` via the normal
`create_audio_file` path (so they're indistinguishable from any other vfs
node — real files in `ntfs/`, listed in `vfs.json` like anything else). It
no-ops if `My Music` already has audio/video content, and runs from both
`_init_default()` (brand-new stores) and `_load()` (existing stores that
have a `My Music` folder but nothing in it yet — covers upgrading from the
version of the sim that had Media Player but no seeded content).

## Earlier design note

An earlier version imported media from the host filesystem. That was removed:
the player now stays entirely inside the simulated filesystem and uses the
procedurally generated sample tracks. See `docs/dialogs.md` for the broader
no-native-chrome policy.
