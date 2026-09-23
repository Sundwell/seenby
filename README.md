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

ffmpeg's scene detection compares each frame with the previous one. Someone recording a phone screen scrolls
smoothly, so neighbouring frames are nearly identical and no threshold ever fires. Measured on four real
customer recordings: scene detection returned zero frames.

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

The agent picks the skill by its name and description. With many skills installed and a model with a 200K context, Claude Code drops the descriptions of rarely used skills from its listing and the agent sees only the name. If the agent does not reach for it, call it directly with `/seenby:read-screen-recording` (plugin) or `/read-screen-recording` (`npx skills`) in Claude Code, `/skill:read-screen-recording` in Pi, or `$` and the skill in Codex. In Claude Code the `skillListingBudgetFraction` setting (for example `0.02`) keeps more descriptions.

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
  54 thumbnails, selected 12/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)
  frames: 0.0 first, 3.0 timer, 3.5 block, 6.5 timer, 9.5 timer, 11.0 block, ..., 26.5 last
  layout: window, tile 516 px, 3x2 per sheet
  contact sheets: demo-frames/sheet-01.jpg, demo-frames/sheet-02.jpg
  manifest: demo-frames/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.
```

When every frame was taken by the timer and the threshold contributed nothing, a line says so and suggests
what to change. Exit codes: 0 done, 1 could not run (one line on stderr, no traceback), 2 bad arguments.

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
               "all_timer": false, "timer_share": 0.7},
  "sheet": {"cols": 3, "rows": 2, "tile_width": 516, "sheet_width": 1568, "count": 2},
  "frames": [
    {"n": 1, "time": 0.0, "file": "frame-01-0.0s.jpg", "sheet": 1, "reason": "first", "diff": 0.0, "block": 0.0,
     "recheck": "ffmpeg -ss 0.000 -i demo.mp4 -frames:v 1 -q:v 2 demo-frames/frame-01-native.jpg"},
    {"n": 3, "time": 3.5, "file": "frame-03-3.5s.jpg", "sheet": 1, "reason": "block", "diff": 6.9, "block": 77.1,
     "recheck": "..."}
  ],
  "sheets": [{"file": "sheet-01.jpg", "frames": [1, 6]}, {"file": "sheet-02.jpg", "frames": [7, 12]}],
  "segments": [{"n": 1, "from": 0.0, "to": 27.1, "frames": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                "activity": 4.3}]
}
```

Numbers in the file are full floats (`6.9111328125`), rounded here for reading. `timer_share` is the share of timer
frames among those the selection loop chose; `block_active` says whether the block rule could still fire at the
effective threshold. `reason` is why the frame was kept: `first`, `diff` (mean difference above the threshold),
`block` (one 8x8 block of the thumbnail changed strongly), `timer` (forced after `max_gap` seconds), `last`.
`segments` index the frames by stretches of `--segment` seconds, with `activity` (mean change between consecutive
thumbnails, 0 to 255) per stretch, so a reader of a long recording knows where to zoom in.

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

`skills/read-screen-recording/SKILL.md` teaches an agent when to run seenby, how to read `frames.json`, and what to do when the console warns. The folder also holds copies of both scripts and `requirements-whisper.txt`, so an installed skill runs without the repository. The copies are byte-for-byte the files at the root. Any agent with a terminal can also run the scripts directly; the skill is a convenience.

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
