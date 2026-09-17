---
name: seenby
description: Read a screen recording (video file) the user shares or points at: bug report, demo, test run, client video, screencast, .mp4/.mov/.webm/.mkv. Runs seenby.py to turn it into contact sheets and frames.json, then reads them. Use whenever a task involves understanding what happens in a screen recording.
---

# seenby: read a screen recording

You cannot watch video. seenby turns a screen recording into a few contact sheets (one image each, readable in
one look) and `frames.json` with the time and reason of every kept frame. Read those instead.

## Run it

```
python3 <path-to>/seenby.py <recording> <out-dir>
```

`<path-to>` is where this skill's repository is checked out; if `seenby.py` is not found, ask the user where
it is or clone `https://github.com/Sundwell/seenby`. Requires `ffmpeg` and `ffprobe` on PATH. No Python
packages.

Always start with no options. The console tells you what happened:

```
demo.mp4: 27.1 s, 814x872, portrait
  54 thumbnails, selected 12/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)
  frames: 0.0 first, 3.0 timer, 3.5 block, 6.5 timer, ..., 26.5 last
  layout: window, tile 516 px, 3x2 per sheet
  contact sheets: out/sheet-01.jpg, out/sheet-02.jpg
  manifest: out/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.
```

Exit code 0 means done; 1 means it could not run and stderr has one line saying why (no ffmpeg, no such file,
not a video, an output directory holding someone else's frames); 2 means bad arguments.

## Read the result

1. Read every `sheet-NN.jpg` in order. Each tile is one kept frame; tiles run left to right, top to bottom.
2. Open `frames.json`. `frames[i].time` is the second in the video, `reason` is why it was kept: `first`,
   `diff` (the picture changed), `block` (a small area changed, such as a dropdown or a highlight), `timer`
   (nothing changed for `max_gap` seconds, forced), `last`. `sheets[]` says which frame numbers are on which
   sheet; `segments[]` groups frames by stretches of time.
3. When you answer about a specific moment, cite the time from `frames.json`, not the tile position.

**Digits.** Sheets are for meaning. A number read off a tile once came out as 118 instead of 218. For any
digit, amount, ID, or code, run the frame's `recheck` command from `frames.json` (it writes
`frame-NN-native.jpg` at full resolution) and read that image.

## When the console warns you

- `all frames taken by the timer: the threshold contributed nothing` means nothing changed enough to be
  noticed, or the recording is long and the cap of 24 frames raised the threshold until only timer frames
  remained. For a short recording that is usually the truth (a static screen). For a long one (minutes), pick
  the stretch you care about and rerun with `--from S --to S`; `segments[]` in `frames.json` shows what is where.
- `N contact sheets are more than 4` means a lot of change; read them all or narrow with `--from/--to`.
- Fewer frames than you expected around a moment the user asked about: rerun with `--dry-run --from S --to S`
  around it (prints the times it would pick, extracts nothing), then without `--dry-run`. `--sample-fps 4`
  looks twice as often for short events; a state shorter than half a second can still be missed.

## Options you may need

| option | default | use it when |
|---|---|---|
| `--from S --to S` | whole video | the user names a moment, or the recording is longer than a few minutes |
| `--max-frames N` | 24 | you accept more sheets to see more moments |
| `--sample-fps F` | 2 | events are short (tooltips, flashes) |
| `--dry-run` | | you want the selected times before extracting anything |
| `--block-k 0` | 5 | too many `block` frames from a blinking element; disables the local metric |
| `--force` | | the output directory holds `frame-*.jpg` from something else and you mean to overwrite |

Do not raise `--max-frames` above about 40: the sheets stop being readable.

## Speech

If the recording has narration, run the wrapper instead; it runs the core and adds `report.md` with the speech
under each frame:

```
python3 <path-to>/seenby_report.py <recording> <out-dir>
```

It needs `pip install -r requirements-whisper.txt` only when the audio is above its gate; silent recordings
are reported without a model. Any option it does not know goes to the core unchanged.

## What seenby cannot do

It notices that pixels changed, not what happened. It sees 2 frames per second, so a flash shorter than half a
second is invisible. On camera footage of a screen it gives an overview, but text on the sheet will not be
readable. Say so instead of guessing.
