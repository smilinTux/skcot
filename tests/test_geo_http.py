"""Tests for the read-only geo HTTP bridge (``skcot.geo_http``).

Proves the CB4 bridge the SkMap feed depends on: the tiny stdlib-asyncio HTTP
server reflects live upserts into the ``GeoStore`` it is handed, in both the
flat ``units`` shape and the GeoJSON ``FeatureCollection`` shape, and rejects
non-GET verbs (it is read-only by construction).
"""

from __future__ import annotations

import asyncio
import json

from skcot.geo import GeoStore, GeoUnit
from skcot.geo_http import start_geo_http_server


async def _raw(host: str, port: int, request_line: str) -> tuple[str, str]:
    """Send one raw HTTP request line, return (status_line, body)."""
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(f"{request_line}\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    raw = await reader.read()
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:  # noqa: BLE001
        pass
    head, _, body = raw.partition(b"\r\n\r\n")
    status_line = head.split(b"\r\n", 1)[0].decode("latin-1")
    return status_line, body.decode("utf-8")


async def _get(host: str, port: int, path: str) -> tuple[str, str]:
    return await _raw(host, port, f"GET {path} HTTP/1.1")


async def _run() -> None:
    store = GeoStore()
    server = await start_geo_http_server(store, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        # Empty store -> a well-shaped empty envelope (never a 500).
        status, body = await _get("127.0.0.1", port, "/geo/units")
        assert status.endswith("200 OK"), status
        assert json.loads(body) == {"units": [], "count": 0}

        # Upsert into GEO_STORE -> the endpoint reflects it immediately.
        store.upsert(
            GeoUnit(uid="PURE", callsign="PURE", cot_type="a-f-G-U-C", lat=40.0, lon=-74.0)
        )
        status, body = await _get("127.0.0.1", port, "/geo/units")
        assert status.endswith("200 OK"), status
        data = json.loads(body)
        assert data["count"] == 1
        assert data["units"][0]["uid"] == "PURE"
        assert data["units"][0]["lat"] == 40.0
        assert data["units"][0]["lon"] == -74.0

        # GeoJSON alternative: [lon, lat] geometry, uid in properties.
        status, body = await _get("127.0.0.1", port, "/geo/units?format=geojson")
        assert status.endswith("200 OK"), status
        fc = json.loads(body)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 1
        assert fc["features"][0]["geometry"]["coordinates"] == [-74.0, 40.0]
        assert fc["features"][0]["properties"]["uid"] == "PURE"

        # Unknown path -> JSON 404, not a crash.
        status, _ = await _get("127.0.0.1", port, "/nope")
        assert status.endswith("404 Not Found"), status

        # Read-only: a write verb is rejected 405.
        status, _ = await _raw("127.0.0.1", port, "POST /geo/units HTTP/1.1")
        assert status.endswith("405 Method Not Allowed"), status
    finally:
        server.close()
        await server.wait_closed()


def test_geo_http_reflects_upsert():
    """End to end over a real socket, driven with asyncio.run (no plugin dep)."""
    asyncio.run(_run())
