# Security Policy

Finlume handles sensitive financial information, so we take security reports
seriously and appreciate responsible disclosure.

## Supported versions

Finlume has not published a release yet. Until version 1.0, security fixes are
made on the `main` branch only.

## Reporting a vulnerability

**Do not open a public issue, discussion or pull request for a vulnerability.**

Report it privately through GitHub's
[private vulnerability reporting](https://github.com/Kiritiaajd/Finlume/security/advisories/new)
("Report a vulnerability" under the repository's **Security** tab).

Please include:

- a description of the issue and its impact;
- steps to reproduce or a proof of concept, using **fictional data only**;
- affected commit, configuration and environment;
- any suggested fix.

We aim to acknowledge reports within 5 working days and to agree a
disclosure timeline with you. Credit is given in the advisory unless you
prefer to stay anonymous.

## Scope

In scope: the code in this repository and its default configuration.

Out of scope: vulnerabilities in third-party dependencies with no
Finlume-specific impact (report those upstream), findings that require a
compromised host, and the configuration of individual self-hosted
deployments.

## For operators

Self-hosters are responsible for TLS, database and backup encryption, and
secret management. See
[docs/architecture/SECURITY_AND_PRIVACY.md](docs/architecture/SECURITY_AND_PRIVACY.md).
Run `python manage.py check --deploy` with production settings before going
live.
