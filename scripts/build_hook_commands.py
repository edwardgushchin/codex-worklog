#!/usr/bin/env python3
"""Generate cache-independent commands from reviewable Python sources.

Compression keeps the Windows command below cmd.exe's command-length limit.
It is packaging, not a second implementation: the validator compares the exact
launcher source and exact wrapper; zlib implementations may encode it differently.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/codex-worklog'


def commands(plugin: Path = PLUGIN) -> tuple[str, str]:
    runtime = (plugin / 'scripts/worklog.py').read_text(encoding='utf-8')
    names = {'WorklogError', '_absolute', '_linked', '_Directory', '_locked'}
    shared = []
    for node in ast.parse(runtime).body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names:
            first = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
            shared.append('\n'.join(runtime.splitlines()[first - 1:node.end_lineno]))
    if len(shared) != len(names):
        raise ValueError('Required runtime storage helpers are missing')
    source = ('from __future__ import annotations\n'
              'import errno, os, secrets, stat, time, unicodedata\n'
              'from pathlib import Path\n'
              'from typing import Any, Iterator\n'
              'from contextlib import contextmanager\n'
              'LOCK_TIMEOUT = 0.1\n' + '\n\n'.join(shared) + '\n')
    launcher = (plugin / 'scripts/hook_launcher.py').read_text(encoding='utf-8')
    digest = hashlib.sha256(runtime.encode('utf-8')).hexdigest()
    launcher = launcher.replace('    main()\n', f'    main({digest!r})\n')
    source += launcher.replace('from worklog import WorklogError, _Directory, _absolute, _locked\n', '')
    compile(source, '<worklog-hook-launcher>', 'exec')
    payload = base64.b64encode(zlib.compress(source.encode('utf-8'), 9)).decode('ascii')
    code = f"import base64,zlib;exec(zlib.decompress(base64.b64decode('{payload}')))"
    unix = f'python3 -B -c "{code}"'
    windows = f'py -3 -B -c "{code}"'
    if len(windows) > 8000:
        raise ValueError('Embedded launcher exceeds the Windows command budget')
    return unix, windows


def command_matches(actual: object, expected: str) -> bool:
    """Validate without executing; zlib and zlib-ng need not emit equal bytes."""
    if not isinstance(actual, str) or len(actual) > 8000:
        return False
    parts, reference = actual.split("'"), expected.split("'")
    if len(parts) != 3 or parts[::2] != reference[::2]:
        return False
    try:
        source = zlib.decompress(base64.b64decode(reference[1], validate=True))
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(base64.b64decode(parts[1], validate=True), len(source) + 1)
        return decoded == source and decoder.eof and not decoder.unused_data
    except (ValueError, zlib.error):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Regenerate hooks.json commands')
    args = parser.parse_args()
    unix, windows = commands()
    path = PLUGIN / 'hooks/hooks.json'
    document = json.loads(path.read_text(encoding='utf-8'))
    changed = False
    for groups in document['hooks'].values():
        for group in groups:
            for handler in group['hooks']:
                changed |= (not command_matches(handler['command'], unix)
                            or not command_matches(handler['commandWindows'], windows))
                handler.update(command=unix, commandWindows=windows)
    if args.write:
        path.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    elif changed:
        print('Hook commands are stale; run scripts/build_hook_commands.py --write')
        return 1
    print(f'Hook commands match source ({len(windows)} Windows characters).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
