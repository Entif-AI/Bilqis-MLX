"""Accepted-run C09 operator-composition correction custody."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import (
    record_accepted_correction, record_accepted_revalidation,
    register_solve_context,
)
from bilqis_mlx.runtime.atlas_revalidation import RevalidationFrontier
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_correction_authority
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _SOURCE_OWNER, _TEST_PUBLIC, _event, _result, _sign_event,
)
from bilqis_mlx.runtime.tests.capability.factory.solver_helpers import _fixture
from bilqis_mlx.runtime.cognitive_solver import (
    NeuralProposal, QualifiedComposition, SolveContext, solve_task,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.domains import contract_digest


SYNTHETIC_SOURCE_AUTHORITY = SourceAuthorityRegistry((
    SourceAuthorityKey(
        _SOURCE_OWNER,
        _TEST_PUBLIC,
        (SourceAuthorityScope(DependencyKind.SOURCE, "synthetic:"),),
    ),
))


class AcceptedCorrectionCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_bamf_generation(
                self.run, source, acceptance=acceptance(source))

    def _composition_context(self, count):
        binding, generation, _budget, add, _ambiguous = _fixture()
        first = QualifiedComposition(
            add, generation.source_binding_digest, generation.generation_digest,
            binding.frontier.rights_epoch, binding.frontier.correction_generation,
            "a" * 64)
        compositions = tuple(
            first if index == 0 else replace(
                first, qualification_receipt_sha256=chr(98 + index - 1) * 64)
            for index in range(count))
        return binding, SolveContext(
            binding, qualified_compositions=compositions,
            qualification_verifier=lambda item: True), compositions

    def _concurrent_corrections(self, binding):
        dependency = DependencyRef(
            DependencyKind.SOURCE,
            "source:binding:" + contract_digest(binding),
        )
        first = _event(dependency)
        second = _sign_event(replace(
            first,
            event_id="correction:synthetic:2",
            source_receipt_sha256="e" * 64,
            old_evidence_sha256="b" * 64,
            new_evidence_sha256="c" * 64,
            recorded_at=631,
            source_signature_hex="0" * 128,
        ))
        return first, second

    def _record_equal_revalidation(self, owner, composition, correction):
        node = owner.node_for(composition)
        with shape_patch():
            return record_accepted_revalidation(
                self.run,
                _result(
                    node, digest=node.content_digest,
                    correction=correction),
                AUTHORITY,
            )

    def test_correction_seen_before_composition_exists_holds_later_materialization(self):
        self.publish(candidate(parent_state()))
        binding, generation, _budget, add, _ambiguous = _fixture()
        context = SolveContext(binding)
        with shape_patch():
            bind_accepted_correction_authority(self.run, AUTHORITY)
            register_solve_context(self.run, context, AUTHORITY)
        dependency = DependencyRef(
            DependencyKind.SOURCE, "source:binding:" + contract_digest(binding))
        correction = _event(dependency)
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
        owner = context.operator_composition_artifact_owner
        self.assertIsNone(owner.queue)
        learned = QualifiedComposition(
            add, generation.source_binding_digest, generation.generation_digest,
            binding.frontier.rights_epoch, binding.frontier.correction_generation,
            "b" * 64)
        self.assertTrue(owner.remember(learned, binding))
        self.assertEqual(owner.queue.event.event_id, correction.event_id)
        with self.assertRaises(BilqisError):
            owner.require(learned, binding)

    def test_neural_answer_cannot_escape_accepted_hold_installed_during_retention(self):
        self.publish(candidate(parent_state()))
        binding, generation, budget, add, ambiguous = _fixture()

        def neural(request):
            return NeuralProposal(
                add, request.source_binding_digest, request.generation_digest,
                request.unresolved_signature, "c" * 64)

        context = SolveContext(binding, neural_proposer=neural)
        with shape_patch():
            bind_accepted_correction_authority(self.run, AUTHORITY)
            register_solve_context(self.run, context, AUTHORITY)
        correction = _event(DependencyRef(
            DependencyKind.SOURCE,
            "source:binding:" + contract_digest(binding)))
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
        self.assertIsNone(context.operator_composition_artifact_owner.queue)

        with self.assertRaises(BilqisError) as caught:
            solve_task(ambiguous, context, generation, budget)
        self.assertEqual(
            caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")
        owner = context.operator_composition_artifact_owner
        retained = owner.compositions
        self.assertEqual(len(retained), 1)
        self.assertIn(
            owner.node_for(retained[0]).artifact_id,
            owner.queue.held_artifact_ids)

    def test_real_source_operand_correction_holds_operator_composition(self):
        self.publish(candidate(parent_state()))
        binding, context, compositions = self._composition_context(1)
        source_reference = binding.operands[0].source_reference
        with shape_patch():
            bind_accepted_correction_authority(
                self.run, SYNTHETIC_SOURCE_AUTHORITY)
            register_solve_context(
                self.run, context, SYNTHETIC_SOURCE_AUTHORITY)
            correction = _event(DependencyRef(
                DependencyKind.SOURCE, source_reference))
            record_accepted_correction(
                self.run, correction, SYNTHETIC_SOURCE_AUTHORITY)

        owner = context.operator_composition_artifact_owner
        self.assertIsNotNone(owner.queue)
        self.assertEqual(owner.queue.event.event_id, correction.event_id)
        with self.assertRaises(BilqisError) as caught:
            owner.require(compositions[0], binding)
        self.assertEqual(caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")

    def test_operator_composition_declares_direct_policy_and_time_premises(self):
        binding, context, compositions = self._composition_context(1)
        node = context.operator_composition_artifact_owner.node_for(compositions[0])
        refs = set(node.immediate_dependencies)
        self.assertIn(DependencyRef(
            DependencyKind.POLICY,
            "policy:" + contract_digest((
                binding.task.scope,
                binding.policy.policy_id,
                binding.policy.policy_epoch,
            )),
        ), refs)
        self.assertIn(DependencyRef(
            DependencyKind.TIME,
            "time:observed-frontier:" + str(binding.task.observed_frontier),
        ), refs)
        self.assertIn(DependencyRef(
            DependencyKind.TIME,
            "time:effective:" + str(binding.task.effective_time),
        ), refs)
        self.assertIn(DependencyRef(
            DependencyKind.TIME,
            "time:causal-prefix-end:" + str(binding.task.causal_prefix_end),
        ), refs)

    def test_multi_result_frontier_consumes_every_applicable_held_artifact(self):
        self.publish(candidate(parent_state()))
        binding, context, compositions = self._composition_context(2)
        with shape_patch():
            bind_accepted_correction_authority(self.run, AUTHORITY)
            register_solve_context(self.run, context, AUTHORITY)
        correction = _event(DependencyRef(
            DependencyKind.SOURCE, "source:binding:" + contract_digest(binding)))
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
        owner = context.operator_composition_artifact_owner
        results = tuple(sorted((
            _result(owner.node_for(item), digest=owner.node_for(item).content_digest,
                    correction=correction).results[0]
            for item in compositions), key=lambda item: item.artifact_id))
        with shape_patch():
            record_accepted_revalidation(
                self.run, RevalidationFrontier(results), AUTHORITY)
        self.assertEqual(owner.queue.held_artifact_ids, ())

    def test_deferred_frontier_remembers_partial_consumption_across_retry(self):
        self.publish(candidate(parent_state()))
        binding, context, _compositions = self._composition_context(3)
        with shape_patch():
            bind_accepted_correction_authority(self.run, AUTHORITY)
            register_solve_context(self.run, context, AUTHORITY)
        correction = _event(DependencyRef(
            DependencyKind.SOURCE, "source:binding:" + contract_digest(binding)))
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
        owner = context.operator_composition_artifact_owner
        task_ids = tuple(task.artifact_id for task in owner.queue.pending)
        by_id = {
            item.artifact_id: _result(
                item, digest=item.content_digest, correction=correction).results[0]
            for item in owner.index.nodes
        }
        with shape_patch():
            first_event = record_accepted_revalidation(
                self.run,
                RevalidationFrontier((by_id[task_ids[0]], by_id[task_ids[2]])),
                AUTHORITY)
        target = owner._accepted_correction_target
        self.assertIn(first_event, target.deferred)
        with shape_patch():
            record_accepted_revalidation(
                self.run, RevalidationFrontier((by_id[task_ids[1]],)), AUTHORITY)
        self.assertNotIn(first_event, target.deferred)
        self.assertIn(first_event, target.seen)
        self.assertEqual(owner.queue.held_artifact_ids, ())

    def test_same_logical_artifact_owners_all_remain_live_for_later_correction(self):
        self.publish(candidate(parent_state()))
        binding, first_context, compositions = self._composition_context(1)
        second_context = SolveContext(
            binding, qualified_compositions=compositions,
            qualification_verifier=lambda item: True)
        with shape_patch():
            bind_accepted_correction_authority(self.run, AUTHORITY)
            register_solve_context(self.run, first_context, AUTHORITY)
            register_solve_context(self.run, second_context, AUTHORITY)
        dependency = DependencyRef(
            DependencyKind.SOURCE,
            "source:binding:" + contract_digest(binding),
        )
        correction = _event(dependency)

        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)

        for context in (first_context, second_context):
            owner = context.operator_composition_artifact_owner
            self.assertIsNotNone(owner.queue)
            self.assertEqual(owner.queue.event.event_id, correction.event_id)
            with self.assertRaises(BilqisError):
                owner.require(compositions[0], binding)

    def test_late_materialization_rechecks_all_active_concurrent_branches(self):
        self.publish(candidate(parent_state()))
        binding, context, compositions = self._composition_context(1)
        with shape_patch():
            bind_accepted_correction_authority(self.run, AUTHORITY)
            register_solve_context(self.run, context, AUTHORITY)
        correction_a, correction_b = self._concurrent_corrections(binding)
        owner = context.operator_composition_artifact_owner

        with shape_patch():
            record_accepted_correction(self.run, correction_a, AUTHORITY)
        self._record_equal_revalidation(
            owner, compositions[0], correction_a)
        with shape_patch():
            record_accepted_correction(self.run, correction_b, AUTHORITY)
        self._record_equal_revalidation(
            owner, compositions[0], correction_b)
        self.assertEqual(owner.queue.held_artifact_ids, ())

        _binding, generation, _budget, add, _ambiguous = _fixture()
        learned = QualifiedComposition(
            add, generation.source_binding_digest, generation.generation_digest,
            binding.frontier.rights_epoch, binding.frontier.correction_generation,
            "f" * 64)
        self.assertTrue(owner.remember(learned, binding))
        with self.assertRaises(BilqisError) as held:
            owner.require(learned, binding)
        self.assertEqual(
            held.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")
        target = owner._accepted_correction_target
        self.assertTrue(any(
            event.event_id == correction_a.event_id
            for event in target.pending
        ) or (
            owner.queue is not None
            and owner.queue.event.event_id == correction_a.event_id
        ))
        for correction in (correction_a, correction_b):
            if (owner.queue is None
                    or owner.queue.event.event_id != correction.event_id):
                continue
            self._record_equal_revalidation(owner, learned, correction)
        if owner.queue is not None and owner.queue.pending:
            self._record_equal_revalidation(
                owner, learned, owner.queue.event)
        self.assertIsNotNone(owner.require(learned, binding))
        learned_artifact_id = (
            "composition:" + learned.qualification_receipt_sha256)
        self.assertIn(
            learned_artifact_id,
            owner._accepted_correction_target.branch_reconciled_artifacts[
                correction_a.event_id],
        )
        self.assertIn(
            learned_artifact_id,
            owner._accepted_correction_target.branch_reconciled_artifacts[
                correction_b.event_id],
        )
