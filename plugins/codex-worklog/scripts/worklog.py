#!/usr/bin/env python3
"""Lifecycle hook for the Codex Worklog plugin.

The hooks own worklog creation and appends. User prompts, tool inputs, tool
output, and transcripts are deliberately not copied into the worklog.
"""

from __future__ import annotations

import hashlib
import json
import locale
import os
import re
import shutil
import stat
import subprocess  # nosec B404 - only bounded, non-shell local Git reads are used.
import sys
import tempfile
import unicodedata
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import urlsplit

DEFAULT_DIRECTORY = ".dev-diary"
DEFAULT_ENFORCEMENT = "strict"
ALLOWED_ENFORCEMENT = {"strict", "advisory", "off"}
TAIL_BYTES = 128 * 1024
MAX_INLINE_CHARS = 2048
MAX_STATE_BYTES = 1024 * 1024
MAX_APPEND_INPUT_BYTES = 32 * 1024
MAX_ENTRY_TITLE_CHARS = 160
MAX_ASSISTANT_SOURCE_CHARS = 16 * 1024
MAX_AUTOMATIC_SUMMARY_CHARS = 1200
MAX_SYSTEM_LOCALE_FILE_BYTES = 4096
REQUIRED_ENTRY_FIELD_NAMES = ("title", "summary")
OPTIONAL_ENTRY_FIELD_NAMES = (
    "reason",
    "unblocks",
    "supersedes_status",
    "verification",
    "artifacts",
    "next",
)
REQUIRED_APPEND_PAYLOAD_KEYS = frozenset(
    ("worklog_path", "marker", *REQUIRED_ENTRY_FIELD_NAMES)
)
ALLOWED_APPEND_PAYLOAD_KEYS = frozenset(
    (*REQUIRED_APPEND_PAYLOAD_KEYS, *OPTIONAL_ENTRY_FIELD_NAMES)
)
TURN_MARKER_PATTERN = re.compile(r"<!-- codex-worklog-turn:[0-9a-f]{16} -->")
FULL_SHA256_PATTERN = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])")
POSIX_ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![:/\w])/(?!/)[^\r\n`]*")
WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|\\\\)[^\r\n`]*"
)
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]\r\n]+)\]\(([^)\r\n]+)\)")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]\r\n]*)\]\(([^)\r\n]+)\)")
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"</?[A-Za-z][^>]*>")
URI_PATTERN = re.compile(r"\b(?:https?|file|codex)://\S+", re.IGNORECASE)
HOME_PATH_PATTERN = re.compile(r"(?<!\w)~[/\\][^\r\n`]*")
BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{8,}")
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|auth[_ -]?token|refresh[_ -]?token|"
    r"token|password|passwd|private[_ -]?key|client[_ -]?secret|secret|credentials?)"
    r"\s*[:=]\s*(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)"
)
ENTRY_REFERENCE_TIME_PATTERN = re.compile(r"(?<!\d)\d{2}:\d{2}(?!\d)")
LANGUAGE_CODE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*$")
ENTRY_HEADING_PATTERN = re.compile(
    r"^### \d{4}-\d{2}-\d{2}T(?P<time>\d{2}:\d{2})(?:[^ ]*) — (?P<title>.+)$",
    re.MULTILINE,
)
GIT_TIMEOUT_SECONDS = 1.0
SYSTEM_LOCALE_PATHS = (Path("/etc/locale.conf"), Path("/etc/default/locale"))
LOCALIZED_TEXT = {
    "en": {
        "started": "Started",
        "project": "Project",
        "repository": "Repository",
        "branch": "Branch",
        "timeline": "Timeline",
        "summary": "Outcome",
        "reason": "Reason/decision",
        "unblocks": "Unblocks",
        "supersedes_status": "Supersedes status",
        "verification": "Verified",
        "artifacts": "Artifacts",
        "next": "Next",
        "automatic_title": "Turn completed",
        "automatic_summary": (
            "Codex completed the turn without a safe reusable prose summary."
        ),
    },
    "ru": {
        "started": "Начат",
        "project": "Проект",
        "repository": "Репозиторий",
        "branch": "Ветка",
        "timeline": "Хронология",
        "summary": "Результат",
        "reason": "Причина/решение",
        "unblocks": "Разблокирует",
        "supersedes_status": "Заменяет статус",
        "verification": "Проверено",
        "artifacts": "Артефакты",
        "next": "Далее",
        "automatic_title": "Ход работы завершён",
        "automatic_summary": (
            "Codex завершил работу без безопасного переиспользуемого резюме."
        ),
    },
}
ACKNOWLEDGEMENT_MAX_CHARS = 80
ACKNOWLEDGEMENT_PHRASES = frozenset(
    {
        "большое спасибо",
        "благодарю",
        "всё ясно",
        "все ясно",
        "ок",
        "окей",
        "отлично",
        "понял",
        "поняла",
        "поняли",
        "принято",
        "спасибо",
        "спасибо большое",
        "спс",
        "супер",
        "хорошо",
        "ясно",
        "got it",
        "ok",
        "okay",
        "sounds good",
        "thank you",
        "thanks",
        "thx",
        "understood",
    }
)
ACKNOWLEDGEMENT_EMOJI = frozenset({"👍", "👌", "✅", "🙏"})
QUESTION_MARKS = frozenset({"?", "¿", "⁇", "⁈", "⁉", "？"})
PROMPT_INTENTS = frozenset(
    {"acknowledgement", "change", "context_recovery", "read_only", "unknown"}
)
PROMPT_CHANGE_PATTERN = re.compile(
    r"(?i)(?:"
    r"\b(?:добав|включ|восстанов|выполн|исправ|измен|настро|обнов|отключ|"
    r"опубли|перемест|переимен|почин|примен|реализ|сдела|созда|удал|установ|"
    r"замен)\w*\b|"
    r"\b(?:add|apply|build|change|configure|create|delete|deploy|disable|enable|"
    r"fix|implement|install|move|publish|remove|rename|restore|run|set up|"
    r"update)\b"
    r")"
)
PROMPT_READ_ONLY_PATTERN = re.compile(
    r"(?i)(?:"
    r"\$(?:worklog)\b|"
    r"\b(?:аудит|где|диагност|зачем|когда|какой|объясн|покаж|посмотр|почему|"
    r"провер|прочита|проанализ|статус|что)\w*\b|"
    r"\b(?:analy[sz]e|audit|check|diagnose|explain|find out|inspect|look at|"
    r"read|review|show|status|verify|what|when|where|why)\b"
    r")"
)
NO_STATE_CHANGE_PATTERN = re.compile(
    r"(?i)(?:"
    r"\bничего\s+не\s+(?:делал\w*|измен(?:ил\w*|ено|ял\w*)|"
    r"менял\w*|записывал\w*)\b|"
    r"\bизменени\w*\s+(?:не\s+было|не\s+вносил\w*|нет)\b|"
    r"\bбез\s+изменений\b|"
    r"\bno\s+changes?(?:\s+(?:were|was))?\s+made\b|"
    r"\bnothing\s+(?:was\s+)?changed\b|"
    r"\bmade\s+no\s+changes?\b"
    r")"
)
STATE_CHANGE_PATTERN = re.compile(
    r"(?i)(?:"
    r"\b(?:добав(?:ил|лен)\w*|включ(?:ил|[её]н)\w*|восстанов(?:ил|лен)\w*|"
    r"выполн(?:ил|ен)\w*|исправ(?:ил|лен)\w*|измен(?:ил|[её]н)\w*|"
    r"настро(?:ил|ен)\w*|обнов(?:ил|л[её]н)\w*|отключ(?:ил|[её]н)\w*|"
    r"опубликов(?:ал|ан)\w*|перемест(?:ил|ён|ен)\w*|переимен(?:овал|ован)\w*|"
    r"почин(?:ил|ен)\w*|примен(?:ил|[её]н)\w*|реализ(?:овал|ован)\w*|"
    r"созд(?:ал|ан)\w*|удал(?:ил|[её]н)\w*|установ(?:ил|лен)\w*|"
    r"замен(?:ил|[её]н)\w*|зафиксир(?:овал|ован)\w*|"
    r"заверш(?:ил|[её]н)\w*|устран(?:ил|[её]н)\w*)\b|"
    r"\b(?:added|applied|built|changed|completed|configured|created|deleted|"
    r"deployed|disabled|enabled|fixed|implemented|installed|moved|published|"
    r"recovered|removed|renamed|resolved|restored|updated)\b"
    r")"
)
FIRST_PERSON_STATE_CHANGE_PATTERN = re.compile(
    r"(?i)(?:"
    r"\b(?:я\s+)?(?:добавил|включил|восстановил|выполнил|исправил|изменил|"
    r"настроил|обновил|отключил|опубликовал|переместил|переименовал|починил|"
    r"применил|реализовал|создал|удалил|установил|заменил|зафиксировал)\b|"
    r"\bI\s+(?:added|applied|built|changed|configured|created|deleted|deployed|"
    r"disabled|enabled|fixed|implemented|installed|moved|published|removed|"
    r"renamed|restored|updated)\b"
    r")"
)
BLOCKER_OR_DISCOVERY_PATTERN = re.compile(
    r"(?i)(?:"
    r"\b(?:обнаружен|выявлен|найден)\w*\s+(?:блокер|дефект|ошибк|причин)\w*|"
    r"\b(?:заблокирован|блокирует|не\s+удалось)\b|"
    r"\b(?:blocked|blocker|could\s+not|failed|root\s+cause|unable\s+to)\b"
    r")"
)
REASON_PATTERN = re.compile(
    r"(?i)(?:"
    r"\b(?:корневая\s+)?причин\w*\b|"
    r"\b(?:дефект|ошибк|проблем)\w*\s+(?:был\w*\s+)?(?:вызван|возник)\w*\b|"
    r"\bиз-за\b|"
    r"\b(?:принят|выбран)\w*\s+(?:решени|вариант|подход)\w*\b|"
    r"\b(?:decided|decision|root\s+cause)\b|"
    r"\b(?:chose|selected)\b.*\bbecause\b"
    r")"
)
VERIFICATION_PATTERN = re.compile(
    r"(?i)(?:"
    r"\b(?:провер(?:ен|ена|ено|ены|ил)\w*|подтвержд(?:ён|ен)(?!и)\w*|"
    r"тест\w*\s+(?:прош|успеш))\b|"
    r"\b(?:confirmed|tests?\s+pass(?:ed)?|verif(?:ied|ication))\b"
    r")"
)
STATUS_ARROW_PATTERN = re.compile(
    r"(?<![\w.-])(?P<previous>[A-Za-z0-9][A-Za-z0-9_.-]{0,63})\s*"
    r"(?:→|->)\s*(?P<current>[A-Za-z0-9][A-Za-z0-9_.-]{0,63})(?![\w.-])"
)
FIELD_LABELS = {
    "summary": frozenset({"outcome", "result", "результат"}),
    "reason": frozenset(
        {
            "decision",
            "reason",
            "reason/decision",
            "причина",
            "причина/решение",
            "решение",
        }
    ),
    "unblocks": frozenset({"unblocks", "разблокирует"}),
    "supersedes_status": frozenset({"supersedes status", "заменяет статус"}),
    "verification": frozenset({"verification", "verified", "проверено"}),
    "artifacts": frozenset({"artifacts", "артефакты"}),
    "next": frozenset({"next", "далее"}),
}


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


def _locale_language(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.split(":", 1)[0].strip().split(".", 1)[0].split("@", 1)[0]
    if candidate.casefold() in {"c", "posix"}:
        return None
    if LANGUAGE_CODE_PATTERN.fullmatch(candidate) is None:
        return None
    return re.split(r"[-_]", candidate, maxsplit=1)[0].lower()


def _language_from_system_locale_files(
    paths: tuple[Path, ...] = SYSTEM_LOCALE_PATHS,
) -> str | None:
    for path in paths:
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if len(raw) > MAX_SYSTEM_LOCALE_FILE_BYTES:
            continue
        try:
            contents = raw.decode("utf-8", errors="strict")
        except UnicodeError:
            continue
        values: dict[str, str] = {}
        for raw_line in contents.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key not in {"LANG", "LANGUAGE", "LC_MESSAGES"}:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            values[key] = value
        for key in ("LANGUAGE", "LC_MESSAGES", "LANG"):
            language = _locale_language(values.get(key))
            if language is not None:
                return language
    return None


def _system_language(
    environment: Mapping[str, str],
    system_locale_paths: tuple[Path, ...] = SYSTEM_LOCALE_PATHS,
) -> str:
    override = environment.get("CODEX_WORKLOG_LANGUAGE")
    if override is not None:
        language = _locale_language(override)
        if language is None:
            raise WorklogError(
                "CODEX_WORKLOG_LANGUAGE must contain a valid language or locale code"
            )
        return language
    for key in ("LC_ALL", "LANGUAGE", "LC_MESSAGES", "LANG"):
        language = _locale_language(environment.get(key))
        if language is not None:
            return language
    language = _language_from_system_locale_files(system_locale_paths)
    if language is not None:
        return language
    try:
        language = _locale_language(locale.getlocale()[0])
    except (TypeError, ValueError, locale.Error):
        language = None
    return language or "en"


def _localized(language: str, key: str) -> str:
    labels = LOCALIZED_TEXT.get(language, LOCALIZED_TEXT["en"])
    return labels[key]


def _contains_absolute_local_path(value: str) -> bool:
    lowered = value.casefold()
    return (
        bool(POSIX_ABSOLUTE_PATH_PATTERN.search(value))
        or bool(WINDOWS_ABSOLUTE_PATH_PATTERN.search(value))
        or "file://" in lowered
        or bool(re.search(r"(?<!\w)~[/\\]", value))
    )


def _portable_metadata(value: object) -> str | None:
    text = _safe_inline(value).strip()
    if not text or _contains_absolute_local_path(text):
        return None
    return text


def _git_output(workspace: Path, *arguments: str) -> str | None:
    git_executable = shutil.which("git")
    if git_executable is None or not Path(git_executable).is_absolute():
        return None
    child_environment = os.environ.copy()
    child_environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    try:
        completed = subprocess.run(  # nosec B603
            [git_executable, "-C", str(workspace), *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
            env=child_environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return output if output and "\n" not in output and "\r" not in output else None


def _repository_identifier(remote: str | None, fallback: str) -> str:
    if remote is None:
        return fallback
    value = remote.strip()
    scp_match = re.fullmatch(r"[^/@\s]+@[^:/\s]+:(.+)", value)
    if scp_match is not None:
        candidate = scp_match.group(1)
    else:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return fallback
        if parsed.scheme:
            if parsed.scheme.casefold() not in {"git", "http", "https", "ssh"}:
                return fallback
            candidate = parsed.path
        else:
            if Path(value).is_absolute() or PureWindowsPath(value).is_absolute():
                return fallback
            candidate = value
    candidate = candidate.strip().strip("/")
    candidate = candidate.removesuffix(".git")
    parts = candidate.split("/")
    if not candidate or any(part in {"", ".", ".."} for part in parts):
        return fallback
    return _portable_metadata(candidate) or fallback


def _project_metadata(workspace: Path) -> dict[str, str]:
    project = _portable_metadata(workspace.name) or "workspace"
    metadata = {"project": project}
    root_value = _git_output(workspace, "rev-parse", "--show-toplevel")
    if root_value is None:
        return metadata
    try:
        repository_root = Path(root_value).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return metadata
    fallback = _portable_metadata(repository_root.name) or project
    remote = _git_output(workspace, "config", "--get", "remote.origin.url")
    metadata["repository"] = _repository_identifier(remote, fallback)
    branch = _portable_metadata(
        _git_output(workspace, "symbolic-ref", "--quiet", "--short", "HEAD")
        or "detached"
    )
    if branch is not None:
        metadata["branch"] = branch
    head = _git_output(workspace, "rev-parse", "HEAD")
    if head is not None and re.fullmatch(r"[0-9A-Fa-f]{40,64}", head):
        metadata["head"] = head[:12].lower()
    return metadata


def _is_acknowledgement_prompt(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if len(value) > ACKNOWLEDGEMENT_MAX_CHARS:
        return False
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    if any(character in QUESTION_MARKS for character in normalized):
        return False
    if normalized in ACKNOWLEDGEMENT_EMOJI:
        return True
    phrase = "".join(
        " "
        if character.isspace() or unicodedata.category(character).startswith(("P", "S"))
        else character
        for character in normalized
    )
    return " ".join(phrase.split()) in ACKNOWLEDGEMENT_PHRASES


def _prompt_intent(value: object) -> str:
    if _is_acknowledgement_prompt(value):
        return "acknowledgement"
    if not isinstance(value, str) or not value.strip():
        return "unknown"
    source = unicodedata.normalize("NFKC", value[:MAX_ASSISTANT_SOURCE_CHARS])
    if (
        re.search(
            r"(?i)(?:\$worklog\b|\bвосстанов\w*\s+контекст\b|\brecover\s+context\b)",
            source,
        )
        is not None
    ):
        return "context_recovery"
    if PROMPT_CHANGE_PATTERN.search(source) is not None:
        return "change"
    if PROMPT_READ_ONLY_PATTERN.search(source) is not None:
        return "read_only"
    return "unknown"


def _entry_value(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorklogError(f"append payload field {key} must be a non-empty string")
    value = unicodedata.normalize("NFC", value.strip())
    limit = MAX_ENTRY_TITLE_CHARS if key == "title" else MAX_INLINE_CHARS
    if len(value) > limit:
        raise WorklogError(f"append payload field {key} is too long")
    if any(
        character in "\r\n" or _unsafe_inline_character(character)
        for character in value
    ):
        raise WorklogError(f"append payload field {key} must be a single safe line")
    if "<!-- codex-worklog-" in value:
        raise WorklogError(f"append payload field {key} contains a reserved marker")
    if _contains_absolute_local_path(value):
        raise WorklogError(
            f"append payload field {key} contains an absolute local path; "
            "use a project-relative reference"
        )
    if FULL_SHA256_PATTERN.search(value) is not None:
        raise WorklogError(
            f"append payload field {key} contains a full SHA-256 digest; "
            "link a report from artifacts instead"
        )
    return value


def _assistant_source(message: object) -> str:
    if not isinstance(message, str) or not message.strip():
        raise WorklogError("the Stop hook did not include a final assistant message")
    source = unicodedata.normalize("NFC", message[:MAX_ASSISTANT_SOURCE_CHARS])
    return re.split(r"\n<oai-mem-citation(?:\s|>)", source, maxsplit=1)[0]


def _assistant_lines(source: str) -> list[str]:
    source = HTML_COMMENT_PATTERN.sub(" ", source)
    lines: list[str] = []
    in_fence = False
    for raw_line in source.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = raw_line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if stripped.startswith((":codex-", "::code-comment", "::created-thread")):
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def _clean_assistant_line(value: str) -> str:
    stripped = value.strip()
    stripped = re.sub(r"^(?:[-*+] |\d+[.)] |>\s*)", "", stripped).strip()
    stripped = MARKDOWN_IMAGE_PATTERN.sub(lambda match: match.group(1), stripped)
    stripped = MARKDOWN_LINK_PATTERN.sub(lambda match: match.group(1), stripped)
    stripped = HTML_TAG_PATTERN.sub(" ", stripped)
    stripped = URI_PATTERN.sub("[link]", stripped)
    stripped = HOME_PATH_PATTERN.sub("[local path]", stripped)
    stripped = WINDOWS_ABSOLUTE_PATH_PATTERN.sub("[local path]", stripped)
    stripped = POSIX_ABSOLUTE_PATH_PATTERN.sub("[local path]", stripped)
    stripped = BEARER_PATTERN.sub("Bearer [redacted]", stripped)
    stripped = SENSITIVE_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[redacted]", stripped
    )
    stripped = FULL_SHA256_PATTERN.sub("[digest]", stripped)
    stripped = stripped.replace("`", "").replace("**", "").replace("__", "")
    return " ".join(stripped.split())


def _field_label_and_value(line: str) -> tuple[str, str] | None:
    candidate = re.sub(r"^(?:[-*+] |\d+[.)] |>\s*)", "", line).strip()
    candidate = candidate.replace("**", "").replace("__", "")
    match = re.match(r"^([^:—]{1,40})\s*(?::|—)\s*(.+)$", candidate)
    if match is None:
        return None
    normalized_label = " ".join(match.group(1).replace("`", "").casefold().split())
    for field, labels in FIELD_LABELS.items():
        if normalized_label in labels:
            return field, match.group(2).strip()
    return None


def _automatic_entry_text(message: object, language: str) -> tuple[str, str]:
    """Derive one bounded prose summary without retaining the full response."""

    source = _assistant_source(message)
    candidates: list[str] = []
    for raw_line in _assistant_lines(source):
        labelled = _field_label_and_value(raw_line)
        if labelled is not None:
            field, raw_value = labelled
            if field != "summary":
                continue
            raw_line = raw_value
        stripped = _clean_assistant_line(raw_line)
        if not stripped:
            continue
        candidates.append(stripped)
        if len(candidates) >= 3 or sum(len(value) for value in candidates) >= 800:
            break

    summary = " ".join(candidates).strip()
    if not summary:
        summary = _localized(language, "automatic_summary")
    if len(summary) > MAX_AUTOMATIC_SUMMARY_CHARS:
        summary = f"{summary[: MAX_AUTOMATIC_SUMMARY_CHARS - 1].rstrip()}…"

    sentence = re.match(r"^(.{1,160}?[.!?…])(?:\s|$)", summary)
    title = sentence.group(1) if sentence is not None else summary
    title = title.rstrip(".!?…").rstrip()
    if len(title) > MAX_ENTRY_TITLE_CHARS:
        title = f"{title[: MAX_ENTRY_TITLE_CHARS - 1].rstrip()}…"
    if not title:
        title = _localized(language, "automatic_title")
    return title, summary


def _safe_automatic_field(value: str) -> str | None:
    cleaned = _clean_assistant_line(value)
    if not cleaned or cleaned.casefold() in {
        "n/a",
        "none",
        "not applicable",
        "нет",
        "не применимо",
    }:
        return None
    if len(cleaned) > MAX_INLINE_CHARS:
        cleaned = f"{cleaned[: MAX_INLINE_CHARS - 1].rstrip()}…"
    return cleaned


def _normalized_status_transition(value: str) -> str | None:
    cleaned = _clean_assistant_line(value)
    match = STATUS_ARROW_PATTERN.search(cleaned)
    if match is not None:
        return f"{match.group('previous')} → {match.group('current')}"
    replacement_patterns = (
        re.compile(
            r"(?i)\bстатус\s+([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\s+"
            r"замен[её]н\s+на\s+([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\b"
        ),
        re.compile(
            r"(?i)\bstatus\s+([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\s+"
            r"(?:was\s+)?(?:replaced|superseded)\s+(?:by|with)\s+"
            r"([A-Za-z0-9][A-Za-z0-9_.-]{0,63})\b"
        ),
    )
    for pattern in replacement_patterns:
        replacement = pattern.search(cleaned)
        if replacement is not None:
            return f"{replacement.group(1)} → {replacement.group(2)}"
    return None


def _automatic_artifacts(value: str, workspace: Path) -> str | None:
    rendered: list[str] = []
    try:
        workspace_root = workspace.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    for match in MARKDOWN_LINK_PATTERN.finditer(value):
        label = _clean_assistant_line(match.group(1))
        raw_target = match.group(2).strip()
        target = (
            raw_target[1:-1]
            if raw_target.startswith("<") and raw_target.endswith(">")
            else raw_target
        )
        try:
            parsed = urlsplit(target)
        except ValueError:
            continue
        if parsed.scheme:
            if (
                parsed.scheme.casefold() != "https"
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
            ):
                continue
            normalized_target = target
        else:
            local_target, separator, fragment = target.partition("#")
            candidate = Path(local_target)
            try:
                resolved = (
                    candidate.resolve(strict=True)
                    if candidate.is_absolute()
                    else (workspace_root / candidate).resolve(strict=True)
                )
                relative = resolved.relative_to(workspace_root)
            except (OSError, RuntimeError, ValueError):
                continue
            if not resolved.is_file():
                continue
            normalized_target = relative.as_posix()
            if separator:
                normalized_target += f"#{fragment}"
        if not label:
            label = "report"
        if any(character.isspace() for character in normalized_target):
            normalized_target = f"<{normalized_target}>"
        rendered.append(f"[{label}]({normalized_target})")
    return ", ".join(rendered) or None


def _assistant_sentences(source: str) -> list[str]:
    lines = [_clean_assistant_line(line) for line in _assistant_lines(source)]
    text = " ".join(line for line in lines if line)
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?…])\s+", text)
        if sentence.strip()
    ]


def _natural_field(sentences: list[str], pattern: re.Pattern[str]) -> str | None:
    for sentence in sentences:
        if pattern.search(sentence) is None:
            continue
        return _safe_automatic_field(sentence)
    return None


def _read_tail_text(path: Path) -> str:
    descriptor = _open_regular_file(path, os.O_RDONLY)
    try:
        with os.fdopen(descriptor, "rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - TAIL_BYTES), os.SEEK_SET)
            return stream.read().decode("utf-8", errors="replace")
    except OSError as error:
        raise WorklogError(f"unable to inspect the worklog tail: {error}") from error


def _previous_unblocked_reference(path: Path, source: str) -> str | None:
    if (
        STATE_CHANGE_PATTERN.search(source) is None
        and re.search(r"(?i)\b(?:разблокирован|снят\s+блокер|unblocked)\b", source)
        is None
    ):
        return None
    source_tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9][\w.-]{3,}", source)
    }
    stop_tokens = {
        "awaiting",
        "blocked",
        "pending",
        "блокер",
        "ожидание",
        "ожидании",
    }
    for match in reversed(list(ENTRY_HEADING_PATTERN.finditer(_read_tail_text(path)))):
        title = match.group("title").strip()
        if (
            re.search(
                r"(?i)\b(?:await|block|pending|блок|ожид|policykit|требует)\w*\b",
                title,
            )
            is None
        ):
            continue
        title_tokens = {
            token.casefold()
            for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9][\w.-]{3,}", title)
        }
        if not ((title_tokens - stop_tokens) & (source_tokens - stop_tokens)):
            continue
        reference = f"{match.group('time')} — {title}"
        try:
            validated = _entry_value({"unblocks": reference}, "unblocks")
            _validate_transition_fields({"unblocks": validated})
        except WorklogError:
            continue
        return validated
    return None


def _automatic_entry(
    message: object,
    language: str,
    prompt_intent: str,
    workspace: Path,
    worklog_path: Path,
) -> dict[str, str] | None:
    source = _assistant_source(message)
    sentences = _assistant_sentences(source)
    labelled: dict[str, str] = {}
    raw_artifacts: str | None = None
    for line in _assistant_lines(source):
        parsed = _field_label_and_value(line)
        if parsed is None:
            continue
        field, raw_value = parsed
        if field == "artifacts":
            raw_artifacts = raw_value
            continue
        if field not in labelled:
            cleaned = _safe_automatic_field(raw_value)
            if cleaned is not None:
                labelled[field] = cleaned

    reason = labelled.get("reason") or _natural_field(sentences, REASON_PATTERN)
    verification = labelled.get("verification") or _natural_field(
        sentences, VERIFICATION_PATTERN
    )
    transition = _normalized_status_transition(
        labelled.get("supersedes_status", source)
    )
    unblocks = labelled.get("unblocks")
    if unblocks is not None:
        try:
            _validate_transition_fields({"unblocks": unblocks})
        except WorklogError:
            unblocks = None
    if unblocks is None:
        unblocks = _previous_unblocked_reference(worklog_path, source)

    has_decision_or_explanation = reason is not None
    has_transition = transition is not None or unblocks is not None
    no_state_change = NO_STATE_CHANGE_PATTERN.search(source) is not None
    state_change = STATE_CHANGE_PATTERN.search(source) is not None
    blocker_or_discovery = BLOCKER_OR_DISCOVERY_PATTERN.search(source) is not None
    if not has_decision_or_explanation and not has_transition:
        if no_state_change:
            return None
        if prompt_intent == "read_only":
            if (
                FIRST_PERSON_STATE_CHANGE_PATTERN.search(source) is None
                and not blocker_or_discovery
            ):
                return None
        elif (
            not state_change
            and not blocker_or_discovery
            and (
                prompt_intent != "change"
                or re.search(r"(?i)^\s*(?:готово|done)[.!]?\s*$", source) is None
            )
        ):
            return None

    title, summary = _automatic_entry_text(message, language)
    if "summary" in labelled:
        summary = labelled["summary"]
        title = re.split(r"[.!?…](?:\s|$)", summary, maxsplit=1)[0].strip()
        if len(title) > MAX_ENTRY_TITLE_CHARS:
            title = f"{title[: MAX_ENTRY_TITLE_CHARS - 1].rstrip()}…"
    entry = {"title": title, "summary": summary}
    optional = {
        "reason": reason,
        "unblocks": unblocks,
        "supersedes_status": transition,
        "verification": verification,
        "artifacts": (
            _automatic_artifacts(raw_artifacts, workspace)
            if raw_artifacts is not None
            else None
        ),
        "next": labelled.get("next"),
    }
    entry.update({key: value for key, value in optional.items() if value is not None})
    return entry


def _path_is_context_safe(path: Path) -> bool:
    value = str(path)
    return (
        len(value) <= MAX_INLINE_CHARS
        and "`" not in value
        and not any(_unsafe_inline_character(character) for character in value)
    )


def _same_existing_directory(left: Path, right: Path) -> bool:
    try:
        return left.absolute().resolve(strict=True) == right.absolute().resolve(
            strict=True
        )
    except (OSError, RuntimeError):
        return False


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
        raise WorklogError("worklog path contains unsupported unsafe characters")
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
    try:
        resolved_workspace = workspace.resolve(strict=True)
        resolved_path = path.resolve(strict=False)
        relative_path = resolved_path.relative_to(resolved_workspace)
    except (OSError, ValueError) as error:
        raise WorklogError(
            f"worklog path escapes the session working directory: {path}"
        ) from error
    try:
        path_parts = path.relative_to(workspace).parts
    except ValueError:
        # macOS commonly exposes /var through the canonical /private/var path.
        path_parts = relative_path.parts
    current = resolved_workspace
    for part in path_parts:
        current = current / part
        if current.is_symlink():
            raise WorklogError(f"refusing symbolic link in the worklog path: {current}")
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
    for key in (
        "last_turn_token",
        "last_appended_turn_token",
        "last_verified_turn_token",
        "last_skipped_turn_token",
    ):
        token = payload.get(key)
        if key in payload and (
            not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{16}", token)
        ):
            raise WorklogError(f"plugin state contains an invalid {key}")
    for key in ("last_turn_requires_entry",):
        if key in payload and not isinstance(payload.get(key), bool):
            raise WorklogError(f"plugin state contains an invalid {key} flag")
    intent = payload.get("last_turn_intent")
    if intent is not None and intent not in PROMPT_INTENTS:
        raise WorklogError("plugin state contains an invalid last_turn_intent")
    previous = payload.get("previous_worklog_path")
    if previous is not None and not isinstance(previous, str):
        raise WorklogError("plugin state contains an invalid previous worklog path")
    language = payload.get("language")
    if language is not None and (
        not isinstance(language, str) or re.fullmatch(r"[a-z]{2,3}", language) is None
    ):
        raise WorklogError("plugin state contains an invalid language")
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
            "the working directory path contains unsupported unsafe characters"
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


def _find_previous_worklog(
    plugin_data: Path, workspace: Path, current_state_path: Path
) -> Path | None:
    candidates: list[tuple[int, str, Path]] = []
    for candidate_state_path in (plugin_data / "sessions").glob("*.json"):
        if (
            candidate_state_path == current_state_path
            or re.fullmatch(r"[0-9a-f]{24}\.json", candidate_state_path.name) is None
        ):
            continue
        try:
            state = _load_json(candidate_state_path)
            workspace_value = state.get("workspace") if state is not None else None
            if (
                state is None
                or not isinstance(workspace_value, str)
                or not _same_existing_directory(Path(workspace_value), workspace)
            ):
                continue
            raw_path = state.get("worklog_path")
            if not isinstance(raw_path, str):
                continue
            path = _validate_worklog_path(workspace, Path(raw_path))
            if not path.name.endswith(f"--{candidate_state_path.stem[:12]}.md"):
                continue
            if not _read_prefix(path, 64).startswith("# Codex Worklog\n"):
                continue
            candidates.append(
                (candidate_state_path.stat().st_mtime_ns, str(path), path)
            )
        except (OSError, ValueError, WorklogError):
            continue
    if not candidates:
        return None
    return max(candidates)[2]


def _new_worklog(
    workspace: Path,
    directory_name: str,
    session_id: str,
    now: datetime,
    language: str,
) -> Path:
    relative_root = Path(directory_name)
    session_token = _token(session_id, 12)
    filename = f"{now:%Y-%m-%d--%H%M%S}--{session_token}.md"
    candidate_path = workspace / relative_root / f"{now:%Y}" / f"{now:%m}" / filename
    if not _path_is_context_safe(candidate_path):
        raise WorklogError("worklog path contains unsupported unsafe characters")
    _ensure_workspace_directory(workspace, relative_root)
    daily_root = _ensure_workspace_directory(
        workspace, relative_root / f"{now:%Y}" / f"{now:%m}"
    )
    path = daily_root / filename
    metadata = _project_metadata(workspace)
    header_lines = [
        "# Codex Worklog",
        "",
        f"- {_localized(language, 'started')}: {now.isoformat(timespec='seconds')}",
        f"- {_localized(language, 'project')}: `{metadata['project']}`",
    ]
    for key in ("repository", "branch", "head"):
        if key in metadata:
            label = "HEAD" if key == "head" else _localized(language, key)
            header_lines.append(f"- {label}: `{metadata[key]}`")
    header_lines.extend(("", f"## {_localized(language, 'timeline')}", ""))
    header = "\n".join(header_lines)
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
        existing_header = _read_prefix(path, 64)
        if not existing_header.startswith("# Codex Worklog\n"):
            raise WorklogError(f"existing worklog has an unexpected header: {path}")
    except OSError as error:
        raise WorklogError(
            f"unable to create the workspace worklog: {error}"
        ) from error
    _private_mode(path, 0o600)
    return path.absolute()


def _state_worklog_path(state: Mapping[str, Any], payload: Mapping[str, Any]) -> Path:
    diary_value = state.get("worklog_path")
    workspace_value = state.get("workspace")
    if not isinstance(diary_value, str) or not isinstance(workspace_value, str):
        raise WorklogError("plugin state is missing the workspace or worklog path")
    workspace = _workspace(payload)
    if not _same_existing_directory(Path(workspace_value), workspace):
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
    language = _system_language(environment)
    if state is not None:
        _state_worklog_path(state, payload)
        state["closed"] = False
        state["language"] = language
        state["last_seen_at"] = now.isoformat(timespec="seconds")
        _atomic_write_json(state_path, state)
        return state, state_path

    directory_name = _worklog_directory_name(environment)
    previous_path = _find_previous_worklog(plugin_data, workspace, state_path)
    worklog_path = _new_worklog(
        workspace=workspace,
        directory_name=directory_name,
        session_id=session_id,
        now=now,
        language=language,
    )
    state = {
        "closed": False,
        "language": language,
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


def _validate_transition_fields(values: Mapping[str, str]) -> None:
    unblocks = values.get("unblocks")
    if unblocks is not None and (
        "—" not in unblocks or ENTRY_REFERENCE_TIME_PATTERN.search(unblocks) is None
    ):
        raise WorklogError(
            "append payload field unblocks must reference a timestamp and title "
            "separated by an em dash"
        )
    supersedes = values.get("supersedes_status")
    if supersedes is not None:
        previous, separator, current = supersedes.partition("→")
        if not separator or not previous.strip() or not current.strip():
            raise WorklogError(
                "append payload field supersedes_status must use previous → current"
            )


def _render_artifacts(value: str, workspace: Path, worklog_path: Path) -> str:
    matches = list(MARKDOWN_LINK_PATTERN.finditer(value))
    if not matches:
        raise WorklogError(
            "append payload field artifacts must contain a Markdown link"
        )
    rendered: list[str] = []
    previous_end = 0
    try:
        workspace_root = workspace.resolve(strict=True)
        worklog_parent = worklog_path.parent.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise WorklogError("artifact context is no longer available") from error
    for match in matches:
        raw_target = match.group(2).strip()
        target = raw_target
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        try:
            parsed = urlsplit(target)
        except ValueError as error:
            raise WorklogError(
                "append payload field artifacts contains an invalid link"
            ) from error
        if parsed.scheme:
            if (
                parsed.scheme.casefold() != "https"
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise WorklogError(
                    "append payload field artifacts contains an unsafe external link"
                )
            rendered_target = raw_target
        else:
            local_target, separator, fragment = target.partition("#")
            candidate_path = Path(local_target)
            windows_candidate = PureWindowsPath(local_target)
            if (
                not local_target
                or candidate_path.is_absolute()
                or windows_candidate.is_absolute()
                or ".." in candidate_path.parts
                or "\\" in local_target
                or "?" in local_target
            ):
                raise WorklogError(
                    "append payload field artifacts must use a safe project-relative link"
                )
            try:
                resolved = (workspace_root / candidate_path).resolve(strict=True)
                resolved.relative_to(workspace_root)
            except (OSError, RuntimeError, ValueError) as error:
                raise WorklogError(
                    "append payload field artifacts points outside the project or to a "
                    "missing report"
                ) from error
            if not resolved.is_file():
                raise WorklogError(
                    "append payload field artifacts must link to a report file"
                )
            rendered_target = Path(
                os.path.relpath(resolved, start=worklog_parent)
            ).as_posix()
            if separator:
                rendered_target += f"#{fragment}"
            if any(character.isspace() for character in rendered_target):
                rendered_target = f"<{rendered_target}>"
        rendered.append(value[previous_end : match.start(2)])
        rendered.append(rendered_target)
        previous_end = match.end(2)
    rendered.append(value[previous_end:])
    return "".join(rendered)


def _append_entry(
    payload: Mapping[str, Any],
    now: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    workspace: Path | None = None,
) -> bool:
    actual_keys = frozenset(payload)
    missing = sorted(REQUIRED_APPEND_PAYLOAD_KEYS - actual_keys)
    unexpected = sorted(actual_keys - ALLOWED_APPEND_PAYLOAD_KEYS)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected fields: {', '.join(unexpected)}")
        raise WorklogError(
            f"append payload has the wrong schema ({'; '.join(details)})"
        )

    active_workspace = _workspace({"cwd": str(workspace or Path.cwd())})
    raw_path = payload.get("worklog_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise WorklogError("append payload worklog_path must be an absolute path")
    try:
        path = Path(raw_path).expanduser()
    except (OSError, RuntimeError, ValueError) as error:
        raise WorklogError("append payload worklog_path is invalid") from error
    if not path.is_absolute():
        raise WorklogError("append payload worklog_path must be an absolute path")
    path = _validate_worklog_path(active_workspace, path)

    marker = payload.get("marker")
    if not isinstance(marker, str) or TURN_MARKER_PATTERN.fullmatch(marker) is None:
        raise WorklogError("append payload marker is invalid")
    if _contains_recent_marker(path, marker):
        return False
    values = {key: _entry_value(payload, key) for key in REQUIRED_ENTRY_FIELD_NAMES}
    optional_values = {
        key: _entry_value(payload, key)
        for key in OPTIONAL_ENTRY_FIELD_NAMES
        if key in payload
    }
    _validate_transition_fields(optional_values)
    if "artifacts" in optional_values:
        optional_values["artifacts"] = _render_artifacts(
            optional_values["artifacts"], active_workspace, path
        )

    timestamp = now or _now()
    if timestamp.tzinfo is None:
        timestamp = timestamp.astimezone()
    language = _system_language(environment or os.environ)
    lines = [f"- {_localized(language, 'summary')}: {values['summary']}"]
    lines.extend(
        f"- {_localized(language, key)}: {optional_values[key]}"
        for key in OPTIONAL_ENTRY_FIELD_NAMES
        if key in optional_values
    )
    entry = (
        f"\n### {timestamp.isoformat(timespec='minutes')} — {values['title']}\n\n"
        + "\n".join(lines)
        + f"\n\n{marker}\n"
    )
    _append_text(path, entry)
    return True


def _session_start(
    payload: Mapping[str, Any], environment: Mapping[str, str], now: datetime
) -> dict[str, Any]:
    _session_state(payload, environment, now)
    return {}


def _user_prompt(
    payload: Mapping[str, Any], environment: Mapping[str, str], now: datetime
) -> dict[str, Any]:
    state, state_path = _session_state(payload, environment, now)
    turn_id = payload.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id:
        raise WorklogError("the prompt hook did not include a turn id")
    turn_token = _token(turn_id)
    intent = _prompt_intent(payload.get("prompt"))
    state["last_turn_started_at"] = now.isoformat(timespec="seconds")
    state["last_turn_token"] = turn_token
    state["last_turn_intent"] = intent
    state["last_turn_requires_entry"] = intent not in {
        "acknowledgement",
        "context_recovery",
    }
    _atomic_write_json(state_path, state)
    return {}


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
        state, state_path = _session_state(payload, environment, now)
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
    stored_intent = state.get("last_turn_intent")
    if (
        turn_token != state.get("last_turn_token")
        or stored_intent not in PROMPT_INTENTS
    ):
        stored_intent = (
            "acknowledgement"
            if turn_token == state.get("last_turn_token")
            and state.get("last_turn_requires_entry") is False
            else "unknown"
        )
    if stored_intent in {"acknowledgement", "context_recovery"}:
        state["last_skipped_at"] = now.isoformat(timespec="seconds")
        state["last_skipped_turn_token"] = turn_token
        _atomic_write_json(state_path, state)
        return {}
    marker = _marker(turn_token)
    if _contains_recent_marker(path, marker):
        state["last_appended_at"] = now.isoformat(timespec="seconds")
        state["last_appended_turn_token"] = turn_token
        _atomic_write_json(state_path, state)
        return {}
    if state.get("last_skipped_turn_token") == turn_token:
        return {}

    language = state.get("language")
    if not isinstance(language, str):
        language = _system_language(environment)
    workspace_value = state.get("workspace")
    if not isinstance(workspace_value, str):
        raise WorklogError("plugin state is missing the workspace path")
    entry = _automatic_entry(
        payload.get("last_assistant_message"),
        language,
        stored_intent,
        Path(workspace_value),
        path,
    )
    if entry is None:
        state["last_skipped_at"] = now.isoformat(timespec="seconds")
        state["last_skipped_turn_token"] = turn_token
        state["last_turn_requires_entry"] = False
        _atomic_write_json(state_path, state)
        return {}
    _append_entry(
        {
            "worklog_path": str(path),
            "marker": marker,
            **entry,
        },
        now=now,
        environment=environment,
        workspace=Path(workspace_value),
    )
    state["last_appended_at"] = now.isoformat(timespec="seconds")
    state["last_appended_turn_token"] = turn_token
    state["last_turn_token"] = turn_token
    state["last_turn_intent"] = stored_intent
    state["last_turn_requires_entry"] = True
    _atomic_write_json(state_path, state)
    return {}


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
    _state_worklog_path(state, payload)
    state["closed"] = True
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


def _append_main() -> int:
    try:
        raw_payload = sys.stdin.buffer.read(MAX_APPEND_INPUT_BYTES + 1)
        if len(raw_payload) > MAX_APPEND_INPUT_BYTES:
            raise WorklogError("append request is too large")
        payload = json.loads(raw_payload.decode("utf-8"))
        if not isinstance(payload, dict):
            raise WorklogError("append request must be a JSON object")
        appended = _append_entry(payload)
    except (json.JSONDecodeError, UnicodeError, WorklogError) as error:
        print(f"Codex Worklog append failed: {_safe_inline(error)}.", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 - CLI boundary must not leak a traceback.
        print(
            f"Codex Worklog append internal error: {type(error).__name__}",
            file=sys.stderr,
        )
        return 2
    json.dump({"appended": appended}, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


def _hook_main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise TypeError("hook input must be a JSON object")
        response = handle_event(payload)
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        response = {
            "systemMessage": f"Codex Worklog received invalid hook input: {error}."
        }
    except Exception as error:  # noqa: BLE001 - hooks must not crash Codex.
        print(
            f"Codex Worklog internal error: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        response = {"systemMessage": "Codex Worklog encountered an internal error."}
    json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


def main() -> int:
    arguments = sys.argv[1:]
    if arguments == ["append"]:
        return _append_main()
    if arguments:
        print("Codex Worklog: unknown command.", file=sys.stderr)
        return 2
    return _hook_main()


if __name__ == "__main__":
    raise SystemExit(main())
