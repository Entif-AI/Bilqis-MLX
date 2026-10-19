"""Exact earning questions protect titles without freezing historical scores."""
from copy import deepcopy
from unittest import TestCase

from bilqis_mlx.learning.championship_witnesses import (
    earning_witness, maxed_role, preserves_witnesses,
)


def exam():
    return {
        "cohort_sha256": "a" * 64, "rubric_sha256": "b" * 64,
        "source_graph_sha256": "c" * 64, "source_oracle_sha256": "d" * 64,
        "assessment_scope_sha256": "e" * 64,
        "scores": {"A.X": {"correct": 2, "total": 2},
                   "B.Y": {"correct": 1, "total": 2}},
        "correct_questions": {
            "A.X": [{"id": "a0", "gold": "TRUE"}, {"id": "a1", "gold": "FALSE"}],
            "B.Y": [{"id": "b0", "gold": "TRUE"}],
        },
        "questions": {
            "A.X": [{"id": "a0", "gold": "TRUE"}, {"id": "a1", "gold": "FALSE"}],
            "B.Y": [{"id": "b0", "gold": "TRUE"}, {"id": "b1", "gold": "FALSE"}],
        },
    }


class ChampionshipWitnessTests(TestCase):
    def test_initial_epoch_is_empty_eligible_and_does_not_fabricate_a_graduate(self):
        from bilqis_mlx.learning.mentor_epoch import begin_initial_epoch, reference_checkpoints
        student = {"filename": "bundles/inert", "sha256": "a" * 64,
                   "optimizer_step": 10, "model_and_native_adamw": True}
        epoch = begin_initial_epoch(student=student, introduced_grade="A",
                                    source_graph_sha256="b" * 64, frontier={}, soups={})
        self.assertEqual(epoch["active_roles"], {})
        self.assertIsNone(epoch["previous_graduate"])
        self.assertLess(epoch["championship_eligibility_after_step"], 10)
        self.assertEqual(reference_checkpoints(epoch), (student,))

    def test_all_influencing_questions_become_obligations_including_misses(self):
        measured = exam()
        proof = earning_witness(measured, ("A.X", "B.Y"))
        self.assertEqual({q["id"] for q in proof["questions"]}, {"a0", "a1", "b0", "b1"})
        self.assertEqual(proof["perfect_capabilities"], ["A.X"])
        self.assertEqual(measured, exam())

    def test_every_influencing_question_must_survive_across_grades(self):
        proof = earning_witness(exam(), ("A.X", "B.Y"))
        role = {"capability": "A.X", "qualification_witnesses": [proof]}
        self.assertFalse(preserves_witnesses(role, {}))
        self.assertFalse(preserves_witnesses(role, {proof["sha256"]: ["a0", "a1"]}))
        self.assertFalse(preserves_witnesses(role, {proof["sha256"]: ["a0", "a1", "b0"]}))
        self.assertTrue(preserves_witnesses(role, {proof["sha256"]: ["a0", "a1", "b0", "b1"]}))

    def test_max_vote_entitlement_uses_saved_proof_even_if_fresh_score_is_lower(self):
        proof = earning_witness(exam(), ("A.X",))
        role = {"capability": "A.X", "correct": 1, "total": 2,
                "qualification_witnesses": [proof]}
        self.assertTrue(maxed_role(role))

    def test_changed_or_missing_earning_evidence_fails_closed(self):
        measured = exam()
        measured["correct_questions"]["A.X"].pop()
        with self.assertRaises(ValueError):
            earning_witness(measured, ("A.X",))
        proof = earning_witness(exam(), ("A.X",))
        damaged = deepcopy(proof)
        damaged["questions"][0]["gold"] = "FALSE"
        with self.assertRaises(ValueError):
            preserves_witnesses({"qualification_witnesses": [damaged]}, {})
