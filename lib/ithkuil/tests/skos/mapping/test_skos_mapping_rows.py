from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import csv
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import quote

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.mapping_admission import load_policy
from lib.ithkuil.src.skos.mapping_rows import load_mapping_rows, preserve_nonadmitted, source_row


ROOT = ITHKUIL_ROOT / "_data/csv"


class MappingHeldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_mapping_rows(ROOT)
        cls.policy = load_policy()

    def test_every_current_source_row_has_one_loss_accounted_record(self):
        records = preserve_nonadmitted(self.rows, self.policy)
        self.assertEqual(len(records), 552)
        self.assertEqual({(item.entry.table, item.entry.key) for item in records},
                         {(row.record_ref.table, row.record_ref.key) for row in self.rows})
        self.assertEqual(sum(item.entry.status == "HELD" for item in records), 551)
        self.assertEqual(sum(item.entry.status == "REJECTED" for item in records), 1)
        self.assertFalse(any(item.entry.status == "EMITTED" for item in records))
        self.assertTrue(all(item.entry.semantic_iri == "" for item in records))

    def test_exact_source_states_commentary_and_targets_survive(self):
        indexed = {row.record_ref: row for row in self.rows}
        records = preserve_nonadmitted(self.rows, self.policy)
        for item in records:
            row = indexed[item.entry.source_refs[0]].values
            body = item.as_dict()
            for field, value in item.original_states:
                self.assertEqual(value, row[field])
            for field, value in item.endpoint_ids:
                self.assertEqual(value, row[field])
            for field, value in item.commentary:
                self.assertEqual(value, row[field])
            self.assertEqual(body['key'], row.get('crosswalk_id', row.get('bridge_id')))
        historical = [item for item in records if dict(item.original_states).get('source_era') == 'historical_2011']
        self.assertEqual(len(historical), 2)
        self.assertTrue(all(dict(item.original_states)['target_kind'] == 'historical_source' for item in historical))

    def test_all_named_nonadmitted_states_are_preserved(self):
        records = preserve_nonadmitted(self.rows, self.policy)
        expected = {'MAPPING_PROPOSAL_HELD', 'MAPPING_BLOCKED_HELD', 'MAPPING_DEFERRED_HELD',
                    'MAPPING_HISTORICAL_ONLY_HELD', 'MAPPING_REJECTED_EXACT_EQUIVALENCE',
                    'MAPPING_STRATEGY_NOT_SEMANTIC_ADMISSION_HELD'}
        self.assertTrue(expected <= {record.entry.reason_code for record in records})
        self.assertTrue(all(record.entry.status in {'HELD', 'REJECTED'} for record in records))

    def test_changed_state_is_reclassified_without_mutating_previous_evidence(self):
        row = next(row for row in self.rows if row.record_kind == 'crosswalk')
        before = preserve_nonadmitted((row,), self.policy)[0].as_dict()
        changed = row.values
        changed['crosswalk_state'] = 'future-unreviewed-state'
        after = preserve_nonadmitted((source_row('crosswalk', changed),), self.policy)[0]
        self.assertEqual(after.entry.status, 'UNSUPPORTED')
        self.assertEqual(after.entry.reason_code, 'MAPPING_POLICY_NO_MATCH')
        self.assertEqual(preserve_nonadmitted((row,), self.policy)[0].as_dict(), before)

    def test_reordered_input_preserves_exact_serialized_records(self):
        forward = [record.as_dict() for record in preserve_nonadmitted(self.rows, self.policy)]
        reverse = [record.as_dict() for record in preserve_nonadmitted(reversed(self.rows), self.policy)]
        self.assertEqual(json.dumps(forward, sort_keys=True), json.dumps(reverse, sort_keys=True))

    def test_private_commentary_is_explicitly_withheld_not_serialized(self):
        row = next(row for row in self.rows if row.record_kind == 'bridge')
        private_value = 'file:///home/example/secret'
        for depth in range(6):
            with self.subTest(encoding_depth=depth):
                changed = row.values
                changed['semantic_caution_or_dependencies'] = private_value
                record = preserve_nonadmitted((source_row('bridge', changed),), self.policy)[0]
                self.assertEqual(record.withheld_fields, ('semantic_caution_or_dependencies',))
                self.assertNotIn(private_value, json.dumps(record.as_dict()))
                self.assertEqual(record.entry.key, row.record_ref.key)
            private_value = quote(private_value, safe='')

    def test_duplicate_and_missing_row_identity_fail_closed(self):
        with self.assertRaises(ProfileError) as caught:
            preserve_nonadmitted((self.rows[0], self.rows[0]), self.policy)
        self.assertEqual(caught.exception.code, 'DUPLICATE_MAPPING_SOURCE_ID')
        with self.assertRaises(ProfileError) as caught:
            source_row('crosswalk', {'crosswalk_id': ''})
        self.assertEqual(caught.exception.code, 'MAPPING_SOURCE_ID_REQUIRED')

    def test_malformed_csv_does_not_turn_into_partial_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'bilqis_ithkuil_crosswalk.csv'
            path.write_text('crosswalk_id,crosswalk_id\na,b\n')
            with self.assertRaises(ProfileError) as caught:
                load_mapping_rows(temporary)
            self.assertEqual(caught.exception.code, 'MAPPING_SOURCE_SCHEMA_INVALID')


if __name__ == '__main__':
    unittest.main()
