# seenby

**Every screen recording, seen by your agent.**

seenby turns a screen recording into a few contact sheets and a `frames.json` that an AI coding agent reads in
one pass: bug reports, demos, test runs, customer videos. One Python file, only `ffmpeg` required. It always
keeps the ending, keeps UI text legible, and says honestly when its selection degenerated into a timer.

```
python3 seenby.py recording.mp4 [out-dir]
```

That writes `recording-frames/` (or `out-dir`) with the frames, a few `sheet-NN.jpg` an agent reads one at a
time, and `frames.json` with the time and reason of every frame.

## Why not `select='gt(scene,X)'`

ffmpeg's scene detection compares each frame with the one right before it. A screen recording changes a little at a time, a smooth scroll or a dropdown opening, so neighbouring frames look almost the same. Measured on 11 real screen recordings at threshold 0.08: it kept no frames at all on 4, and on 7 the last 2 to 27 seconds had no frame. On a 100-second smooth scroll the threshold decides between 212 frames (0.08) and a 64-second hole with the last 15.6 seconds missing (0.30).

seenby compares each frame with the last frame it kept. The change accumulates, and a couple of seconds of
scrolling crosses the threshold. A frame is also forced every few seconds of stillness, the first and the last
frame are always kept, and when more frames are found than fit on readable sheets the threshold is raised
instead of cutting the tail. On top of the mean difference a block metric catches a change confined to one
corner of the screen (a dropdown, a highlight moving one row) that the mean is blind to.

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

- Python 3.8 or newer, `ffmpeg` and `ffprobe` on PATH (or `FFMPEG=/path/to/ffmpeg`, `FFPROBE=...`).
- No packages for the core. `seenby_report.py` needs `pip install -r requirements-whisper.txt` only for recordings whose audio is above its gate; silent ones are reported without it.

To run the scripts by hand, clone the repository. Both are single files.

## What you get

```
recording-frames/
  frame-01-0.0s.jpg      one file per kept frame, number and second in the name
  frame-02-3.0s.jpg
  ...
  sheet-01.jpg           contact sheets, within 1568 px on both sides
  frames.json            the manifest, see below
```

The console says what happened and does not hide a bad outcome:

```
demo.mp4: 27.1 s, 814x872, portrait
  54 thumbnails, selected 19/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)
  frames: 0.0 first, 3.0 timer, 3.5 block, 6.5 timer, 9.5 timer, 11.0 block, ..., 25.5 timer, 26.5 last
  quiet stretches at a lower threshold: 12.0-26.5 s at 3.4 (largest change 10.3)
  layout: window, tile 516 px, 3x2 per sheet
  contact sheets: demo-frames/sheet-01.jpg, demo-frames/sheet-02.jpg, demo-frames/sheet-03.jpg, demo-frames/sheet-04.jpg
  manifest: demo-frames/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.
```

The `quiet stretches` line says where seenby lowered the threshold on its own (see "Pale screens" below). When every frame was still taken by the timer, a line says so. If the frame cap was not what raised the threshold, the line gives the largest change between thumbnails and what a lower `--threshold` would keep. Exit codes: 0 done, 1 could not run (one line on stderr, no traceback), 2 bad arguments.

## frames.json

```json
{
  "tool": "seenby", "version": 1, "ffmpeg": "ffmpeg version 6.1.1 ...",
  "video": {"name": "demo.mp4", "path": "demo.mp4", "duration": 27.1, "width": 814, "height": 872,
            "ratio": 0.933, "orientation": "portrait", "grade": "window"},
  "analysis": {"sample_fps": 2.0, "thumbnails": 54, "max_frames": 24,
               "threshold": {"requested": 12.0, "effective": 12.0},
               "max_gap": {"requested": 3.0, "effective": 3.0}, "block_k": 5.0,
               "block_active": true, "range": {"from": 0.0, "to": 27.1}, "segment": 120.0,
               "all_timer": false, "timer_share": 0.24,
               "quiet": [{"from": 12.0, "to": 26.5, "largest": 10.3, "threshold": 3.4}]},
  "sheet": {"cols": 3, "rows": 2, "tile_width": 516, "sheet_width": 1568, "count": 4},
  "frames": [
    {"n": 1, "time": 0.0, "file": "frame-01-0.0s.jpg", "sheet": 1, "reason": "first", "diff": 0.0, "block": 0.0,
     "recheck": "ffmpeg -ss 0.000 -i demo.mp4 -frames:v 1 -q:v 2 demo-frames/frame-01-native.jpg"},
    {"n": 3, "time": 3.5, "file": "frame-03-3.5s.jpg", "sheet": 1, "reason": "block", "diff": 7.8, "block": 70.5,
     "recheck": "..."}
  ],
  "sheets": [{"file": "sheet-01.jpg", "frames": [1, 6]}, {"file": "sheet-02.jpg", "frames": [7, 12]},
             {"file": "sheet-03.jpg", "frames": [13, 18]}, {"file": "sheet-04.jpg", "frames": [19, 19]}],
  "segments": [{"n": 1, "from": 0.0, "to": 27.1, "frames": [1, 2, 3, ..., 19], "activity": 3.2}]
}
```

Numbers in the file are full floats (`6.9111328125`), rounded here for reading. `timer_share` is the share of timer
frames among those the selection loop chose; `block_active` says whether the block rule could still fire at the
effective threshold. `reason` is why the frame was kept: `first`, `diff` (mean difference above the threshold),
`block` (one 8x8 block of the thumbnail changed strongly), `timer` (forced after `max_gap` seconds), `last`.
`segments` index the frames by stretches of `--segment` seconds, with `activity` (mean change between consecutive
thumbnails, 0 to 255) per stretch, so a reader of a long recording knows where to zoom in. `quiet` lists the stretches judged at a lower threshold of their own, with the largest change found there.

**Reading rule.** Sheets are for meaning. A number read off a tile once came out as 118 instead of 218. For
digits, run the frame's `recheck` command and read the native frame.

## Options

Defaults were set on ten real screen recordings; start without options and change one only when the console
or the manifest tells you why.

| option | default | what it does |
|---|---|---|
| `--max-frames N` | 24 | cap on kept frames; raises the threshold, never cuts the tail |
| `--threshold X` | 12.0 | mean grey-level difference (0-255) against the last kept frame that keeps a frame |
| `--max-gap S` | 3.0 | seconds without a kept frame after which one is forced |
| `--block-k K` | 5.0 | keep a frame when any 8x8 block differs by more than K times the threshold; 0 disables |
| `--sample-fps F` | 2.0 | thumbnails per second analysed |
| `--from S`, `--to S` | whole video | analyse a range only; times in the output stay absolute |
| `--segment S` | 120 | length of the `segments` index in `frames.json` |
| `--sheet-width PX` | 1568 | longest side of a contact sheet |
| `--rows N`, `--tile-width PX` | as many rows as fit, tile by aspect ratio | override the grid |
| `--selector events` | `legacy` | pick frames from changed pixels at native resolution instead of 32x32 thumbnails, see below |
| `--dry-run` | | print the selected times and the layout, extract nothing |
| `--force` | | overwrite an output directory that holds `frame-*.jpg` from something else |

Layout by aspect ratio: phone screens get 256 px tiles in 6 columns, desktop windows 516 px in 3, wide
desktops 776 px in 2, so UI text stays readable after the model downscales the sheet.

**Long recordings.** The cap first stretches the gap between timer frames until they alone fit, then raises
the threshold until everything fits. When that pushes the threshold past the point where the block rule can
fire, a second fit reserves half the cap for content and gives unused slots back to the timer; it is kept only
if it finds more content frames. On a 20-minute concatenation of test recordings that turned 0 content frames
out of 24 into 18. The console still says when the cap was binding: `block rule inactive` when the bar passed
255, and `N of M frames by the timer` with what `--max-frames 48` and `72` would buy, computed on the same
thumbnails. `segments[].activity` in `frames.json` shows where the picture moved, so a reader can zoom with
`--from/--to` on the right stretch instead of raising the cap.

**Pale screens.** A light page on a wide screen barely moves the 32x32 thumbnail. On a 2560x1228 recording, DevTools opening over a third of the screen changed it by 3.6 of 255; on the demo shop, going from the cart to the checkout form changed it by 2.5, both under the default threshold 12. Where the timer alone kept at least three frames in a row between two other frames, or every frame between the first and the last (as on a short recording), seenby looks at that stretch again with a threshold of a third of the largest change inside it, never below 1.0, as long as the result fits the cap; the console and `analysis.quiet` say so. Measured on 18 recordings, it changed the 7 with such stretches (the pale recording went from 0 to 9 frames kept for a change, with the frame showing the reported bug among them; two short recordings went from 3 to 6 frames) and left the other 11 byte for byte. It does not run when the cap was binding; narrow a long recording with `--from/--to` first.

## The events selector (`--selector events`)

The default selector decides with one number, the mean grey difference of two 32x32 thumbnails of the whole frame. That number is the changed share of the frame times the contrast, so it misses exactly the changes a UI bug report is about: a 16 px checkbox on a wide window scores 0.06 against a threshold of 12, a page change on a light site 2.5. `--selector events` measures changes where they happen instead. ffmpeg compares every pixel's luma with the previous sample, four per second, and counts the pixels that moved by more than 24 in 8x8 px cells. Changed cells group into areas; two alike pointer-sized areas and nothing else are the pointer moving. Changes of one screen area are one event, visible from the moment it settles until the next change of that area. seenby keeps the fewest frames that show every event's settled state, plus the first and the last, up to `--max-frames`. There is no timer: a stretch where nothing but the pointer moved gets no frame.

    python3 seenby.py recording.mp4 --selector events

```
demo.mp4: 27.1 s, 814x872, portrait
  109 samples at 4 per second, 106 changes, 16 pointer moves, selected 24/24
  frames: 0.00 first, 0.50 change, 1.50 change, 3.25 change, ..., 26.50 change, 27.00 last
  ignored a blinking area at 120,608 8x32 px (4 times from 2.00 to 3.50 s): a text caret, or a small mark toggled back and forth
  layout: window, tile 516 px, 3x2 per sheet
```

Here every change fit in 24 frames. When they do not fit the cap, a line under the frames says how many were not shown, how many frames all of them would need, and which stretch to rerun with `--from/--to`, for example `151 of 272 changes not shown within 24 frames (all of them would need 131); 36 of them from 0.50 to 26.50 s: rerun with --from 0.00 --to 27.50` on a 20 minute concatenation of test recordings. When nothing changed, a line says so and counts the pointer-like moves (a radio button's dot jumping between options looks like the pointer). A one-cell-wide spot that keeps flipping between the same two looks, a text caret, is ignored and named with the stretch it blinked in; it does not cut short the text typed next to it, and a pointer move in the same moment still counts as the pointer. A 2 px caret that straddles two cells, and a terminal's block cursor, are still counted as changes. The top-level `events` in `frames.json` lists every change found with its `region` in native pixels and whether a kept frame shows it. Frame reasons are `first`, `change` (a settled state), `state` (a short state inside a quick series, shown when the cap has room), `during` and `fill` (inside a long continuous change such as a scroll), `last`. Each frame's `recheck` extracts the very frame that was analysed; `--threshold`, `--max-gap`, `--block-k` and `--sample-fps` belong to the default selector and are refused with this one.

Measured on 15 real recordings with ground truth labeled by two independent agents and an adjudicator: the default selector showed 74% of the key events and 63% of all UI changes, the events selector 92% and 88%. Agents who answered 125 questions about these recordings from the output alone scored 80.0% with the default selector and 94.4% with the events selector (a blind judge, two readers per output), with 10 confidently wrong answers against 1. The weak spot is a dense recording, many changes a second for half a minute: then the cap binds and a frame every 0.5 s without a cap does better; rerun such a stretch with `--from/--to`. It takes about twice as long as the default selector on long recordings (18.3 s against 9.2 s on 20 minutes of 720p, 170 MB against 138 MB of memory), because it decodes the range a second time to extract exactly the frames it analysed. It passes frames through with `-fps_mode` on ffmpeg 5.1 and newer and with `-vsync` before that (9.0 removed `-vsync`); it was run with 4.4.1, 5.0.1, 6.1.1 and 9.0.2, and on 13 recordings it picked the same frames with each, except that 9.0.2 decoded one more sample at the end of one recording.

## Speech: seenby_report.py

```
pip install -r requirements-whisper.txt
python3 seenby_report.py recording.mp4 [out-dir] [--model large-v3-turbo] [--device auto|cuda|cpu]
[--transcribe-anyway] [core options]
```

Runs the core, measures the audio level, and only when it is above a gate (-45 dB peak, -80 dB mean) loads a
whisper model (`faster-whisper`) and transcribes; a recording without an audio track counts as silent. Writes
`report.md` next to the frames: one section per frame with the
speech of its interval (a sentence crossing a frame boundary appears under both frames, marked continued; a
low-confidence line gets `(?)`), the whole speech with timecodes, and the reading rule. Silent recordings never
load a model. Options the wrapper does not know go to the core unchanged. On a GPU the model runs in float16
with a CUDA 12 toolkit from the pip wheels; without one it falls back to CPU int8.

## Guarantees

- The first and the last sampled frame are always kept. The last sample sits up to one sampling interval
  before the end (under 1 s at the default 2 per second; 0.3 to 0.8 s on the ten test recordings). The cap
  raises the threshold; it never cuts the tail.
- No sheet is wider or taller than `--sheet-width` (1568 px) unless you override `--rows` or `--tile-width`.
  The one exception is an aspect ratio so extreme that a single row is already taller; then the sheet is one
  row.
- A failed run leaves no `frames.json`; the previous manifest is removed before ffmpeg is called.
- An output directory holding `frame-*.jpg` without our `frames.json` is refused (`--force` overrides).
- When every frame came from the timer and there are at least five of them, the console and the manifest say
  so (`all_timer`). Below five frames the statement would be empty and is not made.

## Limitations

- 2 thumbnails per second: a state shorter than about 500 ms (a flash, a tooltip) can be missed, and the "last
  frame" is the last sampled one, up to a sampling interval before the end. `--sample-fps 4`
  halves that; a burst mode around change points is planned.
- Pixel difference is not understanding. A frame is kept because the picture changed, not because something
  happened.
- The block metric's grid is fixed: a change smaller than a block or on a block boundary is under-reported,
  up to 4x at a corner. `K` was picked on ten recordings and the useful range is narrow.
- Under a tight cap the block rule raises the shared threshold, so a mean-difference frame can be traded for a
  timer frame.
- The 32x32 thumbnail squashes the aspect ratio; the comparison is coarse by design.
- JPEG bytes depend on the ffmpeg build. Two runs in one directory at the same time conflict.
- Camera footage of a screen works for an overview, but text on the sheet will not be readable; this tool is
  for screen recordings.
- The audio gate thresholds (-45 dB peak, -80 dB mean) separate nine silent recordings from one noisy one and
  have not been checked against real speech yet; use `--transcribe-anyway` when in doubt. Whisper on background
noise produces a short hallucination; the report
  shows the language probability and coverage so you can tell.

## Compared with claude-real-video and clipsheet

Measured once, on ten screen recordings (phone and desktop, 4.7 to 37.7 s) plus one 20-minute concatenation
of them. `claude-real-video` catches local UI changes well (on one recording 14 of its 18 frames came from its
motion channel) but lost the final screen on 3 of the 10 recordings and on the concatenation, and cuts the
tail when its frame limit hits. `clipsheet` lost the ending on 7 of the 11. seenby kept the ending on all 11.
At the time of that comparison seenby had no block metric and missed the same local changes; the block metric
came later and has not been re-measured against `claude-real-video`. It aims at screen recordings only: on
camera footage with cuts `claude-real-video` has scene detection and a motion channel that seenby does not
try to match. A side-by-side table on public recordings will replace this paragraph.

## The skill

`skills/seenby/SKILL.md` teaches an agent when to run seenby, how to read `frames.json`, and what to do when the console warns. The folder also holds copies of both scripts and `requirements-whisper.txt`, so an installed skill runs without the repository. The copies are byte-for-byte the files at the root. Any agent with a terminal can also run the scripts directly; the skill is a convenience.

## Tests

```
pip install -r requirements-dev.txt
python3 -m pytest -q tests
```

Acceptance tests come from the specs in `docs/specs/` (rule IDs, example tables, properties) and need no
ffmpeg. The ffmpeg stages are covered by a byte-for-byte regression against recordings that are not in the
repository.

## License

MIT, see `LICENSE`.

## Contributing

See `CONTRIBUTING.md`: behaviour is defined in the specs, tests follow the specs, the core stays dependency-free.
