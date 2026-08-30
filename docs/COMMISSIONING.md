# Commissioning and Audit Report

This document records the local pre-release acceptance audit performed on
2026-08-30. It is evidence for the reviewed revision, not a permanent claim
that future Codex, Python, operating-system, or GitHub behavior is unchanged.

## Scope

The audit covers:

- the current official Codex plugin, marketplace, skill, and hook contracts;
- installability from a clean repo marketplace;
- `SessionStart`, `UserPromptSubmit`, `Stop`, and `SessionEnd` behavior;
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

No production package was added. Independent audit tools ran from temporary
environments and were not committed or installed as runtime dependencies.
The local repository had no configured Git remote, so the audit did not create
or change GitHub repositories, releases, branches, or status checks.

## Findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| CW-001 | High | The pinned CodeQL action SHA did not exist upstream, so the workflow could not run. | Replaced both CodeQL references with the verified commit for `v4.37.9`. |
| CW-002 | Medium | `interface.defaultPrompt` used a string while the current schema requires an array of up to three bounded strings. | Converted the field to a two-entry string array and added a regression check. |
| CW-003 | Medium | Previous-worklog discovery could advertise a symlink, and runtime state/worklog files did not reject hard links. | Restricted candidates and runtime I/O to recognized regular single-link files and added opened-file identity checks. |
| CW-004 | Medium | Corrupt state could be silently replaced or produce an unstructured internal failure. | Added size, JSON, shape, workspace, and end-counter validation with model-visible errors. |
| CW-005 | Medium | The repository validator did not require the marketplace or itself and checked several fields only for presence. | Expanded manifest, marketplace, hook, asset, link, action-pin, and required-file validation with mutation tests. |
| CW-006 | Medium | GitHub workflows retained checkout credentials, and CodeQL permissions were broader than needed. | Disabled credential persistence and moved minimal permissions to the CodeQL job. |
| CW-007 | Low | The original runtime test suite had 11 tests and 77% branch-aware runtime coverage. | Expanded lifecycle, CLI, privacy, state, and path regression coverage and added validator mutation tests. |
| CW-008 | Low | Contributor instructions contained a placeholder formatted as a live clone URL. | Replaced it with an explicit fork workflow and non-live placeholder argument. |

## Verification Matrix

The final evidence is produced by these independent layers:

```bash
make check
python3 -W error -m unittest discover -s tests -v
python3 scripts/validate_repository.py
```

| Layer | Result |
|---|---|
| Native tests | 58 of 58 passed with warnings promoted to errors; the repository contract validated all 40 required files. |
| Runtime coverage | 90% branch-aware coverage for the dependency-free hook runtime. CLI subprocess behavior is tested separately. |
| Python compatibility | The same 58 tests and 40-file contract passed from read-only Python 3.10.21 and 3.14.7 containers. |
| Official Codex validators | The current `plugin-creator` and `skill-creator` validators passed, and the marketplace name resolved to `codex-worklog`. |
| Python quality | Ruff lint and format checks, strict mypy, and Bandit completed with no findings. |
| Repository and prose | Markdownlint checked 17 files with zero errors; codespell, local-link validation, and the deterministic 1,000-event malformed-input smoke test passed. |
| Secrets and assets | Detect-secrets returned no candidates. Guarded SVG parsing and the unsafe-SVG mutation test passed. |
| GitHub automation | Actionlint, GitHub workflow and Dependabot schema validation, yamllint, and pedantic zizmor completed with no findings. Every action reference is a full commit SHA; the CodeQL commit was also resolved from the peeled upstream `v4.37.9` tag. |
| Isolated installation | A clean local marketplace add and plugin install succeeded under an isolated `CODEX_HOME`; the installed files matched the source plugin byte-for-byte. |
| Live Codex lifecycle | A real Codex task created the worklog, wrote its exact turn marker, and added a session checkpoint. Resuming the task from the same workspace reused the file, wrote a second marker, and added a second checkpoint. |
| Installed-hook lifecycle | The installed copy passed startup, strict missing-marker block, post-marker acceptance, compact restart, prompt and assistant-output non-persistence, and idempotent `SessionEnd`. |
| Permissions and uninstall | Worklog directories were `0700`; worklog and state files were regular, single-link `0600` files. Uninstall removed the plugin and marketplace while preserving the worklog with the same SHA-256 digest. |

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

## Release Decision

The audited revision is accepted as a Linux-tested publication candidate. All
eight findings above are resolved, and no unresolved finding remains from the
local functional, security, packaging, documentation, or installed-copy audit.

This is not a claim that every future environment is defect-free. Final
cross-platform release acceptance remains gated on the Linux, macOS, and
Windows GitHub Actions jobs and CodeQL run for the exact published commit. Any
future release must repeat the checklist in
[RELEASING.md](../RELEASING.md) against current official Codex documentation.
