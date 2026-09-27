#!/usr/bin/env python3
"""Pick frames from a screen recording so an AI agent sees the whole video.

Why not ffmpeg's `select='gt(scene,X)'`: scene detection compares a frame with
the **previous** one. Someone recording a phone screen scrolls smoothly, so
neighbouring frames are nearly identical and no threshold ever fires. Measured
on four real customer recordings: scene detection returned **zero** frames.

The default selector counts changed pixels where they happen: ffmpeg compares
every pixel's luma with the previous sample, four per second, in 8x8 px cells.
Changes of one screen area make one event, on screen from when it settles until
that area changes again, and the kept frames are the fewest that show every
event, plus the first and the last, up to a cap. The legacy selector
(`--selector legacy`, deprecated) compares 32x32 thumbnails with the last kept
frame against a threshold, with a timer and a cap that raises the threshold.

Output: individual frames, contact sheets (each sheet a single image an agent
can read in one go, changes boxed on the first tile that shows them) and
`frames.json`, the manifest with the time and reason of every frame plus a
ready `recheck` command that extracts the native frame.
Sheets are for meaning; digits are read from the native frame. Tile width is
at least 260 px for phone footage and 780 px for desktop footage, otherwise
small UI text becomes unreadable.

  python3 seenby.py recording.mp4 [output-dir]

Requires `ffmpeg` and `ffprobe` on PATH, or `FFMPEG` / `FFPROBE` env vars.
Exit codes: 0 done, 1 could not run, 2 bad arguments.
"""

import argparse
import bisect
import functools
import json
import math
import operator
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

SAMPLE_FPS = 2       # thumbnails per second we look at (not saved)
THRESHOLD = 12.0     # mean brightness difference that counts as a new frame
MAX_GAP = 3.0        # seconds: force a frame even if nothing changed
MAX_FRAMES = 24      # an agent needs no more; sheets become unreadable
THUMB = 32           # side of the grey thumbnail the difference is computed on
BLOCK = 8            # side of the blocks the local difference is computed on
BLOCK_K = 5.0        # a block differing by more than K x threshold keeps the frame; 0 disables
SHEET_WIDTH = 1568   # vision models downscale to about this many px on the long side
MARGIN = 6           # tile filter: border around the sheet, px
PADDING = 4          # tile filter: gap between tiles, px
VERSION = 1          # frames.json contract; consumers check it
EVENT_FPS = 4        # samples per second of the events selector
CELL = 8             # side of the grid cells, native px
PIXEL_T = 24         # per-pixel luma change that counts
MIN_CELL = 8         # a cell with at least this share (of 255) of changed pixels is active
NOISE_PX = 12        # blobs with fewer changed pixels are codec noise
GLOBAL_SHARE = 0.25  # above this share of active cells the whole frame is one blob
POINTER_BOX = 64     # the pointer fits in this box, px
POINTER_DIM = 8      # px the two places of a moved pointer may differ in width or height
POINTER_PX = 0.45    # share of pixels they may differ in
REGION_MARGIN = 16   # px around an event's box that still continue it
LONG_S = 2.0         # a change longer than this gets a frame every LONG_S inside it
INNER_WEIGHT = 0.8   # weight of those frames against the change's own
GLOBAL_WEIGHT = 4.0  # added to the weight of a whole-frame change
EPISODE_S = 5.0      # changes further apart than this are separate bursts, each owed a frame
SPREAD = 0.5         # over the cap, favour frames far from those already chosen
FILL_MIN_S = 0.5     # no two frames added inside a long change closer than this
HOLD_DELTA = 6       # cell-mean levels that still count as the same look
HOLD_SHARE = 0.25    # share of an event's cells that may differ before its state counts as gone
BLINK_REPEATS = 4    # a one-cell-wide spot flipping between two looks this often, briefly, is a blinking caret
CARET_H = 64         # px, the tallest box such a spot may have
LABEL_H = 22         # px, the band above each tile of a sheet with the frame's number and time
BOX_T = 3            # px, the outline of a change box on a sheet
BOX_GAP = 2          # px between a change and the inner edge of its box
BOX_NEAR = 6         # px, boxes closer than this on both axes are joined
BOX_SHARE = 0.5      # a joined box covering more of the tile than this is dropped
BOX_MAX = 12         # a tile with more boxes than this gets none
BOX_SPREAD = 64      # px changed past PIXEL_T since the frame before that make a change visible
BOX_STRONG = 4       # px changed past twice PIXEL_T that do the same
_SAMPLES = 'fps=%g:round=up:start_time=0'
_GLYPHS = {
    '0': '01110 10001 10011 10101 11001 10001 01110', '1': '00100 01100 00100 00100 00100 00100 01110',
    '2': '01110 10001 00001 00010 00100 01000 11111', '3': '11111 00010 00100 00010 00001 10001 01110',
    '4': '00010 00110 01010 10010 11111 00010 00010', '5': '11111 10000 11110 00001 00001 10001 01110',
    '6': '00110 01000 10000 11110 10001 10001 01110', '7': '11111 00001 00010 00100 01000 01000 01000',
    '8': '01110 10001 10001 01110 10001 10001 01110', '9': '01110 10001 10001 01111 00001 00010 01100',
    '#': '01010 01010 11111 01010 11111 01010 01010', '.': '00000 00000 00000 00000 00000 01100 01100',
    's': '00000 00000 01110 10000 01110 00001 11110',
}
_ACTIVE = bytes(1 if v >= MIN_CELL else 0 for v in range(256))


def ffmpeg():
    return os.environ.get('FFMPEG', 'ffmpeg')


def ffprobe():
    return os.environ.get('FFPROBE', 'ffprobe')


def require_tools():
    """None when ffmpeg and ffprobe are runnable, otherwise the message to print."""
    for name, var, exe in (('ffmpeg', 'FFMPEG', ffmpeg()), ('ffprobe', 'FFPROBE', ffprobe())):
        if shutil.which(exe) is None:
            return '%s not found. Install ffmpeg or set %s=/path/to/%s' % (name, var, name)
    return None


def ffmpeg_version():
    out = subprocess.run([ffmpeg(), '-version'], capture_output=True, text=True, check=True).stdout
    return out.splitlines()[0] if out else ''


def passthrough(version):
    """The option that passes every frame through for ffmpeg of this `-version` line: 9.0 removed -vsync, 5.1 added
    -fps_mode."""
    m = re.match(r'ffmpeg version n?(\d+)\.(\d+)', version)
    return '-vsync' if m and (int(m.group(1)), int(m.group(2))) < (5, 1) else '-fps_mode'


def parse_probe(text):
    """(duration, width, height) from ffprobe's csv output, ValueError when any is missing."""
    width = height = 0
    duration = 0.0
    for line in text.split():
        if ',' in line:
            parts = line.split(',')
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                width, height = int(parts[0]), int(parts[1])
        else:
            try:
                duration = float(line)
            except ValueError:
                pass
    if duration <= 0 or width <= 0 or height <= 0:
        raise ValueError('could not read duration, width and height from ffprobe output')
    return duration, width, height


def probe(path):
    """Duration and orientation: the contact sheet layout depends on it."""
    out = subprocess.run(
        [ffprobe(), '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'format=duration:stream=width,height',
         '-of', 'csv=p=0', path],
        capture_output=True, text=True, check=True).stdout
    return parse_probe(out)


def thumbnails(path, sample_fps=SAMPLE_FPS, start=0.0, length=None):
    """Grey THUMB x THUMB thumbnails, sample_fps per second, as one raw stream.

    Nothing is written to disk: the difference is computed on the bytes.
    `-ss` before `-i` is exact on ffmpeg 6 and costs nothing.
    """
    size = THUMB * THUMB
    span = [] if length is None else ['-t', '%.3f' % length]
    raw = subprocess.run(
        [ffmpeg(), '-v', 'error', '-ss', '%.3f' % start] + span + ['-i', path,
         '-vf', 'fps=%g,scale=%d:%d' % (sample_fps, THUMB, THUMB),
         '-pix_fmt', 'gray', '-f', 'rawvideo', '-'],
        capture_output=True, check=True).stdout
    return [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]


@functools.lru_cache(maxsize=None)
def _difference(a, b):
    return sum(map(abs, map(operator.sub, a, b))) / len(a)


def block_max(a, b, bs=BLOCK):
    """Largest mean difference over the bs x bs blocks of two thumbnails.

    The mean over the whole thumbnail is blind to a change in one corner: a
    calendar highlight moving one row gave a mean of 8.6 while the two blocks
    it touched differed by 59 and 77. The grid is fixed, so a change smaller
    than a block or on a block boundary is under-reported, up to 4x at a
    corner. K was picked on ten recordings and the useful range is narrow:
    k=3.3 doubles the frames on one of them, k=8 changes nothing anywhere.
    """
    return _block_max(a, b, bs)


@functools.lru_cache(maxsize=None)
def _block_max(a, b, bs):
    diff = list(map(abs, map(operator.sub, a, b)))
    best = 0.0
    for by in range(0, THUMB, bs):
        for bx in range(0, THUMB, bs):
            total = sum(sum(diff[y * THUMB + bx:y * THUMB + bx + bs]) for y in range(by, by + bs))
            best = max(best, total / (bs * bs))
    return best


def select_frames(thumbs, threshold, max_gap, block_k=BLOCK_K, sample_fps=SAMPLE_FPS, quiet=()):
    """Kept thumbnails as {time, diff, block, reason}, both measured against the last kept one.

    A thumbnail after the start of a quiet stretch and up to its end is judged by
    that stretch's threshold.
    """
    frames = []
    last = None
    last_time = -1e9
    limits = None
    if quiet:
        limits = [threshold] * len(thumbs)
        for s in reversed(quiet):
            for i in range(max(0, math.floor(s['from'] * sample_fps)),
                           min(len(thumbs), math.ceil(s['to'] * sample_fps) + 1)):
                if s['from'] < i / sample_fps <= s['to']:
                    limits[i] = s['threshold']
    for i, thumb in enumerate(thumbs):
        t = i / sample_fps
        limit = limits[i] if limits else threshold
        bar = block_k * limit
        diff = 0.0 if last is None else _difference(thumb, last)
        block = None
        if last is None:
            reason = 'first'
        elif diff > limit:
            reason = 'diff'
        elif block_k > 0 and bar < 255 and (block := block_max(thumb, last)) > bar:
            reason = 'block'
        elif t - last_time >= max_gap:
            reason = 'timer'
        else:
            continue
        if block is None:
            block = 0.0 if last is None else block_max(thumb, last)
        frames.append({'time': t, 'diff': diff, 'block': block, 'reason': reason})
        last = thumb
        last_time = t

    # The last frame is always kept. In a screen recording the end is the
    # result: once the selection stopped at 28.5 s of a 31.3 s video (the gap
    # coincided exactly with the threshold and the frame was skipped), and the
    # "thank you for your order" screen with the order number, the one thing
    # the video was recorded for, never made it into the analysis.
    end = (len(thumbs) - 1) / sample_fps
    if thumbs and frames[-1]['time'] < end:
        frames.append({'time': end, 'diff': _difference(thumbs[-1], last),
                       'block': block_max(thumbs[-1], last), 'reason': 'last'})
    return frames


def select(thumbs, threshold, max_gap, block_k=BLOCK_K, sample_fps=SAMPLE_FPS):
    """Return the timestamps whose frame differs from the last kept frame."""
    return [f['time'] for f in select_frames(thumbs, threshold, max_gap, block_k, sample_fps)]


def quiet_stretches(thumbs, threshold, max_gap, max_frames, block_k=BLOCK_K, sample_fps=SAMPLE_FPS):
    """Runs of timer frames, each with a threshold of its own, as many as fit the cap.

    On a light screen a page change can move the thumbnail by 2 to 4 of 255, under
    the default threshold, and only the timer keeps frames there. A run needs at least
    3 timer frames, unless it runs from the first frame to the last.
    """
    frames = select_frames(thumbs, threshold, max_gap, block_k, sample_fps)
    index = [round(f['time'] * sample_fps) for f in frames]
    ends = [k for k, f in enumerate(frames) if f['reason'] != 'timer' or k == len(frames) - 1]
    stretches = []
    for a, b in zip(ends, ends[1:]):
        if b - a - 1 < 3 and not (a == 0 and b == len(frames) - 1):
            continue
        kept = set(index[a:b])
        largest, last = 0.0, thumbs[index[a]]
        for i in range(index[a] + 1, index[b]):
            largest = max(largest, _difference(thumbs[i], last))
            if i in kept:
                last = thumbs[i]
        if largest > 1.0:
            stretches.append({'from': frames[a]['time'], 'to': frames[b]['time'], 'timer': b - a - 1,
                              'largest': largest, 'threshold': max(1.0, math.floor(largest * 10 / 3) / 10)})
    while stretches and len(select_frames(thumbs, threshold, max_gap, block_k, sample_fps, stretches)) > max_frames:
        stretches.remove(min(stretches, key=lambda s: (s['timer'], -s['from'])))
    return stretches


def fit_to_cap(thumbs, max_frames, threshold, max_gap, block_k=BLOCK_K, sample_fps=SAMPLE_FPS):
    """Raise the threshold until the frames fit the cap. Never cut the tail.

    The gap is stretched first: forced frames alone, plus the first and the
    last one, must fit the cap, otherwise raising the threshold changes
    nothing. A brightness difference never exceeds 255, so above that only the
    forced frames remain and the result is guaranteed to fit.
    An earlier version had a `[:max_frames]` fallback here, and it cut exactly
    the last frame: on a static 120 s video with a cap of 24 the selection
    ended at 115.0 s.
    """
    first = _fit(thumbs, max_frames, max_frames, threshold, max_gap, block_k, sample_fps)
    if first[1] * BLOCK_K < 255:
        return first
    # The first fit degenerated: the threshold went past the point where the
    # block rule can fire, which happens when timer frames alone fill the cap.
    # Reserve half the cap for content, then give unused slots back to the timer.
    second = _fit(thumbs, max_frames, max(2, max_frames // 2), threshold, max_gap, block_k, sample_fps)
    return second if _content(thumbs, second, block_k, sample_fps) > _content(thumbs, first, block_k, sample_fps) else first


def _content(thumbs, fit, block_k, sample_fps):
    return sum(f['reason'] in ('diff', 'block')
               for f in select_frames(thumbs, fit[1], fit[2], block_k, sample_fps))


def _fit(thumbs, max_frames, budget, threshold, max_gap, block_k, sample_fps):
    ladder = [max_gap]
    while len(select(thumbs, 256.0, ladder[-1], 0, sample_fps)) > budget:
        ladder.append(ladder[-1] * 1.25)
    while len(select(thumbs, threshold, ladder[-1], block_k, sample_fps)) > max_frames:
        threshold *= 1.5
    while len(ladder) > 1 and len(select(thumbs, threshold, ladder[-2], block_k, sample_fps)) <= max_frames:
        ladder.pop()
    return select(thumbs, threshold, ladder[-1], block_k, sample_fps), threshold, ladder[-1]


def segments(times, start, end, length):
    """Index of the kept times by stretches of `length` seconds over [start, end]."""
    count = max(1, math.ceil((end - start) / length))
    out = []
    for n in range(1, count + 1):
        low = start + (n - 1) * length
        high = end if n == count else start + n * length
        out.append({'n': n, 'from': low, 'to': high, 'frames': [
            i for i, t in enumerate(times, 1)
            if (low <= t or n == 1) and (t < high or n == count)]})
    return out


def activity(thumbs, start, end, length, sample_fps=SAMPLE_FPS):
    """Mean difference between consecutive thumbnails, one value per segments() entry."""
    out = []
    for entry in segments([start + i / sample_fps for i in range(len(thumbs))], start, end, length):
        idx = entry['frames']
        pairs = [_difference(thumbs[a - 1], thumbs[b - 1]) for a, b in zip(idx, idx[1:])]
        out.append(round(sum(pairs) / len(pairs), 2) if pairs else 0.0)
    return out


def display_size(path, width, height):
    """(width, height) as shown: swapped when the stream carries a rotation of 90 or 270 degrees."""
    out = subprocess.run([ffprobe(), '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream_side_data=rotation:stream_tags=rotate', '-of', 'csv=p=0', path],
                         capture_output=True, text=True).stdout
    for word in out.replace(',', ' ').split():
        try:
            if abs(round(float(word))) % 180 == 90:
                return height, width
        except ValueError:
            pass
    return width, height


def change_grids(path, width, height, fps=EVENT_FPS, start=0.0, length=None):
    """Cell grids of a recording: per sample the cell means and the share of pixels changed since the previous one."""
    cw, ch = width // CELL * CELL, height // CELL * CELL
    gw, gh = cw // CELL, ch // CELL
    pool = 'scale=%d:%d:flags=area+accurate_rnd' % (gw, gh)
    graph = ("[0:v]" + _SAMPLES + ",format=pix_fmts=yuv420p|yuvj420p|yuv422p|yuvj422p|yuv444p|yuvj444p|gray,"
             "extractplanes=y,setrange=full,crop=%d:%d:0:0,split[a][b];[a]%s[m];"
             "[b]tblend=all_mode=difference,lut=c0='if(gt(val,%d),255,0)',%s[d]") % (fps, cw, ch, pool, PIXEL_T, pool)
    span = [] if length is None else ['-t', '%.3f' % length]
    keep = [passthrough(ffmpeg_version()), 'passthrough']
    # two outputs, not one vstack: the stacked pairing of means and differences shifted with the input
    with tempfile.TemporaryDirectory() as tmp:
        means, diffs = os.path.join(tmp, 'means'), os.path.join(tmp, 'diffs')
        subprocess.run([ffmpeg(), '-v', 'error', '-ss', '%.3f' % start] + span + ['-i', path, '-filter_complex', graph,
                        '-map', '[m]'] + keep + ['-pix_fmt', 'gray', '-f', 'rawvideo', means,
                        '-map', '[d]'] + keep + ['-pix_fmt', 'gray', '-f', 'rawvideo', diffs],
                       capture_output=True, check=True)
        with open(means, 'rb') as f:
            m = f.read()
        with open(diffs, 'rb') as f:
            d = f.read()
    n = gw * gh
    m, d = memoryview(m), memoryview(d)
    m = [m[i:i + n] for i in range(0, len(m) - n + 1, n)]
    d = [d[i:i + n] for i in range(0, len(d) - n + 1, n)]
    if len(d) == len(m):
        d = d[1:]
    return gw, gh, [(mean, change) for mean, change in zip(m, [bytes(n)] + d)]


def blobs(change, gw, gh, cell=CELL):
    """Changed areas of one sample in native pixels, or one blob for the whole frame when most of it changed."""
    mask = bytes(change).translate(_ACTIVE)
    active = [i for m in re.finditer(rb'\x01+', mask) for i in range(m.start(), m.end())]
    scale = cell * cell / 255.0
    if len(active) > GLOBAL_SHARE * gw * gh:
        return [{'px': sum(change) * scale, 'x': 0, 'y': 0, 'w': gw * cell, 'h': gh * cell, 'global': True}]
    left = set(active)
    out = []
    for c in active:
        if c not in left:
            continue
        left.discard(c)
        stack, cells = [c], []
        while stack:
            i = stack.pop()
            cells.append(i)
            y, x = divmod(i, gw)
            for yy in range(max(0, y - 2), min(gh, y + 3)):
                for xx in range(max(0, x - 2), min(gw, x + 3)):
                    j = yy * gw + xx
                    if j in left:
                        left.discard(j)
                        stack.append(j)
        px = sum(change[i] for i in cells) * scale
        if px < NOISE_PX:
            continue
        xs = [i % gw for i in cells]
        ys = [i // gw for i in cells]
        out.append({'px': px, 'x': min(xs) * cell, 'y': min(ys) * cell, 'w': (max(xs) - min(xs) + 1) * cell,
                    'h': (max(ys) - min(ys) + 1) * cell, 'global': False})
    return out


def pointer(bs):
    """Two alike pointer-sized blobs and nothing else: the pointer moved, the screen did not change."""
    if len(bs) != 2:
        return False
    a, b = bs
    if a['global'] or b['global'] or max(a['w'], a['h'], b['w'], b['h']) > POINTER_BOX:
        return False
    return (abs(a['w'] - b['w']) <= POINTER_DIM and abs(a['h'] - b['h']) <= POINTER_DIM
            and abs(a['px'] - b['px']) <= POINTER_PX * max(a['px'], b['px']))


def _overlaps(a, b, m):
    return (a['x'] - m < b['x'] + b['w'] and b['x'] - m < a['x'] + a['w']
            and a['y'] - m < b['y'] + b['h'] and b['y'] - m < a['y'] + a['h'])


def _inside(a, b):
    return (b['x'] <= a['x'] and a['x'] + a['w'] <= b['x'] + b['w']
            and b['y'] <= a['y'] and a['y'] + a['h'] <= b['y'] + b['h'])


def _absorb(e, o):
    x0, y0 = min(e['x'], o['x']), min(e['y'], o['y'])
    x1, y1 = max(e['x'] + e['w'], o['x'] + o['w']), max(e['y'] + e['h'], o['y'] + o['h'])
    e.update({'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0, 'px': e['px'] + o['px'],
              'global': e['global'] or o['global']})
    if 'start' in o:
        e['start'] = min(e['start'], o['start'])


def events_of(content, joined=True):
    """Changes grouped by screen area, each with the samples its final state stays on screen."""
    events, open_ = [], []
    for k in range(1, len(content)):
        open_ = [e for e in open_ if e['end'] >= (k - 1 if joined else k)]
        for c in content[k]:
            hit = [e for e in open_ if _overlaps(e, c, REGION_MARGIN)]
            if not hit:
                e = dict(c, start=k, end=k)
                open_.append(e)
                events.append(e)
                continue
            e = hit[0]
            for o in hit[1:]:
                _absorb(e, o)
                open_.remove(o)
                events.remove(o)
            _absorb(e, c)
            e['end'] = k
    last = len(content) - 1
    for e in events:
        e['settled'] = e['end']
        e['until'] = next((k - 1 for k in range(e['end'] + 1, len(content))
                           if any(_overlaps(e, c, 0) for c in content[k])), last)
        e['weight'] = math.log1p(e['px']) + (GLOBAL_WEIGHT if e['global'] else 0.0)
    return events


def pick(windows, budget, last, fps=EVENT_FPS):
    """Samples that show every window, or within the budget the weightiest spread over the recording."""
    points = []
    for a, b, _ in sorted(windows, key=lambda w: (w[1], w[0])):
        if not points or points[-1] < a:
            points.append(b)
    points = sorted(set(points) | {0, last})
    if len(points) <= budget:
        return points
    chosen = {0, last}
    covered = [a <= 0 <= b or a <= last <= b for a, b, _ in windows]

    def take(t):
        chosen.add(t)
        for i, (a, b, _) in enumerate(windows):
            if a <= t <= b:
                covered[i] = True

    # every burst of activity first: on a 20 minute concatenation the weights alone left two clips without a frame
    quiet = round(EPISODE_S * fps)
    order = sorted(range(len(windows)), key=lambda i: windows[i][0])
    groups = []
    for i in order:
        if groups and windows[i][0] - windows[groups[-1][-1]][0] <= quiet:
            groups[-1].append(i)
        else:
            groups.append([i])
    for g in sorted(groups, key=lambda g: -max(windows[i][2] for i in g)):
        if len(chosen) >= budget:
            break
        if not any(covered[i] for i in g):
            take(windows[max(g, key=lambda i: (windows[i][2], -windows[i][1]))][1])
    candidates = sorted({b for _, b, _ in windows})
    inside = {t: [] for t in candidates}
    holders = []
    for i, (a, b, _) in enumerate(windows):
        holders.append(candidates[bisect.bisect_left(candidates, a):bisect.bisect_right(candidates, b)])
        for t in holders[i]:
            inside[t].append(i)
    gain = {t: sum(windows[i][2] for i in inside[t] if not covered[i]) for t in candidates}
    while len(chosen) < budget:
        best = None
        for t in candidates:
            if t in chosen or gain[t] <= 0:
                continue
            g = gain[t] * (1 + SPREAD * math.log1p(min(abs(t - c) for c in chosen) / fps))
            if best is None or g > best[0]:
                best = (g, t)
        if best is None:
            break
        chosen.add(best[1])
        stale = set()
        for i in inside[best[1]]:
            if not covered[i]:
                covered[i] = True
                stale.update(holders[i])
        # recomputed rather than decreased: subtraction leaves a residue that flips exact ties
        for t in stale:
            gain[t] = sum(windows[i][2] for i in inside[t] if not covered[i])
    return sorted(chosen)


def fill(points, long_pairs, budget, fps=EVENT_FPS):
    """Spend what the budget has left inside long continuous changes."""
    step = round(FILL_MIN_S * fps)
    points = sorted(points)
    while len(points) < budget:
        best = None
        for a, b in zip(points, points[1:]):
            inside = [k for k in long_pairs if a < k < b]
            if b - a < 2 * step or not inside:
                continue
            if best is None or len(inside) * (b - a) > best[0]:
                best = (len(inside) * (b - a), a, b, inside)
        if best is None:
            break
        _, a, b, inside = best
        k = min(inside, key=lambda k: (abs(k - (a + b) / 2), k))
        if k - a < step or b - k < step:
            k = round((a + b) / 2)
        points = sorted(points + [k])
    return points


def _rows(e, gw, holes=()):
    x0, x1 = e['x'] // CELL, (e['x'] + e['w']) // CELL
    out = []
    for y in range(e['y'] // CELL, (e['y'] + e['h']) // CELL):
        a = x0
        for h0, h1 in sorted((h['x'] // CELL, (h['x'] + h['w']) // CELL) for h in holes
                             if h['y'] // CELL <= y < (h['y'] + h['h']) // CELL):
            if min(h0, x1) > a:
                out.append(slice(y * gw + a, y * gw + min(h0, x1)))
            a = max(a, h1)
        if a < x1:
            out.append(slice(y * gw + a, y * gw + x1))
    return out


def _differ(rows, a, b):
    """True when more than HOLD_SHARE of the cells in `rows` differ by more than HOLD_DELTA between means a and b."""
    limit = HOLD_SHARE * sum(r.stop - r.start for r in rows)
    off = 0
    for r in rows:
        if a[r] != b[r]:
            off += sum(1 for p, q in zip(a[r], b[r]) if abs(p - q) > HOLD_DELTA)
            if off > limit:
                return True
    return False


def _hold(e, samples, gw, holes=()):
    # a pale change and its undo can both sit under PIXEL_T; the cell means still show the undo
    rows = _rows(e, gw, holes)
    ref = samples[e['settled']][0]
    for j in range(e['settled'] + 1, e['until'] + 1):
        if _differ(rows, samples[j][0], ref):
            e['until'] = j - 1
            return


def _blinking(events, samples, gw, fps):
    # a text caret blinks for as long as a field has focus: a thin spot flipping between two looks, again and again
    groups = {}
    for e in events:
        groups.setdefault((e['x'], e['y'], e['w'], e['h']), []).append(e)
    out = []
    for (x, y, w, h), g in groups.items():
        if w > CELL or h > CARET_H:
            continue
        rows = _rows(g[0], gw)
        runs, run, looks = [], [], []
        for e in g:
            look = samples[e['settled']][0]
            if e['px'] >= w * h / 2:
                runs.append(run)
                run, looks = [], []
                continue
            if len(looks) == 2 and all(_differ(rows, look, v) for v in looks):
                runs.append(run)
                before = samples[e['start'] - 1][0]
                known = not all(_differ(rows, before, v) for v in looks)
                run, looks = [], []
                if known:
                    continue
            elif len(looks) == 1 and not _differ(rows, look, looks[0]):
                run, looks = [], []
            run.append(e)
            if len(looks) < 2:
                looks.append(look)
        runs.append(run)
        for run in runs:
            if sum(e['until'] - e['settled'] < fps for e in run) >= BLINK_REPEATS:
                out.append({'x': x, 'y': y, 'w': w, 'h': h, 'count': len(run), 'first': run[0]['settled'],
                            'last': run[-1]['settled'], 'blinks': run})
    return out


def _visible(e, changes, gw):
    # changed and changed back between two kept frames, or codec noise on text, leaves few and faint pixels
    over, far = changes
    scale = CELL * CELL / 255.0
    rows = _rows(e, gw)
    return (sum(sum(over[r]) for r in rows) * scale >= BOX_SPREAD
            or sum(sum(far[r]) for r in rows) * scale >= BOX_STRONG)


def select_events(samples, gw, gh, budget, fps=EVENT_FPS):
    """Frames by the events selector, each with its reason, and every change found."""
    if not samples:
        return {'frames': [], 'events': [], 'blinking': [], 'pointer_moves': 0, 'needed': 0}
    last = len(samples) - 1
    content = [[]]
    moves = 0
    for mean, change in samples[1:]:
        bs = blobs(change, gw, gh)
        moved = pointer(bs)
        moves += moved
        content.append([] if moved else bs)
    events = events_of(content)
    for e in events:
        _hold(e, samples, gw)
    blinking = _blinking(events, samples, gw, fps)
    if blinking:
        strip = {}
        for b in blinking:
            for e in b.pop('blinks'):
                for k in range(e['start'], e['end'] + 1):
                    strip.setdefault(k, []).append(e)
        for k, blinks in strip.items():
            kept = [c for c in content[k] if not any(_inside(c, e) for e in blinks)]
            if len(kept) < len(content[k]) and pointer(kept):
                moves += 1
                kept = []
            content[k] = kept
        events = events_of(content)
        for e in events:
            _hold(e, samples, gw, [b for b in blinking if b['first'] <= e['until'] and e['settled'] <= b['last']])
    windows = [(e['settled'], e['until'], e['weight']) for e in events]
    n = round(LONG_S * fps)
    long_pairs = set()
    for e in events:
        if e['end'] - e['start'] + 1 > n:
            long_pairs.update(range(e['start'], e['end'] + 1))
            windows += [(j, j, INNER_WEIGHT * e['weight']) for j in range(e['start'] + n, e['end'], n)]
    needed = len(pick(windows, len(windows) + 2, last, fps))
    points = pick(windows, budget, last, fps)
    filled = set(fill(points, sorted(long_pairs), budget, fps)) - set(points)
    points = sorted(set(points) | filled)
    states = set()
    if len(points) < budget:
        inner = [s for s in events_of(content, joined=False)
                 if not any(e['settled'] <= s['settled'] and s['until'] <= e['until'] and _overlaps(e, s, 0)
                            for e in events)]
        for s in sorted(inner, key=lambda s: (-s['weight'], s['settled'])):
            if len(points) >= budget:
                break
            if not any(s['settled'] <= t <= s['until'] for t in points):
                points = sorted(points + [s['until']])
                states.add(s['until'])
    frames = []
    for k in points:
        if k == 0:
            reason = 'first'
        elif k == last:
            reason = 'last'
        elif k in states:
            reason = 'state'
        elif k in filled:
            reason = 'fill'
        elif any(e['settled'] <= k <= e['until'] for e in events):
            reason = 'change'
        else:
            reason = 'during'
        frames.append((k, reason))
    return {'frames': frames, 'events': events, 'blinking': blinking, 'pointer_moves': moves, 'needed': needed}


def layout(width, height, n_frames, sheet_width=SHEET_WIDTH, rows=None, tile_width=None):
    """(grade, tile, cols, rows, sheets) so that no sheet side exceeds sheet_width.

    Three grades by aspect ratio: phone screens tolerate narrow tiles, a
    desktop window needs about 516 px for UI text, a wide desktop two columns
    of 776 px. The boundaries and tiles come from ten real recordings. The
    tile is derived from the grade's nominal columns before the column count
    is cut to the number of frames: the `tile` filter pads missing cells with
    black at full width, so 3 frames at 6 columns would give a 1568 px sheet
    with three black cells instead of a 788 px one.
    """
    ratio = width / height
    if ratio < 0.75:
        grade, cols = 'phone', 6
    elif ratio <= 1.6:
        grade, cols = 'window', 3
    else:
        grade, cols = 'wide', 2
    if tile_width is None:
        tile = (sheet_width - 2 * MARGIN - (cols - 1) * PADDING) // cols
    else:
        tile = tile_width
        cols = max(1, (sheet_width - 2 * MARGIN + PADDING) // (tile + PADDING))
    tile = min(tile, width)
    tile_h = round(tile * height / width)
    if rows is None:
        rows = max(1, (sheet_width - 2 * MARGIN + PADDING) // (tile_h + LABEL_H + PADDING))
    cols = min(cols, n_frames)
    return grade, tile, cols, rows, math.ceil(n_frames / (cols * rows))


def clean(out_dir):
    """Remove our own files from a previous run, leave everything else alone.

    Sheets are built from the `frame-%02d.jpg` sequence in the directory, not
    from a list of paths. If the previous run left more frames than this one
    produced, ffmpeg silently filled the grid with them and the agent read
    pieces of the previous video as this one.
    """
    for name in os.listdir(out_dir):
        ours = (name.startswith('frame-') or name.startswith('sheet')) and name.endswith('.jpg')
        if ours or name in ('frames.json', 'report.md'):
            os.remove(os.path.join(out_dir, name))


def check_out_dir(out_dir, force):
    """None when the directory is ours to clean, otherwise the refusal to print."""
    if force or not os.path.isdir(out_dir):
        return None
    names = os.listdir(out_dir)
    if 'frames.json' not in names and any(n.startswith('frame-') and n.endswith('.jpg') for n in names):
        return '%s already holds frame-*.jpg from something else; pass --force to overwrite' % out_dir
    return None


def write_json(path, data):
    tmp = str(path) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    os.replace(tmp, path)


def save_frames(path, times, out_dir, tile_width):
    os.makedirs(out_dir, exist_ok=True)
    clean(out_dir)
    paths = []
    for n, t in enumerate(times, 1):
        frame = os.path.join(out_dir, 'frame-%02d-%.1fs.jpg' % (n, t))
        subprocess.run([ffmpeg(), '-v', 'error', '-y', '-ss', '%.3f' % t, '-i', path,
                        '-frames:v', '1', '-q:v', '2', '-vf', 'scale=%d:-1' % tile_width, frame],
                       check=True)
        paths.append(frame)
    return paths


def save_samples(path, indices, times, out_dir, tile_width, fps=EVENT_FPS, start=0.0, length=None):
    """Frames of the given sample indices at tile width, the same frames change_grids analysed."""
    os.makedirs(out_dir, exist_ok=True)
    clean(out_dir)
    span = [] if length is None else ['-t', '%.3f' % length]
    select = '+'.join('eq(n\\,%d)' % k for k in indices)
    paths = []
    # one pass through the same fps chain as change_grids: -ss <time> per frame gave another frame for 65 of 325
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        subprocess.run([ffmpeg(), '-v', 'error', '-ss', '%.3f' % start] + span + ['-i', path,
                        '-vf', (_SAMPLES + ",select='%s',scale=%d:-1") % (fps, select, tile_width),
                        passthrough(ffmpeg_version()), 'passthrough', '-q:v', '2', os.path.join(tmp, '%03d.jpg')],
                       capture_output=True, check=True)
        got = len([f for f in os.listdir(tmp) if f.endswith('.jpg')])
        if got < len(times):
            raise ValueError('ffmpeg wrote %d of %d frames' % (got, len(times)))
        for n, t in enumerate(times, 1):
            frame = os.path.join(out_dir, 'frame-%02d-%.2fs.jpg' % (n, t))
            os.replace(os.path.join(tmp, '%03d.jpg' % n), frame)
            paths.append(frame)
    return paths


def kept_changes(path, indices, width, height, fps=EVENT_FPS, start=0.0, length=None):
    """Per kept sample, the cells' shares of pixels changed past PIXEL_T and past twice that since the one before."""
    cw, ch = width // CELL * CELL, height // CELL * CELL
    gw, gh = cw // CELL, ch // CELL
    pool = 'scale=%d:%d:flags=area+accurate_rnd' % (gw, gh)
    select = '+'.join('eq(n\\,%d)' % k for k in indices)
    graph = ("[0:v]" + _SAMPLES + ",select='%s',format=pix_fmts=yuv420p|yuvj420p|yuv422p|yuvj422p|yuv444p|yuvj444p|"
             "gray,extractplanes=y,setrange=full,crop=%d:%d:0:0,tblend=all_mode=difference,split[a][b];"
             "[a]lut=c0='if(gt(val,%d),255,0)',%s[o];[b]lut=c0='if(gt(val,%d),255,0)',%s[f]"
             ) % (fps, select, cw, ch, PIXEL_T, pool, 2 * PIXEL_T, pool)
    span = [] if length is None else ['-t', '%.3f' % length]
    keep = [passthrough(ffmpeg_version()), 'passthrough']
    with tempfile.TemporaryDirectory() as tmp:
        over, far = os.path.join(tmp, 'over'), os.path.join(tmp, 'far')
        subprocess.run([ffmpeg(), '-v', 'error', '-ss', '%.3f' % start] + span + ['-i', path, '-filter_complex', graph,
                        '-map', '[o]'] + keep + ['-pix_fmt', 'gray', '-f', 'rawvideo', over,
                        '-map', '[f]'] + keep + ['-pix_fmt', 'gray', '-f', 'rawvideo', far],
                       capture_output=True, check=True)
        with open(over, 'rb') as f:
            o = f.read()
        with open(far, 'rb') as f:
            g = f.read()
    n = gw * gh
    pairs = [(o[i:i + n], g[i:i + n]) for i in range(0, min(len(o), len(g)) - n + 1, n)]
    return [None] + pairs[len(pairs) - len(indices) + 1:]


def label_band(text, width):
    """A white band LABEL_H px high and `width` wide with `text` in a 5x7 font at double size, as PGM bytes."""
    band = [bytearray(b'\xff') * width for _ in range(LABEL_H - 1)] + [bytearray(width)]
    for i, ch in enumerate(text):
        for r, bits in enumerate(_GLYPHS.get(ch, '').split()):
            for c, bit in enumerate(bits):
                if bit == '1':
                    for y in (4 + 2 * r, 5 + 2 * r):
                        for x in (4 + 12 * i + 2 * c, 5 + 12 * i + 2 * c):
                            if x < width:
                                band[y][x] = 0
    return b'P5\n%d %d\n255\n' % (width, LABEL_H) + b''.join(band)


def change_boxes(regions, native_width, width, height):
    """Boxes to draw around `regions` on a tile: scaled, padded, joined when close, dropped when they cover the tile."""
    pad = BOX_GAP + BOX_T
    boxes = [[x * width // native_width - pad, y * width // native_width - pad,
              -(-(x + w) * width // native_width) + pad, -(-(y + h) * width // native_width) + pad]
             for x, y, w, h in regions]
    joined = True
    while joined:
        joined = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if (a[0] - BOX_NEAR < b[2] and b[0] - BOX_NEAR < a[2]
                        and a[1] - BOX_NEAR < b[3] and b[1] - BOX_NEAR < a[3]):
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    del boxes[j]
                    joined = True
                    break
            if joined:
                break
    out = []
    for x0, y0, x1, y1 in boxes:
        if (min(width, x1) - max(0, x0)) * (min(height, y1) - max(0, y0)) <= BOX_SHARE * width * height:
            out.append((x0, y0, x1 - x0, y1 - y0))
    return [] if len(out) > BOX_MAX else sorted(out, key=lambda b: (b[1], b[0]))


def contact_sheets(paths, out_dir, cols, rows, boxes=None):
    """Tile frames into `cols x rows` images, each frame under a band with its number and time, its `boxes` drawn on it.

    Several sheets rather than one big one: vision models downscale an image
    to roughly 1568 px on the long side. One landscape sheet of 24 frames in
    two columns would be 1580 x 5300 px, and after downscaling a 780 px tile
    turns into 230 px, unreadable. Three landscape rows fit without shrinking.
    """
    if not paths:
        return []
    probed = subprocess.run([ffprobe(), '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                             'stream=width,pix_fmt', '-of', 'csv=p=0', paths[0]],
                            capture_output=True, text=True, check=True).stdout.strip().split(',')
    if len(probed) != 2 or not probed[0].isdigit():
        raise ValueError('ffprobe could not read the frame width of %s' % paths[0])
    width, fmt = int(probed[0]), probed[1]
    per_sheet = cols * rows
    sheets = []
    for n, start in enumerate(range(0, len(paths), per_sheet), 1):
        batch = paths[start:start + per_sheet]
        sheet = os.path.join(out_dir, 'sheet-%02d.jpg' % n)
        # The `tile` filter needs a single input stream; separate `-i` inputs
        # silently collapse into one frame, so the batch goes in as a concat list.
        with tempfile.TemporaryDirectory() as tmp:
            frames, bands = os.path.join(tmp, 'frames.txt'), os.path.join(tmp, 'bands.txt')
            with open(frames, 'w') as f, open(bands, 'w') as b:
                for i, path in enumerate(batch):
                    name = os.path.basename(path)[len('frame-'):-len('.jpg')]
                    band = os.path.join(tmp, 'band-%02d.pgm' % i)
                    with open(band, 'wb') as g:
                        g.write(label_band('#' + name.replace('-', ' ', 1), width))
                    f.write("file '%s'\n" % os.path.abspath(path).replace("'", "'\\''"))
                    b.write("file '%s'\n" % band.replace("'", "'\\''"))
            here = min(cols, len(batch))
            draw = ''.join(",drawbox=x=%d:y=%d:w=%d:h=%d:color=0xff00ff:t=%d:enable='eq(n,%d)'" % (x, y, w, h, BOX_T, i)
                           for i, frame in enumerate((boxes or [])[start:start + per_sheet]) for x, y, w, h in frame)
            if len(draw) > 30000:
                # the command line of Windows holds 32767 characters
                draw = ''
            # concat gives the band images broken timestamps and vstack pairs by timestamp, so both are renumbered
            graph = ('[0:v]setpts=N,format=%s%s[f];[1:v]setpts=N,format=%s[b];[b][f]vstack=shortest=1,'
                     'tile=%dx%d:margin=%d:padding=%d'
                     % (fmt, draw, fmt, here, math.ceil(len(batch) / here), MARGIN, PADDING))
            subprocess.run([ffmpeg(), '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', frames,
                            '-f', 'concat', '-safe', '0', '-i', bands, '-filter_complex', graph,
                            '-frames:v', '1', sheet], check=True)
        sheets.append(sheet)
    return sheets


def _run_events(args, out_dir, start, end, ranged, duration, width, height):
    """main() for --selector events, after the probe and the range checks."""
    def fail(message):
        print(message, file=sys.stderr)
        return 1

    stage = 'grids'
    try:
        width, height = display_size(args.video, width, height)
        if width < CELL or height < CELL:
            return fail('%s: the frame (%dx%d) is smaller than %dx%d px; use --selector legacy'
                        % (args.video, width, height, CELL, CELL))
        length = end - start if ranged else None
        span = [] if length is None else ['-t', '%.3f' % length]
        gw, gh, samples = change_grids(args.video, width, height, EVENT_FPS, start, length)
        if not samples:
            return fail('could not decode the video: no frames')
        picked = select_events(samples, gw, gh, args.max_frames)
        events = picked['events']
        points = [k for k, _ in picked['frames']]
        frames = [{'time': start + k / EVENT_FPS, 'reason': reason} for k, reason in picked['frames']]
        times = [f['time'] for f in frames]
        shown = [any(e['settled'] <= k <= e['until'] for k in points) for e in events]
        portrait = height > width
        grade, tile_width, cols, rows, _ = layout(width, height, len(times), args.sheet_width, args.rows,
                                                  args.tile_width)

        print('%s: %.1f s, %dx%d, %s' % (os.path.basename(args.video), duration, width, height,
                                         'portrait' if portrait else 'landscape'))
        if ranged:
            print('  range: %.1f-%.1f s' % (start, end))
        print('  %d samples at %d per second, %d changes, %d pointer moves, selected %d/%d'
              % (len(samples), EVENT_FPS, len(events), picked['pointer_moves'], len(times), args.max_frames))
        print('  frames: %s' % ', '.join('%.2f %s' % (f['time'], f['reason']) for f in frames))
        for b in picked['blinking']:
            print('  ignored a blinking area at %d,%d %dx%d px (%d times from %.2f to %.2f s): a text caret, '
                  'or a small mark toggled back and forth'
                  % (b['x'], b['y'], b['w'], b['h'], b['count'], start + b['first'] / EVENT_FPS,
                     start + b['last'] / EVENT_FPS))
        if not events and len(samples) > 1:
            if picked['pointer_moves']:
                print('  no change except %d pointer-like moves (the pointer, or a small mark such as a radio dot): '
                      'the first and the last frame only' % picked['pointer_moves'])
            else:
                print('  no change: the first and the last frame only')
        elif not all(shown):
            missing = sorted(start + e['settled'] / EVENT_FPS for e, s in zip(events, shown) if not s)
            runs = [[missing[0]]]
            for t in missing[1:]:
                if t - runs[-1][-1] <= 10.0:
                    runs[-1].append(t)
                else:
                    runs.append([t])
            run = max(runs, key=len)
            print('  %d of %d changes not shown within %d frames (all of them would need %d); %d of them from %.2f to '
                  '%.2f s: rerun with --from %.2f --to %.2f'
                  % (len(missing), len(events), args.max_frames, picked['needed'], len(run), run[0], run[-1],
                     max(start, run[0] - 1.0), math.floor(min(end, run[-1] + 1.0) * 100 + 1e-6) / 100))
        print('  layout: %s, tile %d px, %dx%d per sheet' % (grade, tile_width, cols, rows))
        if args.dry_run:
            return 0

        stage = 'frames'
        paths = save_samples(args.video, points, times, out_dir, tile_width, EVENT_FPS, start, length)
        stage = 'sheets'
        sheets = []
        if len(paths) > 1:
            changes = kept_changes(args.video, points, width, height, EVENT_FPS, start, length)
            regions = [[] for _ in points]
            for e in events:
                i = bisect.bisect_left(points, e['settled'])
                first = 0 < i < len(points) and points[i] <= e['until']
                if first and _visible(e, changes[i], gw):
                    regions[i].append([e['x'], e['y'], e['w'], e['h']])
            tile_height = (tile_width * height + width // 2) // width
            boxes = [change_boxes(r, width, tile_width, tile_height) for r in regions]
            sheets = contact_sheets(paths, out_dir, cols, rows, boxes)
        stage = 'version'
        version = ffmpeg_version()
    except ValueError as e:
        return fail('%s: %s' % (args.video, e))
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors='replace') if isinstance(e.stderr, bytes) else (e.stderr or '')
        lines = err.strip().splitlines()
        return fail('ffmpeg failed during %s (exit %d): %s' % (stage, e.returncode, lines[-1] if lines else ''))

    per_sheet = cols * rows
    settled = [start + e['settled'] / EVENT_FPS for e in events]
    index = segments(times, start, end, args.segment)
    for n, entry in enumerate(index):
        final = n == len(index) - 1
        entry['activity'] = sum(1 for t in settled
                                if entry['from'] <= t and (t < entry['to'] or final and t <= entry['to']))
    manifest = {
        'tool': 'seenby',
        'version': VERSION,
        'ffmpeg': version,
        'video': {'name': os.path.basename(args.video), 'path': args.video, 'duration': duration,
                  'width': width, 'height': height, 'ratio': round(width / height, 3),
                  'orientation': 'portrait' if portrait else 'landscape', 'grade': grade},
        'analysis': {'selector': 'events', 'sample_fps': EVENT_FPS, 'samples': len(samples), 'cell': CELL,
                     'pixel_threshold': PIXEL_T, 'max_frames': args.max_frames, 'range': {'from': start, 'to': end},
                     'segment': args.segment, 'changes': len(events), 'shown': sum(shown),
                     'pointer_moves': picked['pointer_moves'],
                     'blinking': [{'region': [b['x'], b['y'], b['w'], b['h']], 'count': b['count'],
                                   'from': start + b['first'] / EVENT_FPS, 'to': start + b['last'] / EVENT_FPS}
                                  for b in picked['blinking']]},
        'sheet': {'cols': cols, 'rows': rows, 'tile_width': tile_width, 'sheet_width': args.sheet_width,
                  'count': len(sheets)},
        'frames': [{
            'n': n, 'time': f['time'], 'file': os.path.basename(path),
            'sheet': (n - 1) // per_sheet + 1 if len(paths) > 1 else None,
            'reason': f['reason'],
            'recheck': shlex.join([ffmpeg(), '-ss', '%.3f' % start] + span
                                  + ['-i', args.video, '-vf', (_SAMPLES + ',select=eq(n\\,%d)') % (EVENT_FPS, k),
                                     passthrough(version), 'passthrough', '-frames:v', '1', '-q:v', '2',
                                     os.path.join(out_dir, 'frame-%02d-native.jpg' % n)]),
        } for n, (f, k, path) in enumerate(zip(frames, points, paths), 1)],
        'sheets': [{'file': os.path.basename(sheet), 'frames': [first + 1, min(first + per_sheet, len(paths))]}
                   for sheet, first in zip(sheets, range(0, len(paths), per_sheet))],
        'segments': index,
        'events': [{'from': start + e['start'] / EVENT_FPS, 'settled': start + e['settled'] / EVENT_FPS,
                    'until': start + e['until'] / EVENT_FPS, 'region': [e['x'], e['y'], e['w'], e['h']],
                    'changed_px': round(e['px']), 'shown': s} for e, s in zip(events, shown)],
    }
    manifest_path = os.path.join(out_dir, 'frames.json')
    write_json(manifest_path, manifest)

    print('  contact sheets: %s' % ', '.join(sheets or paths))
    if len(sheets) > 4:
        print('  %d contact sheets are more than 4; consider --max-frames or --from/--to' % len(sheets))
    print('  manifest: %s. Sheets are for meaning; read digits from the native frame, '
          'see "recheck" in the manifest.' % manifest_path)
    return 0


def main():
    p = argparse.ArgumentParser(
        description='Pick the frames of a screen recording for an AI agent: contact sheets plus frames.json')
    p.add_argument('video', help='screen recording in any format ffmpeg reads')
    p.add_argument('out_dir', nargs='?', default=None,
                   help='output directory (default: the video path without extension plus -frames)')
    p.add_argument('--max-frames', type=int, default=MAX_FRAMES,
                   help='cap on kept frames (default: %d)' % MAX_FRAMES)
    p.add_argument('--sheet-width', type=int, default=SHEET_WIDTH,
                   help='contact sheet long side, px (default: %d)' % SHEET_WIDTH)
    p.add_argument('--rows', type=int, default=None,
                   help='rows per contact sheet (default: as many as fit the sheet width)')
    p.add_argument('--tile-width', type=int, default=None,
                   help='tile width, px (default: 256, 516 or 776 by aspect ratio)')
    p.add_argument('--from', dest='start', type=float, default=None,
                   help='analyse from this second (default: 0)')
    p.add_argument('--to', dest='end', type=float, default=None,
                   help='analyse up to this second (default: the end of the video)')
    p.add_argument('--segment', type=float, default=120.0,
                   help='length of the index stretches in frames.json, seconds (default: 120)')
    p.add_argument('--selector', choices=('legacy', 'events'), default=None,
                   help='events: changed pixels at native resolution, one frame per screen state that changed (the '
                        'default); legacy: 32x32 thumbnails against a threshold, a timer and a cap, deprecated and to '
                        'be removed; --threshold, --max-gap, --block-k or --sample-fps without --selector choose '
                        'legacy')
    p.add_argument('--threshold', type=float, default=None,
                   help='legacy selector only: mean grey-level difference (0-255) against the last kept frame '
                        'that keeps a frame (default: %.1f)' % THRESHOLD)
    p.add_argument('--max-gap', type=float, default=None,
                   help='legacy selector only: seconds without a kept frame after which one is forced '
                        '(default: %.1f)' % MAX_GAP)
    p.add_argument('--block-k', type=float, default=None,
                   help='legacy selector only: keep a frame when any %dx%d block of the thumbnail differs by more '
                        'than this times the threshold, even if the mean does not; 0 disables (default: %.1f)'
                        % (BLOCK, BLOCK, BLOCK_K))
    p.add_argument('--sample-fps', type=float, default=None,
                   help='legacy selector only: thumbnails per second analysed (default: %.1f)' % SAMPLE_FPS)
    p.add_argument('--dry-run', action='store_true',
                   help='print the selected times and the layout, extract nothing')
    p.add_argument('--force', action='store_true',
                   help='overwrite an output directory that holds frame-*.jpg from something else')
    args = p.parse_args()
    legacy_only = any(v is not None for v in (args.threshold, args.max_gap, args.block_k, args.sample_fps))
    if args.selector == 'events' and legacy_only:
        p.error('--threshold, --max-gap, --block-k and --sample-fps apply to the legacy selector only')
    if args.selector is None:
        args.selector = 'legacy' if legacy_only else 'events'
    args.threshold = THRESHOLD if args.threshold is None else args.threshold
    args.max_gap = MAX_GAP if args.max_gap is None else args.max_gap
    args.block_k = BLOCK_K if args.block_k is None else args.block_k
    args.sample_fps = float(SAMPLE_FPS) if args.sample_fps is None else args.sample_fps
    if args.max_frames < 2:
        p.error('--max-frames must be at least 2: the first and last frames are always kept')
    if args.threshold <= 0:
        p.error('--threshold must be above 0')
    if args.max_gap <= 0:
        p.error('--max-gap must be above 0')
    if args.block_k < 0:
        p.error('--block-k must be 0 or above')
    if args.sheet_width < 64:
        p.error('--sheet-width must be at least 64')
    if args.rows is not None and args.rows < 1:
        p.error('--rows must be at least 1')
    if args.tile_width is not None and args.tile_width < 16:
        p.error('--tile-width must be at least 16')
    if args.sample_fps <= 0:
        p.error('--sample-fps must be above 0')
    if args.start is not None and args.start < 0:
        p.error('--from must be 0 or above')
    if args.end is not None and args.end <= 0:
        p.error('--to must be above 0')
    if args.segment <= 0:
        p.error('--segment must be above 0')
    if args.end is not None and args.end <= (args.start or 0.0):
        p.error('--to must be above --from')
    ranged = args.start is not None or args.end is not None
    start = args.start or 0.0
    try:
        sys.stdout.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass

    def fail(message):
        print(message, file=sys.stderr)
        return 1

    out_dir = args.out_dir or (os.path.splitext(args.video)[0] + '-frames')
    error = require_tools()
    if error:
        return fail(error)
    if not os.path.isfile(args.video):
        return fail('no such file: %s' % args.video)
    error = check_out_dir(out_dir, args.force)
    if error:
        return fail(error)
    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)
        clean(out_dir)

    stage = 'probe'
    try:
        duration, width, height = probe(args.video)
        if start >= duration:
            return fail('--from %.1f is past the end of the video (%.1f s)' % (start, duration))
        if args.end is not None and args.end > duration:
            return fail('--to %.1f is past the end of the video (%.1f s)' % (args.end, duration))
        end = duration if args.end is None else args.end
        if args.selector == 'events':
            return _run_events(args, out_dir, start, end, ranged, duration, width, height)
        stage = 'thumbnails'
        thumbs = thumbnails(args.video, args.sample_fps, start, end - start if ranged else None)
        if not thumbs:
            return fail('could not decode the video: no frames')
        times, threshold, max_gap = fit_to_cap(thumbs, args.max_frames, args.threshold, args.max_gap,
                                               args.block_k, args.sample_fps)
        cap_active = threshold > args.threshold or max_gap > args.max_gap
        quiet = [] if cap_active else quiet_stretches(thumbs, threshold, max_gap, args.max_frames, args.block_k,
                                                      args.sample_fps)
        frames = select_frames(thumbs, threshold, max_gap, args.block_k, args.sample_fps, quiet)
        times = [f['time'] + start for f in frames]
        for f in frames:
            f['time'] += start
        portrait = height > width
        grade, tile_width, cols, rows, _ = layout(width, height, len(times), args.sheet_width,
                                                  args.rows, args.tile_width)

        print('%s: %.1f s, %dx%d, %s' % (os.path.basename(args.video), duration, width, height,
                                         'portrait' if portrait else 'landscape'))
        if ranged:
            print('  range: %.1f-%.1f s' % (start, end))
        print('  %d thumbnails, selected %d/%d (threshold %.1f -> %.1f, max gap %.1f -> %.1f s)'
              % (len(thumbs), len(times), args.max_frames, args.threshold, threshold, args.max_gap, max_gap))
        print('  frames: %s' % ', '.join('%.1f %s' % (f['time'], f['reason']) for f in frames))
        if quiet:
            print('  quiet stretches at a lower threshold: %s' % '; '.join(
                '%.1f-%.1f s at %.1f (largest change %.1f)' % (s['from'] + start, s['to'] + start, s['threshold'],
                                                              s['largest']) for s in quiet))
        print('  layout: %s, tile %d px, %dx%d per sheet' % (grade, tile_width, cols, rows))
        loop = [f for f in frames if f['reason'] in ('diff', 'block', 'timer')]
        timers = sum(f['reason'] == 'timer' for f in loop)
        timer_share = round(timers / len(loop), 2) if loop else 0.0
        block_active = args.block_k > 0 and args.block_k * min([threshold] + [s['threshold'] for s in quiet]) < 255
        if args.block_k > 0 and not block_active:
            print('  block rule inactive: bar %.1f (%.1f x %.1f) is at or above 255'
                  % (args.block_k * threshold, args.block_k, threshold))
        if cap_active and len(times) >= 5:
            options = []
            for cap in (2 * args.max_frames, 3 * args.max_frames):
                alt_times, alt_thr, alt_gap = fit_to_cap(thumbs, cap, args.threshold, args.max_gap,
                                                         args.block_k, args.sample_fps)
                content = sum(f['reason'] in ('diff', 'block')
                              for f in select_frames(thumbs, alt_thr, alt_gap, args.block_k, args.sample_fps))
                sheets_n = layout(width, height, len(alt_times), args.sheet_width, args.rows, args.tile_width)[4]
                options.append((cap, content, alt_thr, sheets_n))
            if any(o[1] > len(loop) - timers for o in options):
                print('  %d of %d frames by the timer; %s' % (timers, len(loop), '; '.join(
                    '--max-frames %d: %d content frames at threshold %.1f (%d sheets)' % o for o in options)))
            else:
                print('  %d of %d frames by the timer; no cap up to %d adds a content frame'
                      % (timers, len(loop), options[-1][0]))
        if args.dry_run:
            return 0

        stage = 'frames'
        paths = save_frames(args.video, times, out_dir, tile_width)
        stage = 'sheets'
        sheets = contact_sheets(paths, out_dir, cols, rows) if len(paths) > 1 else []
        stage = 'version'
        version = ffmpeg_version()
    except ValueError as e:
        return fail('%s: %s' % (args.video, e))
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors='replace') if isinstance(e.stderr, bytes) else (e.stderr or '')
        lines = err.strip().splitlines()
        return fail('ffmpeg failed during %s (exit %d): %s' % (stage, e.returncode, lines[-1] if lines else ''))

    per_sheet = cols * rows
    all_timer = len(frames) >= 5 and not any(f['reason'] in ('diff', 'block') for f in frames)
    manifest = {
        'tool': 'seenby',
        'version': VERSION,
        'ffmpeg': version,
        'video': {'name': os.path.basename(args.video), 'path': args.video, 'duration': duration,
                  'width': width, 'height': height, 'ratio': round(width / height, 3),
                  'orientation': 'portrait' if portrait else 'landscape', 'grade': grade},
        'analysis': {'sample_fps': args.sample_fps, 'thumbnails': len(thumbs), 'max_frames': args.max_frames,
                     'threshold': {'requested': args.threshold, 'effective': threshold},
                     'max_gap': {'requested': args.max_gap, 'effective': max_gap},
                     'block_k': args.block_k, 'block_active': block_active, 'range': {'from': start, 'to': end},
                     'segment': args.segment, 'all_timer': all_timer, 'timer_share': timer_share,
                     'quiet': [{'from': s['from'] + start, 'to': s['to'] + start, 'largest': s['largest'],
                                'threshold': s['threshold']} for s in quiet]},
        'sheet': {'cols': cols, 'rows': rows, 'tile_width': tile_width, 'sheet_width': args.sheet_width,
                  'count': len(sheets)},
        'frames': [{
            'n': n, 'time': f['time'], 'file': os.path.basename(path),
            'sheet': (n - 1) // per_sheet + 1 if len(paths) > 1 else None,
            'reason': f['reason'], 'diff': f['diff'], 'block': f['block'],
            'recheck': shlex.join([ffmpeg(), '-ss', '%.3f' % f['time'], '-i', args.video, '-frames:v', '1',
                                   '-q:v', '2', os.path.join(out_dir, 'frame-%02d-native.jpg' % n)]),
        } for n, (f, path) in enumerate(zip(frames, paths), 1)],
        'sheets': [{'file': os.path.basename(sheet), 'frames': [first + 1, min(first + per_sheet, len(paths))]}
                   for sheet, first in zip(sheets, range(0, len(paths), per_sheet))],
        'segments': [dict(entry, activity=act) for entry, act in zip(
            segments(times, start, end, args.segment), activity(thumbs, start, end, args.segment, args.sample_fps))],
    }
    manifest_path = os.path.join(out_dir, 'frames.json')
    write_json(manifest_path, manifest)

    print('  contact sheets: %s' % ', '.join(sheets or paths))
    if len(sheets) > 4:
        print('  %d contact sheets are more than 4; consider --max-frames or --from/--to' % len(sheets))
    if all_timer and cap_active:
        print('  all frames taken by the timer: the threshold contributed nothing (effective %.1f); '
              'try --max-frames, --block-k or --from/--to' % threshold)
    elif all_timer:
        kept = {round((f['time'] - start) * args.sample_fps) for f in frames}
        largest, last = 0.0, thumbs[0]
        for i, thumb in enumerate(thumbs[1:], 1):
            largest = max(largest, _difference(thumb, last))
            if i in kept:
                last = thumb
        line = ('  all frames taken by the timer: the largest change between thumbnails was %.1f, '
                'under the threshold %.1f' % (largest, threshold))
        if largest > 1.0:
            lower = max(1.0, math.floor(largest * 10 / 3) / 10)
            alt = fit_to_cap(thumbs, args.max_frames, lower, args.max_gap, args.block_k, args.sample_fps)
            sheets_n = layout(width, height, len(alt[0]), args.sheet_width, args.rows, args.tile_width)[4]
            line += '; --threshold %.1f: %d content frames at threshold %.1f (%d sheets)' % (
                lower, _content(thumbs, alt, args.block_k, args.sample_fps), alt[1], sheets_n)
        print(line)
    print('  manifest: %s. Sheets are for meaning; read digits from the native frame, '
          'see "recheck" in the manifest.' % manifest_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
