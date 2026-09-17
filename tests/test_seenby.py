"""Acceptance tests for seenby, written from docs/specs/seenby.md and docs/specs/api/seenby.txt."""

import json
import math
import os
import shlex
import subprocess
import sys
from itertools import product

import pytest
from hypothesis import given, settings, strategies as st

import seenby

T = seenby.THRESHOLD
G = seenby.MAX_GAP
FPS = seenby.SAMPLE_FPS
SIZE = seenby.THUMB * seenby.THUMB


def flat(v):
    return bytes([v]) * SIZE


def static(n):
    return [flat(0)] * n


def alt(n):
    return [flat(255 if i % 2 else 0) for i in range(n)]


def half(v):
    return bytes([0]) * (SIZE // 2) + bytes([v]) * (SIZE // 2)


def ramp():
    return [flat(v) for v in (0, 5, 10, 15, 20, 25, 30, 35, 40, 45)]


def last_time(thumbs):
    return (len(thumbs) - 1) / FPS


def grid(cells):
    """Thumbnail from a set of (row, col, value) cells, everything else 0."""
    pixels = bytearray(SIZE)
    for row, col, value in cells:
        pixels[row * seenby.THUMB + col] = value
    return bytes(pixels)


def patch(v):
    return grid((r, c, v) for r in range(8) for c in range(8))


def straddle(v):
    return grid((r, c, v) for r in range(8) for c in range(4, 12))


def pixel(v):
    return grid([(0, 0, v)])


def blocky():
    return [flat(0), patch(100)] * 10


thumbs_st = st.lists(st.binary(min_size=1024, max_size=1024), min_size=0, max_size=60)
threshold_st = st.floats(min_value=0.1, max_value=300.0)
max_gap_st = st.floats(min_value=0.5, max_value=30.0)
max_frames_st = st.integers(min_value=2, max_value=30)
block_k_st = st.floats(min_value=0.0, max_value=10.0)


# ---------------------------------------------------------------- select


@pytest.mark.spec("SEL-1")
def test_sel_1_empty_thumbs_gives_empty_list():
    assert seenby.select([], T, G) == []


@pytest.mark.spec("SEL-2")
@pytest.mark.spec("SEL-5")
def test_sel_2_sel_5_single_thumbnail_gives_only_zero():
    assert seenby.select(static(1), T, G) == [0.0]


@pytest.mark.spec("SEL-2")
@pytest.mark.parametrize(
    "thumbs",
    [static(20), alt(20), [flat(0), flat(200), flat(0)], [flat(255)] * 3],
)
def test_sel_2_result_starts_with_first_thumbnail(thumbs):
    assert seenby.select(thumbs, T, G)[0] == 0.0


@pytest.mark.spec("SEL-3")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap, expected",
    [
        ([flat(0), flat(12), flat(13), flat(13)], T, 100.0, [0.0, 1.0, 1.5]),
        ([flat(0), half(24), half(26), flat(0)], T, 100.0, [0.0, 1.0, 1.5]),
        (ramp(), T, 100.0, [0.0, 1.5, 3.0, 4.5]),
        (alt(4), 300.0, 100.0, [0.0, 1.5]),
        (alt(20), T, G, [i / 2 for i in range(20)]),
    ],
)
def test_sel_3_kept_when_difference_against_last_kept_exceeds_threshold(thumbs, threshold, max_gap, expected):
    assert seenby.select(thumbs, threshold, max_gap) == expected


@pytest.mark.spec("SEL-3")
def test_sel_3_difference_equal_to_threshold_does_not_keep():
    assert seenby.select([flat(0), flat(12), flat(0), flat(0)], T, 100.0) == [0.0, 1.5]


@pytest.mark.spec("SEL-4")
@pytest.mark.spec("SEL-5")
@pytest.mark.parametrize(
    "thumbs, expected",
    [
        (static(20), [0.0, 3.0, 6.0, 9.0, 9.5]),
        (static(7), [0.0, 3.0]),
    ],
)
def test_sel_4_frame_forced_every_max_gap_on_static_input(thumbs, expected):
    assert seenby.select(thumbs, T, G) == expected


@pytest.mark.spec("SEL-4")
def test_sel_4_forced_frame_follows_max_gap_argument():
    assert seenby.select(static(30), T, 7.0) == [0.0, 7.0, 14.0, 14.5]


@pytest.mark.spec("SEL-5")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap, expected",
    [
        (static(20), T, G, [0.0, 3.0, 6.0, 9.0, 9.5]),
        (static(7), T, G, [0.0, 3.0]),
        (alt(4), 300.0, 100.0, [0.0, 1.5]),
        (static(1), T, G, [0.0]),
    ],
)
def test_sel_5_last_thumbnail_always_kept_once(thumbs, threshold, max_gap, expected):
    result = seenby.select(thumbs, threshold, max_gap)
    assert result == expected
    assert result[-1] == last_time(thumbs)
    assert result.count(last_time(thumbs)) == 1


@pytest.mark.spec("SEL-6")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap",
    [
        (static(20), T, G),
        (static(7), T, G),
        (alt(20), T, G),
        (alt(4), 300.0, 100.0),
        (ramp(), T, 100.0),
        (static(240), T, 5.859375),
    ],
)
def test_sel_6_times_are_increasing_half_seconds_within_range(thumbs, threshold, max_gap):
    result = seenby.select(thumbs, threshold, max_gap)
    assert result
    assert all(a < b for a, b in zip(result, result[1:]))
    assert all(t * FPS == int(t * FPS) for t in result)
    assert all(0.0 <= t <= last_time(thumbs) for t in result)


@pytest.mark.spec("SEL-P1")
@pytest.mark.spec("SEL-6")
@settings(deadline=None)
@given(thumbs=thumbs_st, threshold=threshold_st, max_gap=max_gap_st)
def test_sel_p1_shape_of_result(thumbs, threshold, max_gap):
    result = seenby.select(thumbs, threshold, max_gap)
    assert all(a < b for a, b in zip(result, result[1:]))
    assert (result == []) == (thumbs == [])
    if thumbs:
        assert result[0] == 0.0
        assert result[-1] == last_time(thumbs)
        assert all(t * FPS == int(t * FPS) for t in result)


@pytest.mark.spec("SEL-P2")
@settings(deadline=None)
@given(thumbs=thumbs_st, threshold=threshold_st)
def test_sel_p2_max_gap_half_second_keeps_every_thumbnail(thumbs, threshold):
    assert len(seenby.select(thumbs, threshold, 0.5)) == len(thumbs)


# ---------------------------------------------------------------- fit_to_cap


@pytest.mark.spec("CAP-6")
def test_cap_6_empty_thumbs_returns_empty_and_unchanged_parameters():
    assert seenby.fit_to_cap([], 24, T, G) == ([], 12.0, 3.0)


@pytest.mark.spec("CAP-2")
@pytest.mark.parametrize(
    "thumbs, expected_times",
    [
        (static(20), [0.0, 3.0, 6.0, 9.0, 9.5]),
        (alt(20), [i / 2 for i in range(20)]),
    ],
)
def test_cap_2_selection_within_cap_returns_unchanged_parameters(thumbs, expected_times):
    times, threshold, max_gap = seenby.fit_to_cap(thumbs, 24, T, G)
    assert times == expected_times
    assert times == seenby.select(thumbs, T, G)
    assert threshold == 12.0
    assert max_gap == 3.0


@pytest.mark.spec("CAP-3")
@pytest.mark.spec("CAP-5")
def test_cap_3_cap_5_gap_stretched_by_repeated_product_and_tail_kept():
    times, threshold, max_gap = seenby.fit_to_cap(static(240), 24, T, G)
    assert times == [0.0] + [float(t) for t in range(6, 115, 6)] + [119.5]
    assert len(times) == 21
    assert threshold == 12.0
    assert max_gap == 5.859375


@pytest.mark.spec("CAP-3")
def test_cap_3_returned_gap_is_the_fewest_multiplications_that_fit():
    _, _, max_gap = seenby.fit_to_cap(static(240), 24, T, G)
    gap = G
    while len(seenby.select(static(240), 256.0, gap)) > 24:
        gap = gap * 1.25
    assert max_gap == gap
    assert len(seenby.select(static(240), 256.0, gap / 1.25)) > 24


@pytest.mark.spec("CAP-5")
def test_cap_5_static_120_seconds_ends_at_last_thumbnail():
    times, _, _ = seenby.fit_to_cap(static(240), 24, T, G)
    assert times[-1] == 119.5
    assert 115.0 not in times


@pytest.mark.spec("CAP-4")
@pytest.mark.parametrize(
    "thumbs, max_frames, expected",
    [
        (alt(20), 5, ([0.0, 3.0, 6.0, 9.0, 9.5], 307.546875, 3.0)),
        (alt(20), 8, ([0.0, 3.0, 6.0, 9.0, 9.5], 307.546875, 3.0)),
    ],
)
def test_cap_4_threshold_raised_by_repeated_product_until_it_fits(thumbs, max_frames, expected):
    times, threshold, max_gap = seenby.fit_to_cap(thumbs, max_frames, T, G)
    assert (times, threshold, max_gap) == expected
    assert times == seenby.select(thumbs, threshold, max_gap)


@pytest.mark.spec("CAP-4")
def test_cap_4_returned_threshold_is_the_fewest_multiplications_that_fit():
    _, threshold, max_gap = seenby.fit_to_cap(alt(20), 5, T, G)
    value = T
    while len(seenby.select(alt(20), value, max_gap)) > 5:
        value = value * 1.5
    assert threshold == value
    assert len(seenby.select(alt(20), value / 1.5, max_gap)) > 5


@pytest.mark.spec("CAP-1")
@pytest.mark.spec("CAP-4")
def test_cap_1_cap_4_result_under_the_cap_is_not_padded():
    times, threshold, max_gap = seenby.fit_to_cap(alt(20), 8, T, G)
    assert len(times) <= 8
    assert times == [0.0, 3.0, 6.0, 9.0, 9.5]
    assert (threshold, max_gap) == (307.546875, 3.0)


@pytest.mark.spec("CAP-1")
@pytest.mark.parametrize("max_frames", [2, 3, 5, 8, 24])
def test_cap_1_never_more_than_max_frames(max_frames):
    times, _, _ = seenby.fit_to_cap(alt(60), max_frames, T, G)
    assert len(times) <= max_frames


@pytest.mark.spec("CAP-3")
@pytest.mark.spec("CAP-4")
def test_cap_3_cap_4_cap_of_two_stretches_gap_then_threshold():
    assert seenby.fit_to_cap(alt(20), 2, T, G) == ([0.0, 9.5], 307.546875, 9.1552734375)


@pytest.mark.spec("CAP-P1")
@settings(deadline=None)
@given(thumbs=thumbs_st, max_frames=max_frames_st, threshold=threshold_st, max_gap=max_gap_st)
def test_cap_p1_fits_and_parameters_only_grow(thumbs, max_frames, threshold, max_gap):
    times, out_threshold, out_gap = seenby.fit_to_cap(thumbs, max_frames, threshold, max_gap)
    assert len(times) <= max_frames
    assert out_threshold >= threshold
    assert out_gap >= max_gap
    assert times == seenby.select(thumbs, out_threshold, out_gap)


@pytest.mark.spec("CAP-P2")
@settings(deadline=None)
@given(
    thumbs=st.lists(st.binary(min_size=1024, max_size=1024), min_size=2, max_size=60),
    max_frames=max_frames_st,
)
def test_cap_p2_first_and_last_thumbnail_survive_the_cap(thumbs, max_frames):
    times, _, _ = seenby.fit_to_cap(thumbs, max_frames, T, G)
    assert times[0] == 0.0
    assert times[-1] == last_time(thumbs)


# ---------------------------------------------------------------- select_frames

ENTRY_KEYS = {"time", "diff", "block", "reason"}
REASONS = ("first", "diff", "block", "timer", "last")


def entry(time, diff, block, reason):
    return {"time": time, "diff": diff, "block": block, "reason": reason}


def static_20_entries():
    return [
        entry(0.0, 0.0, 0.0, "first"),
        entry(3.0, 0.0, 0.0, "timer"),
        entry(6.0, 0.0, 0.0, "timer"),
        entry(9.0, 0.0, 0.0, "timer"),
        entry(9.5, 0.0, 0.0, "last"),
    ]


@pytest.mark.spec("REC-2")
@pytest.mark.spec("REC-4")
@pytest.mark.spec("REC-5")
@pytest.mark.spec("REC-7")
def test_rec_2_4_5_7_static_input_first_timers_then_last():
    assert seenby.select_frames(static(20), T, G) == static_20_entries()


@pytest.mark.spec("REC-3")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap, expected",
    [
        (
            ramp(),
            T,
            100.0,
            [
                entry(0.0, 0.0, 0.0, "first"),
                entry(1.5, 15.0, 15.0, "diff"),
                entry(3.0, 15.0, 15.0, "diff"),
                entry(4.5, 15.0, 15.0, "diff"),
            ],
        ),
        (
            [flat(0), flat(12), flat(13), flat(13)],
            T,
            100.0,
            [entry(0.0, 0.0, 0.0, "first"), entry(1.0, 13.0, 13.0, "diff"), entry(1.5, 0.0, 0.0, "last")],
        ),
        (static(6) + [flat(255)], T, G, [entry(0.0, 0.0, 0.0, "first"), entry(3.0, 255.0, 255.0, "diff")]),
    ],
)
def test_rec_3_diff_reason_carries_the_difference_and_beats_the_timer(thumbs, threshold, max_gap, expected):
    assert seenby.select_frames(thumbs, threshold, max_gap) == expected


@pytest.mark.spec("REC-4")
def test_rec_4_timer_reason_on_static_seven():
    assert seenby.select_frames(static(7), T, G) == [entry(0.0, 0.0, 0.0, "first"), entry(3.0, 0.0, 0.0, "timer")]


@pytest.mark.spec("REC-5")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap, expected",
    [
        (alt(4), 300.0, 100.0, [entry(0.0, 0.0, 0.0, "first"), entry(1.5, 255.0, 255.0, "last")]),
        (
            [flat(0), flat(12), flat(13), flat(13)],
            T,
            100.0,
            [entry(0.0, 0.0, 0.0, "first"), entry(1.0, 13.0, 13.0, "diff"), entry(1.5, 0.0, 0.0, "last")],
        ),
        (static(1), T, G, [entry(0.0, 0.0, 0.0, "first")]),
    ],
)
def test_rec_5_appended_last_thumbnail_has_reason_last(thumbs, threshold, max_gap, expected):
    assert seenby.select_frames(thumbs, threshold, max_gap) == expected


@pytest.mark.spec("REC-2")
@pytest.mark.parametrize("thumbs", [static(1), static(20), alt(20), ramp(), blocky()])
def test_rec_2_first_entry_is_first_with_zero_diff(thumbs):
    assert seenby.select_frames(thumbs, T, G)[0] == entry(0.0, 0.0, 0.0, "first")


@pytest.mark.spec("REC-7")
def test_rec_7_empty_thumbs_gives_empty_list():
    assert seenby.select_frames([], T, G) == []
    assert seenby.select_frames([], T, G, 0) == []


@pytest.mark.spec("REC-7")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap",
    [
        (static(20), T, G),
        (alt(20), T, G),
        (ramp(), T, 100.0),
        (alt(4), 300.0, 100.0),
        (static(240), T, G),
        (blocky(), T, G),
        ([flat(0), straddle(100)], T, 100.0),
    ],
)
def test_rec_7_times_equal_select_and_keys_are_exact(thumbs, threshold, max_gap):
    frames = seenby.select_frames(thumbs, threshold, max_gap)
    assert frames
    assert [d["time"] for d in frames] == seenby.select(thumbs, threshold, max_gap)
    assert all(set(d) == ENTRY_KEYS for d in frames)


@pytest.mark.spec("REC-7")
@pytest.mark.parametrize("block_k", [0, 0.5, 5.0])
def test_rec_7_times_equal_select_with_the_same_block_k(block_k):
    frames = seenby.select_frames(blocky(), T, G, block_k)
    assert [d["time"] for d in frames] == seenby.select(blocky(), T, G, block_k)
    assert all(set(d) == ENTRY_KEYS for d in frames)


@pytest.mark.spec("REC-7")
def test_rec_7_static_row_has_block_zero_in_every_entry():
    frames = seenby.select_frames(static(20), T, G)
    assert frames == static_20_entries()
    assert [d["block"] for d in frames] == [0.0] * 5


@pytest.mark.spec("REC-7")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap, block_k, expected_last",
    [
        ([flat(0), patch(100), patch(100)], T, 100.0, 0, entry(1.0, 6.25, 100.0, "last")),
        ([flat(0), straddle(100)], T, 100.0, 5.0, entry(0.5, 6.25, 50.0, "last")),
        ([flat(0), pixel(255)], T, 100.0, 0, entry(0.5, 0.2490234375, 3.984375, "last")),
    ],
)
def test_rec_7_appended_last_entry_carries_its_block(thumbs, threshold, max_gap, block_k, expected_last):
    frames = seenby.select_frames(thumbs, threshold, max_gap, block_k)
    assert frames[-1] == expected_last


@pytest.mark.spec("REC-P1")
@settings(deadline=None)
@given(thumbs=thumbs_st, threshold=threshold_st, max_gap=max_gap_st)
def test_rec_p1_reasons_and_diffs_are_well_formed(thumbs, threshold, max_gap):
    frames = seenby.select_frames(thumbs, threshold, max_gap)
    assert [d["time"] for d in frames] == seenby.select(thumbs, threshold, max_gap)
    assert all(d["reason"] in REASONS for d in frames)
    if frames:
        assert frames[0]["reason"] == "first"
    assert all(d["reason"] != "first" for d in frames[1:])
    assert all(d["reason"] != "last" for d in frames[:-1])
    assert all(isinstance(d["diff"], float) and 0.0 <= d["diff"] <= 255.0 for d in frames)


# ---------------------------------------------------------------- block metric (draft, plan step 4)


@pytest.mark.spec("BLK-1")
def test_blk_1_default_block_size_is_eight():
    assert seenby.BLOCK == 8


@pytest.mark.spec("BLK-1")
@pytest.mark.parametrize(
    "a, b, expected",
    [
        (flat(0), flat(0), 0.0),
        (flat(0), flat(255), 255.0),
        (patch(200), patch(200), 0.0),
        (flat(7), flat(7), 0.0),
        (flat(100), flat(160), 60.0),
    ],
    ids=["flat0-flat0", "flat0-flat255", "patch200-patch200", "flat7-flat7", "flat100-flat160"],
)
def test_blk_1_largest_block_mean_absolute_difference(a, b, expected):
    result = seenby.block_max(a, b)
    assert result == expected
    assert isinstance(result, float)


@pytest.mark.spec("BLK-1")
def test_blk_1_block_size_argument_changes_the_grid():
    assert seenby.block_max(flat(0), patch(200), 16) == 50.0
    assert seenby.block_max(flat(0), patch(200), seenby.BLOCK) == 200.0


@pytest.mark.spec("BLK-2")
@pytest.mark.parametrize(
    "a, b, expected",
    [
        (flat(0), patch(200), 200.0),
        (flat(0), pixel(255), 3.984375),
        (flat(0), straddle(100), 50.0),
        (patch(200), flat(0), 200.0),
    ],
    ids=["patch200", "pixel255", "straddle100", "patch200-reversed"],
)
def test_blk_2_change_confined_to_a_block_is_reported_at_full_strength(a, b, expected):
    assert seenby.block_max(a, b) == expected


@pytest.mark.spec("BLK-2")
def test_blk_2_block_ignores_the_whole_thumbnail_mean():
    assert seenby.block_max(flat(0), patch(200)) == 200.0
    assert seenby.select_frames([flat(0), patch(200)], T, 100.0)[1]["diff"] == 12.5


@pytest.mark.spec("REC-6")
def test_rec_6_default_block_k_is_five():
    assert seenby.BLOCK_K == 5.0


@pytest.mark.spec("REC-6")
@pytest.mark.spec("REC-7")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap, expected",
    [
        ([flat(0), patch(100)], T, 100.0, [entry(0.0, 0.0, 0.0, "first"), entry(0.5, 6.25, 100.0, "block")]),
        (
            [flat(0), patch(100), patch(100)],
            T,
            100.0,
            [entry(0.0, 0.0, 0.0, "first"), entry(0.5, 6.25, 100.0, "block"), entry(1.0, 0.0, 0.0, "last")],
        ),
    ],
)
def test_rec_6_7_strong_block_change_is_kept_with_reason_block(thumbs, threshold, max_gap, expected):
    assert seenby.select_frames(thumbs, threshold, max_gap) == expected


@pytest.mark.spec("REC-6")
@pytest.mark.parametrize(
    "thumbs, expected",
    [
        ([flat(0), patch(60), flat(0)], [entry(0.0, 0.0, 0.0, "first"), entry(1.0, 0.0, 0.0, "last")]),
        ([flat(0), straddle(100)], [entry(0.0, 0.0, 0.0, "first"), entry(0.5, 6.25, 50.0, "last")]),
    ],
)
def test_rec_6_block_not_above_the_bar_does_not_keep(thumbs, expected):
    assert seenby.select_frames(thumbs, T, 100.0) == expected


@pytest.mark.spec("REC-6")
def test_rec_6_diff_wins_over_block():
    assert seenby.select_frames(alt(4), T, 100.0) == [
        entry(0.0, 0.0, 0.0, "first"),
        entry(0.5, 255.0, 255.0, "diff"),
        entry(1.0, 255.0, 255.0, "diff"),
        entry(1.5, 255.0, 255.0, "diff"),
    ]


@pytest.mark.spec("REC-6")
def test_rec_6_block_wins_over_timer():
    assert seenby.select_frames([flat(0)] * 6 + [patch(100)], T, G) == [
        entry(0.0, 0.0, 0.0, "first"),
        entry(3.0, 6.25, 100.0, "block"),
    ]


@pytest.mark.spec("REC-6")
def test_rec_6_bar_scales_with_block_k_and_threshold():
    thumbs = [flat(0), patch(100)]
    assert seenby.select_frames(thumbs, T, 100.0, 8.0)[1]["reason"] == "block"
    assert seenby.select_frames(thumbs, T, 100.0, 9.0)[1]["reason"] == "last"
    assert seenby.select_frames(thumbs, 20.0, 100.0)[1]["reason"] == "last"


@pytest.mark.spec("REC-8")
def test_rec_8_block_k_zero_disables_the_rule_but_still_reports_block():
    assert seenby.select_frames([flat(0), patch(100), patch(100)], T, 100.0, 0) == [
        entry(0.0, 0.0, 0.0, "first"),
        entry(1.0, 6.25, 100.0, "last"),
    ]


@pytest.mark.spec("REC-8")
def test_rec_8_select_with_block_k_zero_versus_default():
    thumbs = [flat(0), patch(100), patch(100)]
    assert seenby.select(thumbs, T, 100.0, 0) == [0.0, 1.0]
    assert seenby.select(thumbs, T, 100.0) == [0.0, 0.5, 1.0]


@pytest.mark.spec("REC-8")
@pytest.mark.parametrize(
    "thumbs, threshold, max_gap, expected",
    [
        (static(20), T, G, [0.0, 3.0, 6.0, 9.0, 9.5]),
        (static(7), T, G, [0.0, 3.0]),
        ([flat(0), flat(12), flat(13), flat(13)], T, 100.0, [0.0, 1.0, 1.5]),
        ([flat(0), half(24), half(26), flat(0)], T, 100.0, [0.0, 1.0, 1.5]),
        (ramp(), T, 100.0, [0.0, 1.5, 3.0, 4.5]),
        (alt(4), 300.0, 100.0, [0.0, 1.5]),
        (alt(20), T, G, [i / 2 for i in range(20)]),
        (blocky(), T, G, [0.0, 3.0, 6.0, 9.0, 9.5]),
    ],
)
def test_rec_8_block_k_zero_reproduces_the_anchored_selection(thumbs, threshold, max_gap, expected):
    assert seenby.select(thumbs, threshold, max_gap, 0) == expected
    assert [d["time"] for d in seenby.select_frames(thumbs, threshold, max_gap, 0)] == expected


@pytest.mark.spec("REC-8")
@settings(deadline=None)
@given(thumbs=thumbs_st, threshold=threshold_st, max_gap=max_gap_st)
def test_rec_8_block_k_zero_never_gives_reason_block(thumbs, threshold, max_gap):
    frames = seenby.select_frames(thumbs, threshold, max_gap, 0)
    assert all(d["reason"] in ("first", "diff", "timer", "last") for d in frames)
    assert [d["time"] for d in frames] == seenby.select(thumbs, threshold, max_gap, 0)


@pytest.mark.spec("REC-P2")
@settings(deadline=None)
@given(thumbs=thumbs_st, threshold=threshold_st, max_gap=max_gap_st, block_k=block_k_st)
def test_rec_p2_block_is_bounded_and_never_below_diff(thumbs, threshold, max_gap, block_k):
    frames = seenby.select_frames(thumbs, threshold, max_gap, block_k)
    assert [d["time"] for d in frames] == seenby.select(thumbs, threshold, max_gap, block_k)
    assert all(set(d) == ENTRY_KEYS for d in frames)
    assert all(0.0 <= d["block"] <= 255.0 for d in frames)
    assert all(d["block"] >= d["diff"] for d in frames)


@pytest.mark.spec("CAP-7")
@pytest.mark.parametrize(
    "max_frames, block_k, expected",
    [
        (5, 5.0, ([0.0, 3.0, 6.0, 9.0, 9.5], 27.0, 3.0)),
        (5, 0, ([0.0, 3.0, 6.0, 9.0, 9.5], 12.0, 3.0)),
        (24, 5.0, ([i / 2 for i in range(20)], 12.0, 3.0)),
        (2, 0.5, ([0.0, 9.5], 205.03125, 9.1552734375)),
    ],
)
def test_cap_7_threshold_loop_uses_block_k_and_gap_loop_does_not(max_frames, block_k, expected):
    times, threshold, max_gap = seenby.fit_to_cap(blocky(), max_frames, T, G, block_k)
    assert (times, threshold, max_gap) == expected
    assert times == seenby.select(blocky(), threshold, max_gap, block_k)


@pytest.mark.spec("CAP-7")
def test_cap_7_default_block_k_is_the_module_constant():
    assert seenby.fit_to_cap(blocky(), 5, T, G) == seenby.fit_to_cap(blocky(), 5, T, G, seenby.BLOCK_K)
    assert seenby.fit_to_cap(blocky(), 5, T, G) != seenby.fit_to_cap(blocky(), 5, T, G, 0)


@pytest.mark.spec("CAP-P3")
@settings(deadline=None)
@given(
    thumbs=thumbs_st,
    max_frames=max_frames_st,
    threshold=threshold_st,
    max_gap=max_gap_st,
    block_k=block_k_st,
)
def test_cap_p3_fits_the_cap_for_any_block_k(thumbs, max_frames, threshold, max_gap, block_k):
    times, out_threshold, out_gap = seenby.fit_to_cap(thumbs, max_frames, threshold, max_gap, block_k)
    assert len(times) <= max_frames
    assert times == seenby.select(thumbs, out_threshold, out_gap, block_k)


# ---------------------------------------------------------------- sampling rate (draft, plan step 3)


@pytest.mark.spec("REC-9")
def test_rec_9_select_at_four_fps_forces_at_three_seconds_and_keeps_the_last():
    assert seenby.select(static(20), T, G, sample_fps=4) == [0.0, 3.0, 4.75]


@pytest.mark.spec("REC-9")
def test_rec_9_select_frames_at_four_fps_has_timer_then_last():
    frames = seenby.select_frames(static(20), T, G, sample_fps=4)
    assert [d["time"] for d in frames] == [0.0, 3.0, 4.75]
    assert [d["reason"] for d in frames] == ["first", "timer", "last"]


@pytest.mark.spec("REC-9")
def test_rec_9_select_frames_at_one_fps_positional_sample_fps():
    frames = seenby.select_frames(static(4), T, G, 5.0, 1.0)
    assert [d["time"] for d in frames] == [0.0, 3.0]
    assert frames[-1]["reason"] == "timer"


@pytest.mark.spec("REC-9")
def test_rec_9_select_at_one_fps_forces_every_three_thumbnails():
    assert seenby.select(static(7), T, G, sample_fps=1.0) == [0.0, 3.0, 6.0]


@pytest.mark.spec("REC-9")
def test_rec_9_fit_to_cap_at_four_fps_spans_sixty_seconds():
    times, threshold, max_gap = seenby.fit_to_cap(static(240), 24, T, G, 5.0, 4.0)
    assert times == [float(t) for t in range(0, 58, 3)] + [59.75]
    assert len(times) == 21
    assert (threshold, max_gap) == (12.0, 3.0)


@pytest.mark.spec("REC-9")
def test_rec_9_default_sample_fps_is_the_module_constant():
    assert seenby.select(static(20), T, G, sample_fps=seenby.SAMPLE_FPS) == seenby.select(static(20), T, G)
    assert seenby.select_frames(static(20), T, G, sample_fps=seenby.SAMPLE_FPS) == seenby.select_frames(static(20), T, G)
    assert seenby.fit_to_cap(static(240), 24, T, G, sample_fps=seenby.SAMPLE_FPS) == seenby.fit_to_cap(static(240), 24, T, G)
    assert seenby.select(static(20), T, G, sample_fps=4) != seenby.select(static(20), T, G)


# ---------------------------------------------------------------- layout (draft, plan step 3)

NOMINAL_COLS = {"phone": 6, "window": 3, "wide": 2}

LAYOUT_ROWS = [
    ((814, 872, 12), {}, ("window", 516, 3, 2, 2)),
    ((2554, 1334, 10), {}, ("wide", 776, 2, 3, 2)),
    ((526, 514, 3), {}, ("window", 516, 3, 3, 1)),
    ((720, 1280, 14), {}, ("phone", 256, 6, 3, 1)),
    ((576, 1280, 3), {}, ("phone", 256, 3, 2, 1)),
    ((2560, 1228, 8), {}, ("wide", 776, 2, 4, 1)),
    ((1636, 1228, 5), {}, ("window", 516, 3, 3, 1)),
    ((576, 1280, 9), {}, ("phone", 256, 6, 2, 1)),
    ((576, 1280, 20), {}, ("phone", 256, 6, 2, 2)),
    ((100, 2000, 5), {}, ("phone", 100, 5, 1, 1)),
    ((1600, 1000, 6), {}, ("window", 516, 3, 4, 1)),
    ((1601, 1000, 6), {}, ("wide", 776, 2, 3, 1)),
    ((750, 1000, 6), {}, ("window", 516, 3, 2, 1)),
    ((749, 1000, 6), {}, ("phone", 256, 6, 4, 1)),
    ((500, 500, 6), {}, ("window", 500, 3, 3, 1)),
    ((800, 600, 6, 1200, 2), {}, ("window", 393, 3, 2, 1)),
    ((800, 600, 6), {"tile_width": 300}, ("window", 300, 5, 6, 1)),
    ((800, 600, 1), {}, ("window", 516, 1, 3, 1)),
    ((800, 600, 2), {}, ("window", 516, 2, 3, 1)),
    ((800, 600, 30), {}, ("window", 516, 3, 3, 4)),
    ((3440, 1440, 24), {}, ("wide", 776, 2, 4, 3)),
]
LAYOUT_IDS = ["-".join(map(str, args)) + "".join(f"-{k}{v}" for k, v in kwargs.items()) for args, kwargs, _ in LAYOUT_ROWS]


def grade_for(width, height):
    ratio = width / height
    if ratio < 0.75:
        return "phone"
    if ratio <= 1.6:
        return "window"
    return "wide"


def assert_layout_invariant(width, height, n_frames, sheet_width, result, rows_given=None, tile_width_given=None):
    grade, tile, cols, rows, sheets = result
    tile_h = round(tile * height / width)
    if tile_width_given is None:
        assert cols * tile + 2 * seenby.MARGIN + (cols - 1) * seenby.PADDING <= sheet_width
    if rows_given is None:
        assert rows == 1 or rows * tile_h + 2 * seenby.MARGIN + (rows - 1) * seenby.PADDING <= sheet_width
    assert 1 <= cols <= n_frames
    assert rows >= 1
    assert sheets >= 1
    assert tile <= width


@pytest.mark.spec("LAY-2")
@pytest.mark.spec("LAY-5")
def test_lay_2_5_sheet_width_margin_and_padding_constants():
    assert seenby.SHEET_WIDTH == 1568
    assert seenby.MARGIN == 6
    assert seenby.PADDING == 4


@pytest.mark.spec("LAY-1")
@pytest.mark.spec("LAY-2")
@pytest.mark.spec("LAY-3")
@pytest.mark.spec("LAY-4")
@pytest.mark.parametrize("args, kwargs, expected", LAYOUT_ROWS, ids=LAYOUT_IDS)
def test_lay_1_4_example_rows(args, kwargs, expected):
    result = seenby.layout(*args, **kwargs)
    assert result == expected
    assert isinstance(result[0], str)
    assert all(type(value) is int for value in result[1:])


@pytest.mark.spec("LAY-1")
@pytest.mark.parametrize(
    "width, height, grade",
    [
        (1600, 1000, "window"),
        (1601, 1000, "wide"),
        (750, 1000, "window"),
        (749, 1000, "phone"),
        (1000, 1000, "window"),
        (720, 1280, "phone"),
        (2554, 1334, "wide"),
        (3440, 1440, "wide"),
    ],
)
def test_lay_1_grade_boundaries_and_nominal_columns(width, height, grade):
    result = seenby.layout(width, height, 60)
    assert result[0] == grade
    assert result[2] == NOMINAL_COLS[grade]


@pytest.mark.spec("LAY-2")
@pytest.mark.parametrize(
    "width, height, sheet_width, tile",
    [
        (2000, 4000, 1568, 256),
        (2000, 2000, 1568, 516),
        (4000, 2000, 1568, 776),
        (2000, 4000, 1200, 194),
        (2000, 2000, 1200, 393),
        (4000, 2000, 1200, 592),
    ],
)
def test_lay_2_tile_from_sheet_width_and_nominal_columns(width, height, sheet_width, tile):
    grade, got_tile, cols, _, _ = seenby.layout(width, height, 60, sheet_width)
    nominal = NOMINAL_COLS[grade]
    assert got_tile == tile
    assert got_tile == (sheet_width - 2 * seenby.MARGIN - (nominal - 1) * seenby.PADDING) // nominal
    assert cols == nominal


@pytest.mark.spec("LAY-2")
@pytest.mark.parametrize(
    "args, kwargs, tile",
    [
        ((500, 500, 6), {}, 500),
        ((100, 2000, 5), {}, 100),
        ((200, 150, 6), {"tile_width": 300}, 200),
        ((576, 1280, 3), {}, 256),
    ],
)
def test_lay_2_tile_is_never_wider_than_the_source(args, kwargs, tile):
    assert seenby.layout(*args, **kwargs)[1] == tile


@pytest.mark.spec("LAY-2")
@pytest.mark.parametrize(
    "tile_width, cols",
    [(300, 5), (516, 3), (776, 2), (1560, 1), (2000, 1)],
)
def test_lay_2_requested_tile_decides_the_columns(tile_width, cols):
    grade, tile, got_cols, _, _ = seenby.layout(4000, 3000, 60, tile_width=tile_width)
    assert grade == "window"
    assert tile == tile_width
    assert got_cols == cols
    assert got_cols == max(1, (seenby.SHEET_WIDTH - 2 * seenby.MARGIN + seenby.PADDING) // (tile + seenby.PADDING))


@pytest.mark.spec("LAY-3")
@pytest.mark.parametrize(
    "args, kwargs, rows",
    [
        ((1600, 1000, 6), {}, 4),
        ((1032, 1033, 6), {}, 3),
        ((814, 872, 12), {}, 2),
        ((100, 2000, 5), {}, 1),
        ((800, 600, 6, 1200, 2), {}, 2),
        ((800, 600, 30), {"rows": 1}, 1),
        ((800, 600, 6), {"rows": 5}, 5),
    ],
    ids=["round-half-even-322", "round-half-even-516", "two-rows", "taller-than-sheet", "rows-2-given", "rows-1-given", "rows-5-given"],
)
def test_lay_3_rows_fill_the_sheet_height_or_are_used_as_given(args, kwargs, rows):
    assert seenby.layout(*args, **kwargs)[3] == rows


@pytest.mark.spec("LAY-3")
def test_lay_3_tile_height_rounds_half_to_even():
    grade, tile, cols, rows, sheets = seenby.layout(1032, 1033, 6)
    assert (grade, tile) == ("window", 516)
    assert tile * 1033 / 1032 == 516.5
    assert rows == 3


@pytest.mark.spec("LAY-4")
@pytest.mark.parametrize("n_frames", list(range(1, 31)))
def test_lay_4_cols_cut_to_n_frames_and_sheets_is_the_ceiling(n_frames):
    grade, tile, cols, rows, sheets = seenby.layout(800, 600, n_frames)
    assert (grade, tile, rows) == ("window", 516, 3)
    assert cols == min(3, n_frames)
    assert sheets == math.ceil(n_frames / (cols * rows))


@pytest.mark.spec("LAY-4")
@pytest.mark.parametrize(
    "args, kwargs, cols, sheets",
    [
        ((800, 600, 1), {}, 1, 1),
        ((800, 600, 2), {}, 2, 1),
        ((800, 600, 30), {}, 3, 4),
        ((3440, 1440, 24), {}, 2, 3),
        ((576, 1280, 3), {}, 3, 1),
        ((576, 1280, 20), {}, 6, 2),
        ((800, 600, 30), {"rows": 1}, 3, 10),
    ],
)
def test_lay_4_example_columns_and_sheet_counts(args, kwargs, cols, sheets):
    result = seenby.layout(*args, **kwargs)
    assert result[2] == cols
    assert result[4] == sheets


@pytest.mark.spec("LAY-5")
@pytest.mark.parametrize("args, kwargs, expected", LAYOUT_ROWS, ids=LAYOUT_IDS)
def test_lay_5_invariant_holds_on_the_example_rows(args, kwargs, expected):
    width, height, n_frames = args[:3]
    sheet_width = args[3] if len(args) > 3 else kwargs.get("sheet_width", seenby.SHEET_WIDTH)
    rows = args[4] if len(args) > 4 else kwargs.get("rows")
    tile_width = args[5] if len(args) > 5 else kwargs.get("tile_width")
    result = seenby.layout(*args, **kwargs)
    assert_layout_invariant(width, height, n_frames, sheet_width, result, rows, tile_width)


@pytest.mark.spec("LAY-P1")
@pytest.mark.spec("LAY-5")
@settings(deadline=None)
@given(
    width=st.integers(min_value=16, max_value=4000),
    height=st.integers(min_value=16, max_value=4000),
    n_frames=st.integers(min_value=1, max_value=60),
    sheet_width=st.integers(min_value=64, max_value=4000),
    rows=st.none() | st.integers(min_value=1, max_value=8),
    tile_width=st.none() | st.integers(min_value=16, max_value=2000),
)
def test_lay_p1_layout_returns_within_the_sheet_for_any_input(width, height, n_frames, sheet_width, rows, tile_width):
    result = seenby.layout(width, height, n_frames, sheet_width, rows, tile_width)
    grade, tile, cols, got_rows, sheets = result
    assert_layout_invariant(width, height, n_frames, sheet_width, result, rows, tile_width)
    assert grade == grade_for(width, height)
    assert tile <= width
    assert sheets == math.ceil(n_frames / (cols * got_rows))


# ---------------------------------------------------------------- parse_probe (draft)


@pytest.mark.spec("PRB-1")
def test_prb_1_size_line_then_duration_line():
    duration, width, height = seenby.parse_probe("814,872\n37.700000\n")
    assert (duration, width, height) == (37.7, 814, 872)
    assert isinstance(duration, float)
    assert isinstance(width, int)
    assert isinstance(height, int)


@pytest.mark.spec("PRB-2")
def test_prb_2_line_order_and_empty_lines_do_not_matter():
    assert seenby.parse_probe("37.700000\n\n814,872") == (37.7, 814, 872)


@pytest.mark.spec("PRB-3")
@pytest.mark.parametrize("text", ["", "814,872\n", "37.7\n", "0,0\n37.7\n", "814,872\nN/A\n"])
def test_prb_3_broken_output_raises_value_error_naming_ffprobe(text):
    with pytest.raises(ValueError) as exc:
        seenby.parse_probe(text)
    assert "ffprobe" in str(exc.value)


# ---------------------------------------------------------------- require_tools (draft)

FFMPEG_MISSING = "ffmpeg not found. Install ffmpeg or set FFMPEG=/path/to/ffmpeg"
FFPROBE_MISSING = "ffprobe not found. Install ffmpeg or set FFPROBE=/path/to/ffprobe"


def executable(tmp_path, name):
    path = tmp_path / name
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return str(path)


@pytest.mark.spec("TOOL-1")
def test_tool_1_both_executables_found_gives_none(monkeypatch, tmp_path):
    monkeypatch.setenv("FFMPEG", executable(tmp_path, "ff"))
    monkeypatch.setenv("FFPROBE", executable(tmp_path, "fp"))
    assert seenby.require_tools() is None


@pytest.mark.spec("TOOL-2")
def test_tool_2_missing_ffmpeg_names_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setenv("FFMPEG", str(tmp_path / "nope"))
    monkeypatch.setenv("FFPROBE", executable(tmp_path, "fp"))
    assert seenby.require_tools() == FFMPEG_MISSING


@pytest.mark.spec("TOOL-2")
def test_tool_2_both_missing_names_ffmpeg_first(monkeypatch, tmp_path):
    monkeypatch.setenv("FFMPEG", str(tmp_path / "nope"))
    monkeypatch.setenv("FFPROBE", str(tmp_path / "nope"))
    assert seenby.require_tools() == FFMPEG_MISSING


@pytest.mark.spec("TOOL-3")
def test_tool_3_missing_ffprobe_names_ffprobe(monkeypatch, tmp_path):
    monkeypatch.setenv("FFMPEG", executable(tmp_path, "ff"))
    monkeypatch.setenv("FFPROBE", str(tmp_path / "nope"))
    assert seenby.require_tools() == FFPROBE_MISSING


# ---------------------------------------------------------------- check_out_dir (draft)


@pytest.mark.spec("DIR-1")
def test_dir_1_missing_directory_gives_none(tmp_path):
    assert seenby.check_out_dir(tmp_path / "missing", False) is None


@pytest.mark.spec("DIR-1")
@pytest.mark.parametrize(
    "names, force",
    [
        ([], False),
        (["other.jpg", "notes.txt"], False),
        (["sheet-01.jpg"], False),
        (["frame-01.jpg", "frames.json"], False),
        (["frame-01.jpg"], True),
    ],
)
def test_dir_1_no_foreign_frames_or_forced_gives_none(tmp_path, names, force):
    populate(tmp_path, names)
    assert seenby.check_out_dir(tmp_path, force) is None


@pytest.mark.spec("DIR-2")
def test_dir_2_foreign_frames_without_manifest_are_refused(tmp_path):
    populate(tmp_path, ["frame-01.jpg"])
    d = str(tmp_path)
    assert seenby.check_out_dir(d, False) == f"{d} already holds frame-*.jpg from something else; pass --force to overwrite"


@pytest.mark.spec("DIR-2")
def test_dir_2_message_uses_the_argument_as_given(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.mkdir("out")
    populate(tmp_path / "out", ["frame-03.jpg", "other.jpg"])
    assert seenby.check_out_dir("out", False) == "out already holds frame-*.jpg from something else; pass --force to overwrite"


# ---------------------------------------------------------------- write_json (draft)


@pytest.mark.spec("JSN-1")
def test_jsn_1_indented_utf8_json_with_trailing_newline(tmp_path):
    data = {"a": [1, 2.5, "ünïcode"], "b": None}
    path = tmp_path / "frames.json"
    seenby.write_json(path, data)
    text = path.read_text(encoding="utf-8")
    assert text == json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    assert "ünïcode" in text
    assert "\\u" not in text
    with open(path, encoding="utf-8") as fh:
        assert json.load(fh) == data


@pytest.mark.spec("JSN-2")
def test_jsn_2_second_write_overwrites(tmp_path):
    path = tmp_path / "frames.json"
    seenby.write_json(path, {"first": 1})
    seenby.write_json(path, {"second": 2})
    with open(path, encoding="utf-8") as fh:
        assert json.load(fh) == {"second": 2}


@pytest.mark.spec("JSN-3")
def test_jsn_3_no_temporary_file_is_left_behind(tmp_path):
    x = tmp_path / "x"
    x.mkdir()
    (x / "keep.txt").write_text("keep")
    seenby.write_json(x / "frames.json", {})
    assert sorted(os.listdir(x)) == ["frames.json", "keep.txt"]
    assert (x / "keep.txt").read_text() == "keep"


# ---------------------------------------------------------------- clean

CLEAN_EXAMPLE_FILES = [
    "frame-01.jpg",
    "frame-10.jpg",
    "sheet-01.jpg",
    "sheet.jpg",
    "sheets-02.jpg",
    "frame-01.png",
    "frames.json",
    "report.md",
    "other.jpg",
    "Frame-01.jpg",
]


def populate(directory, names, subdirs=()):
    for name in names:
        (directory / name).write_bytes(b"x")
    for name in subdirs:
        (directory / name).mkdir()


@pytest.mark.spec("CLN-1")
@pytest.mark.spec("CLN-4")
def test_cln_1_cln_4_removes_own_files_keeps_everything_else(tmp_path):
    populate(tmp_path, CLEAN_EXAMPLE_FILES, subdirs=["notes"])
    seenby.clean(tmp_path)
    assert sorted(os.listdir(tmp_path)) == ["Frame-01.jpg", "frame-01.png", "notes", "other.jpg"]


@pytest.mark.spec("CLN-1")
@pytest.mark.parametrize("name", ["frame-01.jpg", "frame-10.jpg", "sheet-01.jpg", "sheet.jpg", "sheets-02.jpg"])
def test_cln_1_matching_name_is_removed(tmp_path, name):
    populate(tmp_path, [name])
    seenby.clean(tmp_path)
    assert not (tmp_path / name).exists()


@pytest.mark.spec("CLN-1")
def test_cln_1_matching_symlink_is_unlinked_and_target_stays(tmp_path):
    target = tmp_path / "keep.txt"
    target.write_bytes(b"x")
    link = tmp_path / "frame-07.jpg"
    link.symlink_to(target)
    seenby.clean(tmp_path)
    assert not link.is_symlink()
    assert not link.exists()
    assert target.exists()
    assert target.read_bytes() == b"x"


@pytest.mark.spec("CLN-4")
@pytest.mark.parametrize("name", ["frames.json", "report.md"])
def test_cln_4_manifest_and_report_are_removed(tmp_path, name):
    populate(tmp_path, [name, "other.jpg"])
    seenby.clean(tmp_path)
    assert not (tmp_path / name).exists()
    assert (tmp_path / "other.jpg").is_file()


@pytest.mark.spec("CLN-4")
@pytest.mark.parametrize("name", ["Frame-01.jpg", "frame-01.png", "other.jpg"])
def test_cln_4_non_matching_file_stays(tmp_path, name):
    populate(tmp_path, [name])
    seenby.clean(tmp_path)
    assert (tmp_path / name).is_file()


@pytest.mark.spec("CLN-4")
def test_cln_4_subdirectory_and_its_contents_stay(tmp_path):
    populate(tmp_path, ["frame-01.jpg", "frames.json"], subdirs=["notes"])
    populate(tmp_path / "notes", ["frame-02.jpg", "frames.json", "todo.md"])
    seenby.clean(tmp_path)
    assert (tmp_path / "notes").is_dir()
    assert sorted(os.listdir(tmp_path / "notes")) == ["frame-02.jpg", "frames.json", "todo.md"]


@pytest.mark.spec("CLN-3")
def test_cln_3_missing_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        seenby.clean(tmp_path / "missing")


CLEAN_ALPHABET = [
    "".join(parts)
    for parts in product(("frame-", "sheet", "Frame-", "other"), ("01", "02"), (".jpg", ".png", ".json"))
]


def cleaned_by_rule(name):
    return (name.startswith("frame-") or name.startswith("sheet")) and name.endswith(".jpg")


@pytest.mark.spec("CLN-P1")
@settings(deadline=None)
@given(names=st.frozensets(st.sampled_from(CLEAN_ALPHABET)))
def test_cln_p1_exactly_the_own_jpgs_are_gone(names, tmp_path_factory):
    directory = tmp_path_factory.mktemp("clean")
    populate(directory, names)
    seenby.clean(directory)
    assert set(os.listdir(directory)) == {n for n in names if not cleaned_by_rule(n)}


# ---------------------------------------------------------------- ffmpeg(), ffprobe()


@pytest.mark.spec("ENV-1")
def test_env_1_ffmpeg_from_environment(monkeypatch):
    monkeypatch.setenv("FFMPEG", "/opt/ff")
    assert seenby.ffmpeg() == "/opt/ff"


@pytest.mark.spec("ENV-1")
def test_env_1_ffmpeg_default(monkeypatch):
    monkeypatch.delenv("FFMPEG", raising=False)
    assert seenby.ffmpeg() == "ffmpeg"


@pytest.mark.spec("ENV-2")
def test_env_2_ffprobe_from_environment(monkeypatch):
    monkeypatch.setenv("FFPROBE", "/opt/fp")
    assert seenby.ffprobe() == "/opt/fp"


@pytest.mark.spec("ENV-2")
def test_env_2_ffprobe_default(monkeypatch):
    monkeypatch.delenv("FFPROBE", raising=False)
    assert seenby.ffprobe() == "ffprobe"


# ---------------------------------------------------------------- segments (draft, plan step 5)


def segment(n, start, end, frames):
    return {"n": n, "from": start, "to": end, "frames": frames}


SEGMENT_ROWS = [
    (
        [0.0, 3.0, 119.5, 120.0, 200.0],
        0.0,
        240.0,
        120.0,
        [segment(1, 0.0, 120.0, [1, 2, 3]), segment(2, 120.0, 240.0, [4, 5])],
    ),
    (
        [0.0, 600.0, 604.0],
        0.0,
        604.37,
        120.0,
        [
            segment(1, 0.0, 120.0, [1]),
            segment(2, 120.0, 240.0, []),
            segment(3, 240.0, 360.0, []),
            segment(4, 360.0, 480.0, []),
            segment(5, 480.0, 600.0, []),
            segment(6, 600.0, 604.37, [2, 3]),
        ],
    ),
    ([600.0, 650.0, 719.5], 600.0, 720.0, 120.0, [segment(1, 600.0, 720.0, [1, 2, 3])]),
    ([0.0, 10.0], 0.0, 10.0, 120.0, [segment(1, 0.0, 10.0, [1, 2])]),
    ([0.0, 5.0, 10.0], 0.0, 10.0, 5.0, [segment(1, 0.0, 5.0, [1]), segment(2, 5.0, 10.0, [2, 3])]),
    ([], 0.0, 250.0, 120.0, [segment(1, 0.0, 120.0, []), segment(2, 120.0, 240.0, []), segment(3, 240.0, 250.0, [])]),
]


@pytest.mark.spec("SEG-1")
@pytest.mark.spec("SEG-2")
@pytest.mark.spec("SEG-3")
@pytest.mark.parametrize("times, start, end, length, expected", SEGMENT_ROWS)
def test_seg_1_2_3_example_rows(times, start, end, length, expected):
    assert seenby.segments(times, start, end, length) == expected


@pytest.mark.spec("SEG-1")
def test_seg_1_short_tail_is_its_own_entry_ending_at_end():
    result = seenby.segments([0.0, 600.0, 604.0], 0.0, 604.37, 120.0)
    assert len(result) == 6
    assert result[0] == segment(1, 0.0, 120.0, [1])
    assert [e["frames"] for e in result[1:5]] == [[], [], [], []]
    assert result[5] == segment(6, 600.0, 604.37, [2, 3])
    assert result[-1]["to"] == 604.37


@pytest.mark.spec("SEG-1")
@pytest.mark.parametrize(
    "start, end, length, count",
    [
        (0.0, 240.0, 120.0, 2),
        (0.0, 604.37, 120.0, 6),
        (0.0, 10.0, 120.0, 1),
        (600.0, 720.0, 120.0, 1),
        (0.0, 250.0, 120.0, 3),
        (0.0, 10.0, 5.0, 2),
        (3.0, 15.0, 4.0, 3),
    ],
)
def test_seg_1_entry_count_bounds_and_order(start, end, length, count):
    result = seenby.segments([], start, end, length)
    assert len(result) == count
    assert count == max(1, math.ceil((end - start) / length))
    assert [e["n"] for e in result] == list(range(1, count + 1))
    assert [e["from"] for e in result] == [start + k * length for k in range(count)]
    assert [e["to"] for e in result] == [min(start + (k + 1) * length, end) for k in range(count)]
    assert result[0]["from"] == start
    assert result[-1]["to"] == end
    assert all(list(e) == ["n", "from", "to", "frames"] for e in result)


@pytest.mark.spec("SEG-2")
@pytest.mark.parametrize("times, start, end, length, expected", SEGMENT_ROWS)
def test_seg_2_every_index_lands_in_exactly_one_entry(times, start, end, length, expected):
    result = seenby.segments(times, start, end, length)
    placed = [i for e in result for i in e["frames"]]
    assert sorted(placed) == list(range(1, len(times) + 1))
    assert len(placed) == len(set(placed))
    for e in result:
        for i in e["frames"]:
            if e is result[-1]:
                assert e["from"] <= times[i - 1] <= e["to"]
            else:
                assert e["from"] <= times[i - 1] < e["to"]


@pytest.mark.spec("SEG-2")
def test_seg_2_boundary_time_goes_to_the_later_entry_and_end_to_the_last():
    result = seenby.segments([0.0, 5.0, 10.0], 0.0, 10.0, 5.0)
    assert result[0]["frames"] == [1]
    assert result[1]["frames"] == [2, 3]
    at_end = seenby.segments([0.0, 10.0], 0.0, 10.0, 120.0)
    assert at_end == [segment(1, 0.0, 10.0, [1, 2])]


@pytest.mark.spec("SEG-3")
def test_seg_3_empty_times_give_three_entries_with_no_frames():
    result = seenby.segments([], 0.0, 250.0, 120.0)
    assert len(result) == 3
    assert [e["to"] for e in result] == [120.0, 240.0, 250.0]
    assert [e["frames"] for e in result] == [[], [], []]


@pytest.mark.spec("SEG-3")
@pytest.mark.parametrize("times, start, end, length, expected", SEGMENT_ROWS)
def test_seg_3_empty_times_give_the_same_entries_as_full_times(times, start, end, length, expected):
    empty = seenby.segments([], start, end, length)
    assert empty == [dict(e, frames=[]) for e in expected]
    assert all(e["frames"] == [] for e in empty)


@st.composite
def segment_inputs(draw):
    start = draw(st.floats(min_value=0.0, max_value=1000.0))
    span = draw(st.floats(min_value=0.5, max_value=3000.0))
    end = start + span
    length = draw(st.floats(min_value=0.5, max_value=500.0))
    times = sorted(draw(st.lists(st.floats(min_value=start, max_value=end), min_size=0, max_size=40)))
    return start, end, length, times


@pytest.mark.spec("SEG-P1")
@settings(deadline=None)
@given(inputs=segment_inputs())
def test_seg_p1_entries_tile_the_range_and_place_every_index_once(inputs):
    start, end, length, times = inputs
    result = seenby.segments(times, start, end, length)
    assert len(result) == max(1, math.ceil((end - start) / length))
    assert result[0]["from"] == start
    assert result[-1]["to"] == end
    assert all(a["to"] == b["from"] for a, b in zip(result, result[1:]))
    placed = [i for e in result for i in e["frames"]]
    assert sorted(placed) == list(range(1, len(times) + 1))
    assert len(placed) == len(set(placed))
    assert all(e["frames"] == sorted(e["frames"]) for e in result)


# ---------------------------------------------------------------- main()

FFMPEG_VERSION_LINE = "ffmpeg version 6.1.1-test"
MANIFEST_LINE = (
    "  manifest: {out_dir}/frames.json. Sheets are for meaning; read digits from the native frame, "
    'see "recheck" in the manifest.'
)
ALL_TIMER_LINE = (
    "  all frames taken by the timer: the threshold contributed nothing (effective {threshold}); "
    "try --max-frames, --block-k or --from/--to"
)
LAYOUT_LINE = "  layout: {grade}, tile {tile} px, {cols}x{rows} per sheet"
MANY_SHEETS_LINE = "  {n} contact sheets are more than 4; consider --max-frames or --from/--to"
RANGE_LINE = "  range: {start}-{end} s"


def outcome(value):
    if isinstance(value, BaseException):
        raise value
    return value


class Run:
    """Fakes for the ffmpeg-facing functions, recording the calls main() makes.

    `probe`, `thumbs`, `frames` and `sheets` are returned by the matching fake, or raised when they are
    exceptions. `watch` is a path whose existence is recorded at the moment each fake is called.
    """

    def __init__(self, monkeypatch, probe, thumbs, frames, sheets, tools, watch):
        self.probe_calls = []
        self.thumbnails_calls = []
        self.save_frames_calls = []
        self.contact_sheets_calls = []
        self.ffmpeg_version_calls = 0
        self.watched = {}

        def note(name):
            if watch is not None:
                self.watched[name] = os.path.exists(watch)

        def fake_probe(path):
            note("probe")
            self.probe_calls.append(path)
            return outcome(probe)

        def fake_thumbnails(path, sample_fps=None, start=None, length=None):
            note("thumbnails")
            self.thumbnails_calls.append((path, sample_fps, start, length))
            return outcome(thumbs)

        def fake_save_frames(path, times, out_dir, tile_width):
            note("save_frames")
            self.save_frames_calls.append((path, times, out_dir, tile_width))
            if frames is None:
                return [f"{out_dir}/frame-{i:02d}.jpg" for i in range(1, len(times) + 1)]
            return outcome(frames)

        def fake_contact_sheets(paths, out_dir, cols, rows):
            note("contact_sheets")
            self.contact_sheets_calls.append((paths, out_dir, cols, rows))
            if sheets is None:
                return [f"{out_dir}/sheet-01.jpg"]
            return outcome(sheets)

        def fake_require_tools():
            return tools

        def fake_ffmpeg_version():
            self.ffmpeg_version_calls += 1
            return FFMPEG_VERSION_LINE

        monkeypatch.setattr(seenby, "probe", fake_probe)
        monkeypatch.setattr(seenby, "thumbnails", fake_thumbnails)
        monkeypatch.setattr(seenby, "save_frames", fake_save_frames)
        monkeypatch.setattr(seenby, "contact_sheets", fake_contact_sheets)
        monkeypatch.setattr(seenby, "require_tools", fake_require_tools)
        monkeypatch.setattr(seenby, "ffmpeg_version", fake_ffmpeg_version)


def run_main(
    monkeypatch,
    capsys,
    tmp_path,
    argv,
    thumbs,
    probe=(15.0, 800, 600),
    frames=None,
    sheets=None,
    tools=None,
    video_exists=True,
    watch=None,
):
    monkeypatch.chdir(tmp_path)
    if video_exists:
        video = tmp_path / argv[0]
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"")
    run = Run(monkeypatch, probe, thumbs, frames, sheets, tools, watch)
    monkeypatch.setattr(sys, "argv", ["seenby.py"] + argv)
    run.rc = seenby.main()
    captured = capsys.readouterr()
    run.out = captured.out
    run.err = captured.err
    return run


def manifest(out_dir="out"):
    with open(os.path.join(out_dir, "frames.json"), encoding="utf-8") as fh:
        return json.load(fh)


def recheck(video, out_dir, n, time):
    return shlex.join(
        ["ffmpeg", "-ss", "%.3f" % time, "-i", video, "-frames:v", "1", "-q:v", "2", f"{out_dir}/frame-{n:02d}-native.jpg"]
    )


FRAME_KEYS = ["n", "time", "file", "sheet", "reason", "diff", "block", "recheck"]
ANALYSIS_KEYS = [
    "sample_fps", "thumbnails", "max_frames", "threshold", "max_gap", "block_k", "range", "segment", "all_timer"
]
TOP_LEVEL_KEYS = ["tool", "version", "ffmpeg", "video", "analysis", "sheet", "frames", "sheets", "segments"]
VIDEO_KEYS = ["name", "path", "duration", "width", "height", "ratio", "orientation", "grade"]
SHEET_KEYS = ["cols", "rows", "tile_width", "sheet_width", "count"]


def frame_entry(n, time, reason, diff=0.0, block=0.0, sheet=1, video="clip.mp4", out_dir="out"):
    return {
        "n": n,
        "time": time,
        "file": f"frame-{n:02d}.jpg",
        "sheet": sheet,
        "reason": reason,
        "diff": diff,
        "block": block,
        "recheck": recheck(video, out_dir, n, time),
    }


STATIC_30_TIMES = [0.0, 3.0, 6.0, 9.0, 12.0, 14.5]
STATIC_30_REASONS = ["first", "timer", "timer", "timer", "timer", "last"]


def static_30_manifest():
    return {
        "tool": "seenby",
        "version": 1,
        "ffmpeg": FFMPEG_VERSION_LINE,
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
            "all_timer": True,
        },
        "sheet": {"cols": 3, "rows": 3, "tile_width": 516, "sheet_width": 1568, "count": 1},
        "frames": [
            frame_entry(n, t, r) for n, (t, r) in enumerate(zip(STATIC_30_TIMES, STATIC_30_REASONS), start=1)
        ],
        "sheets": [{"file": "sheet-01.jpg", "frames": [1, 6]}],
        "segments": [{"n": 1, "from": 0.0, "to": 15.0, "frames": [1, 2, 3, 4, 5, 6]}],
    }


STATIC_30_DRY_RUN_STDOUT = (
    "clip.mp4: 15.0 s, 800x600, landscape\n"
    "  30 thumbnails, selected 6/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)\n"
    "  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last\n"
    "  layout: window, tile 516 px, 3x3 per sheet\n"
)
STATIC_30_STDOUT = (
    STATIC_30_DRY_RUN_STDOUT
    + "  contact sheets: out/sheet-01.jpg\n"
    + ALL_TIMER_LINE.format(threshold="12.0") + "\n"
    + MANIFEST_LINE.format(out_dir="out") + "\n"
)


# -------- anchored rows (CLI-1, CLI-3..7, CLI-9)


@pytest.mark.spec("CLI-1")
@pytest.mark.spec("CLI-6")
@pytest.mark.spec("CLI-7")
@pytest.mark.spec("CLI-17")
@pytest.mark.spec("CLI-21")
def test_cli_1_6_7_17_21_landscape_static_run(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4"], static(30), sheets=["video-frames/sheet-01.jpg"])
    times = [0.0, 3.0, 6.0, 9.0, 12.0, 14.5]
    frames = [f"video-frames/frame-{i:02d}.jpg" for i in range(1, 7)]
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.save_frames_calls == [("video.mp4", times, "video-frames", 516)]
    assert run.contact_sheets_calls == [(frames, "video-frames", 3, 3)]
    assert lines[0] == "video.mp4: 15.0 s, 800x600, landscape"
    assert lines[3] == "  layout: window, tile 516 px, 3x3 per sheet"
    assert lines[4] == "  contact sheets: video-frames/sheet-01.jpg"


@pytest.mark.spec("CLI-1")
@pytest.mark.spec("CLI-9")
def test_cli_1_9_default_out_dir_strips_extension_and_first_line_uses_basename(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["a/b.MOV"], static(4))
    assert run.rc == 0
    assert len(run.save_frames_calls) == 1
    assert run.save_frames_calls[0][0] == "a/b.MOV"
    assert run.save_frames_calls[0][2] == "a/b-frames"
    assert run.out.splitlines()[0] == "b.MOV: 15.0 s, 800x600, landscape"


@pytest.mark.spec("CLI-1")
def test_cli_1_explicit_out_dir_is_used(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(4))
    assert run.rc == 0
    assert run.save_frames_calls[0][2] == "out"


@pytest.mark.spec("CLI-17")
@pytest.mark.spec("CLI-21")
@pytest.mark.spec("MAN-3")
@pytest.mark.spec("MAN-12")
def test_cli_17_21_man_3_12_portrait_window_layout(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(30), probe=(15.0, 600, 800))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[0] == "video.mp4: 15.0 s, 600x800, portrait"
    assert lines[3] == "  layout: window, tile 516 px, 3x2 per sheet"
    assert run.save_frames_calls[0][2:] == ("out", 516)
    assert run.contact_sheets_calls[0][1:] == ("out", 3, 2)
    data = manifest()
    assert data["video"]["orientation"] == "portrait"
    assert data["video"]["grade"] == "window"


@pytest.mark.spec("CLI-17")
@pytest.mark.spec("CLI-21")
@pytest.mark.spec("MAN-12")
def test_cli_17_21_man_12_phone_layout(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(30), probe=(15.0, 576, 1280))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[0] == "video.mp4: 15.0 s, 576x1280, portrait"
    assert lines[3] == "  layout: phone, tile 256 px, 6x2 per sheet"
    assert run.save_frames_calls[0][3] == 256
    assert run.contact_sheets_calls[0][2:] == (6, 2)
    data = manifest()
    assert data["video"]["grade"] == "phone"
    assert data["sheet"] == {"cols": 6, "rows": 2, "tile_width": 256, "sheet_width": 1568, "count": 1}


@pytest.mark.spec("CLI-17")
@pytest.mark.spec("CLI-21")
@pytest.mark.spec("MAN-12")
def test_cli_17_21_man_12_wide_layout(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(30), probe=(15.0, 1920, 1080))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[3] == "  layout: wide, tile 776 px, 2x3 per sheet"
    assert run.save_frames_calls[0][3] == 776
    assert run.contact_sheets_calls[0][2:] == (2, 3)
    data = manifest()
    assert data["video"]["grade"] == "wide"
    assert data["sheet"] == {"cols": 2, "rows": 3, "tile_width": 776, "sheet_width": 1568, "count": 1}


@pytest.mark.spec("MAN-3")
@pytest.mark.spec("CLI-9")
@pytest.mark.spec("MAN-12")
def test_man_3_12_square_is_landscape_and_window(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(30), probe=(15.0, 500, 500))
    assert run.rc == 0
    assert run.out.splitlines()[0] == "video.mp4: 15.0 s, 500x500, landscape"
    assert run.out.splitlines()[3] == "  layout: window, tile 500 px, 3x3 per sheet"
    assert run.save_frames_calls[0][3] == 500
    assert run.contact_sheets_calls[0][2:] == (3, 3)
    data = manifest()
    assert data["video"]["orientation"] == "landscape"
    assert data["video"]["grade"] == "window"


@pytest.mark.spec("CLI-6")
def test_cli_6_save_frames_called_once_with_fit_to_cap_result(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], alt(20))
    expected, _, _ = seenby.fit_to_cap(alt(20), seenby.MAX_FRAMES, T, G)
    assert run.rc == 0
    assert run.save_frames_calls == [("video.mp4", expected, "out", 516)]


@pytest.mark.spec("CLI-7")
def test_cli_7_single_frame_skips_contact_sheets_and_lists_the_frame(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(1), frames=["out/frame-01.jpg"])
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.contact_sheets_calls == []
    assert lines[3] == "  layout: window, tile 516 px, 1x3 per sheet"
    assert lines[4] == "  contact sheets: out/frame-01.jpg"


@pytest.mark.spec("CLI-7")
@pytest.mark.spec("CLI-21")
def test_cli_7_21_single_frame_second_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(1), frames=["out/frame-01.jpg"])
    assert run.rc == 0
    assert run.out.splitlines()[1] == "  1 thumbnails, selected 1/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"


@pytest.mark.spec("CLI-7")
def test_cli_7_contact_sheets_gets_exactly_the_paths_save_frames_returned(monkeypatch, capsys, tmp_path):
    frames = ["x/one.jpg", "x/two.jpg"]
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(7), frames=frames)
    assert run.rc == 0
    assert len(run.contact_sheets_calls) == 1
    assert run.contact_sheets_calls[0][0] == frames


@pytest.mark.spec("CLI-9")
def test_cli_9_first_line_uses_probe_values_verbatim(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clips/demo.webm", "out"], static(4), probe=(31.25, 1920, 1080))
    assert run.rc == 0
    assert run.out.splitlines()[0] == "demo.webm: 31.2 s, 1920x1080, landscape"


@pytest.mark.spec("CLI-4")
def test_cli_4_no_thumbnails_reports_and_returns_one(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], [])
    assert run.rc == 1
    assert "could not decode the video: no frames" in run.err
    assert run.out == ""
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []


@pytest.mark.spec("CLI-3")
def test_cli_3_max_frames_below_two_is_an_argparse_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["seenby.py", "video.mp4", "out", "--max-frames", "1"])
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    assert exc.value.code == 2
    assert "--max-frames must be at least 2: the first and last frames are always kept" in capsys.readouterr().err


@pytest.mark.spec("CLI-3")
@pytest.mark.parametrize("argv", [[], ["video.mp4", "--bogus"]])
def test_cli_3_missing_video_or_unknown_flag_exits_two(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["seenby.py"] + argv)
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    assert exc.value.code == 2


# -------- CLI-10 (successor of CLI-2)


def expect_argparse_error(monkeypatch, capsys, tmp_path, argv, text):
    monkeypatch.chdir(tmp_path)
    (tmp_path / argv[0]).write_bytes(b"")
    Run(monkeypatch, (15.0, 800, 600), static(4), None, None, None, None)
    monkeypatch.setattr(sys, "argv", ["seenby.py"] + argv)
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    assert exc.value.code == 2
    assert text in capsys.readouterr().err


@pytest.mark.spec("CLI-10")
@pytest.mark.spec("CLI-15")
@pytest.mark.parametrize(
    "argv, text",
    [
        (["clip.mp4", "out", "--threshold", "0"], "--threshold must be above 0"),
        (["clip.mp4", "out", "--threshold", "-2.5"], "--threshold must be above 0"),
        (["clip.mp4", "out", "--max-gap", "-1"], "--max-gap must be above 0"),
        (["clip.mp4", "out", "--max-gap", "0"], "--max-gap must be above 0"),
        (["clip.mp4", "out", "--max-frames", "1"], "--max-frames must be at least 2: the first and last frames are always kept"),
    ],
)
def test_cli_10_out_of_range_option_is_an_argparse_error(monkeypatch, capsys, tmp_path, argv, text):
    expect_argparse_error(monkeypatch, capsys, tmp_path, argv, text)


@pytest.mark.spec("CLI-10")
def test_cli_10_help_lists_units_and_defaults(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["seenby.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for needle in ("default: 12.0", "default: 3.0", "default: 24", "seconds", "--force"):
        assert needle in out


@pytest.mark.spec("CLI-10")
def test_cli_10_threshold_and_max_gap_flags_reach_fit_to_cap(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out", "--threshold", "300", "--max-gap", "7"], alt(30))
    assert run.rc == 0
    assert run.save_frames_calls[0][1] == [0.0, 7.0, 14.0, 14.5]


@pytest.mark.spec("CLI-10")
@pytest.mark.spec("CLI-21")
def test_cli_10_21_threshold_and_max_gap_flags_are_printed(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out", "--threshold", "300", "--max-gap", "7"], alt(30))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  30 thumbnails, selected 4/24 (threshold 300.0 -> 300.0, max gap 7.0 -> 7.0 s)"
    assert lines[2] == "  frames: 0.0 first, 7.0 timer, 14.0 timer, 14.5 last"


@pytest.mark.spec("CLI-10")
def test_cli_10_max_frames_flag_reaches_fit_to_cap(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out", "--max-frames", "2"], alt(20))
    assert run.rc == 0
    assert run.save_frames_calls[0][1] == [0.0, 9.5]


@pytest.mark.spec("CLI-10")
@pytest.mark.spec("CLI-21")
def test_cli_10_21_max_frames_flag_is_printed_with_effective_values(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out", "--max-frames", "2"], alt(20))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  20 thumbnails, selected 2/2 (threshold 12.0 -> 307.5, max gap 3.0 -> 9.2 s)"
    assert lines[2] == "  frames: 0.0 first, 9.5 timer"


@pytest.mark.spec("CLI-10")
def test_cli_10_defaults_are_the_module_constants(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], alt(60))
    expected, _, _ = seenby.fit_to_cap(alt(60), seenby.MAX_FRAMES, T, G)
    assert run.rc == 0
    assert run.save_frames_calls[0][1] == expected
    assert len(expected) <= seenby.MAX_FRAMES
    assert (seenby.THRESHOLD, seenby.MAX_GAP, seenby.MAX_FRAMES) == (12.0, 3.0, 24)


# -------- CLI-11


@pytest.mark.spec("CLI-11")
def test_cli_11_missing_tools_stop_before_any_ffmpeg_call(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4), tools=FFMPEG_MISSING)
    assert run.rc == 1
    assert FFMPEG_MISSING in run.err
    assert len(run.err.splitlines()) == 1
    assert run.out == ""
    assert run.probe_calls == []
    assert run.thumbnails_calls == []
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []


@pytest.mark.spec("CLI-11")
def test_cli_11_missing_video_stops_before_any_ffmpeg_call(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["missing.mp4", "out"], static(4), video_exists=False)
    assert run.rc == 1
    assert "no such file: missing.mp4" in run.err
    assert len(run.err.splitlines()) == 1
    assert run.probe_calls == []
    assert run.thumbnails_calls == []
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []


@pytest.mark.spec("CLI-11")
def test_cli_11_foreign_frames_in_out_dir_are_refused(monkeypatch, capsys, tmp_path):
    (tmp_path / "out").mkdir()
    populate(tmp_path / "out", ["frame-01.jpg"])
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4))
    assert run.rc == 1
    assert "already holds frame-*.jpg" in run.err
    assert len(run.err.splitlines()) == 1
    assert run.probe_calls == []
    assert run.thumbnails_calls == []
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []


@pytest.mark.spec("CLI-11")
def test_cli_11_force_overrides_foreign_frames(monkeypatch, capsys, tmp_path):
    (tmp_path / "out").mkdir()
    populate(tmp_path / "out", ["frame-01.jpg"])
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--force"], static(4))
    assert run.rc == 0
    assert run.err == ""
    assert len(run.save_frames_calls) == 1


@pytest.mark.spec("CLI-11")
def test_cli_11_tools_are_checked_before_the_video_file(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["missing.mp4", "out"], static(4), tools=FFPROBE_MISSING, video_exists=False
    )
    assert run.rc == 1
    assert run.err.splitlines() == [FFPROBE_MISSING]


@pytest.mark.spec("CLI-11")
def test_cli_11_video_file_is_checked_before_out_dir(monkeypatch, capsys, tmp_path):
    (tmp_path / "out").mkdir()
    populate(tmp_path / "out", ["frame-01.jpg"])
    run = run_main(monkeypatch, capsys, tmp_path, ["missing.mp4", "out"], static(4), video_exists=False)
    assert run.rc == 1
    assert run.err.splitlines() == ["no such file: missing.mp4"]


# -------- CLI-12, CLI-13


@pytest.mark.spec("CLI-12")
def test_cli_12_probe_value_error_is_reported_with_the_video_name(monkeypatch, capsys, tmp_path):
    error = ValueError("could not read duration, width and height from ffprobe output")
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4), probe=error)
    assert run.rc == 1
    assert "clip.mp4: could not read duration, width and height from ffprobe output" in run.err
    assert len(run.err.splitlines()) == 1
    assert "Traceback" not in run.err
    assert run.thumbnails_calls == []
    assert run.save_frames_calls == []


@pytest.mark.spec("CLI-12")
@pytest.mark.parametrize(
    "stage, kwargs, expected",
    [
        ("probe", dict(probe=subprocess.CalledProcessError(2, ["ffprobe"], stderr="no stream\n")), "ffmpeg failed during probe (exit 2): no stream"),
        ("thumbnails", dict(thumbs=subprocess.CalledProcessError(1, ["ffmpeg"], stderr="x\nboom\n")), "ffmpeg failed during thumbnails (exit 1): boom"),
        ("frames", dict(frames=subprocess.CalledProcessError(69, ["ffmpeg"], stderr="bad frame")), "ffmpeg failed during frames (exit 69): bad frame"),
        ("sheets", dict(sheets=subprocess.CalledProcessError(3, ["ffmpeg"], stderr="no sheet")), "ffmpeg failed during sheets (exit 3): no sheet"),
    ],
)
def test_cli_12_failing_stage_is_reported_on_one_stderr_line(monkeypatch, capsys, tmp_path, stage, kwargs, expected):
    args = dict(thumbs=static(30))
    args.update(kwargs)
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], **args)
    assert run.rc == 1
    assert expected in run.err
    assert len(run.err.splitlines()) == 1
    assert "Traceback" not in run.err


@pytest.mark.spec("CLI-13")
def test_cli_13_previous_manifest_is_removed_before_probe_and_a_failed_run_leaves_none(monkeypatch, capsys, tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "frames.json").write_text('{"tool": "stale"}')
    populate(tmp_path / "out", ["frame-01.jpg"])
    run = run_main(
        monkeypatch,
        capsys,
        tmp_path,
        ["clip.mp4", "out"],
        subprocess.CalledProcessError(1, ["ffmpeg"], stderr="boom"),
        watch=str(tmp_path / "out" / "frames.json"),
    )
    assert run.rc == 1
    assert not (tmp_path / "out" / "frames.json").exists()
    assert run.watched["probe"] is False


@pytest.mark.spec("CLI-13")
def test_cli_13_probe_failure_leaves_no_manifest(monkeypatch, capsys, tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "frames.json").write_text("{}")
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4), probe=ValueError("ffprobe gave nothing"))
    assert run.rc == 1
    assert not (tmp_path / "out" / "frames.json").exists()


# -------- CLI-21, CLI-15 (CLI-21 is the successor of CLI-18, CLI-14 and CLI-8)


@pytest.mark.spec("CLI-21")
@pytest.mark.spec("MAN-1")
@pytest.mark.spec("MAN-2")
@pytest.mark.spec("MAN-3")
@pytest.mark.spec("MAN-4")
@pytest.mark.spec("MAN-7")
@pytest.mark.spec("MAN-8")
@pytest.mark.spec("MAN-9")
@pytest.mark.spec("MAN-10")
@pytest.mark.spec("MAN-11")
@pytest.mark.spec("MAN-12")
@pytest.mark.spec("MAN-13")
@pytest.mark.spec("MAN-14")
def test_cli_21_man_1_14_static_run_stdout_and_manifest(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    assert run.out == STATIC_30_STDOUT
    assert run.err == ""
    assert manifest() == static_30_manifest()
    assert os.listdir(tmp_path / "out") == ["frames.json"]


@pytest.mark.spec("CLI-21")
def test_cli_21_fewer_than_five_frames_print_six_lines(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(7))
    assert run.rc == 0
    assert run.out == (
        "video.mp4: 15.0 s, 800x600, landscape\n"
        "  7 thumbnails, selected 2/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)\n"
        "  frames: 0.0 first, 3.0 timer\n"
        "  layout: window, tile 516 px, 2x3 per sheet\n"
        "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )


@pytest.mark.spec("CLI-21")
def test_cli_21_two_sheets_are_joined_on_the_contact_sheets_line(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(61), sheets=["out/sheet-01.jpg", "out/sheet-02.jpg"]
    )
    assert run.rc == 0
    assert run.out == (
        "video.mp4: 15.0 s, 800x600, landscape\n"
        "  61 thumbnails, selected 11/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)\n"
        "  frames: 0.0 first, " + ", ".join("%.1f timer" % t for t in range(3, 31, 3)) + "\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
        "  contact sheets: out/sheet-01.jpg, out/sheet-02.jpg\n"
        + ALL_TIMER_LINE.format(threshold="12.0") + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )


@pytest.mark.spec("CLI-21")
@pytest.mark.spec("MAN-11")
def test_cli_21_man_11_no_all_timer_line_with_four_frames(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "300", "--max-gap", "7"], alt(30))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 6
    assert lines[1] == "  30 thumbnails, selected 4/24 (threshold 300.0 -> 300.0, max gap 7.0 -> 7.0 s)"
    assert lines[2] == "  frames: 0.0 first, 7.0 timer, 14.0 timer, 14.5 last"
    assert lines[3] == "  layout: window, tile 516 px, 3x3 per sheet"
    assert lines[5] == MANIFEST_LINE.format(out_dir="out")
    data = manifest()
    assert data["analysis"]["all_timer"] is False
    assert data["analysis"]["threshold"] == {"requested": 300.0, "effective": 300.0}
    assert data["analysis"]["max_gap"] == {"requested": 7.0, "effective": 7.0}


@pytest.mark.spec("CLI-21")
def test_cli_21_all_timer_line_carries_the_effective_threshold(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--max-frames", "5"], alt(20))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 7
    assert lines[1] == "  20 thumbnails, selected 5/5 (threshold 12.0 -> 307.5, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 9.5 last"
    assert lines[5] == ALL_TIMER_LINE.format(threshold="307.5")


@pytest.mark.spec("CLI-21")
def test_cli_21_default_out_dir_appears_on_the_manifest_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4"], static(4))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[4] == "  contact sheets: video-frames/sheet-01.jpg"
    assert lines[-1] == MANIFEST_LINE.format(out_dir="video-frames")


@pytest.mark.spec("CLI-21")
@pytest.mark.spec("MAN-7")
@pytest.mark.spec("MAN-8")
@pytest.mark.spec("MAN-12")
def test_cli_21_man_7_8_12_more_than_four_sheets_get_a_warning_line(monkeypatch, capsys, tmp_path):
    sheets = [f"out/sheet-{i:02d}.jpg" for i in range(1, 7)]
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--max-gap", "1", "--rows", "1"], static(30), sheets=sheets
    )
    times = [float(t) for t in range(15)] + [14.5]
    assert run.rc == 0
    assert run.save_frames_calls[0][1] == times
    assert run.contact_sheets_calls[0][2:] == (3, 1)
    assert run.out == (
        "clip.mp4: 15.0 s, 800x600, landscape\n"
        "  30 thumbnails, selected 16/24 (threshold 12.0 -> 12.0, max gap 1.0 -> 1.0 s)\n"
        "  frames: 0.0 first, " + ", ".join("%.1f timer" % t for t in range(1, 15)) + ", 14.5 last\n"
        "  layout: window, tile 516 px, 3x1 per sheet\n"
        "  contact sheets: " + ", ".join(sheets) + "\n"
        + MANY_SHEETS_LINE.format(n=6) + "\n"
        + ALL_TIMER_LINE.format(threshold="12.0") + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    assert len(run.out.splitlines()) == 8
    data = manifest()
    assert [f["sheet"] for f in data["frames"]] == [(n - 1) // 3 + 1 for n in range(1, 17)]
    assert data["sheets"] == [
        {"file": f"sheet-{k:02d}.jpg", "frames": [3 * k - 2, min(3 * k, 16)]} for k in range(1, 7)
    ]
    assert data["sheet"] == {"cols": 3, "rows": 1, "tile_width": 516, "sheet_width": 1568, "count": 6}


@pytest.mark.spec("CLI-21")
def test_cli_21_exactly_four_sheets_get_no_warning_line(monkeypatch, capsys, tmp_path):
    sheets = [f"out/sheet-{i:02d}.jpg" for i in range(1, 5)]
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--rows", "1"], static(61), sheets=sheets)
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.contact_sheets_calls[0][2:] == (3, 1)
    assert len(lines) == 7
    assert lines[3] == "  layout: window, tile 516 px, 3x1 per sheet"
    assert lines[4] == "  contact sheets: " + ", ".join(sheets)
    assert lines[5] == ALL_TIMER_LINE.format(threshold="12.0")
    assert "more than 4" not in run.out
    assert manifest()["sheet"]["count"] == 4


@pytest.mark.spec("CLI-21")
def test_cli_21_layout_line_reflects_the_flags(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--sheet-width", "1200", "--rows", "2"], static(30)
    )
    assert run.rc == 0
    assert run.out.splitlines()[3] == LAYOUT_LINE.format(grade="window", tile=393, cols=3, rows=2)


# -------- CLI-17 (draft, plan step 3)


@pytest.mark.spec("CLI-17")
@pytest.mark.spec("CLI-15")
@pytest.mark.parametrize(
    "argv, text",
    [
        (["clip.mp4", "out", "--sheet-width", "10"], "--sheet-width must be at least 64"),
        (["clip.mp4", "out", "--sheet-width", "63"], "--sheet-width must be at least 64"),
        (["clip.mp4", "out", "--rows", "0"], "--rows must be at least 1"),
        (["clip.mp4", "out", "--rows", "-3"], "--rows must be at least 1"),
        (["clip.mp4", "out", "--tile-width", "8"], "--tile-width must be at least 16"),
        (["clip.mp4", "out", "--tile-width", "15"], "--tile-width must be at least 16"),
        (["clip.mp4", "out", "--sample-fps", "0"], "--sample-fps must be above 0"),
        (["clip.mp4", "out", "--sample-fps", "-2"], "--sample-fps must be above 0"),
    ],
)
def test_cli_17_out_of_range_option_is_an_argparse_error(monkeypatch, capsys, tmp_path, argv, text):
    expect_argparse_error(monkeypatch, capsys, tmp_path, argv, text)


@pytest.mark.spec("CLI-17")
@pytest.mark.parametrize(
    "argv",
    [
        ["clip.mp4", "out", "--sheet-width", "64"],
        ["clip.mp4", "out", "--rows", "1"],
        ["clip.mp4", "out", "--tile-width", "16"],
        ["clip.mp4", "out", "--sample-fps", "0.5"],
    ],
)
def test_cli_17_boundary_values_are_accepted(monkeypatch, capsys, tmp_path, argv):
    run = run_main(monkeypatch, capsys, tmp_path, argv, static(4))
    assert run.rc == 0


@pytest.mark.spec("CLI-17")
def test_cli_17_help_lists_the_new_defaults_and_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["seenby.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for needle in ("default: 1568", "default: 2.0", "--dry-run", "--sheet-width", "--rows", "--tile-width", "--sample-fps"):
        assert needle in out


@pytest.mark.spec("CLI-17")
@pytest.mark.spec("MAN-12")
def test_cli_17_man_12_default_layout_reaches_the_stages_and_the_manifest(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    assert run.save_frames_calls[0][3] == 516
    assert run.contact_sheets_calls[0][2:] == (3, 3)
    data = manifest()
    assert data["video"]["grade"] == "window"
    assert data["sheet"] == {"cols": 3, "rows": 3, "tile_width": 516, "sheet_width": 1568, "count": 1}
    assert [f["sheet"] for f in data["frames"]] == [1] * 6


@pytest.mark.spec("CLI-17")
@pytest.mark.spec("MAN-12")
def test_cli_17_man_12_sheet_width_and_rows_reach_layout(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--sheet-width", "1200", "--rows", "2"], static(30)
    )
    assert run.rc == 0
    assert run.save_frames_calls[0][3] == 393
    assert run.contact_sheets_calls[0][2:] == (3, 2)
    assert manifest()["sheet"] == {"cols": 3, "rows": 2, "tile_width": 393, "sheet_width": 1200, "count": 1}


@pytest.mark.spec("CLI-17")
@pytest.mark.spec("MAN-12")
def test_cli_17_man_12_tile_width_reaches_layout(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--tile-width", "300"], static(30))
    assert run.rc == 0
    assert run.save_frames_calls[0][3] == 300
    assert run.contact_sheets_calls[0][2:] == (5, 6)
    assert run.out.splitlines()[3] == "  layout: window, tile 300 px, 5x6 per sheet"
    assert manifest()["sheet"] == {"cols": 5, "rows": 6, "tile_width": 300, "sheet_width": 1568, "count": 1}


@pytest.mark.spec("CLI-17")
@pytest.mark.spec("CLI-20")
@pytest.mark.spec("MAN-13")
def test_cli_17_20_man_13_sample_fps_reaches_thumbnails_and_the_selection(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--sample-fps", "4"], static(40))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.thumbnails_calls == [("clip.mp4", 4.0, 0.0, None)]
    assert run.save_frames_calls[0][1] == [0.0, 3.0, 6.0, 9.0, 9.75]
    assert lines[1] == "  40 thumbnails, selected 5/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    data = manifest()
    assert [f["time"] for f in data["frames"]] == [0.0, 3.0, 6.0, 9.0, 9.75]
    assert [f["reason"] for f in data["frames"]] == ["first", "timer", "timer", "timer", "last"]
    assert data["frames"][4]["recheck"] == recheck("clip.mp4", "out", 5, 9.75)
    assert data["analysis"]["thumbnails"] == 40
    assert data["analysis"]["sample_fps"] == 4.0
    assert isinstance(data["analysis"]["sample_fps"], float)


@pytest.mark.spec("MAN-13")
def test_man_13_default_sample_fps_is_recorded_as_a_float(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4))
    assert run.rc == 0
    value = manifest()["analysis"]["sample_fps"]
    assert value == 2.0
    assert isinstance(value, float)
    with open(os.path.join("out", "frames.json"), encoding="utf-8") as fh:
        assert '"sample_fps": 2.0' in fh.read()


@pytest.mark.spec("MAN-12")
@pytest.mark.spec("MAN-14")
def test_man_12_14_grade_follows_orientation_and_sheet_keys_are_exact(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30), probe=(15.0, 576, 1280))
    assert run.rc == 0
    data = manifest()
    assert list(data["video"]) == VIDEO_KEYS
    assert data["video"]["orientation"] == "portrait"
    assert data["video"]["grade"] == "phone"
    assert list(data["sheet"]) == SHEET_KEYS
    assert list(data) == TOP_LEVEL_KEYS


# -------- CLI-19 (draft, plan step 3)


@pytest.mark.spec("CLI-19")
def test_cli_19_dry_run_prints_four_lines_and_extracts_nothing(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], static(30))
    assert run.rc == 0
    assert run.out == STATIC_30_DRY_RUN_STDOUT
    assert run.err == ""
    assert run.probe_calls == ["clip.mp4"]
    assert len(run.thumbnails_calls) == 1
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []
    assert run.ffmpeg_version_calls == 0
    assert not (tmp_path / "out").exists()
    assert os.listdir(tmp_path) == ["clip.mp4"]


@pytest.mark.spec("CLI-19")
def test_cli_19_dry_run_does_not_create_the_default_out_dir(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "--dry-run"], static(4))
    assert run.rc == 0
    assert run.save_frames_calls == []
    assert not (tmp_path / "video-frames").exists()


@pytest.mark.spec("CLI-19")
def test_cli_19_dry_run_still_refuses_foreign_frames(monkeypatch, capsys, tmp_path):
    (tmp_path / "out").mkdir()
    populate(tmp_path / "out", ["frame-01.jpg"])
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], static(30))
    assert run.rc == 1
    assert run.err.splitlines() == ["out already holds frame-*.jpg from something else; pass --force to overwrite"]
    assert run.out == ""
    assert run.probe_calls == []
    assert run.thumbnails_calls == []
    assert (tmp_path / "out" / "frame-01.jpg").is_file()


@pytest.mark.spec("CLI-19")
def test_cli_19_dry_run_leaves_an_existing_out_dir_untouched(monkeypatch, capsys, tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "frames.json").write_text('{"tool": "stale"}')
    populate(tmp_path / "out", ["frame-01.jpg", "sheet-01.jpg"])
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], static(30))
    assert run.rc == 0
    assert run.out == STATIC_30_DRY_RUN_STDOUT
    assert sorted(os.listdir(tmp_path / "out")) == ["frame-01.jpg", "frames.json", "sheet-01.jpg"]
    assert (tmp_path / "out" / "frames.json").read_text() == '{"tool": "stale"}'


@pytest.mark.spec("CLI-19")
def test_cli_19_dry_run_runs_the_tool_and_video_checks(monkeypatch, capsys, tmp_path):
    no_tools = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], static(4), tools=FFMPEG_MISSING)
    assert no_tools.rc == 1
    assert no_tools.err.splitlines() == [FFMPEG_MISSING]
    assert no_tools.probe_calls == []
    no_video = run_main(monkeypatch, capsys, tmp_path, ["missing.mp4", "out", "--dry-run"], static(4), video_exists=False)
    assert no_video.rc == 1
    assert no_video.err.splitlines() == ["no such file: missing.mp4"]
    assert no_video.probe_calls == []
    assert not (tmp_path / "out").exists()


@pytest.mark.spec("CLI-19")
def test_cli_19_dry_run_reports_no_frames_like_a_full_run(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], [])
    assert run.rc == 1
    assert "could not decode the video: no frames" in run.err
    assert run.out == ""
    assert not (tmp_path / "out").exists()


@pytest.mark.spec("CLI-15")
def test_cli_15_success_returns_zero(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4))
    assert run.rc == 0


@pytest.mark.spec("CLI-15")
def test_cli_15_runtime_failures_return_one(monkeypatch, capsys, tmp_path):
    no_frames = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], [])
    assert no_frames.rc == 1
    missing_tools = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out2"], static(4), tools=FFMPEG_MISSING)
    assert missing_tools.rc == 1
    failed_stage = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out3"], subprocess.CalledProcessError(1, ["ffmpeg"], stderr="boom")
    )
    assert failed_stage.rc == 1


@pytest.mark.spec("CLI-15")
def test_cli_15_argparse_errors_exit_two(monkeypatch, capsys, tmp_path):
    expect_argparse_error(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--max-gap", "0"], "--max-gap must be above 0")


# -------- MAN-1..9


@pytest.mark.spec("MAN-1")
@pytest.mark.spec("MAN-14")
def test_man_1_14_manifest_has_exactly_the_top_level_keys_and_is_written_last(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30), watch=str(tmp_path / "out" / "frames.json"))
    assert run.rc == 0
    assert run.watched["contact_sheets"] is False
    assert list(manifest()) == TOP_LEVEL_KEYS


@pytest.mark.spec("MAN-2")
def test_man_2_tool_version_and_ffmpeg_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4))
    assert run.rc == 0
    data = manifest()
    assert data["tool"] == "seenby"
    assert data["version"] == 1
    assert seenby.VERSION == 1
    assert data["ffmpeg"] == FFMPEG_VERSION_LINE


@pytest.mark.spec("MAN-3")
@pytest.mark.spec("MAN-12")
def test_man_3_12_video_block_from_probe(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clips/demo.webm", "out"], static(4), probe=(31.25, 1920, 1080))
    assert run.rc == 0
    video = manifest()["video"]
    assert video == {
        "name": "demo.webm",
        "path": "clips/demo.webm",
        "duration": 31.25,
        "width": 1920,
        "height": 1080,
        "ratio": 1.778,
        "orientation": "landscape",
        "grade": "wide",
    }
    assert list(video) == VIDEO_KEYS


@pytest.mark.spec("MAN-3")
@pytest.mark.spec("MAN-12")
def test_man_3_12_portrait_video_and_sheet_blocks(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30), probe=(15.0, 600, 800))
    assert run.rc == 0
    data = manifest()
    assert data["video"]["orientation"] == "portrait"
    assert data["video"]["ratio"] == 0.75
    assert data["video"]["grade"] == "window"
    assert data["sheet"] == {"cols": 3, "rows": 2, "tile_width": 516, "sheet_width": 1568, "count": 1}
    assert list(data["sheet"]) == SHEET_KEYS
    assert [f["sheet"] for f in data["frames"]] == [1] * 6


@pytest.mark.spec("MAN-4")
@pytest.mark.spec("MAN-10")
@pytest.mark.spec("MAN-11")
@pytest.mark.spec("MAN-14")
def test_man_4_10_11_14_analysis_block_carries_requested_and_effective_values(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--max-frames", "5"], alt(20))
    assert run.rc == 0
    data = manifest()
    assert data["analysis"] == {
        "sample_fps": 2.0,
        "thumbnails": 20,
        "max_frames": 5,
        "threshold": {"requested": 12.0, "effective": 307.546875},
        "max_gap": {"requested": 3.0, "effective": 3.0},
        "block_k": 5.0,
        "range": {"from": 0.0, "to": 15.0},
        "segment": 120.0,
        "all_timer": True,
    }
    assert [f["time"] for f in data["frames"]] == [0.0, 3.0, 6.0, 9.0, 9.5]
    assert [f["reason"] for f in data["frames"]] == ["first", "timer", "timer", "timer", "last"]


@pytest.mark.spec("MAN-4")
def test_man_4_requested_values_are_the_flags_as_given(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "300", "--max-gap", "7"], alt(30))
    assert run.rc == 0
    data = manifest()["analysis"]
    assert data["thumbnails"] == 30
    assert data["max_frames"] == 24
    assert data["threshold"] == {"requested": 300.0, "effective": 300.0}
    assert data["max_gap"] == {"requested": 7.0, "effective": 7.0}


@pytest.mark.spec("MAN-11")
@pytest.mark.spec("MAN-7")
def test_man_11_7_diff_frames_turn_all_timer_off(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], ramp())
    assert run.rc == 0
    data = manifest()
    assert [f["reason"] for f in data["frames"]] == ["first", "diff", "diff", "diff"]
    assert [f["diff"] for f in data["frames"]] == [0.0, 15.0, 15.0, 15.0]
    assert [f["block"] for f in data["frames"]] == [0.0, 15.0, 15.0, 15.0]
    assert data["analysis"]["all_timer"] is False


@pytest.mark.spec("MAN-11")
def test_man_11_five_timer_frames_turn_all_timer_on(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    data = manifest()
    assert len(data["frames"]) == 6
    assert not {"diff", "block"} & {f["reason"] for f in data["frames"]}
    assert data["analysis"]["all_timer"] is True


@pytest.mark.spec("MAN-11")
def test_man_11_four_timer_frames_keep_all_timer_off(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(20))
    assert run.rc == 0
    data = manifest()
    assert len(data["frames"]) == 5
    assert data["analysis"]["all_timer"] is True
    shorter = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out2"], static(19))
    assert shorter.rc == 0
    data = manifest("out2")
    assert len(data["frames"]) == 4
    assert data["analysis"]["all_timer"] is False


@pytest.mark.spec("MAN-7")
@pytest.mark.spec("MAN-8")
@pytest.mark.spec("MAN-12")
def test_man_7_8_12_frames_spread_over_two_sheets_of_nine(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(61), sheets=["out/sheet-01.jpg", "out/sheet-02.jpg"]
    )
    assert run.rc == 0
    data = manifest()
    assert [f["time"] for f in data["frames"]] == [float(t) for t in range(0, 31, 3)]
    assert [f["n"] for f in data["frames"]] == list(range(1, 12))
    assert [f["reason"] for f in data["frames"]] == ["first"] + ["timer"] * 10
    assert [f["sheet"] for f in data["frames"]] == [1] * 9 + [2, 2]
    assert data["sheets"] == [
        {"file": "sheet-01.jpg", "frames": [1, 9]},
        {"file": "sheet-02.jpg", "frames": [10, 11]},
    ]
    assert data["sheet"] == {"cols": 3, "rows": 3, "tile_width": 516, "sheet_width": 1568, "count": 2}


@pytest.mark.spec("MAN-7")
@pytest.mark.spec("MAN-8")
@pytest.mark.spec("MAN-12")
def test_man_7_8_12_single_frame_has_no_sheet(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(1), frames=["out/frame-01.jpg"])
    assert run.rc == 0
    data = manifest()
    assert len(data["frames"]) == 1
    assert data["frames"][0]["sheet"] is None
    assert data["sheets"] == []
    assert data["sheet"] == {"cols": 1, "rows": 3, "tile_width": 516, "sheet_width": 1568, "count": 0}


@pytest.mark.spec("MAN-7")
def test_man_7_frame_entries_and_recheck_commands(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    frames = manifest()["frames"]
    assert frames[0] == {
        "n": 1,
        "time": 0.0,
        "file": "frame-01.jpg",
        "sheet": 1,
        "reason": "first",
        "diff": 0.0,
        "block": 0.0,
        "recheck": "ffmpeg -ss 0.000 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-01-native.jpg",
    }
    assert frames[5] == {
        "n": 6,
        "time": 14.5,
        "file": "frame-06.jpg",
        "sheet": 1,
        "reason": "last",
        "diff": 0.0,
        "block": 0.0,
        "recheck": "ffmpeg -ss 14.500 -i clip.mp4 -frames:v 1 -q:v 2 out/frame-06-native.jpg",
    }
    assert all(set(f) == set(FRAME_KEYS) for f in frames)


@pytest.mark.spec("MAN-7")
def test_man_7_recheck_quotes_paths_with_spaces(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["my clip.mp4", "out dir"], static(4))
    assert run.rc == 0
    frames = manifest("out dir")["frames"]
    assert frames[0]["recheck"] == "ffmpeg -ss 0.000 -i 'my clip.mp4' -frames:v 1 -q:v 2 'out dir/frame-01-native.jpg'"


@pytest.mark.spec("MAN-7")
@pytest.mark.spec("MAN-8")
def test_man_7_8_file_names_are_basenames_of_what_the_stages_returned(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch,
        capsys,
        tmp_path,
        ["clip.mp4", "out"],
        static(7),
        frames=["x/one.jpg", "x/two.jpg"],
        sheets=["y/tiles.jpg"],
    )
    assert run.rc == 0
    data = manifest()
    assert [f["file"] for f in data["frames"]] == ["one.jpg", "two.jpg"]
    assert data["sheets"] == [{"file": "tiles.jpg", "frames": [1, 2]}]


@pytest.mark.spec("MAN-9")
def test_man_9_out_dir_holds_only_the_manifest_with_fakes(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    assert os.listdir(tmp_path / "out") == ["frames.json"]
    assert sorted(os.listdir(tmp_path)) == ["clip.mp4", "out"]


# -------- CLI-16, MAN-10, MAN-11 (draft, plan step 4)

BLOCKY_FRAMES_LINE = "  frames: 0.0 first, " + ", ".join("%.1f block" % (i / 2) for i in range(1, 20))


@pytest.mark.spec("CLI-16")
@pytest.mark.spec("CLI-15")
@pytest.mark.parametrize("value", ["-1", "-0.5"])
def test_cli_16_negative_block_k_is_an_argparse_error(monkeypatch, capsys, tmp_path, value):
    expect_argparse_error(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--block-k", value], "--block-k must be 0 or above")


@pytest.mark.spec("CLI-16")
def test_cli_16_help_lists_the_default_and_the_off_switch(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["seenby.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--block-k" in out
    assert "default: 5.0" in out
    assert "0 disables" in out


@pytest.mark.spec("CLI-16")
@pytest.mark.spec("MAN-10")
@pytest.mark.spec("MAN-11")
def test_cli_16_man_10_11_default_block_k_keeps_every_block_frame(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], blocky())
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 6
    assert lines[1] == "  20 thumbnails, selected 20/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == BLOCKY_FRAMES_LINE
    assert run.save_frames_calls[0][1] == [i / 2 for i in range(20)]
    data = manifest()
    assert len(data["frames"]) == 20
    assert data["analysis"]["block_k"] == 5.0
    assert data["frames"][1]["block"] == 100.0
    assert data["frames"][1]["diff"] == 6.25
    assert data["frames"][1]["reason"] == "block"
    assert [f["reason"] for f in data["frames"][1:]] == ["block"] * 19
    assert data["analysis"]["all_timer"] is False


@pytest.mark.spec("CLI-16")
@pytest.mark.spec("MAN-10")
@pytest.mark.spec("MAN-11")
def test_cli_16_man_10_11_block_k_zero_leaves_the_timer_frames(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--block-k", "0"], blocky())
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 7
    assert lines[1] == "  20 thumbnails, selected 5/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 9.5 last"
    assert lines[5] == ALL_TIMER_LINE.format(threshold="12.0")
    assert run.save_frames_calls[0][1] == [0.0, 3.0, 6.0, 9.0, 9.5]
    data = manifest()
    assert len(data["frames"]) == 5
    assert data["analysis"]["block_k"] == 0.0
    assert data["frames"][4]["time"] == 9.5
    assert data["frames"][4]["diff"] == 6.25
    assert data["frames"][4]["block"] == 100.0
    assert data["frames"][4]["reason"] == "last"
    assert data["frames"][1]["time"] == 3.0
    assert data["frames"][1]["block"] == 0.0
    assert data["analysis"]["all_timer"] is True


@pytest.mark.spec("CLI-16")
def test_cli_16_block_k_reaches_fit_to_cap(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--block-k", "0.5", "--max-frames", "2"], blocky())
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.save_frames_calls[0][1] == [0.0, 9.5]
    assert lines[1] == "  20 thumbnails, selected 2/2 (threshold 12.0 -> 205.0, max gap 3.0 -> 9.2 s)"
    data = manifest()
    assert data["analysis"]["block_k"] == 0.5
    assert data["analysis"]["threshold"] == {"requested": 12.0, "effective": 205.03125}
    assert data["analysis"]["max_gap"] == {"requested": 3.0, "effective": 9.1552734375}


@pytest.mark.spec("MAN-10")
def test_man_10_block_k_is_recorded_as_a_float_as_given(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--block-k", "2.5"], static(4))
    assert run.rc == 0
    value = manifest()["analysis"]["block_k"]
    assert value == 2.5
    assert isinstance(value, float)


@pytest.mark.spec("MAN-10")
def test_man_10_key_order_in_analysis_and_frame_entries(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    data = manifest()
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert all(list(f) == FRAME_KEYS for f in data["frames"])
    assert [f["block"] for f in data["frames"]] == [0.0] * 6


@pytest.mark.spec("MAN-10")
def test_man_10_frame_block_is_the_block_max_against_the_previous_kept(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], [flat(0), straddle(100), flat(0), flat(0)])
    assert run.rc == 0
    frames = manifest()["frames"]
    assert [f["time"] for f in frames] == [0.0, 1.5]
    assert frames[1]["diff"] == 0.0
    assert frames[1]["block"] == 0.0
    assert frames[1]["reason"] == "last"
    second = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out2"], [flat(0), straddle(100)])
    assert second.rc == 0
    frames = manifest("out2")["frames"]
    assert [f["time"] for f in frames] == [0.0, 0.5]
    assert frames[1]["diff"] == 6.25
    assert frames[1]["block"] == 50.0
    assert frames[1]["reason"] == "last"


@pytest.mark.spec("MAN-11")
def test_man_11_one_block_frame_among_timers_turns_all_timer_off(monkeypatch, capsys, tmp_path):
    thumbs = static(11) + [patch(100)] + static(18)
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], thumbs)
    lines = run.out.splitlines()
    assert run.rc == 0
    data = manifest()
    assert [f["time"] for f in data["frames"]] == [0.0, 3.0, 5.5, 6.0, 9.0, 12.0, 14.5]
    assert [f["reason"] for f in data["frames"]] == ["first", "timer", "block", "block", "timer", "timer", "last"]
    assert [f["block"] for f in data["frames"]] == [0.0, 0.0, 100.0, 100.0, 0.0, 0.0, 0.0]
    assert data["analysis"]["all_timer"] is False
    assert len(lines) == 6
    off = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out2", "--block-k", "0"], thumbs)
    lines = off.out.splitlines()
    assert off.rc == 0
    data = manifest("out2")
    assert [f["time"] for f in data["frames"]] == [0.0, 3.0, 6.0, 9.0, 12.0, 14.5]
    assert [f["reason"] for f in data["frames"]] == ["first", "timer", "timer", "timer", "timer", "last"]
    assert data["analysis"]["all_timer"] is True
    assert len(lines) == 7


# -------- CLI-20, CLI-21, MAN-14 (draft, plan step 5)


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("CLI-15")
@pytest.mark.parametrize(
    "argv, text",
    [
        (["clip.mp4", "out", "--from", "-1"], "--from must be 0 or above"),
        (["clip.mp4", "out", "--from", "-0.5"], "--from must be 0 or above"),
        (["clip.mp4", "out", "--to", "0"], "--to must be above 0"),
        (["clip.mp4", "out", "--to", "-3"], "--to must be above 0"),
        (["clip.mp4", "out", "--segment", "0"], "--segment must be above 0"),
        (["clip.mp4", "out", "--segment", "-5"], "--segment must be above 0"),
        (["clip.mp4", "out", "--from", "10", "--to", "10"], "--to must be above --from"),
        (["clip.mp4", "out", "--from", "10", "--to", "5"], "--to must be above --from"),
    ],
)
def test_cli_20_out_of_range_range_option_is_an_argparse_error(monkeypatch, capsys, tmp_path, argv, text):
    expect_argparse_error(monkeypatch, capsys, tmp_path, argv, text)


@pytest.mark.spec("CLI-20")
@pytest.mark.parametrize(
    "argv, text",
    [
        (["clip.mp4", "out", "--from", "15"], "--from 15.0 is past the end of the video (15.0 s)"),
        (["clip.mp4", "out", "--from", "16.5"], "--from 16.5 is past the end of the video (15.0 s)"),
        (["clip.mp4", "out", "--to", "20"], "--to 20.0 is past the end of the video (15.0 s)"),
        (["clip.mp4", "out", "--from", "1", "--to", "15.5"], "--to 15.5 is past the end of the video (15.0 s)"),
    ],
)
def test_cli_20_range_past_the_end_of_the_video_returns_one_after_probe(monkeypatch, capsys, tmp_path, argv, text):
    run = run_main(monkeypatch, capsys, tmp_path, argv, static(30))
    assert run.rc == 1
    assert text in run.err
    assert "Traceback" not in run.err
    assert run.probe_calls == ["clip.mp4"]
    assert run.thumbnails_calls == []
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("CLI-21")
@pytest.mark.spec("MAN-14")
def test_cli_20_21_man_14_to_equal_to_the_duration_is_accepted(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--to", "15"], static(30))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.err == ""
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 0.0, 15.0)]
    assert run.save_frames_calls[0][1] == STATIC_30_TIMES
    assert lines[1] == "  range: 0.0-15.0 s"
    assert lines[2] == "  30 thumbnails, selected 6/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert len(lines) == 8
    data = manifest()
    assert data["analysis"]["range"] == {"from": 0.0, "to": 15.0}
    assert data["segments"] == [segment(1, 0.0, 15.0, [1, 2, 3, 4, 5, 6])]


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("MAN-14")
def test_cli_20_man_14_to_below_the_duration_bounds_the_range(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--to", "12"], static(24))
    assert run.rc == 0
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 0.0, 12.0)]
    assert run.save_frames_calls[0][1] == [0.0, 3.0, 6.0, 9.0, 11.5]
    assert run.out.splitlines()[1] == "  range: 0.0-12.0 s"
    data = manifest()
    assert data["analysis"]["range"] == {"from": 0.0, "to": 12.0}
    assert data["segments"] == [segment(1, 0.0, 12.0, [1, 2, 3, 4, 5])]


@pytest.mark.spec("CLI-20")
def test_cli_20_from_zero_is_accepted_and_prints_the_range(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--from", "0"], static(30))
    assert run.rc == 0
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 0.0, 15.0)]
    assert run.save_frames_calls[0][1] == STATIC_30_TIMES
    assert run.out.splitlines()[1] == RANGE_LINE.format(start="0.0", end="15.0")


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("CLI-21")
def test_cli_20_21_default_run_passes_start_zero_no_length_and_prints_no_range_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 0.0, None)]
    assert not any(line.startswith("  range:") for line in lines)
    assert len(lines) == 7
    assert run.save_frames_calls[0][1] == STATIC_30_TIMES


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("CLI-21")
@pytest.mark.spec("MAN-14")
def test_cli_20_21_man_14_range_shifts_every_time_and_fills_the_segments(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch,
        capsys,
        tmp_path,
        ["clip.mp4", "out", "--from", "10", "--to", "25", "--segment", "5"],
        static(30),
        probe=(60.0, 800, 600),
    )
    times = [10.0, 13.0, 16.0, 19.0, 22.0, 24.5]
    assert run.rc == 0
    assert run.err == ""
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 10.0, 15.0)]
    assert run.save_frames_calls == [("clip.mp4", times, "out", 516)]
    assert run.out == (
        "clip.mp4: 60.0 s, 800x600, landscape\n"
        "  range: 10.0-25.0 s\n"
        "  30 thumbnails, selected 6/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)\n"
        "  frames: 10.0 first, 13.0 timer, 16.0 timer, 19.0 timer, 22.0 timer, 24.5 last\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
        "  contact sheets: out/sheet-01.jpg\n"
        + ALL_TIMER_LINE.format(threshold="12.0") + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    assert all(line.startswith("  ") for line in run.out.splitlines()[1:])
    data = manifest()
    assert [f["time"] for f in data["frames"]] == times
    assert data["frames"][1]["time"] == 13.0
    assert "-ss 13.000" in data["frames"][1]["recheck"]
    assert [f["recheck"] for f in data["frames"]] == [recheck("clip.mp4", "out", n, t) for n, t in enumerate(times, start=1)]
    assert [f["reason"] for f in data["frames"]] == STATIC_30_REASONS
    assert data["analysis"]["thumbnails"] == 30
    assert data["analysis"]["range"] == {"from": 10.0, "to": 25.0}
    assert data["analysis"]["segment"] == 5.0
    assert data["analysis"]["all_timer"] is True
    assert data["segments"] == [
        segment(1, 10.0, 15.0, [1, 2]),
        segment(2, 15.0, 20.0, [3, 4]),
        segment(3, 20.0, 25.0, [5, 6]),
    ]


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("MAN-14")
def test_cli_20_man_14_from_alone_runs_to_the_end_of_the_video(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--from", "3", "--segment", "4"], static(24))
    times = [3.0, 6.0, 9.0, 12.0, 14.5]
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 3.0, 12.0)]
    assert run.save_frames_calls[0][1] == times
    assert lines[1] == "  range: 3.0-15.0 s"
    assert lines[2] == "  24 thumbnails, selected 5/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[3] == "  frames: 3.0 first, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last"
    data = manifest()
    assert [f["time"] for f in data["frames"]] == times
    assert data["frames"][0]["recheck"] == recheck("clip.mp4", "out", 1, 3.0)
    assert data["analysis"]["range"] == {"from": 3.0, "to": 15.0}
    assert data["analysis"]["segment"] == 4.0
    assert data["segments"] == [
        segment(1, 3.0, 7.0, [1, 2]),
        segment(2, 7.0, 11.0, [3]),
        segment(3, 11.0, 15.0, [4, 5]),
    ]


@pytest.mark.spec("MAN-14")
def test_man_14_default_range_segment_and_segments(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    data = manifest()
    assert list(data) == TOP_LEVEL_KEYS
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["range"] == {"from": 0.0, "to": 15.0}
    assert list(data["analysis"]["range"]) == ["from", "to"]
    assert isinstance(data["analysis"]["range"]["from"], float)
    assert isinstance(data["analysis"]["range"]["to"], float)
    assert data["analysis"]["segment"] == 120.0
    assert isinstance(data["analysis"]["segment"], float)
    assert data["segments"] == [segment(1, 0.0, 15.0, [1, 2, 3, 4, 5, 6])]
    assert data["segments"] == seenby.segments(STATIC_30_TIMES, 0.0, 15.0, 120.0)
    with open(os.path.join("out", "frames.json"), encoding="utf-8") as fh:
        content = fh.read()
    assert '"from": 0.0' in content
    assert '"segment": 120.0' in content


@pytest.mark.spec("MAN-14")
def test_man_14_segments_follow_the_segment_flag_over_the_default_range(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--segment", "5"], static(30))
    assert run.rc == 0
    assert not any(line.startswith("  range:") for line in run.out.splitlines())
    data = manifest()
    assert data["analysis"]["range"] == {"from": 0.0, "to": 15.0}
    assert data["analysis"]["segment"] == 5.0
    assert data["segments"] == [
        segment(1, 0.0, 5.0, [1, 2]),
        segment(2, 5.0, 10.0, [3, 4]),
        segment(3, 10.0, 15.0, [5, 6]),
    ]


@pytest.mark.spec("CLI-21")
def test_cli_21_hint_lines_point_at_the_range_flags(monkeypatch, capsys, tmp_path):
    sheets = [f"out/sheet-{i:02d}.jpg" for i in range(1, 7)]
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--max-gap", "1", "--rows", "1"], static(30), sheets=sheets
    )
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[5] == "  6 contact sheets are more than 4; consider --max-frames or --from/--to"
    assert lines[6] == (
        "  all frames taken by the timer: the threshold contributed nothing (effective 12.0); "
        "try --max-frames, --block-k or --from/--to"
    )


@pytest.mark.spec("CLI-21")
def test_cli_21_range_line_comes_second_and_shifts_the_warning_lines(monkeypatch, capsys, tmp_path):
    sheets = [f"out/sheet-{i:02d}.jpg" for i in range(1, 7)]
    run = run_main(
        monkeypatch,
        capsys,
        tmp_path,
        ["clip.mp4", "out", "--max-gap", "1", "--rows", "1", "--to", "15"],
        static(30),
        sheets=sheets,
    )
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 9
    assert lines[1] == "  range: 0.0-15.0 s"
    assert lines[4] == "  layout: window, tile 516 px, 3x1 per sheet"
    assert lines[5] == "  contact sheets: " + ", ".join(sheets)
    assert lines[6] == MANY_SHEETS_LINE.format(n=6)
    assert lines[7] == ALL_TIMER_LINE.format(threshold="12.0")
    assert lines[8] == MANIFEST_LINE.format(out_dir="out")


@pytest.mark.spec("CLI-19")
@pytest.mark.spec("CLI-21")
def test_cli_19_21_dry_run_with_a_range_prints_five_lines(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run", "--from", "3"], static(30))
    assert run.rc == 0
    assert run.out == (
        "clip.mp4: 15.0 s, 800x600, landscape\n"
        "  range: 3.0-15.0 s\n"
        "  30 thumbnails, selected 6/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)\n"
        "  frames: 3.0 first, 6.0 timer, 9.0 timer, 12.0 timer, 15.0 timer, 17.5 last\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
    )
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 3.0, 12.0)]
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []
    assert run.ffmpeg_version_calls == 0
    assert not (tmp_path / "out").exists()
