# skcot Migration Guide

## Overview
The CoT/TAK subsystem has been extracted from `skcomms` into the standalone `skcot` package. This document outlines the changes, unit renames, and deployment steps.

## Changes

### Package Migration
- **Old location**: CoT/TAK code in `skcomms.cot_service` and `skcomms.cot_agent`
- **New location**: Standalone `skcot` package with entry points `skcot.service` and `skcot.agent`

### Systemd Unit Renames
| Original (in skcomms) | Interim (shipped, never deployed) | Current, since 2026-08-14 |
|---|---|---|
| `skcomms-cot.service` | `skcot-service.service` | **`skcot.service`** |
| `skcomms-cot-agent@.service` | `skcot-agent@.service` | `skcot-agent@.service` (unchanged) |

The interim column is a defect, not a step anyone took on purpose. The repo shipped
`systemd/skcot-service.service` while the unit actually installed and running on the reference node
was always named `skcot.service`. The shipped file was renamed to match reality on 2026-08-14. If
you are on a node carrying a unit called `skcot-service.service`, it predates that rename; stop and
disable it, then install `systemd/skcot.service`.

### Entry-Point Changes
| Old Command | New Command |
|---|---|
| `python -m skcomms.cot_service` | `python -m skcot.service` |
| `python -m skcomms.cot_agent` | `python -m skcot.agent` |

### Environment Variables
**No changes**: all environment variables remain the same.
- `SKCOMMS_COT_HOST` (host for CoT streaming endpoint)
- `SKCOMMS_COT_PORT` (port for CoT endpoint)
- `SKCOMMS_COT_MESH_IFACE` (mesh interface address)
- `SKCOMMS_COT_TLS` (enable TLS)
- `SKCOMMS_COT_TLS_PORT` (TLS port)
- `SKCOMMS_COT_PEERS` (peer addresses)
- `SKCOMMS_COT_STRICT` (strict mode flag)

The skcot codebase continues to read these `SKCOMMS_COT_*` prefixed variables unchanged.

## Deployment

### Current status (verified 2026-08-14)
The legacy `skcomms-cot.service` and `skcomms-cot-agent@.service` units were stopped and disabled on
2026-07-11.

- **`skcot.service` is enabled and running** on the reference node (noroc2027), listening on
  `100.108.59.57:8087` plain, `100.108.59.57:8089` TLS, and `127.0.0.1:8091` geo HTTP. The earlier
  claim in this document that "no skcot service currently runs automatically" was stale and has
  been removed.
- **No `skcot-agent@` instance is installed anywhere.**
  `systemctl --user is-enabled skcot-agent@lumina` returns `not-found`. The agent template ships and
  the `python -m skcot.agent` CLI exists, but that path has never been proven in deployment.

Deploy and rollback steps live in **[../SOP.md](../SOP.md) section 5**, which is the operational
source of truth. The steps below are kept because they describe the one-time migration off skcomms.

### Installation Steps

1. **Install skcot into ~/.skenv**
   ```bash
   pip install -e ~/clawd/skcapstone-repos/skcot
   ```

2. **Install with TAK protocol support (protobuf mesh)**
   ```bash
   pip install -e '~/clawd/skcapstone-repos/skcot[tak]'
   ```

3. **Copy systemd units to user systemd directory**
   ```bash
   cp ~/clawd/skcapstone-repos/skcot/systemd/*.service ~/.config/systemd/user/
   ```

4. **Reload systemd daemon**
   ```bash
   systemctl --user daemon-reload
   ```

5. **Enable and start the main service**
   ```bash
   systemctl --user enable skcot
   systemctl --user start skcot
   ```

6. **Enable and start agent instances** (for each agent, e.g., lumina, opus)
   ```bash
   systemctl --user enable skcot-agent@lumina
   systemctl --user start skcot-agent@lumina
   ```

### Verification

Check service status:
```bash
systemctl --user status skcot
systemctl --user status skcot-agent@lumina
```

View logs:
```bash
journalctl --user -u skcot -f
journalctl --user -u 'skcot-agent@lumina' -f
```

## Dependencies

- **Python 3.10+** (`pyproject.toml` sets `requires-python = ">=3.10"`; the earlier "3.8+" here contradicted it. CI tests 3.10 and 3.12.)
- **skcot package** installed in `~/.skenv` venv
- **TAK protocol support** requires `takproto` optional dependency (installed via `[tak]` extra)

## Rollback

To revert to the old skcomms-based deployment:

1. Stop and disable new units:
   ```bash
   systemctl --user stop skcot skcot-agent@lumina
   systemctl --user disable skcot skcot-agent@lumina
   ```

2. Re-enable and start legacy units (if they exist):
   ```bash
   systemctl --user enable skcomms-cot.service skcomms-cot-agent@lumina
   systemctl --user start skcomms-cot.service skcomms-cot-agent@lumina
   ```

3. Uninstall skcot:
   ```bash
   pip uninstall skcot
   ```

## Notes

- The skcot package maintains backward compatibility with all existing `SKCOMMS_COT_*` environment variables.
- Both the main service (`skcot.service`) and agent instances (`skcot-agent@<name>.service`) must be configured with the same mesh host/port and TLS settings.
- Agent spawn location is operator-supplied via `--lat`/`--lon` flags (e.g. `40.0000N, 74.0000W` as a placeholder base, set these to your own deployment coordinates).
