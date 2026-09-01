#!/usr/bin/env python3
"""Validate the distributable repository without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys

# Only guarded, size-limited local SVG assets reach this parser.
import xml.etree.ElementTree as element_tree  # nosec B405
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "codex-worklog"
MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
HOOKS = PLUGIN / "hooks" / "hooks.json"
WORKLOG_SKILL = PLUGIN / "skills" / "worklog" / "SKILL.md"
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
PLUGIN_NAME = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*$")
BRAND_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
ACTION_REFERENCE = re.compile(r"^\s*uses:\s*[^@\s]+@([^\s#]+)", re.MULTILINE)


REQUIRED_FILES = {
    ".agents/plugins/marketplace.json",
    ".editorconfig",
    ".gitattributes",
    ".github/CODEOWNERS",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".gitignore",
    ".markdownlint-cli2.yaml",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "LICENSE",
    "Makefile",
    "PRIVACY.md",
    "README.md",
    "README.ru.md",
    "RELEASING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "TERMS.md",
    "docs/ARCHITECTURE.md",
    "docs/COMMISSIONING.md",
    "docs/PROJECT_GOAL.md",
    "docs/THREAT_MODEL.md",
    "examples/EXAMPLE_WORKLOG.md",
    "examples/reports/MIGRATION_VERIFICATION.md",
    "plugins/codex-worklog/.codex-plugin/plugin.json",
    "plugins/codex-worklog/assets/icon.svg",
    "plugins/codex-worklog/assets/logo-dark.svg",
    "plugins/codex-worklog/assets/logo.svg",
    "plugins/codex-worklog/hooks/hooks.json",
    "plugins/codex-worklog/scripts/worklog.py",
    "plugins/codex-worklog/skills/worklog/SKILL.md",
    "scripts/validate_repository.py",
    "tests/test_validate_repository.py",
    "tests/test_worklog.py",
}


def load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{path.relative_to(ROOT)} is not valid JSON: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT)} must contain a JSON object")
        return {}
    return value


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _plugin_file(value: object) -> Path | None:
    if not isinstance(value, str) or not value.startswith("./"):
        return None
    candidate = PLUGIN / value
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(PLUGIN.resolve(strict=True))
    except (OSError, ValueError):
        return None
    if candidate.is_symlink() or not resolved.is_file():
        return None
    return resolved


def validate_manifest(errors: list[str]) -> None:
    manifest = load_object(MANIFEST, errors)
    name = manifest.get("name")
    if (
        name != PLUGIN.name
        or not isinstance(name, str)
        or not PLUGIN_NAME.fullmatch(name)
    ):
        errors.append(
            "plugin name must match its outer directory and use a valid identifier"
        )
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append("plugin version must use semantic versioning")
    for key in ("description", "homepage", "repository", "license"):
        if not _nonempty_string(manifest.get(key)):
            errors.append(f"plugin {key} must be a non-empty string")
    for key in ("homepage", "repository"):
        if not _https_url(manifest.get(key)):
            errors.append(f"plugin {key} must be an absolute HTTPS URL")
    author = manifest.get("author")
    if not isinstance(author, dict) or not _nonempty_string(author.get("name")):
        errors.append("plugin author.name must be a non-empty string")
    skills_directory = PLUGIN / "skills"
    if (
        manifest.get("skills") != "./skills/"
        or not skills_directory.is_dir()
        or skills_directory.is_symlink()
    ):
        errors.append("plugin skills must resolve to ./skills/")
    if "hooks" in manifest:
        errors.append("hooks must use default hooks/hooks.json discovery")
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin interface metadata is missing")
        return
    for key in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
    ):
        if not _nonempty_string(interface.get(key)):
            errors.append(f"plugin interface.{key} must be a non-empty string")
    capabilities = interface.get("capabilities")
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or not all(_nonempty_string(value) for value in capabilities)
    ):
        errors.append("plugin interface.capabilities must be a non-empty string array")
    prompts = interface.get("defaultPrompt")
    if (
        not isinstance(prompts, list)
        or not 1 <= len(prompts) <= 3
        or not all(
            isinstance(value, str) and 0 < len(value.strip()) <= 128
            for value in prompts
        )
    ):
        errors.append(
            "plugin interface.defaultPrompt must contain 1 to 3 strings of at most 128 characters"
        )
    for key in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
        if not _https_url(interface.get(key)):
            errors.append(f"plugin interface.{key} must be an absolute HTTPS URL")
    if not isinstance(interface.get("brandColor"), str) or not BRAND_COLOR.fullmatch(
        interface["brandColor"]
    ):
        errors.append("plugin interface.brandColor must be a six-digit hex color")
    for key in ("composerIcon", "logo", "logoDark"):
        value = interface.get(key)
        asset = _plugin_file(value)
        if asset is None or "assets" not in asset.relative_to(PLUGIN.resolve()).parts:
            errors.append(
                f"plugin interface.{key} does not point to a safe bundled asset"
            )


def validate_marketplace(errors: list[str]) -> None:
    marketplace = load_object(MARKETPLACE, errors)
    if marketplace.get("name") != "codex-worklog":
        errors.append("marketplace name must be codex-worklog")
    interface = marketplace.get("interface")
    if not isinstance(interface, dict) or not _nonempty_string(
        interface.get("displayName")
    ):
        errors.append("marketplace interface.displayName must be a non-empty string")
    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1:
        errors.append("marketplace must expose exactly one plugin")
        return
    entry = entries[0]
    expected_source = {"source": "local", "path": "./plugins/codex-worklog"}
    if not isinstance(entry, dict) or entry.get("name") != "codex-worklog":
        errors.append("marketplace plugin identifier is invalid")
    elif entry.get("source") != expected_source:
        errors.append("marketplace source must resolve to ./plugins/codex-worklog")
    if not isinstance(entry, dict):
        return
    policy = entry.get("policy")
    if not isinstance(policy, dict) or set(policy) != {
        "installation",
        "authentication",
    }:
        errors.append("marketplace policy must declare installation and authentication")
    elif policy != {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}:
        errors.append("marketplace policy must use AVAILABLE and ON_INSTALL")
    if entry.get("category") != "Productivity":
        errors.append("marketplace category must be Productivity")


def validate_hooks(errors: list[str]) -> None:
    hooks_document = load_object(HOOKS, errors)
    if not _nonempty_string(hooks_document.get("description")):
        errors.append("hooks description must be a non-empty string")
    hooks = hooks_document.get("hooks")
    expected_events = {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"}
    if not isinstance(hooks, dict) or set(hooks) != expected_events:
        errors.append("hook lifecycle events do not match the required contract")
        return
    for event_name, groups in hooks.items():
        if not isinstance(groups, list) or not groups:
            errors.append(f"{event_name} must contain at least one hook group")
            continue
        if len(groups) != 1:
            errors.append(f"{event_name} must contain exactly one hook group")
        for group in groups:
            if not isinstance(group, dict):
                errors.append(f"{event_name} hook group must be an object")
                continue
            if event_name == "SessionStart" and group.get("matcher") != (
                "startup|resume|clear|compact"
            ):
                errors.append(
                    "SessionStart matcher must cover startup, resume, clear, and compact"
                )
            if event_name != "SessionStart" and "matcher" in group:
                errors.append(f"{event_name} must not declare an unused matcher")
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list) or not handlers:
                errors.append(f"{event_name} has no command handler")
                continue
            if len(handlers) != 1:
                errors.append(f"{event_name} must contain exactly one command handler")
            for handler in handlers:
                if not isinstance(handler, dict):
                    errors.append(f"{event_name} command handler must be an object")
                    continue
                if handler.get("type") != "command":
                    errors.append(f"{event_name} must use a command hook")
                if (
                    handler.get("command")
                    != 'python3 -B "$PLUGIN_ROOT/scripts/worklog.py"'
                ):
                    errors.append(
                        f"{event_name} Unix command is not the reviewed runtime command"
                    )
                if handler.get("commandWindows") != (
                    'py -3 -B "%PLUGIN_ROOT%\\scripts\\worklog.py"'
                ):
                    errors.append(
                        f"{event_name} Windows command is not the reviewed runtime command"
                    )
                timeout = handler.get("timeout")
                expected_timeout = 3 if event_name == "SessionEnd" else 5
                if timeout != expected_timeout or isinstance(timeout, bool):
                    errors.append(
                        f"{event_name} timeout must be exactly {expected_timeout} seconds"
                    )
                if "additionalContextLimit" in handler:
                    errors.append(
                        f"{event_name} must not declare additionalContextLimit"
                    )
                if handler.get("async") is True:
                    errors.append(f"{event_name} must run synchronously")


def validate_worklog_skill(errors: list[str]) -> None:
    try:
        text = WORKLOG_SKILL.read_text(encoding="utf-8")
    except OSError as error:
        errors.append(f"worklog skill is unreadable: {error}")
        return
    required_boundaries = (
        "current task `cwd`",
        "user-wide memory registries",
        "do not use it as worklog evidence",
        "never create, append, repair, or reorder worklog entries",
        "report the absence instead",
    )
    for boundary in required_boundaries:
        if boundary not in text:
            errors.append(
                "worklog skill must keep history recovery inside the current cwd "
                f"and read-only ({boundary!r} is missing)"
            )


def validate_assets(errors: list[str]) -> None:
    for path in sorted((PLUGIN / "assets").glob("*.svg")):
        try:
            raw = path.read_bytes()
            if len(raw) > 256 * 1024:
                errors.append(f"{path.relative_to(ROOT)} exceeds the SVG size limit")
                continue
            lowered = raw.lower()
            if any(
                marker in lowered
                for marker in (
                    b"<!doctype",
                    b"<!entity",
                    b"<script",
                    b"javascript:",
                    b"<foreignobject",
                )
            ):
                errors.append(f"{path.relative_to(ROOT)} contains unsafe SVG content")
                continue
            # DTD and entity declarations were rejected before parsing.
            root = element_tree.fromstring(raw)  # nosec B314
            if root.tag.rsplit("}", 1)[-1] != "svg":
                errors.append(
                    f"{path.relative_to(ROOT)} does not have an SVG root element"
                )
            for element in root.iter():
                for attribute, value in element.attrib.items():
                    local_name = attribute.rsplit("}", 1)[-1].lower()
                    if local_name.startswith("on") or (
                        local_name == "href" and not value.startswith("#")
                    ):
                        errors.append(
                            f"{path.relative_to(ROOT)} contains an unsafe SVG attribute"
                        )
        except (OSError, element_tree.ParseError) as error:
            errors.append(f"{path.relative_to(ROOT)} is invalid SVG XML: {error}")


def validate_internal_links(errors: list[str]) -> None:
    for relative in (
        "README.md",
        "README.ru.md",
        "CONTRIBUTING.md",
        "GOVERNANCE.md",
        "PRIVACY.md",
        "RELEASING.md",
        "SECURITY.md",
        "SUPPORT.md",
        "TERMS.md",
        "docs/ARCHITECTURE.md",
        "docs/COMMISSIONING.md",
        "docs/THREAT_MODEL.md",
        "examples/EXAMPLE_WORKLOG.md",
    ):
        path = ROOT / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(ROOT.resolve()) or not resolved.exists():
                errors.append(f"{relative} contains a broken local link: {raw_target}")


def validate_action_pins(errors: list[str]) -> None:
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        references = ACTION_REFERENCE.findall(text)
        if not references:
            errors.append(
                f"{path.relative_to(ROOT)} contains no pinned action references"
            )
            continue
        for reference in references:
            if not re.fullmatch(r"[0-9a-fA-F]{40}", reference):
                errors.append(
                    f"{path.relative_to(ROOT)} contains an action that is not pinned to a full SHA"
                )


def validate_text_hygiene(errors: list[str]) -> None:
    forbidden = ("[TODO:", "YOUR-USER", "super-secret-value")
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or ".git" in path.parts
            or "__pycache__" in path.parts
            or ".ruff_cache" in path.parts
            or ".mypy_cache" in path.parts
        ):
            continue
        if path.suffix.lower() not in {".json", ".md", ".py", ".toml", ".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text and path.name not in {
                "test_worklog.py",
                "validate_repository.py",
            }:
                errors.append(
                    f"{path.relative_to(ROOT)} contains forbidden marker {marker!r}"
                )


def main() -> int:
    errors: list[str] = []
    missing = sorted(path for path in REQUIRED_FILES if not (ROOT / path).is_file())
    errors.extend(f"required file is missing: {path}" for path in missing)
    if MANIFEST.is_file():
        validate_manifest(errors)
    if MARKETPLACE.is_file():
        validate_marketplace(errors)
    if HOOKS.is_file():
        validate_hooks(errors)
    if WORKLOG_SKILL.is_file():
        validate_worklog_skill(errors)
    validate_assets(errors)
    validate_internal_links(errors)
    validate_action_pins(errors)
    validate_text_hygiene(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Repository contract passed ({len(REQUIRED_FILES)} required files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
