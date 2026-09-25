# seenby_report

Status anchored (drafted and implemented 2026-09-17): RPT-1..16, RPT-P1. Written as a draft
before the code existed; the tester wrote red tests from it. Tests `tests/test_seenby_report.py`. Public
surface: `docs/specs/api/seenby_report.txt`.

## Purpose

`seenby_report.py` is the second script: it runs the core (`seenby.py`) as a subprocess through the
`frames.json` contract, decides from the audio level whether speech is worth transcribing, runs whisper only
then, and writes `report.md` next to the frames: one section per frame with the speech of its interval, the
whole speech with timecodes, and the reading rule. The core stays dependency-free; everything that needs
`faster-whisper` lives here, imported lazily.

## Vocabulary

- A speech segment is a dict `{"start": <float s>, "end": <float s>, "text": <str>, "avg_logprob": <float>}`.
  `start < end`. Lists of segments are ascending by `start`.
- A frame entry is an item of `frames.json`'s `frames` list (keys `n`, `time`, `file`, `sheet`, `reason`,
  `diff`, `block`, `recheck`), and the manifest is the whole `frames.json` dict as `seenby.py` writes it.
- "The core" is `seenby.py` in the same directory as `seenby_report.py`.
- Decibel values are floats; `-91.0` is ffmpeg's floor for silence.

## Public surface

    MIN_CORE_VERSION = 1
    MAX_DB = -45.0
    MEAN_DB = -80.0
    SHAKY = -0.7
    TOLERANCE = 2.0
    MODEL = 'large-v3-turbo'
    def core_path()
    def run_core(video, out_dir, tail)                     [hands-on]
    def load_manifest(out_dir)
    def parse_volume(text)
    def measure_volume(video)                              [hands-on]
    def needs_transcription(mean_db, max_db, anyway)
    def transcribe(video, model, device='auto')            [hands-on]
    def coverage(segments, duration)
    def frame_intervals(frames, end)
    def speech_for(interval, segments)
    def render(manifest, speech, audio, model_info)
    def main()

`tests/` reach the module with `import seenby_report` from the repository root, like `seenby`.

## Rules

### Running the core (contract a4)

RPT-1  `core_path()` is `os.path.join(<directory of seenby_report.py>, 'seenby.py')`, the absolute path of the
       core next to the wrapper, whatever the current directory.
       Why. The wrapper must not depend on PATH or on a `python3` by name.

RPT-2  [hands-on] `run_core(video, out_dir, tail)` runs `[sys.executable, core_path(), video, out_dir, *tail]`
       with `capture_output=True, text=True` and returns `(returncode, stdout, stderr)`. Nothing is printed
       by `run_core` itself. Evidence: a run on a real recording, in the maintainer's plan notes.

RPT-3  `main()` parses its own options with `parse_known_args()` and passes every unknown argument to the core
       verbatim, in order, as `tail`. Its own options: `video` (positional), `out_dir` (positional, optional,
       default `<video without extension>-frames`, the same rule as the core), `--model` (str, default `MODEL`),
       `--transcribe-anyway` (flag), `--device` (`auto`, `cuda` or `cpu`, default `auto`). Everything else, for
       example `--max-frames 12 --from 10`, reaches the core untouched. `--help` exits 0 and its stdout names
       the three options and says that other options go to the core.
       Why. The core grows options every step; a forwarding list would break on the first new one.

RPT-4  `main()` removes `<out_dir>/report.md` before calling `run_core`, when it exists, so a failed run never
       leaves last time's report.

RPT-5  When `run_core` returns a non-zero code `N`, `main()` prints `seenby.py exited N` and the last non-empty
       line of the core's stderr (`seenby.py exited N: <last non-empty stderr line>`, or just `seenby.py exited
       N` when stderr is blank) to stderr and returns `N`. A missing video file is the core's business: it
       refuses with code 1 and this rule relays it. The core's stdout
       is not printed in that case, no manifest is read, no audio is measured.

RPT-6  On a zero code `main()` prints the core's stdout unchanged, then continues.

RPT-7  `load_manifest(out_dir)` reads `<out_dir>/frames.json` and returns the dict. It raises `ValueError` with
       message `no frames.json in <out_dir>` when the file is missing, and
       `needs core version >= <MIN_CORE_VERSION>, found <version>` when the manifest's `version` is below
       `MIN_CORE_VERSION`. `main()` prints that message to stderr and returns 1.
       Why. `version` is a contract, not decoration.

### Audio gate

RPT-8  `parse_volume(text)` takes the stderr of `ffmpeg -i <video> -af volumedetect -f null -` and returns
       `(mean_db, max_db)` from the lines containing `mean_volume:` and `max_volume:` (`[Parsed_volumedetect_0
       @ 0x...] mean_volume: -53.7 dB`). Raises `ValueError` with a message containing `volumedetect` when
       either line is missing.

RPT-9  [hands-on] `measure_volume(video)` returns `(-91.0, -91.0)` (ffmpeg's silence floor) when ffprobe finds
       no audio stream, otherwise runs that ffmpeg command and returns `parse_volume(stderr)`. Screen captures
       often have no audio track at all; that is silence, not an error. `--transcribe-anyway` on such a
       recording reaches `transcribe`, which prints `no audio track in <video>, nothing to transcribe` to
       stderr and returns `([], {"language": "none", "language_probability": 0.0, "device": "none", "model":
       <model>})` without loading a model, so the report's Speech section reads `(nothing transcribed)`
       (hands-on; `main()` itself never calls ffprobe, the tests fake `measure_volume` and `transcribe`).
       Evidence: on the nine silent recordings mean is `-91.0`, max `-84.3` or `-91.0`; on
       the one recording with an audio track mean `-53.7`, max `-31.3`. That recording turned out to be steady background noise
       (RMS about -55 dB throughout), not speech: `small` transcribes nothing, `large-v3` and `large-v3-turbo`
       each hallucinate one short segment. The gate lets it through; the report's language probability and
       `(?)` marks are what tell the reader. No recording with real speech exists yet (open question).

RPT-10 `needs_transcription(mean_db, max_db, anyway)` is `True` when `anyway` is true, else when
       `max_db > MAX_DB and mean_db > MEAN_DB` (both strict). The thresholds come from a single recording with
       speech; they are marked `[unverified]` in the README and the report line.
       Why. Loading a whisper model for a silent screen recording wastes seconds and, on a laptop, the battery.

### Transcription

RPT-11 [hands-on] `transcribe(video, model, device='auto')` imports `faster_whisper` inside the function; when
       the import fails it raises `ImportError` whose message is `faster-whisper is not installed: pip install
       -r requirements-whisper.txt`, and `main()` prints that and returns 1 without touching `out_dir` beyond
       the core's own files. With `device` `auto` or `cuda` it loads `WhisperModel(model, device='cuda',
       compute_type='float16')` and, when that raises and `device` is `auto`, falls back to `device='cpu',
       compute_type='int8'`; with `device` `cpu` it goes to cpu int8 directly.
       It calls `model.transcribe(video, beam_size=5, vad_filter=False, condition_on_previous_text=False)` and
       returns `(segments, info)` where `segments` is the list of speech segments (dicts as in Vocabulary, in
       order) and `info` is `{"language": <str>, "language_probability": <float>, "device": <str>, "model":
       <str>}`. Evidence: a run on the one recording with an audio track, in the maintainer's plan notes.

RPT-12 `coverage(segments, duration)` returns `(end, truncated)` where `end` is the largest segment `end`
       (`0.0` for no segments) and `truncated` is `duration - end > TOLERANCE`.
       Why. Whisper stops silently on long files (F71 in the logger project); the report must say so rather
       than let the reader guess. On a screen recording the gap is just as often silence or noise, so the
       report line names all three causes and never says "truncated" as a fact.

### Binding speech to frames

RPT-13 `frame_intervals(frames, end)` returns one `(start, stop)` pair per frame entry, in order: `start` is the
       frame's `time`, `stop` is the next frame's `time`, and the last frame's `stop` is `end` (the analysed
       end, `analysis.range.to`). For one frame the single pair is `(time, end)`.

RPT-14 `speech_for(interval, segments)` returns the segments that overlap `interval = (start, stop)`, in
       order, as `(segment, continued)` pairs: a segment overlaps when `segment.start < stop and segment.end
       > start`; `continued` is true when `segment.start < start` (it began in an earlier interval). A
       segment that spans a frame boundary therefore appears under both frames, the second time marked
       continued.
       Why. A sentence cut at a frame boundary is worth reading twice rather than losing under either frame.

### The report

RPT-15 `render(manifest, speech, audio, model_info)` returns the Markdown text of `report.md`. `speech` is the
       segment list or `None` when nothing was transcribed; `audio` is `(mean_db, max_db)`; `model_info` is the
       `info` dict from `transcribe` or `None`. The text is, in this order (`<...>` filled from the manifest):

           # seenby report: <video.name>

           <video.duration %.1f> s, <video.width>x<video.height>, <video.grade>. <len(frames)> frames on <sheet.count> sheets. seenby <version>, <ffmpeg>.
           Range <analysis.range.from %.1f>-<analysis.range.to %.1f> s.                       (only when analysis.range.from > 0 or analysis.range.to < video.duration)
           All frames were taken by the timer; the threshold contributed nothing (effective <analysis.threshold.effective %.1f>). Try --max-frames, --block-k or --from/--to.   (only when analysis.all_timer)
           Audio: mean <mean_db %.1f> dB, max <max_db %.1f> dB. No speech expected (gate -45/-80 dB, unverified); pass --transcribe-anyway to transcribe.   (when speech is None)
           Audio: mean <mean_db %.1f> dB, max <max_db %.1f> dB. Speech transcribed with <model_info.model> on <model_info.device>, language <language> (<language_probability %.2f>).   (when speech is a list)
           Speech covers <end %.1f> of <duration %.1f> s; the last <duration - end %.1f> s have no transcript (silence, noise, or whisper stopping early).   (only when truncated)

           Sheets: <sheets[i].file> (frames <first>-<last>), ...          (or `Sheets: none (one frame)` when sheets is empty)

           ## Frames

           ### <n %02d> - <time %.1f> s (<reason>)                                             (for reason first)
           ### <n %02d> - <time %.1f> s (<reason>, diff <diff %.1f>, block <block %.1f>)      (for every other reason)
           - [<start %.1f>-<end %.1f>] <text>                                                 (one per overlapping segment; append ` (continued)` when continued; append ` (?)` when avg_logprob < SHAKY)
           (no speech in this interval)                                                       (when speech is a list and no segment overlaps)

           ## Speech                                                                          (section present only when speech is a list)

           - [<start %.1f>-<end %.1f>] <text>                                                 (every segment, ` (?)` when shaky)
           (nothing transcribed)                                                              (when the list is empty)

           ## Reading rule

           Sheets are for meaning; read digits from the native frame. Each frame's `recheck` command in frames.json extracts it, for example:

               <frames[0].recheck>

       Blank lines separate the header lines, each frame block, and the sections. Frame blocks list their
       speech lines right under the heading. The full text ends with a newline.

RPT-16 `main()` order on success: RPT-4, `run_core`, RPT-6, `load_manifest`, `measure_volume`,
       `needs_transcription`, `transcribe` when needed, `coverage` against `video.duration` (whisper reads the
       whole file, whatever `--from/--to` the core got; the rendered coverage line uses `video.duration` too),
       `render`, write `<out_dir>/report.md`
       (through the core's `write` semantics: text written as UTF-8), print `  report: <out_dir>/report.md` as
       the last stdout line, return 0. `measure_volume` raising `ValueError` -> stderr line with its message,
       return 1, no report. When `needs_transcription` is false, `transcribe` is not called and the report has
       no Speech section.

## Examples

For `main()` rows the tests replace `seenby_report.run_core` (returns `(0, 'core stdout\n', '')` and writes a
manifest into `out_dir` unless the row says otherwise), `seenby_report.measure_volume` (returns `(-91.0, -91.0)`
unless the row says otherwise) and `seenby_report.transcribe` (returns `([], {...})` unless the row says
otherwise) through `monkeypatch.setattr`, with `sys.argv = ['seenby_report.py'] + argv` and
`monkeypatch.chdir(tmp_path)`. `MANIFEST` below is a minimal valid manifest:
`{"tool": "seenby", "version": 1, "ffmpeg": "ffmpeg version 6.1.1-test", "video": {"name": "clip.mp4", "path":
"clip.mp4", "duration": 15.0, "width": 800, "height": 600, "ratio": 1.333, "orientation": "landscape", "grade":
"window"}, "analysis": {"sample_fps": 2.0, "thumbnails": 30, "max_frames": 24, "threshold": {"requested": 12.0,
"effective": 12.0}, "max_gap": {"requested": 3.0, "effective": 3.0}, "block_k": 5.0, "range": {"from": 0.0, "to":
15.0}, "segment": 120.0, "all_timer": false}, "sheet": {"cols": 3, "rows": 3, "tile_width": 516, "sheet_width":
1568, "count": 1}, "frames": [F1, F2, F3], "sheets": [{"file": "sheet-01.jpg", "frames": [1, 3]}], "segments":
[{"n": 1, "from": 0.0, "to": 15.0, "frames": [1, 2, 3]}]}` with
`F1 = {"n": 1, "time": 0.0, "file": "frame-01-0.0s.jpg", "sheet": 1, "reason": "first", "diff": 0.0, "block": 0.0,
"recheck": "ffmpeg -ss 0.000 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-01-native.jpg"}`,
`F2 = {..., "n": 2, "time": 5.0, "file": "frame-02-5.0s.jpg", "reason": "diff", "diff": 14.2, "block": 40.0, ...}`,
`F3 = {..., "n": 3, "time": 12.0, "file": "frame-03-12.0s.jpg", "reason": "last", "diff": 0.4, "block": 1.0, ...}`.
`SPEECH` is `[{"start": 1.0, "end": 4.0, "text": "hello", "avg_logprob": -0.3}, {"start": 4.5, "end": 6.0,
"text": "cut here", "avg_logprob": -0.9}, {"start": 9.0, "end": 13.5, "text": "the end", "avg_logprob": -0.2}]`
and `INFO` is `{"language": "en", "language_probability": 0.98, "device": "cuda", "model": "large-v3-turbo"}`.

| ID | Input | Result |
|---|---|---|
| RPT-1 | `core_path()` | ends with `/seenby.py` and its directory is the directory of `seenby_report.__file__`; `os.path.isfile` is true in this repository |
| RPT-3 | argv `['clip.mp4', 'out', '--max-frames', '12', '--model', 'small', '--from', '10']` | `run_core` called with `('clip.mp4', 'out', ['--max-frames', '12', '--from', '10'])`; `transcribe` (when reached) gets model `'small'` |
| RPT-3 | argv `['clip.mp4']` | `run_core` called with `('clip.mp4', 'clip-frames', [])` |
| RPT-3 | argv `['--help']` | `SystemExit` code 0, stdout contains `--model`, `--transcribe-anyway`, `--device`, `seenby.py` |
| RPT-4 | `out/report.md` exists with text `old`; `run_core` fake returns `(1, '', 'boom')` | return 1, `out/report.md` does not exist |
| RPT-5 | `run_core` fake returns `(2, 'ignored', 'usage\nseenby.py: error: bad')` | return 2, stderr contains `seenby.py exited 2: seenby.py: error: bad`, stdout does not contain `ignored`, `measure_volume` not called |
| RPT-5 | `run_core` fake returns `(1, '', 'no such file: nope.mp4\n')` (trailing newline, as the real core writes) | return 1, stderr contains `seenby.py exited 1: no such file: nope.mp4` |
| RPT-5 | `run_core` fake returns `(1, '', '')` | return 1, stderr contains `seenby.py exited 1` and no `: ` after it on that line |
| RPT-5 | `run_core` fake returns `(1, '', 'x\n\n  \n')` | return 1, stderr contains `seenby.py exited 1: x` |
| RPT-6, RPT-16 | `run_core` returns `(0, 'core stdout\n', '')` and writes MANIFEST | return 0; stdout starts with `core stdout\n` and its last line is `  report: out/report.md`; `out/report.md` exists |
| RPT-7 | `load_manifest('out')` with no file | `ValueError`, message `no frames.json in out` |
| RPT-7 | manifest with `"version": 0` | `load_manifest` raises `ValueError` with message `needs core version >= 1, found 0`; `main()` prints it to stderr and returns 1 |
| RPT-7 | `run_core` returns 0 but writes no manifest | return 1, stderr contains `no frames.json in out` |
| RPT-8 | `parse_volume("[Parsed_volumedetect_0 @ 0x55] n_samples: 100\n[Parsed_volumedetect_0 @ 0x55] mean_volume: -53.7 dB\n[Parsed_volumedetect_0 @ 0x55] max_volume: -31.3 dB\n")` | `(-53.7, -31.3)` |
| RPT-8 | `parse_volume("mean_volume: -91.0 dB\nmax_volume: -91.0 dB\n")` | `(-91.0, -91.0)` |
| RPT-8 | `parse_volume("")`, `parse_volume("mean_volume: -53.7 dB\n")` | each `ValueError`, message contains `volumedetect` |
| RPT-10 | `needs_transcription(-53.7, -31.3, False)` | `True` |
| RPT-10 | `needs_transcription(-91.0, -91.0, False)` | `False` |
| RPT-10 | `needs_transcription(-91.0, -91.0, True)` | `True` |
| RPT-10 | `needs_transcription(-85.0, -40.0, False)` | `False` (mean not above -80) |
| RPT-10 | `needs_transcription(-70.0, -45.0, False)` | `False` (max equal to -45 is not above) |
| RPT-10 | `needs_transcription(-79.9, -44.9, False)` | `True` |
| RPT-12 | `coverage(SPEECH, 15.0)` | `(13.5, False)` |
| RPT-12 | `coverage(SPEECH, 16.0)` | `(13.5, True)` (2.5 above the tolerance) |
| RPT-12 | `coverage(SPEECH, 15.5)` | `(13.5, False)` (2.0 is not above) |
| RPT-12 | `coverage([], 15.0)` | `(0.0, True)` |
| RPT-12 | `coverage([], 1.5)` | `(0.0, False)` |
| RPT-13 | `frame_intervals([F1, F2, F3], 15.0)` | `[(0.0, 5.0), (5.0, 12.0), (12.0, 15.0)]` |
| RPT-13 | `frame_intervals([F1], 15.0)` | `[(0.0, 15.0)]` |
| RPT-14 | `speech_for((0.0, 5.0), SPEECH)` | `[(SPEECH[0], False), (SPEECH[1], False)]` |
| RPT-14 | `speech_for((5.0, 12.0), SPEECH)` | `[(SPEECH[1], True), (SPEECH[2], False)]` |
| RPT-14 | `speech_for((12.0, 15.0), SPEECH)` | `[(SPEECH[2], True)]` |
| RPT-14 | `speech_for((13.5, 15.0), SPEECH)` | `[]` (a segment ending exactly at the interval start does not overlap) |
| RPT-14 | `speech_for((6.0, 9.0), SPEECH)` | `[]` |
| RPT-15 | `render(MANIFEST, None, (-91.0, -91.0), None)` | exactly: `# seenby report: clip.mp4` / blank / `15.0 s, 800x600, window. 3 frames on 1 sheets. seenby 1, ffmpeg version 6.1.1-test.` / `Audio: mean -91.0 dB, max -91.0 dB. No speech expected (gate -45/-80 dB, unverified); pass --transcribe-anyway to transcribe.` / blank / `Sheets: sheet-01.jpg (frames 1-3)` / blank / `## Frames` / blank / `### 01 - 0.0 s (first)` / blank / `### 02 - 5.0 s (diff, diff 14.2, block 40.0)` / blank / `### 03 - 12.0 s (last, diff 0.4, block 1.0)` / blank / `## Reading rule` / blank / `Sheets are for meaning; read digits from the native frame. Each frame's \`recheck\` command in frames.json extracts it, for example:` / blank / `    ffmpeg -ss 0.000 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-01-native.jpg` and a final newline; no `## Speech` section |
| RPT-15 | `render(MANIFEST, SPEECH, (-53.7, -31.3), INFO)` | the audio line is `Audio: mean -53.7 dB, max -31.3 dB. Speech transcribed with large-v3-turbo on cuda, language en (0.98).`; no TRUNCATED line (13.5 of 15.0); frame 01 lines `- [1.0-4.0] hello` and `- [4.5-6.0] cut here (?)`; frame 02 lines `- [4.5-6.0] cut here (continued) (?)` and `- [9.0-13.5] the end`; frame 03 line `- [9.0-13.5] the end (continued)`; a `## Speech` section with the three lines `- [1.0-4.0] hello`, `- [4.5-6.0] cut here (?)`, `- [9.0-13.5] the end`, then `## Reading rule` |
| RPT-15 | `render(MANIFEST with video.duration 16.0 and range.to 16.0, SPEECH, (-53.7, -31.3), INFO)` | contains the line `Speech covers 13.5 of 16.0 s; the last 2.5 s have no transcript (silence, noise, or whisper stopping early).` |
| RPT-15 | `render(MANIFEST, [], (-53.7, -31.3), INFO)` | every frame block has `(no speech in this interval)`; the Speech section has `(nothing transcribed)`; the coverage line says `Speech covers 0.0 of 15.0 s; the last 15.0 s have no transcript (silence, noise, or whisper stopping early).` |
| RPT-15 | `render(MANIFEST with analysis.all_timer true and threshold.effective 205.0, None, (-91.0, -91.0), None)` | contains `All frames were taken by the timer; the threshold contributed nothing (effective 205.0). Try --max-frames, --block-k or --from/--to.` right after the first header line |
| RPT-15 | `render(MANIFEST with range {"from": 10.0, "to": 25.0} and duration 60.0, None, ...)` | contains `Range 10.0-25.0 s.` after the first header line |
| RPT-15 | `render(MANIFEST with sheets [] and sheet.count 0 and one frame, None, ...)` | contains `Sheets: none (one frame)` |
| RPT-16 | `measure_volume` fake returns `(-53.7, -31.3)`, `transcribe` fake returns `(SPEECH, INFO)` | `transcribe` called with `('clip.mp4', 'large-v3-turbo', 'auto')`; `out/report.md` equals `render(MANIFEST, SPEECH, (-53.7, -31.3), INFO)`; return 0 |
| RPT-3, RPT-16 | argv `['clip.mp4', 'out', '--model', 'small', '--device', 'cpu']`, `measure_volume` `(-53.7, -31.3)` | `transcribe` called with `('clip.mp4', 'small', 'cpu')` |
| RPT-16 | `measure_volume` returns `(-91.0, -91.0)` | `transcribe` not called; `out/report.md` equals `render(MANIFEST, None, (-91.0, -91.0), None)` |
| RPT-16 | argv `['clip.mp4', 'out', '--transcribe-anyway']`, `measure_volume` returns `(-91.0, -91.0)` | `transcribe` called |
| RPT-16 | `measure_volume` fake raises `ValueError('no volumedetect output')` | return 1, stderr contains `no volumedetect output`, no `out/report.md` |
| RPT-11, RPT-16 | `transcribe` fake raises `ImportError('faster-whisper is not installed: pip install -r requirements-whisper.txt')` with `measure_volume` `(-53.7, -31.3)` | return 1, stderr contains `pip install -r requirements-whisper.txt`, no `out/report.md`, the core's files untouched |

## Properties

RPT-P1  For `frames` a list of 1..20 entries with strictly increasing `time` floats in `[0, 100)` and `end` a
        float above the last `time` and at most 120.0, and `segments` a list of 0..20 segments with
        `start < end` in `[0, 120]`: `frame_intervals` pairs are contiguous and end at `end`; every segment
        that overlaps `[frames[0].time, end)` appears in `speech_for` of at least one interval; on its first
        appearance in interval order `continued` is `segment.start < frames[0].time` (RPT-14's definition:
        a segment that began before the first frame is already "continued"), and on every later appearance
        `continued` is true.

## Errors

- `load_manifest`, `parse_volume`: `ValueError` as stated. `transcribe`: `ImportError` as stated; other
  exceptions from faster-whisper propagate (hands-on).
- `main`: returns the core's code (RPT-5), 1 for RPT-7, RPT-11, RPT-16 failures, 0 otherwise. `SystemExit(2)`
  for a missing `video`.
- The device fallback (RPT-11) is hands-on. A `--device` value other than `auto`, `cuda`, `cpu` is an argparse
  error, code 2.

## Amendment 2026-09-25: the all-timer sentence (implemented 2026-09-26)

Why. The sentence pointed to `--max-frames` also when the cap was not binding, where that option changes nothing; on a wide light recording the knob that helped was `--threshold` (`docs/specs/seenby.md`, step 10). Whether a lower threshold helps depends on the largest change, which the manifest does not hold, so the report does not advise it and points to the core's console line, which `main()` prints unchanged (RPT-6).

RPT-17 (amends RPT-15, the "All frames were taken by the timer" sentence only) When `analysis.threshold.effective` equals `analysis.threshold.requested` and `analysis.max_gap.effective` equals `analysis.max_gap.requested`, the sentence is `All frames were taken by the timer; the threshold contributed nothing (effective <analysis.threshold.effective %.1f>). The seenby.py console output says whether a lower --threshold would keep more.` Otherwise it is exactly as RPT-15 has it.

| ID | Input | Result |
|---|---|---|
| RPT-17 | `render(MANIFEST with analysis.all_timer true, None, (-91.0, -91.0), None)` (threshold 12.0 -> 12.0, gap 3.0 -> 3.0) | contains `All frames were taken by the timer; the threshold contributed nothing (effective 12.0). The seenby.py console output says whether a lower --threshold would keep more.` and not `Try` |
| RPT-17 | `render(MANIFEST with analysis.all_timer true and max_gap.effective 5.0, None, (-91.0, -91.0), None)` (threshold 12.0 -> 12.0) | contains `All frames were taken by the timer; the threshold contributed nothing (effective 12.0). Try --max-frames, --block-k or --from/--to.` |
| RPT-17, RPT-15 | the RPT-15 row with `threshold.effective` 205.0 | unchanged |
