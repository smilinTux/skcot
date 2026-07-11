"""Task 6 codec round-trip characterization test — guards module move fidelity."""

from skcot.codec import parse_cot, to_cot, is_ephemeral_beacon


def test_cot_xml_roundtrip_and_ephemeral_classification():
    """Parse -> serialize -> parse preserves uid/lat/callsign; a-* is ephemeral."""
    xml = ('<event version="2.0" uid="J-1" type="a-f-G-U-C" how="m-g" '
           'time="2026-07-11T00:00:00Z" start="2026-07-11T00:00:00Z" stale="2026-07-11T00:05:00Z">'
           '<point lat="41.1375" lon="-73.424" hae="10" ce="5" le="5"/>'
           '<detail><contact callsign="JARVIS"/></detail></event>')

    # Parse XML
    ev = parse_cot(xml)
    assert ev.uid == "J-1" and ev.callsign == "JARVIS"

    # Round-trip: serialize and parse again
    ev2 = parse_cot(to_cot(ev))
    assert ev2.uid == ev.uid and abs(ev2.point.lat - 41.1375) < 1e-6

    # Verify ephemeral classification for a-* type
    assert is_ephemeral_beacon(ev) is True

    # Verify non-ephemeral for b-* type
    ev.type = "b-t-f"
    assert is_ephemeral_beacon(ev) is False
