"""A12 source replay and current-consumer authority audit."""
from dataclasses import asdict
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.skos_curriculum.checkers import assert_source_lesson_set_current
from bilqis_mlx.factory.skos_curriculum.lesson_types import SourceConstructiveLessonSet
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2

from ..atlas.snapshot import load_pinned_atlas_snapshot
from ..atlas.snapshot_contracts import AtlasArtifactSelection
from ..atlas.vocabulary_contracts import STAGED_ONLY, VocabularyExtension, VocabularyPrior
from ..atlas.vocabulary_planning import plan_vocabulary_extension
from ..atlas.vocabulary_resources import RegistryMirrorDelta, build_registry_mirror_delta
from ..atlas_projection import _fail
from ..released_frame_schemas import VerifiedReleasedFrameSchemas, _source_pins
from .contracts import (
    AUTHORITY_AUDIT_SCHEMA, AuthorityReceipt, _current_prior_abi_sha256,
    _sha, _source_dispositions, consumer_bindings, graph_projection_digest,
)


def _validated_audit_snapshot(
        release, abi, ast, lesson_manifest, registry_mirror, *,
        abi_prior, source_bundle_path):
    if (type(release) is not AtlasArtifactSelection
            or type(abi) is not VocabularyExtension
            or type(ast) is not VerifiedReleasedFrameSchemas
            or type(lesson_manifest) is not SourceConstructiveLessonSet
            or type(registry_mirror) is not RegistryMirrorDelta):
        _fail("A12_AUTHORITY_TYPED_INPUT_REQUIRED")
    snapshot = load_pinned_atlas_snapshot(release)
    ast_manifest = ast.manifest
    ast.__post_init__()
    ast_pins = tuple(
        entry for entry in _source_pins()
        if entry["semantic_release"] == snapshot.release_sha256
        and entry["atlas_bundle_id"] == snapshot.bundle_id
        and entry["source_bundle_id"] == snapshot.source_bundle_id
        and entry["schema_manifest_sha256"] == ast.trusted_sha256
        and entry["schema_map_sha256"] == ast_manifest.schema_map.digest)
    if len(ast_pins) != 1:
        _fail("A12_AUTHORITY_AST_SOURCE_PIN_MISMATCH")
    if (snapshot.release_sha256 != release.release_sha256
            or snapshot.source_bundle_id != release.source_bundle_id
            or snapshot.bundle_id != release.bundle_id
            or abi.status != STAGED_ONLY or registry_mirror.status != STAGED_ONLY
            or abi.semantic_release != snapshot.release_sha256
            or ast_manifest.semantic_release != snapshot.release_sha256
            or lesson_manifest.semantic_release != snapshot.release_sha256
            or registry_mirror.semantic_release != snapshot.release_sha256
            or abi.source_bundle_id != snapshot.source_bundle_id
            or ast_manifest.source_bundle_id != snapshot.source_bundle_id
            or registry_mirror.source_bundle_id != snapshot.source_bundle_id
            or ast_manifest.atlas_bundle_id != snapshot.bundle_id):
        _fail("A12_AUTHORITY_SOURCE_BINDING_MISMATCH")
    if snapshot.prior_abi_sha256 != _current_prior_abi_sha256():
        _fail("A12_AUTHORITY_PRIOR_ABI_MISMATCH")
    if (type(abi_prior) is not VocabularyPrior or not isinstance(source_bundle_path, Path)
            or abi_prior.source_selection.bundle_id != snapshot.bundle_id
            or abi_prior.source_selection.release_sha256 != snapshot.release_sha256
            or abi_prior.source_selection.source_bundle_id != snapshot.source_bundle_id):
        _fail("A12_AUTHORITY_ABI_SOURCE_MISMATCH")
    try:
        replayed_abi = plan_vocabulary_extension(
            abi_prior, tuple(item.semantic_id for item in abi.allocations),
            ModelTopologySpecV2())
    except BilqisError:
        _fail("A12_AUTHORITY_ABI_SOURCE_MISMATCH")
    if replayed_abi != abi:
        _fail("A12_AUTHORITY_ABI_SOURCE_MISMATCH")
    abi_ids = {entry.semantic_id: entry for entry in snapshot.abi_entries}
    if any(item.semantic_id not in abi_ids
           or item.abi_index != abi_ids[item.semantic_id].index for item in abi.allocations):
        _fail("A12_AUTHORITY_ABI_SOURCE_MISMATCH")
    if (registry_mirror.allocation_source_digest != abi.source_allocation_digest
            or registry_mirror.predecessor_generation_id != abi.parent_generation_id
            or registry_mirror.active_indices != abi.active_indices
            or len(registry_mirror.rows) != len(abi.allocations)
            or any((row.semantic_id, row.abi_index, row.bank, row.row, row.source_status)
                   != (allocation.semantic_id, allocation.abi_index, allocation.bank,
                       allocation.row, allocation.source_status)
                   for row, allocation in zip(registry_mirror.rows, abi.allocations))):
        _fail("A12_AUTHORITY_REGISTRY_MIRROR_MISMATCH")
    try:
        replayed_mirror = build_registry_mirror_delta(
            abi_prior, abi, source_bundle_path=source_bundle_path)
    except BilqisError:
        _fail("A12_AUTHORITY_REGISTRY_MIRROR_MISMATCH")
    if replayed_mirror != registry_mirror:
        _fail("A12_AUTHORITY_REGISTRY_MIRROR_MISMATCH")
    try:
        assert_source_lesson_set_current(lesson_manifest, release)
    except BilqisError:
        _fail("A12_AUTHORITY_LESSON_SOURCE_MISMATCH")
    formal_ids = {semantic_id for binding in snapshot.formal_domain_bindings
                  for semantic_id in binding.semantic_ids}
    admitted = set(abi_ids) | formal_ids
    if any(lesson.semantic_id not in admitted
           or lesson.semantic_release != snapshot.release_sha256
           or any(item not in admitted
                  for item in (*lesson.constituents, *lesson.prerequisite_closure))
           for lesson in lesson_manifest.lessons):
        _fail("A12_AUTHORITY_LESSON_SOURCE_MISMATCH")
    return snapshot


def audit_atlas_authority(
        release, abi, ast, lesson_manifest, registry_mirror, *,
        abi_prior, source_bundle_path) -> AuthorityReceipt:
    """Replay pinned owners before binding the current semantic consumers."""
    snapshot = _validated_audit_snapshot(
        release, abi, ast, lesson_manifest, registry_mirror,
        abi_prior=abi_prior, source_bundle_path=source_bundle_path)
    graph_digest = graph_projection_digest(snapshot)
    dispositions = _source_dispositions(snapshot)
    formal_digests = tuple(sorted(_sha(asdict(binding))
                                  for binding in snapshot.formal_domain_bindings))
    bindings = consumer_bindings(
        snapshot, abi, ast, lesson_manifest, registry_mirror, graph_digest)
    evidence = {
        "schema": AUTHORITY_AUDIT_SCHEMA, "release": snapshot.release_sha256,
        "source_bundle": snapshot.source_bundle_id, "atlas_bundle": snapshot.bundle_id,
        "consumers": [asdict(item) for item in bindings],
        "prior_abi": snapshot.prior_abi_sha256, "formal_domains": formal_digests,
        "source_dispositions": dispositions,
    }
    return AuthorityReceipt(
        snapshot.release_sha256, snapshot.source_bundle_id, snapshot.bundle_id,
        bindings, graph_digest, snapshot.prior_abi_sha256, formal_digests,
        dispositions, _sha(evidence))
