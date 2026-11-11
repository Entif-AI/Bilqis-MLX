"""Real-A01 source-backed B11 fixture shared by B14 production tests."""
from functools import lru_cache

from bilqis_mlx.learning.atlas_engram_reads.source_owner import _B13_EXECUTION_SEAL
from bilqis_mlx.learning.frame_embeddings import semantic_bank_views
from bilqis_mlx.learning.tests.motif_reads.test_source_owner import (
    SourceOwnedMotifReadTests,
)
from bilqis_mlx.learning.source_atoms.backbone import (
    complete_source_backbone_producer,
    start_retained_source_backbone_producer,
)
from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch
from bilqis_mlx.runtime.bamf_bundle.execution_cache import _new_execution_cache
from bilqis_mlx.runtime.tests.model.execution.active_semantic_rows_support import (
    snapshot_active_semantic_rows,
)
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from .cache_authority_integration_fixture import _accepted_registry


@lru_cache(maxsize=1)
def _source_backed_base():
    (compiled, parameters, source, feature_schema, manifest, spec, extents,
     _hidden, _slot_id) = SourceOwnedMotifReadTests()._fixture()
    loaded = load_pinned_atlas_snapshot(source.selection)
    authority_registry = _accepted_registry()
    sources = (source,)
    batch = BamfCompiledBatch(
        compiled, sources, feature_schema,
        snapshot_active_semantic_rows(
            compiled, loaded, run_id="b14-source-backed", generation=0))
    producer = start_retained_source_backbone_producer(
        compiled, parameters, sources, feature_schema,
        semantic_bank_views(
            parameters, extents, compiled.features.semantic_release,
            tuple(entry.index for entry in loaded.abi_entries if entry.active)),
        manifest, batch.atlas_feature_artifact_owner,
        seal=_B13_EXECUTION_SEAL)
    complete_source_backbone_producer(producer)
    return batch, producer, parameters, loaded, manifest, authority_registry


def source_backed_production_fixture():
    batch, producer, parameters, loaded, manifest, authority_registry = (
        _source_backed_base())
    cache = _new_execution_cache(
        run_id="b14-source-backed", generation=0,
        accepted_manifest_sha256="8" * 64,
        generation_binding=producer._generation, motif_manifest=manifest,
        source_authority_registry_sha256=authority_registry.digest)
    object.__setattr__(cache, "_correction_registry", authority_registry)
    return cache, batch, producer, parameters, loaded
