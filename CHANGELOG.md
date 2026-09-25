# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-09-25

### Fixed

- Explain when a workspace-write shell cannot write the plugin's private state,
  and direct the author to request scoped filesystem approval for the exact
  submit command. Repeat the permission guidance after compaction without
  changing submission or deduplication semantics.
- Distinguish read-only and permission-denied storage errors from missing or
  linked files. A refused approval remains an explicit failure, never a false
  diary commit or an automatic full-access retry.

## [1.0.1] - 2026-09-21

### Fixed

- Keep the reviewed runtime under `PLUGIN_DATA/runtimes-v1/<sha256>.py`
  before delivering author commands. Already loaded hooks, outstanding submit
  commands, next turns and staged retries survive removal of the installed cache.
  Pin the digest in the trusted hook definition; never select a newer cached
  version or execute a mismatched retained file. Pre-retention tasks still need
  a one-time reload of reviewed hooks.
- Require actual diary commits after native cache replacement in regression
  coverage, rather than only checking nonblocking warnings.

## [1.0.0] - 2026-09-21

### Changed

- Record bounded, local launch diagnostics under `PLUGIN_DATA/diagnostics-v1`,
  including runtime identity changes, missing files, and startup failures.
  Record observer PIDs separately from unknown change initiators; never log
  prompts, tool data, exception messages, or absolute paths.
- Add an explicit audited update helper with operation IDs, before/after cache
  versions, and start/completion/failure records. Native UI and unrelated
  processes remain outside this helper's attribution boundary.

### Fixed

- Repeat the current author command and a short schema on `PreToolUse` until
  the turn is recorded or explicitly skipped, instead of treating initial
  context delivery as sufficient. Preserve staged data, exact retries, and
  non-blocking hooks without adding Stop continuations or synthetic entries.
- Handle a task's workspace change on a new host turn without losing its
  author command. Preserve old diary bytes and staged destinations; defer
  retries outside the current workspace until the task returns there. Keep
  direct submissions and existing turns from changing their workspace binding.
- Promote moved sessions to state version 3 so older runtimes reject them
  instead of retrying old prepared blocks in the new workspace.
- Embed the hook-only launcher and reviewed storage guards in each saved hook
  command, so losing the complete plugin cache cannot yield exit code 2, block
  tools, or request Stop continuations. Direct `submit` retains nonzero failures.
- Exercise missing and replaced packages, startup failures, concurrent audit
  writes, path protection, and a real isolated native CLI reinstall.

## [0.3.0] - 2026-09-08

### Changed

- Replace final-answer and commentary classification with active-model authored
  work blocks containing context, chronology, changes, decisions, checks, and
  next steps. Sections retain bounded lists instead of flattened sentences.
- Supply universal authoring instructions and an exact installed `submit`
  command in lifecycle context. The read-only history skill stays separate.
- Validate and durably stage JSON submissions, then atomically commit them
  inside `submit` to one daily file; `Stop` and `SessionEnd` retry prepared work.
- Preserve failed attempts, explicit superseding references, evidence links,
  exact commands, numerical results, SHA-256 digests, and safe relative paths.
  In-workspace absolute paths become relative references.
- Prefer host session language and the author's language before an explicit
  override or operating-system locale. Remove automatic Git status/HEAD fields.
- Keep old diaries and legacy private state unchanged while new submissions
  use a separate `sessions-v2` schema.

### Fixed

- Preserve public evidence paths beneath canonical workspace ancestors such as
  macOS `/private/var`, while still redacting project-relative private paths.
  Use canonical temporary test roots for macOS aliases and Windows short names.
- Keep exact redaction placeholders stable during staged-content revalidation.
  Enforce text limits after sanitization before staging, preserving any earlier
  prepared submission and avoiding a payload that cannot be committed.
- Bind automatic goal continuations through `PreToolUse` and refresh author
  context after compaction instead of reusing the first user turn. Safely map
  stale commands from the same live host session to its current bound turn;
  preserve exact retries and immutable committed blocks.
- Return `recorded: true` and `staged: false` only after `submit` commits the
  daily diary, so a missing end hook cannot leave a successful submission
  unwritten. Storage failures exit nonzero without false success and retain
  prepared blocks for command or hook retries.
- Avoid empty diaries by creating a daily file only when a material block is
  committed. Acknowledgements and already-recorded work use explicit skips.
- Warn and skip when an author payload is missing; do not fabricate a fallback
  from short replies or start a logging continuation.
- Remove the author's need to reconstruct skill aliases and cache paths.
- Serialize marker detection and daily commits across concurrent sessions;
  publish complete replacements while preserving all previous bytes.

### Security

- Derive write targets only from validated session state; reject arbitrary
  caller-selected diary paths and markers, wrong headers, symlinks, and
  multi-linked files. Anchor supported POSIX traversal to directory descriptors.
- Preserve existing directory and diary permissions; private modes apply to
  newly created objects.
- Validate and redact bounded payloads before staging. Hooks no longer read
  transcripts or retain raw prompts, tool dumps, or complete assistant messages.
- Document that schema checks cannot prove semantic truth or detect every
  secret, and keep native platform acceptance separate from source validation.

## [0.2.0] - 2026-09-01

### Added

- Added optional cause/decision, blocker-link, status-transition, and artifact
  fields so append-only entries can explicitly retire stale state and point to
  detailed reports.

### Changed

- Moved routine entry creation entirely into lifecycle hooks. `SessionStart`
  and `UserPromptSubmit` no longer inject paths, schemas, markers, or file-work
  instructions into model context; `Stop` appends directly from a bounded
  normalized subset of `last_assistant_message`.
- Limited the exported `worklog` skill to requested history inspection and
  context recovery; routine logging remains entirely hook-owned and supplies
  no maintenance instructions to the active agent.
- Added the full date and UTC offset to every entry heading and switched diary
  labels to the detected system language.
- Replaced the visible absolute workspace path with portable project name and,
  when available, sanitized repository, branch, and abbreviated `HEAD`
  metadata.
- Reduced verification text to the checked item and result; detailed logs,
  complete test inventories, and full digests now belong in linked reports.

### Fixed

- Replaced generic project-scope wording with a concrete description of
  automatic semantic worklogging and made the README logo switch to its
  high-contrast variant in dark mode.
- Made `Stop` reconstruct missing session state when earlier lifecycle hooks
  were skipped, and replaced missing-marker continuation prompts with a direct
  idempotent hook-owned append.
- Prevented read-only inspection, context recovery, verification, and explicit
  no-change outcomes from creating misleading timeline entries. Causes,
  decisions, transitions, and newly discovered blockers remain recordable.
- Extract optional cause/decision, blocker link, status transition, concise
  verification, artifact, and next-step fields in the normal lifecycle path.
- Fall back from a non-linguistic hook-process locale to the host locale
  configuration, with a validated explicit language override when needed.
- Confined requested worklog recovery to the current task `cwd` and prohibited
  the bundled skill from initiating global-memory or conversation-history
  searches; context recovery itself never re-appends historical fields.
- Made POSIX absolute-path rejection independent of the host operating system
  and kept append-validation diagnostics ASCII-safe on Windows.

### Security

- Reject absolute local paths and full SHA-256 values from entry fields, strip
  credentials from repository metadata, and validate project-relative artifact
  links before appending them.
- Strip fenced code, hook metadata, link targets, local paths, full SHA-256
  values, and common labelled secrets from automatic summaries; generic token
  and private-key assignments plus unquoted local paths containing spaces are
  covered explicitly. Never store the complete final response in plugin state.

## [0.1.0] - 2026-08-30

### Added

- Repo-scoped Codex marketplace and installable `codex-worklog` plugin.
- Workspace-local, per-session append-only Markdown worklogs for coding and
  non-coding tasks.
- `SessionStart`, `UserPromptSubmit`, `Stop`, and `SessionEnd` lifecycle hooks.
- Context recovery from the current and latest plugin-recorded previous worklog.
- Strict, advisory, and disabled enforcement modes.
- Secret-safe state that excludes raw prompts, transcripts, and tool output.
- Cross-platform Python standard-library runtime and automated tests.
- English and Russian documentation plus full community health files.
- Documented the project mission, measurable success criteria, product
  boundaries, and external-audit standard.
- Added a sanitized worklog that demonstrates concise material entries, resume
  ordering, context recovery, optional fields, and acknowledgement omission.

### Changed

- Routed material turn entries through one bounded append helper instead of a
  general-purpose model file edit.
- Reduced the entry contract to required `title` and `summary` fields; `changes`,
  `verification`, and `next` are optional and omitted instead of receiving
  boilerplate. Removed the separate `decisions` field.
- Removed visible session/model metadata and automatic session checkpoints from
  human-readable worklogs.
- Skip timeline entries for acknowledgement-only turns; prompts with any
  additional instruction, question, cancellation, or decision remain material.
- Derive automatic previous-session pointers only from private plugin state,
  and treat all worklog text as untrusted history rather than instructions or
  authorization.
- Added a resume regression that requires all pre-resume bytes to remain an
  exact prefix of the updated worklog.
- Expanded lifecycle, path-safety, state-integrity, validator, and CLI regression coverage.
- Hardened repository validation for manifest metadata, marketplace policy, hook commands, SVG assets, local links, and immutable GitHub Action references.
- Updated the CI matrix to exercise minimum Python 3.10 and current Python 3.14.

### Fixed

- Changed `interface.defaultPrompt` to the current bounded string-array schema.
- Replaced a nonexistent CodeQL action commit with the verified `v4.37.9` commit.
- Made the repo marketplace and validator themselves mandatory repository artifacts.
- Removed a contributor-clone placeholder that looked like a live URL.
- Accept canonical workspace aliases such as macOS `/var` → `/private/var`
  while retaining rejection of symlinked worklog components.

### Security

- The append helper uses a fixed schema, bounded single-line fields, workspace
  path revalidation, exact turn markers, and `O_APPEND` writes with `fsync`.
- Reject symbolic or hard-linked worklog and state files before runtime reads and appends.
- Create private files and directories with restrictive modes from the initial filesystem operation.
- Reject non-portable directory overrides, invalid hook paths, corrupt, oversized, or cross-workspace state, and sanitize control characters in model-visible metadata.
- Reduced GitHub workflow token permissions and disabled checkout credential persistence.

[Unreleased]: https://github.com/edwardgushchin/codex-worklog/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/edwardgushchin/codex-worklog/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/edwardgushchin/codex-worklog/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/edwardgushchin/codex-worklog/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/edwardgushchin/codex-worklog/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/edwardgushchin/codex-worklog/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/edwardgushchin/codex-worklog/releases/tag/v0.1.0
