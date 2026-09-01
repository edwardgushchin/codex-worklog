# Project Goal

## Mission

Codex Worklog makes the reasoning and outcomes of Codex work inspectable across
coding and non-coding projects. Install it once, then receive a local semantic
worklog in every task's original working directory without adding instructions
or infrastructure to each project.

The worklog should let a person or a later Codex task answer five questions:

1. What outcome did Codex report?
2. When did the material work happen?
3. Why was a defect explained or a non-obvious decision made, when recorded?
4. What was checked and where does the detailed evidence live?
5. Which earlier blocker or status was superseded, and what remains?

## Intended outcome

The project is successful when all of the following remain true:

- one normal Codex plugin installation covers Git repositories, ordinary
  directories, coding work, and non-coding work;
- every worklog is rooted under the session's original `cwd` and uses a
  readable, append-only Markdown format;
- lifecycle hooks, not the active agent, create and append every normal entry;
- each resulting state change produces at most one concise entry derived from
  a bounded, normalized subset of `last_assistant_message`; acknowledgement,
  inspection, context-recovery, and verification-only turns produce no entry
  unless they establish a cause, decision, transition, or new blocker;
- resuming a task preserves all existing bytes and appends newer events after
  older ones;
- hooks return no worklog path, append command, marker, or maintenance
  instruction to the active agent;
- structural labels follow the system language even when the hook process uses
  the non-linguistic `C` locale, entry timestamps include the full date and UTC
  offset, and headers use portable project/Git identity instead of an absolute
  workspace path;
- the plugin manifest exposes a focused read-only history skill, while normal
  lifecycle events inject neither maintenance nor history context;
- raw prompts, transcripts, full tool output, credentials, secrets, and
  unnecessary personal data are not copied into the worklog or plugin state;
- complete final responses are not retained; the automatic summary removes
  code fences, hook metadata, link targets, local paths, full SHA-256 values,
  and common labelled secret values before writing;
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
- a guarantee that hook-derived summaries are complete or correct;
- a live-state database. Files, Git, services, external systems, dates, and
  prices must be verified again before a later session relies on them.

The format is intentionally project-independent and does not assume a software
stack, package manager, deployment model, or even the presence of Git.

## Audit standard

Claims about behavior should be supported by executable tests or reproducible
acceptance evidence. A package or validator passing is not enough when a claim
depends on live Codex behavior: material, acknowledgement-only, resume, coding,
non-coding, and requested context-recovery scenarios must also be exercised.

See the [architecture](ARCHITECTURE.md), [threat model](THREAT_MODEL.md),
[commissioning report](COMMISSIONING.md), and
[sanitized worklog example](../examples/EXAMPLE_WORKLOG.md).
