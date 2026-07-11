# Architecture

skcot is seven modules. Six of them do one job each; the seventh (`skcot.service`) ties them together into a running daemon. This doc walks through each module's job, then spends the rest of its length on the design decision that justifies skcot existing as its own package: the ephemeral situational rail.

## The seven modules

### skcot.codec

Translates between wire formats and the shared skcomms `Envelope`. Two directions:

- **CoT XML <-> Envelope**: `parse_cot` reads a CoT `<event>` element into a `CotEvent` model; `to_cot` serializes it back out, preserving full detail-subtree fidelity where possible; `cot_to_envelope` / `envelope_to_cot` wrap and unwrap the CoT payload inside a signed skcomms Envelope for fabric transport.
- **TAK Protocol protobuf <-> Envelope**: the mesh path (with the `[tak]` extra installed) speaks the binary TAK Protocol format ATAK's Mesh SA uses, alongside the legacy XML path.

The module also carries `is_ephemeral_beacon`, the classifier that decides whether a given CoT event is a position beacon (type `a-*`, fire-and-forget) or a durable event (type `b-*`, reliable delivery). Every other module's routing decisions trace back to this one function.

### skcot.server

The TCP/TLS/mesh CoT streaming endpoint. `CotStreamServer` binds plain TCP (default `:8087`) and accepts connections from ATAK, iTAK, and WinTAK clients; `TlsCotStreamServer` extends it with the TLS-enrolled path (default `:8089`) so devices connect with per-device client certificates. `UdpMeshListener` handles the multicast "Mesh SA" UDP path. `federation_ingest` is the bridge outward: it takes CoT received from a connected device and pushes it onto the skcomms fabric so peer nodes see it too, applying the ephemeral/durable split from `skcot.codec` on the way out.

### skcot.agent

Puts the AI on the net as a friendly contact. It connects to the CoT endpoint as a unit, beacons its own position on an interval, and reads inbound GeoChat addressed to it, routing each message through the configured LLM and replying in the operator's ATAK chat window. Identity (callsign, enrollment package) is name-agnostic, derived from the `SKAGENT` environment variable, so multiple agents (lumina, opus, jarvis) can each run their own agent process against the same shared CoT service.

### skcot.geo

The situational store, `GEO_STORE`. Every CoT update this node sees, whether from a directly connected device or federated in from a peer, gets upserted here by entity `uid` (supersede, not append). It classifies incoming CoT types into units, markers, or waypoints, and supports nearest-neighbor lookups, situational summaries, and GeoJSON export, so the current picture is queryable without re-parsing the CoT stream.

### skcot.pki

ATAK data-package enrollment and TLS. Builds and signs the certificate authority and per-device client certificates, and packages a device's certificate, the server's connect string, and ATAK preference XML into a single `.zip` data package the operator imports once. Also underlies the TLS-enrolled streaming server in `skcot.server`.

### skcot.service

The daemon that ties it together. `python -m skcot.service` starts the streaming server (plain and TLS), binds the mesh listener, wires inbound CoT into `GEO_STORE` and outbound federation, and advertises CoT capability on the fabric so peers know this node can receive beacon traffic.

### skcot.client

A CoT client, useful for testing the server and for any process that needs to connect to a skcot endpoint as a CoT peer rather than run one.

## The ephemeral situational rail

This is the design decision that made skcot its own package rather than three modules living inside skcomms.

### The problem: two kinds of CoT traffic

CoT traffic on a tactical net splits cleanly into two categories, and TAK's own type namespace already marks the split:

- **Atoms (`a-*`)**: position reports. Friendly and hostile unit locations, sensor tracks, the AI teammate's own beacon. A TAK client re-sends these constantly, often every few seconds, and each one carries a `stale` time after which the position is no longer trustworthy: typically minutes, not hours.
- **Bits (`b-*`)**: discrete events. GeoChat messages, dropped markers, shared files. Each one is a thing that happened once and needs to be delivered, not superseded by the next one.

A position beacon that is two minutes old is not "pending delivery," it is wrong. There is no value in retrying it, no value in storing it, and no value in acknowledging it, because a fresher beacon for the same entity is already on its way. A GeoChat message is the opposite: it is a specific thing someone said, and it needs to arrive exactly once, reliably, or the operator loses the message.

### The fix: two rails

skcot routes these two categories onto two different transport disciplines:

**The ephemeral rail (atoms, `a-*`)**:
- Short TTL, derived directly from the CoT event's own `stale` time (clamped to a sane maximum) rather than the fabric's long durable default. A beacon that says "I'm stale in 90 seconds" gets a wire TTL of about 90 seconds, not a day.
- Supersede-only per entity `uid`. A new beacon for the same unit replaces the old one; nothing accumulates.
- No acknowledgement requested. Fire-and-forget: if a peer is offline, the beacon has already expired by the time it would matter, so there is nothing to retry.
- Gated to CoT-capable peers only. The fabric advertises capability, and beacon traffic is only sent to nodes that have advertised they consume CoT, so a plain-mail peer never sees position spam it has no code to interpret.
- On the receiving end, the beacon is consumed straight into `GEO_STORE`. It never touches a durable inbox file. There is no message sitting on disk waiting to be read; the moment it lands, it either updates the picture or, if a fresher one has already arrived, gets discarded.

**The durable rail (bits, `b-*`)**:
- GeoChat, markers, and files ride the same reliable mail path as everything else on the skcomms fabric: signed, retried until delivered, and kept until the recipient has actually read them.

### Why this had to be its own package

Before this split existed, all CoT traffic, beacons included, rode the durable mail path, because that was the only path skcomms had. The result was exactly what you would expect: a mailbox meant to hold "things you have not read yet" filled up with tens of thousands of position updates that were already stale by the time anyone looked, because nothing about the durable path knew a beacon was disposable.

That is a quality-of-service mismatch, not a bug in either side. skcomms is correct to treat mail as durable. CoT atoms are correct to be disposable. The fix is not a patch to skcomms's retry logic; it is a second transport discipline that only makes sense in the context of CoT, with its own TTL derivation, its own supersede semantics, and its own capability gating. Building that as a bolt-on inside skcomms would have meant every future skcomms feature carried CoT-shaped baggage. Building it as its own package means skcomms stays a general-purpose fabric, and skcot owns the situational rail end to end.

## Leaf design

skcot consumes skcomms; skcomms never imports skcot. Every module above (`codec`, `server`, `agent`, `geo`, `pki`, `service`, `client`) reaches down into `skcomms.core`, `skcomms.envelope`, `skcomms.identity`, and the rest of the module list in [STACK.md](STACK.md), and nothing in skcomms reaches back up. That one-way boundary is what lets skcot own an entirely CoT-specific transport discipline (the ephemeral rail above) without asking the general-purpose fabric to know anything about tactical position beacons at all.
