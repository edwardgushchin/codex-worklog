#!/usr/bin/env python3
"""Validate the distributable repository without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as element_tree
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "codex-worklog"
MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
HOOKS = PLUGIN / "hooks" / "hooks.json"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


REQUIRED_FILES = {
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
    "docs/THREAT_MODEL.md",
    "plugins/codex-worklog/.codex-plugin/plugin.json",
    "plugins/codex-worklog/assets/icon.svg",
    "plugins/codex-worklog/assets/logo-dark.svg",
    "plugins/codex-worklog/assets/logo.svg",
    "plugins/codex-worklog/hooks/hooks.json",
    "plugins/codex-worklog/scripts/worklog.py",
    "plugins/codex-worklog/skills/worklog/SKILL.md",
    "tests/test_worklog.py",
}


def load_object(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{path.relative_to(ROOT)} is not valid JSON: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT)} must contain a JSON object")
        return {}
    return value


def validate_manifest(errors: list[str]) -> None:
    manifest = load_object(MANIFEST, errors)
    if manifest.get("name") != PLUGIN.name:
        errors.append("plugin name must match its outer directory")
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        errors.append("plugin version must be strict semantic versioning")
    if manifest.get("skills") != "./skills/":
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
        "capabilities",
        "defaultPrompt",
    ):
        if key not in interface:
            errors.append(f"plugin interface.{key} is missing")
    for key in ("composerIcon", "logo", "logoDark"):
        value = interface.get(key)
        if not isinstance(value, str) or not (PLUGIN / value).is_file():
            errors.append(f"plugin interface.{key} does not point to an asset")


def validate_marketplace(errors: list[str]) -> None:
    marketplace = load_object(MARKETPLACE, errors)
    if marketplace.get("name") != "codex-worklog":
        errors.append("marketplace name must be codex-worklog")
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
    policy = entry.get("policy") if isinstance(entry, dict) else None
    if not isinstance(policy, dict) or set(policy) != {"installation", "authentication"}:
        errors.append("marketplace policy must declare installation and authentication")


def validate_hooks(errors: list[str]) -> None:
    hooks = load_object(HOOKS, errors).get("hooks")
    expected_events = {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"}
    if not isinstance(hooks, dict) or set(hooks) != expected_events:
        errors.append("hook lifecycle events do not match the required contract")
        return
    for event_name, groups in hooks.items():
        if not isinstance(groups, list) or not groups:
            errors.append(f"{event_name} must contain at least one hook group")
            continue
        for group in groups:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list) or not handlers:
                errors.append(f"{event_name} has no command handler")
                continue
            for handler in handlers:
                if handler.get("type") != "command":
                    errors.append(f"{event_name} must use a command hook")
                if "$PLUGIN_ROOT/scripts/worklog.py" not in handler.get("command", ""):
                    errors.append(f"{event_name} does not use PLUGIN_ROOT on Unix")
                if "%PLUGIN_ROOT%\\scripts\\worklog.py" not in handler.get(
                    "commandWindows", ""
                ):
                    errors.append(f"{event_name} does not use PLUGIN_ROOT on Windows")
                if event_name == "SessionEnd" and handler.get("timeout", 99) > 3:
                    errors.append("SessionEnd timeout exceeds the Codex maximum")


def validate_assets(errors: list[str]) -> None:
    for path in sorted((PLUGIN / "assets").glob("*.svg")):
        try:
            element_tree.parse(path)
        except element_tree.ParseError as error:
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
        "docs/THREAT_MODEL.md",
    ):
        path = ROOT / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(ROOT.resolve()) or not resolved.exists():
                errors.append(f"{relative} contains a broken local link: {raw_target}")


def validate_text_hygiene(errors: list[str]) -> None:
    forbidden = ("[TODO:", "super-secret-value")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".json", ".md", ".py", ".toml", ".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text and path.name not in {
                "test_worklog.py",
                "validate_repository.py",
            }:
                errors.append(f"{path.relative_to(ROOT)} contains forbidden marker {marker!r}")


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
    validate_assets(errors)
    validate_internal_links(errors)
    validate_text_hygiene(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Repository contract passed ({len(REQUIRED_FILES)} required files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
