"""Shared synthetic A02 vocabulary fixtures."""
from dataclasses import replace

from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasCounts, BANK_SIZE, SHAPE_POLICY,
    _canonical_bytes as _atlas_bytes, _digest as _atlas_sha256,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas.vocabulary import VocabularyPrior
from bilqis_mlx.semantics.tests.test_atlas_features import _snapshot

def _allocation_fixture(*, highest=16384):
    """Large *synthetic* ABI boundary fixture, not a source-admission witness."""
    names = {0: "urn:concept:prior", 8191: "urn:concept:8191",
             8192: "urn:concept:8192", 16384: "urn:concept:16384"}
    if highest >= 65536:
        names[65536] = "urn:concept:65536"
    entries = tuple(AbiEntry(
        index, index // BANK_SIZE, index % BANK_SIZE,
        names.get(index, f"urn:reserved:{index}"), None,
        "PRIOR_ACCEPTED_NATIVE_REGISTRY" if index == 0
        else "CANONICAL_SKOS" if index in names else "FORMAL_DOMAIN",
        index == 0, index == 0,
        "PRIOR_ACCEPTED_ABI" if index == 0 else "IMPLEMENTATION_UNCOVERED",
    ) for index in range(highest + 1))
    seed = _snapshot((("urn:concept:prior", ("urn:type:Entity",)),))
    original = seed.concepts[0]
    concepts = tuple(replace(
        original,
        concept=replace(original.concept, semantic_id=name),
        abi_index=index, abi_bank=index // BANK_SIZE,
        abi_row=index % BANK_SIZE,
        active=index == 0,
        implementation_status="ADMITTED" if index == 0 else "IMPLEMENTATION_UNCOVERED",
        teaching_candidate=index == 0,
        teaching_reason="SOURCE_ADMITTED" if index == 0 else "IMPLEMENTATION_UNCOVERED",
    ) for index, name in names.items())
    snapshot = replace(
        seed,
        abi_entries=entries, concepts=concepts,
        counts=AtlasCounts(
            highest + 1, highest + 1, len(names), highest + 1,
            highest // BANK_SIZE + 1, 1, 0, 0, 0, len(names) - 1),
        semantic_lookup=tuple(sorted(
            (item.semantic_id, item.index) for item in entries)),
        concept_lookup=tuple(sorted(
            (item.concept.semantic_id, position)
            for position, item in enumerate(concepts))),
        shape_policy_sha256=_atlas_sha256(_atlas_bytes(SHAPE_POLICY)),
        active_set_sha256=_atlas_sha256(_atlas_bytes([0])),
    )
    feature_schema = FeatureSchema((), ())
    features = build_feature_manifest(snapshot, feature_schema)
    extents = GenerationExtents(
        1, 1, _atlas_sha256(_atlas_bytes([0])), "b" * 64, features.digest)
    prior = VocabularyPrior(
        AtlasArtifactSelection(
            "synthetic-not-a-real-pin", snapshot.bundle_id,
            snapshot.release_sha256, snapshot.source_bundle_id),
        extents, features, feature_schema, ("urn:concept:prior",), "e" * 64,
    )
    return snapshot, prior
