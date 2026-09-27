---
name: seenby
description: "Read a screen recording (video file) the user shares or points at: bug report, demo, test run, client video, screencast, .mp4/.mov/.webm/.mkv. Runs seenby.py to turn it into contact sheets and frames.json, then reads them. Use whenever a task involves understanding what happens in a screen recording."
---

# seenby: read a screen recording

You cannot watch video. seenby turns a screen recording into a few contact sheets (one image each, readable in
one look) and `frames.json` with the time and reason of every kept frame. Read those instead.

## Run it

```
python3 <skill-dir>/seenby.py <recording> <out-dir>
```

`<skill-dir>` is the folder this SKILL.md is in; `seenby.py` and `seenby_report.py` sit next to it. Use `python` where `python3` is not found (Windows). Needs Python 3.8 or newer and `ffmpeg` and `ffprobe` on PATH, no Python packages. If it exits 1 because ffmpeg is missing, tell the user to install it (`brew install ffmpeg`, `sudo apt install ffmpeg`, `winget install ffmpeg`) and stop; do not fall back to guessing from the file name.

Always start with no options. The console tells you what happened:

```
demo.mp4: 27.1 s, 814x872, portrait
  54 thumbnails, selected 19/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)
  frames: 0.0 first, 3.0 timer, 3.5 block, 6.5 timer, ..., 25.5 timer, 26.5 last
  quiet stretches at a lower threshold: 12.0-26.5 s at 3.4 (largest change 10.3)
  layout: window, tile 516 px, 3x2 per sheet
  contact sheets: out/sheet-01.jpg, out/sheet-02.jpg, out/sheet-03.jpg, out/sheet-04.jpg
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

- `quiet stretches at a lower threshold: ...` is not a problem. On a light screen a change can be too small for the default threshold, so seenby looked at those seconds again with a lower one; the frames there are real changes. Nothing to do.
- `all frames taken by the timer: the largest change between thumbnails was 4.4, under the threshold 12.0; --threshold 1.4: 9 content frames ...` means the picture did change, too little for the default threshold, and the lower one did not fit the cap of frames. Rerun with the `--threshold` the line names, with `--from S --to S` around the part you need, and read the new sheets. When the line stops after `under the threshold 12.0` with no suggestion, the largest change was 1.0 or less. That is not proof that nothing happened: on a wide or high-resolution window a checkbox, a radio button or a small badge toggling moves this measure by only 0.1-0.3. If the recording is about such controls, rerun with `--threshold 0.2` on the part you need, or read the native frames around the moments in question.
- `all frames taken by the timer: the threshold contributed nothing ... try --max-frames` means the recording is long and the cap of 24 frames raised the threshold until only timer frames remained. Pick the stretch you care about and rerun with `--from S --to S`; `segments[]` in `frames.json` shows what is where.
- `N contact sheets are more than 4` means a lot of change; read them all or narrow with `--from/--to`.
- Fewer frames than you expected around a moment the user asked about: rerun with `--dry-run --from S --to S`
  around it (prints the times it would pick, extracts nothing), then without `--dry-run`. `--sample-fps 4`
  looks twice as often for short events; a state shorter than half a second can still be missed.

## UI recordings: `--selector events`

For a recording of an interface (a browser or app window, a phone screen) where the user clicks, types, toggles checkboxes, opens dropdowns or dialogs, run with `--selector events`, and use it as the second run whenever the default output is mostly `timer` frames:

```
python3 <skill-dir>/seenby.py <recording> <out-dir> --selector events
```

It finds changes by counting changed pixels at native resolution, so it sees a checkbox or a digit that the default selector's 32x32 thumbnails average away, and it keeps the frame after each change settles instead of a frame every 3 seconds. Measured on 15 real recordings, agents reading its output answered 94.4% of questions right against 80.0% with the default, with 1 confidently wrong answer against 10.

- `frames[].reason`: `first`, `change` (the screen after a change settled), `state` (a short state inside a quick series, such as the first click of a double click), `during` and `fill` (inside a long continuous change such as a scroll), `last`. There are no timer frames. A stretch without a frame had no change the selector could see, unless the console says that changes were not shown.
- `events` at the end of `frames.json` lists every change found: `settled` and `until` (the seconds the new state was on screen), `region` (`[x, y, w, h]` in native pixels: where to look on the frame) and `shown` (whether a kept frame shows it).
- `N of M changes not shown within 24 frames (all of them would need K); C of them from A to B s: rerun with --from A' --to B'` means the recording had more states than the cap. Rerun with the `--from` and `--to` it names (and `--selector events`) to see them.
- `no change: the first and the last frame only` means nothing on screen changed. `no change except N pointer-like moves (...)` means only pointer-sized marks moved; that is usually the pointer, but a radio button's dot jumping between two options looks the same, so if the question is about such a control, compare it on the first and the last frame (run their `recheck` for the native frames); the output does not say when the moves happened.
- `ignored a blinking area at X,Y WxH px (N times from A to B s): a text caret, or a small mark toggled back and forth` means a one-cell-wide spot kept flipping between the same two looks between A and B s and was not counted as a change. Usually that is the caret of a focused field. If the question is about a small mark at that place, rerun that stretch with `--from A --to B` without `--selector events`: there may be no frame of it now.
- `recheck` extracts exactly the analysed frame at full resolution; use it for digits as above.
- `--threshold`, `--max-gap`, `--block-k` and `--sample-fps` belong to the default selector; with `--selector events` they are an error.

## Options you may need

| option | default | use it when |
|---|---|---|
| `--from S --to S` | whole video | the user names a moment, or the recording is longer than a few minutes |
| `--max-frames N` | 24 | you accept more sheets to see more moments |
| `--threshold X` | 12 | the all-timer line names a lower value; lower keeps smaller changes |
| `--sample-fps F` | 2 | events are short (tooltips, flashes) |
| `--dry-run` | | you want the selected times before extracting anything |
| `--block-k 0` | 5 | too many `block` frames from a blinking element; disables the local metric |
| `--force` | | the output directory holds `frame-*.jpg` from something else and you mean to overwrite |

Do not raise `--max-frames` above about 40: the sheets stop being readable.

## Speech

If the recording has narration, run the wrapper instead; it runs the core and adds `report.md` with the speech
under each frame:

```
python3 <skill-dir>/seenby_report.py <recording> <out-dir>
```

It needs `pip install -r <skill-dir>/requirements-whisper.txt` only when the audio is above its gate; silent recordings are reported without a model. Ask the user before installing it, the packages are large. Any option it does not know goes to the core unchanged.

## What seenby cannot do

It notices that pixels changed, not what happened. It sees 2 frames per second, so a flash shorter than half a
second is invisible. On camera footage of a screen it gives an overview, but text on the sheet will not be
readable. Say so instead of guessing.
