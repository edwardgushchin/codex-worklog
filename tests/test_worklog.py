from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKLOG_SCRIPT = (
    REPOSITORY_ROOT
    / "plugins"
    / "codex-worklog"
    / "scripts"
    / "worklog.py"
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

    def event(self, name: str, session: str = "session-one", **extra: object) -> dict:
        payload = {
            "cwd": str(self.workspace),
            "hook_event_name": name,
            "model": "gpt-test",
            "session_id": session,
        }
        payload.update(extra)
        return payload

    def start(self, session: str = "session-one", source: str = "startup") -> dict:
        return worklog.handle_event(
            self.event("SessionStart", session, source=source),
            self.environment,
            self.now,
        )

    def state_files(self) -> list[Path]:
        return sorted(self.plugin_data.glob("sessions/*.json"))

    def worklog_files(self) -> list[Path]:
        return sorted(self.workspace.glob(".dev-diary/**/*.md"))

    def test_session_start_creates_private_log_and_recovery_context(self) -> None:
        response = self.start(source="startup")

        files = self.worklog_files()
        self.assertEqual(len(files), 1)
        path = files[0]
        self.assertEqual(path.parent.relative_to(self.workspace), Path(".dev-diary/2026/08"))
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

    def test_prompt_is_not_persisted_and_stop_requires_exact_marker(self) -> None:
        self.start()
        secret_prompt = "deploy with token super-secret-value"
        prompt_response = worklog.handle_event(
            self.event(
                "UserPromptSubmit",
                turn_id="turn-one",
                prompt=secret_prompt,
            ),
            self.environment,
            self.now,
        )
        context = prompt_response["hookSpecificOutput"]["additionalContext"]
        marker_match = re.search(r"<!-- codex-worklog-turn:[0-9a-f]{16} -->", context)
        self.assertIsNotNone(marker_match)
        marker = marker_match.group(0)

        stored_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in self.worklog_files() + self.state_files()
        )
        self.assertNotIn(secret_prompt, stored_text)
        self.assertNotIn("super-secret-value", stored_text)

        stop_response = worklog.handle_event(
            self.event("Stop", turn_id="turn-one", stop_hook_active=False),
            self.environment,
            self.now,
        )
        self.assertEqual(stop_response["decision"], "block")
        self.assertIn(marker, stop_response["reason"])

        diary = self.worklog_files()[0]
        with diary.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"\n\n### 11:15 — Tested\n\n- Decisions: Verify markers.\n\n{marker}\n")

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

    def test_advisory_mode_warns_without_continuing(self) -> None:
        environment = {**self.environment, "CODEX_WORKLOG_ENFORCEMENT": "advisory"}
        worklog.handle_event(self.event("SessionStart", source="startup"), environment, self.now)
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

    def test_invalid_directory_override_fails_closed_without_workspace_write(self) -> None:
        environment = {**self.environment, "CODEX_WORKLOG_DIR": "../outside"}

        response = worklog.handle_event(
            self.event("SessionStart", source="startup"),
            environment,
            self.now,
        )

        self.assertIn("must be a safe, non-empty relative path", response["systemMessage"])
        self.assertEqual(self.worklog_files(), [])

    @unittest.skipIf(os.name == "nt", "symlink creation is privilege-dependent on Windows")
    def test_symlinked_worklog_directory_is_refused(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.workspace / ".dev-diary").symlink_to(outside, target_is_directory=True)

        response = self.start()

        self.assertIn("refusing symbolic link", response["systemMessage"])
        self.assertEqual(list(outside.rglob("*")), [])

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

        self.assertIn("escapes the session working directory", response["systemMessage"])
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep\n")

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
