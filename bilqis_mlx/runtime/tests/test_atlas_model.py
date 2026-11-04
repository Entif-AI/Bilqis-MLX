"""Source-backed B11 integration through the actual typed B10 decoder."""
from unittest import skipUnless
import mlx.core as mx

from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, ControlAction, DecisionKind, DecisionOutput, DecisionSpec,
    ExecutionMode,
    compile_frame_output,
)
from bilqis_mlx.learning.atlas_participation import ActiveAdmittedRows
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, group_eligibility
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import (
    SourceBackboneTestBase,
)
from bilqis_mlx.runtime.atlas_model import (
    BamfCompiledBatch, BamfGradientExecution, BamfLossExecution,
    bamf_value_and_grad, forward_bamf,
)
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.topology_v2.ledger import bamf_parameter_census
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import (
    load_released_frame_schemas,
    seal_released_frame_schemas,
)
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class AtlasModelSourceForwardTests(SourceBackboneTestBase):
    def _answer_plan(self):
        role_id = next(
            role for role, _row in self.compiled.features.role_map
            if role not in ("UNKNOWN", "NONE")
        )
        schema = FrameSchema(
            "frame:test-b11-forward", 1, "test:b11-forward",
            (RoleSpec(role_id, ("Entity",), 0, 1),),
            "ORDERED", "test",
        )
        manifest = seal_released_frame_schemas(
            (schema,),
            SchemaTagMap.from_schemas(self.snapshot.release_sha256, (schema,)),
            self.snapshot,
        )
        released = load_released_frame_schemas(
            manifest.canonical_bytes(),
            expected_sha256=manifest.digest,
            snapshot=self.snapshot,
        )
        domain = compile_frame_output(schema, released, self.compiled.features)
        generation = execution_generation_digest(
            self.parameters,
            spec=ModelTopologySpecV2(),
            extents=self.compiled.extents,
        )
        row = self.compiled.compiled.rows[0]
        return AnswerPlan(
            domain.modality_id,
            len(row.positions),
            (DecisionSpec(
                "finish", None, 0, DecisionKind.CONTROL,
                (ControlAction.END_FRAME,),
            ),),
            domain,
            self.snapshot,
            SourceSpan(0, 0),
            generation,
        )

    def test_forward_bamf_owns_source_backbone_and_typed_readout(self):
        batch = BamfCompiledBatch(
            self.compiled, (self.source,), self.schema)
        output = forward_bamf(
            self.parameters, batch, self._answer_plan(),
            ExecutionMode.INFERENCE, None)
        self.assertIs(output.execution_mode, ExecutionMode.INFERENCE)
        self.assertEqual(
            tuple(item.decision_id for item in output.decisions),
            ("finish",),
        )
        self.assertEqual(output.committed[0].value, ControlAction.END_FRAME)

    def test_loss_execution_is_issued_only_from_exact_live_forward(self):
        batch = BamfCompiledBatch(
            self.compiled, (self.source,), self.schema)
        gradient_execution = bamf_value_and_grad(
            self.parameters, batch, self._answer_plan(),
            (DecisionOutput("finish", ControlAction.END_FRAME),),
            {"finish": True},
        )
        execution = gradient_execution.execution
        self.assertIn("blocks.0.query", execution.dense_parameter_names)
        self.assertEqual(
            float(mx.abs(
                gradient_execution.gradients["blocks.0.query"]).sum()), 0.0)
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

        ages = tuple(
            IdentityRowAge(bank, row, 0)
            for bank, row in execution.visible_identity_rows
        )
        eligibility = group_eligibility(
            "FULL",
            bamf_parameter_census(
                ModelTopologySpecV2(), self.compiled.extents),
            ages,
        )
        provenance = bind_execution_provenance(
            loss_bearing_target=True,
            loss_execution=execution,
            group_eligible=eligibility,
            active_admitted=ActiveAdmittedRows(
                identity_rows=execution.visible_identity_rows,
                feature_rows=execution.feature_rows,
                local_slot_rows=execution.local_slot_rows,
            ),
            spec=ModelTopologySpecV2(),
            extents=self.compiled.extents,
            run_id="source-backed-forward",
            generation=1,
            parent_manifest_sha256="6" * 64,
            parent_candidate_identity_sha256="7" * 64,
            parent_optimizer_step=0,
            topology_digest=ModelTopologySpecV2().digest,
            candidate_step_ordinal=1,
        )
        self.assertTrue(
            provenance.mask.parameter("blocks.0.query").whole_parameter)
        self.assertTrue(provenance.mask.has_loss_bearing_target)

