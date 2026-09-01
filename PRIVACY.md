# Privacy Policy

Effective date: 2026-08-30

Codex Worklog is local, open-source software. It does not operate a hosted service, send telemetry, make network requests, use cookies, or maintain a developer-controlled user database.

## Data processed locally

The plugin processes lifecycle metadata supplied by Codex:

- the session working directory and worklog path, retained only in private
  plugin state;
- session and turn identifiers, which are stored only as one-way truncated
  SHA-256 tokens;
- timestamps, the detected language code, lifecycle flags, and event names;
- portable project name and optional sanitized repository, branch, and
  abbreviated `HEAD` metadata written to the visible header;
- bounded Markdown summaries derived by `Stop` from the final assistant message.

Raw user prompts, Codex transcripts, tool inputs, and tool output are not copied
by the hook. The complete final assistant message is not retained: the runtime
keeps at most three normalized prose lines and removes code fences, hook
metadata, link targets, local paths, full SHA-256 values, and common labelled
secret values. Git remote credentials are discarded, and local-path remotes are
not rendered.

Normal lifecycle hooks do not send worklog content back into model context. When the user requests history inspection or context recovery, the bundled read-only skill may load the newest relevant worklog tail and linked evidence from the current task directory. That content is treated as untrusted history and is not interpreted as instructions or authorization.

## Storage

- Worklogs are stored under the configured relative directory in the session `cwd`; the default is `.dev-diary/`.
- Small session-state JSON files are stored in the Codex-provided `PLUGIN_DATA` directory.
- POSIX permission modes are restricted to `0700` for directories and `0600` for files where supported.

## Sharing and retention

The plugin does not transmit or automatically delete data. The user controls retention, backup, Git tracking, synchronization, publication, and deletion. Other software on the device may access files according to operating-system permissions.

## User responsibility

Semantic entries are derived from AI-generated final responses. Deterministic
normalization cannot recognize every possible unlabelled secret or personal
detail, so users should review worklogs before committing, syncing, archiving,
or sharing them.

## Deletion

Uninstalling the plugin does not delete worklogs. Delete the relevant `.dev-diary/` directory and the plugin's Codex data directory when those records are no longer needed.

## Changes

Material policy changes are documented in [CHANGELOG.md](CHANGELOG.md) and released with the repository.

Questions can be raised through the channels described in [SUPPORT.md](SUPPORT.md).
