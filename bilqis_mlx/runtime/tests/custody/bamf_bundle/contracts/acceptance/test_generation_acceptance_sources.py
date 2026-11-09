"""B13 source-qualified acceptance must preserve learned dependency custody."""
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.runtime.tests.correction.capability_support_owner_support import (
    source_qualified_state,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import retention_decision


class GenerationAcceptanceSourceCustodyTests(unittest.TestCase):
    def test_source_qualified_proof_cannot_publish_without_training_authority(self):
        _parent, _transaction, retained, authority = source_qualified_state()
        decision = retention_decision(retained=retained)
        with self.assertRaises(BilqisError):
            mint_acceptance_binding(
                decision, retained, run_id="run", generation=1,
                feature_sha256="f" * 64)
        binding = mint_acceptance_binding(
            decision, retained, run_id="run", generation=1,
            feature_sha256="f" * 64, training_authorities=(authority,))
        self.assertEqual(len(binding.source_anchors), 1)
        self.assertEqual(binding.source_anchors[0][8], authority.digest)


if __name__ == "__main__":
    unittest.main()
