# ATAK Integration

skcot speaks standard TAK protocol. There is no side-loaded app, no custom client, and no vendor relay in the loop: ATAK, iTAK, and WinTAK connect to a skcot endpoint the same way they would connect to any other TAK server, using the built-in import and connect flow those apps already ship with.

## Enrollment: one import, one connection

Enrollment is a single data package, built and imported once per device.

1. **skcot.pki builds the package.** Running `python -m skcot.pki package <device> --host $TAK_HOST --port 8089` mints a per-device client certificate, signs it against skcot's own certificate authority, and bundles it with the server's certificate and a connect string into a single `.zip` data package.
2. **The operator imports it once.** In ATAK: hamburger menu, Import, Local SD (or share-to-ATAK from the phone's file picker), then select the `.zip`. ATAK reads the manifest, installs the certificates, and adds the server entry automatically. No manual certificate pinning, no typed-in server settings.
3. **The device connects over TLS.** Default port 8089. From that point on the device is enrolled: it authenticates with its own client certificate, not a shared password, and every session is TLS-encrypted end to end.

Once enrolled, the device streams CoT to the skcot endpoint over the same TLS connection. Plain CoT streaming (unauthenticated devices, testing, or trusted-network deployments) defaults to port 8087; the TLS-enrolled path defaults to port 8089. Both can run at once on the same node.

## The AI teammate as a contact

`skcot.agent` connects to the CoT endpoint as its own unit and beacons a friendly Cursor-on-Target position, CoT type `a-f-G-U-C` (friendly, ground, unit, combatant). That beacon rides the ephemeral rail described in [ARCHITECTURE.md](ARCHITECTURE.md), refreshed on an interval, so the AI teammate shows up and stays current as a contact on every enrolled device's map, the same way a human teammate's PLI would.

## Two-way: GeoChat in, GeoChat out

Traffic flows both ways over the same wire:

- **Operator to skcot**: PLIs (position location info), markers, and GeoChat messages the operator sends from ATAK flow into the skcot endpoint, get classified by `skcot.codec`, and land in `GEO_STORE` (positions and markers) or get routed to whichever handler consumes them (GeoChat).
- **skcot to operator**: `skcot.agent` reads inbound GeoChat addressed to it, routes the text through the configured LLM (with skcapstone driving the reasoning, if it is running alongside), and replies in the operator's ATAK chat window over the same connection. The reply rides as CoT type `b-t-f`, standard GeoChat, so it appears exactly like a message from any other teammate.

There is no separate channel for the AI's replies. It is the same TAK stream the operator already has open.

## Mesh: Mesh SA and TAK Protocol

ATAK's "Mesh SA" mode sends CoT over UDP multicast rather than a direct TCP/TLS connection to a server, for teams operating without infrastructure reachability. `skcot.server`'s `UdpMeshListener` handles this path. Mesh traffic can arrive as either:

- legacy CoT XML, handled by `skcot.codec` out of the box, or
- TAK Protocol protobuf, the more compact binary encoding newer ATAK builds prefer for mesh, which requires the `skcot[tak]` extra (`pip install -e "skcot[tak]"`) to pull in `takproto`.

Both paths feed the same `GEO_STORE` and the same federation logic as the TCP/TLS paths; mesh is a transport, not a separate picture.

## Nothing unusual for the operator

From the device's point of view, this is a completely standard TAK server flow: import a data package once, connect, see contacts on the map, send and receive GeoChat. skcot's sovereignty comes from what is on the other end of that wire, an endpoint, a certificate authority, and an AI teammate the operator's own team controls, not from anything unusual about the protocol.
