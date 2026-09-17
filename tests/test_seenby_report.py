"""Acceptance tests for seenby_report, written from docs/specs/seenby_report.md (draft, plan step 6).

The module is imported inside each test through `report_module()` so that a missing module fails the test
itself, not collection. The import happens before any `chdir`, because the repository root reaches sys.path
only as the current directory.
"""

import copy
import importlib
import json
import os
import sys

import pytest
from hypothesis import given, settings, strategies as st


def report_module():
    return importlib.import_module("seenby_report")


# ---------------------------------------------------------------- fixtures from the spec's Examples

F1 = {
    "n": 1,
    "time": 0.0,
    "file": "frame-01-0.0s.jpg",
    "sheet": 1,
    "reason": "first",
    "diff": 0.0,
    "block": 0.0,
    "recheck": "ffmpeg -ss 0.000 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-01-native.jpg",
}
F2 = {
    "n": 2,
    "time": 5.0,
    "file": "frame-02-5.0s.jpg",
    "sheet": 1,
    "reason": "diff",
    "diff": 14.2,
    "block": 40.0,
    "recheck": "ffmpeg -ss 5.000 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-02-native.jpg",
}
F3 = {
    "n": 3,
    "time": 12.0,
    "file": "frame-03-12.0s.jpg",
    "sheet": 1,
    "reason": "last",
    "diff": 0.4,
    "block": 1.0,
    "recheck": "ffmpeg -ss 12.000 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-03-native.jpg",
}

MANIFEST = {
    "tool": "seenby",
    "version": 1,
    "ffmpeg": "ffmpeg version 6.1.1-test",
    "video": {
        "name": "clip.mp4",
        "path": "clip.mp4",
        "duration": 15.0,
        "width": 800,
        "height": 600,
        "ratio": 1.333,
        "orientation": "landscape",
        "grade": "window",
    },
    "analysis": {
        "sample_fps": 2.0,
        "thumbnails": 30,
        "max_frames": 24,
        "threshold": {"requested": 12.0, "effective": 12.0},
        "max_gap": {"requested": 3.0, "effective": 3.0},
        "block_k": 5.0,
        "range": {"from": 0.0, "to": 15.0},
        "segment": 120.0,
        "all_timer": False,
    },
    "sheet": {"cols": 3, "rows": 3, "tile_width": 516, "sheet_width": 1568, "count": 1},
    "frames": [F1, F2, F3],
    "sheets": [{"file": "sheet-01.jpg", "frames": [1, 3]}],
    "segments": [{"n": 1, "from": 0.0, "to": 15.0, "frames": [1, 2, 3]}],
}

SPEECH = [
    {"start": 1.0, "end": 4.0, "text": "hello", "avg_logprob": -0.3},
    {"start": 4.5, "end": 6.0, "text": "cut here", "avg_logprob": -0.9},
    {"start": 9.0, "end": 13.5, "text": "the end", "avg_logprob": -0.2},
]

INFO = {"language": "en", "language_probability": 0.98, "device": "cuda", "model": "large-v3-turbo"}

LOUD = (-53.7, -31.3)
SILENT = (-91.0, -91.0)


def manifest_with(*changes):
    """Deep copy of MANIFEST with `("dotted.path", value)` changes applied."""
    result = copy.deepcopy(MANIFEST)
    for path, value in changes:
        target = result
        *parents, leaf = path.split(".")
        for key in parents:
            target = target[key]
        target[leaf] = value
    return result


# ---------------------------------------------------------------- expected report texts (RPT-15)

TITLE = "# seenby report: clip.mp4"
HEADER = "15.0 s, 800x600, window. 3 frames on 1 sheets. seenby 1, ffmpeg version 6.1.1-test."
AUDIO_SILENT = (
    "Audio: mean -91.0 dB, max -91.0 dB. No speech expected (gate -45/-80 dB, unverified); "
    "pass --transcribe-anyway to transcribe."
)
AUDIO_LOUD = "Audio: mean -53.7 dB, max -31.3 dB. Speech transcribed with large-v3-turbo on cuda, language en (0.98)."
SHEETS = "Sheets: sheet-01.jpg (frames 1-3)"
HEADING_1 = "### 01 - 0.0 s (first)"
HEADING_2 = "### 02 - 5.0 s (diff, diff 14.2, block 40.0)"
HEADING_3 = "### 03 - 12.0 s (last, diff 0.4, block 1.0)"
READING_RULE = [
    "## Reading rule",
    "",
    "Sheets are for meaning; read digits from the native frame. Each frame's `recheck` command in frames.json "
    "extracts it, for example:",
    "",
    "    ffmpeg -ss 0.000 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-01-native.jpg",
]
ALL_TIMER = (
    "All frames were taken by the timer; the threshold contributed nothing (effective 205.0). "
    "Try --max-frames, --block-k or --from/--to."
)
NO_SPEECH = "(no speech in this interval)"


def text_of(lines):
    return "\n".join(lines) + "\n"


REPORT_SILENT = text_of(
    [TITLE, "", HEADER, AUDIO_SILENT, "", SHEETS, "", "## Frames", "", HEADING_1, "", HEADING_2, "", HEADING_3, ""]
    + READING_RULE
)

REPORT_SPEECH = text_of(
    [
        TITLE,
        "",
        HEADER,
        AUDIO_LOUD,
        "",
        SHEETS,
        "",
        "## Frames",
        "",
        HEADING_1,
        "- [1.0-4.0] hello",
        "- [4.5-6.0] cut here (?)",
        "",
        HEADING_2,
        "- [4.5-6.0] cut here (continued) (?)",
        "- [9.0-13.5] the end",
        "",
        HEADING_3,
        "- [9.0-13.5] the end (continued)",
        "",
        "## Speech",
        "",
        "- [1.0-4.0] hello",
        "- [4.5-6.0] cut here (?)",
        "- [9.0-13.5] the end",
        "",
    ]
    + READING_RULE
)

REPORT_EMPTY_SPEECH = text_of(
    [
        TITLE,
        "",
        HEADER,
        AUDIO_LOUD,
        "Speech covers 0.0 of 15.0 s; the last 15.0 s have no transcript (silence, noise, or whisper stopping early).",
        "",
        SHEETS,
        "",
        "## Frames",
        "",
        HEADING_1,
        NO_SPEECH,
        "",
        HEADING_2,
        NO_SPEECH,
        "",
        HEADING_3,
        NO_SPEECH,
        "",
        "## Speech",
        "",
        "(nothing transcribed)",
        "",
    ]
    + READING_RULE
)


# ---------------------------------------------------------------- main() harness


def outcome(value):
    if isinstance(value, BaseException):
        raise value
    return value


def snapshot(directory):
    if not os.path.isdir(directory):
        return None
    return {name: open(os.path.join(directory, name), "rb").read() for name in sorted(os.listdir(directory))}


class Run:
    """Fakes for run_core, measure_volume and transcribe, recording the calls main() makes.

    `run_core` returns `core` and writes `manifest` (plus the sheet and frame files it names) into the out_dir
    it was called with, unless `manifest` is None. `volume` and `speech` are returned by their fake, or raised
    when they are exceptions.
    """

    def __init__(self, monkeypatch, rpt, core, manifest, volume, speech):
        self.core_calls = []
        self.volume_calls = []
        self.transcribe_calls = []
        self.report_seen_by_core = None
        self.core_files = None

        def fake_run_core(video, out_dir, tail):
            self.core_calls.append((video, out_dir, tail))
            self.report_seen_by_core = os.path.exists(os.path.join(out_dir, "report.md"))
            if manifest is not None:
                os.makedirs(out_dir, exist_ok=True)
                with open(os.path.join(out_dir, "frames.json"), "w", encoding="utf-8") as fh:
                    json.dump(manifest, fh)
                for entry in manifest.get("sheets", []) + manifest.get("frames", []):
                    with open(os.path.join(out_dir, entry["file"]), "wb") as fh:
                        fh.write(b"jpeg")
                self.core_files = snapshot(out_dir)
            return core

        def fake_measure_volume(video):
            self.volume_calls.append(video)
            return outcome(volume)

        def fake_transcribe(video, model, device="auto"):
            self.transcribe_calls.append((video, model, device))
            return outcome(speech)

        monkeypatch.setattr(rpt, "run_core", fake_run_core)
        monkeypatch.setattr(rpt, "measure_volume", fake_measure_volume)
        monkeypatch.setattr(rpt, "transcribe", fake_transcribe)


def run_main(
    monkeypatch,
    capsys,
    tmp_path,
    argv,
    core=(0, "core stdout\n", ""),
    manifest=MANIFEST,
    volume=SILENT,
    speech=([], INFO),
    before=None,
):
    rpt = report_module()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "clip.mp4").write_bytes(b"")
    if before is not None:
        before(tmp_path)
    run = Run(monkeypatch, rpt, core, manifest, volume, speech)
    monkeypatch.setattr(sys, "argv", ["seenby_report.py"] + argv)
    run.rc = rpt.main()
    captured = capsys.readouterr()
    run.out = captured.out
    run.err = captured.err
    run.rpt = rpt
    return run


def report_text(out_dir="out"):
    with open(os.path.join(out_dir, "report.md"), encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------- RPT-1 core_path


@pytest.mark.spec("RPT-1")
def test_rpt_1_core_path_is_seenby_py_next_to_the_wrapper():
    rpt = report_module()
    path = rpt.core_path()
    assert os.path.isabs(path)
    assert path.endswith("/seenby.py")
    assert os.path.dirname(path) == os.path.dirname(os.path.abspath(rpt.__file__))
    assert os.path.isfile(path)


@pytest.mark.spec("RPT-1")
def test_rpt_1_core_path_does_not_depend_on_the_current_directory(monkeypatch, tmp_path):
    rpt = report_module()
    at_root = rpt.core_path()
    monkeypatch.chdir(tmp_path)
    assert rpt.core_path() == at_root
    assert os.path.isfile(rpt.core_path())


# ---------------------------------------------------------------- RPT-3 options and forwarding


@pytest.mark.spec("RPT-3")
def test_rpt_3_model_default_is_large_v3_turbo():
    assert report_module().MODEL == "large-v3-turbo"


@pytest.mark.spec("RPT-3")
def test_rpt_3_unknown_options_reach_the_core_in_order_and_model_is_taken_out(monkeypatch, capsys, tmp_path):
    argv = ["clip.mp4", "out", "--max-frames", "12", "--model", "small", "--from", "10"]
    run = run_main(monkeypatch, capsys, tmp_path, argv, volume=LOUD, speech=(SPEECH, INFO))
    assert run.rc == 0
    assert run.core_calls == [("clip.mp4", "out", ["--max-frames", "12", "--from", "10"])]
    assert run.transcribe_calls == [("clip.mp4", "small", "auto")]


@pytest.mark.spec("RPT-3")
def test_rpt_3_default_out_dir_is_the_video_name_with_frames(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4"])
    assert run.rc == 0
    assert run.core_calls == [("clip.mp4", "clip-frames", [])]
    assert run.out.splitlines()[-1] == "  report: clip-frames/report.md"
    assert os.path.isfile(os.path.join("clip-frames", "report.md"))


@pytest.mark.spec("RPT-3")
def test_rpt_3_help_names_the_three_options_and_the_core(monkeypatch, capsys):
    rpt = report_module()
    monkeypatch.setattr(sys, "argv", ["seenby_report.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        rpt.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for needle in ("--model", "--transcribe-anyway", "--device", "seenby.py"):
        assert needle in out


@pytest.mark.spec("RPT-3")
@pytest.mark.parametrize("argv", [[], ["clip.mp4", "out", "--device", "gpu"]])
def test_rpt_3_missing_video_or_unknown_device_is_an_argparse_error(monkeypatch, capsys, tmp_path, argv):
    rpt = report_module()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["seenby_report.py"] + argv)
    with pytest.raises(SystemExit) as exc:
        rpt.main()
    assert exc.value.code == 2


# ---------------------------------------------------------------- RPT-4, RPT-5, RPT-6 around run_core


def stale_report(tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "report.md").write_text("old", encoding="utf-8")


@pytest.mark.spec("RPT-4")
@pytest.mark.spec("RPT-5")
def test_rpt_4_last_report_is_removed_before_the_core_runs_and_a_failed_run_leaves_none(
    monkeypatch, capsys, tmp_path
):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], core=(1, "", "boom"), manifest=None, before=stale_report
    )
    assert run.rc == 1
    assert run.report_seen_by_core is False
    assert not os.path.exists(os.path.join("out", "report.md"))
    assert "seenby.py exited 1: boom" in run.err


@pytest.mark.spec("RPT-5")
def test_rpt_5_non_zero_core_exit_is_reported_with_the_last_stderr_line(monkeypatch, capsys, tmp_path):
    core = (2, "ignored", "usage\nseenby.py: error: bad")
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], core=core, manifest=None)
    assert run.rc == 2
    assert "seenby.py exited 2: seenby.py: error: bad" in run.err
    assert "ignored" not in run.out
    assert "no frames.json" not in run.err
    assert run.volume_calls == []
    assert run.transcribe_calls == []


@pytest.mark.spec("RPT-5")
@pytest.mark.parametrize(
    "stderr, expected",
    [
        ("no such file: nope.mp4\n", "seenby.py exited 1: no such file: nope.mp4"),
        ("x\n\n  \n", "seenby.py exited 1: x"),
    ],
)
def test_rpt_5_last_non_empty_stderr_line_is_relayed(monkeypatch, capsys, tmp_path, stderr, expected):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], core=(1, "", stderr), manifest=None)
    assert run.rc == 1
    assert expected in run.err


@pytest.mark.spec("RPT-5")
def test_rpt_5_blank_stderr_gives_the_exit_line_alone(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], core=(1, "", ""), manifest=None)
    assert run.rc == 1
    lines = [line for line in run.err.splitlines() if "seenby.py exited 1" in line]
    assert len(lines) == 1
    assert ": " not in lines[0].split("seenby.py exited 1", 1)[1]


@pytest.mark.spec("RPT-6")
@pytest.mark.spec("RPT-16")
def test_rpt_6_16_core_stdout_is_printed_first_and_the_report_line_last(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"])
    assert run.rc == 0
    assert run.out.startswith("core stdout\n")
    assert run.out.splitlines()[-1] == "  report: out/report.md"
    assert os.path.isfile(os.path.join("out", "report.md"))


# ---------------------------------------------------------------- RPT-7 load_manifest


@pytest.mark.spec("RPT-7")
def test_rpt_7_min_core_version_is_one():
    assert report_module().MIN_CORE_VERSION == 1


@pytest.mark.spec("RPT-7")
def test_rpt_7_load_manifest_returns_the_dict(monkeypatch, tmp_path):
    rpt = report_module()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "frames.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    assert rpt.load_manifest("out") == MANIFEST


@pytest.mark.spec("RPT-7")
def test_rpt_7_missing_manifest_raises_value_error(monkeypatch, tmp_path):
    rpt = report_module()
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError) as exc:
        rpt.load_manifest("out")
    assert str(exc.value) == "no frames.json in out"


@pytest.mark.spec("RPT-7")
def test_rpt_7_old_core_version_raises_value_error(monkeypatch, tmp_path):
    rpt = report_module()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "frames.json").write_text(json.dumps(manifest_with(("version", 0))), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rpt.load_manifest("out")
    assert str(exc.value) == "needs core version >= 1, found 0"


@pytest.mark.spec("RPT-7")
def test_rpt_7_main_reports_an_old_core_version_and_returns_one(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], manifest=manifest_with(("version", 0)))
    assert run.rc == 1
    assert "needs core version >= 1, found 0" in run.err
    assert not os.path.exists(os.path.join("out", "report.md"))


@pytest.mark.spec("RPT-7")
def test_rpt_7_main_reports_a_missing_manifest_and_returns_one(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], manifest=None)
    assert run.rc == 1
    assert "no frames.json in out" in run.err
    assert not os.path.exists(os.path.join("out", "report.md"))


# ---------------------------------------------------------------- RPT-8 parse_volume


@pytest.mark.spec("RPT-8")
@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "[Parsed_volumedetect_0 @ 0x55] n_samples: 100\n"
            "[Parsed_volumedetect_0 @ 0x55] mean_volume: -53.7 dB\n"
            "[Parsed_volumedetect_0 @ 0x55] max_volume: -31.3 dB\n",
            (-53.7, -31.3),
        ),
        ("mean_volume: -91.0 dB\nmax_volume: -91.0 dB\n", (-91.0, -91.0)),
    ],
)
def test_rpt_8_parse_volume_reads_mean_and_max(text, expected):
    assert report_module().parse_volume(text) == expected


@pytest.mark.spec("RPT-8")
@pytest.mark.parametrize("text", ["", "mean_volume: -53.7 dB\n"])
def test_rpt_8_parse_volume_raises_when_a_line_is_missing(text):
    rpt = report_module()
    with pytest.raises(ValueError) as exc:
        rpt.parse_volume(text)
    assert "volumedetect" in str(exc.value)


# ---------------------------------------------------------------- RPT-10 needs_transcription


@pytest.mark.spec("RPT-10")
def test_rpt_10_gate_thresholds():
    rpt = report_module()
    assert rpt.MAX_DB == -45.0
    assert rpt.MEAN_DB == -80.0


@pytest.mark.spec("RPT-10")
@pytest.mark.parametrize(
    "mean_db, max_db, anyway, expected",
    [
        (-53.7, -31.3, False, True),
        (-91.0, -91.0, False, False),
        (-91.0, -91.0, True, True),
        (-85.0, -40.0, False, False),
        (-70.0, -45.0, False, False),
        (-79.9, -44.9, False, True),
    ],
)
def test_rpt_10_needs_transcription_is_strict_on_both_thresholds(mean_db, max_db, anyway, expected):
    assert report_module().needs_transcription(mean_db, max_db, anyway) is expected


# ---------------------------------------------------------------- RPT-12 coverage


@pytest.mark.spec("RPT-12")
def test_rpt_12_tolerance_is_two_seconds():
    assert report_module().TOLERANCE == 2.0


@pytest.mark.spec("RPT-12")
@pytest.mark.parametrize(
    "segments, duration, expected",
    [
        (SPEECH, 15.0, (13.5, False)),
        (SPEECH, 16.0, (13.5, True)),
        (SPEECH, 15.5, (13.5, False)),
        ([], 15.0, (0.0, True)),
        ([], 1.5, (0.0, False)),
    ],
)
def test_rpt_12_coverage_is_the_last_end_and_whether_the_gap_exceeds_tolerance(segments, duration, expected):
    assert report_module().coverage(segments, duration) == expected


# ---------------------------------------------------------------- RPT-13 frame_intervals


@pytest.mark.spec("RPT-13")
@pytest.mark.parametrize(
    "frames, end, expected",
    [
        ([F1, F2, F3], 15.0, [(0.0, 5.0), (5.0, 12.0), (12.0, 15.0)]),
        ([F1], 15.0, [(0.0, 15.0)]),
    ],
)
def test_rpt_13_frame_intervals_run_from_each_time_to_the_next_and_end_at_end(frames, end, expected):
    assert report_module().frame_intervals(frames, end) == expected


# ---------------------------------------------------------------- RPT-14 speech_for


@pytest.mark.spec("RPT-14")
@pytest.mark.parametrize(
    "interval, expected",
    [
        ((0.0, 5.0), [(SPEECH[0], False), (SPEECH[1], False)]),
        ((5.0, 12.0), [(SPEECH[1], True), (SPEECH[2], False)]),
        ((12.0, 15.0), [(SPEECH[2], True)]),
        ((13.5, 15.0), []),
        ((6.0, 9.0), []),
    ],
)
def test_rpt_14_speech_for_returns_overlapping_segments_marked_continued(interval, expected):
    assert report_module().speech_for(interval, SPEECH) == expected


# ---------------------------------------------------------------- RPT-P1 binding property


def frame_entry(n, time):
    return {
        "n": n,
        "time": time,
        "file": f"frame-{n:02d}-{time:.1f}s.jpg",
        "sheet": 1,
        "reason": "diff",
        "diff": 20.0,
        "block": 50.0,
        "recheck": f"ffmpeg -ss {time:.3f} -i clip.mp4 -frames:v 1 -q:v 2 out/frame-{n:02d}-native.jpg",
    }


@st.composite
def binding_inputs(draw):
    times = sorted(
        draw(
            st.lists(
                st.floats(min_value=0.0, max_value=100.0, exclude_max=True), min_size=1, max_size=20, unique=True
            )
        )
    )
    frames = [frame_entry(i + 1, t) for i, t in enumerate(times)]
    end = draw(st.floats(min_value=times[-1], max_value=120.0, exclude_min=True))
    bounds = draw(
        st.lists(
            st.lists(st.floats(min_value=0.0, max_value=120.0), min_size=2, max_size=2, unique=True).map(sorted),
            min_size=0,
            max_size=20,
        )
    )
    segments = [
        {"start": a, "end": b, "text": f"segment {i}", "avg_logprob": -0.3}
        for i, (a, b) in enumerate(sorted(bounds))
    ]
    return frames, end, segments


@pytest.mark.spec("RPT-P1")
@settings(deadline=None)
@given(inputs=binding_inputs())
def test_rpt_p1_intervals_tile_the_range_and_every_overlapping_segment_appears_once_unmarked(inputs):
    rpt = report_module()
    frames, end, segments = inputs
    intervals = rpt.frame_intervals(frames, end)
    assert len(intervals) == len(frames)
    assert [start for start, _ in intervals] == [f["time"] for f in frames]
    assert all(a[1] == b[0] for a, b in zip(intervals, intervals[1:]))
    assert intervals[-1][1] == end

    first_time = frames[0]["time"]
    appearances = {}
    for interval in intervals:
        for segment, continued in rpt.speech_for(interval, segments):
            appearances.setdefault(segments.index(segment), []).append(continued)
    for i, segment in enumerate(segments):
        if segment["start"] < end and segment["end"] > first_time:
            first, *later = appearances[i]
            assert first == (segment["start"] < first_time)
            assert all(later)


# ---------------------------------------------------------------- RPT-15 render


@pytest.mark.spec("RPT-15")
def test_rpt_15_shaky_threshold():
    assert report_module().SHAKY == -0.7


@pytest.mark.spec("RPT-15")
def test_rpt_15_silent_report_text_is_exact():
    assert report_module().render(MANIFEST, None, SILENT, None) == REPORT_SILENT


@pytest.mark.spec("RPT-15")
def test_rpt_15_transcribed_report_text_is_exact():
    assert report_module().render(MANIFEST, SPEECH, LOUD, INFO) == REPORT_SPEECH


@pytest.mark.spec("RPT-15")
def test_rpt_15_empty_transcript_report_text_is_exact():
    assert report_module().render(MANIFEST, [], LOUD, INFO) == REPORT_EMPTY_SPEECH


@pytest.mark.spec("RPT-15")
def test_rpt_15_coverage_line_follows_the_audio_line():
    manifest = manifest_with(("video.duration", 16.0), ("analysis.range.to", 16.0))
    lines = report_module().render(manifest, SPEECH, LOUD, INFO).splitlines()
    assert lines[3] == AUDIO_LOUD
    assert lines[4] == (
        "Speech covers 13.5 of 16.0 s; the last 2.5 s have no transcript (silence, noise, or whisper stopping early)."
    )
    assert lines[5] == ""


@pytest.mark.spec("RPT-15")
def test_rpt_15_all_timer_line_follows_the_first_header_line():
    manifest = manifest_with(("analysis.all_timer", True), ("analysis.threshold.effective", 205.0))
    lines = report_module().render(manifest, None, SILENT, None).splitlines()
    assert lines[2] == HEADER
    assert lines[3] == ALL_TIMER
    assert lines[4] == AUDIO_SILENT


@pytest.mark.spec("RPT-15")
@pytest.mark.parametrize(
    "changes, header, range_line",
    [
        (
            (("analysis.range.from", 10.0), ("analysis.range.to", 25.0), ("video.duration", 60.0)),
            "60.0 s, 800x600, window. 3 frames on 1 sheets. seenby 1, ffmpeg version 6.1.1-test.",
            "Range 10.0-25.0 s.",
        ),
        ((("analysis.range.to", 12.0),), HEADER, "Range 0.0-12.0 s."),
    ],
)
def test_rpt_15_range_line_follows_the_first_header_line_when_the_range_is_narrower(changes, header, range_line):
    lines = report_module().render(manifest_with(*changes), None, SILENT, None).splitlines()
    assert lines[2] == header
    assert lines[3] == range_line
    assert lines[4] == AUDIO_SILENT


@pytest.mark.spec("RPT-15")
def test_rpt_15_no_sheets_says_one_frame():
    manifest = manifest_with(("sheets", []), ("sheet.count", 0), ("frames", [F1]))
    lines = report_module().render(manifest, None, SILENT, None).splitlines()
    assert "Sheets: none (one frame)" in lines
    assert lines[lines.index("## Frames") + 2] == HEADING_1


@pytest.mark.spec("RPT-15")
def test_rpt_15_sheets_line_lists_every_sheet_with_its_frame_range():
    sheets = [{"file": "sheet-01.jpg", "frames": [1, 2]}, {"file": "sheet-02.jpg", "frames": [3, 3]}]
    manifest = manifest_with(("sheets", sheets), ("sheet.count", 2))
    lines = report_module().render(manifest, None, SILENT, None).splitlines()
    assert lines[2] == "15.0 s, 800x600, window. 3 frames on 2 sheets. seenby 1, ffmpeg version 6.1.1-test."
    assert "Sheets: sheet-01.jpg (frames 1-2), sheet-02.jpg (frames 3-3)" in lines


@pytest.mark.spec("RPT-15")
@pytest.mark.parametrize(
    "avg_logprob, line",
    [(-0.7, "- [1.0-4.0] hello"), (-0.8, "- [1.0-4.0] hello (?)"), (-0.3, "- [1.0-4.0] hello")],
)
def test_rpt_15_question_mark_only_below_shaky(avg_logprob, line):
    segment = {"start": 1.0, "end": 4.0, "text": "hello", "avg_logprob": avg_logprob}
    lines = report_module().render(MANIFEST, [segment], LOUD, INFO).splitlines()
    assert lines[lines.index(HEADING_1) + 1] == line
    assert lines[lines.index("## Speech") + 2] == line


# ---------------------------------------------------------------- RPT-16 main() end to end


@pytest.mark.spec("RPT-16")
def test_rpt_16_speech_is_transcribed_with_the_default_model_and_written_to_the_report(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], volume=LOUD, speech=(SPEECH, INFO))
    assert run.rc == 0
    assert run.volume_calls == ["clip.mp4"]
    assert run.transcribe_calls == [("clip.mp4", "large-v3-turbo", "auto")]
    assert report_text() == run.rpt.render(MANIFEST, SPEECH, LOUD, INFO)
    assert run.out.splitlines()[-1] == "  report: out/report.md"


@pytest.mark.spec("RPT-3")
@pytest.mark.spec("RPT-16")
def test_rpt_3_16_model_and_device_options_reach_transcribe(monkeypatch, capsys, tmp_path):
    argv = ["clip.mp4", "out", "--model", "small", "--device", "cpu"]
    run = run_main(monkeypatch, capsys, tmp_path, argv, volume=LOUD, speech=(SPEECH, INFO))
    assert run.rc == 0
    assert run.core_calls == [("clip.mp4", "out", [])]
    assert run.transcribe_calls == [("clip.mp4", "small", "cpu")]


@pytest.mark.spec("RPT-16")
def test_rpt_16_silent_audio_skips_transcription_and_the_speech_section(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], volume=SILENT)
    assert run.rc == 0
    assert run.transcribe_calls == []
    text = report_text()
    assert text == run.rpt.render(MANIFEST, None, SILENT, None)
    assert "## Speech" not in text


@pytest.mark.spec("RPT-16")
def test_rpt_16_transcribe_anyway_overrides_the_gate(monkeypatch, capsys, tmp_path):
    argv = ["clip.mp4", "out", "--transcribe-anyway"]
    run = run_main(monkeypatch, capsys, tmp_path, argv, volume=SILENT, speech=(SPEECH, INFO))
    assert run.rc == 0
    assert run.transcribe_calls == [("clip.mp4", "large-v3-turbo", "auto")]
    assert report_text() == run.rpt.render(MANIFEST, SPEECH, SILENT, INFO)


@pytest.mark.spec("RPT-16")
def test_rpt_16_report_is_written_as_utf8(monkeypatch, capsys, tmp_path):
    speech = [{"start": 1.0, "end": 4.0, "text": "café, naïve, Zürich", "avg_logprob": -0.3}]
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], volume=LOUD, speech=(speech, INFO))
    assert run.rc == 0
    raw = open(os.path.join("out", "report.md"), "rb").read()
    assert raw.decode("utf-8") == run.rpt.render(MANIFEST, speech, LOUD, INFO)
    assert "- [1.0-4.0] café, naïve, Zürich" in raw.decode("utf-8")


@pytest.mark.spec("RPT-16")
def test_rpt_16_volume_failure_returns_one_without_a_report(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], volume=ValueError("no volumedetect output")
    )
    assert run.rc == 1
    assert "no volumedetect output" in run.err
    assert run.transcribe_calls == []
    assert not os.path.exists(os.path.join("out", "report.md"))


@pytest.mark.spec("RPT-11")
@pytest.mark.spec("RPT-16")
def test_rpt_11_16_missing_faster_whisper_returns_one_and_leaves_the_core_files(monkeypatch, capsys, tmp_path):
    error = ImportError("faster-whisper is not installed: pip install -r requirements-whisper.txt")
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], volume=LOUD, speech=error)
    assert run.rc == 1
    assert "pip install -r requirements-whisper.txt" in run.err
    assert not os.path.exists(os.path.join("out", "report.md"))
    assert snapshot("out") == run.core_files
