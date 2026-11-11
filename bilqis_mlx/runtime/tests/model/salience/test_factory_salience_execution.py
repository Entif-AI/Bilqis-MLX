"""Real A01/A05/C02/B13 inputs carry signed fixture labels into B11."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.learning.atlas_salience import derive_salience, verify_salience_inputs
from bilqis_mlx.learning.salience_contracts import AuthoritySnapshot, Metric
from bilqis_mlx.learning.tests.test_atlas_salience import _CONTEXT, _policy, _fact, _signed
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.factory_candidate_training import (
    FactoryDeliveryObservation, execute_factory_candidate_step,
)
from bilqis_mlx.runtime.salience_auxiliaries import RowSalienceBinding
from bilqis_mlx.runtime.salience_training import SalienceLabelRequest
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture, store_sidecar
from bilqis_mlx.runtime.tests.batch.factory.factory_training_bridge_support import FactoryTrainingBridgeFixture
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import HP
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, provision_source_authority_registry, with_source_authority_registry,
)
from bilqis_mlx.runtime.tests.model.test_salience_auxiliaries import _REGISTRY as SALIENCE_REGISTRY
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY
from bilqis_mlx.semantics.domains import contract_digest


REGISTRY = SourceAuthorityRegistry(tuple(sorted((*AUTHORITY.keys, *SALIENCE_REGISTRY.keys),
                                              key=lambda key: key.owner_id)))


class FactorySalienceExecutionTests(FactoryTrainingBridgeFixture):
    def _provider(self, prepared):
        batch = prepared.training_batch
        row = batch.rows[0]
        context = replace(_CONTEXT, semantic_release=batch.release_sha256,
            generation_digest=batch.generation_binding,
            capability_id=row.provenance.capability_id,
            source_family_id=row.provenance.source_family_id,
            source_binding_digest=contract_digest(self.context.release.source_bindings.by_capability[
                row.provenance.capability_id]))
        snapshot = AuthoritySnapshot((context,), 100, REGISTRY)
        policy = _signed(replace(_policy(), semantic_release=batch.release_sha256,
                                 source_family_ids=(context.source_family_id,)))
        evidence = derive_salience(verify_salience_inputs((
            _fact(Metric.DECLARED_IMPACT, 2, policy, context=context),
            _fact(Metric.BLOCKED_COUNT, 0, policy, context=context),
        ), policy, snapshot, context))
        binding = _signed(RowSalienceBinding.for_row(batch, row, evidence,
            source_owner='fixture:salience-owner', signature_hex='0' * 128))
        return SalienceLabelRequest(((binding, evidence),), snapshot, lambda *args: False)

    def test_real_factory_step_uses_present_heads_and_preserves_missing_head(self):
        capability, seed = 'B.IDBOOLOPS', 37901
        rows = tuple(self.context.draw_rows(seed=seed, capability=capability, each=1))
        execution = self.context.release.execution_plan.capability_map[capability]
        delivery = describe_delivered_teaching(self.context.release, capability,
                                               execution.teaching_option_ids[0], rows)
        with TemporaryDirectory() as run_value:
            run_dir = Path(run_value)
            provision_source_authority_registry(run_dir, REGISTRY)
            candidate = with_source_authority_registry(self.candidate, REGISTRY)
            with patch('bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom', return_value=None):
                publish_bamf_generation(run_dir, candidate, acceptance=acceptance(candidate))
            context = self.accepted_source_context(run_dir)
            parent = load_accepted_generation(run_dir)
            capture = ObservationCapture(run_dir, {})
            capture.attempt_id = 'c06-salience-disposable'
            capture.proposal_id = store_sidecar(run_dir, {'attempt_id': capture.attempt_id})['sha256']
            capture.select_option(capability, None)
            result = execute_factory_candidate_step(
                run_dir, context, parent, str(self.artifact), self.feature_receipt.path, rows,
                capability=capability, delivery=delivery, requested_count=3, source_seed=seed,
                source_each=1, optimizer_step_seed=379,
                visit_provenance=visit_provenance(capability),
                teacher_strategy={'policy': 'c06-disposable-proof'}, teacher_hparams=HP,
                max_norm=1.0, observation=FactoryDeliveryObservation(capture, 1, rows, seed),
                salience_provider=self._provider)
            loss = result.gradient_execution.execution.loss
            self.assertGreater(float(loss.impact), 0.)
            self.assertGreater(float(loss.exigency), 0.)
            self.assertEqual(float(loss.novelty), 0.)
            gradients = result.gradient_execution.gradients
            for name in ('impact', 'exigency'):
                self.assertGreater(float(mx.abs(gradients['readout.salience_bias.' + name]).sum()), 0.)
            self.assertEqual(float(mx.abs(gradients['readout.salience_bias.novelty']).sum()), 0.)
            census = result.gradient_execution.execution.dense_parameter_names
            self.assertIn('readout.salience.impact', census)
            self.assertNotIn('readout.salience.novelty', census)
            self.assertEqual(result.transaction.update_steps, 1)
            self.assertEqual(parent.retained_state.optimizer_step, 0)
            self.assertEqual(load_accepted_generation(run_dir).generation, parent.generation)
