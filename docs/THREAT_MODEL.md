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
| --- | --- |
| Raw prompts or transcripts are retained | The runtime reads `prompt` only for an in-process exact acknowledgement classification, discards it immediately, and stores only a Boolean result; `transcript_path` is ignored. Tests use a canary secret to verify non-persistence. |
| Tool output contains credentials | Tool hooks are not used for capture; agent instructions explicitly prohibit copying full output or secrets. |
| `cwd` or configuration escapes the workspace | Worklog paths must be portable and relative to the event `cwd`; `..`, absolute or Windows-drive overrides, control characters, and unsafe restored paths are rejected. |
| A workspace link redirects reads or writes | Symbolic links are rejected, worklog and state files must be regular files with one hard link, and opened-file identity is checked before runtime reads or appends. |
| Tampered `PLUGIN_DATA` redirects SessionEnd | Restored worklog paths and stored workspace identity are validated against the current event `cwd` before reads or appends; malformed or oversized state fails visibly. |
| Shell metacharacters in the installed path execute code | `PLUGIN_ROOT` is quoted in Unix and Windows hook commands. Runtime paths are passed as one interpreter argument. |
| A malicious path injects model instructions | Unsafe workspace/worklog paths fail closed. Other model-visible values have control and format characters removed and are length bounded. Previous-session pointers accept only recognized regular worklogs. |
| A missing turn entry causes an infinite loop | Strict mode allows one continuation and honors `stop_hook_active`; the second miss becomes a warning. |
| A general-purpose edit inserts an entry before older history | Material turns use the bundled helper, which validates a fixed single-line schema and opens the target with `O_APPEND`; resume regression coverage requires the old file to remain an exact byte prefix. |
| A helper request injects structure or consumes excessive memory | The helper accepts only the exact key set, bounds total input and every field, and rejects controls, newlines, reserved markers, invalid turn markers, and extra fields. |
| A substantive prompt is mistaken for noise | Only a short prompt whose entire normalized content matches a small acknowledgement allowlist is skipped; any additional word remains material. Cancellation and question regressions are explicit negative controls. |
| Concurrent tasks corrupt one daily file | Each session uses a distinct file derived from time and a hashed session identifier. State writes use atomic replacement. |
| Worklogs leak through Git | The plugin never edits `.gitignore` or stages files and tells the agent not to add worklogs without explicit user intent. Users remain responsible for repository policy. |
| Stale history drives an unsafe action | Context recovery treats entries as historical notes and requires current verification of mutable state. |
| Hook changes execute without review | Codex requires users to review and trust plugin hooks; updated definitions may require renewed trust. |

## Residual Risks

- The model can still write sensitive or inaccurate semantic content despite instructions.
- A local process with user permissions can tamper with worklogs or state.
- A same-user process can still race helper path validation and append; protection
  from a compromised account is out of scope.
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
