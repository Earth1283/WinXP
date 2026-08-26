# Windows Media Player: real audio + video playback

`winxp/apps/wmp.py` plays real media through `PyQt6.QtMultimedia`
(`QMediaPlayer` + `QAudioOutput`, backed by ffmpeg) — not a fake/decorative
transport bar. It's also fully DIY-chrome like the rest of the app,
including the import picker (see `HostFileDialog` in `docs/dialogs.md`) —
no native OS dialog opens anywhere in this app.

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
- `_on_media_status()` watches for `QMediaPlayer.MediaStatus.EndOfMedia` and
  calls `_play_next()` automatically — verified with a synthetic short WAV
  during development (it audibly/measurably auto-advanced mid-test).

## Audio vs. video display

A `QStackedLayout` holds two widgets in the same spot: `Visualizer` (a
decorative animated bar graph — it does not analyze the real audio signal,
Qt Multimedia doesn't expose spectrum data without considerably more
plumbing than this warrants) and a `QVideoWidget`. `_play_track()` checks
`node.kind == vfs_mod.VIDEO` and calls `stack.setCurrentWidget(...)`
accordingly; `player.setVideoOutput(video_widget)` is wired once up front
and is harmless when the loaded source has no video stream.

## Import

`_import_from_computer()` opens `HostFileDialog` (`docs/dialogs.md`) — Luna
chrome, but browsing the real host filesystem rather than the vfs, filtered
to `MEDIA_EXTS` (`AUDIO_EXTS | VIDEO_EXTS`). Whatever's picked gets read as
raw bytes and written straight into the vfs via
`create_audio_file`/`create_video_file` based on the file's extension — no
transcoding, no format conversion, the original bytes become the new node's
content file in `ntfs/`.

## Testing note

Playback was verified against ffmpeg-generated synthetic clips (a sine-tone
WAV, and an `ffmpeg -f lavfi -i testsrc ...` test-pattern MP4 with an AAC
tone track) rather than any downloaded real-world media — confirmed real
h264/AAC decode, `hasVideo`, position/duration tracking, and the
audio↔video widget switch, without pulling in copyrighted content just to
exercise a codec path.
