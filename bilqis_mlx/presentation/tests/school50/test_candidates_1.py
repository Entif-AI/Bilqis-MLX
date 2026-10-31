"""Candidates projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest


class CandidatesTests(unittest.TestCase):
    def test_method_column_projects_actual_instruction_mechanism(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "B", "active_grade": "C", "capability": "B.IFF",
                "optimizer_step": 232472, "retained_optimizer_updates": 0,
                "teacher_decision": {"selected": {
                    "exam_mistake_replay": 128,
                    "prerequisite_connections": [],
                    "champion_priority": 0,
                }},
                "boolean_association_bridge": {
                    "active_for_visit": True,
                    "borrowed_source_grades": ["A", "C"],
                    "delivered_examples": 128,
                },
            })
            self.assertEqual(board.rows["CANDIDATES"][-1]["method"], "COMPOSE+MISS")

    def test_teacher_policy_health_is_visible_in_soup_and_teacher(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            self.assertIn(
                ("HEALTH", 9),
                [(column.name, column.width)
                 for column in dict(board.tables)["SOUP & TEACHER"]],
            )
            for attempt in range(16):
                ingest(board, {
                    "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                    "grade": "C", "generation": attempt + 2,
                    "capability": "C.ADD", "optimizer_step": 120 + attempt,
                    "teacher_policy": "policy-low",
                    "strategy": {
                        "lr": .00013, "depth": 3, "contrast": .5,
                        "old": 8, "preview": 0, "distill": .15,
                    },
                    "source_training_accuracy_before": .5,
                    "source_training_accuracy_after": .6,
                    "teacher_reward": .1, "gradient_norm": 1.0, "loss": .4,
                    "next_phase": "RECOVERY_1",
                    "teacher_decision": {"selected": {}},
                    "candidate_retention": {
                        "active_capability": "C.ADD",
                        "phase": "RECOVERY_1",
                        "decision": "PROVISIONAL" if attempt == 0 else "REJECT",
                        "reason": "FIXTURE",
                        "local_correct_delta": 1 if attempt == 0 else 0,
                        "protected_net_correct_delta": 0,
                        "worst_protected_loss": 0,
                    },
                })
            self.assertEqual(
                board.rows["SOUP & TEACHER"][-1]["health"], "LOW-YIELD")

    def test_teacher_policy_health_marks_unproven_and_exhausted_policies(self):
        from bilqis_mlx.presentation.teacher_vnext import teacher_fields
        history = {}
        event = {
            "capability": "C.SUB", "teacher_policy": "policy-zero",
            "candidate_retention": {
                "phase": "RECOVERY_2", "decision": "REJECT",
            },
        }
        for _ in range(7):
            fields = teacher_fields(event, history)
        self.assertEqual(fields["health"], "UNCERTAIN")
        for _ in range(9):
            fields = teacher_fields(event, history)
        self.assertEqual(fields["health"], "LOW-YIELD")

        cooled = dict(event, teacher_policy_health={
            "status": "SEARCH_NEIGHBORHOOD_EXHAUSTED",
            "remaining_capability_visits": 8,
        })
        self.assertEqual(teacher_fields(cooled, history)["health"], "EXHAUSTED")

        mutated = dict(event, teacher_selection_reason="FRESH_MUTATED_CHALLENGER")
        self.assertEqual(teacher_fields(mutated, {})["health"], "EXPLORE")

    def test_policy_with_grade_wide_failure_history_is_not_uncertain_on_new_capability(self):
        from bilqis_mlx.presentation.teacher_vnext import teacher_fields
        history = {}
        for _ in range(9):
            teacher_fields({
                "grade": "B", "capability": "B.IFF", "teacher_policy": "dead",
                "candidate_retention": {"phase": "MAIN", "decision": "REJECT"},
            }, history)

        fields = teacher_fields({
            "grade": "B", "capability": "B.COMPOSITE", "teacher_policy": "dead",
            "candidate_retention": {"phase": "MAIN", "decision": "REJECT"},
        }, history)

        self.assertEqual(fields["health"], "LOW-YIELD")

    def test_candidate_retention_populates_retention_panel_with_real_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "B", "capability": "B.IFF", "optimizer_step": 232472,
                "attempted_optimizer_updates": 16, "retained_optimizer_updates": 0,
                "candidate_retention": {
                    "active_probe_before": 10, "active_probe_after": 8,
                    "active_probe_total": 12, "local_correct_delta": -2,
                    "protected_net_correct_delta": 0, "worst_protected_loss": 0,
                    "decision": "REJECT", "reason": "NO_MEASURABLE_TARGET_GAIN",
                    "unsampled_admitted_capabilities": 18,
                },
            })
            row = board.rows["SENTINEL & RETENTION"][-1]
            self.assertEqual(row["capability"], "B.IFF")
            self.assertEqual(row["target"], "10>8/12")
            self.assertEqual(row["target_delta"], "-2")
            self.assertEqual(row["protected"], "+0")
            self.assertEqual(row["worst"], "0")
            self.assertEqual(row["decision"], "REJECT")
            self.assertIn("NO_MEASURABLE_TARGET_GAIN", row["evidence"])

    def test_retention_decision_not_instructional_note_controls_commit_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for cap, decision, reason, updates in (
                ("C.NUMBER", "REJECT", "NO_MEASURABLE_TARGET_GAIN", 0),
                ("C.MUL", "REJECT", "FRAGILE_COMPOSITION_REPLAY_REGRESSION", 0),
                ("B.NOT", "PROVISIONAL", "PAIRED_SCREEN_WITHIN_BUDGET", 16),
            ):
                ingest(board, {
                    "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                    "capability": cap, "grade": cap[0],
                    "optimizer_step": 229512,
                    "retained_optimizer_updates": updates,
                    "candidate_retention": {"decision": decision, "reason": reason},
                    "teacher_decision": {"selected": {"exam_mistake_replay": 1}},
                })
            c_number, c_mul, b_not = list(board.rows["CANDIDATES"])[-3:]
            self.assertIn("REJECT", c_number["decision"])
            self.assertIn("NO TARGET GAIN", c_number["decision"])
            self.assertNotIn("LESSON COMMITTED", c_number["decision"])
            self.assertIn("REJECT", c_mul["decision"])
            self.assertIn("OR/XOR", c_mul["decision"])
            self.assertIn("RETAIN 16", b_not["decision"])
            self.assertIn("miss 1", b_not["decision"])
            self.assertNotIn("LESSON COMMITTED", b_not["decision"])

    def test_inconsistent_retention_metadata_does_not_claim_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "C", "capability": "C.NUMBER",
                "retained_optimizer_updates": 0,
                "candidate_retention": {"decision": "PROVISIONAL",
                                        "reason": "PAIRED_SCREEN_WITHIN_BUDGET"}})
            self.assertIn("ADMISSION CONFLICT",
                          board.rows["CANDIDATES"][-1]["decision"])

    def test_candidate_probe_score_uses_same_compact_score_shape_as_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            labels = [column.name for column in dict(board.tables)["CANDIDATES"]]
            self.assertIn("WAS/CHP/NOW/ALL", labels)
            self.assertNotIn("LESSON% BFR>AFTER", labels)
            self.assertNotIn("TRAIN BEFORE>AFTER", labels)
