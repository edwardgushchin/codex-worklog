# Commissioning and Audit Report

This document records the local pre-release acceptance audit performed on
2026-08-30. It is evidence for the reviewed revision, not a permanent claim
that future Codex, Python, operating-system, or GitHub behavior is unchanged.

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
