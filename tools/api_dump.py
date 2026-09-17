"""Dump the public surface of a module: constants, functions, classes.

The tester session writes tests against this listing, not against the source.
CI regenerates it and fails when it drifts from the code.

  python3 tools/api_dump.py seenby > docs/specs/api/seenby.txt
"""

import importlib
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def dump(mod):
    out = []
    for name, obj in sorted(vars(mod).items()):
        if name.startswith('_'):
            continue
        if isinstance(obj, (int, float, str)) and not isinstance(obj, bool):
            out.append('%s = %r' % (name, obj))
        elif inspect.isfunction(obj) and obj.__module__ == mod.__name__:
            out.append('def %s%s' % (name, inspect.signature(obj)))
            if obj.__doc__:
                out.append('    """%s"""' % obj.__doc__.strip().splitlines()[0])
        elif inspect.isclass(obj) and obj.__module__ == mod.__name__:
            out.append('class %s:' % name)
            for m, f in sorted(vars(obj).items()):
                if not m.startswith('_') and inspect.isfunction(f):
                    out.append('    def %s%s' % (m, inspect.signature(f)))
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    sys.stdout.write(dump(importlib.import_module(sys.argv[1])))
