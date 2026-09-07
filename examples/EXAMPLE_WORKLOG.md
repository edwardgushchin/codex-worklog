# Codex Worklog — 2026-09-04

## 2026-09-04 16:51 +03:00 — Migration verified; consumers switched with rollback retained

<!-- codex-worklog-session:example-session turn:example-turn -->

### Context

- Illustrative example, not a report of a production migration. The user needs
  to move a report archive without losing attachments or breaking consumers.
- The source remains authoritative until both integrity and the consumer path
  are verified. Copying files alone is insufficient evidence of completion.

### Timeline

- `14:10`
  - Established the source baseline: 120 reports and 34 attachment files.
  - Recorded relative filenames, sizes and SHA-256 digests before copying.
- `14:27`
  - Rejected the first copy: the manifest comparison found one missing
    attachment. A successful report-count check had not covered attachments.
  - Identified the exclusion pattern responsible and corrected the copy scope.
- `16:45`
  - Repeated the copy and the complete manifest comparison: all 154 files matched.
  - Switched the example consumer, opened a report with its attachment, and
    confirmed that rollback could still select the unchanged source.

### Changes

- The example consumer now reads from the verified destination. The original
  archive was not removed or modified.
- The verification procedure now includes attachments rather than only reports.
- No repository commit or production rollout occurred in this illustrative
  scenario; Git metadata does not apply.

### Decisions

- Retained the source through the agreed retention window to keep rollback
  reversible. Immediate deletion would remove that fallback without a need.
- Rejected report counts as the sole gate: the first candidate passed that
  check while still missing an attachment.
- Used filenames, byte sizes and full digests for integrity, then a consumer
  smoke check for usability. Neither check substitutes for the other.

### Checks

- First candidate: 120/120 reports, 33/34 attachments; FAILED. This candidate
  was not selected as the active destination.
- Final candidate: 154/154 filenames, byte sizes and SHA-256 values matched.
- Example evidence digest:
  `8d8c693225ab99c04fae20b66ea444cd35c0ba2ba388a1e9901de443a1423d71`.
- Consumer smoke: one report and its attachment opened from the destination;
  rollback selection still resolved to the source. This does not demonstrate
  that every consumer has been manually exercised.
- [Illustrative verification report](reports/MIGRATION_VERIFICATION.md).
  All names, events, counts and identifiers here are fictional.

### Next steps

- Keep the source until the agreed retention window ends. Before deletion,
  confirm destination use and obtain the required authorization.
- If a consumer reports a regression, select the retained source and investigate
  that consumer; do not repeat the migration blindly.

<!-- codex-worklog-entry:0123456789abcdef01234567 -->
