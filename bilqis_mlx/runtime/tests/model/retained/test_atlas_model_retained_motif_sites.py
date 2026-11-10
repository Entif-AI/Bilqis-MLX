"""B08 parent acceptance for both retained motif read sites in the real B11 path."""
from dataclasses import replace
import hashlib
from unittest import TestCase, skipUnless
from unittest.mock import patch
import mlx.core as mx
import numpy as np
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import begin_candidate, resolve_candidate
from bilqis_mlx.learning.atlas_engram import MotifManifest, MotifSlot
from bilqis_mlx.learning.atlas_engram_reads.source_owner import _B13_EXECUTION_SEAL
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, group_eligibility
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, ControlAction, DecisionKind, DecisionOutput, DecisionSpec,
)
from bilqis_mlx.learning.source_atoms.backbone import (
    start_retained_source_backbone_producer, start_source_backbone_producer,
)
from bilqis_mlx.learning.source_atoms.backbone_receipts import QUALIFIED_MISS
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch, bamf_value_and_grad
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.execution_cache import _new_execution_cache
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents
import bilqis_mlx.runtime.atlas_model_forward as forward_impl
import bilqis_mlx.runtime.tests.model.test_atlas_model_retained as retained_tests
from bilqis_mlx.runtime.topology_v2.ledger import bamf_parameter_census
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE
@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class RetainedMotifSiteIntegrationTests(TestCase):
    def _candidate_step(self, case, parameters, manifest, spec, extents, gradient):
        admitted = set(gradient.execution.visible_identity_rows)
        admitted.update(gradient.execution.semantic_denominator_identity_rows)
        ages = tuple(IdentityRowAge(bank, row, 0) for bank, row in sorted(admitted))
        eligibility = group_eligibility(
            "FULL", bamf_parameter_census(spec, extents), ages)
        parent = case._retained_parent(parameters, manifest, spec, extents, ages)
        kwargs = dict(
            group_eligible=eligibility, spec=spec, extents=extents,
            run_id="test-retained", generation=2,
            parent_manifest_sha256="8" * 64,
            parent_candidate_identity_sha256=candidate_identity_digest(parent),
            parent_optimizer_step=0, topology_digest=spec.digest,
            candidate_step_ordinal=1)
        transaction = production_candidate_step(
            begin_candidate(parent), loss_bearing_target=True,
            gradient_execution=gradient,
            teacher_hparams=AdamWHyperparameters(.001, (.9, .95), 1e-8, .01),
            max_norm=1.0, **kwargs)
        return parent, transaction, eligibility, kwargs
    def _nondegenerate_gradient(self):
        case = retained_tests.AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        (compiled, parameters, source, feature_schema, plan, _cache,
         spec, extents, manifest, slot_id) = case._runtime_fixture()
        role = plan.allowed_output_schema.schema.roles[0]
        (first_identity, first), (second_identity, second) = (
            case._source_owned_unseen_concepts(compiled, source, plan))
        parameters = dict(parameters)
        parameters["readout.state_norm"] = mx.ones_like(
            parameters["readout.state_norm"])
        parameters["readout.output_norm"] = mx.ones_like(
            parameters["readout.output_norm"])
        for identity, sign in ((first_identity, 1.0), (second_identity, -1.0)):
            bank, row = identity
            name = f"identity.bank.{bank}"
            parameters[name] = parameters[name].at[row, 0].add(sign)
        generation = execution_generation_digest(
            parameters, spec=spec, extents=extents)
        value_plan = AnswerPlan(
            plan.modality_id, plan.input_prefix_end,
            (
                DecisionSpec(
                    "emit", role.role_id, 0, DecisionKind.CONTROL,
                    (ControlAction.EMIT_VALUE,)),
                DecisionSpec(
                    "value", role.role_id, 0, DecisionKind.VALUE,
                    (first, second), ("emit",)),
                DecisionSpec(
                    "finish", None, 0, DecisionKind.CONTROL,
                    (ControlAction.END_FRAME,), ("value",)),
            ),
            plan.allowed_output_schema, plan.snapshot, plan.source_span, generation,
        )
        cache = _new_execution_cache(
            run_id="test-retained", generation=1,
            accepted_manifest_sha256="8" * 64,
            generation_binding=generation, motif_manifest=manifest)
        with patch.object(
                forward_impl, "require_accepted_execution_cache",
                return_value=cache), patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache.require_accepted_execution_cache",
            return_value=cache,
        ):
            gradient = bamf_value_and_grad(
                parameters,
                BamfCompiledBatch(compiled, (source,), feature_schema),
                value_plan,
                (DecisionOutput("value", first),),
                {"value": True}, cache=cache)
        return case, parameters, manifest, spec, extents, slot_id, gradient
    def test_both_retained_sites_backpropagate_on_a_nondegenerate_loss(self):
        _case, _parameters, _manifest, _spec, _extents, slot_id, gradient = (
            self._nondegenerate_gradient())
        self.assertGreater(float(gradient.loss_total), 0.0)
        self.assertEqual(
            tuple(read.participating_slots for read in gradient.execution.motif_reads),
            ((slot_id,), (slot_id,)),
        )
        motif_gradients = {
            name: value for name, value in gradient.gradients.items()
            if name == "motif.page.0" or name.startswith("motif.site.")
        }
        self.assertTrue(all(
            bool(mx.all(mx.isfinite(value))) for value in motif_gradients.values()))
        for name in (
            "motif.page.0",
            "motif.site.0.projection", "motif.site.0.gate_feature",
            "motif.site.0.bias", "motif.site.1.projection",
            "motif.site.1.gate_hidden", "motif.site.1.gate_feature",
            "motif.site.1.bias",
        ):
            self.assertGreater(float(mx.abs(gradient.gradients[name]).sum()), 0.0)
    def test_two_site_update_rejects_back_to_the_exact_retained_parent(self):
        case, parameters, manifest, spec, extents, slot_id, gradient = (
            self._nondegenerate_gradient())
        parent, transaction, _eligibility, kwargs = self._candidate_step(
            case, parameters, manifest, spec, extents, gradient)
        self.assertEqual(int(transaction.optimizer.update_counts["motif.page.0"][slot_id]), 1)
        provenance = bind_execution_provenance(loss_bearing_target=True,
                                               loss_execution=gradient.execution, **kwargs)
        for site_index in (0, 1):
            for suffix in ("projection", "norm", "gate_hidden", "gate_feature", "bias"):
                name = f"motif.site.{site_index}.{suffix}"
                self.assertTrue(provenance.mask.parameter(name).whole_parameter)
                self.assertEqual(int(transaction.optimizer.update_counts[name]), 1)
        self.assertIs(resolve_candidate(transaction, accepted=False), parent)
