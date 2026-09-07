# Repository Instructions

## Purpose

This repository packages `codex-worklog`, a local Codex plugin that asks the active model to author structured work blocks and uses a runtime helper to validate and commit them to an append-only daily diary in the original session working directory. Lifecycle hooks supply authoring context and retry prepared work. A focused skill exposes that history only for inspection and context recovery.

## Structure

- `.agents/plugins/marketplace.json`: repo marketplace entry.
- `plugins/codex-worklog/.codex-plugin/plugin.json`: stable plugin identity and UI metadata.
- `plugins/codex-worklog/hooks/hooks.json`: lifecycle hook registration.
- `plugins/codex-worklog/scripts/worklog.py`: dependency-free runtime.
- `plugins/codex-worklog/skills/worklog/SKILL.md`: read-only history inspection and context-recovery workflow.
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
- Keep semantic authorship in the active model and filesystem writes in the
  runtime. Supply self-contained author instructions and an exact, quoted
  `submit` command through lifecycle context; never require the model to
  reconstruct skill aliases or plugin cache paths.
- Require six substantive sections for a material work block: context,
  chronology, changes, decisions, checks, and next steps. Preserve failed
  candidates, uncertainty, evidence, and remaining work. Skip trivial turns.
- `submit` validates and sanitizes structured data, durably stages it for
  recovery, and atomically commits it before returning `recorded: true` and
  `staged: false`. A storage error must fail with a nonzero exit status, retain
  prepared work for retry, and never report false success.
- `Stop` and `SessionEnd` retry prepared work; they are not the only commit
  boundary and must never invent a summary. Missing payloads produce a warning
  and no entry, never a regex-generated substitute or a continuation loop.
- Bind automatic turns through `PreToolUse`, not only `UserPromptSubmit`.
  Never reissue a stale turn command after compaction or weaken exact-retry
  deduplication to accept independent work.
- Derive every write target from validated session state. Preserve existing
  permissions and diary bytes; serialize marker checks and atomic commits.
- Keep the exported `worklog` skill read-only and limited to requested history inspection or context recovery; it must never perform routine appends.
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
