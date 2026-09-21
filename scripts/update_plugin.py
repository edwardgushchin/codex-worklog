#!/usr/bin/env python3
"""Explicit, locally audited reinstall; never invoked by lifecycle hooks.

Close/disable legacy-hook tasks first. Native installation can remove old cache
directories. This tool logs its own operation, not operations performed by the
Codex UI, other processes, or an administrator. No raw CLI output is retained.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/codex-worklog/scripts'))
from hook_launcher import record_observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Refresh the configured Git marketplace first')
    args = parser.parse_args()
    codex_directory = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex').resolve()
    cache = codex_directory / 'plugins/cache/codex-worklog/codex-worklog'
    os.environ['PLUGIN_DATA'] = str(codex_directory / 'plugins/data/codex-worklog-codex-worklog')
    operation = uuid.uuid4().hex

    def record(event, **extra):
        versions = sorted(p.name for p in cache.glob('*')
                          if re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[+.-][A-Za-z0-9.]+)?', p.name))[:128]
        observation = dict(runtime_root_id=hashlib.sha256(str(cache).encode()).hexdigest()[:24],
                           event=event, operation_id=operation, cached_versions=versions, **extra)
        return record_observation(observation, change_initiator='update_plugin.py')

    if not record('update_started', refresh=args.refresh):
        print('Codex Worklog: update cancelled; audit start could not be saved.', file=sys.stderr)
        return 1
    commands = []
    if args.refresh:
        commands.append(['codex', 'plugin', 'marketplace', 'upgrade', 'codex-worklog'])
    commands.append(['codex', 'plugin', 'add', 'codex-worklog@codex-worklog'])
    try:
        for command in commands:
            result = subprocess.run(command, check=False, timeout=120)
            if result.returncode:
                if not record('update_failed', returncode=result.returncode):
                    print('Codex Worklog: update failure audit not saved.', file=sys.stderr)
                return result.returncode
    except (OSError, subprocess.TimeoutExpired) as error:
        saved = record('update_failed', failure_type=type(error).__name__)
        print('Codex Worklog: updater failed; audit ' + ('saved.' if saved else 'not saved.'), file=sys.stderr)
        return 1
    if not record('update_completed'):
        print('Codex Worklog: install finished but completion audit was not saved.', file=sys.stderr)
        return 1
    print('Codex Worklog: update audited. Start a new task and review the new hook definitions.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
