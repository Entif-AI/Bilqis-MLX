"""B11 live loss, gradient, and production-candidate execution witnesses."""
from dataclasses import replace
from unittest import skipUnless

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, begin_candidate,
)
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import (
    IdentityRowAge, PlasticityPolicy, group_eligibility,
)
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, ControlAction, DecisionKind, DecisionOutput, DecisionSpec,
    ExecutionMode, compile_frame_output,
)
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import SourceBackboneTestBase
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance
from bilqis_mlx.runtime.atlas_model import (
    BamfCompiledBatch, BamfGradientExecution, BamfLossExecution, bamf_value_and_grad,
)
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.model_topology_v2 import (
    Initializer, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.runtime.tests.model.execution.active_semantic_rows_support import active_semantic_rows
from bilqis_mlx.runtime.topology_v2.ledger import bamf_parameter_census
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import (
    load_released_frame_schemas, seal_released_frame_schemas,
)
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class AtlasModelTrainingExecutionTests(SourceBackboneTestBase):
    def _answer_plan(self, *, compiled=None, parameters=None):
        compiled = self.compiled if compiled is None else compiled
        parameters = self.parameters if parameters is None else parameters
        role_id = next(
            role for role, _row in compiled.features.role_map
            if role not in ("UNKNOWN", "NONE")
        )
        schema = FrameSchema(
            "frame:test-b11-forward", 1, "test:b11-forward",
            (RoleSpec(role_id, ("Entity",), 0, 1),), "ORDERED", "test")
        manifest = seal_released_frame_schemas(
            (schema,), SchemaTagMap.from_schemas(
                self.snapshot.release_sha256, (schema,)), self.snapshot)
        released = load_released_frame_schemas(
            manifest.canonical_bytes(), expected_sha256=manifest.digest,
            snapshot=self.snapshot)
        domain = compile_frame_output(schema, released, compiled.features)
        generation = execution_generation_digest(
            parameters, spec=ModelTopologySpecV2(), extents=compiled.extents)
        row = compiled.compiled.rows[0]
        return AnswerPlan(
            domain.modality_id, len(row.positions),
            (DecisionSpec(
                "finish", None, 0, DecisionKind.CONTROL,
                (ControlAction.END_FRAME,),
            ),),
            domain, self.snapshot, SourceSpan(0, 0), generation)

    def _live_gradient_execution(self):
        genesis = MotifAllocationSnapshot(MotifManifest(self.snapshot.release_sha256))
        compiled = replace(
            self.compiled,
            extents=replace(
                self.compiled.extents, motif_key_map_digest=genesis.manifest.digest),
        )
        plan = self._answer_plan(compiled=compiled, parameters=self.parameters)
        batch = BamfCompiledBatch(
            compiled, (self.source,), self.schema,
            active_semantic_rows(
                compiled, self.active_indices, run_id="source-backed-forward",
                generation=0))
        gradient_execution = bamf_value_and_grad(
            self.parameters, batch, plan,
            (DecisionOutput("finish", ControlAction.END_FRAME),),
            {"finish": True}, cache=None)
        execution = gradient_execution.execution
        self.assertIsNone(execution.custody_run_id)
        self.assertIsNone(execution.custody_generation)
        self.assertIsNone(execution.custody_manifest_sha256)
        self.assertIn("blocks.0.query", execution.dense_parameter_names)
        self.assertEqual(
            float(mx.abs(gradient_execution.gradients["blocks.0.query"]).sum()), 0.0)
        self.assertEqual(
            execution.visible_identity_rows,
            tuple(sorted(set(
                divmod(index, ModelTopologySpecV2.semantic_bank_rows)
                for index in self.source.source_row["tokens"][:2]
            ))),
        )
        with self.assertRaises(BilqisError):
            BamfLossExecution()
        with self.assertRaises(BilqisError):
            BamfGradientExecution()
        ages = tuple(IdentityRowAge(bank, row, 0) for bank, row in execution.visible_identity_rows)
        spec = ModelTopologySpecV2()
        extents = compiled.extents
        eligibility = group_eligibility("FULL", bamf_parameter_census(spec, extents), ages)
        provenance = bind_execution_provenance(
            loss_bearing_target=True, loss_execution=execution,
            group_eligible=eligibility, spec=spec, extents=extents,
            run_id="source-backed-forward", generation=1,
            parent_manifest_sha256="6" * 64,
            parent_candidate_identity_sha256="7" * 64, parent_optimizer_step=0,
            topology_digest=spec.digest, candidate_step_ordinal=1)
        self.assertTrue(provenance.mask.parameter("blocks.0.query").whole_parameter)
        self.assertTrue(provenance.mask.has_loss_bearing_target)
        return compiled, gradient_execution, execution, genesis

    def _production_candidate_from_live_execution(
        self, compiled, gradient_execution, execution, genesis,
    ):
        ages = tuple(IdentityRowAge(bank, row, 0) for bank, row in execution.visible_identity_rows)
        spec = ModelTopologySpecV2()
        extents = compiled.extents
        eligibility = group_eligibility("FULL", bamf_parameter_census(spec, extents), ages)
        declared = expected_bamf_shapes(spec, extents)
        rowwise = {Initializer.IDENTITY_BANK, Initializer.MOTIF_PAGE, Initializer.FEATURE_TABLE}
        counts = {
            item.name: mx.zeros(
                (item.shape[0],) if (
                    item.initializer in rowwise
                    or (item.initializer is Initializer.EMBEDDING and len(item.shape) == 2)
                ) else (), dtype=mx.uint64)
            for item in declared
        }
        optimizer = AdamWStateTree(
            self.parameters,
            {name: mx.zeros_like(value) for name, value in self.parameters.items()},
            {name: mx.zeros_like(value) for name, value in self.parameters.items()}, counts)
        parent = CandidateState(
            optimizer, PlasticityPolicy("FOUNDATION", 0, ages), genesis, 0,
            CandidateCustodyIdentity(
                "source-backed-forward", 0, "6" * 64, spec.digest, extents.digest))
        with self.assertRaises(BilqisError) as caught:
            production_candidate_step(
                begin_candidate(parent), loss_bearing_target=True,
                gradient_execution=gradient_execution, group_eligible=eligibility,
                spec=spec, extents=extents, run_id="source-backed-forward", generation=1,
                parent_manifest_sha256="6" * 64,
                parent_candidate_identity_sha256=candidate_identity_digest(parent),
                parent_optimizer_step=0, topology_digest=spec.digest,
                candidate_step_ordinal=1,
                teacher_hparams=AdamWHyperparameters(.001, (.9, .95), 1e-8, .01),
                max_norm=1.0)
        self.assertEqual(
            caught.exception.context["reason"],
            "B11_GRADIENT_EXECUTION_CUSTODY_MISMATCH")

    def test_loss_execution_is_issued_only_from_exact_live_forward(self):
        compiled, gradient_execution, execution, genesis = self._live_gradient_execution()
        self._production_candidate_from_live_execution(
            compiled, gradient_execution, execution, genesis)
