"""Measured fixture evidence through B13 custody into ordinary C03 selection."""
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.learning.teacher_lineage import restore_teacher_lineage
from bilqis_mlx.runtime.accepted_priority_visit import accepted_priority_school
from bilqis_mlx.runtime.bamf_bundle import record_bamf_rejection
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.capability_retention import DecisionStatus
from bilqis_mlx.runtime.foundation_teacher_owner import select_foundation_priority_visit
from bilqis_mlx.runtime.outcomes.issuance import build_outcome
from bilqis_mlx.runtime.tests.capability.factory.owner.adversarial import support as factory_fixture

from .pre_neural_journey_support import (
    PreNeuralJourneySupport, historical_school_release, journey_source,
    portable_atlas_snapshot, wide_shape_patch,
)


def _commit_fixture_rejection(run, parent, selection):
    """Issue a C05 fixture decision without running a neural evaluation."""
    identity = selection.visit.identity
    capability = identity.capability_id
    fixture = list(factory_fixture._foundation_owner_fixture())
    fixture[-1] = replace(
        fixture[-1], status=DecisionStatus.REJECT,
        reason="NO_MEASURABLE_TARGET_GAIN",
        outcome_scores=((capability, 1, 1, 4),))

    def fixture_mock(*args, **kwargs):
        if kwargs.get("return_value") == "d" * 64:
            kwargs["return_value"] = identity.student_sha256
        return Mock(*args, **kwargs)

    with evidence_mode(strict=True), patch.object(
            factory_fixture, "Mock", side_effect=fixture_mock):
        evaluation = factory_fixture._evaluate_foundation_owner(*fixture)
    decision = issue_factory_retention_decision(evaluation)
    outcome = build_outcome(
        run, selection, evaluation, decision, None,
        learning_summary={
            "attempt_id": "previsit-fixture:" + identity.visit_id,
            "candidate_steps": 1, "batch_size": 1, "policy_controls": ({},),
            "guidance_applied_steps": 0, "enrichment_examples": 0,
        })
    step = parent.retained_state.optimizer_step
    record_bamf_rejection(run, parent, {
        "schema": "bilqis.bamf.c16.3-rejection/v2",
        "rejection_attempt_ordinal": 1, "rejection_journal_ordinal": 1,
        "visit_id": identity.visit_id, "teacher_visit": identity.to_record(),
        "selected_option_id": capability, "selected_policy_key": identity.policy_key,
        "candidate_optimizer_step": step + 1, "retained_optimizer_step": step,
        "retention_reason": decision.reason, "capability": capability,
        "decision": decision.to_record(), "candidate_evidence": None,
        "how_outcome": outcome,
    })
    return outcome


class PreNeuralDiagnosticReceiptTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_current_parent_measurement_reaches_native_selection_receipt(self):
        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            pointer = (self.run / "bamf-state.json").read_bytes()
            with self.journey_mounts(
                    snapshot, schema, features, atlas_selection,
                    patch_active_generated_grade=False), evidence_mode(strict=False):
                parent, context, atlas_path, _ = _execution_context(self.run)
                program = schedule_program_from_executable_release(context.release)
                school = accepted_priority_school(parent, program)
                first = select_foundation_priority_visit(
                    self.run, context, atlas_path, program=program, school=school)
                self.assertEqual(first.status, "TEACHER_SELECTED")
                outcome = _commit_fixture_rejection(self.run, parent, first)
                selected = select_foundation_priority_visit(
                    self.run, context, atlas_path, program=program, school=school)

        self.assertEqual(selected.status, "TEACHER_SELECTED")
        self.assertEqual(selected.visit.identity.capability_id,
                         first.visit.identity.capability_id)
        how = selected.metadata["how_context"]
        self.assertEqual(how["diagnostics"]["native_previsit"], {
            "fixed_reference_deficit": None, "target_sample_deficit": True,
            "reference_conflict": False, "structural_debt": None,
        })
        self.assertEqual(how["competence_priority"]["target"]["correct"], 1)
        self.assertEqual(how["competence_priority"]["target"]["outcome_sha256"],
                         outcome["outcome_sha256"])
        self.assertNotEqual(how["diagnostic_context_key"],
                            first.metadata["diagnostic_context_key"])
        teacher = restore_teacher_lineage(
            selected.visit.projection.teacher_state).teacher()
        self.assertEqual(
            teacher["causal_experiment"]["diagnostic_contexts"][
                how["diagnostic_context_key"]], how["diagnostics"])
        self.assertEqual((self.run / "bamf-state.json").read_bytes(), pointer)
