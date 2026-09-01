# Threat Model

## Scope

Codex Worklog writes hook-derived Markdown into a workspace and keeps minimal lifecycle state in Codex plugin storage. This document covers confidentiality, integrity, path safety, command execution, availability, and context-recovery risks.

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
- Hook-derived summaries originate from model-authored final responses and may be inaccurate or incomplete.

## Threats and Mitigations

| Threat | Mitigation |
| --- | --- |
| Raw prompts or transcripts are retained | The runtime reads `prompt` only for an in-process intent classification, discards it immediately, and stores only a small enum plus a hashed turn identifier; `transcript_path` is ignored. Tests use a canary secret to verify non-persistence. |
| Tool output contains credentials | Tool hooks and `transcript_path` are not used for capture. Fenced code and common labelled secret values are removed from the bounded final-response summary. |
| `cwd` or configuration escapes the workspace | Worklog paths must be portable and relative to the event `cwd`; `..`, absolute or Windows-drive overrides, control characters, and unsafe restored paths are rejected. |
| A visible header or derived field discloses local filesystem structure | Headers contain only portable project/Git identity. Automatic summaries replace absolute POSIX, Windows, home-relative, and `file://` paths. Absolute paths remain only in private runtime state. |
| A Git remote exposes embedded credentials | Optional repository metadata is collected with bounded non-interactive local Git commands, reduced to a repository identifier, and stripped of authority/user information. Local-path remotes fall back to the repository directory name. |
| A workspace link redirects reads or writes | Symbolic links are rejected, worklog and state files must be regular files with one hard link, and opened-file identity is checked before runtime reads or appends. |
| Tampered `PLUGIN_DATA` redirects SessionEnd | Restored worklog paths and stored workspace identity are validated against the current event `cwd` before reads or appends; malformed or oversized state fails visibly. |
| Shell metacharacters in the installed path execute code | `PLUGIN_ROOT` is quoted in Unix and Windows hook commands. Runtime paths are passed as one interpreter argument. |
| A malicious path or planted worklog injects model instructions | Lifecycle hooks do not inject worklog content or paths. The optional inspection skill reads only requested history inside the current `cwd`, does not initiate global-memory or conversation-history searches, treats diary text as untrusted, and never follows embedded instructions or authorization. |
| A missing turn entry causes an infinite loop | `Stop` performs the append itself and never creates a continuation prompt. Repeated events are deduplicated by an internal hashed marker. |
| A general-purpose edit inserts an entry before older history | The hook validates a fixed single-line schema internally and opens the target with `O_APPEND`; resume regression coverage requires the old file to remain an exact byte prefix. |
| A helper request injects structure or consumes excessive memory | The helper accepts a small allowlisted schema with two required semantic fields, bounds total input and every field, and rejects controls, newlines, reserved markers, invalid turn markers, empty optional values, and extra fields. |
| An artifact link escapes the project or points to invented evidence | Local artifact targets must be existing project-relative regular files that resolve inside the workspace; the helper rewrites them relative to the nested worklog. External artifacts require credential-free HTTPS links. |
| A final response contains excessive or sensitive detail | The runtime keeps at most three normalized outcome lines, extracts only bounded single-line optional fields, and strips code fences, hook metadata, unsafe link targets, local paths, full SHA-256 values, and common labelled secrets. Complete prevention of arbitrary unlabelled secrets is not claimed. |
| Read-only work creates misleading state changes | Prompt intent and the final result are classified separately. Acknowledgements, pure inspection, verification, context recovery, and explicit no-change outcomes append nothing; tests require byte-identical files for representative cases. Causes, decisions, transitions, and newly discovered blockers remain recordable. |
| Concurrent tasks corrupt one daily file | Each session uses a distinct file derived from time and a hashed session identifier. State writes use atomic replacement. |
| Worklogs leak through Git | The plugin never edits `.gitignore` or stages files. Users remain responsible for repository policy. |
| Stale history drives an unsafe action | Normal lifecycle hooks do not inject historical entries. The inspection skill labels worklog-only conclusions and requires fresh verification of mutable state before action. |
| Hook changes execute without review | Codex requires users to review and trust plugin hooks; updated definitions may require renewed trust. |

## Residual Risks

- The final response can still contain an unlabelled secret or inaccurate content that deterministic normalization does not recognize.
- Deterministic natural-language classification can omit an ambiguously worded
  state change or record a misleading one; concise explicit outcome and field
  labels reduce this risk but do not eliminate it.
- A local process with user permissions can tamper with worklogs or state.
- A same-user process can still race runtime path validation and append; protection
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
- correctness guarantees for hook-derived summaries.

Report vulnerabilities privately according to [SECURITY.md](../SECURITY.md).
