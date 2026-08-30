from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKLOG_SCRIPT = (
    REPOSITORY_ROOT / "plugins" / "codex-worklog" / "scripts" / "worklog.py"
)
SPEC = importlib.util.spec_from_file_location("codex_worklog_hook", WORKLOG_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {WORKLOG_SCRIPT}")
worklog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worklog)


class WorklogHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.plugin_data = self.root / "plugin-data"
        self.workspace.mkdir()
        self.environment = {"PLUGIN_DATA": str(self.plugin_data)}
        self.now = datetime(
            2026, 8, 30, 11, 15, 30, tzinfo=timezone(timedelta(hours=3))
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def event(
        self, name: str, session: str = "session-one", **extra: object
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "cwd": str(self.workspace),
            "hook_event_name": name,
            "model": "gpt-test",
            "session_id": session,
        }
        payload.update(extra)
        return payload

    def start(
        self, session: str = "session-one", source: str = "startup"
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            worklog.handle_event(
                self.event("SessionStart", session, source=source),
                self.environment,
                self.now,
            ),
        )

    def state_files(self) -> list[Path]:
        return sorted(self.plugin_data.glob("sessions/*.json"))

    def worklog_files(self) -> list[Path]:
        return sorted(self.workspace.glob(".dev-diary/**/*.md"))

    def run_cli(
        self, input_text: str, environment: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        command_environment = os.environ.copy()
        command_environment.pop("CODEX_WORKLOG_DIR", None)
        command_environment.pop("CODEX_WORKLOG_ENFORCEMENT", None)
        command_environment.update(environment or self.environment)
        return subprocess.run(
            [sys.executable, "-B", str(WORKLOG_SCRIPT)],
            cwd=self.workspace,
            env=command_environment,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_inline_values_are_bounded(self) -> None:
        value = "x" * (worklog.MAX_INLINE_CHARS + 100)

        sanitized = worklog._safe_inline(value)

        self.assertEqual(len(sanitized), worklog.MAX_INLINE_CHARS)
        self.assertTrue(sanitized.endswith("…"))

    def test_private_mode_failure_is_nonfatal(self) -> None:
        with mock.patch.object(Path, "chmod", side_effect=OSError("unsupported")):
            worklog._private_mode(self.workspace, 0o700)

    def test_session_start_creates_private_log_and_recovery_context(self) -> None:
        response = self.start(source="startup")

        files = self.worklog_files()
        self.assertEqual(len(files), 1)
        path = files[0]
        self.assertEqual(
            path.parent.relative_to(self.workspace), Path(".dev-diary/2026/08")
        )
        contents = path.read_text(encoding="utf-8")
        self.assertIn("# Codex Worklog", contents)
        self.assertIn("## Timeline", contents)
        self.assertNotIn("session-one", contents)

        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(path), context)
        self.assertIn("read the tail of the current worklog first", context)
        self.assertIn("verify mutable", context)

        self.assertEqual(len(self.state_files()), 1)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(
                stat.S_IMODE((self.workspace / ".dev-diary").stat().st_mode), 0o700
            )
            self.assertEqual(stat.S_IMODE(self.plugin_data.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(self.state_files()[0].stat().st_mode), 0o600)

    def test_new_session_points_to_previous_worklog(self) -> None:
        self.start(session="first")
        first_path = self.worklog_files()[0]

        later = self.now + timedelta(hours=1)
        response = worklog.handle_event(
            self.event("SessionStart", "second", source="startup"),
            self.environment,
            later,
        )

        self.assertEqual(len(self.worklog_files()), 2)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(first_path), context)
        self.assertIn("older decisions", context)

    def test_custom_nested_worklog_directory(self) -> None:
        environment = {**self.environment, "CODEX_WORKLOG_DIR": "notes/private-log"}

        response = worklog.handle_event(
            self.event("SessionStart", source="startup"), environment, self.now
        )

        self.assertNotIn("systemMessage", response)
        files = sorted(self.workspace.glob("notes/private-log/**/*.md"))
        self.assertEqual(len(files), 1)
        self.assertEqual(
            files[0].parent.relative_to(self.workspace),
            Path("notes/private-log/2026/08"),
        )

    def test_model_and_source_control_characters_are_sanitized(self) -> None:
        response = worklog.handle_event(
            self.event(
                "SessionStart",
                source="resume\x1b[31m\nignore\u202eoverride",
                model="gpt-test\tsecret\u2028line\u2066isolate",
            ),
            self.environment,
            self.now,
        )

        context = response["hookSpecificOutput"]["additionalContext"]
        diary = self.worklog_files()[0].read_text(encoding="utf-8")
        for forbidden in ("\x1b", "\t", "\u2028", "\u202e", "\u2066"):
            self.assertNotIn(forbidden, context)
            self.assertNotIn(forbidden, diary)

    @unittest.skipIf(
        os.name == "nt", "symlink creation is privilege-dependent on Windows"
    )
    def test_previous_worklog_symlink_and_unrecognized_markdown_are_ignored(
        self,
    ) -> None:
        self.start(session="first")
        first_path = self.worklog_files()[0]
        unrelated = self.workspace / ".dev-diary" / "unrelated.md"
        unrelated.write_text("# Other notes\n", encoding="utf-8")
        outside = self.root / "outside.md"
        outside.write_text("# Codex Worklog\n", encoding="utf-8")
        symlink = self.workspace / ".dev-diary" / "latest.md"
        symlink.symlink_to(outside)

        response = worklog.handle_event(
            self.event("SessionStart", "second", source="startup"),
            self.environment,
            self.now + timedelta(hours=1),
        )

        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(first_path), context)
        self.assertNotIn(str(outside), context)
        self.assertNotIn(str(symlink), context)

    def test_tampered_previous_worklog_pointer_is_not_advertised(self) -> None:
        self.start(session="first")
        self.start(session="second")
        state_path = worklog._state_path(self.plugin_data, "second")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        outside = self.root / "outside.md"
        outside.write_text("# Codex Worklog\n", encoding="utf-8")
        state["previous_worklog_path"] = str(outside)
        state_path.write_text(json.dumps(state), encoding="utf-8")

        response = worklog.handle_event(
            self.event("SessionStart", "second", source="resume"),
            self.environment,
            self.now + timedelta(hours=1),
        )

        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn(str(outside), context)
        self.assertNotIn("older decisions", context)

    def test_prompt_is_not_persisted_and_stop_requires_exact_marker(self) -> None:
        self.start()
        secret_prompt = (
            "deploy with token super-secret-value"  # pragma: allowlist secret
        )
        prompt_response = worklog.handle_event(
            self.event(
                "UserPromptSubmit",
                turn_id="turn-one",
                prompt=secret_prompt,
                transcript_path="/private/transcript-with-secret.jsonl",
            ),
            self.environment,
            self.now,
        )
        context = prompt_response["hookSpecificOutput"]["additionalContext"]
        marker_match = re.search(r"<!-- codex-worklog-turn:[0-9a-f]{16} -->", context)
        self.assertIsNotNone(marker_match)
        if marker_match is None:
            self.fail("turn marker is missing")
        marker = marker_match.group(0)

        stored_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in self.worklog_files() + self.state_files()
        )
        self.assertNotIn(secret_prompt, stored_text)
        self.assertNotIn("super-secret-value", stored_text)

        stop_response = worklog.handle_event(
            self.event(
                "Stop",
                turn_id="turn-one",
                stop_hook_active=False,
                last_assistant_message="secret assistant output",
            ),
            self.environment,
            self.now,
        )
        self.assertEqual(stop_response["decision"], "block")
        self.assertIn(marker, stop_response["reason"])
        stored_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in self.worklog_files() + self.state_files()
        )
        self.assertNotIn("private/transcript", stored_text)
        self.assertNotIn("secret assistant output", stored_text)

        diary = self.worklog_files()[0]
        with diary.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
                f"\n\n### 11:15 — Tested\n\n- Decisions: Verify markers.\n\n{marker}\n"
            )

        verified = worklog.handle_event(
            self.event("Stop", turn_id="turn-one", stop_hook_active=True),
            self.environment,
            self.now,
        )
        self.assertEqual(verified, {})

    def test_stop_continuation_does_not_loop(self) -> None:
        self.start()
        worklog.handle_event(
            self.event("UserPromptSubmit", turn_id="turn-two", prompt="status"),
            self.environment,
            self.now,
        )

        response = worklog.handle_event(
            self.event("Stop", turn_id="turn-two", stop_hook_active=True),
            self.environment,
            self.now,
        )

        self.assertNotIn("decision", response)
        self.assertIn("after one continuation", response["systemMessage"])

    def test_prompt_requires_a_turn_id(self) -> None:
        response = worklog.handle_event(
            self.event("UserPromptSubmit", prompt="status"),
            self.environment,
            self.now,
        )

        self.assertIn("did not include a turn id", response["systemMessage"])
        self.assertEqual(len(self.worklog_files()), 1)

    def test_stop_uses_the_stored_turn_id_when_event_omits_it(self) -> None:
        self.start()
        worklog.handle_event(
            self.event("UserPromptSubmit", turn_id="stored-turn", prompt="status"),
            self.environment,
            self.now,
        )

        response = worklog.handle_event(
            self.event("Stop", stop_hook_active=False), self.environment, self.now
        )

        self.assertEqual(response["decision"], "block")
        self.assertIn(
            worklog._marker(worklog._token("stored-turn")), response["reason"]
        )

    def test_stop_early_exit_paths_are_safe(self) -> None:
        self.assertEqual(
            worklog.handle_event(
                {"hook_event_name": "Stop"}, self.environment, self.now
            ),
            {},
        )
        self.assertEqual(
            worklog.handle_event(
                self.event("Stop", session="unknown", turn_id="turn"),
                self.environment,
                self.now,
            ),
            {},
        )
        self.start()
        self.assertEqual(
            worklog.handle_event(self.event("Stop"), self.environment, self.now), {}
        )
        worklog.handle_event(
            self.event("SessionEnd", reason="other"), self.environment, self.now
        )
        self.assertEqual(
            worklog.handle_event(
                self.event("Stop", turn_id="turn"), self.environment, self.now
            ),
            {},
        )

    def test_advisory_mode_warns_without_continuing(self) -> None:
        environment = {**self.environment, "CODEX_WORKLOG_ENFORCEMENT": "advisory"}
        worklog.handle_event(
            self.event("SessionStart", source="startup"), environment, self.now
        )
        worklog.handle_event(
            self.event("UserPromptSubmit", turn_id="turn-three", prompt="status"),
            environment,
            self.now,
        )

        response = worklog.handle_event(
            self.event("Stop", turn_id="turn-three", stop_hook_active=False),
            environment,
            self.now,
        )

        self.assertNotIn("decision", response)
        self.assertIn("no entry for this turn", response["systemMessage"])

    def test_session_end_is_idempotent_until_resume(self) -> None:
        self.start()
        end_event = self.event("SessionEnd", reason="other")

        self.assertEqual(
            worklog.handle_event(end_event, self.environment, self.now), {}
        )
        self.assertEqual(
            worklog.handle_event(end_event, self.environment, self.now), {}
        )
        diary = self.worklog_files()[0]
        contents = diary.read_text(encoding="utf-8")
        self.assertEqual(contents.count("codex-worklog-session-end:"), 1)

        worklog.handle_event(
            self.event("SessionStart", source="resume"),
            self.environment,
            self.now + timedelta(hours=1),
        )
        worklog.handle_event(
            end_event,
            self.environment,
            self.now + timedelta(hours=2),
        )
        contents = diary.read_text(encoding="utf-8")
        self.assertEqual(contents.count("codex-worklog-session-end:"), 2)

    def test_session_end_early_exit_paths_are_safe(self) -> None:
        self.assertEqual(
            worklog.handle_event(
                {"hook_event_name": "SessionEnd"}, self.environment, self.now
            ),
            {},
        )
        self.assertEqual(
            worklog.handle_event(
                self.event("SessionEnd", session="unknown", reason="other"),
                self.environment,
                self.now,
            ),
            {},
        )

    def test_existing_session_end_marker_is_not_duplicated(self) -> None:
        self.start()
        diary = self.worklog_files()[0]
        with diary.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\n<!-- codex-worklog-session-end:1 -->\n")

        response = worklog.handle_event(
            self.event("SessionEnd", reason="other"), self.environment, self.now
        )

        self.assertEqual(response, {})
        contents = diary.read_text(encoding="utf-8")
        self.assertEqual(contents.count("codex-worklog-session-end:1"), 1)

    def test_invalid_directory_override_fails_closed_without_workspace_write(
        self,
    ) -> None:
        for value in (
            "",
            ".",
            "..",
            "../outside",
            "/absolute",
            "C:relative-drive",
            "C:\\absolute-drive",
            "notes\\windows-path",
            "bad:name",
            "bad`name",
            "bad\x00name",
            "bad\x7fname",
            "bad\u2028name",
        ):
            with self.subTest(value=value):
                environment = {**self.environment, "CODEX_WORKLOG_DIR": value}
                response = worklog.handle_event(
                    self.event(
                        "SessionStart", f"session-{repr(value)}", source="startup"
                    ),
                    environment,
                    self.now,
                )
                self.assertIn(
                    "must be a safe, non-empty relative path", response["systemMessage"]
                )
        self.assertEqual(self.worklog_files(), [])

    def test_worklog_path_component_must_be_a_directory(self) -> None:
        (self.workspace / ".dev-diary").write_text("occupied\n", encoding="utf-8")

        response = self.start()

        self.assertIn("path component is not a directory", response["systemMessage"])

    def test_unbounded_worklog_path_fails_before_workspace_write(self) -> None:
        environment = {
            **self.environment,
            "CODEX_WORKLOG_DIR": "/".join(["nested"] * 400),
        }

        response = worklog.handle_event(
            self.event("SessionStart", source="startup"), environment, self.now
        )

        self.assertIn("unsafe to expose to the model", response["systemMessage"])
        self.assertEqual(list(self.workspace.iterdir()), [])

    @unittest.skipIf(
        os.name == "nt", "symlink creation is privilege-dependent on Windows"
    )
    def test_plugin_data_symlink_is_refused(self) -> None:
        real_data = self.root / "real-plugin-data"
        real_data.mkdir()
        self.plugin_data.symlink_to(real_data, target_is_directory=True)

        response = self.start()

        self.assertIn(
            "refusing symbolic link for private plugin data", response["systemMessage"]
        )
        self.assertEqual(list(real_data.iterdir()), [])

    @unittest.skipIf(
        os.name == "nt", "symlink creation is privilege-dependent on Windows"
    )
    def test_symlinked_state_directory_is_refused_before_workspace_write(self) -> None:
        self.plugin_data.mkdir()
        outside = self.root / "outside-state-directory"
        outside.mkdir()
        self.plugin_data.joinpath("sessions").symlink_to(
            outside, target_is_directory=True
        )

        response = self.start()

        self.assertIn(
            "refusing symbolic link for private plugin data", response["systemMessage"]
        )
        self.assertEqual(self.worklog_files(), [])
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipIf(
        os.name == "nt", "symlink creation is privilege-dependent on Windows"
    )
    def test_symlinked_worklog_directory_is_refused(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.workspace / ".dev-diary").symlink_to(outside, target_is_directory=True)

        response = self.start()

        self.assertIn("refusing symbolic link", response["systemMessage"])
        self.assertEqual(list(outside.rglob("*")), [])

    def test_preexisting_hard_link_cannot_become_the_worklog(self) -> None:
        session = "session-one"
        session_token = worklog._token(session, 12)
        daily_root = self.workspace / ".dev-diary" / "2026" / "08"
        daily_root.mkdir(parents=True)
        outside = self.root / "outside.md"
        original = f"# Codex Worklog\n\n- Session: `{session_token}`\n"
        outside.write_text(original, encoding="utf-8")
        expected = daily_root / f"2026-08-30--111530--{session_token}.md"
        os.link(outside, expected)

        response = self.start(session=session)

        self.assertIn("hard-linked worklog", response["systemMessage"])
        self.assertEqual(outside.read_text(encoding="utf-8"), original)

    def test_preexisting_session_file_requires_the_expected_marker(self) -> None:
        session_token = worklog._token("session-one", 12)
        daily_root = self.workspace / ".dev-diary" / "2026" / "08"
        daily_root.mkdir(parents=True)
        expected = daily_root / f"2026-08-30--111530--{session_token}.md"
        expected.write_text(
            "# Codex Worklog\n\n- Session: `different`\n", encoding="utf-8"
        )

        response = self.start()

        self.assertIn("unexpected session marker", response["systemMessage"])
        self.assertEqual(self.state_files(), [])
        self.assertEqual(list(self.plugin_data.joinpath("sessions").iterdir()), [])

    def test_corrupted_state_fails_visibly_without_creating_another_log(self) -> None:
        self.start()
        state_path = self.state_files()[0]
        state_path.write_text("not-json\n", encoding="utf-8")

        response = worklog.handle_event(
            self.event("SessionStart", source="resume"),
            self.environment,
            self.now + timedelta(hours=1),
        )

        self.assertIn("invalid JSON", response["systemMessage"])
        self.assertEqual(len(self.worklog_files()), 1)

    def test_invalid_state_shapes_and_size_fail_visibly(self) -> None:
        self.start()
        state_path = self.state_files()[0]
        invalid_values = (
            ("[]\n", "must contain a JSON object"),
            ('{"closed": null}\n', "invalid closed flag"),
            ('{"last_turn_token": "bad"}\n', "invalid last_turn_token"),
            ('{"previous_worklog_path": 7}\n', "invalid previous worklog path"),
            (" " * (worklog.MAX_STATE_BYTES + 1), "too large"),
            (b"{\xff}".decode("latin1"), "unable to inspect regular file"),
        )
        for raw_value, expected in invalid_values:
            with self.subTest(expected=expected):
                state_path.write_bytes(raw_value.encode("latin1"))
                response = worklog.handle_event(
                    self.event("SessionStart", source="resume"),
                    self.environment,
                    self.now + timedelta(hours=1),
                )
                self.assertIn(expected, response["systemMessage"])

    def test_empty_state_is_not_silently_replaced(self) -> None:
        self.start()
        state_path = self.state_files()[0]
        state_path.write_text("{}\n", encoding="utf-8")
        original_worklogs = self.worklog_files()

        response = worklog.handle_event(
            self.event("SessionStart", source="resume"), self.environment, self.now
        )

        self.assertIn(
            "missing the workspace or worklog path", response["systemMessage"]
        )
        self.assertEqual(state_path.read_text(encoding="utf-8"), "{}\n")
        self.assertEqual(self.worklog_files(), original_worklogs)

    def test_state_requires_workspace_and_worklog_paths(self) -> None:
        self.start()
        state_path = self.state_files()[0]
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.pop("workspace")
        state_path.write_text(json.dumps(state), encoding="utf-8")

        response = worklog.handle_event(
            self.event("SessionStart", source="resume"), self.environment, self.now
        )

        self.assertIn(
            "missing the workspace or worklog path", response["systemMessage"]
        )

    @unittest.skipIf(
        os.name == "nt", "symlink creation is privilege-dependent on Windows"
    )
    def test_symlinked_state_file_is_refused(self) -> None:
        self.start()
        state_path = self.state_files()[0]
        outside = self.root / "outside-state.json"
        outside.write_text(state_path.read_text(encoding="utf-8"), encoding="utf-8")
        state_path.unlink()
        state_path.symlink_to(outside)

        response = worklog.handle_event(
            self.event("SessionStart", source="resume"), self.environment, self.now
        )

        self.assertIn("unable to open regular file", response["systemMessage"])

    def test_hard_linked_state_file_is_refused(self) -> None:
        self.start()
        state_path = self.state_files()[0]
        outside = self.root / "outside-state.json"
        os.link(state_path, outside)

        response = worklog.handle_event(
            self.event("SessionStart", source="resume"), self.environment, self.now
        )

        self.assertIn("file changed or is linked", response["systemMessage"])

    def test_session_state_cannot_move_to_another_workspace(self) -> None:
        self.start()
        other_workspace = self.root / "other-workspace"
        other_workspace.mkdir()

        response = worklog.handle_event(
            {
                **self.event("SessionStart", source="resume"),
                "cwd": str(other_workspace),
            },
            self.environment,
            self.now + timedelta(hours=1),
        )

        self.assertIn("stored workspace does not match", response["systemMessage"])
        self.assertEqual(list(other_workspace.rglob("*")), [])

    def test_invalid_session_end_counter_is_rejected(self) -> None:
        self.start()
        state_path = self.state_files()[0]
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["end_count"] = "not-an-integer"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        response = worklog.handle_event(
            self.event("SessionEnd", reason="other"), self.environment, self.now
        )

        self.assertIn("invalid session end counter", response["systemMessage"])
        contents = self.worklog_files()[0].read_text(encoding="utf-8")
        self.assertNotIn("codex-worklog-session-end", contents)

    def test_compatibility_plugin_data_variable_is_supported(self) -> None:
        response = worklog.handle_event(
            self.event("SessionStart", source="startup"),
            {"CLAUDE_PLUGIN_DATA": str(self.plugin_data)},
            self.now,
        )

        self.assertNotIn("systemMessage", response)
        self.assertEqual(len(self.state_files()), 1)
        self.assertEqual(len(self.worklog_files()), 1)

    def test_invalid_enforcement_fails_before_writing(self) -> None:
        response = worklog.handle_event(
            self.event("SessionStart", source="startup"),
            {**self.environment, "CODEX_WORKLOG_ENFORCEMENT": "mandatory"},
            self.now,
        )

        self.assertIn("must be strict, advisory, or off", response["systemMessage"])
        self.assertFalse(self.plugin_data.exists())
        self.assertEqual(self.worklog_files(), [])

    def test_missing_required_session_fields_fail_visibly(self) -> None:
        for missing_key, expected in (
            ("session_id", "session id"),
            ("cwd", "working directory"),
        ):
            with self.subTest(missing_key=missing_key):
                payload = self.event("SessionStart", source="startup")
                del payload[missing_key]
                response = worklog.handle_event(payload, self.environment, self.now)
                self.assertIn(expected, response["systemMessage"])

    def test_unknown_event_has_no_side_effects(self) -> None:
        response = worklog.handle_event(
            self.event("FutureEvent"), self.environment, self.now
        )

        self.assertEqual(response, {})
        self.assertFalse(self.plugin_data.exists())
        self.assertEqual(self.worklog_files(), [])

    def test_cli_rejects_invalid_json_and_non_object_input(self) -> None:
        for input_text in ("not-json", "[]"):
            with self.subTest(input_text=input_text):
                completed = self.run_cli(input_text)
                self.assertEqual(completed.returncode, 0)
                response = json.loads(completed.stdout)
                self.assertIn("invalid hook input", response["systemMessage"])
                self.assertEqual(completed.stderr, "")

    def test_cli_session_start_contract(self) -> None:
        payload = self.event("SessionStart", source="startup")

        completed = self.run_cli(json.dumps(payload))

        self.assertEqual(completed.returncode, 0)
        response = json.loads(completed.stdout)
        self.assertEqual(
            response["hookSpecificOutput"]["hookEventName"], "SessionStart"
        )
        self.assertEqual(completed.stderr, "")
        self.assertEqual(len(self.worklog_files()), 1)

    def test_cli_resolves_relative_workspace_and_plugin_data(self) -> None:
        payload = {
            **self.event("SessionStart", source="startup", model=None),
            "cwd": ".",
            "session_id": "relative-session",
        }

        completed = self.run_cli(
            json.dumps(payload), {"PLUGIN_DATA": "relative-plugin-data"}
        )

        self.assertEqual(completed.returncode, 0)
        self.assertNotIn("systemMessage", json.loads(completed.stdout))
        self.assertTrue((self.workspace / "relative-plugin-data/sessions").is_dir())
        diary = sorted(self.workspace.glob(".dev-diary/**/*.md"))[0]
        self.assertIn("- Model: `unknown`", diary.read_text(encoding="utf-8"))

    def test_nonexistent_workspace_fails_visibly(self) -> None:
        response = worklog.handle_event(
            {
                **self.event("SessionStart", source="startup"),
                "cwd": str(self.root / "missing"),
            },
            self.environment,
            self.now,
        )

        self.assertIn("working directory does not exist", response["systemMessage"])

    def test_invalid_workspace_path_fails_visibly(self) -> None:
        response = worklog.handle_event(
            {**self.event("SessionStart", source="startup"), "cwd": "bad\x00path"},
            self.environment,
            self.now,
        )

        self.assertIn("working directory path is invalid", response["systemMessage"])
        self.assertEqual(self.worklog_files(), [])

    def test_context_unsafe_workspace_path_fails_visibly(self) -> None:
        unsafe_workspace = self.root / "unsafe`workspace"
        unsafe_workspace.mkdir()
        response = worklog.handle_event(
            {
                **self.event("SessionStart", source="startup"),
                "cwd": str(unsafe_workspace),
            },
            self.environment,
            self.now,
        )

        self.assertIn("unsafe model-context characters", response["systemMessage"])
        self.assertEqual(list(unsafe_workspace.iterdir()), [])

    def test_invalid_plugin_data_path_fails_visibly(self) -> None:
        response = worklog.handle_event(
            self.event("SessionStart", source="startup"),
            {"PLUGIN_DATA": "bad\x00path"},
            self.now,
        )

        self.assertIn("PLUGIN_DATA is not a usable path", response["systemMessage"])
        self.assertEqual(self.worklog_files(), [])

    def test_tampered_state_cannot_redirect_session_end_outside_workspace(self) -> None:
        self.start()
        outside = self.root / "outside.md"
        outside.write_text("keep\n", encoding="utf-8")
        state_path = self.state_files()[0]
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["worklog_path"] = str(outside)
        state_path.write_text(json.dumps(state), encoding="utf-8")

        response = worklog.handle_event(
            self.event("SessionEnd", reason="other"),
            self.environment,
            self.now,
        )

        self.assertIn(
            "escapes the session working directory", response["systemMessage"]
        )
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep\n")

    @unittest.skipIf(
        os.name == "nt", "symlink creation is privilege-dependent on Windows"
    )
    def test_replaced_worklog_symlink_is_not_followed(self) -> None:
        self.start()
        diary = self.worklog_files()[0]
        preserved = diary.with_suffix(".preserved")
        diary.rename(preserved)
        outside = self.root / "outside.md"
        outside.write_text("keep\n", encoding="utf-8")
        diary.symlink_to(outside)

        response = worklog.handle_event(
            self.event("SessionEnd", reason="other"), self.environment, self.now
        )

        self.assertIn("refusing symbolic link", response["systemMessage"])
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep\n")

    def test_replaced_worklog_directory_is_rejected(self) -> None:
        self.start()
        diary = self.worklog_files()[0]
        diary.unlink()
        diary.mkdir()

        response = worklog.handle_event(
            self.event("SessionEnd", reason="other"), self.environment, self.now
        )

        self.assertIn("not a regular file", response["systemMessage"])

    def test_missing_worklog_file_is_reported(self) -> None:
        self.start()
        self.worklog_files()[0].unlink()

        response = worklog.handle_event(
            self.event("SessionEnd", reason="other"), self.environment, self.now
        )

        self.assertIn("worklog file is unavailable", response["systemMessage"])

    def test_off_mode_has_no_side_effects(self) -> None:
        environment = {**self.environment, "CODEX_WORKLOG_ENFORCEMENT": "off"}

        response = worklog.handle_event(
            self.event("SessionStart", source="startup"),
            environment,
            self.now,
        )

        self.assertEqual(response, {})
        self.assertFalse(self.plugin_data.exists())
        self.assertEqual(self.worklog_files(), [])

    def test_missing_plugin_data_is_reported_without_workspace_write(self) -> None:
        response = worklog.handle_event(
            self.event("SessionStart", source="startup"),
            {},
            self.now,
        )

        self.assertIn("PLUGIN_DATA is unavailable", response["systemMessage"])
        self.assertEqual(self.worklog_files(), [])


if __name__ == "__main__":
    unittest.main()
