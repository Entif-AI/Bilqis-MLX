"""Accepted BAMF custody projects only proven Factory cockpit facts."""
import unittest

from bilqis_mlx.control_plane.native_contracts import AuthenticatedGeneration
from bilqis_mlx.control_plane.native_factory import accepted_factory_records
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2


def digest(char):
    return char * 64


def generation(number, release, semantic, *, adoption=False):
    outbox = ()
    if adoption:
        outbox = ({
            "event": "BAMF_FACTORY_RELEASE_ADOPTION_COMMITTED",
            "factory_release_sha256": release,
            "transition_sha256": digest("5"),
            "selection_receipt_sha256": digest("6"),
        },)
    return AuthenticatedGeneration(
        digest(str(number + 1)), digest(str(number + 2)),
        {
            "run_id": "run-factory", "generation": number,
            "optimizer": {"step": number},
            "provenance": {"release_digest": semantic},
            "topology": ModelTopologySpecV2().to_record(),
            "transition": {},
        },
        {"candidate_identity_sha256": digest("8"), "factory_release_sha256": release},
        {
            "run_identity_sha256": digest("9"),
            "initial_candidate_identity_sha256": digest("8"),
            "factory_release_sha256": release,
        },
        correction_frontier={}, teacher_state={}, outbox=outbox,
    )


class NativeFactoryProjectionTests(unittest.TestCase):
    def test_accepted_history_keeps_prior_release_stale_and_current_release_exact(self):
        old_release, current_release = digest("a"), digest("c")
        rows = accepted_factory_records((
            generation(0, old_release, digest("b")),
            generation(1, current_release, digest("d"), adoption=True),
        ))
        self.assertEqual([item.currency_state.value for item in rows], ["STALE", "CURRENT"])
        self.assertEqual(rows[0].meta.coverage.value, "PARTIAL")
        self.assertEqual(rows[1].lifecycle_state.value, "ADMITTED")
        self.assertEqual(rows[1].delivery_status.value, "NOT_EVIDENCED")
        self.assertEqual(rows[1].lineage[0].generation, 1)
        self.assertEqual(rows[1].lineage[0].topology.knowledge.value, "EXACT")
        self.assertEqual(rows[1].lineage[0].topology.layers, 12)
        self.assertEqual(rows[1].admission_receipt_sha256, digest("3"))
        self.assertEqual(rows[1].capability_ids, ())


if __name__ == "__main__":
    unittest.main()
