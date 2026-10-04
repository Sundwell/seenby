"""Acceptance tests for seenby, written from docs/specs/seenby.md and docs/specs/api/seenby.txt."""

import json
import math
import os
import random
import shlex
import subprocess
import sys
from itertools import combinations, permutations, product

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


def thumb_grid(cells):
    """Thumbnail from a set of (row, col, value) cells, everything else 0."""
    pixels = bytearray(SIZE)
    for row, col, value in cells:
        pixels[row * seenby.THUMB + col] = value
    return bytes(pixels)


def patch(v):
    return thumb_grid((r, c, v) for r in range(8) for c in range(8))


def straddle(v):
    return thumb_grid((r, c, v) for r in range(8) for c in range(4, 12))


def pixel(v):
    return thumb_grid([(0, 0, v)])


def blocky():
    return [flat(0), patch(100)] * 10


def steps(a, b):
    return [flat(0)] * 10 + [flat(a)] * 10 + [flat(b)] * 10


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
    ((526, 514, 3), {}, ("window", 516, 3, 2, 1)),
    ((720, 1280, 14), {}, ("phone", 256, 6, 3, 1)),
    ((576, 1280, 3), {}, ("phone", 256, 3, 2, 1)),
    ((2560, 1228, 8), {}, ("wide", 776, 2, 3, 2)),
    ((1636, 1228, 5), {}, ("window", 516, 3, 3, 1)),
    ((576, 1280, 9), {}, ("phone", 256, 6, 2, 1)),
    ((576, 1280, 20), {}, ("phone", 256, 6, 2, 2)),
    ((100, 2000, 5), {}, ("phone", 100, 5, 1, 1)),
    ((1600, 1000, 6), {}, ("window", 516, 3, 4, 1)),
    ((1601, 1000, 6), {}, ("wide", 776, 2, 3, 1)),
    ((750, 1000, 6), {}, ("window", 516, 3, 2, 1)),
    ((749, 1000, 6), {}, ("phone", 256, 6, 4, 1)),
    ((500, 500, 6), {}, ("window", 500, 3, 2, 1)),
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
@pytest.mark.spec("LBL-3")
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
        ((1032, 989, 6), {}, 3),
        ((814, 872, 12), {}, 2),
        ((100, 2000, 5), {}, 1),
        ((800, 600, 6, 1200, 2), {}, 2),
        ((800, 600, 30), {"rows": 1}, 1),
        ((800, 600, 6), {"rows": 5}, 5),
    ],
    ids=["round-half-even-322", "round-half-even-494", "two-rows", "taller-than-sheet", "rows-2-given", "rows-1-given", "rows-5-given"],
)
def test_lay_3_rows_fill_the_sheet_height_or_are_used_as_given(args, kwargs, rows):
    assert seenby.layout(*args, **kwargs)[3] == rows


@pytest.mark.spec("LAY-3")
@pytest.mark.spec("LBL-3")
def test_lay_3_lbl_3_tile_height_rounds_half_to_even():
    grade, tile, cols, rows, sheets = seenby.layout(1032, 989, 6)
    assert (grade, tile) == ("window", 516)
    assert tile * 989 / 1032 == 494.5
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


def manifest_segment(n, start, end, frames, activity=0.0):
    """A `segments` entry as frames.json carries it (MAN-15): the `segments()` entry plus `activity`."""
    return dict(segment(n, start, end, frames), activity=activity)


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
ALL_TIMER_M_LINE = (
    "  all frames taken by the timer: the largest change between thumbnails was {m}, "
    "under the threshold {threshold}"
)
ALL_TIMER_M_SUGGEST_LINE = (
    ALL_TIMER_M_LINE + "; --threshold {t}: {content} content frames at threshold {t2} ({sheets} sheets)"
)
LAYOUT_LINE = "  layout: {grade}, tile {tile} px, {cols}x{rows} per sheet"
MANY_SHEETS_LINE = "  {n} contact sheets are more than 4; consider --max-frames or --from/--to"
RANGE_LINE = "  range: {start}-{end} s"
BLOCK_LINE = "  block rule inactive: bar {bar} ({block_k} x {threshold}) is at or above 255"
BIGGER_CAP_LINE = (
    "  {timer} of {loop} frames by the timer; "
    "--max-frames {c2}: {n2} content frames at threshold {t2} ({s2} sheets); "
    "--max-frames {c3}: {n3} content frames at threshold {t3} ({s3} sheets)"
)
NO_CAP_HELPS_LINE = "  {timer} of {loop} frames by the timer; no cap up to {c3} adds a content frame"


def outcome(value):
    if isinstance(value, BaseException):
        raise value
    return value


class Run:
    """Fakes for the ffmpeg-facing functions, recording the calls main() makes.

    `probe`, `thumbs`, `frames` and `sheets` are returned by the matching fake, or raised when they are
    exceptions. `change_grids` returns `(20, 10, samples)`, or raises `samples` when it is an exception.
    `save_samples` returns `frames` like `save_frames`, one path per index when `frames` is None.
    `display_size` returns `(width, height)` unchanged, or `display` when given (raised when it is an exception).
    `ffmpeg_version` returns `version`.
    `contact_sheets` takes `boxes` as a fifth argument, default None (BOX-3), recorded in `contact_sheets_boxes`
    beside `contact_sheets_calls`, and the number of arguments of each call in `contact_sheets_arity`.
    `kept_changes` returns `changes`, or raises it when it is an exception; without `changes` it returns `None`
    for the first index and two all-zero 20 x 10 grids for every other (BOX-3 examples).
    `contact_sheets` also takes `marks` as a sixth argument, default None (CRP-6), recorded in
    `contact_sheets_marks`.
    `write_crops` records its arguments in `write_crops_calls` and returns `crops` (None by default), or raises it
    when it is an exception (CRP-6).
    `watch` is a path whose existence is recorded at the moment each fake is called.
    """

    def __init__(
        self, monkeypatch, probe, thumbs, frames, sheets, tools, watch, samples=None, display=None,
        version=FFMPEG_VERSION_LINE, changes=None, crops=None,
    ):
        self.probe_calls = []
        self.thumbnails_calls = []
        self.display_size_calls = []
        self.change_grids_calls = []
        self.save_frames_calls = []
        self.save_samples_calls = []
        self.contact_sheets_calls = []
        self.contact_sheets_boxes = []
        self.contact_sheets_arity = []
        self.contact_sheets_marks = []
        self.write_crops_calls = []
        self.kept_changes_calls = []
        self.saved_samples = []
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

        def fake_display_size(path, width, height):
            note("display_size")
            self.display_size_calls.append((path, width, height))
            if display is None:
                return (width, height)
            return outcome(display)

        def fake_change_grids(path, width, height, fps=4, start=0.0, length=None):
            note("change_grids")
            self.change_grids_calls.append((path, width, height, fps, start, length))
            if isinstance(samples, BaseException):
                raise samples
            return (20, 10, samples)

        def fake_save_frames(path, times, out_dir, tile_width):
            note("save_frames")
            self.save_frames_calls.append((path, times, out_dir, tile_width))
            if frames is None:
                return [f"{out_dir}/frame-{i:02d}.jpg" for i in range(1, len(times) + 1)]
            return outcome(frames)

        def fake_save_samples(path, indices, times, out_dir, tile_width, fps=4, start=0.0, length=None):
            note("save_samples")
            self.save_samples_calls.append((path, indices, times, out_dir, tile_width, fps, start, length))
            if frames is None:
                self.saved_samples = [f"{out_dir}/frame-{i:02d}.jpg" for i in range(1, len(indices) + 1)]
            else:
                self.saved_samples = outcome(frames)
            return self.saved_samples

        def fake_kept_changes(path, indices, width, height, fps=4, start=0.0, length=None):
            note("kept_changes")
            self.kept_changes_calls.append((path, indices, width, height, fps, start, length))
            if changes is None:
                return [None] + [(bytes(20 * 10), bytes(20 * 10))] * (len(indices) - 1)
            return outcome(changes)

        def fake_contact_sheets(paths, out_dir, cols, rows, boxes=None, marks=None):
            note("contact_sheets")
            self.contact_sheets_calls.append((paths, out_dir, cols, rows))
            self.contact_sheets_boxes.append(boxes)
            self.contact_sheets_marks.append(marks)
            if sheets is None:
                return [f"{out_dir}/sheet-01.jpg"]
            return outcome(sheets)

        def counted_contact_sheets(*args, **kwargs):
            self.contact_sheets_arity.append(len(args) + len(kwargs))
            return fake_contact_sheets(*args, **kwargs)

        def fake_write_crops(
            path, out_dir, screens, crop_list, tiles, points, width, height, fps=4, start=0.0, length=None
        ):
            note("write_crops")
            self.write_crops_calls.append(
                (path, out_dir, screens, crop_list, tiles, points, width, height, fps, start, length)
            )
            return outcome(crops)

        def fake_require_tools():
            return tools

        def fake_ffmpeg_version():
            self.ffmpeg_version_calls += 1
            return version

        monkeypatch.setattr(seenby, "probe", fake_probe)
        monkeypatch.setattr(seenby, "thumbnails", fake_thumbnails)
        monkeypatch.setattr(seenby, "display_size", fake_display_size, raising=False)
        monkeypatch.setattr(seenby, "change_grids", fake_change_grids, raising=False)
        monkeypatch.setattr(seenby, "save_frames", fake_save_frames)
        monkeypatch.setattr(seenby, "save_samples", fake_save_samples, raising=False)
        monkeypatch.setattr(seenby, "contact_sheets", counted_contact_sheets)
        monkeypatch.setattr(seenby, "kept_changes", fake_kept_changes, raising=False)
        monkeypatch.setattr(seenby, "write_crops", fake_write_crops)
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
    samples=None,
    display=None,
    version=FFMPEG_VERSION_LINE,
    as_given=False,
    changes=None,
    crops=None,
):
    """main() with the fakes in place. Unless `as_given`, an argv without `--selector` gets the selector its row
    implies (CLI-28): `legacy` for a row that fakes only `thumbnails`, `events` for one that fakes `change_grids`."""
    monkeypatch.chdir(tmp_path)
    if video_exists:
        video = tmp_path / argv[0]
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"")
    if not as_given and "--selector" not in argv:
        argv = argv + ["--selector", "legacy" if samples is None else "events"]
    run = Run(monkeypatch, probe, thumbs, frames, sheets, tools, watch, samples, display, version, changes, crops)
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
    "sample_fps", "thumbnails", "max_frames", "threshold", "max_gap", "block_k", "block_active", "range", "segment",
    "all_timer", "timer_share", "quiet",
]
SEGMENT_KEYS = ["n", "from", "to", "frames", "activity"]
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
            "block_active": True,
            "range": {"from": 0.0, "to": 15.0},
            "segment": 120.0,
            "all_timer": True,
            "timer_share": 1.0,
            "quiet": [],
        },
        "sheet": {"cols": 3, "rows": 3, "tile_width": 516, "sheet_width": 1568, "count": 1},
        "frames": [
            frame_entry(n, t, r) for n, (t, r) in enumerate(zip(STATIC_30_TIMES, STATIC_30_REASONS), start=1)
        ],
        "sheets": [{"file": "sheet-01.jpg", "frames": [1, 6]}],
        "segments": [{"n": 1, "from": 0.0, "to": 15.0, "frames": [1, 2, 3, 4, 5, 6], "activity": 0.0}],
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
    + ALL_TIMER_M_LINE.format(m="0.0", threshold="12.0") + "\n"
    + MANIFEST_LINE.format(out_dir="out") + "\n"
)


# -------- anchored rows (CLI-1, CLI-3..7, CLI-9)


@pytest.mark.spec("CLI-1")
@pytest.mark.spec("CLI-6")
@pytest.mark.spec("CLI-7")
@pytest.mark.spec("CLI-17")
@pytest.mark.spec("CLI-23")
def test_cli_1_6_7_17_23_landscape_static_run(monkeypatch, capsys, tmp_path):
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
@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-3")
@pytest.mark.spec("MAN-12")
def test_cli_17_23_man_3_12_portrait_window_layout(monkeypatch, capsys, tmp_path):
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
@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-12")
def test_cli_17_23_man_12_phone_layout(monkeypatch, capsys, tmp_path):
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
@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-12")
def test_cli_17_23_man_12_wide_layout(monkeypatch, capsys, tmp_path):
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
@pytest.mark.spec("LBL-3")
def test_man_3_12_lbl_3_square_is_landscape_and_window(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4", "out"], static(30), probe=(15.0, 500, 500))
    assert run.rc == 0
    assert run.out.splitlines()[0] == "video.mp4: 15.0 s, 500x500, landscape"
    assert run.out.splitlines()[3] == "  layout: window, tile 500 px, 3x2 per sheet"
    assert run.save_frames_calls[0][3] == 500
    assert run.contact_sheets_calls[0][2:] == (3, 2)
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
@pytest.mark.spec("CLI-23")
def test_cli_7_23_single_frame_second_line(monkeypatch, capsys, tmp_path):
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
    if "--selector" not in argv:
        argv = argv + ["--selector", "legacy"]
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
@pytest.mark.spec("CLI-23")
def test_cli_10_23_threshold_and_max_gap_flags_are_printed(monkeypatch, capsys, tmp_path):
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
@pytest.mark.spec("CLI-23")
def test_cli_10_23_max_frames_flag_is_printed_with_effective_values(monkeypatch, capsys, tmp_path):
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
        ("sheets-ffprobe", dict(sheets=subprocess.CalledProcessError(1, ["ffprobe"], stderr="x\nno width\n")), "ffmpeg failed during sheets (exit 1): no width"),
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


# -------- CLI-23, CLI-15 (CLI-23 is the successor of CLI-22, CLI-21, CLI-18, CLI-14 and CLI-8)


@pytest.mark.spec("CLI-23")
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
@pytest.mark.spec("MAN-15")
def test_cli_23_man_1_15_static_run_stdout_and_manifest(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    assert run.out == STATIC_30_STDOUT
    assert run.err == ""
    assert manifest() == static_30_manifest()
    assert os.listdir(tmp_path / "out") == ["frames.json"]


@pytest.mark.spec("CLI-23")
def test_cli_23_fewer_than_five_frames_print_six_lines(monkeypatch, capsys, tmp_path):
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


@pytest.mark.spec("CLI-23")
def test_cli_23_two_sheets_are_joined_on_the_contact_sheets_line(monkeypatch, capsys, tmp_path):
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
        + ALL_TIMER_M_LINE.format(m="0.0", threshold="12.0") + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )


@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-11")
def test_cli_23_man_11_no_all_timer_line_with_four_frames(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "300", "--max-gap", "7"], alt(30))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 7
    assert lines[1] == "  30 thumbnails, selected 4/24 (threshold 300.0 -> 300.0, max gap 7.0 -> 7.0 s)"
    assert lines[2] == "  frames: 0.0 first, 7.0 timer, 14.0 timer, 14.5 last"
    assert lines[3] == "  layout: window, tile 516 px, 3x3 per sheet"
    assert lines[4] == BLOCK_LINE.format(bar="1500.0", block_k="5.0", threshold="300.0")
    assert lines[5] == "  contact sheets: out/sheet-01.jpg"
    assert lines[6] == MANIFEST_LINE.format(out_dir="out")
    assert "frames by the timer;" not in run.out
    assert "all frames taken by the timer" not in run.out
    data = manifest()
    assert data["analysis"]["all_timer"] is False
    assert data["analysis"]["threshold"] == {"requested": 300.0, "effective": 300.0}
    assert data["analysis"]["max_gap"] == {"requested": 7.0, "effective": 7.0}


@pytest.mark.spec("CLI-23")
@pytest.mark.spec("CLI-24")
def test_cli_23_24_all_timer_line_carries_the_effective_threshold(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--max-frames", "5"], alt(20))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 9
    assert lines[1] == "  20 thumbnails, selected 5/5 (threshold 12.0 -> 307.5, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 9.5 last"
    assert lines[4] == BLOCK_LINE.format(bar="1537.7", block_k="5.0", threshold="307.5")
    assert lines[5] == NO_CAP_HELPS_LINE.format(timer=3, loop=3, c3=15)
    assert lines[7] == ALL_TIMER_LINE.format(threshold="307.5")


@pytest.mark.spec("CLI-23")
def test_cli_23_default_out_dir_appears_on_the_manifest_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["video.mp4"], static(4))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[4] == "  contact sheets: video-frames/sheet-01.jpg"
    assert lines[-1] == MANIFEST_LINE.format(out_dir="video-frames")


@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-7")
@pytest.mark.spec("MAN-8")
@pytest.mark.spec("MAN-12")
def test_cli_23_man_7_8_12_more_than_four_sheets_get_a_warning_line(monkeypatch, capsys, tmp_path):
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
        + ALL_TIMER_M_LINE.format(m="0.0", threshold="12.0") + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    assert len(run.out.splitlines()) == 8
    data = manifest()
    assert [f["sheet"] for f in data["frames"]] == [(n - 1) // 3 + 1 for n in range(1, 17)]
    assert data["sheets"] == [
        {"file": f"sheet-{k:02d}.jpg", "frames": [3 * k - 2, min(3 * k, 16)]} for k in range(1, 7)
    ]
    assert data["sheet"] == {"cols": 3, "rows": 1, "tile_width": 516, "sheet_width": 1568, "count": 6}


@pytest.mark.spec("CLI-23")
def test_cli_23_exactly_four_sheets_get_no_warning_line(monkeypatch, capsys, tmp_path):
    sheets = [f"out/sheet-{i:02d}.jpg" for i in range(1, 5)]
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--rows", "1"], static(61), sheets=sheets)
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.contact_sheets_calls[0][2:] == (3, 1)
    assert len(lines) == 7
    assert lines[3] == "  layout: window, tile 516 px, 3x1 per sheet"
    assert lines[4] == "  contact sheets: " + ", ".join(sheets)
    assert lines[5] == ALL_TIMER_M_LINE.format(m="0.0", threshold="12.0")
    assert "more than 4" not in run.out
    assert manifest()["sheet"]["count"] == 4


@pytest.mark.spec("CLI-23")
def test_cli_23_layout_line_reflects_the_flags(monkeypatch, capsys, tmp_path):
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
@pytest.mark.spec("MAN-15")
def test_man_12_15_grade_follows_orientation_and_sheet_keys_are_exact(monkeypatch, capsys, tmp_path):
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
@pytest.mark.spec("MAN-15")
def test_man_1_15_manifest_has_exactly_the_top_level_keys_and_is_written_last(monkeypatch, capsys, tmp_path):
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
@pytest.mark.spec("MAN-15")
def test_man_4_10_11_15_analysis_block_carries_requested_and_effective_values(monkeypatch, capsys, tmp_path):
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
        "block_active": False,
        "range": {"from": 0.0, "to": 15.0},
        "segment": 120.0,
        "all_timer": True,
        "timer_share": 1.0,
        "quiet": [],
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
@pytest.mark.spec("CLI-25")
@pytest.mark.spec("MAN-16")
def test_cli_16_man_10_11_25_block_k_zero_finds_a_quiet_stretch(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--block-k", "0"], blocky(), probe=(10.0, 800, 600))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 7
    assert lines[0] == "clip.mp4: 10.0 s, 800x600, landscape"
    assert lines[1] == "  20 thumbnails, selected 20/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, " + ", ".join("%.1f diff" % (i / 2) for i in range(1, 20))
    assert lines[3] == quiet_line([{"from": 0.0, "to": 9.5, "threshold": 2.0, "largest": 6.25}])
    assert "all frames taken by the timer" not in run.out
    assert run.save_frames_calls[0][1] == [i / 2 for i in range(20)]
    data = manifest()
    assert len(data["frames"]) == 20
    assert data["analysis"]["block_k"] == 0.0
    assert data["analysis"]["quiet"] == [{"from": 0.0, "to": 9.5, "largest": 6.25, "threshold": 2.0}]
    assert data["frames"][1]["time"] == 0.5
    assert data["frames"][1]["reason"] == "diff"
    assert data["frames"][1]["diff"] == 6.25
    assert data["frames"][1]["block"] == 100.0
    assert data["frames"][-1]["time"] == 9.5
    assert data["frames"][-1]["reason"] == "diff"
    assert data["frames"][-1]["diff"] == 6.25
    assert data["frames"][-1]["block"] == 100.0
    assert data["analysis"]["all_timer"] is False


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
@pytest.mark.spec("MAN-15")
def test_man_10_15_key_order_in_analysis_and_frame_entries(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    data = manifest()
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert all(list(f) == FRAME_KEYS for f in data["frames"])
    assert [f["block"] for f in data["frames"]] == [0.0] * 6


@pytest.mark.spec("MAN-10")
@pytest.mark.spec("CLI-25")
def test_man_10_frame_block_is_the_block_max_against_the_previous_kept(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], [flat(0), straddle(100), flat(0), flat(0)],
        probe=(2.0, 800, 600),
    )
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[2] == "  frames: 0.0 first, 0.5 diff, 1.0 diff, 1.5 last"
    assert lines[3] == quiet_line([{"from": 0.0, "to": 1.5, "threshold": 2.0, "largest": 6.25}])
    frames = manifest()["frames"]
    assert [f["time"] for f in frames] == [0.0, 0.5, 1.0, 1.5]
    assert frames[1]["diff"] == 6.25
    assert frames[1]["block"] == 50.0
    assert frames[3]["diff"] == 0.0
    assert frames[3]["block"] == 0.0
    assert frames[3]["reason"] == "last"
    second = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out2"], [flat(0), straddle(100)])
    assert second.rc == 0
    frames = manifest("out2")["frames"]
    assert [f["time"] for f in frames] == [0.0, 0.5]
    assert frames[1]["diff"] == 6.25
    assert frames[1]["block"] == 50.0
    assert frames[1]["reason"] == "last"


@pytest.mark.spec("MAN-11")
@pytest.mark.spec("CLI-25")
@pytest.mark.spec("MAN-16")
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
    assert data["analysis"]["quiet"] == []
    assert len(lines) == 6

    off = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out2", "--block-k", "0"], thumbs)
    lines = off.out.splitlines()
    assert off.rc == 0
    data = manifest("out2")
    assert [f["time"] for f in data["frames"]] == [0.0, 3.0, 5.5, 6.0, 9.0, 12.0, 14.5]
    assert [f["reason"] for f in data["frames"]] == ["first", "timer", "diff", "diff", "timer", "timer", "last"]
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 5.5 diff, 6.0 diff, 9.0 timer, 12.0 timer, 14.5 last"
    assert lines[3] == quiet_line([{"from": 0.0, "to": 14.5, "threshold": 2.0, "largest": 6.25}])
    assert "all frames taken by the timer" not in off.out
    assert data["analysis"]["all_timer"] is False
    assert data["analysis"]["quiet"] == [{"from": 0.0, "to": 14.5, "largest": 6.25, "threshold": 2.0}]
    assert len(lines) == 7


# -------- CLI-20, CLI-23, MAN-15 (plan step 5; CLI-23 and MAN-15 succeed CLI-21 and MAN-14)


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
@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-15")
def test_cli_20_23_man_15_to_equal_to_the_duration_is_accepted(monkeypatch, capsys, tmp_path):
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
    assert data["segments"] == [manifest_segment(1, 0.0, 15.0, [1, 2, 3, 4, 5, 6])]


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("MAN-15")
def test_cli_20_man_15_to_below_the_duration_bounds_the_range(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--to", "12"], static(24))
    assert run.rc == 0
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 0.0, 12.0)]
    assert run.save_frames_calls[0][1] == [0.0, 3.0, 6.0, 9.0, 11.5]
    assert run.out.splitlines()[1] == "  range: 0.0-12.0 s"
    data = manifest()
    assert data["analysis"]["range"] == {"from": 0.0, "to": 12.0}
    assert data["segments"] == [manifest_segment(1, 0.0, 12.0, [1, 2, 3, 4, 5])]


@pytest.mark.spec("CLI-20")
def test_cli_20_from_zero_is_accepted_and_prints_the_range(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--from", "0"], static(30))
    assert run.rc == 0
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 0.0, 15.0)]
    assert run.save_frames_calls[0][1] == STATIC_30_TIMES
    assert run.out.splitlines()[1] == RANGE_LINE.format(start="0.0", end="15.0")


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("CLI-23")
def test_cli_20_23_default_run_passes_start_zero_no_length_and_prints_no_range_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 0.0, None)]
    assert not any(line.startswith("  range:") for line in lines)
    assert len(lines) == 7
    assert run.save_frames_calls[0][1] == STATIC_30_TIMES


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-15")
def test_cli_20_23_man_15_range_shifts_every_time_and_fills_the_segments(monkeypatch, capsys, tmp_path):
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
        + ALL_TIMER_M_LINE.format(m="0.0", threshold="12.0") + "\n"
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
        manifest_segment(1, 10.0, 15.0, [1, 2]),
        manifest_segment(2, 15.0, 20.0, [3, 4]),
        manifest_segment(3, 20.0, 25.0, [5, 6]),
    ]
    assert all(list(e) == SEGMENT_KEYS for e in data["segments"])


@pytest.mark.spec("CLI-20")
@pytest.mark.spec("MAN-15")
def test_cli_20_man_15_from_alone_runs_to_the_end_of_the_video(monkeypatch, capsys, tmp_path):
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
        manifest_segment(1, 3.0, 7.0, [1, 2]),
        manifest_segment(2, 7.0, 11.0, [3]),
        manifest_segment(3, 11.0, 15.0, [4, 5]),
    ]


@pytest.mark.spec("MAN-15")
def test_man_15_default_range_segment_and_segments(monkeypatch, capsys, tmp_path):
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
    assert data["segments"] == [manifest_segment(1, 0.0, 15.0, [1, 2, 3, 4, 5, 6])]
    assert data["segments"] == [
        dict(e, activity=a)
        for e, a in zip(seenby.segments(STATIC_30_TIMES, 0.0, 15.0, 120.0), seenby.activity(static(30), 0.0, 15.0, 120.0))
    ]
    with open(os.path.join("out", "frames.json"), encoding="utf-8") as fh:
        content = fh.read()
    assert '"from": 0.0' in content
    assert '"segment": 120.0' in content


@pytest.mark.spec("MAN-15")
def test_man_15_segments_follow_the_segment_flag_over_the_default_range(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--segment", "5"], static(30))
    assert run.rc == 0
    assert not any(line.startswith("  range:") for line in run.out.splitlines())
    data = manifest()
    assert data["analysis"]["range"] == {"from": 0.0, "to": 15.0}
    assert data["analysis"]["segment"] == 5.0
    assert data["segments"] == [
        manifest_segment(1, 0.0, 5.0, [1, 2]),
        manifest_segment(2, 5.0, 10.0, [3, 4]),
        manifest_segment(3, 10.0, 15.0, [5, 6]),
    ]


@pytest.mark.spec("CLI-23")
@pytest.mark.spec("CLI-24")
def test_cli_23_hint_lines_point_at_the_range_flags(monkeypatch, capsys, tmp_path):
    sheets = [f"out/sheet-{i:02d}.jpg" for i in range(1, 7)]
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--max-gap", "1", "--rows", "1"], static(30), sheets=sheets
    )
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[5] == "  6 contact sheets are more than 4; consider --max-frames or --from/--to"
    assert lines[6] == ALL_TIMER_M_LINE.format(m="0.0", threshold="12.0")


@pytest.mark.spec("CLI-23")
def test_cli_23_range_line_comes_second_and_shifts_the_warning_lines(monkeypatch, capsys, tmp_path):
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
    assert lines[7] == ALL_TIMER_M_LINE.format(m="0.0", threshold="12.0")
    assert lines[8] == MANIFEST_LINE.format(out_dir="out")


@pytest.mark.spec("CLI-19")
@pytest.mark.spec("CLI-23")
def test_cli_19_23_dry_run_with_a_range_prints_five_lines(monkeypatch, capsys, tmp_path):
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


# ---------------------------------------------------------------- Step 9: honest cap and budget (draft)


def long_ramp():
    """The step 9 `ramp`: 50 s static, then 25 thumbnails climbing by 10 grey levels (125 thumbnails, 62.0 s)."""
    return static(100) + [flat(10 * i) for i in range(1, 26)]


def two():
    return static(60) + [flat(10 * i) for i in range(1, 26)] + static(60) + [flat(10 * i) for i in range(1, 26)]


def saw():
    return static(120) + [flat(30 * (i % 8)) for i in range(48)]


def mixed():
    return [flat(0), patch(100), patch(100), flat(0)]


def reasons_at(thumbs, threshold, max_gap):
    return [d["reason"] for d in seenby.select_frames(thumbs, threshold, max_gap)]


def content_count(thumbs, threshold, max_gap):
    return sum(r in ("diff", "block") for r in reasons_at(thumbs, threshold, max_gap))


# -------- SEG-4 activity


@pytest.mark.spec("SEG-4")
@pytest.mark.parametrize(
    "thumbs, start, end, length, expected",
    [
        (static(20), 0.0, 9.5, 120.0, [0.0]),
        (alt(4), 0.0, 1.5, 120.0, [255.0]),
        (mixed(), 0.0, 1.5, 120.0, [4.17]),
        (static(20), 0.0, 9.5, 5.0, [0.0, 0.0]),
        (long_ramp(), 0.0, 62.0, 30.0, [0.0, 3.39, 10.0]),
        (static(3), 10.0, 11.0, 0.4, [0.0, 0.0, 0.0]),
    ],
    ids=["static-one-entry", "alt", "mixed", "static-two-entries", "long-ramp", "single-thumbnail-entries"],
)
def test_seg_4_activity_example_rows(thumbs, start, end, length, expected):
    result = seenby.activity(thumbs, start, end, length)
    assert result == expected
    assert all(isinstance(value, float) for value in result)


@pytest.mark.spec("SEG-4")
@pytest.mark.parametrize(
    "thumbs, start, end, length",
    [
        (static(20), 0.0, 9.5, 120.0),
        (static(20), 0.0, 9.5, 5.0),
        (long_ramp(), 0.0, 62.0, 30.0),
        (static(3), 10.0, 11.0, 0.4),
        ([], 0.0, 250.0, 120.0),
        (static(30), 0.0, 15.0, 120.0),
    ],
)
def test_seg_4_one_value_per_segments_entry(thumbs, start, end, length):
    result = seenby.activity(thumbs, start, end, length)
    assert len(result) == len(seenby.segments([], start, end, length))


@pytest.mark.spec("SEG-4")
def test_seg_4_thumbnail_times_start_at_the_range_start():
    assert seenby.activity(mixed(), 10.0, 11.5, 120.0) == [4.17]
    assert seenby.activity(alt(4), 10.0, 11.0, 0.5) == [0.0, 255.0]


@pytest.mark.spec("SEG-4")
def test_seg_4_sample_fps_places_the_thumbnails():
    assert seenby.activity(alt(4), 0.0, 1.5, 0.5, 4) == [255.0, 255.0, 0.0]
    assert seenby.activity(alt(4), 0.0, 1.5, 0.5, sample_fps=4) == [255.0, 255.0, 0.0]
    assert seenby.activity(alt(4), 0.0, 1.5, 120.0, seenby.SAMPLE_FPS) == seenby.activity(alt(4), 0.0, 1.5, 120.0)


@pytest.mark.spec("SEG-4")
def test_seg_4_only_pairs_inside_one_entry_count():
    thumbs = [flat(0), flat(0), flat(200), flat(200)]
    assert seenby.activity(thumbs, 0.0, 1.5, 1.0) == [0.0, 0.0]
    assert seenby.activity(thumbs, 0.0, 1.5, 120.0) == [66.67]


# -------- CAP-8, CAP-9 second fit


@pytest.mark.spec("CAP-8")
def test_cap_8_gate_closed_below_51_keeps_the_first_fit():
    times, threshold, max_gap = seenby.fit_to_cap(long_ramp(), 24, T, G)
    assert (threshold, max_gap) == (40.5, 3.0)
    assert len(times) == 23
    assert times == seenby.select(long_ramp(), threshold, max_gap)
    assert content_count(long_ramp(), 40.5, 3.0) == 4
    assert threshold < 255 / seenby.BLOCK_K


@pytest.mark.spec("CAP-8")
@pytest.mark.spec("CAP-9")
def test_cap_8_9_long_ramp_at_cap_12_takes_the_second_fit():
    times, threshold, max_gap = seenby.fit_to_cap(long_ramp(), 12, T, G)
    assert times == [0.0, 7.5, 15.0, 22.5, 30.0, 37.5, 45.0, 52.0, 54.5, 57.0, 59.5, 62.0]
    assert (threshold, max_gap) == (40.5, 7.32421875)
    assert times == seenby.select(long_ramp(), threshold, max_gap)
    assert content_count(long_ramp(), threshold, max_gap) == 5


@pytest.mark.spec("CAP-8")
def test_cap_8_second_fit_gap_is_a_rung_of_the_ladder():
    _, _, max_gap = seenby.fit_to_cap(long_ramp(), 12, T, G)
    rung = G
    ladder = [rung]
    for _ in range(4):
        rung = rung * 1.25
        ladder.append(rung)
    assert max_gap == ladder[-1]


@pytest.mark.spec("CAP-8")
@pytest.mark.spec("CAP-9")
def test_cap_8_9_two_ramps_keep_nine_content_frames():
    times, threshold, max_gap = seenby.fit_to_cap(two(), 24, T, G)
    assert (threshold, max_gap) == (40.5, 4.6875)
    assert len(times) == 23
    assert times == seenby.select(two(), threshold, max_gap)
    frames = seenby.select_frames(two(), threshold, max_gap)
    assert [d["time"] for d in frames if d["reason"] == "diff"] == [32.5, 35.0, 37.5, 40.0, 42.5, 75.0, 77.5, 80.0, 82.5]
    assert content_count(two(), threshold, max_gap) == 9


@pytest.mark.spec("CAP-8")
@pytest.mark.spec("CAP-9")
def test_cap_8_9_saw_keeps_eleven_content_frames():
    times, threshold, max_gap = seenby.fit_to_cap(saw(), 24, T, G)
    assert (threshold, max_gap) == (91.125, 5.859375)
    assert len(times) == 23
    assert times == seenby.select(saw(), threshold, max_gap)
    frames = seenby.select_frames(saw(), threshold, max_gap)
    assert [d["time"] for d in frames if d["reason"] == "diff"] == [float(t) for t in range(62, 83, 2)]
    assert content_count(saw(), threshold, max_gap) == 11


@pytest.mark.spec("CAP-9")
def test_cap_9_second_fit_without_more_content_is_discarded():
    thumbs = static(200) + [flat(40 * (i % 6)) for i in range(60)]
    times, threshold, max_gap = seenby.fit_to_cap(thumbs, 24, T, G)
    assert (threshold, max_gap) == (205.03125, 5.859375)
    assert len(times) == 23
    assert times == seenby.select(thumbs, threshold, max_gap)
    assert content_count(thumbs, threshold, max_gap) == 0


@pytest.mark.spec("CAP-9")
def test_cap_9_open_gate_with_no_content_keeps_the_cap_4_row():
    assert seenby.fit_to_cap(alt(20), 5, T, G) == ([0.0, 3.0, 6.0, 9.0, 9.5], 307.546875, 3.0)
    assert 307.546875 >= 255 / seenby.BLOCK_K


@pytest.mark.spec("CAP-9")
@pytest.mark.parametrize(
    "thumbs, max_frames, block_k, expected",
    [
        (static(240), 24, 5.0, ([0.0] + [float(t) for t in range(6, 115, 6)] + [119.5], 12.0, 5.859375)),
        (alt(20), 8, 5.0, ([0.0, 3.0, 6.0, 9.0, 9.5], 307.546875, 3.0)),
        (alt(20), 2, 5.0, ([0.0, 9.5], 307.546875, 9.1552734375)),
        (blocky(), 5, 5.0, ([0.0, 3.0, 6.0, 9.0, 9.5], 27.0, 3.0)),
        (blocky(), 5, 0, ([0.0, 3.0, 6.0, 9.0, 9.5], 12.0, 3.0)),
        (blocky(), 24, 5.0, ([i / 2 for i in range(20)], 12.0, 3.0)),
        (blocky(), 2, 0.5, ([0.0, 9.5], 205.03125, 9.1552734375)),
    ],
    ids=["static240-cap24", "alt20-cap8", "alt20-cap2", "blocky-cap5", "blocky-cap5-k0", "blocky-cap24", "blocky-cap2-k0.5"],
)
def test_cap_9_earlier_rows_are_unchanged_by_the_second_fit(thumbs, max_frames, block_k, expected):
    assert seenby.fit_to_cap(thumbs, max_frames, T, G, block_k) == expected


@pytest.mark.spec("CAP-8")
@pytest.mark.spec("CAP-9")
@pytest.mark.parametrize("cap", [2, 3, 6, 12, 24])
def test_cap_8_9_second_fit_still_fits_the_cap_and_matches_select(cap):
    for thumbs in (long_ramp(), two(), saw()):
        times, threshold, max_gap = seenby.fit_to_cap(thumbs, cap, T, G)
        assert len(times) <= cap
        assert threshold >= T
        assert max_gap >= G
        assert times == seenby.select(thumbs, threshold, max_gap)
        assert times[0] == 0.0
        assert times[-1] == last_time(thumbs)


# -------- MAN-15


@pytest.mark.spec("MAN-15")
def test_man_15_static_run_analysis_keys_and_segment_activity(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    data = manifest()
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["block_active"] is True
    assert data["analysis"]["timer_share"] == 1.0
    assert data["segments"] == [
        {"n": 1, "from": 0.0, "to": 15.0, "frames": [1, 2, 3, 4, 5, 6], "activity": 0.0}
    ]
    assert list(data["segments"][0]) == SEGMENT_KEYS


@pytest.mark.spec("MAN-15")
def test_man_15_high_threshold_turns_block_active_off_and_reports_activity(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "300", "--max-gap", "7"], alt(30))
    assert run.rc == 0
    data = manifest()
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["block_active"] is False
    assert data["analysis"]["timer_share"] == 1.0
    assert data["segments"][0]["activity"] == 255.0
    assert data["segments"] == [manifest_segment(1, 0.0, 15.0, [1, 2, 3, 4], 255.0)]


@pytest.mark.spec("MAN-15")
def test_man_15_diff_frames_give_timer_share_zero(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], ramp())
    assert run.rc == 0
    data = manifest()
    assert [f["reason"] for f in data["frames"]] == ["first", "diff", "diff", "diff"]
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["timer_share"] == 0.0
    assert data["analysis"]["block_active"] is True


@pytest.mark.spec("MAN-15")
def test_man_15_range_run_has_activity_in_every_segment(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch,
        capsys,
        tmp_path,
        ["clip.mp4", "out", "--from", "10", "--to", "25", "--segment", "5"],
        static(30),
        probe=(60.0, 800, 600),
    )
    assert run.rc == 0
    data = manifest()
    assert len(data["segments"]) == 3
    assert all(list(e) == SEGMENT_KEYS for e in data["segments"])
    assert [e["activity"] for e in data["segments"]] == [0.0, 0.0, 0.0]
    assert data["analysis"]["range"] == {"from": 10.0, "to": 25.0}
    assert data["analysis"]["segment"] == 5.0


@pytest.mark.spec("MAN-15")
@pytest.mark.parametrize(
    "thumbs, reasons, timer_share",
    [
        (static(1), ["first"], 0.0),
        (static(4), ["first", "last"], 0.0),
        (static(7), ["first", "timer"], 1.0),
        (static(6) + [flat(255)] * 13, ["first", "diff", "timer", "timer"], 0.67),
        (static(11) + [patch(100)] + static(18), ["first", "timer", "block", "block", "timer", "timer", "last"], 0.6),
    ],
    ids=["first-only", "first-last", "one-timer", "two-of-three", "three-of-five"],
)
def test_man_15_timer_share_counts_timer_over_loop_reasons(monkeypatch, capsys, tmp_path, thumbs, reasons, timer_share):
    frames = ["out/frame-01.jpg"] if len(reasons) == 1 else None
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], thumbs, frames=frames)
    assert run.rc == 0
    data = manifest()
    assert [f["reason"] for f in data["frames"]] == reasons
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["timer_share"] == timer_share
    assert isinstance(data["analysis"]["timer_share"], float)


@pytest.mark.spec("MAN-15")
@pytest.mark.parametrize(
    "argv, block_active",
    [
        (["clip.mp4", "out"], True),
        (["clip.mp4", "out", "--block-k", "0"], False),
        (["clip.mp4", "out", "--threshold", "50.9"], True),
        (["clip.mp4", "out", "--threshold", "51"], False),
        (["clip.mp4", "out", "--block-k", "2", "--threshold", "127"], True),
        (["clip.mp4", "out", "--block-k", "2", "--threshold", "127.5"], False),
    ],
    ids=["default", "k0", "bar-254.5", "bar-255", "k2-bar-254", "k2-bar-255"],
)
def test_man_15_block_active_is_the_bar_under_255(monkeypatch, capsys, tmp_path, argv, block_active):
    run = run_main(monkeypatch, capsys, tmp_path, argv, static(30))
    assert run.rc == 0
    data = manifest()
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["block_active"] is block_active


@pytest.mark.spec("MAN-15")
def test_man_15_block_active_uses_the_effective_threshold(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], alt(30))
    assert run.rc == 0
    data = manifest()
    assert data["analysis"]["threshold"] == {"requested": 12.0, "effective": 307.546875}
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["block_active"] is False
    assert data["analysis"]["timer_share"] == 1.0


@pytest.mark.spec("MAN-15")
def test_man_15_segment_activity_is_computed_over_the_analysed_thumbnails(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--segment", "5"], mixed() * 8, probe=(16.0, 800, 600))
    assert run.rc == 0
    data = manifest()
    assert [(e["from"], e["to"]) for e in data["segments"]] == [(0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, 16.0)]
    assert all(list(e) == SEGMENT_KEYS for e in data["segments"])
    assert [e["activity"] for e in data["segments"]] == seenby.activity(mixed() * 8, 0.0, 16.0, 5.0)
    assert data["segments"][3]["activity"] == 6.25


# -------- CLI-23 (the timer line triggers on an active cap and five frames alone)


LONG_RAMP_FRAMES_LINE = (
    "  frames: 0.0 first, "
    + ", ".join("%.1f timer" % t for t in range(3, 52, 3))
    + ", 53.5 diff, 56.0 diff, 58.5 diff, 61.0 diff, 62.0 last"
)
LONG_RAMP_TIMER_LINE = BIGGER_CAP_LINE.format(timer=17, loop=21, c2=48, n2=12, t2="12.0", s2=4, c3=72, n3=12, t3="12.0", s3=4)
LONG_RAMP_DRY_RUN_STDOUT = (
    "clip.mp4: 65.0 s, 800x600, landscape\n"
    "  125 thumbnails, selected 23/24 (threshold 12.0 -> 40.5, max gap 3.0 -> 3.0 s)\n"
    + LONG_RAMP_FRAMES_LINE + "\n"
    "  layout: window, tile 516 px, 3x3 per sheet\n"
    + LONG_RAMP_TIMER_LINE + "\n"
)
ALT_30_TIMER_LINE = BIGGER_CAP_LINE.format(timer=4, loop=4, c2=48, n2=29, t2="12.0", s2=4, c3=72, n3=29, t3="12.0", s3=4)


@pytest.mark.spec("CLI-23")
def test_cli_23_static_run_prints_the_cli_21_lines_unchanged(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30))
    assert run.rc == 0
    assert run.out == STATIC_30_STDOUT
    assert "block rule" not in run.out
    assert "frames by the timer;" not in run.out


@pytest.mark.spec("CLI-23")
def test_cli_23_block_line_after_the_layout_line_when_the_bar_is_above_255(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "300", "--max-gap", "7"], alt(30))
    assert run.rc == 0
    assert run.out == (
        "clip.mp4: 15.0 s, 800x600, landscape\n"
        "  30 thumbnails, selected 4/24 (threshold 300.0 -> 300.0, max gap 7.0 -> 7.0 s)\n"
        "  frames: 0.0 first, 7.0 timer, 14.0 timer, 14.5 last\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
        "  block rule inactive: bar 1500.0 (5.0 x 300.0) is at or above 255\n"
        "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )


@pytest.mark.spec("CLI-23")
def test_cli_23_block_line_prints_under_dry_run(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "300", "--max-gap", "7", "--dry-run"], alt(30)
    )
    assert run.rc == 0
    assert run.out == (
        "clip.mp4: 15.0 s, 800x600, landscape\n"
        "  30 thumbnails, selected 4/24 (threshold 300.0 -> 300.0, max gap 7.0 -> 7.0 s)\n"
        "  frames: 0.0 first, 7.0 timer, 14.0 timer, 14.5 last\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
        "  block rule inactive: bar 1500.0 (5.0 x 300.0) is at or above 255\n"
    )
    assert run.save_frames_calls == []
    assert not (tmp_path / "out").exists()


@pytest.mark.spec("CLI-23")
def test_cli_23_block_line_at_the_boundary_bar_of_255(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "51"], static(30))
    assert run.rc == 0
    assert run.out.splitlines()[4] == BLOCK_LINE.format(bar="255.0", block_k="5.0", threshold="51.0")
    below = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out2", "--threshold", "50.9"], static(30))
    assert below.rc == 0
    assert "block rule" not in below.out


@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-15")
def test_cli_23_man_15_long_ramp_names_what_a_bigger_cap_buys(monkeypatch, capsys, tmp_path):
    sheets = [f"out/sheet-{i:02d}.jpg" for i in range(1, 4)]
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], long_ramp(), probe=(65.0, 800, 600), sheets=sheets)
    assert run.rc == 0
    assert run.err == ""
    assert run.out == (
        LONG_RAMP_DRY_RUN_STDOUT
        + "  contact sheets: " + ", ".join(sheets) + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    assert run.out.splitlines()[4] == LONG_RAMP_TIMER_LINE
    assert len(run.save_frames_calls[0][1]) == 23
    data = manifest()
    reasons = [f["reason"] for f in data["frames"]]
    assert reasons.count("timer") == 17
    assert reasons.count("diff") == 4
    assert data["analysis"]["threshold"] == {"requested": 12.0, "effective": 40.5}
    assert data["analysis"]["timer_share"] == 0.81
    assert data["analysis"]["block_active"] is True
    assert data["analysis"]["all_timer"] is False
    assert data["analysis"]["quiet"] == []
    assert data["sheets"] == [
        {"file": "sheet-01.jpg", "frames": [1, 9]},
        {"file": "sheet-02.jpg", "frames": [10, 18]},
        {"file": "sheet-03.jpg", "frames": [19, 23]},
    ]
    assert data["segments"] == [manifest_segment(1, 0.0, 65.0, list(range(1, 24)), 2.02)]


@pytest.mark.spec("CLI-23")
@pytest.mark.spec("CLI-19")
def test_cli_23_19_timer_line_prints_under_dry_run_after_the_layout_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], long_ramp(), probe=(65.0, 800, 600))
    assert run.rc == 0
    assert run.out == LONG_RAMP_DRY_RUN_STDOUT
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []
    assert run.ffmpeg_version_calls == 0
    assert not (tmp_path / "out").exists()
    assert os.listdir(tmp_path) == ["clip.mp4"]


@pytest.mark.spec("CLI-23")
@pytest.mark.spec("CLI-24")
def test_cli_23_24_static_long_recording_says_no_cap_adds_content(monkeypatch, capsys, tmp_path):
    sheets = [f"out/sheet-{i:02d}.jpg" for i in range(1, 4)]
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(240), probe=(125.0, 800, 600), sheets=sheets)
    assert run.rc == 0
    assert run.out == (
        "clip.mp4: 125.0 s, 800x600, landscape\n"
        "  240 thumbnails, selected 21/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 5.9 s)\n"
        "  frames: 0.0 first, " + ", ".join("%.1f timer" % t for t in range(6, 115, 6)) + ", 119.5 last\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
        + NO_CAP_HELPS_LINE.format(timer=19, loop=19, c3=72) + "\n"
        + "  contact sheets: " + ", ".join(sheets) + "\n"
        + ALL_TIMER_LINE.format(threshold="12.0") + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    data = manifest()
    assert data["analysis"]["max_gap"] == {"requested": 3.0, "effective": 5.859375}
    assert data["analysis"]["timer_share"] == 1.0
    assert data["analysis"]["all_timer"] is True
    assert data["analysis"]["quiet"] == []


@pytest.mark.spec("CLI-23")
def test_cli_23_timer_line_prints_with_a_share_under_0_7(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch,
        capsys,
        tmp_path,
        ["clip.mp4", "out", "--max-frames", "8"],
        long_ramp(),
        probe=(65.0, 800, 600),
        sheets=["out/sheet-01.jpg"],
    )
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.err == ""
    assert lines[1] == "  125 thumbnails, selected 8/8 (threshold 12.0 -> 40.5, max gap 3.0 -> 17.9 s)"
    assert lines[3] == "  layout: window, tile 516 px, 3x3 per sheet"
    assert lines[4] == NO_CAP_HELPS_LINE.format(timer=2, loop=7, c3=24)
    assert lines[4] == "  2 of 7 frames by the timer; no cap up to 24 adds a content frame"
    assert lines[5] == "  contact sheets: out/sheet-01.jpg"
    assert lines[6] == MANIFEST_LINE.format(out_dir="out")
    assert len(lines) == 7
    assert "block rule" not in run.out
    assert "all frames taken by the timer" not in run.out
    assert len(run.save_frames_calls[0][1]) == 8
    data = manifest()
    reasons = [f["reason"] for f in data["frames"]]
    assert len(reasons) == 8
    assert reasons.count("timer") == 2
    assert reasons.count("diff") + reasons.count("block") == 5
    assert data["analysis"]["timer_share"] == 0.29
    assert data["analysis"]["threshold"] == {"requested": 12.0, "effective": 40.5}
    assert data["analysis"]["max_gap"] == {"requested": 3.0, "effective": 17.881393432617188}
    assert data["analysis"]["block_active"] is True
    assert data["analysis"]["all_timer"] is False


@pytest.mark.spec("CLI-23")
@pytest.mark.spec("MAN-15")
@pytest.mark.spec("CLI-24")
def test_cli_23_man_15_24_alternating_input_prints_both_lines(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], alt(30))
    assert run.rc == 0
    assert run.out == (
        "clip.mp4: 15.0 s, 800x600, landscape\n"
        "  30 thumbnails, selected 6/24 (threshold 12.0 -> 307.5, max gap 3.0 -> 3.0 s)\n"
        "  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
        "  block rule inactive: bar 1537.7 (5.0 x 307.5) is at or above 255\n"
        + ALT_30_TIMER_LINE + "\n"
        + "  contact sheets: out/sheet-01.jpg\n"
        + ALL_TIMER_LINE.format(threshold="307.5") + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    data = manifest()
    assert data["analysis"]["timer_share"] == 1.0
    assert data["analysis"]["block_active"] is False
    assert data["analysis"]["quiet"] == []


@pytest.mark.spec("CLI-23")
def test_cli_23_block_k_zero_drops_the_block_line_only(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--block-k", "0"], alt(30))
    assert run.rc == 0
    assert run.out == (
        "clip.mp4: 15.0 s, 800x600, landscape\n"
        "  30 thumbnails, selected 6/24 (threshold 12.0 -> 307.5, max gap 3.0 -> 3.0 s)\n"
        "  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 timer, 14.5 last\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
        + ALT_30_TIMER_LINE + "\n"
        + "  contact sheets: out/sheet-01.jpg\n"
        + ALL_TIMER_LINE.format(threshold="307.5") + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    assert manifest()["analysis"]["block_active"] is False


@pytest.mark.spec("CLI-23")
def test_cli_23_no_timer_line_under_five_frames(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--max-frames", "2"], alt(20))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  20 thumbnails, selected 2/2 (threshold 12.0 -> 307.5, max gap 3.0 -> 9.2 s)"
    assert lines[4] == BLOCK_LINE.format(bar="1537.7", block_k="5.0", threshold="307.5")
    assert lines[5] == "  contact sheets: out/sheet-01.jpg"
    assert len(lines) == 7
    assert "frames by the timer;" not in run.out


@pytest.mark.spec("CLI-23")
def test_cli_23_no_timer_line_when_the_cap_was_not_active(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(61), sheets=["out/sheet-01.jpg", "out/sheet-02.jpg"])
    assert run.rc == 0
    assert "frames by the timer;" not in run.out
    assert len(run.out.splitlines()) == 7
    data = manifest()
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["timer_share"] == 1.0


# ---------------------------------------------------------------- Step 10: the all-timer line names --threshold (draft)


@pytest.mark.spec("CLI-24")
@pytest.mark.spec("CLI-25")
@pytest.mark.spec("MAN-16")
def test_cli_24_25_quiet_stretch_replaces_the_all_timer_line_for_steps(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], steps(4, 8))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 7
    assert lines[1] == "  30 thumbnails, selected 7/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 5.0 diff, 8.0 timer, 10.0 diff, 13.0 timer, 14.5 last"
    assert lines[3] == quiet_line([{"from": 0.0, "to": 14.5, "threshold": 1.3, "largest": 4.0}])
    assert "all frames taken by the timer" not in run.out
    data = manifest()
    assert list(data["analysis"]) == ANALYSIS_KEYS
    assert data["analysis"]["all_timer"] is False
    assert data["analysis"]["timer_share"] == 0.6
    assert data["analysis"]["quiet"] == [{"from": 0.0, "to": 14.5, "largest": 4.0, "threshold": 1.3}]
    assert [f["reason"] for f in data["frames"]] == ["first", "timer", "diff", "timer", "diff", "timer", "last"]


@pytest.mark.spec("CLI-24")
@pytest.mark.spec("CLI-25")
def test_cli_24_25_quiet_stretch_from_a_slow_creep(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], [flat(i // 2) for i in range(30)])
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  30 thumbnails, selected 9/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == (
        "  frames: 0.0 first, 2.0 diff, 4.0 diff, 6.0 diff, 8.0 diff, 10.0 diff, 12.0 diff, 14.0 diff, 14.5 last"
    )
    assert lines[3] == quiet_line([{"from": 0.0, "to": 14.5, "threshold": 1.0, "largest": 3.0}])
    assert "all frames taken by the timer" not in run.out
    data = manifest()
    assert data["analysis"]["quiet"] == [{"from": 0.0, "to": 14.5, "largest": 3.0, "threshold": 1.0}]


@pytest.mark.spec("CLI-24")
@pytest.mark.spec("CLI-25")
def test_cli_24_25_quiet_stretch_ignores_the_requested_threshold(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "30"], steps(4, 8))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  30 thumbnails, selected 7/24 (threshold 30.0 -> 30.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 5.0 diff, 8.0 timer, 10.0 diff, 13.0 timer, 14.5 last"
    assert lines[3] == quiet_line([{"from": 0.0, "to": 14.5, "threshold": 1.3, "largest": 4.0}])


@pytest.mark.spec("CLI-24")
@pytest.mark.spec("CLI-25")
def test_cli_24_25_quiet_stretch_replaces_the_all_timer_line_for_a_small_step(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], [flat(0)] * 10 + [flat(2)] * 20)
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 5.0 diff, 8.0 timer, 11.0 timer, 14.0 timer, 14.5 last"
    assert lines[3] == quiet_line([{"from": 0.0, "to": 14.5, "threshold": 1.0, "largest": 2.0}])
    data = manifest()
    assert data["analysis"]["timer_share"] == 0.8
    assert data["analysis"]["quiet"] == [{"from": 0.0, "to": 14.5, "largest": 2.0, "threshold": 1.0}]


@pytest.mark.spec("CLI-24")
@pytest.mark.spec("CLI-25")
def test_cli_24_second_form_when_m_is_not_above_1_0(monkeypatch, capsys, tmp_path):
    """largest is 1.0 here, not above 1.0, so quiet_stretches finds no candidate (SEL-7)."""
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], [flat(0)] * 10 + [flat(1)] * 20)
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[5] == ALL_TIMER_M_LINE.format(m="1.0", threshold="12.0")
    assert "--threshold" not in lines[5]
    assert "quiet stretches" not in run.out
    assert manifest()["analysis"]["quiet"] == []


@pytest.mark.spec("CLI-24")
@pytest.mark.spec("CLI-25")
def test_cli_24_block_k_zero_long_recording_suggested_threshold_the_cap_then_rejects(monkeypatch, capsys, tmp_path):
    """The one candidate (60 frames at threshold 2.0) does not fit the cap and is dropped: CLI-24 fires as before."""
    sheets = ["out/sheet-01.jpg", "out/sheet-02.jpg"]
    run = run_main(
        monkeypatch,
        capsys,
        tmp_path,
        ["clip.mp4", "out", "--block-k", "0"],
        [flat(0), patch(100)] * 30,
        probe=(30.0, 800, 600),
        sheets=sheets,
    )
    assert run.rc == 0
    assert run.out == (
        "clip.mp4: 30.0 s, 800x600, landscape\n"
        "  60 thumbnails, selected 11/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)\n"
        "  frames: 0.0 first, " + ", ".join("%.1f timer" % t for t in range(3, 28, 3)) + ", 29.5 last\n"
        "  layout: window, tile 516 px, 3x3 per sheet\n"
        "  contact sheets: " + ", ".join(sheets) + "\n"
        + ALL_TIMER_M_SUGGEST_LINE.format(m="6.2", threshold="12.0", t="2.0", content=0, t2="6.8", sheets=2) + "\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    assert "quiet stretches" not in run.out
    assert manifest()["analysis"]["quiet"] == []


@pytest.mark.spec("CLI-24")
@pytest.mark.spec("CLI-25")
def test_cli_24_25_no_line_under_dry_run(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], steps(4, 8))
    assert run.rc == 0
    assert "all frames taken by the timer" not in run.out
    assert run.out.splitlines() == [
        "clip.mp4: 15.0 s, 800x600, landscape",
        "  30 thumbnails, selected 7/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)",
        "  frames: 0.0 first, 3.0 timer, 5.0 diff, 8.0 timer, 10.0 diff, 13.0 timer, 14.5 last",
        quiet_line([{"from": 0.0, "to": 14.5, "threshold": 1.3, "largest": 4.0}]),
        "  layout: window, tile 516 px, 3x3 per sheet",
    ]
    assert not (tmp_path / "out").exists()


# ---------------------------------------------------------------- Step 11: quiet stretches get their own threshold (draft)


def split():
    return [flat(0), flat(2)] * 12 + [flat(100)] * 10 + [flat(104)] * 10 + [flat(108)] * 10


def popup():
    return [flat(2 if i % 2 else 0) for i in range(20)] + [flat(13)] + [flat(0)] * 9


def short():
    return [flat(0)] * 7 + [flat(5)] * 5 + [flat(0)] * 2


def patch_on(base, v):
    pixels = bytearray([base]) * SIZE
    for r in range(8):
        for c in range(8):
            pixels[r * seenby.THUMB + c] = v
    return bytes(pixels)


def quiet_line(entries):
    return "  quiet stretches at a lower threshold: " + "; ".join(
        "%.1f-%.1f s at %.1f (largest change %.1f)" % (e["from"], e["to"], e["threshold"], e["largest"])
        for e in entries
    )


@pytest.mark.spec("REC-10")
def test_rec_10_quiet_entry_lowers_the_threshold_inside_its_range():
    frames = seenby.select_frames(steps(4, 8), 12.0, 3.0, quiet=[{"from": 0.0, "to": 14.5, "threshold": 1.3}])
    assert [(d["time"], d["reason"]) for d in frames] == [
        (0.0, "first"),
        (3.0, "timer"),
        (5.0, "diff"),
        (8.0, "timer"),
        (10.0, "diff"),
        (13.0, "timer"),
        (14.5, "last"),
    ]


@pytest.mark.spec("REC-10")
def test_rec_10_from_is_excluded_but_the_closing_to_uses_the_stretch_threshold():
    frames = seenby.select_frames(steps(4, 8), 12.0, 3.0, quiet=[{"from": 5.0, "to": 10.0, "threshold": 1.3}])
    assert [(d["time"], d["reason"]) for d in frames] == [
        (0.0, "first"),
        (3.0, "timer"),
        (5.5, "diff"),
        (8.5, "timer"),
        (10.0, "diff"),
        (13.0, "timer"),
        (14.5, "last"),
    ]


@pytest.mark.spec("REC-10")
def test_rec_10_popup_at_the_closing_end_of_a_stretch_survives_at_its_threshold():
    today = seenby.select_frames(popup(), 12.0, 3.0)
    assert [(d["time"], d["reason"]) for d in today] == [
        (0.0, "first"),
        (3.0, "timer"),
        (6.0, "timer"),
        (9.0, "timer"),
        (10.0, "diff"),
        (10.5, "diff"),
        (13.5, "timer"),
        (14.5, "last"),
    ]
    with_quiet = seenby.select_frames(popup(), 12.0, 3.0, quiet=[{"from": 0.0, "to": 10.0, "threshold": 1.0}])
    assert [(d["time"], d["reason"]) for d in with_quiet] == (
        [(0.0, "first")] + [(i / 2, "diff") for i in range(1, 22)] + [(13.5, "timer"), (14.5, "last")]
    )
    assert len(with_quiet) == 24


@pytest.mark.spec("REC-10")
def test_rec_10_empty_quiet_matches_todays_result():
    today = seenby.select_frames(steps(4, 8), 12.0, 3.0)
    assert [(d["time"], d["reason"]) for d in today] == [
        (0.0, "first"),
        (3.0, "timer"),
        (6.0, "timer"),
        (9.0, "timer"),
        (12.0, "timer"),
        (14.5, "last"),
    ]
    assert seenby.select_frames(steps(4, 8), 12.0, 3.0, quiet=[]) == today


@pytest.mark.spec("SEL-7")
def test_sel_7_quiet_stretches_from_the_steps_recording():
    assert seenby.quiet_stretches(steps(4, 8), T, G, 24) == [
        {"from": 0.0, "to": 14.5, "timer": 4, "largest": 4.0, "threshold": 1.3}
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_candidate_ignores_the_requested_threshold():
    assert seenby.quiet_stretches(steps(4, 8), 30.0, G, 24) == [
        {"from": 0.0, "to": 14.5, "timer": 4, "largest": 4.0, "threshold": 1.3}
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_slow_creep_gives_the_cli_24_threshold():
    assert seenby.quiet_stretches([flat(i // 2) for i in range(30)], T, G, 24) == [
        {"from": 0.0, "to": 14.5, "timer": 4, "largest": 3.0, "threshold": 1.0}
    ]


@pytest.mark.spec("SEL-7")
@pytest.mark.parametrize("thumbs", [static(30), [flat(0)] * 10 + [flat(1)] * 20])
def test_sel_7_no_candidate_when_the_largest_change_is_at_or_below_1(thumbs):
    assert seenby.quiet_stretches(thumbs, T, G, 24) == []


@pytest.mark.spec("SEL-7")
def test_sel_7_short_selection_with_no_content_frame_before_last_gets_a_stretch():
    thumbs = [flat(0)] * 5 + [flat(2)] * 11 + [flat(100)]
    assert seenby.quiet_stretches(thumbs, T, G, 24) == [
        {"from": 0.0, "to": 8.0, "timer": 2, "largest": 2.0, "threshold": 1.0}
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_run_after_a_content_frame_still_needs_three_timer_frames():
    thumbs = [flat(0)] + [flat(20)] * 8 + [flat(23)] * 6
    assert seenby.quiet_stretches(thumbs, T, G, 24) == []


@pytest.mark.spec("SEL-7")
def test_sel_7_short_recording_needs_only_the_two_ends():
    assert seenby.quiet_stretches(short(), T, G, 24) == [
        {"from": 0.0, "to": 6.5, "timer": 2, "largest": 5.0, "threshold": 1.6}
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_short_selection_with_zero_timer_frames_still_gets_a_stretch():
    thumbs = [flat(0)] * 3 + [flat(3)] * 2
    assert seenby.quiet_stretches(thumbs, T, G, 24) == [
        {"from": 0.0, "to": 2.0, "timer": 0, "largest": 3.0, "threshold": 1.0}
    ]


@pytest.mark.spec("SEL-7")
@pytest.mark.parametrize("thumbs", [static(14), [flat(0), straddle(100)], [flat(0)]])
def test_sel_7_no_candidate_pair_gives_empty_list(thumbs):
    assert seenby.quiet_stretches(thumbs, T, G, 24) == []


@pytest.mark.spec("SEL-7")
def test_sel_7_block_k_zero_finds_the_blocky_stretch():
    assert seenby.quiet_stretches(blocky(), T, G, 24, 0.0) == [
        {"from": 0.0, "to": 9.5, "timer": 3, "largest": 6.25, "threshold": 2.0}
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_candidate_dropped_when_it_does_not_fit_the_cap():
    assert seenby.quiet_stretches([flat(0), patch(100)] * 30, T, G, 24, 0.0) == []


@pytest.mark.spec("SEL-7")
def test_sel_7_split_recording_keeps_the_stretch_with_fewer_timer_frames():
    assert seenby.quiet_stretches(split(), T, G, 24) == [
        {"from": 12.0, "to": 26.5, "timer": 4, "largest": 4.0, "threshold": 1.3}
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_split_recording_keeps_both_stretches_under_a_bigger_cap():
    assert seenby.quiet_stretches(split(), T, G, 60) == [
        {"from": 0.0, "to": 12.0, "timer": 3, "largest": 2.0, "threshold": 1.0},
        {"from": 12.0, "to": 26.5, "timer": 4, "largest": 4.0, "threshold": 1.3},
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_empty_thumbs_gives_empty_list():
    assert seenby.quiet_stretches([], T, G, 24) == []


@pytest.mark.spec("SEL-7")
def test_sel_7_popup_at_the_closing_end_counts_as_the_largest_change():
    assert seenby.quiet_stretches(popup(), T, G, 24) == [
        {"from": 0.0, "to": 10.0, "timer": 3, "largest": 2.0, "threshold": 1.0}
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_selection_ending_on_a_timer_frame_is_still_an_end():
    thumbs = [flat(0)] * 7 + [flat(4)] * 12
    assert seenby.quiet_stretches(thumbs, T, G, 24) == [
        {"from": 0.0, "to": 9.0, "timer": 2, "largest": 4.0, "threshold": 1.3}
    ]
    frames = seenby.select_frames(thumbs, T, G, quiet=[{"from": 0.0, "to": 9.0, "threshold": 1.3}])
    assert [(d["time"], d["reason"]) for d in frames] == [
        (0.0, "first"),
        (3.0, "timer"),
        (3.5, "diff"),
        (6.5, "timer"),
        (9.0, "last"),
    ]


@pytest.mark.spec("SEL-7")
def test_sel_7_cap_drops_the_whole_range_candidate():
    thumbs = [flat(3 * (i % 2)) for i in range(14)]
    assert seenby.quiet_stretches(thumbs, T, G, 4) == []
    assert seenby.quiet_stretches(thumbs, T, G, 24) == [
        {"from": 0.0, "to": 6.5, "timer": 2, "largest": 3.0, "threshold": 1.0}
    ]


@pytest.mark.spec("CLI-25")
@pytest.mark.spec("MAN-16")
def test_cli_25_man_16_quiet_times_are_shifted_by_the_range_start(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--from", "5"], steps(4, 8), probe=(20.0, 800, 600)
    )
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  range: 5.0-20.0 s"
    assert lines[2] == "  30 thumbnails, selected 7/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[3] == "  frames: 5.0 first, 8.0 timer, 10.0 diff, 13.0 timer, 15.0 diff, 18.0 timer, 19.5 last"
    assert lines[4] == quiet_line([{"from": 5.0, "to": 19.5, "threshold": 1.3, "largest": 4.0}])
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 5.0, 15.0)]
    data = manifest()
    assert data["analysis"]["quiet"] == [{"from": 5.0, "to": 19.5, "largest": 4.0, "threshold": 1.3}]


@pytest.mark.spec("CLI-25")
def test_cli_25_split_recording_keeps_only_the_busy_half_quiet(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], split(), probe=(27.0, 800, 600))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  54 thumbnails, selected 11/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == (
        "  frames: 0.0 first, 3.0 timer, 6.0 timer, 9.0 timer, 12.0 diff, 15.0 timer, "
        "17.0 diff, 20.0 timer, 22.0 diff, 25.0 timer, 26.5 last"
    )
    assert lines[3] == quiet_line([{"from": 12.0, "to": 26.5, "threshold": 1.3, "largest": 4.0}])
    data = manifest()
    assert data["analysis"]["quiet"] == [{"from": 12.0, "to": 26.5, "largest": 4.0, "threshold": 1.3}]


@pytest.mark.spec("CLI-25")
def test_cli_25_short_recording_gets_a_quiet_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], short(), probe=(7.0, 800, 600))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  14 thumbnails, selected 5/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 3.5 diff, 6.0 diff, 6.5 last"
    assert lines[3] == quiet_line([{"from": 0.0, "to": 6.5, "threshold": 1.6, "largest": 5.0}])
    assert lines[4].startswith("  layout: window")
    assert "all frames taken by the timer" not in run.out
    data = manifest()
    assert data["analysis"]["quiet"] == [{"from": 0.0, "to": 6.5, "largest": 5.0, "threshold": 1.6}]
    assert data["analysis"]["all_timer"] is False
    assert data["analysis"]["timer_share"] == 0.33
    frames = data["frames"]
    assert frames[2]["diff"] == 5.0
    assert frames[3]["diff"] == 5.0


@pytest.mark.spec("CLI-25")
def test_cli_25_short_recording_dry_run_prints_the_same_lines(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], short(), probe=(7.0, 800, 600))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert len(lines) == 5
    assert lines[0] == "clip.mp4: 7.0 s, 800x600, landscape"
    assert lines[1] == "  14 thumbnails, selected 5/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 3.5 diff, 6.0 diff, 6.5 last"
    assert lines[3] == quiet_line([{"from": 0.0, "to": 6.5, "threshold": 1.6, "largest": 5.0}])
    assert lines[4].startswith("  layout: window")
    assert not (tmp_path / "out").exists()


@pytest.mark.spec("CLI-25")
@pytest.mark.spec("MAN-11")
def test_cli_25_man_11_static_14_at_7s_has_no_quiet_line(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(14), probe=(7.0, 800, 600))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[2] == "  frames: 0.0 first, 3.0 timer, 6.0 timer, 6.5 last"
    assert "quiet stretches at a lower threshold" not in run.out
    assert "all frames taken by the timer" not in run.out
    data = manifest()
    assert data["analysis"]["quiet"] == []
    assert data["analysis"]["all_timer"] is False


@pytest.mark.spec("CLI-25")
def test_cli_25_popup_at_the_closing_end_is_kept_by_the_stretch(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], popup())
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  30 thumbnails, selected 24/24 (threshold 12.0 -> 12.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == (
        "  frames: 0.0 first, " + ", ".join("%.1f diff" % (i / 2) for i in range(1, 22)) + ", 13.5 timer, 14.5 last"
    )
    assert lines[3] == quiet_line([{"from": 0.0, "to": 10.0, "threshold": 1.0, "largest": 2.0}])
    data = manifest()
    assert data["analysis"]["quiet"] == [{"from": 0.0, "to": 10.0, "largest": 2.0, "threshold": 1.0}]


@pytest.mark.spec("MAN-16")
@pytest.mark.spec("CLI-25")
def test_man_16_cli_25_block_active_uses_the_lowest_of_the_quiet_thresholds(monkeypatch, capsys, tmp_path):
    thumbs = [flat(0)] * 3 + [flat(30)] * 3 + [patch_on(30, 100)] * 3 + [flat(30)] * 21
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--threshold", "60"], thumbs)
    lines = run.out.splitlines()
    assert run.rc == 0
    assert lines[1] == "  30 thumbnails, selected 8/24 (threshold 60.0 -> 60.0, max gap 3.0 -> 3.0 s)"
    assert lines[2] == "  frames: 0.0 first, 1.5 diff, 3.0 block, 4.5 block, 7.5 timer, 10.5 timer, 13.5 timer, 14.5 last"
    assert lines[3] == quiet_line([{"from": 0.0, "to": 14.5, "threshold": 11.4, "largest": 34.375}])
    assert "block rule inactive" not in run.out
    data = manifest()
    assert data["analysis"]["block_active"] is True
    assert data["analysis"]["quiet"] == [{"from": 0.0, "to": 14.5, "largest": 34.375, "threshold": 11.4}]
    frames = data["frames"]
    assert [f["time"] for f in frames] == [0.0, 1.5, 3.0, 4.5, 7.5, 10.5, 13.5, 14.5]
    assert [f["reason"] for f in frames] == ["first", "diff", "block", "block", "timer", "timer", "timer", "last"]
    assert frames[2]["diff"] == 4.375
    assert frames[2]["block"] == 70.0


# ---------------------------------------------------------------- Step 12: the events selector

GW, GH = 20, 10


def grid(cells):
    """Change plane of 20 x 10 cells, cell (x, y) at index y * 20 + x, every other byte 0."""
    plane = bytearray(GW * GH)
    for (x, y), v in cells.items():
        plane[y * GW + x] = v
    return bytes(plane)


def box(x0, y0, w, h, v=255):
    return {(x, y): v for x in range(x0, x0 + w) for y in range(y0, y0 + h)}


def S(cells):
    return (bytes(GW * GH), grid(cells))


def M(mean_cells, change_cells):
    return (grid(mean_cells), grid(change_cells))


def blob(x, y, w=24, h=32, px=300.0, g=False):
    return {"px": px, "x": x, "y": y, "w": w, "h": h, "global": g}


def approx_px(expected):
    """`expected` with `px` compared approximately: the spec leaves the order of `* cell * cell / 255` open."""
    return dict(expected, px=pytest.approx(expected["px"]))


def event_fields(event, expected):
    """The keys of `expected` taken from `event`, for comparison with `expected` (events carry more keys)."""
    return {key: event[key] for key in expected}


@pytest.mark.parametrize(
    "name, value",
    [
        pytest.param("EVENT_FPS", 4, marks=pytest.mark.spec("CLI-26")),
        pytest.param("CELL", 8, marks=pytest.mark.spec("BLB-2")),
        pytest.param("PIXEL_T", 24, marks=pytest.mark.spec("MAN-17")),
        pytest.param("MIN_CELL", 8, marks=pytest.mark.spec("BLB-1")),
        pytest.param("NOISE_PX", 12, marks=pytest.mark.spec("BLB-2")),
        pytest.param("GLOBAL_SHARE", 0.25, marks=pytest.mark.spec("BLB-3")),
        pytest.param("POINTER_BOX", 64, marks=pytest.mark.spec("PTR-1")),
        pytest.param("POINTER_DIM", 8, marks=pytest.mark.spec("PTR-1")),
        pytest.param("POINTER_PX", 0.45, marks=pytest.mark.spec("PTR-1")),
        pytest.param("REGION_MARGIN", 16, marks=pytest.mark.spec("EVT-1")),
        pytest.param("LONG_S", 2.0, marks=pytest.mark.spec("PCK-4")),
        pytest.param("INNER_WEIGHT", 0.8, marks=pytest.mark.spec("PCK-4")),
        pytest.param("GLOBAL_WEIGHT", 4.0, marks=pytest.mark.spec("EVT-2")),
        pytest.param("EPISODE_S", 5.0, marks=pytest.mark.spec("PCK-2")),
        pytest.param("SPREAD", 0.5, marks=pytest.mark.spec("PCK-2")),
        pytest.param("FILL_MIN_S", 0.5, marks=pytest.mark.spec("PCK-3")),
    ],
)
def test_blb_ptr_evt_pck_cli_26_man_17_step_12_constants_have_the_spec_values(name, value):
    assert getattr(seenby, name) == value


@pytest.mark.spec("EVT-3")
@pytest.mark.parametrize("name, value", [("HOLD_DELTA", 6), ("HOLD_SHARE", 0.25)])
def test_evt_3_constants_have_the_spec_values(name, value):
    assert getattr(seenby, name) == value


@pytest.mark.spec("EVT-4")
def test_evt_4_blink_repeats_is_four():
    assert seenby.BLINK_REPEATS == 4


@pytest.mark.spec("EVT-4")
def test_evt_4_caret_h_is_64():
    assert seenby.CARET_H == 64


# -------- BLB-1..3 (blobs)


@pytest.mark.spec("BLB-1")
@pytest.mark.spec("BLB-2")
def test_blb_1_2_one_box_is_one_blob_in_native_pixels():
    assert seenby.blobs(grid(box(2, 2, 3, 4)), GW, GH) == [
        approx_px({"px": 768.0, "x": 16, "y": 16, "w": 24, "h": 32, "global": False})
    ]


@pytest.mark.spec("BLB-1")
def test_blb_1_a_gap_of_one_cell_joins():
    assert seenby.blobs(grid(box(2, 2, 1, 1) | box(4, 2, 1, 1)), GW, GH) == [
        approx_px({"px": 128.0, "x": 16, "y": 16, "w": 24, "h": 8, "global": False})
    ]


@pytest.mark.spec("BLB-1")
def test_blb_1_a_gap_of_two_cells_does_not_join():
    assert seenby.blobs(grid(box(2, 2, 1, 1) | box(5, 2, 1, 1)), GW, GH) == [
        approx_px({"px": 64.0, "x": 16, "y": 16, "w": 8, "h": 8, "global": False}),
        approx_px({"px": 64.0, "x": 40, "y": 16, "w": 8, "h": 8, "global": False}),
    ]


@pytest.mark.spec("BLB-1")
@pytest.mark.spec("BLB-2")
@pytest.mark.parametrize(
    "v, expected",
    [
        (7, []),
        (8, []),
        (51, [approx_px({"px": 12.8, "x": 16, "y": 16, "w": 8, "h": 8, "global": False})]),
    ],
)
def test_blb_1_2_active_cell_and_noise_floor(v, expected):
    assert seenby.blobs(grid(box(2, 2, 1, 1, v)), GW, GH) == expected


@pytest.mark.spec("BLB-2")
def test_blb_2_a_quarter_of_the_cells_is_not_global():
    assert seenby.blobs(grid(box(0, 0, 10, 5, 100)), GW, GH) == [
        approx_px({"px": 1254.9019607843138, "x": 0, "y": 0, "w": 80, "h": 40, "global": False})
    ]


@pytest.mark.spec("BLB-3")
def test_blb_3_more_than_a_quarter_of_the_cells_is_one_global_blob():
    assert seenby.blobs(grid(box(0, 0, 10, 5) | box(10, 0, 1, 1)), GW, GH) == [
        approx_px({"px": 3264.0, "x": 0, "y": 0, "w": 160, "h": 80, "global": True})
    ]


@pytest.mark.spec("BLB-1")
def test_blb_1_no_active_cell_gives_no_blob():
    assert seenby.blobs(grid({}), GW, GH) == []


@pytest.mark.spec("BLB-1")
@pytest.mark.spec("BLB-2")
def test_blb_1_2_cell_argument_scales_the_box():
    assert seenby.blobs(grid(box(3, 3, 2, 2)), GW, GH, cell=4) == [
        approx_px({"px": 64.0, "x": 12, "y": 12, "w": 8, "h": 8, "global": False})
    ]


# -------- PTR-1 (pointer)


def pointer_pair():
    return blob(80, 40, px=190.0), blob(120, 48, px=170.0)


@pytest.mark.spec("PTR-1")
def test_ptr_1_two_alike_pointer_sized_blobs_are_the_pointer():
    a, b = pointer_pair()
    assert seenby.pointer([a, b]) is True


@pytest.mark.spec("PTR-1")
@pytest.mark.parametrize(
    "case",
    ["one blob", "three blobs", "px 90 against 190", "widths 24 and 40", "wider than 64", "global"],
)
def test_ptr_1_anything_else_is_not_the_pointer(case):
    a, b = pointer_pair()
    bs = {
        "one blob": [a],
        "three blobs": [a, b, blob(200, 48)],
        "px 90 against 190": [a, b | {"px": 90.0}],
        "widths 24 and 40": [a, b | {"w": 40}],
        "wider than 64": [a | {"w": 72}, b | {"w": 72}],
        "global": [a | {"global": True}, b],
    }[case]
    assert seenby.pointer(bs) is False


# -------- EVT-1..2 (events_of)

EVENT_BOX_24x32 = {"px": 300.0, "w": 24, "h": 32, "global": False}


@pytest.mark.spec("EVT-1")
@pytest.mark.spec("EVT-2")
def test_evt_1_2_a_change_is_settled_until_the_next_change_over_it():
    content = [[], [], [blob(16, 16)], [], [], [blob(100, 16)], [blob(16, 16)], []]
    events = seenby.events_of(content)
    expected = [
        {"start": 2, "end": 2, "settled": 2, "until": 5, "x": 16},
        {"start": 5, "settled": 5, "until": 7, "x": 100},
        {"start": 6, "settled": 6, "until": 7, "x": 16},
    ]
    assert [event_fields(e, want) for e, want in zip(events, expected)] == expected
    assert len(events) == 3
    for e in events:
        assert event_fields(e, EVENT_BOX_24x32) == approx_px(EVENT_BOX_24x32)


@pytest.mark.spec("EVT-1")
def test_evt_1_changes_touching_the_growing_box_join_one_event():
    content = [[], [blob(16, 16)], [blob(40, 16)], [blob(16, 16)], [], []]
    events = seenby.events_of(content)
    expected = {"start": 1, "end": 3, "settled": 3, "until": 5, "px": 900.0, "x": 16, "w": 48, "h": 32}
    assert len(events) == 1
    assert event_fields(events[0], expected) == approx_px(expected)


@pytest.mark.spec("EVT-1")
def test_evt_1_not_joined_an_event_grows_only_within_one_pair():
    content = [[], [blob(16, 16)], [blob(40, 16)], [blob(16, 16)], [], []]
    events = seenby.events_of(content, joined=False)
    expected = [
        {"start": 1, "until": 2, "x": 16},
        {"start": 2, "until": 5, "x": 40},
        {"start": 3, "until": 5, "x": 16},
    ]
    assert len(events) == 3
    assert [event_fields(e, want) for e, want in zip(events, expected)] == expected


@pytest.mark.spec("EVT-1")
def test_evt_1_whole_frame_blob_absorbs_the_open_event():
    content = [[], [blob(16, 16)], [blob(100, 16)], [blob(0, 0, 160, 80, 5000.0, True)], []]
    events = seenby.events_of(content)
    first = {"start": 1, "end": 1, "until": 2, "x": 16}
    second = {
        "start": 2, "end": 3, "settled": 3, "until": 4, "px": 5300.0,
        "x": 0, "y": 0, "w": 160, "h": 80, "global": True,
    }
    assert len(events) == 2
    assert event_fields(events[0], first) == first
    assert event_fields(events[1], second) == approx_px(second)


@pytest.mark.spec("EVT-1")
@pytest.mark.parametrize("x", [56, 57])
def test_evt_1_a_pair_without_change_ends_the_event(x):
    events = seenby.events_of([[], [blob(16, 16)], [], [blob(x, 16)], []])
    assert len(events) == 2
    assert [e["until"] for e in events] == [4, 4]
    assert [e["start"] for e in events] == [1, 3]


@pytest.mark.spec("EVT-2")
def test_evt_2_weight_is_log_of_changed_pixels():
    weight = seenby.events_of([[], [blob(0, 0, px=300.0)]])[0]["weight"]
    assert round(weight, 4) == 5.7071
    assert weight == pytest.approx(math.log(301))


@pytest.mark.spec("EVT-2")
def test_evt_2_global_event_weighs_four_more():
    weight = seenby.events_of([[], [blob(0, 0, 160, 80, 5000.0, True)]])[0]["weight"]
    assert round(weight, 4) == 12.5174
    assert weight == pytest.approx(math.log(5001) + 4)


# -------- PCK-1..3 (pick, fill)


@pytest.mark.spec("PCK-1")
@pytest.mark.parametrize(
    "windows, budget, last, expected",
    [
        ([(2, 4, 1.0), (3, 6, 1.0), (7, 7, 1.0)], 24, 9, [0, 4, 7, 9]),
        ([(2, 4, 1.0), (5, 6, 1.0), (7, 7, 1.0)], 24, 9, [0, 4, 6, 7, 9]),
        ([], 24, 0, [0]),
        ([], 24, 5, [0, 5]),
        ([(0, 3, 1.0)], 24, 5, [0, 3, 5]),
        ([(2, 5, 1.0)], 24, 5, [0, 5]),
    ],
)
def test_pck_1_stabbing_set_within_budget(windows, budget, last, expected):
    assert seenby.pick(windows, budget, last) == expected


@pytest.mark.spec("PCK-2")
@pytest.mark.parametrize(
    "windows, budget, last, expected",
    [
        ([(2, 4, 1.0), (5, 6, 1.0), (7, 7, 1.0), (8, 8, 1.0)], 4, 9, [0, 4, 6, 9]),
        ([(2, 2, 5.0), (3, 3, 1.0), (40, 40, 1.0), (41, 41, 1.0)], 4, 60, [0, 2, 40, 60]),
        ([(2, 2, 5.0), (3, 3, 1.0), (4, 4, 1.0), (5, 5, 1.0)], 4, 60, [0, 2, 5, 60]),
        ([(2, 2, 1.0), (3, 3, 1.0), (4, 4, 1.0), (30, 30, 1.0), (31, 31, 1.0)], 5, 60, [0, 2, 4, 30, 60]),
    ],
)
def test_pck_2_over_budget_bursts_first_then_weighted_spread(windows, budget, last, expected):
    assert seenby.pick(windows, budget, last) == expected


def pick_as_written(windows, budget, last, fps=4):
    """PCK-1 and PCK-2 word for word, every gain recomputed from scratch and summed in the order of `windows`."""
    points = []
    for settled, until, _ in sorted(windows, key=lambda w: (w[1], w[0])):
        if not points or points[-1] < settled:
            points.append(until)
    stabbing = sorted(set(points) | {0, last})
    if len(stabbing) <= budget:
        return stabbing
    chosen = {0, last}

    def covered(window):
        return any(window[0] <= p <= window[1] for p in chosen)

    groups = []
    for window in sorted(windows, key=lambda w: w[0]):
        if groups and window[0] - groups[-1][-1][0] <= round(5.0 * fps):
            groups[-1].append(window)
        else:
            groups.append([window])
    for _, group in sorted(enumerate(groups), key=lambda g: (-max(w[2] for w in g[1]), g[0])):
        if len(chosen) >= budget:
            break
        if any(covered(w) for w in group):
            continue
        chosen.add(min(group, key=lambda w: (-w[2], w[1]))[1])
    while len(chosen) < budget:
        best, best_gain = None, 0.0
        for t in sorted({w[1] for w in windows} - chosen):
            total = sum(w[2] for w in windows if w[0] <= t <= w[1] and not covered(w))
            d = min(abs(t - p) for p in chosen)
            gain = total * (1 + 0.5 * math.log(1 + d / fps))
            if gain > best_gain:
                best, best_gain = t, gain
        if best is None:
            break
        chosen.add(best)
    return sorted(chosen)


@pytest.mark.spec("PCK-2")
@pytest.mark.spec("PCK-1")
def test_pck_2_pick_equals_the_rules_as_written_on_seeded_random_inputs():
    rng = random.Random(20260927)
    mismatches = []
    for _ in range(4000):
        last = rng.randint(5, 120)
        windows = []
        for _ in range(rng.randint(1, 30)):
            a = rng.randint(0, last)
            windows.append((a, min(last, a + rng.choice([0, 1, 2, 3, 5, 10, 40])), rng.uniform(2.5, 14.0)))
        budget = rng.randint(2, 12)
        got, want = seenby.pick(windows, budget, last), pick_as_written(windows, budget, last)
        if got != want:
            mismatches.append((windows, budget, last, got, want))
    assert (len(mismatches), mismatches[:1]) == (0, [])


@pytest.mark.spec("PCK-3")
@pytest.mark.parametrize(
    "points, long_pairs, budget, expected",
    [
        ([0, 20], list(range(4, 17)), 5, [0, 5, 10, 15, 20]),
        ([0, 20], [], 5, [0, 20]),
        ([0, 3], [1, 2], 5, [0, 3]),
        ([0, 20, 40], list(range(21, 40)), 5, [0, 20, 25, 30, 40]),
    ],
)
def test_pck_3_fill_spends_the_budget_inside_long_changes(points, long_pairs, budget, expected):
    assert seenby.fill(points, long_pairs, budget) == expected


# -------- PCK-4 (select_events)
# events_ptr, events_dbl, events_two and events_long are the spec's `ptr`, `dbl`, `two` and `long` of step 12
# (step 9 already has a `two`).


def events_ptr():
    return [
        S({}),
        S(box(2, 2, 3, 4, 170) | box(10, 2, 3, 4, 150)),
        S(box(10, 2, 3, 4, 170) | box(15, 5, 3, 4, 160)),
        S({}),
        S({}),
    ]


def events_dbl():
    return [S({}), S(box(2, 2, 3, 3)), S(box(2, 2, 3, 3)), S({}), S({})]


def events_two():
    return [S({}), S(box(2, 2, 3, 3)), S({}), S(box(12, 2, 3, 3)), S({}), S(box(2, 2, 3, 3)), S({})]


def events_long():
    return [S({})] + [S(box(0, 0, 20, 10, 60))] * 12 + [S({}), S({})]


@pytest.mark.spec("PCK-4")
def test_pck_4_a_toggle_that_stays_is_shown_by_the_last_frame():
    samples = [S({}), S({}), S(box(2, 2, 3, 4)), S({}), S({}), S({}), S({}), S({})]
    result = seenby.select_events(samples, GW, GH, 24)
    expected = {"start": 2, "settled": 2, "until": 7, "px": 768.0}
    assert result["frames"] == [(0, "first"), (7, "last")]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == approx_px(expected)


@pytest.mark.spec("PCK-4")
@pytest.mark.spec("PTR-1")
def test_pck_4_ptr_1_pointer_moves_make_no_event():
    result = seenby.select_events(events_ptr(), GW, GH, 24)
    assert result["frames"] == [(0, "first"), (4, "last")]
    assert result["events"] == []


@pytest.mark.spec("PCK-4")
@pytest.mark.spec("PTR-1")
def test_pck_4_ptr_1_pointer_moves_counts_the_pairs_taken_for_the_pointer():
    assert seenby.select_events(events_ptr(), GW, GH, 24).get("pointer_moves") == 2


@pytest.mark.spec("PCK-4")
@pytest.mark.spec("PTR-1")
def test_pck_4_ptr_1_a_pointer_pair_then_a_real_change():
    samples = [S({}), S(box(2, 2, 3, 4, 170) | box(10, 2, 3, 4, 150)), S({}), S(box(15, 5, 3, 3)), S({}), S({})]
    result = seenby.select_events(samples, GW, GH, 24)
    expected = {"start": 3, "until": 5, "px": 576.0, "x": 120, "y": 40, "w": 24, "h": 24}
    assert result["frames"] == [(0, "first"), (5, "last")]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == approx_px(expected)


@pytest.mark.spec("PCK-4")
@pytest.mark.parametrize(
    "samples, frames",
    [
        ([S({})] * 6, [(0, "first"), (5, "last")]),
        ([S({})], [(0, "first")]),
    ],
)
def test_pck_4_no_change_gives_first_and_last_only(samples, frames):
    result = seenby.select_events(samples, GW, GH, 24)
    assert result["frames"] == frames
    assert result["events"] == []


@pytest.mark.spec("PCK-4")
def test_pck_4_empty_samples_give_nothing():
    assert seenby.select_events([], GW, GH, 24) == {
        "frames": [], "events": [], "blinking": [], "pointer_moves": 0, "needed": 0,
    }


@pytest.mark.spec("PCK-4")
def test_pck_4_a_state_inside_a_transition_gets_a_frame():
    result = seenby.select_events(events_dbl(), GW, GH, 24)
    expected = {"start": 1, "settled": 2, "until": 4, "px": 1152.0}
    assert result["frames"] == [(0, "first"), (1, "state"), (4, "last")]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == approx_px(expected)


@pytest.mark.spec("PCK-4")
def test_pck_4_state_frames_only_while_the_budget_lasts():
    result = seenby.select_events(events_dbl(), GW, GH, 2)
    assert result["frames"] == [(0, "first"), (4, "last")]


@pytest.mark.spec("PCK-4")
def test_pck_4_one_sample_shows_two_earlier_states():
    result = seenby.select_events(events_two(), GW, GH, 24)
    expected = [
        {"start": 1, "until": 4, "x": 16, "y": 16, "w": 24, "h": 24},
        {"start": 3, "until": 6, "x": 96, "y": 16, "w": 24, "h": 24},
        {"start": 5, "until": 6, "x": 16, "y": 16, "w": 24, "h": 24},
    ]
    assert result["frames"] == [(0, "first"), (4, "change"), (6, "last")]
    assert len(result["events"]) == 3
    assert [event_fields(e, want) for e, want in zip(result["events"], expected)] == expected


@pytest.mark.spec("PCK-4")
@pytest.mark.spec("PCK-3")
def test_pck_3_4_long_change_under_a_small_budget():
    result = seenby.select_events(events_long(), GW, GH, 4)
    expected = {"start": 1, "settled": 12, "until": 14, "global": True}
    assert result["frames"] == [(0, "first"), (4, "fill"), (9, "during"), (14, "last")]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == expected


@pytest.mark.spec("PCK-4")
@pytest.mark.spec("PCK-3")
def test_pck_3_4_long_change_under_the_default_budget():
    result = seenby.select_events(events_long(), GW, GH, 24)
    assert result["frames"] == [
        (0, "first"), (1, "state"), (2, "fill"), (3, "state"), (4, "fill"), (5, "state"), (6, "fill"),
        (7, "state"), (8, "state"), (9, "during"), (10, "state"), (11, "fill"), (14, "last"),
    ]


@pytest.mark.spec("PCK-4")
@pytest.mark.parametrize(
    "samples, budget, needed",
    [
        (events_two(), 24, 3),
        (events_two(), 2, 3),
        ([S({})], 24, 1),
    ],
)
def test_pck_4_needed_is_the_frames_every_window_would_take(samples, budget, needed):
    assert seenby.select_events(samples, GW, GH, budget).get("needed") == needed


# -------- CLI-26, CLI-27, MAN-17 (main() with --selector events)

EVENTS_ARGV = ["clip.mp4", "out", "--selector", "events"]
EVENTS_PROBE = (2.0, 160, 80)
EVENTS_HEADER = "clip.mp4: 2.0 s, 160x80, landscape"
EVENTS_LAYOUT = "  layout: wide, tile 160 px, 2x14 per sheet"
LEGACY_ONLY = "--threshold, --max-gap, --block-k and --sample-fps apply to the legacy selector only"
EVENTS_ANALYSIS_KEYS = [
    "selector", "sample_fps", "samples", "cell", "pixel_threshold", "max_frames", "range", "segment", "changes",
    "shown", "pointer_moves", "blinking",
]
EVENTS_TOP_LEVEL_KEYS = TOP_LEVEL_KEYS + ["events"]
EVENTS_EVENT_KEYS = ["from", "settled", "until", "region", "changed_px", "shown"]
EVENTS_FRAME_KEYS = ["n", "time", "file", "sheet", "reason", "recheck"]


def events_recheck(video, out_dir, n, k, start, length=None, flag="-fps_mode"):
    """MAN-17 `recheck`; `flag` is `passthrough` of FFMPEG_VERSION_LINE (FF-11) unless a test fakes another line."""
    ranged = [] if length is None else ["-t", "%.3f" % length]
    return shlex.join(
        ["ffmpeg", "-ss", "%.3f" % start] + ranged
        + ["-i", video, "-vf", f"fps=4:round=up:start_time=0,select=eq(n\\,{k})", flag, "passthrough"]
        + ["-frames:v", "1", "-q:v", "2", f"{out_dir}/frame-{n:02d}-native.jpg"]
    )


def run_events(
    monkeypatch, capsys, tmp_path, extra, samples, probe=EVENTS_PROBE, frames=None, display=None,
    version=FFMPEG_VERSION_LINE,
):
    return run_main(
        monkeypatch, capsys, tmp_path, EVENTS_ARGV + extra, static(4),
        probe=probe, frames=frames, samples=samples, display=display, version=version,
    )


def run_events_exit(monkeypatch, capsys, tmp_path, argv, samples):
    """main() with the fakes in place, for argv that argparse rejects; returns the Run with `code` and `err`."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / argv[0]).write_bytes(b"")
    run = Run(monkeypatch, EVENTS_PROBE, static(4), None, None, None, None, samples)
    monkeypatch.setattr(sys, "argv", ["seenby.py"] + argv)
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    run.code = exc.value.code
    run.err = capsys.readouterr().err
    return run


@pytest.mark.spec("CLI-26")
@pytest.mark.spec("CLI-27")
def test_cli_26_27_events_selector_run_calls_change_grids_and_prints_its_lines(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, [], events_two())
    assert run.rc == 0
    assert run.display_size_calls == [("clip.mp4", 160, 80)]
    assert run.change_grids_calls == [("clip.mp4", 160, 80, 4, 0.0, None)]
    assert run.thumbnails_calls == []
    assert run.out == (
        EVENTS_HEADER + "\n"
        + "  7 samples at 4 per second, 3 changes, 0 pointer moves, selected 3/24\n"
        + "  frames: 0.00 first, 1.00 change, 1.50 last\n"
        + EVENTS_LAYOUT + "\n"
        + "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )


@pytest.mark.spec("MAN-17")
@pytest.mark.spec("CLI-26")
def test_man_17_cli_26_events_selector_manifest(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("FFMPEG", raising=False)
    run = run_events(monkeypatch, capsys, tmp_path, [], events_two())
    assert run.rc == 0
    assert run.save_samples_calls == [("clip.mp4", [0, 4, 6], [0.0, 1.0, 1.5], "out", 160, 4, 0.0, None)]
    assert run.save_frames_calls == []
    data = manifest()
    assert list(data) == EVENTS_TOP_LEVEL_KEYS
    analysis = data["analysis"]
    assert list(analysis) == EVENTS_ANALYSIS_KEYS
    assert analysis == {
        "selector": "events",
        "sample_fps": 4,
        "samples": 7,
        "cell": 8,
        "pixel_threshold": 24,
        "max_frames": 24,
        "range": {"from": 0.0, "to": 2.0},
        "segment": 120.0,
        "changes": 3,
        "shown": 3,
        "pointer_moves": 0,
        "blinking": [],
    }
    assert data["events"] == [
        {"from": 0.25, "settled": 0.25, "until": 1.0, "region": [16, 16, 24, 24], "changed_px": 576, "shown": True},
        {"from": 0.75, "settled": 0.75, "until": 1.5, "region": [96, 16, 24, 24], "changed_px": 576, "shown": True},
        {"from": 1.25, "settled": 1.25, "until": 1.5, "region": [16, 16, 24, 24], "changed_px": 576, "shown": True},
    ]
    assert all(list(event) == EVENTS_EVENT_KEYS for event in data["events"])
    assert all(list(frame) == EVENTS_FRAME_KEYS for frame in data["frames"])
    assert data["frames"] == [
        {
            "n": n, "time": t, "file": f"frame-{n:02d}.jpg", "sheet": 1, "reason": r,
            "recheck": events_recheck("clip.mp4", "out", n, k, 0.0),
        }
        for n, k, t, r in [(1, 0, 0.0, "first"), (2, 4, 1.0, "change"), (3, 6, 1.5, "last")]
    ]
    assert data["frames"][1]["recheck"] == (
        "ffmpeg -ss 0.000 -i clip.mp4 -vf 'fps=4:round=up:start_time=0,select=eq(n\\,4)' "
        "-fps_mode passthrough -frames:v 1 -q:v 2 out/frame-02-native.jpg"
    )
    assert data["segments"] == [{"n": 1, "from": 0.0, "to": 2.0, "frames": [1, 2, 3], "activity": 3}]


@pytest.mark.spec("MAN-17")
@pytest.mark.spec("FF-11")
def test_man_17_ff_11_recheck_takes_vsync_before_ffmpeg_5_1(monkeypatch, capsys, tmp_path):
    line = "ffmpeg version 4.4.1-static https://johnvansickle.com/ffmpeg/"
    run = run_events(monkeypatch, capsys, tmp_path, [], events_two(), version=line)
    assert run.rc == 0
    data = manifest()
    assert data["ffmpeg"] == line
    assert [f["recheck"] for f in data["frames"]] == [
        events_recheck("clip.mp4", "out", n, k, 0.0, flag="-vsync") for n, k in [(1, 0), (2, 4), (3, 6)]
    ]
    assert data["frames"][1]["recheck"] == (
        "ffmpeg -ss 0.000 -i clip.mp4 -vf 'fps=4:round=up:start_time=0,select=eq(n\\,4)' "
        "-vsync passthrough -frames:v 1 -q:v 2 out/frame-02-native.jpg"
    )


@pytest.mark.spec("CLI-27")
def test_cli_27_changes_without_a_frame_are_named_with_their_range(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, ["--max-frames", "2"], events_two())
    assert run.rc == 0
    assert run.out == (
        EVENTS_HEADER + "\n"
        + "  7 samples at 4 per second, 3 changes, 0 pointer moves, selected 2/2\n"
        + "  frames: 0.00 first, 1.50 last\n"
        + "  1 of 3 changes not shown within 2 frames (all of them would need 3); "
        + "1 of them from 0.25 to 0.25 s: rerun with --from 0.00 --to 1.25\n"
        + EVENTS_LAYOUT + "\n"
        + "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )


@pytest.mark.spec("MAN-17")
def test_man_17_shown_counts_the_events_with_a_frame(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, ["--max-frames", "2"], events_two())
    assert run.rc == 0
    data = manifest()
    analysis = data["analysis"]
    assert analysis["max_frames"] == 2
    assert analysis["changes"] == 3
    assert analysis["shown"] == 2
    assert "events" in data
    assert data["events"][0]["shown"] is False


@pytest.mark.spec("CLI-27")
def test_cli_27_no_change_gives_the_first_and_the_last_frame_only(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, [], [S({})] * 6)
    assert run.rc == 0
    assert run.out == (
        EVENTS_HEADER + "\n"
        + "  6 samples at 4 per second, 0 changes, 0 pointer moves, selected 2/24\n"
        + "  frames: 0.00 first, 1.25 last\n"
        + "  no change: the first and the last frame only\n"
        + EVENTS_LAYOUT + "\n"
        + "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )


@pytest.mark.spec("CLI-27")
@pytest.mark.spec("MAN-17")
def test_cli_27_no_change_except_pointer_like_moves_counts_them(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, [], events_ptr())
    assert run.rc == 0
    assert run.out == (
        EVENTS_HEADER + "\n"
        + "  5 samples at 4 per second, 0 changes, 2 pointer moves, selected 2/24\n"
        + "  frames: 0.00 first, 1.00 last\n"
        + "  no change except 2 pointer-like moves (the pointer, or a small mark such as a radio dot): "
        + "the first and the last frame only\n"
        + EVENTS_LAYOUT + "\n"
        + "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    assert manifest()["analysis"].get("pointer_moves") == 2


@pytest.mark.spec("CLI-27")
def test_cli_27_one_sample_has_no_no_change_line(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, [], [S({})])
    assert run.rc == 0
    assert run.out.splitlines()[:4] == [
        EVENTS_HEADER,
        "  1 samples at 4 per second, 0 changes, 0 pointer moves, selected 1/24",
        "  frames: 0.00 first",
        "  layout: wide, tile 160 px, 1x14 per sheet",
    ]


TOGGLE_BOXES = [box(1, 1, 2, 2), box(8, 1, 2, 2), box(15, 1, 2, 2)]


def toggles(n, starts):
    """`n` samples; the i-th start `k` changes TOGGLE_BOXES[i] at pair k and changes it back at pair k + 2."""
    samples = [S({})] * n
    for k, cells in zip(starts, TOGGLE_BOXES):
        samples[k] = samples[k + 2] = S(cells)
    return samples


@pytest.mark.spec("CLI-27")
@pytest.mark.parametrize(
    "duration, starts, line",
    [
        (
            20.0, [4, 60, 64],
            "  3 of 6 changes not shown within 2 frames (all of them would need 5); "
            "2 of them from 15.00 to 16.00 s: rerun with --from 14.00 --to 17.00",
        ),
        (
            30.0, [2, 100],
            "  2 of 4 changes not shown within 2 frames (all of them would need 4); "
            "1 of them from 0.50 to 0.50 s: rerun with --from 0.00 --to 1.50",
        ),
        (
            20.0, [4, 44],
            "  2 of 4 changes not shown within 2 frames (all of them would need 4); "
            "2 of them from 1.00 to 11.00 s: rerun with --from 0.00 --to 12.00",
        ),
        (
            10.0, [37],
            "  1 of 2 changes not shown within 2 frames (all of them would need 3); "
            "1 of them from 9.25 to 9.25 s: rerun with --from 8.25 --to 10.00",
        ),
    ],
    ids=["largest-run-wins", "tie-takes-the-earliest", "ten-seconds-apart-is-one-run", "clamped-at-the-end"],
)
def test_cli_27_not_shown_line_names_the_largest_run_of_missed_changes(
    monkeypatch, capsys, tmp_path, duration, starts, line
):
    samples = toggles(int(duration * 4) + 1, starts)
    run = run_events(monkeypatch, capsys, tmp_path, ["--max-frames", "2"], samples, probe=(duration, 160, 80))
    assert run.rc == 0
    assert run.out.splitlines()[3] == line


@pytest.mark.spec("CLI-27")
def test_cli_27_the_to_of_the_hint_is_rounded_down_to_stay_inside_the_video(monkeypatch, capsys, tmp_path):
    late = [S({}), S({}), S({}), S(box(2, 2, 3, 3)), S({}), S(box(2, 2, 3, 3)), S({})]
    run = run_events(monkeypatch, capsys, tmp_path, ["--max-frames", "2"], late, probe=(1.618, 160, 80))
    assert run.rc == 0
    assert run.out.splitlines()[2:4] == [
        "  frames: 0.00 first, 1.50 last",
        "  1 of 2 changes not shown within 2 frames (all of them would need 3); "
        "1 of them from 0.75 to 0.75 s: rerun with --from 0.00 --to 1.61",
    ]


@pytest.mark.spec("CLI-27")
def test_cli_27_dry_run_stops_after_the_layout_line(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, ["--dry-run"], events_two())
    assert run.rc == 0
    assert run.out == (
        EVENTS_HEADER + "\n"
        + "  7 samples at 4 per second, 3 changes, 0 pointer moves, selected 3/24\n"
        + "  frames: 0.00 first, 1.00 change, 1.50 last\n"
        + EVENTS_LAYOUT + "\n"
    )
    assert len(run.change_grids_calls) == 1
    assert run.save_samples_calls == []
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []
    assert not (tmp_path / "out").exists()


@pytest.mark.spec("CLI-26")
@pytest.mark.spec("CLI-27")
def test_cli_26_27_range_goes_to_change_grids_and_shifts_the_times(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, ["--from", "1"], events_two(), probe=(3.0, 160, 80))
    lines = run.out.splitlines()
    assert run.rc == 0
    assert run.change_grids_calls == [("clip.mp4", 160, 80, 4, 1.0, 2.0)]
    assert lines[0] == "clip.mp4: 3.0 s, 160x80, landscape"
    assert lines[1] == "  range: 1.0-3.0 s"
    assert lines[2] == "  7 samples at 4 per second, 3 changes, 0 pointer moves, selected 3/24"
    assert lines[3] == "  frames: 1.00 first, 2.00 change, 2.50 last"
    assert run.save_samples_calls == [("clip.mp4", [0, 4, 6], [1.0, 2.0, 2.5], "out", 160, 4, 1.0, 2.0)]
    frames = manifest()["frames"]
    assert [f["recheck"] for f in frames] == [
        events_recheck("clip.mp4", "out", n, k, 1.0, 2.0) for n, k in [(1, 0), (2, 4), (3, 6)]
    ]
    assert frames[0]["recheck"] == (
        "ffmpeg -ss 1.000 -t 2.000 -i clip.mp4 -vf 'fps=4:round=up:start_time=0,select=eq(n\\,0)' "
        "-fps_mode passthrough -frames:v 1 -q:v 2 out/frame-01-native.jpg"
    )


@pytest.mark.spec("CLI-26")
def test_cli_26_range_checks_come_before_change_grids(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, ["--to", "5"], events_two())
    assert run.rc == 1
    assert "--to 5.0 is past the end of the video (2.0 s)" in run.err
    assert run.display_size_calls == []
    assert run.change_grids_calls == []


@pytest.mark.spec("CLI-26")
@pytest.mark.spec("MAN-17")
def test_cli_26_rotated_stream_uses_the_display_size_everywhere(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, [], events_two(), probe=(2.0, 80, 160), display=(160, 80))
    assert run.rc == 0
    assert run.display_size_calls == [("clip.mp4", 80, 160)]
    assert run.change_grids_calls == [("clip.mp4", 160, 80, 4, 0.0, None)]
    assert run.out.splitlines()[0] == "clip.mp4: 2.0 s, 160x80, landscape"
    video = manifest()["video"]
    assert video["width"] == 160
    assert video["height"] == 80


@pytest.mark.spec("CLI-26")
@pytest.mark.parametrize(
    "probe, display, size",
    [
        ((2.0, 6, 6), None, "6x6"),
        ((2.0, 160, 7), None, "160x7"),
        ((2.0, 6, 160), (160, 6), "160x6"),
    ],
)
def test_cli_26_a_frame_under_one_cell_is_refused(monkeypatch, capsys, tmp_path, probe, display, size):
    run = run_events(monkeypatch, capsys, tmp_path, [], events_two(), probe=probe, display=display)
    assert run.rc == 1
    assert f"clip.mp4: the frame ({size}) is smaller than 8x8 px; use --selector legacy" in run.err.splitlines()
    assert run.change_grids_calls == []


@pytest.mark.spec("CLI-26")
def test_cli_26_save_samples_value_error_is_reported_with_the_video_name(monkeypatch, capsys, tmp_path):
    error = ValueError("ffmpeg wrote 2 of 3 frames")
    run = run_events(monkeypatch, capsys, tmp_path, [], events_two(), frames=error)
    assert run.rc == 1
    assert "clip.mp4: ffmpeg wrote 2 of 3 frames" in run.err.splitlines()
    assert run.out.splitlines() == [
        EVENTS_HEADER,
        "  7 samples at 4 per second, 3 changes, 0 pointer moves, selected 3/24",
        "  frames: 0.00 first, 1.00 change, 1.50 last",
        EVENTS_LAYOUT,
    ]
    assert not (tmp_path / "out" / "frames.json").exists()


@pytest.mark.spec("CLI-26")
@pytest.mark.parametrize(
    "extra",
    [["--threshold", "5"], ["--max-gap", "2"], ["--block-k", "0"], ["--sample-fps", "4"]],
)
def test_cli_26_legacy_options_with_the_events_selector_are_a_usage_error(monkeypatch, capsys, tmp_path, extra):
    run = run_events_exit(monkeypatch, capsys, tmp_path, EVENTS_ARGV + extra, events_two())
    assert run.code == 2
    assert LEGACY_ONLY in run.err
    assert run.change_grids_calls == []


@pytest.mark.spec("CLI-26")
def test_cli_26_no_samples_is_a_decode_failure(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, [], [])
    assert run.rc == 1
    assert "could not decode the video: no frames" in run.err


@pytest.mark.spec("CLI-26")
def test_cli_26_ffmpeg_failure_in_change_grids_names_the_grids_stage(monkeypatch, capsys, tmp_path):
    error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="x\nboom\n")
    run = run_events(monkeypatch, capsys, tmp_path, [], error)
    assert run.rc == 1
    assert "ffmpeg failed during grids (exit 1): boom" in run.err


@pytest.mark.spec("CLI-26")
def test_cli_26_unknown_selector_is_an_argparse_choices_error(monkeypatch, capsys, tmp_path):
    run = run_events_exit(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--selector", "bogus"], events_two())
    assert run.code == 2
    assert "invalid choice" in run.err
    assert "bogus" in run.err


@pytest.mark.spec("CLI-26")
@pytest.mark.parametrize(
    "extra, thumbs",
    [
        ([], static(30)),
        (["--threshold", "30"], steps(4, 8)),
        (["--max-gap", "2", "--block-k", "0", "--sample-fps", "4"], blocky()),
    ],
)
def test_cli_26_selector_legacy_changes_nothing(monkeypatch, capsys, tmp_path, extra, thumbs):
    outputs = []
    for name, selector in [("plain", []), ("legacy", ["--selector", "legacy"])]:
        where = tmp_path / name
        where.mkdir()
        run = run_main(monkeypatch, capsys, where, ["clip.mp4", "out"] + extra + selector, thumbs)
        assert run.rc == 0
        assert run.change_grids_calls == []
        assert run.save_samples_calls == []
        outputs.append((run.out, run.err, run.save_frames_calls, run.contact_sheets_calls, manifest()))
    assert outputs[0] == outputs[1]


# -------- EVT-3: select_events cuts `until` where the box's cell means stop matching `settled`


def events_flash():
    return [M({}, {}), M(box(2, 2, 3, 1, 200), box(2, 2, 3, 1)), M({}, {}), M({}, {}), M({}, {})]


@pytest.mark.spec("EVT-3")
def test_evt_3_a_flash_that_goes_back_is_cut_at_its_last_sample():
    result = seenby.select_events(events_flash(), GW, GH, 24)
    expected = {"settled": 1, "until": 1}
    assert result["frames"] == [(0, "first"), (1, "change"), (4, "last")]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == expected


@pytest.mark.spec("EVT-3")
def test_evt_3_more_than_a_quarter_of_the_cells_beyond_hold_delta_cuts():
    on = box(2, 2, 4, 2, 200)
    samples = [
        M({}, {}),
        M(on, box(2, 2, 4, 2)),
        M(on | {(2, 2): 0}, {}),
        M(on | {(2, 2): 194}, {}),
        M(on | box(2, 2, 3, 1, 0), {}),
        M({}, {}),
    ]
    result = seenby.select_events(samples, GW, GH, 24)
    expected = {"x": 16, "y": 16, "w": 32, "h": 16, "settled": 1, "until": 3}
    assert result["frames"] == [(0, "first"), (3, "change"), (5, "last")]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == expected


@pytest.mark.spec("EVT-3")
@pytest.mark.spec("CLI-27")
@pytest.mark.spec("MAN-17")
def test_evt_3_console_and_manifest_use_the_cut_until(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, ["--max-frames", "2"], events_flash())
    assert run.rc == 0
    assert run.out == (
        EVENTS_HEADER + "\n"
        + "  5 samples at 4 per second, 1 changes, 0 pointer moves, selected 2/2\n"
        + "  frames: 0.00 first, 1.00 last\n"
        + "  1 of 1 changes not shown within 2 frames (all of them would need 3); "
        + "1 of them from 0.25 to 0.25 s: rerun with --from 0.00 --to 1.25\n"
        + EVENTS_LAYOUT + "\n"
        + "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    data = manifest()
    assert data["analysis"]["changes"] == 1
    assert data["analysis"]["shown"] == 0
    assert data.get("events") == [
        {"from": 0.25, "settled": 0.25, "until": 0.25, "region": [16, 16, 24, 8], "changed_px": 192, "shown": False}
    ]


# -------- EVT-4: select_events sets aside a one-cell-wide box that blinks between two looks, such as a text caret

BLINK_ON = box(5, 2, 1, 4, 100)
BLINK_C = box(5, 2, 1, 4, 60)


def events_blink(on=BLINK_ON, change=BLINK_C):
    """The spec's `blink`: a caret that appears at 1, 5, 9 and goes at 3, 7, each look on screen for two samples."""
    return [M(on if k % 4 in (1, 2) else {}, change if k % 2 == 1 else {}) for k in range(10)]


def blink_area(count, first, last, x=40, y=16, w=8, h=32):
    return {"x": x, "y": y, "w": w, "h": h, "count": count, "first": first, "last": last}


BLINK_BOX = {"x": 40, "y": 16, "w": 8, "h": 32}
FIVE_CHANGE_FRAMES = [(0, "first"), (2, "change"), (4, "change"), (6, "change"), (8, "change"), (9, "last")]


@pytest.mark.spec("EVT-4")
def test_evt_4_a_box_one_cell_wide_blinking_between_two_looks_is_a_blinking_area():
    result = seenby.select_events(events_blink(), GW, GH, 24)
    assert result.get("blinking") == [blink_area(5, 1, 9)]
    assert result["events"] == []
    assert result["frames"] == [(0, "first"), (9, "last")]
    assert result.get("needed") == 2


@pytest.mark.spec("EVT-4")
def test_evt_4_a_third_look_is_not_a_blinking_area():
    three = events_blink()
    three[5] = (grid(box(5, 2, 1, 4, 180)), three[5][1])
    three[6] = (grid(box(5, 2, 1, 4, 180)), three[6][1])
    result = seenby.select_events(three, GW, GH, 24)
    assert result.get("blinking") == []
    assert [event_fields(e, BLINK_BOX) for e in result["events"]] == [BLINK_BOX] * 5
    assert [round(e["px"], 4) for e in result["events"]] == [60.2353] * 5
    assert [(e["settled"], e["until"]) for e in result["events"]] == [(1, 2), (3, 4), (5, 6), (7, 8), (9, 9)]
    assert result["frames"] == FIVE_CHANGE_FRAMES
    assert result.get("needed") == 6


@pytest.mark.spec("EVT-4")
def test_evt_4_a_caret_that_stops_with_a_long_last_event_is_still_a_blinking_area():
    samples = events_blink() + [M(BLINK_ON, {}), M({}, BLINK_C)] + [M({}, {})] * 4
    result = seenby.select_events(samples, GW, GH, 24)
    assert result["frames"] == [(0, "first"), (15, "last")]
    assert result["events"] == []
    assert result.get("blinking") == [blink_area(6, 1, 11)]


@pytest.mark.spec("EVT-4")
def test_evt_4_a_caret_that_pauses_and_resumes_is_one_blinking_area():
    blink = events_blink()
    samples = blink[:8] + [M({}, {})] * 8 + blink[:8]
    result = seenby.select_events(samples, GW, GH, 24)
    assert result["frames"] == [(0, "first"), (23, "last")]
    assert result["events"] == []
    assert result.get("blinking") == [blink_area(8, 1, 23)]


@pytest.mark.spec("EVT-4")
@pytest.mark.parametrize(
    "on, change",
    [(box(5, 2, 2, 4, 100), box(5, 2, 2, 4, 30)), (BLINK_ON, box(5, 2, 1, 4, 128))],
    ids=["two-cells-wide", "128.502-px"],
)
def test_evt_4_a_wider_or_heavier_box_is_not_a_blinking_area(on, change):
    result = seenby.select_events(events_blink(on, change), GW, GH, 24)
    assert result.get("blinking") == []
    assert len(result["events"]) == 5
    assert result["frames"] == FIVE_CHANGE_FRAMES


@pytest.mark.spec("EVT-4")
def test_evt_4_three_changes_are_not_a_blinking_area():
    samples = events_blink()[:7] + [M({}, {})] * 3
    result = seenby.select_events(samples, GW, GH, 24)
    assert result.get("blinking") == []
    assert [event_fields(e, BLINK_BOX) for e in result["events"]] == [BLINK_BOX] * 3
    assert [e["until"] for e in result["events"]] == [2, 4, 6]
    assert result["frames"] == [(0, "first"), (2, "change"), (4, "change"), (6, "change"), (9, "last")]


TYPED_CARET = {(6, 1): 100, (6, 2): 120, (6, 3): 120, (6, 4): 100}
TYPED_CC = box(6, 1, 1, 4, 60)


def caret_after(text, change):
    """`text` typed at 1 (`change` its change plane), then the spec's CARET blinking in cell column 6 from 3."""
    return [M({}, {}), M(text, change)] + [
        M(text | (TYPED_CARET if k % 4 in (0, 3) else {}), TYPED_CC if k % 2 == 1 else {}) for k in range(2, 12)
    ]


@pytest.mark.spec("EVT-4")
def test_evt_4_a_caret_dropped_from_content_no_longer_cuts_the_typed_text():
    typed = caret_after(box(2, 2, 5, 2, 150), box(2, 2, 5, 2))
    result = seenby.select_events(typed, GW, GH, 2)
    expected = {"start": 1, "settled": 1, "until": 11, "x": 16, "y": 16, "w": 40, "h": 16, "px": 640.0}
    assert result["frames"] == [(0, "first"), (11, "last")]
    assert result.get("blinking") == [blink_area(5, 3, 11, x=48, y=8)]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == approx_px(expected)


@pytest.mark.spec("EVT-4")
def test_evt_4_cells_inside_a_blinking_area_are_left_out_of_evt_3():
    short = caret_after(box(5, 2, 2, 2, 150), box(5, 2, 2, 2))
    result = seenby.select_events(short, GW, GH, 2)
    expected = {"start": 1, "settled": 1, "until": 11, "x": 40, "y": 16, "w": 16, "h": 16, "px": 256.0}
    assert result["frames"] == [(0, "first"), (11, "last")]
    assert result.get("blinking") == [blink_area(5, 3, 11, x=48, y=8)]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == approx_px(expected)


@pytest.mark.spec("EVT-4")
@pytest.mark.parametrize(
    "on, change, region, px",
    [
        (box(2, 5, 10, 1, 100), box(2, 5, 10, 1, 60), {"x": 16, "y": 40, "w": 80, "h": 8}, 150.5882),
        (box(5, 0, 1, 9, 100), box(5, 0, 1, 9, 30), {"x": 40, "y": 0, "w": 8, "h": 72}, 67.7647),
    ],
    ids=["80x8-underline", "8x72-taller-than-caret-h"],
)
def test_evt_4_only_a_box_one_cell_wide_and_at_most_caret_h_tall_can_blink(on, change, region, px):
    result = seenby.select_events(events_blink(on, change), GW, GH, 24)
    assert result.get("blinking") == []
    assert [event_fields(e, region) for e in result["events"]] == [region] * 5
    assert [round(e["px"], 4) for e in result["events"]] == [px] * 5
    assert result["frames"] == FIVE_CHANGE_FRAMES


@pytest.mark.spec("EVT-4")
def test_evt_4_a_box_exactly_caret_h_tall_can_blink():
    result = seenby.select_events(events_blink(box(5, 0, 1, 8, 100), box(5, 0, 1, 8, 30)), GW, GH, 24)
    assert result.get("blinking") == [blink_area(5, 1, 9, y=0, h=64)]
    assert result["events"] == []
    assert result["frames"] == [(0, "first"), (9, "last")]


@pytest.mark.spec("EVT-4")
def test_evt_4_a_pair_left_with_the_pointer_after_a_blink_is_a_pointer_move():
    pa, pb = box(10, 2, 3, 4, 170), box(15, 5, 3, 4, 160)
    ptr_blink = [
        M(BLINK_ON if k % 4 in (1, 2) else {}, (BLINK_C | pa | pb) if k == 3 else (BLINK_C if k % 2 == 1 else {}))
        for k in range(10)
    ]
    result = seenby.select_events(ptr_blink, GW, GH, 24)
    assert result["frames"] == [(0, "first"), (9, "last")]
    assert result["events"] == []
    assert result.get("pointer_moves") == 1
    assert result.get("blinking") == [blink_area(5, 1, 9)]


@pytest.mark.spec("EVT-4")
def test_evt_4_a_change_that_is_not_faint_splits_the_blinks_into_two_areas():
    on2, char = box(5, 2, 1, 4, 180), box(5, 2, 1, 4, 50)
    narrow = [
        M(
            (BLINK_ON if k % 4 in (1, 2) else {}) if k < 9 else (on2 if (k - 9) // 2 % 2 == 0 else char),
            box(5, 2, 1, 4, 200) if k == 9 else (BLINK_C if k % 2 == 1 else {}),
        )
        for k in range(19)
    ]
    result = seenby.select_events(narrow, GW, GH, 24)
    expected = dict(BLINK_BOX, start=9, settled=9, until=18)
    assert result["frames"] == [(0, "first"), (18, "last")]
    assert result.get("blinking") == [blink_area(4, 1, 7), blink_area(4, 11, 17)]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == expected
    assert round(result["events"][0]["px"], 4) == 200.7843


@pytest.mark.spec("EVT-4")
def test_evt_4_a_third_look_from_a_state_the_run_never_had_starts_the_next_run():
    pl, pr, ib = box(12, 2, 2, 4, 150), box(4, 2, 2, 4, 150), box(4, 2, 2, 4, 60)
    rest = [
        M(
            (BLINK_ON if k % 4 in (1, 2) else {}) if k < 8 else ib | (box(5, 2, 1, 4, 160) if k % 4 in (1, 2) else {}),
            (pl | pr) if k == 8 else (BLINK_C if k % 2 == 1 else {}),
        )
        for k in range(18)
    ]
    result = seenby.select_events(rest, GW, GH, 24)
    assert result["frames"] == [(0, "first"), (17, "last")]
    assert result["events"] == []
    assert result.get("pointer_moves") == 1
    assert result.get("blinking") == [blink_area(4, 1, 7), blink_area(5, 9, 17)]


@pytest.mark.spec("EVT-4")
def test_evt_4_a_third_look_made_from_a_look_of_the_run_belongs_to_no_run():
    dot = [
        M(
            (BLINK_ON if k % 4 in (1, 2) else {}) if k < 9 else box(5, 2, 1, 4, 130 if k % 4 in (1, 2) else 30),
            box(5, 2, 1, 4, 90) if k == 9 else (BLINK_C if k % 2 == 1 else {}),
        )
        for k in range(19)
    ]
    result = seenby.select_events(dot, GW, GH, 24)
    expected = dict(BLINK_BOX, start=9, settled=9, until=18)
    assert result["frames"] == [(0, "first"), (18, "last")]
    assert result.get("blinking") == [blink_area(4, 1, 7), blink_area(4, 11, 17)]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == expected
    assert round(result["events"][0]["px"], 4) == 90.3529


@pytest.mark.spec("EVT-4")
def test_evt_4_a_third_look_is_checked_against_the_run_in_sample_start_minus_1():
    """The dot of the `dot` row drawn over two pairs, top half at 9 and bottom half at 10 (start 9, settled 10), then
    the caret changing at 12, 14, 16 and 18. Sample 8 has the run's "off" look; the half-drawn sample 9 differs from
    both of the run's looks, so taking it would start a run of five blinks at 10."""
    samples = []
    for k in range(20):
        if k < 9:
            means, change = (BLINK_ON if k % 4 in (1, 2) else {}), (BLINK_C if k % 2 == 1 else {})
        elif k == 9:
            means, change = box(5, 2, 1, 2, 130), box(5, 2, 1, 2, 90)
        else:
            means = box(5, 2, 1, 4, 130 if k % 4 in (2, 3) else 30)
            change = box(5, 4, 1, 2, 90) if k == 10 else (BLINK_C if k % 2 == 0 else {})
        samples.append(M(means, change))
    result = seenby.select_events(samples, GW, GH, 24)
    expected = dict(BLINK_BOX, start=9, settled=10, until=19)
    assert result["frames"] == [(0, "first"), (19, "last")]
    assert result.get("blinking") == [blink_area(4, 1, 7), blink_area(4, 12, 18)]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == expected
    assert round(result["events"][0]["px"], 4) == 90.3529


@pytest.mark.spec("EVT-4")
def test_evt_4_a_faint_event_with_the_look_of_the_runs_only_event_replaces_it():
    same = [
        M(
            BLINK_ON if k in (1, 2, 3, 4) or (k >= 7 and k % 4 in (3, 0)) else {},
            BLINK_C if k in (1, 3) or (k >= 5 and k % 2 == 1) else {},
        )
        for k in range(16)
    ]
    result = seenby.select_events(same, GW, GH, 24)
    expected = dict(BLINK_BOX, start=1, settled=1, until=15)
    assert result["frames"] == [(0, "first"), (15, "last")]
    assert result.get("blinking") == [blink_area(7, 3, 15)]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == expected


@pytest.mark.spec("EVT-4")
def test_evt_4_areas_outside_an_events_columns_leave_all_its_cells_in_evt_3():
    tx = box(2, 2, 2, 2, 150)
    two_carets = [
        M(
            (
                {} if k < 1 else tx | ({(2, 2): 151} if k >= 12 else {})
                | (box(7, 1, 1, 4, 100) if k >= 3 and (k - 3) // 4 % 2 == 0 else {})
                | (box(10, 1, 1, 4, 100) if k >= 5 and (k - 5) // 4 % 2 == 0 else {})
            ),
            box(2, 2, 2, 2) if k == 1
            else box(7, 1, 1, 4, 60) if k >= 3 and (k - 3) % 4 == 0
            else box(10, 1, 1, 4, 60) if k >= 5 and (k - 5) % 4 == 0
            else {},
        )
        for k in range(24)
    ]
    result = seenby.select_events(two_carets, GW, GH, 24)
    expected = {"start": 1, "settled": 1, "until": 23, "x": 16, "y": 16, "w": 16, "h": 16, "px": 256.0}
    assert result["frames"] == [(0, "first"), (23, "last")]
    assert result.get("blinking") == [blink_area(6, 3, 23, x=56, y=8), blink_area(5, 5, 21, x=80, y=8)]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == approx_px(expected)


@pytest.mark.spec("EVT-4")
def test_evt_4_evt_3_compares_the_cells_of_an_area_that_does_not_overlap_the_event_in_time():
    mark = box(5, 2, 1, 4, 40)
    after_stop = events_blink() + [
        M(BLINK_ON, {}), M({}, BLINK_C), M({}, {}), M({}, {}), M(mark, mark), M(mark, {}),
    ] + [M({}, {})] * 4
    result = seenby.select_events(after_stop, GW, GH, 24)
    expected = dict(BLINK_BOX, start=14, settled=14, until=15)
    assert result["frames"] == [(0, "first"), (15, "change"), (19, "last")]
    assert result.get("blinking") == [blink_area(6, 1, 11)]
    assert len(result["events"]) == 1
    assert event_fields(result["events"][0], expected) == expected
    assert round(result["events"][0]["px"], 4) == 40.1569


@pytest.mark.spec("EVT-4")
def test_evt_4_blobs_smaller_than_a_blink_inside_its_box_are_removed_over_its_pairs():
    """Each caret appearance is drawn over two pairs, top half then bottom half, so the blinks at 2, 7 and 12 span
    pairs 1-2, 6-7 and 11-12 and none of their blobs has the blink's box."""
    phases = [
        (box(5, 2, 1, 2, 100), box(5, 2, 1, 2, 60)),
        (BLINK_ON, box(5, 4, 1, 2, 60)),
        (BLINK_ON, {}),
        ({}, BLINK_C),
        ({}, {}),
    ]
    samples = [M({}, {})] + [M(*phases[(k - 1) % 5]) for k in range(1, 14)]
    result = seenby.select_events(samples, GW, GH, 24)
    assert result.get("blinking") == [blink_area(5, 2, 12)]
    assert result["events"] == []
    assert result["frames"] == [(0, "first"), (13, "last")]
    assert result.get("pointer_moves") == 0


def alternating(on, change, gap, looks=5):
    """`change` at pairs 1, 1 + gap, ... of `looks * gap + 1` samples; the means show `on` after the 1st, 3rd, ...
    change and nothing after the 2nd, 4th, ...: `looks` alternating looks of `gap` samples each."""
    return [M({}, {})] + [
        M(on if (k - 1) // gap % 2 == 0 else {}, change if (k - 1) % gap == 0 else {})
        for k in range(1, looks * gap + 1)
    ]


@pytest.mark.spec("EVT-4")
@pytest.mark.parametrize(
    "samples, blinking, events",
    [
        (alternating(box(3, 2, 4, 1, 100), box(3, 2, 4, 1, 60), 2), [], 5),
        (alternating(BLINK_ON, BLINK_C, 4), [blink_area(5, 1, 17)], 0),
        (alternating(BLINK_ON, BLINK_C, 5), [], 5),
        ([M({}, BLINK_C if k % 2 == 1 else {}) for k in range(10)], [], 5),
    ],
    ids=["one-cell-tall-four-cells-wide", "looks-of-4-samples", "looks-of-5-samples", "one-look-only"],
)
def test_evt_4_a_thin_box_counts_with_brief_events_and_two_looks(samples, blinking, events):
    result = seenby.select_events(samples, GW, GH, 24)
    assert result.get("blinking") == blinking
    assert len(result["events"]) == events


@pytest.mark.spec("EVT-4")
def test_evt_4_blinking_areas_come_in_the_order_of_their_first_event():
    right_on, right_change = box(15, 2, 1, 4, 100), box(15, 2, 1, 4, 60)
    samples = []
    for k in range(14):
        left = k >= 4 and (k - 4) // 2 % 2 == 0
        right = k % 4 in (1, 2)
        change = right_change if k % 2 == 1 else BLINK_C if k >= 4 else {}
        samples.append(M((BLINK_ON if left else {}) | (right_on if right else {}), change))
    result = seenby.select_events(samples, GW, GH, 24)
    assert result.get("blinking") == [blink_area(7, 1, 13, x=120), blink_area(5, 4, 12)]
    assert result["events"] == []
    assert result["frames"] == [(0, "first"), (13, "last")]


@pytest.mark.spec("EVT-4")
@pytest.mark.spec("CLI-27")
@pytest.mark.spec("MAN-17")
def test_evt_4_cli_27_man_17_a_blinking_area_is_named_and_listed(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, [], events_blink())
    assert run.rc == 0
    assert run.out == (
        EVENTS_HEADER + "\n"
        + "  10 samples at 4 per second, 0 changes, 0 pointer moves, selected 2/24\n"
        + "  frames: 0.00 first, 2.25 last\n"
        + "  ignored a blinking area at 40,16 8x32 px (5 times from 0.25 to 2.25 s): "
        + "a text caret, or a small mark toggled back and forth\n"
        + "  no change: the first and the last frame only\n"
        + EVENTS_LAYOUT + "\n"
        + "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    data = manifest()
    assert data["analysis"]["changes"] == 0
    assert data["analysis"].get("blinking") == [{"region": [40, 16, 8, 32], "count": 5, "from": 0.25, "to": 2.25}]
    assert data.get("events") == []


@pytest.mark.spec("CLI-27")
@pytest.mark.spec("MAN-17")
def test_cli_27_man_17_blinking_times_are_shifted_by_the_range_start(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, ["--from", "1"], events_blink(), probe=(4.0, 160, 80))
    assert run.rc == 0
    assert run.out.splitlines()[3:5] == [
        "  frames: 1.00 first, 3.25 last",
        "  ignored a blinking area at 40,16 8x32 px (5 times from 1.25 to 3.25 s): "
        "a text caret, or a small mark toggled back and forth",
    ]
    assert manifest()["analysis"].get("blinking") == [
        {"region": [40, 16, 8, 32], "count": 5, "from": 1.25, "to": 3.25}
    ]


# -------- FF-11 (passthrough) and the bytes-like samples of the step 12 vocabulary


@pytest.mark.spec("FF-11")
@pytest.mark.parametrize(
    "version, option",
    [
        ("ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers", "-fps_mode"),
        ("ffmpeg version n9.0.2-10-g51c4a23d74-20260926 Copyright (c) 2000-2026 the FFmpeg developers", "-fps_mode"),
        ("ffmpeg version 5.1", "-fps_mode"),
        ("ffmpeg version 10.0", "-fps_mode"),
        ("ffmpeg version 7.1-full_build-www.gyan.dev", "-fps_mode"),
        ("ffmpeg version 4.4.1-static https://johnvansickle.com/ffmpeg/", "-vsync"),
        ("ffmpeg version 5.0.1", "-vsync"),
        ("ffmpeg version n4.3.2", "-vsync"),
        ("ffmpeg version N-112345-gabcdef0", "-fps_mode"),
        ("ffmpeg version 2024-10-10-git-0f5592cfc7-full_build-www.gyan.dev", "-fps_mode"),
        ("", "-fps_mode"),
        ("avconv version 12", "-fps_mode"),
    ],
)
def test_ff_11_passthrough_option_by_ffmpeg_version(version, option):
    assert seenby.passthrough(version) == option


@pytest.mark.spec("PCK-4")
@pytest.mark.spec("EVT-3")
@pytest.mark.parametrize(
    "samples, frames",
    [
        (events_two(), [(0, "first"), (4, "change"), (6, "last")]),
        (
            [
                M({}, {}),
                M(box(2, 2, 4, 2, 200), box(2, 2, 4, 2)),
                M(box(2, 2, 4, 2, 200) | {(2, 2): 0}, {}),
                M(box(2, 2, 4, 2, 200) | {(2, 2): 194}, {}),
                M(box(2, 2, 4, 2, 200) | box(2, 2, 3, 1, 0), {}),
                M({}, {}),
            ],
            [(0, "first"), (3, "change"), (5, "last")],
        ),
    ],
    ids=["two", "on"],
)
def test_pck_4_samples_may_be_memoryviews(samples, frames):
    views = [(memoryview(mean), memoryview(change)) for mean, change in samples]
    assert seenby.select_events(views, GW, GH, 24)["frames"] == frames


# -------- CLI-28 (step 13): the events selector by default

SELECTOR_HELP = (
    "events: changed pixels at native resolution, one frame per screen state that changed (the default); "
    "legacy: 32x32 thumbnails against a threshold, a timer and a cap, deprecated and to be removed; "
    "--threshold, --max-gap, --block-k or --sample-fps without --selector choose legacy"
)
EVENTS_TWO_DRY_RUN_STDOUT = (
    EVENTS_HEADER + "\n"
    + "  7 samples at 4 per second, 3 changes, 0 pointer moves, selected 3/24\n"
    + "  frames: 0.00 first, 1.00 change, 1.50 last\n"
    + EVENTS_LAYOUT + "\n"
)


def run_without_and_with(monkeypatch, capsys, tmp_path, argv, selector, thumbs, probe):
    """main() on `argv` as given and on `argv` with `--selector <selector>`, each in its own folder, both with
    `thumbnails` and `change_grids` faked (samples `two`); each Run carries its `frames.json` as `manifest`."""
    runs = []
    for name, extra in [("without", []), ("with", ["--selector", selector])]:
        where = tmp_path / name
        where.mkdir()
        run = run_main(
            monkeypatch, capsys, where, argv + extra, thumbs, probe=probe, samples=events_two(), as_given=True
        )
        run.manifest = manifest() if os.path.exists(os.path.join("out", "frames.json")) else None
        runs.append(run)
    return runs


def observed(run):
    return (
        run.rc, run.out, run.err, run.thumbnails_calls, run.change_grids_calls, run.save_frames_calls,
        run.save_samples_calls, run.contact_sheets_calls, run.manifest,
    )


@pytest.mark.spec("CLI-28")
def test_cli_28_without_selector_the_events_selector_runs(monkeypatch, capsys, tmp_path):
    without, with_events = run_without_and_with(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], "events", static(4), EVENTS_PROBE
    )
    assert without.rc == 0
    assert without.change_grids_calls == [("clip.mp4", 160, 80, 4, 0.0, None)]
    assert without.thumbnails_calls == []
    assert without.out == (
        EVENTS_TWO_DRY_RUN_STDOUT
        + "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    assert without.manifest["analysis"]["selector"] == "events"
    assert observed(without) == observed(with_events)


@pytest.mark.spec("CLI-28")
def test_cli_28_dry_run_without_selector_prints_the_events_lines(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], static(4),
        probe=EVENTS_PROBE, samples=events_two(), as_given=True,
    )
    assert run.rc == 0
    assert run.out == EVENTS_TWO_DRY_RUN_STDOUT
    assert run.thumbnails_calls == []
    assert run.change_grids_calls == [("clip.mp4", 160, 80, 4, 0.0, None)]
    assert run.save_samples_calls == []
    assert run.save_frames_calls == []
    assert run.contact_sheets_calls == []
    assert not (tmp_path / "out").exists()


@pytest.mark.spec("CLI-28")
@pytest.mark.parametrize(
    "extra",
    [
        ["--threshold", "5"],
        ["--max-gap", "2"],
        ["--block-k", "0"],
        ["--sample-fps", "4"],
        ["--threshold", "12"],
    ],
    ids=["threshold", "max-gap", "block-k", "sample-fps", "threshold-at-its-default"],
)
def test_cli_28_a_legacy_only_option_without_selector_chooses_legacy(monkeypatch, capsys, tmp_path, extra):
    without, with_legacy = run_without_and_with(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"] + extra, "legacy", static(30), (15.0, 800, 600)
    )
    assert without.rc == 0
    assert len(without.thumbnails_calls) == 1
    assert without.change_grids_calls == []
    assert without.save_samples_calls == []
    assert without.out.splitlines()[1].startswith("  30 thumbnails, selected ")
    assert observed(without) == observed(with_legacy)


@pytest.mark.spec("CLI-28")
def test_cli_28_explicit_legacy_gives_the_static_legacy_result(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--selector", "legacy"], static(30), samples=events_two()
    )
    assert run.rc == 0
    assert run.change_grids_calls == []
    assert run.thumbnails_calls == [("clip.mp4", 2.0, 0.0, None)]
    assert run.out == STATIC_30_STDOUT
    assert manifest() == static_30_manifest()


@pytest.mark.spec("CLI-28")
@pytest.mark.spec("CLI-26")
def test_cli_28_explicit_events_with_a_legacy_only_option_stays_a_usage_error(monkeypatch, capsys, tmp_path):
    run = run_events_exit(monkeypatch, capsys, tmp_path, EVENTS_ARGV + ["--threshold", "5"], events_two())
    assert run.code == 2
    assert LEGACY_ONLY in run.err
    assert run.change_grids_calls == []


@pytest.mark.spec("CLI-28")
@pytest.mark.spec("CLI-26")
def test_cli_28_a_frame_under_one_cell_without_selector_points_to_selector_legacy(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4), probe=(2.0, 6, 6), samples=events_two(),
        as_given=True,
    )
    assert run.rc == 1
    assert "clip.mp4: the frame (6x6) is smaller than 8x8 px; use --selector legacy" in run.err.splitlines()
    assert run.change_grids_calls == []
    assert run.thumbnails_calls == []


@pytest.mark.spec("CLI-28")
def test_cli_28_help_names_events_the_default_and_legacy_deprecated(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "1000")
    monkeypatch.setattr(sys, "argv", ["seenby.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    assert exc.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert SELECTOR_HELP in out
    assert "cap on kept frames (default: 24)" in out


def help_entries(monkeypatch, capsys):
    """`--help` at 1000 columns as (help text per option string, whitespace collapsed; option strings in printed
    order). An entry starts on a line indented two spaces with a dash, its help follows two spaces on that line or
    on the lines indented deeper."""
    monkeypatch.setenv("COLUMNS", "1000")
    monkeypatch.setattr(sys, "argv", ["seenby.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        seenby.main()
    assert exc.value.code == 0
    helps, order, parts = {}, [], None
    for line in capsys.readouterr().out.splitlines():
        if line.startswith("  -"):
            invocation, _, first = line.strip().partition("  ")
            parts = [first]
            for name in [each.split()[0] for each in invocation.split(", ")]:
                helps[name] = parts
                order.append(name)
        elif parts is not None and line.startswith("   "):
            parts.append(line)
        else:
            parts = None
    return {name: " ".join(" ".join(p).split()) for name, p in helps.items()}, order


@pytest.mark.spec("CLI-28")
@pytest.mark.parametrize(
    "option, needles",
    [
        ("--threshold", ["default: 12.0"]),
        ("--max-gap", ["seconds", "default: 3.0"]),
        ("--block-k", ["default: 5.0", "0 disables"]),
        ("--sample-fps", ["default: 2.0"]),
    ],
    ids=["threshold", "max-gap", "block-k", "sample-fps"],
)
def test_cli_28_help_of_a_legacy_only_option_starts_legacy_selector_only_after_selector(
    monkeypatch, capsys, option, needles
):
    helps, order = help_entries(monkeypatch, capsys)
    assert option in helps and "--selector" in helps
    assert helps[option].startswith("legacy selector only: ")
    for needle in needles:
        assert needle in helps[option]
    assert order.index("--selector") < order.index(option)


@pytest.mark.spec("CLI-28")
def test_cli_28_sample_fps_help_is_the_rule_text(monkeypatch, capsys):
    helps, _ = help_entries(monkeypatch, capsys)
    assert helps.get("--sample-fps") == "legacy selector only: thumbnails per second analysed (default: 2.0)"


# ---------------------------------------------------------------- Step 14: frame number and time above every tile

BAND_H = 22

GLYPHS = {
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111",
    "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00010 01100",
    "#": "01010 01010 11111 01010 11111 01010 01010",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    "s": "00000 00000 01110 10000 01110 00001 11110",
    " ": "00000 00000 00000 00000 00000 00000 00000",
}
GLYPH_IDS = [{"#": "hash", ".": "dot", " ": "space"}.get(char, char) for char in GLYPHS]


def band_header(width):
    return b"P5\n%d 22\n255\n" % width


def reference_band(text, width):
    """LBL-1 from the glyph table: each 1 of the i-th character's glyph (row r, column c) is the 2x2 bytes at
    x 4 + 12 * i + 2 * c, y 4 + 2 * r set to 0, bytes at x >= width left out; a character without a glyph draws nothing.
    Row 21 is all 0."""
    pixels = bytearray([255]) * ((BAND_H - 1) * width) + bytearray(width)
    for i, char in enumerate(text):
        for r, bits in enumerate(GLYPHS.get(char, "").split()):
            for c, bit in enumerate(bits):
                if bit != "1":
                    continue
                for y in (4 + 2 * r, 5 + 2 * r):
                    for x in (4 + 12 * i + 2 * c, 5 + 12 * i + 2 * c):
                        if x < width:
                            pixels[y * width + x] = 0
    return band_header(width) + bytes(pixels)


def band_pixels(band, width):
    header = band_header(width)
    assert band[: len(header)] == header
    return band[len(header):]


# -------- LBL-1 (label_band)


@pytest.mark.spec("LBL-1")
@pytest.mark.spec("LBL-3")
def test_lbl_1_3_band_is_22_px_high():
    assert seenby.LABEL_H == 22


@pytest.mark.spec("LBL-1")
def test_lbl_1_hash_1_at_width_30():
    band = seenby.label_band("#1", 30)
    assert isinstance(band, bytes)
    assert len(band) == 673
    assert band[:13] == b"P5\n30 22\n255\n"
    pixels = band[13:]
    assert len(pixels) == 660
    assert pixels.count(0) == 150
    assert pixels.count(255) == 510
    assert pixels[21 * 30:] == bytes(30)
    assert pixels[4 * 30 + 6] == 0
    assert pixels[4 * 30 + 4] == 255
    assert pixels[4 * 30 + 20] == 0
    assert band == reference_band("#1", 30)


@pytest.mark.spec("LBL-1")
def test_lbl_1_bytes_at_or_past_the_width_are_not_drawn():
    band = seenby.label_band("88", 10)
    assert band[:13] == b"P5\n10 22\n255\n"
    pixels = band[13:]
    assert len(pixels) == 220
    assert pixels[:210].count(0) == 40
    assert pixels[:210].count(255) == 170
    assert {i % 10 for i, value in enumerate(pixels[:210]) if value == 0} == set(range(4, 10))
    assert pixels[210:] == bytes(10)
    assert band == reference_band("88", 10)


@pytest.mark.spec("LBL-1")
@pytest.mark.parametrize("text, width, count", [("", 8, 168), ("?!", 40, 840)], ids=["empty", "no-glyphs"])
def test_lbl_1_text_without_glyphs_draws_nothing(text, width, count):
    pixels = band_pixels(seenby.label_band(text, width), width)
    assert len(pixels) == 22 * width
    assert pixels[:count] == bytes([255]) * count
    assert pixels[count:] == bytes(width)


@pytest.mark.spec("LBL-1")
def test_lbl_1_a_frame_label_stays_within_its_ten_characters_and_rows_4_to_17():
    band = seenby.label_band("#07 12.25s", 256)
    pixels = band_pixels(band, 256)
    assert len(pixels) == 22 * 256
    rows = [pixels[y * 256:(y + 1) * 256] for y in range(22)]
    assert all(0 not in row[124:] for row in rows[:21])
    assert all(0 not in rows[y] for y in [0, 1, 2, 3, 18, 19, 20])
    assert rows[21] == bytes(256)
    assert pixels.count(0) == 4 * sum(GLYPHS[char].count("1") for char in "#07 12.25s") + 256
    assert band == reference_band("#07 12.25s", 256)


@pytest.mark.spec("LBL-1")
@pytest.mark.parametrize("char", list(GLYPHS), ids=GLYPH_IDS)
def test_lbl_1_every_glyph_of_the_table(char):
    assert seenby.label_band(char, 16) == reference_band(char, 16)


@pytest.mark.spec("LBL-1")
@pytest.mark.parametrize(
    "text, width",
    [
        ("#01 0.00s", 160),
        ("#24 31.50s", 776),
        ("#07 12.25s", 124),
        ("0123456789#. s", 200),
        ("0123456789#. s", 101),
        ("?#", 30),
        ("S5", 30),
        ("#1", 5),
    ],
    ids=[
        "first-frame", "last-frame-at-776", "ends-at-the-width", "whole-table", "cut-inside-a-glyph-column",
        "no-glyph-keeps-its-12-px", "upper-case-has-no-glyph", "one-byte-column",
    ],
)
def test_lbl_1_more_labels_match_the_glyph_table(text, width):
    assert seenby.label_band(text, width) == reference_band(text, width)


# -------- LBL-2 (contact_sheets with the bands; amends FF-4)


@pytest.mark.spec("LBL-2")
def test_lbl_2_no_frames_give_no_sheets(tmp_path):
    assert seenby.contact_sheets([], str(tmp_path), 3, 2) == []


@pytest.mark.spec("LBL-2")
@pytest.mark.spec("CLI-12")
@pytest.mark.parametrize(
    "argv, kwargs",
    [
        (["clip.mp4", "out"], dict(thumbs=static(30))),
        (EVENTS_ARGV, dict(thumbs=static(4), probe=EVENTS_PROBE, samples=events_two())),
    ],
    ids=["legacy", "events"],
)
def test_lbl_2_contact_sheets_value_error_is_reported_with_the_video_name(monkeypatch, capsys, tmp_path, argv, kwargs):
    error = ValueError("ffprobe could not read the frame width of out/frame-01.jpg")
    run = run_main(monkeypatch, capsys, tmp_path, argv, sheets=error, **kwargs)
    assert run.rc == 1
    assert len(run.contact_sheets_calls) == 1
    assert run.err.splitlines() == ["clip.mp4: ffprobe could not read the frame width of out/frame-01.jpg"]
    assert not (tmp_path / "out" / "frames.json").exists()


# -------- LBL-3 (layout rows with the band; amends LAY-3)


@pytest.mark.spec("LBL-3")
@pytest.mark.parametrize(
    "args, kwargs, expected",
    [
        ((2120, 422, 24), {}, ("wide", 776, 2, 8, 2)),
        ((814, 872, 24), {}, ("window", 516, 3, 2, 4)),
        ((800, 600, 30), {"rows": 5}, ("window", 516, 3, 5, 2)),
        ((526, 514, 3), {}, ("window", 516, 3, 2, 1)),
        ((2560, 1228, 8), {}, ("wide", 776, 2, 3, 2)),
        ((500, 500, 6), {}, ("window", 500, 3, 2, 1)),
        ((1032, 1033, 6), {}, ("window", 516, 3, 2, 1)),
    ],
    ids=[
        "wide-9-to-8-rows", "window-unchanged", "rows-given-as-is", "lay-row-526x514", "lay-row-2560x1228",
        "lay-row-500x500", "1032x1033-3-to-2-rows",
    ],
)
def test_lbl_3_rows_leave_room_for_the_band(args, kwargs, expected):
    assert seenby.layout(*args, **kwargs) == expected


@pytest.mark.spec("LBL-3")
@pytest.mark.spec("LAY-P1")
@settings(deadline=None)
@given(
    width=st.integers(min_value=16, max_value=4000),
    height=st.integers(min_value=16, max_value=4000),
    n_frames=st.integers(min_value=1, max_value=60),
    sheet_width=st.integers(min_value=64, max_value=4000),
    rows=st.none() | st.integers(min_value=1, max_value=8),
    tile_width=st.none() | st.integers(min_value=16, max_value=2000),
)
def test_lbl_3_rows_are_the_most_whose_sheet_with_bands_fits(width, height, n_frames, sheet_width, rows, tile_width):
    grade, tile, cols, got_rows, sheets = seenby.layout(width, height, n_frames, sheet_width, rows, tile_width)
    if rows is not None:
        assert got_rows == rows
        return
    tile_h = round(tile * height / width)
    step = tile_h + BAND_H + seenby.PADDING
    assert got_rows == max(1, (sheet_width - 2 * seenby.MARGIN + seenby.PADDING) // step)
    assert got_rows == 1 or got_rows * step - seenby.PADDING + 2 * seenby.MARGIN <= sheet_width


@pytest.mark.spec("LBL-3")
@pytest.mark.spec("MAN-12")
def test_lbl_3_events_run_at_160x80_has_14_rows_per_sheet(monkeypatch, capsys, tmp_path):
    run = run_events(monkeypatch, capsys, tmp_path, [], events_two())
    assert run.rc == 0
    assert run.out.splitlines()[3] == "  layout: wide, tile 160 px, 2x14 per sheet"
    assert run.contact_sheets_calls[0][1:] == ("out", 2, 14)
    assert manifest()["sheet"] == {"cols": 2, "rows": 14, "tile_width": 160, "sheet_width": 1568, "count": 1}


@pytest.mark.spec("LBL-3")
@pytest.mark.spec("MAN-12")
def test_lbl_3_portrait_80x160_has_8_rows_per_sheet(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(30), probe=(15.0, 80, 160))
    assert run.rc == 0
    assert run.out.splitlines()[3] == "  layout: phone, tile 80 px, 6x8 per sheet"
    assert run.save_frames_calls[0][3] == 80
    assert run.contact_sheets_calls[0][1:] == ("out", 6, 8)
    assert manifest()["sheet"] == {"cols": 6, "rows": 8, "tile_width": 80, "sheet_width": 1568, "count": 1}


@pytest.mark.spec("LBL-3")
@pytest.mark.spec("MAN-7")
@pytest.mark.spec("MAN-12")
def test_lbl_3_man_7_12_square_frames_spread_over_sheets_of_six(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(61), probe=(30.0, 500, 500),
        sheets=["out/sheet-01.jpg", "out/sheet-02.jpg"],
    )
    assert run.rc == 0
    assert run.contact_sheets_calls[0][2:] == (3, 2)
    data = manifest()
    assert [f["time"] for f in data["frames"]] == [float(t) for t in range(0, 31, 3)]
    assert [f["sheet"] for f in data["frames"]] == [1] * 6 + [2] * 5
    assert data["sheets"] == [
        {"file": "sheet-01.jpg", "frames": [1, 6]},
        {"file": "sheet-02.jpg", "frames": [7, 11]},
    ]
    assert data["sheet"] == {"cols": 3, "rows": 2, "tile_width": 500, "sheet_width": 1568, "count": 2}


# ---------------------------------------------------------------- Step 15: a box around each change on the sheets

# BOX_GAP + BOX_T, BOX_NEAR, BOX_SHARE and BOX_MAX of the spec, pinned by test_box_1_constants_have_the_spec_values.
BOX_PAD, BOX_NEAR_PX, BOX_SHARE_OF_TILE, BOX_MOST = 2 + 3, 6, 0.5, 12


def box_rect(region, native_width, width):
    """BOX-1 step 1: `(x0, y0, x1, y1)` of a region on the tile, `x1` and `y1` exclusive."""
    x, y, w, h = region
    return (
        x * width // native_width - BOX_PAD,
        y * width // native_width - BOX_PAD,
        -(-(x + w) * width // native_width) + BOX_PAD,
        -(-(y + h) * width // native_width) + BOX_PAD,
    )


def rects_near(a, b):
    """BOX-1 step 2."""
    return (
        a[0] - BOX_NEAR_PX < b[2] and b[0] - BOX_NEAR_PX < a[2]
        and a[1] - BOX_NEAR_PX < b[3] and b[1] - BOX_NEAR_PX < a[3]
    )


def part_on_tile(rect, width, height):
    """BOX-1 step 3."""
    x0, y0, x1, y1 = rect
    return (max(0, x0), max(0, y0), min(width, x1), min(height, y1))


def part_area(rect, width, height):
    x0, y0, x1, y1 = part_on_tile(rect, width, height)
    return max(0, x1 - x0) * max(0, y1 - y0)


def boxes_as_written(regions, native_width, width, height):
    """The five steps of BOX-1, one at a time: the share test on the part on the tile, the box not cut."""
    rects = [box_rect(region, native_width, width) for region in regions]
    joined = True
    while joined:
        joined = False
        for i, j in combinations(range(len(rects)), 2):
            a, b = rects[i], rects[j]
            if rects_near(a, b):
                rects[i] = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
                del rects[j]
                joined = True
                break
    rects = [r for r in rects if part_area(r, width, height) <= BOX_SHARE_OF_TILE * width * height]
    if len(rects) > BOX_MOST:
        return []
    return sorted(((x0, y0, x1 - x0, y1 - y0) for x0, y0, x1, y1 in rects), key=lambda b: (b[1], b[0]))


def box_p1_region():
    return st.tuples(st.integers(min_value=8, max_value=80), st.integers(min_value=8, max_value=80)).flatmap(
        lambda wh: st.tuples(
            st.integers(min_value=0, max_value=1552 - wh[0]), st.integers(min_value=0, max_value=800 - wh[1])
        ).map(lambda xy: [xy[0], xy[1], wh[0], wh[1]])
    )


box_p1_regions_st = st.lists(box_p1_region(), min_size=0, max_size=6)


# -------- BOX-1 (change_boxes)


@pytest.mark.spec("BOX-1")
@pytest.mark.parametrize(
    "name, value",
    [("BOX_T", 3), ("BOX_GAP", 2), ("BOX_NEAR", 6), ("BOX_SHARE", 0.5), ("BOX_MAX", 12)],
)
def test_box_1_constants_have_the_spec_values(name, value):
    assert getattr(seenby, name) == value


@pytest.mark.spec("BOX-1")
@pytest.mark.parametrize(
    "regions, native_width, width, height, expected",
    [
        ([], 160, 160, 80, []),
        ([[16, 16, 24, 24], [96, 16, 24, 24]], 160, 160, 80, [(11, 11, 34, 34), (91, 11, 34, 34)]),
        ([[96, 16, 24, 24], [16, 16, 24, 24]], 160, 160, 80, [(11, 11, 34, 34), (91, 11, 34, 34)]),
        ([[1384, 88, 16, 16]], 2120, 776, 154, [(501, 27, 17, 17)]),
        ([[1384, 88, 16, 16], [1480, 88, 56, 16]], 2120, 776, 154, [(501, 27, 17, 17), (536, 27, 32, 17)]),
        ([[16, 16, 24, 24], [55, 16, 24, 24]], 160, 160, 80, [(11, 11, 73, 34)]),
        ([[16, 16, 24, 24], [56, 16, 24, 24]], 160, 160, 80, [(11, 11, 34, 34), (51, 11, 34, 34)]),
        ([[72, 24, 8, 8], [40, 40, 8, 8], [56, 56, 8, 8]], 160, 160, 80, [(35, 19, 50, 50)]),
        ([[72, 24, 8, 8], [40, 40, 8, 8]], 160, 160, 80, [(67, 19, 18, 18), (35, 35, 18, 18)]),
        ([[0, 0, 24, 24]], 160, 160, 80, [(-5, -5, 34, 34)]),
        ([[0, 0, 160, 80]], 160, 160, 80, []),
        ([[5, 5, 40, 90]], 100, 100, 100, [(0, 0, 50, 100)]),
        ([[5, 5, 41, 90]], 100, 100, 100, []),
        ([[0, 0, 45, 90]], 100, 100, 100, [(-5, -5, 55, 100)]),
        ([[0, 0, 46, 95]], 100, 100, 100, []),
        ([[24 * i, 0, 8, 8] for i in range(13)], 400, 400, 100, []),
    ],
    ids=[
        "no-regions", "two-apart", "two-apart-swapped", "checkbox-on-a-2120-px-strip", "two-checkboxes-18-px-apart",
        "5-px-apart-joined", "6-px-apart-not-joined", "joined-then-near-the-union", "two-not-near",
        "not-cut-at-the-tile-edge", "the-whole-tile", "exactly-half-the-tile-kept", "over-half-the-tile-dropped",
        "corner-part-on-the-tile-under-half-kept", "corner-part-on-the-tile-over-half-dropped", "thirteen-boxes-none",
    ],
)
def test_box_1_change_boxes_example_rows(regions, native_width, width, height, expected):
    assert seenby.change_boxes(regions, native_width, width, height) == expected


@pytest.mark.spec("BOX-1")
def test_box_1_twelve_boxes_are_kept():
    result = seenby.change_boxes([[24 * i, 0, 8, 8] for i in range(12)], 400, 400, 100)
    assert len(result) == 12
    assert result[:2] == [(-5, -5, 18, 18), (19, -5, 18, 18)]


@pytest.mark.spec("BOX-1")
@pytest.mark.parametrize(
    "regions",
    list(permutations([[72, 24, 8, 8], [40, 40, 8, 8], [56, 56, 8, 8]])),
    ids=[f"order-{i}" for i in range(6)],
)
def test_box_1_a_rectangle_near_only_a_joined_one_is_joined_in_every_order(regions):
    assert seenby.change_boxes(list(regions), 160, 160, 80) == [(35, 19, 50, 50)]


@pytest.mark.spec("BOX-1")
@settings(deadline=None)
@given(regions=box_p1_regions_st)
def test_box_1_change_boxes_equals_the_five_steps_as_written(regions):
    assert seenby.change_boxes(regions, 1552, 776, 400) == boxes_as_written(regions, 1552, 776, 400)


@pytest.mark.spec("BOX-P1")
@settings(deadline=None)
@given(regions=box_p1_regions_st)
def test_box_p1_boxes_are_order_free_on_the_tile_apart_sorted_and_hold_every_region(regions):
    result = seenby.change_boxes(regions, 1552, 776, 400)
    assert isinstance(result, list)
    assert all(isinstance(b, tuple) and len(b) == 4 and all(type(v) is int for v in b) for b in result)
    assert all(seenby.change_boxes(list(order), 1552, 776, 400) == result for order in permutations(regions))
    assert all(w > 0 and h > 0 and x < 776 and y < 400 and x + w > 0 and y + h > 0 for x, y, w, h in result)
    rects = [(x, y, x + w, y + h) for x, y, w, h in result]
    assert not any(rects_near(a, b) for a, b in combinations(rects, 2))
    assert result == sorted(result, key=lambda b: (b[1], b[0]))
    for region in regions:
        x0, y0, x1, y1 = box_rect(region, 1552, 776)
        assert any(bx <= x0 and by <= y0 and x1 <= bx + bw and y1 <= by + bh for bx, by, bw, bh in result)


# -------- BOX-2 (contact_sheets takes the boxes; amends LBL-2) is [hands-on] beyond its empty input


@pytest.mark.spec("BOX-2")
def test_box_2_no_frames_with_boxes_give_no_sheets(tmp_path):
    assert seenby.contact_sheets([], str(tmp_path), 3, 2, []) == []
    assert seenby.contact_sheets([], str(tmp_path), 3, 2, boxes=None) == []


# -------- BOX-3 (main() passes the boxes to contact_sheets; amends CLI-26)

TWO_BOXES = [[], [(11, 11, 34, 34), (91, 11, 34, 34)], [(11, 11, 34, 34)]]
Z, CA, CB = grid({}), grid(box(2, 2, 3, 3)), grid(box(12, 2, 3, 3))
CAB = grid(box(2, 2, 3, 3) | box(12, 2, 3, 3))
TWO_CHANGES = [None, (CAB, Z), (CA, Z)]


@pytest.mark.spec("BOX-3")
@pytest.mark.parametrize("name, value", [("BOX_SPREAD", 24), ("BOX_STRONG", 5)])
def test_box_3_constants_have_the_spec_values(name, value):
    assert getattr(seenby, name) == value


@pytest.mark.spec("BOX-3")
@pytest.mark.spec("CLI-28")
def test_box_3_each_event_is_boxed_on_the_first_frame_that_shows_it(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4),
        probe=EVENTS_PROBE, samples=events_two(), as_given=True, changes=TWO_CHANGES,
    )
    assert run.rc == 0
    assert run.kept_changes_calls == [("clip.mp4", [0, 4, 6], 160, 80, 4, 0.0, None)]
    assert len(run.contact_sheets_calls) == 1
    assert run.contact_sheets_boxes == [TWO_BOXES]
    assert run.out == (
        EVENTS_TWO_DRY_RUN_STDOUT
        + "  contact sheets: out/sheet-01.jpg\n"
        + MANIFEST_LINE.format(out_dir="out") + "\n"
    )
    data = manifest()
    assert list(data) == EVENTS_TOP_LEVEL_KEYS
    assert list(data["analysis"]) == EVENTS_ANALYSIS_KEYS
    assert all(list(frame) == EVENTS_FRAME_KEYS for frame in data["frames"])
    assert [(f["time"], f["reason"]) for f in data["frames"]] == [(0.0, "first"), (1.0, "change"), (1.5, "last")]
    assert data["events"] == [
        {"from": 0.25, "settled": 0.25, "until": 1.0, "region": [16, 16, 24, 24], "changed_px": 576, "shown": True},
        {"from": 0.75, "settled": 0.75, "until": 1.5, "region": [96, 16, 24, 24], "changed_px": 576, "shown": True},
        {"from": 1.25, "settled": 1.25, "until": 1.5, "region": [16, 16, 24, 24], "changed_px": 576, "shown": True},
    ]


@pytest.mark.spec("BOX-3")
@pytest.mark.parametrize(
    "extra, probe, changes, call, boxes",
    [
        ([], EVENTS_PROBE, None, ("clip.mp4", [0, 4, 6], 160, 80, 4, 0.0, None), [[], [], []]),
        (
            ["--max-frames", "2"], EVENTS_PROBE, [None, (CB, Z)], ("clip.mp4", [0, 6], 160, 80, 4, 0.0, None),
            [[], [(91, 11, 34, 34)]],
        ),
        (["--from", "1"], (3.0, 160, 80), TWO_CHANGES, ("clip.mp4", [0, 4, 6], 160, 80, 4, 1.0, 2.0), TWO_BOXES),
    ],
    ids=["no-entries-all-zero-no-box", "max-frames-2-only-B-changed-since-0", "from-1"],
)
def test_box_3_boxes_per_frame(monkeypatch, capsys, tmp_path, extra, probe, changes, call, boxes):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"] + extra, static(4),
        probe=probe, samples=events_two(), as_given=True, changes=changes,
    )
    assert run.rc == 0
    assert run.kept_changes_calls == [call]
    assert run.contact_sheets_boxes == [boxes]


@pytest.mark.spec("BOX-3")
@pytest.mark.parametrize(
    "changes, boxes",
    [
        ([None, (grid({(2, 2): 96}), Z), (Z, Z)], [[], [(11, 11, 34, 34)], []]),
        ([None, (grid({(2, 2): 95}), Z), (Z, Z)], [[], [], []]),
        ([None, (Z, grid({(4, 4): 20})), (Z, Z)], [[], [(11, 11, 34, 34)], []]),
        ([None, (Z, grid({(4, 4): 19})), (Z, Z)], [[], [], []]),
        ([None, (grid({(2, 2): 48, (3, 3): 48}), Z), (Z, Z)], [[], [(11, 11, 34, 34)], []]),
        ([None, (grid({(2, 2): 48, (4, 2): 48}), Z), (Z, Z)], [[], [], []]),
        ([None, (grid({(5, 2): 255, (1, 4): 255, (3, 5): 255}), Z), (Z, Z)], [[], [], []]),
    ],
    ids=[
        "over-96-is-24.09-px-in-one-block-boxed", "over-95-is-23.84-px-no-box",
        "far-20-in-the-last-cell-alone-is-5.02-px-boxed", "far-19-is-4.77-px-no-box",
        "cells-2-2-and-3-3-share-a-block-boxed", "cells-2-2-and-4-2-share-no-block-no-box",
        "cells-right-left-and-under-A-no-box",
    ],
)
def test_box_3_a_box_needs_box_spread_px_past_pixel_t_or_box_strong_px_past_twice_it_in_a_block(
    monkeypatch, capsys, tmp_path, changes, boxes
):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4),
        probe=EVENTS_PROBE, samples=events_two(), as_given=True, changes=changes,
    )
    assert run.rc == 0
    assert run.contact_sheets_boxes == [boxes]


@pytest.mark.spec("BOX-3")
@pytest.mark.parametrize(
    "changes, boxes",
    [
        ([None, (CA, Z), (Z, Z)], [[], [(11, 11, 34, 34)], []]),
        ([None, (Z, Z), (CA, Z)], [[], [], [(11, 11, 34, 34)]]),
    ],
    ids=["state-frame-at-1-shows-it-before-it-settles-at-2", "nothing-visible-at-1-so-the-last-frame"],
)
def test_box_3_an_event_goes_to_the_first_frame_from_start_on_that_shows_it(
    monkeypatch, capsys, tmp_path, changes, boxes
):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4),
        probe=EVENTS_PROBE, samples=events_dbl(), as_given=True, changes=changes,
    )
    assert run.rc == 0
    assert run.kept_changes_calls == [("clip.mp4", [0, 1, 4], 160, 80, 4, 0.0, None)]
    assert run.contact_sheets_boxes == [boxes]


@pytest.mark.spec("BOX-3")
def test_box_3_boxes_are_scaled_onto_a_tile_narrower_than_the_frame(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4),
        probe=(2.0, 1600, 80), samples=events_two(), as_given=True, changes=TWO_CHANGES,
    )
    assert run.rc == 0
    assert "  layout: wide, tile 776 px, 2x24 per sheet" in run.out.splitlines()
    assert run.contact_sheets_boxes == [[[], [(2, 2, 23, 23), (41, 2, 23, 23)], [(2, 2, 23, 23)]]]


@pytest.mark.spec("BOX-3")
def test_box_3_one_frame_calls_neither_kept_changes_nor_contact_sheets(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4),
        probe=EVENTS_PROBE, samples=[S({})], as_given=True,
    )
    assert run.rc == 0
    assert len(run.saved_samples) == 1
    assert run.kept_changes_calls == []
    assert run.contact_sheets_calls == []


@pytest.mark.spec("BOX-3")
def test_box_3_a_kept_changes_failure_is_reported_under_the_sheets_stage(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4),
        probe=EVENTS_PROBE, samples=events_two(), as_given=True,
        changes=subprocess.CalledProcessError(1, ["ffmpeg"], stderr="x\nboom\n"),
    )
    assert run.rc == 1
    assert "ffmpeg failed during sheets (exit 1): boom" in run.err
    assert "Traceback" not in run.err


@pytest.mark.spec("BOX-3")
def test_box_3_the_legacy_selector_calls_contact_sheets_with_four_arguments(monkeypatch, capsys, tmp_path):
    run = run_main(monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--selector", "legacy"], static(30))
    assert run.rc == 0
    assert run.contact_sheets_arity == [4]
    assert run.contact_sheets_boxes == [None]
    assert run.kept_changes_calls == []


# ---------------------------------------------------------------- Step 16: crops of every change at native size

# -------- CRP-1 (crop_units)


def E(x, y, w, h, start, settled):
    return {"x": x, "y": y, "w": w, "h": h, "start": start, "settled": settled}


def unit(rect, events, crop, start, settled, screen):
    return {"rect": rect, "events": events, "crop": crop, "start": start, "settled": settled, "screen": screen}


def screen_of(start, key, crops, n):
    return {"start": start, "key": key, "crops": crops, "n": n}


def a4():
    return [E(40 + 380 * i, 40, 300, 300, 2 + i, 3 + i) for i in range(4)]


def a4_units():
    return [unit([40 + 380 * i, 40, 300, 300], [i], [24 + 380 * i, 24, 332, 332], 2 + i, 3 + i, 1) for i in range(4)]


def late():
    return E(40, 440, 24, 24, 11, 12)


@pytest.mark.spec("CRP-1")
def test_crp_1_no_events_give_one_empty_screen():
    assert seenby.crop_units([], 1600, 800, 40) == ([screen_of(0, 0, [], 1)], [])


@pytest.mark.spec("CRP-1")
def test_crp_1_no_events_in_under_a_second_give_nothing():
    assert seenby.crop_units([], 1600, 800, 3) == ([], [])


@pytest.mark.spec("CRP-1")
def test_crp_1_near_changes_of_a_moment_share_a_crop_far_ones_do_not():
    events = [E(100, 100, 24, 24, 3, 4), E(200, 100, 24, 24, 4, 4), E(1000, 500, 40, 20, 4, 4)]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == [
        unit([100, 100, 124, 24], [0, 1], [84, 84, 156, 56], 3, 4, 1),
        unit([1000, 500, 40, 20], [2], [984, 484, 72, 52], 4, 4, 1),
    ]
    assert screens == [screen_of(0, 0, crops, 1)]
    assert screens[0]["crops"][0] is crops[0]
    assert screens[0]["crops"][1] is crops[1]


@pytest.mark.spec("CRP-1")
def test_crp_1_units_are_sorted_by_y_then_x():
    events = [E(1000, 500, 40, 20, 4, 4), E(100, 100, 24, 24, 3, 4)]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == [
        unit([100, 100, 24, 24], [1], [84, 84, 56, 56], 3, 4, 1),
        unit([1000, 500, 40, 20], [0], [984, 484, 72, 52], 4, 4, 1),
    ]
    assert screens == [screen_of(0, 0, crops, 1)]


@pytest.mark.spec("CRP-1")
@pytest.mark.parametrize(
    "second_x, expected",
    [
        (251, [unit([100, 100, 175, 24], [0, 1], [84, 84, 207, 56], 3, 4, 1)]),
        (
            252,
            [
                unit([100, 100, 24, 24], [0], [84, 84, 56, 56], 3, 4, 1),
                unit([252, 100, 24, 24], [1], [236, 84, 56, 56], 4, 4, 1),
            ],
        ),
    ],
    ids=["gap-127-joins", "gap-128-stays-apart"],
)
def test_crp_1_join_distance_is_under_128_px(second_x, expected):
    events = [E(100, 100, 24, 24, 3, 4), E(second_x, 100, 24, 24, 4, 4)]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == expected
    assert screens == [screen_of(0, 0, crops, 1)]


@pytest.mark.spec("CRP-1")
def test_crp_1_changes_of_different_moments_never_share_a_crop():
    events = [E(100, 100, 24, 24, 1, 2), E(130, 100, 24, 24, 3, 4)]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == [
        unit([100, 100, 24, 24], [0], [84, 84, 56, 56], 1, 2, 1),
        unit([130, 100, 24, 24], [1], [114, 84, 56, 56], 3, 4, 1),
    ]
    assert screens == [screen_of(0, 0, crops, 1)]


@pytest.mark.spec("CRP-1")
@pytest.mark.parametrize(
    "second_x, expected",
    [
        (320, [unit([0, 0, 420, 300], [0, 1], [0, 0, 436, 316], 3, 4, 1)]),
        (
            360,
            [
                unit([0, 0, 300, 300], [0], [0, 0, 316, 316], 3, 4, 1),
                unit([360, 0, 100, 100], [1], [344, 0, 132, 116], 4, 4, 1),
            ],
        ),
    ],
    ids=["126000-px-joins", "138000-px-over-the-share-stays-apart"],
)
def test_crp_1_a_joined_crop_stays_within_the_crop_share(second_x, expected):
    events = [E(0, 0, 300, 300, 3, 4), E(second_x, 0, 100, 100, 4, 4)]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == expected
    assert screens == [screen_of(0, 0, crops, 1)]


@pytest.mark.spec("CRP-1")
def test_crp_1_a_chain_joins_the_first_pair_in_list_order():
    events = [E(0, 0, 200, 200, 3, 4), E(260, 0, 200, 200, 4, 4), E(520, 0, 200, 200, 2, 4)]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == [
        unit([0, 0, 460, 200], [0, 1], [0, 0, 476, 216], 3, 4, 1),
        unit([520, 0, 200, 200], [2], [504, 0, 232, 216], 2, 4, 1),
    ]
    assert screens == [screen_of(0, 0, crops, 1)]


@pytest.mark.spec("CRP-1")
def test_crp_1_the_same_chain_in_reverse_order_joins_the_other_pair():
    events = [E(520, 0, 200, 200, 2, 4), E(260, 0, 200, 200, 4, 4), E(0, 0, 200, 200, 3, 4)]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == [
        unit([0, 0, 200, 200], [2], [0, 0, 216, 216], 3, 4, 1),
        unit([260, 0, 460, 200], [0, 1], [244, 0, 492, 216], 2, 4, 1),
    ]
    assert screens == [screen_of(0, 0, crops, 1)]


@pytest.mark.spec("CRP-1")
def test_crp_1_halo_of_70_by_70_cells_stays_one_screen_with_its_crop():
    screens, crops = seenby.crop_units([E(200, 200, 432, 432, 3, 4)], 1600, 800, 40)
    assert crops == [unit([200, 200, 432, 432], [0], [184, 184, 464, 464], 3, 4, 1)]
    assert screens == [screen_of(0, 0, crops, 1)]


@pytest.mark.spec("CRP-1")
def test_crp_1_halo_of_71_by_71_cells_starts_a_screen_and_gets_no_crop():
    screens, crops = seenby.crop_units([E(200, 200, 440, 440, 3, 4)], 1600, 800, 40)
    assert crops == []
    assert screens == [screen_of(0, 0, [], 1), screen_of(4, 4, [], 2)]


@pytest.mark.spec("CRP-1")
def test_crp_1_a_redraw_starts_a_screen_keyed_on_its_own_sample():
    events = [E(100, 100, 24, 24, 3, 4), E(0, 0, 1600, 800, 9, 10), E(700, 300, 40, 20, 19, 20)]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == [
        unit([100, 100, 24, 24], [0], [84, 84, 56, 56], 3, 4, 1),
        unit([700, 300, 40, 20], [2], [684, 284, 72, 52], 19, 20, 2),
    ]
    assert screens == [screen_of(0, 0, crops[:1], 1), screen_of(10, 10, crops[1:], 2)]


@pytest.mark.spec("CRP-1")
def test_crp_1_a_screen_of_one_sample_without_crops_is_dropped():
    events = [
        E(100, 100, 24, 24, 3, 4), E(0, 0, 1600, 800, 9, 10), E(0, 0, 1600, 800, 10, 11), E(700, 300, 40, 20, 19, 20),
    ]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == [
        unit([100, 100, 24, 24], [0], [84, 84, 56, 56], 3, 4, 1),
        unit([700, 300, 40, 20], [3], [684, 284, 72, 52], 19, 20, 2),
    ]
    assert screens == [screen_of(0, 0, crops[:1], 1), screen_of(11, 11, crops[1:], 2)]


@pytest.mark.spec("CRP-1")
def test_crp_1_a_last_screen_under_a_second_is_dropped():
    screens, crops = seenby.crop_units([E(0, 0, 1600, 800, 37, 38)], 1600, 800, 40)
    assert (screens, crops) == ([screen_of(0, 0, [], 1)], [])


@pytest.mark.spec("CRP-1")
def test_crp_1_accumulated_crops_past_the_screen_share_start_a_screen_keyed_a_sample_earlier():
    screens, crops = seenby.crop_units(a4() + [late()], 1600, 800, 40)
    late_unit = unit([40, 440, 24, 24], [4], [24, 424, 56, 56], 11, 12, 2)
    assert crops == a4_units() + [late_unit]
    assert screens == [screen_of(0, 0, crops[:4], 1), screen_of(7, 6, [crops[4]], 2)]


@pytest.mark.spec("CRP-1")
def test_crp_1_three_accumulated_crops_stay_on_the_first_screen():
    screens, crops = seenby.crop_units(a4()[:3] + [late()], 1600, 800, 40)
    assert crops == a4_units()[:3] + [unit([40, 440, 24, 24], [3], [24, 424, 56, 56], 11, 12, 1)]
    assert screens == [screen_of(0, 0, crops, 1)]


@pytest.mark.spec("CRP-1")
def test_crp_1_a_screen_made_by_accumulation_takes_the_key_of_a_redraw_right_after():
    events = a4() + [E(0, 0, 1600, 800, 6, 7), late()]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == a4_units() + [unit([40, 440, 24, 24], [5], [24, 424, 56, 56], 11, 12, 2)]
    assert screens == [screen_of(0, 0, crops[:4], 1), screen_of(7, 7, [crops[4]], 2)]


@pytest.mark.spec("CRP-1")
def test_crp_1_a_redraw_two_samples_after_accumulation_drops_the_short_screen():
    events = a4() + [E(0, 0, 1600, 800, 8, 9), late()]
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    assert crops == a4_units() + [unit([40, 440, 24, 24], [5], [24, 424, 56, 56], 11, 12, 2)]
    assert screens == [screen_of(0, 0, crops[:4], 1), screen_of(9, 9, [crops[4]], 2)]


# -------- CRP-P1 (properties of crop_units)


def crp_events():
    def build(w, h, x_frac, y_frac, settled, start_frac):
        x = x_frac % (1600 - w + 1)
        y = y_frac % (800 - h + 1)
        start = 1 + start_frac % settled
        return E(x, y, w, h, start, settled)

    event = st.builds(
        build,
        st.integers(min_value=8, max_value=400),
        st.integers(min_value=8, max_value=400),
        st.integers(min_value=0, max_value=10**6),
        st.integers(min_value=0, max_value=10**6),
        st.integers(min_value=1, max_value=39),
        st.integers(min_value=0, max_value=10**6),
    )
    return st.lists(event, min_size=0, max_size=8)


@pytest.mark.spec("CRP-P1")
@settings(deadline=None)
@given(crp_events())
def test_crp_p1_crops_and_screens_keep_their_invariants(events):
    screens, crops = seenby.crop_units(events, 1600, 800, 40)
    seen = [i for crop in crops for i in crop["events"]]
    assert len(seen) == len(set(seen))
    for crop in crops:
        members = [events[i] for i in crop["events"]]
        x0 = min(e["x"] for e in members)
        y0 = min(e["y"] for e in members)
        x1 = max(e["x"] + e["w"] for e in members)
        y1 = max(e["y"] + e["h"] for e in members)
        assert crop["rect"] == [x0, y0, x1 - x0, y1 - y0]
        assert all(e["settled"] == crop["settled"] for e in members)
        assert crop["start"] == min(e["start"] for e in members)
        if len(members) >= 2:
            assert crop["rect"][2] * crop["rect"][3] <= seenby.CROP_SHARE * 1600 * 800
        cx, cy, cw, ch = crop["crop"]
        rx, ry, rw, rh = crop["rect"]
        assert 0 <= cx and 0 <= cy and cx + cw <= 1600 and cy + ch <= 800
        assert cx <= rx and cy <= ry and rx + rw <= cx + cw and ry + rh <= cy + ch
    assert [s["n"] for s in screens] == list(range(1, len(screens) + 1))
    starts = [s["start"] for s in screens]
    assert all(a < b for a, b in zip(starts, starts[1:]))
    assert all(s["key"] in (s["start"], s["start"] - 1) for s in screens)
    ends = starts[1:] + [40]
    for s, end in zip(screens, ends):
        for crop in s["crops"]:
            assert crop["screen"] == s["n"]
            assert s["start"] <= crop["settled"] < end
            assert sum(crop is c for c in crops) == 1
    in_screens = [crop for s in screens for crop in s["crops"]]
    assert len(in_screens) == len(crops)
    assert all(a is b for a, b in zip(in_screens, crops))


# -------- CRP-2 (mark_image), CRP-3 (the glyph >)

MARK_HEADER = b"P7\nWIDTH %d\nHEIGHT %d\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n"
CLEAR, WHITE, MAGENTA = (0, 0, 0, 0), (255, 255, 255, 255), (255, 0, 255, 255)
ARROW = "10000 01000 00100 00010 00100 01000 10000"


def mark_pixels(image, width, height):
    header = MARK_HEADER % (width, height)
    assert image[: len(header)] == header
    body = image[len(header):]
    assert len(body) == 4 * width * height
    return [[tuple(body[4 * (y * width + x): 4 * (y * width + x) + 4]) for x in range(width)] for y in range(height)]


def mark_counts(rows):
    flat_pixels = [p for row in rows for p in row]
    return flat_pixels.count(CLEAR), flat_pixels.count(WHITE), flat_pixels.count(MAGENTA)


def reference_mark(width, height, marks):
    """CRP-2 from the rule text: white box, then 2x2 magenta pixels for each 1 of the glyph, later marks on top."""
    glyphs = dict(GLYPHS, **{">": ARROW})
    rows = [[CLEAR] * width for _ in range(height)]

    def put(x, y, value):
        if 0 <= x < width and 0 <= y < height:
            rows[y][x] = value

    for x0, y0, text in marks:
        for y in range(y0, y0 + 18):
            for x in range(x0, x0 + 12 * len(text) + 2):
                put(x, y, WHITE)
        for i, char in enumerate(text):
            for r, bits in enumerate(glyphs.get(char, "").split()):
                for c, bit in enumerate(bits):
                    if bit == "1":
                        for dy in (0, 1):
                            for dx in (0, 1):
                                put(x0 + 2 + 12 * i + 2 * c + dx, y0 + 2 + 2 * r + dy, MAGENTA)
    return rows


@pytest.mark.spec("CRP-2")
def test_crp_2_no_marks_give_a_transparent_image_of_193_bytes():
    image = seenby.mark_image(8, 4, [])
    assert isinstance(image, bytes)
    assert image == b"P7\nWIDTH 8\nHEIGHT 4\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n" + bytes(128)
    assert len(image) == 193


@pytest.mark.spec("CRP-2")
def test_crp_2_one_digit_on_white_in_a_30_by_20_image():
    image = seenby.mark_image(30, 20, [(1, 1, "1")])
    assert len(image) == 2467
    rows = mark_pixels(image, 30, 20)
    assert mark_counts(rows) == (348, 212, 40)
    assert [rows[3][7], rows[4][8], rows[5][7]] == [MAGENTA] * 3
    assert [rows[1][1], rows[18][14], rows[3][6]] == [WHITE] * 3
    assert [rows[1][15], rows[0][0]] == [CLEAR] * 2


@pytest.mark.spec("CRP-2")
def test_crp_2_a_mark_off_the_left_edge_is_cut_not_shifted():
    rows = mark_pixels(seenby.mark_image(10, 10, [(-3, 5, "8")]), 10, 10)
    assert mark_counts(rows) == (50, 35, 15)
    assert all(p == CLEAR for row in rows[:5] for p in row)
    assert rows[7][1:7] == [MAGENTA] * 6
    assert [rows[7][x] for x in (0, 7, 8, 9)] == [WHITE] * 4


@pytest.mark.spec("CRP-2")
def test_crp_2_a_later_mark_paints_over_an_earlier_one():
    rows = mark_pixels(seenby.mark_image(40, 20, [(0, 0, "8"), (6, 0, "1")]), 40, 20)
    assert mark_counts(rows) == (440, 292, 68)
    assert [rows[2][x] for x in (4, 5)] == [MAGENTA] * 2
    assert rows[2][6:12] == [WHITE] * 6


@pytest.mark.spec("CRP-2")
def test_crp_2_a_character_without_a_glyph_takes_its_12_px_and_draws_no_ink():
    rows = mark_pixels(seenby.mark_image(40, 20, [(0, 0, "0?")]), 40, 20)
    assert mark_counts(rows) == (332, 392, 76)


@pytest.mark.spec("CRP-2")
@pytest.mark.spec("CRP-3")
@pytest.mark.parametrize("char", list(GLYPHS) + [">"], ids=GLYPH_IDS + ["arrow"])
def test_crp_2_3_every_glyph_is_drawn_by_the_rule(char):
    assert seenby.mark_image(20, 24, [(3, 2, char)]) == MARK_HEADER % (20, 24) + b"".join(
        bytes(p) for row in reference_mark(20, 24, [(3, 2, char)]) for p in row
    )


@pytest.mark.spec("CRP-2")
@pytest.mark.parametrize(
    "width, height, marks",
    [
        (60, 30, [(5, 6, "12"), (40, 20, "3>")]),
        (30, 20, [(20, 10, "#07")]),
        (30, 20, [(-40, -4, "0000")]),
        (50, 30, [(2, 2, "88"), (10, 8, "11")]),
    ],
    ids=["two-marks", "cut-on-the-right", "cut-on-top-left", "overlap"],
)
def test_crp_2_more_placements_match_the_rule(width, height, marks):
    rows = mark_pixels(seenby.mark_image(width, height, marks), width, height)
    assert rows == reference_mark(width, height, marks)


@pytest.mark.spec("CRP-3")
def test_crp_3_label_band_draws_the_arrow_glyph():
    band = seenby.label_band(">", 20)
    assert len(band) == 453
    pixels = band_pixels(band, 20)
    assert pixels.count(0) == 48
    at = lambda x, y: pixels[y * 20 + x]
    assert [at(4, 4), at(5, 5), at(6, 6), at(10, 10), at(4, 16), at(5, 17)] == [0] * 6
    assert [at(6, 4), at(12, 10)] == [255, 255]


# -------- CRP-7 (clean also removes screens and crops)


@pytest.mark.spec("CRP-7")
def test_crp_7_removes_screens_crops_and_crops_json_only(tmp_path):
    names = [
        "screen-01-0.00s.jpg", "screen-02-12.25s.jpg", "crops-01.png", "crops-01b.png", "crops.json", "crops-01.jpg",
        "screen.jpg", "Screen-01.jpg", "crop-01-before.png", "crops.json.tmp", "frames.json",
    ]
    populate(tmp_path, names)
    seenby.clean(tmp_path)
    assert sorted(os.listdir(tmp_path)) == [
        "Screen-01.jpg", "crop-01-before.png", "crops-01.jpg", "crops.json.tmp", "screen.jpg",
    ]


# -------- CRP-6 (main() calls crop_units and write_crops, marks the tiles, names the files), CRP-8 (frames.json)

WIDE_PROBE = (2.0, 1600, 80)
TWO_TILES = {0: 1, 1: 1, 2: 2}
TWO_POINTS = [0, 4, 6]
SCREEN_FILE = "screen-01-0.00s.jpg"


def lc(files):
    return f"  crops, every change at native size before > after, numbered as on the sheets: {files}"


def ls(files):
    return (
        f"  screens, a full native frame of each screen as it starts, for reading text and digits: {files}; "
        "all listed in out/crops.json"
    )


def crop_entry(n, tile, rect, events, file):
    return {"n": n, "tile": tile, "rect": rect, "events": events, "file": file}


def result_r():
    return {
        "crops": [
            crop_entry(1, 1, [16, 16, 24, 24], [0], "crops-01.png"),
            crop_entry(2, 1, [96, 16, 24, 24], [1], "crops-01.png"),
            crop_entry(3, 2, [16, 16, 24, 24], [2], "crops-01.png"),
        ],
        "images": ["crops-01.png"],
        "screens": [{"n": 1, "start": 0, "file": SCREEN_FILE}],
        "left": 0,
    }


def result_r2():
    return {
        "crops": [
            crop_entry(1, 1, [96, 48, 24, 24], [0], "crops-01.png"),
            crop_entry(2, 1, [1590, 48, 8, 8], [1], "crops-01b.png"),
            crop_entry(3, 2, [16, 0, 24, 8], [2], "crops-02.png"),
        ],
        "images": ["crops-01.png", "crops-01b.png", "crops-02.png"],
        "screens": [{"n": 1, "start": 0, "file": SCREEN_FILE}, {"n": 2, "start": 5, "file": "screen-02-1.00s.jpg"}],
        "left": 1,
    }


def result_r3():
    return {
        "crops": [crop_entry(1, None, [16, 16, 104, 24], [0, 1], "crops-01.png")],
        "images": ["crops-01.png"],
        "screens": [{"n": 1, "start": 0, "file": SCREEN_FILE}],
        "left": 1,
    }


def result_r4():
    return {"crops": [], "images": [], "screens": [], "left": 3}


def run_crops(monkeypatch, capsys, tmp_path, crops, extra=(), probe=WIDE_PROBE, sheets=None):
    return run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"] + list(extra), static(4),
        probe=probe, samples=events_two(), changes=TWO_CHANGES, crops=crops, sheets=sheets,
    )


@pytest.mark.spec("CRP-6")
def test_crp_6_write_crops_gets_the_units_the_tiles_and_the_sample_points(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, None)
    assert run.rc == 0
    crops = [
        unit([16, 16, 24, 24], [0], [0, 0, 56, 56], 1, 1, 1),
        unit([96, 16, 24, 24], [1], [80, 0, 56, 56], 3, 3, 1),
        unit([16, 16, 24, 24], [2], [0, 0, 56, 56], 5, 5, 1),
    ]
    screens = [screen_of(0, 0, crops, 1)]
    assert run.write_crops_calls == [("clip.mp4", "out", screens, crops, TWO_TILES, TWO_POINTS, 1600, 80, 4, 0.0, None)]
    assert run.contact_sheets_arity == [5]
    assert run.contact_sheets_marks == [None]
    assert run.out.splitlines()[-1] == MANIFEST_LINE.format(out_dir="out")
    assert run.err == ""


@pytest.mark.spec("CRP-6")
def test_crp_6_a_result_puts_numbered_marks_on_the_tiles_and_names_the_files(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, result_r())
    assert run.rc == 0
    assert run.contact_sheets_arity == [6]
    assert run.contact_sheets_marks == [[[], [(2, 21, "01"), (41, 21, "02")], [(2, 21, "03")]]]
    assert run.out.splitlines()[-3:] == [
        MANIFEST_LINE.format(out_dir="out"), lc("out/crops-01.png"), ls("out/screen-01-0.00s.jpg"),
    ]
    assert run.err == ""


@pytest.mark.spec("CRP-6")
def test_crp_6_marks_sit_above_the_box_when_there_is_room_and_stay_within_the_tile(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, result_r2())
    assert run.rc == 0
    assert run.contact_sheets_marks == [[[], [(41, 0, "01"), (750, 0, "02")], [(2, 9, "03")]]]
    assert run.out.splitlines()[-2:] == [
        lc("out/crops-01.png, out/crops-01b.png, out/crops-02.png"),
        ls("out/screen-01-0.00s.jpg, out/screen-02-1.00s.jpg"),
    ]


@pytest.mark.spec("CRP-6")
@pytest.mark.parametrize(
    "result, crops_line, screens_line",
    [
        (result_r3, "out/crops-01.png", "out/screen-01-0.00s.jpg"),
        (result_r4, "none", "none"),
    ],
    ids=["no-crop-has-a-tile", "nothing-written"],
)
def test_crp_6_without_a_tile_on_any_crop_the_sheets_get_no_marks(
    monkeypatch, capsys, tmp_path, result, crops_line, screens_line
):
    run = run_crops(monkeypatch, capsys, tmp_path, result())
    assert run.rc == 0
    assert run.contact_sheets_arity == [5]
    assert run.contact_sheets_marks == [None]
    assert run.out.splitlines()[-2:] == [lc(crops_line), ls(screens_line)]


@pytest.mark.spec("CRP-6")
@pytest.mark.spec("CRP-8")
@pytest.mark.parametrize(
    "error, message",
    [
        (OSError(2, "No such file or directory"), "  crops not written: [Errno 2] No such file or directory\n"),
        (
            subprocess.CalledProcessError(1, ["ffmpeg"]),
            "  crops not written: Command '['ffmpeg']' returned non-zero exit status 1.\n",
        ),
    ],
    ids=["oserror", "called-process-error"],
)
def test_crp_6_a_failing_write_crops_is_reported_and_the_run_goes_on(monkeypatch, capsys, tmp_path, error, message):
    run = run_crops(monkeypatch, capsys, tmp_path, error)
    assert run.rc == 0
    assert run.err == message
    assert run.contact_sheets_arity == [5]
    assert run.out.splitlines()[-1] == MANIFEST_LINE.format(out_dir="out")
    data = manifest()
    assert list(data) == EVENTS_TOP_LEVEL_KEYS
    assert all(list(event) == EVENTS_EVENT_KEYS for event in data["events"])


@pytest.mark.spec("CRP-6")
def test_crp_6_a_range_gives_write_crops_its_start_and_length(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, None, extra=["--from", "1"], probe=(3.0, 1600, 80))
    assert run.rc == 0
    assert len(run.write_crops_calls) == 1
    assert run.write_crops_calls[0][4:] == (TWO_TILES, TWO_POINTS, 1600, 80, 4, 1.0, 2.0)


@pytest.mark.spec("CRP-6")
def test_crp_6_a_narrow_frame_makes_every_screen_short_and_leaves_no_units(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, None, probe=EVENTS_PROBE)
    assert run.rc == 0
    assert run.write_crops_calls == [("clip.mp4", "out", [], [], TWO_TILES, TWO_POINTS, 160, 80, 4, 0.0, None)]


@pytest.mark.spec("CRP-6")
def test_crp_6_one_frame_does_not_call_write_crops(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out"], static(4),
        probe=EVENTS_PROBE, samples=[S({})], changes=TWO_CHANGES, crops=result_r(),
    )
    assert run.rc == 0
    assert run.write_crops_calls == []


@pytest.mark.spec("CRP-6")
def test_crp_6_a_dry_run_does_not_call_write_crops(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--dry-run"], static(4),
        probe=EVENTS_PROBE, samples=events_two(), changes=TWO_CHANGES, crops=result_r(),
    )
    assert run.rc == 0
    assert run.write_crops_calls == []


@pytest.mark.spec("CRP-6")
def test_crp_6_the_legacy_selector_does_not_call_write_crops(monkeypatch, capsys, tmp_path):
    run = run_main(
        monkeypatch, capsys, tmp_path, ["clip.mp4", "out", "--selector", "legacy"], static(30), crops=result_r()
    )
    assert run.rc == 0
    assert run.write_crops_calls == []
    assert run.contact_sheets_arity == [4]


@pytest.mark.spec("CRP-6")
def test_crp_6_a_sheets_error_message_is_the_only_stderr(monkeypatch, capsys, tmp_path):
    run = run_crops(
        monkeypatch, capsys, tmp_path, None, probe=EVENTS_PROBE,
        sheets=ValueError("ffprobe could not read the frame width of out/frame-01.jpg"),
    )
    assert run.err == "clip.mp4: ffprobe could not read the frame width of out/frame-01.jpg\n"


@pytest.mark.spec("CRP-8")
def test_crp_8_without_a_result_frames_json_is_that_of_man_17(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, None)
    assert run.rc == 0
    data = manifest()
    assert list(data) == EVENTS_TOP_LEVEL_KEYS
    assert data["events"] and all(list(event) == EVENTS_EVENT_KEYS for event in data["events"])


@pytest.mark.spec("CRP-8")
def test_crp_8_a_result_adds_the_crops_key_and_a_crop_per_event(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, result_r())
    assert run.rc == 0
    data = manifest()
    assert list(data) == EVENTS_TOP_LEVEL_KEYS + ["crops"]
    assert data["crops"] == {
        "file": "crops.json", "images": ["crops-01.png"], "screens": [{"n": 1, "from": 0.0, "file": SCREEN_FILE}],
    }
    assert all(list(event) == EVENTS_EVENT_KEYS + ["crop"] for event in data["events"])
    assert [event["crop"] for event in data["events"]] == [{"n": n, "file": "crops-01.png"} for n in (1, 2, 3)]
    assert [list(event["crop"]) for event in data["events"]] == [["n", "file"]] * 3


@pytest.mark.spec("CRP-8")
def test_crp_8_crops_on_several_pages_and_screens_are_listed_in_order(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, result_r2())
    assert run.rc == 0
    data = manifest()
    assert data["crops"] == {
        "file": "crops.json",
        "images": ["crops-01.png", "crops-01b.png", "crops-02.png"],
        "screens": [
            {"n": 1, "from": 0.0, "file": SCREEN_FILE}, {"n": 2, "from": 1.25, "file": "screen-02-1.00s.jpg"},
        ],
    }
    assert [event["crop"] for event in data["events"]] == [
        {"n": 1, "file": "crops-01.png"}, {"n": 2, "file": "crops-01b.png"}, {"n": 3, "file": "crops-02.png"},
    ]


@pytest.mark.spec("CRP-8")
def test_crp_8_an_event_no_crop_holds_gets_null(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, result_r3())
    assert run.rc == 0
    data = manifest()
    assert [event["crop"] for event in data["events"]] == [
        {"n": 1, "file": "crops-01.png"}, {"n": 1, "file": "crops-01.png"}, None,
    ]
    assert data["crops"]["images"] == ["crops-01.png"]


@pytest.mark.spec("CRP-8")
def test_crp_8_an_empty_result_gives_empty_lists_and_null_crops(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, result_r4())
    assert run.rc == 0
    data = manifest()
    assert data["crops"] == {"file": "crops.json", "images": [], "screens": []}
    assert [event["crop"] for event in data["events"]] == [None, None, None]
    assert all(list(event) == EVENTS_EVENT_KEYS + ["crop"] for event in data["events"])


@pytest.mark.spec("CRP-8")
def test_crp_8_screen_times_count_from_the_start_of_the_recording(monkeypatch, capsys, tmp_path):
    run = run_crops(monkeypatch, capsys, tmp_path, result_r(), extra=["--from", "1"], probe=(3.0, 1600, 80))
    assert run.rc == 0
    assert manifest()["crops"]["screens"] == [{"n": 1, "from": 1.0, "file": SCREEN_FILE}]
