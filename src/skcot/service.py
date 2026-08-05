"""Runnable CoT service — bind the CB2 TAK-streaming endpoint to a live node.

``python -m skcot.service`` starts the :class:`CotStreamServer` bound to
the tailnet (``0.0.0.0:8087``) wired to this node's SKComms:

  * **phone → fabric:** inbound CoT from connected ATAK/iTAK clients is wrapped
    in a signed Envelope and federated to peer nodes (``federation_ingest``),
  * **fabric → phone:** a poll loop watches the skcomms inbox for CoT-bearing
    envelopes that arrived from peers and :meth:`~CotStreamServer.push`es them
    to the connected clients — so an operator on this node sees remote teams.

This is the deploy substrate for CB5 (real-device E2E). Plain TCP; CB3 adds TLS
+ per-device capauth identity.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from .codec import COT_CONTENT_TYPE, parse_cot
from .server import (
    DEFAULT_COT_PORT, DEFAULT_COT_TLS_PORT, CotStreamServer, TlsCotStreamServer,
    UdpMeshListener, federation_ingest,
)
from .geo import GeoStore, GeoUnit
from .geo_http import DEFAULT_HTTP_HOST, DEFAULT_HTTP_PORT, start_geo_http_server
from skcomms.envelope import Envelope
from skcomms.home import skcomms_home
from skcomms.identity import resolve_self_identity

logger = logging.getLogger("skcot.service")

# Process-wide situational-awareness store (CB4). Every CoT this node receives
# — TCP, TLS, mesh, or peer-injected — is upserted here so agents and the map
# read one ground-truth picture. In-memory; positions are re-beaconed.
GEO_STORE = GeoStore()


def consume_cot_inbound(
    env: Envelope, *, source: str = "federation", source_path: Optional[Path] = None
) -> Optional[GeoUnit]:
    """Consume one inbound CoT-bearing Envelope into GEO_STORE. The receiver hook.

    This is the single entry point for turning an *arrived* CoT envelope --
    however it got here (a peer-federation inbox file, a TCP/TLS/mesh push
    already wrapped as an Envelope) -- into the CB4 situational picture.

    The core property this exists to guarantee: an ephemeral position beacon
    (CoT atom, ``a-*``) must land in :data:`GEO_STORE` and must NEVER become a
    durable mailbox file. So this function:

      * upserts the parsed CoT into :data:`GEO_STORE` (supersede-by-uid --
        re-beaconing the same entity never accumulates extra state), and
      * writes nothing to disk itself (no durable inbox copy, ever), and
      * if *source_path* names the file this envelope arrived as (e.g. a
        peer-federation inbox drop), deletes it -- so a beacon that DID land
        as a file on the way in leaves nothing behind on the way out.

    Non-CoT envelopes (wrong ``content_type``) and unparseable CoT bodies are
    silently ignored (returns ``None``); *source_path*, if given, is left
    alone in that case since this hook didn't consume it.

    Args:
        env: The arrived Envelope. Only ``application/cot+xml`` is consumed.
        source: Attribution tag stored on the :class:`~skcot.geo.GeoUnit`
            (``GeoUnit.source``), e.g. ``"federation"`` / ``"tcp"`` / ``"mesh"``.
        source_path: Optional path to the durable file this envelope arrived
            as. When given and the envelope is consumed, the file is deleted.

    Returns:
        The upserted :class:`~skcot.geo.GeoUnit`, or ``None`` if the envelope
        wasn't CoT, was unparseable, or :meth:`GeoStore.upsert_from_cot`
        skipped it (chat / ping / no usable fix).
    """
    if env.content_type != COT_CONTENT_TYPE:
        return None
    try:
        cot = parse_cot(env.body)
    except ValueError:
        return None
    unit = GEO_STORE.upsert_from_cot(cot, source=source)
    if source_path is not None:
        try:
            source_path.unlink(missing_ok=True)
        except OSError:
            pass
    return unit


def _extract_cot_body(data: dict) -> str | None:
    """Pull a CoT XML string out of a stored inbox envelope (shape-tolerant)."""
    for k in ("content", "body"):
        v = data.get(k)
        if isinstance(v, str) and "<event" in v:
            return v
    payload = data.get("payload")
    if isinstance(payload, dict):
        v = payload.get("content") or payload.get("body")
        if isinstance(v, str) and "<event" in v:
            return v
    return None


async def _inbox_inject_loop(
    server: CotStreamServer, *, also: CotStreamServer | None = None, poll_s: float = 3.0
) -> None:
    """Inject peer-originated CoT (landed in the inbox) to connected clients.

    *also* is an optional second server (e.g. the TLS endpoint) to fan the same
    CoT to, so peer-originated traffic reaches both plain and TLS operators.
    """
    inbox = skcomms_home() / "inbox"
    processed = inbox / "cot-processed"
    try:
        processed.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass
    seen: set[str] = set()
    while True:
        try:
            for f in sorted(inbox.glob("*.json")):
                if f.name in seen:
                    continue
                seen.add(f.name)
                try:
                    data = json.loads(f.read_text())
                except Exception:  # noqa: BLE001
                    continue
                body = _extract_cot_body(data)
                if not body:
                    continue
                try:
                    cot = parse_cot(body)
                except ValueError:
                    continue
                GEO_STORE.upsert_from_cot(cot, source="federation")  # CB4 picture
                await server.push(cot)
                if also is not None:
                    await also.push(cot)
                logger.info("injected peer CoT uid=%s to %d client(s)", cot.uid, server.client_count)
                try:
                    f.rename(processed / f.name)
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("inbox inject loop error: %s", exc)
        await asyncio.sleep(poll_s)


def advertise_cot_capability(sk=None) -> None:
    """Ensure this node's realm-directory entry advertises the ``cot`` capability.

    Called on skcot startup (:func:`main`) so the beacon peer-gate
    (``skcot.server._cot_peer_fqids`` / ``_cot_gate_active``) can eventually
    self-configure from this node's own advertised capabilities instead of a
    manual ``SKCOMMS_COT_PEERS`` allowlist: once this node's realm-directory
    entry carries ``"cot"``, anything that resolves it via
    :mod:`skcomms.skfed_resolve` (or the realm directory) sees it as a CoT
    consumer.

    :func:`skcomms.skfed_directory.publish_self_to_realm_directory` OVERWRITES
    the ``caps`` field on upsert -- it does not merge. So this reads the
    node's *current* directory entry first and unions ``"cot"`` into whatever
    is already there, preserving any other advertised tags (``dm``,
    ``files``, ...). Idempotent: calling it twice does not duplicate the tag.

    Fails soft (logs + returns) if no fqid, signing key, or inbox URL can be
    resolved -- cot-capability advertisement must never block the CoT TCP/TLS
    /mesh service from starting.

    Args:
        sk: Optional live :class:`~skcomms.core.SKComms` instance (its
            configured identity name is used to load the right node key).
    """
    from skcomms import skfed_announce as sfa
    from skcomms import skfed_directory as sfd

    agent = getattr(sk, "_identity", None) if sk is not None else None
    ident = resolve_self_identity(agent)
    fqid = ident.get("fqid")
    if not fqid:
        logger.debug("advertise_cot_capability: no fqid resolved, skipping")
        return
    agent = agent or ident.get("agent")

    try:
        existing_dir = sfd.load_directory()
    except Exception as exc:  # noqa: BLE001
        logger.debug("advertise_cot_capability: could not load realm directory: %s", exc)
        existing_dir = None
    existing = existing_dir.get(fqid) if existing_dir is not None else None

    caps = list(existing.caps) if existing is not None else []
    if "cot" not in caps:
        caps.append("cot")

    inbox_url = existing.inbox_url if existing is not None else None
    prekey_url = existing.prekey_url if existing is not None else None
    did = existing.did if existing is not None else None

    if inbox_url is None:
        inbox_url = os.environ.get("SKFED_INBOX_URL")
    if inbox_url is None:
        base = sfa.resolve_base()
        if base:
            inbox_url = base.rstrip("/") + sfa.INBOX_PATH
            if prekey_url is None:
                prekey_url = base.rstrip("/") + sfa.PREKEY_PATH
    if inbox_url is None:
        logger.debug("advertise_cot_capability: no inbox URL resolvable, skipping")
        return

    try:
        sfd.publish_self_to_realm_directory(
            fqid, inbox_url, prekey_url, did=did, caps=caps, agent=agent,
        )
        logger.info("advertised cot capability for %s (caps=%s)", fqid, caps)
    except Exception as exc:  # noqa: BLE001
        logger.warning("advertise_cot_capability: could not publish cot capability: %s", exc)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ident = resolve_self_identity()
    fqid = ident.get("fqid") or ident.get("agent") or "local"
    host = os.environ.get("SKCOMMS_COT_HOST", "0.0.0.0")
    port = int(os.environ.get("SKCOMMS_COT_PORT", DEFAULT_COT_PORT))

    from skcomms.core import SKComms  # local import — avoids heavy import at module load

    sk = SKComms.from_config()
    advertise_cot_capability(sk)  # self-configure the beacon peer-gate (no manual allowlist)
    fed_hook = federation_ingest(sk, from_fqid=fqid)

    # Mesh bridge holder: TCP-fabric CoT is multicast OUT to mesh devices (iTAK)
    # so they see the rest of the net. Mesh-origin CoT is NOT re-meshed (no echo).
    _mesh: dict[str, object] = {}

    def mesh_out(cot):
        m = _mesh.get("listener")
        if m is not None:
            try:
                m.send_cot(cot)
            except Exception:  # noqa: BLE001
                pass

    def tcp_ingest(cot):
        GEO_STORE.upsert_from_cot(cot, source="tcp")  # CB4 situational picture
        fed_hook(cot)   # federate to peer nodes
        mesh_out(cot)   # bridge TCP fabric → mesh devices

    server = CotStreamServer(host=host, port=port, ingest=tcp_ingest)
    await server.start()
    logger.info("CoT service up as %s on %s:%d (phone→federate + inbox→inject)", fqid, host, port)

    # CB3: TLS-enrolled endpoint (:8089). Each TLS connection's CoT is
    # additionally attributed to the device identity pinned from its client cert.
    tls_server: TlsCotStreamServer | None = None
    if os.environ.get("SKCOMMS_COT_TLS", "0") == "1":
        tls_port = int(os.environ.get("SKCOMMS_COT_TLS_PORT", DEFAULT_COT_TLS_PORT))

        def _ident_hook(cot, identity, fingerprint):
            logger.info("TLS CoT uid=%s attributed to device=%s (fp=%s)", cot.uid, identity, fingerprint)
            GEO_STORE.upsert_from_cot(cot, source=identity or "tls")  # CB4 picture
            fed_hook(cot)
            mesh_out(cot)   # bridge TLS clients (Androids, LUMINA) → mesh devices

        # Optional override: present a publicly-trusted server cert (e.g. a
        # `tailscale cert` Let's Encrypt cert) so strict clients (iTAK) trust us
        # without importing our CA. The PKI CA still verifies optional client
        # certs for per-device identity.
        tls_cert = os.environ.get("SKCOMMS_COT_TLS_CERT")
        tls_key = os.environ.get("SKCOMMS_COT_TLS_KEY")
        tls_ca = os.environ.get("SKCOMMS_COT_CA")
        if tls_cert and tls_key and not tls_ca:
            from .pki import pki_dir
            tls_ca = str(pki_dir() / "ca.pem")
        tls_server = TlsCotStreamServer(
            host=host, port=tls_port, ident_ingest=_ident_hook,
            server_cert=tls_cert, server_key=tls_key, ca_cert=tls_ca,
        )
        await tls_server.start()
        logger.info("CoT TLS endpoint up on %s:%d (server_cert=%s)", host, tls_port,
                    tls_cert or "PKI self-signed")

    # Mesh-mode ATAK (no server/auth): join the multicast group on the LAN so a
    # phone's mesh CoT is ingested + federated + shown to any TCP viewers.
    if os.environ.get("SKCOMMS_COT_MESH", "1") != "0":
        async def _mesh_event(cot):
            # mesh device CoT → fabric: federate + show to TCP clients. Do NOT
            # mesh_out (it came from mesh; re-sending would echo).
            GEO_STORE.upsert_from_cot(cot, source="mesh")  # CB4 picture
            fed_hook(cot)
            await server.push(cot)
            if tls_server is not None:
                await tls_server.push(cot)
            logger.info("mesh CoT uid=%s callsign=%s pos=(%s,%s)", cot.uid, cot.callsign,
                        cot.point.lat, cot.point.lon)
        mesh_iface = os.environ.get("SKCOMMS_COT_MESH_IFACE", "0.0.0.0")
        try:
            _mesh["listener"] = await UdpMeshListener(on_event=_mesh_event, iface_ip=mesh_iface).start()
            logger.info("mesh bridge active (iface=%s) — TCP fabric <-> mesh devices", mesh_iface)
        except Exception as exc:  # noqa: BLE001
            logger.warning("mesh listener not started: %s", exc)

    # CB4 bridge: expose the live GEO_STORE read-only over HTTP so the
    # skcomms-api daemon (a separate process serving GET /api/v1/geo/units for
    # SkMap) can source REAL CoT telemetry from this node instead of only its
    # own in-process fleet seed. GET-only, read-only, fail-soft: a bind failure
    # logs and does NOT take down the CoT TCP/TLS/mesh service.
    http_host = os.environ.get("SKCOT_HTTP_HOST", DEFAULT_HTTP_HOST)
    http_port = int(os.environ.get("SKCOT_HTTP_PORT", str(DEFAULT_HTTP_PORT)))
    try:
        await start_geo_http_server(GEO_STORE, http_host, http_port)
        logger.info("geo HTTP endpoint up on %s:%d (GET /geo/units, read-only)", http_host, http_port)
    except Exception as exc:  # noqa: BLE001 - HTTP bridge must never crash CoT
        logger.warning("geo HTTP endpoint not started (%s:%s): %s", http_host, http_port, exc)

    await _inbox_inject_loop(server, also=tls_server)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
