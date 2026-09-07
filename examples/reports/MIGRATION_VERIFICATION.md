# Migration verification report

This fictional report accompanies the daily work-block example. It illustrates
supporting evidence; the work block still includes the important outcomes.

## Result

The destination copy matched the source, the consumer smoke check passed, and
the source remained unchanged for rollback.

## Evidence

- Source inventory: 120 reports and 34 attachments, 154 files total.
- First candidate: 120 reports and 33 attachments; rejected.
- Final destination inventory: 154 files, all names, sizes and digests matched.
- Manifest SHA-256: `8d8c693225ab99c04fae20b66ea444cd35c0ba2ba388a1e9901de443a1423d71`.
- Checks run: inventory comparison, manifest verification, read smoke test,
  consumer configuration check, and rollback-path check.

All names and values are illustrative.
