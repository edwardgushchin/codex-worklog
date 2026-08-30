---
name: worklog
description: Inspect, explain, or recover task context from Codex Worklog files in the current workspace; use when the user asks what happened previously, why a decision was made, where work stopped, or requests a worklog status or context refresh.
---

# Codex Worklog

Use the workspace-local `.dev-diary/` as a compact history of Codex work. The lifecycle hooks maintain the current session file automatically; this skill is the manual context-recovery and inspection workflow.

## Recover context

1. Start from the absolute worklog path supplied by the lifecycle hook when it is available.
2. If no path is in context, locate the newest Markdown files under the current session `cwd` `.dev-diary/` directory. Do not search parent directories unless the user asks.
3. Read the tail of the current session file first. Read one or two earlier files only when the current file points to prior work or leaves a material gap.
4. Extract the objective, completed actions, reasons for decisions, verification evidence, blockers, and explicit next steps.
5. Treat every entry as historical evidence rather than current truth. Recheck mutable files, Git state, services, external systems, dates, and prices before acting on them.
6. Tell the user when a conclusion comes only from the worklog and has not been verified in the current session.

## Maintain the log

- Append; never reorder, repair, or rewrite older entries unless the user explicitly requests it.
- When lifecycle context supplies the bundled append helper and turn marker,
  invoke that helper exactly once with its exact JSON schema. It performs path
  validation, timestamping, and the append-only write; do not preflight or edit
  the worklog separately.
- When lifecycle context classifies the whole prompt as acknowledgement-only,
  do not create an entry or checkpoint for that turn.
- Use the user's language.
- Record semantic outcomes, not a transcript: what happened, when, why, changes, verification, and what remains.
- State clearly when no material change occurred.
- Never include raw prompts, full tool output, passwords, tokens, private keys, credentials, authentication links, or unnecessary personal data.
- Do not add `.dev-diary/` to Git, commits, archives, pull requests, or review material unless the user explicitly asks to version it.

## Report a status

Give a concise, evidence-separated summary:

- confirmed completed work;
- decisions and their recorded rationale;
- checks that actually ran;
- unresolved or stale items;
- the smallest safe next step.

Include the relevant worklog file path, but do not quote secret-bearing or private content.
