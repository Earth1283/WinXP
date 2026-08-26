# Storage: vfs.json + ntfs/

Everything the simulator persists lives under `~/.winxp_sim/`:

```
~/.winxp_sim/
  vfs.json      # tree structure only: names, kinds, parent/child links
  ntfs/         # one real file per content-bearing node
    <node_id>.txt    # Notepad (TEXT)
    <node_id>.html   # WordPad (RICH) -- QTextEdit.toHtml() output
    <node_id>.png    # Paint (IMAGE)
    <node_id>.<ext>  # Media Player (AUDIO / VIDEO) -- ext varies per import
```

## Why content lives outside vfs.json

Originally every file's content (including base64-encoded Paint images) was
inlined directly in `vfs.json`, and *every* tree mutation — even renaming an
unrelated file — called `VFS.save()`, which rewrote the entire JSON blob
including all embedded content. This didn't scale: the file kept growing
and every save got slower with it.

Now `vfs.json` only ever holds tree metadata (`Node.to_dict()` — id, name,
kind, parent, children, icon, target, ext, timestamps). It stays small
regardless of how much media exists. Actual bytes are read/written directly
to their own file in `ntfs/`, so touching one file's content never rewrites
another's.

## The `Node.ext` field

`CONTENT_EXT` in `winxp/vfs.py` gives fixed extensions for kinds that only
ever have one format: `TEXT -> .txt`, `RICH -> .html`, `IMAGE -> .png`.
`AUDIO` and `VIDEO` nodes vary per imported file (`.mp3` vs `.wav` vs
`.mp4`...), so those store their real extension on the node itself
(`Node.ext`) at creation time, set once and never re-derived from the
(mutable) display name — renaming a file never breaks its content path.

`VFS.content_path(node_id)` resolves `node.ext or CONTENT_EXT[node.kind]`
to build the real path on disk. This is also what `winxp/apps/wmp.py` hands
directly to `QUrl.fromLocalFile()` for playback — the vfs content store
doubles as real, valid files any real media backend can open.

## API surface (`winxp/vfs.py`)

- `read_content(node_id) -> str` / `write_content(node_id, text)` — text kinds
- `read_blob(node_id) -> bytes` / `write_blob(node_id, data)` — binary kinds
- `create_text_file`, `create_image_file`, `create_audio_file`,
  `create_video_file` — the latter two share `_create_media_file(kind, ...)`
- `content_path(node_id) -> str` — real path on disk, for anything (like
  `QMediaPlayer`) that needs one directly instead of going through
  read_content/read_blob

`delete(node_id, permanent=True)` removes the matching content file too, so
`ntfs/` doesn't accumulate orphans from deleted files. (This has to compute
the content path *before* popping the node out of `self.nodes` — a node
that's already gone can't tell you its own `.ext` anymore. Got this wrong
once during development; `_rm()` now captures the path first.)

## Migration

Old stores (from before this split) have `content` inlined per-node in
`vfs.json`. `VFS._load()` detects this (`v.pop("content", None)`), and for
any node that still has it, `_migrate_legacy_content()` writes it out to
`ntfs/` (base64-decoding it first if the node is an `IMAGE`, since that's
how images used to be inlined) and the tree gets re-saved without it. This
runs automatically on next load — no user action needed, and it's been
verified against a real populated store, not just a synthetic one.

The same pattern covers the `My Music` folder (`VFS.my_music_id`): a store
saved before Media Player existed won't have `my_music_id` in its JSON.
`_load()` checks for that and creates the folder on the fly, same as the
content migration.
