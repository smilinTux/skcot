# skcot docs

The front-door README moved to the repo root so it is the first thing a reader (human or agent)
opens, per the SK_REPO_DOC_STANDARD "README is the hub" rule. It is not duplicated here.

- **Start at [../README.md](../README.md)** for what skcot is, the quickstart, and the map of every
  other doc.
- **[../SOP.md](../SOP.md)** is the operational source of truth: build, test, deploy, rollback,
  configuration, API, troubleshooting.
- **[../SECURITY.md](../SECURITY.md)** carries the threat model and the honest crypto posture.

This directory holds the long-form background docs:

| Doc | What it answers |
|---|---|
| [STACK.md](STACK.md) | What skcot depends on, what is optional, where it sits in the SK layer stack. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The seven modules, and the ephemeral situational rail that justifies the package split. |
| [ATAK-INTEGRATION.md](ATAK-INTEGRATION.md) | How ATAK, iTAK, and WinTAK enroll, connect, and chat. |
| [STANDARDS.md](STANDARDS.md) | The SK standing orders skcot is built to follow. |
| [GETTING-STARTED.md](GETTING-STARTED.md) | Install, enroll a device, run the endpoint, put the AI teammate on the net. |
| [MIGRATION.md](MIGRATION.md) | The move off the old `skcomms.cot_service` / `skcomms.cot_agent` modules and unit names. |
