# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/edwardgushchin/codex-worklog/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/edwardgushchin/codex-worklog/releases/tag/v0.1.0
