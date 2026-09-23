#!/usr/bin/env python3
"""Pick frames from a screen recording so an AI agent sees the whole video.

Why not ffmpeg's `select='gt(scene,X)'`: scene detection compares a frame with
the **previous** one. Someone recording a phone screen scrolls smoothly, so
neighbouring frames are nearly identical and no threshold ever fires. Measured
on four real customer recordings: scene detection returned **zero** frames.

This script compares each frame with the **last frame it kept**. The change
accumulates, and a couple of seconds of scrolling crosses the threshold. Two
safety nets on top: a frame is forced when more than `--max-gap` seconds have
passed since the last kept one, and there is a cap on the number of frames.
The cap **raises the threshold** instead of cutting the tail: in a screen
recording the end usually matters more than the start, that is where the
result is shown.

Output: individual frames, contact sheets (each sheet a single image an agent
can read in one go) and `frames.json`, the manifest with the time and reason
of every frame plus a ready `recheck` command that extracts the native frame.
Sheets are for meaning; digits are read from the native frame. Tile width is
at least 260 px for phone footage and 780 px for desktop footage, otherwise
small UI text becomes unreadable.

  python3 seenby.py recording.mp4 [output-dir]

Requires `ffmpeg` and `ffprobe` on PATH, or `FFMPEG` / `FFPROBE` env vars.
Exit codes: 0 done, 1 could not run, 2 bad arguments.
"""

import argparse
import functools
import json
import math
import operator
import os
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


def select_frames(thumbs, threshold, max_gap, block_k=BLOCK_K, sample_fps=SAMPLE_FPS):
    """Kept thumbnails as {time, diff, block, reason}, both measured against the last kept one."""
    frames = []
    last = None
    last_time = -1e9
    bar = block_k * threshold
    for i, thumb in enumerate(thumbs):
        t = i / sample_fps
        diff = 0.0 if last is None else _difference(thumb, last)
        block = None
        if last is None:
            reason = 'first'
        elif diff > threshold:
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
        rows = max(1, (sheet_width - 2 * MARGIN + PADDING) // (tile_h + PADDING))
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


def contact_sheets(paths, out_dir, cols, rows):
    """Tile frames into `cols x rows` images: an agent reads each in one go.

    Several sheets rather than one big one: vision models downscale an image
    to roughly 1568 px on the long side. One landscape sheet of 24 frames in
    two columns would be 1580 x 5300 px, and after downscaling a 780 px tile
    turns into 230 px, unreadable. Three landscape rows fit without shrinking.
    """
    per_sheet = cols * rows
    sheets = []
    for n, start in enumerate(range(0, len(paths), per_sheet), 1):
        batch = paths[start:start + per_sheet]
        sheet = os.path.join(out_dir, 'sheet-%02d.jpg' % n)
        # The `tile` filter needs a single input stream; separate `-i` inputs
        # silently collapse into one frame, so the batch goes in as a concat list.
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
            f.write(''.join("file '%s'\n" % os.path.abspath(p) for p in batch))
        try:
            here = min(cols, len(batch))
            subprocess.run([ffmpeg(), '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f.name,
                            '-vf', 'tile=%dx%d:margin=%d:padding=%d' % (
                                here, math.ceil(len(batch) / here), MARGIN, PADDING),
                            '-frames:v', '1', sheet], check=True)
        finally:
            os.remove(f.name)
        sheets.append(sheet)
    return sheets


def main():
    p = argparse.ArgumentParser(
        description='Pick the frames of a screen recording for an AI agent: contact sheets plus frames.json')
    p.add_argument('video', help='screen recording in any format ffmpeg reads')
    p.add_argument('out_dir', nargs='?', default=None,
                   help='output directory (default: the video path without extension plus -frames)')
    p.add_argument('--threshold', type=float, default=THRESHOLD,
                   help='mean grey-level difference (0-255) against the last kept frame that keeps a frame '
                        '(default: %.1f)' % THRESHOLD)
    p.add_argument('--max-gap', type=float, default=MAX_GAP,
                   help='seconds without a kept frame after which one is forced (default: %.1f)' % MAX_GAP)
    p.add_argument('--max-frames', type=int, default=MAX_FRAMES,
                   help='cap on kept frames; raises the threshold, never cuts the tail (default: %d)' % MAX_FRAMES)
    p.add_argument('--block-k', type=float, default=BLOCK_K,
                   help='keep a frame when any %dx%d block of the thumbnail differs by more than this times the '
                        'threshold, even if the mean does not; 0 disables (default: %.1f)' % (BLOCK, BLOCK, BLOCK_K))
    p.add_argument('--sheet-width', type=int, default=SHEET_WIDTH,
                   help='contact sheet long side, px (default: %d)' % SHEET_WIDTH)
    p.add_argument('--rows', type=int, default=None,
                   help='rows per contact sheet (default: as many as fit the sheet width)')
    p.add_argument('--tile-width', type=int, default=None,
                   help='tile width, px (default: 256, 516 or 776 by aspect ratio)')
    p.add_argument('--sample-fps', type=float, default=float(SAMPLE_FPS),
                   help='thumbnails per second analysed (default: %.1f)' % SAMPLE_FPS)
    p.add_argument('--from', dest='start', type=float, default=None,
                   help='analyse from this second (default: 0)')
    p.add_argument('--to', dest='end', type=float, default=None,
                   help='analyse up to this second (default: the end of the video)')
    p.add_argument('--segment', type=float, default=120.0,
                   help='length of the index stretches in frames.json, seconds (default: 120)')
    p.add_argument('--dry-run', action='store_true',
                   help='print the selected times and the layout, extract nothing')
    p.add_argument('--force', action='store_true',
                   help='overwrite an output directory that holds frame-*.jpg from something else')
    args = p.parse_args()
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
        stage = 'thumbnails'
        thumbs = thumbnails(args.video, args.sample_fps, start, end - start if ranged else None)
        if not thumbs:
            return fail('could not decode the video: no frames')
        times, threshold, max_gap = fit_to_cap(thumbs, args.max_frames, args.threshold, args.max_gap,
                                               args.block_k, args.sample_fps)
        frames = select_frames(thumbs, threshold, max_gap, args.block_k, args.sample_fps)
        times = [t + start for t in times]
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
        print('  layout: %s, tile %d px, %dx%d per sheet' % (grade, tile_width, cols, rows))
        loop = [f for f in frames if f['reason'] in ('diff', 'block', 'timer')]
        timers = sum(f['reason'] == 'timer' for f in loop)
        timer_share = round(timers / len(loop), 2) if loop else 0.0
        block_active = args.block_k > 0 and args.block_k * threshold < 255
        if args.block_k > 0 and not block_active:
            print('  block rule inactive: bar %.1f (%.1f x %.1f) is at or above 255'
                  % (args.block_k * threshold, args.block_k, threshold))
        cap_active = threshold > args.threshold or max_gap > args.max_gap
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
                     'segment': args.segment, 'all_timer': all_timer, 'timer_share': timer_share},
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
    if all_timer:
        print('  all frames taken by the timer: the threshold contributed nothing (effective %.1f); '
              'try --max-frames, --block-k or --from/--to' % threshold)
    print('  manifest: %s. Sheets are for meaning; read digits from the native frame, '
          'see "recheck" in the manifest.' % manifest_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
