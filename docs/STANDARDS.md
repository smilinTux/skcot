# SK Standards and Standing Orders

skcot is built to a small set of SK operating standards. These are not aspirational; they are the standing orders that shaped the module boundaries described in [ARCHITECTURE.md](ARCHITECTURE.md) and the dependency rules in [STACK.md](STACK.md). Sovereignty here is treated as something built into the code, not a policy statement layered on top of it.

## SK-SOV-01: Your keys, your ground

The endpoint, the TLS certificate authority, the enrollment authority that mints device certificates, and the model answering GeoChat are all on infrastructure the operator controls. Nothing in the ATAK connection path transits a vendor server, a vendor identity provider, or a vendor-hosted model. When `skcot.pki` builds an enrollment package, the certificate chain it hands the device roots at a CA the operator generated; when `skcot.agent` answers a GeoChat message, the LLM behind that answer is one the operator is running. Sovereignty is a construction property of the deployment, not a checkbox in a settings screen.

## SK-QOS-02: Ephemeral is not durable

Situational beacons, CoT atoms (`a-*`), ride a fire-and-forget rail with a short TTL derived from the beacon's own stale time, supersede-only semantics, and no acknowledgement. Discrete events, CoT bits (`b-*`) such as GeoChat, markers, and files, ride reliable mail: signed, retried, delivered, kept until read. Mixing these two disciplines, sending a position beacon down a durable-mail path or trying to make a GeoChat message disposable, is a defect, not an acceptable tradeoff. skcot exists as its own package specifically because that mismatch was found in production and the fix was a second transport, not a compromise on either rail. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full mechanism.

## SK-SEC-03: Signed and enrolled

Every device joins the net via a TLS data package: a per-device client certificate minted against skcot's own CA, imported once, never a shared password. Every envelope that federates across the skcomms fabric is signed and verified on receipt. Capability is advertised, not assumed: a node tells its peers it can consume CoT before beacon traffic is routed to it, so ephemeral position data only ever reaches peers that have the code to interpret it, never a plain-mail node that would otherwise have to store and ignore it.

## SK-ARCH-04: A leaf, not a tangle

skcot depends on the fabric; the fabric never depends on skcot. This is a one-way, testable boundary: skcomms has no import of and no awareness of anything in skcot, and that can be verified directly by searching the skcomms tree for any reference back to skcot, which should come back empty. Keeping the dependency arrow pointing one direction is what lets skcomms remain a general-purpose fabric usable by any package, and lets skcot own everything CoT-specific, from beacon TTLs to the situational store's schema, without either package's internals leaking into the other.
