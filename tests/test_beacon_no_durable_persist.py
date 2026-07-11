"""[CoT][CB4] Receiver property: a beacon lands in GEO_STORE, never a file.

The whole reason skcot was extracted is that ephemeral CoT position beacons
(atoms, ``a-*``) must never accumulate as durable mailbox envelopes -- that is
what caused the ~270k-file flood. ``test_cot_beacon_outbox.py`` /
``test_cot_beacon_ephemeral_routing.py`` already prove the SENDER side
(supersede-only outbox, short TTL, no-ack). This file proves the RECEIVER
side: when this node consumes an inbound CoT beacon envelope, it (a) lands in
:data:`skcot.service.GEO_STORE` -- the CB4 situational picture -- and (b)
leaves no leftover durable envelope file in the node's comms inbox.

Uses :func:`skcot.service.consume_cot_inbound`, the single receiver entry
point: given a CoT-bearing :class:`~skcomms.envelope.Envelope` (however it
arrived -- mailbox inbox file, TCP push, mesh datagram), it upserts into
GEO_STORE and never itself writes a durable copy; if handed the path of a
file the envelope arrived as, it deletes that file too (supersede-by-erasure,
mirroring the sender-side supersede-only outbox).
"""

from __future__ import annotations

import json

import pytest

from skcot.codec import COT_CONTENT_TYPE, CotEvent, CotPoint, cot_to_envelope
from skcot.service import GEO_STORE, consume_cot_inbound
from skcomms.home import skcomms_home

BEACON_UID = "ANDROID-BEACON-1"


def _beacon(uid: str = BEACON_UID, lat: float = 38.8895, lon: float = -77.0353) -> CotEvent:
    """An ephemeral position beacon (PLI): CoT atom, type ``a-f-G-U-C``."""
    return CotEvent(
        uid=uid,
        type="a-f-G-U-C",
        how="m-g",
        point=CotPoint(lat=lat, lon=lon, hae=50.0),
        callsign="JARVIS-1",
    )


@pytest.fixture(autouse=True)
def _clean_geo_store():
    """GEO_STORE is a process-wide singleton (service.py) -- isolate tests."""
    GEO_STORE.clear()
    yield
    GEO_STORE.clear()


@pytest.fixture
def comms_home(tmp_path, monkeypatch):
    """A tmp SKCOMMS_HOME with the node's comms inbox the consume path uses."""
    home = tmp_path / "home"
    monkeypatch.setenv("SKCOMMS_HOME", str(home))
    inbox = skcomms_home() / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    return home


class TestConsumeLandsInGeoStore:
    def test_beacon_upserted_into_geo_store(self, comms_home):
        cot = _beacon()
        env = cot_to_envelope(cot, from_fqid="jarvis@chef.skworld")
        unit = consume_cot_inbound(env)

        assert unit is not None
        stored = GEO_STORE.get(BEACON_UID)
        assert stored is not None
        assert stored.uid == BEACON_UID
        assert stored.lat == pytest.approx(38.8895)
        assert stored.lon == pytest.approx(-77.0353)
        assert stored.kind == "unit"

    def test_non_cot_envelope_is_ignored(self, comms_home):
        from skcomms.envelope import Envelope

        env = Envelope(from_fqid="a@b.c", to_fqid="*", content_type="text/plain", body="hi")
        assert consume_cot_inbound(env) is None
        assert GEO_STORE.count() == 0


class TestNoDurableMailboxFile:
    def test_consuming_an_in_memory_envelope_writes_no_file(self, comms_home):
        """The consume step itself never persists a durable inbox copy."""
        inbox = skcomms_home() / "inbox"
        cot = _beacon()
        env = cot_to_envelope(cot, from_fqid="jarvis@chef.skworld")

        consume_cot_inbound(env)  # never touched disk; source_path not given

        assert list(inbox.glob("*.json")) == []
        assert list(inbox.rglob("*.skc.json")) == []

    def test_arrived_beacon_file_is_consumed_with_no_leftover(self, comms_home):
        """A beacon that DID arrive as a durable file leaves none behind after consume.

        Mirrors how ``_inbox_inject_loop`` finds peer-originated CoT: a JSON
        file in the node's comms inbox carrying the envelope body. Feeding it
        through the single consume entry point must (a) land the entity in
        GEO_STORE and (b) delete the source file -- not archive/rename it --
        so the durable inbox never accumulates beacon envelopes.
        """
        inbox = skcomms_home() / "inbox"
        cot = _beacon(uid="ANDROID-BEACON-2", lat=39.0, lon=-77.5)
        env = cot_to_envelope(cot, from_fqid="jarvis@chef.skworld")

        arrived = inbox / f"{env.id}.skc.json"
        arrived.write_text(json.dumps(env.model_dump(mode="json")))
        assert arrived.exists()

        unit = consume_cot_inbound(env, source_path=arrived)

        assert unit is not None
        assert GEO_STORE.get("ANDROID-BEACON-2") is not None
        assert not arrived.exists()                # deleted, not archived
        assert list(inbox.glob("*.skc.json")) == []  # inbox left clean
        assert list(inbox.iterdir()) == []            # no "processed" subdir litter either

    def test_repeated_rebeaconing_never_leaves_a_growing_pile(self, comms_home):
        """The property that actually matters: N re-beacons -> 0 durable files, 1 GEO_STORE entry."""
        inbox = skcomms_home() / "inbox"
        for i in range(20):
            cot = _beacon(lat=38.0 + i * 0.001, lon=-77.0)
            env = cot_to_envelope(cot, from_fqid="jarvis@chef.skworld")
            arrived = inbox / f"{env.id}.skc.json"
            arrived.write_text(json.dumps(env.model_dump(mode="json")))
            consume_cot_inbound(env, source_path=arrived)

        assert GEO_STORE.count() == 1               # same uid -> upsert, not accumulate
        assert list(inbox.glob("*")) == []           # zero durable files, even after 20 beacons
