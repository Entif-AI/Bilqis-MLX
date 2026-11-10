"""Literal B13 custody proof for retained B08 reads."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.atlas_model_forward as forward_impl
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning._atlas_candidate.common import (
    RETAINED_STATE_ISSUER, STATE_SCHEMA,
)
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.source_atoms.backbone import finalize_source_backbone_hidden
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch
from bilqis_mlx.runtime.bamf_bundle import admission, publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle
from bilqis_mlx.runtime.bamf_bundle.execution_cache import _new_execution_cache
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    DECLARED, acceptance, next_accepted_step,
    publish_genesis, provision_source_authority_registry, shape_patch,
    with_source_authority_registry,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY
from bilqis_mlx.runtime.topology_v2.ledger import (
    expected_bamf_shapes as real_expected_bamf_shapes,
)
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


@unittest.skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class RetainedB13CustodyTests(unittest.TestCase):
    def test_live_accepted_cache_owns_retained_hit_and_stale_or_unowned_reject(self):
        from bilqis_mlx.runtime.tests.model.test_atlas_model_retained import (
            AtlasModelRetainedMotifTests,
        )

        fixture = AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        fixture.setUp()
        try:
            (compiled, parameters, source, feature_schema, _plan, _fake_cache,
             _spec, _extents, manifest, slot_id) = fixture._runtime_fixture()
            with TemporaryDirectory() as temporary, patch.dict(
                os.environ,
                {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")},
            ):
                run = Path(temporary) / "run"
                with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                    pointer = publish_genesis(run)
                    parent = admission.load_accepted_generation(run)
                    retained = object.__new__(CandidateState)
                    for name, value in (
                        ("optimizer", parent.retained_state.optimizer),
                        ("policy", parent.retained_state.policy),
                        ("allocations", MotifAllocationSnapshot(manifest)),
                        ("optimizer_step", parent.retained_state.optimizer_step + 1),
                        ("custody", parent.retained_state.custody),
                        ("step_proofs", ()),
                        ("schema_version", STATE_SCHEMA),
                        ("_issuance", RETAINED_STATE_ISSUER),
                    ):
                        object.__setattr__(retained, name, value)
                    retained.__post_init__()
                    successor = derive_successor_bundle(
                        parent, retained,
                        parent_manifest_sha256=pointer["manifest_sha256"],
                        delivery_events=({"event": "RETAINED_MOTIF_PROOF"},),
                    )
                    successor = replace(
                        successor,
                        extents=replace(
                            parent.extents,
                            motif_key_map_digest=manifest.digest,
                        ),
                        transition={
                            "schema": "bilqis.mlx.bamf-generation-transition/v1",
                            "kind": "PARAMETER_EXTENSION",
                            "invalidate_derived_caches": True,
                        },
                    )
                    provision_source_authority_registry(run, AUTHORITY)
                    successor = with_source_authority_registry(successor, AUTHORITY)
                    publish_bamf_generation(
                        run, successor,
                        acceptance=acceptance(
                            successor, parent=parent.retained_state),
                        reserve_gib=0.,
                    )
                    cache = bind_accepted_execution_cache(run)
                    tiny_factor = successor.extents.factor_map_digest

                    def expected_shapes(spec, extents):
                        if extents.factor_map_digest == tiny_factor:
                            return DECLARED
                        return real_expected_bamf_shapes(spec, extents)

                    with patch(
                        "bilqis_mlx.runtime.topology_v2.validation."
                        "expected_bamf_shapes",
                        side_effect=expected_shapes,
                    ):
                        batch = BamfCompiledBatch(
                            compiled, (source,), feature_schema)
                        producer, accepted = forward_impl._source_producer(
                            parameters, batch, cache.generation_binding, cache)
                        finalize_source_backbone_hidden(producer)
                        self.assertIs(accepted, cache)
                        self.assertEqual(
                            producer._motif_read.participating_slots, (slot_id,))
                        self.assertEqual(
                            producer._motif_read.dispositions[0][-1], "EXACT")

                        unowned = _new_execution_cache(
                            run_id=cache.run_id,
                            generation=cache.generation,
                            accepted_manifest_sha256=cache.accepted_manifest_sha256,
                            generation_binding=cache.generation_binding,
                            motif_manifest=cache.motif_manifest,
                            source_authority_registry_sha256=(
                                cache.source_authority_registry_sha256),
                        )
                        with self.assertRaises(BilqisError) as unowned_error:
                            forward_impl._source_producer(
                                parameters, batch, cache.generation_binding, unowned)
                        self.assertEqual(
                            unowned_error.exception.context["reason"],
                            "B13_EXECUTION_CACHE_REQUIRED")

                        absent_producer, absent_cache = forward_impl._source_producer(
                            parameters, batch, cache.generation_binding, None)
                        finalize_source_backbone_hidden(absent_producer)
                        self.assertIsNone(absent_cache)
                        self.assertIsNone(absent_producer._motif_read)

                    accepted_student = admission.load_accepted_generation(run)
                    next_state = next_accepted_step(
                        accepted_student.retained_state,
                        accepted_student.extents,
                    )
                    next_bundle = derive_successor_bundle(
                        accepted_student,
                        next_state,
                        parent_manifest_sha256=cache.accepted_manifest_sha256,
                        delivery_events=({"event": "STALE_CACHE_PROOF"},),
                    )
                    publish_bamf_generation(
                        run,
                        next_bundle,
                        acceptance=acceptance(
                            next_bundle,
                            parent=accepted_student.retained_state,
                        ),
                        reserve_gib=0.,
                    )
                    with self.assertRaises(BilqisError) as stale_error:
                        forward_impl._source_producer(
                            parameters, batch, cache.generation_binding, cache)
                    self.assertEqual(
                        stale_error.exception.context["reason"],
                        "B13_EXECUTION_CACHE_STALE")
        finally:
            fixture.tearDown()
