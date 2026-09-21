# Commissioning and Audit Report

This document records revision-specific acceptance evidence. Earlier reports
are retained as history; their test counts, installations, and release decisions
do not establish acceptance of the current source.

## Automatic goal turn binding — 2026-09-07

In the reported desktop goal, automatic continuations did not initialize a new
`UserPromptSubmit` turn. Compaction repeatedly supplied the first turn's command,
so independent work was rejected as a replacement of the already recorded block.
The isolated RED reproduction also rejected an invented replacement turn ID:
it had never been bound by a host event.

The fix adds a turn-scoped `PreToolUse` hook, shares turn initialization with
`UserPromptSubmit`, and refreshes context once per turn or after compaction.
`SessionStart` no longer emits a stale command. An old literal command in the
same live host session can use the current host-observed tool turn; an exact
retry still identifies the original entry. No transcript inspection or relaxed
same-turn overwrite rule was added.

Verification for installed version `0.2.0+codex.20260907190040`:

- All 82 source tests passed on Python 3.14 and network-disabled Python 3.10.21
  with a read-only repository mount. Compilation, the 44-file repository
  contract, source and installed plugin validators, and diff whitespace checks
  passed. One additional CLI test initially assumed that a fixed fixture date
  and today's real CLI date shared a daily file; its assertion was corrected
  to count both files, without changing the runtime date behavior.
- All 67 runtime and storage-security tests passed against the installed code.
  Each of 25 retained cache roots matched all seven source package files and
  passed the multi-turn automatic-continuation/compaction regression.
- The desktop's Codex 0.153.1 binary discovered all five hooks through its
  native `hooks/list` API. Only the new `PreToolUse` definition required a
  reviewed trust entry; the native version-checked configuration write and
  readback confirmed all five enabled and trusted in both affected workspaces.
  No hook-trust bypass was used.
- The already-running desktop goal had not loaded the new handler at the last
  readback: its state still lacked `tool_turn_id`. Its execution was not
  interrupted or resumed by this repair. Applying the new hook in that task
  requires a host reload and continuation; actual diary delivery from its next
  automatic turn remains unverified. Native macOS/Windows acceptance is also
  pending. Synthetic lifecycle tests are not a substitute for those checks.

Runtime SHA-256:
`41edb29b11834cda3330fb5c79d3d746225b043a2d567fa293ddd752da7eceec`.
Existing diaries were not rewritten or backfilled; unrelated worktree changes
were preserved. No commit, publication, or release was created.

## Submission commit boundary — 2026-09-05

A completed desktop task had a valid model-authored payload left in private
`staged` state without a daily diary. The successful staging response was not
proof of publication. The maintainer approved moving the normal commit boundary
into `submit`, with `Stop` and `SessionEnd` retained only as recovery paths.

The revised contract validates and sanitizes the payload, durably stages it,
then atomically commits the daily file before returning `recorded: true` and
`staged: false`. Storage errors exit nonzero without claiming success; prepared
work remains available for a command or hook retry. Missing author content is
still warned about and skipped, never synthesized or requested through a forced
continuation.

Acceptance for this change must verify that the diary exists when `submit`
returns, with no `Stop` or `SessionEnd` dispatched. It must also cover retained
staging after publication failure, command and hook recovery without duplicate
blocks, and the actual installed desktop path. The earlier test counts and CLI
acceptance below apply to the previous commit boundary, not this fix.

## Model-authored daily work blocks — 2026-09-04

The maintainer rejected the previous compact regex-derived diaries as too weak
to recover substantial work. The accepted quality reference is the six-section
work-block structure in a manually maintained diary: context, chronology,
changes, decisions, checks, and next steps. Its project-specific workflow is not
part of the plugin contract.

The source redesign makes the active model the semantic author. Lifecycle
context supplies the schema and an exact quoted runtime command; the author
submits JSON through stdin. The runtime validates and sanitizes that payload,
stages it in versioned private state, and commits complete blocks at `Stop`.
`SessionEnd` only flushes staged work. Missing submissions warn and skip instead
of starting a maintenance continuation or falling back to sentence extraction.

New records share `.dev-diary/YYYY/MM/YYYY-MM-DD.md`. Marker checks and commits
use a cross-process lock and atomic publication that preserves the original
bytes as a prefix. Targets derive from workspace-bound state rather than an
arbitrary caller-supplied path. New objects receive private permissions;
existing directory and diary permissions remain unchanged. Evidence can retain
exact commands, numerical results, relative paths, and complete SHA-256 digests.

The supplied command also removes routine authoring's dependence on expanding a
skill-root alias or reconstructing an installed cache path. The separate
history-inspection skill remains read-only. This is a concrete mitigation for
logging instructions; it is not proof that every future host-side file-opening
error is prevented.

### Acceptance status for this redesign

| Layer | Status |
| --- | --- |
| Source tests and repository contract | 70 warning-strict tests passed on Python 3.10.21 and 3.14.7; 44-file repository contract, compilation, plugin and skill validators, and diff whitespace checks passed. |
| Synthetic lifecycle, concurrency, privacy, and path checks | Passed in network-disabled Linux containers with a read-only repository mount and temporary writable storage. Includes concurrent sessions, crash retries, midnight retries, malformed private state, credential filtering, and link/path attacks. |
| Model-authored diary quality | A separate active model followed the actual returned instruction and exact command, repaired a temporary Python example (3 tests, 2 initial failures; rejected candidate; 3 final passes), and produced one Russian six-section block. The generated diary was read back; full digests and resolving artifact links were checked. |
| Native new-task instruction pickup | Passed in an actual ephemeral Codex CLI 0.153.2 session using the installed plugin and normal persisted hook trust. Desktop-panel task startup was not separately exercised. |
| Native macOS and Windows filesystem acceptance | Pending. |
| User installation or publication | Installed and enabled locally as `0.2.0+codex.20260904192836` after explicit authorization. No publication or release. |

The author exercise exposed loss of seconds in ISO timeline values. The runtime
now preserves seconds and fractional seconds; a regression also covers UTC `Z`
on Python 3.10. The exercise used temporary files, not an actual application
defect or a live installed-plugin session. Markdownlint was not completed because
its package fetch failed; it is not included among the passing checks.

### Installed acceptance — 2026-09-04

The update used the cachebuster helper and `codex plugin add`. All 21 previous
cache roots were backed up before the update and retained as compatibility
paths, giving 22 roots including the active version. All seven package files
matched the validated source in every root. The installed runtime passed all
56 lifecycle and security tests; the complete source suite passed all 70 tests.
All 22 cache paths also passed an isolated author-context, submission, `Stop`,
and duplicate-`Stop` lifecycle; each produced exactly one entry.

The native hook browser reported `SessionStart` and `Stop` as modified because
their status messages changed. Those two exact definitions were reviewed and
trusted through the native configuration API with optimistic version checking;
the other hook trust and permissions were preserved. All four plugin hooks
were then confirmed enabled and trusted. No hook-trust bypass was used.

An actual `codex exec --ephemeral` run used the default configured model, a
temporary workspace, and workspace-write access including this plugin's data
directory. Its prompt requested a small Python fix, not diary instructions.
The model received the plugin context, reproduced three failures out of four
tests, corrected Unicode label deduplication, reran four passing tests, and
submitted its own Russian payload through the exact installed command. The
normal host lifecycle committed one 3,376-byte daily block with all six sections;
private turn state was `committed` with no pending payload. Reading the diary
confirmed the failed and successful checks, causal decisions, and absence of
the absolute temporary workspace path. The unrelated Git diagnostic failure
was preserved honestly because the example was not a Git repository.

The native test diary SHA-256 was
`855a8b68ed7698a6e5796399ec5db918acf8ba891424aa4ee208951e5325328a`.
This establishes the real CLI path, not native macOS/Windows acceptance or a
separate desktop-panel startup check. Existing user diaries were not rewritten.

Existing diaries and legacy state were not rewritten or migrated. The earlier
reports below document superseded formats and append strategies; in particular,
the 2026-09-03 handoff result is historical evidence, not current semantic
acceptance. Schema and privacy checks cannot prove arbitrary textual claims or
semantic consistency. No native Windows parent-race guarantee is inferred from
POSIX descriptor-based checks.

## Session handoff redesign — 2026-09-03

The diary reported by the maintainer contained 25 entries, 718 lines, repeated
fields, truncated lists, false change/check classifications, and 24 accidental
`[local path]` replacements. The append boundary was the root cause: `Stop`
wrote one entry for almost every assistant response before later turns could
establish the final state.

`Stop` now stores only bounded sanitized facts in private session state.
`SessionEnd` writes one consolidated entry with a factual heading, required
`Result` and `Check`, optional state/chronology/change/decision/cancellation/
blocker/artifact/next-step fields, and final `HEAD` plus `git status`. Only the
six latest change milestones and three latest change groups are retained.
Future actions are not checks or completed changes; rollback targets are marked
as cancelled and can supersede a prior persisted entry. Project-relative
artifact links, safe HTTPS links, complete bounded lists, and identifiers such
as `HomeAction / Главная` are preserved.

A replay of all 30 final assistant messages present in the reported Codex
session at the final check produced one 20-line, 196-word handoff with one
result, one check, no
`[local path]`, and no empty decision/check placeholders. Focused regressions
cover the four reported classification failures, result-list preservation,
session consolidation, cancellation links, and final Git state. Bytecode
compilation, all 90 tests, the 43-file repository contract, the plugin
validator, and `git diff --check` passed. The source candidate is
`0.2.0+codex.20260903201035`. Updating the local marketplace manifest caused
Codex to refresh that installed cache automatically and remove older versioned
roots. All 20 older paths still referenced by session history were immediately
restored from the validated source. Runtime and hook hashes, hook JSON, and a
minimal invocation matched across all 21 roots; complete temporary lifecycles
also passed through both the active root and the formerly failing
`0.2.0+codex.20260901141205` root. No explicit CLI reinstall was invoked.
Native fresh-task UI pickup remains pending.

## Structured semantic entries — 2026-09-02

The automatic heading no longer comes from `UserPromptSubmit`. Prompt text is
discarded after intent classification; `Stop` derives a task summary and
context from bounded assistant commentary, with the bounded final outcome as a
fallback. Existing private state is also stripped of the legacy
`last_turn_title` field when reopened.

Entries now render in one fixed order: context, chronology, changes, decisions,
checks, optional next steps, and result. Missing decisions and checks are
reported explicitly instead of being inferred, while read-only and explicit
no-change turns receive a truthful no-change statement. The compatibility
append schema accepts optional `context` and `changes` fields and uses safe
fallbacks when older callers omit them.

The source passed bytecode compilation, all 85 unit tests, the 43-file
repository contract, the current plugin validator with PyYAML 6.0.3,
markdownlint-cli2 0.23.2, and `git diff --check`. The local installation was
refreshed as `0.2.0+codex.20260902202202`; source and active cache were
byte-identical. All 19 prior cache paths were repopulated from that active tree,
and all 20 roots had matching runtime and hook hashes and returned valid hook
JSON. Full installed lifecycles through both the active path and the previously
failing `0.2.0+codex.20260901151656` path confirmed the section order and that
the user's prompt text was absent. Existing historical diary entries were not
rewritten. Visual desktop acceptance was stopped at the maintainer's request.

## Chronological action enrichment — 2026-09-01

A comparison with the project's manually maintained portfolio diary showed the
remaining semantic gap: the automatic entry retained the result and selected
decisions but discarded the chronological path through inspection, failed
attempts, recovery, changes, and verification.

`Stop` now renders a nested `Actions`/`Действия` block from assistant
commentary in the matching turn. Each bullet carries the transcript event's
local `HH:MM` time and at most two normalized sentences. A turn retains at most
twelve updates; longer turns preserve the first and last six. The existing
role, turn, path, size, redaction, and raw-transcript restrictions still apply,
and the compatibility `append` schema remains unchanged.

Replay of the original Penpot setup produced six chronological phases covering
the official deployment choice, Docker and port checks, pinned installation,
the recoverable TLS failure, seven-container startup, UI onboarding, and the
confirmation boundary. The installed-copy smoke rendered those phases beside a
concise outcome, reason, verified state, and next step.

The source passed bytecode compilation, all 85 unit tests, the 43-file
repository contract, `git diff --check`, and the current plugin and skill
validators. The validators used the host's installed `python-yaml` 6.0.3
package. The local marketplace installation was refreshed as
`0.2.0+codex.20260901152911`; its cached plugin tree matched the source tree.
A new Codex task remains the native hook-pickup boundary, and historical
append-only diary entries were not rewritten.

Already-open tasks still referenced removed cache versions. Restoring only the
development task's `0.2.0+codex.20260901141205` path proved insufficient when a
second task failed through `0.2.0+codex.20260901151656`. Session history named
19 cache versions in total, so all 18 stale roots were repopulated with the
validated `0.2.0+codex.20260901152911` plugin tree without another reinstall.
Every restored root had matching runtime and hook-definition hashes and
returned valid hook JSON. A complete temporary lifecycle through the exact
`0.2.0+codex.20260901151656` path from the UI error created the expected entry
and closed its private state. These local compatibility copies exist only for
already-open tasks and do not replace new-task pickup of the active cache.

## Turn-context semantic correction — 2026-09-01

A real 20-minute Penpot setup turn exposed that the hook reduced all decisions,
failures, verification, and remaining work to one final-answer paragraph. Two
later turns also used Codex's injected `Current URL` browser context as their
headings instead of the user's requests.

`Stop` now transiently reads a bounded trusted transcript and selects only
assistant commentary from the matching turn. User and developer messages,
reasoning, tool calls, tool output, final-answer records, and other turns are
ignored. The resulting entry separates outcome, decision context, verified
state, and remaining work. The request classifier also removes the injected
in-app browser block and `My request` wrapper before intent and heading
derivation.

Replay of the original Penpot turn produced a subject-bearing heading, the
installed and connected state, the pinned/local-only/retry decisions, the
seven-container verification, and the pending MCP-plugin confirmation as five
separate fields. The source passed bytecode compilation, all 85 tests, the
43-file repository contract, `git diff --check`, and the official plugin
validator. PyYAML 6.0.3 was installed as the host's `python-yaml` package for
that validator; the plugin still has no runtime package dependency.

The local marketplace installation was refreshed as
`0.2.0+codex.20260901151656`. Its cached tree matched the source tree, and an
installed-copy smoke invoked through the pre-refresh cache path, proving that
the compatibility forwarder and enriched entry both worked. A new Codex task
is still the required acceptance boundary for native hook pickup; historical
append-only diary entries were not rewritten.

## Final trusted-hook regression acceptance — 2026-09-01

The final installed candidate is
`0.1.0+codex.20260901114849`. Its cached plugin tree matched the source tree,
and the trusted hook definition retained the reviewed SHA-256 value
`6eed551aa978a617ebdecc06e2106cc66d9e9a375652e7c8b1438da9e00df746`.
No final field-regression run used `--dangerously-bypass-hook-trust`.

The acceptance campaign found and resolved three Russian-language semantic
boundaries that the earlier unit suite did not cover:

- a request for user confirmation was incorrectly inferred as completed
  verification;
- the completed-state wording `состояние зафиксировано` was not recognized as
  a state change;
- `Ничего не изменял` was not recognized as a no-change statement when the
  preceding sentence contained `завершён`.

Each correction has a focused regression test. The final native gate passed
all 83 tests with warnings promoted to errors, bytecode compilation, the
43-file repository contract, `git diff --check`, Ruff lint and format checks,
strict mypy, codespell, detect-secrets with zero candidates, markdownlint with
zero errors, and the official plugin and skill validators. Bandit reported no
product-code findings under Python 3.10.21. The same 83 tests and repository
contract passed in a network-disabled, read-only Python 3.10.21 container.

A clean isolated marketplace add and plugin install of the final candidate
succeeded. The installed runtime kept a no-change turn at zero entries, wrote
one entry for `Итоговое состояние зафиксировано`, and preserved that worklog
byte-for-byte after plugin and marketplace removal. The broader installed
lifecycle matrix also passed Russian locale fallback from `C.UTF-8`, non-Git
and Unicode paths, Stop idempotency, read-only and context-recovery byte
identity, acknowledgement skipping, root-cause recording, inferred blocker
links, explicit status replacement, concise verification, relative report
artifacts, append-only resume prefixes, separate session files, private modes,
prompt canary exclusion, and side-effect-free off mode.

A real non-Git Codex task with spaces and Cyrillic in its path ran the trusted
hooks through the normal host lifecycle. Its material turn produced exactly
one Russian entry with cause, `absent → present`, verification, and a relative
report link, without an absolute workspace path. A `$worklog` resume read only
the installed skill and the current workspace diary, independently rechecked
the artifact, and left the diary byte-identical. A subsequent `Спасибо!` turn
also left it byte-identical.

The project `Моя мигрень` received a fresh final-version field session without
reading its project files. SessionStart created a private portable Russian
worklog, while the explicit no-change turn added zero timeline entries. The
earlier field run that exposed the missing `изменял` form remains in its own
append-only historical worklog; it was not rewritten or deleted.

Codex also emitted host-wide warnings about skill interface icon paths that
contain `..`. The `codex-worklog` archive does not define those fields: its
manifest uses only `./assets/...` paths and its skill has no
`agents/openai.yaml`. Hook dispatch and all worklog assertions still passed.
Native macOS and Windows execution remains outside this Linux field campaign.

## State-change and trusted-hook field acceptance — 2026-09-01

The state-change classifier now separates acknowledgement, context recovery,
other read-only work, requested mutation, and unknown intent without retaining
the prompt. `Stop` appends only a reported mutation, newly established cause or
decision, explicit transition, or new blocker. Context recovery is a hard
zero-entry path, so historical cause and transition fields cannot be appended
again merely because `$worklog` summarizes them.

The normal lifecycle path now extracts optional cause/decision, blocker link,
status transition, concise verification, artifact, and next-step fields from a
bounded normalized final response. Language detection falls back from the hook
process's `C.UTF-8` environment to the host's `ru_RU.UTF-8` locale
configuration. The bundled inspection skill prohibits initiating parent, home,
global-memory, or conversation-history discovery and reports an absent
workspace worklog instead of searching elsewhere.

The source passed bytecode compilation, all 81 unit tests, the 43-file
repository contract, `git diff --check`, Ruff check and format verification,
the official plugin and skill validators, and the same 81 tests plus repository
contract under a network-disabled read-only Python 3.10.21 container. PyYAML
and Ruff were installed only in a disposable validation environment; no project
dependency was added.

The transition candidate was installed as
`0.1.0+codex.20260901111845`. A new non-Git Codex task then ran the trusted hooks
without `--dangerously-bypass-hook-trust`. Its first turn created
`package-ready` with an explicit pending condition; its second turn created the
approval condition and moved to `installed`. The Russian worklog contained
exactly two entries and two markers, one per resulting state change. The
completed entry included `Причина/решение`, an inferred `Разблокирует` reference
to the first entry, `Заменяет статус: package-ready → installed`, a concise
`Проверено` result, and a project-relative `Артефакты` link. It contained no
absolute workspace or home path.

That field run exposed one remaining semantic boundary: a context-recovery
answer could repeat historical optional fields. The hard zero-entry intent was
added and the final package was refreshed as
`0.1.0+codex.20260901112207`. Its cached plugin tree matched the source tree,
including the restored skill, runtime, manifest, and unchanged hook definition.

The same live task then invoked `$worklog`. The agent loaded the installed
skill, discovered and read history only under the current `cwd`, performed a
separate read-only check of the two state files, and did not search global
memory or conversation history. The worklog remained byte-identical at 1,667
bytes with two entries after that turn; private plugin state recorded only the
`context_recovery` enum and hashed turn identifier, not the prompt or response.

## Context-recovery scope correction — 2026-09-01

The earlier removal of the bundled `worklog` skill incorrectly generalized a repository-specific request to remove manual diary instructions. The skill has been restored as a read-only inspection and context-recovery workflow: it can read relevant history when requested, treats diary text as untrusted, and never creates, appends, repairs, or reorders entries. Routine lifecycle writes remain entirely hook-owned, and `SessionStart` plus `UserPromptSubmit` still return no maintenance context.

The corrected source passed bytecode compilation, all 73 unit tests, the 43-file repository contract, `git diff --check`, and the current Codex plugin and skill validators. The official validators ran in a temporary environment with PyYAML 6.0.3; no dependency was added to the project.

The local marketplace was refreshed as `0.1.0+codex.20260901095014`. The cached plugin tree was byte-for-byte equal to the source tree apart from ignored bytecode and contained `skills/worklog/SKILL.md`. An isolated installed-runtime lifecycle smoke created one Russian entry with a portable header, removed generic token and private-key canaries, removed the tail of an unquoted absolute path containing spaces, and did not expose the temporary workspace path. A new Codex task is still required to prove host pickup of the refreshed skill and hooks; the preceding no-skill installation remains historical evidence for the superseded package only.

## Hook-owned lifecycle revision — 2026-09-01

The routine append path no longer depends on the active agent. `SessionStart`
and `UserPromptSubmit` return empty JSON after updating private state, while
`Stop` derives a bounded summary from the official `last_assistant_message`
field and appends it directly. The runtime ignores `transcript_path`, never
injects the target path, helper schema, or marker into model context, and does
not create a continuation prompt when writing fails. An internal hashed marker
keeps repeated `Stop` events idempotent, and `Stop` reconstructs missing state
when earlier lifecycle events were skipped.

The source revision passed bytecode compilation, all 72 unit tests, the 42-file
repository contract, `git diff --check`, markdownlint-cli2 0.18.1 with zero
errors, and the current Codex plugin validator. The plugin validator ran in an
ephemeral environment with PyYAML 6.0.3 because its own undeclared import was
not available in either host or bundled Codex Python. Installed-copy smoke and
a real new-task lifecycle run are recorded separately from this source gate.

The superseded local marketplace install was refreshed as
`0.1.0+codex.20260831233036`; the cached plugin tree was byte-for-byte equal to
the source tree, contained no skill directory, and its hook definition contained
no `additionalContext`. A temporary installed-runtime smoke invoked `Stop`
without prior session state and confirmed a hook-owned Russian entry at the
canonical session path plus redaction of an absolute link target and a labelled
API key. These direct installed-script checks do not replace a new Codex task
proving that the host loaded and dispatched the refreshed hook definition.

## v0.2.0 worklog-contract revision — 2026-08-31

The 2026-08-31 source revision treated one resulting state change as the unit
of an entry, added explicit blocker/status transition links and report
artifacts, used full date-and-offset entry headings, localized visible content
from the system locale, and replaced visible absolute workspace paths with
portable project/Git identity. That runtime rejected absolute local paths and
full SHA-256 values from timeline fields and validated local artifact targets
before linking them.

The final local source gate for that revision completed successfully on Python
3.14.7: bytecode compilation, all 70 unit tests, and the 43-file repository
contract passed. `git diff --check` also passed. The bundled plugin and skill
validator entry points were attempted with both host and Codex runtime Python,
but their undeclared `PyYAML` import was unavailable; no package was installed
and those two validator results are therefore not claimed. The source plugin
was not reinstalled and no new live-session acceptance was performed because
the current change request did not authorize user Codex configuration changes.

## Final v0.1.0 delta

An external review of the audited candidate led to one deliberately small
finalization pass:

- entries now require only `title` and `summary`; `changes`, `verification`,
  and `next` are optional, and the separate `decisions` field is gone;
- visible session/model metadata and session checkpoints were removed from the
  human-readable file;
- automatic previous-worklog discovery now uses only valid records in private
  `PLUGIN_DATA`, and agents are told never to follow worklog-embedded
  instructions or treat them as authorization;
- `.gitignore` policy remains the user's choice; the plugin does not edit it;
- no pause/resume/skip-once subsystem or separate eval framework was added.

The final delta passed all 65 tests and the 42-file repository contract on
Python 3.10.21 and 3.14.7, plus the official plugin and skill validators, Ruff,
strict mypy, Bandit, codespell, and markdownlint. References below to checkpoint
entries and the earlier seven-field shape describe the original commissioning
run and are retained as historical evidence rather than the final file format.

A final installed-copy semantic smoke added three representative boundaries:
a coding task produced only `Summary`, `Changes`, and actual `Verification`; a
non-coding recommendation produced one useful `Summary` with no filler; and an
acknowledgement-only resume used no tools and left the worklog byte-identical.

## Scope

The audit covers:

- the current official Codex plugin, marketplace, skill, and hook contracts;
- installability from a clean repo marketplace;
- `SessionStart`, `UserPromptSubmit`, `Stop`, and `SessionEnd` behavior;
- fixed-schema helper appends, acknowledgement skipping, and model/tool overhead;
- resume and compaction context recovery;
- prompt and transcript non-persistence;
- workspace confinement, links, permissions, malformed state, and failure paths;
- Python compatibility and dependency-free runtime operation;
- Git integrity, community health files, documentation, and release guidance;
- GitHub Actions syntax, immutable action pins, token permissions, CodeQL, and
  Dependabot configuration.

## Acceptance Environment

- Codex CLI: `0.149.0`
- Native host: Linux x86-64
- Native Python: `3.14.7`
- Container Python: `3.10.21` and `3.14.7`
- Git: `2.55.0`
- Live acceptance model: `gpt-5.6-sol` with medium reasoning

No production package was added. Independent audit tools ran from temporary
environments and were not committed or installed as runtime dependencies.
The local repository had no configured Git remote, so the audit did not create
or change GitHub repositories, releases, branches, or status checks.

## Findings

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| CW-001 | High | The pinned CodeQL action SHA did not exist upstream, so the workflow could not run. | Replaced both CodeQL references with the verified commit for `v4.37.9`. |
| CW-002 | Medium | `interface.defaultPrompt` used a string while the current schema requires an array of up to three bounded strings. | Converted the field to a two-entry string array and added a regression check. |
| CW-003 | Medium | Previous-worklog discovery could advertise a symlink, and runtime state/worklog files did not reject hard links. | Restricted candidates and runtime I/O to recognized regular single-link files and added opened-file identity checks. |
| CW-004 | Medium | Corrupt state could be silently replaced or produce an unstructured internal failure. | Added size, JSON, shape, workspace, and end-counter validation with model-visible errors. |
| CW-005 | Medium | The repository validator did not require the marketplace or itself and checked several fields only for presence. | Expanded manifest, marketplace, hook, asset, link, action-pin, and required-file validation with mutation tests. |
| CW-006 | Medium | GitHub workflows retained checkout credentials, and CodeQL permissions were broader than needed. | Disabled credential persistence and moved minimal permissions to the CodeQL job. |
| CW-007 | Low | The original runtime test suite had 11 tests and 77% branch-aware runtime coverage. | Expanded lifecycle, CLI, privacy, state, and path regression coverage and added validator mutation tests. |
| CW-008 | Low | Contributor instructions contained a placeholder formatted as a live clone URL. | Replaced it with an explicit fork workflow and non-live placeholder argument. |
| CW-009 | High | During a real resume, a general-purpose model edit inserted a new entry before an older session checkpoint. The marker still passed, so the claimed append-only chronology was false. | Replaced direct model edits with one bundled fixed-schema helper that revalidates the path and writes with `O_APPEND`; a regression requires all old bytes to remain an exact prefix after resume. |
| CW-010 | Medium | A pure acknowledgement incurred a full strict logging continuation, multiple file tools, and a semantically empty entry. | Added a narrow whole-prompt acknowledgement classifier and zero-entry `Stop` handling; final v0.1.0 writes no `SessionEnd` checkpoint at all. Any question, cancellation, decision, or added instruction remains material. |

## Verification Matrix

The final evidence is produced by these independent layers:

```bash
make check
python3 -W error -m unittest discover -s tests -v
python3 scripts/validate_repository.py
```

| Layer | Result |
| --- | --- |
| Native tests | 64 of 64 passed with warnings promoted to errors; the repository contract validated all 42 required files. |
| Runtime coverage | 91% branch-aware coverage for the dependency-free hook runtime, including helper and hook subprocesses. |
| Python compatibility | The same 64 tests and 42-file contract passed from network-disabled, read-only Python 3.10.21 and 3.14.7 containers. |
| Official Codex validators | The current `plugin-creator` and `skill-creator` validators passed, and the marketplace name resolved to `codex-worklog`. |
| Python quality | Ruff 0.16.5 lint and format checks, strict mypy, and Bandit completed with no findings. |
| Repository and prose | Markdownlint-cli2 0.23.2 with markdownlint 0.41.1 checked 19 files with zero errors; codespell and local-link validation passed. |
| Secrets and assets | Detect-secrets returned zero candidates after generated tool caches were excluded. Guarded SVG parsing and the unsafe-SVG mutation test passed. |
| GitHub automation | Workflow files are byte-unchanged from the earlier actionlint/schema/pedantic-zizmor pass. The current repository validator reran immutable action-SHA and Dependabot checks; yamllint completed without errors. |
| Isolated installation | A clean local marketplace add and plugin install succeeded under an isolated `CODEX_HOME`; the installed files matched the source plugin byte-for-byte. |
| Installed-hook lifecycle | The installed copy passed startup, strict missing-marker block, helper idempotency, post-marker acceptance, privacy canaries, acknowledgement resume, exact-prefix material resume, and conditional `SessionEnd`. |
| Live Codex lifecycle | A real coding task and material resume each used exactly one helper call. The old 1,347 bytes remained an exact prefix, both file changes and checks matched the log, and chronological markers/checkpoints were `2/2`. |
| Live acknowledgement | A real `Спасибо!` resume completed in 8.7 seconds with 8 output tokens, zero tools, and a byte-identical worklog (same size and SHA-256). The prior strict implementation took 26.2 seconds, two shell checks, an edit, and 547 output tokens in the same one-shot A/B setup. |
| Non-coding and recovery | A real non-coding backup decision captured constraints, rationale, risk controls, verification limits, and next steps. A new session recovered it from the previous worklog and explicitly separated history from a fresh read-only filesystem check. |
| Subprocess efficiency | Across 40 material and 40 acknowledgement lifecycle runs, p50 totals were 312.35 ms and 244.44 ms. Material turns required one model file-tool call; acknowledgements required none and injected only 168 prompt-context characters. |
| Permissions and uninstall | Worklog directories were `0700`; worklog and state files were regular, single-link `0600` files. Isolated uninstall removed the plugin and marketplace while preserving all five acceptance worklogs with an unchanged aggregate digest. |

## Semantic Quality Review

- The coding entries matched the independently inspected file bytes, line
  counts, performed commands, and actual decisions. The material resume was
  chronologically after the older checkpoint.
- The non-coding entry preserved the 100 GB and 15 GB constraints, selected a
  full external copy plus a critical cloud subset, explained the failure modes,
  stated that no material workspace change occurred, and proposed restore and
  checksum checks. Relevant risk information fit naturally in `Decisions` and
  `Next`; mandatory `Risks` or `Blockers` fields were not needed.
- Context recovery identified its source as historical, then separately stated
  what the current filesystem check did and did not prove. This is the intended
  boundary between diary evidence and live truth.
- Pure acknowledgements now contribute no semantic noise and no model file-tool
  work. A prompt such as `Ок?` remains material, while `Ок!` is skipped; this
  guards questions from the acknowledgement normalization.
- Entries remain model-authored summaries rather than tamper-evident audit
  records. Prefix hashing and mandatory risk fields were deliberately not added
  because the accepted defects were resolved by a much smaller helper and
  classifier contract.

## Acceptance Boundary

Local Linux commissioning can validate the installed plugin and exact hook
wire format. Native macOS and Windows execution requires the configured GitHub
Actions matrix after the repository is published. Until those remote jobs run,
cross-platform support is supported by portable standard-library code, static
command validation, and the committed CI contract rather than current native
acceptance evidence.

The original v0.1.0 commissioning used a reviewed one-off trust bypass. The
final 2026-09-01 field regression instead used the user's persisted hook trust
and never passed `--dangerously-bypass-hook-trust`; normal users must still
review and trust the hook definition themselves.

The original live smoke test used a temporary `0600` authentication-file copy
inside a `0700` isolated `CODEX_HOME`. Its contents were never printed, and the
copy was removed immediately after the model runs. The later authorized field
regression refreshed the primary local plugin installation and separately used
a clean isolated profile for install and uninstall acceptance.

`SessionStart` necessarily precedes the prompt. Therefore a brand-new session
containing only an acknowledgement can leave a header-only worklog file; it
adds no turn entry or checkpoint. Lazy file creation was not adopted because it
would materially expand the lifecycle and state contract for negligible
semantic benefit.

## Release Decision

The audited revision is accepted as a Linux-tested publication candidate. All
ten findings above are resolved, and no unresolved finding remains from the
local functional, security, packaging, documentation, or installed-copy audit.

This is not a claim that every future environment is defect-free. Final
cross-platform release acceptance remains gated on the Linux, macOS, and
Windows GitHub Actions jobs and CodeQL run for the exact published commit. Any
future release must repeat the checklist in
[RELEASING.md](../RELEASING.md) against current official Codex documentation.
