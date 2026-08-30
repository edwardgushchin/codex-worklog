# Commissioning and Audit Report

This document records the local pre-release acceptance audit performed on
2026-08-30. It is evidence for the reviewed revision, not a permanent claim
that future Codex, Python, operating-system, or GitHub behavior is unchanged.

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
| CW-010 | Medium | A pure acknowledgement incurred a full strict logging continuation, multiple file tools, and a semantically empty entry. | Added a narrow whole-prompt acknowledgement classifier, zero-entry `Stop` handling, and conditional `SessionEnd` checkpoints. Any question, cancellation, decision, or added instruction remains material. |

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

Hook trust is intentionally not persisted during automated acceptance. The
one-off Codex run uses the documented bypass only after reviewing the installed
hook definition; normal users must review and trust the hook hash themselves.

The live smoke test used a temporary `0600` authentication-file copy inside a
`0700` isolated `CODEX_HOME`. Its contents were never printed, and the copy was
removed immediately after the model runs. The primary Codex plugin and
marketplace configuration was not changed.

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
