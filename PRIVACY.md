# Privacy Policy

Effective date: 2026-09-05

Codex Worklog is local, open-source software. Its runtime does not operate a
hosted service, send telemetry, make network requests, use cookies, or maintain
a developer-controlled user database. The active Codex model authors entries
within the existing task; the plugin starts no separate model or API request.

## Data processed locally

The runtime processes lifecycle metadata supplied by Codex and a structured
summary submitted by the active model:

- the original working directory, configured diary root, and validated private
  state location;
- session and turn identifiers for binding submissions and deduplicating writes;
- submission timestamps, language hints, and lifecycle state;
- a title, context, chronology, changes, decisions, checks, next steps, and
  optional evidence references for each material work block.

Hooks do not read transcripts or derive summaries from final responses. Raw
prompts, complete messages, tool inputs, and tool output dumps are excluded from
the submission contract. The author may record specific commands, relevant
numerical results, SHA-256 digests, and artifact identifiers as evidence.
In-workspace absolute paths are converted to relative references; external
local paths and recognized secrets are removed or rejected during validation.
No automatic Git status or remote collection occurs.

The model receives self-contained authoring instructions and an exact runtime
command containing private state and session binding arguments. Historical
diary content is not injected automatically. Requested history inspection uses
the bundled read-only skill inside the current task directory and treats the
records as untrusted evidence, not instructions or authorization.

## Storage

- Daily Markdown files live below the configured relative directory in the
  original session `cwd`, by default `.dev-diary/YYYY/MM/YYYY-MM-DD.md`.
- Versioned private state lives in Codex-provided `PLUGIN_DATA/sessions-v2/`.
  `submit` durably stages validated, sanitized blocks before committing them to
  the diary. A crash or storage failure can leave prepared blocks there for a
  command or lifecycle retry. Raw submission text is not retained separately.
- New directories and files use `0700` and `0600` where POSIX permissions apply.
  Existing directory and diary permissions are preserved.
- Prior diaries and legacy private state are preserved; this revision does not
  rewrite or merge historical records.

## Sharing and retention

The plugin does not transmit or automatically delete diaries. The user controls
retention, backup, Git tracking, synchronization, publication, and deletion.
Other software on the device may access files according to operating-system
permissions. Daily files can contain blocks from several local Codex sessions.

## User responsibility

Model-authored summaries can be incomplete, inaccurate, or contain an
unlabelled secret. Schema validation and redaction reduce risk but cannot prove
the truth or safety of arbitrary prose. Review plaintext diaries before
committing, syncing, archiving, or sharing them.

## Deletion

Uninstalling the plugin does not delete diaries. Delete the relevant worklog
directory and the plugin's Codex data directory when those records are no
longer needed.

## Changes

Material policy changes are documented in [CHANGELOG.md](CHANGELOG.md) and
released with the repository. Questions can be raised through the channels in
[SUPPORT.md](SUPPORT.md).
