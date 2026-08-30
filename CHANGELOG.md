# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-30

### Added

- Repo-scoped Codex marketplace and installable `codex-worklog` plugin.
- Workspace-local, per-session append-only Markdown worklogs.
- `SessionStart`, `UserPromptSubmit`, `Stop`, and `SessionEnd` lifecycle hooks.
- Context recovery from the current and latest relevant previous worklog.
- Strict, advisory, and disabled enforcement modes.
- Secret-safe state that excludes raw prompts, transcripts, and tool output.
- Cross-platform Python standard-library runtime and automated tests.
- English and Russian documentation plus full community health files.

[Unreleased]: https://github.com/edwardgushchin/codex-worklog/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/edwardgushchin/codex-worklog/releases/tag/v0.1.0
