import csv
import io
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.ithkuil.src import affix_admission as admission


class AffixAdmissionTests(unittest.TestCase):
    def test_published_rows_fully_reconcile(self):
        data = admission.DATA
        admission.validate(data, admission.read_rows(data / 'sources/source_manifest.csv'),
                           admission.read_rows(data / 'source_tables.csv'),
                           admission.read_rows(data / 'source_table_cells.csv'))

    def test_mutated_or_missing_source_rows_are_rejected(self):
        data = admission.DATA
        manifest = admission.read_rows(data / 'sources/source_manifest.csv')
        tables = admission.read_rows(data / 'source_tables.csv')
        cells = admission.read_rows(data / 'source_table_cells.csv')
        changed = [dict(row) for row in cells]
        next(row for row in changed if row['source_id'] == 'NI-AFFIX-PDF')['cell_text'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'AFFIX_OUTPUT_DIGEST'):
            admission.validate(data, manifest, tables, changed)
        with self.assertRaisesRegex(ValueError, 'AFFIX_OUTPUT_DIGEST'):
            admission.validate(data, manifest, tables[:-1], cells)
        source = next(row for row in manifest if row['source_id'] == 'NI-AFFIX-PDF')
        source['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'AFFIX_SOURCE_PIN'):
            admission.validate(data, manifest, tables, cells)

    def test_ambiguous_locus_is_not_hidden_by_valid_ledger_digest(self):
        data = admission.DATA
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory)
            (staged / 'sources').mkdir()
            profile = json.loads((data / admission.PROFILE).read_text())
            ledger = json.loads((data / admission.LEDGER).read_text())
            next(row for row in ledger if row['disposition'] == 'PARSED')['bbox'] = None
            payload = admission.parser.canonical_bytes(ledger)
            profile['receipt']['observations_sha256'] = admission.digest(payload)
            (staged / admission.PROFILE).write_text(json.dumps(profile))
            (staged / admission.LEDGER).write_bytes(payload)
            with self.assertRaisesRegex(ValueError, 'AFFIX_LEDGER_LOCUS_OR_STATE'):
                admission.validate(staged, admission.read_rows(data / 'sources/source_manifest.csv'),
                                   admission.read_rows(data / 'source_tables.csv'),
                                   admission.read_rows(data / 'source_table_cells.csv'))

    def test_preexisting_affix_and_semantic_identities_are_byte_compatible(self):
        expected = {
            'affix_degrees.csv': '7eb67d6e39a9798f57da66a0b8840996a9caa46bfb5c0df10b71c4299bdbb2a3',
            'morphemes_atomic.csv': '6c6e2ea64a659b7061bdc3d388201c6219207bc1aa002869537f56d1f7ddf083',
            'source_assertions.csv': '20a197bd4ca9757c19b731652d124139109351294a3b561fb456c81f2e922f7d',
            'lexicon_roots.csv': 'ddd84523758a5dcbfa86f70cd2c7bb0f63bdea18ee089015390f0d3a8199fc46',
            'lexicon_root_senses.csv': 'fe0701acb57e9257b56bf2feac741171e583fdfab032f3d017cfcc8fa404eb5c',
            'lexicon_root_evidence.csv': 'aaefff67aa4b2ddf058a1926ce874145c1eb2fab4c5821eb7ce04e0cce601b50',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((admission.DATA / name).read_bytes()).hexdigest(), digest, name)

    def test_missing_receipt_rejects_pdf_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'AFFIX_UNADMITTED_ROWS'):
                admission.validate(Path(directory), [],
                                   [{'source_id': 'NI-AFFIX-PDF'}], [])

    def test_validator_rehashes_the_actual_pdf(self):
        data = admission.DATA
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed.pdf'
            path.write_bytes(b'not the pinned source')
            with patch.object(admission.parser, 'PDF', path):
                with self.assertRaisesRegex(ValueError, 'AFFIX_SOURCE_FILE_PIN'):
                    admission.validate(data, admission.read_rows(data / 'sources/source_manifest.csv'),
                                       admission.read_rows(data / 'source_tables.csv'),
                                       admission.read_rows(data / 'source_table_cells.csv'))

    def test_row_serialization_preserves_existing_csv_bytes(self):
        for name in ('source_sections.csv', 'source_tables.csv', 'source_table_cells.csv'):
            path = admission.DATA / name
            rows = list(csv.DictReader(io.StringIO(path.read_text())))
            self.assertEqual(admission.csv_bytes(rows), path.read_bytes())

    def test_failed_stage_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / 'csv'
            data.mkdir()
            sentinel = data / 'source_tables.csv'
            sentinel.write_bytes(b'untouched\n')
            with patch.object(admission, '_stage_validate', side_effect=ValueError('stage failed')):
                with self.assertRaisesRegex(ValueError, 'stage failed'):
                    admission.publish_files(data, {'source_tables.csv': b'replaced\n'})
            self.assertEqual(sentinel.read_bytes(), b'untouched\n')


if __name__ == '__main__':
    unittest.main()
