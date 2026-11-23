"""Learning-first and strict-evidence human resume routing."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime.atlas_flywheel import AdmissionFlywheelStatus

from .resume_test_support import ResumeCase, TOPOLOGY, tree_snapshot


class BamfResumeTests(ResumeCase):
    def test_human_resume_dispatches_bamf_native_operator_after_validation(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            from bilqis_mlx.runtime.bamf_operator import BamfOperatorResult
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("legacy learner must remain untouched")), patch(
                    "bilqis_mlx.runtime.bamf_operator.operate_bamf",
                    return_value=BamfOperatorResult(
                        "VISIT_LIMIT", 1, 1, 0, 1, 1)) as operate:
                code, output, errors = self.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--max-visits", "1", "--strict-evidence",
                ])
            self.assertEqual((code, errors), (0, ""))
            report = json.loads(output)
            self.assertEqual(report["status"], "VISIT_LIMIT")
            self.assertEqual(report["generation"], 1)
            call = operate.call_args
            self.assertEqual(call.args, (target,))
            self.assertEqual(call.kwargs["minutes"], 90)
            self.assertEqual(call.kwargs["max_visits"], 1)
            self.assertEqual(call.kwargs["reserve_gib"], 100.0)
            self.assertTrue(callable(call.kwargs["progress"]))
            self.assertEqual(tree_snapshot(target), before)

    def test_human_resume_with_saved_atlas_lease_replans_then_continues_learning(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            from bilqis_mlx.runtime.bamf_operator import BamfOperatorResult
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle._accepted_atlas",
                    return_value=SimpleNamespace(
                        bundle_id="a" * 64, release_sha256="b" * 64,
                        source_bundle_id="c" * 64)), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle._saved_policy",
                    return_value="atlas-release"), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle.source_foundation",
                    return_value=(None, None, self.graph)), patch(
                    "bilqis_mlx.runtime.atlas_flywheel_runtime.run_accepted_atlas_flywheel",
                    return_value=SimpleNamespace(
                        status=AdmissionFlywheelStatus.WAITING_FOR_EVIDENCE,
                        reason="LEARNER_EVIDENCE_REQUIRED", advances=2,
                    )) as flywheel, patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("BAMF v2 must not re-enter the legacy learner")), patch(
                    "bilqis_mlx.runtime.bamf_operator.operate_bamf",
                    return_value=BamfOperatorResult(
                        "VISIT_LIMIT", 1, 1, 0, 1, 1)) as operate:
                code, output, errors = self.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--max-visits", "1", "--strict-evidence",
                ])
            self.assertEqual((code, errors), (0, ""))
            report = json.loads(output)
            self.assertEqual(report["status"], "VISIT_LIMIT")
            self.assertEqual(report["admission_status"], "WAITING_FOR_EVIDENCE")
            self.assertEqual(report["admission_reason"], "LEARNER_EVIDENCE_REQUIRED")
            self.assertEqual(report["admission_advances"], 2)
            self.assertEqual(report["admission_label"], "C07 waiting for learner evidence")
            flywheel.assert_called_once()
            self.assertEqual(Path(flywheel.call_args.args[0]), target.resolve())
            call = operate.call_args
            self.assertEqual(call.args, (target,))
            self.assertEqual(call.kwargs["minutes"], 90)
            self.assertEqual(call.kwargs["max_visits"], 1)
            self.assertEqual(call.kwargs["reserve_gib"], 100.0)
            self.assertTrue(callable(call.kwargs["progress"]))

    def test_learning_first_resume_skips_pre_dashboard_atlas_flywheel(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            from bilqis_mlx.runtime.bamf_operator import BamfOperatorResult
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle._accepted_atlas",
                    return_value=SimpleNamespace(
                        bundle_id="a" * 64, release_sha256="b" * 64,
                        source_bundle_id="c" * 64)), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle._saved_policy",
                    return_value="atlas-release"), patch(
                    "bilqis_mlx.runtime.atlas_flywheel_runtime.run_accepted_atlas_flywheel",
                    side_effect=AssertionError("learning-first resume must not run admission flywheel")), patch(
                    "bilqis_mlx.runtime.bamf_operator.operate_bamf",
                    return_value=BamfOperatorResult("VISIT_LIMIT", 1, 1, 0, 1, 1)) as operate:
                code, output, errors = self.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--max-visits", "1",
                ])
            self.assertEqual((code, errors), (0, ""))
            self.assertEqual(json.loads(output)["status"], "VISIT_LIMIT")
            self.assertFalse(operate.call_args.kwargs["strict_mode"])

    def test_human_resume_with_ambiguous_flywheel_hold_does_not_start_learning(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle._accepted_atlas",
                    return_value=SimpleNamespace(
                        bundle_id="a" * 64, release_sha256="b" * 64,
                        source_bundle_id="c" * 64)), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle._saved_policy",
                    return_value="atlas-release"), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle.source_foundation",
                    return_value=(None, None, self.graph)), patch(
                    "bilqis_mlx.runtime.atlas_flywheel_runtime.run_accepted_atlas_flywheel",
                    return_value=SimpleNamespace(
                        status=AdmissionFlywheelStatus.HELD,
                        reason="EXACT_HOLD", advances=3,
                    )), patch(
                    "bilqis_mlx.runtime.bamf_operator.operate_bamf",
                    side_effect=AssertionError("ambiguous admission hold must stop learning")):
                code, output, errors = self.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--strict-evidence",
                ])
            self.assertEqual((code, errors), (0, ""))
            report = json.loads(output)
            self.assertEqual(report["result"], "HELD")
            self.assertEqual(report["admission_reason"], "EXACT_HOLD")
            self.assertEqual(report["admission_advances"], 3)
            self.assertEqual(report["admission_policy"], "atlas-release")
            self.assertEqual(report["neural_updates"], 0)
