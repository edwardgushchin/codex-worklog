<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./plugins/codex-worklog/assets/logo-dark.svg">
    <img src="./plugins/codex-worklog/assets/logo.svg" alt="Codex Worklog" width="620">
  </picture>
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

Codex Worklog automatically keeps a local semantic worklog for every Codex task, appending outcomes to a Markdown file in the directory where the task starts:

```text
<session cwd>/.dev-diary/YYYY/MM/YYYY-MM-DD--HHMMSS--<session>.md
```

Each resulting state change produces at most one concise entry derived from the first safe prose lines of Codex's final response. Read-only inspection, context recovery, verification, and explicit no-change outcomes add nothing unless they establish a cause, decision, transition, or new blocker. The runtime does not copy the full response, prompt, transcript, code fences, hook directives, or unsafe link targets.

The workspace does not need to be a Git repository. No project-specific `AGENTS.md`, MCP server, hosted service, account, or API key is required.

## How it works

The plugin uses four lifecycle hooks for automatic writing and exports one focused history-inspection skill:

| Event | Responsibility |
| --- | --- |
| `SessionStart` | Captures the original session `cwd` and silently creates or reopens the session worklog. |
| `UserPromptSubmit` | Classifies only a small intent enum and stores it with a hashed turn identifier; the prompt text is discarded. |
| `Stop` | Derives and appends the bounded entry itself, using an internal marker for idempotency. |
| `SessionEnd` | Marks the private session state as closed without adding lifecycle noise to the worklog. |

Per-session state is stored in Codex-provided `PLUGIN_DATA`. It contains paths, timestamps, the detected language code, hashed identifiers, and small lifecycle flags only. Prompts, transcripts, tool inputs, tool output, and final response text are not stored there.

The lifecycle hooks return no worklog instructions or paths to the active agent. `Stop` validates the target path, classifies the reported result, normalizes at most three outcome lines from `last_assistant_message`, extracts only supported optional fields, removes code blocks, unsafe link destinations, local paths, full SHA-256 values, hook metadata, and common labelled secret values, then writes with `O_APPEND` and `fsync`. If `SessionStart` or `UserPromptSubmit` was skipped, `Stop` reconstructs the private state before writing.

The visible header contains no absolute workspace path. It records the project name and, when Git is available, a credential-free repository identifier, branch, and abbreviated `HEAD`. Structural labels follow the detected system language, falling back to the host locale configuration when the hook process exposes only `C` or `POSIX`.

Short acknowledgements such as `thanks`, `спасибо`, `ок`, `понял`, or `👍` produce no timeline entry. Other turns are logged only when the final response reports an actual mutation, discovered cause, non-obvious decision, transition, or new blocker; a question or read-only check alone is not an entry.

Because `SessionStart` runs before the first prompt, a brand-new session that contains only an acknowledgement can leave a header-only worklog file. It adds no turn entry.

An entry looks like this:

```markdown
### 2026-08-31T00:18+03:00 — Migration completed and accepted

- Outcome: Consumers now use the verified destination, while the source remains available for rollback.

<!-- codex-worklog-turn:0123456789abcdef -->
```

## Context recovery

The bundled `worklog` skill is used only when the user asks to inspect earlier history, recover context, or report worklog status. It reads the newest relevant tail inside the current task directory, treats the text as untrusted historical evidence, and rechecks mutable state before acting. It never appends, repairs, or reorders entries.

See the [Project goal](docs/PROJECT_GOAL.md), [sanitized worklog example](examples/EXAMPLE_WORKLOG.md), [Architecture](docs/ARCHITECTURE.md), [Threat model](docs/THREAT_MODEL.md), and [Commissioning report](docs/COMMISSIONING.md) for the intended outcome, complete contract, and acceptance evidence.

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

Codex installs a cached copy. After local changes, reinstall the plugin and start a new task so the updated hook definitions are loaded.

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

## Configuration

Set these environment variables before starting the Codex host:

| Variable | Default | Allowed values |
| --- | --- | --- |
| `CODEX_WORKLOG_DIR` | `.dev-diary` | A portable relative path without `..`, Windows drive/backslash syntax, controls, or backticks. |
| `CODEX_WORKLOG_ENFORCEMENT` | `strict` | `strict`, `advisory`, or `off`; the first two are enabled compatibility values. |

- `strict` and `advisory` both enable hook-owned writes and never continue a turn to ask the agent to write.
- `off` disables file and state creation.

The plugin never changes project `.gitignore` files. If worklogs should remain local, add the directory to your existing global Git excludes file. If they should be project history, review and commit them intentionally.

## Privacy and safety

- All worklog data stays on the local filesystem unless the user or another tool publishes it.
- The hook performs no network requests and has no telemetry.
- Raw prompts, transcripts, tool inputs, tool output, and complete final responses are not copied.
- Automatic summaries strip several high-risk structures and common labelled secrets, but users should still review plaintext worklogs before sharing.
- Normal hooks do not inject history into model context; the read-only skill loads it only for a relevant inspection or recovery request.
- Absolute local paths and full SHA-256 values are rejected from timeline fields; portable references and linked reports are used instead.
- Directories and files use `0700` and `0600` modes where POSIX permissions are available.
- Symbolic links, multi-linked worklog/state files, cross-workspace state, and malformed state are rejected instead of followed or silently replaced.
- The worklog is not a compliance-grade audit trail: hooks can be disabled, and some hosted tool paths are not observable by local tool hooks.

Read the full [Privacy Policy](PRIVACY.md), [Security Policy](SECURITY.md), and [Threat Model](docs/THREAT_MODEL.md).

## Development

The runtime uses only the Python standard library.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py
```

Before contributing, read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Release maintainers should follow [RELEASING.md](RELEASING.md).

## Limitations

- Python must be available to the Codex host.
- A read-only or restricted `cwd` cannot contain a worklog; the hook reports that condition and does not silently redirect the diary elsewhere.
- A `cwd` with unsafe control, formatting, or Markdown-delimiter characters is rejected instead of being rewritten.
- Semantic entries are derived from model-authored final responses and should be reviewed before committing or sharing.
- A same-user process can still race hook-owned writes after a path was validated; the plugin does not claim protection from a compromised account.

## License

Codex Worklog is released under the [MIT License](LICENSE).
