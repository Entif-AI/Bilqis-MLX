"""Shared fixture support for Atlas admission policy v2 tests."""
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.factory.atlas_frontier import (
    AtlasCoverageEpoch,
    bind_realized_snapshot,
    next_atlas_delta,
)
from bilqis_mlx.factory.atlas_frontier_closure import resolve_frontier_closure
from bilqis_mlx.factory.tests.events.support import EventCandidateRealizationFixture, LEGACY
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionLeaseV2,
    AtlasSourceApproval,
    ResourceCeilingV2,
    adopt_parameter_extension_atlas_successor_v2,
    advance_atlas_frontier_v2,
    issue_atlas_lease_v2,
    persist_atlas_lease_v2,
    renew_atlas_lease_v2,
)
from bilqis_mlx.runtime.atlas_admission_policy import (
    AdmissionResult,
    AdmissionStatus,
    AtlasAdmissionContext,
)
from bilqis_mlx.runtime.atlas_admission_policy_v2 import (
    AtlasAdmissionContextV2,
    AtlasDeltaEnvelopeV2,
)
from bilqis_mlx.runtime.tests.admission.atlas.adoption.atlas_adoption_executor_support import (
    AtlasAdoptionExecutorFixture,
)
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _REGISTRY, _lease, _run,
)
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.source_adapters import event_frames


class PolicyV2Support(EventCandidateRealizationFixture, unittest.TestCase):
    def _event_handoff(self):
        candidate, source_frontier, policy = self.atlas_fixture()
        capability = next(iter(event_frames.SOURCE_SPECS))
        semantic_id = event_frames.atlas_semantic_id(capability)
        staged = candidate_realizations.prepare_realized_candidate(
            self.frontier, self.current, self.parent_graph, semantic_id,
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry)
        snapshot = self.build_snapshot(
            candidate, source_frontier, policy, self.current, staged)
        snapshot = bind_realized_snapshot(
            snapshot, candidate, self.frontier, self.current, (staged,))
        plan, checkpoint_sha256, step, ledger, learner = self.learner_evidence(
            self.current, {"A.IDENTITY"}, capability)
        closure = resolve_frontier_closure(
            snapshot, candidate.census, current_release=self.current,
            evidence_ledger=ledger, autonomy_plan=plan,
            checkpoint_sha256=checkpoint_sha256, optimizer_step=step)
        handoff = next_atlas_delta(
            AtlasCoverageEpoch(
                snapshot=snapshot, closure=closure,
                candidate_frontier=self.frontier,
                current_release=self.current,
                staged_candidates=(staged,), prior=None),
            learner, plan)
        handoff.verify()
        checkpoint = Checkpoint(
            checkpoint_sha256, "bundles/v2-event-owner", step, True)
        return capability, semantic_id, handoff, plan, ledger, checkpoint

    @staticmethod
    def _a02_staged(semantic_id):
        helper = object.__new__(AtlasAdoptionExecutorFixture)
        _parent, candidate = AtlasAdoptionExecutorFixture._native_parent_and_candidate(helper)
        return AtlasAdoptionExecutorFixture._a02_staged(
            helper, candidate, semantic_id=semantic_id)

    def _authority(self, handoff):
        approval = _signed(replace(
            AtlasSourceApproval(
                "fixture-v2-source", "a" * 64,
                handoff.family_ids, handoff.operator_ids,
                "b" * 64, 1, "c" * 64, "d" * 64, "e" * 64,
                True, True, "fixture:salience-owner", "0" * 128),
            signature_hex="0" * 128))
        lease = issue_atlas_lease_v2(
            "fixture-v2", _run(), approval,
            ResourceCeilingV2(4, 4, 32768, 1 << 40, 1 << 40),
            requested_at="2026-11-10T16:00:00Z",
            human_command_sha256="9" * 64, human_started=True,
            registry=_REGISTRY)
        return approval, lease

    def _context(self, handoff, plan, ledger, checkpoint, approval):
        legacy = AtlasAdmissionContext(
            _run(), handoff.receipt.predecessor_release,
            handoff.candidate_frontier, ledger, plan, checkpoint,
            approval, _REGISTRY, self.source_registry, self.answer_registry)
        return AtlasAdmissionContextV2(legacy, Path("/accepted/run"))
