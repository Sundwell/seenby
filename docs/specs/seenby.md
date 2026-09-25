# seenby

Status anchored for SEL-1..6, CAP-1..9, CLN-1, CLN-3..4, ENV-1..2, CLI-1, CLI-3..4, CLI-6..7, CLI-9..13,
CLI-15..17, CLI-19..20, CLI-22, REC-2..9, PRB-1..3, TOOL-1..3, DIR-1..2, JSN-1..3, MAN-1..4, MAN-7..13, MAN-15,
BLK-1..2, LAY-1..6, SEG-1..4, FF-1..7 (code exists, tests green).
CLI-23 anchored 2026-09-17 (the "by the timer" line triggers on an active cap alone; supersedes CLI-22).
Removed: CLN-2, CLI-2, CLI-5, CLI-8, CLI-14, CLI-18, CLI-21, CLI-22, REC-1, MAN-5, MAN-6, MAN-14 (each names
its successor). Sections keep the heading of the step that
introduced them so the IDs stay where they were born. Tests `tests/test_seenby.py`. Public surface:
`docs/specs/api/seenby.txt`.

## Purpose

Picks the frames of a screen recording an agent should look at: a thumbnail is kept when it differs from the
last kept one, is forced every `max_gap` seconds, and the last one is always kept. A cap on the number of frames
raises the threshold instead of cutting the tail. ffmpeg does the decoding and the contact sheets.

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
       `frames.json`, or `force` is true.
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
- Nothing else new raises. The alternatives in CLI-22 use `fit_to_cap`, so they terminate when it does.

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
