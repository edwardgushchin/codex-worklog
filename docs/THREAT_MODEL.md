# Threat Model

## Scope

Codex Worklog writes model-authored Markdown into a workspace and keeps minimal lifecycle state in Codex plugin storage. This document covers confidentiality, integrity, path safety, command execution, availability, and context-recovery risks.

## Assets

- project history and rationale;
- filesystem paths and session timing;
- the integrity of files outside the intended worklog directory;
- Codex availability and turn completion;
- secrets or personal data that could be mentioned during work.

## Trust Assumptions

- The user intentionally installs and trusts the reviewed plugin hooks.
- The Codex host supplies authentic lifecycle event fields and `PLUGIN_ROOT`/`PLUGIN_DATA` values.
- The Python interpreter invoked by the hook is trusted.
- Processes with the user's filesystem privileges can read or alter user-owned files; the plugin cannot defend against a fully compromised account.
- Model-authored summaries may be inaccurate and require human or live-state verification.

## Threats and Mitigations

| Threat | Mitigation |
|---|---|
| Raw prompts or transcripts are retained | The runtime ignores `prompt` and `transcript_path` content and stores neither. Tests use a canary secret to verify non-persistence. |
| Tool output contains credentials | Tool hooks are not used for capture; agent instructions explicitly prohibit copying full output or secrets. |
| `cwd` or configuration escapes the workspace | Worklog paths must be relative to the event `cwd`; `..`, absolute overrides, control characters, and unsafe restored paths are rejected. |
| A workspace symlink redirects writes | Every existing worklog path component is checked and symbolic links are rejected. |
| Tampered `PLUGIN_DATA` redirects SessionEnd | Restored worklog paths are validated against the current event `cwd` before reads or appends. |
| Shell metacharacters in the installed path execute code | `PLUGIN_ROOT` is quoted in Unix and Windows hook commands. Runtime paths are passed as one interpreter argument. |
| A malicious path injects model instructions | Paths are flattened to one line and Markdown backticks are removed before inclusion in model-visible context. |
| A missing turn entry causes an infinite loop | Strict mode allows one continuation and honors `stop_hook_active`; the second miss becomes a warning. |
| Concurrent tasks corrupt one daily file | Each session uses a distinct file derived from time and a hashed session identifier. State writes use atomic replacement. |
| Worklogs leak through Git | The plugin never edits `.gitignore` or stages files and tells the agent not to add worklogs without explicit user intent. Users remain responsible for repository policy. |
| Stale history drives an unsafe action | Context recovery treats entries as historical notes and requires current verification of mutable state. |
| Hook changes execute without review | Codex requires users to review and trust plugin hooks; updated definitions may require renewed trust. |

## Residual Risks

- The model can still write sensitive or inaccurate semantic content despite instructions.
- A local process with user permissions can tamper with worklogs or state.
- POSIX modes do not provide the same semantics on every filesystem or Windows host.
- Worklogs are plaintext and are not encrypted by the plugin.
- Hooks can be disabled, skipped, or unavailable; this is not a compliance-grade audit trail.
- Hosted tool paths outside local hook coverage may not contribute mechanical evidence.
- A malicious Python executable earlier in `PATH` can run instead of the expected interpreter.

## Out of Scope

- protection from a compromised operating system or user account;
- encrypted storage or key management;
- regulatory retention, legal hold, non-repudiation, or tamper evidence;
- remote synchronization and access control;
- correctness guarantees for model-generated summaries.

Report vulnerabilities privately according to [SECURITY.md](../SECURITY.md).
