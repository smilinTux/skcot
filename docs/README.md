# skcot

**A sovereign CoT/TAK package that puts your own AI teammate on the ATAK tactical net.**

skcot speaks Cursor-on-Target (CoT), the wire format behind ATAK, iTAK, and WinTAK, from infrastructure you own. Enroll a device once, connect it to a skcot endpoint you control, and your AI teammate shows up as a contact on the tactical map: it beacons a position, reads the operator's GeoChat, and answers back over the same wire. No vendor cloud in the loop, no side-loaded app, just standard TAK protocol talking to a server you run.

## Why this is its own package

skcot did not start as a package. It started as a handful of modules inside `skcomms`, the sovereign messaging fabric, because CoT is, at its core, just another message type riding the fabric. That worked until position beacons (the constant stream of "here I am" updates every TAK client sends) started flooding a durable mailbox designed for mail: signed, retried, and kept until read. A position beacon that is a minute old is worthless, but the durable outbox did not know that, so it kept retrying, kept storing, and kept growing.

The root problem was a quality-of-service mismatch. CoT position traffic is ephemeral: fire it, supersede it, forget it. Mail is durable: sign it, retry it, deliver it, keep it. Bolting the ephemeral traffic onto the durable rail meant every design decision had to compromise one side or the other. So the CoT/TAK code earned its own package, its own ephemeral rail, and its own two-way boundary against skcomms. That package is skcot.

## What skcot gives you

- **A CoT/TAK streaming endpoint** that ATAK, iTAK, and WinTAK connect to directly (`skcot.server`), plain TCP or TLS, plus a UDP mesh listener for "Mesh SA" traffic.
- **A situational store** (`skcot.geo`, the `GEO_STORE`) that ingests every CoT update, whether from a connected device or federated in from a peer node, and keeps one ground-truth picture: units, markers, waypoints, nearest-neighbor queries, GeoJSON export.
- **An AI teammate on the net** (`skcot.agent`): it beacons a friendly position so it appears as a contact on enrolled devices, and it answers operator GeoChat with a real reply, routed through your own LLM.
- **Standard ATAK enrollment** (`skcot.pki`): build one data-package `.zip` with the server certificate and connect string, import it once on the device, done.
- **A codec** (`skcot.codec`) that translates CoT XML and TAK Protocol protobuf into the shared skcomms Envelope, and classifies traffic into the ephemeral beacon rail versus the durable event rail.

## Where to go next

- **[STACK.md](STACK.md)**, the dependency doc: exactly what skcot depends on, what is optional, and where it sits in the SK layer stack.
- **[ARCHITECTURE.md](ARCHITECTURE.md)**, the seven modules and how the ephemeral situational rail actually works.
- **[ATAK-INTEGRATION.md](ATAK-INTEGRATION.md)**, how ATAK, iTAK, and WinTAK connect: enrollment, streaming, two-way GeoChat, mesh.
- **[STANDARDS.md](STANDARDS.md)**, the SK standing orders skcot is built to follow.
- **[GETTING-STARTED.md](GETTING-STARTED.md)**, install, enroll a device, run the endpoint, put the AI teammate on the net.
- **[MIGRATION.md](MIGRATION.md)**, the move from the old `skcomms.cot_service` / `skcomms.cot_agent` modules and systemd units to the standalone package.

## Sovereignty, in one line

The endpoint, the TLS certificate authority, the enrollment packages, and the model answering GeoChat are all yours. Nothing in the loop is a vendor's server.
