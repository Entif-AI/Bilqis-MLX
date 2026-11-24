"""Cheap receipt comparison contract; never launches training."""
from copy import deepcopy
import unittest

from scripts.bamf.profiling.issue1616.operator_receipts import behavioral_outcome


class OperatorReceiptTests(unittest.TestCase):
    def test_rejection_token_does_not_replace_behavioral_comparison(self):
        left = {
            "event": "BAMF_CANDIDATE_REJECTED", "teacher": "teacher-a",
            "how_outcome": {
                "selected_teacher_sha256": "teacher-a", "outcome_sha256": "outcome-a",
                "teacher_visit": {"selection_seed": 594},
                "selected_policy": {"lr": 0.001},
                "decision": {"candidate_generation": "process-a",
                             "parent_generation": "parent",
                             "decision_sha256": "decision-a",
                             "evidence_sha256": "evidence-a", "decision": "REJECT"},
                "scores": [["A.PARENT", 3, 3, 6]],
            },
        }
        right = deepcopy(left)
        right["teacher"] = "teacher-b"
        how = right["how_outcome"]
        how.update(selected_teacher_sha256="teacher-b", outcome_sha256="outcome-b")
        how["decision"].update(candidate_generation="process-b",
                               decision_sha256="decision-b", evidence_sha256="evidence-b")
        self.assertNotEqual(left, right)
        self.assertEqual(behavioral_outcome(left), behavioral_outcome(right))
        how["selected_policy"]["lr"] = 0.002
        self.assertNotEqual(behavioral_outcome(left), behavioral_outcome(right))
        how["selected_policy"]["lr"] = 0.001
        how["scores"][0][2] = 4
        self.assertNotEqual(behavioral_outcome(left), behavioral_outcome(right))

    def test_accepted_candidate_generation_remains_behavioral_evidence(self):
        left = {"event": "BAMF_C16_3_ACCEPTED", "teacher": "teacher",
                "how_outcome": {"decision": {"candidate_generation": "canonical-a"}}}
        right = deepcopy(left)
        right["how_outcome"]["decision"]["candidate_generation"] = "canonical-b"
        self.assertNotEqual(behavioral_outcome(left), behavioral_outcome(right))


if __name__ == "__main__":
    unittest.main()
