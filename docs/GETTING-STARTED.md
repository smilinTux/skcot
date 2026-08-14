# Getting Started

This walks through installing skcot, enrolling a device, starting the endpoint, and putting an AI teammate on the net. All host and coordinate values below are placeholders: substitute your own deployment values wherever you see `$TAK_HOST`, `$LAT`, or `$LON`. `$TAK_HOST` must be the tailnet IP of the node running the service.

> This is the narrative walkthrough. **[../SOP.md](../SOP.md) is the operational source of truth** for deploy, rollback, the full environment-variable table, the API surface, and troubleshooting. Where the two disagree, the SOP is right.

## Install

skcot installs alongside skcomms, which is required, and optionally alongside skcapstone, the AI brain that gives the teammate its reasoning and memory. Install with the `[tak]` extra if you need the TAK Protocol protobuf mesh path (recommended for current ATAK builds):

```bash
pip install -e "skcot[tak]"
```

This pulls in `skcomms` (the one hard dependency) and `takproto` (the optional protobuf codec). If you already have `skcapstone` installed and running in the same environment, skcot's agent will pick up its reasoning and memory automatically; if not, skcot still runs as a standalone CoT/TAK bridge and situational store. See [STACK.md](STACK.md) for the full dependency picture.

## Enroll a device

Build a data package for the device, pointing at your own TAK host and TLS port:

```bash
python -m skcot.pki package <device-name> --host $TAK_HOST --port 8089
```

This mints a per-device client certificate, signs it against skcot's certificate authority, and writes a `.zip` data package containing the certificate, the server's connect string, and ATAK preference XML.

Transfer that `.zip` to the phone and import it once in ATAK: hamburger menu, Import, Local SD (or share-to-ATAK), select the file. ATAK installs the certificates and adds the server automatically. See [ATAK-INTEGRATION.md](ATAK-INTEGRATION.md) for the full enrollment and connection flow.

## Start the endpoint

```bash
python -m skcot.service
```

This binds the CoT streaming server (plain TCP on `:8087`, TLS on `:8089`), starts the mesh UDP listener, wires inbound CoT into `GEO_STORE`, and federates traffic to any peer nodes on the skcomms fabric. Leave this running; it is the endpoint enrolled devices connect to.

## Put the AI teammate on the net

```bash
python -m skcot.agent <name> --host $TAK_HOST --lat $LAT --lon $LON --interval 20
```

This connects to the endpoint as a unit, beacons a friendly position (CoT type `a-f-G-U-C`) every `--interval` seconds so the teammate appears as a live contact on every enrolled device, and listens for inbound GeoChat addressed to it, replying through the configured LLM. `<name>` is name-agnostic: it follows the `SKAGENT` environment variable when set, so multiple agents (lumina, opus, jarvis) can each run their own agent process against the same shared endpoint.

## Running it as a service

Systemd units for both pieces ship in the repo (`systemd/skcot.service` and `systemd/skcot-agent@.service`), so you don't have to run either command by hand in a terminal session.

**Both units ship deliberate `REPLACE_ME_...` placeholders and will not start until you supply real values.** That is intentional: leaving `SKCOMMS_COT_HOST` unset makes the service fall back to `0.0.0.0` and bind a tactical endpoint on every interface, so it fails closed instead. Put your values in `~/.config/skcot/skcot.env`, which the unit reads after its own defaults:

```bash
cp skcot/systemd/*.service ~/.config/systemd/user/
mkdir -p ~/.config/skcot
cat > ~/.config/skcot/skcot.env <<'EOF'
SKCOMMS_COT_HOST=<this node's tailnet IP>
SKCOMMS_COT_MESH_IFACE=<this node's tailnet IP>
SKCOMMS_COT_SNI_NAME=<this node's MagicDNS name>
EOF
systemctl --user daemon-reload
systemctl --user enable --now skcot
systemctl --user enable --now skcot-agent@<name>
```

The service unit is named `skcot.service`, not `skcot-service.service`; see [MIGRATION.md](MIGRATION.md) for the rename history. Note that no `skcot-agent@` instance is deployed anywhere today, so that last line is an untested path.

If you are migrating from the older `skcomms.cot_service` / `skcomms.cot_agent` modules and their `skcomms-cot*` unit names, see [MIGRATION.md](MIGRATION.md) for the full unit-rename table, environment variable notes, and rollback steps.

## What you should see

Once the service is running and a device is enrolled and connected, the device shows the AI teammate's callsign as a contact on the map, updating on the beacon interval. Sending it a GeoChat message from ATAK gets a reply back in the same chat window within a few seconds, and any position, marker, or GeoChat traffic the device sends is visible in `GEO_STORE`'s situational picture, ready for a nearest-neighbor query or a GeoJSON export.
