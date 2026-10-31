"""Historical persisted record identity survives implementation extraction."""
import pickle
import unittest
from bilqis_mlx.semantics.atlas_projection import SourceRecordRef
from bilqis_mlx.semantics.atlas_projection_parts.concepts import SourceRecordRef as OwnedRef


class HistoricalConceptRecordTests(unittest.TestCase):
    def test_historical_global_pickle_and_public_type_are_unchanged(self):
        historical = (b'cbilqis_mlx.semantics.atlas_projection\nSourceRecordRef\n'
                      b'(Vlexicon\nVroots\nVROOT-TEST\ntR.')
        record = pickle.loads(historical)
        self.assertIs(type(record), SourceRecordRef)
        self.assertIs(OwnedRef, SourceRecordRef)
        self.assertEqual((record.domain, record.table, record.key),
                         ('lexicon', 'roots', 'ROOT-TEST'))
        self.assertIn(b'bilqis_mlx.semantics.atlas_projection', pickle.dumps(record))
