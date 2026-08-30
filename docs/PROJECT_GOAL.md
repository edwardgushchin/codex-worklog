# Project Goal

## Mission

Codex Worklog makes the reasoning and outcomes of Codex work inspectable across
coding and non-coding projects. Install it once, then receive a local semantic
worklog in every task's original working directory without adding instructions
or infrastructure to each project.

The worklog should let a person or a later Codex session answer five questions:

1. What was the task and what was actually done?
2. When did the material work happen?
3. Why were the important decisions made?
4. What evidence was used to verify the result?
5. What remains, and where should work resume?

## Intended outcome

The project is successful when all of the following remain true:

- one normal Codex plugin installation covers Git repositories, ordinary
  directories, coding work, and non-coding work;
- every worklog is rooted under the session's original `cwd` and uses a
  readable, append-only Markdown format;
- a material turn produces one concise semantic entry through the bundled
  append helper, while acknowledgement-only turns produce no entry;
- resuming a task preserves all existing bytes and appends newer events after
  older ones;
- Codex is told to use the worklog for context recovery after a resume,
  compaction, or uncertainty, while rechecking mutable live state;
- raw prompts, transcripts, full tool output, credentials, secrets, and
  unnecessary personal data are not copied into the worklog or plugin state;
- the runtime performs no network requests, has no telemetry, uses no runtime
  packages, and supports Python 3.10 or newer on Linux, macOS, and Windows;
- the implementation, lifecycle contract, threat model, tests, and release
  process are independently inspectable.

## Product boundaries

Codex Worklog is a local development and decision diary. It is not:

- a full conversation archive, activity monitor, or employee-surveillance
  system;
- a remote synchronization, backup, analytics, or project-management service;
- a cryptographic audit ledger or protection against a malicious local user;
- a guarantee that model-written summaries are complete or correct;
- a live-state database. Files, Git, services, external systems, dates, and
  prices must be verified again before a later session relies on them.

## Audit standard

Claims about behavior should be supported by executable tests or reproducible
acceptance evidence. A package or validator passing is not enough when a claim
depends on live Codex behavior: material, acknowledgement-only, resume,
context-recovery, coding, and non-coding scenarios must also be exercised.

See the [architecture](ARCHITECTURE.md), [threat model](THREAT_MODEL.md),
[commissioning report](COMMISSIONING.md), and
[sanitized worklog example](../examples/EXAMPLE_WORKLOG.md).
