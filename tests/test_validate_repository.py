from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class RepositoryValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "candidate"
        shutil.copytree(
            REPOSITORY_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(
                ".git",
                "__pycache__",
                ".coverage",
                ".ruff_cache",
                ".mypy_cache",
            ),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/validate_repository.py"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )

    def read_json(self, relative: str) -> dict[str, Any]:
        value = json.loads((self.root / relative).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            self.fail(f"{relative} is not a JSON object")
        return value

    def write_json(self, relative: str, value: dict[str, Any]) -> None:
        (self.root / relative).write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8"
        )

    def assert_validation_error(self, expected: str) -> None:
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(expected, completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_current_repository_contract_passes(self) -> None:
        completed = self.run_validator()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Repository contract passed", completed.stdout)

    def test_marketplace_is_required(self) -> None:
        (self.root / ".agents/plugins/marketplace.json").unlink()

        self.assert_validation_error("required file is missing")

    def test_default_prompt_must_be_a_bounded_string_array(self) -> None:
        relative = "plugins/codex-worklog/.codex-plugin/plugin.json"
        manifest = self.read_json(relative)
        manifest["interface"]["defaultPrompt"] = "not-an-array"
        self.write_json(relative, manifest)

        self.assert_validation_error("defaultPrompt must contain 1 to 3 strings")

    def test_marketplace_policy_and_category_are_validated(self) -> None:
        relative = ".agents/plugins/marketplace.json"
        marketplace = self.read_json(relative)
        marketplace["plugins"][0]["policy"]["authentication"] = "NEVER"
        marketplace["plugins"][0].pop("category")
        self.write_json(relative, marketplace)

        self.assert_validation_error(
            "marketplace policy must use AVAILABLE and ON_INSTALL"
        )

    def test_malformed_hook_handler_fails_without_crashing(self) -> None:
        relative = "plugins/codex-worklog/hooks/hooks.json"
        hooks = self.read_json(relative)
        hooks["hooks"]["Stop"][0]["hooks"] = ["not-an-object"]
        self.write_json(relative, hooks)

        self.assert_validation_error("Stop command handler must be an object")

    def test_duplicate_hook_handlers_are_rejected(self) -> None:
        relative = "plugins/codex-worklog/hooks/hooks.json"
        hooks = self.read_json(relative)
        handler = hooks["hooks"]["Stop"][0]["hooks"][0]
        hooks["hooks"]["Stop"][0]["hooks"].append(handler.copy())
        self.write_json(relative, hooks)

        self.assert_validation_error("Stop must contain exactly one command handler")

    def test_github_actions_must_use_full_commit_shas(self) -> None:
        workflow = self.root / ".github/workflows/ci.yml"
        text = workflow.read_text(encoding="utf-8")
        text = text.replace(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/checkout@v7",
        )
        workflow.write_text(text, encoding="utf-8")

        self.assert_validation_error("not pinned to a full SHA")

    def test_unsafe_svg_content_is_rejected(self) -> None:
        icon = self.root / "plugins/codex-worklog/assets/icon.svg"
        icon.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>\n',
            encoding="utf-8",
        )

        self.assert_validation_error("contains unsafe SVG content")


if __name__ == "__main__":
    unittest.main()
