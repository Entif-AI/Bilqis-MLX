"""Observation storage is replayable and has no authority over learner behavior."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.teacher_observation_capture import store_sidecar, read_sidecar


class CaptureIdentityTests(unittest.TestCase):
    def capture(self, root, *, topology_width=12, stats=0, steps=2):
        from copy import deepcopy
        from dataclasses import asdict
        from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
        from bilqis_mlx.factory.tests.test_executable_release import ExecutableFactoryReleaseTests
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.learning.champions import Checkpoint
        from bilqis_mlx.runtime.model_topology import ModelTopologySpec
        fixture = ExecutableFactoryReleaseTests()
        fixture.setUp()
        release = fixture.compile()
        school = start_new(schedule_program_from_executable_release(release), Checkpoint("a" * 64, "bundles/fixture", 0, True))
        receipt = dict(run_id="fixture", generation=1, school=asdict(school),
            model_topology=ModelTopologySpec(1, 2, topology_width, 24, 96).to_record(), teacher_source_sha256="c" * 64)
        teacher = {"strategies": {"fixed": {"lr": .00013}}, "events": stats}
        capture = ObservationCapture(root, receipt)
        capture.select_option("Z.C0", None)
        capture.propose(release, school, "Z.C0", "fixed", teacher["strategies"]["fixed"], {},
            configured_steps=steps, effective_steps=steps, batch_size=6, settings=None,
            enrichment=False, source_rows=[], teacher=teacher, parent_optimizer_step=0)
        return capture, release

    def test_topology_is_partition_and_statistics_do_not_change_policy_epoch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, _ = self.capture(root)
            stats, _ = self.capture(root, stats=50)
            topology, _ = self.capture(root, topology_width=24)
            epoch, _ = self.capture(root, steps=4)
            self.assertEqual(first.proposal["policy_evidence_epoch"], stats.proposal["policy_evidence_epoch"])
            self.assertEqual(first.proposal["policy_evidence_epoch"], topology.proposal["policy_evidence_epoch"])
            self.assertNotEqual(first.proposal["partition"], topology.proposal["partition"])
            self.assertEqual(first.proposal["student_region"], topology.proposal["student_region"])
            self.assertNotEqual(first.proposal["policy_evidence_epoch"], epoch.proposal["policy_evidence_epoch"])

    def test_realized_step_preserves_multiplicity_and_changed_composition(self):
        from bilqis_mlx.runtime.teacher_observation_capture import read_sidecar
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture, release = self.capture(root)
            one = dict(id="one", capability="Z.C0", gold="FALSE")
            support = dict(id="support", capability="Z.C1", gold="TRUE")
            capture.delivery(release, "Z.C0", 1, [one, one, support], option_rows=[one],
                priority=(), preservation=(), support=[support], enrichment=(), guidance=None,
                controls={"old": 1}, seed=17)
            step = read_sidecar(root, capture.steps[0])
            self.assertEqual([position["row"]["sha256"] for position in step["positions"]][:2],
                             [step["positions"][0]["row"]["sha256"]] * 2)
            self.assertEqual(step["delivered_teaching"]["specimen_ids"], ["one"])
            self.assertEqual(len(step["positions"]), 3)
            self.assertEqual(step["positions"][-1]["roles"], ["retention_support"])
            self.assertTrue(step["realization_changed"])


    def test_readback_verifies_policy_and_selection_context_objects(self):
        from bilqis_mlx.runtime.teacher_observation_capture import read_observation
        for field in ("policy_evidence_epoch", "selection_source_context"):
            with self.subTest(field=field), TemporaryDirectory() as tmp:
                root = Path(tmp)
                capture, _ = self.capture(root)
                event = {}
                capture.finish(event, decision=None, paired=None, protected=None,
                    stage="ORDINARY", attempted=1, retained=1)
                (root / capture.proposal[field]["file"]).write_text("{}")
                with self.assertRaisesRegex(ValueError, "CONTENT_MISMATCH"):
                    read_observation(root, event)

    def test_skip_scores_preserve_only_valid_pre_action_measurements(self):
        from bilqis_mlx.runtime.teacher_observation_capture import read_observation
        for correct, total, expected in ((6, 6, "MEASURED"), (0, 0, "NOT_MEASURED"),
                                          (7, 6, "NOT_MEASURED")):
            with self.subTest(correct=correct, total=total), TemporaryDirectory() as tmp:
                root = Path(tmp)
                capture, _ = self.capture(root)
                event = {"target_probe_correct": correct, "target_probe_total": total}
                capture.finish(event, decision=None, paired=None, protected=None,
                    stage="PERFECT_TARGET_SKIP", attempted=0, retained=0)
                observation = read_observation(root, event)
                self.assertEqual(observation["outcome"]["target"]["before"]["status"], expected)
                self.assertEqual(observation["outcome"]["target"]["after"]["status"], "NOT_MEASURED")
                self.assertEqual(observation["attempt_status"], "SELECTION_SKIPPED")
