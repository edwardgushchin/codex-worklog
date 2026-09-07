"""Security regressions for immediate commits and staged recovery."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins" / "codex-worklog" / "scripts" / "worklog.py"
)
SPEC = importlib.util.spec_from_file_location("storage_security_worklog", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT}")
worklog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worklog)


class StorageSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.plugin_data = self.root / "plugin-data"
        self.environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "LANG": "en_US.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        self.now = datetime(2026, 8, 30, 11, 15, tzinfo=timezone(timedelta(hours=3)))
        self.diary = self.workspace / ".dev-diary/2026/08/2026-08-30.md"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def event(self, name: str, session: str = "storage-session", turn: str = "one") -> dict:
        return {
            "hook_event_name": name,
            "session_id": session,
            "turn_id": turn,
            "cwd": str(self.workspace),
        }

    def handle(self, name: str, session: str = "storage-session", turn: str = "one") -> dict:
        return worklog.handle_event(
            self.event(name, session, turn), self.environment, self.now
        )

    def start(self, session: str = "storage-session", turn: str = "one") -> None:
        self.handle("SessionStart", session, turn)
        self.handle("UserPromptSubmit", session, turn)

    def document(self, title: str = "Validated safe diary storage") -> dict:
        return {
            "language": "en",
            "entries": [{
                "title": title,
                "context": ["The requested storage change needed verification."],
                "timeline": [{"time": "11:15", "items": ["Examined the write boundary."]}],
                "changes": ["Restricted writes to the session's daily diary."],
                "decisions": ["Used the existing standard-library implementation."],
                "checks": ["The isolated storage check passed."],
                "next_steps": ["No further work is required for this block."],
                "artifacts": [],
                "supersedes": [],
            }],
        }

    def submit(self, document: dict | None = None, session: str = "storage-session", turn: str = "one", workspace: Path | None = None) -> dict:
        return worklog.submit_entry(
            self.document() if document is None else document,
            session, turn, environment=self.environment,
            workspace=self.workspace if workspace is None else workspace,
            now=self.now,
        )

    def state_path(self, session: str = "storage-session") -> Path:
        token = hashlib.sha256(session.encode()).hexdigest()[:24]
        return self.plugin_data / "sessions-v2" / f"{token}.json"

    def stage(self, session: str = "storage-session", title: str = "Validated safe diary storage", turn: str = "one", document: dict | None = None) -> None:
        """Prepare recoverable state without taking the public submit commit path."""
        self.start(session, turn)
        worklog._stage_entry(
            self.document(title) if document is None else document,
            session, turn, environment=self.environment, workspace=self.workspace,
            now=self.now,
        )

    def test_submit_creates_a_complete_diary_before_stop(self) -> None:
        self.start()
        self.assertFalse(self.diary.exists())
        result = self.submit()
        self.assertTrue(result["recorded"])
        self.assertFalse(result["staged"])
        self.assertIn("Validated safe diary storage", self.diary.read_text())
        original = self.diary.read_bytes()
        self.assertEqual(self.handle("Stop"), {})
        self.assertEqual(self.diary.read_bytes(), original)

    def test_payload_cannot_select_readme_or_supply_markers(self) -> None:
        self.start()
        readme = self.workspace / "README.md"
        original = b"# Existing user document\n"
        readme.write_bytes(original)
        original_mode = stat.S_IMODE(readme.stat().st_mode)
        for location in ("document", "entry"):
            for field, value in (
                ("worklog_path", str(readme)),
                ("path", str(readme)),
                ("marker", "<!-- codex-worklog-entry:0123456789abcdef -->"),
            ):
                with self.subTest(location=location, field=field):
                    document = self.document()
                    target = document if location == "document" else document["entries"][0]
                    target[field] = value
                    with self.assertRaises(worklog.WorklogError):
                        self.submit(document)
                    self.assertEqual(readme.read_bytes(), original)
                    self.assertEqual(stat.S_IMODE(readme.stat().st_mode), original_mode)
        self.handle("Stop")
        self.assertFalse(self.diary.exists())

    def test_reserved_marker_cannot_be_injected_as_section_text(self) -> None:
        self.start()
        document = self.document()
        document["entries"][0]["checks"] = [
            "<!-- codex-worklog-entry:0123456789abcdef -->"
        ]
        with self.assertRaises(worklog.WorklogError):
            self.submit(document)
        self.assertFalse(self.diary.exists())

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are not available on Windows")
    def test_existing_directory_and_file_permissions_are_preserved(self) -> None:
        self.diary.parent.mkdir(parents=True)
        directories = [self.workspace / ".dev-diary", self.diary.parent.parent, self.diary.parent]
        for directory in directories:
            directory.chmod(0o755)
        self.start()
        self.submit()
        for directory in directories:
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o755)
        self.diary.chmod(0o640)
        original = self.diary.read_bytes()
        self.handle("UserPromptSubmit", turn="two")
        self.submit(self.document("Completed the second storage check"), turn="two")
        self.assertEqual(stat.S_IMODE(self.diary.stat().st_mode), 0o640)
        self.assertTrue(self.diary.read_bytes().startswith(original))

    def test_existing_unrelated_daily_file_is_not_modified(self) -> None:
        self.diary.parent.mkdir(parents=True)
        original = b"# A different application owns this file\n"
        self.diary.write_bytes(original)
        mode = stat.S_IMODE(self.diary.stat().st_mode)
        self.start()
        with self.assertRaises(worklog.WorklogError):
            self.submit()
        result = self.handle("Stop")
        self.assertIn("systemMessage", result)
        self.assertEqual(self.diary.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(self.diary.stat().st_mode), mode)

    @unittest.skipIf(os.name == "nt", "Creating symbolic links may require privileges")
    def test_symlinked_diary_is_rejected(self) -> None:
        self.start()
        self.diary.parent.mkdir(parents=True, exist_ok=True)
        outside = self.root / "outside.md"
        original = b"# Outside document\n"
        outside.write_bytes(original)
        self.diary.symlink_to(outside)
        with self.assertRaises(worklog.WorklogError):
            self.submit()
        result = self.handle("Stop")
        self.assertIn("systemMessage", result)
        self.assertEqual(outside.read_bytes(), original)

    def test_hardlinked_diary_is_rejected(self) -> None:
        self.start()
        self.submit()
        outside = self.root / "linked-diary.md"
        original = self.diary.read_bytes()
        try:
            os.link(self.diary, outside)
        except OSError as error:
            self.skipTest(f"Hard links are unavailable: {error}")
        self.handle("UserPromptSubmit", turn="two")
        with self.assertRaises(worklog.WorklogError):
            self.submit(self.document("A later storage check"), turn="two")
        result = self.handle("Stop", turn="two")
        self.assertIn("systemMessage", result)
        self.assertEqual(self.diary.read_bytes(), original)
        self.assertEqual(outside.read_bytes(), original)

    @unittest.skipIf(os.name == "nt", "Creating symbolic links may require privileges")
    def test_symlinked_worklog_root_cannot_redirect_creation(self) -> None:
        self.start()
        outside = self.root / "outside-diary"
        outside.mkdir()
        (self.workspace / ".dev-diary").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(worklog.WorklogError):
            self.submit()
        result = self.handle("Stop")
        self.assertIn("systemMessage", result)
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "Creating symbolic links may require privileges")
    def test_symlinked_state_is_rejected_before_staging(self) -> None:
        self.start()
        state = self.state_path()
        outside = self.root / "outside-state.json"
        original = state.read_bytes()
        outside.write_bytes(original)
        state.unlink()
        state.symlink_to(outside)
        with self.assertRaises(worklog.WorklogError):
            self.submit()
        self.assertEqual(outside.read_bytes(), original)
        self.assertFalse(self.diary.exists())

    def test_hardlinked_state_is_rejected_before_staging(self) -> None:
        self.start()
        state = self.state_path()
        outside = self.root / "linked-state.json"
        original = state.read_bytes()
        try:
            os.link(state, outside)
        except OSError as error:
            self.skipTest(f"Hard links are unavailable: {error}")
        with self.assertRaises(worklog.WorklogError):
            self.submit()
        self.assertEqual(state.read_bytes(), original)
        self.assertEqual(outside.read_bytes(), original)
        self.assertFalse(self.diary.exists())

    @unittest.skipIf(os.name == "nt", "Creating symbolic links may require privileges")
    def test_symlinked_session_directory_cannot_redirect_state(self) -> None:
        self.start()
        sessions = self.state_path().parent
        outside = self.root / "outside-sessions"
        sessions.rename(outside)
        sessions.symlink_to(outside, target_is_directory=True)
        original = (outside / self.state_path().name).read_bytes()
        with self.assertRaises(worklog.WorklogError):
            self.submit()
        self.assertEqual((outside / self.state_path().name).read_bytes(), original)
        self.assertFalse(self.diary.exists())

    def test_session_cannot_be_submitted_from_a_different_workspace(self) -> None:
        self.start()
        other_workspace = self.root / "other-workspace"
        other_workspace.mkdir()
        original = self.state_path().read_bytes()
        with self.assertRaises(worklog.WorklogError):
            self.submit(workspace=other_workspace)
        self.assertEqual(self.state_path().read_bytes(), original)
        self.assertEqual(list(other_workspace.iterdir()), [])
        self.assertFalse(self.diary.exists())

    def parallel_events(self, events: list[dict]) -> None:
        child = (
            "import importlib.util,json,os,sys; from datetime import datetime; "
            "s=importlib.util.spec_from_file_location('child_worklog',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "p=json.loads(sys.argv[2]); t=datetime.fromisoformat(sys.argv[3]); "
            "print(json.dumps(m.submit_entry(p['document'],p['session_id'],p['turn_id'],"
            "os.environ,now=t) if 'document' in p else m.handle_event(p,os.environ,t)))"
        )
        environment = os.environ.copy()
        for key in ("CODEX_WORKLOG_DIR", "CODEX_WORKLOG_ENFORCEMENT", "CODEX_WORKLOG_LANGUAGE"):
            environment.pop(key, None)
        environment.update(self.environment)
        processes = [
            subprocess.Popen(
                [sys.executable, "-B", "-c", child, str(SCRIPT),
                 json.dumps(event), self.now.isoformat()],
                cwd=self.workspace, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for event in events
        ]
        try:
            for process, event in zip(processes, events):
                stdout, stderr = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 0, stderr)
                result = json.loads(stdout)
                self.assertNotIn("systemMessage", result, result)
                if "document" in event:
                    self.assertTrue(result["recorded"], result)
                    self.assertFalse(result["staged"], result)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_parallel_stop_retries_append_each_block_once(self) -> None:
        self.stage()
        self.parallel_events([self.event("Stop")] * 6)
        rendered = self.diary.read_text()
        self.assertEqual(rendered.count("Validated safe diary storage"), 1)
        self.assertEqual(rendered.count("<!-- codex-worklog-entry:"), 1)

    def test_parallel_submit_and_stop_retries_append_each_block_once(self) -> None:
        self.stage()
        self.parallel_events([
            self.event("submit") | {"document": self.document()} if index % 2
            else self.event("Stop") for index in range(6)
        ])
        rendered = self.diary.read_text()
        self.assertEqual(rendered.count("Validated safe diary storage"), 1)
        self.assertEqual(rendered.count("<!-- codex-worklog-entry:"), 1)

    def test_parallel_submissions_do_not_overwrite_each_others_blocks(self) -> None:
        sessions = [f"parallel-{index}" for index in range(6)]
        for session in sessions:
            self.start(session)
        self.parallel_events([
            self.event("submit", session) | {
                "document": self.document(f"Completed independent storage check {index}")
            } for index, session in enumerate(sessions)
        ])
        diaries = list((self.workspace / ".dev-diary").rglob("*.md"))
        self.assertEqual(diaries, [self.diary])
        rendered = self.diary.read_text()
        for index in range(6):
            self.assertEqual(rendered.count(f"Completed independent storage check {index}"), 1)

    def test_replayed_pending_state_deduplicates_markers_beyond_128_kib(self) -> None:
        self.stage()
        staged_state = self.state_path().read_bytes()
        self.handle("Stop")
        with self.diary.open("ab") as stream:
            stream.write(b"\nHistorical appendix.\n" * 8000)
        original = self.diary.read_bytes()
        # Simulate a crash after diary persistence, before the state update.
        self.state_path().write_bytes(staged_state)
        self.handle("Stop")
        self.assertEqual(self.diary.read_bytes(), original)
        self.assertEqual(original.count(b"<!-- codex-worklog-entry:"), 1)

    def test_secret_values_are_removed_before_state_or_diary_persistence(self) -> None:
        document = self.document()
        document["entries"][0]["checks"] = [
            "Checked token=worklog-synthetic-secret-canary without exposing it.",
            "The report SHA-256 is " + "a1" * 32 + ".",
        ]
        self.stage(document=document)
        staged_files = [path for path in self.plugin_data.rglob("*") if path.is_file()]
        for path in staged_files:
            self.assertNotIn(b"worklog-synthetic-secret-canary", path.read_bytes())
        self.handle("Stop")
        rendered = self.diary.read_text()
        self.assertNotIn("worklog-synthetic-secret-canary", rendered)
        self.assertIn("a1" * 32, rendered)

    def test_commands_and_links_do_not_persist_credential_values(self) -> None:
        document = self.document()
        canaries = (
            "command-token-canary", "command-password-canary",
            "ZmFrZS1iYXNpYy1jYW5hcnk=", "ftp-password-canary", "upper-password-canary",
            "uri-password-canary",
        )
        document["entries"][0]["checks"] = [
            "`client --token command-token-canary --check`",
            "`client --password 'command-password-canary' --check`",
            '`curl -H "Authorization: Basic ZmFrZS1iYXNpYy1jYW5hcnk=" https://example.test`',
            "`psql postgresql://login:uri-password-canary@example.test/db`",
        ]
        document["entries"][0]["artifacts"] = [
            "[report](ftp://login:ftp-password-canary@example.test/report)",
            "[report](HTTPS://login:upper-password-canary@example.test/report)",
        ]
        self.stage(document=document)
        staged = self.state_path().read_text()
        for canary in canaries:
            with self.subTest(stage="private staging", canary=canary):
                self.assertFalse(canary in staged, "Credential canary persisted in staging")
        result = self.handle("Stop")
        self.assertNotIn("systemMessage", result, result)
        rendered = self.diary.read_text()
        for canary in canaries:
            with self.subTest(stage="daily diary", canary=canary):
                self.assertFalse(canary in rendered, "Credential canary persisted in diary")

    def test_extensionless_artifact_links_survive_staging_and_commit_revalidation(self) -> None:
        self.start()
        document = self.document()
        document["entries"][0]["artifacts"] = [
            "[license](LICENSE)", "[artifacts](artifacts)",
        ]
        self.submit(document)
        result = self.handle("Stop")
        self.assertNotIn("systemMessage", result, result)
        rendered = self.diary.read_text()
        self.assertIn("[license](<../../../LICENSE>)", rendered)
        self.assertIn("[artifacts](<../../../artifacts>)", rendered)
        self.handle("Stop")
        self.assertEqual(self.diary.read_text(), rendered)

    def test_malformed_private_state_is_rejected_without_writes(self) -> None:
        self.stage()
        original = self.state_path().read_bytes()
        cases = (
            ("null turn", "SessionEnd"),
            ("missing submitted_at", "Stop"),
            ("missing turn_id", "Stop"),
            ("different turn_id", "Stop"),
            ("injected turn_id", "Stop"),
            ("unknown status", "Stop"),
            ("staged skip", "Stop"),
            ("directory traversal", "Stop"),
        )
        for case, event in cases:
            with self.subTest(case=case):
                self.diary.unlink(missing_ok=True)
                state = json.loads(original)
                key = next(iter(state["turns"]))
                turn = state["turns"][key]
                if case == "null turn":
                    state["turns"][key] = None
                elif case.startswith("missing "):
                    turn.pop(case.removeprefix("missing "))
                elif case == "different turn_id":
                    turn["turn_id"] = "another-turn"
                elif case == "injected turn_id":
                    turn["turn_id"] = "one -->\nINJECTED-STATE-CANARY\n<!--"
                elif case == "unknown status":
                    turn["status"] = "unknown-status"
                elif case == "staged skip":
                    turn["submission"] = {"skip": "no_material_work"}
                elif case == "directory traversal":
                    state["directory"] = "../outside-diary"
                poisoned = json.dumps(state).encode()
                self.state_path().write_bytes(poisoned)
                result = self.handle(event)
                self.assertIn("systemMessage", result)
                self.assertEqual(self.state_path().read_bytes(), poisoned)
                self.assertFalse(self.diary.exists())
                self.assertFalse((self.root / "outside-diary").exists())

    def test_atomic_write_failures_preserve_prefix_and_allow_retry(self) -> None:
        self.stage()
        self.handle("Stop")
        real_fsync, real_replace = os.fsync, os.replace
        boundaries = ("file fsync", "replace") + (("directory fsync",) if os.name != "nt" else ())
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                turn_id = boundary.replace(" ", "-")
                title = f"Completed storage recovery check for {boundary}"
                self.stage(title=title, turn=turn_id)
                staged_state = self.state_path().read_bytes()
                prefix = self.diary.read_bytes()

                def fail_fsync(fd: int) -> None:
                    is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
                    if (boundary == "file fsync" and not is_directory) or (
                        boundary == "directory fsync" and is_directory
                    ):
                        raise OSError("simulated durability failure")
                    real_fsync(fd)

                def fail_replace(source: object, destination: object, *args: object, **kwargs: object) -> None:
                    if boundary == "replace" and Path(os.fsdecode(destination)).name == self.diary.name:
                        raise OSError("simulated atomic replacement failure")
                    real_replace(source, destination, *args, **kwargs)

                with mock.patch.object(worklog.os, "fsync", side_effect=fail_fsync), mock.patch.object(
                    worklog.os, "replace", side_effect=fail_replace
                ):
                    result = self.handle("Stop", turn=turn_id)
                self.assertIn("systemMessage", result)
                self.assertEqual(self.state_path().read_bytes(), staged_state)
                if boundary == "directory fsync" and os.name != "nt":
                    self.assertTrue(self.diary.read_bytes().startswith(prefix))
                    self.assertEqual(self.diary.read_text().count(title), 1)
                else:
                    self.assertEqual(self.diary.read_bytes(), prefix)
                self.assertEqual(list(self.diary.parent.glob("*.tmp")), [])
                retry = self.handle("Stop", turn=turn_id)
                self.assertNotIn("systemMessage", retry, retry)
                self.assertTrue(self.diary.read_bytes().startswith(prefix))
                self.assertEqual(self.diary.read_text().count(title), 1)

    def test_identical_resubmission_after_state_failure_keeps_commit_recoverable(self) -> None:
        self.stage()
        staged_state = self.state_path().read_bytes()
        real_replace = os.replace

        def fail_state_replace(source: object, destination: object, *args: object, **kwargs: object) -> None:
            if Path(os.fsdecode(destination)).name == self.state_path().name:
                raise OSError("simulated state replacement failure")
            real_replace(source, destination, *args, **kwargs)

        with mock.patch.object(worklog.os, "replace", side_effect=fail_state_replace):
            with self.assertRaises(OSError):
                self.submit()
        self.assertEqual(self.state_path().read_bytes(), staged_state)
        committed = self.diary.read_bytes()
        worklog.submit_entry(
            self.document(), "storage-session", "one",
            environment=self.environment, workspace=self.workspace,
            now=self.now + timedelta(minutes=1),
        )
        retry = self.handle("Stop")
        self.assertNotIn("systemMessage", retry, retry)
        self.assertEqual(self.diary.read_bytes(), committed)

    @unittest.skipUnless(os.name != "nt" and hasattr(os, "O_NOFOLLOW"), "Emulates the no-O_NOFOLLOW fallback with an unprivileged POSIX symlink")
    def test_portable_open_rejects_dangling_symlink_before_creating_target(self) -> None:
        store = self.root / "portable-store"
        outside = self.root / "must-not-be-created"
        with worklog._Directory(store, create=True) as directory:
            # Exercise the pathname fallback used where descriptor-relative opens
            # and O_NOFOLLOW are unavailable, without pretending this is native Windows QA.
            directory.close()
            (store / "day.lock").symlink_to(outside)
            with mock.patch.object(worklog.os, "O_NOFOLLOW", 0):
                with self.assertRaises(worklog.WorklogError):
                    directory.open("day.lock", os.O_RDWR | os.O_CREAT)
        self.assertFalse(outside.exists())

    @unittest.skipIf(os.name == "nt", "POSIX descriptor-relative rename regression")
    def test_directory_swap_during_replace_cannot_write_outside_workspace(self) -> None:
        self.start()
        outside = self.root / "outside-month"
        outside.mkdir()
        external = outside / self.diary.name
        original = b"# Existing outside document\n"
        external.write_bytes(original)
        replace = os.replace
        swapped = False

        def swap_parent(source: object, destination: object, *args: object, **kwargs: object) -> None:
            nonlocal swapped
            if Path(os.fsdecode(destination)).name == self.diary.name and not swapped:
                swapped = True
                self.diary.parent.rename(self.diary.parent.with_name("preserved-month"))
                self.diary.parent.symlink_to(outside, target_is_directory=True)
            replace(source, destination, *args, **kwargs)

        with mock.patch.object(worklog.os, "replace", side_effect=swap_parent):
            self.submit()
        self.assertTrue(swapped, "The atomic diary replacement must be exercised")
        self.assertEqual(external.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
