<p align="center">
  <img src="./plugins/codex-worklog/assets/logo.svg" alt="Codex Worklog" width="620">
</p>

<h3 align="center">A local semantic worklog for every Codex task.</h3>

<p align="center">
  Understand what changed, when it changed, why it changed, and where to resume.
</p>

<p align="center">
  <a href="https://github.com/edwardgushchin/codex-worklog/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/edwardgushchin/codex-worklog/actions/workflows/ci.yml/badge.svg?branch=main">
  </a>
  <a href="https://github.com/edwardgushchin/codex-worklog/blob/main/LICENSE">
    <img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue.svg">
  </a>
  <img alt="Python 3.10 or newer" src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg">
  <img alt="No runtime packages" src="https://img.shields.io/badge/runtime%20dependencies-none-16A34A.svg">
  <img alt="Codex plugin" src="https://img.shields.io/badge/Codex-plugin-2563EB.svg">
</p>

<p align="center">
  <a href="#about">About</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#context-recovery">Context recovery</a> ·
  <a href="#privacy-and-safety">Privacy</a> ·
  <a href="#development">Development</a>
</p>

<p align="center"><a href="README.ru.md">Русская версия</a></p>

## About

Codex Worklog is a local Codex plugin for coding and non-coding projects. It creates an append-only Markdown worklog inside the working directory from which the Codex task starts:

```text
<session cwd>/.dev-diary/YYYY/MM/YYYY-MM-DD--HHMMSS--<session>.md
```

Each entry captures the semantic outcome of a turn instead of copying a transcript:

- context and intent;
- actions and material changes;
- decisions and their rationale;
- verification that actually ran;
- unresolved work and the next step.

The workspace does not need to be a Git repository. No project-specific `AGENTS.md`, MCP server, hosted service, account, or API key is required.

## How it works

The plugin combines a skill with four lifecycle hooks:

| Event | Responsibility |
| --- | --- |
| `SessionStart` | Captures the original session `cwd`, creates or reopens the session worklog, and tells the agent how to recover context. |
| `UserPromptSubmit` | Skips acknowledgement-only prompts; otherwise gives the agent one bundled append helper, the entry contract, and a one-way hashed completion marker. |
| `Stop` | Accepts skipped acknowledgements or verifies that the turn marker was appended, with one bounded continuation if it was missed. |
| `SessionEnd` | Appends an idempotent checkpoint only when material work occurred since the previous checkpoint. |

Per-session state is stored in Codex-provided `PLUGIN_DATA`. It contains paths,
timestamps, hashed identifiers, and small lifecycle flags only. Prompts,
transcripts, tool inputs, and tool output are not copied there.

Material turns are written through a single bundled helper invocation. The
helper validates the exact schema and target path, adds the local timestamp,
and opens the worklog with append semantics; the agent does not preflight or
edit the Markdown file separately.

Prompts whose entire normalized content is a short acknowledgement such as
`thanks`, `спасибо`, `ок`, `понял`, or `👍` deliberately produce no timeline
entry. Any additional instruction, question, cancellation, decision, or other
content makes the prompt material and therefore loggable.

Because `SessionStart` runs before the first prompt, a brand-new session that
contains only an acknowledgement can leave a header-only worklog file. It adds
neither a turn entry nor a session checkpoint.

An entry looks like this:

```markdown
### 14:32 — Confirmed the migration strategy

- Context: The workspace needs a reversible migration.
- Actions: Compared both storage layouts and inspected current state.
- Changes: No files changed.
- Decisions: Use copy-verify-switch because it preserves rollback.
- Verification: Source and destination checksums matched.
- Next: Switch consumers after user approval.

<!-- codex-worklog-turn:0123456789abcdef -->
```

See [Architecture](docs/ARCHITECTURE.md), [Threat model](docs/THREAT_MODEL.md),
and [Commissioning report](docs/COMMISSIONING.md) for the complete contract and
acceptance evidence.

## Requirements

- Codex Desktop or Codex CLI with plugin and hook support.
- Python 3.10 or newer:
  - `python3` on Linux and macOS;
  - the `py -3` launcher on Windows.
- Permission for Codex to write inside the task working directory.

## Installation

### From GitHub

Add this repository as a marketplace and install the plugin:

```bash
codex plugin marketplace add edwardgushchin/codex-worklog --ref main
codex plugin add codex-worklog@codex-worklog
```

Start a new Codex task after installation. Review and trust the bundled hooks when Codex asks; plugin hooks do not run until they are trusted.

You can also open `/plugins`, select the **Codex Worklog** marketplace, and install the plugin from the browser.

### From a local clone

```bash
git clone https://github.com/edwardgushchin/codex-worklog.git
codex plugin marketplace add /absolute/path/to/codex-worklog
codex plugin add codex-worklog@codex-worklog
```

Codex installs a cached copy. After local changes, reinstall the plugin and start a new task so the updated hook and skill definitions are loaded.

### Update or remove

```bash
codex plugin marketplace upgrade codex-worklog
codex plugin add codex-worklog@codex-worklog
```

```bash
codex plugin remove codex-worklog@codex-worklog
codex plugin marketplace remove codex-worklog
```

Removing the plugin does not delete existing `.dev-diary/` directories.

## Context recovery

At every session start, Codex learns that the worklog is available as a context source. When a task is resumed, compacted, or unclear, the agent is instructed to:

1. read the tail of the current session worklog;
2. read the newest relevant previous session only if a gap remains;
3. extract decisions, evidence, blockers, and next steps;
4. verify mutable files, Git state, services, external systems, dates, and prices before acting.

The bundled `worklog` skill provides the same workflow when you explicitly ask Codex to recover context or explain earlier decisions.

Worklog entries are historical evidence, not a live-state database.

## Configuration

Set these environment variables before starting the Codex host:

| Variable | Default | Allowed values |
| --- | --- | --- |
| `CODEX_WORKLOG_DIR` | `.dev-diary` | A portable relative path without `..`, Windows drive/backslash syntax, controls, or backticks. |
| `CODEX_WORKLOG_ENFORCEMENT` | `strict` | `strict`, `advisory`, or `off`. |

- `strict` asks Codex for one bounded continuation when the current turn entry is missing.
- `advisory` reports the missing entry without continuing the turn.
- `off` disables file and state creation.

The plugin never changes project `.gitignore` files. If worklogs should remain local, add the directory to your existing global Git excludes file. If they should be project history, review and commit them intentionally.

## Privacy and safety

- All worklog data stays on the local filesystem unless the user or another tool publishes it.
- The hook performs no network requests and has no telemetry.
- Raw prompts, transcripts, tool inputs, and tool output are not copied.
- Agents are instructed to redact secrets and unnecessary personal data.
- Directories and files use `0700` and `0600` modes where POSIX permissions are available.
- Symbolic links, multi-linked worklog/state files, cross-workspace state, and
  malformed state are rejected instead of followed or silently replaced.
- The worklog is not a compliance-grade audit trail: hooks can be disabled, and some hosted tool paths are not observable by local tool hooks.

Read the full [Privacy Policy](PRIVACY.md), [Security Policy](SECURITY.md), and [Threat Model](docs/THREAT_MODEL.md).

## Development

The runtime uses only the Python standard library.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py
```

The repository follows the community structure used by [SDL3-CS](https://github.com/edwardgushchin/SDL3-CS): focused contribution guidance, issue forms, a pull request checklist, a code of conduct, security and support policies, release instructions, pinned CI actions, and Dependabot coverage.

Before contributing, read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Release maintainers should follow [RELEASING.md](RELEASING.md).

## Limitations

- Python must be available to the Codex host.
- A read-only or restricted `cwd` cannot contain a worklog; the hook reports that condition and does not silently redirect the diary elsewhere.
- A `cwd` with characters that cannot be represented safely in model context is rejected instead of exposing an altered path.
- Semantic entries are model-authored and should be reviewed before committing or sharing.
- Context recovery deliberately reads a small, relevant history rather than loading every prior file.
- A same-user process can still race model-authored writes after a path was
  validated; the plugin does not claim protection from a compromised account.

## License

Codex Worklog is released under the [MIT License](LICENSE).
