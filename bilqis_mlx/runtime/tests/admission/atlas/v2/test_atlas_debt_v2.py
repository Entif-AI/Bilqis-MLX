"""Current C07 debt/policy projection from A09 handoff plus accepted B13 release."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.runtime.atlas_debt_v2 import read_current_atlas_debt_policy
from bilqis_mlx.runtime.tests.admission.atlas.v2.policy_support import PolicyV2Support


class CurrentAtlasDebtV2Tests(PolicyV2Support):
    @staticmethod
    def _with_debt(handoff, capability_id):
        snapshot = rehash(
            handoff.receipt.selection_snapshot,
            retained_mastery_debt=(capability_id,),
            retained_debt_source_sha256="d" * 64,
        )
        selection = replace(
            handoff.receipt.selection,
            snapshot_sha256=snapshot.snapshot_sha256,
            selection_sha256="0" * 64,
        )
        selection = replace(selection, selection_sha256=selection.expected_digest())
        receipt = replace(
            handoff.receipt,
            selection=selection,
            selection_snapshot=snapshot,
            receipt_sha256="0" * 64,
        )
        receipt = replace(receipt, receipt_sha256=receipt.expected_digest())
        changed = replace(handoff, receipt=receipt, handoff_sha256="0" * 64)
        return replace(changed, handoff_sha256=changed.expected_digest())

    def test_current_view_maps_debt_to_actual_grades_and_policy_epoch(self):
        _capability, _semantic_id, handoff, _plan, _ledger, _checkpoint = self._event_handoff()
        predecessor = handoff.receipt.predecessor_release
        debt_capability = predecessor.execution_plan.capabilities[0].capability_id
        handoff = self._with_debt(handoff, debt_capability)
        grade = predecessor.execution_plan.capability_map[debt_capability].grade_id

        with patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                return_value=predecessor):
            result = read_current_atlas_debt_policy(Path("/accepted/run"), handoff)

        self.assertIn((grade, (debt_capability,)), result.grade_debt)
        self.assertEqual(
            tuple(item[0] for item in result.grade_debt),
            tuple(item.grade_id for item in predecessor.execution_plan.grades),
        )
        self.assertEqual(
            result.current_domain_policy.policy_epoch,
            handoff.receipt.selection_snapshot.policy_epoch,
        )
        self.assertEqual(
            result.current_domain_policy.curriculum_sha256,
            predecessor.execution_plan.curriculum_sha256,
        )
        self.assertEqual(
            result.current_domain_policy.source_binding_sha256,
            predecessor.execution_plan.source_binding_sha256,
        )
        self.assertEqual(result.historical_scope_policy_status, "NOT_MEASURED")
        self.assertFalse(result.authorizes_learning)

    def test_accepted_release_substitution_rejects(self):
        _capability, _semantic_id, handoff, _plan, _ledger, _checkpoint = self._event_handoff()
        with patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                return_value=handoff.receipt.staged_successor), self.assertRaises(BilqisError):
            read_current_atlas_debt_policy(Path("/accepted/run"), handoff)
