---
name: seenby
description: "Read a screen recording (video file) the user shares or points at: bug report, demo, test run, client video, screencast, .mp4/.mov/.webm/.mkv. Runs seenby.py to turn it into contact sheets and frames.json, then reads them. Use whenever a task involves understanding what happens in a screen recording."
---

# seenby: read a screen recording

You cannot watch video. seenby turns a screen recording into a few contact sheets (one image each, readable in one look) and `frames.json` with the time and reason of every kept frame and every change it found. Read those instead.

## Run it

```
python3 <skill-dir>/seenby.py <recording> <out-dir>
```

`<skill-dir>` is the folder this SKILL.md is in; `seenby.py` and `seenby_report.py` sit next to it. Use `python` where `python3` is not found (Windows). Needs Python 3.8 or newer and `ffmpeg` and `ffprobe` on PATH, no Python packages. If it exits 1 because ffmpeg is missing, tell the user to install it (`brew install ffmpeg`, `sudo apt install ffmpeg`, `winget install ffmpeg`) and stop; do not fall back to guessing from the file name.

Always start with no options. It compares every pixel four times a second, so it sees a checkbox, a digit or a small popup change, and keeps the frame after each change settles. The console tells you what happened.

```
demo.mp4: 27.1 s, 814x872, portrait
  109 samples at 4 per second, 106 changes, 16 pointer moves, selected 24/24
  frames: 0.00 first, 0.50 change, 1.50 change, 3.25 change, ..., 26.50 change, 27.00 last
  ignored a blinking area at 120,608 8x32 px (4 times from 2.00 to 3.50 s): a text caret, or a small mark toggled back and forth
  layout: window, tile 516 px, 3x2 per sheet
  contact sheets: out/sheet-01.jpg, out/sheet-02.jpg, out/sheet-03.jpg, out/sheet-04.jpg
  manifest: out/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.
```

Exit code 0 means done; 1 means it could not run and stderr has one line saying why (no ffmpeg, no such file, not a video, a frame smaller than 8x8 px, an output directory holding someone else's frames); 2 means bad arguments.

## Read the result

1. Read every `sheet-NN.jpg` in order. Each tile is one kept frame, with its number and time in the band above it. `#07 12.25s` is frame 7 at 12.25 s, the file `frame-07-12.25s.jpg`. Tiles run left to right, top to bottom.
2. Open `frames.json`. `frames[i].time` is the second in the video, `reason` is why it was kept: `first`, `change` (the screen after a change settled), `state` (a short state inside a quick series, such as the first click of a double click), `during` and `fill` (inside a long continuous change such as a scroll), `last`. `sheets[]` says which frame numbers are on which sheet; `segments[]` groups frames by stretches of time.
3. `events` at the end of `frames.json` lists every change found: `settled` and `until` (the seconds the new state was on screen), `region` (`[x, y, w, h]` in native pixels, where to look on the frame) and `shown` (whether a kept frame shows it).
4. When you answer about a specific moment, cite the time from the band or `frames.json`, not the tile position.

**Digits.** Sheets are for meaning. The number and time in a tile's band are exact, but a number read off the picture once came out as 118 instead of 218. For any digit, amount, ID, or code, run the frame's `recheck` command from `frames.json` (it writes `frame-NN-native.jpg` at full resolution, exactly the frame that was analysed) and read that image.

## When the console warns you

- `N of M changes not shown within 24 frames (all of them would need K); C of them from A to B s: rerun with --from A' --to B'` means the recording had more states than the cap. Rerun with the `--from` and `--to` it names to see them; `events` with `shown: false` says which ones were left out.
- `no change: the first and the last frame only` means nothing on screen changed. `no change except N pointer-like moves (...)` means only pointer-sized marks moved; that is usually the pointer, but a radio button's dot jumping between two options looks the same, so if the question is about such a control, compare it on the first and the last frame (run their `recheck` for the native frames); the output does not say when the moves happened.
- `ignored a blinking area at X,Y WxH px (N times from A to B s): a text caret, or a small mark toggled back and forth` means a one-cell-wide spot kept flipping between the same two looks between A and B s and was not counted as a change. Usually that is the caret of a focused field. If the question is about a small mark at that place, there may be no frame of it now: rerun from a second before A to a second after B with `--selector legacy --threshold 0.2`.
- `N contact sheets are more than 4` means a lot of change; read them all or narrow with `--from/--to`.
- Fewer frames than you expected around a moment the user asked about: rerun with `--from S --to S` around it. A state shorter than a quarter of a second can still be missed.

## Options you may need

| option | default | use it when |
|---|---|---|
| `--from S --to S` | whole video | the user names a moment, the console names a stretch, or the recording is longer than a few minutes |
| `--max-frames N` | 24 | you accept more sheets to see more moments |
| `--dry-run` | | you want the selected times before extracting anything |
| `--force` | | the output directory holds `frame-*.jpg` from something else and you mean to overwrite |

Do not raise `--max-frames` above about 40: the sheets stop being readable.

`--selector legacy` runs the old selector (32x32 thumbnails, a threshold, a frame every 3 s by timer). It is deprecated and misses small changes; use it only for a mark hidden as a blinking area (above) or when the default fails on a recording, and say so to the user. `--threshold`, `--max-gap`, `--block-k` and `--sample-fps` belong to it: given without `--selector`, they switch to it.

## Speech

If the recording has narration, run the wrapper instead; it runs the core and adds `report.md` with the speech under each frame:

```
python3 <skill-dir>/seenby_report.py <recording> <out-dir>
```

It needs `pip install -r <skill-dir>/requirements-whisper.txt` only when the audio is above its gate; silent recordings are reported without a model. Ask the user before installing it, the packages are large. Any option it does not know goes to the core unchanged.

## What seenby cannot do

It notices that pixels changed, not what happened. It looks four times a second, so a flash shorter than a quarter of a second can be invisible. On camera footage of a screen it gives an overview, but text on the sheet will not be readable. Say so instead of guessing.
