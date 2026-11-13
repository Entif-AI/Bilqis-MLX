"""Canonical sources and receipts survive physical module grouping."""
import hashlib
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys
import unittest

from bilqis_mlx.paths import REPO_ROOT, source_path


class SourcePathTests(unittest.TestCase):
    def test_canonical_source_and_resource_locations(self):
        self.assertEqual(source_path('boolean_composite.py'),
                         REPO_ROOT / 'bilqis_mlx/_boolean_sources/boolean_composite.py')
        self.assertEqual(source_path('semantics/numeric_v1.json'),
                         REPO_ROOT / 'bilqis_mlx/semantics/numeric_v1.json')
        self.assertEqual(find_spec('bilqis_mlx.boolean_composite').origin,
                         str(source_path('boolean_composite.py')))
        self.assertEqual(import_module('bilqis_mlx.boolean_composite').__name__,
                         'bilqis_mlx.boolean_composite')

    def test_alternate_module_names_cannot_duplicate_source_owners(self):
        result = subprocess.run([sys.executable, '-B', '-c',
            "import importlib; importlib.import_module("
            "'bilqis_mlx._boolean_sources.boolean_composite')"],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No module named 'bilqis_mlx._boolean_sources.boolean_composite'",
                      result.stderr)

    def test_constructor_fingerprint_keeps_logical_keys_and_actual_bytes(self):
        from bilqis_mlx.live_grade_b import constructor_digest
        import json
        expected = {name: hashlib.sha256(source_path(name).read_bytes()).hexdigest()
                    for name in ('live_grade_b.py', 'grade_b_oracle.py')}
        expected_digest = hashlib.sha256(json.dumps(expected, sort_keys=True,
            ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        self.assertEqual(constructor_digest(), expected_digest)

    def test_numeric_resource_and_historical_constructor_remain_readable(self):
        from bilqis_mlx.live_grade_c import REGISTRY_PATH, constructor_digest
        self.assertEqual(REGISTRY_PATH, REPO_ROOT / 'bilqis_mlx/semantics/numeric_registry_v1.json')
        self.assertEqual(len(constructor_digest()), 64)


if __name__ == '__main__':
    unittest.main()
