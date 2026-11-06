"""Retained B08 reads must flow through the same B11/B09 execution trace."""
from unittest import skipUnless

from bilqis_mlx.learning.atlas_plasticity import (
    IdentityRowAge, group_eligibility,
)
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, ControlAction, DecisionKind, DecisionOutput, DecisionSpec,
    compile_frame_output,
)
from bilqis_mlx.learning.tests.motif_reads.test_source_owner import (
    SourceOwnedMotifReadTests,
)
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch, bamf_value_and_grad
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
    _issue_accepted_execution_cache,
)
from bilqis_mlx.runtime.topology_v2.ledger import bamf_parameter_census
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import (
    load_released_frame_schemas, seal_released_frame_schemas,
)
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class AtlasModelRetainedMotifTests(SourceOwnedMotifReadTests):
    def _runtime_fixture(self):
        (compiled, parameters, source, feature_schema, manifest, spec, extents,
         _hidden, slot_id) = self._fixture()
        snapshot = load_pinned_atlas_snapshot(source.selection)
        role_id = next(
            role for role, _row in compiled.features.role_map
            if role not in ("UNKNOWN", "NONE")
        )
        schema = FrameSchema(
            "frame:test-b11-retained", 1, "test:b11-retained",
            (RoleSpec(role_id, ("Entity",), 0, 1),),
            "ORDERED", "test",
        )
        release = seal_released_frame_schemas(
            (schema,),
            SchemaTagMap.from_schemas(snapshot.release_sha256, (schema,)),
            snapshot,
        )
        released = load_released_frame_schemas(
            release.canonical_bytes(),
            expected_sha256=release.digest,
            snapshot=snapshot,
        )
        domain = compile_frame_output(schema, released, compiled.features)
        generation = execution_generation_digest(
            parameters, spec=spec, extents=extents)
        row = compiled.compiled.rows[0]
        plan = AnswerPlan(
            domain.modality_id,
            len(row.positions),
            (DecisionSpec(
                "finish", None, 0, DecisionKind.CONTROL,
                (ControlAction.END_FRAME,),
            ),),
            domain,
            snapshot,
            SourceSpan(0, 0),
            generation,
        )
        cache = _issue_accepted_execution_cache(
            run_id="test-retained",
            generation=1,
            accepted_manifest_sha256="8" * 64,
            generation_binding=generation,
            motif_manifest=manifest,
        )
        return (
            compiled, parameters, source, feature_schema, plan, cache,
            spec, extents, slot_id,
        )

    def test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace(self):
        (compiled, parameters, source, feature_schema, plan, cache,
         spec, extents, slot_id) = self._runtime_fixture()
        execution = bamf_value_and_grad(
            parameters,
            BamfCompiledBatch(compiled, (source,), feature_schema),
            plan,
            (DecisionOutput("finish", ControlAction.END_FRAME),),
            {"finish": True},
            cache=cache,
        ).execution
        self.assertEqual(len(execution.motif_reads), 1)
        self.assertEqual(
            execution.motif_reads[0].participating_slots, (slot_id,))
        ages = tuple(
            IdentityRowAge(bank, row, 0)
            for bank, row in execution.visible_identity_rows
        )
        eligibility = group_eligibility(
            "FULL", bamf_parameter_census(spec, extents), ages)
        provenance = bind_execution_provenance(
            loss_bearing_target=True,
            loss_execution=execution,
            group_eligible=eligibility,
            spec=spec,
            extents=extents,
            run_id="retained-source-forward",
            generation=1,
            parent_manifest_sha256="6" * 64,
            parent_candidate_identity_sha256="7" * 64,
            parent_optimizer_step=0,
            topology_digest=spec.digest,
            candidate_step_ordinal=1,
        )
        self.assertEqual(
            provenance.mask.parameter("motif.page.0").row_indices,
            (slot_id,),
        )
