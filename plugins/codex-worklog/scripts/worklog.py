#!/usr/bin/env python3
"""Lifecycle hook for the Codex Worklog plugin.

The hook stores only session metadata in PLUGIN_DATA. User prompts, tool inputs,
tool output, and transcripts are deliberately not copied into the worklog.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping


DEFAULT_DIRECTORY = ".dev-diary"
DEFAULT_ENFORCEMENT = "strict"
ALLOWED_ENFORCEMENT = {"strict", "advisory", "off"}
TAIL_BYTES = 128 * 1024
MAX_INLINE_CHARS = 2048
MAX_STATE_BYTES = 1024 * 1024


class WorklogError(RuntimeError):
    """Expected configuration or filesystem error."""


def _now() -> datetime:
    return datetime.now().astimezone()


def _token(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]


def _unsafe_inline_character(character: str) -> bool:
    return unicodedata.category(character) in {"Cc", "Cf", "Cs", "Zl", "Zp"}


def _safe_inline(value: object) -> str:
    text = str(value)
    sanitized = "".join(
        " " if _unsafe_inline_character(character) else character for character in text
    ).replace("`", "'")
    if len(sanitized) > MAX_INLINE_CHARS:
        return f"{sanitized[: MAX_INLINE_CHARS - 1]}…"
    return sanitized


def _path_is_context_safe(path: Path) -> bool:
    value = str(path)
    return (
        len(value) <= MAX_INLINE_CHARS
        and "`" not in value
        and not any(_unsafe_inline_character(character) for character in value)
    )


def _private_mode(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        # Windows and some network filesystems do not expose POSIX modes.
        pass


def _ensure_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise WorklogError(f"refusing symbolic link for private plugin data: {path}")
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        raise WorklogError(
            f"unable to create private directory {path}: {error}"
        ) from error
    if path.is_symlink() or not path.is_dir():
        raise WorklogError(f"private path is not a safe directory: {path}")
    _private_mode(path, 0o700)


def _ensure_workspace_directory(workspace: Path, relative_path: Path) -> Path:
    current = workspace
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise WorklogError(f"refusing symbolic link in the worklog path: {current}")
        if current.exists() and not current.is_dir():
            raise WorklogError(f"worklog path component is not a directory: {current}")
        try:
            current.mkdir(mode=0o700, exist_ok=True)
        except OSError as error:
            raise WorklogError(
                f"unable to create worklog directory {current}: {error}"
            ) from error
        _private_mode(current, 0o700)
    return current


def _validate_worklog_path(workspace: Path, path: Path) -> Path:
    workspace = workspace.absolute()
    path = path.absolute()
    if not _path_is_context_safe(path):
        raise WorklogError("worklog path is unsafe to expose to the model")
    try:
        relative_path = path.relative_to(workspace)
    except ValueError as error:
        raise WorklogError(
            f"worklog path escapes the session working directory: {path}"
        ) from error
    current = workspace
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise WorklogError(f"refusing symbolic link in the worklog path: {current}")
    try:
        path.resolve(strict=False).relative_to(workspace.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise WorklogError(
            f"worklog path escapes the session working directory: {path}"
        ) from error
    try:
        path_status = path.lstat()
    except OSError as error:
        raise WorklogError(f"worklog file is unavailable: {path}") from error
    if stat.S_ISLNK(path_status.st_mode):
        raise WorklogError(f"refusing symbolic link for the worklog file: {path}")
    if not stat.S_ISREG(path_status.st_mode):
        raise WorklogError(f"worklog path is not a regular file: {path}")
    if path_status.st_nlink != 1:
        raise WorklogError(f"refusing hard-linked worklog file: {path}")
    return path


def _open_regular_file(path: Path, flags: int) -> int:
    secure_flags = flags
    if hasattr(os, "O_CLOEXEC"):
        secure_flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        secure_flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        secure_flags |= os.O_BINARY
    try:
        descriptor = os.open(path, secure_flags)
    except OSError as error:
        raise WorklogError(f"unable to open regular file {path}: {error}") from error
    try:
        opened_status = os.fstat(descriptor)
        current_status = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(opened_status.st_mode)
            or opened_status.st_nlink != 1
            or stat.S_ISLNK(current_status.st_mode)
            or (opened_status.st_dev, opened_status.st_ino)
            != (current_status.st_dev, current_status.st_ino)
        ):
            raise WorklogError(f"file changed or is linked while opening: {path}")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _read_prefix(path: Path, limit: int) -> str:
    descriptor = _open_regular_file(path, os.O_RDONLY)
    try:
        with os.fdopen(descriptor, "r", encoding="utf-8", errors="strict") as stream:
            return stream.read(limit)
    except (OSError, UnicodeError) as error:
        raise WorklogError(f"unable to inspect regular file {path}: {error}") from error


def _append_text(path: Path, text: str) -> None:
    descriptor = _open_regular_file(path, os.O_WRONLY | os.O_APPEND)
    try:
        with os.fdopen(descriptor, "a", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        raise WorklogError(f"unable to append the worklog: {error}") from error
    _private_mode(path, 0o600)


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
    if not path.exists() and not path.is_symlink():
        return None
    try:
        raw_payload = _read_prefix(path, MAX_STATE_BYTES + 1)
        if len(raw_payload.encode("utf-8")) > MAX_STATE_BYTES:
            raise WorklogError(f"plugin state file is too large: {path}")
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as error:
        raise WorklogError(f"plugin state file is invalid JSON: {path}") from error
    if not isinstance(payload, dict):
        raise WorklogError(f"plugin state file must contain a JSON object: {path}")
    closed = payload.get("closed")
    if "closed" in payload and not isinstance(closed, bool):
        raise WorklogError("plugin state contains an invalid closed flag")
    end_count = payload.get("end_count")
    if "end_count" in payload and (
        isinstance(end_count, bool) or not isinstance(end_count, int) or end_count < 0
    ):
        raise WorklogError("plugin state contains an invalid session end counter")
    for key in ("last_turn_token", "last_verified_turn_token"):
        token = payload.get(key)
        if key in payload and (
            not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{16}", token)
        ):
            raise WorklogError(f"plugin state contains an invalid {key}")
    previous = payload.get("previous_worklog_path")
    if previous is not None and not isinstance(previous, str):
        raise WorklogError("plugin state contains an invalid previous worklog path")
    return payload


def _plugin_data(environment: Mapping[str, str]) -> Path:
    raw_path = environment.get("PLUGIN_DATA") or environment.get("CLAUDE_PLUGIN_DATA")
    if not isinstance(raw_path, str) or not raw_path:
        raise WorklogError("PLUGIN_DATA is unavailable; no workspace file was written")
    try:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        _ensure_private_directory(path)
    except WorklogError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise WorklogError(f"PLUGIN_DATA is not a usable path: {error}") from error
    return path.absolute()


def _workspace(payload: Mapping[str, Any]) -> Path:
    raw_path = payload.get("cwd")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise WorklogError("the hook event did not include a working directory")
    if "\x00" in raw_path:
        raise WorklogError("the working directory path is invalid: embedded null byte")
    try:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.absolute()
        is_directory = path.is_dir()
    except (OSError, RuntimeError, ValueError) as error:
        raise WorklogError(f"the working directory path is invalid: {error}") from error
    if not is_directory:
        raise WorklogError(f"the session working directory does not exist: {path}")
    if not _path_is_context_safe(path):
        raise WorklogError(
            "the working directory path contains unsafe model-context characters"
        )
    return path


def _worklog_directory_name(environment: Mapping[str, str]) -> str:
    raw_value = environment.get("CODEX_WORKLOG_DIR", DEFAULT_DIRECTORY)
    if not isinstance(raw_value, str):
        raise WorklogError(
            "CODEX_WORKLOG_DIR must be a safe, non-empty relative path without '..'"
        )
    raw_name = raw_value.strip()
    candidate = Path(raw_name)
    windows_candidate = PureWindowsPath(raw_name)
    if (
        not raw_name
        or candidate.is_absolute()
        or windows_candidate.is_absolute()
        or bool(windows_candidate.drive)
        or bool(windows_candidate.root)
        or raw_name in {".", ".."}
        or ".." in candidate.parts
        or "\\" in raw_name
        or ":" in raw_name
        or "`" in raw_name
        or any(_unsafe_inline_character(character) for character in raw_name)
    ):
        raise WorklogError(
            "CODEX_WORKLOG_DIR must be a safe, non-empty relative path without '..'"
        )
    return raw_name


def _enforcement(environment: Mapping[str, str]) -> str:
    value = environment.get("CODEX_WORKLOG_ENFORCEMENT", DEFAULT_ENFORCEMENT)
    if not isinstance(value, str):
        raise WorklogError("CODEX_WORKLOG_ENFORCEMENT must be strict, advisory, or off")
    value = value.strip().lower()
    if value not in ALLOWED_ENFORCEMENT:
        raise WorklogError("CODEX_WORKLOG_ENFORCEMENT must be strict, advisory, or off")
    return value


def _state_path(plugin_data: Path, session_id: str) -> Path:
    sessions = plugin_data / "sessions"
    _ensure_private_directory(sessions)
    return sessions / f"{_token(session_id, 24)}.json"


def _find_previous_worklog(root: Path) -> Path | None:
    try:
        resolved_root = root.resolve(strict=True)
        candidates: list[Path] = []
        for path in root.rglob("*.md"):
            try:
                path_status = path.lstat()
                path.resolve(strict=True).relative_to(resolved_root)
                if (
                    not stat.S_ISREG(path_status.st_mode)
                    or path_status.st_nlink != 1
                    or not _path_is_context_safe(path)
                    or not _read_prefix(path, 64).startswith("# Codex Worklog\n")
                ):
                    continue
                candidates.append(path)
            except (OSError, ValueError, WorklogError):
                continue
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
    session_token = _token(session_id, 12)
    filename = f"{now:%Y-%m-%d--%H%M%S}--{session_token}.md"
    candidate_path = workspace / relative_root / f"{now:%Y}" / f"{now:%m}" / filename
    if not _path_is_context_safe(candidate_path):
        raise WorklogError("worklog path is unsafe to expose to the model")
    root = _ensure_workspace_directory(workspace, relative_root)
    previous = _find_previous_worklog(root) if root.is_dir() else None
    daily_root = _ensure_workspace_directory(
        workspace, relative_root / f"{now:%Y}" / f"{now:%m}"
    )
    path = daily_root / filename
    model_name = model if isinstance(model, str) and model else "unknown"
    header = (
        "# Codex Worklog\n\n"
        f"- Started: {now.isoformat(timespec='seconds')}\n"
        f"- Workspace: `{_safe_inline(workspace)}`\n"
        f"- Session: `{session_token}`\n"
        f"- Model: `{_safe_inline(model_name)}`\n\n"
        "## Timeline\n"
    )
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(header)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        _validate_worklog_path(workspace, path)
        existing_header = _read_prefix(path, 4096)
        if f"- Session: `{session_token}`" not in existing_header:
            raise WorklogError(
                f"existing worklog has an unexpected session marker: {path}"
            )
    except OSError as error:
        raise WorklogError(
            f"unable to create the workspace worklog: {error}"
        ) from error
    _private_mode(path, 0o600)
    return path.absolute(), previous.absolute() if previous else None


def _state_worklog_path(state: Mapping[str, Any], payload: Mapping[str, Any]) -> Path:
    diary_value = state.get("worklog_path")
    workspace_value = state.get("workspace")
    if not isinstance(diary_value, str) or not isinstance(workspace_value, str):
        raise WorklogError("plugin state is missing the workspace or worklog path")
    workspace = _workspace(payload)
    if Path(workspace_value).absolute() != workspace:
        raise WorklogError(
            "stored workspace does not match the current session working directory"
        )
    return _validate_worklog_path(workspace, Path(diary_value))


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
    if state is not None:
        _state_worklog_path(state, payload)
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
    descriptor = _open_regular_file(path, os.O_RDONLY)
    try:
        with os.fdopen(descriptor, "rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - TAIL_BYTES), os.SEEK_SET)
            return encoded_marker in stream.read()
    except OSError as error:
        raise WorklogError(f"unable to inspect the worklog tail: {error}") from error


def _previous_worklog_for_context(state: Mapping[str, Any]) -> Path | None:
    previous = state.get("previous_worklog_path")
    workspace = state.get("workspace")
    current = state.get("worklog_path")
    if (
        not isinstance(previous, str)
        or not isinstance(workspace, str)
        or previous == current
    ):
        return None
    try:
        path = _validate_worklog_path(Path(workspace), Path(previous))
        if not _read_prefix(path, 64).startswith("# Codex Worklog\n"):
            return None
        return path
    except WorklogError:
        return None


def _context_recovery_text(state: Mapping[str, Any], source: object) -> str:
    worklog_path = _safe_inline(state["worklog_path"])
    source_name = source if isinstance(source, str) and source else "unknown"
    previous = _previous_worklog_for_context(state)
    previous_text = (
        " If older decisions are needed, inspect the newest relevant entries, starting with "
        f"`{_safe_inline(previous)}`."
        if previous is not None
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
        f"Session start source: `{_safe_inline(source_name)}`. Do not add the worklog to Git "
        "unless the user explicitly wants it versioned."
    )


def _turn_context_text(path: str, marker: str) -> str:
    return (
        f"Before the final answer for this turn, append one concise entry to `{_safe_inline(path)}`. "
        "Use this shape: `### HH:MM — concise outcome`, followed by Context, Actions, Changes, "
        "Decisions (including why), Verification, and Next. State explicitly when there were no "
        "material changes. Before appending, refuse if the path is no longer a regular, single-link "
        "file inside the session workspace. Append only; never rewrite previous entries. Redact "
        "secrets and avoid raw "
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
    if state is None:
        return {}
    if state.get("closed") is True:
        return {}
    path = _state_worklog_path(state, payload)
    turn_id = payload.get("turn_id")
    turn_token = _token(turn_id) if isinstance(turn_id, str) and turn_id else None
    if not turn_token:
        stored_token = state.get("last_turn_token")
        turn_token = stored_token if isinstance(stored_token, str) else None
    if not turn_token:
        return {}
    marker = _marker(turn_token)
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
    if state is None:
        return {}
    if state.get("closed") is True:
        return {}
    path = _state_worklog_path(state, payload)
    stored_end_count = state.get("end_count", 0)
    if (
        isinstance(stored_end_count, bool)
        or not isinstance(stored_end_count, int)
        or stored_end_count < 0
    ):
        raise WorklogError("plugin state contains an invalid session end counter")
    end_count = stored_end_count + 1
    marker = f"<!-- codex-worklog-session-end:{end_count} -->"
    if not _contains_recent_marker(path, marker):
        entry = (
            f"\n\n### {now:%H:%M} — Session checkpoint\n\n"
            f"- Outcome: Codex session ended or became inactive at {now.isoformat(timespec='seconds')}.\n\n"
            f"{marker}\n"
        )
        _append_text(path, entry)
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
        return {"systemMessage": f"Codex Worklog: {_safe_inline(error)}."}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
        response = handle_event(payload)
    except (json.JSONDecodeError, ValueError) as error:
        response = {
            "systemMessage": f"Codex Worklog received invalid hook input: {error}."
        }
    except Exception as error:  # Defensive boundary: hooks must not crash Codex.
        print(
            f"Codex Worklog internal error: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        response = {"systemMessage": "Codex Worklog encountered an internal error."}
    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
