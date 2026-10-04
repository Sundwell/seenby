---
name: seenby
description: "Read a screen recording (video file) the user shares or points at: bug report, demo, test run, client video, screencast, .mp4/.mov/.webm/.mkv. Runs seenby.py to turn it into contact sheets and frames.json, then reads them. Use whenever a task involves understanding what happens in a screen recording."
---

# seenby: read a screen recording

You cannot watch video. seenby turns a screen recording into a few contact sheets (one image each, readable in one look) and `frames.json` with the time and reason of every kept frame and every change it found. Next to them it puts every change cut out at native size, before and after (`crops-NN.png`), and a full native frame of each screen (`screen-NN-<t>s.jpg`). Read those instead.

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
  crops, every change at native size before > after, numbered as on the sheets: out/crops-01.png, out/crops-02.png
  screens, a full native frame of each screen as it starts, for reading text and digits: out/screen-01-0.00s.jpg, out/screen-02-9.00s.jpg; all listed in out/crops.json
```

Exit code 0 means done; 1 means it could not run and stderr has one line saying why (no ffmpeg, no such file, not a video, a frame smaller than 8x8 px, an output directory holding someone else's frames); 2 means bad arguments.

## Read the result

1. Read every `sheet-NN.jpg` in order. Each tile is one kept frame, with its number and time in the band above it. `#07 12.25s` is frame 7 at 12.25 s, the file `frame-07-12.25s.jpg`. Tiles run left to right, top to bottom. A magenta box marks a change seenby found, on the first tile that shows it (its `region` in `events`): look there first. Boxes close together are joined into one. A change gets no box when its area did not visibly change since the tile before (it changed and changed back, or it is codec noise), when its box, with the boxes joined to it, would cover more than half the tile, or when its tile has more than 12 boxes, so a tile without boxes can still hold changes; `events` lists them all. A box around the pointer alone means the pointer moved in the same quarter second as a change. The frame files have no boxes. The magenta number next to a box is the number of its crop.
2. Read every `crops-NN.png` the console lists; do not skip them, on a wide recording they are the only place where small things are readable. Each block is one boxed change at native size: a label with its number (the one next to the box), the times and the tile it is on, `07 7.50>7.75>8.00 #12`, and under it the same area before and after the change. A third picture in the middle is the frame the box is on when it shows something that is gone again after, such as a tooltip, or a state that came and went. `crops-02.png` holds the changes of screen 2, `crops-02b.png` its second page. The pointer's shape, a hover outline, a zoom label going `95% > 128%` are a few pixels on a sheet and plain here.
3. Open every `screen-NN-<t>s.jpg`. A screen is the stretch between two redraws of most of the picture (a page load, a dialog over the page, an editor opening). The file is the full frame at native size as that screen starts: read page text, headers and counters there. What changed on that screen afterwards is in its crops.
4. Open `frames.json`. `frames[i].time` is the second in the video, `reason` is why it was kept: `first`, `change` (the screen after a change settled), `state` (a short state inside a quick series, such as the first click of a double click), `during` and `fill` (inside a long continuous change such as a scroll), `last`. `sheets[]` says which frame numbers are on which sheet; `segments[]` groups frames by stretches of time.
5. `events` in `frames.json` lists every change found: `settled` and `until` (the seconds the new state was on screen), `region` (`[x, y, w, h]` in native pixels, where to look on the frame), `shown` (whether a kept frame shows it) and `crop` (the number and file of its crop, or `null`: the change started a new screen, so look at that screen's full frame, or it looked the same before and after). `crops` at the end names the crop images and the screen files; `crops.json` has, for each crop, its times, its tile and the `recrop_before` and `recrop_after` commands that cut the same area again.
6. When you answer about a specific moment, cite the time from the band or `frames.json`, not the tile position.

**Digits.** Sheets are for meaning. The number and time in a tile's band are exact, but a number read off the picture once came out as 118 instead of 218, and a counter of 36 as 34. Never state a digit, amount, ID, code or file name read off a sheet, even in passing. Read it at native size: first from what is already on disk, the crop of that change or the full frame of its screen (the screen as it starts; its crops show whether the number changed later), otherwise run the frame's `recheck` command from `frames.json` (it writes `frame-NN-native.jpg` at full resolution, exactly the frame that was analysed) and read that image.

## When the console warns you

- `N of M changes not shown within 24 frames (all of them would need K); C of them from A to B s: rerun with --from A' --to B'` means the recording had more states than the cap. Rerun with the `--from` and `--to` it names to see them; `events` with `shown: false` says which ones were left out.
- `no change: the first and the last frame only` means nothing on screen changed. `no change except N pointer-like moves (...)` means only pointer-sized marks moved; that is usually the pointer, but a radio button's dot jumping between two options looks the same, so if the question is about such a control, compare it on the first and the last frame (run their `recheck` for the native frames); the output does not say when the moves happened.
- `ignored a blinking area at X,Y WxH px (N times from A to B s): a text caret, or a small mark toggled back and forth` means a one-cell-wide spot kept flipping between the same two looks between A and B s and was not counted as a change. Usually that is the caret of a focused field. If the question is about a small mark at that place, there may be no frame of it now: rerun from a second before A to a second after B with `--selector legacy --threshold 0.2`.
- `N contact sheets are more than 4` means a lot of change; read them all or narrow with `--from/--to`.
- `crops not written: ...` on stderr, or no `crops` line at all, means the sheets and `frames.json` are complete but there are no crops and no screen files; use `recheck` for anything small. A recording with one kept frame and the legacy selector never have them.
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
