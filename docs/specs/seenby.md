# seenby

Status anchored for SEL-1..6, CAP-1..9, CLN-1, CLN-3..4, ENV-1..2, CLI-1, CLI-3..4, CLI-6..7, CLI-9..13,
CLI-15..17, CLI-19..20, CLI-22, REC-2..9, PRB-1..3, TOOL-1..3, DIR-1..2, JSN-1..3, MAN-1..4, MAN-7..13, MAN-15,
BLK-1..2, LAY-1..6, SEG-1..4, FF-1..7 (code exists, tests green).
CLI-23 anchored 2026-09-17 (the "by the timer" line triggers on an active cap alone; supersedes CLI-22).
Step 10 2026-09-26: CLI-24 implemented (tests green) (the all-timer line names --threshold; amends CLI-23).
Step 11 2026-09-26: SEL-7, REC-10, CLI-25, MAN-16 implemented (tests green); review amendments to REC-10 and MAN-16 implemented (tests green) (quiet stretches get their own threshold; MAN-16 replaces MAN-15).
Step 12 2026-09-27: GRD-1..2, BLB-1..3, PTR-1, EVT-1..3, PCK-1..4, CLI-26..27, MAN-17, FF-9 implemented (tests green); FF-8 removed (superseded by FF-9). Review amendments (EVT-4, FF-10, parts of PCK-4, CLI-26, CLI-27, MAN-17, FF-9, GRD-1) implemented the same day. Re-review amendments (FF-11, EVT-4 rewritten, parts of GRD-1, PCK-2, CLI-27, MAN-17, FF-9) implemented 2026-09-27 (tests green). Final-review amendments (EVT-4 rewritten again, CARET_H, the CLI-27 blinking line) implemented 2026-09-27 (tests green). Last-check amendments (EVT-4 runs by walk, EVT-3 holes by time) implemented 2026-09-27 (tests green).
Step 13 2026-09-27: CLI-28 implemented (tests green); its help texts of the legacy-only options and the too-small message amended after review (implemented, tests green) (the events selector is the default; CLI-26's default `legacy` is superseded).
Step 14 2026-09-27: LBL-1..3 implemented (tests green); review amendments (row 21 of the band, frame order on the sheet, the ffprobe error) implemented (tests green) (a label band with the frame number and time above every tile of a sheet; LAY-3 and FF-4 amended).
Step 15 2026-09-27: BOX-1..3 and BOX-P1 implemented (tests green); review amendments (a box on the first frame of the change's life where it is visible at native resolution in some 2x2 cells, boxes not cut at the tile's edge, the length guard) and BOX-5 implemented (tests green); BOX-4 removed (magenta boxes around changes on the sheets of the events selector; LBL-2 amended).
Step 16 2026-09-29: CRP-1..8 and CRP-P1 drafted over the code published 2026-09-28; amended 2026-10-04 after the first feedback (CRP-8, the tile's frame as the middle picture, the console lines) (crops of every change at native size before and after, a full frame per screen, numbers next to the boxes, the crop of each event in `frames.json`; LBL-1, BOX-2, BOX-3, CLN-4 and MAN-17 amended).
Step 17 2026-10-04: CRP-9..16 drafted and implemented after the review of the crops, tests green after tester round 16 (the comparison of two pictures by luma with a count for strong changes, the last screen kept, one number per box placed where it covers nothing, any failure of the crops survived, the guard over `screen-*.jpg` and `crops-*.png`, bounded memory, numbered pages; DIR-1, DIR-2, LBL-1, LBL-2, CRP-1, CRP-3, CRP-4, CRP-5 and CRP-6 amended).
Step 18 2026-10-04: CRP-17..18 drafted and implemented, tests green after tester round 17 (a mark takes the free place around its box where the frame is emptiest, judged by the cell means of the frame; CRP-11 and CRP-13 amended).
Removed: CLN-2, CLI-2, CLI-5, CLI-8, CLI-14, CLI-18, CLI-21, CLI-22, REC-1, MAN-5, MAN-6, MAN-14, FF-8, BOX-4 (each names
its successor). Sections keep the heading of the step that
introduced them so the IDs stay where they were born. Tests `tests/test_seenby.py`. Public surface:
`docs/specs/api/seenby.txt`.

## Purpose

Picks the frames of a screen recording an agent should look at. Since step 13 the default is the events selector (step 12): changed pixels are counted at native resolution, changes of one screen area make an event, and the frames are the fewest that show every event, plus the first and the last, up to a cap. The rules of steps 1 to 11 describe the legacy selector, kept behind `--selector legacy`: a thumbnail is kept when it differs from the last kept one, is forced every `max_gap` seconds, the last one is always kept, and a cap on the number of frames raises the threshold instead of cutting the tail. ffmpeg does the decoding and the contact sheets.

## Vocabulary

- A thumbnail is `bytes` of length `THUMB * THUMB` (1024), one grey level per pixel, 0..255.
- Thumbnail `i` has time `i / SAMPLE_FPS` seconds (`SAMPLE_FPS` is 2, so 0.0, 0.5, 1.0, ...).
- The difference of two thumbnails is the mean of the absolute byte differences, a float in 0..255.
- `flat(v)` is one thumbnail `bytes([v]) * 1024`. `static(n)` is `[flat(0)] * n`. `alt(n)` is n thumbnails
  alternating `flat(0)`, `flat(255)`, `flat(0)`, ... starting with 0 (difference 255 between neighbours).
  `half(v)` is `bytes([0]) * 512 + bytes([v]) * 512` (difference against `flat(0)` is v / 2).
- Times are printed and compared as floats; `%.1f` formatting is exact for multiples of 0.5.

## Public surface

    SAMPLE_FPS = 2
    THRESHOLD = 12.0
    MAX_GAP = 3.0
    MAX_FRAMES = 24
    THUMB = 32
    def select(thumbs, threshold, max_gap)
    def fit_to_cap(thumbs, max_frames, threshold, max_gap)
    def clean(out_dir)
    def ffmpeg()
    def ffprobe()
    def main()
    def probe(path)                                 [hands-on]
    def thumbnails(path)                            [hands-on]
    def save_frames(path, times, out_dir, tile_width)   [hands-on]
    def contact_sheets(paths, out_dir, cols, rows)  [hands-on]

## Rules

### select(thumbs, threshold, max_gap) -> list of float times

SEL-1  Empty `thumbs` gives `[]`.
       Why. Nothing decoded, nothing to pick; `main()` reports that case itself (CLI-4).

SEL-2  With non-empty `thumbs` the result starts with `0.0`: the first thumbnail is always kept.
       Why. The agent needs the starting screen.

SEL-3  A thumbnail is kept when its difference against the last kept thumbnail is strictly greater than
       `threshold`. The comparison is against the last kept one, not the previous thumbnail, so a slow ramp
       accumulates until it crosses. A difference equal to `threshold` does not keep.
       Why. ffmpeg's scene detection compares neighbours and returns zero frames on smooth scrolling.

SEL-4  A thumbnail at time `t` is kept when `t - time_of_last_kept >= max_gap`, whatever its difference.
       Why. A frame is forced even when nothing changed, so long static stretches are still represented.

SEL-5  The time of the last thumbnail, `(len(thumbs) - 1) / SAMPLE_FPS`, is always the last element: appended
       when the loop did not keep it, not duplicated when it did.
       Why. In a screen recording the end is the result. A selection once stopped at 28.5 s of a 31.3 s video and
       missed the order confirmation screen.

SEL-6  The result is strictly increasing, every value is `k / SAMPLE_FPS` for an integer `k`, and every value
       lies in `[0.0, (len(thumbs) - 1) / SAMPLE_FPS]`.
       Why. Times are fed to `ffmpeg -ss` one by one and name the frames in order.

### fit_to_cap(thumbs, max_frames, threshold, max_gap) -> (times, threshold, max_gap)

Precondition: `max_frames >= 2`. With fewer than 2 the call never returns when `thumbs` has 2 or more
entries (the first and last are always kept); `main()` rejects it (CLI-3). Do not test it.

CAP-1  `len(times) <= max_frames`.
       Why. A contact sheet with more tiles becomes unreadable.

CAP-2  When `select(thumbs, threshold, max_gap)` already fits, `times` equals it and `threshold` and `max_gap`
       come back unchanged.
       Why. Defaults must not drift on short recordings. This relies on the forced-only selection (CAP-3) never
       being larger than the real one, which holds because every forced frame is also kept by the real selection.

CAP-3  The gap is stretched first: `gap = max_gap`, then repeatedly `gap = gap * 1.25` until
       `select(thumbs, 256.0, gap)` (forced frames only, since no difference exceeds 255) fits the cap. The
       returned `max_gap` is that repeated product with the fewest multiplications. It is a repeated product,
       not `max_gap * 1.25 ** k`: the two differ in the last bit for some floats, so compare against the
       product loop or use the exact example values.
       Why. When the forced frames alone exceed the cap, raising the threshold changes nothing.

CAP-4  Then repeatedly `threshold = threshold * 1.5` until `select(thumbs, threshold, gap)` fits. The returned
       `threshold` is that repeated product with the fewest multiplications (same remark as CAP-3 about
       `** m`), and `times` equals `select(thumbs, returned_threshold, returned_max_gap)`.
       Why. The cap raises the threshold instead of cutting the tail.

CAP-5  The last thumbnail time is the last element of `times` (inherits SEL-5): on a static 120 s input with
       cap 24 the selection ends at 119.5, not 115.0.
       Why. An earlier `[:max_frames]` fallback cut exactly the last frame.

CAP-6  Empty `thumbs` gives `([], threshold, max_gap)`.

### clean(out_dir)

CLN-1  Removes every entry directly in `out_dir` whose name starts with `frame-` or `sheet` and ends with
       `.jpg`. Case-sensitive, name-based. `sheet.jpg` and `sheets-02.jpg` match, `Frame-01.jpg` and
       `frame-01.png` do not. A symlink with a matching name is unlinked, its target stays. A directory with a
       matching name raises `IsADirectoryError`; do not test that.
       Why. Sheets are built from the `frame-%02d.jpg` sequence in the directory; stale frames from a previous
       run would be tiled into this one.

CLN-2  removed, superseded by CLN-4 (`frames.json` and `report.md` are now ours and go too).

CLN-3  Raises `FileNotFoundError` when `out_dir` does not exist. (`save_frames` creates the directory before
       calling it.)

### ffmpeg(), ffprobe()

ENV-1  `ffmpeg()` returns the value of environment variable `FFMPEG` when it is set, else the string `'ffmpeg'`.
ENV-2  `ffprobe()` returns `FFPROBE` when set, else `'ffprobe'`.
       Why. A machine without ffmpeg on PATH points at a binary this way.

### main() -> int

How to test. Replace `sys.argv`, and replace the four ffmpeg-facing functions on the module (`seenby.probe`,
`seenby.thumbnails`, `seenby.save_frames`, `seenby.contact_sheets`) with fakes through `monkeypatch.setattr`;
they are public names in the API listing. `probe` returns `(duration, width, height)`, `thumbnails` returns a
list of thumbnails, `save_frames(path, times, out_dir, tile_width)` returns the list of frame paths it would
have written, `contact_sheets(paths, out_dir, cols, rows)` returns the list of sheet paths. Read stdout with
`capsys`. No file is written by `main()` itself. `argv` in the rules and rows below is the list after the program
name: set `sys.argv = ['seenby.py'] + argv`. The CLI-3 rows need no fakes: argparse exits before `probe` is
called. `sys` and `monkeypatch` are not in the API listing and do not need to be; they are test machinery.

CLI-1  Positional `video` is required; positional `out_dir` is optional and defaults to the video path with its
       extension removed plus `-frames` (`video.mp4` -> `video-frames`, `a/b.MOV` -> `a/b-frames`).

CLI-2  removed, superseded by CLI-10 (bounds on `--threshold` and `--max-gap`, `--force`, help texts).

CLI-3  `--max-frames` below 2 is an argparse error: `SystemExit` with code 2, and stderr contains
       `--max-frames must be at least 2: the first and last frames are always kept` (argparse prefixes it with
       usage and `seenby.py: error: `, so test with "contains", not equality). Missing `video` and unknown
       flags also exit with code 2.

CLI-4  When `thumbnails()` returns `[]`, `main()` prints `could not decode the video: no frames` to stderr,
       returns 1, prints nothing to stdout (`probe` was already called, nothing of it is printed), and
       `save_frames` is not called.

CLI-5  removed, superseded by LAY-1..4 and MAN-12 (three grades by aspect ratio, tile and grid from `layout()`;
       `orientation` stays in the manifest, MAN-3).

CLI-6  `save_frames` is called once with `(video, times, out_dir, tile_width)` where `times` is exactly the
       `fit_to_cap` result and `out_dir` is the resolved output directory.

CLI-7  `contact_sheets(paths, out_dir, cols, rows)` is called only when `save_frames` returned more than one
       path, and `paths` is exactly the list `save_frames` returned. With exactly one path it is not called and
       the fourth stdout line lists that frame path instead.

CLI-8  removed, superseded by CLI-14 (stdout grows to five or six lines with reasons and the manifest).

CLI-9  The first line starts with the basename of the video path and uses `probe`'s duration, width and height
       verbatim: argv `['a/b.MOV']` with `(15.0, 800, 600)` prints `b.MOV: 15.0 s, 800x600, landscape`.

### ffmpeg stages

FF-1  [hands-on] `probe(path)` returns `(duration, width, height)` of the first video stream via ffprobe.
FF-2  [hands-on] `thumbnails(path)` returns grey `THUMB x THUMB` thumbnails at `SAMPLE_FPS` per second, decoded
      in memory, never written to disk.
FF-3  [hands-on] `save_frames` writes `frame-01.jpg`, `frame-02.jpg`, ... scaled to `tile_width`, after
      `clean(out_dir)`.
FF-4  [hands-on] `contact_sheets` writes `sheet-01.jpg`, ... with `cols` columns, at most `rows` rows, margin 6,
      padding 4, from the `frame-%02d.jpg` sequence.
      Evidence for FF-1..4: the maintainer's byte-for-byte regression script, run against baselines that are not in the repository, prints `mismatches: 0` and
      `sha256sum -c tools/baseline.sha256` passes (59 files, ffmpeg 6.1.1). Both need the private recordings.

## Examples

`T` is `THRESHOLD` (12.0), `G` is `MAX_GAP` (3.0). `static`, `alt`, `flat`, `half` as in Vocabulary. For `main()`
rows, `probe` returns `(15.0, 800, 600)` unless the row says otherwise, and the fake `save_frames` returns
`['<out_dir>/frame-01.jpg', ...]`, one path per time, unless the row says otherwise.

| ID | Input | Result |
|---|---|---|
| SEL-1 | `select([], T, G)` | `[]` |
| SEL-2, SEL-5 | `select(static(1), T, G)` | `[0.0]` |
| SEL-4, SEL-5 | `select(static(20), T, G)` | `[0.0, 3.0, 6.0, 9.0, 9.5]` |
| SEL-4, SEL-5 | `select(static(7), T, G)` | `[0.0, 3.0]` (last thumbnail is at 3.0 and forced; not duplicated) |
| SEL-3 | `select([flat(0), flat(12), flat(13), flat(13)], T, 100.0)` | `[0.0, 1.0, 1.5]` (12.0 equals T, not kept; 13.0 kept; 1.5 is the last) |
| SEL-3 | `select([flat(0), half(24), half(26), flat(0)], T, 100.0)` | `[0.0, 1.0, 1.5]` (half(24) differs by 12.0 from flat(0), not kept; half(26) by 13.0, kept; flat(0) differs by 13.0 from half(26), kept) |
| SEL-3 | `select([flat(v) for v in (0, 5, 10, 15, 20, 25, 30, 35, 40, 45)], T, 100.0)` | `[0.0, 1.5, 3.0, 4.5]` (ramp accumulates against the last kept: 15, then 30, then 45) |
| SEL-3, SEL-5 | `select(alt(4), 300.0, 100.0)` | `[0.0, 1.5]` (nothing beats 300, nothing forced, 1.5 appended) |
| SEL-3 | `select(alt(20), T, G)` | `[i / 2 for i in range(20)]` (every thumbnail) |
| CAP-6 | `fit_to_cap([], 24, T, G)` | `([], 12.0, 3.0)` |
| CAP-2 | `fit_to_cap(static(20), 24, T, G)` | `([0.0, 3.0, 6.0, 9.0, 9.5], 12.0, 3.0)` |
| CAP-2 | `fit_to_cap(alt(20), 24, T, G)` | `([i / 2 for i in range(20)], 12.0, 3.0)` |
| CAP-3, CAP-5 | `fit_to_cap(static(240), 24, T, G)` | `([0.0] + [float(t) for t in range(6, 115, 6)] + [119.5], 12.0, 5.859375)` (21 entries; gap 3.0 -> 3.75 -> 4.6875 -> 5.859375 is the first that fits) |
| CAP-4 | `fit_to_cap(alt(20), 5, T, G)` | `([0.0, 3.0, 6.0, 9.0, 9.5], 307.546875, 3.0)` |
| CAP-1, CAP-4 | `fit_to_cap(alt(20), 8, T, G)` | `([0.0, 3.0, 6.0, 9.0, 9.5], 307.546875, 3.0)` (5 entries under a cap of 8, not 8) |
| CAP-3, CAP-4 | `fit_to_cap(alt(20), 2, T, G)` | `([0.0, 9.5], 307.546875, 9.1552734375)` |
| CLN-1, CLN-4 | directory with files `frame-01.jpg`, `frame-10.jpg`, `sheet-01.jpg`, `sheet.jpg`, `sheets-02.jpg`, `frame-01.png`, `frames.json`, `report.md`, `other.jpg`, `Frame-01.jpg` and a subdirectory `notes`, then `clean(dir)` | remaining: `Frame-01.jpg`, `frame-01.png`, `notes`, `other.jpg` |
| CLN-3 | `clean(tmp_path / 'missing')` | raises `FileNotFoundError` |
| ENV-1 | `FFMPEG=/opt/ff` set, `ffmpeg()` | `'/opt/ff'` |
| ENV-1 | `FFMPEG` unset, `ffmpeg()` | `'ffmpeg'` |
| ENV-2 | `FFPROBE=/opt/fp` set, `ffprobe()` | `'/opt/fp'` |
| ENV-2 | `FFPROBE` unset, `ffprobe()` | `'ffprobe'` |
| CLI-1, CLI-5, CLI-6, CLI-7 | argv `['video.mp4']`, thumbnails `static(30)`, fake `contact_sheets` returns `['video-frames/sheet-01.jpg']` | return 0; `save_frames` called once with `('video.mp4', [0.0, 3.0, 6.0, 9.0, 12.0, 14.5], 'video-frames', 780)`; `contact_sheets` called once with `(<the 6 paths save_frames returned>, 'video-frames', 2, 3)`; first line `video.mp4: 15.0 s, 800x600, landscape`; the "contact sheets" line is `  contact sheets: video-frames/sheet-01.jpg` (full stdout: CLI-14) |
| CLI-1, CLI-9 | argv `['a/b.MOV']`, thumbnails `static(4)` | `save_frames` gets `out_dir` `'a/b-frames'`; first line `b.MOV: 15.0 s, 800x600, landscape` |
| CLI-5 | argv `['video.mp4', 'out']`, probe `(15.0, 600, 800)`, thumbnails `static(30)` | first line `video.mp4: 15.0 s, 600x800, portrait`; `save_frames` gets `tile_width` 260 and `out_dir` `'out'`; `contact_sheets` gets `cols` 6, `rows` 4 |
| CLI-5 | argv `['video.mp4', 'out']`, probe `(15.0, 500, 500)`, thumbnails `static(30)` | first line ends with `landscape`; `save_frames` gets 780; `contact_sheets` gets `cols` 2, `rows` 3 |
| CLI-10, CLI-14 | argv `['video.mp4', 'out', '--threshold', '300', '--max-gap', '7']`, thumbnails `alt(30)` | second line `  30 thumbnails, selected 4/24 (threshold 300.0 -> 300.0, max gap 7.0 -> 7.0 s)`; third line `  frames: 0.0 first, 7.0 timer, 14.0 timer, 14.5 last` |
| CLI-7 | argv `['video.mp4', 'out']`, thumbnails `static(1)`, fake `save_frames` returns `['out/frame-01.jpg']` | `contact_sheets` not called; the "contact sheets" line is `  contact sheets: out/frame-01.jpg`; second line `  1 thumbnails, selected 1/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)` |
| CLI-4 | argv `['video.mp4', 'out']`, thumbnails `[]` | return 1; stderr contains `could not decode the video: no frames`; stdout is `''`; `save_frames` not called |
| CLI-3 | argv `['video.mp4', 'out', '--max-frames', '1']` | `SystemExit` code 2; stderr contains `--max-frames must be at least 2: the first and last frames are always kept` |
| CLI-3 | argv `[]` | `SystemExit` code 2 |
| CLI-3 | argv `['video.mp4', '--bogus']` | `SystemExit` code 2 |

## Properties

Generators: `thumbs` is a list of 0..60 thumbnails, each `bytes` of length 1024 drawn from any byte values
(Hypothesis `st.binary(min_size=1024, max_size=1024)`); `threshold` a float in `[0.1, 300.0]`; `max_gap` a float
in `[0.5, 30.0]`; `max_frames` an integer in `[2, 30]`. `threshold` must stay above 0: `fit_to_cap` multiplies
it by 1.5, and 0.0 times 1.5 never crosses anything.

SEL-P1  For any `thumbs`, `threshold`, `max_gap`: the result is strictly increasing; empty iff `thumbs` is empty;
        otherwise its first element is `0.0`, its last is `(len(thumbs) - 1) / SAMPLE_FPS`, and each element
        times `SAMPLE_FPS` is an integer.

SEL-P2  For any `thumbs` and `threshold`, with `max_gap` = 0.5: every thumbnail is kept (result has `len(thumbs)`
        entries).

CAP-P1  For any `thumbs`, `max_frames`, `threshold`, `max_gap`: `len(times) <= max_frames`;
        `returned_threshold >= threshold`; `returned_max_gap >= max_gap`; and
        `times == select(thumbs, returned_threshold, returned_max_gap)`.

CAP-P2  For any `thumbs` with 2 or more entries and any `max_frames`: `times[0] == 0.0` and
        `times[-1] == (len(thumbs) - 1) / SAMPLE_FPS`.

CLN-P1  For any set of file names built from the alphabet `{frame-, sheet, Frame-, other}` x `{01, 02}` x
        `{.jpg, .png, .json}` created in `tmp_path`: after `clean`, exactly the names that start with `frame-` or
        `sheet` and end with `.jpg` are gone, and the rest remain.

## Errors

- `select`, `fit_to_cap`: raise nothing on inputs from the generators above. Thumbnails of unequal length are
  undefined, do not test. `select` with `max_gap <= 0` or `threshold < 0` returns every thumbnail and
  terminates; outside the generators, do not test. `fit_to_cap` never returns, when the selection exceeds the
  cap, with `max_frames < 2`, `threshold <= 0.0` or `max_gap <= 0.0`: multiplying 0 or a negative number never
  crosses anything. Do not call it with those values and do not pass them to `main()` through `--threshold` or
  `--max-gap`.
- `clean`: `FileNotFoundError` on a missing directory (CLN-3), `IsADirectoryError` on a matching directory name
  (CLN-1). Nothing is swallowed.
- `probe`: swallows `ValueError` while parsing ffprobe output and returns zeros, which `main()` prints as
  `0.0 s, 0x0, landscape`. Hands-on (FF-1), do not pin; a later step makes it fatal.
- `main`: `SystemExit(2)` for argparse errors (CLI-3). Return value 1 for no thumbnails (CLI-4). A failing ffmpeg
  stage propagates `subprocess.CalledProcessError` as a traceback; that behaviour is not a rule and changes in a
  later step, do not pin it.

## Reliability and frames.json (drafted and implemented 2026-09-16)

Anchored since 2026-09-16. Written as a draft before the code existed; the tester wrote red tests from it, then
the executor implemented it.

### Public surface added

    VERSION = 1
    def select_frames(thumbs, threshold, max_gap)
    def parse_probe(text)
    def require_tools()
    def ffmpeg_version()                           [hands-on]
    def check_out_dir(out_dir, force)
    def write_json(path, data)

Unchanged: `select`, `fit_to_cap`, `clean`, `ffmpeg`, `ffprobe`, `main`, the constants, and the four ffmpeg stages.
`probe(path)` now returns `parse_probe(<ffprobe output>)`, still hands-on.

### select_frames(thumbs, threshold, max_gap) -> list of dicts

REC-1  removed, superseded by REC-7 (the entries gain a `block` key).

REC-2  The first entry has `reason` `'first'` and `diff` `0.0`.

REC-3  A thumbnail kept because its difference against the previous kept one is strictly greater than
       `threshold` has `reason` `'diff'` and `diff` equal to that difference (float). When the difference and the
       gap condition both hold, `'diff'` wins.

REC-4  A thumbnail kept only because `t - time_of_last_kept >= max_gap` has `reason` `'timer'` and `diff` equal
       to its difference against the previous kept one.

REC-5  The last thumbnail appended by the SEL-5 rule (not kept by the loop) has `reason` `'last'` and `diff`
       equal to its difference against the previous kept one. When the last thumbnail was kept by the loop, its
       reason is whatever kept it. A single thumbnail gives one entry with reason `'first'`.

### parse_probe(text) -> (duration, width, height)

`text` is the stdout of `ffprobe -v error -select_streams v:0 -show_entries format=duration:stream=width,height
-of csv=p=0 <video>`: one line `<width>,<height>` for the stream, one line `<duration>` for the format, in either
order, possibly with a trailing newline.

PRB-1  Returns `(float(duration), int(width), int(height))`. `"814,872\\n37.700000\\n"` gives `(37.7, 814, 872)`.
PRB-2  Line order does not matter; empty lines are ignored.
PRB-3  Raises `ValueError` whose message contains `ffprobe` when the duration line is missing or not a number,
       the size line is missing, or any of the three values is not above 0. Examples: `""`, `"814,872\\n"`,
       `"37.7\\n"`, `"0,0\\n37.7\\n"`, `"814,872\\nN/A\\n"`.
       Why. Without this a broken probe produced `scale=0:-1`, exit 0 and a wrong sheet.

### require_tools() -> None or str

TOOL-1 Returns `None` when `shutil.which(ffmpeg())` and `shutil.which(ffprobe())` both find an executable.
TOOL-2 Returns `'ffmpeg not found. Install ffmpeg or set FFMPEG=/path/to/ffmpeg'` when `ffmpeg()` is not found.
TOOL-3 Returns `'ffprobe not found. Install ffmpeg or set FFPROBE=/path/to/ffprobe'` when ffmpeg is found but
       `ffprobe()` is not.
       How to test. Point `FFMPEG` / `FFPROBE` at an executable file created in `tmp_path` (`chmod 0o755`) or at
       `tmp_path / 'nope'`.

### check_out_dir(out_dir, force) -> None or str

`out_dir` is a `str` or a path-like object; the message uses it as given (`str(out_dir)`).

DIR-1  Returns `None` when `out_dir` does not exist, is empty, contains no file matching `frame-*.jpg`, contains
       `frames.json`, or `force` is true. (Amended by CRP-14, step 17: `screen-*.jpg` and `crops-*.png` are guarded
       like `frame-*.jpg`.)
DIR-2  Returns `'<out_dir> already holds frame-*.jpg from something else; pass --force to overwrite'` when
       `out_dir` contains at least one `frame-*.jpg`, no `frames.json`, and `force` is false. `<out_dir>` is the
       argument as given.
       Why. Our sheets are tiled from the `frame-%02d.jpg` sequence; a stranger's frames would be tiled in.

### write_json(path, data)

JSN-1  Writes `data` as JSON with `indent=2` and `ensure_ascii=False`, followed by a newline; `json.load` of the
       file equals `data`. A non-ASCII string value appears in the file as itself, not as `\\uXXXX`.
JSN-2  Overwrites an existing file at `path`.
JSN-3  Writes through a temporary file in the same directory and `os.replace`: afterwards the directory holds
       `path` and nothing else that was not there before.

### clean(out_dir), amended

CLN-4  In addition to CLN-1, `frames.json` and `report.md` directly in `out_dir` are removed. Every other entry
       stays, files and subdirectories alike: `other.jpg`, `frame-01.png`, `Frame-01.jpg`, a subdirectory `notes`.

### main(), amended

Fakes for the draft rows: as in the anchored "How to test", plus `seenby.require_tools` (returns `None` unless the
row says otherwise) and `seenby.ffmpeg_version` (returns `'ffmpeg version 6.1.1-test'`). The video must exist:
create an empty file in `tmp_path`, `monkeypatch.chdir(tmp_path)`, and pass its relative name in argv. `out_dir`
rows use a name inside `tmp_path`. Once the draft lands, CLI-11 applies to the anchored `main()` rows too: their
tests need the same two fakes and an existing video file (`video.mp4`, `a/b.MOV` inside `tmp_path`); the
anchored rules CLI-1, CLI-3..7, CLI-9 keep their meaning and IDs.

CLI-10 Options: `--threshold` (float, default 12.0, must be above 0), `--max-gap` (float seconds, default 3.0,
       must be above 0), `--max-frames` (int, default 24, at least 2), `--force` (flag). Out of range is an
       argparse error, `SystemExit` code 2, stderr contains `--threshold must be above 0`,
       `--max-gap must be above 0`, or the CLI-3 text. `--help` exits 0 and its stdout contains, for each
       option, one help line with the unit and the default: the substrings `default: 12.0`, `default: 3.0`,
       `default: 24`, `seconds`, `--force`.
       Why. Two real runs reported that `--help` gave no units and no range.

CLI-11 Checks before any ffmpeg call, in this order, each printing one line to stderr and returning 1:
       `require_tools()` returned a string -> that string; `video` is not an existing file ->
       `no such file: <video>`; `check_out_dir(out_dir, force)` returned a string -> that string. On any of
       them `probe`, `thumbnails`, `save_frames`, `contact_sheets` are not called.

CLI-12 A stage failure returns 1 with one stderr line. `probe` raising `ValueError` -> `<video>: <message>`.
       Any of `probe`, `thumbnails`, `save_frames`, `contact_sheets` raising `subprocess.CalledProcessError` ->
       `ffmpeg failed during <stage> (exit <returncode>): <stderr of the error, last line>` where `<stage>` is
       `probe`, `thumbnails`, `frames` or `sheets`. No traceback.

CLI-13 After the CLI-11 checks and before `probe`, `main()` creates `out_dir` if needed (`os.makedirs`,
       `exist_ok`) and calls `clean(out_dir)`, so a previous `frames.json` is gone before any ffmpeg call and a
       run that fails at any stage leaves no manifest. Example: `out_dir` holds `frames.json` and `frame-01.jpg`, `thumbnails` raises
       `CalledProcessError(1, 'ffmpeg', stderr='boom')` -> return 1, `out_dir` has no `frames.json`.

CLI-14 removed, superseded by CLI-18 (a layout line is added and the sheet grid comes from `layout()`).

CLI-15 Return codes: 0 success, 1 runtime failure (CLI-4, CLI-11, CLI-12), 2 argparse (CLI-3, CLI-10).

### frames.json (MAN)

MAN-1  On success `main()` writes `<out_dir>/frames.json` through `write_json` as its last action, after
       `contact_sheets` returned. The file is valid JSON with exactly the top-level keys `tool`, `version`,
       `ffmpeg`, `video`, `analysis`, `sheet`, `frames`, `sheets`.

MAN-2  `tool` is `"seenby"`, `version` is `VERSION` (1), `ffmpeg` is the string `ffmpeg_version()` returned.

MAN-3  `video` is `{"name": <basename>, "path": <video argument as given>, "duration": <float>, "width": <int>,
       "height": <int>, "ratio": <round(width / height, 3)>, "orientation": "portrait" | "landscape"}` from
       `probe`; `orientation` is `"portrait"` when `height > width`, else `"landscape"` (a square is landscape).
       Since step 3 the dict ends with `"grade"` (MAN-12).

MAN-4  `analysis` is `{"sample_fps": 2, "thumbnails": <len(thumbnails())>, "max_frames": <--max-frames>,
       "threshold": {"requested": <--threshold>, "effective": <returned by fit_to_cap>},
       "max_gap": {"requested": <--max-gap>, "effective": <returned by fit_to_cap>}, "all_timer": <bool>}`.

MAN-5  removed, superseded by MAN-12 (values from `layout()`).

MAN-6  removed, superseded by MAN-11 (`block` counts as a content reason too).

MAN-7  `frames` has one entry per kept time, in order:
       `{"n": <1-based>, "time": <float>, "file": <basename of the path save_frames returned>,
       "sheet": <1-based sheet number or null>, "reason": <REC reason>, "diff": <REC diff>, "recheck": <str>}`.
       `sheet` is `(n - 1) // (cols * rows) + 1`, and `null` for every frame when there is exactly one frame.
       `recheck` is `shlex.join([ffmpeg(), '-ss', '%.3f' % time, '-i', <video argument as given>, '-frames:v',
       '1', '-q:v', '2', <out_dir>/frame-NN-native.jpg])`, a command the reader runs to get the native frame;
       with `FFMPEG` unset it starts with the literal `ffmpeg`.
       Why. A number read off a 260 px tile once came out as 118 instead of 218.

MAN-8  `sheets` has one entry per path `contact_sheets` returned, in order:
       `{"file": <basename>, "frames": [<first n on it>, <last n on it>]}`; `[]` when no sheet was built. The
       count of returned paths is trusted; a fake must return exactly `layout`'s `sheets` paths (LAY-4). More
       paths than sheets is undefined, do not test.

MAN-9  Nothing else is written by `main()`: `out_dir` gains only what the (real) `save_frames` and
       `contact_sheets` write plus `frames.json`. With fakes, `out_dir` (created by CLI-13 when missing)
       contains exactly `frames.json`.

### ffmpeg stages, amended

FF-5  [hands-on] `ffmpeg_version()` returns the first line of `ffmpeg -version`, for example
      `ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers`. `probe` calls
      `parse_probe` on the real ffprobe output. Evidence: the byte regression at 0 mismatches, and a run
      on a real recording whose `frames.json` opens and whose `recheck` command produces a frame.

### Examples (draft)

`ramp` is `[flat(v) for v in (0, 5, 10, 15, 20, 25, 30, 35, 40, 45)]`. For `main()` rows: `probe` returns
`(15.0, 800, 600)`, video is an empty file `clip.mp4` in `tmp_path` (cwd), `out_dir` argv is `'out'`,
`save_frames` fake returns `['out/frame-01.jpg', ...]`, `contact_sheets` fake returns `['out/sheet-01.jpg']`
unless the row says otherwise.

| ID | Input | Result |
|---|---|---|
| REC-1, REC-2, REC-4, REC-5 | `select_frames(static(20), T, G)` | `[{'time': 0.0, 'diff': 0.0, 'reason': 'first'}, {'time': 3.0, 'diff': 0.0, 'reason': 'timer'}, {'time': 6.0, 'diff': 0.0, 'reason': 'timer'}, {'time': 9.0, 'diff': 0.0, 'reason': 'timer'}, {'time': 9.5, 'diff': 0.0, 'reason': 'last'}]` |
| REC-3 | `select_frames(ramp, T, 100.0)` | `[{'time': 0.0, 'diff': 0.0, 'reason': 'first'}, {'time': 1.5, 'diff': 15.0, 'reason': 'diff'}, {'time': 3.0, 'diff': 15.0, 'reason': 'diff'}, {'time': 4.5, 'diff': 15.0, 'reason': 'diff'}]` (4.5 is the last thumbnail but was kept by the loop, so `'diff'`) |
| REC-5 | `select_frames(alt(4), 300.0, 100.0)` | `[{'time': 0.0, 'diff': 0.0, 'reason': 'first'}, {'time': 1.5, 'diff': 255.0, 'reason': 'last'}]` |
| REC-3, REC-5 | `select_frames([flat(0), flat(12), flat(13), flat(13)], T, 100.0)` | `[{'time': 0.0, 'diff': 0.0, 'reason': 'first'}, {'time': 1.0, 'diff': 13.0, 'reason': 'diff'}, {'time': 1.5, 'diff': 0.0, 'reason': 'last'}]` |
| REC-3 | `select_frames(static(6) + [flat(255)], T, G)` | `[{'time': 0.0, 'diff': 0.0, 'reason': 'first'}, {'time': 3.0, 'diff': 255.0, 'reason': 'diff'}]` (at 3.0 both conditions hold, diff wins) |
| REC-4 | `select_frames(static(7), T, G)` | `[{'time': 0.0, 'diff': 0.0, 'reason': 'first'}, {'time': 3.0, 'diff': 0.0, 'reason': 'timer'}]` |
| REC-5 | `select_frames(static(1), T, G)` | `[{'time': 0.0, 'diff': 0.0, 'reason': 'first'}]` |
| REC-1 | `select_frames([], T, G)` | `[]` |
| PRB-1 | `parse_probe("814,872\\n37.700000\\n")` | `(37.7, 814, 872)` |
| PRB-2 | `parse_probe("37.700000\\n\\n814,872")` | `(37.7, 814, 872)` |
| PRB-3 | `parse_probe("")`, `parse_probe("814,872\\n")`, `parse_probe("37.7\\n")`, `parse_probe("0,0\\n37.7\\n")`, `parse_probe("814,872\\nN/A\\n")` | each raises `ValueError`, message contains `ffprobe` |
| TOOL-1 | `FFMPEG` and `FFPROBE` both set to an executable file in `tmp_path` | `None` |
| TOOL-2 | `FFMPEG` set to `tmp_path / 'nope'` | `'ffmpeg not found. Install ffmpeg or set FFMPEG=/path/to/ffmpeg'` |
| TOOL-3 | `FFMPEG` executable, `FFPROBE` set to `tmp_path / 'nope'` | `'ffprobe not found. Install ffmpeg or set FFPROBE=/path/to/ffprobe'` |
| DIR-1 | `check_out_dir(tmp_path / 'missing', False)` | `None` |
| DIR-1 | empty directory, `force` false | `None` |
| DIR-1 | directory with `other.jpg` and `notes.txt` | `None` |
| DIR-1 | directory with `frame-01.jpg` and `frames.json` | `None` |
| DIR-1 | directory with `frame-01.jpg`, no `frames.json`, `force` true | `None` |
| DIR-2 | directory `d` with `frame-01.jpg`, no `frames.json`, `force` false | `'<d> already holds frame-*.jpg from something else; pass --force to overwrite'` with `<d>` the string passed |
| JSN-1 | `write_json(p, {'a': [1, 2.5, 'ünïcode'], 'b': None})` | file text is `json.dumps(data, indent=2, ensure_ascii=False) + '\\n'`; contains `ünïcode` literally |
| JSN-2 | `write_json` twice to the same path | second content wins |
| JSN-3 | `write_json(tmp_path / 'x' / 'frames.json', {})` with `x` an existing directory holding `keep.txt` | `x` contains exactly `frames.json` and `keep.txt` |
| CLN-4 | the CLN-1 directory row above | remaining: `Frame-01.jpg`, `frame-01.png`, `notes`, `other.jpg` |
| CLI-10 | argv `['clip.mp4', 'out', '--threshold', '0']` | `SystemExit` code 2, stderr contains `--threshold must be above 0` |
| CLI-10 | argv `['clip.mp4', 'out', '--max-gap', '-1']` | `SystemExit` code 2, stderr contains `--max-gap must be above 0` |
| CLI-10 | argv `['--help']` | `SystemExit` code 0, stdout contains `default: 12.0`, `default: 3.0`, `default: 24`, `seconds`, `--force` |
| CLI-11 | `require_tools` fake returns `'ffmpeg not found. Install ffmpeg or set FFMPEG=/path/to/ffmpeg'` | return 1, stderr contains that string, `probe` not called |
| CLI-11 | argv `['missing.mp4', 'out']`, no such file | return 1, stderr contains `no such file: missing.mp4`, `probe` not called |
| CLI-11 | `out` exists with `frame-01.jpg` and no `frames.json`, argv `['clip.mp4', 'out']` | return 1, stderr contains `already holds frame-*.jpg`, `probe` not called; with `--force` the run returns 0 and, `clean` being real, `out` ends up with exactly `frames.json` (CLI-13, MAN-9) |
| CLI-12 | `probe` fake raises `ValueError('could not read duration, width and height from ffprobe output')` | return 1, stderr contains `clip.mp4: could not read duration, width and height from ffprobe output` |
| CLI-12 | `thumbnails` fake raises `subprocess.CalledProcessError(1, ['ffmpeg'], stderr='x\\nboom\\n')` | return 1, stderr contains `ffmpeg failed during thumbnails (exit 1): boom` |
| CLI-12 | `save_frames` fake raises `subprocess.CalledProcessError(69, ['ffmpeg'], stderr='bad frame')` | return 1, stderr contains `ffmpeg failed during frames (exit 69): bad frame` |
| CLI-13 | `out` holds `frames.json` (any content) and `frame-01.jpg`; `thumbnails` fake raises `CalledProcessError(1, ['ffmpeg'], stderr='boom')` | return 1, `out/frames.json` does not exist |
| CLI-14, MAN-1..9 | argv `['clip.mp4', 'out']`, thumbnails `static(30)` | return 0; stdout exactly: `clip.mp4: 15.0 s, 800x600, landscape` / `  30 thumbnails, selected 6/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)` / `  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last` / `  contact sheets: out/sheet-01.jpg` / `  all frames taken by the timer: the threshold contributed nothing (effective 12.0); try --threshold or --max-frames` / `  manifest: out/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.` and `out/frames.json` equals `{"tool": "seenby", "version": 1, "ffmpeg": "ffmpeg version 6.1.1-test", "video": {"name": "clip.mp4", "path": "clip.mp4", "duration": 15.0, "width": 800, "height": 600, "ratio": 1.333, "orientation": "landscape"}, "analysis": {"sample_fps": 2, "thumbnails": 30, "max_frames": 24, "threshold": {"requested": 12.0, "effective": 12.0}, "max_gap": {"requested": 3.0, "effective": 3.0}, "all_timer": true}, "sheet": {"cols": 2, "rows": 3, "tile_width": 780, "count": 1}, "frames": [{"n": 1, "time": 0.0, "file": "frame-01.jpg", "sheet": 1, "reason": "first", "diff": 0.0, "recheck": "ffmpeg -ss 0.000 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-01-native.jpg"}, ... {"n": 6, "time": 14.5, "file": "frame-06.jpg", "sheet": 1, "reason": "last", "diff": 0.0, "recheck": "ffmpeg -ss 14.500 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-06-native.jpg"}], "sheets": [{"file": "sheet-01.jpg", "frames": [1, 6]}]}` (entries 2..5 are times 3.0, 6.0, 9.0, 12.0 with reason `timer`, diff 0.0, sheet 1); `out` contains exactly `frames.json` |
| CLI-14, MAN-6 | argv `['clip.mp4', 'out', '--threshold', '300', '--max-gap', '7']`, thumbnails `alt(30)` | stdout has five lines (no "all frames" line): line 2 `  30 thumbnails, selected 4/24 (threshold 300.0 -> 300.0, max gap 7.0 -> 7.0 s)`, line 3 `  frames: 0.0 first, 7.0 timer, 14.0 timer, 14.5 last`; manifest `analysis.all_timer` false, `analysis.threshold` `{"requested": 300.0, "effective": 300.0}`, `analysis.max_gap` `{"requested": 7.0, "effective": 7.0}` |
| MAN-4, MAN-6 | argv `['clip.mp4', 'out', '--max-frames', '5']`, thumbnails `alt(20)` | `analysis.threshold` `{"requested": 12.0, "effective": 307.546875}`, `analysis.max_gap` `{"requested": 3.0, "effective": 3.0}`, `analysis.max_frames` 5, frames times `[0.0, 3.0, 6.0, 9.0, 9.5]`, reasons `first, timer, timer, timer, last`, `all_timer` true, line 2 `  20 thumbnails, selected 5/5 (threshold 12.0 -> 307.5, max gap 3.0 -> 3.0 s)` |
| MAN-6, MAN-7 | argv `['clip.mp4', 'out']`, thumbnails `ramp` | frames reasons `first, diff, diff, diff`, diffs `0.0, 15.0, 15.0, 15.0`, `all_timer` false |
| MAN-7, MAN-8 | argv `['clip.mp4', 'out']`, thumbnails `static(33)`, `contact_sheets` fake returns `['out/sheet-01.jpg', 'out/sheet-02.jpg']` | 7 frames (times 0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 16.0); `sheet` values `1, 1, 1, 1, 1, 1, 2`; `sheets` `[{"file": "sheet-01.jpg", "frames": [1, 6]}, {"file": "sheet-02.jpg", "frames": [7, 7]}]`; `sheet.count` 2 |
| MAN-5, MAN-7, MAN-8 | argv `['clip.mp4', 'out']`, thumbnails `static(1)`, `save_frames` fake returns `['out/frame-01.jpg']` | one frame with `sheet` `null`, `sheets` `[]`, `sheet.count` 0, `sheet.cols` 2, `sheet.rows` 3, `sheet.tile_width` 780 |
| MAN-3, MAN-5 | argv `['clip.mp4', 'out']`, probe `(15.0, 600, 800)`, thumbnails `static(30)` | `video.orientation` `"portrait"`, `video.ratio` 0.75, `sheet` `{"cols": 6, "rows": 4, "tile_width": 260, "count": 1}` |
| MAN-7 | argv `['my clip.mp4', 'out dir']` (file `my clip.mp4` exists), thumbnails `static(4)` | `frames[0].recheck` is `"ffmpeg -ss 0.000 -i 'my clip.mp4' -frames:v 1 -q:v 2 'out dir/frame-01-native.jpg'"` |

### Properties (draft)

REC-P1  For any `thumbs`, `threshold`, `max_gap` from the anchored generators: `select_frames` times equal
        `select`; every `reason` is one of `first`, `diff`, `block`, `timer`, `last` (`block` since REC-6: one
        pixel of 255 has mean 0.249 and block 3.98, so small thresholds trigger it); the first entry is `first`
        and no other is; at most the last entry is `last`; every `diff` is a float in `[0.0, 255.0]`.

### Errors (draft)

- `parse_probe`: `ValueError` (PRB-3). Nothing else.
- `require_tools`, `check_out_dir`: return strings, never raise on inputs above.
- `write_json`: whatever `open` or `os.replace` raise on an unwritable path; do not test.
- `main`: 0, 1 or `SystemExit(2)` (CLI-15). No traceback on any failure covered by CLI-11, CLI-12.

## Block metric (drafted and implemented 2026-09-16)

Anchored since 2026-09-16. Written as a draft before the code existed; the tester wrote red tests from it.

Why. The mean difference over a 32x32 thumbnail is blind to a change in one corner of the screen: a calendar
highlight moving one row gives a mean of 8.6 (below 12) while the two blocks it touches differ by 59 and 77.
On the reference recording every frame was taken by the timer. The block metric keeps a frame when any 8x8
block of the thumbnail changed strongly, even if the mean did not.

### Public surface added or changed

    BLOCK = 8
    BLOCK_K = 5.0
    def block_max(a, b, bs=BLOCK)
    def select_frames(thumbs, threshold, max_gap, block_k=BLOCK_K)
    def select(thumbs, threshold, max_gap, block_k=BLOCK_K)
    def fit_to_cap(thumbs, max_frames, threshold, max_gap, block_k=BLOCK_K)

The anchored SEL, CAP and REC rules and rows stay true with the default `block_k`: none of their inputs has a
block that changes strongly while the mean stays under the threshold.

### block_max(a, b, bs=BLOCK) -> float

`a` and `b` are thumbnails (1024 bytes, row-major, 32 pixels per row). The thumbnail is cut into
`(32 // bs) ** 2` square blocks of `bs x bs` pixels (16 blocks of 64 pixels at the default).

BLK-1  Returns the largest, over the blocks, of the mean absolute byte difference inside the block. A float in
       `[0.0, 255.0]`. Identical thumbnails give `0.0`.

BLK-2  A change confined to one block is reported at its full strength: one 8x8 block differing by 200 while the
       rest is identical gives `200.0`, although the whole-thumbnail mean is `12.5`. One pixel differing by 255
       gives `255 / 64 = 3.984375`. A change split across two blocks is halved: an 8-pixel-wide, 8-pixel-tall
       patch of 100 straddling the boundary between two blocks gives `50.0`.
       Why. The grid is fixed; a change smaller than a block or on a boundary is under-reported, up to 4x at a
       corner. Documented limitation, not a bug.

### select_frames, select, fit_to_cap with block_k

REC-6  A thumbnail whose difference against the last kept one is not above `threshold` is still kept, with
       reason `'block'`, when `block_k > 0` and `block_max(thumb, last) > block_k * threshold` (strictly).
       Precedence of reasons: `'diff'`, then `'block'`, then `'timer'`; `'first'` and `'last'` as before.

REC-7  Every entry of `select_frames` has exactly the keys `time`, `diff`, `block`, `reason`, in kept order.
       `block` is `block_max` against the previous kept thumbnail (`0.0` for the first entry, and computed for
       the appended `'last'` entry as well). `[d['time'] for d in select_frames(...)] == select(...)` with the
       same arguments, for every input. `block` is reported whatever `block_k` is, including 0.

REC-8  `block_k = 0` disables the rule: `select_frames(thumbs, threshold, max_gap, 0)` keeps exactly the
       thumbnails REC-2..5 keep, for every input.
       Why. The rollback path: `--block-k 0` must reproduce the previous behaviour byte for byte.

CAP-7  `fit_to_cap` passes `block_k` to `select` in its threshold loop (CAP-4). The gap-stretching loop (CAP-3)
       keeps using forced frames only (`block_k` 0 there), so the call returns for any `block_k >= 0`.
       `times == select(thumbs, returned_threshold, returned_max_gap, block_k)`.
       Why. With the block rule inside the gap loop, a small `block_k` never lets the forced-only count drop and
       the loop runs forever.

### main(), amended

CLI-16 Option `--block-k` (float, default 5.0, 0 or above; 0 disables the block rule). Below 0 is an argparse
       error, `SystemExit` code 2, stderr contains `--block-k must be 0 or above`. `--help` stdout contains
       `default: 5.0` and `0 disables`. The value is passed to `fit_to_cap` and `select_frames`. The CLI-14
       "frames" line prints `block` as a reason like any other.

### frames.json, amended

MAN-10 `analysis` gains `"block_k": <--block-k as float>` (after `max_gap`, before `all_timer`). Every entry of
       `frames` gains `"block": <REC-7 block>` after `diff`, so the keys are exactly `n`, `time`, `file`,
       `sheet`, `reason`, `diff`, `block`, `recheck`. Key order in the file is part of the rule: a reader sees
       the file, not a dict.

MAN-11 `all_timer` is true exactly when no entry of `frames` has reason `"diff"` or `"block"` and
       `len(frames) >= 5`.

### Examples (step 4)

`patch(v)` is a thumbnail whose top-left 8x8 block (rows 0..7, columns 0..7) is `v` and the rest is 0.
`straddle(v)` is a thumbnail whose rows 0..7, columns 4..11 are `v` and the rest is 0. `pixel(v)` is a
thumbnail with byte 0 set to `v` and the rest 0. `T`, `G`, `flat`, `static`, `alt` as before. Entries below
are written as `(time, diff, block, reason)`.

| ID | Input | Result |
|---|---|---|
| BLK-1 | `block_max(flat(0), flat(0))` | `0.0` |
| BLK-1 | `block_max(flat(0), flat(255))` | `255.0` |
| BLK-2 | `block_max(flat(0), patch(200))` | `200.0` (mean difference of the whole thumbnail is 12.5) |
| BLK-2 | `block_max(flat(0), pixel(255))` | `3.984375` |
| BLK-2 | `block_max(flat(0), straddle(100))` | `50.0` |
| BLK-1 | `block_max(flat(0), patch(200), 16)` | `50.0` (4 blocks of 16x16; 64 of 256 pixels differ) |
| REC-6, REC-7 | `select_frames([flat(0), patch(100)], T, 100.0)` | `[(0.0, 0.0, 0.0, 'first'), (0.5, 6.25, 100.0, 'block')]` (mean 6.25 is under 12, block 100 is above 60) |
| REC-6 | `select_frames([flat(0), patch(60), flat(0)], T, 100.0)` | `[(0.0, 0.0, 0.0, 'first'), (1.0, 0.0, 0.0, 'last')]` (60 is not above 60) |
| REC-6, REC-7 | `select_frames([flat(0), patch(100), patch(100)], T, 100.0)` | `[(0.0, 0.0, 0.0, 'first'), (0.5, 6.25, 100.0, 'block'), (1.0, 0.0, 0.0, 'last')]` |
| REC-6 | `select_frames([flat(0), straddle(100)], T, 100.0)` | `[(0.0, 0.0, 0.0, 'first'), (0.5, 6.25, 50.0, 'last')]` (50 is not above 60: the boundary limitation) |
| REC-6 | `select_frames(alt(4), T, 100.0)` | `[(0.0, 0.0, 0.0, 'first'), (0.5, 255.0, 255.0, 'diff'), (1.0, 255.0, 255.0, 'diff'), (1.5, 255.0, 255.0, 'diff')]` (diff wins over block) |
| REC-6 | `select_frames([flat(0)] * 6 + [patch(100)], T, G)` | `[(0.0, 0.0, 0.0, 'first'), (3.0, 6.25, 100.0, 'block')]` (block wins over timer) |
| REC-8 | `select_frames([flat(0), patch(100), patch(100)], T, 100.0, 0)` | `[(0.0, 0.0, 0.0, 'first'), (1.0, 6.25, 100.0, 'last')]` |
| REC-8 | `select([flat(0), patch(100), patch(100)], T, 100.0, 0)` | `[0.0, 1.0]`; with the default `block_k` `[0.0, 0.5, 1.0]` |
| REC-7 | `select_frames(static(20), T, G)` | the REC-1 static row with `block` `0.0` in every entry |
| CAP-7 | `fit_to_cap([flat(0), patch(100)] * 10, 5, T, G)` | `([0.0, 3.0, 6.0, 9.0, 9.5], 27.0, 3.0)` (at 12.0 and 18.0 every thumbnail is a block frame, 20 > 5; at 27.0 the block bar is 135, above 100, and only the timer frames remain) |
| CAP-7 | `fit_to_cap([flat(0), patch(100)] * 10, 5, T, G, 0)` | `([0.0, 3.0, 6.0, 9.0, 9.5], 12.0, 3.0)` |
| CAP-7 | `fit_to_cap([flat(0), patch(100)] * 10, 24, T, G)` | `([i / 2 for i in range(20)], 12.0, 3.0)` |
| CAP-7 | `fit_to_cap([flat(0), patch(100)] * 10, 2, T, G, 0.5)` | `([0.0, 9.5], 205.03125, 9.1552734375)` (the gap is stretched on timer frames only; then the threshold grows 12 -> 18 -> 27 -> 40.5 -> 60.75 -> 91.125 -> 136.6875 -> 205.03125, where the block bar `0.5 * 205.03125 = 102.5` finally exceeds 100 and only the two forced frames remain) |
| CLI-16 | argv `['clip.mp4', 'out', '--block-k', '-1']` | `SystemExit` code 2, stderr contains `--block-k must be 0 or above` |
| CLI-16 | argv `['--help']` | stdout contains `default: 5.0` and `0 disables` |
| CLI-16, MAN-10, MAN-11 | argv `['clip.mp4', 'out']`, thumbnails `[flat(0), patch(100)] * 10` | 20 frames; line 3 `  frames: 0.0 first, 0.5 block, 1.0 block, ..., 9.5 block`; manifest `analysis.block_k` 5.0, `frames[1].block` 100.0, `frames[1].diff` 6.25, `frames[1].reason` `"block"`, `all_timer` false, no "all frames" line |
| CLI-16, MAN-10, MAN-11 | argv `['clip.mp4', 'out', '--block-k', '0']`, thumbnails `[flat(0), patch(100)] * 10` | 5 frames, line 3 `  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 9.5 last`; `analysis.block_k` 0.0; `frames[4]` (time 9.5) has `diff` 6.25 and `block` 100.0, still reported with the rule off; `frames[1]` (time 3.0) has `block` 0.0; `all_timer` true and the "all frames" line is printed |
| MAN-10 | the CLI-14 static(30) row | `analysis` is `{"sample_fps": 2, "thumbnails": 30, "max_frames": 24, "threshold": {...}, "max_gap": {...}, "block_k": 5.0, "all_timer": true}` and every frame entry has `"block": 0.0` between `diff` and `recheck` |

### Properties (step 4)

REC-P2  For any `thumbs`, `threshold`, `max_gap` from the anchored generators and `block_k` a float in
        `[0.0, 10.0]`: `select_frames` times equal `select` with the same arguments; every entry has exactly the
        four keys; `0.0 <= block <= 255.0`; and `block >= diff` for every entry (the largest block mean is never
        below the whole-thumbnail mean).

CAP-P3  For any `thumbs`, `max_frames`, `threshold`, `max_gap` from the anchored generators and `block_k` in
        `[0.0, 10.0]`: `fit_to_cap` returns; `len(times) <= max_frames`;
        `times == select(thumbs, returned_threshold, returned_max_gap, block_k)`.

### Errors (step 4)

- `block_max`: undefined for inputs that are not 1024 bytes or `bs` that does not divide 32; do not test.
- `block_k < 0` in `select_frames` or `fit_to_cap` is undefined (main rejects it, CLI-16); do not test.

## Layout (drafted and implemented 2026-09-16)

Anchored since 2026-09-16. Written as a draft before the code existed; the tester wrote red tests from it.

Why. Vision models downscale an image to about 1568 px on its long side. Today's sheets are 1592 and 1576 px
wide, so every tile loses a little, and one 24-frame portrait sheet would be 1592x2336, read at 175 px per
tile. The layout now derives the tile from the sheet width and a grade of the aspect ratio, and never lets a
sheet exceed the width on either side. This is the one step that changes bytes on purpose: tile sizes, JPEG
quality and frame names change; the selected times do not (the maintainer's frame-time regression stays at 0).

### Public surface added or changed

    SHEET_WIDTH = 1568
    MARGIN = 6
    PADDING = 4
    def layout(width, height, n_frames, sheet_width=SHEET_WIDTH, rows=None, tile_width=None)
    def thumbnails(path, sample_fps=SAMPLE_FPS)                                          [hands-on]
    def select_frames(thumbs, threshold, max_gap, block_k=BLOCK_K, sample_fps=SAMPLE_FPS)
    def select(thumbs, threshold, max_gap, block_k=BLOCK_K, sample_fps=SAMPLE_FPS)
    def fit_to_cap(thumbs, max_frames, threshold, max_gap, block_k=BLOCK_K, sample_fps=SAMPLE_FPS)

`save_frames` and `contact_sheets` keep their signatures. `MARGIN` and `PADDING` are the `tile` filter's
margin and padding in pixels: a sheet of `c` columns and `r` rows is `c * tile + 2 * MARGIN + (c - 1) * PADDING`
wide and `r * tile_h + 2 * MARGIN + (r - 1) * PADDING` tall.

### layout(width, height, n_frames, sheet_width=SHEET_WIDTH, rows=None, tile_width=None) -> (grade, tile, cols, rows, sheets)

`width` and `height` are the video's, positive ints; `n_frames >= 1`; `sheet_width >= 64`; `rows`, when given,
is an int `>= 1`; `tile_width`, when given, is an int `>= 16`. All five results are ints except `grade`, a str.

LAY-1  The grade comes from `ratio = width / height`: `ratio < 0.75` is `'phone'` with 6 nominal columns,
       `0.75 <= ratio <= 1.6` is `'window'` with 3, `ratio > 1.6` is `'wide'` with 2. Both boundaries belong
       to `'window'`.
       Why. Phone screens tolerate narrow tiles, a desktop window needs about 516 px for UI text, a wide
       desktop needs two columns of 776 px. Boundaries were set on ten recordings.

LAY-2  Without `tile_width`: `tile = (sheet_width - 2 * MARGIN - (nominal_cols - 1) * PADDING) // nominal_cols`,
       computed with the grade's nominal columns before any reduction by `n_frames`, then `tile = min(tile,
       width)`. At the default width that is 256, 516 and 776 for the three grades. With `tile_width`:
       `tile = min(tile_width, width)` and the nominal columns become
       `max(1, (sheet_width - 2 * MARGIN + PADDING) // (tile + PADDING))`.
       Why. The tile is never wider than the source (upscaling adds nothing), and a requested tile decides how
       many columns fit rather than the other way round.

LAY-3  `tile_h = round(tile * height / width)` (Python `round`, half to even). Without `rows`:
       `rows = max(1, (sheet_width - 2 * MARGIN + PADDING) // (tile_h + PADDING))`, the most rows whose sheet
       height stays within `sheet_width`; at least one row even when a single row is already taller. With
       `rows` given it is used as is.
       Why. Both sides of the sheet must stay under the downscale size; a 100x2000 video cannot, so one row.

LAY-4  `cols = min(nominal_cols, n_frames)`, and `sheets = ceil(n_frames / (cols * rows))`. `sheets` is 1 for
       `n_frames` 1 although `main()` builds no sheet then (CLI-7).
       Why. The `tile` filter pads missing cells with black at the full width: 3 frames at 6 columns would give
       a 1568 px sheet with three black cells instead of 788 px.

LAY-5  Invariant. For any inputs in range: `1 <= cols <= n_frames`, `rows >= 1`, `sheets >= 1`, `tile <= width`.
       When `tile_width` is `None`: `cols * tile + 2 * MARGIN + (cols - 1) * PADDING <= sheet_width`. When
       `rows` is `None`: either `rows == 1` or `rows * tile_h + 2 * MARGIN + (rows - 1) * PADDING <= sheet_width`.
       An explicit `rows` or `tile_width` is the user's choice and may exceed the sheet; `layout` does not clamp
       it.

LAY-6  [hands-on] Each sheet built for a batch of `count` frames uses `min(cols, count)` columns and
       `ceil(count / min(cols, count))` rows in the `tile` filter, so a tail sheet with fewer frames is narrower
       and shorter, never padded to the full grid. Evidence: `ffprobe` on every sheet of the ten recordings
       gives both sides `<= 1568`, in the maintainer's plan notes.

### Sampling rate

REC-9  `thumbnails`, `select_frames`, `select` and `fit_to_cap` take `sample_fps` (float, default
       `SAMPLE_FPS` 2). Thumbnail `i` has time `i / sample_fps`, and the appended last time is
       `(len(thumbs) - 1) / sample_fps`. With `sample_fps` 4 the static(20) input gives
       `[0.0, 3.0, 4.75]`: forced at 3.0 (the first time `t >= 3.0`), then the last thumbnail at 4.75.
       Why. A short event (a tooltip, a flash) needs denser sampling; `--sample-fps 4` doubles the thumbnails.
       Times at a rate that is not a power of two (`i / 3`) are not exact binary fractions; SEL-6 and SEL-P1
       describe the default rate only. Do not test beyond the rows below.

### main(), amended

CLI-17 New options. `--sheet-width` (int, default 1568, at least 64), `--rows` (int, at least 1, default from
       LAY-3), `--tile-width` (int, at least 16, default from LAY-2), `--sample-fps` (float, above 0, default
       2.0), `--dry-run` (flag). Out of range is an argparse error, `SystemExit` code 2, stderr contains
       `--sheet-width must be at least 64`, `--rows must be at least 1`, `--tile-width must be at least 16` or
       `--sample-fps must be above 0`. `--help` stdout contains `default: 1568`, `default: 2.0` and `--dry-run`.
       `--sheet-width`, `--rows`, `--tile-width` go to `layout()` as `sheet_width`, `rows`, `tile_width`;
       `--sample-fps` goes to `thumbnails` and, as `sample_fps`, to `fit_to_cap` and `select_frames`.
       `save_frames` gets `layout`'s `tile` as `tile_width`; `contact_sheets` gets `layout`'s `cols` and `rows`.

CLI-18 removed, superseded by CLI-21 (a range line, and the hint lines mention `--from/--to`).

CLI-19 `--dry-run` runs the CLI-11 checks for tools and video, calls `probe` and `thumbnails`, prints the first
       four lines of CLI-18 and returns 0. It does not create or clean `out_dir`, does not call `save_frames`,
       `contact_sheets` or `ffmpeg_version`, and writes no `frames.json`. The `check_out_dir` refusal still
       applies.
       Why. Choosing flags for a long recording should not cost the extraction.

### frames.json, amended

MAN-12 `video` gains `"grade": <LAY-1 grade>` after `orientation`. `sheet` is
       `{"cols": <layout cols>, "rows": <layout rows>, "tile_width": <layout tile>, "sheet_width":
       <--sheet-width>, "count": <len(sheets)>}`; `count` is 0 when no sheet was built. Frame `sheet` numbers
       (MAN-7) use `layout`'s `cols * rows`.

MAN-13 `analysis.sample_fps` is the `--sample-fps` value as a float (2.0 by default), no longer the constant.

### ffmpeg stages, amended

FF-6  [hands-on] `save_frames` names frames `frame-<NN>-<time %.1f>s.jpg` (`frame-03-5.0s.jpg`) and extracts
      them with `-q:v 2`. `contact_sheets` tiles the paths it is given through an explicit list (ffmpeg concat
      demuxer), not a `%02d` pattern, per LAY-6. The `recheck` native name stays `frame-NN-native.jpg`. Evidence:
      the maintainer's acceptance table of ten recordings, the byte regression rebaselined with the reason, the frame-time regression at 0.

### Examples (step 3)

`layout` rows give `(grade, tile, cols, rows, sheets)`.

| ID | Input | Result |
|---|---|---|
| LAY-1..4 | `layout(814, 872, 12)` | `('window', 516, 3, 2, 2)` |
| LAY-1..4 | `layout(2554, 1334, 10)` | `('wide', 776, 2, 3, 2)` |
| LAY-1..4 | `layout(526, 514, 3)` | `('window', 516, 3, 3, 1)` |
| LAY-1..4 | `layout(720, 1280, 14)` | `('phone', 256, 6, 3, 1)` |
| LAY-4 | `layout(576, 1280, 3)` | `('phone', 256, 3, 2, 1)` (tile from 6 nominal columns, then cols cut to 3) |
| LAY-1..4 | `layout(2560, 1228, 8)` | `('wide', 776, 2, 4, 1)` |
| LAY-1..4 | `layout(1636, 1228, 5)` | `('window', 516, 3, 3, 1)` |
| LAY-1..4 | `layout(576, 1280, 9)` | `('phone', 256, 6, 2, 1)` |
| LAY-1..4 | `layout(576, 1280, 20)` | `('phone', 256, 6, 2, 2)` |
| LAY-3 | `layout(100, 2000, 5)` | `('phone', 100, 5, 1, 1)` (tile capped at the width, one row) |
| LAY-1 | `layout(1600, 1000, 6)` | `('window', 516, 3, 4, 1)` (1.6 is window) |
| LAY-1 | `layout(1601, 1000, 6)` | `('wide', 776, 2, 3, 1)` |
| LAY-1 | `layout(750, 1000, 6)` | `('window', 516, 3, 2, 1)` (0.75 is window) |
| LAY-1 | `layout(749, 1000, 6)` | `('phone', 256, 6, 4, 1)` |
| LAY-2 | `layout(500, 500, 6)` | `('window', 500, 3, 3, 1)` (tile capped at the width) |
| LAY-2, LAY-3 | `layout(800, 600, 6, 1200, 2)` | `('window', 393, 3, 2, 1)` |
| LAY-2 | `layout(800, 600, 6, tile_width=300)` | `('window', 300, 5, 6, 1)` (5 columns of 300 fit in 1568) |
| LAY-4 | `layout(800, 600, 1)` | `('window', 516, 1, 3, 1)` |
| LAY-4 | `layout(800, 600, 2)` | `('window', 516, 2, 3, 1)` |
| LAY-4 | `layout(800, 600, 30)` | `('window', 516, 3, 3, 4)` |
| LAY-4 | `layout(3440, 1440, 24)` | `('wide', 776, 2, 4, 3)` |
| REC-9 | `select(static(20), T, G, sample_fps=4)` | `[0.0, 3.0, 4.75]` |
| REC-9 | `select_frames(static(4), T, G, 5.0, 1.0)` | times `[0.0, 3.0]` (thumbnail 3 is at 3.0 s and forced, also the last) |
| REC-9 | `fit_to_cap(static(240), 24, T, G, 5.0, 4.0)` | 240 thumbnails at 4 fps span 59.75 s: times `[0.0, 3.0, 6.0, ..., 57.0, 59.75]` (21 entries), `12.0`, `3.0` |
| CLI-17 | argv `['clip.mp4', 'out', '--sheet-width', '10']`, `['clip.mp4', 'out', '--rows', '0']`, `['clip.mp4', 'out', '--tile-width', '8']`, `['clip.mp4', 'out', '--sample-fps', '0']` | each `SystemExit` code 2 with its message |
| CLI-17 | argv `['--help']` | stdout contains `default: 1568`, `default: 2.0`, `--dry-run` |
| CLI-17, MAN-12 | argv `['clip.mp4', 'out']`, probe `(15.0, 800, 600)`, thumbnails `static(30)` | `save_frames` gets `tile_width` 516; `contact_sheets` gets `cols` 3, `rows` 3; manifest `video.grade` `"window"`, `sheet` `{"cols": 3, "rows": 3, "tile_width": 516, "sheet_width": 1568, "count": 1}`; every frame `sheet` 1 |
| CLI-17, MAN-12 | argv `['clip.mp4', 'out']`, probe `(15.0, 600, 800)`, thumbnails `static(30)` | `video.orientation` `"portrait"`, `video.grade` `"window"` (ratio 0.75); `save_frames` gets 516; `contact_sheets` gets `cols` 3, `rows` 2 |
| CLI-17, MAN-12 | argv `['clip.mp4', 'out']`, probe `(15.0, 576, 1280)`, thumbnails `static(30)` | `grade` `"phone"`, `save_frames` gets 256, `contact_sheets` gets `cols` 6, `rows` 2 |
| CLI-17, MAN-12 | argv `['clip.mp4', 'out', '--sheet-width', '1200', '--rows', '2']`, probe `(15.0, 800, 600)`, thumbnails `static(30)` | `save_frames` gets 393; `contact_sheets` gets `cols` 3, `rows` 2; `sheet` `{"cols": 3, "rows": 2, "tile_width": 393, "sheet_width": 1200, "count": 1}` |
| CLI-17, MAN-13 | argv `['clip.mp4', 'out', '--sample-fps', '4']`, thumbnails `static(40)` | `thumbnails` called with `('clip.mp4', 4.0)` or `sample_fps=4.0`; frames times `[0.0, 3.0, 6.0, 9.0, 9.75]`; `analysis.sample_fps` 4.0 |
| MAN-13 | argv `['clip.mp4', 'out']` | `analysis.sample_fps` is `2.0` (float) |
| MAN-7, MAN-12 | argv `['clip.mp4', 'out']`, probe `(15.0, 800, 600)`, thumbnails `static(61)` (11 frames, 0.0 to 30.0 every 3 s, the last one forced), `contact_sheets` fake returns two paths | `sheet` numbers `1` for frames 1..9 and `2` for 10..11 (3x3 per sheet); `sheets` `[{"file": "sheet-01.jpg", "frames": [1, 9]}, {"file": "sheet-02.jpg", "frames": [10, 11]}]` |
| CLI-18 | argv `['clip.mp4', 'out']`, probe `(15.0, 800, 600)`, thumbnails `static(30)` | stdout exactly: `clip.mp4: 15.0 s, 800x600, landscape` / `  30 thumbnails, selected 6/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)` / `  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last` / `  layout: window, tile 516 px, 3x3 per sheet` / `  contact sheets: out/sheet-01.jpg` / `  all frames taken by the timer: the threshold contributed nothing (effective 12.0); try --threshold or --max-frames` / `  manifest: out/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.` |
| CLI-18 | argv `['clip.mp4', 'out', '--max-gap', '1', '--rows', '1']`, probe `(15.0, 800, 600)`, thumbnails `static(30)` (16 frames: every second plus 14.5), `contact_sheets` fake returns 6 paths | `contact_sheets` gets `cols` 3, `rows` 1; a line `  6 contact sheets are more than 4; consider --max-frames` right after the "contact sheets" line; stdout has eight lines |
| CLI-19 | argv `['clip.mp4', 'out', '--dry-run']`, thumbnails `static(30)` | return 0; stdout is exactly the first four CLI-18 lines; `save_frames`, `contact_sheets`, `ffmpeg_version` not called; `out` does not exist afterwards |
| CLI-19 | argv `['clip.mp4', 'out', '--dry-run']` with `out` holding a foreign `frame-01.jpg` | return 1, the DIR-2 message (checks still apply) |
| CLI-19 | argv `['clip.mp4', 'out', '--dry-run']` with `out` holding `frames.json` and `frame-01.jpg` | return 0 and both files still there (nothing cleaned) |

### Properties (step 3)

LAY-P1  For `width`, `height` ints in `[16, 4000]`, `n_frames` in `[1, 60]`, `sheet_width` in `[64, 4000]`,
        `rows` in `None` or `[1, 8]`, `tile_width` in `None` or `[16, 2000]`: `layout` returns; LAY-5 holds
        (its two sheet-size clauses only for the `None` cases, as LAY-5 says); `grade` matches LAY-1 for the
        ratio; `tile <= width`; and `sheets == ceil(n_frames / (cols * rows))`.

### Errors (step 3)

- `layout`: undefined outside the ranges above (zero sizes, `n_frames` 0); do not test.
- `main`: the new argparse checks exit 2 (CLI-17). Nothing else new raises.

## Long recordings (drafted and implemented 2026-09-17)

Anchored since 2026-09-17. Written as a draft before the code existed; the tester wrote red tests from it.

Why. On a 20-minute recording the cap of 24 raises the threshold from 12 to 205 and no frame is kept for its
content; the honest `all_timer` line already says so. The remedy is not a bigger cap (the sheet must stay
readable) but a range: `--from/--to` analyse a part of the recording at full sensitivity, and `segments` in the
manifest tell the reader which frames cover which stretch of time, so it can pick the range to zoom into.

### Public surface added or changed

    def thumbnails(path, sample_fps=SAMPLE_FPS, start=0.0, length=None)     [hands-on]
    def segments(times, start, end, length)

### segments(times, start, end, length) -> list of dicts

`times` are the kept times in seconds, ascending, all within `[start, end]`; `end > start`; `length > 0`.

SEG-1  Returns `ceil((end - start) / length)` entries, at least 1, in order, each
       `{"n": <1-based>, "from": <start + (n - 1) * length>, "to": <start + n * length>, "frames": <list of
       1-based indexes into times>}`, except that the last entry's `to` is `end` itself (assigned, not
       `min(...)`: `start + count * length` can round below `end`). A tail shorter than `length` is its own
       entry (604.37 s at 120 s gives 6 entries, the last from 600.0 to 604.37).
       Why. The plan's reviewers found 604 s giving 5 or 6 segments depending on the tail rule; this is the rule.

SEG-2  Index `i` (1-based) of `times` belongs to the entry with `from <= times[i] < to`; a time equal to `end`
       or past it belongs to the last entry, and a time below `start` to the first (tolerant, so a fake
       `thumbnails` that ignores the range does not break `main()`). Every index appears in exactly one entry;
       an entry with no times has `"frames": []`.

SEG-3  Empty `times` gives the same entries with every `frames` empty.

### main(), amended

CLI-20 Options `--from` (float seconds, default 0.0, 0 or above), `--to` (float seconds, above 0, default: the
       end of the video), `--segment` (float seconds, default 120.0, above 0). Argparse errors, `SystemExit`
       code 2, stderr contains `--from must be 0 or above`, `--to must be above 0`, `--segment must be above 0`,
       or, when both are given and `--to <= --from`, `--to must be above --from`. After `probe` (CLI-12 order):
       `--from` at or past the duration -> stderr `--from <value %.1f> is past the end of the video (<duration
       %.1f> s)`, return 1; `--to` past the duration -> `--to <value %.1f> is past the end of the video
       (<duration %.1f> s)`, return 1; `--to` equal to the duration is fine. `thumbnails` is called as
       `thumbnails(video, sample_fps, start, length)` with `start` the `--from` value (0.0 by default) and
       `length` the analysed span `to - from`, where `to` is the duration when `--to` is absent; `length` is
       `None` only when neither flag is given. Every kept time is shifted by `start` after
       `fit_to_cap` (`times[i] + start`), so frame times, names, `recheck` commands and the "frames" line are
       absolute times in the video; `select_frames` and `fit_to_cap` themselves are unchanged.
       Why. `-ss` before `-i` is exact and costs nothing on ffmpeg 6; shifting after selection keeps SEL and
       CAP rules untouched.

CLI-21 removed, superseded by CLI-22 (two honest lines about the cap and the block rule).

### frames.json, amended

MAN-14 removed, superseded by MAN-15 (`block_active`, `timer_share`, `segments[].activity`).

### ffmpeg stages, amended

FF-7  [hands-on] `thumbnails(path, sample_fps, start, length)` passes `-ss start` and, when `length` is not
      `None`, `-t length` before `-i`, so the first thumbnail is at `start` and thumbnail `i` at
      `start + i / sample_fps`. Evidence, on the maintainer's two long stitches (604.37 s and
      1204.37 s) with defaults: full run `<= 15 s` and `<= 25 s`, peak RSS `<= 400 MB`, 4 sheets each with both
      sides `<= 1568`, `segments` of 6 and 11 entries at `--segment 120`, `--from 600 --to 720` on the 20-minute
      stitch in `<= 3 s` with every time in `[600, 720]` and the first at 600.0. Recorded in the maintainer's plan notes.

### Examples (step 5)

For `main()` rows: probe `(15.0, 800, 600)`, thumbnails `static(30)` unless said otherwise; the fake
`thumbnails` records its arguments.

| ID | Input | Result |
|---|---|---|
| SEG-1, SEG-2 | `segments([0.0, 3.0, 119.5, 120.0, 200.0], 0.0, 240.0, 120.0)` | `[{'n': 1, 'from': 0.0, 'to': 120.0, 'frames': [1, 2, 3]}, {'n': 2, 'from': 120.0, 'to': 240.0, 'frames': [4, 5]}]` |
| SEG-1 | `segments([0.0, 600.0, 604.0], 0.0, 604.37, 120.0)` | 6 entries; entry 1 `{'n': 1, 'from': 0.0, 'to': 120.0, 'frames': [1]}`, entries 2..5 with `'frames': []`, entry 6 `{'n': 6, 'from': 600.0, 'to': 604.37, 'frames': [2, 3]}` |
| SEG-1, SEG-2 | `segments([600.0, 650.0, 719.5], 600.0, 720.0, 120.0)` | `[{'n': 1, 'from': 600.0, 'to': 720.0, 'frames': [1, 2, 3]}]` |
| SEG-2 | `segments([0.0, 10.0], 0.0, 10.0, 120.0)` | `[{'n': 1, 'from': 0.0, 'to': 10.0, 'frames': [1, 2]}]` (a time equal to `end` belongs to the last entry) |
| SEG-2 | `segments([0.0, 5.0, 10.0], 0.0, 10.0, 5.0)` | `[{'n': 1, 'from': 0.0, 'to': 5.0, 'frames': [1]}, {'n': 2, 'from': 5.0, 'to': 10.0, 'frames': [2, 3]}]` |
| SEG-3 | `segments([], 0.0, 250.0, 120.0)` | 3 entries, `'to'` values `120.0, 240.0, 250.0`, every `'frames'` `[]` |
| CLI-20 | argv `['clip.mp4', 'out', '--from', '-1']`, `[..., '--to', '0']`, `[..., '--segment', '0']`, `[..., '--from', '10', '--to', '10']`, `[..., '--from', '10', '--to', '5']` | each `SystemExit` code 2 with its message (the last two: `--to must be above --from`) |
| CLI-20 | argv `['clip.mp4', 'out', '--from', '15']` | return 1, stderr contains `--from 15.0 is past the end of the video (15.0 s)`, `thumbnails` not called |
| CLI-20 | argv `['clip.mp4', 'out', '--to', '20']` | return 1, stderr contains `--to 20.0 is past the end of the video (15.0 s)`, `thumbnails` not called |
| CLI-20 | argv `['clip.mp4', 'out', '--to', '15']` | return 0; `thumbnails` called with `('clip.mp4', 2.0, 0.0, 15.0)`; range line `  range: 0.0-15.0 s` |
| CLI-20 | argv `['clip.mp4', 'out']` | `thumbnails` called with `('clip.mp4', 2.0, 0.0, None)`; no range line |
| CLI-20, CLI-21, MAN-14 | argv `['clip.mp4', 'out', '--from', '10', '--to', '25', '--segment', '5']`, probe `(60.0, 800, 600)`, thumbnails `static(30)` | `thumbnails` called with `('clip.mp4', 2.0, 10.0, 15.0)`; line 2 `  range: 10.0-25.0 s`; line 4 `  frames: 10.0 first, 13.0 timer, 16.0 timer, 19.0 timer, 22.0 timer, 24.5 last`; `save_frames` gets times `[10.0, 13.0, 16.0, 19.0, 22.0, 24.5]`; `frames[1].time` 13.0, `frames[1].recheck` contains `-ss 13.000`; `analysis.range` `{"from": 10.0, "to": 25.0}`, `analysis.segment` 5.0; `segments` `[{"n": 1, "from": 10.0, "to": 15.0, "frames": [1, 2]}, {"n": 2, "from": 15.0, "to": 20.0, "frames": [3, 4]}, {"n": 3, "from": 20.0, "to": 25.0, "frames": [5, 6]}]` |
| MAN-14 | argv `['clip.mp4', 'out']` | `analysis` keys exactly `sample_fps, thumbnails, max_frames, threshold, max_gap, block_k, range, segment, all_timer`; `analysis.range` `{"from": 0.0, "to": 15.0}`; `analysis.segment` 120.0; `segments` `[{"n": 1, "from": 0.0, "to": 15.0, "frames": [1, 2, 3, 4, 5, 6]}]`; top-level keys end with `sheets`, `segments` |
| CLI-21 | argv `['clip.mp4', 'out']`, thumbnails `static(30)` | stdout exactly: `clip.mp4: 15.0 s, 800x600, landscape` / `  30 thumbnails, selected 6/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)` / `  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last` / `  layout: window, tile 516 px, 3x3 per sheet` / `  contact sheets: out/sheet-01.jpg` / `  all frames taken by the timer: the threshold contributed nothing (effective 12.0); try --max-frames, --block-k or --from/--to` / `  manifest: out/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.` |
| CLI-21 | the CLI-18 six-sheet row (`--max-gap 1 --rows 1`) | the warning line reads `  6 contact sheets are more than 4; consider --max-frames or --from/--to` |
| CLI-19, CLI-21 | argv `['clip.mp4', 'out', '--dry-run', '--from', '3']` | return 0; stdout exactly `clip.mp4: 15.0 s, 800x600, landscape` / `  range: 3.0-15.0 s` / `  30 thumbnails, selected 6/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)` / `  frames: 3.0 first, 6.0 timer, 9.0 timer, 12.0 timer, 15.0 timer, 17.5 last` / `  layout: window, tile 516 px, 3x3 per sheet` (the fake returns 30 thumbnails whatever the range, so the shifted times run past 15.0; a real run cannot) |

### Properties (step 5)

SEG-P1  For `start` a float in `[0.0, 1000.0]`, `span` in `[0.5, 3000.0]` (`end = start + span`), `length` in
        `[0.5, 500.0]`, and `times` a sorted list of 0..40 floats drawn from `[start, end]`: `segments` returns
        `ceil((end - start) / length)` entries (the function sees `end`, not `span`); entries are contiguous (`entry[k].to == entry[k+1].from`),
        the first starts at `start`, the last ends at `end`; every index 1..len(times) appears in exactly one
        `frames` list, and the lists are ascending.

### Errors (step 5)

- `segments`: undefined when `end <= start` or `length <= 0`; do not test. Times outside `[start, end]` fall
  into the first or last entry (SEG-2).
- `main`: the new argparse checks exit 2; the two past-the-end checks return 1 (CLI-20). Nothing else new raises.

## Step 9: honest cap and budget (drafted and implemented 2026-09-17)

Anchored since 2026-09-17. Written as a draft before the code existed; the tester wrote red tests from it.

Why. A third real run (a 100 s smooth scroll) showed that under the cap the timer frames crowd out content and
the block rule goes dead above threshold 51 without a word, and that raising `--max-frames` only adds timer
frames. Part A makes the output say so with numbers. Part B reserves half the cap for content when the first
fit degenerated, measured on two long concatenations (content frames 3 -> 14 and 0 -> 18 at the default cap)
with the ten short recordings unchanged at caps 24 and 12.

### Public surface added or changed

    def activity(thumbs, start, end, length, sample_fps=SAMPLE_FPS)

`fit_to_cap`, `select_frames`, `select`, `segments` keep their signatures. `block_max` may be skipped for
thumbnails the diff rule already kept or the block rule cannot keep; kept entries still report it (REC-7).

### Part A: activity, timer share, honest lines

SEG-4  `activity(thumbs, start, end, length, sample_fps)` returns one float per `segments` entry (same count and
       order as `segments(times, start, end, length)`): the mean of the differences between consecutive
       thumbnails whose times both fall in the entry (thumbnail `i` at `start + i / sample_fps`; the entry
       covers `from <= t < to`, the last entry also `t == end`), rounded to 2 decimals; `0.0` when the entry
       holds fewer than two thumbnails. The difference is the SEL-3 mean (0..255).
       Why. A reader of a long recording needs to know where the picture moved before deciding where to zoom
       with `--from/--to`; the thumbnails are already computed, this costs one pass.

MAN-15 (replaces MAN-14) `analysis` keys are exactly, in order: `sample_fps`, `thumbnails`, `max_frames`,
       `threshold`, `max_gap`, `block_k`, `block_active`, `range`, `segment`, `all_timer`, `timer_share`, where
       `block_active` is `block_k > 0 and block_k * effective_threshold < 255` (the block rule can still fire)
       and `timer_share` is the number of frames with reason `timer` divided by the number with reason `diff`,
       `block` or `timer`, rounded to 2 decimals, `0.0` when that number is 0 (`first` and `last` never count).
       `segments[k]` gains `"activity": <activity(...)[k]>` after `frames`, so each entry's keys are exactly
       `n`, `from`, `to`, `frames`, `activity`, computed over the analysed thumbnails with `start` the range
       start, `end` the analysed end and `length` `--segment`. `range` and `segment` as MAN-14 said.

CLI-22 removed, superseded by CLI-23 (same lines; the "by the timer" line no longer waits for a timer share
       above 0.7).

CLI-23 (replaces CLI-22) On success stdout is these lines, in this order:

           <basename of video>: <duration %.1f> s, <width>x<height>, <portrait|landscape>
             range: <from %.1f>-<to %.1f> s                                          (only when --from or --to was given)
             <n> thumbnails, selected <k>/<max_frames> (threshold <requested %.1f> -> <effective %.1f>, max gap <requested %.1f> -> <effective %.1f> s)
             frames: <time %.1f> <reason>, ...
             layout: <grade>, tile <tile> px, <cols>x<rows> per sheet
             block rule inactive: bar <block_k * threshold %.1f> (<block_k %.1f> x <threshold %.1f>) is at or above 255   (only when block_k > 0 and not block_active)
             <timer> of <loop> frames by the timer; --max-frames <2c>: <content> content frames at threshold <t %.1f> (<sheets> sheets); --max-frames <3c>: <content> content frames at threshold <t %.1f> (<sheets> sheets)   (see below)
             <timer> of <loop> frames by the timer; no cap up to <3c> adds a content frame   (see below)
             contact sheets: <paths joined by ", ">           (or the single frame path, CLI-7)
             <sheets> contact sheets are more than 4; consider --max-frames or --from/--to
             all frames taken by the timer: the threshold contributed nothing (effective <effective threshold %.1f>); try --max-frames, --block-k or --from/--to
             manifest: <out_dir>/frames.json. Sheets are for meaning; read digits from the native frame, see "recheck" in the manifest.

       The "by the timer" line, one of its two forms, appears only when the cap was active (effective threshold
       above the requested one or effective gap above the requested one) and the selection has at least 5
       frames (`len(times) >= 5`, the MAN-11 convention). The timer share no longer gates it: on the real
       recording that triggered step 9 the share was 0.62 and the numbers were exactly what the reader needed.
       On the ten short test recordings the cap is active on one; the line stays silent on the other nine.
       The second form makes no claim about the recording: "no cap up to <3c> adds a content frame" is all
       the numbers support (a second fit may already hold the content, as the `ramp` cap-8 row shows). At a bar of exactly 255
       (`--threshold 51`) the rule cannot fire (`block > 255` is impossible), so `block_active` is false and the
       block line prints "is at or above 255". `<timer>` is the count of timer frames, `<loop>` the count of frames
       with reason `diff`, `block` or `timer`. `<2c>` and `<3c>` are `2 * max_frames` and `3 * max_frames`; each
       alternative is `fit_to_cap` on the same thumbnails with that cap and the requested threshold and gap,
       `<content>` its count of `diff` and `block` frames, `<t>` its effective threshold, `<sheets>`
       `layout(width, height, <its frame count>, sheet_width, rows, tile_width)[4]`. The second form is used
       when neither alternative has more content frames than the selection. Both lines also print under
       `--dry-run`, after the layout line; nothing else about `--dry-run` changes (CLI-19). The block line
       prints under `--dry-run` too. The other lines as in CLI-21.
       Why. The reader must learn from the console, not from a source file, that the cap or the block rule was
       binding, and what a rerun would buy; the alternatives are computed on thumbnails already in memory and
       only when the line fires.

### Part B: a second fit when the first degenerated

CAP-8  When the CAP-4 threshold of the first fit is at or above `255 / BLOCK_K` (51.0, where the block rule at
       the default factor cannot fire), a second fit is run: the gap ladder starts at `max_gap` and each rung
       is the previous times 1.25, extended until `select(thumbs, 256.0, rung, 0, sample_fps)` has at most
       `max(2, max_frames // 2)` entries; at the top rung the threshold is raised as in CAP-4 (starting again
       from the requested threshold); then, while the ladder has more than one rung and the selection at the
       rung below the top, with that threshold, has at most `max_frames` entries, the top rung is dropped. The
       second fit's result is `select` at the final rung and threshold. The gate compares with the constant
       `BLOCK_K`, not `block_k`, so `--block-k 0` gates the same way.
       Why. Timer frames that fill the cap leave no room for content; reserving half the cap for content and
       giving unused slots back to the timer keeps 14-18 content frames on ten-minute recordings where the
       first fit keeps 0-3. Half was measured against 1/3 and 2/3.

CAP-9  The second fit replaces the first only when it keeps strictly more frames with reason `diff` or `block`.
       Otherwise the first fit's `times`, `threshold` and `max_gap` are returned. CAP-1..7 and their rows stay
       true: on their inputs the gate is closed or the second fit is discarded.
       Why. The walk-down can be blocked by a jump in the count and return fewer frames with no more content.

Termination. First fit as today. Second fit: the forced-only count tends to 2 as the rung outgrows the
recording and the budget is at least 2, so the ladder is finite; the threshold loop ends as in CAP-4; the
walk-down pops at most `len(ladder) - 1` times. CAP-P1, CAP-P2, CAP-P3 hold for both fits. Monotonicity in
`max_frames` is not promised.

### Examples (step 9)

`ramp` here is the long ramp `static(100) + [flat(10 * i) for i in range(1, 26)]` (125 thumbnails, 62.0 s), not the
REC-3 ramp of 10 (called `ramp10` in the MAN-15 row); `two` is
`static(60) + [flat(10 * i) for i in range(1, 26)] + static(60) + [flat(10 * i) for i in range(1, 26)]` (84.5 s);
`saw` is `static(120) + [flat(30 * (i % 8)) for i in range(48)]` (83.5 s); `mixed` is
`[flat(0), patch(100), patch(100), flat(0)]`. For `main()` rows the fakes are as before; `probe` returns
`(15.0, 800, 600)` unless said otherwise.

| ID | Input | Result |
|---|---|---|
| SEG-4 | `activity(static(20), 0.0, 9.5, 120.0)` | `[0.0]` |
| SEG-4 | `activity(alt(4), 0.0, 1.5, 120.0)` | `[255.0]` |
| SEG-4 | `activity(mixed, 0.0, 1.5, 120.0)` | `[4.17]` (differences 6.25, 0.0, 6.25) |
| SEG-4 | `activity(static(20), 0.0, 9.5, 5.0)` | `[0.0, 0.0]` |
| SEG-4 | `activity(ramp, 0.0, 62.0, 30.0)` | `[0.0, 3.39, 10.0]` |
| SEG-4 | `activity(static(3), 10.0, 11.0, 0.4)` | `[0.0, 0.0, 0.0]` (entries with fewer than two thumbnails) |
| MAN-15 | argv `['clip.mp4', 'out']`, thumbnails `static(30)` | `analysis` keys exactly the MAN-15 list; `block_active` true; `timer_share` 1.0; `segments` `[{"n": 1, "from": 0.0, "to": 15.0, "frames": [1, 2, 3, 4, 5, 6], "activity": 0.0}]` |
| MAN-15 | argv `['clip.mp4', 'out', '--threshold', '300', '--max-gap', '7']`, thumbnails `alt(30)` | `block_active` false (5 x 300 = 1500); `timer_share` 1.0; `segments[0].activity` 255.0 |
| MAN-15 | argv `['clip.mp4', 'out']`, thumbnails `ramp10` (the REC-3 ramp of 10) | `timer_share` 0.0; `block_active` true |
| MAN-15 | argv `['clip.mp4', 'out', '--from', '10', '--to', '25', '--segment', '5']`, probe `(60.0, 800, 600)`, thumbnails `static(30)` | three segments, each with `"activity": 0.0` after `frames` |
| CLI-23 | argv `['clip.mp4', 'out']`, thumbnails `static(30)` | stdout exactly the CLI-21 static(30) row (cap inactive, no "by the timer" line; block active, no block line) |
| CLI-23 | argv `['clip.mp4', 'out', '--threshold', '300', '--max-gap', '7']`, thumbnails `alt(30)` | after the layout line: `  block rule inactive: bar 1500.0 (5.0 x 300.0) is at or above 255`; no "by the timer" line (cap inactive) |
| CLI-23 | argv `['clip.mp4', 'out']`, probe `(65.0, 800, 600)`, thumbnails `ramp`, fake `contact_sheets` returns 3 paths | selection 23 frames, threshold 12.0 -> 40.5, 17 timer, 4 diff; after the layout line: `  17 of 21 frames by the timer; --max-frames 48: 12 content frames at threshold 12.0 (4 sheets); --max-frames 72: 12 content frames at threshold 12.0 (4 sheets)`; `timer_share` 0.81; no block line (bar 202.5) |
| CLI-23 | argv `['clip.mp4', 'out', '--dry-run']`, probe `(65.0, 800, 600)`, thumbnails `ramp` | return 0; stdout is the first four lines then the same "17 of 21 frames by the timer; ..." line; nothing written |
| CLI-23 | argv `['clip.mp4', 'out']`, probe `(125.0, 800, 600)`, thumbnails `static(240)`, fake `contact_sheets` returns 3 paths (21 frames on 3x3) | 21 frames, gap 3.0 -> 5.859375 (cap active); after the layout line `  19 of 19 frames by the timer; no cap up to 72 adds a content frame`; the "all frames taken by the timer" line also prints (all_timer true) |
| CLI-23 | argv `['clip.mp4', 'out']`, thumbnails `alt(30)` (default cap; every thumbnail differs, 30 > 24, the threshold climbs to 307.546875) | 6 frames `0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last`, `timer_share` 1.0 (4 of 4), `block_active` false; after the layout line: `  block rule inactive: bar 1537.7 (5.0 x 307.5) is at or above 255` then `  4 of 4 frames by the timer; --max-frames 48: 29 content frames at threshold 12.0 (4 sheets); --max-frames 72: 29 content frames at threshold 12.0 (4 sheets)` (at those caps all 30 thumbnails fit, 29 with reason diff, and layout(800, 600, 30) gives 4 sheets) |
| CLI-23 | the same with `--block-k 0` | no block line; the same "4 of 4 frames by the timer" line |
| CLI-23 | argv `['clip.mp4', 'out', '--max-frames', '8']`, probe `(65.0, 800, 600)`, thumbnails `ramp`, fake `contact_sheets` returns 1 path | 8 frames (threshold 12.0 -> 40.5, gap 3.0 -> 17.881393432617188, the second fit), 5 content and 2 timer, share 0.29; the line prints anyway: `  2 of 7 frames by the timer; no cap up to 24 adds a content frame` (caps 16 and 24 give 4 content frames each, not more than 5) |
| CAP-8 gate closed | `fit_to_cap(ramp, 24, T, G)` | `(..., 40.5, 3.0)`, 23 entries, of which 4 have reason diff in `select_frames(ramp, 40.5, 3.0)`; the first fit's threshold 40.5 is under 51 |
| CAP-8, CAP-9 | `fit_to_cap(ramp, 12, T, G)` | `([0.0, 7.5, 15.0, 22.5, 30.0, 37.5, 45.0, 52.0, 54.5, 57.0, 59.5, 62.0], 40.5, 7.32421875)`, 5 diff. First fit `(91.125, 5.859375)` with 1 diff; second fit: budget 6, ladder to 14.30511474609375, thresholds 12 -> 18 -> 27 -> 40.5, walk-down to 7.32421875 |
| CAP-8, CAP-9 | `fit_to_cap(two, 24, T, G)` | `(..., 40.5, 4.6875)`, 23 entries, 9 diff at 32.5, 35.0, 37.5, 40.0, 42.5, 75.0, 77.5, 80.0, 82.5; first fit `(60.75, 3.75)` had 5 diff |
| CAP-8, CAP-9 | `fit_to_cap(saw, 24, T, G)` | `(..., 91.125, 5.859375)`, 23 entries, 11 diff at 62.0, 64.0, ..., 82.0; first fit `(307.546875, 3.75)` had 22 entries and 0 content |
| CAP-9 | `fit_to_cap(static(200) + [flat(40 * (i % 6)) for i in range(60)], 24, T, G)` | `(..., 205.03125, 5.859375)`, 23 entries, 0 content: the second fit (10 entries, 0 content) is discarded |
| CAP-9 | `fit_to_cap(alt(20), 5, T, G)` | the CAP-4 row unchanged, `([0.0, 3.0, 6.0, 9.0, 9.5], 307.546875, 3.0)`: the gate opens (307.5) but the second fit has 0 content, not more |
| unchanged | every CAP-1..7 row, `static(240)` cap 24, all `[flat(0), patch(100)] * 10` rows | today's values |

Properties CAP-P1, CAP-P2, CAP-P3 are unchanged and must still pass with the second fit in place.

### Errors (step 9)

- `activity`: undefined when `end <= start` or `length <= 0`; do not test.
- Nothing else new raises. The alternatives in CLI-23 use `fit_to_cap`, so they terminate when it does.

## Step 10: the all-timer line names --threshold (drafted 2026-09-25, implemented 2026-09-26)

Anchored since 2026-09-26. Written as a draft before the code existed; the tester wrote red tests from it, a review moved `<m>` to the last kept frame.

Why. A real bug-report recording (reported by an agent on 2026-09-25, 23.6 s, 2560x1228, a light web page with a light DevTools pane) kept 9 frames, all by the timer. DevTools opening over a third of the screen changed the 32x32 thumbnail by 3.6 on average, and the largest change of any thumbnail against the last kept frame over the whole recording was 4.4, under the default threshold 12, so the threshold could not fire anywhere. The console line said `try --max-frames, --block-k or --from/--to`. The cap was not binding (9 of 24), so `--max-frames` changed nothing, and the knob that helped, `--threshold`, was not named. With `--threshold 2` every event of the recording was kept. This step changes only the console line. The selection, the manifest and every frame stay byte-identical.

### Public surface added or changed

None. `seenby.txt` does not change.

### main(), amended

CLI-24 (amends CLI-23, the "all frames taken by the timer" line only) When `all_timer` is true and the cap was not active (the CLI-23 condition is false, that is the effective threshold equals the requested one and the effective gap equals the requested one), the line takes one of the two forms below.

           all frames taken by the timer: the largest change between thumbnails was <m %.1f>, under the threshold <threshold %.1f>; --threshold <t %.1f>: <content> content frames at threshold <t2 %.1f> (<sheets> sheets)
           all frames taken by the timer: the largest change between thumbnails was <m %.1f>, under the threshold <threshold %.1f>

       `<m>` is the largest SEL-3 mean difference between an analysed thumbnail and the last frame kept before it in the final selection, over every thumbnail after the first, `0.0` when there is only one. This is the difference the threshold was compared with, so under `all_timer` it is never above the effective threshold. Consecutive thumbnails are not enough: a slow change (typing, a progress bar) moves little from one thumbnail to the next and a lot between kept frames. The first form is used when `m > 1.0`, the second when `m <= 1.0`. `<t>` is `max(1.0, math.floor(m * 10 / 3) / 10)`, computed in exactly this order. The alternative is `fit_to_cap(thumbs, max_frames, t, max_gap, block_k, sample_fps)` with the requested cap, gap, block factor and rate. `<content>` is its count of frames with reason `diff` or `block` in `select_frames` at its returned threshold and gap, `<t2>` its returned threshold, `<sheets>` is `layout(width, height, <its frame count>, sheet_width, rows, tile_width)[4]`. `<threshold>` is the effective threshold, equal to the requested one here.

       When the cap was active the line is exactly as CLI-23 has it. The line keeps its place (after the "contact sheets" line and the "more than 4" line) and, as before, does not print under `--dry-run`.

       Why a third. On the recording above the kept set is the same for every threshold from 1.3 to 2.0. The frame that shows the reported bug differs from the frame before it by 2.02 and drops out at 2.1, so half of the largest change (2.2) loses it and a third (1.4) keeps it with a margin. Why 1.0. On the same recording, between consecutive thumbnails, stretches without change differ by 0.00 to 0.09, cursor-only moves by 0.5 to 0.97, and the smallest real UI change (a sidebar collapsing) by 1.45. Below 1.0 a lower threshold would only keep cursor moves and compression noise. Both constants rest on one recording and belong to the hint, not to the selection.

Rows of earlier steps whose stdout changes, because their thumbnails are static and the cap is inactive, are the CLI-14 `static(30)` row, the CLI-18 `static(30)` row, the CLI-21 `static(30)` row and the CLI-23 row that refers to it. In each, the "all frames" line becomes `  all frames taken by the timer: the largest change between thumbnails was 0.0, under the threshold 12.0`. The CLI-16/MAN-11 row with `--block-k 0` and `[flat(0), patch(100)] * 10` still prints the line, now in the first form (see the examples). The CLI-23 rows with an active cap (`static(240)` at 125 s, `alt(30)`, the MAN-4 `--max-frames 5` row) keep today's line.

### Examples (step 10)

`steps(a, b)` is `[flat(0)] * 10 + [flat(a)] * 10 + [flat(b)] * 10` (30 thumbnails, 14.5 s). For every row the fakes are as before, `probe` returns `(15.0, 800, 600)` unless said otherwise, and the selection is `0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last` unless said otherwise.

| ID | Input | Result |
|---|---|---|
| CLI-24 | argv `['clip.mp4', 'out']`, thumbnails `steps(4, 8)` | line `  all frames taken by the timer: the largest change between thumbnails was 4.0, under the threshold 12.0; --threshold 1.3: 2 content frames at threshold 1.3 (1 sheets)` (at 1.3 the selection is `0.0 first, 3.0 timer, 5.0 diff, 8.0 timer, 10.0 diff, 13.0 timer, 14.5 last`) |
| CLI-24 | argv `['clip.mp4', 'out', '--threshold', '30']`, thumbnails `steps(4, 8)` | line `  all frames taken by the timer: the largest change between thumbnails was 4.0, under the threshold 30.0; --threshold 1.3: 2 content frames at threshold 1.3 (1 sheets)` |
| CLI-24 | argv `['clip.mp4', 'out']`, thumbnails `[flat(0)] * 10 + [flat(2)] * 20` | line `  all frames taken by the timer: the largest change between thumbnails was 2.0, under the threshold 12.0; --threshold 1.0: 1 content frames at threshold 1.0 (1 sheets)` (`math.floor(20 / 3) / 10` is 0.6, raised to 1.0) |
| CLI-24 | argv `['clip.mp4', 'out']`, thumbnails `[flat(i // 2) for i in range(30)]` (a slow creep, consecutive thumbnails differ by at most 1.0) | line `  all frames taken by the timer: the largest change between thumbnails was 3.0, under the threshold 12.0; --threshold 1.0: 7 content frames at threshold 1.0 (1 sheets)` (m is 3.0, the timer frame at 3.0 against the one at 0.0; at 1.0 the selection is `0.0 first, 2.0 diff, 4.0 diff, 6.0 diff, 8.0 diff, 10.0 diff, 12.0 diff, 14.0 diff, 14.5 last`) |
| CLI-24 | argv `['clip.mp4', 'out']`, thumbnails `[flat(0)] * 10 + [flat(1)] * 20` | line `  all frames taken by the timer: the largest change between thumbnails was 1.0, under the threshold 12.0` (m is not above 1.0) |
| CLI-24 | argv `['clip.mp4', 'out']`, thumbnails `static(30)` | line `  all frames taken by the timer: the largest change between thumbnails was 0.0, under the threshold 12.0`; the rest of stdout as the CLI-21 `static(30)` row |
| CLI-24 | argv `['clip.mp4', 'out', '--block-k', '0']`, thumbnails `[flat(0), patch(100)] * 10` | selection `0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 9.5 last`; line `  all frames taken by the timer: the largest change between thumbnails was 6.2, under the threshold 12.0; --threshold 2.0: 19 content frames at threshold 2.0 (3 sheets)` (m is 6.25) |
| CLI-24 | argv `['clip.mp4', 'out', '--block-k', '0']`, probe `(30.0, 800, 600)`, thumbnails `[flat(0), patch(100)] * 30` | selection `0.0 first`, timer frames every 3.0 s up to 27.0, `29.5 last`; line `  all frames taken by the timer: the largest change between thumbnails was 6.2, under the threshold 12.0; --threshold 2.0: 0 content frames at threshold 6.8 (2 sheets)` (at 2.0 all 60 thumbnails differ, the cap raises the threshold to 6.75, above 6.25) |
| CLI-24 | argv `['clip.mp4', 'out', '--dry-run']`, thumbnails `steps(4, 8)` | no "all frames" line (CLI-19 unchanged) |
| CLI-24, CLI-23 | the CLI-23 `static(240)` row at 125 s, the `alt(30)` row, the MAN-4 `--max-frames 5` row | the "all frames" line exactly as today, `... the threshold contributed nothing (effective <%.1f>); try --max-frames, --block-k or --from/--to` |
| unchanged | every `frames.json` of the rows above | identical to what the same argv gives today; only stdout changes |

### Errors (step 10)

Nothing new raises. The alternative uses `fit_to_cap`, so it terminates when it does.

## Step 11: quiet stretches get their own threshold (drafted and implemented 2026-09-26)

Anchored since 2026-09-26. Written as a draft before the code existed; the tester wrote red tests from it. A review before the first commit found that the closing end of a stretch could be lost and that `block_active` ignored the stretch thresholds; REC-10 and MAN-16 were amended, tests first, then the code. The same day an agent reported a 7 s recording with the bug moment dropped and no line printed; SEL-7 was amended so that a selection with no content frame before its last is one stretch whatever its length, tests first, then the code.

Why. Step 10 only named a lower threshold, and only when a whole recording went to the timer. The measurement behind this step (18 recordings, kept in the development repository) showed the problem is not limited to whole recordings. On the demo site, light and 1920x1080, the change from the cart to the checkout form moved the 32x32 thumbnail by 2.5 and the change to the review page, the one that shows two of the planted bugs, by 3.3; the default threshold 12 kept neither, and the timer happened to land within 1.5 s of both. A concatenation of a busy wide recording and the pale one from step 10 kept 3 content frames in the busy part and none in the pale part. Lowering the default to 4 instead changed the frames of 13 of the 15 recordings that are not pale, the long ones included (for example 14 -> 22 and 9 -> 15 frames on two phone recordings). The rule below changes 7: the pale wide recording (0 -> 9 content frames, the frame with the reported bug among them), the concatenation (3 -> 12), both demo-site pilots with timer runs (the two page changes above kept at the second they happen; an export progress bar), the calendar recording behind the README example (12 -> 19 frames, the date picks that the default skipped), and, through the short-recording amendment of SEL-7, the two short client recordings with no content frame (3 -> 6 frames each). The other 11, every recording where the cap was active, and the regression scenarios on them keep their bytes.

### Public surface added or changed

    def quiet_stretches(thumbs, threshold, max_gap, max_frames, block_k=BLOCK_K, sample_fps=SAMPLE_FPS)
    def select_frames(thumbs, threshold, max_gap, block_k=BLOCK_K, sample_fps=SAMPLE_FPS, quiet=())

`select`, `fit_to_cap` and every other name keep their signatures.

### Rules

REC-10 `select_frames` takes `quiet`, a sequence of dicts that each have at least `from`, `to` and `threshold` (seconds relative to the first thumbnail, and a threshold). A thumbnail at time `t` with `from < t <= to` for some entry is judged with that entry's threshold instead of `threshold`, both in the SEL-3 comparison and in the block bar (`block_k * <that threshold>`, still only when it is below 255). The first entry that contains `t` wins, so an end shared by two entries belongs to the earlier one. Thumbnails at exactly `from` of an entry that no earlier entry contains, and every thumbnail outside all entries, are judged as today. With `quiet` empty (the default) the result is identical to today's for every input.
       Why `to` is included. The closing end of a quiet stretch is a change the default kept. Judged at the default threshold against a frame kept inside the stretch, it can fall under that threshold and vanish: a popup shown for one thumbnail at the end of a pale stretch did (see the examples). Judged at the stretch threshold it is kept unless the frame kept just before it already shows it.

SEL-7  `quiet_stretches(thumbs, threshold, max_gap, max_frames, block_k, sample_fps)` returns a list of dicts with exactly the keys `from`, `to`, `timer`, `largest`, `threshold`, in time order.
       1. `frames = select_frames(thumbs, threshold, max_gap, block_k, sample_fps)`. The ends are the indices `k` of `frames` whose reason is not `timer`, plus the last index of `frames` whatever its reason.
       2. For each pair of consecutive ends `a < b` with at least 3 frames between them (`b - a - 1 >= 3`, all of them timer frames by construction), and for the pair of consecutive ends `a = 0`, `b = len(frames) - 1` when there is one, whatever the number of frames between them (the pair exists exactly when no frame before the last was kept for a change), with `p` and `q` the thumbnail indices of `frames[a]` and `frames[b]` (`round(time * sample_fps)`): `largest` is the largest SEL-3 difference of a thumbnail `i` with `p < i < q` against the thumbnail of the last frame of `frames` at an index below `i`. The pair is a candidate when `largest > 1.0`, with `from` `frames[a].time`, `to` `frames[b].time`, `timer` `b - a - 1` and `threshold` `max(1.0, math.floor(largest * 10 / 3) / 10)`, the CLI-24 formula.
       3. While the candidates are not empty and `len(select_frames(thumbs, threshold, max_gap, block_k, sample_fps, candidates)) > max_frames`, the candidate with the fewest timer frames is removed, the latest one among equals. The rest is returned.
       Empty `thumbs` gives `[]`.
       Why 3 timer frames. Two ends and three timer frames are five frames with no content, the MAN-11 convention for `all_timer`, applied to a stretch. Runs of 1 or 2 timer frames sit between content frames on every busy recording measured (718887, 719892, 720028, 720744) and are left alone; runs of 3 or more occurred only where the default missed events. Why the whole selection is exempt. A recording of 4 to 10 s with nothing kept for a change has at most 2 timer frames, so the minimum skipped exactly the short bug-report recordings, and MAN-11 keeps the "all frames" line off below 5 frames, so nothing was printed either. The minimum is there for short runs between content frames; a run from the first frame to the last has no content frame around it. On a light 7 s recording of a form (largest change 5.7) the stretch at 1.9 keeps the frame with the reported bug, the one `--threshold 2` kept by hand. Of the 18 measured recordings it changes only the two whose selection had no content frame (718825, 719884, both 3 -> 6 frames); on 718825 the new frame is the popup message that the recording was made to show, which the default skipped. A short selection that stays all timer after this either has largest change 1.0 or less, nothing to suggest, or lost its stretch to the cap in step 3, which at 2 fps, gap 3.0 and the default cap never happens (the pair spans at most 19 thumbnails); so MAN-11 is unchanged. Why the same third and 1.0 as CLI-24: the same measurements, and a stretch is judged the way CLI-24 judges a whole recording.

CLI-25 (amends CLI-23) Right after `fit_to_cap`, `main()` decides whether the cap was active (the CLI-23 condition). When it was not, `quiet = quiet_stretches(thumbs, threshold, max_gap, max_frames, block_k, sample_fps)`; when it was, `quiet = []`. The frames are `select_frames(thumbs, threshold, max_gap, block_k, sample_fps, quiet)`, and everything after uses them: the times written and extracted, the `selected <k>` count, the "frames" line, `all_timer`, `timer_share`, the layout, the sheets, CLI-24. When `quiet` is not empty, one line follows the "frames" line:

           quiet stretches at a lower threshold: <from %.1f>-<to %.1f> s at <threshold %.1f> (largest change <largest %.1f>); ...

       one entry per stretch joined by `; `, times shifted by the range start like every other time. It prints under `--dry-run` too. Nothing else about the line order changes.

MAN-16 (replaces MAN-15) `analysis` keys are exactly, in order: `sample_fps`, `thumbnails`, `max_frames`, `threshold`, `max_gap`, `block_k`, `block_active`, `range`, `segment`, `all_timer`, `timer_share`, `quiet`. `quiet` is a list with one dict per entry of CLI-25's `quiet`, keys exactly `from`, `to`, `largest`, `threshold`, with `from` and `to` shifted by the range start; `[]` when there is none. `block_active` is `block_k > 0 and block_k * <lowest> < 255`, where `<lowest>` is the smallest of the effective threshold and every threshold in `quiet`: the block rule counts as active when it can fire anywhere. The CLI-23 "block rule inactive" line prints exactly when `block_k > 0` and `block_active` is false, its text unchanged. Everything else as MAN-15 said.

Rows of earlier steps whose output changes. Every row that pins the `analysis` key list (MAN-15 rows and the CLI rows that check it) gains `quiet` at the end, `[]` in all of them except the ones below. The CLI-16/MAN-10/MAN-11 row with `--block-k 0` and `[flat(0), patch(100)] * 10`, the MAN-11 case with `--block-k 0` and `static(11) + [patch(100)] + static(18)`, and the CLI-24 rows with `steps(4, 8)` (with and without `--threshold 30`, and under `--dry-run`), `[flat(0)] * 10 + [flat(2)] * 20` and `[flat(i // 2) for i in range(30)]` now get a quiet stretch; their new values are in the examples below. The CLI-24 rows with `[flat(0)] * 10 + [flat(1)] * 20`, `static(30)` and `[flat(0), patch(100)] * 30` keep their lines: the first two have no stretch with a change above 1.0, and in the third the stretch does not fit the cap (60 frames at 2.0) and is dropped, so the frames stay all timer and CLI-24 prints as step 10 says. After the short-recording amendment of SEL-7, any input whose selection has no content frame before its last and a thumbnail between the two ends more than 1.0 from the frame kept before it gets a candidate however few timer frames it has. Among earlier rows, the MAN-10 input `[flat(0), straddle(100), flat(0), flat(0)]` keeps it, and its new values are in the examples below; the `alt(30)` rows with `--threshold 300 --max-gap 7` get a candidate (largest 255.0, threshold 85.0) that gives 30 frames, over the cap, so step 3 drops it and their output is unchanged. Inputs with no thumbnail between the ends, such as the REC-6 and MAN-10 input `[flat(0), straddle(100)]`, are unchanged.

### Examples (step 11)

`steps(a, b)` as in step 10. `split` is `[flat(0), flat(2)] * 12 + [flat(100)] * 10 + [flat(104)] * 10 + [flat(108)] * 10` (54 thumbnails, 26.5 s). `short` is `[flat(0)] * 7 + [flat(5)] * 5 + [flat(0)] * 2` (14 thumbnails, 6.5 s). `T, G` are `12.0, 3.0`. For `main()` rows the fakes are as before and `probe` returns `(15.0, 800, 600)` unless said otherwise.

| ID | Input | Result |
|---|---|---|
| REC-10 | `select_frames(steps(4, 8), 12.0, 3.0, quiet=[{"from": 0.0, "to": 14.5, "threshold": 1.3}])` | times and reasons `0.0 first, 3.0 timer, 5.0 diff, 8.0 timer, 10.0 diff, 13.0 timer, 14.5 last` |
| REC-10 | `select_frames(steps(4, 8), 12.0, 3.0, quiet=[{"from": 5.0, "to": 10.0, "threshold": 1.3}])` | `0.0 first, 3.0 timer, 5.5 diff, 8.5 timer, 10.0 diff, 13.0 timer, 14.5 last` (5.0 is judged at 12.0 and not kept; 10.0 is judged at 1.3, 4.0 against 8.5) |
| REC-10 | `popup = [flat(2 if i % 2 else 0) for i in range(20)] + [flat(13)] + [flat(0)] * 9`; `select_frames(popup, 12.0, 3.0)` and `select_frames(popup, 12.0, 3.0, quiet=[{"from": 0.0, "to": 10.0, "threshold": 1.0}])` | today `0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 10.0 diff, 10.5 diff, 13.5 timer, 14.5 last`; with the stretch `0.0 first`, `diff` at every 0.5 s from 0.5 to 10.5, `13.5 timer, 14.5 last` (24 entries). The popup at 10.0 is 11.0 against the frame at 9.5, under 12, and stays only because 10.0 is judged at 1.0 |
| REC-10 | `select_frames(steps(4, 8), 12.0, 3.0)` and the same with `quiet=[]` | both today's `0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last` |
| SEL-7 | `quiet_stretches(steps(4, 8), T, G, 24)` | `[{"from": 0.0, "to": 14.5, "timer": 4, "largest": 4.0, "threshold": 1.3}]` |
| SEL-7 | `quiet_stretches(steps(4, 8), 30.0, G, 24)` | the same list |
| SEL-7 | `quiet_stretches([flat(i // 2) for i in range(30)], T, G, 24)` | `[{"from": 0.0, "to": 14.5, "timer": 4, "largest": 3.0, "threshold": 1.0}]` |
| SEL-7 | `quiet_stretches(static(30), T, G, 24)`, `quiet_stretches([flat(0)] * 10 + [flat(1)] * 20, T, G, 24)` | `[]` (largest 0.0 and 1.0, not above 1.0) |
| SEL-7 | `quiet_stretches([flat(0)] * 5 + [flat(2)] * 11 + [flat(100)], T, G, 24)` | `[{"from": 0.0, "to": 8.0, "timer": 2, "largest": 2.0, "threshold": 1.0}]`: the selection `0.0 first, 3.0 timer, 6.0 timer, 8.0 diff` has no content frame before its last, so the two timer frames are enough; with the stretch the selection is `0.0 first, 2.5 diff, 5.5 timer, 8.0 diff` |
| SEL-7 | `quiet_stretches([flat(0)] + [flat(20)] * 8 + [flat(23)] * 6, T, G, 24)` | `[]`: the selection is `0.0 first, 0.5 diff, 3.5 timer, 6.5 timer, 7.0 last`, and the run after the content frame at 0.5 has two timer frames, so its change of 3.0 is not considered |
| SEL-7 | `quiet_stretches(short, T, G, 24)` | `[{"from": 0.0, "to": 6.5, "timer": 2, "largest": 5.0, "threshold": 1.6}]` (the selection is `0.0 first, 3.0 timer, 6.0 timer, 6.5 last`) |
| SEL-7 | `quiet_stretches([flat(0)] * 7 + [flat(4)] * 12, T, G, 24)` | `[{"from": 0.0, "to": 9.0, "timer": 2, "largest": 4.0, "threshold": 1.3}]`: the selection `0.0 first, 3.0 timer, 6.0 timer, 9.0 timer` ends on a timer frame, which is an end like any last frame; with the stretch `0.0 first, 3.0 timer, 3.5 diff, 6.5 timer, 9.0 last` |
| SEL-7 | `quiet_stretches([flat(3 * (i % 2)) for i in range(14)], T, G, 4)` and the same with `24` | `[]` with 4: the one candidate (0.0-6.5, timer 2, largest 3.0, threshold 1.0) gives 14 frames and is dropped by step 3; with 24 it is returned, `[{"from": 0.0, "to": 6.5, "timer": 2, "largest": 3.0, "threshold": 1.0}]` |
| SEL-7 | `quiet_stretches([flat(0)] * 3 + [flat(3)] * 2, T, G, 24)` | `[{"from": 0.0, "to": 2.0, "timer": 0, "largest": 3.0, "threshold": 1.0}]` (the selection is `0.0 first, 2.0 last`, no timer frame at all) |
| SEL-7 | `quiet_stretches(static(14), T, G, 24)`, `quiet_stretches([flat(0), straddle(100)], T, G, 24)`, `quiet_stretches([flat(0)], T, G, 24)` | `[]` (largest 0.0; no thumbnail between the two ends; one frame, no pair of ends) |
| SEL-7 | `quiet_stretches([flat(0), patch(100)] * 10, T, G, 24, 0.0)` | `[{"from": 0.0, "to": 9.5, "timer": 3, "largest": 6.25, "threshold": 2.0}]` |
| SEL-7 | `quiet_stretches([flat(0), patch(100)] * 30, T, G, 24, 0.0)` | `[]` (the one candidate gives 60 frames at 2.0) |
| SEL-7 | `quiet_stretches(split, T, G, 24)` | `[{"from": 12.0, "to": 26.5, "timer": 4, "largest": 4.0, "threshold": 1.3}]`: both candidates give 31 frames, the one with 3 timer frames (0.0-12.0, largest 2.0) is removed, the other gives 11 |
| SEL-7 | `quiet_stretches(split, T, G, 60)` | `[{"from": 0.0, "to": 12.0, "timer": 3, "largest": 2.0, "threshold": 1.0}, {"from": 12.0, "to": 26.5, "timer": 4, "largest": 4.0, "threshold": 1.3}]` |
| SEL-7 | `quiet_stretches(popup, T, G, 24)` | `[{"from": 0.0, "to": 10.0, "timer": 3, "largest": 2.0, "threshold": 1.0}]` (24 frames, exactly the cap) |
| SEL-7 | `quiet_stretches([], T, G, 24)` | `[]` |
| CLI-25, MAN-16 | argv `['clip.mp4', 'out']`, thumbnails `steps(4, 8)` | stdout lines 2-4 `  30 thumbnails, selected 7/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)` / `  frames: 0.0 first, 3.0 timer, 5.0 diff, 8.0 timer, 10.0 diff, 13.0 timer, 14.5 last` / `  quiet stretches at a lower threshold: 0.0-14.5 s at 1.3 (largest change 4.0)`, then the layout line; no "all frames" line; `analysis.quiet` `[{"from": 0.0, "to": 14.5, "largest": 4.0, "threshold": 1.3}]`, `all_timer` false, `timer_share` 0.6 |
| CLI-25 | the same with `--threshold 30` | the same frames and quiet line, second line `(threshold 30.0 -> 30.0, ...)` |
| CLI-25 | the same with `--dry-run` | the first five lines as above (header, thumbnails, frames, quiet, layout), nothing written |
| CLI-25, MAN-16 | argv `['clip.mp4', 'out', '--from', '5']`, probe `(20.0, 800, 600)`, thumbnails `steps(4, 8)` | `  frames: 5.0 first, 8.0 timer, 10.0 diff, 13.0 timer, 15.0 diff, 18.0 timer, 19.5 last` / `  quiet stretches at a lower threshold: 5.0-19.5 s at 1.3 (largest change 4.0)`; `analysis.quiet` `[{"from": 5.0, "to": 19.5, "largest": 4.0, "threshold": 1.3}]` |
| CLI-25 | argv `['clip.mp4', 'out']`, thumbnails `[flat(0)] * 10 + [flat(2)] * 20` | `  frames: 0.0 first, 3.0 timer, 5.0 diff, 8.0 timer, 11.0 timer, 14.0 timer, 14.5 last` / `  quiet stretches at a lower threshold: 0.0-14.5 s at 1.0 (largest change 2.0)`; `timer_share` 0.8 |
| CLI-25 | argv `['clip.mp4', 'out']`, thumbnails `[flat(i // 2) for i in range(30)]` | `  selected 9/24`, `  frames: 0.0 first, 2.0 diff, 4.0 diff, 6.0 diff, 8.0 diff, 10.0 diff, 12.0 diff, 14.0 diff, 14.5 last` / `  quiet stretches at a lower threshold: 0.0-14.5 s at 1.0 (largest change 3.0)` |
| CLI-25 | argv `['clip.mp4', 'out', '--block-k', '0']`, probe `(10.0, 800, 600)`, thumbnails `[flat(0), patch(100)] * 10` | `  selected 20/24`, frames `0.0 first`, then `diff` at every 0.5 s from 0.5 to 9.5 (the end 9.5 is judged at 2.0, so no `last` entry); `  quiet stretches at a lower threshold: 0.0-9.5 s at 2.0 (largest change 6.2)`; no "all frames" line; `all_timer` false |
| CLI-25 | argv `['clip.mp4', 'out', '--block-k', '0']`, thumbnails `static(11) + [patch(100)] + static(18)` | `  frames: 0.0 first, 3.0 timer, 5.5 diff, 6.0 diff, 9.0 timer, 12.0 timer, 14.5 last` / `  quiet stretches at a lower threshold: 0.0-14.5 s at 2.0 (largest change 6.2)`; `all_timer` false |
| CLI-25 | argv `['clip.mp4', 'out']`, probe `(27.0, 800, 600)`, thumbnails `split` | `  54 thumbnails, selected 11/24 (...)` / `  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 diff, 15.0 timer, 17.0 diff, 20.0 timer, 22.0 diff, 25.0 timer, 26.5 last` / `  quiet stretches at a lower threshold: 12.0-26.5 s at 1.3 (largest change 4.0)` |
| CLI-25 | argv `['clip.mp4', 'out']`, thumbnails `popup` | `  selected 24/24`, frames as the REC-10 `popup` row with the stretch; `  quiet stretches at a lower threshold: 0.0-10.0 s at 1.0 (largest change 2.0)` |
| MAN-16, CLI-25 | argv `['clip.mp4', 'out', '--threshold', '60']`, thumbnails `[flat(0)] * 3 + [flat(30)] * 3 + [p] * 3 + [flat(30)] * 21` where `p` is `flat(30)` with the top-left 8x8 block at 100 | `  frames: 0.0 first, 1.5 diff, 3.0 block, 4.5 block, 7.5 timer, 10.5 timer, 13.5 timer, 14.5 last` / `  quiet stretches at a lower threshold: 0.0-14.5 s at 11.4 (largest change 34.4)`; `block_active` true (5.0 x 11.4 = 57.0) and no "block rule inactive" line, although 5.0 x 60.0 is 300 |
| CLI-25, MAN-16 | argv `['clip.mp4', 'out']`, probe `(7.0, 800, 600)`, thumbnails `short` | stdout lines 2-4 `  14 thumbnails, selected 5/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)` / `  frames: 0.0 first, 3.0 timer, 3.5 diff, 6.0 diff, 6.5 last` / `  quiet stretches at a lower threshold: 0.0-6.5 s at 1.6 (largest change 5.0)`, then the layout line; `analysis.quiet` `[{"from": 0.0, "to": 6.5, "largest": 5.0, "threshold": 1.6}]`, `all_timer` false, `timer_share` 0.33; `frames[2]` and `frames[3]` have `diff` 5.0 |
| CLI-25 | the same with `--dry-run` | the first five lines as above (header, thumbnails, frames, quiet, layout), nothing written |
| CLI-25, MAN-11 | argv `['clip.mp4', 'out']`, probe `(7.0, 800, 600)`, thumbnails `static(14)` | `  frames: 0.0 first, 3.0 timer, 6.0 timer, 6.5 last`, no quiet line and no "all frames" line (4 frames, MAN-11 unchanged); `analysis.quiet` `[]`, `all_timer` false |
| CLI-25, MAN-10 | argv `['clip.mp4', 'out']`, probe `(2.0, 800, 600)`, thumbnails `[flat(0), straddle(100), flat(0), flat(0)]` | `  frames: 0.0 first, 0.5 diff, 1.0 diff, 1.5 last` / `  quiet stretches at a lower threshold: 0.0-1.5 s at 2.0 (largest change 6.2)`; `frames[1]` `diff` 6.25, `block` 50.0; `frames[3]` reason `"last"`, `diff` 0.0, `block` 0.0 (against the frame kept at 1.0). Before the short-recording amendment this input kept only `0.0 first, 1.5 last` |
| CLI-25, CLI-24 | argv `['clip.mp4', 'out', '--block-k', '0']`, probe `(30.0, 800, 600)`, thumbnails `[flat(0), patch(100)] * 30` | no quiet line, `analysis.quiet` `[]`; the CLI-24 line of step 10 unchanged |
| CLI-25, MAN-16 | any row with an active cap (the CLI-23 `ramp`, `static(240)` at 125 s and `alt(30)` rows) | no quiet line, `analysis.quiet` `[]`, everything else unchanged |

### Errors (step 11)

Nothing new raises. `quiet_stretches` terminates: each round of step 3 removes one candidate.

## Step 12: the events selector, `--selector events` (drafted and implemented 2026-09-27)

The legacy selector stays the default and keeps its bytes; this step adds a second selector behind a flag (step 13 made the events selector the default). EVT-3 was added after round 11. GRD-1 was amended and FF-9 added after a hands-on check found that the analysed and the extracted frames differed; FF-8 is removed, superseded by FF-9, and CLI-26 and MAN-17 changed with them. All implemented 2026-09-27. A review then found a blinking caret counted as changes (EVT-4 added), a radio dot taken for the pointer without a word in the output, a not-shown line that named the whole recording, events crowding out the frames in `frames.json`, `-fps_mode` needing ffmpeg 5.1, rotated recordings failing and a quadratic `pick`; the amendments below answer them, implemented the same day. A second review then found `-vsync` removed in ffmpeg 9.0, a caret rule that missed a caret which stops blinking and folded a one-digit counter into "a caret", an ignored caret still cutting the window of the text typed next to it, a `--to` hint past the end of the video and exact ties in `pick` broken differently from PCK-2; FF-11 and the rewritten EVT-4 answer them, and the rows marked "re-review" below.

Why. Every legacy decision is one number, the mean grey difference of two 32x32 thumbnails squashed from the whole frame, compared with a constant. That number is the changed share of the frame times the contrast, so a change that matters on a screen (a 16 px checkbox on a 2120x422 window, dark text replacing dark text on a light page, a small popup) scores 0.06 to 3.6 against a threshold of 12, while at native resolution the same change is hundreds to tens of thousands of pixels over a codec noise of zero. Steps 4, 10 and 11 each moved a constant for the last recording that failed and the next recording failed in the corner none of them covered (three agent reports in three days, 2026-09-25 to 27). Measured in the development repository against ground truth labeled by two independent agents plus an adjudicator on 15 recordings (110 key and 186 key-or-normal events): the legacy selector shows 74% of key events and 63% of all, the events selector as implemented here 92% and 88% (the labels were taken on a sample grid half a sample later than `round=up`, so this is the upper of two bounds; the lower is 78% and 68%), a frame every 0.5 s without a cap 96% and 93% with twice the frames. In a reading test on all 15 (125 questions, two readers per output, a blind judge), agents answered 80.0% from legacy output and 94.4% from this selector's output, with 10 confidently wrong answers against 1. Legacy also extracts a different frame than it analysed: `fps=2` keeps the last source frame of each half-second slot, `-ss t` the frame at t, so 25 of 61 legacy frames kept for a change show the state before it; the events selector samples with `round=up`, which makes the analysed and the extracted frame the same.

### Vocabulary (step 12)

- A sample is a pair `(mean, change)` of bytes-like objects (`change_grids` returns `memoryview` slices, the examples `bytes`), each `gw * gh` long, one byte per cell of `CELL x CELL` native pixels, row-major. `mean` is the cell's mean luma. `change` is 255 times the share of the cell's pixels whose luma moved by more than `PIXEL_T` since the previous sample. Sample `k` has time `k / EVENT_FPS` relative to the range start.
- `grid(cells)` is `bytes` of length 200 (`gw = 20`, `gh = 10`) with cell `(x, y)` at index `y * 20 + x` set to `cells[(x, y)]` and every other byte 0. `box(x0, y0, w, h, v=255)` is the dict of every `(x, y)` with `x0 <= x < x0 + w`, `y0 <= y < y0 + h` mapped to `v`. `S(cells)` is the sample `(bytes(200), grid(cells))`. Dicts are merged with `|`.
- A blob is a dict with exactly the keys `px`, `x`, `y`, `w`, `h`, `global`: changed pixels (float), bounding box in native pixels, and whether it is the whole-frame blob of BLB-3. `blob(x, y, w=24, h=32, px=300.0, g=False)` in the examples is such a dict.
- A window is a tuple `(settled, until, weight)` of two sample indices and a float.
- `M(mean_cells, change_cells)` is the sample `(grid(mean_cells), grid(change_cells))`, for rows where the cell means matter.

### Public surface added (step 12)

    EVENT_FPS = 4
    CELL = 8
    PIXEL_T = 24
    def change_grids(path, width, height, fps=EVENT_FPS, start=0.0, length=None)   [hands-on]
    def blobs(change, gw, gh, cell=CELL)
    def pointer(bs)
    def events_of(content, joined=True)
    def pick(windows, budget, last, fps=EVENT_FPS)
    def fill(points, long_pairs, budget, fps=EVENT_FPS)
    def select_events(samples, gw, gh, budget, fps=EVENT_FPS)
    def save_samples(path, indices, times, out_dir, tile_width, fps=EVENT_FPS, start=0.0, length=None)   [hands-on]
    def display_size(path, width, height)                                                              [hands-on]
    def passthrough(version)

Constants used by the rules below, module-level with these exact names and values: `MIN_CELL = 8`, `NOISE_PX = 12`, `GLOBAL_SHARE = 0.25`, `POINTER_BOX = 64`, `POINTER_DIM = 8`, `POINTER_PX = 0.45`, `REGION_MARGIN = 16`, `LONG_S = 2.0`, `INNER_WEIGHT = 0.8`, `GLOBAL_WEIGHT = 4.0`, `EPISODE_S = 5.0`, `SPREAD = 0.5`, `FILL_MIN_S = 0.5`, `HOLD_DELTA = 6`, `HOLD_SHARE = 0.25`, `BLINK_REPEATS = 4`, `CARET_H = 64`. Every other name keeps its signature.

### Rules (step 12)

GRD-1 [hands-on] `change_grids(path, width, height, fps, start, length)` runs one ffmpeg process with `-ss start` (and `-t length` when `length` is not None) before `-i path`, and the filter graph `[0:v]fps=<fps>:round=up:start_time=0,format=pix_fmts=yuv420p|yuvj420p|yuv422p|yuvj422p|yuv444p|yuvj444p|gray,extractplanes=y,setrange=full,crop=<cw>:<ch>:0:0,split[a][b];[a]scale=<gw>:<gh>:flags=area+accurate_rnd[m];[b]tblend=all_mode=difference,lut=c0='if(gt(val,<PIXEL_T>),255,0)',scale=<gw>:<gh>:flags=area+accurate_rnd[d]`, where `cw = width // CELL * CELL`, `gw = cw // CELL`, and likewise `ch`, `gh` from `height`. `[m]` and `[d]` go to two raw grey outputs, each with `<passthrough(ffmpeg_version())> passthrough` (FF-11), in a temporary directory that is removed afterwards. `[m]` has one image per sample, the `mean` of samples 0, 1, ...; `[d]` has as many images (the first repeats the second, then it is dropped) or one fewer, and its images in order are the `change` of samples 1, 2, ...; the `change` of sample 0 is `gw * gh` zero bytes. It returns `(gw, gh, samples)`. Why so, all measured on 2026-09-27 (with a script kept in the development repository). Stacked into one output with `vstack`, the pairing of `[m]` and `[d]` depended on the input: sample 0 never matched the plain `fps` chain, and on pilot1 from 1.3 s every sample was one late. Without `passthrough` the output side duplicated a frame at the start whenever the range start fell between two source frames, so the samples no longer matched a second pass. `start_time=0` makes sample 0 the frame at the range start in that case too, so sample `k` is at `start + k / fps`. `setrange=full` stops `scale` from stretching limited-range luma (16-235) to full range on the way to the cells, which shifted phone recordings' means by up to 20 levels against the frames. Why `round=up`: it makes sample `k` the frame on screen at `start + k / fps`, the frame `-ss` extracts; the default rounding keeps the last frame of a slot, up to half a slot later. Why the `format` list: `extractplanes` needs planar input, and the listed formats pass through without a conversion (a `format=gray` conversion costs 16 s on 20 minutes of 720p, measured).

GRD-2 [hands-on] On a 60 fps, a 30 fps and a 25 fps H.264 recording, from 0 and from a start between source frames, `change` of sample `k >= 1` equals the share of pixels of each cell whose luma differs by more than `PIXEL_T` between the frames `save_samples` extracts as samples `k - 1` and `k`, and `mean` of sample `k` is the cell average of the second (measured: identical, at most 1 level of rounding in the means).

BLB-1 `blobs(change, gw, gh, cell)` returns the blobs of one sample, in the order their first cell appears in row-major order. A cell is active when its byte is at least `MIN_CELL`. Two active cells belong to the same blob when their column indices differ by at most 2 and their row indices by at most 2, and blobs are closed under that relation.

BLB-2 A blob's `px` is the sum of its cells' bytes times `cell * cell / 255` (a float, not rounded), `x` and `y` the smallest column and row times `cell`, `w` and `h` the column and row span plus one, times `cell`, `global` false. A blob with `px` under `NOISE_PX` is dropped.

BLB-3 When more than `GLOBAL_SHARE * gw * gh` cells are active, `blobs` returns exactly one blob: `px` the sum of all bytes times `cell * cell / 255`, `x` and `y` 0, `w` `gw * cell`, `h` `gh * cell`, `global` true.

PTR-1 `pointer(bs)` is true exactly when `bs` has two blobs, neither global, each with `w` and `h` at most `POINTER_BOX`, whose `w` differ by at most `POINTER_DIM`, whose `h` differ by at most `POINTER_DIM`, and whose `px` differ by at most `POINTER_PX` times the larger `px`. Such a pair is the pointer leaving one place and appearing at another.
       Why nothing more. The prototype also learned pointer shapes and tracked the pointer to call lone pointer-sized blobs the pointer. On the labeled recordings both made results worse (key events 98% with them, 100% without), because a checkbox, an icon or a text selection has the pointer's size.

EVT-1 `events_of(content, joined)` takes `content`, a list whose item `k` is the list of content blobs of pair `k` (item 0 unused), and returns events: dicts with at least the keys `start`, `end`, `settled`, `until`, `px`, `x`, `y`, `w`, `h`, `global`, `weight`, in creation order. It walks `k = 1, 2, ...`. When blob `c` of pair `k` is processed, the open events are those with `end >= k - 1` when `joined` is true, `end == k` when false; an event created or extended by an earlier blob of the same pair is open either way (so with `joined` false an event can only grow within one pair). For each blob `c` of pair `k` in order: the open events `e` that overlap `c` with margin `REGION_MARGIN` (below) are hit. No hit: a new open event with `start` and `end` `k`, `px`, `x`, `y`, `w`, `h`, `global` from `c`. Hits: the first hit absorbs the others in order (box union, `px` sum, smallest `start`, `global` or; the absorbed events are removed from the result), then absorbs `c` the same way and gets `end = k`. Boxes `a`, `b` overlap with margin `m` when `a.x - m < b.x + b.w`, `b.x - m < a.x + a.w`, `a.y - m < b.y + b.h` and `b.y - m < a.y + a.h`.

EVT-2 After the walk, every event gets `settled = end`, `until` = one less than the first `k > end` whose content has a blob overlapping the event with margin 0, or `len(content) - 1` when there is none, and `weight = ln(1 + px)`, plus `GLOBAL_WEIGHT` when `global`. The event's final state is on screen from sample `settled` to sample `until`.

EVT-3 (amends PCK-4 step 2) In `select_events`, right after `events_of(content)`, each event's `until` is cut where its box stops looking as it did at `settled`. The box's cells are the columns `x // CELL` to `(x + w) // CELL - 1` and the rows `y // CELL` to `(y + h) // CELL - 1`. For `j = settled + 1, ..., until`, the first `j` at which more than `HOLD_SHARE` times the number of those cells have a `mean` byte in sample `j` differing by more than `HOLD_DELTA` from the same cell in sample `settled` sets `until = j - 1`. Everything after uses the cut `until`: the windows, the containment test of step 4, the reasons, the console line and `shown` in the manifest. The `joined=False` events of step 4 are not cut.
       Why. A pale change, a yellow row flash on a white table, moves few pixels by more than `PIXEL_T` and its undo moves none, so EVT-2 kept the flash on screen until the next change of that area, seconds later, and a frame long after the flash counted as showing it; the manifest said `shown` for a state no kept frame showed. On the labeled recordings this cost one key event (a short window the budget could not afford) and removed that false claim.

EVT-4 (amends PCK-4 step 2 and, in the second pass below, EVT-3; rewritten after the re-review and again after the final review) In `select_events`, after EVT-3, the events of step 2 are grouped by their box (`x`, `y`, `w`, `h`), groups in the order their first event appears, the events of a group in result order. Only a group whose box is at most `CELL` wide and at most `CARET_H` tall can hold a blinking area. An event of such a group is faint when its `px` is under `w * h / 2`. The look of an event in sample `j` is the `mean` bytes of its box's cells (the cells of EVT-3) in sample `j`, and its look, unqualified, the one in sample `settled`; two looks differ when more than `HOLD_SHARE` times the number of those cells differ by more than `HOLD_DELTA` (the EVT-3 test). The group's events are walked in order, building runs; a run's looks are the looks of its first two events. An event that is not faint ends the current run and belongs to no run. A faint event, when the current run has at least two events and the event's look differs from both of the run's looks, ends the run; the event then belongs to no run if its look in sample `start - 1` does not differ from one of the ended run's looks (a change made in the box from a state the run had, such as a character typed into the caret's cell), and otherwise starts the next run (the box changed without an event, such as the pointer coming to rest over the caret). A faint event whose look does not differ from that of the current run's only event replaces it: that event belongs to no run, and the run starts anew with this one. Every other faint event joins the current run. A run is a blinking area when at least `BLINK_REPEATS` of its events have `until - settled` under `fps`; the run's events are the area's blinks. When there are blinking areas: for every blink and every pair `k` from its `start` to its `end`, the blobs of `content[k]` whose box lies inside the blink's box (`b.x <= c.x`, `c.x + c.w <= b.x + b.w`, and the same for `y` and `h`) are removed; a pair that lost a blob and whose remaining blobs make `pointer` true is emptied and counted in `pointer_moves`. Then step 2 runs again on that content: `events_of`, then EVT-3 with the cells of the event's box that lie inside the box of a blinking area whose `first..last` overlaps the event's `settled..until` left out, both from the comparison and from the number of cells; an event with no cells left is not cut. Steps 3 and 4 use this content and these events. The areas are returned under `blinking` as dicts with exactly `x`, `y`, `w`, `h`, `count` (the number of blinks), `first` and `last` (the `settled` of its first and of its last blink), in group order and, within a group, in time order.
       Why. A text caret blinks for as long as a field has focus. On pilot1 one 8x32 px box changed 15 times at 22 px each and produced 7 "not shown" changes, a false alarm; a static screen with a focused field would report hundreds of changes. The first rule (every event brief, `px` under `CELL * CELL`) failed in three shapes the re-review built as synthetic recordings: a caret that stops when the field loses focus leaves a long last event, so the group failed and 19 of 21 frames went to the caret; a 3x40 px HiDPI caret changes 120 px, over 64 (56 changes, 33 not shown); a one-digit counter stepping every 0.75 s had four brief faint changes in an 8x16 px box and was folded into "a caret", its values gone. And a caret dropped only after the windows were found still cut the window of the text typed into the cell it sits in. Two looks tell a caret or a blinking indicator from a counter; counting the brief events instead of requiring all of them keeps a caret that pauses or stops; half the box's area scales with the caret's height. The final review then found that rewrite folding any one-cell-thin line (a 200x8 px validation underline, a 64x8 px hover underline), a caret still cutting one to three typed characters through EVT-3 (its column is a third or more of their cells), a pointer move in the pair of a blink counted as two changes (44 changes on a recording where only the caret and the pointer moved), and a caret never folded after one narrow character typed into its cell, whose own change and third look joined the group. Hence the upright box, the runs of faint events, the removal of the blinks' blobs only, the pointer test after it and the cells left out of EVT-3. Measured with this rule: on the 15 labeled recordings and four more the same two carets fold (o6kq, pilot1), the recall stays 101 of 110 key and 163 of 186 key-or-normal events, and one frame of pilot-rec1 moves by 0.25 s; on the synthetic recordings the stopping caret goes from 19 changes to 0, the HiDPI caret from 56 to 0, the counter keeps its 5 changes, the underlines are changes again (21 to 31), 1 to 8 typed characters stay on screen to the end, the caret with the pointer goes from 44 changes to 1 and 42 pointer moves, one typed character from 104 changes to 35 (the rest are toasts), a "1" typed into the caret's cell from 35 to 3. A last check of that rule found three more things, measured on synthetic recordings. A faint change with a third look in the caret's box, a dot typed into its cell or the pointer's I-beam coming to rest over it, broke the caret's run (54 to 56 changes, 43 to 45 of them "not shown" at 12 frames); with the walk above those recordings give 0 or 1 change, every other synthetic recording and all 19 real ones are unchanged. An event inside a caret's box was never cut by EVT-3, even long after the caret stopped (hence the overlap of `first..last` and `settled..until`). And the code counted the cells of two areas to the right of an event, in its rows, as negative (the `two_carets` row below). A pair left with two alike pointer-sized blobs after the removal is taken for the pointer as PTR-1 takes any such pair, so two alike toasts at a blink's pair count as a pointer move, as they do at any other pair. Left as they are: a 2 px caret across a cell boundary (a box two cells wide) still counts as changes, since a two-cell limit would also fold a small checkbox toggled four times in a row; a terminal's block cursor spans two cells and is not folded either, nor is the caret of a 3x phone recording, about 6 px wide and usually across two cells; a one-cell-wide digit that flips between two values folds, which the console line admits; a mark of one cell inside a caret's box of four or more cells changes too few cells to be a third look and folds with the caret.

PCK-1 `pick(windows, budget, last, fps)` returns sorted sample indices. First the stabbing set: the windows sorted by `(until, settled)`; a point is appended at `until` whenever there is no point yet or the last point is below `settled`. With `0` and `last` added, if the set has at most `budget` points it is the result. This is the smallest set of points that hits every window.

PCK-2 Over budget: start from `{0, last}`; a window is covered when a chosen point lies inside it. Bursts: the windows sorted by `settled` split into groups wherever two consecutive `settled` differ by more than `round(EPISODE_S * fps)`. Groups are taken in order of their largest weight, larger first, groups with equal largest weights in time order; a group with a covered window is skipped; otherwise, while fewer than `budget` points are chosen, the `until` of its heaviest window is chosen (ties: the earlier `until`). Then, while fewer than `budget` points are chosen, the candidate `t` among all `until` values not yet chosen with the largest gain is chosen, the gain being the sum, in the order of `windows`, of the weights of uncovered windows that contain `t`, times `1 + SPREAD * ln(1 + d / fps)` with `d` the distance from `t` to the nearest chosen point; ties go to the smaller `t`; nothing is chosen when the best gain is 0.
       Why bursts first. On a 20 minute concatenation of ten clips the plain weighted choice left two clips without a frame.

PCK-3 `fill(points, long_pairs, budget, fps)` adds points while fewer than `budget`: among consecutive points `a < b` with `b - a >= 2 * round(FILL_MIN_S * fps)` and at least one of `long_pairs` strictly between, the pair with the largest `(count of those pairs) * (b - a)` wins (ties: the earlier `a`); the new point is the one of those pairs nearest to `(a + b) / 2` (ties: the smaller), replaced by `round((a + b) / 2)` when it is closer than `round(FILL_MIN_S * fps)` to `a` or to `b`. It returns the sorted points.

PCK-4 `select_events(samples, gw, gh, budget, fps)` returns `{'frames': [(k, reason), ...], 'events': events, 'blinking': [...], 'pointer_moves': n, 'needed': m}` .
       1. For every pair `k >= 1`, `bs = blobs(samples[k][1], gw, gh)`; its content is `[]` when `pointer(bs)`, otherwise `bs`. `pointer_moves` is the number of pairs for which `pointer(bs)` held.
       2. `events = events_of(content)`. The windows are `(settled, until, weight)` of every event, plus, for every event with `end - start + 1 > round(LONG_S * fps)`, the windows `(j, j, INNER_WEIGHT * weight)` for `j = start + n, start + 2n, ...` below `end`, `n = round(LONG_S * fps)`. The pairs `start..end` of those events are the long pairs.
       3. `needed = len(pick(windows, len(windows) + 2, len(samples) - 1, fps))`, the frames every window would take. `points = pick(windows, budget, len(samples) - 1, fps)`, then `fill(points, long pairs, budget, fps)`.
       4. While fewer than `budget` points: the events of `events_of(content, joined=False)` that are not contained in an event of step 2 (contained: `settled` and `until` both within the step 2 event's `settled..until`, and the boxes overlap with margin 0), taken by weight, larger first (ties: smaller `settled`), each add its `until` unless a point already lies inside its `settled..until`. These are states inside a transition, a toggle and its undo within half a second.
       5. Reasons, first match: `first` for 0, `last` for `len(samples) - 1`, `state` for a point of step 4, `fill` for a point `fill` added, `change` when the point lies inside some event's `settled..until`, otherwise `during`.
       Empty `samples` gives `{'frames': [], 'events': [], 'blinking': [], 'pointer_moves': 0, 'needed': 0}`.

CLI-26 `--selector {legacy,events}`, default `legacy` (step 13: the default is set by CLI-28). With `legacy` nothing changes. With `events`, after `probe` and the range checks, `main()` takes `width, height = display_size(video, width, height)` (everything after, the header line and `video` in the manifest included, uses this size), fails with `<video>: the frame (<w>x<h>) is smaller than 8x8 px; use --selector legacy` (exit 1) when either side is under `CELL`, and calls `change_grids(video, width, height, EVENT_FPS, start, end - start if ranged else None)` (stage name `grids` in the ffmpeg failure message), fails with `could not decode the video: no frames` when it returns no samples, and takes `select_events(samples, gw, gh, max_frames)`; `thumbnails` is not called. Frame times are `start + k / EVENT_FPS`, and the frames are written by `save_samples(video, ks, times, out_dir, tile_width, EVENT_FPS, start, length)`, where `ks` are the kept sample indices and `length` is what `change_grids` got. `--threshold`, `--max-gap`, `--block-k` and `--sample-fps` belong to the legacy selector: given together with `--selector events` they are a usage error (exit 2) with the message `--threshold, --max-gap, --block-k and --sample-fps apply to the legacy selector only`. Their defaults, help texts and validation are unchanged for `legacy`.

CLI-27 Console of the events selector (amended after review): the header line and the range line as today, then
       `  <samples> samples at 4 per second, <changes> changes, <pointer_moves> pointer moves, selected <frames>/<max_frames>`
       `  frames: <time %.2f> <reason>, ...`
       then one line per blinking area, `  ignored a blinking area at <x>,<y> <w>x<h> px (<count> times from <start + first / 4 %.2f> to <start + last / 4 %.2f> s): a text caret, or a small mark toggled back and forth` (final review: it said "such as a text caret", but a one-cell-wide mark flipping between two values folds too),
       then at most one of these lines, then the layout line as today:
       with no events and at least 2 samples, `  no change: the first and the last frame only` when `pointer_moves` is 0, otherwise `  no change except <pointer_moves> pointer-like moves (the pointer, or a small mark such as a radio dot): the first and the last frame only`;
       when `n` events have no frame inside their `settled..until`, `  <n> of <changes> changes not shown within <max_frames> frames (all of them would need <needed>); <c> of them from <a %.2f> to <b %.2f> s: rerun with --from <a' %.2f> --to <b' %.2f>`, where the times `start + settled / 4` of those events, sorted, are split into runs wherever two neighbours are more than 10 s apart, the run with the most times (the earliest on ties) gives `c`, its first time `a` and its last `b`, `a' = max(start, a - 1)` and `b'` is `min(end, b + 1)` rounded down to two decimals, `math.floor(min(end, b + 1) * 100 + 1e-6) / 100` (re-review: `%.2f` alone rounded a duration of 10.066667 s up to `--to 10.07`, which the rerun refuses as past the end).
       Why these lines. A radio dot that jumps between two options is two alike pointer-sized blobs, which PTR-1 takes for the pointer; the count says there was such a move instead of claiming nothing happened. The old not-shown line named the first and the last missing time, on a 20 minute recording 0.50 to 1097.50 s, and `--from 0.25 --to 0.25` for a single one, which `--from/--to` refuse.
       Under `--dry-run` it stops after the layout line. Otherwise the contact sheets, the more-than-4-sheets line and the manifest line as today; none of the legacy hint lines (block rule, by the timer, all frames taken by the timer, quiet stretches) print.

MAN-17 `frames.json` of the events selector has the top-level keys of MAN-1 plus `segments`, in the same order as the legacy selector. `analysis` has exactly, in order: `selector` (`"events"`), `sample_fps` (4), `samples`, `cell` (8), `pixel_threshold` (24), `max_frames`, `range` (`{"from": start, "to": end}` as in the legacy analysis), `segment`, `changes` (number of events), `shown` (events with a frame inside `settled..until`), `pointer_moves`, `blinking` (a list of `{"region": [x, y, w, h], "count": n, "from": start + first / 4, "to": start + last / 4}`). The events are a top-level key `events`, after `segments` (they were the last key of `analysis`, and on a 24 s recording pushed `frames` past line 4000 of the file). `events` has one dict per event in `select_events` order with exactly `from`, `settled`, `until` (`start + index / 4` for `start`, `settled`, `until`), `region` (`[x, y, w, h]`), `changed_px` (`round(px)`), `shown` (bool). Every frame entry has exactly `n`, `time`, `file`, `sheet`, `reason`, `recheck`. `recheck` is `shlex.join` of `ffmpeg -ss <start %.3f>`, then `-t <length %.3f>` when a range was given, then `-i <video> -vf fps=4:round=up:start_time=0,select=eq(n\,<k>) <passthrough(<the manifest's ffmpeg>)> passthrough -frames:v 1 -q:v 2 <out_dir>/frame-<NN>-native.jpg`: the same chain as `save_samples`, so the native frame is the analysed sample, not the frame `-ss <time>` would give (checked by hand on a 25 fps, a 30 fps and a 60 fps recording, from 0 and from starts between source frames). `segments` are `segments(times, start, end, segment)` with `activity` the number of events whose `start + settled / 4` lies in `[from, to)` of the segment (the last segment includes its `to`).

FF-8 removed, superseded by FF-9 (`save_frames` keeps its step 3 signature).

FF-10 [hands-on] `display_size(path, width, height)` runs ffprobe for the first video stream's `rotation` side data and `rotate` tag and returns `(height, width)` when one of them is 90 or 270 degrees (either sign), otherwise `(width, height)`. Why: ffmpeg turns a rotated stream upright while decoding, so a 1280x720 stream tagged 90 degrees arrives as 720x1280 and the crop sized from the probe failed (`ffmpeg failed during grids (exit 234)`, measured).

FF-9 [hands-on] `save_samples(path, indices, times, out_dir, tile_width, fps, start, length)` cleans `out_dir` as `save_frames` does and runs one ffmpeg process with the same `-ss start` and `-t length` as `change_grids` and the filter `fps=<fps>:round=up:start_time=0,select='<eq(n\,k) for every k in indices, joined by +>',scale=<tile_width>:-1`, passing every selected image through (`<passthrough(ffmpeg_version())> passthrough`, FF-11), and names the images, in order, `frame-<NN>-<times[i] %.2f>s.jpg`; it returns their paths. When ffmpeg wrote fewer images than `times` it raises `ValueError('ffmpeg wrote <got> of <wanted> frames')` before renaming any. The extracted image of index `k` is the frame `change_grids` analysed as sample `k`. Why not `-ss <time>` per frame as legacy does: on the 15 labeled recordings `-ss` gave a different frame than the analysed sample for 65 of the 325 frames the events selector keeps; screen recorders write irregular timestamps, and at 25 or 30 fps the frame on screen at `t` and the first frame at or after `t` differ.

FF-11 `passthrough(version)` returns `'-vsync'` when `version` starts with a match of `ffmpeg version n?(\d+)\.(\d+)` whose two numbers, as integers, are below `(5, 1)`, and `'-fps_mode'` otherwise, a version line that does not parse (a git build `N-...`, a dated build, an empty string) included.
       Why. `-fps_mode` appeared in ffmpeg 5.1 and `-vsync` was removed in 9.0 (commit 927ffd0930), so no single option runs on both. With `-vsync` everywhere the selector failed on 9.0.2 with `ffmpeg failed during grids (exit 8): Error splitting the argument list: Option not found` (measured with a static 9.0.2 build). Measured with this rule on static builds 4.4.1 and 9.0.2 against the system 6.1.1, 13 recordings, dry runs: every sample count, frame line, blinking line and not-shown line equal on 4.4.1, and on 9.0.2 equal on 12 recordings; on the thirteenth 9.0.2 decodes one more sample at the end (56 against 55), so its last frame is 13.75 s instead of 13.50. 5.0.1 (`-vsync`) gave the same frames as 6.1 on one recording.

No row of an earlier step changes: the legacy selector is untouched. `main()` rows of this step fake `save_samples` the way earlier rows fake `save_frames`, returning `<out_dir>/frame-<NN>.jpg` paths.

### Examples (step 12)

`S`, `grid`, `box` and `blob` as in the vocabulary; `GW, GH = 20, 10`. For `main()` rows the fakes are as before, `probe` returns `(2.0, 160, 80)` unless said otherwise, and `change_grids` is replaced by a fake that returns `(20, 10, samples)` for the samples named in the row and records its arguments.

| ID | Input | Result |
|---|---|---|
| BLB-1, BLB-2 | `blobs(grid(box(2, 2, 3, 4)), 20, 10)` | `[{"px": 768.0, "x": 16, "y": 16, "w": 24, "h": 32, "global": False}]` |
| BLB-1 | `blobs(grid(box(2, 2, 1, 1) \| box(4, 2, 1, 1)), 20, 10)` | one blob, `px` 128.0, `x` 16, `y` 16, `w` 24, `h` 8 (a gap of one cell joins) |
| BLB-1 | `blobs(grid(box(2, 2, 1, 1) \| box(5, 2, 1, 1)), 20, 10)` | two blobs, `px` 64.0 each, `x` 16 and 40, `w` 8 (a gap of two cells does not) |
| BLB-1, BLB-2 | `blobs(grid(box(2, 2, 1, 1, v)), 20, 10)` for `v` 7, 8, 51 | `[]`, `[]` (8 is active, `px` 2.0078 is under 12), one blob with `px` 12.8 |
| BLB-2 | `blobs(grid(box(0, 0, 10, 5, 100)), 20, 10)` | one blob, `px` 1254.9019607843138, `w` 80, `h` 40, `global` False (50 of 200 cells is not more than a quarter) |
| BLB-3 | `blobs(grid(box(0, 0, 10, 5) \| box(10, 0, 1, 1)), 20, 10)` | `[{"px": 3264.0, "x": 0, "y": 0, "w": 160, "h": 80, "global": True}]` |
| BLB-1 | `blobs(grid({}), 20, 10)`, `blobs(grid(box(3, 3, 2, 2)), 20, 10, cell=4)` | `[]`; one blob with `px` 64.0, `x` 12, `y` 12, `w` 8, `h` 8 |
| PTR-1 | `a = blob(80, 40, px=190.0)`, `b = blob(120, 48, px=170.0)`: `pointer([a, b])` | True |
| PTR-1 | `pointer([a])`, `pointer([a, b, blob(200, 48)])`, `pointer([a, b \| {"px": 90.0}])`, `pointer([a, b \| {"w": 40}])`, `pointer([a \| {"w": 72}, b \| {"w": 72}])`, `pointer([a \| {"global": True}, b])` | all False (one blob; three; `px` 90 is more than 45% under 190; widths 24 and 40; wider than 64; global) |
| EVT-1, EVT-2 | `events_of([[], [], [blob(16, 16)], [], [], [blob(100, 16)], [blob(16, 16)], []])` | three events: `start` 2, `end` 2, `settled` 2, `until` 5, `x` 16; `start` 5, `settled` 5, `until` 7, `x` 100; `start` 6, `settled` 6, `until` 7, `x` 16; each `px` 300.0, `w` 24, `h` 32, `global` False |
| EVT-1 | `events_of([[], [blob(16, 16)], [blob(40, 16)], [blob(16, 16)], [], []])` | one event, `start` 1, `end` 3, `settled` 3, `until` 5, `px` 900.0, `x` 16, `w` 48, `h` 32 (each change touches the growing box of the previous pair) |
| EVT-1 | the same with `joined=False` | three events: `start` 1, `until` 2, `x` 16; `start` 2, `until` 5, `x` 40; `start` 3, `until` 5, `x` 16 |
| EVT-1 | `events_of([[], [blob(16, 16)], [blob(100, 16)], [blob(0, 0, 160, 80, 5000.0, True)], []])` | two events: `start` 1, `end` 1, `until` 2, `x` 16; `start` 2, `end` 3, `settled` 3, `until` 4, `px` 5300.0, box `0, 0, 160, 80`, `global` True (the whole-frame blob absorbs the open event at 100) |
| EVT-1 | `events_of([[], [blob(16, 16)], [], [blob(56, 16)], []])` and the same with `blob(57, 16)` | two events both times, `until` 4 and 4 (a pair without change in between ends the first event, so the margin does not matter) |
| EVT-2 | `events_of([[], [blob(0, 0, px=300.0)]])[0]["weight"]`, `events_of([[], [blob(0, 0, 160, 80, 5000.0, True)]])[0]["weight"]` | `ln(301)` (5.7071 to 4 places), `ln(5001) + 4` (12.5174) |
| PCK-1 | `pick([(2, 4, 1.0), (3, 6, 1.0), (7, 7, 1.0)], 24, 9)` | `[0, 4, 7, 9]` |
| PCK-1 | `pick([(2, 4, 1.0), (5, 6, 1.0), (7, 7, 1.0)], 24, 9)` | `[0, 4, 6, 7, 9]` |
| PCK-1 | `pick([], 24, 0)`, `pick([], 24, 5)`, `pick([(0, 3, 1.0)], 24, 5)`, `pick([(2, 5, 1.0)], 24, 5)` | `[0]`, `[0, 5]`, `[0, 3, 5]`, `[0, 5]` |
| PCK-2 | `pick([(2, 4, 1.0), (5, 6, 1.0), (7, 7, 1.0), (8, 8, 1.0)], 4, 9)` | `[0, 4, 6, 9]` |
| PCK-2 | `pick([(2, 2, 5.0), (3, 3, 1.0), (40, 40, 1.0), (41, 41, 1.0)], 4, 60)` | `[0, 2, 40, 60]` (two bursts, one frame each) |
| PCK-2 | `pick([(2, 2, 5.0), (3, 3, 1.0), (4, 4, 1.0), (5, 5, 1.0)], 4, 60)` | `[0, 2, 5, 60]` |
| PCK-2 | `pick([(2, 2, 1.0), (3, 3, 1.0), (4, 4, 1.0), (30, 30, 1.0), (31, 31, 1.0)], 5, 60)` | `[0, 2, 4, 30, 60]` |
| PCK-3 | `fill([0, 20], list(range(4, 17)), 5)` | `[0, 5, 10, 15, 20]` |
| PCK-3 | `fill([0, 20], [], 5)`, `fill([0, 3], [1, 2], 5)`, `fill([0, 20, 40], list(range(21, 40)), 5)` | `[0, 20]`, `[0, 3]`, `[0, 20, 25, 30, 40]` |
| PCK-4 | `select_events([S({}), S({}), S(box(2, 2, 3, 4)), S({}), S({}), S({}), S({}), S({})], 20, 10, 24)` | frames `[(0, "first"), (7, "last")]`; one event, `start` 2, `settled` 2, `until` 7, `px` 768.0 (the toggle stays to the end, so the last frame shows it) |
| PCK-4 | `ptr = [S({}), S(box(2, 2, 3, 4, 170) \| box(10, 2, 3, 4, 150)), S(box(10, 2, 3, 4, 170) \| box(15, 5, 3, 4, 160)), S({}), S({})]`: `select_events(ptr, 20, 10, 24)` | frames `[(0, "first"), (4, "last")]`, no events (both pairs are the pointer), `pointer_moves` 2 |
| PCK-4 | `select_events([S({}), S(box(2, 2, 3, 4, 170) \| box(10, 2, 3, 4, 150)), S({}), S(box(15, 5, 3, 3)), S({}), S({})], 20, 10, 24)` | frames `[(0, "first"), (5, "last")]`; one event, `start` 3, `until` 5, `px` 576.0, box `120, 40, 24, 24` |
| PCK-4 | `select_events([S({})] * 6, 20, 10, 24)`, `select_events([S({})], 20, 10, 24)`, `select_events([], 20, 10, 24)` | `[(0, "first"), (5, "last")]` and no events; `[(0, "first")]`; `{"frames": [], "events": [], "blinking": [], "pointer_moves": 0, "needed": 0}` |
| PCK-4 | `dbl = [S({}), S(box(2, 2, 3, 3)), S(box(2, 2, 3, 3)), S({}), S({})]`: `select_events(dbl, 20, 10, 24)` and with budget 2 | `[(0, "first"), (1, "state"), (4, "last")]`, one event `start` 1, `settled` 2, `until` 4, `px` 1152.0; with budget 2 `[(0, "first"), (4, "last")]` |
| PCK-4 | `two = [S({}), S(box(2, 2, 3, 3)), S({}), S(box(12, 2, 3, 3)), S({}), S(box(2, 2, 3, 3)), S({})]`: `select_events(two, 20, 10, 24)` | `[(0, "first"), (4, "change"), (6, "last")]`; events `start` 1 `until` 4 box `16, 16, 24, 24`; `start` 3 `until` 6 box `96, 16, 24, 24`; `start` 5 `until` 6 box `16, 16, 24, 24` (sample 4 shows both earlier states) |
| PCK-4 | `long = [S({})] + [S(box(0, 0, 20, 10, 60))] * 12 + [S({}), S({})]`: `select_events(long, 20, 10, 4)` | `[(0, "first"), (4, "fill"), (9, "during"), (14, "last")]`; one event, `start` 1, `settled` 12, `until` 14, `global` True |
| PCK-4 | `select_events(long, 20, 10, 24)` | `[(0, "first"), (1, "state"), (2, "fill"), (3, "state"), (4, "fill"), (5, "state"), (6, "fill"), (7, "state"), (8, "state"), (9, "during"), (10, "state"), (11, "fill"), (14, "last")]` |
| PCK-4 | `select_events(two, 20, 10, 24)["needed"]`, `select_events(two, 20, 10, 2)["needed"]`, `select_events([S({})], 20, 10, 24)["needed"]` | 3, 3, 1 (`[0, 4, 6]` shows every change; one sample is one frame) |
| EVT-4 | `ON = box(5, 2, 1, 4, 100)`, `C = box(5, 2, 1, 4, 60)`, `blink = [M(ON if k % 4 in (1, 2) else {}, C if k % 2 == 1 else {}) for k in range(10)]` (a caret that appears at 1, 5, 9 and goes at 3, 7, each look on screen for two samples): `select_events(blink, 20, 10, 24)` | frames `[(0, "first"), (9, "last")]`, no events, `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 5, "first": 1, "last": 9}]`, `needed` 2 |
| EVT-4 | `three`: `blink` with the means of samples 5 and 6 replaced by `box(5, 2, 1, 4, 180)` (a third look) | `blinking` `[]`; five events, box `40, 16, 8, 32`, `px` 60.2353 to 4 places, `(settled, until)` `(1, 2)`, `(3, 4)`, `(5, 6)`, `(7, 8)`, `(9, 9)`; frames `[(0, "first"), (2, "change"), (4, "change"), (6, "change"), (8, "change"), (9, "last")]`, `needed` 6 |
| EVT-4 | `blink + [M(ON, {}), M({}, C)] + [M({}, {})] * 4` (the caret goes at 11 and stays gone: a long last event) | frames `[(0, "first"), (15, "last")]`, no events, `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 6, "first": 1, "last": 11}]` |
| EVT-4 | `blink[:8] + [M({}, {})] * 8 + blink[:8]` (focus lost for two seconds, then back) | frames `[(0, "first"), (23, "last")]`, no events, `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 8, "first": 1, "last": 23}]` |
| EVT-4 | `blink` with the means `box(5, 2, 2, 4, 100)` and the changes `box(5, 2, 2, 4, 30)` (two cells wide), and `blink` with the changes `box(5, 2, 1, 4, 128)` (128.502 px, not under half of 8x32) | `blinking` `[]` both times, five events each, frames as in the `three` row |
| EVT-4 | `blink[:7] + [M({}, {})] * 3` (three changes) | `blinking` `[]`; three events, box `40, 16, 8, 32`, `until` 2, 4 and 6; frames `[(0, "first"), (2, "change"), (4, "change"), (6, "change"), (9, "last")]` |
| EVT-4 | `TEXT = box(2, 2, 5, 2, 150)`, `CARET = {(6, 1): 100, (6, 2): 120, (6, 3): 120, (6, 4): 100}`, `CC = box(6, 1, 1, 4, 60)`, `typed = [M({}, {}), M(TEXT, box(2, 2, 5, 2))] + [M(TEXT \| (CARET if k % 4 in (0, 3) else {}), CC if k % 2 == 1 else {}) for k in range(2, 12)]` (text typed at 1, then a caret blinking in the text's last cell column): `select_events(typed, 20, 10, 2)` | frames `[(0, "first"), (11, "last")]`; `blinking` `[{"x": 48, "y": 8, "w": 8, "h": 32, "count": 5, "first": 3, "last": 11}]`; one event, `start` 1, `settled` 1, `until` 11, box `16, 16, 40, 16`, `px` 640.0 (with the caret's blobs left in `content` its first blink at 3 cut `until` to 2, and the text counted as not shown) |
| EVT-4 | `blink` with the means `box(2, 5, 10, 1, 100)` and the changes `box(2, 5, 10, 1, 60)` (an 80x8 px underline), and with the means `box(5, 0, 1, 9, 100)` and the changes `box(5, 0, 1, 9, 30)` (8x72 px, taller than `CARET_H`) (final review) | `blinking` `[]` both times; five events each, box `16, 40, 80, 8` with `px` 150.5882 to 4 places, and box `40, 0, 8, 72` with `px` 67.7647; frames as in the `three` row |
| EVT-4 | `PA = box(10, 2, 3, 4, 170)`, `PB = box(15, 5, 3, 4, 160)`, `ptr_blink = [M(ON if k % 4 in (1, 2) else {}, (C \| PA \| PB) if k == 3 else (C if k % 2 == 1 else {})) for k in range(10)]` (the pointer moves in the pair where the caret goes off) (final review) | frames `[(0, "first"), (9, "last")]`, no events, `pointer_moves` 1, `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 5, "first": 1, "last": 9}]` (pair 3 holds three blobs, so PTR-1 fails on it until the caret's blob is removed) |
| EVT-4 | `TEXT2 = box(5, 2, 2, 2, 150)`, `short = [M({}, {}), M(TEXT2, box(5, 2, 2, 2))] + [M(TEXT2 \| (CARET if k % 4 in (0, 3) else {}), CC if k % 2 == 1 else {}) for k in range(2, 12)]` (two typed cells, the caret in the second): `select_events(short, 20, 10, 2)` (final review) | frames `[(0, "first"), (11, "last")]`; `blinking` `[{"x": 48, "y": 8, "w": 8, "h": 32, "count": 5, "first": 3, "last": 11}]`; one event, `start` 1, `settled` 1, `until` 11, box `40, 16, 16, 16`, `px` 256.0 (with the caret's cells compared, two of the text's four cells differ at 3 and EVT-3 cut `until` to 2) |
| EVT-4 | `ON2 = box(5, 2, 1, 4, 180)`, `CHAR = box(5, 2, 1, 4, 50)`, `narrow = [M((ON if k % 4 in (1, 2) else {}) if k < 9 else (ON2 if (k - 9) // 2 % 2 == 0 else CHAR), box(5, 2, 1, 4, 200) if k == 9 else (C if k % 2 == 1 else {})) for k in range(19)]` (the caret blinks, a narrow character is typed into its cell at 9, the caret blinks next to it) (final review) | frames `[(0, "first"), (18, "last")]`; `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 4, "first": 1, "last": 7}, {"x": 40, "y": 16, "w": 8, "h": 32, "count": 4, "first": 11, "last": 17}]`; one event, `start` 9, `settled` 9, `until` 18, box `40, 16, 8, 32`, `px` 200.7843 to 4 places (not faint, so it ends the first run and stays a change) |
| EVT-4 | `PL = box(12, 2, 2, 4, 150)`, `PR = box(4, 2, 2, 4, 150)`, `IB = box(4, 2, 2, 4, 60)`, `rest = [M((ON if k % 4 in (1, 2) else {}) if k < 8 else IB \| (box(5, 2, 1, 4, 160) if k % 4 in (1, 2) else {}), (PL \| PR) if k == 8 else (C if k % 2 == 1 else {})) for k in range(18)]` (at 8 the pointer comes to rest over the caret, a pointer pair; the caret blinks on under it) (last check) | frames `[(0, "first"), (17, "last")]`, no events, `pointer_moves` 1, `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 4, "first": 1, "last": 7}, {"x": 40, "y": 16, "w": 8, "h": 32, "count": 5, "first": 9, "last": 17}]` (the look before 9 is the pointer's, not one of the first run's) |
| EVT-4 | `dot = [M((ON if k % 4 in (1, 2) else {}) if k < 9 else box(5, 2, 1, 4, 130 if k % 4 in (1, 2) else 30), box(5, 2, 1, 4, 90) if k == 9 else (C if k % 2 == 1 else {})) for k in range(19)]` (a faint change with a third look at 9, made from the run's "off" look: a dot typed into the caret's cell) (last check) | frames `[(0, "first"), (18, "last")]`; `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 4, "first": 1, "last": 7}, {"x": 40, "y": 16, "w": 8, "h": 32, "count": 4, "first": 11, "last": 17}]`; one event, `start` 9, `settled` 9, `until` 18, box `40, 16, 8, 32`, `px` 90.3529 to 4 places |
| EVT-4 | `same = [M(ON if k in (1, 2, 3, 4) or (k >= 7 and k % 4 in (3, 0)) else {}, C if k in (1, 3) or (k >= 5 and k % 2 == 1) else {}) for k in range(16)]` (the first two faint events have the same look) (last check) | frames `[(0, "first"), (15, "last")]`; `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 7, "first": 3, "last": 15}]`; one event, `start` 1, `settled` 1, `until` 15 (it belongs to no run and, being inside the area's box with `first..last` overlapping, is not cut) |
| EVT-4 | `two_carets`: 24 samples, the text `box(2, 2, 2, 2, 150)` typed at 1 (change `box(2, 2, 2, 2)`), a caret in column 7 (`box(7, 1, 1, 4)`, means 100 when on) changing at 3, 7, 11, ... and one in column 10 changing at 5, 9, 13, ..., each on for four samples from its first change and off for four, changes 60; from 12 on, the text's cell `(2, 2)` has mean 151 (one level of noise). Written out: `two_carets = [M(({} if k < 1 else TX \| ({(2, 2): 151} if k >= 12 else {}) \| (box(7, 1, 1, 4, 100) if k >= 3 and (k - 3) // 4 % 2 == 0 else {}) \| (box(10, 1, 1, 4, 100) if k >= 5 and (k - 5) // 4 % 2 == 0 else {})), box(2, 2, 2, 2) if k == 1 else box(7, 1, 1, 4, 60) if k >= 3 and (k - 3) % 4 == 0 else box(10, 1, 1, 4, 60) if k >= 5 and (k - 5) % 4 == 0 else {}) for k in range(24)]` with `TX = box(2, 2, 2, 2, 150)` (last check) | frames `[(0, "first"), (23, "last")]`; `blinking` `[{"x": 56, "y": 8, "w": 8, "h": 32, "count": 6, "first": 3, "last": 23}, {"x": 80, "y": 8, "w": 8, "h": 32, "count": 5, "first": 5, "last": 21}]`; one event, `start` 1, `settled` 1, `until` 23, box `16, 16, 16, 16`, `px` 256.0 (neither area lies in the text's columns; the level of noise is not a difference) |
| EVT-4 | `after_stop = blink + [M(ON, {}), M({}, C), M({}, {}), M({}, {}), M(box(5, 2, 1, 4, 40), box(5, 2, 1, 4, 40)), M(box(5, 2, 1, 4, 40), {})] + [M({}, {})] * 4` (the caret stops at 11; at 14 a pale mark appears in its box and goes at 16 without a change over `PIXEL_T`) (last check) | frames `[(0, "first"), (15, "change"), (19, "last")]`; `blinking` `[{"x": 40, "y": 16, "w": 8, "h": 32, "count": 6, "first": 1, "last": 11}]`; one event, `start` 14, `settled` 14, `until` 15, `px` 40.1569 to 4 places (the area's `1..11` does not overlap `14..19`, so its cells are compared and EVT-3 cuts at 16) |
| PCK-2 | property (re-review): 4000 inputs from `random.Random(20260927)`, `last` 5 to 120, 1 to 30 windows `(a, min(last, a + d), w)` with `a` uniform in `0..last`, `d` from `0, 1, 2, 3, 5, 10, 40` and `w` uniform in 2.5 to 14.0, budgets 2 to 12 | `pick` equals a direct implementation of PCK-1 and PCK-2 that recomputes every gain from scratch, summed in the order of `windows` (exact ties go to the smaller `t`) |
| EVT-3 | `flash = [M({}, {}), M(box(2, 2, 3, 1, 200), box(2, 2, 3, 1)), M({}, {}), M({}, {}), M({}, {})]`: `select_events(flash, 20, 10, 24)` | frames `[(0, "first"), (1, "change"), (4, "last")]`; one event, `settled` 1, `until` 1 (the means go back at sample 2; without the rule `until` would be 4 and the frames `[(0, "first"), (4, "last")]`) |
| EVT-3 | `on = box(2, 2, 4, 2, 200)`; `select_events([M({}, {}), M(on, box(2, 2, 4, 2)), M(on \| {(2, 2): 0}, {}), M(on \| {(2, 2): 194}, {}), M(on \| box(2, 2, 3, 1, 0), {}), M({}, {})], 20, 10, 24)` | frames `[(0, "first"), (3, "change"), (5, "last")]`; one event, box `16, 16, 32, 16`, `settled` 1, `until` 3 (one cell of eight off is not more than a quarter; 194 is within 6 of 200; three cells of eight off at sample 4 is) |
| CLI-26, CLI-27 | argv `['clip.mp4', 'out', '--selector', 'events']`, samples `two` | return 0; `change_grids` called once with `('clip.mp4', 160, 80, 4, 0.0, None)`; stdout exactly: `clip.mp4: 2.0 s, 160x80, landscape` / `  7 samples at 4 per second, 3 changes, 0 pointer moves, selected 3/24` / `  frames: 0.00 first, 1.00 change, 1.50 last` / `  layout: wide, tile 160 px, 2x18 per sheet` / `  contact sheets: out/sheet-01.jpg` / the manifest line |
| CLI-27 | the same with `--max-frames 2` | line 2 `  7 samples at 4 per second, 3 changes, 0 pointer moves, selected 2/2`, line 3 `  frames: 0.00 first, 1.50 last`, line 4 `  1 of 3 changes not shown within 2 frames (all of them would need 3); 1 of them from 0.25 to 0.25 s: rerun with --from 0.00 --to 1.25` (only the first event has no frame in `1..4`) |
| CLI-27 | argv `['clip.mp4', 'out', '--selector', 'events']`, samples `[S({})] * 6` | line 3 `  frames: 0.00 first, 1.25 last`, line 4 `  no change: the first and the last frame only` |
| CLI-27 | argv `['clip.mp4', 'out', '--selector', 'events']`, samples `ptr` | line 2 `  5 samples at 4 per second, 0 changes, 2 pointer moves, selected 2/24`, line 4 `  no change except 2 pointer-like moves (the pointer, or a small mark such as a radio dot): the first and the last frame only` |
| CLI-27, MAN-17 | argv `['clip.mp4', 'out', '--selector', 'events']`, samples `blink` | line 3 `  frames: 0.00 first, 2.25 last`, line 4 `  ignored a blinking area at 40,16 8x32 px (5 times from 0.25 to 2.25 s): a text caret, or a small mark toggled back and forth`, line 5 `  no change: the first and the last frame only`; `analysis.changes` 0, `analysis.blinking` `[{"region": [40, 16, 8, 32], "count": 5, "from": 0.25, "to": 2.25}]`, top-level `events` `[]` |
| CLI-27, MAN-17 | the same with `--from 1`, probe `(4.0, 160, 80)` | line 4 (after the range line) `  frames: 1.00 first, 3.25 last`, line 5 `  ignored a blinking area at 40,16 8x32 px (5 times from 1.25 to 3.25 s): a text caret, or a small mark toggled back and forth`; `analysis.blinking` `[{"region": [40, 16, 8, 32], "count": 5, "from": 1.25, "to": 3.25}]` |
| CLI-27 | argv `['clip.mp4', 'out', '--selector', 'events', '--max-frames', '2']`, probe `(1.618, 160, 80)`, samples `late = [S({}), S({}), S({}), S(box(2, 2, 3, 3)), S({}), S(box(2, 2, 3, 3)), S({})]` | line 3 `  frames: 0.00 first, 1.50 last`, line 4 `  1 of 2 changes not shown within 2 frames (all of them would need 3); 1 of them from 0.75 to 0.75 s: rerun with --from 0.00 --to 1.61` (1.618 rounded down) |
| CLI-27 | argv `['clip.mp4', 'out', '--selector', 'events']`, samples `[S({})]` | line 2 `  1 samples at 4 per second, 0 changes, 0 pointer moves, selected 1/24`, line 3 `  frames: 0.00 first`, then the layout line (no "no change" line for one sample) |
| CLI-26 | argv `['clip.mp4', 'out', '--selector', 'events']`, probe `(2.0, 80, 160)`, `display_size` faked to return `(160, 80)`, samples `two` | `display_size` called with `('clip.mp4', 80, 160)`; `change_grids` called with `('clip.mp4', 160, 80, 4, 0.0, None)`; header `clip.mp4: 2.0 s, 160x80, landscape`; manifest `video.width` 160, `video.height` 80 |
| CLI-26 | argv `['clip.mp4', 'out', '--selector', 'events']`, probe `(2.0, 6, 6)` | return 1, stderr `clip.mp4: the frame (6x6) is smaller than 8x8 px; use --selector legacy`, `change_grids` not called |
| CLI-26 | the `two` row with the fake `save_samples` raising `ValueError('ffmpeg wrote 2 of 3 frames')` | return 1, stderr `clip.mp4: ffmpeg wrote 2 of 3 frames`, the first four stdout lines printed, no `frames.json` |
| CLI-27 | the `two` row with `--dry-run` | the first four lines of that row (header, samples, frames, layout), nothing written, `change_grids` still called |
| CLI-26 | argv `['clip.mp4', 'out', '--selector', 'events', '--from', '1']`, probe `(3.0, 160, 80)`, samples `two` | `change_grids` called with `('clip.mp4', 160, 80, 4, 1.0, 2.0)` (a range was given, so the length is `3.0 - 1.0`); `save_samples` called with `('clip.mp4', [0, 4, 6], [1.0, 2.0, 2.5], 'out', 160, 4, 1.0, 2.0)`; the first frame's `recheck` is `ffmpeg -ss 1.000 -t 2.000 -i clip.mp4 -vf 'fps=4:round=up:start_time=0,select=eq(n\,0)' -fps_mode passthrough -frames:v 1 -q:v 2 out/frame-01-native.jpg`; stdout line 2 `  range: 1.0-3.0 s`, line 4 `  frames: 1.00 first, 2.00 change, 2.50 last` |
| CLI-26 | argv `['clip.mp4', 'out', '--selector', 'events', '--threshold', '5']`, and the same with `--max-gap 2`, `--block-k 0`, `--sample-fps 4` | exit 2, stderr contains `--threshold, --max-gap, --block-k and --sample-fps apply to the legacy selector only`, `change_grids` not called |
| CLI-26 | argv `['clip.mp4', 'out', '--selector', 'events']` with `change_grids` returning `(20, 10, [])` | return 1, stderr `could not decode the video: no frames` |
| CLI-26 | argv `['clip.mp4', 'out', '--selector', 'bogus']` | exit 2 (argparse choices) |
| CLI-26 | any legacy row with `--selector legacy` added | identical output and manifest to the row without it |
| MAN-17 | the first CLI-26/CLI-27 row | `analysis` is `{"selector": "events", "sample_fps": 4, "samples": 7, "cell": 8, "pixel_threshold": 24, "max_frames": 24, "range": {"from": 0.0, "to": 2.0}, "segment": 120.0, "changes": 3, "shown": 3, "pointer_moves": 0, "blinking": []}`; the top-level keys are `tool, version, ffmpeg, video, analysis, sheet, frames, sheets, segments, events`, and `events` is `[{"from": 0.25, "settled": 0.25, "until": 1.0, "region": [16, 16, 24, 24], "changed_px": 576, "shown": true}, {"from": 0.75, "settled": 0.75, "until": 1.5, "region": [96, 16, 24, 24], "changed_px": 576, "shown": true}, {"from": 1.25, "settled": 1.25, "until": 1.5, "region": [16, 16, 24, 24], "changed_px": 576, "shown": true}]`; frames `n` 1..3 with `time` 0.0, 1.0, 1.5, `reason` `first`, `change`, `last`, keys exactly `n, time, file, sheet, reason, recheck`; `save_samples` called once with `('clip.mp4', [0, 4, 6], [0.0, 1.0, 1.5], 'out', 160, 4, 0.0, None)` and `save_frames` not called; the second frame's `recheck` is `ffmpeg -ss 0.000 -i clip.mp4 -vf 'fps=4:round=up:start_time=0,select=eq(n\,4)' -fps_mode passthrough -frames:v 1 -q:v 2 out/frame-02-native.jpg`; `segments` `[{"n": 1, "from": 0.0, "to": 2.0, "frames": [1, 2, 3], "activity": 3}]` |
| MAN-17 | the `--max-frames 2` row | `analysis.changes` 3, `analysis.shown` 2, top-level `events[0].shown` false |
| MAN-17, FF-11 | the first CLI-26/CLI-27 row with `ffmpeg_version` returning `'ffmpeg version 4.4.1-static https://johnvansickle.com/ffmpeg/'` | `ffmpeg` in the manifest is that line; the second frame's `recheck` is `ffmpeg -ss 0.000 -i clip.mp4 -vf 'fps=4:round=up:start_time=0,select=eq(n\,4)' -vsync passthrough -frames:v 1 -q:v 2 out/frame-02-native.jpg` |
| FF-11 | `passthrough(v)` for `v` `'ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers'`, `'ffmpeg version n9.0.2-10-g51c4a23d74-20260926 Copyright (c) 2000-2026 the FFmpeg developers'`, `'ffmpeg version 5.1'`, `'ffmpeg version 10.0'`, `'ffmpeg version 7.1-full_build-www.gyan.dev'` | `'-fps_mode'` each |
| FF-11 | `passthrough(v)` for `v` `'ffmpeg version 4.4.1-static https://johnvansickle.com/ffmpeg/'`, `'ffmpeg version 5.0.1'`, `'ffmpeg version n4.3.2'` | `'-vsync'` each |
| FF-11 | `passthrough(v)` for `v` `'ffmpeg version N-112345-gabcdef0'`, `'ffmpeg version 2024-10-10-git-0f5592cfc7-full_build-www.gyan.dev'`, `''`, `'avconv version 12'` | `'-fps_mode'` each (does not parse, taken as new) |

### Errors (step 12)

`change_grids` raises `subprocess.CalledProcessError` when ffmpeg fails; `main()` reports it as the other stages do, with the stage name `grids`. `save_samples` raises `ValueError` when ffmpeg wrote fewer frames than asked; `main()` prints `<video>: <message>` and returns 1.

## Step 13: the events selector by default (drafted and implemented 2026-09-27)

Why. On the 15 labeled recordings (4.7 to 38 s, 110 key and 186 key-or-normal events), scored by the source frame each method actually shows, the events selector shows 78% of key events and 69% of all (332 frames), the legacy selector as shipped (with the quiet stretches of step 11) 63% and 54% (179 frames), `claude-real-video` 56% and 46% (160 frames). Scored by frame times against the labels' own sample grid, which favours methods on that grid, the same three give 86% and 79%, 76% and 66%, 71% and 61% (the 92% and 88% of step 12 were the reference model with a lenient bound). Agents reading the output answered 94.4% of 125 questions right from the events selector against 80.0% from the legacy selector, with 1 confidently wrong answer against 10. The events selector ran without a fault on all 19 real recordings of the development repository, and on ffmpeg 4.4.1, 5.0.1, 6.1.1 and 9.0.2 on up to 13 of them. It costs about twice the time on long recordings (18.3 s against 9.2 s on 20 minutes of 720p). The agent that reran the checkbox recording on step 12 found the default path still blind there (12 timer frames), and the events selector "better than anything before"; an agent that follows the skill starts with no options. So the events selector becomes the default. Not settled by this step: on these short recordings 24 evenly spaced frames show 83% and 76% by the source-frame score (355 frames), more than the events selector, and were not part of the reading test; that comparison is open. The legacy selector stays behind `--selector legacy` as a fallback, deprecated, to be removed after real runs of the new default; its offset bug (25 of 61 frames kept for a change show the state before it) is not fixed for that reason. Scripts and agents that pass a legacy-only option keep getting the legacy selector.

CLI-28 When `--selector` is not given, the selector is `legacy` if any of `--threshold`, `--max-gap`, `--block-k`, `--sample-fps` is given (present on the command line, whatever its value, so `--threshold 12` counts), and `events` otherwise. An explicit `--selector` always wins: `--selector events` with a legacy-only option stays the CLI-26 usage error, `--selector legacy` works with or without them. Nothing else changes: each selector prints, writes and fails exactly as in its own rows. The help text of `--selector` is `events: changed pixels at native resolution, one frame per screen state that changed (the default); legacy: 32x32 thumbnails against a threshold, a timer and a cap, deprecated and to be removed; --threshold, --max-gap, --block-k or --sample-fps without --selector choose legacy`, that of `--max-frames` is `cap on kept frames (default: 24)`, and those of the four legacy-only options start with `legacy selector only: ` followed by their step 1 to 11 text (`legacy selector only: thumbnails per second analysed (default: 2.0)` for `--sample-fps`). They are listed after `--selector` in `--help`.

Every `main()` row of steps 1 to 11, and every step 12 row whose argv has no `--selector`, is read with `--selector legacy` added to its argv when it is a legacy row (it fakes `thumbnails`) and with `--selector events` added when it is an events row (it fakes `change_grids`); its result does not change.

### Examples (step 13)

`two`, `S`, the fakes and the probe as in the step 12 examples; `static(30)` as in the legacy examples.

| ID | Input | Result |
|---|---|---|
| CLI-28 | argv `['clip.mp4', 'out']`, samples `two` | the result of the first CLI-26/CLI-27 row (argv with `--selector events`): return 0, `change_grids` called once with `('clip.mp4', 160, 80, 4, 0.0, None)`, `thumbnails` not called, the same stdout and `frames.json` |
| CLI-28 | argv `['clip.mp4', 'out', '--dry-run']`, samples `two` | the first four lines of that row, nothing written, `thumbnails` not called |
| CLI-28 | argv `['clip.mp4', 'out', '--threshold', '5']`, thumbnails `static(30)`; and the same with `--max-gap 2`, with `--block-k 0`, with `--sample-fps 4` | the legacy selector: `thumbnails` called, `change_grids` not called, and the result of the same argv with `--selector legacy` added |
| CLI-28 | argv `['clip.mp4', 'out', '--selector', 'legacy']`, thumbnails `static(30)` | the legacy result of the CLI-14 row (`30 thumbnails, selected 6/24 ...`); `change_grids` not called |
| CLI-28 | argv `['clip.mp4', 'out', '--selector', 'events', '--threshold', '5']` | exit 2 with the CLI-26 message, as before |
| CLI-28 | `seenby.py --help` | contains `(the default)` after the events description, `deprecated and to be removed`, `cap on kept frames (default: 24)`, and `legacy selector only: ` before each of the texts of `--threshold`, `--max-gap`, `--block-k`, `--sample-fps`; `--selector` comes before `--threshold` |
| CLI-26, CLI-28 | argv `['clip.mp4', 'out']`, probe `(2.0, 6, 6)` | return 1, stderr `clip.mp4: the frame (6x6) is smaller than 8x8 px; use --selector legacy`, `change_grids` not called |

### Errors (step 13)

None new.

## Step 14: frame number and time above every tile (drafted and implemented 2026-09-27)

Why. The tiles of a sheet carry no label, so an agent that cites a frame or runs its `recheck` counts tiles in order and matches them against `frames.json`, which is easy to get wrong by one on 24 tiles (feedback of 2026-09-27 on the checkbox recording, proposal 1). The label goes in a band above the tile, not over the picture, because a corner overlay can hide exactly what changed. It is drawn from a 5x7 bitmap font by seenby itself and stacked by ffmpeg, not by ffmpeg's `drawtext`: `drawtext` needs a build with libfreetype and a font that fontconfig can find, which minimal and some platform builds lack, and its pixels would depend on the installed font. Both selectors share the sheets, so both get the band.

### Public surface added (step 14)

    LABEL_H = 22
    def label_band(text, width)

### Rules (step 14)

LBL-1 `label_band(text, width)` returns the bytes of a binary PGM image: the header `b'P5\n<width> 22\n255\n'`, then 22 rows of `width` bytes, row 0 first. Every byte of rows 0 to 20 is 255 except the ink, and every byte of row 21 is 0 (a line that keeps the band apart from a light frame under it): the `i`-th character of `text` (from 0) with a glyph below draws each `1` of its glyph (row `r` from 0 at the top, column `c` from 0 at the left) as the four bytes at `x` in `4 + 12 * i + 2 * c` and one more, `y` in `4 + 2 * r` and one more, set to 0; bytes at `x >= width` are not drawn. A character without a glyph draws nothing and still takes its 12 px. On a tile narrower than the label (under 124 px for `#NN TT.TTs`, only for extreme aspect ratios) the end of the label is cut, which is accepted.

    0 01110 10001 10011 10101 11001 10001 01110      8 01110 10001 10001 01110 10001 10001 01110
    1 00100 01100 00100 00100 00100 00100 01110      9 01110 10001 10001 01111 00001 00010 01100
    2 01110 10001 00001 00010 00100 01000 11111      # 01010 01010 11111 01010 11111 01010 01010
    3 11111 00010 00100 00010 00001 10001 01110      . 00000 00000 00000 00000 00000 01100 01100
    4 00010 00110 01010 10010 11111 00010 00010      s 00000 00000 01110 10000 01110 00001 11110
    5 11111 10000 11110 00001 00001 10001 01110        (a space) all zeros
    6 00110 01000 10000 11110 10001 10001 01110
    7 11111 00001 00010 00100 01000 01000 01000

LBL-2 (amends FF-4) [hands-on] `contact_sheets(paths, out_dir, cols, rows)` keeps its signature and its sheets, with one change: above every frame of a sheet it stacks `label_band(label, width)`, where `width` is the width of the first frame in `paths` (read with ffprobe together with its pixel format, which the sheet keeps; all frames of a run have the tile width; ffprobe output without a width raises `ValueError('ffprobe could not read the frame width of <path>')`) and `label` is `'#'` followed by the frame's file name without its `frame-` prefix and `.jpg` suffix, its first `-` replaced by a space: `frame-07-12.25s.jpg` is labelled `#07 12.25s`, `frame-03-6.5s.jpg` `#03 6.5s`. The band and the frame together form one tile of the `tile` filter (margin and padding unchanged), band `i` over frame `i`: both inputs are numbered in order before they are stacked, because concat gives the band images broken timestamps and the stacking pairs frames by timestamp (the first implementation showed frame 2 under every band from the third on, found in review). `contact_sheets([], ...)` returns `[]`. The frames on disk and every `recheck` stay without a band.

LBL-3 (amends LAY-3) Without `rows`, `rows = max(1, (sheet_width - 2 * MARGIN + PADDING) // (tile_h + LABEL_H + PADDING))`, so that a sheet with its bands stays within `sheet_width`. With `rows` given it is used as is. LAY-5 and LAY-P1 hold with `tile_h + LABEL_H` in place of `tile_h`.

Rows of earlier steps change only where LBL-3 gives another row count. Among the layout rows, `layout(526, 514, 3)` gives `('window', 516, 3, 2, 1)`, `layout(2560, 1228, 8)` gives `('wide', 776, 2, 3, 2)` and `layout(500, 500, 6)` gives `('window', 500, 3, 2, 1)`; the other 18 keep their values. Among the `main()` rows, a 160x80 video (the step 12 and 13 default probe) now has 14 rows per sheet instead of 18 (`layout: wide, tile 160 px, 2x14 per sheet`, `sheet.rows` 14), an unrotated 80x160 one 8 instead of 9 (the rotated CLI-26 row is laid out as 160x80, 14 rows), a 500x500 one 2 instead of 3; every other probe size in the examples keeps its rows. Anything that follows from the row count (a frame's `sheet`, `sheets[].frames`, the number of sheets) follows the new count.

### Examples (step 14)

| ID | Input | Result |
|---|---|---|
| LBL-1 | `label_band('#1', 30)` | 673 bytes: the header `b'P5\n30 22\n255\n'` (13 bytes) and 660 pixel bytes, of which 150 are 0 (the 20 ones of `#` and the 10 of `1`, four bytes each, and the 30 of row 21) and 510 are 255; the pixel at `x` 6, `y` 4 (the first `1` of `#`) is 0, at `x` 4, `y` 4 is 255, at `x` 20, `y` 4 (the top of `1`, column 2) is 0 |
| LBL-1 | `label_band('88', 10)` | the header `b'P5\n10 22\n255\n'` and 220 pixel bytes; only columns 0 to 2 of the first `8` are drawn (`x` 4 to 9); its column 0 has four ones and columns 1 and 2 three each, so 40 bytes are 0 in rows 0 to 20, and the 10 of row 21 |
| LBL-1 | `label_band('', 8)`, `label_band('?!', 40)` | every byte of rows 0 to 20 is 255 (168 and 840 of them), every byte of row 21 is 0 |
| LBL-1 | `label_band('#07 12.25s', 256)` | 22 rows of 256 bytes; in rows 0 to 20 no byte at `x` 124 or beyond is 0 (ten characters end at `4 + 12 * 10 = 124`) and no byte in rows 0 to 3 or 18 to 20 is 0; row 21 is all 0 |
| LBL-3 | `layout(2120, 422, 24)` | `('wide', 776, 2, 8, 2)` (it was 9 rows) |
| LBL-3 | `layout(814, 872, 24)`, `layout(800, 600, 30, rows=5)` | `('window', 516, 3, 2, 4)` unchanged; `('window', 516, 3, 5, 2)` (`rows` given is used as is) |
| LBL-2 | [hands-on] a real run on a recording with frames `frame-01-0.00s.jpg` to `frame-24-31.50s.jpg` at tile 776 | every tile of each sheet shows a white band 22 px high above its frame, reading `#01 0.00s` to `#24 31.50s` in order, and the picture under band `#NN` is `frame-NN-*.jpg` (the maintainer's `tools/check_sheets.py` compares every tile with every frame file and names the closest; the regression runs it on every scenario); both sides of every sheet are at most 1568 px; the frame files on disk are unchanged |

### Errors (step 14)

`contact_sheets` raises `subprocess.CalledProcessError` when ffprobe or ffmpeg fails, reported by `main()` as before with the stage name `sheets`, and `ValueError` when ffprobe prints no width, reported as `<video>: <message>` with return 1 and no traceback.


## Step 15: a box around each change on the sheets (drafted and implemented 2026-09-27, amended after four reviews)

Why. On a 2120 px admin strip a 16 px checkbox is 6 px wide on the sheet, and the agent that read the checkbox recording asked for a frame around each change, on the sheets only, in a colour rare in interfaces, with pointer moves left out (feedback of 2026-09-27 on the checkbox recording, proposal 2; the owner asked for it too). seenby already knows where every change is (`events[].region`). On the 15 labeled recordings (332 tiles) a box for every event on the first tile that shows it gave up to 52 boxes on one tile: a page load outlines every product card and the outlines hide the text between them. Joining boxes closer than 6 px, dropping a box over half the tile and dropping all boxes of a tile with more than 12 leaves 376 boxes on 160 tiles, at most 12 on one; on the checkbox recording each toggled box is outlined on its own. After the reviews, which found boxes over areas that looked the same as on the tile before (BOX-3), 350 boxes on 149 tiles, at most 10 on one, and none over an area whose tile pixels differ by 12 levels or less from the tile before. The reading test of step 12 (125 questions, two fresh readers per variant, a blind judge) on the current sheets against the same sheets with the boxes of the first rule, before the review: 92.8% both, correct 221 against 219, partial 22 against 26, wrong 7 against 5, 15.2 against 15.1 images read per reader; no wrong answer was about something a box marked. So the boxes do not change what an agent answers on these questions, and they do not mislead it; they are kept for where the eye goes first, which the readers of this test did not need on short recordings. Pure pointer moves are not events and get no box. A pointer that moves in the same sample as a change is part of the events and is boxed, which the skill says: telling it from a small control by pixels is the open problem of step 12. The boxes are drawn by ffmpeg's `drawbox`, which needs no font and is in every build; the sheets came out alike on ffmpeg 4.4.1, 5.0.1, 6.1.1 and 9.0.2.

### Public surface added (step 15)

    BOX_T = 3        # px, the outline of a change box on a sheet
    BOX_GAP = 2      # px between a change and the inner edge of its box
    BOX_NEAR = 6     # px, boxes closer than this on both axes are joined
    BOX_SHARE = 0.5  # a joined box covering more of the tile than this is dropped
    BOX_MAX = 12     # a tile with more boxes than this gets none
    BOX_SPREAD = 24  # px changed past PIXEL_T in 2x2 cells since the frame before that make a change visible
    BOX_STRONG = 5   # px changed past twice PIXEL_T in 2x2 cells that do the same
    def change_boxes(regions, native_width, width, height)
    def contact_sheets(paths, out_dir, cols, rows, boxes=None)
    def kept_changes(path, indices, width, height, fps=EVENT_FPS, start=0.0, length=None)

### Rules (step 15)

BOX-1 `change_boxes(regions, native_width, width, height)` takes `regions`, a list of `[x, y, w, h]` in the pixels of a frame `native_width` wide, and returns the boxes to draw on a tile `width` x `height` px, a list of `(x, y, w, h)` tuples of ints, in five steps.
1. Each region becomes the rectangle `x0 = x * width // native_width - BOX_GAP - BOX_T`, `y0 = y * width // native_width - BOX_GAP - BOX_T`, `x1 = -(-(x + w) * width // native_width) + BOX_GAP + BOX_T`, `y1 = -(-(y + h) * width // native_width) + BOX_GAP + BOX_T` (the region scaled by `width / native_width` on both axes, outward to whole pixels, then padded; `x1` and `y1` are exclusive).
2. Two rectangles are near when `a.x0 - BOX_NEAR < b.x1`, `b.x0 - BOX_NEAR < a.x1`, `a.y0 - BOX_NEAR < b.y1` and `b.y0 - BOX_NEAR < a.y1`. While two rectangles are near, they are replaced by the smallest rectangle holding both. The result does not depend on the order of `regions` (a rectangle only grows, and a grown rectangle is near everything its parts were near).
3. The part of each rectangle on the tile is `max(0, x0)` to `min(width, x1)` by `max(0, y0)` to `min(height, y1)`.
4. A rectangle whose part on the tile covers more than `BOX_SHARE * width * height` px is dropped: the screen changed almost everywhere and a box would only frame the tile.
5. When more than `BOX_MAX` rectangles remain, the result is `[]` (a tile that changed in that many separate places is read as a whole). Otherwise the result is `(x0, y0, x1 - x0, y1 - y0)` for each, the rectangle of step 2, not cut to the tile, sorted by `(y, x)`. A box may start left of or above the tile and end right of or below it: ffmpeg draws only its part on the tile, so at the tile's edge the box stays open instead of drawing its outline over the change (review: a box cut to the tile drew its 3 px outline inside, over a change at the edge; on a phone tile a 40x24 px change in a corner disappeared under it).
`change_boxes([], ...)` is `[]`.

BOX-2 (amends LBL-2) [hands-on] `contact_sheets(paths, out_dir, cols, rows, boxes=None)`: `boxes` is `None` or a list with one entry per path, each a list of `(x, y, w, h)` in the pixels of that frame. For every frame of a sheet, in order, and every box of its entry, in order, the frame chain of the filter graph gets `,drawbox=x=<x>:y=<y>:w=<w>:h=<h>:color=0xff00ff:t=3:enable='eq(n,<i>)'` right after its `format=<fmt>`, where `<i>` is the frame's place on this sheet from 0: `[0:v]setpts=N,format=yuvj420p,drawbox=x=11:y=11:w=34:h=34:color=0xff00ff:t=3:enable='eq(n,1)'[f];[1:v]...`. The outline is `BOX_T` px wide inside the box, so it lies `BOX_GAP` px outside the region, and the region itself is never drawn over; `x` and `y` may be negative and the box may pass the frame's edge, where `drawbox` draws nothing. When the drawbox part of a sheet's graph is longer than 30000 characters, that sheet gets no boxes: the command line of Windows holds 32767 characters, and no one option reads a graph from a file on every supported ffmpeg (`-filter_complex_script` is gone in 9.0, `-/filter_complex` came in 7.1). With the defaults a sheet stays under about 20000 characters; only options that put far more tiles on one sheet (`--tile-width 200 --max-frames 60`) reach the limit (review). With `boxes` `None`, or every entry empty, the graph and the sheets are exactly those of step 14. The band, the frames on disk and every `recheck` carry no box.

BOX-3 (events selector only; amends CLI-26) With at least two frames, after `save_samples` and under the stage name `sheets`, `main()` calls `kept_changes(video, ks, width, height, EVENT_FPS, start, length)` with the kept sample indices and the arguments `change_grids` got, and gives every event of `select_events` at most one frame: the first kept sample `k` with `e.start <= k <= e.until` (the event's own `start` and `until`) and `k > 0`, in order, at which the event's area changed visibly since the kept frame before (the first frame that shows the change; the frames from `e.start` on show it as it happens, the frames from `settled` on as it ends, so an event with `shown` false can still get a box on a frame that shows it happening). With `(over, far)` the entry of `kept_changes` for that frame and the cells of the event's box (columns `x // CELL` to `(x + w) // CELL - 1`, rows `y // CELL` to `(y + h) // CELL - 1`, `gw` from `change_grids`), the change is visible when some block of cells, `(c, r)` to `(c + 1, r + 1)` cut to the box, for any cell `(c, r)` of the box, has a sum of `over` times `CELL * CELL / 255` of at least `BOX_SPREAD`, or of `far` of at least `BOX_STRONG`: a change dense somewhere, as a digit, a checkbox or a pale area is, and not a few faint pixels spread over a large area, as codec noise is. An event without such a frame has no box: its area changed and changed back between two kept frames (the pointer passing over a checkbox), or its change is codec noise on text.
       Why at native resolution and these two counts. The first review found 15 of 157 boxes on three real recordings over areas that looked the same as on the tile before. Comparing the cell means of the analysis dropped the boxes of digits swapped for ones with as much ink (6 for 9: 20% of digit changes in clean renders, second review); comparing the tiles' own pixels at `PIXEL_T` dropped grey 13 px digits on 2560 and 3840 px screens, where the tile is a third of the frame or less, and boxed codec noise at a scale of 0.6 with a keyframe every 2 s (final review). At native resolution the two separate: on the reviewers' synthetic recordings codec noise on static text changes 12 to 39 pixels past `PIXEL_T` and at most 3 past twice it (largest change 65 levels), while every real change of a digit, a label or a checkbox changes at least 9 pixels past twice `PIXEL_T` (largest change 121 levels or more); pale changes over an area, a row highlight or a scroll bar, change hundreds of pixels past `PIXEL_T`. The rule keeps 45 of 45 real changes and 0 of 51 noise changes there, and on the 15 recordings of step 12 it leaves 837 of 1044 first shown events boxed; of the 207 without a box, 27 are identical on both frames and 116 differ nowhere by more than `PIXEL_T`. It costs one more pass over the recording: 4 s on 20 minutes of 720p (25.8 s against 21.7 s).
       A fourth review found three faults in that first version of the counts, which summed over the whole region and took only the kept frame at or after `settled`. A keyframe or the encoder's refinement often changes an area for one more quarter second, so `settled` moved past a kept frame that already showed the change, and the box was lost (a tooltip hidden at 1.75 s, a digit on a 2880 px grid) or went one tile late onto an unchanged tile (a 320x420 px menu). Summed over a region of a few hundred cells, codec drift on unchanged text passed 64 px (a menu opened and closed between two kept frames, boxed around 200x270 px of the same text), and at crf 28 on 1600 px and wider small noise passed 4 px past twice `PIXEL_T`. Counting in blocks of 2x2 cells and taking the first kept frame from `start` on fixes all three on the reviewers' 186 synthetic recordings: of 1885 real changes (digits, labels, checkboxes) 1867 are boxed (1862 before), of 2062 noise events 52 (159 before, all 52 at crf 36 and 40, none at crf 24 to 32), of 244 changed-back areas 6 (32 before, all at crf 36). On the 15 recordings 844 of 1052 events are boxed (837 before); 137 boxes moved to an earlier tile, 107 of them by one or two samples, onto the tile where the change first shows.
       The regions `[x, y, w, h]` of the events given to a frame, in `events` order, become its boxes `change_boxes(regions, width, tile_width, (tile_width * height + width // 2) // width)`, where `width` and `height` are the analysed size (after `display_size`) and `tile_width` is that of the layout line; the height is rounded half up, as ffmpeg's `scale=<tile_width>:-1` rounds it. The sheets are written by `contact_sheets(paths, out_dir, cols, rows, boxes)` with one entry per frame, an empty list for a frame without boxes. With one frame neither `kept_changes` nor `contact_sheets` is called. The legacy selector keeps calling `contact_sheets(paths, out_dir, cols, rows)` and never calls `kept_changes`. Console and `frames.json` do not change.

BOX-4 removed, superseded by BOX-5 (`frame_grey` is gone).

BOX-5 [hands-on] `kept_changes(path, indices, width, height, fps, start, length)` runs one ffmpeg pass over the chain of `change_grids` (the same `-ss`, `-t`, sampling, luma and crop to whole cells), keeps the samples `indices` with the `select` of `save_samples`, takes the difference of each kept sample with the kept one before (`tblend`), marks the pixels past `PIXEL_T` and, separately, past `2 * PIXEL_T`, and pools both to cells like `change_grids`. It returns a list with one entry per index: `None` for the first, then `(over, far)`, two grids of `gw * gh` bytes, the share (0 to 255) of the cell's pixels changed past `PIXEL_T` and past `2 * PIXEL_T` since the kept sample before. It raises `subprocess.CalledProcessError` when ffmpeg fails, which `main()` reports with the stage name `sheets`.

The fake `contact_sheets` of the `main()` rows takes `boxes` as a fifth argument, default `None`, and records it. Every `main()` row of earlier steps keeps its result.

### Examples (step 15)

`two`, `S`, `box`, `grid`, the fakes and the default probe `(2.0, 160, 80)` as in the step 12 examples. `two` gives frames at samples 0, 4 and 6 and three events with the boxes `A = (16, 16, 24, 24)`, cells 2 to 4 by 2 to 4 (settled 1, first shown at 4), `B = (96, 16, 24, 24)`, cells 12 to 14 by 2 to 4 (settled 3, first shown at 4), and `A` again (settled 5, first shown at 6). The main rows fake `kept_changes`: it returns the entries the row names, one per kept frame, and where a row names none, `None` for the first frame and `(grid({}), grid({}))` for every other. `Z = grid({})`, `CA = grid(box(2, 2, 3, 3))`, `CB = grid(box(12, 2, 3, 3))`, `CAB = grid(box(2, 2, 3, 3) | box(12, 2, 3, 3))`. `dbl` as in the PCK-4 rows gives frames at samples 0, 1 (`state`) and 4 and one event with the box `A`, `start` 1, `settled` 2, `until` 4.

| ID | Input | Result |
|---|---|---|
| BOX-1 | `change_boxes([], 160, 160, 80)` | `[]` |
| BOX-1 | `change_boxes([[16, 16, 24, 24], [96, 16, 24, 24]], 160, 160, 80)` and the same with the two regions swapped | `[(11, 11, 34, 34), (91, 11, 34, 34)]` both times |
| BOX-1 | `change_boxes([[1384, 88, 16, 16]], 2120, 776, 154)` (a checkbox on a 2120 px strip) | `[(501, 27, 17, 17)]` (`1384 * 776 // 2120` is 506, `-(-1400 * 776 // 2120)` is 513) |
| BOX-1 | `change_boxes([[1384, 88, 16, 16], [1480, 88, 56, 16]], 2120, 776, 154)` | `[(501, 27, 17, 17), (536, 27, 32, 17)]` (18 px apart) |
| BOX-1 | `change_boxes([[16, 16, 24, 24], [55, 16, 24, 24]], 160, 160, 80)`, `change_boxes([[16, 16, 24, 24], [56, 16, 24, 24]], 160, 160, 80)` | `[(11, 11, 73, 34)]` (5 px apart, joined); `[(11, 11, 34, 34), (51, 11, 34, 34)]` (6 px apart, not joined) |
| BOX-1 | `change_boxes([[72, 24, 8, 8], [40, 40, 8, 8], [56, 56, 8, 8]], 160, 160, 80)`, and `change_boxes([[72, 24, 8, 8], [40, 40, 8, 8]], 160, 160, 80)` | `[(35, 19, 50, 50)]` (the second and third overlap; the first is near only the rectangle holding both); `[(67, 19, 18, 18), (35, 35, 18, 18)]` |
| BOX-1 | `change_boxes([[0, 0, 24, 24]], 160, 160, 80)` | `[(-5, -5, 34, 34)]` (not cut: the outline's left and top lines fall outside the tile) |
| BOX-1 | `change_boxes([[0, 0, 160, 80]], 160, 160, 80)` | `[]` (the whole tile) |
| BOX-1 | `change_boxes([[5, 5, 40, 90]], 100, 100, 100)`, `change_boxes([[5, 5, 41, 90]], 100, 100, 100)` | `[(0, 0, 50, 100)]` (exactly half the tile is kept); `[]` |
| BOX-1 | `change_boxes([[0, 0, 45, 90]], 100, 100, 100)`, `change_boxes([[0, 0, 46, 95]], 100, 100, 100)` | `[(-5, -5, 55, 100)]` (on the tile 50 by 95, 4750 px); `[]` (on the tile 51 by 100, 5100 px) |
| BOX-1 | `change_boxes([[24 * i, 0, 8, 8] for i in range(12)], 400, 400, 100)`, and the same with `range(13)` | twelve boxes, the first two `(-5, -5, 18, 18)` and `(19, -5, 18, 18)`; `[]` (thirteen) |
| BOX-3 | argv `['clip.mp4', 'out']`, samples `two`, entries `None`, `(CAB, Z)`, `(CA, Z)` | `kept_changes` called once with `('clip.mp4', [0, 4, 6], 160, 80, 4, 0.0, None)`; `contact_sheets` called once with `boxes` `[[], [(11, 11, 34, 34), (91, 11, 34, 34)], [(11, 11, 34, 34)]]`; stdout and `frames.json` as in the CLI-28 row |
| BOX-3 | argv `['clip.mp4', 'out']`, samples `two`, no entries named (all zero) | `boxes` `[[], [], []]` |
| BOX-3 | argv `['clip.mp4', 'out', '--max-frames', '2']`, samples `two`, entries `None`, `(CB, Z)` | `kept_changes` called with `('clip.mp4', [0, 6], 160, 80, 4, 0.0, None)`; `boxes` `[[], [(91, 11, 34, 34)]]` (the event settled at 1 is not shown; of the two first shown at 6, only B changed since 0) |
| BOX-3 | argv `['clip.mp4', 'out', '--from', '1']`, probe `(3.0, 160, 80)`, samples `two`, the entries of the first row | `kept_changes` called with `('clip.mp4', [0, 4, 6], 160, 80, 4, 1.0, 2.0)`; `boxes` as in the first row |
| BOX-3 | argv `['clip.mp4', 'out']`, probe `(2.0, 1600, 80)`, samples `two` (the fake grids stay 20x10, so the boxes are the same pixels), the entries of the first row (tester round 14) | `boxes` `[[], [(2, 2, 23, 23), (41, 2, 23, 23)], [(2, 2, 23, 23)]]`: the regions scaled by 776/1600 onto a tile 776 px wide and `(776 * 80 + 800) // 1600` = 39 px high; the layout line `  layout: wide, tile 776 px, 2x24 per sheet` |
| BOX-3 | argv `['clip.mp4', 'out']`, samples `two`, entries `None`, `(grid({(2, 2): v}), Z)`, `(Z, Z)` for `v` 96 and 95 | `[[], [(11, 11, 34, 34)], []]` (24.09 px past `PIXEL_T` in one block); `[[], [], []]` (23.84 px) |
| BOX-3 | argv `['clip.mp4', 'out']`, samples `two`, entries `None`, `(Z, grid({(4, 4): v}))`, `(Z, Z)` for `v` 20 and 19 | `[[], [(11, 11, 34, 34)], []]` (5.02 px past twice `PIXEL_T`, the block of the box's last cell is that cell alone); `[[], [], []]` (4.77 px) |
| BOX-3 | argv `['clip.mp4', 'out']`, samples `two`, entries `None`, `(grid({(2, 2): 48, (3, 3): 48}), Z)`, `(Z, Z)`, and the same with `{(2, 2): 48, (4, 2): 48}` | `[[], [(11, 11, 34, 34)], []]` (24.09 px in the block of cell (2, 2)); `[[], [], []]` (12.05 px in any one block, though 24.09 px over the box) |
| BOX-3 | argv `['clip.mp4', 'out']`, samples `dbl`, entries `None`, `(CA, Z)`, `(Z, Z)`, and entries `None`, `(Z, Z)`, `(CA, Z)` | `[[], [(11, 11, 34, 34)], []]` (the `state` frame at 1 shows the change before it settles at 2); `[[], [], [(11, 11, 34, 34)]]` (nothing visible at 1, so the last frame) |
| BOX-3 | argv `['clip.mp4', 'out']`, samples `two`, entries `None`, `(grid({(5, 2): 255, (1, 4): 255, (3, 5): 255}), Z)`, `(Z, Z)` | `[[], [], []]` (the cells right of, left of and under A are not A's) |
| BOX-3 | argv `['clip.mp4', 'out']`, samples `[S({})]` | `kept_changes` and `contact_sheets` not called |
| BOX-3 | argv `['clip.mp4', 'out', '--selector', 'legacy']`, thumbnails `static(30)` | `contact_sheets` called with four arguments, its recorded `boxes` `None`; `kept_changes` not called |
| BOX-2 | [hands-on] a real run on the checkbox recording (2120x422, tile 776) | every tile shows its frame with a magenta outline 3 px wide around each changed checkbox and nothing else changed (the maintainer's `tools/check_sheets.py` derives the boxes from `frames.json` and `kept_changes`, finds all three lines of every outline on the sheet and compares the rest of the tile with the frame file); the frame files on disk and the bands are unchanged |

### Properties (step 15)

BOX-P1 For `native_width` 1552, `width` 776, `height` 400 and `regions` a list of 0 to 6 regions `[x, y, w, h]` with `w`, `h` integers in `[8, 80]`, `x` in `[0, 1552 - w]` and `y` in `[0, 800 - h]`: the result of `change_boxes` is the same for every order of `regions`; every box has `w > 0`, `h > 0` and a part on the tile (`x < 776`, `y < 400`, `x + w > 0`, `y + h > 0`); no two boxes are near (BOX-1 step 2); the boxes are sorted by `(y, x)`; and every region's rectangle after step 1 lies inside one of the boxes (with these sizes no joined rectangle can pass `BOX_SHARE` and there are never more than 6 boxes).

### Errors (step 15)

None new. `change_boxes` with `native_width` 0 or negative sizes is undefined; do not test.


## Step 16: crops of every change at native size (code published 2026-09-28, drafted 2026-09-29, amended 2026-10-04 after the first feedback)

Why. A sheet shows a change at tile scale: on a 2120 px strip a 16 px checkbox is 6 px wide, and a digit on a wide screen is a few pixels of grey. The native frame of `recheck` is exact but costs a whole screen per question. The crops give the agent every change the events selector found, at native size, before and after, next to each other, and a full frame of each screen they belong to, so a question about one control is answered from a picture a few dozen pixels across. seenby does not guess the structure of the page (a row, a column, a card): an agent or a person reads that from the picture, pixels alone cannot. It only decides two things. Changes that settle in the same sample close to each other share a crop, and a moment that redraws much of the frame, or crops that together cover much of it, start a new screen that gets a full frame of its own instead of crops. Measured on a prototype over the 15 labeled recordings before the port: joining every change within 128 px fused whole page redraws into crops of 32 to 39% of the screen (8.3k tokens on one recording); the halo rule for new screens and the cap of `CROP_SHARE` on a joined crop left 12 crops and about 4k tokens there. A crop whose before and after looked the same showed nothing; showing the first sample in between that differs recovered a change that had come and gone between two kept frames, one the frames missed in a comparison with other tools. The crops add pictures and change none of the sheets' frames or the console lines of earlier steps; `frames.json` gains keys only when crops were written (CRP-8). [unverified] Whether they change the answers of the reading test of step 12 has not been measured yet.

The first real run by an agent (feedback of 2026-10-04, a 12.7 s recording 2560 px wide) found nothing missing in the recording and three gaps on the reading side, closed in this step before its tests were written. The agent did not open the crops, the best part of the output for that recording, because nothing it was told to read pointed at them: `frames.json` now names the crop of each event and the screen files (CRP-8), and the console names the files (CRP-6). It read a counter off a tile as 34 for 36 while the full frame of that screen lay next to the sheets. And a crop skipped the very frame its box was drawn on, a tooltip that was gone again in the picture after: that frame is now the crop's middle picture (CRP-5 step 3).

This step describes code that exists: CRP-1 to CRP-7 and CRP-P1 are anchored (tests expected green), except the screen key of CRP-1 step 2 when a new screen falls on the sample right after a screen made by accumulation, which is a fix, and the amendments of 2026-10-04 (the `points` argument, the console lines of CRP-6 and CRP-8), which are implemented together with the tests of this step.

### Vocabulary (step 16)

- A moment is the events of `select_events` with one `settled` value.
- `E(x, y, w, h, start, settled)` in the examples is the dict `{'x': x, 'y': y, 'w': w, 'h': h, 'start': start, 'settled': settled}`; `crop_units` reads no other key of an event.
- The cells of a list of rectangles `[x, y, w, h]` are the `CELL` px cells `(cx, cy)` with `x // CELL <= cx <= (x + w - 1) // CELL` and `y // CELL <= cy <= (y + h - 1) // CELL` for some rectangle, each counted once.
- `F = 1600 * 800`: the examples of `crop_units` use a 1600x800 frame and 40 samples unless a row says otherwise, so `SCREEN_SHARE * F` is 320000 px (5000 cells) and `CROP_SHARE * F` 128000 px.

### Public surface added (step 16)

    CROP_MARGIN = 16     # px of the screen kept around a change in its crop
    CROP_JOIN = 128      # px, changes settling in the same sample closer than this share one crop
    CROP_SHARE = 0.1     # while that crop stays within this share of the frame
    SCREEN_SHARE = 0.25  # changes covering this share of the frame start a screen with a full frame of its own
    def mark_image(width, height, marks)
    def contact_sheets(paths, out_dir, cols, rows, boxes=None, marks=None)
    def crop_units(events, width, height, samples)
    def write_crops(path, out_dir, screens, crops, tiles, points, width, height, fps=EVENT_FPS, start=0.0, length=None)   [hands-on]

### Rules (step 16)

CRP-1 `crop_units(events, width, height, samples)` takes the events of `select_events`, the analysed frame size and the number of samples, and returns `(screens, crops)`, in six steps. `d` is `CROP_JOIN // 2` (64).
1. The first screen has `start` 0 and `key` 0 (`key` is the sample its full frame is taken from). The moments are taken in increasing `settled` value `k`, the events of a moment in `events` order. The accumulated cells start empty.
2. The halo of an event is its rectangle grown by `d` on every side and cut to the frame: `[x0, y0, x1 - x0, y1 - y0]` with `x0 = max(0, x - d)`, `x1 = min(width, x + w + d)`, likewise `y0` and `y1` with `height`. When the cells of the halos of a moment times `CELL * CELL` exceed `SCREEN_SHARE * width * height`, the moment is a new screen: when the last screen's `start` is not `k`, a screen with `start` `k` and `key` `k` is added; when it is `k`, that screen's `key` becomes `k` (fix: the code keeps the key it had, a sample before the new screen). The accumulated cells are emptied and the moment gets no crops.
3. Otherwise each event of the moment becomes a unit with `rect` `[x, y, w, h]` and `events` `[i]`, its index in `events`. Two units are near when `a.x - d < b.x + b.w + d`, `b.x - d < a.x + a.w + d`, `a.y - d < b.y + b.h + d` and `b.y - d < a.y + a.h + d` (their gap is under `CROP_JOIN` on both axes). Repeatedly, the first pair `(i, j)`, `i < j`, in list order (by `i`, then `j`) that is near and whose smallest rectangle holding both has an area of at most `CROP_SHARE * width * height` is joined: unit `i` gets that rectangle and the `events` of `i` followed by those of `j`, and unit `j` is removed; this stops when no pair joins. The result depends on the order of the events of a moment (a join can block a later one), which is why the order is fixed.
4. The units of the moment, sorted by `(rect y, rect x)`, are added to the crops of the last screen, and the cells of their rectangles (without halo) are added to the accumulated cells. When the accumulated cells times `CELL * CELL` exceed `SCREEN_SHARE * width * height`, a screen with `start` `k + 1` and `key` `k` is added and the accumulated cells are emptied.
5. A screen ends at the `start` of the next screen, the last at `samples`. A screen without crops that lasts fewer than `EVENT_FPS` samples (under a second) is dropped: a transition, such as one step of a scroll (amended by CRP-10, step 17: the last screen is kept however short, unless it has no sample). The screens left are numbered `n` from 1 in order.
6. Each unit gets `crop`, its rectangle grown by `CROP_MARGIN` on every side and cut to the frame (`[x0, y0, x1 - x0, y1 - y0]` as in step 2), `start`, the smallest `start` of its events, `settled`, `k`, and `screen`, the `n` of its screen.
`screens` is a list of dicts with exactly the keys `start`, `key`, `crops` (its units, in order) and `n`; `crops` is the list of the units of all screens left, in screen order, each a dict with exactly the keys `rect`, `events`, `crop`, `start`, `settled`, `screen`; the dicts in a screen's `crops` are the same objects as in `crops`. With `events` `[]` the result is one screen `{'start': 0, 'key': 0, 'crops': [], 'n': 1}` and no crops when `samples >= 1`, and `([], [])` for `samples` 0 (amended by CRP-10, step 17; it was `samples >= EVENT_FPS`).
       Why a halo and not the changed area alone. A page load changes text lines with white between them; their own pixels cover a small share of the screen, while the screen is new. With 64 px around each change the lines of a redraw merge into most of the frame, and a single control with its 64 px stays far below a quarter of a 720p frame.

CRP-2 `mark_image(width, height, marks)` returns the bytes of a PAM image: the header `b'P7\nWIDTH <width>\nHEIGHT <height>\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n'`, then `width * height` pixels of four bytes (red, green, blue, alpha), row 0 first. Every pixel is `(0, 0, 0, 0)` except these, drawn for each mark `(x0, y0, text)` in order: first every pixel with `x0 <= x < x0 + 12 * len(text) + 2` and `y0 <= y < y0 + 18` becomes `(255, 255, 255, 255)`, then each `1` of the glyph of the `i`-th character of `text` (the glyphs of LBL-1 and CRP-3; row `r`, column `c` from 0) sets the four pixels at `x` in `x0 + 2 + 12 * i + 2 * c` and one more, `y` in `y0 + 2 + 2 * r` and one more, to `(255, 0, 255, 255)`. Pixels outside the image are not drawn; `x0` and `y0` may be negative. A character without a glyph draws no ink and still takes its 12 px. A later mark paints over an earlier one where they overlap.
       Why. The numbers are drawn by seenby into a transparent layer that ffmpeg lays over the sheet: `drawtext` needs a font (step 14), and a `drawbox` per pixel of a digit is too long for the command line of Windows.

CRP-3 (amends LBL-1) The glyph table of LBL-1 gains `>`: `10000 01000 00100 00010 00100 01000 10000`. `label_band` and `mark_image` draw it like every other glyph.

CRP-4 (amends BOX-2; amended by CRP-16, step 17: one ffprobe call reads width, height and pixel format, the overlay keeps the chroma of the sheet, and a sheet whose boxes BOX-2 drops gets no marks) [hands-on] `contact_sheets(paths, out_dir, cols, rows, boxes=None, marks=None)`: `marks` is `None` or a list with one entry per path, each a list of `(x, y, text)` in the pixels of that frame. When some entry is not empty, `contact_sheets` also reads the height `h` of the first frame with ffprobe (`-show_entries stream=height`), and for every sheet with at least one mark writes `mark_image(W, H, sheet_marks)` into its temporary folder as `marks.pam`, with `W = 2 * MARGIN + c * (width + PADDING)`, `H = 2 * MARGIN + ceil(len(batch) / c) * (h + LABEL_H + PADDING)`, `c` the columns of that sheet (`min(cols, len(batch))`), and each mark `(x, y, text)` of the frame at place `i` on the sheet (from 0) moved to `(MARGIN + (i % c) * (width + PADDING) + x, MARGIN + (i // c) * (h + LABEL_H + PADDING) + LABEL_H + y, text)`. The layer is a third input (`-i <folder>/marks.pam` after the two concat lists) and the graph of step 15 gets `[t];[t][2:v]overlay=0:0,format=<fmt>` appended. A sheet without marks, and every sheet when `marks` is `None` or every entry is empty, is exactly that of step 15. Evidence: a real run where crops were written shows each crop's number in magenta on white next to the box of its change, on the tile named in `crops.json`, and nowhere else.

CRP-5 [hands-on] `write_crops(path, out_dir, screens, crops, tiles, points, width, height, fps, start, length)` takes the result of `crop_units`, `tiles`, a dict from the index of an event to the kept frame (from 0) whose box it got (CRP-6), `points`, the sample index of every kept frame, the analysed size and the arguments of `change_grids`, and writes the crops.
1. Each crop gets `before`, `start - 1` (`None` when `start` is 0), `after`, its `settled`, and `tile`, the smallest `tiles[i]` over its `events` that are in `tiles` (`None` when none is).
2. One ffmpeg process decodes the samples as `change_grids` takes them (`-ss <start>`, `-t <length>` when `length` is not `None`, `fps=<fps>:round=up:start_time=0`), scaled to `width` x `height` as `rgb24`, and reads them from 0 up to the last one needed. It keeps the area `crop` of each crop in its samples `before` and `start` to `settled`, and writes the sample `key` of each screen as `screen-<n:02d>-<t:.2f>s.jpg` (`t = start + key / fps`) in `out_dir`. When no sample is decoded it returns `None`.
3. (Amended by CRP-9 and CRP-15, step 17: the comparison is `looks_same`, and of the samples in between at most two are candidates, the first that differs from `before` and the first past it that differs from both.) A crop whose `after` sample was not decoded is dropped. Two pictures of a crop look the same when no block of 16x16 px of the crop, counted from its top left corner, has `BOX_SPREAD` or more pixels whose luma `(77 R + 150 G + 29 B) / 256` differs by more than `PIXEL_T`. A sample can be the crop's `passing` picture when its picture looks the same as neither `before` (when there is one) nor `after`. The candidates, in order: the sample of the crop's tile, `points[tile]`, when it lies from `start` to `settled - 1` (the frame the box is drawn on shows the change on its way, such as a tooltip that is gone again in `after`; without it the crop of a box would skip the one frame the box is on); then, only when `before` is not `None` and looks the same as `after`, the samples from `start` to `settled - 1` in order. The first candidate that can be is `passing`. A crop whose `before` and `after` look the same and that has no `passing` is left out. The crops kept are numbered `n` from 1 in the order of `crops`.
4. (Amended by CRP-15, step 17: the label is black on white as LBL-1 draws it, which is what the code always did; a block wider than `SHEET_WIDTH` is a page of its own; the pages after the first are `crops-<n:02d>-02.png`, `-03.png` and on.) For each screen, its kept crops become blocks: a label band (LBL-1, drawn in grey on white) reading `<n:02d> <times>`, the times of `before`, `passing` and `after` that exist as `%.2f` of `start + k / fps` joined by `>`, followed by ` #<tile + 1:02d>` when `tile` is not `None`; under it the pictures in that order, each in a 1 px grey frame, side by side with a 24 px gap holding an arrow, or one under another with a 6 px gap when side by side is wider than `SHEET_WIDTH`. The blocks are packed in order into rows at most `SHEET_WIDTH` px wide with 12 px between blocks and rows, and the rows into pages whose height times `SHEET_WIDTH` stays within 1150000 px; the pages are written as `crops-<n:02d>.png`, `crops-<n:02d>b.png`, `crops-<n:02d>c.png` and on.
5. `crops.json` in `out_dir`: `{"screens": [...], "crops": [...], "left_out": [...]}`. A screen is `{"n", "from": start + start_sample / fps, "full_frame": its file or null, "crops": its page files}`; a crop is `{"n", "screen", "tile": tile + 1 or null, "file": its page, "before", "passing", "after": times or null, "region": rect, "crop": crop, "recrop_before", "recrop_after"}`, where a recrop is the command `ffmpeg -ss <start:.3f> [-t <length:.3f>] -i <path> -vf fps=<fps>:round=up:start_time=0,select=eq(n\,<k>),crop=<w>:<h>:<x>:<y> <passthrough> passthrough -frames:v 1 <out_dir>/crop-<n:02d>-before.png` (or `-after.png`), `null` when `before` is `None`; a crop left out is `{"before", "after", "region"}`.
6. It returns `{'crops': the kept crops, 'images': every page file name in order, 'screens': the screens whose full frame was written, 'left': the number left out}`; each kept crop has at least the keys `n`, `tile`, `rect`, `screen`, `events` and `file` (its page), each of those screens at least `n`, `start` and `file`. It raises `subprocess.CalledProcessError` when writing an image fails and `OSError` when ffmpeg cannot start.
Evidence: a real run on the checkbox recording, on a recording where a value changes and changes back within a second, and on the recording of the feedback of 2026-10-04; every toggled checkbox is a crop at native size, before and after; the value shows its passing state; the crop of the box on the tile at 7.75 s of the feedback recording reads `7.50>7.75>8.00` and its middle picture shows the tooltip; each recrop command writes the picture of its crop.

CRP-6 (events selector only; amends BOX-3; amended by CRP-13, step 17: any exception of the crops is survived, and the marks are one per box, from `box_marks`, not one per crop from its `rect` and `tile`) With at least two frames, after the boxes of BOX-3 are computed, `main()` calls `crop_units(events, width, height, len(samples))` and `write_crops(video, out_dir, screens, crops, tiles, points, width, height, EVENT_FPS, start, length)`, where `tiles` maps the index (in `events`) of every event that got a box to the index (from 0) of the kept frame it got it on, `points` is the list of kept sample indices `kept_changes` got, and `width`, `height`, `start` and `length` are those `kept_changes` got. When `write_crops` raises `subprocess.CalledProcessError` or `OSError`, `main()` prints `  crops not written: <the exception>` to stderr and goes on as if it had returned `None`. Each crop of the result with `tile` not `None`, in order, puts a mark on that frame: with `(x, y, w, h)` its `rect`, `text = '%02d' % n`, `pad = BOX_GAP + BOX_T`, `x0 = x * tile_width // width - pad`, `y0 = y * tile_width // width - pad`, `y1 = -(-(y + h) * tile_width // width) + pad` and `tile_height` as in BOX-3, the mark is `(max(0, min(tile_width - 12 * len(text) - 2, x0)), y0 - 18 if y0 >= 18 else min(tile_height - 18, y1), text)`: above the box when there is room, else under it. When some frame has a mark, the sheets are written by `contact_sheets(paths, out_dir, cols, rows, boxes, marks)` with one list per frame; otherwise by `contact_sheets(paths, out_dir, cols, rows, boxes)` as in step 15. When `write_crops` returned a result, stdout gets two more lines after the manifest line: `  crops, every change at native size before > after, numbered as on the sheets: <P>` and `  screens, a full native frame of each screen as it starts, for reading text and digits: <F>; all listed in <out_dir>/crops.json`, where `P` is its `images` and `F` the `file` of each of its `screens`, each joined to `out_dir` with `os.path.join` and separated by `, `, or `none` when there are none. The files are named, not counted and not given as a pattern, so that an agent can open them from the line alone. With one frame, with `--dry-run` and with the legacy selector neither `crop_units` nor `write_crops` is called.

CRP-7 (amends CLN-4) `clean(out_dir)` also removes every entry directly in `out_dir` whose name starts with `screen-` and ends with `.jpg`, or starts with `crops-` and ends with `.png`, and the file `crops.json`. Everything else stays as in CLN-4.

CRP-8 (events selector only; amends MAN-17) When `write_crops` returned a result, `frames.json` gets two additions and is otherwise that of MAN-17. A top-level key `crops` after `events`: `{"file": "crops.json", "images": <the result's images>, "screens": [{"n": n, "from": start + s / EVENT_FPS, "file": file}, ...]}`, one entry per screen of the result in order, `s` its `start` sample; the names are file names in the folder of `frames.json`, as a frame's `file` is. And every entry of `events` gets a key `crop` after `shown`: `{"n": n, "file": file}` of the kept crop whose `events` holds the entry's index, or `null` when no crop holds it (its moment started a screen, or its crop was left out). When `write_crops` returned `None`, raised, or was not called, `frames.json` has neither key and is exactly that of step 15. `VERSION` stays 1: the keys are additions.
       Why. An agent goes from a tile to `frames.json`; before this rule nothing there led on to the crop of a change or to the full frames, and the agent of the first feedback stopped at the sheets.

The fakes of the `main()` rows: `write_crops` records its arguments and returns `None` unless the row names a result (or raises it when it is an exception); `contact_sheets` takes `marks` as a sixth argument, default `None`, and records it. Every `main()` row of earlier steps keeps its result: a real `write_crops` would start ffmpeg, which the test machine need not have (the first run of the published code failed the LBL-2 events row on a machine without ffmpeg, with the extra stderr line `  crops not written: [Errno 2] No such file or directory: 'ffmpeg'`).

### Examples (step 16)

`two`, `S`, `box`, `grid`, `Z`, `CA`, `CAB` and the fakes as in the step 15 examples; the main rows use the probe `(2.0, 1600, 80)` unless they say otherwise (the fake grids stay 20x10, so the events are those of `two` in pixels, on a tile 776 px wide and 39 px high; the kept samples are `[0, 4, 6]`). Results of the fake `write_crops`: `R` is `{'crops': [{'n': 1, 'tile': 1, 'rect': [16, 16, 24, 24], 'events': [0], 'file': 'crops-01.png'}, {'n': 2, 'tile': 1, 'rect': [96, 16, 24, 24], 'events': [1], 'file': 'crops-01.png'}, {'n': 3, 'tile': 2, 'rect': [16, 16, 24, 24], 'events': [2], 'file': 'crops-01.png'}], 'images': ['crops-01.png'], 'screens': [{'n': 1, 'start': 0, 'file': 'screen-01-0.00s.jpg'}], 'left': 0}`; `R2` is `{'crops': [{'n': 1, 'tile': 1, 'rect': [96, 48, 24, 24], 'events': [0], 'file': 'crops-01.png'}, {'n': 2, 'tile': 1, 'rect': [1590, 48, 8, 8], 'events': [1], 'file': 'crops-01b.png'}, {'n': 3, 'tile': 2, 'rect': [16, 0, 24, 8], 'events': [2], 'file': 'crops-02.png'}], 'images': ['crops-01.png', 'crops-01b.png', 'crops-02.png'], 'screens': [{'n': 1, 'start': 0, 'file': 'screen-01-0.00s.jpg'}, {'n': 2, 'start': 5, 'file': 'screen-02-1.00s.jpg'}], 'left': 1}`; `R3` is `{'crops': [{'n': 1, 'tile': None, 'rect': [16, 16, 104, 24], 'events': [0, 1], 'file': 'crops-01.png'}], 'images': ['crops-01.png'], 'screens': [{'n': 1, 'start': 0, 'file': 'screen-01-0.00s.jpg'}], 'left': 1}`; `R4` is `{'crops': [], 'images': [], 'screens': [], 'left': 3}`. `LC(P)` is the line `  crops, every change at native size before > after, numbered as on the sheets: P` and `LS(F)` the line `  screens, a full native frame of each screen as it starts, for reading text and digits: F; all listed in out/crops.json`.

| ID | Input | Result |
|---|---|---|
| CRP-1, CRP-10 | `crop_units([], 1600, 800, 40)`, `crop_units([], 1600, 800, 3)` | `([{'start': 0, 'key': 0, 'crops': [], 'n': 1}], [])` both times (amended by CRP-10, step 17: the only screen is the last one and stays; the second was `([], [])`) |
| CRP-1 | `crop_units([E(100, 100, 24, 24, 3, 4), E(200, 100, 24, 24, 4, 4), E(1000, 500, 40, 20, 4, 4)], 1600, 800, 40)` | one screen `start` 0 `key` 0 `n` 1 holding both crops; crops `{'rect': [100, 100, 124, 24], 'events': [0, 1], 'crop': [84, 84, 156, 56], 'start': 3, 'settled': 4, 'screen': 1}` and `{'rect': [1000, 500, 40, 20], 'events': [2], 'crop': [984, 484, 72, 52], 'start': 4, 'settled': 4, 'screen': 1}` |
| CRP-1 | the same events in the order `E(1000, 500, 40, 20, 4, 4)`, `E(100, 100, 24, 24, 3, 4)` (two only) | crops `[100, 100, 24, 24]` with `events` `[1]` first, then `[1000, 500, 40, 20]` with `events` `[0]` (sorted by `(y, x)`) |
| CRP-1 | `[E(100, 100, 24, 24, 3, 4), E(251, 100, 24, 24, 4, 4)]`, and the same with the second at `x` 252 | one crop `rect` `[100, 100, 175, 24]`, `events` `[0, 1]`, `crop` `[84, 84, 207, 56]` (a gap of 127 px); two crops `[100, 100, 24, 24]` and `[252, 100, 24, 24]`, `crop` `[236, 84, 56, 56]` for the second (128 px) |
| CRP-1 | `[E(100, 100, 24, 24, 1, 2), E(130, 100, 24, 24, 3, 4)]` | two crops, `settled` 2 and 4, `start` 1 and 3 (6 px apart, but in two moments) |
| CRP-1 | `[E(0, 0, 300, 300, 3, 4), E(320, 0, 100, 100, 4, 4)]`, and the same with the second at `x` 360 | one crop `rect` `[0, 0, 420, 300]` (126000 px), `crop` `[0, 0, 436, 316]`; two crops, `[0, 0, 300, 300]` with `crop` `[0, 0, 316, 316]` and `[360, 0, 100, 100]` with `crop` `[344, 0, 132, 116]` (the pair would cover 138000 px, over `CROP_SHARE * F`) |
| CRP-1 | `[E(0, 0, 200, 200, 3, 4), E(260, 0, 200, 200, 4, 4), E(520, 0, 200, 200, 2, 4)]`, and the same three in reverse order | `[0, 0, 460, 200]` `events` `[0, 1]` `start` 3, then `[520, 0, 200, 200]` `events` `[2]` `start` 2; in reverse, `[0, 0, 200, 200]` `events` `[2]` `crop` `[0, 0, 216, 216]`, then `[260, 0, 460, 200]` `events` `[0, 1]` `crop` `[244, 0, 492, 216]` `start` 2 (the first pair joined blocks the third) |
| CRP-1 | `[E(200, 200, 432, 432, 3, 4)]`, and `[E(200, 200, 440, 440, 3, 4)]` | one crop `[200, 200, 432, 432]`, `crop` `[184, 184, 464, 464]` (halo 70x70 cells, 4900); screens `start` 0 `key` 0 `n` 1 and `start` 4 `key` 4 `n` 2, both without crops, and no crops (halo 71x71 cells, 5041) |
| CRP-1 | `[E(100, 100, 24, 24, 3, 4), E(0, 0, 1600, 800, 9, 10), E(700, 300, 40, 20, 19, 20)]` | screens `(start 0, key 0, n 1)` with the first crop and `(start 10, key 10, n 2)` with `{'rect': [700, 300, 40, 20], 'events': [2], 'crop': [684, 284, 72, 52], 'start': 19, 'settled': 20, 'screen': 2}` |
| CRP-1 | the events of the row above with `E(0, 0, 1600, 800, 10, 11)` inserted after the second | screens `(0, 0, n 1)` and `(start 11, key 11, n 2)`; the screen from 10 lasted one sample without crops and is dropped; the last crop has `events` `[3]` and `screen` 2 |
| CRP-1, CRP-10 | `[E(0, 0, 1600, 800, 37, 38)]` | screens `[{'start': 0, 'key': 0, 'crops': [], 'n': 1}, {'start': 38, 'key': 38, 'crops': [], 'n': 2}]`, crops `[]` (amended by CRP-10, step 17: the screen from 38 lasts 2 samples and is the last, so it stays; it was dropped) |
| CRP-1 | `A4 = [E(40 + 380 * i, 40, 300, 300, 2 + i, 3 + i) for i in range(4)]`; `A4 + [E(40, 440, 24, 24, 11, 12)]` | screen 1 (`start` 0, `key` 0) with four crops (`crop` `[24, 24, 332, 332]`, `[404, 24, 332, 332]`, `[784, 24, 332, 332]`, `[1164, 24, 332, 332]`, 1444 cells each: after the fourth, 5776 cells pass 5000); screen 2 `start` 7 `key` 6 with the crop `[40, 440, 24, 24]`, `events` `[4]`; `A4[:3] + [E(40, 440, 24, 24, 11, 12)]` gives one screen with four crops |
| CRP-1 | `A4 + [E(0, 0, 1600, 800, 6, 7), E(40, 440, 24, 24, 11, 12)]` | screen 2 has `start` 7 and `key` 7 (the full frame after the new screen, not before it) and the crop with `events` `[5]`; `A4 + [E(0, 0, 1600, 800, 8, 9), E(40, 440, 24, 24, 11, 12)]` gives screen 2 `start` 9 `key` 9 (the screen from 7 lasted two samples without crops and is dropped) |
| CRP-2 | `mark_image(8, 4, [])` | 193 bytes: the header `b'P7\nWIDTH 8\nHEIGHT 4\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n'` (65 bytes) and 128 zero bytes |
| CRP-2 | `mark_image(30, 20, [(1, 1, '1')])` | 2467 bytes; of 600 pixels 348 are `(0, 0, 0, 0)`, 212 `(255, 255, 255, 255)` and 40 `(255, 0, 255, 255)` (the 10 ones of `1`); pixels `(7, 3)`, `(8, 4)` and `(7, 5)` are magenta, `(1, 1)`, `(14, 18)` and `(6, 3)` white, `(15, 1)` and `(0, 0)` transparent |
| CRP-2 | `mark_image(10, 10, [(-3, 5, '8')])` | 50 pixels transparent (rows 0 to 4), 35 white, 15 magenta; in row 7 pixels `x` 1 to 6 are magenta and 0, 7, 8, 9 white |
| CRP-2 | `mark_image(40, 20, [(0, 0, '8'), (6, 0, '1')])` | 440 transparent, 292 white, 68 magenta; in row 2 pixels `x` 4 and 5 are magenta and 6 to 11 white (the second mark's white covers the first's ink) |
| CRP-2 | `mark_image(40, 20, [(0, 0, '0?')])` | 332 transparent, 392 white (26 x 18 minus the ink), 76 magenta (`?` has no glyph and takes its 12 px) |
| CRP-3 | `label_band('>', 20)` | 453 bytes; 48 pixel bytes are 0 (the 7 ones of `>` times four, and the 20 of row 21); pixels `(4, 4)`, `(5, 5)`, `(6, 6)`, `(10, 10)`, `(4, 16)` and `(5, 17)` are 0, `(6, 4)` and `(12, 10)` are 255 |
| CRP-6 | argv `['clip.mp4', 'out']`, samples `two`, entries `None`, `(CAB, Z)`, `(CA, Z)` | `write_crops` called once with `('clip.mp4', 'out', screens, crops, {0: 1, 1: 1, 2: 2}, [0, 4, 6], 1600, 80, 4, 0.0, None)`, where crops are `{'rect': [16, 16, 24, 24], 'events': [0], 'crop': [0, 0, 56, 56], 'start': 1, 'settled': 1, 'screen': 1}`, `{'rect': [96, 16, 24, 24], 'events': [1], 'crop': [80, 0, 56, 56], 'start': 3, 'settled': 3, 'screen': 1}`, `{'rect': [16, 16, 24, 24], 'events': [2], 'crop': [0, 0, 56, 56], 'start': 5, 'settled': 5, 'screen': 1}` and screens `[{'start': 0, 'key': 0, 'crops': <those three>, 'n': 1}]`; it returns `None`, so `contact_sheets` is called with five arguments, stdout ends with the manifest line and stderr is empty |
| CRP-6, CRP-13 | the row above with `write_crops` returning `R` | `contact_sheets` called with the marks `[[], [(64, 2, '02')], [(25, 2, '03')]]` as its sixth argument (amended by CRP-13, step 17: on a tile 39 px high a mark fits neither above nor under a box, so it goes right of it, and right of the first box of the second frame lies the other box 16 px away, so crop 01 has no mark; it was `[[], [(2, 21, '01'), (41, 21, '02')], [(2, 21, '03')]]`); stdout ends with the manifest line, `LC('out/crops-01.png')` and `LS('out/screen-01-0.00s.jpg')`, in that order; stderr empty; return 0 |
| CRP-6, CRP-13 | argv `['clip.mp4', 'out']`, samples `two`, `write_crops` returning `R2` | `contact_sheets` called with five arguments (amended by CRP-13, step 17: the row names no entries of `kept_changes`, so no frame has a box, and without a box there is no number; the marks were `[[], [(41, 0, '01'), (750, 0, '02')], [(2, 9, '03')]]`, from the crops' `rect` and `tile`, which are no longer read); the last two lines of stdout are `LC('out/crops-01.png, out/crops-01b.png, out/crops-02.png')` and `LS('out/screen-01-0.00s.jpg, out/screen-02-1.00s.jpg')` |
| CRP-6 | argv `['clip.mp4', 'out']`, samples `two`, `write_crops` returning `R3`, and returning `R4` | `contact_sheets` called with five arguments both times (no frame has a box, the row names no entries of `kept_changes`; before CRP-13, step 17, the reason was that no crop has a tile); last two lines `LC('out/crops-01.png')` and `LS('out/screen-01-0.00s.jpg')`; and `LC('none')` and `LS('none')` |
| CRP-6 | argv `['clip.mp4', 'out']`, samples `two`, `write_crops` raising `OSError(2, 'No such file or directory')`, and raising `subprocess.CalledProcessError(1, ['ffmpeg'])` | return 0; stderr exactly `  crops not written: [Errno 2] No such file or directory\n`, and `  crops not written: Command '['ffmpeg']' returned non-zero exit status 1.\n`; `contact_sheets` called with five arguments; stdout ends with the manifest line; `frames.json` written, without the keys of CRP-8 |
| CRP-6 | argv `['clip.mp4', 'out', '--from', '1']`, probe `(3.0, 1600, 80)`, samples `two`, entries of the first row | `write_crops` called with the last seven arguments `({0: 1, 1: 1, 2: 2}, [0, 4, 6], 1600, 80, 4, 1.0, 2.0)` |
| CRP-6, CRP-10 | argv `['clip.mp4', 'out']`, probe `(2.0, 160, 80)`, samples `two`, entries of the first row | `write_crops` called with `('clip.mp4', 'out', [{'start': 5, 'key': 5, 'crops': [], 'n': 1}], [], {0: 1, 1: 1, 2: 2}, [0, 4, 6], 160, 80, 4, 0.0, None)` (on 160x80 the halo of every change passes a quarter of the frame, and each screen lasts under a second; amended by CRP-10, step 17: the last of them stays, the screens were `[]`) |
| CRP-6 | argv `['clip.mp4', 'out']`, samples `[S({})]`; argv `['clip.mp4', 'out', '--dry-run']`, samples `two`; argv `['clip.mp4', 'out', '--selector', 'legacy']`, thumbnails `static(30)` | `write_crops` not called in any of the three |
| CRP-6 | argv `['clip.mp4', 'out']`, probe `(2.0, 160, 80)`, samples `two`, `contact_sheets` raising `ValueError('ffprobe could not read the frame width of out/frame-01.jpg')` (the LBL-2 events row) | stderr exactly `clip.mp4: ffprobe could not read the frame width of out/frame-01.jpg\n` |
| CRP-8 | argv `['clip.mp4', 'out']`, samples `two`, `write_crops` returning `None` | the top-level keys of `frames.json` are those of MAN-17, the last `events`; every entry of `events` has exactly the keys `from`, `settled`, `until`, `region`, `changed_px`, `shown` |
| CRP-8 | the same with `write_crops` returning `R` | the top-level keys are those of MAN-17 followed by `crops`, which is `{"file": "crops.json", "images": ["crops-01.png"], "screens": [{"n": 1, "from": 0.0, "file": "screen-01-0.00s.jpg"}]}`; every entry of `events` has the keys of MAN-17 followed by `crop`: `{"n": 1, "file": "crops-01.png"}`, `{"n": 2, "file": "crops-01.png"}`, `{"n": 3, "file": "crops-01.png"}` |
| CRP-8 | the same with `R2`; with `R3`; with `R4` | `R2`: `crop` `{"n": 1, "file": "crops-01.png"}`, `{"n": 2, "file": "crops-01b.png"}`, `{"n": 3, "file": "crops-02.png"}`, and `crops.screens` `[{"n": 1, "from": 0.0, "file": "screen-01-0.00s.jpg"}, {"n": 2, "from": 1.25, "file": "screen-02-1.00s.jpg"}]`, `crops.images` the three names; `R3`: `crop` `{"n": 1, "file": "crops-01.png"}` for the first two events and `null` for the third; `R4`: `crop` `null` for all three and `crops` `{"file": "crops.json", "images": [], "screens": []}` |
| CRP-8 | argv `['clip.mp4', 'out', '--from', '1']`, probe `(3.0, 1600, 80)`, samples `two`, `write_crops` returning `R` | `crops.screens` `[{"n": 1, "from": 1.0, "file": "screen-01-0.00s.jpg"}]` (`from` counts from the start of the recording) |
| CRP-7 | directory with `screen-01-0.00s.jpg`, `screen-02-12.25s.jpg`, `crops-01.png`, `crops-01b.png`, `crops.json`, `crops-01.jpg`, `screen.jpg`, `Screen-01.jpg`, `crop-01-before.png`, `crops.json.tmp` and `frames.json`, then `clean(dir)` | remaining: `Screen-01.jpg`, `crop-01-before.png`, `crops-01.jpg`, `crops.json.tmp`, `screen.jpg` |

### Properties (step 16)

CRP-P1 For `width` 1600, `height` 800, `samples` 40 and `events` a list of 0 to 8 events `E(x, y, w, h, start, settled)` with `w`, `h` integers in `[8, 400]`, `x` in `[0, 1600 - w]`, `y` in `[0, 800 - h]`, `settled` in `[1, 39]` and `start` in `[1, settled]`: no event index is in two crops; each crop's `rect` is the smallest rectangle holding the rectangles of its events, all of which have its `settled`, and its `start` is the smallest of their `start`s; a crop of two or more events has a `rect` of at most `CROP_SHARE * 1600 * 800` px; each `crop` lies inside the frame and holds `rect`; the screens have strictly increasing `start`, `n` 1, 2, ... in order, and a `key` equal to `start` or `start - 1`; every crop is in the `crops` of exactly the screen whose `n` is its `screen`, and its `settled` is at least that screen's `start` and below the next screen's `start`.

### Errors (step 16)

`crop_units` and `mark_image` raise nothing on the inputs above; `crop_units` with a zero `width` or `height` is undefined, do not test. `write_crops` raises as CRP-5 step 6 says, and `main()` swallows those two types (CRP-6; every `Exception` since CRP-13, step 17). `contact_sheets` raises as in step 14 for the second ffprobe too (one ffprobe call since CRP-16, step 17).


## Step 17: fixes after the review of the crops (drafted and implemented 2026-10-04)

Why. A review of the crops code (`docs/specs/reports/2026-10-04-review-crops.md`) found eight faults, each confirmed by a second pass told to break it. All eight were in the code published on 2026-09-28, and five were behaviour that step 16 itself prescribed, so their fix starts here. A real small change, a digit in an 11 px font or a text selection, was left out of the crops as "looks the same", and so was a change of colour that keeps its BT.601 luma (CRP-9). The numbers on a sheet covered neighbouring changes and each other (CRP-11, CRP-13). The crops kept every sample of a change in memory, 1.8 GB for an animation of 8 minutes, and a failure in them took the sheets and `frames.json` along (CRP-13, CRP-15). The screen a recording ends on got no full frame when it lasted under a second (CRP-10). A crop wider than a sheet shrank the small crops on its page, and the 27th page of a screen got a file name past `z` (CRP-15). `clean` removed files named `screen-*.jpg` and `crops-*.png` that were not ours, without the guard that protects `frame-*.jpg` (CRP-14).

Measured on the 15 labeled recordings, before against after. The comparison of CRP-9 was run over the 291 crops that have a picture before the change. The rule of step 16 called 48 of them the same, this rule 41, so 275 crops are kept against 268 and 16 left out against 23. The seven recovered are a text selection, the I-beam pointer over text (twice) and a text caret (four times), each plain in its two pictures. Six crops gained or changed their middle picture. Counting a pixel by its largest change among red, green and blue, the first plan, kept an eighth crop, blue link text whose two pictures look the same to the eye. It has 81 px past `PIXEL_T` in one block by a channel against 22 by luma, the chroma a codec re-encodes at a keyframe, which is why the rule stays with luma and takes it by both standards. The memory rule of CRP-15 alone left every `crops.json`, every page of crops and every sheet of the 15 recordings byte for byte the same. The last screen of CRP-10 gave four recordings one more screen file, 77 against 73, and the feedback recording its fifth, from 12.0 s. All 15 take 45.1 s against 42.6 s. The triggers of the review were rebuilt as synthetic recordings: "qty 1" becoming "qty 7" at 8, 9 and 10 px and in grey at 11 px, and the dot turning from `#e53935` to `#43a047` on a stream tagged BT.709, were each left out before and are a crop now.

The code of this step exists. CRP-9 to CRP-14 are anchored (tests expected green); CRP-15 and CRP-16 are [hands-on].

### Vocabulary (step 17)

- `pic(w, h, c)` in the examples is the picture `[bytes(c) * w for _ in range(h)]`, `w` x `h` px of the colour `c`, an `(r, g, b)` tuple. `dots(p, c, xs)` is a copy of the picture `p` with the pixels `(x, y)` of the list `xs` set to `c` (bytes `3 * x` to `3 * x + 2` of row `y`).
- `G` is `pic(32, 32, (100, 100, 100))`, four blocks of grey. `g(d)` is the colour `(100 + d, 100 + d, 100 + d)`, which differs from the grey of `G` by `abs(d)` levels of luma by either standard. `first(n)` is `[(i % 16, i // 16) for i in range(n)]`, the first `n` pixels of block (0, 0) in reading order.
- `FIRST` is the entries `None`, `(CAB, Z)`, `(CA, Z)` of `kept_changes` of the first CRP-6 row: with samples `two`, frame 1 (from 0) gets the boxes of the events 0 and 1 and frame 2 the box of event 2, so `tiles` is `{0: 1, 1: 1, 2: 2}`.

### Public surface added (step 17)

    def looks_same(a, b)
    def box_marks(boxes, numbers, width, height)

### Rules (step 17)

CRP-9 `looks_same(a, b)` takes two pictures of one area and returns a bool. A picture is a list of rows, each row `bytes`, three per pixel (red, green, blue); the two have the same size. The change of a pixel is the larger of its luma differences by BT.601 and by BT.709, `max(abs(77 * dR + 150 * dG + 29 * dB), abs(54 * dR + 183 * dG + 19 * dB)) / 256` with `dR`, `dG`, `dB` the differences of its three bytes. A pixel is changed when that is more than `PIXEL_T` (24) and strongly changed when it is more than `2 * PIXEL_T` (48); a strongly changed pixel is a changed one too. Pixel `(x, y)` belongs to block `(x // 16, y // 16)`. The result is `False` when some block holds `BOX_SPREAD` (24) or more changed pixels or `BOX_STRONG` (5) or more strongly changed pixels, and `True` otherwise. `looks_same([], [])` is `True`. Pictures of different sizes are undefined.
       Why the second count. The rule of step 16 had only the first, and "qty 1" becoming "qty 7" in an 11 px font changes 21 px (review, bug 1). The event of such a change was shown on the sheet with a box and came out with `"crop": null`, which the skill explains as "looked the same". `BOX_STRONG` is the count BOX-3 already uses for the boxes, on the same grounds: codec noise on unchanged text changes at most 3 px past twice `PIXEL_T`, a real change of a digit, a label or a checkbox at least 9.
       Why luma by two standards. Events are found on the luma plane of the recording itself, and the pictures are that recording converted to RGB by its own matrix, so its luma is the BT.709 luma of the picture when the stream is tagged BT.709 and the BT.601 luma otherwise. Step 16 took BT.601 alone, and a 40 px dot turning from `#e53935` to `#43a047` on a BT.709 recording, 41 levels by its own luma, was 14 levels and "the same" (review, bug 2). The larger of the two never calls the same what the selector saw as a change. The largest change among the three channels was tried and dropped, see the measurements above.

CRP-10 (amends CRP-1 step 5) A screen without crops is dropped when it lasts fewer than `EVENT_FPS` samples and is not the last screen, or when it is the last screen and its `start` is `samples` or more (it holds no sample, which happens when the crops of the last sample fill the accumulated cells of step 4). The last screen is otherwise kept however short it is. With `events` `[]` the result is one screen `{'start': 0, 'key': 0, 'crops': [], 'n': 1}` for `samples >= 1` and `([], [])` for `samples` 0. Everything else in CRP-1, and CRP-P1, stays.
       Why. A screen that ends with another redraw within a second is a transition. The last screen ends with the recording, so its length says nothing: a form for 5.3 s, then a full-screen error page, and the recording stops at 6.0 s, and the error page had no full frame (review, bug 5; the feedback recording of 2026-10-04 did the same from 12.0 s).

CRP-11 (amended by CRP-17, step 18: an optional fifth argument, the grid of the frame, makes step 4 take the free place that hides the least) `box_marks(boxes, numbers, width, height)` takes the boxes of one tile, `(x, y, w, h)` tuples as `change_boxes` returns them, `numbers`, a list with one list of ints per box (the crops of the changes that box frames, in any order, repeats allowed, `[]` for none), and the size of the tile in px, and returns the marks to write on the tile, a list of `(x, y, text)` for `mark_image`. The boxes are taken in order, each in four steps.
1. A box whose list of numbers is empty gets no mark. Otherwise its text lists the distinct numbers in increasing order. Each maximal run of consecutive numbers becomes `'%02d' % n` when it holds one number and `'%02d-%02d' % (first, last)` when it holds two or more, and the runs are joined by one space: `[1, 2, 3, 4, 5, 6]` gives `01-06`, `[3, 1, 2, 9, 5, 5]` gives `01-03 05 09`.
2. A mark is `mw = 12 * len(text) + 2` px wide and 18 px high (CRP-2). With `cx = max(0, min(width - mw, x))` and `cy = max(0, min(height - 18, y))`, the places for the mark are tried in this order: above the box `(cx, y - 18)`, under it `(cx, y + h)`, right of it `(x + w, cy)`, left of it `(x - mw, cy)`.
3. A place `(px, py)` is free when the mark lies on the tile, `0 <= px <= width - mw` and `0 <= py <= height - 18`, and its rectangle `(px, py, mw, 18)` shares no pixel with any box of `boxes` (with or without numbers, each by its rectangle as given, also where that passes the tile's edge) and with no mark placed for an earlier box. Two rectangles share a pixel when `a.x < b.x + b.w`, `b.x < a.x + a.w`, `a.y < b.y + b.h` and `b.y < a.y + a.h`.
4. The box gets the mark `(px, py, text)` of the first free place, and no mark when none of the four is free (always so when the text is wider than the tile).
The result holds the marks in the order of their boxes. `box_marks([], [], width, height)` is `[]`.
       Why one mark per box and a free place. Step 16 put one mark per crop above its own rectangle. Six 16 px checkboxes 36 px apart on a 2560 px screen, ticked between two kept frames, are one joined box on the tile and got six marks 11 px apart, which cut each other and hid five of the checkboxes (review, bug 3). And a tile with more than `BOX_MAX` changes lost its boxes and kept the numbers, fourteen of them around nothing. A box is what the eye is sent to, so the number belongs to it, and the crops of a joined box are named together.
       Why no mark rather than a mark over something. The sheet is where a change is seen at all, the number is a convenience: the crop of every event is named in `frames.json` (CRP-8), and the label of a crop names its tile. A mark over a neighbouring box hides a change on the one picture that shows it in context.

CRP-12 (amends LBL-1 and CRP-3) The glyph table gains `-`: `00000 00000 00000 11111 00000 00000 00000`. `label_band` and `mark_image` draw it like every other glyph.

CRP-13 (amends CRP-6) Two changes in `main()` for the events selector with at least two frames. Everything CRP-6 says that is not named here stays, the console lines and the calls with one frame, `--dry-run` and the legacy selector included.
1. `crop_units` and `write_crops` are called as in CRP-6. When either raises any `Exception`, `main()` prints `  crops not written: <text>` to stderr, where `<text>` is `str()` of the exception, or the name of its type when that is empty (`MemoryError`), and goes on as if `write_crops` had returned `None`. When `crop_units` raises, `write_crops` is not called. The boxes, the sheets, `frames.json` (without the keys of CRP-8) and the return value 0 are those of a run without crops.
2. The marks. (Amended by CRP-18, step 18: `box_marks` also gets the grid of the frame.) With a result of `write_crops`, the number of an event is the `n` of the crop of the result whose `events` holds the event's index; an event that no crop holds has no number. An event lies in a box `(bx, by, bw, bh)` of a frame when its corner does, `bx <= x0 < bx + bw` and `by <= y0 < by + bh`, with `x0 = x * tile_width // width - BOX_GAP - BOX_T` and `y0 = y * tile_width // width - BOX_GAP - BOX_T` for the event's region `[x, y, w, h]` (the corner of its rectangle of BOX-1 step 1, which lies in exactly one box of its frame, or in none when BOX-1 step 4 or 5 dropped that box). For each kept frame `i` (from 0), its boxes (BOX-3) are taken in order, and the numbers of a box are the numbers of the events `j` with `tiles[j] == i` that lie in it, each number once, in increasing order, without the numbers an earlier box of the same frame already got: a crop whose changes are in several boxes of a frame is numbered at the first of them only. The marks of the frame are `box_marks(boxes[i], numbers, tile_width, tile_height)` with `tile_height` as in BOX-3. The `rect` and `tile` of the crops are not read for the marks. When some frame has a mark, the sheets are written by `contact_sheets(paths, out_dir, cols, rows, boxes, marks)` with one list per frame, otherwise by `contact_sheets(paths, out_dir, cols, rows, boxes)`. Without a result there are no marks.
       Why any exception. The crops are an addition to the sheets and run before them. With the process capped at 1.2 GB the animation of the review ended in a `MemoryError` that `main()` did not catch, with no sheet and no `frames.json` (review, bug 4).
       Why by event and not by crop. A crop joins changes up to `CROP_JOIN` px apart, a box only those `BOX_NEAR` px apart on the tile, and the events of one crop can get their boxes on different frames. So a crop can have several boxes on a frame. Its number stands at the first: with a number at each, a row of seven checkboxes toggled at once on the checkbox recording, one crop, got seven marks that hid the seven column headers above them, and the crop shows the whole row anyway. A box whose change has no crop (it looked the same before and after) carries no number.

CRP-14 (amends DIR-1, DIR-2 and CRP-7) `check_out_dir(out_dir, force)` returns `None` when `force` is true, when `out_dir` is not a directory, or when it holds `frames.json`. Otherwise the patterns `frame-*.jpg`, `screen-*.jpg` and `crops-*.png` are taken in this order, and for the first one that some entry of `out_dir` matches (its name starts with the part before `*` and ends with the part after) the result is `'<out_dir> already holds <pattern> from something else; pass --force to overwrite'`. When none matches the result is `None`. `clean` is as in CRP-7.
       Why. `clean` removes `screen-*.jpg` and `crops-*.png` since step 16, and only `frame-*.jpg` was guarded: `screen-shot-of-the-bug.jpg` in a folder that was never ours was deleted without a word (review, bug 8).

CRP-15 (amends CRP-5 steps 2, 3 and 4) [hands-on] Four changes in `write_crops`.
1. Memory. Of the samples of a crop it keeps at most five pictures: `before`, `after`, the sample of its tile `points[tile]` when that lies from `start` to `settled - 1`, the first sample from `start` to `settled - 1` whose picture does not look the same as `before` (`looks_same`, CRP-9), and the first sample past that one, up to `settled - 1`, whose picture looks the same as neither `before` nor that one (none of the two when `before` is `None`). Every other sample is cut, compared and let go.
2. The `passing` picture. The candidates are, in order, the sample of the tile, then, only when `before` is not `None` and looks the same as `after`, the two samples of change 1 in their order. The first candidate whose picture looks the same as neither `before` (when there is one) nor `after` is `passing`. Step 16 tried every sample in between against both, which is what took the memory. Two are kept and not one because looking the same is not transitive: a faint first sample can differ from `before` and still look like `after`, with a plain state right behind it. A change is still left out when both kept samples look like `after` and a third state came later.
3. Pages. A block wider than `SHEET_WIDTH` is alone on its page, which is as wide as the block; the blocks before it and after it are packed as before on pages of their own.
4. Names and label. The first page of screen `n` is `crops-<n:02d>.png`, page `p` from 2 on is `crops-<n:02d>-<p:02d>.png` (`crops-01-02.png`), for any number of pages. The label of a block is black on white, as `label_band` draws it (step 16 said grey, the code never did).
Evidence. On the 15 labeled recordings changes 1 and 2 alone, with the comparison of step 16, give the same bytes in every `crops.json`, page and sheet, with one sample kept past `before` or with two. A lossless synthetic recording in which a faint patch of 6x5 px appears at 2.00 s, a 120x60 px tooltip covers it at 2.25 s and 6x3 px of the patch stay from 2.50 s on gives the crop `1.75>2.25>2.50` with the tooltip in the middle; with only the first sample kept, the one at 2.00 s, which looks like `after`, the change was left out (review of this step's diff). A synthetic recording of a 600x400 panel animating for 2 minutes on 1920x1080, one crop of about 480 samples, peaks at 90 MB in the process itself against 472 MB before (33 MB on a 5 s recording of that size). A synthetic recording with a row highlight 2000x30 on 2560x1440 and three small changes gives the highlight the page `crops-01.png`, 2034x176 px, and the three `crops-01-02.png`, 624x80 px, where step 16 gave one page 2034x268. The checkbox recording gives `crops-01.png`, `crops-01-02.png`, `crops-01-03.png` with the same 53 crops, and a synthetic recording of a panel changing every 1.5 s for 90 s gives 59 pages, the last `crops-01-59.png` (from the 27th on, the names of step 16 held characters past `z`, the last a control character).

CRP-16 (amends CRP-4 and LBL-2) [hands-on] Three changes in `contact_sheets`.
1. One ffprobe call reads the width, the height and the pixel format of the first frame (`-show_entries stream=width,height,pix_fmt`). Output without all three, or with a width or height that is not a number, raises `ValueError('ffprobe could not read the frame width of <path>')`. Step 16 read the height in a second call whose empty output raised `IndexError`, which `main()` does not catch.
2. The overlay of the marks is `overlay=0:0:format=yuv444` when the pixel format of the frames holds `444`, `format=yuv422` when it holds `422`, and `format=yuv420` otherwise (the filter's default, so those sheets are the same bytes as before).
3. A sheet that gets no boxes because the drawbox part of its graph is longer than 30000 characters (BOX-2) gets no marks either: it is the sheet of a call without `boxes` and `marks`. A number next to nothing is what CRP-11 ends.
Evidence. On a synthetic 4:4:4 recording a sheet with two marks differs from the same sheet without marks by more than 2 levels in 653 pixels, all in the rows of the marks; with the overlay of step 16 in 77965, over the whole sheet. On the two real recordings (4:2:0) the sheets differ from those of step 16 only at marks. On the feedback recording of 2026-10-04 in one place, a mark that is gone because its change has no box. On the checkbox recording in three: two marks that cut each other now stand apart, two marks over one joined box became one reading `26 28`, and a mark that stood inside a box stands above it. A sheet of four frames given 600 boxes and a mark on its first frame is the same bytes as the sheet given neither; before change 3 it carried the mark.

The fakes of the `main()` rows are those of step 16. A row that names an exception for `crop_units` replaces it with a function that raises it.

Rows of earlier steps that this step changes, each edited where it stands and marked there: the CRP-1 rows `crop_units([], 1600, 800, 3)` and `[E(0, 0, 1600, 800, 37, 38)]`; the CRP-6 rows with `write_crops` returning `R` (the marks), returning `R2` (five arguments) and the probe `(2.0, 160, 80)` row (the screens given to `write_crops`). Every other row of earlier steps keeps its result. Since the marks now follow the boxes, the entries of `kept_changes` matter to every CRP-6 and CRP-8 row: a row that names none means zeros for every frame, as the step 15 examples say, and so no box and no mark. The CRP-6 row with `R3` and `R4` keeps its five arguments only on those terms; with the entries `FIRST` and the probe of that row its `R3` half still gets five arguments, because on a tile 39 px high the first box of the crop has no free place, and on the probe `(2.0, 160, 80)` it gets the marks of the CRP-13 row with `R3`.

### Examples (step 17)

`two`, `Z`, `CA`, `CAB`, `R`, `R3`, `R4`, `LC`, `LS` and the fakes as in the step 16 examples, `E`, `F` and the 1600x800 frame with 40 samples as in its vocabulary. `R6` is `{'crops': [{'n': 4, 'tile': 1, 'rect': [16, 16, 24, 24], 'events': [0], 'file': 'crops-01.png'}, {'n': 6, 'tile': 1, 'rect': [96, 16, 24, 24], 'events': [1], 'file': 'crops-01.png'}, {'n': 12, 'tile': 2, 'rect': [16, 16, 24, 24], 'events': [2], 'file': 'crops-01-02.png'}], 'images': ['crops-01.png', 'crops-01-02.png'], 'screens': [{'n': 1, 'start': 0, 'file': 'screen-01-0.00s.jpg'}], 'left': 0}`. `B` is the box `(100, 100, 30, 30)`.

| ID | Input | Result |
|---|---|---|
| CRP-9 | `looks_same([], [])`, `looks_same(G, G)` | `True`, `True` |
| CRP-9 | `looks_same(G, dots(G, g(25), first(n)))` for `n` 23 and 24, and the same with the two arguments swapped | `True`; `False`; the same swapped |
| CRP-9 | `looks_same(G, dots(G, g(24), first(256)))` | `True` (24 levels is not past `PIXEL_T`) |
| CRP-9 | `looks_same(G, dots(G, g(49), first(n)))` for `n` 4 and 5 | `True`; `False` |
| CRP-9 | `looks_same(G, dots(G, g(48), first(n)))` for `n` 5, 23 and 24 | `True`, `True`, `False` (48 levels is changed, not strongly) |
| CRP-9 | `looks_same(G, dots(G, g(-25), first(24)))`, `looks_same(G, dots(G, g(-49), first(5)))` | `False`, `False` (darker counts as lighter does) |
| CRP-9 | `looks_same(G, dots(G, g(25), [(4 + i, 0) for i in range(24)]))`, and with `[(0, 4 + i) for i in range(24)]` | `True` both times (12 px in block (0, 0) and 12 in block (1, 0); 12 and 12 in blocks (0, 0) and (0, 1)) |
| CRP-9 | `looks_same(G, dots(G, g(49), [(13 + i, 0) for i in range(5)]))`, and with `[(16 + i, 16) for i in range(5)]` | `True` (3 px in block (0, 0), 2 in block (1, 0)); `False` (5 in block (1, 1)) |
| CRP-9 | `looks_same(G, dots(dots(G, g(25), first(n)), g(49), [(i, 2) for i in range(4)]))` for `n` 19 and 20 | `True` (23 changed, 4 of them strongly); `False` (24 changed) |
| CRP-9 | `looks_same(pic(40, 40, (229, 57, 53)), pic(40, 40, (67, 160, 71)))` | `False` (13.7 levels by BT.601, 40.8 by BT.709) |
| CRP-9 | `looks_same(pic(16, 16, (20, 150, 100)), pic(16, 16, (220, 91, 100)))` | `False` (25.6 levels by BT.601, 0.01 by BT.709) |
| CRP-9 | `looks_same(pic(16, 16, (100, 100, 100)), pic(16, 16, (100, 100, 160)))` | `True` (60 levels of blue alone are 6.8 and 4.5 levels of luma) |
| CRP-9 | `looks_same(pic(4, 1, (0, 0, 0)), pic(4, 1, (255, 255, 255)))`, and the same with `pic(5, 1, ...)` | `True`; `False` |
| CRP-10 | `crop_units([], 1600, 800, 1)`, `crop_units([], 1600, 800, 0)` | `([{'start': 0, 'key': 0, 'crops': [], 'n': 1}], [])`; `([], [])` |
| CRP-10 | `[E(0, 0, 1600, 800, 35, 36), E(0, 0, 1600, 800, 37, 38)]` | screens `[{'start': 0, 'key': 0, 'crops': [], 'n': 1}, {'start': 38, 'key': 38, 'crops': [], 'n': 2}]`, crops `[]` (the screen from 36 lasts 2 samples and is dropped; the last, as short, stays) |
| CRP-10 | `crop_units([E(0, 0, 1600, 800, 0, 1), E(0, 0, 1600, 800, 1, 2)], 1600, 800, 3)` | `([{'start': 2, 'key': 2, 'crops': [], 'n': 1}], [])` (the screens from 0 and from 1 last one sample each) |
| CRP-10 | `[E(40 + 380 * i, 40, 300, 300, 35 + i, 36 + i) for i in range(4)]`, and the same with `34 + i, 35 + i` | one screen `start` 0 `key` 0 `n` 1 with four crops (the screen their cells start would begin at sample 40, past the last one); screens `start` 0 `key` 0 `n` 1 with four crops and `{'start': 39, 'key': 38, 'crops': [], 'n': 2}` |
| CRP-11 | `box_marks([], [], 776, 400)`, `box_marks([B], [[]], 776, 400)` | `[]`, `[]` |
| CRP-11 | `box_marks([B], [ns], 776, 400)` for `ns` `[7]`, `[1, 2, 3, 4, 5, 6]`, `[1, 2]`, `[1, 3]`, `[3, 1, 2, 9, 5, 5]`, `[99, 100]` | `[(100, 82, t)]` with `t` `'07'`, `'01-06'`, `'01-02'`, `'01 03'`, `'01-03 05 09'`, `'99-100'` |
| CRP-11 | `box_marks([(100, y, 30, 30)], [[7]], 776, 400)` for `y` 18, 17 and 360 | `[(100, 0, '07')]` (just room above); `[(100, 47, '07')]` (under it); `[(100, 342, '07')]` |
| CRP-11 | `box_marks([(x, 100, 30, 30)], [[7]], 776, 400)` for `x` 770 and -5; `box_marks([(-5, -5, 34, 34)], [[7]], 776, 400)` | `[(750, 82, '07')]`, `[(0, 82, '07')]` (held within the tile); `[(0, 29, '07')]` |
| CRP-11 | `box_marks([(100, 100, 30, 30), (100, 140, 30, 30), (100, 180, 30, 30)], [[1], [2], [3]], 776, 400)`, and the same with numbers `[[], [2], []]` | `[(100, 82, '01'), (130, 140, '02'), (100, 210, '03')]` (above the second lies the first box, under it the third, so right of it); `[(130, 140, '02')]` (a box without numbers is in the way all the same) |
| CRP-11 | the same three boxes at `x` 740 | `[(740, 82, '01'), (714, 140, '02'), (740, 210, '03')]` (right of the second is off the tile, so left) |
| CRP-11 | `box_marks([(100, 100, 10, 10), (120, 100, 10, 10), (140, 100, 10, 10)], [[1], [2], [3]], 776, 400)` | `[(100, 82, '01'), (120, 110, '02'), (140, 82, '03')]` (above the second lies the mark of the first) |
| CRP-11 | `box_marks([(2, 2, 23, 23), (41, 2, 23, 23)], [[1], [2]], 776, 39)`, and with the second box at `x` 51 | `[(64, 2, '02')]` (the first has no free place: above and under are off the tile, right of it is the second box, left is off the tile); `[(25, 2, '01'), (74, 2, '02')]` |
| CRP-11 | `box_marks([(100, 0, 30, 400)], [[7]], 776, 400)`, `box_marks([(0, 191, 776, 19)], [[7]], 776, 400)` | `[(130, 0, '07')]`; `[(0, 173, '07')]` |
| CRP-11 | `box_marks([(0, 20, 10, 10)], [[1, 3, 5]], 90, 100)`, and the same on a tile 98 px wide | `[]` (`01 03 05` is 98 px wide); `[(0, 2, '01 03 05')]` |
| CRP-11 | `box_marks([(x, y, 20, 20) for y in (100, 130) for x in (100, 130, 160)], [[1], [2], [3], [4], [5], [6]], 776, 400)` | `[(100, 82, '01'), (130, 82, '02'), (160, 82, '03'), (100, 150, '04'), (130, 150, '05'), (160, 150, '06')]` |
| CRP-12 | `label_band('-', 20)` | 453 bytes; 40 pixel bytes are 0 (the 5 ones of `-` times four, and the 20 of row 21); pixels `(4, 10)`, `(13, 10)`, `(4, 11)` and `(13, 11)` are 0, `(4, 9)`, `(14, 10)` and `(4, 12)` are 255 |
| CRP-12 | `mark_image(70, 20, [(1, 1, '01-06')])` | 5667 bytes; of 1400 pixels 284 are `(0, 0, 0, 0)`, 844 `(255, 255, 255, 255)` and 272 `(255, 0, 255, 255)`; pixels `(27, 9)` and `(36, 10)` are magenta, `(27, 8)` and `(37, 9)` white |
| CRP-13 | argv `['clip.mp4', 'out']`, probe `(2.0, 160, 80)`, samples `two`, entries `FIRST`, `write_crops` returning `R` | `contact_sheets` called with the boxes `[[], [(11, 11, 34, 34), (91, 11, 34, 34)], [(11, 11, 34, 34)]]` and, as its sixth argument, the marks `[[], [(11, 45, '01'), (91, 45, '02')], [(11, 45, '03')]]` (a tile 160x80: no room above a box at `y` 11, so under it) |
| CRP-13 | the same with the probe `(2.0, 3200, 80)` | boxes `[[], [(-2, -2, 37, 17)], [(-2, -2, 17, 17)]]`, marks `[[], [(35, 0, '01-02')], [(15, 0, '03')]]` (a tile 776x19: the two changes of frame 1 are one box, and its mark names both crops) |
| CRP-13 | the probe `(2.0, 3200, 80)` row with `write_crops` returning `R6` | marks `[[], [(35, 0, '04 06')], [(15, 0, '12')]]`; the last two lines of stdout are `LC('out/crops-01.png, out/crops-01-02.png')` and `LS('out/screen-01-0.00s.jpg')`; in `frames.json` the `crop` of the events is `{"n": 4, "file": "crops-01.png"}`, `{"n": 6, "file": "crops-01.png"}`, `{"n": 12, "file": "crops-01-02.png"}` |
| CRP-13 | the probe `(2.0, 160, 80)` row with `write_crops` returning `R3` (one crop holding the events 0 and 1, its `tile` `None`; event 2 in no crop) | marks `[[], [(11, 45, '01')], []]` (the crop is numbered at the first of its two boxes, the box of the event without a crop has no number; the crop's `tile` is not read) |
| CRP-13 | the probe `(2.0, 160, 80)` row with `write_crops` returning `R4`; and with `write_crops` returning `R` and no entries named (all zero) | `contact_sheets` called with five arguments both times (no crop; no box) |
| CRP-13 | argv `['clip.mp4', 'out']`, samples `two`, entries `FIRST`, `write_crops` raising `MemoryError()`, raising `RuntimeError('boom')`, raising `KeyError('x')` | return 0 each time; stderr exactly `  crops not written: MemoryError\n`, `  crops not written: boom\n`, `  crops not written: 'x'\n`; `contact_sheets` called with five arguments, its boxes `[[], [(2, 2, 23, 23), (41, 2, 23, 23)], [(2, 2, 23, 23)]]`; stdout ends with the manifest line; `frames.json` written, without the keys of CRP-8 |
| CRP-13 | the same with `write_crops` returning `R` and `crop_units` raising `KeyError('x')` | return 0; stderr exactly `  crops not written: 'x'\n`; `write_crops` not called; `contact_sheets` called with five arguments; `frames.json` written, without the keys of CRP-8 |
| CRP-14 | directory `d` with `screen-shot-of-the-bug.jpg`, `force` false; with `crops-of-wheat.png` | `'<d> already holds screen-*.jpg from something else; pass --force to overwrite'`; `'<d> already holds crops-*.png from something else; pass --force to overwrite'`, `<d>` the string passed |
| CRP-14 | directory with `crops-01.png` and `screen-01.jpg`; with `frame-01.jpg` and `crops-01.png` | the `screen-*.jpg` message; the `frame-*.jpg` message (the first pattern in order) |
| CRP-14 | directory with `screen-01-0.00s.jpg` and `frames.json`; with `crops-of-wheat.png` and `force` true; with `screen.jpg`, `crops.png`, `crops-01.jpg`, `screen-01.png`, `crops.json` and `Screen-01.jpg` | `None` each time |
| CRP-14 | `out` exists with `crops-of-wheat.png` and no `frames.json`, argv `['clip.mp4', 'out']` | return 1, stderr exactly `out already holds crops-*.png from something else; pass --force to overwrite\n`, `probe` not called, the file still there |

### Errors (step 17)

`looks_same` and `box_marks` raise nothing on the inputs above. `looks_same` with pictures of different sizes and `box_marks` with lists of different lengths are undefined, do not test. `main()` survives every `Exception` of `crop_units` and `write_crops` (CRP-13); `KeyboardInterrupt` and `SystemExit` are not `Exception` and pass through, do not test. `check_out_dir` raises nothing. `contact_sheets` raises `ValueError` as CRP-16 says, reported by `main()` as in step 14.

## Step 18: a mark where the frame is empty (drafted and implemented 2026-10-04)

Why. A mark of step 17 takes the first free place around its box, above it when it can, and what is drawn there is hidden: the header of the column over a checkbox, the label next to it. The request after step 17 was for the number to stand where nothing is drawn. The cell means of every sample are in memory anyway (GRD-1), so the frame under a place is judged without decoding anything.

Measured on the 15 labeled recordings, 215 marks. A place is empty when none of its cells is busy (CRP-17). With step 17, 53 of the marks (24%) stand on an empty place and all of them together cover 4411 busy cells; with this step 116 (53%) and 1337. Every box with numbers has its mark before and after, 215 of 215: a mark that moves can take the last free place of a later box, which then gets none (CRP-11 step 4), and on these recordings that happens nowhere. Trying every place along the edges of a box, in steps of 4 px, gave 154 (71%) and 728, but put marks at the corners of boxes, where in a row of boxes a number reads as the neighbour's. Not taken: the places stay the four of CRP-11.

The code of this step exists. CRP-17 and CRP-18 are anchored (tests expected green).

CRP-17 (amends CRP-11) `box_marks(boxes, numbers, width, height, grid=None)`. `grid` is `None` or `(means, gw, native_width)`: the cell means of the frame the tile shows, `gw` values per row, as `change_grids` returns them for one sample (`bytes` or a `memoryview`), and the width in px of the frame they were taken from. With `grid` `None` or left out the result is that of CRP-11. With a grid, steps 1 to 3 of CRP-11 stay and step 4 becomes: the box gets the mark of the free place with the fewest busy cells, of several such the first in the order of step 2, and no mark when none of the four is free.
1. The cells of a place. A place `(px, py)` of a mark `mw` px wide covers the columns of the frame from `px * native_width // width` up to, not including, `ceil((px + mw) * native_width / width)`, and its rows from `py * native_width // width` up to, not including, `ceil((py + 18) * native_width / width)`. One factor serves both: a tile keeps the shape of the frame. The cells of the place are the cells `(column // CELL, row // CELL)` of those pixels that the grid holds, `column // CELL < gw` and `row // CELL < len(means) // gw`; the mean of cell `(c, r)` is `means[r * gw + c]`.
2. Busy cells. With the `n` means of those cells sorted in increasing order, `middle` is the one at index `(n - 1) // 2`. A cell is busy when its mean differs from `middle` by more than `HOLD_DELTA` (6 levels). A place with no cell in the grid has no busy cell.
       Why the middle of the place and not of the frame. A mark over a dark panel hides nothing as long as the panel is even under it; what counts is whether something is drawn within the place. Text leaves most cells at the background, so the middle is the background, and a place across the edge of a panel has many busy cells, as it should.
       Why the fewest and not none. On a dense screen no place around a box is empty. The mark is what links the box to its crop, so it goes where it hides the least.
       Why the same four places. See the measurement above: more places find more empty ones and loosen the tie between a number and its box.

CRP-18 (amends CRP-13 step 2) `main()` gives every frame its grid: the marks of frame `i` are `box_marks(boxes[i], numbers, tile_width, tile_height, (means, gw, width))`, with `means` the cell means of the sample `points[i]` as `change_grids` returned them, `gw` the grid width it returned and `width` the width the recording is analysed at. Everything else in CRP-13 stays. With samples whose means are all equal, as in every example row of the earlier steps, the marks are those of CRP-13.

### Examples (step 18)

`grid`, `box`, `two`, `FIRST`, `R` and the fakes as in the examples of steps 12, 16 and 17. `ink(...)` is `grid(box(...))`, a 20x10 grid of zeros with the cells of the box set, so a frame of 160x80 px. `C` is the box `(60, 30, 20, 20)`. On a tile 160x80 with `native_width` 160 the places for its mark `07` are: above `(60, 12)` over the cells of columns 7 to 10 and rows 1 to 3, under `(60, 50)` over columns 7 to 10 and rows 6 to 8, right `(80, 30)` over columns 10 to 13 and rows 3 to 5, left `(34, 30)` over columns 4 to 7 and rows 3 to 5. Unless a row says otherwise the call is `box_marks([C], [[7]], 160, 80, (g, 20, 160))` and the row names `g`. `inked` is `two` with the means of every sample replaced by `M = ink(2, 6, 2, 1, 90)`, that is `[(M, change) for _, change in two]`; `late` is `two` with the means of the last sample alone replaced by `M`.

| ID | Input | Result |
|---|---|---|
| CRP-17 | `grid({})`; the call with `None` in place of the grid; the call with four arguments | `[(60, 12, '07')]` each time |
| CRP-17 | `ink(8, 1, 2, 2, 100)`; the same as a `memoryview` | `[(60, 50, '07')]` both times (four busy cells above, none under) |
| CRP-17 | `grid(box(8, 1, 2, 2, 100) \| box(8, 7, 1, 1, 100))` | `[(80, 30, '07')]` (busy 4 above, 1 under, 0 right) |
| CRP-17 | `grid(box(8, 1, 2, 2, 100) \| box(7, 7, 3, 1, 100) \| box(11, 4, 2, 1, 100) \| box(5, 4, 1, 1, 100))` | `[(34, 30, '07')]` (busy 4, 3, 2 and 1: the fewest is left) |
| CRP-17 | `grid(box(8, 1, 2, 1, 100) \| box(8, 7, 2, 1, 100) \| box(11, 4, 3, 1, 100) \| box(5, 4, 3, 1, 100))` | `[(60, 12, '07')]` (busy 2, 2, 3 and 3: above is the first of the two) |
| CRP-17 | `grid(box(0, 0, 20, 4, 100) \| box(8, 7, 1, 1, 100))` | `[(60, 12, '07')]` (above lies wholly on the panel, no busy cell; 1 under, 4 and 4 at the sides) |
| CRP-17 | `grid(box(0, 0, 20, 2, 100) \| box(8, 7, 1, 1, 100))` | `[(80, 30, '07')]` (above lies across the panel's edge: 4 of its 12 cells are busy) |
| CRP-17 | `grid(box(7, 1, 4, 2, 100) \| box(8, 7, 1, 1, 100))` | `[(80, 30, '07')]` (8 of the 12 cells above are 100, so `middle` is 100 and the other 4 are busy) |
| CRP-17 | `ink(8, 1, 2, 2, 6)`; `ink(8, 1, 2, 2, 7)` | `[(60, 12, '07')]` (6 levels is not more than `HOLD_DELTA`); `[(60, 50, '07')]` |
| CRP-17 | `ink(8, 1, 2, 2, 100)` with every 0 replaced by 200 and the four cells set to 194; set to 193 | `[(60, 12, '07')]`; `[(60, 50, '07')]` (darker counts as lighter does) |
| CRP-17 | `box_marks([(30, 20, 10, 2)], [[7]], 80, 40, (g, 20, 160))` for `g` `ink(13, 4, 1, 1, 100)` and `ink(14, 4, 1, 1, 100)` | `[(30, 22, '07')]` (a tile at half the frame: above, `(30, 2)`, covers the columns 60 to 111 and the rows 4 to 39 of the frame, so the cells of columns 7 to 13 and rows 0 to 4); `[(30, 2, '07')]` |
| CRP-17 | `box_marks([(13, 20, 10, 2)], [[7]], 776, 388, (g, 20, 1600))` for `g` `ink(10, 2, 1, 1, 100)` and `ink(11, 2, 1, 1, 100)` | `[(13, 22, '07')]` (above, `(13, 2)`, ends at column `39 * 1600 / 776 = 80.4` of the frame, rounded up to 81, so it covers the columns 26 to 80 and with them the cells of column 10); `[(13, 2, '07')]` |
| CRP-17 | `box_marks([(13, 35, 10, 2)], [[7]], 776, 54, (g, 20, 1600))` for `g` `ink(4, 9, 1, 1, 100)` and `ink(4, 3, 1, 1, 100)` | `[(23, 35, '07')]` (under is off the tile; above, `(13, 17)`, covers the rows 35 to 72 of the frame, `35 * 1600 / 776 = 72.2` rounded up to 73, so the cells of rows 4 to 9; right of the box the cells of columns 5 to 12); `[(13, 17, '07')]` |
| CRP-17 | `box_marks([(150, 30, 20, 20)], [[7]], 320, 80, (grid(box(19, 2, 1, 1, 100) \| box(18, 7, 1, 1, 100) \| box(16, 4, 1, 1, 100)), 20, 320))` | `[(170, 30, '07')]` (busy 1 above, under and left; right of the box the grid holds no cell) |
| CRP-17 | `box_marks([(60, 60, 20, 20)], [[7]], 160, 160, (grid(box(8, 6, 1, 1, 100) \| box(11, 8, 1, 1, 100) \| box(6, 8, 1, 1, 100)), 20, 160))` | `[(60, 80, '07')]` (busy 1 above, right and left; under the box the grid holds no row) |
| CRP-17 | `box_marks([(60, 10, 20, 20), (60, 30, 20, 20), (60, 50, 20, 20)], [[], [2], []], 160, 80, (g, 20, 160))` for `g` `ink(10, 4, 2, 1, 100)` and `grid(box(10, 4, 1, 1, 100) \| box(5, 4, 2, 1, 100))` | `[(34, 30, '02')]` (above and under are boxes; right has 2 busy cells, left none); `[(80, 30, '02')]` (1 right, 2 left) |
| CRP-17 | `box_marks([(60, 30, 20, 20), (90, 30, 20, 20)], [[1], [2]], 160, 80, (ink(7, 1, 7, 2, 100), 20, 160))` | `[(60, 50, '01'), (90, 50, '02')]` |
| CRP-17 | `box_marks([C], [[1, 2, 3, 4, 5, 6]], 160, 80, (ink(8, 1, 2, 2, 100), 20, 160))`; `box_marks([C], [[]], 160, 80, (ink(8, 1, 2, 2, 100), 20, 160))` | `[(60, 50, '01-06')]`; `[]` |
| CRP-17 | `box_marks([(2, 2, 23, 23), (41, 2, 23, 23)], [[1], [2]], 776, 39, (grid({}), 20, 1600))` | `[(64, 2, '02')]` (a box with no free place has no mark, with a grid as without) |
| CRP-18 | argv `['clip.mp4', 'out']`, probe `(2.0, 160, 80)`, samples `inked`, entries `FIRST`, `write_crops` returning `R` | `contact_sheets` called with the boxes `[[], [(11, 11, 34, 34), (91, 11, 34, 34)], [(11, 11, 34, 34)]]` and the marks `[[], [(45, 11, '01'), (91, 45, '02')], [(45, 11, '03')]]` (under the box at `x` 11 two cells are busy, right of it none; with samples `two` the same call gives the marks of the CRP-13 row, `(11, 45, '01')` and `(11, 45, '03')`) |
| CRP-18 | the same with samples `late` | marks `[[], [(11, 45, '01'), (91, 45, '02')], [(45, 11, '03')]]` (each frame is judged by its own sample: the kept samples are 0, 4 and 6) |
| CRP-18 | the same with the probe `(2.0, 1600, 800)` and the means of every sample replaced by `ink(12, 7, 1, 1, 90)`; by `ink(6, 4, 1, 1, 90)` | boxes `[[], [(2, 2, 23, 23), (41, 2, 23, 23)], [(2, 2, 23, 23)]]` both times; marks `[[], [(2, 25, '01'), (64, 2, '02')], [(2, 25, '03')]]` (a tile 776x388 of a frame 1600 px wide: the place under the second box covers the cells of columns 10 to 17 and rows 6 to 9, cell `(12, 7)` among them, so its mark stands right of it); marks `[[], [(2, 25, '01'), (41, 25, '02')], [(2, 25, '03')]]` (cell `(6, 4)` lies under none of the places; with the tile's width taken for the frame's it would lie under `(41, 25)`) |

### Errors (step 18)

`box_marks` with a grid raises nothing on the inputs above. A `gw` or a `native_width` of 0 or less, and `means` whose length is not a multiple of `gw`, are undefined, do not test.
