"""The public error catalog preserves exact wire and recovery contracts."""
from dataclasses import asdict
import hashlib
import json
import pickle
import unittest

from bilqis_mlx.errors import CATALOG, ErrorBus, SCHOOL, SOURCE
from bilqis_mlx.errors.catalog import BY_CODE, BY_LEGACY_CODE


class CatalogTests(unittest.TestCase):
    def test_frozen_catalog_order_and_complete_contracts(self):
        payload = json.dumps([asdict(spec) for spec in CATALOG],
                             sort_keys=True, separators=(",", ":"))
        self.assertEqual(len(CATALOG), 112)
        self.assertEqual(hashlib.sha256(payload.encode()).hexdigest(),
                         "1461ea2506a42c037e58dc295e375445e3d192634d4fc5eb24e9a8b30da99ab8")
        self.assertEqual(len(BY_CODE), 112)
        self.assertIs(BY_CODE["SCHOOL.STATE.COURSE_DIGEST_MISMATCH"],
                      SCHOOL.STATE.COURSE_DIGEST_MISMATCH)
        for spec in CATALOG:
            for alias in spec.legacy_codes:
                self.assertIn(spec, BY_LEGACY_CODE[alias])

    def test_nested_namespaces_keep_historical_pickle_paths(self):
        for namespace in (SCHOOL, SCHOOL.STATE, SCHOOL.BAMF_AKASHA,
                          SOURCE, SOURCE.BOOLEAN):
            with self.subTest(namespace=namespace):
                self.assertEqual(namespace.__module__, "bilqis_mlx.errors.catalog")
                self.assertIs(pickle.loads(pickle.dumps(namespace)), namespace)

    def test_source_failure_still_has_recoverable_operator_contract(self):
        report = ErrorBus.explain("SOURCE.BOOLEAN.UNKNOWN_OPERATOR")[0]
        self.assertEqual(report.owner, "live_grade_b")
        self.assertTrue(report.preserve_state)
        self.assertFalse(report.legacy_untyped)
