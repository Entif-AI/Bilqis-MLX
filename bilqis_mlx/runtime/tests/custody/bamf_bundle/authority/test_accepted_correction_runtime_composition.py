"""Accepted-run C09 operator-composition custody and late materialization."""
from dataclasses import replace
from types import SimpleNamespace

from bilqis_mlx.curriculum import AnswerFamily, BINARY
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import (
    record_accepted_correction, register_solve_context,
)
from bilqis_mlx.runtime.accepted_correction_ledger import (
    append_record, context_invalidation_record,
)
from bilqis_mlx.runtime.accepted_correction_runtime import runtime
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_correction_authority, bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.authority.accepted_correction_runtime_composition_support import (
    AUTHORITY, SYNTHETIC_SOURCE_AUTHORITY, AcceptedCorrectionCompositionCase,
    _event,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.authority.accepted_correction_runtime_temporal_support import (
    source_owned_temporal_case,
)
from bilqis_mlx.runtime.tests.capability.factory.solver_helpers import _fixture
from bilqis_mlx.runtime.cognitive_solver import (
    NeuralProposal, QualifiedComposition, SolveContext, solve_task,
)
from bilqis_mlx.source_adapters.answer_choice_task_goal import (
    lower_answer_choice_task_goal,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.domains import contract_digest


class AcceptedCorrectionCompositionTests(AcceptedCorrectionCompositionCase):
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

    def test_context_invalidation_seen_before_composition_holds_later_materialization(self):
            self.publish(candidate(parent_state()))
            original_binding, generation, _budget, add, _ambiguous = _fixture()
            case = source_owned_temporal_case()
            binding = replace(
                original_binding,
                task=case.task,
                frontier=case.frontier,
                policy=case.policy,
                frames=case.frames,
            )
            context = SolveContext(binding)
            with shape_patch():
                bind_accepted_correction_authority(self.run, AUTHORITY)
                register_solve_context(self.run, context, AUTHORITY)
            owner = context.operator_composition_artifact_owner
            invalidation = self._context_invalidation(case, "e" * 64)
            # Persist through the same accepted-run ledger/dispatch path used in production.
            from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
            with shape_patch():
                accepted_cache = bind_accepted_execution_cache(self.run)
            record = context_invalidation_record(
                accepted_cache.accepted_manifest_sha256, invalidation)
            append_record(self.run, accepted_cache.accepted_manifest_sha256, record)
            runtime(self.run, accepted_cache.accepted_manifest_sha256).deliver_context_invalidation(
                record["event_id"], invalidation)
            target = owner._accepted_correction_target
            self.assertEqual(target.context_queues, {})
            self.assertIn(invalidation.event_id, target.context_invalidations)

            learned = QualifiedComposition(
                add,
                contract_digest(binding),
                generation.generation_digest,
                binding.frontier.rights_epoch,
                binding.frontier.correction_generation,
                "d" * 64,
            )
            self.assertTrue(owner.remember(learned, binding))
            old_context = DependencyRef(
                DependencyKind.TIME,
                "time:asof:context:" + case.previous.digest,
            )
            self.assertIn(old_context, owner.node_for(learned).immediate_dependencies)
            with self.assertRaises(BilqisError) as caught:
                owner.require(learned, binding)
            self.assertEqual(
                caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")

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

    def test_answer_choice_source_correction_holds_operator_composition(self):
            self.publish(candidate(parent_state()))
            capability = SimpleNamespace(
                capability_id="A.IDENTITY",
                answer_families=(AnswerFamily("binary", BINARY),),
            )
            source_id = "synthetic:answer-premise"
            goal, binding = lower_answer_choice_task_goal(
                {
                    "id": "answer-row-1",
                    "source_id": source_id,
                    "capability": capability.capability_id,
                    "tokens": [1],
                },
                semantic_release="a" * 64,
                capability=capability,
            )
            _fixture_binding, generation, _budget, _add, _ambiguous = _fixture()
            composition = QualifiedComposition(
                goal,
                contract_digest(binding),
                generation.generation_digest,
                binding.frontier.rights_epoch,
                binding.frontier.correction_generation,
                "9" * 64,
            )
            context = SolveContext(
                binding,
                qualified_compositions=(composition,),
                qualification_verifier=lambda item: True,
            )
            with shape_patch():
                bind_accepted_correction_authority(
                    self.run, SYNTHETIC_SOURCE_AUTHORITY)
                register_solve_context(
                    self.run, context, SYNTHETIC_SOURCE_AUTHORITY)
                correction = _event(DependencyRef(
                    DependencyKind.SOURCE, source_id))
                record_accepted_correction(
                    self.run, correction, SYNTHETIC_SOURCE_AUTHORITY)

            owner = context.operator_composition_artifact_owner
            self.assertIn(
                DependencyRef(DependencyKind.SOURCE, source_id),
                owner.node_for(composition).immediate_dependencies,
            )
            with self.assertRaises(BilqisError) as caught:
                owner.require(composition, binding)
            self.assertEqual(
                caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")
