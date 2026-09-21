# Threat Model

## Scope

Codex Worklog validates model-authored work blocks, stages them in private
plugin storage, and commits them to a workspace daily diary before `submit`
reports success. Lifecycle hooks retry prepared work. The active model
is a semantic author, not a trusted filesystem writer.

## Assets and assumptions

Assets include project history, evidence, local paths, session timing, turn
completion, and the integrity of unrelated workspace files. The user trusts
the installed hook definition, Codex host, and Python interpreter. The host
supplies lifecycle identifiers and plugin paths. A process with the user's
privileges can still alter user-owned content; this is not protection against
a compromised account.

Model submissions, restored state, workspace paths, existing diary contents,
and linked evidence are validated at their respective trust boundaries.
Schema validity does not establish semantic truth.

## Threats and mitigations

| Threat | Mitigation |
| --- | --- |
| Raw conversations or tool dumps are persisted | Hooks do not read transcripts or extract final messages. The author submits bounded semantic sections; raw prompts, complete responses, and tool dumps are outside the contract. |
| A summary exposes secrets | Redact recognized secrets and unsafe structures before staging. Keep intentional evidence such as SHA-256 values; never treat every long hex value as a credential. Arbitrary unlabelled secrets remain a review risk. |
| A helper overwrites an arbitrary workspace file | `submit` accepts session-bound content, not `worklog_path` or a marker. The destination derives from validated state and must match the configured root, daily filename, workspace, and header. |
| Tampered state crosses workspaces or sessions | Validate state shape, size, and host-bound session/turn workspace before staging or commit. Only a new host turn can switch workspaces; direct submissions cannot. Old prepared blocks retain their destination and are retried only when it is current. Corrupt state fails visibly instead of being silently replaced. |
| Traversal or a symlink redirects a write | Reject unsafe relative roots, symlinks, inspected Windows reparse points, and multi-linked state, lock, and diary files. POSIX directory descriptors anchor supported operations. |
| Filesystem checks are overstated on Windows | Treat Windows reparse and path validation separately from POSIX descriptor anchoring. Do not claim equivalent parent-race protection or native acceptance without evidence. |
| Existing user permissions change unexpectedly | Apply private modes to new files/directories only; preserve existing directory and diary modes during updates. |
| Two sessions race marker checks and writes | Hold a cross-process sidecar lock across marker detection and publication of old bytes plus new blocks. |
| A crash tears an append or causes duplicate retry | Flush and synchronize a temporary replacement before publication. Runtime-generated markers make a retry idempotent if diary publication preceded the state update. |
| A successful submission leaves no diary because an end hook is absent | Commit inside `submit` before returning `recorded: true` and `staged: false`. Durably stage first; storage failures exit nonzero without false success and retain prepared work for command or hook retries. |
| A submission inserts reserved diary structure | Validate an allowlisted JSON schema, section types, reserved markers, safe Markdown, references, and size before rendering. The author cannot supply entry IDs or destinations. |
| Input consumes excessive resources | Bound each submission to 64 KiB, eight blocks, 32 items per section/phase, 32 phases, and 4,096 characters per item. |
| Shell characters in installed paths execute code | Inject an exact quoted command using the installed runtime path and bound identifiers. Do not ask the author to reconstruct aliases or cache paths. |
| Missing author output blocks the task indefinitely | Both enabled modes warn and skip. No `Stop` continuation, retry loop, or regex fallback is generated. |
| A future action is presented as a completed check | Author instructions require explicit chronology, outcomes, failures, and limitations. Validation cannot prove these distinctions; semantic acceptance checks model behavior. |
| A local reference reveals outside paths | Convert in-workspace absolute references to relative ones and reject or remove unsafe external local paths. Diary headers omit the original absolute workspace path. |
| A linked artifact is mistaken for proof | Validate safe references; require the author and later reader to verify their relevance. A valid path or URL is not evidence that a claim is true. |
| A diary injects instructions during recovery | The read-only skill treats records as untrusted historical notes, stays inside the current task, and never treats embedded instructions as authority. |
| Stale notes drive a new action | Recheck mutable facts before relying on recorded status. Superseding references annotate history without editing it. |
| Diaries leak through Git or synchronization | The plugin neither changes ignore policy nor stages or publishes files. Users control sharing and retention. |
| Hook definitions change without review | Codex hook trust remains a host responsibility; installation and native acceptance are separate from source tests. |

## Residual risks

- A model can omit important context, invent an unsupported claim, or include an
  unlabelled secret. Redaction and structural checks are not semantic proofs.
- The model may fail to submit. Valid content must reach a successful `submit`
  commit; a missing end hook does not undo an already successful submission.
- A crash or storage error after staging but before publication can leave work
  pending. Recovery needs a command retry or a later lifecycle event; the runtime
  must not claim pending work is already in the diary.
- Plaintext files are not encrypted. Same-user processes can read or tamper
  with diaries, state, and locks.
- Atomic replacement and permission behavior depend on the platform and
  filesystem. Native Windows and macOS guarantees need explicit testing.
- A malicious Python executable earlier in `PATH` can replace the interpreter.
- Concurrent block order is commit order, not a global timestamp-sorted history.

## Out of scope

Encrypted storage, remote access control, regulatory retention, non-repudiation,
and protection against compromised users or operating systems are outside this
plugin's scope. It provides no guarantee that all work has been observed or
that every model-authored entry is correct.

Report vulnerabilities privately using [SECURITY.md](../SECURITY.md).
