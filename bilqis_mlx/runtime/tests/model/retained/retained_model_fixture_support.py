"""Shared real-A01 retained-model fixture helpers for B08 integration tests."""
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.learning._atlas_candidate.common import RETAINED_STATE_ISSUER, STATE_SCHEMA
from bilqis_mlx.learning.atlas_candidate import CandidateCustodyIdentity, CandidateState
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, ControlAction, DecisionKind, DecisionOutput, DecisionSpec,
    compile_frame_output,
)
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch, bamf_value_and_grad
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.execution_cache import _new_execution_cache
import bilqis_mlx.runtime.atlas_model_forward as forward_impl
from bilqis_mlx.runtime.model_topology_v2 import Initializer, expected_bamf_shapes
from bilqis_mlx.runtime.tests.model.execution.active_semantic_rows_support import (
    snapshot_active_semantic_rows,
)
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.frame_adapters import bind_registered_source_row
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import (
    load_released_frame_schemas, seal_released_frame_schemas,
)
from bilqis_mlx.source_adapters.school import A_ORACLE, live_source_registry


class RetainedModelFixtureSupport:
    def _retained_parent(self, parameters, manifest, spec, extents, ages):
        declared = expected_bamf_shapes(spec, extents)
        rowwise = {
            Initializer.IDENTITY_BANK, Initializer.MOTIF_PAGE,
            Initializer.FEATURE_TABLE,
        }
        counts = {
            item.name: mx.zeros(
                (item.shape[0],) if (
                    item.initializer in rowwise
                    or (item.initializer is Initializer.EMBEDDING
                        and len(item.shape) == 2)
                ) else (), dtype=mx.uint64)
            for item in declared
        }
        optimizer = AdamWStateTree(
            parameters,
            {name: mx.zeros_like(value) for name, value in parameters.items()},
            {name: mx.zeros_like(value) for name, value in parameters.items()},
            counts)
        state = object.__new__(CandidateState)
        for name, value in (
                ("optimizer", optimizer),
                ("policy", PlasticityPolicy("FOUNDATION", 0, ages)),
                ("allocations", MotifAllocationSnapshot(manifest)),
                ("optimizer_step", 0),
                ("custody", CandidateCustodyIdentity(
                    "test-retained", 1, "8" * 64, spec.digest, extents.digest)),
                ("step_proofs", ()), ("schema_version", STATE_SCHEMA),
                ("_issuance", RETAINED_STATE_ISSUER)):
            object.__setattr__(state, name, value)
        state.__post_init__()
        return state

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
        cache = _new_execution_cache(
            run_id="test-retained",
            generation=1,
            accepted_manifest_sha256="8" * 64,
            generation_binding=generation,
            motif_manifest=manifest,
        )
        return (
            compiled, parameters, source, feature_schema, plan, cache,
            spec, extents, manifest, slot_id,
        )

    def _source_owned_unseen_concepts(self, compiled, source, plan):
        snapshot = plan.snapshot
        row = compiled.compiled.rows[0]
        visible = {
            (entry.bank, entry.row)
            for abi_index in tuple(source.source_row.get("tokens", ()))[:row.visible_end]
            for entry in (snapshot.abi(abi_index),)
        }
        adapter = live_source_registry().require(
            "bilqis_mlx.grade_a_probe.make_record", A_ORACLE)
        rows = adapter.draw(
            source_root=source.source_root, graph=source.graph, course=None,
            capability="A.IDENTITY", seed=source.source_seed, each=10)
        allowed_types = plan.allowed_output_schema.schema.roles[0].allowed_type_ids
        concepts = {}
        for source_row in rows:
            tree = bind_registered_source_row(
                adapter, source_row, snapshot,
                source_root=source.source_root, graph=source.graph,
                source_span=SourceSpan(0, len(source_row["tokens"])),
                causal_prefix_end=len(source_row["tokens"]))
            for binding in tree.root.bindings:
                if binding.concept is None or binding.concept.type_ids != allowed_types:
                    continue
                entry = snapshot.abi_for_semantic(binding.concept.semantic_id)
                identity = (entry.bank, entry.row)
                if identity not in visible:
                    concepts.setdefault(identity, binding.concept)
        self.assertGreaterEqual(len(concepts), 2)
        return tuple(concepts.items())[:2]

    def _real_output_denominator_case(self):
        (compiled, parameters, source, feature_schema, plan, cache,
         spec, extents, manifest, _slot_id) = self._runtime_fixture()
        snapshot = plan.snapshot
        role = plan.allowed_output_schema.schema.roles[0]
        ((denominator, candidate), (unrelated, _unrelated_concept)
         ) = self._source_owned_unseen_concepts(compiled, source, plan)
        value_plan = AnswerPlan(
            plan.modality_id, plan.input_prefix_end,
            (
                DecisionSpec(
                    "emit", role.role_id, 0, DecisionKind.CONTROL,
                    (ControlAction.EMIT_VALUE,),
                ),
                DecisionSpec(
                    "value", role.role_id, 0, DecisionKind.VALUE,
                    (candidate,), ("emit",),
                ),
                DecisionSpec(
                    "finish", None, 0, DecisionKind.CONTROL,
                    (ControlAction.END_FRAME,), ("value",),
                ),
            ),
            plan.allowed_output_schema, snapshot, plan.source_span,
            plan.generation_binding,
        )
        with patch.object(
                forward_impl, "require_accepted_execution_cache",
                return_value=cache), patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache.require_accepted_execution_cache",
            return_value=cache,
        ):
            gradient = bamf_value_and_grad(
                parameters,
                BamfCompiledBatch(
                    compiled, (source,), feature_schema,
                    snapshot_active_semantic_rows(
                        compiled, snapshot, run_id=cache.run_id,
                        generation=cache.generation)),
                value_plan,
                (DecisionOutput("value", candidate),),
                {"value": True},
                cache=cache,
            )
        return (
            parameters, manifest, spec, extents, gradient,
            (denominator,), unrelated,
        )
