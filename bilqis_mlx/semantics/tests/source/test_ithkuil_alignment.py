"""A new linguistic bridge must never masquerade as legacy semantic mastery."""
from dataclasses import replace
import unittest
from bilqis_mlx.ithkuil_alignment import (BRIDGES, validate_bridges,
                                           approved_training_bridges)

class AlignmentTests(unittest.TestCase):
    def test_registry_bridge_ids_cannot_become_taught_roots_by_listing(self):
        validate_bridges()
        self.assertEqual(len(BRIDGES),7)
        self.assertEqual(approved_training_bridges(passed_prerequisites=frozenset()),())
        self.assertEqual(approved_training_bridges(passed_prerequisites=frozenset({"G19"})),())
        self.assertTrue(all(x.status=="RESEARCH_SEED_NOT_TAUGHT" for x in BRIDGES))
        self.assertTrue(all(x.not_equivalent_to for x in BRIDGES))

    def test_bridge_preserves_legacy_aliases_but_never_relabels_graph(self):
        reference=next(b for b in BRIDGES if b.bridge_id=="NI-N13-001")
        self.assertEqual(reference.legacy_concepts,("G19","G20","G21","G22"))
        with self.assertRaisesRegex(ValueError,"PREMATURE"):
            validate_bridges((replace(reference,status="TAUGHT"),))

if __name__=="__main__":
    unittest.main()
