# Contributing to skcot

skcot terminates the tactical wire protocol and runs a certificate authority for a live tactical
net. A bad change here does not fail a test somewhere, it puts a wrong position on someone's map or
un-enrolls a fleet of devices. Read [SOP.md](SOP.md) and [SECURITY.md](SECURITY.md) before your
first change.

## Before you start

- **Read the operational truth first.** [SOP.md](SOP.md) is the source of truth for ports, unit
  names, env vars, and deploy steps. If your change moves any of those, the SOP changes in the same
  PR, and so does the `docs-evidence` block at the bottom of it.
- **Never work in a shared checkout.** `~/clawd/skcapstone-repos/skcot` is the live service's
  `WorkingDirectory` and other sessions share it. Use a worktree:
  `git worktree add ~/skworld-worktrees/<purpose>-skcot -b <branch> origin/main`.
- **Check `origin/main` and open PRs before implementing.** `git log origin/main` and
  `gh pr list` first; duplicating an open PR is the most common wasted effort in this fleet.

## Branch model

- `main` is the only branch on the remote and is protected by intent: **never push to it directly.**
- Branch from `origin/main` with a scoped prefix: `feat/...`, `fix/...`, `docs/...`, `ci/...`,
  `refactor/...`, `test/...`.
- One logical change per branch. Open a PR and leave it for review; do not self-merge a change that
  touches the PKI, the TLS context, or a listener bind address.

## Commit convention

Conventional Commits, scoped to the module you touched:

```
fix(server): install the SNI callback when only two of the three env vars are set

<body: what was wrong, why this fixes it, how you verified>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

Every commit ends with a `Co-Authored-By:` trailer naming the agent or human who wrote it.

**No em dashes or en dashes (`—` / `–`) anywhere**: not in code, comments, docs, commit messages, or
PR bodies. Use commas, parentheses, a colon, or a new sentence. Regular hyphens are fine.

## The test gate

**Every PR must be `0 failed`.** The CI gate is **96 hermetic tests**. The suite reports 98 on a host
that is already a configured SK cluster member, which is why you should check both:

```bash
python -m pytest tests/ -q
HOME=$(mktemp -d) python -m pytest tests/ -q   # what CI sees: 2 failed, 96 passed
```

`pyproject.toml` sets `pythonpath = ["src"]`, so no install is needed. In a clean environment you
also need `pgpy`, an undeclared transitive test dependency. Two tests in
`tests/test_capability_advertise.py` need a `cluster.json` that CI does not have and are deselected
by name in `ci.yml`. **Making those two hermetic is a welcome PR.** See [SOP.md](SOP.md) section 4.

CI runs three gates on every push and pull request, and none of them is `|| true`:

| Workflow | What it enforces |
|---|---|
| `ci.yml` | 96 hermetic tests on Python 3.10 and 3.12 |
| `secret-scan.yml` | `gitleaks detect` over the full history, `--exit-code 1` |
| `docs-check.yml` | sk-standards docs-check, presence and changelog tiers |

### Writing tests

- **Anything touching the ephemeral/durable split needs a test.** That distinction is the reason
  this package exists. See `tests/test_beacon_no_durable_persist.py`,
  `tests/test_cot_beacon_ephemeral_routing.py`, `tests/test_cot_beacon_outbox.py`.
- **Anything touching `pki.py` needs a test** and must not regenerate an existing CA. See
  `tests/test_cot_pki.py`.
- Tests must be hermetic: no live host, no network, no `systemctl`. Use `port=0` for an ephemeral
  bind (`geo_http.start_geo_http_server` supports it and the tests read the port back).

## Documentation gate

The docs are held to
[SK_REPO_DOC_STANDARD](https://github.com/smilinTux/sk-standards/blob/main/standards/SK_REPO_DOC_STANDARD.md).

- **State each fact once.** `README.md` is the hub, `SOP.md` is the operational truth, `docs/` holds
  the long-form background. Do not copy a port number or a path into two files; link instead.
- **If you change a documented value, update the `docs-evidence` block** at the bottom of
  `SOP.md` in the same PR, and bump its `verified:` date. Those checks are repo-local, hermetic, and
  cheap by contract: no network, no live host, no `systemctl`, no `ssh`, no `curl`.
- Verify locally before you push:
  ```bash
  python3 <path-to>/sk-standards/scripts/docs_check.py --repo . --tier 1 --tier 2 --tier 3
  ```
- **Every claim carries its verifier**: a file:line, a test name, a command, or a cited spec. A
  claim you cannot evidence goes in `SOP.md`'s "Unverified / needs an operator pass" section
  instead. An honest partial doc beats a complete-looking invented one, because the invented one
  gets trusted.
- **No forbidden crypto words.** "quantum-proof", "unbreakable", "quantum-safe", "CNSA 2.0
  compliant", "FIPS 206", "Falcon" are banned outright, and skcot is classical T0 so there is no
  post-quantum claim to make at all. Never imply AES-256 is quantum-broken.

## Changes that need extra care

| Area | Why | What is required |
|---|---|---|
| `pki.py` CA construction | The CA is pinned in every enrolled device's truststore. Regenerating it un-enrolls the fleet. | `init_ca()` must stay idempotent. A test proving it. |
| Listener bind addresses | `0.0.0.0` would expose a tactical endpoint publicly. | Keep the tailnet bind. Update SOP section 5 and the evidence block. |
| `is_ephemeral_beacon` in `codec.py` | Misclassification recreates the exact production defect that split this package out of skcomms. | A test on both rails. |
| The geo HTTP route or port | `skcomms/src/skcomms/geo_store.py:61` hardcodes `http://127.0.0.1:8091/geo/units`. | A coordinated skcomms PR, or do not change it. |
| `SKCOMMS_COT_*` env names | Renaming them to `SKCOT_*` silently un-configures every deployment. | Do not, unless you also ship a compatibility shim and update every unit. |
| The shipped systemd units | They ship deliberate `REPLACE_ME_...` placeholders so a copied unit fails closed instead of binding `0.0.0.0`. | Never replace a placeholder with a real IP in the repo. This is public. |

## Secrets

Never commit a key, a certificate private key, a token, or a real coordinate you care about.
`secret-scan.yml` scans the full history and the history is currently clean; if that gate ever goes
red, a secret was **added**. Rotate it and purge it. Do not weaken the scan to an incremental one.

## Review path

1. Open the PR against `main` with a body that states: what changed, which documented facts moved,
   the test result, and anything you could not verify.
2. CI must be green: `ci`, `secret-scan`, `docs-check`.
3. A change to `pki.py`, `server.py`'s TLS context, or any bind address needs a second reviewer.
4. Add a `CHANGELOG.md` entry under `## [Unreleased]` in the same PR.
5. Do not merge your own PR.

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
