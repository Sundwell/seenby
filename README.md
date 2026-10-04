# seenby

**Every screen recording, seen by your agent.**

seenby turns a screen recording into a few contact sheets and a `frames.json` that an AI coding agent reads in one pass: bug reports, demos, test runs, customer videos. One Python file, only `ffmpeg` required. It keeps a frame for every screen state that changed, down to a single checkbox, always keeps the ending, keeps UI text legible, and says what did not fit.

```
python3 seenby.py recording.mp4 [out-dir]
```

That writes `recording-frames/` (or `out-dir`) with the frames, a few `sheet-NN.jpg` an agent reads one at a time, and `frames.json` with the time and reason of every frame and every change found.

## How it picks frames

ffmpeg's scene detection (`select='gt(scene,X)'`) compares each frame with the one right before it. A screen recording changes a little at a time, a smooth scroll or a dropdown opening, so neighbouring frames look almost the same. Measured on 11 real screen recordings at threshold 0.08, it kept no frames at all on 4, and on 7 the last 2 to 27 seconds had no frame. On a 100-second smooth scroll the threshold decides between 212 frames (0.08) and a 64-second hole with the last 15.6 seconds missing (0.30).

seenby measures changes where they happen. ffmpeg compares every pixel's luma with the previous sample, four samples per second at native resolution, and seenby counts the pixels that moved by more than 24 in cells of 8x8 px. Changed cells group into areas; two alike pointer-sized areas and nothing else are the pointer moving, not a change. Changes of one screen area make one event, on screen from the moment it settles until that area changes again. seenby keeps the fewest frames that show every event's settled state, plus the first and the last, up to `--max-frames`. When they do not fit, it gives each burst of activity a frame first and then the weightiest changes, and says what was left out. There is no timer: a stretch where nothing changed gets no frame.

A 16 px checkbox on a 2120x422 window is a few hundred changed pixels over a codec noise of zero, so it is found; averaged over the whole frame, the way the legacy selector did, it was 0.06 against a threshold of 12.

## Install

One command installs the skill into your agent.

```
npx skills add Sundwell/seenby -g
```

It asks which agents to install into, among them Claude Code, Codex, Cursor, OpenCode, Pi, Gemini CLI and GitHub Copilot. Then give the agent a recording and ask what happens in it. The native routes do the same.

| Agent | Command |
|---|---|
| Claude Code | `/plugin marketplace add Sundwell/seenby`, then `/plugin install seenby@seenby` |
| Codex | `codex plugin marketplace add Sundwell/seenby`, then `codex plugin add seenby@seenby` |
| Pi | `pi install git:github.com/Sundwell/seenby` |

The agent picks the skill by its name and description. With many skills installed and a model with a 200K context, Claude Code drops the descriptions of rarely used skills from its listing and the agent sees only the name. If the agent does not reach for it, call it directly with `/seenby:seenby` (plugin) or `/seenby` (`npx skills`) in Claude Code, `/skill:seenby` in Pi, or `$` and the skill in Codex. In Claude Code the `skillListingBudgetFraction` setting (for example `0.02`) keeps more descriptions.

Every route needs two things on the machine that no installer adds.

- Python 3.8 or newer, `ffmpeg` and `ffprobe` on PATH (or `FFMPEG=/path/to/ffmpeg`, `FFPROBE=...`). ffmpeg 4.4 and newer work; 4.4.1, 5.0.1, 6.1.1 and 9.0.2 were run.
- No packages for the core. `seenby_report.py` needs `pip install -r requirements-whisper.txt` only for recordings whose audio is above its gate; silent ones are reported without it.

To run the scripts by hand, clone the repository. Both are single files.

## What you get

```
recording-frames/
  frame-01-0.00s.jpg     one file per kept frame, number and second in the name
  frame-02-0.50s.jpg
  ...
  sheet-01.jpg           contact sheets, within 1568 px on both sides, every tile under its number and time, changes boxed
  crops-01.png           every change of screen 1 at native size, before and after, numbered as its box on the sheets
  screen-01-0.00s.jpg    the full native frame of each screen as it starts
  crops.json             the crops and screens: times, tile, region, a command that cuts each crop again
  frames.json            the manifest, see below
```

Every tile of a sheet has a band above it with the frame's number and time, `#07 12.25s` for `frame-07-12.25s.jpg`, so a frame is cited and rechecked without counting tiles. The band is drawn with a built-in pixel font, so it needs nothing beyond ffmpeg itself; the frame files and `recheck` stay without it.

On the default selector a change gets a magenta box on the first tile that shows it, a few pixels outside the changed area, so the eye goes straight to a 16 px checkbox on a 2120 px strip. The boxes come from the `region`s of `events` in `frames.json`, and a change gets one only where some 16x16 px of it changed clearly since the tile before, counted at full resolution: an area that changed and changed back in between (the pointer passing over it) and codec noise on text get none. Boxes closer than 6 px are joined into one, a box over more than half of the tile is dropped together with anything joined to it, and a tile with more than 12 separate boxes gets none. With options that put far more tiles on a sheet than the defaults, a sheet whose boxes would not fit on the Windows command line is drawn without them. So a tile without boxes can still hold changes; `events` lists them all. Like the band, the boxes are on the sheets only; the frame files and `recheck` stay clean for reading digits.

A tile is a third of a wide screen or less, so a boxed change can be a few pixels of grey. The default selector therefore also cuts every change out at native size. `crops-NN.png` holds the changes of screen `NN`, each as a small block: a label such as `07 7.50>7.75>8.00 #12` (crop 7, the times of its pictures, on tile 12), and under it the same area before and after the change, 16 px of the screen kept around it. The number is also written in magenta next to the box on the sheet. Changes that settle in the same quarter second within 128 px of each other share a crop while it stays under a tenth of the frame; seenby does not guess rows, columns or cards. A picture in the middle is the frame the box is on when it shows something that is gone again in the picture after (a tooltip), or, when before and after look the same, the first state in between that does not; a change with no such state is left out and listed in `crops.json`. A change that redraws about a quarter of the frame or more starts a new screen instead of a crop, as do crops that add up to a quarter of it, and each screen gets its full native frame, `screen-NN-<t>s.jpg`: page text, headers and counters are read there without a command. A stretch between two redraws that lasts under a second and holds no crop (a step of a scroll) is not a screen. The legacy selector and a recording with one kept frame get no crops.

The console says what happened and does not hide a bad outcome.

```
demo.mp4: 27.1 s, 814x872, portrait
  109 samples at 4 per second, 106 changes, 16 pointer moves, selected 24/24
  frames: 0.00 first, 0.50 change, 1.50 change, 3.25 change, ..., 26.50 change, 27.00 last
  ignored a blinking area at 120,608 8x32 px (4 times from 2.00 to 3.50 s): a text caret, or a small mark toggled back and forth
  layout: window, tile 516 px, 3x2 per sheet
  contact sheets: demo-frames/sheet-01.jpg, demo-frames/sheet-02.jpg, demo-frames/sheet-03.jpg, demo-frames/sheet-04.jpg
  manifest: demo-frames/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.
  crops, every change at native size before > after, numbered as on the sheets: demo-frames/crops-01.png, demo-frames/crops-02.png
  screens, a full native frame of each screen as it starts, for reading text and digits: demo-frames/screen-01-0.00s.jpg, demo-frames/screen-02-9.00s.jpg; all listed in demo-frames/crops.json
```

Here every change fit in 24 frames. When they do not, a line under the frames says how many were not shown, how many frames all of them would need, and which stretch to rerun with `--from/--to`, for example `151 of 272 changes not shown within 24 frames (all of them would need 131); 36 of them from 0.50 to 26.50 s: rerun with --from 0.00 --to 27.50` on a 20 minute concatenation of test recordings. When nothing changed, a line says so and counts the pointer-like moves (a radio button's dot jumping between options looks like the pointer). A one-cell-wide spot that keeps flipping between the same two looks, a text caret, is ignored and named with the stretch it blinked in; it does not cut short the text typed next to it, and a pointer move in the same moment still counts as the pointer. Exit codes are 0 done, 1 could not run (one line on stderr, no traceback), 2 bad arguments.

## frames.json

```json
{
  "tool": "seenby", "version": 1, "ffmpeg": "ffmpeg version 6.1.1 ...",
  "video": {"name": "demo.mp4", "path": "demo.mp4", "duration": 27.1, "width": 814, "height": 872,
            "ratio": 0.933, "orientation": "portrait", "grade": "window"},
  "analysis": {"selector": "events", "sample_fps": 4, "samples": 109, "cell": 8, "pixel_threshold": 24,
               "max_frames": 24, "range": {"from": 0.0, "to": 27.1}, "segment": 120.0,
               "changes": 106, "shown": 106, "pointer_moves": 16,
               "blinking": [{"region": [120, 608, 8, 32], "count": 4, "from": 2.0, "to": 3.5}]},
  "sheet": {"cols": 3, "rows": 2, "tile_width": 516, "sheet_width": 1568, "count": 4},
  "frames": [
    {"n": 1, "time": 0.0, "file": "frame-01-0.00s.jpg", "sheet": 1, "reason": "first",
     "recheck": "ffmpeg -ss 0.000 -i demo.mp4 -vf 'fps=4:round=up:start_time=0,select=eq(n\\,0)' -fps_mode passthrough -frames:v 1 -q:v 2 demo-frames/frame-01-native.jpg"},
    {"n": 2, "time": 0.5, "file": "frame-02-0.50s.jpg", "sheet": 1, "reason": "change", "recheck": "..."}
  ],
  "sheets": [{"file": "sheet-01.jpg", "frames": [1, 6]}, {"file": "sheet-02.jpg", "frames": [7, 12]}, "..."],
  "segments": [{"n": 1, "from": 0.0, "to": 27.1, "frames": [1, 2, 3, "...", 24], "activity": 106}],
  "events": [
    {"from": 1.0, "settled": 1.0, "until": 4.75, "region": [112, 224, 288, 72], "changed_px": 3120, "shown": true,
     "crop": {"n": 1, "file": "crops-01.png"}},
    "..."
  ],
  "crops": {"file": "crops.json", "images": ["crops-01.png", "crops-02.png"],
            "screens": [{"n": 1, "from": 0.0, "file": "screen-01-0.00s.jpg"}, {"n": 2, "from": 9.0, "file": "screen-02-9.00s.jpg"}]}
}
```

Numbers in the file are full floats (`27.099892`), rounded here for reading. `reason` is why the frame was kept: `first`, `change` (the screen after a change settled), `state` (a short state inside a quick series, such as the first click of a double click, shown when the cap has room), `during` and `fill` (inside a long continuous change such as a scroll), `last`. `events` lists every change found. `settled` and `until` are the seconds its new state was on screen, `region` is `[x, y, w, h]` in native pixels (where to look on the frame), and `shown` says whether a kept frame shows it. `crop` is the number and file of the crop that shows the change at native size, or `null` when it has none (it started a new screen, or it looked the same before and after); `crops` names the crop images and the full frame of each screen. Both keys are there only when crops were written. `segments` index the frames by stretches of `--segment` seconds, with `activity`, the number of changes that settled in the stretch, so a reader of a long recording knows where to zoom in. Each frame's `recheck` extracts the very frame that was analysed, at full resolution.

**Reading rule.** Sheets are for meaning. A number read off a tile once came out as 118 instead of 218, and a counter of 36 as 34 on a 2560 px recording. For digits, read the crop of the change or the full frame of its screen, which are already on disk at native size, or run the frame's `recheck` command and read the native frame.

## Options

Start without options and change one only when the console or the manifest tells you why.

| option | default | what it does |
|---|---|---|
| `--max-frames N` | 24 | cap on kept frames |
| `--from S`, `--to S` | whole video | analyse a range only; times in the output stay absolute |
| `--segment S` | 120 | length of the `segments` index in `frames.json` |
| `--sheet-width PX` | 1568 | longest side of a contact sheet |
| `--rows N`, `--tile-width PX` | as many rows as fit, tile by aspect ratio | override the grid |
| `--selector legacy` | `events` | the deprecated 32x32-thumbnail selector, see below |
| `--threshold X`, `--max-gap S`, `--block-k K`, `--sample-fps F` | | legacy selector only; given without `--selector`, they choose it |
| `--dry-run` | | print the selected times and the layout, extract nothing |
| `--force` | | overwrite an output directory that holds `frame-*.jpg` from something else |

Layout by aspect ratio: phone screens get 256 px tiles in 6 columns, desktop windows 516 px in 3, wide desktops 776 px in 2, so UI text stays readable after the model downscales the sheet.

**Dense recordings.** When many things change every second for half a minute, the cap binds and some changes get no frame. The console names the densest stretch; rerun it with `--from/--to`, and `events` in `frames.json` lists what was not shown.

## How well it works

Measured on 15 real screen recordings, 4.7 to 38 s, with ground truth labeled by two independent agents and an adjudicator (110 key and 186 key-or-normal events). Scored by the source frame each method actually shows, seenby's frames show 78% of the key events and 69% of all UI changes (332 frames in all), the legacy selector 63% and 54% (179 frames), `claude-real-video` 56% and 46% (160 frames). Agents who answered 125 questions about these recordings from the output alone scored 94.4% with seenby against 80.0% with the legacy selector (a blind judge, two readers per output), with 1 confidently wrong answer against 10.

Two honest limits of that measurement. On recordings this short, 24 evenly spaced frames show more of the labeled events, 83% and 76% (355 frames); they were not part of the reading test, and on a long recording 24 evenly spaced frames are minutes apart, where seenby still gives each burst of activity a frame. And on a dense recording, many changes a second for half a minute, the cap binds and some changes get no frame: rerun the stretch the console names.

It takes about twice as long as the legacy selector on long recordings (18.3 s against 9.2 s on 20 minutes of 720p, 170 MB against 138 MB of memory), because it decodes the range a second time to extract exactly the frames it analysed. It passes frames through with `-fps_mode` on ffmpeg 5.1 and newer and with `-vsync` before that (9.0 removed `-vsync`); on 13 recordings it picked the same frames with 4.4.1, 6.1.1 and 9.0.2, except that 9.0.2 decoded one more sample at the end of one recording, and 5.0.1 gave the same frames on the recording it was run on.

## The legacy selector (deprecated)

`--selector legacy`, or any of `--threshold`, `--max-gap`, `--block-k`, `--sample-fps` given without `--selector`, runs the selector seenby had before. It is kept as a fallback while the new default gets real use and will be removed.

It shrinks the whole frame to a 32x32 grey thumbnail twice per second and keeps a frame when the mean difference from the last kept frame passes a threshold (12 by default, `--threshold`), or when one 8x8 block of the thumbnail changes strongly (`--block-k`). A frame is forced after `--max-gap` seconds without one, and when too many frames are found the threshold is raised instead of cutting the tail. Where the timer alone kept three frames in a row, it looks at the stretch again with a lower threshold of its own. Its console reports thumbnails, the threshold, `timer` frames and, when every frame came from the timer, says so.

Why it is deprecated. One number for the whole frame is the changed share of the screen times the contrast, so it misses exactly the changes a UI bug report is about: a checkbox on a wide window scores 0.06 and a page change on a light site 2.5, both under 12, and the timer then picks frames blind. It also extracts a different frame than it analysed: `fps=2` keeps the last source frame of each half-second slot and `-ss t` the frame at t, so 25 of 61 frames kept for a change show the state before it. Both are fixed in the default selector, not here.

## Speech: seenby_report.py

```
pip install -r requirements-whisper.txt
python3 seenby_report.py recording.mp4 [out-dir] [--model large-v3-turbo] [--device auto|cuda|cpu]
[--transcribe-anyway] [core options]
```

Runs the core, measures the audio level, and only when it is above a gate (-45 dB peak, -80 dB mean) loads a whisper model (`faster-whisper`) and transcribes; a recording without an audio track counts as silent. Writes `report.md` next to the frames: one section per frame with the speech of its interval (a sentence crossing a frame boundary appears under both frames, marked continued; a low-confidence line gets `(?)`), the whole speech with timecodes, and the reading rule. Silent recordings never load a model. Options the wrapper does not know go to the core unchanged. On a GPU the model runs in float16 with a CUDA 12 toolkit from the pip wheels; without one it falls back to CPU int8.

## Guarantees

For the default selector (the legacy one keeps its own, older ones).

- The first and the last sample are always kept. The last sample sits within a quarter of a second and one source frame of the end.
- No sheet is wider or taller than `--sheet-width` (1568 px) unless you override `--rows` or `--tile-width`. The one exception is an aspect ratio so extreme that a single row is already taller; then the sheet is one row.
- Every frame on the sheets is the frame that was analysed, and its `recheck` extracts the same frame at full resolution.
- A failed run leaves no `frames.json`; the previous manifest is removed before ffmpeg is called.
- An output directory holding `frame-*.jpg` without our `frames.json` is refused (`--force` overrides).
- When changes did not fit the cap, the console says how many and where, and `events` marks each one `shown: false`.

## Limitations

- Four samples per second: a state shorter than a quarter of a second (a flash, a tooltip) can be missed.
- Pixel difference is not understanding. A frame is kept because the picture changed, not because something happened.
- A box marks changed pixels, not a meaningful change. When the pointer moves in the same quarter second as a change, the pointer is boxed too, and so is a hover mark such as a row highlight. On heavily compressed recordings (x264 crf 36 and above) codec noise on text can still get a box.
- A change of fewer than 12 pixels is taken for codec noise, and two alike pointer-sized changes with nothing else in the same sample are taken for the pointer, so a radio button's dot moving between two options is counted as a pointer move.
- A 2 px text caret across two cells, a terminal's block cursor and the caret of a 3x phone recording are not recognised as blinking and count as changes.
- Over the cap, short states inside a quick series (the first click of a double click) are the first to go.
- JPEG bytes depend on the ffmpeg build. Two runs in one directory at the same time conflict.
- Camera footage of a screen works for an overview, but text on the sheet will not be readable; this tool is for screen recordings.
- The audio gate thresholds (-45 dB peak, -80 dB mean) separate nine silent recordings from one noisy one and have not been checked against real speech yet; use `--transcribe-anyway` when in doubt. Whisper on background noise produces a short hallucination; the report shows the language probability and coverage so you can tell.

## Compared with claude-real-video and clipsheet

On the 15 labeled recordings above, `claude-real-video` showed 56% of the key events and 46% of all UI changes, seenby 78% and 69%, scored the same way, and on the four of them held out while seenby's rules were tuned 70% and 57% against seenby's 73% and 61%. Measured earlier on ten screen recordings plus a 20-minute concatenation of them, `claude-real-video` lost the final screen on 3 of the 10 and on the concatenation, and cuts the tail when its frame limit hits; `clipsheet` lost the ending on 7 of the 11; seenby kept the ending on all 11. It aims at screen recordings only: on camera footage with cuts `claude-real-video` has scene detection and a motion channel that seenby does not try to match.

## The skill

`skills/seenby/SKILL.md` teaches an agent when to run seenby, how to read `frames.json`, and what to do when the console warns. The folder also holds copies of both scripts and `requirements-whisper.txt`, so an installed skill runs without the repository. The copies are byte-for-byte the files at the root. Any agent with a terminal can also run the scripts directly; the skill is a convenience.

## Tests

```
pip install -r requirements-dev.txt
python3 -m pytest -q tests
```

Acceptance tests come from the specs in `docs/specs/` (rule IDs, example tables, properties) and need no ffmpeg. The ffmpeg stages are covered by a byte-for-byte regression against recordings that are not in the repository.

## License

MIT, see `LICENSE`.

## Contributing

See `CONTRIBUTING.md`: behaviour is defined in the specs, tests follow the specs, the core stays dependency-free.
