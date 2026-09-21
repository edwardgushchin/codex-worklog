# Project Goal

## Mission

Codex Worklog preserves enough context, evidence, and reasoning to resume
material Codex work without reopening the original conversation. One plugin
installation supplies universal authoring instructions for coding and
non-coding tasks; projects need no diary-specific `AGENTS.md` rules.

The target is fewer complete work blocks, each with six readable sections:

1. Context: the user's problem, relevant starting state, and constraints.
2. Chronology: significant investigation, attempts, failures, and corrections.
3. Changes: the final behavior and the artifacts actually affected.
4. Decisions: the chosen approach, rationale, and rejected alternatives.
5. Checks: commands, numerical results, inspected states, and honest limitations.
6. Next steps: unresolved work and the smallest useful continuation.

A later reader should be able to distinguish what was proposed, attempted,
rejected, verified, and left for a user decision. Unknown information stays
unknown. Timestamps are evidence, not invented decoration.

## Intended outcome

- The active model authors structured meaning using the work context it already
  has. Python handles schema checks, privacy, path safety, rendering, and
  storage; it does not invent semantics from final-answer keywords.
- Hooks give the author self-contained instructions and an exact command.
  Routine logging does not depend on finding a skill or interpreting cache
  path aliases.
- `submit` durably stages complete blocks for recovery and commits them before
  returning `recorded: true` and `staged: false`, without waiting for a lifecycle
  event. Storage errors exit nonzero without false success; prepared work is
  retained for command retries and the `Stop`/`SessionEnd` fallback.
- Acknowledgements, repeated history, and already-recorded work are skipped.
  Missing payloads produce a warning, never a low-quality fallback or a
  maintenance continuation loop.
- Sessions share one append-only daily file beneath each turn's host-bound workspace.
  Concurrent commits are locked and atomic, with markers for retry safety.
- Multi-item sections retain useful detail within explicit size limits.
  Failures and overturned decisions remain understandable in chronological
  context rather than being overwritten by a final success sentence.
- Evidence includes precise commands, paths, numerical results, SHA-256
  digests, and relevant external identifiers. Git metadata appears only when
  pertinent to the work; a full status listing is not mandatory.
- Language follows the active session or its author before falling back to an
  override and the operating-system locale.
- The exported history skill stays read-only, scoped to requested inspection
  within the current task directory. Mutable facts are verified again.
- Raw prompts, transcripts, tool dumps, secrets, and unnecessary personal data
  are excluded from the diary contract and private state.
- The runtime uses only Python 3.10-compatible standard-library code and makes
  no network calls. Platform support is backed by explicit acceptance evidence.

## Product boundaries

Codex Worklog is a local work and decision diary. It is not a conversation
archive, remote synchronization service, task manager, employee activity
monitor, cryptographic audit ledger, or protection against a compromised local
account. A valid schema does not guarantee that model-authored claims are
complete or correct.

The six-section structure is universal. A particular project's task tracker,
package manager, RED/GREEN workflow, design system, and user acceptance gates
belong only in entries where that work actually used them.

Earlier diaries remain historical records. The redesign does not rewrite,
merge, or retrospectively improve them, and historical notes do not authorize
new actions.

## Acceptance standard

Executable checks must cover submission validation, privacy boundaries,
commit-before-success without end hooks, retained staging after storage errors,
command and hook recovery, daily grouping, concurrent and duplicate commits,
workspace binding, links, permissions, and exact-prefix preservation. Semantic acceptance also needs
real active-model runs that preserve a failed candidate, a decision and its
reason, concrete checks, and an honest next step.

A package or validator passing does not prove real host instruction pickup or
the quality of a newly authored diary. Coding, non-coding, acknowledgement,
resume, and requested history-recovery behavior must be exercised separately.

See [Architecture](ARCHITECTURE.md), [Threat Model](THREAT_MODEL.md),
[Commissioning](COMMISSIONING.md), and the
[sanitized worklog example](../examples/EXAMPLE_WORKLOG.md).
