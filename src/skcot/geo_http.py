"""Minimal read-only HTTP surface over the live CoT situational picture.

skcot's service (:mod:`skcot.service`) keeps a process-wide
:class:`~skcot.geo.GeoStore` fed from every CoT it receives (TCP :8087, TLS
:8089, UDP mesh :6969, and the federation inbox). That store lives inside the
skcot process; the skcomms-api daemon that serves ``GET /api/v1/geo/units`` for
the SkMap pane runs in a *separate* process with its own store. This module is
the bridge: a tiny stdlib-asyncio HTTP server (no new dependency) that exposes
the live store read-only, so skcomms can source real telemetry from it.

Contract (GET only, read-only):

  * ``GET /geo/units``                -> ``{"units": [...], "count": N}``
  * ``GET /geo/units?format=geojson`` -> a GeoJSON ``FeatureCollection``
  * ``?include_stale=1``              -> include fixes past their stale / TTL

Anything else is a small JSON 404 / 405. Every request is handled fail-soft: a
handler error becomes a 500 JSON body, never a crash of the CoT service. The
server is deliberately GET-only, so this surface can never mutate the picture.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import parse_qs, urlsplit

logger = logging.getLogger("skcot.geo_http")

DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8091

_TRUTHY = {"1", "true", "yes", "on"}
_READ_TIMEOUT_S = 5.0


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in _TRUTHY


def _geo_payload(store: Any, *, fmt: str, include_stale: bool) -> Any:
    """Render the store in the requested shape (same contract as skcomms)."""
    if fmt == "geojson":
        return store.to_feature_collection(include_stale=include_stale)
    units = store.units_json(include_stale=include_stale)
    return {"units": units, "count": len(units)}


def _http_response(status: str, body: bytes, *, content_type: str = "application/json") -> bytes:
    head = (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    return head + body


def _json_response(status: str, obj: Any) -> bytes:
    return _http_response(status, json.dumps(obj).encode("utf-8"))


def make_geo_http_handler(store: Any):
    """Build an ``asyncio.start_server`` handler that serves *store* read-only."""

    async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            try:
                request_line = await asyncio.wait_for(reader.readline(), timeout=_READ_TIMEOUT_S)
            except asyncio.TimeoutError:
                return
            if not request_line:
                return
            # Drain request headers (ignored; a GET carries no body we consume).
            while True:
                h = await asyncio.wait_for(reader.readline(), timeout=_READ_TIMEOUT_S)
                if h in (b"\r\n", b"\n", b""):
                    break

            try:
                method, target, _ = request_line.decode("latin-1").split(" ", 2)
            except ValueError:
                writer.write(_json_response("400 Bad Request", {"error": "bad request line"}))
                await writer.drain()
                return

            if method.upper() != "GET":
                writer.write(_json_response("405 Method Not Allowed", {"error": "GET only"}))
                await writer.drain()
                return

            parts = urlsplit(target)
            path = parts.path.rstrip("/") or "/"
            if path != "/geo/units":
                writer.write(
                    _json_response("404 Not Found", {"error": "not found", "path": parts.path})
                )
                await writer.drain()
                return

            q = parse_qs(parts.query)
            fmt = (q.get("format", ["units"])[0] or "units").lower()
            if fmt not in ("units", "geojson"):
                fmt = "units"
            include_stale = _truthy(q.get("include_stale", [None])[0])

            try:
                payload = _geo_payload(store, fmt=fmt, include_stale=include_stale)
                writer.write(_json_response("200 OK", payload))
            except Exception as exc:  # noqa: BLE001 - never crash the CoT service
                logger.warning("geo http handler error: %s", exc)
                writer.write(
                    _json_response("500 Internal Server Error", {"error": "geo store read failed"})
                )
            await writer.drain()
        except (ConnectionError, asyncio.TimeoutError):
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("geo http connection error: %s", exc)
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    return _handle


async def start_geo_http_server(
    store: Any, host: str = DEFAULT_HTTP_HOST, port: int = DEFAULT_HTTP_PORT
) -> asyncio.AbstractServer:
    """Start the read-only geo HTTP server bound to (host, port).

    Returns the running :class:`asyncio.AbstractServer`. Raises on bind failure
    (the caller in :func:`skcot.service.main` catches that and logs, so a busy
    port never takes down the CoT service). Pass ``port=0`` for an ephemeral
    port (tests read it back from ``server.sockets[0].getsockname()``).
    """
    handler = make_geo_http_handler(store)
    return await asyncio.start_server(handler, host, port)
