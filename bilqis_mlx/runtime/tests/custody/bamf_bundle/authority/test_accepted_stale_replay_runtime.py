"""Accepted-run production ingress for post-remediation stale replay faults."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import (
    record_accepted_correction, record_accepted_derived_claim,
    record_accepted_remediation, record_accepted_revalidation,
    register_solve_context,
)
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.cognitive_solver import QualifiedComposition, SolveContext
from bilqis_mlx.runtime.tests.capability.factory.solver_helpers import _fixture
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _result,
)
from bilqis_mlx.runtime.atlas_stale_replay import (
    DerivedClaim, RemediationReceipt, RemediationStatus,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.domains import contract_digest


class AcceptedStaleReplayRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()
        source = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            publish_bamf_generation(
                self.run, source, acceptance=acceptance(source))

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def test_post_remediation_stale_claim_enters_accepted_runtime_and_blocks_reuse(self):
        binding, generation, _budget, add, _ambiguous = _fixture()
        cached = QualifiedComposition(
            add, generation.source_binding_digest, generation.generation_digest,
            binding.frontier.rights_epoch, binding.frontier.correction_generation,
            "a" * 64)
        context = SolveContext(
            binding, qualified_compositions=(cached,),
            qualification_verifier=lambda item: True)
        with shape_patch():
            register_solve_context(self.run, context, AUTHORITY)
        dependency = DependencyRef(
            DependencyKind.SOURCE,
            "source:binding:" + contract_digest(binding),
        )
        correction = _event(dependency)
        owner = context.operator_composition_artifact_owner
        node = owner.node_for(cached)
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
            record_accepted_revalidation(
                self.run,
                _result(node, digest=node.content_digest, correction=correction),
                AUTHORITY,
            )
        self.assertEqual(owner.require(cached, binding), node)

        remediation = RemediationReceipt(
            remediation_id="remediation:accepted-runtime",
            correction_event_id=correction.event_id,
            correction_receipt_sha256=correction.source_receipt_sha256,
            original_actor_id="actor:accepted-runtime",
            original_source_event_id="event:planned",
            original_source_time=570,
            superseded_fact_digest="a" * 64,
            superseded_source_receipt_sha256="1" * 64,
            affected_artifact_ids=(node.artifact_id,),
            retained_generation_sha256="9" * 64,
            completed_at=650,
            status=RemediationStatus.COMPLETED,
        )
        stale = DerivedClaim(
            claim_id="claim:accepted-runtime-stale",
            actor_id="actor:accepted-runtime",
            source_event_id="event:planned",
            source_time=570,
            source_receipt_sha256="1" * 64,
            fact_digest="a" * 64,
            observed_at=660,
            derived_path=(node.artifact_id,),
        )
        with shape_patch():
            record_accepted_remediation(self.run, remediation, AUTHORITY)
            _event_id, faults = record_accepted_derived_claim(
                self.run, stale, AUTHORITY)
        self.assertEqual(len(faults), 1)
        self.assertEqual(
            faults[0].fault.reason_code,
            "BAMF_C09_PROPAGATION_REPAIR_FAILED",
        )
        with self.assertRaises(BilqisError) as caught:
            owner.require(cached, binding)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_PROPAGATION_REPAIR_FAILED",
        )

    def test_independent_later_evidence_is_not_classified_as_stale_replay(self):
        binding, generation, _budget, add, _ambiguous = _fixture()
        cached = QualifiedComposition(
            add, generation.source_binding_digest, generation.generation_digest,
            binding.frontier.rights_epoch, binding.frontier.correction_generation,
            "a" * 64)
        context = SolveContext(
            binding, qualified_compositions=(cached,),
            qualification_verifier=lambda item: True)
        with shape_patch():
            register_solve_context(self.run, context, AUTHORITY)
        dependency = DependencyRef(
            DependencyKind.SOURCE,
            "source:binding:" + contract_digest(binding),
        )
        correction = _event(dependency)
        owner = context.operator_composition_artifact_owner
        node = owner.node_for(cached)
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
            record_accepted_revalidation(
                self.run,
                _result(node, digest=node.content_digest, correction=correction),
                AUTHORITY,
            )
            record_accepted_remediation(
                self.run,
                RemediationReceipt(
                    remediation_id="remediation:accepted-runtime-independent",
                    correction_event_id=correction.event_id,
                    correction_receipt_sha256=correction.source_receipt_sha256,
                    original_actor_id="actor:accepted-runtime",
                    original_source_event_id="event:planned",
                    original_source_time=570,
                    superseded_fact_digest="a" * 64,
                    superseded_source_receipt_sha256="1" * 64,
                    affected_artifact_ids=(node.artifact_id,),
                    retained_generation_sha256="9" * 64,
                    completed_at=650,
                    status=RemediationStatus.COMPLETED,
                ),
                AUTHORITY,
            )
            _event_id, faults = record_accepted_derived_claim(
                self.run,
                DerivedClaim(
                    claim_id="claim:accepted-runtime-independent",
                    actor_id="actor:later-independent",
                    source_event_id="event:later-independent",
                    source_time=720,
                    source_receipt_sha256="2" * 64,
                    fact_digest="a" * 64,
                    observed_at=725,
                    derived_path=(node.artifact_id,),
                ),
                AUTHORITY,
            )
        self.assertEqual(faults, ())
        self.assertEqual(owner.require(cached, binding), node)


if __name__ == "__main__":
    unittest.main()
