"""Public Atlas feature record identities remain versioned across extraction."""
import pickle
import unittest
from bilqis_mlx.semantics import atlas_features


class FeatureRecordTests(unittest.TestCase):
    def test_public_record_pickle_modules_remain_stable(self):
        for name in ("FeatureSchema", "ConceptFeature", "FeatureRow", "AtlasFeatures",
                     "ProspectiveIdentityFeature", "ProspectiveIdentityFeatureSet"):
            record = getattr(atlas_features, name)
            with self.subTest(record=name):
                self.assertEqual(record.__module__, "bilqis_mlx.semantics.atlas_features")
                self.assertIs(pickle.loads(pickle.dumps(record)), record)
