"""Cold package reads reject malformed and noncanonical wire records."""
import json
import unittest
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import PackageAssertions, snapshot
from bilqis_mlx.runtime.cognitive_package import CognitivePackage, export_capability


class SerializationTests(PackageAssertions, unittest.TestCase):
    def setUp(self):
        source, rights = snapshot()
        self.package = export_capability(source, source.signature, rights)

    def test_malformed_records_fail_closed(self):
        raw = json.loads(self.package.canonical_json)
        variants = [[], {'unknown': 1}, {**raw, 'unknown': 1},
                    {**raw, 'schema_version': 'unknown'},
                    {**raw, 'max_memory_bytes': True},
                    {**raw, 'artifacts': []}]
        for value in variants:
            with self.subTest(value=value):
                with self.assertPackageError('wire'):
                    CognitivePackage.from_canonical_json(json.dumps(value, sort_keys=True, separators=(',', ':')))

    def test_invalid_hex_is_catalog_error(self):
        raw = json.loads(self.package.canonical_json)
        raw['artifacts'][0]['payload'] = 'not hex'
        with self.assertPackageError('wire'):
            CognitivePackage.from_canonical_json(json.dumps(raw, sort_keys=True, separators=(',', ':')))

    def test_duplicate_keys_noncanonical_and_truncation_reject(self):
        wire = self.package.canonical_json
        variants = [' ' + wire, wire[:-1], wire[:-1] + ',"schema_version":"other"}',
                    wire.replace('1024', '1024.0'), wire.replace('1024', 'NaN')]
        for value in variants:
            with self.subTest(value=value):
                with self.assertPackageError('wire'):
                    CognitivePackage.from_canonical_json(value)

    def test_literal_canonical_wire_and_digest(self):
        from pathlib import Path
        expected = Path(__file__).with_name('golden_package.json').read_text()
        self.assertEqual(self.package.canonical_json, expected)
        self.assertEqual(self.package.digest, '98527cd13e7a10c65d4697277e681137f34ff55dbdf479bf842eb7f87c6372e4')
        self.assertEqual(CognitivePackage.from_canonical_json(expected), self.package)

    def test_surrogates_rejected_on_cold_read(self):
        raw = json.loads(self.package.canonical_json)
        raw['operator_identity'] = chr(0xD800)
        for ascii_escape in (False, True):
            wire = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=ascii_escape)
            with self.assertPackageError('wire'):
                CognitivePackage.from_canonical_json(wire)
