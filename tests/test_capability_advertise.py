"""Tests for ``skcot.service.advertise_cot_capability`` (skcot extraction Task 4).

skcot's beacon peer-gate (``skcot.server._cot_peer_fqids`` / ``_cot_gate_active``)
only fans ephemeral position beacons out to peers that ADVERTISE a ``cot``/``tak``
capability. Previously that meant a manual ``SKCOMMS_COT_PEERS`` allowlist. This
module makes a running skcot node self-advertise ``"cot"`` on startup by writing it
into its own entry in the local SKFed realm directory
(:func:`skcomms.skfed_directory.publish_self_to_realm_directory`).

``publish_self_to_realm_directory`` OVERWRITES the ``caps`` field on upsert (it
does not merge -- confirmed by tracing ``SignedDirectory.upsert``, which replaces
the whole entry by fqid). So ``advertise_cot_capability`` must read the node's
current directory entry first and union ``"cot"`` in, or it would clobber any
other advertised tags (``dm``, ``files``, ...) on re-announce.

The read-back API asserted on here is the real one: ``skfed_directory.load_directory()``
-> ``SignedDirectory.get(fqid)`` -> ``DirectoryEntry.caps``, the same path
``test_skfed_announce.py::test_announce_self_end_to_end_persists_and_verifies``
uses in skcomms itself. (``skcomms.discovery.PeerStore`` is a *separate* local
peer-discovery cache fed by Syncthing/file/mDNS/nostr scanning -- it is not
written by ``publish_self_to_realm_directory`` and is out of scope here.)
"""

from __future__ import annotations

import pytest

FQID = "testnode@chef.skworld"
AGENT = "testnode"


def _gen_key(uid: str):
    """In-process PGP key (mirrors skcomms' test_skfed_announce.py::_gen_key)."""
    import pgpy
    from pgpy.constants import (
        CompressionAlgorithm,
        HashAlgorithm,
        KeyFlags,
        PubKeyAlgorithm,
        SymmetricKeyAlgorithm,
    )

    key = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 1024)
    key.add_uid(
        pgpy.PGPUID.new(uid),
        usage={KeyFlags.Sign, KeyFlags.EncryptCommunications},
        hashes=[HashAlgorithm.SHA256],
        ciphers=[SymmetricKeyAlgorithm.AES256],
        compression=[CompressionAlgorithm.ZLIB],
    )
    return str(key), str(key.pubkey)


@pytest.fixture
def realm(tmp_path, monkeypatch):
    """Tmp SKCOMMS_HOME + injected node signer + fixed self identity.

    Mirrors the offline fixture pattern in skcomms' test_skfed_directory.py /
    test_api_skfed_directory.py (monkeypatch ``load_node_signer`` to an
    in-process key) and test_skfed_announce.py (tmp ``SKCOMMS_HOME``).
    """
    monkeypatch.setenv("SKCOMMS_HOME", str(tmp_path))
    monkeypatch.setenv("SKFED_BASE_URL", "https://testnode.ts.net")

    from skcomms import skfed_directory as sfd
    from skcomms.signing import EnvelopeSigner
    from skcot import service as svc

    priv, _pub = _gen_key("chef <chef@chef.skworld>")
    signer = EnvelopeSigner(priv)
    monkeypatch.setattr(sfd, "load_node_signer", lambda agent=None: signer)
    monkeypatch.setattr(
        svc, "resolve_self_identity", lambda agent=None: {"agent": AGENT, "fqid": FQID}
    )
    return sfd


def test_advertise_cot_capability_lands_in_realm_directory(realm):
    """A fresh node's realm-directory entry gets ``cot`` after advertising."""
    from skcot.service import advertise_cot_capability

    advertise_cot_capability()

    loaded = realm.load_directory()
    assert loaded is not None
    entry = loaded.get(FQID)
    assert entry is not None
    assert "cot" in entry.caps


def test_advertise_cot_capability_is_idempotent_and_preserves_other_caps(realm):
    """Calling twice does not duplicate ``cot``, and an existing tag survives."""
    from skcot.service import advertise_cot_capability

    # Seed an existing entry advertising an unrelated capability first, the
    # way a prior dm/files announce would have.
    realm.publish_self_to_realm_directory(
        FQID, "https://testnode.ts.net/api/v1/inbox", caps=["dm"], agent=AGENT,
    )

    advertise_cot_capability()
    advertise_cot_capability()

    loaded = realm.load_directory()
    entry = loaded.get(FQID)
    assert entry is not None
    assert entry.caps.count("cot") == 1
    assert "dm" in entry.caps  # not clobbered by the re-publish
