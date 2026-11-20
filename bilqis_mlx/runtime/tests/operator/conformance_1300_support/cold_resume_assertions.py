"""Cold accepted-custody and legal-next assertions for the #1300 lineage."""
from __future__ import annotations

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation

from .cold_probe import probe as local_probe
from .scenario import cold_legal_next_probe, cold_probe


def assert_cold_resume_legality(test, run_dir, successor: str) -> dict:
    in_process = local_probe(run_dir)
    cold = cold_probe(run_dir)
    test.assertEqual(cold, in_process)
    test.assertEqual(cold["topology_layers"], 12)
    test.assertEqual(
        cold["checkpoint_identity_sha256"],
        candidate_identity_digest(load_accepted_generation(run_dir).retained_state),
    )

    first = cold_legal_next_probe(run_dir)
    test.assertTrue(first["accepted_state_unchanged"])
    test.assertEqual(
        first["checkpoint_identity_sha256"], cold["checkpoint_identity_sha256"])
    test.assertEqual(first["generation"], cold["generation"])
    test.assertEqual(first["optimizer_step"], cold["optimizer_step"])
    test.assertEqual(
        first["factory_release_sha256"], cold["factory_release_sha256"])
    test.assertEqual(first["active_grade"], cold["active_grade"])
    test.assertEqual(first["cadence_before"], cold["cadence"])
    test.assertIsNotNone(first["autonomy_before"])
    test.assertIsNotNone(first["autonomy_after"])
    test.assertEqual(
        first["frontier_checkpoint_identity_sha256"],
        cold["checkpoint_identity_sha256"],
    )
    test.assertEqual(
        first["frontier_factory_release_sha256"],
        cold["factory_release_sha256"],
    )
    test.assertEqual(
        first["frontier_active_grade_activation_sha256"],
        cold["active_grade"]["activation_sha256"],
    )
    test.assertTrue(first["lawful_frontier_sha256"])
    test.assertEqual(first["legal_next_status"], "TEACHER_SELECTED")
    test.assertEqual(first["legal_next_capability_id"], successor)

    replay = cold_legal_next_probe(run_dir)
    test.assertTrue(replay["accepted_state_unchanged"])
    test.assertEqual(
        replay["checkpoint_identity_sha256"], cold["checkpoint_identity_sha256"])
    test.assertEqual(
        replay["factory_release_sha256"], cold["factory_release_sha256"])
    test.assertEqual(replay["active_grade"], cold["active_grade"])
    test.assertEqual(first["lawful_frontier_sha256"], replay["lawful_frontier_sha256"])
    test.assertEqual(first["legal_next_status"], replay["legal_next_status"])
    test.assertEqual(
        first["legal_next_capability_id"], replay["legal_next_capability_id"])
    test.assertEqual(
        first["legal_next_visit_identity"], replay["legal_next_visit_identity"])
    test.assertEqual(first["cadence_after"], replay["cadence_before"])
    test.assertEqual(replay["cadence_before"], replay["cadence_after"])
    test.assertEqual(first["autonomy_after"], replay["autonomy_before"])
    test.assertEqual(replay["autonomy_before"], replay["autonomy_after"])
    return {"accepted": cold, "legal_next": first, "legal_next_replay": replay}
