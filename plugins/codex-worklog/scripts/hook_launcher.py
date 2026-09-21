"""Hook-only failure boundary; embedded in hooks.json, never loaded from cache.

build_hook_commands.py embeds this source and the existing safe storage helpers.
The runtime still owns submit: this launcher never turns a failed submit into
success. Diagnostics identify the observer, never pretend to identify a deleter.
"""
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

from worklog import WorklogError, _Directory, _absolute, _locked


def record_observation(observation, change_initiator='unknown'):
    """Append only state transitions, under the runtime's secure storage lock."""
    try:
        data = _absolute(os.environ.get('PLUGIN_DATA') or os.environ.get('CLAUDE_PLUGIN_DATA'), 'PLUGIN_DATA')
        now = datetime.now(timezone.utc).isoformat()
        with _Directory(data / 'diagnostics-v1', create=True) as directory:
            with _locked(directory, 'events.lock'):
                state_name = observation['runtime_root_id'] + '.json'
                previous = directory.read(state_name, 8192)
                signature = json.dumps(observation, sort_keys=True).encode('utf-8')
                if previous is not None and previous[0] == signature:
                    return True
                event = dict(observation, timestamp=now, observer_pid=os.getpid(),
                             observer_ppid=os.getppid(), change_initiator=change_initiator)
                line = json.dumps(event, sort_keys=True).encode('utf-8') + b'\n'
                name = 'events-' + now[:10] + '.jsonl'
                before = directory.read(name, 2 * 1024 * 1024)
                raw = before[0] if before else b''
                if len(raw) + len(line) > 2 * 1024 * 1024:
                    return False
                directory.replace(name, raw + line, before[1] if before else None)
                directory.replace(state_name, signature, previous[1] if previous else None)
        return True
    except Exception:
        return False


def retained_runtime(root, data, expected_digest):
    """Pin reviewed code outside the disposable cache; never select a newer copy."""
    if not isinstance(expected_digest, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_digest):
        raise WorklogError('reviewed runtime digest is unavailable')
    path = data / 'runtimes-v1' / (expected_digest + '.py')
    with _Directory(path.parent, create=True) as directory:
        with _locked(directory, expected_digest + '.lock'):
            source = directory.read(path.name, 512 * 1024)
            if source is None:
                with _Directory(root / 'scripts') as installed:
                    source = installed.read('worklog.py', 512 * 1024)
                if source is None:
                    raise FileNotFoundError()
                # Match the builder's universal-newline read on Windows too.
                raw = source[0].decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
                if hashlib.sha256(raw).hexdigest() != expected_digest:
                    raise WorklogError('installed runtime does not match the reviewed hook')
                directory.replace(path.name, raw, None)
                source = directory.read(path.name, 512 * 1024)
            if source is None or hashlib.sha256(source[0]).hexdigest() != expected_digest:
                raise WorklogError('retained runtime does not match the reviewed hook')
            return path, source


def main(expected_digest=None):
    raw_root = os.environ.get('PLUGIN_ROOT') or os.environ.get('CLAUDE_PLUGIN_ROOT') or ''
    observation = {'runtime_root_id': hashlib.sha256(raw_root.encode('utf-8', errors='replace')).hexdigest()[:24],
                   'event': 'runtime_failed', 'runtime_sha256': None, 'runtime_version': None}
    response = {}
    try:
        if os.environ.get('CODEX_WORKLOG_ENFORCEMENT') == 'off':
            print('{}')
            return
        root = _absolute(raw_root, 'PLUGIN_ROOT')
        if re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[+.-][A-Za-z0-9.]+)?', root.name):
            observation['runtime_version'] = root.name
        data = _absolute(os.environ.get('PLUGIN_DATA') or os.environ.get('CLAUDE_PLUGIN_DATA'), 'PLUGIN_DATA')
        script, source = retained_runtime(root, data, expected_digest)
        raw, status = source
        observation['runtime_sha256'] = hashlib.sha256(raw).hexdigest()
        observation['runtime_file_id'] = [status.st_dev, status.st_ino, status.st_mtime_ns, status.st_size]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            sys.argv = [str(script)]
            try:
                exec(compile(raw, str(script), 'exec'), {'__name__': '__main__', '__file__': str(script)})
            except SystemExit as error:
                if error.code not in (None, 0):
                    raise RuntimeError('runtime exit') from None
        output = stdout.getvalue()
        if len(output) > 128 * 1024:
            raise ValueError('runtime output too large')
        response = json.loads(output) if output.strip() else {}
        if not isinstance(response, dict) or set(response) - {'systemMessage', 'hookSpecificOutput'}:
            raise ValueError('blocking or invalid hook output')
        nested = response.get('hookSpecificOutput', {})
        if not isinstance(nested, dict) or set(nested) - {'hookEventName', 'additionalContext'}:
            raise ValueError('invalid hook-specific output')
        observation['event'] = 'runtime_observed'
    except Exception as error:
        # _Directory wraps OS errors. Inspect causes without printing their text.
        cause = error
        while cause.__cause__ is not None:
            cause = cause.__cause__
        if isinstance(cause, FileNotFoundError):
            observation['event'] = 'runtime_missing'
        observation['failure_type'] = type(cause).__name__
        response = {'systemMessage': 'Codex Worklog: hook runtime unavailable or failed; '
                    'logging skipped, task may continue. Reload the updated plugin in a new task.'}
    if not record_observation(observation):
        response['systemMessage'] = (response.get('systemMessage', '') +
                                     ' Codex Worklog: launch diagnostics not saved.').strip()
    print(json.dumps(response, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
