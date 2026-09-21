# Releasing Codex Worklog

Codex Worklog follows [Semantic Versioning](https://semver.org/). Tags use the form `vMAJOR.MINOR.PATCH` and must match the version in `plugins/codex-worklog/.codex-plugin/plugin.json` without the `v` prefix.

## Release Requirements

- `main` is clean and up to date.
- All CI checks pass on Linux, macOS, and Windows.
- `CHANGELOG.md` describes user-visible changes.
- English and Russian installation documentation agree.
- Privacy, security, migration, and compatibility impact were reviewed.
- Hook changes were tested from an installed marketplace copy, not only from the source path.

## Prepare the Release

1. Choose the version according to SemVer.
2. Update `plugin.json`.
3. Move relevant changelog entries from **Unreleased** into a dated version section.
4. Verify marketplace and plugin identifiers remain `codex-worklog`.
5. Run:

   ```bash
   python3 -m compileall -q plugins scripts tests
   python3 -m unittest discover -s tests -v
   python3 scripts/validate_repository.py
   ```

6. Validate the plugin with the current Codex `plugin-creator` validator.
   Regenerate saved hook commands with `python3 scripts/build_hook_commands.py --write`
   after any runtime or launcher change; the hook pins the full runtime digest.
7. Register a temporary local marketplace, install the plugin, trust the reviewed hooks, and run a smoke task in a temporary directory.
8. Confirm exact author-command delivery and a diary commit before `submit`
   returns `recorded: true` and `staged: false`, even without `Stop` or
   `SessionEnd`. Check nonzero storage failures with retained staging, recovery
   through command and hook retries, retries across midnight, concurrent daily
   appends, explicit skips, missing-payload warnings, evidence preservation, language priority, resume
   prefix preservation, compaction context, quiet session close, disabled mode,
   and uninstall behavior. Inspect an actual model-authored work block; a schema
   test alone does not establish semantic quality.
9. In an isolated Codex home, deliver an author command, replace the whole
   installed package through native reinstall, then execute the **previously
   delivered command**. Require an actual diary commit, an unchanged existing
   prefix, no duplicate retry, and a fresh command for the next host turn from
   the saved old hook. Repeat with a staged storage failure and a Stop retry.
   A warning and exit 0 alone do not pass this gate. Also verify unprimed missing
   runtime warnings, digest/link rejection, disabled mode, direct nonzero submit
   failures and updater operation IDs/cache inventories. Never delete a working
   task's cache for testing. Pre-retention tasks need a one-time reviewed reload.

## Publish

1. Merge the reviewed release pull request.
2. Create a signed annotated tag:

   ```bash
   git tag -s vMAJOR.MINOR.PATCH -m "Codex Worklog vMAJOR.MINOR.PATCH"
   git push origin vMAJOR.MINOR.PATCH
   ```

3. Create a GitHub Release from the tag using the matching changelog section.
4. Verify a clean installation from the Git-backed marketplace at the release tag.
5. Check that the README badges, release link, and marketplace metadata resolve publicly.

## Security Releases

Coordinate security releases privately according to [SECURITY.md](SECURITY.md). Publish details only after a fixed version is available, and avoid exposing exploit-ready information before users can update.
