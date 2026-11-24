"""Boundary, hold, and resource tests for native BAMF sessions."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.bamf_operator.session_parts.native_session import priority_hold_result
from bilqis_mlx.runtime.tests.operator.test_bamf_operator_session import _prepare_native_resource_visit


class BamfOperatorNativeSessionBoundaryTests(unittest.TestCase):
    def setUp(self):
        for name, behavior in (
                ('build_outcome', {'return_value': {'schema': 'routing-fixture'}}),
                ('credited_visit', {'side_effect': lambda visit, outcome: visit}),
                ('carry_credit_to_successor', {
                    'side_effect': lambda visit, successor, parent: successor})):
            patched = patch('bilqis_mlx.runtime.outcomes.issuance.' + name, **behavior)
            patched.start()
            self.addCleanup(patched.stop)

    def test_accepted_visit_persists_native_resource_observation(self):
        with TemporaryDirectory() as temporary:
            prepared, successor, derive, evidence = _prepare_native_resource_visit(temporary)
        self.assertIs(prepared.successor, successor)
        event = derive.call_args.kwargs["delivery_events"][0]
        self.assertEqual(event["event"], "BAMF_C16_3_ACCEPTED")
        resource = event["resource"]
        self.assertEqual(resource["schema"], "bilqis.bamf.c16.3-resource-observation/v2")
        self.assertEqual(resource["candidate_identity_full_computations"], 0)
        self.assertEqual(resource["candidate_identity_numerical_bytes_hashed"], 0)
        self.assertEqual(resource["memory_budget_bytes"], 64 * 1024 ** 3)
        self.assertGreater(resource["disk_used_bytes"], 0)
        self.assertEqual(resource["optimizer_steps"], 1)
        self.assertEqual(resource["wall_seconds"], 30.0)
        self.assertEqual(resource["evidence_bytes_written"], 300)
        self.assertEqual(resource["evidence_file_fsyncs"], 1)
        self.assertEqual(resource["evidence_directory_fsyncs"], 1)
        self.assertEqual(resource["evidence_objects"], 4)
        self.assertEqual(resource["evidence_persistence_seconds"], 0.005)
        self.assertEqual(event["candidate_evidence"], evidence)

    def test_execution_context_uses_accepted_release_without_requiring_c07_lease(self):
        parent = object()
        context = SimpleNamespace()
        host = SimpleNamespace(source_context=lambda **_kwargs: context)
        authenticated = SimpleNamespace(
            features="features", construction_predecessor="predecessor",
            selection=SimpleNamespace(path="/atlas"),
            feature_artifact_path="/feature")
        with patch(
                "bilqis_mlx.runtime.bamf_operator.session_parts.session_support.load_accepted_generation",
                return_value=parent), patch(
                "bilqis_mlx.runtime.bamf_operator.session_parts.session_support.AcceptedRuntimeHost",
                return_value=host), patch(
                "bilqis_mlx.runtime.bamf_operator.session_parts.session_support.bind_accepted_execution_feature_context",
                return_value=authenticated):
            self.assertEqual(
                _execution_context(Path("/run")),
                (parent, context, "/atlas", "/feature"))
        self.assertIs(context._accepted_feature_context, authenticated)

    def test_recovery_exhaustion_rearms_same_grade_without_certification(self):
        parent = object()
        context = object()
        authorization = object()
        lawful_frontier = object()
        selection = SimpleNamespace(
            status="HELD",
            metadata={"cadence": {"disposition": "RECOVERY_EXHAUSTED"}},
            holds=(),
            exclusions=(),
        )
        progress = []

        with patch(
                "bilqis_mlx.runtime.grade_certification.run_grade_boundary_certification",
                return_value=SimpleNamespace(status="SUCCEEDED")) as certify, patch(
                "bilqis_mlx.runtime.accepted_priority_visit_contracts."
                "require_priority_cadence_authorization",
                return_value=authorization), patch(
                "bilqis_mlx.runtime.accepted_priority_visit_contracts."
                "require_priority_lawful_frontier",
                return_value=lawful_frontier), patch(
                "bilqis_mlx.runtime.active_grade_cadence."
                "rearm_active_grade_acquisition") as rearm:
            prepared = priority_hold_result(
                Path("/run"), selection, context, parent, Path("/atlas"), 0.0,
                progress.append,
                emit_progress=lambda sink, message: sink(message),
            )

        self.assertEqual(prepared.status, "ACQUISITION_REARMED")
        self.assertIs(prepared.parent, parent)
        rearm.assert_called_once_with(
            Path("/run"), authorization, lawful_frontier)
        certify.assert_not_called()
        self.assertIn(
            "active grade recovery exhausted; rearmed ordinary MAIN acquisition",
            progress,
        )

    def test_genuine_current_grade_hold_remains_terminal(self):
        parent = object()
        selection = SimpleNamespace(
            status="HELD",
            metadata={"cadence": {"disposition": "HELD"}},
            holds=(("A.BLOCKED", "SOURCE_HELD"),),
            exclusions=(),
        )

        with patch(
                "bilqis_mlx.runtime.grade_certification.run_grade_boundary_certification") as certify, patch(
                "bilqis_mlx.runtime.active_grade_cadence."
                "rearm_active_grade_acquisition") as rearm:
            prepared = priority_hold_result(
                Path("/run"), selection, object(), parent, Path("/atlas"), 0.0,
                None, emit_progress=lambda _sink, _message: None,
            )

        self.assertEqual(prepared.status, "HELD")
        self.assertIs(prepared.parent, parent)
        certify.assert_not_called()
        rearm.assert_not_called()

    def test_successful_grade_completion_refreshes_a09_only_at_boundary_before_c07(self):
        parent = object()
        context = object()
        selection = SimpleNamespace(
            status="HELD",
            metadata={"cadence": {"disposition": "GRADE_COMPLETE"}},
            holds=(),
            exclusions=(),
        )
        progress = []
        order = []
        evidence = SimpleNamespace(
            measured=2, passed=2, final_action="QUALIFICATION")

        with patch(
                "bilqis_mlx.runtime.grade_certification.run_grade_boundary_certification",
                return_value=SimpleNamespace(
                    status="SUCCEEDED",
                    receipt=SimpleNamespace(receipt_sha256="c" * 64))), patch(
                "bilqis_mlx.runtime.bamf_operator.accepted_learning_evidence."
                "refresh_accepted_learning_evidence",
                side_effect=lambda *_args, **_kwargs: (
                    order.append("A09") or evidence)) as refresh, patch(
                "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
                "adopt_and_activate_certified_successor",
                side_effect=lambda *_args, **_kwargs: (
                    order.append("C07") or True)) as adopt:
            prepared = priority_hold_result(
                Path("/run"), selection, context, parent, Path("/atlas"), 0.0,
                progress.append,
                emit_progress=lambda sink, message: sink(message),
            )

        self.assertEqual(prepared.status, "GRADE_TRANSITIONED")
        self.assertEqual(order, ["A09", "C07"])
        refresh.assert_called_once_with(Path("/run"), progress=progress.append)
        adopt.assert_called_once_with(
            Path("/run"), context,
            certification_receipt_sha256="c" * 64,
            reserve_gib=0.0,
        )
        self.assertIn(
            "grade boundary learner evidence refresh: 2 measured, 2 passed; next QUALIFICATION",
            progress,
        )
