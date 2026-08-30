# Architecture

Codex Worklog is a local plugin composed of a repo marketplace, one plugin manifest, lifecycle hooks, a Python standard-library runtime, and a context-recovery skill.

## Goals

- Work in coding and non-coding directories.
- Require no project-local agent instructions.
- Keep the log beside the work, in the original Codex session `cwd`.
- Explain what happened, when, and why without copying the conversation.
- Give a resumed or compacted agent a bounded path back to relevant context.
- Avoid collisions between concurrent Codex tasks.
- Fail visibly when the requested location is unsafe or unwritable.

## Components

```text
Codex host
  │
  ├─ SessionStart ───────┐
  ├─ UserPromptSubmit ───┼─> hooks/hooks.json
  ├─ Stop ───────────────┤          │
  └─ SessionEnd ─────────┘          v
                              scripts/worklog.py
                                │           │
                                │           └─ PLUGIN_DATA/sessions/<hash>.json
                                v
                   <session cwd>/.dev-diary/YYYY/MM/<session>.md
```

- `.agents/plugins/marketplace.json` exposes the plugin through a repo marketplace.
- `.codex-plugin/plugin.json` provides stable identity, discovery metadata, assets, and the `worklog` skill path.
- `hooks/hooks.json` uses the default plugin hook discovery location.
- `scripts/worklog.py` is the only runtime program. It handles lifecycle events
  and exposes the bounded `append` command, with no third-party dependencies.
- `skills/worklog/SKILL.md` handles explicit history inspection and context recovery.

## Lifecycle

### SessionStart

The hook validates `cwd`, creates a private per-session Markdown file, and stores its absolute path in `PLUGIN_DATA`. Startup context tells the agent:

- where to append entries;
- which semantic fields to record;
- how to redact sensitive information;
- how to recover context after resume or compaction;
- that mutable state must be checked again.

If the same session is resumed or compacted, the existing file is reused. A new session receives a new file and a pointer to the newest previous worklog when one exists.

### UserPromptSubmit

The runtime applies a local, deterministic exact-phrase classifier to the
current prompt and immediately discards the text. A short prompt made entirely
of a recognized acknowledgement is marked as non-material; any additional word
keeps the normal logging contract. Only the resulting Boolean is retained.

For a material turn, the runtime hashes `turn_id` with SHA-256, truncates the
digest, and supplies the installed helper path, its exact input schema, and an
exact Markdown marker. The marker proves only that an entry was appended for
the turn; it does not authenticate content.

### Append helper

The agent invokes `scripts/worklog.py append` once from the session `cwd` and
sends a bounded JSON object on standard input. The helper requires the exact
semantic field set, rejects multiline/control content and reserved markers,
revalidates the worklog as a regular single-link file inside that `cwd`, adds
the local timestamp, and writes with `O_APPEND`, flush, and `fsync`.

If the exact turn marker already exists in the recent tail, the helper returns
success without adding a duplicate. The agent does not perform separate path
inspection or a general-purpose Markdown edit.

### Stop

For a turn classified as acknowledgement-only, the hook returns immediately.
For a material turn, it reads only the tail of the current worklog and searches
for the exact turn marker.

- `strict`: ask Codex for one continuation when missing;
- `advisory`: show a warning without continuing;
- `off`: do nothing.

`stop_hook_active` prevents an infinite continuation loop. A second miss produces a warning and allows the turn to end.

### SessionEnd

The hook appends a small checkpoint only if material work occurred since the
previous checkpoint, then records a closed flag. Repeated end events are
idempotent until the session resumes. An acknowledgement-only resume therefore
does not alter the existing worklog bytes.

## Storage Contract

Default worklog path:

```text
<cwd>/.dev-diary/YYYY/MM/YYYY-MM-DD--HHMMSS--<session-hash>.md
```

Properties:

- one file per session;
- chronological, append-only entries;
- sortable ISO date components;
- no raw session or turn identifier in the filename;
- `0700` directories and `0600` files from creation time when POSIX modes are
  available.

State path:

```text
<PLUGIN_DATA>/sessions/<session-hash>.json
```

State contains only paths, timestamps, lifecycle Boolean flags, an end counter,
and hashed turn identifiers. It does not contain the user prompt or transcript.

## Context Recovery

Context recovery is deliberately progressive:

1. read the tail of the current session file;
2. consult the newest relevant earlier session only if needed;
3. summarize objective, decisions, evidence, blockers, and next steps;
4. verify live or time-sensitive state before taking action.

This avoids injecting every historical entry into the model context and reduces the chance of stale notes overriding current evidence.

## Path Safety

- `CODEX_WORKLOG_DIR` must be a portable relative path and cannot contain `..`,
  Windows drive or backslash syntax, control characters, or Markdown backticks.
- A `cwd` or restored worklog path containing control/format characters,
  Markdown backticks, or an unbounded model-context value fails visibly instead
  of supplying an altered path to the agent.
- Existing symbolic links in worklog or plugin-state paths, including the
  state directory, are rejected.
- Worklog and state files must be regular files with exactly one hard link.
- Restored state is checked to ensure the worklog still resolves inside the event `cwd`.
- A pre-existing session file must contain the expected hashed session marker.
- Previous-session pointers consider only regular, single-link Markdown files
  with the Codex Worklog header; unrelated files and links are ignored.
- Corrupt, oversized, or structurally invalid state fails visibly instead of
  being silently replaced.
- An unsafe or missing path produces a model-visible warning; the runtime does not redirect records to another directory.

## Compatibility

The runtime targets Python 3.10 or newer and uses `python3` on Unix-like hosts and `py -3` on Windows. Hook commands resolve the installed script through `PLUGIN_ROOT`, while writable state uses `PLUGIN_DATA`.

Codex hook behavior is versioned outside this repository. Release validation must compare the implementation with the current [Codex hooks documentation](https://learn.chatgpt.com/docs/hooks).
