"""Stored generated-suite hashes reject changed gold without pointer writes."""
import unittest
from bilqis_mlx.verification.generated_tests.storage import _read_release
from bilqis_mlx.verification.generated_tests.tests.helpers import boolean_release_fixture, publish


class StoredReleaseTests(unittest.TestCase):
    def test_changed_suite_bytes_fail_closed_and_preserve_active_pointer(self):
        with boolean_release_fixture() as (parity, root):
            manifest = publish(parity, root)
            pointer = (root / 'current.json').read_bytes()
            suite = root / 'releases' / manifest['release_sha256'] / 'suites/boolean.constants.json'
            suite.write_bytes(suite.read_bytes().replace(b'"expected":false', b'"expected":true'))
            with self.assertRaisesRegex(ValueError, 'SEMANTIC_TEST_INTEGRITY_SUITE_HASH:boolean.constants'):
                _read_release(root)
            self.assertEqual((root / 'current.json').read_bytes(), pointer)
