# Changelog

All notable changes to skcot are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning intends
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note on versions.** `pyproject.toml` hardcodes `version = "0.1.0"`, the repository has **no
> git tags**, and skcot is **not published to PyPI**. That string therefore pins nothing: the real
> deployed identity is a commit SHA on `origin/main`. Entries below are dated rather than tagged
> until the project adopts a tag-driven version. See [SOP.md](SOP.md) section 9.

## [Unreleased]

### Added
- **The full SK_REPO_DOC_STANDARD doc set.** The repo previously had **zero** root-level docs; its
  only README lived at `docs/README.md`, so every presence scan read it as undocumented. Added
  `README.md`, `SOP.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`,
  and `LICENSE`.
- **`LICENSE`: GPL-3.0-or-later.** The repository had no license at all, which left it
  all-rights-reserved by default despite being public. Per the fleet-wide decision of 2026-08-14.
- **`SOP.md`** with all nine required sections, a mermaid architecture diagram, and a
  `docs-evidence` block of 14 hermetic repo-local checks pinning the ports, the entry point, the
  unit name, the absence of a console script, the config env prefix, and the three security facts
  that `SECURITY.md` discloses (RSA-2048, unencrypted keys at rest, optional client certs).
- **`.github/workflows/ci.yml`**, running `pytest tests/` on Python 3.10 and 3.12. **Nothing had
  ever run the test suite.** The only workflow on `main` was `secret-scan.yml`, while 12 test files
  and a configured `[tool.pytest.ini_options]` sat unexecuted on every push. Verified green before
  the gate was added: `98 passed` in a clean venv.
- **`.github/workflows/docs-check.yml`**, the sk-standards docs gate at tiers 1 and 2.
- **`EnvironmentFile=-%h/.config/skcot/skcot.env`** in both shipped systemd units, read after the
  unit's own `Environment=` lines, so a site can supply real values without editing a shipped file.

### Fixed
- **The shipped systemd unit pointed at a documentation IP address.**
  `systemd/skcot-service.service` hardcoded `SKCOMMS_COT_HOST=198.51.100.10`, which is **RFC 5737
  TEST-NET-2**, a reserved range that routes nowhere. It also carried **no TLS or SNI certificate
  paths at all**, no `SKCOMMS_COT_SNI_NAME`, no `Wants=network-online.target`, and no
  `WorkingDirectory`. Anyone who deployed the repo as shipped got a service bound to a
  documentation address with TLS silently unconfigured. The address is now the unmistakable
  placeholder `REPLACE_ME_WITH_THIS_NODES_TAILNET_IP` (a placeholder rather than a real default
  because leaving the variable unset falls back to `0.0.0.0`, which would expose a tactical
  endpoint on every interface), and the four TLS/SNI cert paths, the SNI name, the network-online
  ordering, and the working directory are all present.
- **The shipped unit name never matched the deployed one.** The repo shipped
  `systemd/skcot-service.service` while the unit actually installed and running on the reference
  node is `skcot.service`. Renamed to `systemd/skcot.service`; the mapping is recorded in
  [SOP.md](SOP.md) section 5 and [docs/MIGRATION.md](docs/MIGRATION.md).
- **`systemd/skcot-agent@.service` hardcoded example coordinates and a TEST-NET-2 host** in its
  `ExecStart` and ordered itself `After=skcot-service.service`, a unit that no longer exists.
  Placeholders are now explicit, the ordering points at `skcot.service`, and the header states
  plainly that no agent instance has ever been deployed.
- **`docs/MIGRATION.md` claimed "No skcot service currently runs automatically."** That has been
  false since the service was enabled; it runs on the reference node as `skcot.service`. Corrected,
  along with the unit names and the entry-point commands in `docs/GETTING-STARTED.md`.
- **`docs/README.md` was the repo's only README**, invisible to anyone landing on the repo root.
  Promoted to `README.md` (rewritten as the hub, with the maturity tier and the unaudited posture
  statement in the header) and replaced at its old path with a short pointer, so the content lives
  in exactly one place.

### Security
- **Documented the honest crypto posture for the first time.** `SECURITY.md` now states, with a
  file:line for each: the PKI is **classical RSA-2048** (`pki.py:94`), maturity tier **T0**, with no
  post-quantum anything; **CA and device private keys are written to disk unencrypted**
  (`pki.py` `NoEncryption()`, `password=None`), protected by `chmod 0600` alone; the TLS listener
  runs **`ssl.CERT_OPTIONAL`** (`server.py:289`), so an enrollment certificate **attributes** a
  device rather than **admitting** it, and the tailnet bind is the only access control; certificates
  are valid for **10 years with no CRL and no OCSP**, so a stolen device certificate cannot be
  revoked; and the `:8087` plain listener and the `:8091` geo bridge are unauthenticated by design.
  None of this is new behaviour. It was simply never written down.
- Added the mandatory experimental/unaudited posture statement to both `README.md` and
  `SECURITY.md`, per SECURITY_DISCLOSURE_STANDARD section 2.
- Recorded that the reference node's publicly-trusted SNI certificate (`ts-cot.crt`) **expired on
  2026-07-26** and that skcot neither renews nor monitors it. Operator action, tracked in
  `SOP.md` "Unverified".

### Known gaps
- No `/health` endpoint exists. The nearest liveness probe is `GET http://127.0.0.1:8091/geo/units`.
- No self-report or `doctor` command, so skcot cannot evidence its own negotiated primitives. This
  is what keeps it below tier T1 (Agile).
- `cryptography` is imported by `pki.py` but is not a declared dependency; it resolves transitively
  today.
- `pgpy` is required to run the test suite but is declared by neither skcot nor (as installed from
  PyPI) skcomms. `ci.yml` installs it explicitly.

## History before 2026-08-14

No changelog was kept. Reconstructed headlines from the git history and
[docs/MIGRATION.md](docs/MIGRATION.md):

- **Extracted from skcomms.** The CoT/TAK subsystem moved out of `skcomms.cot_service` and
  `skcomms.cot_agent` into this standalone package, because ephemeral position beacons were being
  signed, retried, and durably stored by a mailbox built for mail. That quality-of-service mismatch,
  and the two-rail fix for it, is the reason skcot exists. See
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **Geo HTTP bridge added** (`85c15ae`): a read-only `GET /geo/units` on `127.0.0.1:8091` exposing
  the live `GEO_STORE`, which skcomms consumes at
  `skcomms/src/skcomms/geo_store.py:61`.
- **Real secret scanning** (`886c716`, PR #1): replaced the licensed gitleaks action, which exits
  before scanning a single byte on an org-owned repo, with the pinned gitleaks binary. The full
  history scanned clean on 2026-08-14.
