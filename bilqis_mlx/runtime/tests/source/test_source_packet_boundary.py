"""Every immutable worker packet constructor enforces the same boundary."""
import hashlib
import json
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.source_prefetch import ImmutableSourcePacket, SCHEMA, freeze_source_packet


def record(payload):
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return ImmutableSourcePacket('a' * 64, payload, digest)


class SourcePacketBoundaryTests(unittest.TestCase):
    def test_direct_constructor_rejects_mutable_alias_and_forbidden_authority(self):
        mutable = []
        for payload in ((('identity', 'a' * 64), ('schema', SCHEMA), ('weights', mutable)),
                        tuple(sorted(dict(identity='a' * 64, schema=SCHEMA, fresh=mutable,
                            prior=(), preservation=(), retention_support=(), teaching_enrichment_rows=()).items()))):
            with self.subTest(payload=payload), self.assertRaises(BilqisError):
                record(payload)

    def test_frozen_factory_payload_roundtrips_without_retained_alias(self):
        fresh = [{'source_receipt': {'receipt': 'source-only'}, 'value': [1, 2]}]
        packet = dict(schema=SCHEMA, identity='a' * 64, fresh=fresh, prior=[],
            preservation=[], retention_support=[], teaching_enrichment_rows=[])
        frozen = freeze_source_packet(packet)
        fresh[0]['value'].append(3)
        self.assertEqual(record(frozen.payload), frozen)
        self.assertNotEqual(freeze_source_packet(packet), frozen)
