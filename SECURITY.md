# Security Policy - skcot

`skcot` is the sovereign **CoT/TAK service**: it terminates TLS for tactical clients, runs its own
X.509 certificate authority, mints per-device client certificates, and packages them into ATAK
enrollment `.zip` files. It generates and stores key material, so it is a **crypto component** under
the [SECURITY_DISCLOSURE_STANDARD](https://github.com/smilinTux/sk-standards/blob/main/standards/SECURITY_DISCLOSURE_STANDARD.md)
and carries the honest-claim rules in full. Read the posture and the threat model before relying on
it or reporting an issue.

> ⚠️ **Experimental, pre-1.0, NOT independently security-audited.** No third-party security audit,
> fuzzing, or formal review has been performed on skcot. It binds the vetted `cryptography` library
> rather than hand-rolling primitives, but the original code is the CA construction, the certificate
> issuance and packaging, the TLS context and SNI wiring, and the ephemeral/durable routing split.
> A passing test suite (98 tests, section "Evidence" below) proves interop and behaviour, **not** the
> absence of side channels, misuse hazards, or protocol flaws. **Review it yourself before
> production use.** Do not represent skcot as "audited", "production-hardened", or post-quantum.

**Maturity tier: T0 - Classical.** Tier is posture, not assurance. A T0 component is unaudited *and*
entirely classical.

---

## Honest claims (what skcot does and does NOT promise)

Per the sk-standards
[CRYPTOGRAPHY_STANDARD](https://github.com/smilinTux/sk-standards/blob/main/standards/CRYPTOGRAPHY_STANDARD.md),
every claim below is scoped to a **surface** and carries its **evidence**.

### What it does do

- ✅ **TLS transport confidentiality on the `:8089` CoT stream, classical.** `TlsCotStreamServer`
  (`src/skcot/server.py:284`) builds a `ssl.PROTOCOL_TLS_SERVER` context and loads a server chain.
  The cipher suites and version floor are whatever the host Python and OpenSSL negotiate; skcot
  does not pin them.
- ✅ **Per-device identity attribution.** A client presenting a certificate signed by the skcot CA
  is attributed by identity and fingerprint into the situational store (`service.py:264-276`,
  `_ident_hook`). Each device gets its own certificate, never a shared password.
- ✅ **The CA is never silently regenerated.** `init_ca()` (`pki.py:151`) loads an existing
  `ca.pem`/`ca.key` and returns it unchanged. This is deliberate: the CA is pinned in every enrolled
  device's truststore, so regenerating it would un-enroll the fleet.
- ✅ **No public network surface.** All three listeners bind tailnet or loopback only
  (`100.108.59.57:8087`, `100.108.59.57:8089`, `127.0.0.1:8091`, confirmed via `ss` 2026-08-14).
  There is no Funnel route, no Caddy vhost, and no `:443` path. See [SOP.md](SOP.md) section 5.
- ✅ **Ephemeral beacons never become durable state.** A CoT atom lands in the in-memory
  `GEO_STORE` and is never written to a mailbox file (`tests/test_beacon_no_durable_persist.py`).
  This bounds what an attacker with disk access can recover from position history.

### What it does NOT do (read these as findings, not caveats)

- ❌ **Nothing here is post-quantum.** The asymmetric crypto is **classical RSA-2048**:
  `pki.py:94` `_gen_key()` is
  `rsa.generate_private_key(public_exponent=65537, key_size=2048)`, and the CA, the server
  certificate, and every device certificate use it, signed `sha256WithRSAEncryption`. There is no
  hybrid KEM, no ML-KEM (FIPS 203), no ML-DSA (FIPS 204), no suite negotiation, and no
  crypto-agility layer. **Maturity tier T0.** Any traffic on this surface is Harvest-Now-
  Decrypt-Later exposed, and any signature on this surface is classically forgeable by a future
  cryptographically-relevant quantum computer.
- ❌ **Private keys are written to disk UNENCRYPTED.** `_write_key()` (`pki.py:98-110`) serializes
  with `encryption_algorithm=serialization.NoEncryption()`, and `_load_key()` (`pki.py:117`) reads
  with `password=None`. This covers `ca.key`, `server.key`, and every device key under
  `~/.skcapstone/skcomms/cot-pki/`. They are `chmod 0600`, and that is the **only** protection:
  no passphrase, no KMS, no HSM, no vault. **Anyone who can read the file owns the certificate
  authority for the entire tactical net.** Filesystem permissions and disk encryption are the
  operator's responsibility.
- ❌ **A client certificate does not gate access.** `TlsCotStreamServer.__init__` takes
  `require_client_cert: bool = False` (`server.py:289`), and `service.py` never passes `True`, so
  the live listener runs `ssl.CERT_OPTIONAL` (`server.py:322-325`). A client with **no certificate
  at all** completes the TLS handshake and joins the CoT stream. Enrollment provides
  **attribution**, not **admission**. The only access control on the tactical net is the tailnet
  bind.
- ❌ **The `:8087` plain TCP listener has no transport security whatsoever.** No TLS, no
  authentication. It is unencrypted CoT on the tailnet by design, for testing and trusted-network
  use. Anything that reaches that port can read and inject position and GeoChat traffic.
- ❌ **The geo HTTP bridge on `127.0.0.1:8091` is unauthenticated.** It is GET-only and read-only,
  but any local process or local user can read the full situational picture, including every unit's
  position. Its only control is the loopback bind.
- ❌ **Certificate lifetimes are 10 years and there is no revocation.** `_VALIDITY_DAYS = 3650`
  (`pki.py:68`). skcot publishes no CRL and implements no OCSP. **A lost or stolen device
  certificate cannot be revoked.** The only remedy is regenerating the CA, which re-enrolls
  everything.
- ❌ **skcot does not renew the publicly-trusted SNI certificate.** The `tailscale cert` pair used
  for the SNI leg (see [SOP.md](SOP.md) section 6) is site-supplied and site-renewed. On the
  reference node it expired 2026-07-26 and nothing alerted. There is no expiry monitoring in skcot.
- ❌ **skcot is not the identity root of trust.** Agent identity, FQIDs, and envelope signing keys
  come from [skcomms](https://github.com/smilinTux/skcomms) and
  [capauth](https://github.com/smilinTux/capauth). skcot consumes them.
- ❌ **Never** "quantum-proof", "quantum-safe", "unbreakable", "CNSA 2.0 compliant", "FIPS 206", or
  "Falcon". skcot is classical; there is no post-quantum claim to scope. Note that AES-256 and
  SHA-256 are **not** broken by quantum (Grover only halves symmetric strength); do not "fix" them.

### CRYPTOGRAPHY_STANDARD compliance statement

**skcot does not currently meet the CRYPTOGRAPHY_STANDARD's requirements for a new crypto
component.** It has no suite-ids on its containers, no suite registry, no backend ABC, no
negotiation surface, and no self-report or `doctor` command with which to evidence a claim. It sits
at **T0** and has not begun the T1 (agility) work. Whether RSA-2048 specifically clears the
standard's floor for an internal X.509 device-enrollment PKI is **not determinable from the
standard's text**, which specifies KEM and signature targets but sets no minimum RSA modulus and
does not scope X.509 PKI. That question is recorded as open in [SOP.md](SOP.md) "Unverified", and no
compliance is asserted here in either direction.

---

## Threat model

### In scope

- **Theft or disclosure of `cot-pki/ca.key`.** Full compromise: the holder can mint a certificate
  for any device and impersonate any enrolled unit. Unencrypted on disk, `0600` only.
- **Unauthenticated join of the TLS stream.** `ssl.CERT_OPTIONAL` means a certless client reaches
  the CoT stream. Anything that can route to the tailnet IP on `:8089` can read and inject.
- **Injection or spoofing of CoT on the plain `:8087` listener or the UDP mesh group.** Neither has
  any authentication. A spoofed `a-*` beacon writes a false position into `GEO_STORE`
  (supersede-by-`uid`, so a spoofer who guesses a real `uid` can move a real unit on the map).
- **Local disclosure of the situational picture** via `127.0.0.1:8091`.
- **A CoT payload that crashes or hangs a parser** (`codec.py` XML and protobuf paths), including
  XML entity-expansion and oversized-frame handling on the streaming split.
- **Path traversal or zip-slip in data-package construction** (`pki.py` `build_data_package`).
- **A misrouted beacon becoming durable state**, the defect skcot exists to prevent.
- **A false crypto label**: describing any skcot surface as post-quantum, audited, or
  access-controlled by transport is itself a defect worth reporting.

### Out of scope (you MUST handle these elsewhere)

- **Network access control.** The tailnet is the perimeter. Firewalling, device authorisation, and
  ACLs are Tailscale's and the operator's job, not skcot's.
- **Key custody and disk encryption.** skcot writes plaintext PEM at `0600`. Full-disk encryption,
  backup encryption, and host hardening are the operator's.
- **Certificate revocation and rotation.** Not implemented. Operator process.
- **Renewal of the site-supplied SNI certificate.** Operator process.
- **Harvest-Now-Decrypt-Later on any skcot surface.** Everything here is classical; this is a known,
  documented, unmitigated exposure, not a bug report.
- **Side channels in bound libraries.** RSA key generation, X.509 construction, and PKCS#12
  packaging come from `cryptography`; TLS comes from the host OpenSSL. skcot does not re-audit them.
- **Vulnerabilities in skcomms, ATAK/iTAK/WinTAK, or `takproto`.** Report those upstream; skcot will
  track and bump.
- **The LLM answering GeoChat.** Prompt injection through a GeoChat message into the agent's model
  is a real risk and is the agent operator's problem; skcot passes the text through.

### Trust roots / dependencies

| Surface | Library | Assurance basis | Posture |
|---|---|---|---|
| CA, server, and device certificates | `cryptography` | RSA-2048 (PKCS#1), SHA-256, X.509 (RFC 5280) | **classical, T0** |
| PKCS#12 device keystores | `cryptography` | RFC 7292 | classical |
| TLS on `:8089` | host Python / OpenSSL | whatever the platform negotiates, unpinned | classical |
| Publicly-trusted SNI leg | site-supplied `tailscale cert` (Let's Encrypt, ECDSA) | RFC 5280 / ACME | classical, **externally renewed** |
| Envelope signing for federation | skcomms (PGPy) | see [skcomms SECURITY.md](https://github.com/smilinTux/skcomms/blob/main/SECURITY.md) | inherited |

skcot **binds** these libraries; it does not hand-roll RSA, X.509, PKCS#12, or TLS.

---

## Evidence

Every claim above is checkable in-repo without a running service.

| Claim | Verifier |
|---|---|
| RSA-2048, classical | `grep -n 'key_size=2048' src/skcot/pki.py` |
| Private keys unencrypted at rest | `grep -n 'NoEncryption()' src/skcot/pki.py` and `grep -n 'password=None' src/skcot/pki.py` |
| TLS client cert optional, not required | `grep -n 'require_client_cert: bool = False' src/skcot/server.py` |
| 10-year certs, no revocation | `grep -n '_VALIDITY_DAYS' src/skcot/pki.py`; no CRL or OCSP code exists |
| Geo bridge is loopback and GET-only | `grep -n 'DEFAULT_HTTP_HOST' src/skcot/geo_http.py` |
| Beacons never persist durably | `python -m pytest tests/test_beacon_no_durable_persist.py -q` |
| Behaviour suite | `python -m pytest tests/ -q` -> `98 passed` (2026-08-14, Python 3.12.3) |

A passing suite is evidence of behaviour. It is **not** an audit.

---

## Supported versions

| Version | Supported |
|---|---|
| `main` (unreleased, hardcoded `0.1.0`) | ✅ the only supported line |
| anything else | ❌ does not exist |

skcot has **no git tags and is not published to PyPI**. The `0.1.0` string in `pyproject.toml` is
hardcoded and pins nothing. In practice the supported version is the tip of `origin/main`, the only
branch on the remote. Per
[VERSION_LIFECYCLE](https://github.com/smilinTux/sk-standards/blob/main/standards/VERSION_LIFECYCLE.md)
this is an **Incubating** component: best-effort, expected to break.

---

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

- **Primary:** GitHub **private vulnerability reporting** - "Report a vulnerability" on the Security
  tab of [`smilinTux/skcot`](https://github.com/smilinTux/skcot/security).
- **Secondary (out of band):** contact the maintainers (smilinTux / SKWorld) via the address on the
  GitHub org profile; encrypt sensitive reports to the maintainer's sovereign capauth / `sk_pgp` PGP
  key, whose fingerprint is published on the org profile.

Please include: the affected commit SHA, your Python version, whether `takproto` is installed,
which listener is involved (`:8087` plain, `:8089` TLS, the UDP mesh group, or `:8091` geo HTTP),
and a minimal reproduction.

**We aim to acknowledge within 72 hours** and to ship a fix or mitigation within 90 days,
coordinating a disclosure date with you.

**Safe harbour:** good-faith research conducted under coordinated disclosure will not be pursued.
Credit is given unless you ask otherwise.

### What we especially want to hear about

- A path from a CoT payload to code execution, a crash, or unbounded memory growth in `codec.py` or
  the streaming frame splitter.
- Zip-slip, path traversal, or unintended file inclusion in `build_data_package`.
- A way to read `ca.key` or a device key that does not already require the ability to read
  `0600` files as the service user.
- A way to reach any skcot listener from outside the tailnet, or to make it bind `0.0.0.0` without
  the operator intending to.
- Spoofing a `uid` such that a real unit's position is moved in `GEO_STORE` on a path that was
  supposed to be attributed.
- An ephemeral beacon that ends up as durable state on disk.
- A crypto-label overclaim anywhere in this repo: any suggestion that a classical surface is
  post-quantum, that enrollment is access control, or that skcot has been audited.

---

**License:** GPL-3.0-or-later. **Standards:** RFC 5280 (X.509); RFC 7292 (PKCS#12); RFC 5737
(documentation address ranges); ISO/IEC 29147 & 30111 (disclosure); CVSS v4.0. No FIPS 203/204/205
claim is made: skcot implements none of them.
