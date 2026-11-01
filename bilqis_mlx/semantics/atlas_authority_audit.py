"""A12.1 source-attested cross-consumer audit, never an admission grant."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from bilqis_mlx.errors import ErrorBus, SEMANTIC_FRAME
from bilqis_mlx.factory.skos_curriculum.lesson_types import SourceConstructiveLessonSet
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas.vocabulary_contracts import VocabularyExtension, STAGED_ONLY
from bilqis_mlx.semantics.atlas.vocabulary_resources import RegistryMirrorDelta
from bilqis_mlx.semantics.frame_schema import FrameSchema

AUDIT_SCHEMA = 'bilqis.atlas-authority-audit/source-attested-v1'


def _invalid(reason):
    ErrorBus.raise_(SEMANTIC_FRAME.BINDING.INVALID, reason=reason,
                    role_id='<atlas-authority-audit>', span_start=0, span_end=0)


@dataclass(frozen=True)
class AuthorityReceipt:
    source_release_sha256: str
    source_bundle_id: str
    atlas_bundle_id: str
    abi_digest: str
    ast_digest: str
    lesson_census_digest: str
    registry_digest: str
    audit_digest: str
    status: str = 'SOURCE_ATTESTED_NOT_NEURAL_ADMITTED'
    schema: str = AUDIT_SCHEMA


def audit_atlas_authority(release, abi, ast, lesson_manifest, registry_mirror) -> AuthorityReceipt:
    """Replay the registered A01 pin and reject unbound staged derivatives.

    A historical shadow is not an input authority. Neither this receipt nor a
    staged A02 mirror represents accepted Factory/neural admission.
    """
    if (type(release) is not AtlasArtifactSelection
            or type(abi) is not VocabularyExtension
            or type(ast) is not FrameSchema
            or type(lesson_manifest) is not SourceConstructiveLessonSet
            or type(registry_mirror) is not RegistryMirrorDelta):
        _invalid('A12_AUDIT_TYPED_INPUT_REQUIRED')
    snapshot = load_pinned_atlas_snapshot(release)
    for record in (abi, ast, lesson_manifest, registry_mirror):
        record.__post_init__() if hasattr(record, '__post_init__') else None
    if (snapshot.release_sha256 != release.release_sha256
            or snapshot.source_bundle_id != release.source_bundle_id
            or abi.status != STAGED_ONLY
            or registry_mirror.status != STAGED_ONLY
            or abi.semantic_release != release.release_sha256
            or ast.semantic_release != release.release_sha256
            or lesson_manifest.semantic_release != release.release_sha256
            or registry_mirror.semantic_release != release.release_sha256
            or abi.source_bundle_id != release.source_bundle_id
            or registry_mirror.source_bundle_id != release.source_bundle_id
            or registry_mirror.allocation_source_digest != abi.source_allocation_digest
            or registry_mirror.predecessor_generation_id != abi.parent_generation_id
            or registry_mirror.active_indices != abi.active_indices
            or len(registry_mirror.rows) != len(abi.allocations)
            or any((row.semantic_id, row.abi_index, row.bank, row.row, row.source_status)
                   != (allocation.semantic_id, allocation.abi_index, allocation.bank,
                       allocation.row, allocation.source_status)
                   for row, allocation in zip(registry_mirror.rows, abi.allocations))
            or any(lesson.semantic_id not in {item.semantic_id for item in snapshot.concepts}
                   for lesson in lesson_manifest.lessons)):
        _invalid('A12_AUDIT_SOURCE_BINDING_MISMATCH')
    ast_digest = hashlib.sha256(ast.canonical_bytes()).hexdigest()
    evidence = (release.release_sha256, release.source_bundle_id, release.bundle_id,
                abi.source_allocation_digest, ast_digest, lesson_manifest.census_digest,
                registry_mirror.digest)
    audit_digest = hashlib.sha256(json.dumps(evidence, separators=(',', ':')).encode()).hexdigest()
    return AuthorityReceipt(*evidence, audit_digest)
