"""Shared fixture support for capability-only Atlas v2 tests."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_delta_adapter_fixtures import (
    AtlasDeltaAdapterFixture,
)
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.runtime.atlas_admission import (
    AtlasSourceApproval,
    ResourceCeilingV2,
    adopt_capability_only_atlas_successor_v2,
    advance_atlas_frontier_v2,
    issue_atlas_lease_v2,
)
from bilqis_mlx.runtime.atlas_admission_policy import (
    AdmissionResult,
    AdmissionStatus,
    AtlasAdmissionContext,
)
from bilqis_mlx.runtime.atlas_admission_policy_v2 import (
    AtlasAdmissionContextV2,
    AtlasDeltaEnvelopeV2,
    AtlasDerivedAdmissionFactsV2,
)
from bilqis_mlx.runtime.tests.admission.atlas.atlas_adoption_executor_support import (
    AtlasAdoptionExecutorFixture,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _REGISTRY,
    _run,
)
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
from bilqis_mlx.runtime.atlas_capability_adoption_v2 import (
    accepted_capability_only_retry_v2,
    publish_capability_only_factory_successor,
)


class CapabilityV2Support(AtlasDeltaAdapterFixture):
    def _lease_authority(self, handoff):
        approval = _signed(replace(
            AtlasSourceApproval(
                "fixture-v2-capability",
                handoff.receipt.selection_snapshot.semantic_release,
                handoff.family_ids,
                handoff.operator_ids,
                "b" * 64,
                1,
                "c" * 64,
                "d" * 64,
                "e" * 64,
                True,
                True,
                "fixture:salience-owner",
                "0" * 128,
            ),
            signature_hex="0" * 128,
        ))
        lease = issue_atlas_lease_v2(
            "fixture-v2-capability-lease",
            _run(),
            approval,
            ResourceCeilingV2(4, 4, 32768, 1 << 40, 1 << 40),
            requested_at="2026-11-10T18:00:00Z",
            human_command_sha256="9" * 64,
            human_started=True,
            registry=_REGISTRY,
        )
        return approval, lease

    def _context(self, handoff, approval):
        checkpoint = Checkpoint(
            self.learner.checkpoint_sha256,
            "bundles/z-c6-capability-only",
            self.learner.optimizer_step,
            True,
        )
        legacy = AtlasAdmissionContext(
            _run(),
            handoff.receipt.predecessor_release,
            handoff.candidate_frontier,
            self.learner.ledger,
            self.plan,
            checkpoint,
            approval,
            _REGISTRY,
            self.staging.fixture.fixture.registry,
            self.staging.fixture.fixture.answers,
        )
        return AtlasAdmissionContextV2(legacy, Path("/accepted/run"))
