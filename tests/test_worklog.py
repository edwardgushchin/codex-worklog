from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPOSITORY_ROOT / "plugins" / "codex-worklog"
WORKLOG_SCRIPT = PLUGIN / "scripts" / "worklog.py"
SPEC = importlib.util.spec_from_file_location("codex_worklog_hook", WORKLOG_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {WORKLOG_SCRIPT}")
worklog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worklog)


class WorklogHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.plugin_data = self.root / "plugin-data"
        self.environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "LANG": "en_US.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        self.now = datetime(
            2026, 9, 4, 12, 15, 30, tzinfo=timezone(timedelta(hours=3))
        )

    def event(self, name: str, session: str = "session-one", **extra: Any) -> dict:
        return {
            "cwd": str(self.workspace),
            "hook_event_name": name,
            "model": "gpt-test",
            "session_id": session,
            **extra,
        }

    def handle(
        self, name: str, session: str = "session-one", now: datetime | None = None,
        **extra: Any,
    ) -> dict:
        return worklog.handle_event(
            self.event(name, session, **extra), self.environment, now or self.now
        )

    def begin(self, session: str = "session-one", turn: str = "turn-one") -> dict:
        self.handle("SessionStart", session, source="startup")
        return self.handle(
            "UserPromptSubmit", session, turn_id=turn,
            prompt="Investigate and repair the stale cache entry.",
        )

    def document(self, language: str | None = "en") -> dict:
        value = {
            "entries": [{
                "title": "Repaired stale cache handling; visual acceptance pending",
                "context": [
                    "The user reported stale values after switching accounts.",
                    "Existing unrelated work was present in the workspace.",
                ],
                "timeline": [
                    {"time": "11:15", "items": ["Reproduced the stale value."]},
                    {"time": "11:27", "items": [
                        "The first candidate passed focused tests but failed the real route.",
                        "Rejected that candidate and traced the shared cache guard.",
                    ]},
                    {"time": None, "items": ["Applied the shared guard correction."]},
                    {"time": "2026-09-04T11:45:00+03:00", "items": [
                        "Repeated the focused check after correcting the guard.",
                    ]},
                ],
                "changes": [
                    "Updated the shared cache guard.\nExisting user changes remain intact.",
                    "Both account-switch routes now invalidate the previous value.",
                ],
                "decisions": [
                    "Used the shared guard because both callers route through it.",
                    "Rejected per-screen workarounds after reproducing the second route.",
                ],
                "checks": [
                    "RED: python3 -m unittest tests.test_cache failed: 1 failure.",
                    "GREEN: python3 -m unittest tests.test_cache passed: 12 tests.",
                    "The broader audit still failed on 2 unrelated existing findings.",
                    "Visual acceptance has not been performed.",
                ],
                "next_steps": [
                    "Inspect the account-switch route with the user before accepting.",
                ],
                "artifacts": [],
                "supersedes": [],
            }],
        }
        if language is not None:
            value["language"] = language
        return value

    def submit(
        self, document: dict | None = None, session: str = "session-one",
        turn: str = "turn-one", now: datetime | None = None,
    ) -> dict:
        return worklog.submit_entry(
            self.document() if document is None else document,
            session, turn, environment=self.environment, workspace=self.workspace,
            now=now or self.now,
        )

    def stage(
        self, document: dict | None = None, session: str = "session-one",
        turn: str = "turn-one", now: datetime | None = None,
    ) -> dict:
        """Arrange interrupted/legacy staging without exercising public submit."""
        return worklog._stage_entry(
            self.document() if document is None else document,
            session, turn, environment=self.environment, workspace=self.workspace,
            now=now or self.now,
        )

    def stop(
        self, session: str = "session-one", turn: str = "turn-one",
        now: datetime | None = None,
    ) -> dict:
        return self.handle(
            "Stop", session, now, turn_id=turn, stop_hook_active=False,
            last_assistant_message="Done.",
        )

    def diaries(self, directory: str = ".dev-diary") -> list[Path]:
        return sorted(self.workspace.glob(f"{directory}/**/*.md"))

    def rendered(self) -> str:
        files = self.diaries()
        self.assertEqual(len(files), 1)
        return files[0].read_text(encoding="utf-8")

    def states(self) -> list[Path]:
        return sorted(self.plugin_data.glob("sessions-v2/*.json"))

    def run_cli(
        self, text: str, arguments: tuple[str, ...] = (),
        script: Path = WORKLOG_SCRIPT,
    ) -> subprocess.CompletedProcess[str]:
        environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("CODEX_WORKLOG_")
            and key not in {"PLUGIN_DATA", "CLAUDE_PLUGIN_DATA"}
        }
        environment.update(self.environment)
        return subprocess.run(
            [sys.executable, "-B", str(script), *arguments],
            cwd=self.workspace, env=environment, input=text, text=True,
            capture_output=True, check=False,
        )

    def submit_arguments(self, session: str = "session-one") -> tuple[str, ...]:
        return (
            "submit", "--data", str(self.plugin_data), "--session", session,
            "--turn", "turn-one",
        )

    def test_start_creates_only_versioned_state_and_author_context(self) -> None:
        response = self.handle("SessionStart", source="startup")
        output = response["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        self.assertTrue(output["additionalContext"])
        self.assertEqual(self.diaries(), [])
        self.assertFalse((self.workspace / ".dev-diary").exists())
        self.assertEqual(len(self.states()), 1)
        state = json.loads(self.states()[0].read_text(encoding="utf-8"))
        self.assertEqual(state["version"], 2)
        self.assertEqual(state["session_id"], "session-one")
        self.assertEqual(state["workspace"], str(self.workspace))
        self.assertEqual(state["directory"], ".dev-diary")
        self.assertEqual(state["turns"], {})

    def test_iso_timeline_preserves_seconds_and_accepts_utc_z(self) -> None:
        self.begin()
        document = self.document()
        document["entries"][0]["timeline"] = [
            {"time": "2026-09-04T19:20:27Z", "items": ["First observed phase."]},
            {"time": "2026-09-04T19:20:50.123456+00:00", "items": ["Second observed phase."]},
        ]
        self.submit(document)
        self.assertEqual(self.stop(), {})
        self.assertIn("2026-09-04T19:20:27+00:00", self.rendered())
        self.assertIn("2026-09-04T19:20:50.123456+00:00", self.rendered())

    def test_prompt_provides_exact_submission_command_and_six_section_schema(self) -> None:
        output = self.begin()["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "UserPromptSubmit")
        context = output["additionalContext"]
        for expected in (
            sys.executable, str(WORKLOG_SCRIPT), str(self.plugin_data),
            "submit", "--data", "--session", "--turn", "session-one", "turn-one",
            "context", "timeline", "changes", "decisions", "checks", "next_steps",
        ):
            self.assertIn(expected, context)
        self.assertEqual(self.diaries(), [])

    def test_installed_command_keeps_repeated_plugin_directory(self) -> None:
        installed = self.root / "cache" / "codex-worklog" / "codex-worklog" / "test"
        shutil.copytree(PLUGIN, installed, ignore=shutil.ignore_patterns("__pycache__"))
        script = installed / "scripts" / "worklog.py"
        started = self.run_cli(
            json.dumps(self.event("SessionStart", source="startup")), script=script
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        prompted = self.run_cli(
            json.dumps(self.event(
                "UserPromptSubmit", turn_id="turn-one", prompt="Repair the cache."
            )), script=script,
        )
        self.assertEqual(prompted.returncode, 0, prompted.stderr)
        context = json.loads(prompted.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(script), context)
        submitted = self.run_cli(
            json.dumps(self.document()), self.submit_arguments(), script=script
        )
        self.assertEqual(submitted.returncode, 0, submitted.stderr)
        self.assertTrue(json.loads(submitted.stdout)["recorded"])
        self.assertEqual(len(self.diaries()), 1)
        before = self.diaries()[0].read_bytes()
        completed = self.run_cli(
            json.dumps(self.event("Stop", turn_id="turn-one")), script=script
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.diaries()[0].read_bytes(), before)

    def test_submit_records_full_model_authored_block_without_stop(self) -> None:
        self.begin()
        result = self.submit()
        self.assertTrue(result["recorded"])
        self.assertFalse(result["staged"])
        self.assertEqual(len(result["entry_ids"]), 1)
        rendered = self.rendered()
        for heading in (
            "Context", "Timeline", "Changes", "Decisions", "Checks", "Next steps"
        ):
            self.assertIn(f"### {heading}", rendered)
        self.assertIn("# Codex Worklog — 2026-09-04", rendered)
        self.assertIn("11:15", rendered)
        self.assertIn("+03:00", rendered)
        self.assertEqual(
            self.diaries()[0].relative_to(self.workspace),
            Path(".dev-diary/2026/09/2026-09-04.md"),
        )
        self.assertRegex(rendered, r"guard\.\n[ \t]*Existing user changes remain intact\.")
        self.assertIn("The first candidate passed focused tests but failed the real route.", rendered)
        self.assertIn("RED: python3 -m unittest tests.test_cache failed: 1 failure.", rendered)
        self.assertIn("GREEN: python3 -m unittest tests.test_cache passed: 12 tests.", rendered)
        self.assertIn("The broader audit still failed on 2 unrelated existing findings.", rendered)
        self.assertIn("Visual acceptance has not been performed.", rendered)
        self.assertIn("before accepting.", rendered)
        self.assertNotIn("Done.", rendered)
        self.assertEqual(rendered.count("<!-- codex-worklog-entry:"), 1)
        state = json.loads(self.states()[0].read_text(encoding="utf-8"))
        turn = next(iter(state["turns"].values()))
        self.assertEqual(turn["status"], "committed")
        self.assertNotIn("submission", turn)
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.rendered(), rendered)

    def test_session_end_only_flushes_staged_content(self) -> None:
        self.begin()
        self.stage()
        self.assertEqual(self.diaries(), [])
        self.assertEqual(self.handle("SessionEnd", reason="other"), {})
        first = self.diaries()[0].read_bytes()
        self.assertEqual(self.handle("SessionEnd", reason="other"), {})
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.diaries()[0].read_bytes(), first)

    def test_automatic_goal_turns_refresh_context_and_accept_stale_host_commands(self) -> None:
        self.begin()
        self.submit()
        self.environment["CODEX_THREAD_ID"] = "session-one"
        previous = self.diaries()[0].read_bytes()
        for index in range(3):
            turn = f"goal-turn-{index}"
            start = self.handle("SessionStart", source="compact")
            self.assertNotIn("--turn turn-one", start["hookSpecificOutput"]["additionalContext"])
            response = self.handle("PreToolUse", turn_id=turn, tool_name="Bash",
                                   tool_input={"command": "raw-tool-input-canary"})
            context = response["hookSpecificOutput"]["additionalContext"]
            self.assertIn(f"--turn {turn}", context)
            state_before = self.states()[0].read_bytes()
            self.assertEqual(self.handle("PreToolUse", turn_id=turn, tool_name="Bash"), {})
            self.assertEqual(self.states()[0].read_bytes(), state_before)
            document = self.document()
            document["entries"][0]["title"] = f"Completed independent automatic work block {index}"
            result = self.submit(document, turn="turn-one")
            self.assertTrue(result["recorded"])
            self.assertEqual(result["turn_id"], turn)
            raw = self.diaries()[0].read_bytes()
            self.assertTrue(raw.startswith(previous))
            self.assertIn(f"turn:{turn}".encode(), raw)
            self.assertEqual(self.submit(document, turn=turn)["entry_ids"], result["entry_ids"])
            self.assertEqual(self.stop(turn=turn), {})
            previous = raw
        self.assertEqual(previous.count(b"<!-- codex-worklog-entry:"), 4)
        self.assertNotIn(b"raw-tool-input-canary", self.states()[0].read_bytes())

    def test_pretool_context_refreshes_after_compact_without_reopening_recorded_turn(self) -> None:
        self.begin()
        self.handle("SessionStart", source="compact")
        response = self.handle("PreToolUse", turn_id="turn-one", tool_name="Bash")
        self.assertIn("--turn turn-one", response["hookSpecificOutput"]["additionalContext"])
        self.submit()
        self.handle("SessionStart", source="compact")
        response = self.handle("PreToolUse", turn_id="turn-one", tool_name="Bash")
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("already recorded", context)
        self.assertNotIn("--turn", context)
        changed = self.document()
        changed["entries"][0]["title"] = "Cannot replace the already saved block in this turn"
        with self.assertRaisesRegex(worklog.WorklogError, "already recorded"):
            self.submit(changed)

    def test_stale_turn_rebinding_requires_matching_host_and_pretool_binding(self) -> None:
        self.begin()
        first = self.submit()
        changed = self.document()
        changed["entries"][0]["title"] = "A new block must use a host-observed automatic turn"
        self.environment["CODEX_THREAD_ID"] = "session-one"
        with self.assertRaisesRegex(worklog.WorklogError, "already recorded"):
            self.submit(changed)
        self.handle("PreToolUse", turn_id="goal-turn", tool_name="Bash")
        self.environment["CODEX_THREAD_ID"] = "another-session"
        with self.assertRaisesRegex(worklog.WorklogError, "already recorded"):
            self.submit(changed)
        self.environment["CODEX_THREAD_ID"] = "session-one"
        # An exact retry of the old block remains an old-block retry, even when
        # the host has moved on. A new payload can use the new bound turn.
        self.assertEqual(self.submit()["entry_ids"], first["entry_ids"])
        self.assertEqual(self.submit(changed)["turn_id"], "goal-turn")

    def test_pretool_can_initialize_a_turn_without_user_prompt(self) -> None:
        response = self.handle("PreToolUse", turn_id="goal-turn", tool_name="Bash")
        self.assertIn("--turn goal-turn", response["hookSpecificOutput"]["additionalContext"])
        self.assertTrue(self.submit(turn="goal-turn")["recorded"])

    def test_cli_first_automatic_tool_can_submit_using_an_old_command(self) -> None:
        self.begin()
        self.submit()
        self.environment["CODEX_THREAD_ID"] = "session-one"
        event = self.event("PreToolUse", turn_id="goal-turn", tool_name="Bash")
        hooked = self.run_cli(json.dumps(event))
        self.assertEqual(hooked.returncode, 0, hooked.stderr)
        document = self.document()
        document["entries"][0]["title"] = "The next automatic work block is saved synchronously"
        result = self.run_cli(json.dumps(document), self.submit_arguments())
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(result.stdout)
        self.assertTrue(saved["recorded"])
        self.assertFalse(saved["staged"])
        self.assertEqual(saved["turn_id"], "goal-turn")
        # The first in-process call uses the fixed test date; the CLI uses today.
        self.assertEqual(sum(path.read_text(encoding="utf-8").count(
            "<!-- codex-worklog-entry:") for path in self.diaries()), 2)

    def test_missing_payload_warns_once_without_synthetic_content_or_continuation(self) -> None:
        self.begin()
        response = self.stop()
        self.assertTrue(response.get("systemMessage"))
        self.assertNotIn("decision", response)
        self.assertNotIn("hookSpecificOutput", response)
        self.assertEqual(self.stop(), {})
        self.handle("SessionEnd", reason="other")
        self.assertEqual(self.diaries(), [])

    def test_repeated_submission_and_stop_are_idempotent(self) -> None:
        self.begin()
        first = self.submit()
        original = self.diaries()[0].read_bytes()
        repeated = self.submit()
        self.assertTrue(repeated["recorded"])
        self.assertFalse(repeated["staged"])
        self.assertTrue(repeated["already_recorded"])
        self.assertEqual(first["entry_ids"], repeated["entry_ids"])
        self.stop()
        self.handle("SessionEnd", reason="other")
        self.assertEqual(self.diaries()[0].read_bytes(), original)
        self.assertEqual(original.count(b"codex-worklog-entry:"), 1)

    def test_changed_submission_cannot_replace_recorded_content(self) -> None:
        self.begin()
        self.submit()
        original = self.diaries()[0].read_bytes()
        changed = self.document()
        changed["entries"][0]["checks"] = ["The earlier claim requires correction."]
        with self.assertRaises(worklog.WorklogError):
            self.submit(changed)
        self.assertEqual(self.diaries()[0].read_bytes(), original)

    def test_failed_submit_retains_staging_for_stop_or_submit_retry(self) -> None:
        for recovery in ("Stop", "submit"):
            with self.subTest(recovery=recovery):
                session = f"failure-{recovery}"
                self.begin(session)
                before = [path.read_bytes() for path in self.diaries()]
                with mock.patch.object(
                    worklog, "_commit", side_effect=worklog.WorklogError("disk unavailable")
                ), self.assertRaisesRegex(worklog.WorklogError, "disk unavailable"):
                    self.submit(session=session)
                self.assertEqual([path.read_bytes() for path in self.diaries()], before)
                state = next(
                    json.loads(path.read_text(encoding="utf-8")) for path in self.states()
                    if json.loads(path.read_text(encoding="utf-8"))["session_id"] == session
                )
                turn = next(iter(state["turns"].values()))
                self.assertEqual(turn["status"], "staged")
                self.assertEqual(turn["submission"], self.document())
                if recovery == "Stop":
                    self.assertEqual(self.stop(session=session), {})
                else:
                    self.assertTrue(self.submit(session=session)["recorded"])
                self.assertIn(session, self.rendered())
        self.assertEqual(self.rendered().count("<!-- codex-worklog-entry:"), 2)

    def test_submit_retry_after_diary_commit_before_state_commit_is_exactly_once(self) -> None:
        self.begin()
        real_replace = worklog._Directory.replace

        def fail_state_commit(directory: Any, name: str, raw: bytes, previous: Any) -> None:
            if name.endswith(".json"):
                state = json.loads(raw)
                if any(turn["status"] == "committed" for turn in state["turns"].values()):
                    raise worklog.WorklogError("state commit interrupted")
            real_replace(directory, name, raw, previous)

        with mock.patch.object(worklog._Directory, "replace", fail_state_commit):
            with self.assertRaisesRegex(worklog.WorklogError, "state commit interrupted"):
                self.submit()
        original = self.diaries()[0].read_bytes()
        state = json.loads(self.states()[0].read_text(encoding="utf-8"))
        self.assertEqual(next(iter(state["turns"].values()))["status"], "staged")
        changed = self.document()
        changed["entries"][0]["title"] = "Changed result after interrupted acknowledgement"
        for skip_before_retry in (False, True):
            with self.subTest(skip_before_retry=skip_before_retry):
                if skip_before_retry:
                    self.assertTrue(self.submit({"skip": "no_material_work"})["skipped"])
                with self.assertRaises(worklog.WorklogError):
                    self.submit(changed, now=self.now + timedelta(days=1))
                self.assertEqual(len(self.diaries()), 1)
                self.assertEqual(self.diaries()[0].read_bytes(), original)
        result = self.submit(now=self.now + timedelta(days=1))
        self.assertTrue(result["recorded"])
        self.assertFalse(result["staged"])
        self.assertEqual(self.diaries()[0].read_bytes(), original)
        self.assertEqual(len(self.diaries()), 1)
        self.assertEqual(original.count(b"codex-worklog-entry:"), 1)

    def test_submit_does_not_acknowledge_different_payload_staged_between_locks(self) -> None:
        self.begin()
        replacement = self.document()
        replacement["entries"][0]["title"] = "Concurrent correction of the cache investigation"
        real_stage = worklog._stage_entry

        def replace_staging(document: dict, *args: Any, **kwargs: Any) -> dict:
            result = real_stage(document, *args, **kwargs)
            real_stage(replacement, *args, **kwargs)
            return result

        with mock.patch.object(worklog, "_stage_entry", replace_staging):
            with self.assertRaisesRegex(worklog.WorklogError, "submission changed"):
                self.submit()
        self.assertEqual(self.diaries(), [])
        self.assertTrue(self.submit(replacement)["recorded"])
        rendered = self.rendered()
        self.assertIn(replacement["entries"][0]["title"], rendered)
        self.assertNotIn(self.document()["entries"][0]["title"], rendered)

    def test_identical_submission_retry_keeps_first_timestamp_across_midnight(self) -> None:
        self.begin()
        first = self.now.replace(hour=23, minute=59, second=0)
        self.submit(now=first)
        before = self.states()[0].read_bytes()
        self.submit(now=first + timedelta(minutes=2))
        self.assertEqual(self.states()[0].read_bytes(), before)
        self.stop(now=first + timedelta(minutes=3))
        self.assertEqual([path.name for path in self.diaries()], ["2026-09-04.md"])
        self.assertIn("2026-09-04 23:59 +03:00", self.rendered())

    def test_next_stop_flushes_interrupted_staging_in_chronological_order(self) -> None:
        self.begin()
        self.stage()
        later = self.now + timedelta(hours=1)
        self.handle(
            "UserPromptSubmit", now=later, turn_id="next-turn",
            prompt="Inspect the transport next."
        )
        following = self.document()
        following["entries"][0]["title"] = "Investigated independent transport failure"
        self.stage(following, turn="next-turn", now=later)
        self.assertEqual(self.diaries(), [])
        self.stop(turn="next-turn", now=later)
        rendered = self.rendered()
        self.assertIn(self.document()["entries"][0]["title"], rendered)
        self.assertIn(following["entries"][0]["title"], rendered)
        self.assertLess(
            rendered.index(self.document()["entries"][0]["title"]),
            rendered.index(following["entries"][0]["title"]),
        )
        self.assertEqual(rendered.count("<!-- codex-worklog-entry:"), 2)
        before = self.diaries()[0].read_bytes()
        self.stop()
        self.handle("SessionEnd", reason="other")
        self.assertEqual(self.diaries()[0].read_bytes(), before)

    def test_acknowledgement_stop_also_flushes_interrupted_material_submission(self) -> None:
        self.begin()
        self.stage()
        self.assertEqual(self.handle(
            "UserPromptSubmit", turn_id="thanks", prompt="Спасибо!"
        ), {})
        self.assertEqual(self.stop(turn="thanks"), {})
        self.assertEqual(self.rendered().count("<!-- codex-worklog-entry:"), 1)

    def test_multiple_sessions_share_daily_file_and_keep_distinct_markers(self) -> None:
        for session in ("session-one", "session-two"):
            self.begin(session)
            self.submit(session=session)
            self.stop(session=session)
        rendered = self.rendered()
        self.assertEqual(rendered.count("# Codex Worklog — 2026-09-04"), 1)
        markers = re.findall(r"<!-- codex-worklog-entry:([^>]+) -->", rendered)
        self.assertEqual(len(markers), 2)
        self.assertEqual(len(set(markers)), 2)
        self.assertIn("session-one", rendered)
        self.assertIn("session-two", rendered)

    def test_distinct_blocks_are_not_collapsed_to_the_last_entry(self) -> None:
        self.begin()
        document = self.document()
        second = copy.deepcopy(document["entries"][0])
        second["title"] = "Recorded independent transport investigation"
        second["context"] = ["A second unrelated transport issue was investigated."]
        document["entries"].append(second)
        self.submit(document)
        self.stop()
        rendered = self.rendered()
        self.assertEqual(rendered.count("<!-- codex-worklog-entry:"), 2)
        self.assertIn(document["entries"][0]["title"], rendered)
        self.assertIn(second["title"], rendered)
        self.assertEqual(rendered.count("### Context"), 2)

    def test_submission_date_controls_midnight_flush_and_resume_preserves_prefix(self) -> None:
        self.begin()
        late = self.now.replace(hour=23, minute=59)
        self.submit(now=late)
        self.stop(now=late + timedelta(minutes=2))
        first = self.diaries()[0]
        self.assertEqual(first.name, "2026-09-04.md")
        prefix = first.read_bytes()
        tomorrow = late + timedelta(minutes=3)
        self.handle("SessionStart", now=tomorrow, source="resume")
        self.handle("UserPromptSubmit", now=tomorrow, turn_id="next-day", prompt="Continue.")
        self.submit(turn="next-day", now=tomorrow)
        self.stop(turn="next-day", now=tomorrow)
        self.assertEqual(first.read_bytes(), prefix)
        self.assertEqual([path.name for path in self.diaries()], ["2026-09-04.md", "2026-09-05.md"])

    def test_resumed_same_day_work_is_append_only(self) -> None:
        self.begin()
        self.submit()
        self.stop()
        diary = self.diaries()[0]
        prefix = diary.read_bytes()
        self.handle("SessionEnd", reason="other")
        self.handle("SessionStart", source="resume")
        self.handle("UserPromptSubmit", turn_id="second-turn", prompt="Inspect another route.")
        self.submit(turn="second-turn")
        self.stop(turn="second-turn")
        self.assertTrue(diary.read_bytes().startswith(prefix))
        self.assertEqual(diary.read_bytes().count(b"codex-worklog-entry:"), 2)

    def test_acknowledgements_skip_but_thanks_with_instruction_does_not(self) -> None:
        for index, prompt in enumerate(("Спасибо!", "Thank you.", "👍")):
            turn = f"ack-{index}"
            self.handle("SessionStart", source="startup")
            response = self.handle("UserPromptSubmit", turn_id=turn, prompt=prompt)
            self.assertEqual(response, {})
            self.assertEqual(self.stop(turn=turn), {})
        self.assertEqual(self.diaries(), [])
        response = self.handle(
            "UserPromptSubmit", turn_id="instruction", prompt="Спасибо, исправь README"
        )
        self.assertIn("additionalContext", response["hookSpecificOutput"])
        self.submit(turn="instruction")
        self.stop(turn="instruction")
        self.assertEqual(len(self.diaries()), 1)

    def test_explicit_skip_does_not_create_an_empty_diary_or_warning(self) -> None:
        for reason in ("acknowledgement", "no_material_work", "already_recorded"):
            self.begin(turn=reason)
            result = self.submit({"skip": reason}, turn=reason)
            self.assertFalse(result["recorded"])
            self.assertTrue(result["skipped"])
            self.assertEqual(self.stop(turn=reason), {})
        self.assertEqual(self.handle("SessionEnd", reason="other"), {})
        self.assertEqual(self.diaries(), [])

    def test_model_language_wins_over_environment_and_localizes_all_sections(self) -> None:
        self.environment["CODEX_WORKLOG_LANGUAGE"] = "en"
        self.begin()
        self.submit(self.document("ru"))
        self.stop()
        rendered = self.rendered()
        for heading in (
            "Контекст", "Хронология", "Изменения", "Решения", "Проверки", "Следующие шаги"
        ):
            self.assertIn(f"### {heading}", rendered)
        self.assertNotIn("### Context", rendered)

    def test_language_without_model_value_uses_override_then_os_locale(self) -> None:
        for environment in (
            {"CODEX_WORKLOG_LANGUAGE": "ru", "LANG": "en_US.UTF-8"},
            {"LANG": "ru_RU.UTF-8", "LC_ALL": "C.UTF-8"},
        ):
            with self.subTest(environment=environment):
                self.environment = {"PLUGIN_DATA": str(self.plugin_data), **environment}
                session = hashlib.sha256(json.dumps(environment).encode()).hexdigest()
                self.begin(session)
                self.submit(self.document(None), session=session)
                self.stop(session=session)
        self.assertEqual(self.rendered().count("### Контекст"), 2)

    def test_evidence_preserves_digests_relative_paths_commands_and_artifact_ids(self) -> None:
        self.begin()
        document = self.document()
        digest = "0123456789abcdef" * 4
        document["entries"][0]["checks"].append(
            f"SHA-256: {digest}; inspected 9 pages; external artifact node 17:42."
        )
        document["entries"][0]["changes"].append(
            f"Updated {self.workspace}/src/cache.py after tracing both callers."
        )
        document["entries"][0]["artifacts"] = ["reports/verification.md"]
        self.submit(document)
        self.stop()
        rendered = self.rendered()
        for expected in (digest, "src/cache.py", "node 17:42", "reports/verification.md"):
            self.assertIn(expected, rendered)
        self.assertNotIn(str(self.workspace), rendered)
        self.assertNotIn("[digest]", rendered)
        self.assertNotIn("[local path]", rendered)

    def test_private_named_workspace_ancestor_does_not_hide_public_evidence(self) -> None:
        self.workspace = self.root / "private" / "public-project"
        self.workspace.mkdir(parents=True)
        self.begin()
        document = self.document()
        public = self.workspace / "src" / "cache.py"
        secret = self.workspace / "private" / "config.json"
        document["entries"][0]["checks"] = [
            f"Inspected {public}", f"Inspected `{public}`",
            f"Ran `python3 {public}`", f"[Source](<{public}>)",
            f"Excluded `{secret}` and [closed](<{secret}>).",
        ]
        self.assertTrue(self.submit(document)["recorded"])
        rendered = self.rendered()
        self.assertIn("`python3 src/cache.py`", rendered)
        self.assertIn("[Source](<../../../src/cache.py>)", rendered)
        self.assertNotIn("config.json", rendered)
        self.assertNotIn(str(self.workspace), rendered)

    def test_hooks_do_not_read_transcripts_preserve_raw_text_or_run_git(self) -> None:
        transcript = self.root / "private-transcript.jsonl"
        transcript.write_text("transcript-content-canary", encoding="utf-8")
        original_open = Path.open

        def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
            self.assertNotEqual(path, transcript, "Hooks must not read raw transcripts")
            return original_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", guarded_open), mock.patch.object(
            subprocess, "run", side_effect=AssertionError("No Git or model subprocess")
        ):
            self.handle("SessionStart", source="startup", transcript_path=str(transcript))
            self.handle(
                "UserPromptSubmit", turn_id="turn-one", prompt="raw-prompt-canary",
                transcript_path=str(transcript),
            )
            self.submit()
            self.handle(
                "Stop", turn_id="turn-one", transcript_path=str(transcript),
                last_assistant_message="raw-final-canary",
            )
            self.handle("SessionEnd", reason="other", transcript_path=str(transcript))
        stored = "\n".join(
            path.read_text(encoding="utf-8") for path in self.states() + self.diaries()
        )
        for forbidden in (
            "raw-prompt-canary", "raw-final-canary", "transcript-content-canary",
            str(transcript), "Git status", "Final HEAD", "gpt-test",
        ):
            self.assertNotIn(forbidden, stored)

    def test_custom_root_is_bound_to_the_session(self) -> None:
        self.environment["CODEX_WORKLOG_DIR"] = "notes/private-log"
        self.begin()
        self.environment["CODEX_WORKLOG_DIR"] = "different-root"
        self.submit()
        self.stop()
        self.assertEqual(self.diaries(), [])
        self.assertFalse((self.workspace / "different-root").exists())
        files = self.diaries("notes/private-log")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "2026-09-04.md")

    def test_legacy_diaries_and_state_are_not_rewritten_or_auto_migrated(self) -> None:
        legacy_state = self.plugin_data / "sessions" / "old-session.json"
        legacy_state.parent.mkdir(parents=True)
        legacy_state.write_text('{"legacy":"leave untouched"}\n', encoding="utf-8")
        legacy_diary = self.workspace / ".dev-diary" / "2026" / "09" / "old-session.md"
        legacy_diary.parent.mkdir(parents=True)
        legacy_diary.write_text("# Codex Worklog\nHistorical note.\n", encoding="utf-8")
        state_before, diary_before = legacy_state.read_bytes(), legacy_diary.read_bytes()
        self.begin()
        self.submit()
        self.stop()
        self.assertEqual(legacy_state.read_bytes(), state_before)
        self.assertEqual(legacy_diary.read_bytes(), diary_before)
        self.assertEqual(len(self.states()), 1)

    def test_payload_schema_rejects_incomplete_generic_and_oversized_entries(self) -> None:
        self.begin()
        invalid: list[dict] = [{"entries": []}, {"skip": "unknown"}]
        for field in ("context", "timeline", "changes", "decisions", "checks", "next_steps"):
            missing = self.document()
            del missing["entries"][0][field]
            invalid.append(missing)
            empty = self.document()
            empty["entries"][0][field] = []
            invalid.append(empty)
        for title in ("", "Done", "Готово"):
            document = self.document()
            document["entries"][0]["title"] = title
            invalid.append(document)
        for field, value in (
            ("context", ["x" * 4097]),
            ("checks", ["A meaningful verification result."] * 33),
            ("timeline", [{"time": None, "items": ["A meaningful milestone."]}] * 33),
        ):
            document = self.document()
            document["entries"][0][field] = value
            invalid.append(document)
        document = self.document()
        document["entries"] *= 9
        invalid.append(document)
        for index, document in enumerate(invalid):
            with self.subTest(case=index):
                with self.assertRaises(worklog.WorklogError):
                    self.submit(document)
        self.assertEqual(self.diaries(), [])
        self.submit()
        self.stop()
        self.assertEqual(len(self.diaries()), 1)

    def test_redaction_markers_remain_stable_through_commit_and_retry(self) -> None:
        self.begin()
        document = self.document()
        document["entries"][0]["checks"] = [
            "Inspected private/config.json without retaining its contents.",
            "Skipped [.env] and [private/config.json].",
            "Private key: -----BEGIN PRIVATE KEY-----\nfixture-only\n-----END PRIVATE KEY-----",
            "[private path] [private link] [private key redacted] "
            "[private or unsafe reference] [private or external path] [PRIVATE PATH]",
            "Preserve `[private path]` and [redacted] in a safe explanation.",
        ]
        normalized = worklog._validate_document(document, self.workspace)
        self.assertEqual(worklog._validate_document(normalized, self.workspace), normalized)
        self.stage(document)
        staged = self.states()[0].read_bytes()
        self.assertEqual(self.stop(), {})
        before = self.diaries()[0].read_bytes()
        self.assertNotIn(b"[[private path] path]", before)
        self.assertNotIn(b"fixture-only", staged + before)
        self.assertNotIn(b"private/config.json", staged + before)
        self.assertTrue(self.submit(document)["already_recorded"])
        self.assertEqual(self.diaries()[0].read_bytes(), before)

    def test_normalized_field_limits_reject_before_staging(self) -> None:
        self.begin()
        for staged in (False, True):
            if staged:
                self.stage()
            before = self.states()[0].read_bytes()
            for field in ("title", *worklog.TEXT_FIELDS, "timeline", "artifacts"):
                with self.subTest(staged=staged, field=field):
                    limit = 160 if field == "title" else worklog.MAX_ITEM_CHARS
                    value = "a" * (limit - 9) + " .env"
                    document = self.document()
                    entry = document["entries"][0]
                    entry[field] = (value if field == "title" else
                                    [{"time": None, "items": [value]}] if field == "timeline" else
                                    [value])
                    result = self.run_cli(json.dumps(document), self.submit_arguments())
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("after sanitization", result.stderr)
                    self.assertEqual(self.states()[0].read_bytes(), before)
                    self.assertEqual(self.diaries(), [])
        self.assertEqual(self.stop(), {})
        self.assertEqual(len(self.diaries()), 1)

    def test_normalized_field_at_limit_commits_without_truncation(self) -> None:
        self.begin()
        document = self.document()
        value = "a" * (worklog.MAX_ITEM_CHARS - 15) + " .env"
        document["entries"][0]["checks"] = [value]
        normalized = worklog._validate_document(document, self.workspace)
        check = normalized["entries"][0]["checks"][0]
        self.assertEqual(len(check), worklog.MAX_ITEM_CHARS)
        self.assertTrue(self.submit(document)["recorded"])
        self.assertIn(check, self.rendered())
        before = self.diaries()[0].read_bytes()
        self.assertTrue(self.submit(document)["already_recorded"])
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.diaries()[0].read_bytes(), before)

    def test_bad_language_and_skip_types_fail_validation_without_losing_staging(self) -> None:
        self.begin()
        self.stage()
        before = self.states()[0].read_bytes()
        for value in (None, "", [], {}, 7, True):
            with self.subTest(field="skip", value=value):
                with self.assertRaises(worklog.WorklogError):
                    self.submit({"skip": value})
            with self.subTest(field="language", value=value):
                document = self.document()
                document["language"] = value
                with self.assertRaises(worklog.WorklogError):
                    self.submit(document)
            with self.subTest(field="session_language", value=value):
                response = self.handle("SessionStart", source="resume", session_language=value)
                self.assertTrue(response.get("systemMessage"))
            self.assertEqual(self.states()[0].read_bytes(), before)
        self.stop()
        self.assertEqual(len(self.diaries()), 1)

    def test_superseding_prior_entry_preserves_original_and_rejects_self_reference(self) -> None:
        self.begin()
        original_ids = self.submit()["entry_ids"]
        self.stop()
        diary = self.diaries()[0]
        original = diary.read_bytes()
        self.handle("UserPromptSubmit", turn_id="correction", prompt="Correct the earlier result.")
        correction = self.document()
        correction["entries"][0]["title"] = "Corrected earlier cache verification conclusion"
        correction["entries"][0]["supersedes"] = original_ids
        correction_ids = self.submit(correction, turn="correction")["entry_ids"]
        self.stop(turn="correction")
        self.assertTrue(diary.read_bytes().startswith(original))
        self.assertIn(f"Supersedes entries: {chr(96)}{original_ids[0]}{chr(96)}", self.rendered())
        self.assertNotEqual(correction_ids, original_ids)
        preserved = diary.read_bytes()
        self.handle("UserPromptSubmit", turn_id="self-reference", prompt="Correct the next result.")
        self.stage(turn="self-reference")
        ids = worklog._entry_ids("session-one", "self-reference", 1)
        invalid = self.document()
        invalid["entries"][0]["supersedes"] = ids
        with self.assertRaises(worklog.WorklogError):
            self.submit(invalid, turn="self-reference")
        self.assertTrue(self.stop(turn="self-reference").get("systemMessage"))
        self.assertEqual(diary.read_bytes(), preserved)

    def test_supersedes_resolves_prior_day_entry_from_another_session(self) -> None:
        self.begin()
        previous_id = self.submit()["entry_ids"][0]
        self.stop()
        previous = self.diaries()[0]
        original = previous.read_bytes()
        self.now += timedelta(days=1)
        self.begin(session="another-session")
        correction = self.document()
        correction["entries"][0]["title"] = "Corrected the previous day's verification evidence"
        correction["entries"][0]["supersedes"] = [previous_id]
        self.submit(correction, session="another-session")
        self.assertEqual(self.stop(session="another-session"), {})
        self.assertEqual(previous.read_bytes(), original)
        self.assertEqual([path.name for path in self.diaries()], ["2026-09-04.md", "2026-09-05.md"])
        self.assertIn(
            f"Supersedes entries: {chr(96)}{previous_id}{chr(96)}",
            self.diaries()[1].read_text(encoding="utf-8"),
        )

    def test_unknown_and_same_batch_supersedes_references_cannot_create_diaries(self) -> None:
        for kind in ("unknown", "same-batch"):
            with self.subTest(kind=kind):
                self.begin(session=kind)
                document = self.document()
                reference = "0" * 24
                if kind == "same-batch":
                    peer = copy.deepcopy(document["entries"][0])
                    peer["title"] = "Independent transport investigation result"
                    document["entries"].append(peer)
                    self.stage(document, session=kind)
                    reference = worklog._entry_ids(kind, "turn-one", 2)[1]
                document["entries"][0]["supersedes"] = [reference]
                with self.assertRaises(worklog.WorklogError):
                    self.submit(document, session=kind)
                self.assertTrue(self.stop(session=kind).get("systemMessage"))
                self.assertEqual(self.diaries(), [])

    def test_cli_duplicate_json_keys_do_not_replace_valid_staging(self) -> None:
        self.begin()
        self.stage()
        before = self.states()[0].read_bytes()
        duplicates = (
            '{"skip":"no_material_work","skip":"already_recorded"}',
            '{"entries":[{"title":"first result","title":"second result"}]}',
        )
        for raw in duplicates:
            with self.subTest(raw=raw):
                completed = self.run_cli(raw, self.submit_arguments())
                self.assertEqual(completed.returncode, 2)
                self.assertIn("duplicate", completed.stderr)
                self.assertEqual(completed.stdout, "")
                self.assertEqual(self.states()[0].read_bytes(), before)
        payload = json.dumps(self.event("Stop", turn_id="turn-one"))
        completed = self.run_cli(payload[:-1] + ',"session_id":"different-session"}')
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(json.loads(completed.stdout).get("systemMessage"))
        self.assertEqual(self.states()[0].read_bytes(), before)
        self.assertEqual(self.diaries(), [])

    def test_cli_success_means_diary_exists_before_stop_and_retry_is_idempotent(self) -> None:
        for event in (
            self.event("SessionStart", source="startup"),
            self.event("UserPromptSubmit", turn_id="turn-one", prompt="Repair cache."),
        ):
            completed = self.run_cli(json.dumps(event))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("hookSpecificOutput", json.loads(completed.stdout))
        completed = self.run_cli(json.dumps(self.document()), self.submit_arguments())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["recorded"])
        self.assertFalse(result["staged"])
        original = self.diaries()[0].read_bytes()
        repeated = self.run_cli(json.dumps(self.document()), self.submit_arguments())
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertTrue(json.loads(repeated.stdout)["already_recorded"])
        stopped = self.run_cli(json.dumps(self.event("Stop", turn_id="turn-one")))
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertEqual(json.loads(stopped.stdout), {})
        self.assertEqual(self.diaries()[0].read_bytes(), original)

    def test_cli_storage_failure_returns_nonzero_and_retains_staged_payload(self) -> None:
        self.begin()
        blocked_root = self.workspace / ".dev-diary"
        blocked_root.write_text("Unrelated existing file.\n", encoding="utf-8")
        completed = self.run_cli(json.dumps(self.document()), self.submit_arguments())
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertTrue(completed.stderr)
        state = json.loads(self.states()[0].read_text(encoding="utf-8"))
        self.assertEqual(next(iter(state["turns"].values()))["status"], "staged")
        self.assertEqual(blocked_root.read_text(encoding="utf-8"), "Unrelated existing file.\n")
        blocked_root.unlink()
        completed = self.run_cli(json.dumps(self.document()), self.submit_arguments())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["recorded"])
        self.assertEqual(len(self.diaries()), 1)

    def test_cli_invalid_hook_input_fails_open_and_invalid_submit_fails_closed(self) -> None:
        self.begin()
        for text in ("not-json", "[]", " " * (64 * 1024 + 1)):
            with self.subTest(text=text[:30], command="hook"):
                completed = self.run_cli(text)
                self.assertEqual(completed.returncode, 0)
                self.assertTrue(json.loads(completed.stdout).get("systemMessage"))
                self.assertEqual(completed.stderr, "")
            with self.subTest(text=text[:30], command="submit"):
                completed = self.run_cli(text, self.submit_arguments())
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertTrue(completed.stderr)
        removed = self.run_cli("{}", ("append",))
        self.assertEqual(removed.returncode, 2)
        self.assertEqual(removed.stdout, "")
        self.assertEqual(self.diaries(), [])

    def test_unknown_event_and_off_mode_have_no_side_effects(self) -> None:
        self.assertEqual(self.handle("FutureEvent"), {})
        self.environment["CODEX_WORKLOG_ENFORCEMENT"] = "off"
        self.assertEqual(self.handle("SessionStart", source="startup"), {})
        self.assertFalse(self.plugin_data.exists())
        self.assertEqual(self.diaries(), [])

    def test_compatibility_plugin_data_environment_is_supported(self) -> None:
        self.environment = {
            "CLAUDE_PLUGIN_DATA": str(self.plugin_data), "LANG": "en_US.UTF-8"
        }
        self.begin()
        self.submit()
        self.stop()
        self.assertEqual(len(self.states()), 1)
        self.assertEqual(len(self.diaries()), 1)


if __name__ == "__main__":
    unittest.main()
