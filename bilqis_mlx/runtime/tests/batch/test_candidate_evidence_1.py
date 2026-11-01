"""Candidate evidence."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, patch, predicted,
    rows, schedule_program,
)


class CandidateEvidence1Tests(CausalTeacherExperimentTests):
    def test_trainer_defers_missing_peer_inference_until_candidate_target_passes(self):
        from pathlib import Path
        from bilqis_mlx import trainer as trainer
        grade = ("B.IFF", "B.NOT", "B.XOR")
        rows = [{"id": cap + str(i), "capability": cap,
                 "gold": "TRUE"} for cap in (*grade, "A.EDGE") for i in range(2)]
        parent = predicted(rows, {"B.XOR0", "B.NOT0"})
        candidate = dict(parent)
        candidate["B.XOR0"] = "TRUE"
        candidate["B.NOT0"] = "TRUE"
        candidate["B.IFF0"] = "FALSE"
        evaluated = []
        def inference(_mx, identity, chosen, _config, _answers):
            evaluated.append((identity, tuple(row["id"] for row in chosen)))
            truth = parent if identity == "parent" else candidate
            return {row["id"]: truth[row["id"]] for row in chosen}
        with (patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=(*grade, "A.EDGE")),
              patch('bilqis_mlx.learning.student_ops._predictions', side_effect=inference),
              patch('bilqis_mlx.runtime.candidate_evidence._fixed_same_grade_rows',
                           return_value=()) as fixed,
              patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                    return_value=())):
            school = type("School", (), {"current_student": type(
                "Student", (), {"sha256": "a" * 64, "optimizer_step": 1})()})()
            program = schedule_program(
                ("A", ("A.EDGE",)),
                ("B", grade),
            )
            pair, protected, required, _, _, _, stage = trainer._candidate_grade_evidence(
                None, Path("/not-used"), {"config": {}, "answer_ids": []},
                program, school, "B.XOR", "parent", "candidate", rows,
                {"B.XOR0": parent["B.XOR0"], "B.XOR1": parent["B.XOR1"]},
                Settings())
        self.assertEqual(stage, "COMPLETE_SAME_GRADE")
        self.assertEqual(required, tuple(sorted(grade)))
        self.assertEqual(pair["B.XOR"], {"before": 1, "after": 2, "total": 2})
        self.assertEqual(pair["B.IFF"], {"before": 2, "after": 1, "total": 2})
        self.assertEqual(pair["B.NOT"], {"before": 1, "after": 2, "total": 2})
        self.assertEqual(protected, {"B.IFF", "B.NOT", "A.EDGE"})
        self.assertEqual(len(evaluated), 3)
        self.assertEqual(evaluated[0], ("candidate", ("B.XOR0", "B.XOR1")))
        self.assertTrue(all("B.XOR0" not in call[1] and
                            "B.XOR1" not in call[1] for call in evaluated[1:]))
        fixed.assert_called_once()

    def test_failed_target_and_grade_net_skip_expensive_fixed_replay(self):
        from pathlib import Path
        from bilqis_mlx import trainer as trainer
        grade = ("B.IFF", "B.NOT", "B.XOR")
        rows = [{"id": cap + str(i), "capability": cap,
                 "gold": "TRUE"} for cap in (*grade, "A.EDGE") for i in range(2)]
        parent = predicted(rows, {"B.XOR0", "B.NOT0"})
        candidate = dict(parent)
        candidate["B.XOR0"] = "TRUE"
        candidate["B.IFF0"] = "FALSE"

        # With no target gain, neither peers nor a fixed full-grade exam are
        # evaluated and the unchanged parent can be rejected immediately.
        with (patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=(*grade, "A.EDGE")),
              patch('bilqis_mlx.learning.student_ops._predictions',
                           side_effect=lambda _mx, _id, selected, *_:
                           {row["id"]: parent[row["id"]] for row in selected}),
              patch('bilqis_mlx.runtime.candidate_evidence._fixed_same_grade_rows',
                           side_effect=AssertionError("no extra grade test"))):
            program = schedule_program(
                ("A", ("A.EDGE",)),
                ("B", grade),
            )
            small, protected, required, fixed, replay, _, stage = (
                trainer._candidate_grade_evidence(
                    None, Path("/not-used"), {"config": {}, "answer_ids": []},
                    program, object(), "B.XOR", "parent", "candidate", rows,
                    {"B.XOR0": parent["B.XOR0"], "B.XOR1": parent["B.XOR1"]},
                    Settings()))
        self.assertEqual(stage, "TARGET_ONLY_REJECTED")
        self.assertEqual(set(small), {"B.XOR"})
        self.assertEqual(protected, set())
        self.assertEqual(required, ("B.XOR",))
        self.assertEqual(fixed["status"], "NOT_MEASURED")
        self.assertEqual(replay["status"], "NOT_MEASURED")

        # A positive target with negative/tied grade net is also terminal:
        # the full fixed examination must not run for an already-rejected
        # candidate, and only the previously missing grade peers were scored.
        degraded = dict(candidate)
        degraded["B.NOT0"] = "FALSE"
        degraded["B.NOT1"] = "FALSE"
        with (patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=(*grade, "A.EDGE")),
              patch('bilqis_mlx.learning.student_ops._predictions',
                           side_effect=lambda _mx, identity, selected, *_:
                           {row["id"]: (parent if identity == "parent"
                                        else degraded)[row["id"]]
                            for row in selected}),
              patch('bilqis_mlx.runtime.candidate_evidence._fixed_same_grade_rows',
                           side_effect=AssertionError("net grade loss must stop"))):
            incomplete, controls, required, fixed, replay, _, stage = (
                trainer._candidate_grade_evidence(
                    None, Path("/not-used"), {"config": {}, "answer_ids": []},
                    program, object(), "B.XOR", "parent", "candidate", rows,
                    {"B.XOR0": parent["B.XOR0"], "B.XOR1": parent["B.XOR1"]},
                    Settings()))
        self.assertEqual(stage, "GRADE_NET_REJECTED")
        self.assertEqual(set(incomplete), {*grade, "A.EDGE"})
        self.assertEqual(sum(incomplete[cap]["after"]-incomplete[cap]["before"]
                             for cap in grade), -1)
        self.assertEqual(controls, {"B.IFF", "B.NOT", "A.EDGE"})
        self.assertEqual(fixed["status"], "NOT_MEASURED")
