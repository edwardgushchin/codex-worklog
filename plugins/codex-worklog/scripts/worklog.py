#!/usr/bin/env python3
"""Lifecycle hook for the Codex Worklog plugin.

The hook stores only session metadata in PLUGIN_DATA. User prompts, tool inputs,
tool output, and transcripts are deliberately not copied into the worklog.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


DEFAULT_DIRECTORY = ".dev-diary"
DEFAULT_ENFORCEMENT = "strict"
ALLOWED_ENFORCEMENT = {"strict", "advisory", "off"}
TAIL_BYTES = 128 * 1024


class WorklogError(RuntimeError):
    """Expected configuration or filesystem error."""


def _now() -> datetime:
    return datetime.now().astimezone()


def _token(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]


def _safe_inline(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("`", "'")


def _private_mode(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        # Windows and some network filesystems do not expose POSIX modes.
        pass


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _private_mode(path, 0o700)


def _ensure_workspace_directory(workspace: Path, relative_path: Path) -> Path:
    current = workspace
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise WorklogError(f"refusing symbolic link in the worklog path: {current}")
        if current.exists() and not current.is_dir():
            raise WorklogError(f"worklog path component is not a directory: {current}")
        current.mkdir(exist_ok=True)
        _private_mode(current, 0o700)
    return current


def _validate_worklog_path(workspace: Path, path: Path) -> Path:
    workspace = workspace.absolute()
    path = path.absolute()
    try:
        relative_path = path.relative_to(workspace)
    except ValueError as error:
        raise WorklogError(f"worklog path escapes the session working directory: {path}") from error
    current = workspace
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise WorklogError(f"refusing symbolic link in the worklog path: {current}")
    try:
        path.resolve(strict=False).relative_to(workspace.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise WorklogError(f"worklog path escapes the session working directory: {path}") from error
    if not path.is_file():
        raise WorklogError(f"worklog file is unavailable: {path}")
    return path


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _ensure_private_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _private_mode(temporary_path, 0o600)
        temporary_path.replace(path)
        _private_mode(path, 0o600)
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _plugin_data(environment: Mapping[str, str]) -> Path:
    raw_path = environment.get("PLUGIN_DATA") or environment.get("CLAUDE_PLUGIN_DATA")
    if not raw_path:
        raise WorklogError("PLUGIN_DATA is unavailable; no workspace file was written")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    _ensure_private_directory(path)
    return path.absolute()


def _workspace(payload: Mapping[str, Any]) -> Path:
    raw_path = payload.get("cwd")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise WorklogError("the hook event did not include a working directory")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.absolute()
    if not path.is_dir():
        raise WorklogError(f"the session working directory does not exist: {path}")
    return path


def _worklog_directory_name(environment: Mapping[str, str]) -> str:
    raw_name = environment.get("CODEX_WORKLOG_DIR", DEFAULT_DIRECTORY).strip()
    candidate = Path(raw_name)
    if (
        not raw_name
        or candidate.is_absolute()
        or raw_name in {".", ".."}
        or ".." in candidate.parts
        or "`" in raw_name
        or any(ord(character) < 32 for character in raw_name)
    ):
        raise WorklogError(
            "CODEX_WORKLOG_DIR must be a safe, non-empty relative path without '..'"
        )
    return raw_name


def _enforcement(environment: Mapping[str, str]) -> str:
    value = environment.get("CODEX_WORKLOG_ENFORCEMENT", DEFAULT_ENFORCEMENT)
    value = value.strip().lower()
    if value not in ALLOWED_ENFORCEMENT:
        raise WorklogError(
            "CODEX_WORKLOG_ENFORCEMENT must be strict, advisory, or off"
        )
    return value


def _state_path(plugin_data: Path, session_id: str) -> Path:
    return plugin_data / "sessions" / f"{_token(session_id, 24)}.json"


def _find_previous_worklog(root: Path) -> Path | None:
    try:
        candidates = [path for path in root.rglob("*.md") if path.is_file()]
    except OSError:
        return None
    if not candidates:
        return None
    try:
        return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))
    except OSError:
        return max(candidates, key=str)


def _new_worklog(
    workspace: Path,
    directory_name: str,
    session_id: str,
    model: object,
    now: datetime,
) -> tuple[Path, Path | None]:
    relative_root = Path(directory_name)
    root = _ensure_workspace_directory(workspace, relative_root)
    previous = _find_previous_worklog(root) if root.is_dir() else None
    daily_root = _ensure_workspace_directory(
        workspace, relative_root / f"{now:%Y}" / f"{now:%m}"
    )
    session_token = _token(session_id, 12)
    path = daily_root / f"{now:%Y-%m-%d--%H%M%S}--{session_token}.md"
    header = (
        "# Codex Worklog\n\n"
        f"- Started: {now.isoformat(timespec='seconds')}\n"
        f"- Workspace: `{_safe_inline(workspace)}`\n"
        f"- Session: `{session_token}`\n"
        f"- Model: `{_safe_inline(model or 'unknown')}`\n\n"
        "## Timeline\n"
    )
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(header)
    except FileExistsError:
        _validate_worklog_path(workspace, path)
        try:
            existing_header = path.read_text(encoding="utf-8")[:4096]
        except OSError as error:
            raise WorklogError(f"unable to inspect the existing worklog: {error}") from error
        if f"- Session: `{session_token}`" not in existing_header:
            raise WorklogError(f"existing worklog has an unexpected session marker: {path}")
    except OSError as error:
        raise WorklogError(f"unable to create the workspace worklog: {error}") from error
    _private_mode(path, 0o600)
    return path.absolute(), previous.absolute() if previous else None


def _session_state(
    payload: Mapping[str, Any],
    environment: Mapping[str, str],
    now: datetime,
) -> tuple[dict[str, Any], Path]:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise WorklogError("the hook event did not include a session id")
    plugin_data = _plugin_data(environment)
    state_path = _state_path(plugin_data, session_id)
    workspace = _workspace(payload)
    state = _load_json(state_path)
    if state:
        diary_value = state.get("worklog_path")
        workspace_value = state.get("workspace")
        if (
            isinstance(diary_value, str)
            and isinstance(workspace_value, str)
            and Path(workspace_value).absolute() == workspace
        ):
            _validate_worklog_path(workspace, Path(diary_value))
            state["closed"] = False
            state["last_seen_at"] = now.isoformat(timespec="seconds")
            _atomic_write_json(state_path, state)
            return state, state_path

    directory_name = _worklog_directory_name(environment)
    worklog_path, previous_path = _new_worklog(
        workspace=workspace,
        directory_name=directory_name,
        session_id=session_id,
        model=payload.get("model"),
        now=now,
    )
    state = {
        "closed": False,
        "end_count": 0,
        "last_seen_at": now.isoformat(timespec="seconds"),
        "previous_worklog_path": str(previous_path) if previous_path else None,
        "started_at": now.isoformat(timespec="seconds"),
        "workspace": str(workspace),
        "worklog_path": str(worklog_path),
    }
    _atomic_write_json(state_path, state)
    return state, state_path


def _marker(turn_token: str) -> str:
    return f"<!-- codex-worklog-turn:{turn_token} -->"


def _contains_recent_marker(path: Path, marker: str) -> bool:
    encoded_marker = marker.encode("utf-8")
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - TAIL_BYTES), os.SEEK_SET)
            return encoded_marker in stream.read()
    except OSError:
        return False


def _context_recovery_text(state: Mapping[str, Any], source: object) -> str:
    worklog_path = _safe_inline(state["worklog_path"])
    previous = state.get("previous_worklog_path")
    previous_text = (
        " If older decisions are needed, inspect the newest relevant entries, starting with "
        f"`{_safe_inline(previous)}`."
        if isinstance(previous, str) and previous
        else ""
    )
    return (
        "Codex Worklog is active. Keep an append-only semantic log at "
        f"`{worklog_path}`. Record what was done, when, why, material changes, decisions, "
        "verification, and next steps. Use the user's language. Never copy raw prompts, full tool "
        "output, transcripts, credentials, tokens, private keys, or unnecessary personal data. "
        "Before resuming work, after compaction, or whenever context is uncertain, read the tail of "
        "the current worklog first. Treat entries as historical notes: verify mutable repository, "
        f"filesystem, service, and external state before relying on them.{previous_text} "
        f"Session start source: `{_safe_inline(source or 'unknown')}`. Do not add the worklog to Git "
        "unless the user explicitly wants it versioned."
    )


def _turn_context_text(path: str, marker: str) -> str:
    return (
        f"Before the final answer for this turn, append one concise entry to `{_safe_inline(path)}`. "
        "Use this shape: `### HH:MM — concise outcome`, followed by Context, Actions, Changes, "
        "Decisions (including why), Verification, and Next. State explicitly when there were no "
        "material changes. Append only; never rewrite previous entries. Redact secrets and avoid raw "
        f"prompts or tool output. End the entry with this exact marker on its own line: `{marker}`"
    )


def _session_start(
    payload: Mapping[str, Any], environment: Mapping[str, str], now: datetime
) -> dict[str, Any]:
    state, _ = _session_state(payload, environment, now)
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": _context_recovery_text(state, payload.get("source")),
        }
    }


def _user_prompt(
    payload: Mapping[str, Any], environment: Mapping[str, str], now: datetime
) -> dict[str, Any]:
    state, state_path = _session_state(payload, environment, now)
    turn_id = payload.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id:
        raise WorklogError("the prompt hook did not include a turn id")
    turn_token = _token(turn_id)
    state["last_turn_started_at"] = now.isoformat(timespec="seconds")
    state["last_turn_token"] = turn_token
    _atomic_write_json(state_path, state)
    marker = _marker(turn_token)
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": _turn_context_text(state["worklog_path"], marker),
        }
    }


def _stop(
    payload: Mapping[str, Any], environment: Mapping[str, str], now: datetime
) -> dict[str, Any]:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return {}
    plugin_data = _plugin_data(environment)
    state_path = _state_path(plugin_data, session_id)
    state = _load_json(state_path)
    if not state:
        return {}
    if state.get("closed") is True:
        return {}
    diary_value = state.get("worklog_path")
    if not isinstance(diary_value, str):
        return {}
    turn_id = payload.get("turn_id")
    turn_token = _token(turn_id) if isinstance(turn_id, str) and turn_id else None
    if not turn_token:
        stored_token = state.get("last_turn_token")
        turn_token = stored_token if isinstance(stored_token, str) else None
    if not turn_token:
        return {}
    marker = _marker(turn_token)
    path = _validate_worklog_path(_workspace(payload), Path(diary_value))
    if _contains_recent_marker(path, marker):
        state["last_verified_at"] = now.isoformat(timespec="seconds")
        state["last_verified_turn_token"] = turn_token
        _atomic_write_json(state_path, state)
        return {}

    message = (
        "Codex Worklog has no entry for this turn. Append a semantic entry to "
        f"`{_safe_inline(path)}` now. "
        "Include what happened, why decisions were made, changes, verification, and next steps; "
        f"redact secrets and finish with `{marker}`. Do not rewrite earlier entries."
    )
    if payload.get("stop_hook_active"):
        return {
            "systemMessage": (
                "Codex Worklog could not verify the required turn marker after one continuation. "
                f"Expected `{marker}` in `{_safe_inline(path)}`."
            )
        }
    if _enforcement(environment) == "advisory":
        return {"systemMessage": message}
    return {"decision": "block", "reason": message}


def _session_end(
    payload: Mapping[str, Any], environment: Mapping[str, str], now: datetime
) -> dict[str, Any]:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return {}
    plugin_data = _plugin_data(environment)
    state_path = _state_path(plugin_data, session_id)
    state = _load_json(state_path)
    if not state:
        return {}
    if state.get("closed") is True:
        return {}
    diary_value = state.get("worklog_path")
    if not isinstance(diary_value, str):
        return {}
    end_count = int(state.get("end_count", 0)) + 1
    marker = f"<!-- codex-worklog-session-end:{end_count} -->"
    path = _validate_worklog_path(_workspace(payload), Path(diary_value))
    if not _contains_recent_marker(path, marker):
        entry = (
            f"\n\n### {now:%H:%M} — Session checkpoint\n\n"
            f"- Outcome: Codex session ended or became inactive at {now.isoformat(timespec='seconds')}.\n\n"
            f"{marker}\n"
        )
        try:
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(entry)
        except OSError as error:
            raise WorklogError(f"unable to append the session checkpoint: {error}") from error
        _private_mode(path, 0o600)
    state["closed"] = True
    state["end_count"] = end_count
    state["last_seen_at"] = now.isoformat(timespec="seconds")
    _atomic_write_json(state_path, state)
    return {}


def handle_event(
    payload: Mapping[str, Any],
    environment: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Handle one Codex hook event and return its JSON response."""

    active_environment = environment if environment is not None else os.environ
    event_name = payload.get("hook_event_name")
    try:
        enforcement = _enforcement(active_environment)
        if enforcement == "off":
            return {}
        current_time = now or _now()
        if event_name == "SessionStart":
            return _session_start(payload, active_environment, current_time)
        if event_name == "UserPromptSubmit":
            return _user_prompt(payload, active_environment, current_time)
        if event_name == "Stop":
            return _stop(payload, active_environment, current_time)
        if event_name == "SessionEnd":
            return _session_end(payload, active_environment, current_time)
        return {}
    except WorklogError as error:
        return {"systemMessage": f"Codex Worklog: {error}."}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
        response = handle_event(payload)
    except (json.JSONDecodeError, ValueError) as error:
        response = {"systemMessage": f"Codex Worklog received invalid hook input: {error}."}
    except Exception as error:  # Defensive boundary: hooks must not crash Codex.
        print(f"Codex Worklog internal error: {type(error).__name__}: {error}", file=sys.stderr)
        response = {"systemMessage": "Codex Worklog encountered an internal error."}
    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
