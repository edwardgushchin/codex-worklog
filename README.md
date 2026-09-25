<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./plugins/codex-worklog/assets/logo-dark.svg">
    <img src="./plugins/codex-worklog/assets/logo.svg" alt="Codex Worklog" width="620">
  </picture>
</p>

<h3 align="center">A local semantic worklog for every Codex task.</h3>

<p align="center">
  Understand what was requested, what happened, why, and where to resume.
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

Codex Worklog automatically keeps a local semantic worklog for every Codex task, appending outcomes to a Markdown file in the working directory bound to the current turn:

```text
<session cwd>/.dev-diary/YYYY/MM/YYYY-MM-DD.md
```

The active model authors complete work blocks using the context of the work it
actually performed. Each block has six sections: context, chronology, changes,
decisions, checks, and next steps. Failed candidates, rejected alternatives,
exact verification results, evidence links, and unresolved work belong beside
the outcome. Trivial acknowledgements and repeated history produce no entry.

Python validates, sanitizes, and commits this structured content; it does not
guess the meaning of the final answer. `submit` saves completed blocks before
confirming success, without waiting for end hooks. Concurrent sessions share
one daily file and retain their own entry markers and session references.

The workspace does not need to be a Git repository. No project-specific `AGENTS.md`, MCP server, hosted service, account, or API key is required.

## How it works

The plugin combines a submission helper, five lifecycle hooks, and one focused history-inspection skill:

| Boundary | Responsibility |
| --- | --- |
| `SessionStart` | Establishes private state bound to the original session `cwd`; no empty diary is created. |
| `UserPromptSubmit` | Supplies self-contained authoring instructions and the exact installed `submit` command for this turn. |
| `PreToolUse` | Binds automatic continuation turns; repeats the current command and a short schema while the turn is unrecorded, and refreshes full context after compaction. |
| `submit` | Validates and durably stages blocks, then atomically commits them before confirming that they are recorded. |
| `Stop` | Retries prepared blocks that were not committed; no new prose is generated. |
| `SessionEnd` | Retries any remaining prepared work; never generates additional prose. |

Before finishing, the model sends a JSON envelope on stdin to the supplied
`worklog.py submit --data … --session … --turn …` command from the working
directory specified in that turn's instructions. It submits up to eight independent work blocks, or an
explicit skip reason. The runtime accepts no caller-selected diary path or
marker. The full schema and limits are in [Architecture](docs/ARCHITECTURE.md).

If Codex changes the task's working directory between turns, the next prompt or
local tool binds new work to the new project. Existing diary entries stay put;
prepared blocks from the previous project remain pending until the task returns
there. A submission cannot select or change its own destination.

For material work, success includes `recorded: true` and `staged: false` only
after the daily file is committed. A storage failure exits nonzero without
reporting success; prepared blocks remain staged for a command or hook retry.
An explicit skip is acknowledged separately and creates no diary entry.

In a `workspace-write` task, the shell may be unable to write Codex's `PLUGIN_DATA` even when the project diary is writable. The authoring context asks for scoped filesystem approval on the exact `submit` tool call in that case. If approval is unavailable, the command fails explicitly and the author must report the missing entry; repeating it in the same sandbox cannot help.

Text limits apply after sanitization too. If redaction expands an item beyond
its limit, `submit` rejects it before staging and asks the author to shorten it;
existing prepared work is retained, and evidence is not silently truncated.

Private state in Codex-provided `PLUGIN_DATA` holds validated paths, identifiers,
timestamps, language, and sanitized blocks awaiting commit. Hooks do not read
transcripts or extract prose from final responses. If no valid submission
arrives, `Stop` reports a warning and skips the entry; it does not invent an
outcome or start a logging continuation.

The diary date follows the submission timestamp. Structural labels prefer the
host's session language, then the author's selected language, an explicit
override, and finally the operating-system locale. Exact commands, numerical
results, SHA-256 digests, safe inline Markdown, and relative evidence paths are
preserved. In-workspace absolute paths become relative. The runtime does not
automatically collect Git status: relevant baselines, changes, and commits
belong in the model-authored block only when useful to the work.

An entry looks like this:

```markdown
## 2026-09-04 16:51 +03:00 — Consumers moved to the verified destination

### Context

- Consumers still used the source after the destination copy was prepared.

### Chronology

- `16:10`
  - Compared the source and destination before switching consumers.
- `16:45`
  - Switched consumers and checked their normal read path.

### Changes

- Consumers use the destination; the source remains available for rollback.

### Decisions

- Kept the source until the retention window ends so rollback remains possible.

### Checks

- Integrity comparison and the consumer smoke check passed.

### Next steps

- Remove the source after the retention window.
```

The runtime adds a session reference and an idempotency marker to each block.

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

Native installation can replace the **whole plugin cache**, including older
versions referenced by open tasks. This revision retains the reviewed runtime
under `PLUGIN_DATA/runtimes-v1/<sha256>.py` before delivering author commands.
Initialized hooks and outstanding submit commands keep working after cache
replacement, using their pinned version rather than silently loading new code.
Runtime copies are not automatically deleted while old tasks may need them.
Tasks loaded before this retention fix still require a one-time reload: disable
the plugin in affected tasks before updating, then load reviewed hooks in a new
task. A warning from an old hook is not evidence that logging still works.

### Update or remove

```bash
codex plugin marketplace upgrade codex-worklog
codex plugin add codex-worklog@codex-worklog
```

For an attributed update log, run from a reviewed local clone instead:

```bash
python3 scripts/update_plugin.py --refresh
```

Omit `--refresh` to reinstall an already refreshed/local source. This explicit
command runs native Codex installation, so it may enable the installed plugin;
do not run it just to inspect a deliberately disabled installation.
It records start/completion/failure, operation ID, observer PID and before/after
cache versions in `PLUGIN_DATA/diagnostics-v1/events-YYYY-MM-DD.jsonl`. Launchers
also record runtime changes and failures there without raw task content.
For operations outside this helper the change initiator is **unknown**, not the
PID of the observer. Identifying an arbitrary deleting process requires separate
OS auditing; the plugin does not install an OS watcher or audit service.

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
| `CODEX_WORKLOG_LANGUAGE` | Automatic | A supported language code, used after host and author language hints. |

- `strict` and `advisory` both enable authoring instructions and runtime writes;
  a missing payload produces a warning and no continuation in either mode.
- `off` disables file and state creation.

The plugin never changes project `.gitignore` files. If worklogs should remain local, add the directory to your existing global Git excludes file. If they should be project history, review and commit them intentionally.

## Privacy and safety

- All worklog data stays on the local filesystem unless the user or another tool publishes it.
- The hook performs no network requests and has no telemetry.
- Hooks do not read transcripts or retain raw prompts, tool dumps, or complete
  final responses. The author submits a deliberate summary of the work.
- Validation removes common secret patterns and unsafe structures; review
  plaintext diaries before sharing. Schema checks cannot prove semantic truth
  or detect every unlabelled secret.
- Hooks provide authoring instructions, not historical diary content; the
  read-only skill loads history only for a relevant inspection or recovery request.
- Safe relative paths, commands, and complete SHA-256 evidence remain readable.
- New directories and files use `0700` and `0600` where supported; existing
  directory and diary permissions are preserved.
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
- A block requires a valid model submission and a successful `submit` commit.
  A crash or storage error after staging can leave work pending; retrying the
  command or a later `Stop`/`SessionEnd` can recover it. Hook delivery is not
  required after a successful submission.
- A read-only or restricted `cwd` cannot contain a worklog; the hook reports that condition and does not silently redirect the diary elsewhere.
- A `cwd` with unsafe control, formatting, or Markdown-delimiter characters is rejected instead of being rewritten.
- Semantic quality depends on the active model, its available context, and its
  following the author instructions. No automatic regex fallback exists.
- Earlier per-session diaries are preserved without rewriting. New state uses
  a separate versioned schema; this change does not migrate old pending summaries.
- Platform-specific filesystem behavior and native host instruction pickup
  require acceptance testing; see [Commissioning](docs/COMMISSIONING.md).

## License

Codex Worklog is released under the [MIT License](LICENSE).
