# Support

## Documentation

Start with:

- [README](README.md) for installation, configuration, and limitations;
- [Russian README](README.ru.md) for the Russian-language overview;
- [Architecture](docs/ARCHITECTURE.md) for lifecycle and storage behavior;
- [Threat Model](docs/THREAT_MODEL.md) for security boundaries;
- [OpenAI plugin packaging documentation](https://developers.openai.com/plugins/build/plugins);
- [Codex hooks documentation](https://learn.chatgpt.com/docs/hooks).

## Where to Ask

- Use [GitHub Discussions](https://github.com/edwardgushchin/codex-worklog/discussions) for setup questions, workflow ideas, and general help.
- Use the [bug report form](https://github.com/edwardgushchin/codex-worklog/issues/new?template=bug_report.yml) for reproducible defects.
- Use the [feature request form](https://github.com/edwardgushchin/codex-worklog/issues/new?template=feature_request.yml) for proposals.
- Use [private security reporting](https://github.com/edwardgushchin/codex-worklog/security/advisories/new) for vulnerabilities.

Before requesting help, collect a redacted diagnostic set:

- Codex version and host surface;
- plugin version;
- operating system and Python version;
- hook event that failed;
- whether `PLUGIN_ROOT` and `PLUGIN_DATA` were available, without exposing unrelated environment values;
- the exact error message with private paths and secrets removed.

Do not publish worklog contents, transcripts, tokens, credentials, private keys, or private repository data unless the minimum relevant excerpt is safe to share.
