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
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_correction_authority
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _result,
)
from bilqis_mlx.runtime.tests.capability.factory.solver_helpers import _fixture
from bilqis_mlx.runtime.cognitive_solver import QualifiedComposition, SolveContext
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.domains import contract_digest


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
