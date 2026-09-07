#!/usr/bin/env python3
"""Model-authored work blocks; deterministic validation and local daily storage.

The model submits semantic JSON before its final answer. Submission commits it;
Stop retries pending work. No facts are inferred from transcripts or tool output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import locale
import os
import re
import secrets
import shlex
import stat
import subprocess  # nosec B404 - list2cmdline only, no process execution.
import sys
import time
import unicodedata
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Iterator
from urllib.parse import unquote, urlsplit, urlunsplit

DEFAULT_DIRECTORY = ".dev-diary"
MAX_APPEND_INPUT_BYTES = 64 * 1024
MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_DAY_BYTES = 32 * 1024 * 1024
MAX_ITEM_CHARS = 4096
MAX_ITEMS = 32
MAX_ENTRIES = 8
LOCK_TIMEOUT = 1.0
TEXT_FIELDS = ("context", "changes", "decisions", "checks", "next_steps")
ENTRY_KEYS = {"title", *TEXT_FIELDS, "timeline", "artifacts", "supersedes"}
REQUIRED_KEYS = {"title", *TEXT_FIELDS, "timeline"}
SKIP_REASONS = {"acknowledgement", "no_material_work", "already_recorded"}
LABELS = {
    "en": ("Context", "Timeline", "Changes", "Decisions", "Checks", "Next steps"),
    "ru": ("Контекст", "Хронология", "Изменения", "Решения", "Проверки", "Следующие шаги"),
}
ACKNOWLEDGEMENTS = {
    "ок", "окей", "спасибо", "спасибо большое", "большое спасибо", "благодарю",
    "понял", "поняла", "поняли", "принято", "ясно", "всё ясно", "все ясно",
    "хорошо", "отлично", "супер", "спс", "ok", "okay", "thanks", "thank you",
    "thx", "understood", "got it", "sounds good",
}
LINK = re.compile(r"(?<!!)\[([^\]\n]*)\]\((<[^>\n]+>|[^)\n]+)\)")
URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s`<>\"()]+", re.I)
ABSOLUTE = re.compile(r"(?<![\w:/])(?:[A-Za-z]:[\\/]|\\\\|/(?!/)|~/)[^\s`<>\"()]+")
PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?(?:-----END [^-\n]*PRIVATE KEY-----|\Z)",
    re.S,
)
ASSIGNMENT = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|auth[_ -]?token|refresh[_ -]?token|"
    r"token|password|passwd|private[_ -]?key|client[_ -]?secret|secret|credentials?|"
    r"токен|пароль|секрет)\b\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|`[^`]*`|[^\s,;]+)"
)
KNOWN_SECRET = re.compile(
    r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    r"github_pat_[A-Za-z0-9_]{16,}|AKIA[A-Z0-9]{16}|"
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b"
)
AUTHORIZATION = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
SECRET_ARGUMENT = re.compile(
    r"(?i)(--(?:password|passwd|token|api-key|access-token|client-secret|secret)\b)"
    r"(?:\s+|=)(?:\"[^\"]*\"|'[^']*'|[^\s`]+)"
)
SECRET_PARAMETER = re.compile(r"auth|credential|key|password|secret|signature|token", re.I)


class WorklogError(RuntimeError):
    """A safe, user-visible contract failure (never includes submitted content)."""


def _now() -> datetime:
    return datetime.now().astimezone()


def _token(value: str, length: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _timestamp(now: datetime | None = None) -> datetime:
    value = now or _now()
    return value if value.tzinfo is not None else value.astimezone()


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None:
        raise WorklogError(f"{field} must be a non-empty host identifier")
    return value


def _language(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().split(":", 1)[0].split(".", 1)[0].split("@", 1)[0]
    if candidate.casefold() in {"c", "posix"}:
        return None
    if re.fullmatch(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*", candidate):
        return re.split(r"[-_]", candidate)[0].lower()
    return None


def _system_language(environment: Mapping[str, str]) -> str:
    override = environment.get("CODEX_WORKLOG_LANGUAGE")
    if override is not None:
        if not _language(override):
            raise WorklogError("CODEX_WORKLOG_LANGUAGE must be a language code")
        return _language(override) or "en"
    for key in ("LC_ALL", "LANGUAGE", "LC_MESSAGES", "LANG"):
        if _language(environment.get(key)):
            return _language(environment[key]) or "en"
    try:
        return _language(locale.getlocale()[0]) or "en"
    except (ValueError, locale.Error):
        return "en"


def _is_acknowledgement_prompt(value: object) -> bool:
    if not isinstance(value, str) or len(value.strip()) > 80:
        return False
    value = unicodedata.normalize("NFKC", value.strip()).casefold()
    if not value or any(c in value for c in "?¿⁇⁈⁉？"):
        return False
    if value in {"👍", "👌", "✅", "🙏"}:
        return True
    phrase = "".join(" " if unicodedata.category(c).startswith(("P", "S")) else c for c in value)
    return " ".join(phrase.split()) in ACKNOWLEDGEMENTS


def _absolute(value: object, label: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise WorklogError(f"{label} is unavailable")
    raw = str(value)
    if len(raw) > 4096 or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in raw):
        raise WorklogError(f"{label} contains unsafe characters")
    return Path(os.path.abspath(raw))


def _workspace(value: object) -> Path:
    path = _absolute(value, "session cwd")
    try:
        # A host-provided cwd may itself be an OS alias (/var on macOS).
        path = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise WorklogError("session cwd is unavailable") from error
    if not path.is_dir():
        raise WorklogError("session cwd must be a directory")
    return path


def _worklog_directory_name(environment: Mapping[str, str]) -> str:
    value = environment.get("CODEX_WORKLOG_DIR", DEFAULT_DIRECTORY)
    if not isinstance(value, str) or not value or len(value) > 256:
        raise WorklogError("CODEX_WORKLOG_DIR must be a bounded relative directory")
    parts = value.split("/")
    if (
        any(part in {"", ".", ".."} for part in parts)
        or any(c in value for c in "\\:`")
        or any(unicodedata.category(c).startswith("C") for c in value)
        or Path(value).is_absolute() or PureWindowsPath(value).drive
    ):
        raise WorklogError("CODEX_WORKLOG_DIR must be a safe relative directory")
    return value


def _plugin_data(environment: Mapping[str, str]) -> Path:
    return _absolute(environment.get("PLUGIN_DATA") or environment.get("CLAUDE_PLUGIN_DATA"), "PLUGIN_DATA")


def _linked(status: os.stat_result) -> bool:
    return stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & 0x400  # Windows reparse point.
    )


class _Directory:
    """Anchor every path component; keep Windows ancestors non-renamable."""

    def __init__(self, path: Path, create: bool = False):
        self.path = path
        self.fd: int | None = None
        self.handles: list[Any] = []
        self.kernel: Any = None
        try:
            if os.name == "nt":
                self._windows_open(create)
            else:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                self.fd = os.open(path.anchor, flags)
                for part in path.parts[1:]:
                    if create:
                        try:
                            os.mkdir(part, 0o700, dir_fd=self.fd)
                        except FileExistsError:
                            pass
                    child = os.open(part, flags, dir_fd=self.fd)
                    os.close(self.fd)
                    self.fd = child
        except (OSError, ValueError) as error:
            self.close()
            raise WorklogError("directory is unavailable, linked, or unsafe") from error

    def _windows_open(self, create: bool) -> None:
        import ctypes
        from ctypes import wintypes

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = (
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        )
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        current = Path(self.path.anchor)
        for part in self.path.parts[1:]:
            current /= part
            if create:
                current.mkdir(mode=0o700, exist_ok=True)
            # No FILE_SHARE_DELETE: an open ancestor cannot be renamed/replaced.
            handle = self.kernel.CreateFileW(str(current), 0x80, 3, None, 3, 0x02200000, None)
            if handle == ctypes.c_void_p(-1).value:
                raise OSError("unable to anchor directory")
            self.handles.append(handle)
            status = current.lstat()
            if _linked(status) or not stat.S_ISDIR(status.st_mode):
                raise OSError("linked directory")

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        for handle in reversed(self.handles):
            self.kernel.CloseHandle(handle)
        self.handles.clear()

    def __enter__(self) -> _Directory:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _name(self, name: str) -> str:
        if not name or name in {".", ".."} or any(c in name for c in "/\\\0"):
            raise WorklogError("invalid storage filename")
        return name

    def info(self, name: str) -> os.stat_result:
        name = self._name(name)
        if self.fd is not None:
            return os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        return (self.path / name).lstat()

    def open(self, name: str, flags: int, mode: int = 0o600) -> int:
        name = self._name(name)
        if flags & os.O_CREAT and not flags & os.O_EXCL:
            # Never create through a dangling leaf link, including on Windows.
            try:
                return self.open(name, flags | os.O_EXCL, mode)
            except FileExistsError:
                if _linked(self.info(name)):
                    raise WorklogError("storage file is linked")
                return self.open(name, flags & ~os.O_CREAT, mode)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            fd = os.open(name if self.fd is not None else self.path / name, flags, mode, dir_fd=self.fd)
        except (FileNotFoundError, FileExistsError):
            raise
        except OSError as error:
            raise WorklogError("storage file is unavailable or linked") from error
        try:
            opened, current = os.fstat(fd), self.info(name)
            if (
                not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or _linked(current)
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            ):
                raise WorklogError("storage file is linked or is not a regular file")
            return fd
        except BaseException:
            os.close(fd)
            raise

    def read(self, name: str, limit: int) -> tuple[bytes, os.stat_result] | None:
        try:
            fd = self.open(name, os.O_RDONLY)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, "rb") as stream:
            status = os.fstat(stream.fileno())
            if status.st_size > limit:
                raise WorklogError("storage file exceeds the size limit")
            raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise WorklogError("storage file exceeds the size limit")
            return raw, status

    def replace(self, name: str, raw: bytes, previous: os.stat_result | None) -> None:
        temporary = f".{name}.{secrets.token_hex(8)}.tmp"
        fd = self.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            with os.fdopen(fd, "wb") as stream:
                if previous is not None and hasattr(os, "fchmod"):
                    os.fchmod(stream.fileno(), stat.S_IMODE(previous.st_mode))
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                current = self.info(name)
            except FileNotFoundError:
                current = None
            if (current is None) != (previous is None) or (
                current is not None and previous is not None and (
                    _linked(current) or current.st_nlink != 1
                    or (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                    != (previous.st_dev, previous.st_ino, previous.st_size, previous.st_mtime_ns)
                )
            ):
                raise WorklogError("storage file changed outside the worklog lock")
            if self.fd is not None:
                os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
                os.fsync(self.fd)
            else:
                os.replace(self.path / temporary, self.path / name)
        finally:
            try:
                if self.fd is not None:
                    os.unlink(temporary, dir_fd=self.fd)
                else:
                    (self.path / temporary).unlink()
            except FileNotFoundError:
                pass


@contextmanager
def _locked(directory: _Directory, name: str) -> Iterator[None]:
    fd = directory.open(name, os.O_RDWR | os.O_CREAT)
    acquired = False
    try:
        if os.name == "nt" and os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
        deadline = time.monotonic() + LOCK_TIMEOUT
        while not acquired:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as error:
                if time.monotonic() >= deadline:
                    raise WorklogError("worklog is busy; submission remains staged for retry") from error
                time.sleep(0.02)
        opened, current = os.fstat(fd), directory.info(name)
        if _linked(current) or current.st_nlink != 1 or (
            opened.st_dev, opened.st_ino
        ) != (current.st_dev, current.st_ino):
            raise WorklogError("worklog lock was replaced")
        yield
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _json_bytes(value: Any) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise WorklogError("value must be bounded UTF-8 JSON") from error


def _json_object(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise WorklogError("duplicate JSON keys are not allowed")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise WorklogError("invalid UTF-8 JSON object") from error
    if not isinstance(value, dict):
        raise WorklogError("input must be a JSON object")
    return value


def _validate_turns(state: Mapping[str, Any]) -> None:
    turns = state["turns"]
    if len(turns) > 128:
        raise WorklogError("session has too many pending turns")
    for key, turn in turns.items():
        if not isinstance(turn, dict):
            raise WorklogError("invalid turn state")
        identity = _identity(turn.get("turn_id"), "stored turn_id")
        status = turn.get("status")
        if key != _token(identity) or not isinstance(status, str) or status not in {
            "open", "staged", "committed", "skipped", "missing",
        }:
            raise WorklogError("invalid turn identity or status")
        if status in {"staged", "committed"}:
            try:
                timestamp = datetime.fromisoformat(turn["submitted_at"])
            except (KeyError, TypeError, ValueError) as error:
                raise WorklogError("invalid staged timestamp") from error
            if timestamp.tzinfo is None or _language(turn.get("language")) != turn.get("language") or not turn.get("language"):
                raise WorklogError("invalid staged language or timezone")
            if not isinstance(turn.get("digest"), str) or re.fullmatch(r"[0-9a-f]{64}", turn["digest"]) is None:
                raise WorklogError("invalid submission digest")
        if status == "staged":
            document = turn.get("submission")
            if not isinstance(document, dict) or "entries" not in document:
                raise WorklogError("staged submission is missing")
            if hashlib.sha256(_json_bytes(document)).hexdigest() != turn["digest"]:
                raise WorklogError("staged submission does not match its digest")
        if status == "committed":
            ids = turn.get("entry_ids")
            if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_ENTRIES or ids != _entry_ids(state["session_id"], identity, len(ids)):
                raise WorklogError("invalid committed entry IDs")
    for field in ("last_turn_id", "tool_turn_id", "context_turn_id"):
        if field in state:
            _identity(state[field], f"stored {field}")
    if "session_language" in state and (
        not state["session_language"] or _language(state["session_language"]) != state["session_language"]
    ):
        raise WorklogError("invalid stored session language")


@contextmanager
def _session(
    session_id: str, workspace: Path, environment: Mapping[str, str],
    now: datetime, create: bool = False,
) -> Iterator[dict[str, Any]]:
    session_id = _identity(session_id, "session_id")
    root = _worklog_directory_name(environment)
    name = f"{_token(session_id)}.json"
    with _Directory(_plugin_data(environment) / "sessions-v2", create=create) as directory:
        with _locked(directory, f"{_token(session_id)}.lock"):
            previous = directory.read(name, MAX_STATE_BYTES)
            if previous is None:
                if not create:
                    raise WorklogError("session state is missing; wait for SessionStart/UserPromptSubmit")
                state: dict[str, Any] = {
                    "version": 2, "session_id": session_id, "workspace": str(workspace),
                    "directory": root, "turns": {}, "started_at": now.isoformat(),
                }
            else:
                state = _json_object(previous[0])
                if (
                    state.get("version") != 2 or state.get("session_id") != session_id
                    or state.get("workspace") != str(workspace)
                    or not isinstance(state.get("turns"), dict)
                ):
                    raise WorklogError("session state does not match this workspace, session, or diary root")
                _worklog_directory_name({"CODEX_WORKLOG_DIR": state.get("directory")})
                _validate_turns(state)
            before = _json_bytes(state) if previous else None
            yield state
            raw = _json_bytes(state)
            if len(raw) > MAX_STATE_BYTES:
                raise WorklogError("too many pending work blocks; commit staged work first")
            if raw != before:
                directory.replace(name, raw, previous[1] if previous else None)


def _private_path(value: str) -> bool:
    parts = value.replace("\\", "/").casefold().split("/")
    return any(
        p in {"private", ".ssh", ".gnupg", "credentials", "credentials.json", "id_rsa", "id_ed25519"}
        or p == ".env" or p.startswith(".env.") for p in parts
    )


def _local_reference(value: str, workspace: Path) -> str | None:
    value = unquote(value)
    if _private_path(value):
        return None
    suffix = ""
    match = re.fullmatch(r"(.+?):(\d+)(?::\d+)?", value)
    if match and not re.fullmatch(r"[A-Za-z]:", match.group(1)):
        value, suffix = match.group(1), f"#L{match.group(2)}"
    if value.startswith("~/"):
        return None
    if os.name != "nt" and (PureWindowsPath(value).drive or "\\" in value):
        return None
    candidate = Path(value)
    if ".." in candidate.parts:
        return None
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(workspace)
        except ValueError:
            return None
    if not candidate.parts or str(candidate) == ".":
        return None
    current = workspace
    for part in candidate.parts:
        current /= part
        try:
            if _linked(current.lstat()):
                return None
        except FileNotFoundError:
            # Deleted files and not-yet-created next-step paths remain useful references.
            pass
    return candidate.as_posix() + suffix


def _remote_reference(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            return None
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if SECRET_PARAMETER.search(unquote(parsed.query)) or SECRET_PARAMETER.search(unquote(parsed.fragment)):
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        return value
    except ValueError:
        return None


def _normalize_link(match: re.Match[str], workspace: Path) -> str:
    label, target = match.group(1), match.group(2).strip("<>")
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", target):
        normalized = _remote_reference(target)
    else:
        normalized = _local_reference(target, workspace)
    if normalized is None:
        return "[private or unsafe reference]"
    return f"[{label}](<{normalized}>)"


def _text(value: object, workspace: Path, label: str, limit: int = MAX_ITEM_CHARS) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise WorklogError(f"{label} must be non-empty text of at most {limit} characters")
    value = unicodedata.normalize("NFC", value.strip().replace("\r\n", "\n"))
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} and c != "\n" for c in value):
        raise WorklogError(f"{label} contains unsafe control characters")
    if "<!--" in value or "-->" in value or re.search(r"(?m)^\s*(?:#{1,6}\s|::|```|~~~)", value):
        raise WorklogError(f"{label} contains reserved Markdown structure")
    if re.search(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s+[^<>]*|\s*/?)>", LINK.sub(lambda m: m.group(1), value)):
        raise WorklogError(f"{label} contains raw HTML")
    value = PRIVATE_KEY.sub("[private key redacted]", value)
    value = ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[redacted]", value)
    value = AUTHORIZATION.sub(lambda m: f"{m.group(1)} [redacted]", value)
    value = SECRET_ARGUMENT.sub(lambda m: f"{m.group(1)}=[redacted]", value)
    value = KNOWN_SECRET.sub("[redacted]", value)
    # Preserve links/inline code as units so absolute paths containing spaces survive.
    units: list[str] = []

    def hold(text: str) -> str:
        units.append(text)
        return f"\x00{len(units) - 1}\x00"

    value = LINK.sub(lambda m: hold(_normalize_link(m, workspace)), value)

    def code(match: re.Match[str]) -> str:
        body = match.group(1)
        if body.startswith(("/", "~/", "\\\\")) or PureWindowsPath(body).drive:
            body = _local_reference(body, workspace) or "[private or external path]"
        elif _private_path(body):
            body = "[private path]"
        else:
            body = URL.sub(lambda m: _remote_reference(m.group(0)) or "[private link]", body)
            body = ABSOLUTE.sub(lambda m: _local_reference(m.group(0), workspace) or "[external path]", body)
        return hold(f"`{body}`")

    value = re.sub(r"`([^`\n]+)`", code, value)
    value = URL.sub(lambda m: hold(_remote_reference(m.group(0)) or "[private link]"), value)
    value = ABSOLUTE.sub(lambda m: _local_reference(m.group(0), workspace) or "[external path]", value)
    # Protect only our exact placeholders, after links/code are already held.
    # Holding them earlier would nest units inside units during inline parsing.
    value = re.sub(r"\[private (?:path|link|key redacted|or external path|or unsafe reference)\]",
                   lambda m: hold(m.group(0)), value, flags=re.I)
    value = re.sub(r"(?<!\w)(?:[\w.-]+/)*(?:private|\.ssh|\.gnupg|\.env)(?:/[^\s`]+)?", "[private path]", value, flags=re.I)
    value = re.sub(r"\x00(\d+)\x00", lambda m: units[int(m.group(1))], value)
    if len(value) > limit:
        raise WorklogError(f"{label} exceeds {limit} characters after sanitization; shorten the item")
    return value


def _items(value: object, workspace: Path, label: str, optional: bool = False) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_ITEMS or (not value and not optional):
        raise WorklogError(f"{label} must contain {'0' if optional else '1'}..{MAX_ITEMS} text items")
    return [_text(item, workspace, label) for item in value]


def _validate_document(document: Mapping[str, Any], workspace: Path) -> dict[str, Any]:
    if len(_json_bytes(document)) > MAX_APPEND_INPUT_BYTES:
        raise WorklogError("submission exceeds 64 KiB")
    if set(document) == {"skip"}:
        if not isinstance(document["skip"], str) or document["skip"] not in SKIP_REASONS:
            raise WorklogError("unknown skip reason")
        return dict(document)
    if set(document) - {"language", "entries"} or "entries" not in document:
        raise WorklogError("submission requires entries and optional language; paths and markers are not accepted")
    result: dict[str, Any] = {"entries": []}
    if "language" in document:
        language = _language(document["language"])
        if language is None:
            raise WorklogError("language must be a language code")
        result["language"] = language
    entries = document["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise WorklogError("entries must contain 1..8 independent work blocks")
    titles: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - ENTRY_KEYS or REQUIRED_KEYS - set(entry):
            raise WorklogError("each entry requires title and all six semantic sections")
        title = _text(entry["title"], workspace, "title", 160)
        if "\n" in title or len(title) < 12 or title.casefold().strip(".! ") in {
            "готово", "ты прав", "исправил", "переделал", "done", "completed", "work completed",
        }:
            raise WorklogError("title must name a self-contained concrete result")
        if title in titles:
            raise WorklogError("duplicate work block titles; consolidate the same work")
        titles.add(title)
        normalized = {"title": title}
        normalized.update({key: _items(entry[key], workspace, key) for key in TEXT_FIELDS})
        timeline = entry["timeline"]
        if not isinstance(timeline, list) or not 1 <= len(timeline) <= MAX_ITEMS:
            raise WorklogError("timeline requires 1..32 phases (use null for unknown time)")
        normalized["timeline"] = []
        for phase in timeline:
            if not isinstance(phase, dict) or set(phase) != {"time", "items"}:
                raise WorklogError("timeline phases require time and items")
            clock = phase["time"]
            if clock is not None:
                if not isinstance(clock, str):
                    raise WorklogError("timeline time must be HH:MM, timezone ISO date, or null")
                if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock) is None:
                    try:
                        parsed = datetime.fromisoformat(clock.removesuffix("Z") + "+00:00" if clock.endswith("Z") else clock)
                        if parsed.tzinfo is None:
                            raise ValueError
                        clock = parsed.isoformat()
                    except ValueError as error:
                        raise WorklogError("timeline time must be HH:MM, timezone ISO date, or null") from error
            normalized["timeline"].append({"time": clock, "items": _items(phase["items"], workspace, "timeline items")})
        normalized["artifacts"] = _items(entry.get("artifacts", []), workspace, "artifacts", optional=True)
        supersedes = entry.get("supersedes", [])
        if not isinstance(supersedes, list) or len(supersedes) > MAX_ITEMS or any(
            not isinstance(item, str) or re.fullmatch(r"[0-9a-f]{24}", item) is None for item in supersedes
        ):
            raise WorklogError("supersedes must contain generated 24-character entry IDs")
        normalized["supersedes"] = list(dict.fromkeys(supersedes))
        result["entries"].append(normalized)
    if len(_json_bytes(result)) > MAX_APPEND_INPUT_BYTES:
        raise WorklogError("normalized submission exceeds 64 KiB")
    return result


def _entry_ids(session_id: str, turn_id: str, count: int) -> list[str]:
    return [_token(f"{session_id}\0{turn_id}\0{index}") for index in range(count)]


def _link_from_diary(match: re.Match[str], depth: int) -> str:
    target = match.group(2).strip("<>")
    if target.lower().startswith(("https://", "http://")):
        return match.group(0)
    return f"[{match.group(1)}](<{'../' * depth}{target}>)"


def _bullet(value: str, depth: int, indent: str = "") -> str:
    value = LINK.sub(lambda m: _link_from_diary(m, depth), value)
    lines = value.splitlines()
    return f"{indent}- {lines[0]}\n" + "".join(f"{indent}  {line}\n" for line in lines[1:])


def _render_entry(entry: Mapping[str, Any], entry_id: str, state: Mapping[str, Any],
                  turn: Mapping[str, Any], language: str) -> str:
    timestamp = datetime.fromisoformat(turn["submitted_at"])
    offset = timestamp.strftime("%z")
    stamp = f"{timestamp:%Y-%m-%d %H:%M} {offset[:3]}:{offset[3:]}"
    labels = LABELS.get(language, LABELS["en"])
    depth = len(Path(state["directory"]).parts) + 2
    output = [f"\n## {stamp} — {entry['title']}\n\n",
              f"<!-- codex-worklog-session:{state['session_id']} turn:{turn['turn_id']} -->\n"]
    for key, label in zip(("context", "timeline", "changes", "decisions", "checks", "next_steps"), labels):
        output.append(f"\n### {label}\n\n")
        if key == "timeline":
            for phase in entry[key]:
                clock = phase["time"] or ("Время не зафиксировано" if language == "ru" else "Time not recorded")
                output.append(f"- `{clock}`\n")
                output.extend(_bullet(item, depth, "  ") for item in phase["items"])
        else:
            output.extend(_bullet(item, depth) for item in entry[key])
        if key == "decisions" and entry["supersedes"]:
            label = "Заменяет записи" if language == "ru" else "Supersedes entries"
            output.append(f"- {label}: " + ", ".join(f"`{i}`" for i in entry["supersedes"]) + ".\n")
        if key == "checks":
            output.extend(_bullet(item, depth) for item in entry["artifacts"])
    output.append(f"\n<!-- codex-worklog-entry:{entry_id} -->\n")
    return "".join(output)


def _check_supersedes(state: Mapping[str, Any], entries: list[dict[str, Any]], ids: list[str]) -> None:
    missing = {identity for entry in entries for identity in entry["supersedes"]}
    if missing.intersection(ids):
        raise WorklogError("entries cannot supersede themselves or the same submission")
    if not missing:
        return
    root = Path(state["workspace"]) / state["directory"]
    remaining = 128 * 1024 * 1024
    days = 0
    if root.exists():
        # ponytail: bounded scan only when correcting an entry; add an index if
        # real history reaches the 4096-day / 128 MiB lookup ceiling.
        with _Directory(root) as years:
            for year in sorted(os.listdir(years.fd if years.fd is not None else years.path), reverse=True):
                if re.fullmatch(r"\d{4}", year) is None:
                    continue
                with _Directory(root / year) as months:
                    for month in sorted(os.listdir(months.fd if months.fd is not None else months.path), reverse=True):
                        if re.fullmatch(r"(?:0[1-9]|1[0-2])", month) is None:
                            continue
                        with _Directory(root / year / month) as directory:
                            for name in sorted(os.listdir(directory.fd if directory.fd is not None else directory.path), reverse=True):
                                if re.fullmatch(rf"{year}-{month}-\d{{2}}\.md", name) is None:
                                    continue
                                days += 1
                                if days > 4096:
                                    raise WorklogError("supersedes history lookup exceeds 4096 days")
                                previous = directory.read(name, min(MAX_DAY_BYTES, remaining))
                                if previous is None:
                                    continue
                                raw = previous[0]
                                remaining -= len(raw)
                                if not raw.startswith(f"# Codex Worklog — {name[:-3]}\n".encode()):
                                    raise WorklogError("supersedes history has an unexpected daily header")
                                missing.difference_update(match.decode() for match in re.findall(
                                    rb"(?m)^<!-- codex-worklog-entry:([0-9a-f]{24}) -->$", raw,
                                ))
                                if not missing:
                                    return
    raise WorklogError("supersedes references an unknown entry in this workspace diary")


def _commit(state: dict[str, Any], turn: dict[str, Any]) -> bool:
    document = turn.get("submission")
    if not isinstance(document, dict):
        return False
    workspace = _workspace(state["workspace"])
    # Revalidate private staging too; its directory is trusted, its JSON still isn't.
    document = _validate_document(document, workspace)
    timestamp = datetime.fromisoformat(turn["submitted_at"])
    if timestamp.tzinfo is None:
        raise WorklogError("staged time is missing its timezone")
    date = timestamp.strftime("%Y-%m-%d")
    relative = Path(state["directory"]) / f"{timestamp:%Y}" / f"{timestamp:%m}"
    language = turn["language"]
    ids = _entry_ids(state["session_id"], turn["turn_id"], len(document["entries"]))
    _check_supersedes(state, document["entries"], ids)
    blocks = b"".join(_render_entry(entry, identity, state, turn, language).encode("utf-8")
                      for entry, identity in zip(document["entries"], ids))
    header = f"# Codex Worklog — {date}\n".encode("utf-8")
    name = f"{date}.md"
    with _Directory(workspace / relative, create=True) as directory:
        with _locked(directory, f".{date}.lock"):
            previous = directory.read(name, MAX_DAY_BYTES)
            raw = previous[0] if previous else header
            if not raw.startswith(header) or not raw.endswith(b"\n"):
                raise WorklogError("daily worklog has an unexpected header or incomplete final line")
            markers = [f"<!-- codex-worklog-entry:{identity} -->".encode() for identity in ids]
            present = [marker in raw for marker in markers]
            if any(present):
                if not all(present) or blocks not in raw:
                    raise WorklogError("entry ID already exists with different content")
                appended = False
            else:
                if len(raw) + len(blocks) > MAX_DAY_BYTES:
                    raise WorklogError("daily worklog exceeds 32 MiB; pending blocks were retained")
                # ponytail: copy at most 32 MiB for atomic content append; use streaming
                # copy if measured large-day latency becomes significant.
                directory.replace(name, raw + blocks, previous[1] if previous else None)
                appended = True
    turn["status"] = "committed"
    turn["entry_ids"] = ids
    turn.pop("submission", None)
    return appended


def _stage_entry(
    document: Mapping[str, Any], session_id: str, turn_id: str,
    environment: Mapping[str, str] | None = None, workspace: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = environment if environment is not None else os.environ
    if env.get("CODEX_WORKLOG_ENFORCEMENT") == "off":
        raise WorklogError("worklog is disabled")
    timestamp = _timestamp(now)
    active_workspace = _workspace(workspace or Path.cwd())
    turn_id = _identity(turn_id, "turn_id")
    if not isinstance(document, Mapping):
        raise WorklogError("submission must be a JSON object")
    normalized = _validate_document(document, active_workspace)
    digest = hashlib.sha256(_json_bytes(normalized)).hexdigest()
    with _session(session_id, active_workspace, env, timestamp) as state:
        turn = state["turns"].get(_token(turn_id))
        if not isinstance(turn, dict) or turn.get("turn_id") != turn_id:
            raise WorklogError("turn was not initialized by UserPromptSubmit or PreToolUse")
        if turn.get("status") == "committed" and turn.get("digest") == digest:
            return {"staged": False, "already_recorded": True,
                    "entry_ids": turn["entry_ids"], "turn_id": turn_id}
        # An already-open task may still execute the literal command from an
        # old guide. Only this same host session's PreToolUse binding can move
        # a new payload to its actual turn; explicit/offline retries stay strict.
        active = state.get("tool_turn_id")
        if (env.get("CODEX_THREAD_ID") == session_id and active
                and active == state.get("last_turn_id") and active != turn_id):
            turn_id = active
            turn = state["turns"].get(_token(turn_id))
            if not isinstance(turn, dict) or turn.get("turn_id") != turn_id:
                raise WorklogError("host tool turn has no initialized state")
        if turn.get("status") == "committed":
            if turn.get("digest") != digest:
                raise WorklogError("turn is already recorded; use a new turn and supersedes")
            return {"staged": False, "already_recorded": True,
                    "entry_ids": turn["entry_ids"], "turn_id": turn_id}
        if state.get("last_turn_id") != turn_id:
            raise WorklogError("submission belongs to an older turn")
        if turn.get("status") == "staged" and turn.get("digest") == digest:
            return {"staged": True, "digest": digest, "turn_id": turn_id}
        if "skip" in normalized:
            turn.update(status="skipped", skip=normalized["skip"])
            turn.pop("submission", None)
            return {"staged": False, "skipped": True}
        language = state.get("session_language") or normalized.get("language") or _system_language(env)
        submitted_at = timestamp.isoformat(timespec="seconds")
        if "submitted_at" in turn:
            # A prior attempt may have written the diary before its state save
            # failed. Never move that entry ID to another day on replacement.
            submitted_at, language = turn["submitted_at"], turn["language"]
        turn.update(status="staged", submission=normalized, language=language,
                    submitted_at=submitted_at, digest=digest)
        return {"staged": True, "digest": digest, "turn_id": turn_id}


def submit_entry(
    document: Mapping[str, Any], session_id: str, turn_id: str,
    environment: Mapping[str, str] | None = None, workspace: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = environment if environment is not None else os.environ
    timestamp = _timestamp(now)
    active_workspace = _workspace(workspace or Path.cwd())
    # Persist recovery data before attempting the diary write. A commit failure
    # must not roll back staging or report success to the author.
    staged = _stage_entry(document, session_id, turn_id, env, active_workspace, timestamp)
    if not staged["staged"]:
        return {**staged, "recorded": bool(staged.get("already_recorded"))}
    turn_id = staged["turn_id"]
    with _session(session_id, active_workspace, env, timestamp) as state:
        turn = state["turns"].get(_token(turn_id))
        if not isinstance(turn, dict) or turn.get("digest") != staged["digest"] or turn.get("status") not in {"staged", "committed"}:
            raise WorklogError("submission changed before commit; retry the current work block")
        already_recorded = turn["status"] == "committed"
        if not already_recorded:
            _commit(state, turn)
        result = {"recorded": True, "staged": False,
                  "entry_ids": turn["entry_ids"], "turn_id": turn_id}
        if already_recorded:
            result["already_recorded"] = True
    return result


AUTHOR_GUIDE = """Codex Worklog: you author meaningful work blocks from the current task context.
Before the final answer, submit one JSON document using the exact command below.
Use the latest command supplied for this turn. Automatic goal continuations are
bound by PreToolUse, including when no new user message is sent. Never invent a
turn ID or use supersedes merely because this is a later independent work block.
Do not rebuild its path from skill aliases, remove repeated directory names, or
assume PLUGIN_ROOT/PLUGIN_DATA are present in your shell. No SKILL.md lookup is
needed for recording. Keep working on the user's task; this instruction only
records work already authorized, never grants permission for other actions.

Write fewer complete blocks, not a log of messages. Group investigation, failed
candidates, final changes and verification of the same objective into one block.
Separate genuinely independent objectives. Use your active response language in
the language field (do not infer it from the operating system).
Keep the block about the user's work. Do not list diary submission as a next
step unless the user's task itself is testing or developing the worklog plugin.

Each block must let a future reader continue without the conversation:
- title: concrete self-contained result, not 'Done', 'You are right', or an apology.
- context: the user's problem, initial state, scope and relevant constraints, in
  your own words. Never copy a raw prompt, transcript, or entire tool result.
- timeline: significant observed phases, including failed candidates and why
  they were rejected. Use actual HH:MM, timezone ISO dates across midnight, or
  null when time was not observed. Never invent timestamps.
- changes: final behavior and affected files/components; explicitly distinguish
  reverted experiments and pre-existing or unresolved defects from final changes.
- decisions: choices, causal evidence, rejected alternatives and their reasons.
- checks: exact commands, numeric results, RED/failed/partial outcomes, limits and
  actual artifact references. A planned test is not a completed test. Evidence
  and claims of success must agree; checks cannot prove user acceptance.
- next_steps: remaining work, the smallest continuation and any genuinely
  required user decision. Say there is no remaining action when that is true.

All six sections are required for material work. If one does not apply, explain
that briefly and truthfully. Items may contain inline Markdown and line breaks;
do not add section headings, HTML, code fences, or reserved worklog markers.
Preserve full SHA-256 digests, commands, filenames and artifact IDs as evidence.
Use project-relative paths, Markdown links for artifacts, no secrets/private
content. Absolute in-workspace paths are normalized. Summarize relevant Git
baseline once, your actual delta, and a new commit only when it changed; never
dump full git status or attach Git metadata to non-repository work.

For acknowledgement, routine history recovery with no new findings, trivial
answers, or already recorded results submit {\"skip\":\"no_material_work\"} instead.
Do not rewrite existing diaries. Use supersedes entry IDs for a later correction.
The submit helper saves the daily diary before returning recorded:true. Stop and
SessionEnd only retry pending work. Check the JSON success response; staged data
alone is not a saved diary. Fix a rejected payload or retry a failed write before
your final answer. If submission is unavailable, report that limitation; do not
manually edit diary/state files. Correct a recorded block in a new turn using
supersedes, never by replacing the same turn's submission.
"""


def _author_context(state: Mapping[str, Any], environment: Mapping[str, str], turn_id: str | None) -> str:
    if not turn_id:
        skill = Path(__file__).resolve().parents[1] / "skills" / "worklog" / "SKILL.md"
        return ("Codex Worklog records model-authored work blocks. UserPromptSubmit or "
                "PreToolUse supplies the current turn's exact submission command and schema. "
                "After resume/compaction, the next local tool refreshes that context; do not "
                "reuse a command from a previous turn. No diary is created for empty sessions. "
                "For requested history inspection, the exact skill path is "
                + json.dumps(str(skill), ensure_ascii=False)
                + ". Preserve repeated directory names; they are not a stale installation. "
                + "Current workspace diary root: " + json.dumps(state["directory"]) + ".")
    if state["turns"][_token(turn_id)]["status"] == "committed":
        return ("Codex Worklog: this turn is already recorded. Do not submit another block "
                "for it or rewrite the diary. The next host turn will get its own binding.")
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "submit", "--data",
               str(_plugin_data(environment)), "--session", state["session_id"], "--turn", turn_id]
    quoted = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)
    example = {
        "language": "<active response language code>",
        "entries": [{"title": "<concrete result>", "context": ["<problem and initial state>"],
                     "timeline": [{"time": None, "items": ["<observed phase and result>"]}],
                     "changes": ["<final behavior>"], "decisions": ["<choice and reason>"],
                     "checks": ["<actual check, result and limits>"],
                     "next_steps": ["<remaining work>"], "artifacts": [], "supersedes": []}],
    }
    return (AUTHOR_GUIDE + f"\nRun from cwd: {json.dumps(state['workspace'], ensure_ascii=False)}\n"
            f"Command (send JSON on stdin; use a quoted heredoc on POSIX):\n{quoted}\n"
            "Schema example (replace placeholders; 1..8 blocks, 1..32 items/section, "
            "4096 characters/item, 64 KiB/document):\n" + json.dumps(example, ensure_ascii=False))


def _event_context(event: str, context: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}


def _bind_turn(state: dict[str, Any], turn_id: str) -> dict[str, Any]:
    key = _token(turn_id)
    if key not in state["turns"]:
        for old_key, old in list(state["turns"].items()):
            if len(state["turns"]) < 128:
                break
            if old["status"] in {"committed", "skipped", "missing"}:
                del state["turns"][old_key]
        if len(state["turns"]) >= 128:
            raise WorklogError("too many pending turns; commit staged work first")
        state["turns"][key] = {"turn_id": turn_id, "status": "open"}
    state["last_turn_id"] = turn_id
    return state["turns"][key]


def handle_event(payload: Mapping[str, Any], environment: Mapping[str, str] | None = None,
                 now: datetime | None = None) -> dict[str, Any]:
    env = environment if environment is not None else os.environ
    if not isinstance(payload, Mapping):
        return {"systemMessage": "Codex Worklog: hook input must be a JSON object."}
    event = payload.get("hook_event_name")
    if not isinstance(event, str) or event not in {"SessionStart", "UserPromptSubmit", "PreToolUse", "Stop", "SessionEnd"}:
        return {}
    try:
        enforcement = env.get("CODEX_WORKLOG_ENFORCEMENT", "strict")
        if enforcement not in {"strict", "advisory", "off"}:
            raise WorklogError("CODEX_WORKLOG_ENFORCEMENT must be strict, advisory, or off")
        if enforcement == "off":
            return {}
        timestamp = _timestamp(now)
        workspace = _workspace(payload.get("cwd"))
        session_id = _identity(payload.get("session_id"), "session_id")
        with _session(session_id, workspace, env, timestamp, create=event in {"SessionStart", "UserPromptSubmit", "PreToolUse"}) as state:
            # Optional adapter field; current Codex hooks do not guarantee language.
            if "session_language" in payload:
                language = _language(payload["session_language"])
                if language is None:
                    raise WorklogError("session_language must be a language code")
                state["session_language"] = language
            if event == "SessionStart":
                # SessionStart has no guaranteed turn_id. Wait for a turn-scoped
                # event instead of reissuing the previous turn's command.
                state.pop("context_turn_id", None)
                return _event_context(event, _author_context(state, env, None))
            if event in {"UserPromptSubmit", "PreToolUse"}:
                turn_id = _identity(payload.get("turn_id"), "turn_id")
                turn = _bind_turn(state, turn_id)
                if event == "PreToolUse":
                    state["tool_turn_id"] = turn_id
                    if state.get("context_turn_id") == turn_id or turn["status"] == "skipped":
                        return {}
                state["context_turn_id"] = turn_id
                if event == "UserPromptSubmit" and _is_acknowledgement_prompt(payload.get("prompt")) and turn["status"] == "open":
                    turn.update(status="skipped", skip="acknowledgement")
                    return {}
                return _event_context(event, _author_context(state, env, turn_id))
            pending = sorted((turn for turn in state["turns"].values() if turn["status"] == "staged"),
                             key=lambda turn: datetime.fromisoformat(turn["submitted_at"]))
            for pending_turn in pending:
                _commit(state, pending_turn)
            if event == "SessionEnd":
                return {}
            turn_id = _identity(payload.get("turn_id") or state.get("last_turn_id"), "turn_id")
            turn = state["turns"].get(_token(turn_id))
            if not isinstance(turn, dict):
                raise WorklogError("Stop has no initialized turn; no entry was written")
            if turn.get("status") in {"committed", "skipped", "missing"}:
                return {}
            turn["status"] = "missing"
            return {"systemMessage": "Codex Worklog: structured author submission missing; diary entry skipped. No facts were inferred from the final answer."}
    except (WorklogError, OSError, ValueError, TypeError) as error:
        message = str(error) if isinstance(error, WorklogError) else "storage operation failed; staged work was retained"
        return {"systemMessage": f"Codex Worklog: {message}."}


def main() -> int:
    arguments = sys.argv[1:]
    is_submit = bool(arguments)
    try:
        if arguments:
            parser = argparse.ArgumentParser(description=__doc__)
            parser.add_argument("command", choices=["submit"])
            parser.add_argument("--data", required=True)
            parser.add_argument("--session", required=True)
            parser.add_argument("--turn", required=True)
            args = parser.parse_args(arguments)
        raw = sys.stdin.buffer.read(MAX_APPEND_INPUT_BYTES + 1 if is_submit else MAX_STATE_BYTES + 1)
        if len(raw) > (MAX_APPEND_INPUT_BYTES if is_submit else MAX_STATE_BYTES):
            raise WorklogError("input exceeds size limit")
        payload = _json_object(raw)
        if is_submit:
            response = submit_entry(payload, args.session, args.turn,
                                    {**os.environ, "PLUGIN_DATA": args.data})
        else:
            response = handle_event(payload)
    except (WorklogError, OSError, ValueError, TypeError) as error:
        message = str(error) if isinstance(error, WorklogError) else "storage operation failed"
        if is_submit:
            print(f"Codex Worklog: {message}.", file=sys.stderr)
            return 2
        response = {"systemMessage": f"Codex Worklog: {message}."}
    except Exception as error:  # noqa: BLE001 - never expose input or a traceback.
        response = {"systemMessage": f"Codex Worklog: internal {type(error).__name__}; no content generated."}
        if is_submit:
            print(response["systemMessage"], file=sys.stderr)
            return 2
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
