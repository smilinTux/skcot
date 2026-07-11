# skcot Migration Guide

## Overview
The CoT/TAK subsystem has been extracted from `skcomms` into the standalone `skcot` package. This document outlines the changes, unit renames, and deployment steps.

## Changes

### Package Migration
- **Old location**: CoT/TAK code in `skcomms.cot_service` and `skcomms.cot_agent`
- **New location**: Standalone `skcot` package with entry points `skcot.service` and `skcot.agent`

### Systemd Unit Renames
| Old Unit Name | New Unit Name |
|---|---|
| `skcomms-cot.service` | `skcot-service.service` |
| `skcomms-cot-agent@.service` | `skcot-agent@.service` |

### Entry-Point Changes
| Old Command | New Command |
|---|---|
| `python -m skcomms.cot_service` | `python -m skcot.service` |
| `python -m skcomms.cot_agent` | `python -m skcot.agent` |

### Environment Variables
**No changes** — all environment variables remain the same:
- `SKCOMMS_COT_HOST` (host for CoT streaming endpoint)
- `SKCOMMS_COT_PORT` (port for CoT endpoint)
- `SKCOMMS_COT_MESH_IFACE` (mesh interface address)
- `SKCOMMS_COT_TLS` (enable TLS)
- `SKCOMMS_COT_TLS_PORT` (TLS port)
- `SKCOMMS_COT_PEERS` (peer addresses)
- `SKCOMMS_COT_STRICT` (strict mode flag)

The skcot codebase continues to read these `SKCOMMS_COT_*` prefixed variables unchanged.

## Deployment

### Old Status
The legacy `skcomms-cot.service` and `skcomms-cot-agent@.service` units were stopped and disabled on 2026-07-11. No skcot service currently runs automatically.

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
   systemctl --user enable skcot-service
   systemctl --user start skcot-service
   ```

6. **Enable and start agent instances** (for each agent, e.g., lumina, opus)
   ```bash
   systemctl --user enable skcot-agent@lumina
   systemctl --user start skcot-agent@lumina
   ```

### Verification

Check service status:
```bash
systemctl --user status skcot-service
systemctl --user status skcot-agent@lumina
```

View logs:
```bash
journalctl --user -u skcot-service -f
journalctl --user -u 'skcot-agent@lumina' -f
```

## Dependencies

- **Python 3.8+**
- **skcot package** installed in `~/.skenv` venv
- **TAK protocol support** requires `takproto` optional dependency (installed via `[tak]` extra)

## Rollback

To revert to the old skcomms-based deployment:

1. Stop and disable new units:
   ```bash
   systemctl --user stop skcot-service skcot-agent@lumina
   systemctl --user disable skcot-service skcot-agent@lumina
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
- Both the main service (`skcot-service.service`) and agent instances (`skcot-agent@<name>.service`) must be configured with the same mesh host/port and TLS settings.
- Default agent spawn location: 41.1375N, 73.4240W (Connecticut baseline; override via `--lat`/`--lon` flags).
