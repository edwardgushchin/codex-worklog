## Summary

<!-- Explain the problem and the approach taken. -->

## Related issue

<!-- Use Fixes #123, Closes #123, or Refs #123 when applicable. -->

## Changes

- <!-- Describe each material change. -->

## Verification

<!-- List the exact commands, operating systems, and manual checks used. -->

- [ ] `python3 -m compileall -q plugins scripts tests`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `python3 scripts/validate_repository.py`
- [ ] The current Codex plugin validator passes when plugin packaging changed.
- [ ] An installed-plugin smoke test was run when lifecycle behavior changed.
- [ ] Windows, macOS, and Linux impact was considered.

## Privacy and security

- [ ] No prompt, transcript, tool output, credential, token, private key, or unnecessary personal data is newly persisted.
- [ ] Paths remain inside session `cwd` or Codex `PLUGIN_DATA`.
- [ ] Symbolic-link, command-injection, and continuation-loop risks were considered.
- [ ] Threat model and privacy documentation were updated when boundaries changed.

## Compatibility and release impact

<!-- Describe hook/schema compatibility, migration needs, breaking changes, and release level, or write "None". -->

## Documentation

- [ ] User-visible behavior is documented in English and Russian.
- [ ] `CHANGELOG.md` is updated under **Unreleased**.
- [ ] No generated worklogs, plugin cache, secrets, or unrelated changes are included.
