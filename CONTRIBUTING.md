# Contributing

Thanks for looking. seenby is small on purpose: one dependency-free core, one optional wrapper, and a spec
that says exactly what they do. Most of what follows is about keeping it that way.

## Reporting a problem

Open an issue with the bug report template. The useful parts are the exact command, the whole console output,
the `frames.json` from the run, and the recording's resolution and duration. If you can share the recording
itself, do; if not, `--dry-run` output plus `frames.json` is usually enough to see what the selection did.

"It picked the wrong frames" is a real bug class here. Say which moment you expected on a sheet and was not
there; the `reason` and `diff` values in `frames.json` show why it was skipped.

## How behaviour is defined

Every rule of behaviour lives in `docs/specs/seenby.md` and `docs/specs/seenby_report.md` with an ID
(`SEL-3`, `MAN-7`, `RPT-14`). The tests in `tests/` are written from those rules and the example tables, and
each test carries its rule ID in its name and a `@pytest.mark.spec("ID")` marker. `docs/specs/api/*.txt` is
the generated public surface; CI fails when it drifts from the code.

That gives a simple order for changes:

1. **A behaviour change starts in the spec.** Add a rule with a new ID and an example row with the exact value
   a test can pin. IDs are never renumbered or reused; a rule that goes away keeps its ID and is marked
   `removed`, naming its successor when there is one.
2. **Then the test**, from the spec row, before touching the implementation. The maintainer has a separate
   test-writing session that is mechanically kept from reading the code; a contributor gets the same effect by
   writing the test first. A test that would also pass on an empty implementation is a defect. No `skip`, no
   `xfail`, no `try/except` around the call under test.
3. **Then the code.** Keep the core on the standard library. Anything that pulls a dependency belongs in
   `seenby_report.py` or a new script that talks to the core through `frames.json`.
4. Regenerate the API listing when the surface changed: `python3 tools/api_dump.py seenby >
   docs/specs/api/seenby.txt` (same for `seenby_report`).

Fixes that do not change behaviour (help texts, README, comments) need none of that; just keep the suite
green.

## Running the tests

```
pip install -r requirements-dev.txt
python3 -m pytest -q tests
```

No ffmpeg is needed for the suite. The ffmpeg stages (decoding, frame extraction, sheet tiling) are marked
`[hands-on]` in the specs and are verified by the maintainer against real recordings that are not in the
repository; a change to one of them should come with a before/after run on a real screen recording and its
console output in the pull request.

## What a pull request needs

- The spec change, when behaviour changes, with the new IDs.
- Tests green: `python3 -m pytest -q tests`.
- `docs/specs/api/*.txt` regenerated when the public surface changed.
- For anything that touches the selection or the layout, a before/after table on at least a couple of real
  screen recordings: frame count, threshold reached, and what was gained or lost. Numbers, not adjectives.
- No new dependency in `seenby.py`.

## Style

Plain Python, `%` formatting, no type annotations, no comment that restates the code. A comment earns its
place only where the code does something roundabout for a reason a reader would not guess, and then it says
the reason in one line. English everywhere.
