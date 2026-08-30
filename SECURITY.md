# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| Latest `0.1.x` | Yes |
| Older versions | No |

Security fixes are released on the latest supported line. There is no promise of backports before the project reaches `1.0.0`.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability.

Preferred reporting channel:

1. Open a [private GitHub security advisory](https://github.com/edwardgushchin/codex-worklog/security/advisories/new).
2. If private reporting is unavailable, email **eduardgushchin[at]yandex.ru** with the subject `Codex Worklog security report`.

Include:

- the affected version or commit;
- operating system and Codex host;
- impact and realistic attack scenario;
- minimal reproduction steps;
- any proposed mitigation;
- whether the issue is already public.

Do not include live credentials, private keys, production transcripts, or another person's private worklog. Use synthetic data.

The maintainer will acknowledge a complete report when practical, investigate it, coordinate a fix and disclosure timeline, and credit reporters who want attribution. Response times are best effort because this is a volunteer project.

## Security Boundaries

Security-sensitive areas include:

- command construction in `hooks/hooks.json`;
- path traversal and symbolic-link handling;
- writes outside the session `cwd` or Codex `PLUGIN_DATA`;
- accidental prompt, transcript, tool-output, credential, or personal-data persistence;
- unbounded `Stop` continuation loops;
- unsafe permissions or marketplace packaging;
- dependencies or network behavior added to the hook runtime.

Codex Worklog is not a tamper-proof audit facility. A user, agent, administrator, or local process with sufficient filesystem access can modify or delete entries. Hooks can be disabled, and not every hosted tool path is observable by local hooks.

See [Threat Model](docs/THREAT_MODEL.md) for assumptions and mitigations.
