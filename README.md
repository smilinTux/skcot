# skcot

**A sovereign CoT/TAK service that puts your own AI teammate on the ATAK tactical net.**

`Status:` Active · `Kind:` service (systemd, `python -m skcot.service`) · `Maturity-tier:` **T0 - Classical**
`Canonical-home:` <https://github.com/smilinTux/skcot> · `Standards:` [sk-standards](https://github.com/smilinTux/sk-standards)
`Operational source of truth:` **[SOP.md](SOP.md)**

skcot speaks Cursor-on-Target (CoT), the wire format behind ATAK, iTAK, and WinTAK, from
infrastructure you own. Enroll a device once, connect it to a skcot endpoint you control, and your
AI teammate shows up as a contact on the tactical map: it beacons a position, reads the operator's
GeoChat, and answers back over the same wire. No vendor cloud in the loop, no side-loaded app, just
standard TAK protocol talking to a server you run.

> ⚠️ **Experimental, unaudited, self-built reference implementation.** skcot runs its own X.509
> certificate authority (`src/skcot/pki.py`) and terminates TLS. No independent third-party
> security audit, fuzzing, or formal review has been performed. Its 98 tests prove behaviour and
> interop, **not** the absence of side-channel or implementation flaws. The asymmetric crypto is
> **classical RSA-2048 (maturity tier T0)**, the CA and server private keys are written to disk
> **unencrypted**, and the TLS listener is configured with `ssl.CERT_OPTIONAL`, so a client
> certificate identifies a device but does **not** gate access. Access control is the tailnet bind,
> nothing else. Read [SECURITY.md](SECURITY.md) before relying on this. Do not represent it as
> "audited", "production-hardened", or post-quantum: it is none of those.

## Why this is its own package

skcot did not start as a package. It started as a handful of modules inside `skcomms`, the sovereign
messaging fabric, because CoT is, at its core, just another message type riding the fabric. That
worked until position beacons (the constant stream of "here I am" updates every TAK client sends)
started flooding a durable mailbox designed for mail: signed, retried, and kept until read. A
position beacon that is a minute old is worthless, but the durable outbox did not know that, so it
kept retrying, kept storing, and kept growing.

The root problem was a quality-of-service mismatch. CoT position traffic is ephemeral: fire it,
supersede it, forget it. Mail is durable: sign it, retry it, deliver it, keep it. Bolting the
ephemeral traffic onto the durable rail meant every design decision had to compromise one side or
the other. So the CoT/TAK code earned its own package, its own ephemeral rail, and its own two-way
boundary against skcomms. That package is skcot.

## What skcot gives you

- **A CoT/TAK streaming endpoint** that ATAK, iTAK, and WinTAK connect to directly
  (`skcot.server`), plain TCP (`:8087`) or TLS (`:8089`), plus a UDP mesh listener for "Mesh SA"
  traffic on `239.2.3.1:6969`.
- **A situational store** (`skcot.geo`, the `GEO_STORE`) that ingests every CoT update, whether from
  a connected device or federated in from a peer node, and keeps one ground-truth picture: units,
  markers, waypoints, nearest-neighbor queries, GeoJSON export.
- **A read-only geo HTTP bridge** (`skcot.geo_http`) on `127.0.0.1:8091`, serving
  `GET /geo/units`, which is how skcomms sources live CoT telemetry
  (`skcomms/src/skcomms/geo_store.py:61`).
- **An AI teammate on the net** (`skcot.agent`): it beacons a friendly position so it appears as a
  contact on enrolled devices, and it answers operator GeoChat with a real reply, routed through
  your own LLM.
- **Standard ATAK enrollment** (`skcot.pki`): build one data-package `.zip` with the server
  certificate and connect string, import it once on the device, done.
- **A codec** (`skcot.codec`) that translates CoT XML and TAK Protocol protobuf into the shared
  skcomms Envelope, and classifies traffic into the ephemeral beacon rail versus the durable event
  rail.

## Quickstart

```bash
pip install -e "skcot[tak]"          # skcomms is the one hard dependency
python -m skcot.pki init             # create the CA + server cert
python -m skcot.pki package phone1 --host <your-tailnet-ip> --port 8089
python -m skcot.service              # bind :8087 plain, :8089 TLS, :8091 geo HTTP
```

There is **no console script**: `pyproject.toml` has no `[project.scripts]` block, so every entry
point is `python -m skcot.<module>`. Full build, deploy, rollback, and troubleshooting steps are in
**[SOP.md](SOP.md)**.

## Documentation map

| Doc | What it answers |
|---|---|
| **[SOP.md](SOP.md)** | Operational source of truth: build, test, deploy, rollback, config, API, troubleshooting, maturity tier. |
| **[SECURITY.md](SECURITY.md)** | Threat model, the honest crypto posture, how to report a vulnerability. |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Branch model, commit trailer, the test gate, review path. |
| **[CHANGELOG.md](CHANGELOG.md)** | Keep-a-Changelog history. |
| [docs/STACK.md](docs/STACK.md) | Exactly what skcot depends on, what is optional, where it sits in the SK layer stack. |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The seven modules and how the ephemeral situational rail actually works. |
| [docs/ATAK-INTEGRATION.md](docs/ATAK-INTEGRATION.md) | How ATAK, iTAK, and WinTAK connect: enrollment, streaming, two-way GeoChat, mesh. |
| [docs/STANDARDS.md](docs/STANDARDS.md) | The SK standing orders skcot is built to follow. |
| [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) | Install, enroll a device, run the endpoint, put the AI teammate on the net. |
| [docs/MIGRATION.md](docs/MIGRATION.md) | The move from the old `skcomms.cot_service` / `skcomms.cot_agent` modules and systemd units. |

## Sovereignty, in one line

The endpoint, the TLS certificate authority, the enrollment packages, and the model answering
GeoChat are all yours. Nothing in the loop is a vendor's server.

## Related projects / See also

- ⬆️ **Depends on:** [skcomms](https://github.com/smilinTux/skcomms) - the sovereign messaging
  fabric. The only hard dependency: envelopes, identity, discovery, TOFU. skcot also resolves its
  package home through `skcomms.home.skcomms_home()`, so it has no home directory of its own.
- ⬇️ **Used by:** [skcomms](https://github.com/smilinTux/skcomms) at runtime (not as an import) -
  `skcomms/src/skcomms/geo_store.py:61` reads `http://127.0.0.1:8091/geo/units` to source live CoT
  telemetry for SkMap. The code dependency arrow still points one way only: skcomms never imports
  skcot.
- ↔️ **Optional companion:** [skcapstone](https://github.com/smilinTux/skcapstone) - the agent
  framework whose reasoning and memory drive what the AI teammate says in GeoChat. skcot runs
  without it as a plain CoT/TAK bridge plus situational store.
- 📐 **Standards:** [sk-standards](https://github.com/smilinTux/sk-standards) - the doc/SOP,
  cryptography, security-disclosure, testing/CI, and version-lifecycle standards this repo is
  written to.

**License:** [GPL-3.0-or-later](LICENSE).
