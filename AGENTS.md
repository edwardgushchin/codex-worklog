# Repository Instructions

## Purpose

This repository packages `codex-worklog`, a local Codex plugin that keeps a semantic, append-only worklog in the original session working directory and makes that history available for context recovery.

## Structure

- `.agents/plugins/marketplace.json`: repo marketplace entry.
- `plugins/codex-worklog/.codex-plugin/plugin.json`: stable plugin identity and UI metadata.
- `plugins/codex-worklog/hooks/hooks.json`: lifecycle hook registration.
- `plugins/codex-worklog/scripts/worklog.py`: dependency-free runtime.
- `plugins/codex-worklog/skills/worklog/SKILL.md`: manual inspection and context-recovery workflow.
- `tests/`: lifecycle, privacy, path-safety, and portability tests.
- `scripts/validate_repository.py`: repository contract check.

## Development Rules

- Reply in the user's language; keep source, comments, commits, and primary documentation in English.
- Preserve Python 3.10 compatibility and use the standard library in runtime code.
- Do not add production dependencies without explicit maintainer approval.
- Keep plugin and marketplace identifiers exactly `codex-worklog`.
- Keep `hooks/hooks.json` at the default discovery path; do not add a `hooks` field to `plugin.json` unless the current validator and official Codex specification both require it.
- Never persist raw prompts, transcripts, tool inputs, tool output, secrets, credentials, private keys, or unnecessary personal data.
- Reject path traversal and symbolic-link redirection. Never silently write outside session `cwd` or Codex `PLUGIN_DATA`.
- Keep Stop-hook continuation bounded by `stop_hook_active`.
- Treat worklogs as historical notes and verify mutable state before acting on them.
- Do not modify user Codex configuration, install the plugin, publish GitHub state, or create releases unless the current request authorizes it.
- Do not add generated `.dev-diary/`, plugin cache, bytecode, coverage, or local environment files to Git.

## Verification

After changes, run the narrowest relevant test, then the full local gate:

```bash
python3 -m compileall -q plugins scripts tests
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py
```

Before release, also run the current Codex plugin validator and a temporary installed-plugin smoke test on each supported operating-system family when practical.
