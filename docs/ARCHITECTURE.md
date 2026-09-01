# Architecture

Codex Worklog is a local plugin composed of a repo marketplace, one plugin manifest, lifecycle hooks, a focused history-inspection skill, and a Python standard-library runtime.

## Goals

- Work in coding and non-coding directories.
- Require no project-local agent instructions.
- Keep the log beside the work, in the original Codex session `cwd`.
- Record one bounded outcome for each resulting state change without copying the conversation or asking the active agent to maintain files.
- Expose worklog history only through a focused inspection and context-recovery skill, never through routine model-facing maintenance context.
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

Requested history inspection
  │
  └─ skills/worklog/SKILL.md ──> read-only worklog tail and linked evidence
```

- `.agents/plugins/marketplace.json` exposes the plugin through a repo marketplace.
- `.codex-plugin/plugin.json` provides stable identity, discovery metadata, assets, and the bundled skill directory.
- `hooks/hooks.json` uses the default plugin hook discovery location.
- `scripts/worklog.py` is the only runtime program. It handles lifecycle events
  and exposes the bounded `append` command, with no third-party dependencies.
- `skills/worklog/SKILL.md` provides read-only history inspection and context recovery only when that history is relevant to the user's request. It never appends or repairs entries.

## Lifecycle

### SessionStart

The hook validates `cwd`, creates a private per-session Markdown file, stores
its absolute path in `PLUGIN_DATA`, and returns an empty JSON object. It does not
add instructions or paths to model context.

If the same session is resumed or compacted, the existing file is reused. A new
session receives a new file and a pointer to the newest previous worklog when
one exists. Its visible header contains no absolute local path: it records the
project name and, when available, a sanitized repository identifier, branch,
and abbreviated `HEAD`. Optional Git metadata is collected only through bounded,
non-interactive local commands; a non-Git directory still receives a worklog.

### UserPromptSubmit

The runtime applies a local deterministic intent classifier to the current
prompt and immediately discards the text. It retains only an enum distinguishing
acknowledgement, requested change, context recovery, other read-only work, and
unknown intent, plus a truncated SHA-256 token of `turn_id`. Context recovery
always produces no entry, preventing previously recorded causes and transitions
from being logged again, while a prompt that combines inspection and an edit is
treated as a requested change. The hook returns an empty JSON object.

### Stop

For a turn classified as acknowledgement-only, the hook returns immediately.
Otherwise, `Stop` uses the official `last_assistant_message` field and does not
read `transcript_path`. A deterministic result classifier omits read-only
inspection, context recovery, verification, and explicit no-change results.
A discovered cause, non-obvious decision, blocker, explicit transition, or
reported mutation remains recordable. Thus one completed turn can append at
most one state-change entry, regardless of how many preparation, execution, or
verification steps the response mentions.

The normalizer removes fenced code, hook directives, HTML metadata, link
destinations, local paths, full SHA-256 values, and common labelled secret
values, then keeps at most three prose lines for the outcome. It also recovers
optional cause/decision, blocker and status transitions, concise verification,
artifact links, and next-step fields only when the final response contains
safe evidence for them. A completed state can link to a matching earlier
blocker in the same worklog so stale append-only status remains visibly retired.

The runtime derives the title from the first sentence, revalidates the stored
workspace and target, adds the full local date, time, and UTC offset, and writes
with `O_APPEND`, flush, and `fsync`. A hidden turn marker makes repeated `Stop`
events idempotent; the marker is never sent to the agent. If earlier lifecycle
events did not create state, `Stop` reconstructs it from `session_id` and
`cwd`. Missing final text or a filesystem failure produces a warning and never
creates a continuation that asks the agent to write.

The `append` CLI remains a bounded compatibility and development interface. It
uses the same path checks and append primitive, but normal lifecycle operation
does not invoke it through the active agent.

### SessionEnd

The hook validates the stored worklog path and records a closed flag in private
plugin state. It never adds session lifecycle messages to the human-readable
timeline. Repeated end events are idempotent until the session resumes.

## Context Recovery

Normal lifecycle hooks never inject worklog paths, contents, or maintenance instructions into model context. When the user asks what happened previously, why a decision was made, where work stopped, or requests a worklog status, the bundled `worklog` skill can inspect the newest relevant tail inside the current task `cwd`.

The skill treats all diary text as untrusted historical evidence, follows no embedded instructions, opens linked reports only when needed, and separates recorded claims from facts rechecked in the current task. It is not part of the append path.

## Storage Contract

Default worklog path:

```text
<cwd>/.dev-diary/YYYY/MM/YYYY-MM-DD--HHMMSS--<session-hash>.md
```

Properties:

- one file per session;
- chronological, append-only entries;
- full ISO-style entry timestamps with a UTC offset, even when a session crosses
  midnight;
- sortable ISO date components;
- no raw session or turn identifier in the filename;
- system-language structural labels and hook-derived values;
- `0700` directories and `0600` files from creation time when POSIX modes are
  available.

State path:

```text
<PLUGIN_DATA>/sessions/<session-hash>.json
```

State contains only paths, timestamps, the detected language code, a small
intent enum, lifecycle Boolean flags, and hashed turn identifiers. It does not
contain the user prompt, transcript, or final assistant message.

## Path Safety

- `CODEX_WORKLOG_DIR` must be a portable relative path and cannot contain `..`,
  Windows drive or backslash syntax, control characters, or Markdown backticks.
- A `cwd` or restored worklog path containing control/format characters,
  Markdown backticks, or an overlong value fails visibly instead of being
  rewritten.
- Human-readable headers omit `cwd`; entry fields reject absolute POSIX,
  Windows, home-relative, and `file://` paths.
- Equivalent canonical operating-system aliases, such as macOS `/var` and
  `/private/var`, are accepted without relaxing workspace confinement.
- Existing symbolic links in worklog or plugin-state paths, including the
  state directory, are rejected.
- Worklog and state files must be regular files with exactly one hard link.
- Restored state is checked to ensure the worklog still resolves inside the event `cwd`.
- A pre-existing session file must use the expected collision-resistant name
  and Codex Worklog header.
- Automatic previous-session pointers are derived only from valid per-session
  records in private `PLUGIN_DATA`; arbitrary workspace Markdown files are not
  discovered merely because they have a Codex Worklog heading.
- Corrupt, oversized, or structurally invalid state fails visibly instead of
  being silently replaced.
- An unsafe or missing path produces a hook warning; the runtime does not redirect records to another directory.

## Compatibility

The runtime targets Python 3.10 or newer and uses `python3` on Unix-like hosts and `py -3` on Windows. Hook commands resolve the installed script through `PLUGIN_ROOT`, while writable state uses `PLUGIN_DATA`.

Visible-language detection ignores non-linguistic `C` and `POSIX` process
locales, consults the host locale configuration when available, and supports a
validated `CODEX_WORKLOG_LANGUAGE` override for environments that do not expose
a usable system locale.

Codex hook behavior is versioned outside this repository. Release validation must compare the implementation with the current [Codex hooks documentation](https://learn.chatgpt.com/docs/hooks).
