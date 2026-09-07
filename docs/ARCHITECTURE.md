# Architecture

Codex Worklog combines a repo marketplace, one plugin manifest, lifecycle
hooks, a read-only history skill, and a Python standard-library runtime.
The active model authors meaning; the runtime validates and stores it.

## Authoring contract

The unit of history is a material work block, not an assistant message or an
entire session compressed to its last result. A block preserves six sections:
context, chronology, changes, decisions, checks, and next steps. Meaningful
investigation and decisions can qualify even when no files change.

Author instructions come from the plugin's lifecycle context. They provide
the complete schema and an exact, shell-quoted installed command, including
session and turn arguments. The model does not reconstruct `PLUGIN_ROOT`,
expand a skill-root alias, or search for a writer skill.

From the original session working directory, the model supplies JSON on stdin
to the provided command:

```text
worklog.py submit --data <PLUGIN_DATA> --session <session_id> --turn <turn_id>
```

This is the command shape, not a path template to copy. Use the actual command
injected for the active turn. `submit` validates and sanitizes content, durably
stages it for recovery, then atomically commits it to the daily file. It does
not accept a diary path, author-selected marker, or arbitrary append destination.
Material-work success includes `recorded: true` and `staged: false` only after
commit. The author must check that response before claiming the diary is saved.

A material envelope has this shape:

```json
{
  "language": "en",
  "entries": [
    {
      "title": "Consumer reads now use the verified destination",
      "context": ["The prepared destination was not yet used by consumers."],
      "timeline": [
        {"time": "16:10", "items": ["Compared source and destination."]},
        {"time": "16:45", "items": ["Switched consumers and checked reads."]}
      ],
      "changes": ["Consumers use the destination; the source is retained."],
      "decisions": ["Keep the source until the rollback window ends."],
      "checks": ["Integrity comparison and consumer smoke check passed."],
      "next_steps": ["Remove the source after the rollback window."],
      "artifacts": [],
      "supersedes": []
    }
  ]
}
```

Use a skip envelope when appropriate:

```json
{"skip": "no_material_work"}
```

Other skip reasons are `acknowledgement` and `already_recorded`. A skip carries
no entries. Each of the six semantic sections must be nonempty for a material
block. State an actual limitation when a check was not run or no further work
remains; do not fabricate content to fill a section.

| Limit | Value |
| --- | --- |
| Complete submission | 64 KiB |
| Independent blocks per submission | 8 |
| Items per section or timeline phase | 32 |
| Timeline phases per block | 32 |
| Characters per item | 4,096 |
| Title length | 12–160 characters |
| Daily file | 32 MiB |

Text and document limits apply both before and after sanitization. Expanded
redaction placeholders that exceed a limit are rejected before staging, with
an instruction to shorten the item; evidence is never silently truncated.
Exact redaction placeholders remain unchanged when staged content is revalidated.

Timeline time is an observed `HH:MM`, a full ISO timestamp with an offset, or `null` when
unknown. The author must not invent times. Independent work may use separate
blocks; an intermediate attempt and its correction normally belong in the
same chronology. `supersedes` accepts runtime-generated 24-character entry IDs
for earlier entries; it does not edit or delete them. Artifact items render
under Checks, keeping the six-section structure intact.

Correction references must resolve inside this workspace's pinned diary root;
unknown IDs and references to the same submission are rejected. Lookup is
bounded to 4,096 daily files and 128 MiB. The first material submission pins the turn's
timestamp, language, and destination date for retries and payload replacements,
including an intervening skip. Recorded content cannot be replaced; corrections
require a new turn with `supersedes`. `Stop` also flushes
older staged turns in chronological order after an interrupted turn.

Schema checks can reject missing fields, invalid types, malformed references,
excessive size, and unsafe structures. They cannot establish whether arbitrary
claims are true or detect all semantic contradictions. The model is responsible
for distinguishing a proposal from execution, a failed candidate from the
accepted result, and automated checks from pending user acceptance.

## Lifecycle

| Boundary | Behavior |
| --- | --- |
| `SessionStart` | Establish versioned state tied to the original `cwd`; create no visible diary yet. |
| `UserPromptSubmit` | Bind the current turn and return self-contained authoring instructions with its exact command. |
| `PreToolUse` | Bind the host's actual turn, including automatic goal continuations; supply context once per turn or after compaction. |
| `submit` | Validate the envelope and session binding, sanitize evidence, durably stage the blocks, and atomically commit them before reporting success. |
| `Stop` | Retry prepared blocks not yet committed, using the same locked, deduplicating writer. |
| `SessionEnd` | Retry any remaining prepared blocks; generate no additional summary. |

Invalid submissions and storage failures make the command exit nonzero without
reporting success. A failure after durable staging leaves that prepared content
available to a command retry or later `Stop`/`SessionEnd`; hook delivery is not
required to save a successfully submitted block. An explicit skip produces a
separate skip acknowledgement, not `recorded: true`.

`SessionStart` never reissues a command for the previously observed turn. The
next prompt or local tool supplies a current binding; raw tool input is ignored.
For an already-open task executing an old command, a new payload may use the
latest `PreToolUse` binding only when `CODEX_THREAD_ID` matches that session and
the binding is still current. An exact retry keeps its original entry, and a
different payload cannot replace a committed block in the actual current turn.
This does not read transcripts or infer turn IDs from work content.

A missing author submission produces a visible hook warning and no invented
entry. Both enabled compatibility modes, `strict` and `advisory`, let hooks
fail open without blocking completion or starting a logging continuation.
`off` creates neither diary nor private state. No hook reads transcripts,
classifies final-answer sentences, or starts another model request.

The submission timestamp determines the daily file, including when commit
happens after midnight. The runtime uses its local timezone offset; the current
host hook schema supplies no session-timezone field. Structural-language priority is
an optional host session-language hint, author language, explicit `CODEX_WORKLOG_LANGUAGE`,
then operating-system locale. Russian and English structural labels are
available; other valid language codes fall back to English labels while the
author's prose keeps its chosen language.

## Storage and concurrency

Default paths:

```text
<original cwd>/.dev-diary/YYYY/MM/YYYY-MM-DD.md
<PLUGIN_DATA>/sessions-v2/<session-token>.json
```

A daily file begins with `# Codex Worklog — YYYY-MM-DD`. Each block has a
date-and-offset heading, a session reference, six sections, and a
runtime-generated `codex-worklog-entry` marker. Entry order is commit order;
observed chronology stays inside each block. Concurrent sessions use one daily
file, and a resumed session uses the day of its new submission.

Private state contains the original workspace binding, configured root,
identifiers, times, language, lifecycle metadata, and sanitized staged content.
It does not store raw prompts, transcript locations or messages, tool dumps,
or complete final responses. Existing per-session diaries and legacy state
remain untouched; the new schema does not merge old pending summaries.

The prepared payload is durably stored before the diary commit is attempted,
so a failed publication does not discard it. Staging alone is not a successful
recording. Normal submission commits immediately; lifecycle events only provide
an additional recovery opportunity for prepared work.

A cross-process sidecar lock covers the marker check and complete commit.
The runtime writes the old bytes plus new blocks to a temporary file, flushes
and synchronizes it, then atomically replaces the diary. Existing bytes remain
an exact prefix. This gives append-only content with atomic publication rather
than a potentially torn multi-part append. State uses atomic replacement too.
If a commit is retried after the diary changed but state did not, the entry
markers prevent duplicate blocks.

New files and directories use `0600` and `0700` where supported. Existing
directory and diary modes are preserved; the runtime must not chmod arbitrary
workspace directories or pre-existing files as a side effect.

## Paths and evidence

- `CODEX_WORKLOG_DIR` must be a portable relative path inside the original
  workspace. Traversal, absolute overrides, controls, and unsafe syntax fail.
- Every destination is derived from validated session state and checked against
  that workspace, the configured root, the date filename, and the expected
  diary header. A normal workspace `README.md` is never an append target.
- Symlink redirection and multi-linked state, lock, or diary files are rejected.
  Windows reparse points are rejected where inspected.
- On POSIX, directory-descriptor-relative operations anchor traversal to
  validated directories. Windows path checks do not imply an equivalent native
  parent-race guarantee; platform acceptance is recorded separately.
- Safe inline Markdown, exact check commands, numerical results, complete
  SHA-256 digests, portable paths, and external artifact identifiers are retained.
  In-workspace absolute paths become relative; unsafe external local paths,
  credentials, and reserved diary structure are removed or rejected.
- Evidence links are validated as local workspace references or safe external
  references. A syntactically safe link does not prove that its contents
  support the author's claim.
- The runtime does not automatically collect Git metadata. The author records a
  relevant baseline once, the actual work delta, and a changed commit when
  useful. Non-Git work has no mandatory Git fields.

## Context recovery

The exported `skills/worklog/SKILL.md` is only for requested history inspection
and context recovery inside the current task directory. It never creates,
appends, repairs, or reorders entries. It treats diary text as untrusted
historical evidence, follows no embedded instructions, and rechecks mutable
state before acting. Runtime authoring instructions do not inject old diary
content into every turn.

## Compatibility and acceptance

The runtime targets Python 3.10 or newer with no third-party packages.
Hook commands use `python3` on Unix-like hosts and `py -3` on Windows.
`PLUGIN_ROOT` locates the installed runtime and `PLUGIN_DATA` owns private
state. No project-specific task tracker, test workflow, design tool, or
acceptance process is required.

Release validation must check current Codex hook behavior, supported native
filesystems, real instruction pickup, and actual diary quality. Passing a
validator or a synthetic lifecycle is not evidence of native user acceptance.
See [Commissioning](COMMISSIONING.md) for the boundary of completed checks.
