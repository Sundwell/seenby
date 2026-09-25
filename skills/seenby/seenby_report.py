#!/usr/bin/env python3
"""Run seenby.py, transcribe the speech when there is any, write report.md.

The core stays dependency-free; this wrapper is where `faster-whisper` lives.
It talks to the core through `frames.json` only: runs it as a subprocess with
the same interpreter, forwards every option it does not know, and refuses a
manifest older than `MIN_CORE_VERSION`.

  python3 seenby_report.py recording.mp4 [output-dir] [--model NAME] [core options...]

Requires `pip install -r requirements-whisper.txt` only when the recording
has audio above the gate; silent screen recordings never load a model.
"""

import argparse
import ctypes
import glob
import importlib
import json
import os
import subprocess
import sys

MIN_CORE_VERSION = 1
MAX_DB = -45.0       # gate: peak below this is silence
MEAN_DB = -80.0      # gate: mean below this is silence
SHAKY = -0.7         # whisper avg_logprob below this gets a (?) mark
TOLERANCE = 2.0      # seconds of tail without transcript that still count as covered
MODEL = 'large-v3-turbo'


def core_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'seenby.py')


def run_core(video, out_dir, tail):
    done = subprocess.run([sys.executable, core_path(), video, out_dir] + list(tail),
                          capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


def load_manifest(out_dir):
    path = os.path.join(out_dir, 'frames.json')
    if not os.path.isfile(path):
        raise ValueError('no frames.json in %s' % out_dir)
    with open(path, encoding='utf-8') as f:
        manifest = json.load(f)
    if manifest.get('version', 0) < MIN_CORE_VERSION:
        raise ValueError('needs core version >= %d, found %s' % (MIN_CORE_VERSION, manifest.get('version')))
    return manifest


def parse_volume(text):
    found = {}
    for line in text.splitlines():
        for key in ('mean_volume', 'max_volume'):
            if key + ':' in line:
                found[key] = float(line.split(key + ':')[1].split('dB')[0])
    if len(found) < 2:
        raise ValueError('no volumedetect output: mean_volume and max_volume lines missing')
    return found['mean_volume'], found['max_volume']


def _has_audio(video):
    probe = subprocess.run([os.environ.get('FFPROBE', 'ffprobe'), '-v', 'error', '-select_streams', 'a',
                            '-show_entries', 'stream=index', '-of', 'csv=p=0', video],
                           capture_output=True, text=True)
    return not (probe.returncode == 0 and not probe.stdout.strip())


def measure_volume(video):
    """(mean_db, max_db) of the audio track; a recording without one counts as silence."""
    if not _has_audio(video):
        return -91.0, -91.0
    done = subprocess.run([os.environ.get('FFMPEG', 'ffmpeg'), '-i', video, '-af', 'volumedetect',
                           '-f', 'null', '-'], capture_output=True, text=True)
    return parse_volume(done.stderr)


def needs_transcription(mean_db, max_db, anyway):
    return anyway or (max_db > MAX_DB and mean_db > MEAN_DB)


def _preload_cuda_libraries():
    # The pip CUDA wheels put libcublas and libcudnn under site-packages, where
    # the dynamic loader does not look; loading them by full path first makes
    # ctranslate2's later dlopen by soname succeed.
    for name in ('nvidia.cublas.lib', 'nvidia.cudnn.lib'):
        try:
            folder = list(importlib.import_module(name).__path__)[0]
        except ImportError:
            continue
        for so in sorted(glob.glob(os.path.join(folder, 'lib*.so.*'))):
            try:
                ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass


def transcribe(video, model, device='auto'):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError('faster-whisper is not installed: pip install -r requirements-whisper.txt')
    if not _has_audio(video):
        print('no audio track in %s, nothing to transcribe' % video, file=sys.stderr)
        return [], {'language': 'none', 'language_probability': 0.0, 'device': 'none', 'model': model}
    _preload_cuda_libraries()
    used = 'cpu'
    if device in ('auto', 'cuda'):
        try:
            engine = WhisperModel(model, device='cuda', compute_type='float16')
            used = 'cuda'
        except Exception as error:
            if device == 'cuda':
                raise
            print('cuda unavailable (%s), falling back to cpu int8' % error, file=sys.stderr)
    if used == 'cpu':
        engine = WhisperModel(model, device='cpu', compute_type='int8')
    raw, info = engine.transcribe(video, beam_size=5, vad_filter=False, condition_on_previous_text=False)
    segments = [{'start': float(s.start), 'end': float(s.end), 'text': s.text.strip(),
                 'avg_logprob': float(s.avg_logprob)} for s in raw]
    return segments, {'language': info.language, 'language_probability': float(info.language_probability),
                      'device': used, 'model': model}


def coverage(segments, duration):
    end = max((s['end'] for s in segments), default=0.0)
    return end, duration - end > TOLERANCE


def frame_intervals(frames, end):
    times = [f['time'] for f in frames]
    return [(t, times[i + 1] if i + 1 < len(times) else end) for i, t in enumerate(times)]


def speech_for(interval, segments):
    start, stop = interval
    return [(s, s['start'] < start) for s in segments if s['start'] < stop and s['end'] > start]


def _line(segment, continued=False):
    text = '- [%.1f-%.1f] %s' % (segment['start'], segment['end'], segment['text'])
    if continued:
        text += ' (continued)'
    if segment['avg_logprob'] < SHAKY:
        text += ' (?)'
    return text


def render(manifest, speech, audio, model_info):
    video, analysis, frames = manifest['video'], manifest['analysis'], manifest['frames']
    mean_db, max_db = audio
    out = ['# seenby report: %s' % video['name'], '',
           '%.1f s, %dx%d, %s. %d frames on %d sheets. seenby %s, %s.' % (
               video['duration'], video['width'], video['height'], video['grade'], len(frames),
               manifest['sheet']['count'], manifest['version'], manifest['ffmpeg'])]
    rng = analysis['range']
    if rng['from'] > 0 or rng['to'] < video['duration']:
        out.append('Range %.1f-%.1f s.' % (rng['from'], rng['to']))
    if analysis['all_timer']:
        capped = (analysis['threshold']['effective'] != analysis['threshold']['requested']
                  or analysis['max_gap']['effective'] != analysis['max_gap']['requested'])
        out.append('All frames were taken by the timer; the threshold contributed nothing (effective %.1f). %s' % (
            analysis['threshold']['effective'], 'Try --max-frames, --block-k or --from/--to.' if capped else
            'The seenby.py console output says whether a lower --threshold would keep more.'))
    if speech is None:
        out.append('Audio: mean %.1f dB, max %.1f dB. No speech expected (gate -45/-80 dB, unverified); '
                   'pass --transcribe-anyway to transcribe.' % (mean_db, max_db))
    else:
        out.append('Audio: mean %.1f dB, max %.1f dB. Speech transcribed with %s on %s, language %s (%.2f).' % (
            mean_db, max_db, model_info['model'], model_info['device'], model_info['language'],
            model_info['language_probability']))
        end, truncated = coverage(speech, video['duration'])
        if truncated:
            out.append('Speech covers %.1f of %.1f s; the last %.1f s have no transcript '
                       '(silence, noise, or whisper stopping early).' % (end, video['duration'],
                                                                         video['duration'] - end))
    out.append('')
    sheets = manifest['sheets']
    out.append('Sheets: %s' % (', '.join('%s (frames %d-%d)' % (s['file'], s['frames'][0], s['frames'][1])
                                         for s in sheets) if sheets else 'none (one frame)'))
    out += ['', '## Frames']
    for frame, interval in zip(frames, frame_intervals(frames, rng['to'])):
        out.append('')
        if frame['reason'] == 'first':
            out.append('### %02d - %.1f s (%s)' % (frame['n'], frame['time'], frame['reason']))
        else:
            out.append('### %02d - %.1f s (%s, diff %.1f, block %.1f)' % (
                frame['n'], frame['time'], frame['reason'], frame['diff'], frame['block']))
        if speech is not None:
            lines = [_line(s, continued) for s, continued in speech_for(interval, speech)]
            out += lines or ['(no speech in this interval)']
    if speech is not None:
        out += ['', '## Speech', '']
        out += [_line(s) for s in speech] or ['(nothing transcribed)']
    out += ['', '## Reading rule', '',
            "Sheets are for meaning; read digits from the native frame. Each frame's `recheck` command in "
            'frames.json extracts it, for example:', '', '    ' + frames[0]['recheck']]
    return '\n'.join(out) + '\n'


def main():
    p = argparse.ArgumentParser(
        description='Run seenby.py, transcribe speech with whisper when the audio is loud enough, write report.md. '
                    'Options not listed here go to seenby.py unchanged.')
    p.add_argument('video')
    p.add_argument('out_dir', nargs='?', default=None)
    p.add_argument('--model', default=MODEL, help='whisper model name (default: %s)' % MODEL)
    p.add_argument('--transcribe-anyway', action='store_true', help='transcribe even below the audio gate')
    p.add_argument('--device', choices=('auto', 'cuda', 'cpu'), default='auto',
                   help='whisper device (default: auto, cuda with a cpu fallback)')
    args, tail = p.parse_known_args()
    out_dir = args.out_dir or (os.path.splitext(args.video)[0] + '-frames')
    report = os.path.join(out_dir, 'report.md')
    if os.path.isfile(report):
        os.remove(report)

    code, stdout, stderr = run_core(args.video, out_dir, tail)
    if code != 0:
        lines = [l for l in stderr.splitlines() if l.strip()]
        print('seenby.py exited %d%s' % (code, ': ' + lines[-1] if lines else ''), file=sys.stderr)
        return code
    sys.stdout.write(stdout)

    try:
        manifest = load_manifest(out_dir)
        audio = measure_volume(args.video)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    speech = info = None
    if needs_transcription(audio[0], audio[1], args.transcribe_anyway):
        try:
            speech, info = transcribe(args.video, args.model, args.device)
        except ImportError as error:
            print(error, file=sys.stderr)
            return 1
    with open(report, 'w', encoding='utf-8') as f:
        f.write(render(manifest, speech, audio, info))
    print('  report: %s' % report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
