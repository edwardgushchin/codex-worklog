"""Exercise the saved hook command, including loss of the entire package."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / 'plugins/codex-worklog'


class HookLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.plugin = self.root / 'cache with spaces' / '0.3.1'
        shutil.copytree(PLUGIN, self.plugin, ignore=shutil.ignore_patterns('__pycache__'))
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        self.data = self.root / 'data'
        self.commands = json.loads((self.plugin / 'hooks/hooks.json').read_text())['hooks']
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('CODEX_WORKLOG_')}
        self.env.update(PLUGIN_ROOT=str(self.plugin), PLUGIN_DATA=str(self.data))

    def run_hook(self, event='PreToolUse'):
        handler = self.commands[event][0]['hooks'][0]
        command = handler['commandWindows' if os.name == 'nt' else 'command']
        return subprocess.run(command, shell=True, env=self.env, cwd=self.workspace,
                              input=json.dumps({'hook_event_name': event, 'cwd': str(self.workspace),
                                                'session_id': 'launcher-test', 'turn_id': 'one',
                                                'prompt': 'DO_NOT_PERSIST_THIS_PROMPT'}),
                              text=True, capture_output=True, timeout=10)

    def events(self):
        return [json.loads(line) for p in sorted(self.data.glob('diagnostics-v1/events-*.jsonl'))
                for line in p.read_text().splitlines()]

    def assert_advisory(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertIn('systemMessage', response)
        self.assertNotIn('decision', response)
        self.assertNotIn('continue', response)
        self.assertNotIn('Traceback', result.stderr)
        return response

    def test_saved_commands_survive_entire_package_removal(self):
        self.plugin.rename(self.root / 'removed-package')
        for event in self.commands:
            with self.subTest(event=event):
                self.assert_advisory(self.run_hook(event))
        records = self.events()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['event'], 'runtime_missing')
        self.assertEqual(records[0]['change_initiator'], 'unknown')
        self.assertIn('observer_pid', records[0])

    def test_unrecorded_turn_receives_repeated_command_and_commits_once(self):
        initial = self.run_hook('UserPromptSubmit')
        self.assertEqual(initial.returncode, 0, initial.stderr)
        full_context = json.loads(initial.stdout)['hookSpecificOutput']['additionalContext']
        for _ in range(3):
            result = self.run_hook('PreToolUse')
            self.assertEqual(result.returncode, 0, result.stderr)
            response = json.loads(result.stdout)
            self.assertEqual(set(response), {'hookSpecificOutput'})
            context = response['hookSpecificOutput']['additionalContext']
            self.assertIn('not recorded', context)
            self.assertLess(len(context), len(full_context))
        command = context.split('Command (send JSON on stdin; use a quoted heredoc on POSIX):\n')[1].splitlines()[0]
        self.assertIn(str(self.plugin / 'scripts/worklog.py'), command)
        payload = {'language': 'en', 'entries': [{
            'title': 'Recovered the author command through the packaged hook',
            'context': ['The initial instruction was not used during this isolated check.'],
            'timeline': [{'time': None, 'items': ['Requested the current command again.']}],
            'changes': ['Saved one block in the temporary workspace.'],
            'decisions': ['Use the generated command without reconstructing its path.'],
            'checks': ['Execute the command and read back the resulting diary.'],
            'next_steps': ['No production files are affected by this test.'],
        }]}
        saved = subprocess.run(command, shell=True, env=self.env, cwd=self.workspace,
                               input=json.dumps(payload), text=True, capture_output=True, timeout=10)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        response = json.loads(saved.stdout)
        self.assertTrue(response['recorded'])
        self.assertFalse(response['staged'])
        diary = next((self.workspace / '.dev-diary').rglob('*.md'))
        recorded = diary.read_bytes()
        self.assertEqual(recorded.count(b'<!-- codex-worklog-entry:'), 1)
        for event in ('PreToolUse', 'Stop', 'SessionEnd'):
            self.assertEqual(json.loads(self.run_hook(event).stdout), {})
        self.assertEqual(diary.read_bytes(), recorded)

    def test_runtime_start_and_replacement_are_logged_without_payloads(self):
        self.assertEqual(self.run_hook('SessionStart').returncode, 0)
        self.assertEqual(self.run_hook().returncode, 0)
        self.assertEqual(len(self.events()), 1)
        (self.plugin / 'scripts/worklog.py').write_text('print("{}")\n')
        self.assertEqual(self.run_hook().returncode, 0)
        records = self.events()
        self.assertEqual(len(records), 2)
        self.assertEqual({r['event'] for r in records}, {'runtime_observed'})
        self.assertEqual(len({r['runtime_sha256'] for r in records}), 2)
        rendered = json.dumps(records)
        for forbidden in ('DO_NOT_PERSIST_THIS_PROMPT', str(self.workspace), str(self.root)):
            self.assertNotIn(forbidden, rendered)

    def test_crash_and_exit_two_are_advisory_only_for_hooks(self):
        script = self.plugin / 'scripts/worklog.py'
        for source in ('raise SystemExit(2)', 'raise RuntimeError("DO_NOT_PERSIST_EXCEPTION")',
                       'this is not valid Python!', 'print("partial"); raise SystemExit(2)'):
            with self.subTest(source=source):
                script.write_text(source)
                response = self.assert_advisory(self.run_hook('Stop'))
                self.assertNotIn('DO_NOT_PERSIST_EXCEPTION', json.dumps(response))
        direct = subprocess.run([sys.executable, '-B', str(script), 'submit'],
                                text=True, capture_output=True)
        self.assertEqual(direct.returncode, 2)
        self.assertTrue(all(r['event'] == 'runtime_failed' for r in self.events()))

    def test_unavailable_diagnostics_do_not_block_or_leak_paths(self):
        self.data.write_text('existing user file')
        self.plugin.rename(self.root / 'removed-package')
        response = self.assert_advisory(self.run_hook('Stop'))
        self.assertIn('not saved', response['systemMessage'])
        self.assertNotIn(str(self.root), response['systemMessage'])
        self.assertEqual(self.data.read_text(), 'existing user file')

    def test_linked_diagnostic_directory_is_not_followed(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.data.mkdir()
        try:
            (self.data / 'diagnostics-v1').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Directory symlinks are unavailable')
        self.plugin.rename(self.root / 'removed-package')
        self.assert_advisory(self.run_hook())
        self.assertEqual(list(outside.iterdir()), [])

    def test_off_mode_does_not_create_diagnostics_even_when_runtime_is_missing(self):
        self.env['CODEX_WORKLOG_ENFORCEMENT'] = 'off'
        self.plugin.rename(self.root / 'removed-package')
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertFalse(self.data.exists())

    def test_existing_direct_submit_still_reports_invalid_payload(self):
        script = self.plugin / 'scripts/worklog.py'
        result = subprocess.run([sys.executable, '-B', str(script), 'submit', '--data', str(self.data),
                                 '--session', 'launcher-test', '--turn', 'one'],
                                cwd=self.workspace, env=self.env, input='{}',
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('"recorded":true', result.stdout)
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_failure_output_cannot_block_or_rewrite_a_tool(self):
        script = self.plugin / 'scripts/worklog.py'
        for response in ({'decision': 'block'}, {'continue': False},
                         {'hookSpecificOutput': {'permissionDecision': 'deny'}},
                         {'hookSpecificOutput': {'updatedInput': {'cmd': 'unwanted'}}}):
            script.write_text('print(' + repr(json.dumps(response)) + ')')
            self.assert_advisory(self.run_hook())

    def test_concurrent_diagnostics_are_deduplicated(self):
        from concurrent.futures import ThreadPoolExecutor
        self.plugin.rename(self.root / 'removed-package')
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(lambda _: self.run_hook(), range(6)))
        for result in results:
            self.assert_advisory(result)
        self.assertEqual(len(self.events()), 1)

    def test_diagnostics_preserve_prefix_and_reject_linked_event_file(self):
        self.run_hook('SessionStart')
        path = next(self.data.glob('diagnostics-v1/events-*.jsonl'))
        before = path.read_bytes()
        (self.plugin / 'scripts/worklog.py').write_text('print("{}")\n')
        self.run_hook()
        self.assertTrue(path.read_bytes().startswith(before))
        outside = self.root / 'protected'
        try:
            os.link(path, outside)
        except OSError:
            self.skipTest('Hard links are unavailable')
        before = outside.read_bytes()
        self.plugin.rename(self.root / 'removed-package')
        response = self.assert_advisory(self.run_hook())
        self.assertIn('not saved', response['systemMessage'])
        self.assertEqual(outside.read_bytes(), before)

    def test_updater_refuses_mutation_without_audit_and_records_failure(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('audited_updater', REPO / 'scripts/update_plugin.py')
        updater = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(updater)
        with mock.patch.dict(os.environ, {'CODEX_HOME': str(self.root / 'codex')}), \
                mock.patch.object(sys, 'argv', ['update_plugin.py']), \
                mock.patch.object(updater, 'record_observation', return_value=False), \
                mock.patch.object(updater.subprocess, 'run') as run:
            self.assertEqual(updater.main(), 1)
            run.assert_not_called()
        with mock.patch.dict(os.environ, {'CODEX_HOME': str(self.root / 'codex')}), \
                mock.patch.object(sys, 'argv', ['update_plugin.py']), \
                mock.patch.object(updater, 'record_observation', return_value=True) as audit, \
                mock.patch.object(updater.subprocess, 'run', return_value=subprocess.CompletedProcess([], 17)):
            self.assertEqual(updater.main(), 17)
            self.assertEqual([call.args[0]['event'] for call in audit.call_args_list],
                             ['update_started', 'update_failed'])

    @unittest.skipUnless(shutil.which('codex'), 'Native Codex CLI is not installed')
    def test_native_reinstall_removes_cache_but_saved_hook_survives_and_update_is_audited(self):
        # All native writes are confined to a disposable Codex configuration.
        isolated = self.root / 'codex'
        isolated.mkdir()
        self.env['CODEX_HOME'] = str(isolated)
        marketplace = self.root / 'marketplace'
        shutil.copytree(REPO / '.agents', marketplace / '.agents')
        candidate = marketplace / 'plugins/codex-worklog'
        shutil.copytree(self.plugin, candidate)
        manifest = candidate / '.codex-plugin/plugin.json'
        value = json.loads(manifest.read_text())
        value['version'] = '0.3.1'
        manifest.write_text(json.dumps(value))
        def cli(*args):
            result = subprocess.run(['codex', 'plugin', *args, '--json'], env=self.env,
                                    cwd=self.workspace, text=True, capture_output=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        cli('marketplace', 'add', str(marketplace))
        installed = cli('add', 'codex-worklog@codex-worklog')
        self.plugin = Path(installed['installedPath'])
        self.assertTrue(self.plugin.is_relative_to(isolated))
        self.env['PLUGIN_ROOT'] = str(self.plugin)
        self.data = isolated / 'plugins/data/codex-worklog-codex-worklog'
        self.env['PLUGIN_DATA'] = str(self.data)
        self.assertEqual(self.run_hook('SessionStart').returncode, 0)
        value['version'] = '0.3.2'
        manifest.write_text(json.dumps(value))
        updated = subprocess.run([sys.executable, '-B', str(REPO / 'scripts/update_plugin.py')],
                                 env=self.env, cwd=self.workspace, text=True, capture_output=True, timeout=120)
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertFalse(self.plugin.exists(), 'Native reinstall should reproduce the reported cache replacement')
        self.assert_advisory(self.run_hook('Stop'))
        self.assert_advisory(self.run_hook())
        events = self.events()
        operations = [event for event in events if event['event'].startswith('update_')]
        self.assertEqual([e['event'] for e in operations], ['update_started', 'update_completed'])
        self.assertEqual({e['change_initiator'] for e in operations}, {'update_plugin.py'})
        self.assertEqual(operations[0]['operation_id'], operations[1]['operation_id'])
        self.assertEqual(operations[0]['cached_versions'], ['0.3.1'])
        self.assertEqual(operations[1]['cached_versions'], ['0.3.2'])
        self.assertEqual(len([e for e in events if e['event'] == 'runtime_missing']), 1)


if __name__ == '__main__':
    unittest.main()
