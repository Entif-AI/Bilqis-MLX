"""A12 source-owner release, cross-consumer audit, and export contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re

from bilqis_mlx.factory.skos_curriculum.lesson_types import (
    SourceConstructiveLessonSet,
)

from .atlas.snapshot_contracts import (
    AtlasArtifactSelection, _require_registered_source_pin,
)
from .atlas.snapshot import load_pinned_atlas_snapshot
from .atlas.vocabulary_contracts import STAGED_ONLY, VocabularyExtension
from .atlas.vocabulary_resources import RegistryMirrorDelta
from .atlas_projection import HEX64, _canonical_bytes, _fail
from .cognitive_dependencies import DependencyKind, DependencyRef
from .context_eligibility import SourceFrontier
from .domains import contract_digest
from .released_frame_schemas import VerifiedReleasedFrameSchemas


_SIGNATURE = re.compile(r"[0-9a-f]{128}")
EXPORT_CLEARANCE_SCHEMA = "bilqis.a12.export-clearance/v1"
AUTHORITY_AUDIT_SCHEMA = "bilqis.a12.semantic-authority-audit/v1"
AUTHORITY_AUDIT_STATUS = "SOURCE_ATTESTED_NOT_NEURAL_ADMITTED"
SOURCE_DISPOSITION_PARTS = 2

SOURCE_DISPOSITIONS = (
    ("atlas_source_pins_v1.json", "CURRENT_SOURCE_PIN_LEDGER"),
    ("frame_schema_source_pins_v1.json", "CURRENT_DERIVED_SOURCE_PIN_LEDGER"),
    ("copular_registry_v1.json", "CURRENT_PRIOR_ABI_LEDGER"),
    ("atlas_projection.py", "HISTORICAL_COMPATIBILITY_FACADE"),
)


def _digests(values, *, allow_empty=False):
    return (type(values) is tuple and (allow_empty or bool(values))
            and all(type(value) is str and HEX64.fullmatch(value) for value in values)
            and values == tuple(sorted(set(values))))


def _sha(value) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _current_prior_abi_sha256() -> str:
    path = Path(__file__).with_name("copular_registry_v1.json")
    if path.is_symlink() or not path.is_file():
        _fail("A12_AUTHORITY_PRIOR_ABI_MISSING")
    return sha256(path.read_bytes()).hexdigest()


def _source_dispositions(snapshot) -> tuple[tuple[str, str], ...]:
    return SOURCE_DISPOSITIONS + tuple(
        (binding.source_owner, "DECLARED_FORMAL_DOMAIN")
        for binding in snapshot.formal_domain_bindings)


@dataclass(frozen=True)
class ConsumerBinding:
    consumer: str
    schema_version: str
    semantic_release: str
    source_bundle_id: str
    artifact_sha256: str

    def __post_init__(self):
        if (type(self.consumer) is not str or not self.consumer
                or type(self.schema_version) is not str or not self.schema_version
                or any(type(value) is not str or not HEX64.fullmatch(value)
                       for value in (
                           self.semantic_release, self.source_bundle_id,
                           self.artifact_sha256))):
            _fail("A12_AUTHORITY_BINDING_INVALID")


@dataclass(frozen=True)
class AuthorityReceipt:
    """One source-attested binding across the current semantic consumers."""

    source_release_sha256: str
    source_bundle_id: str
    atlas_bundle_id: str
    consumer_bindings: tuple[ConsumerBinding, ...]
    graph_projection_sha256: str
    prior_abi_sha256: str
    formal_domain_digests: tuple[str, ...]
    source_dispositions: tuple[tuple[str, str], ...]
    audit_sha256: str
    status: str = AUTHORITY_AUDIT_STATUS
    schema_version: str = AUTHORITY_AUDIT_SCHEMA

    def __post_init__(self):
        if (any(type(value) is not str or not HEX64.fullmatch(value)
                for value in (
                    self.source_release_sha256, self.source_bundle_id,
                    self.atlas_bundle_id, self.graph_projection_sha256,
                    self.prior_abi_sha256, self.audit_sha256))
                or type(self.consumer_bindings) is not tuple
                or tuple(item.consumer for item in self.consumer_bindings)
                != ("abi", "ast_frames", "lessons", "graph_projection",
                    "registry_mirror")
                or any(type(item) is not ConsumerBinding
                       for item in self.consumer_bindings)
                or not _digests(self.formal_domain_digests, allow_empty=True)
                or self.source_dispositions[:len(SOURCE_DISPOSITIONS)]
                != SOURCE_DISPOSITIONS
                or any(
                    type(item) is not tuple
                    or len(item) != SOURCE_DISPOSITION_PARTS
                    or not all(type(value) is str and value for value in item)
                    or item[1] != "DECLARED_FORMAL_DOMAIN"
                    for item in self.source_dispositions[len(SOURCE_DISPOSITIONS):])
                or self.status != AUTHORITY_AUDIT_STATUS
                or self.schema_version != AUTHORITY_AUDIT_SCHEMA):
            _fail("A12_AUTHORITY_RECEIPT_INVALID")


def _graph_projection(snapshot) -> str:
    """Bind the read-only source graph separately from its other consumers."""
    return _sha({
        "schema": "bilqis.a12.graph-projection/v1",
        "semantic_release": snapshot.release_sha256,
        "source_bundle_id": snapshot.source_bundle_id,
        "semantic_lookup": snapshot.semantic_lookup,
        "concept_lookup": snapshot.concept_lookup,
        "relations": [asdict(item) for item in snapshot.relations],
    })


def audit_atlas_authority(
        release, abi, ast, lesson_manifest, registry_mirror) -> AuthorityReceipt:
    """Replay the pinned source and bind each current consumer to that authority.

    The receipt is an audit witness, not a neural-admission grant.  It accepts
    only current typed producer records and recomputes the source graph from the
    independently pinned A01 snapshot.
    """
    if (type(release) is not AtlasArtifactSelection
            or type(abi) is not VocabularyExtension
            or type(ast) is not VerifiedReleasedFrameSchemas
            or type(lesson_manifest) is not SourceConstructiveLessonSet
            or type(registry_mirror) is not RegistryMirrorDelta):
        _fail("A12_AUTHORITY_TYPED_INPUT_REQUIRED")
    snapshot = load_pinned_atlas_snapshot(release)
    abi_ids = {entry.semantic_id: entry for entry in snapshot.abi_entries}
    formal_ids = {
        semantic_id for binding in snapshot.formal_domain_bindings
        for semantic_id in binding.semantic_ids
    }
    ast_manifest = ast.manifest
    for value in (abi, lesson_manifest, registry_mirror):
        if hasattr(value, "__post_init__"):
            value.__post_init__()
    ast.__post_init__()
    if (snapshot.release_sha256 != release.release_sha256
            or snapshot.source_bundle_id != release.source_bundle_id
            or snapshot.bundle_id != release.bundle_id
            or abi.status != STAGED_ONLY
            or registry_mirror.status != STAGED_ONLY
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
    if any(
            item.semantic_id not in abi_ids
            or item.abi_index != abi_ids[item.semantic_id].index
            for item in abi.allocations):
        _fail("A12_AUTHORITY_ABI_SOURCE_MISMATCH")
    if (registry_mirror.allocation_source_digest
            != abi.source_allocation_digest
            or registry_mirror.predecessor_generation_id
            != abi.parent_generation_id
            or registry_mirror.active_indices != abi.active_indices
            or len(registry_mirror.rows) != len(abi.allocations)
            or any(
                (row.semantic_id, row.abi_index, row.bank, row.row,
                 row.source_status)
                != (allocation.semantic_id, allocation.abi_index,
                    allocation.bank, allocation.row, allocation.source_status)
                for row, allocation in zip(
                    registry_mirror.rows, abi.allocations))):
        _fail("A12_AUTHORITY_REGISTRY_MIRROR_MISMATCH")
    allowed_lesson_ids = set(abi_ids) | formal_ids
    if any(
            lesson.semantic_id not in allowed_lesson_ids
            or lesson.semantic_release != snapshot.release_sha256
            for lesson in lesson_manifest.lessons):
        _fail("A12_AUTHORITY_LESSON_SOURCE_MISMATCH")
    graph_digest = _graph_projection(snapshot)
    source_dispositions = _source_dispositions(snapshot)
    formal_digests = tuple(sorted(
        _sha(asdict(binding)) for binding in snapshot.formal_domain_bindings))
    bindings = (
        ConsumerBinding(
            "abi", abi.schema_version, snapshot.release_sha256,
            snapshot.source_bundle_id, _sha(asdict(abi))),
        ConsumerBinding(
            "ast_frames", ast_manifest.schema_version,
            snapshot.release_sha256, snapshot.source_bundle_id,
            ast.trusted_sha256),
        ConsumerBinding(
            "lessons", lesson_manifest.schema,
            snapshot.release_sha256, snapshot.source_bundle_id,
            _sha(asdict(lesson_manifest))),
        ConsumerBinding(
            "graph_projection", "bilqis.a12.graph-projection/v1",
            snapshot.release_sha256, snapshot.source_bundle_id,
            graph_digest),
        ConsumerBinding(
            "registry_mirror", registry_mirror.schema_version,
            snapshot.release_sha256, snapshot.source_bundle_id,
            registry_mirror.digest),
    )
    evidence = {
        "schema": AUTHORITY_AUDIT_SCHEMA,
        "release": snapshot.release_sha256,
        "source_bundle": snapshot.source_bundle_id,
        "atlas_bundle": snapshot.bundle_id,
        "consumers": [asdict(item) for item in bindings],
        "prior_abi": snapshot.prior_abi_sha256,
        "formal_domains": formal_digests,
        "source_dispositions": source_dispositions,
    }
    return AuthorityReceipt(
        snapshot.release_sha256, snapshot.source_bundle_id, snapshot.bundle_id,
        bindings, graph_digest, snapshot.prior_abi_sha256, formal_digests,
        source_dispositions,
        _sha(evidence))


@dataclass(frozen=True)
class ExportClearanceReceipt:
    """Source-owner statement for one exact export set at one rights frontier."""

    source_owner: str
    atlas_bundle_id: str
    semantic_release: str
    source_bundle_id: str
    source_frontier_sha256: str
    rights_epoch: int
    correction_generation: int
    export_artifact_digests: tuple[str, ...]
    private_artifact_digests: tuple[str, ...]
    revoked_artifact_digests: tuple[str, ...]
    revocation_lineage: tuple[str, ...]
    signature_hex: str
    schema_version: str = EXPORT_CLEARANCE_SCHEMA

    def __post_init__(self):
        exported = set(self.export_artifact_digests)
        private = set(self.private_artifact_digests)
        revoked = set(self.revoked_artifact_digests)
        if (type(self.source_owner) is not str or not self.source_owner
                or any(type(value) is not str or not HEX64.fullmatch(value)
                       for value in (
                           self.atlas_bundle_id, self.semantic_release,
                           self.source_bundle_id, self.source_frontier_sha256))
                or type(self.rights_epoch) is not int or self.rights_epoch < 0
                or type(self.correction_generation) is not int
                or self.correction_generation < 0
                or not _digests(self.export_artifact_digests)
                or not _digests(self.private_artifact_digests, allow_empty=True)
                or not _digests(self.revoked_artifact_digests, allow_empty=True)
                or not _digests(self.revocation_lineage, allow_empty=True)
                or exported & (private | revoked)
                or private & revoked
                or type(self.signature_hex) is not str
                or _SIGNATURE.fullmatch(self.signature_hex) is None
                or self.schema_version != EXPORT_CLEARANCE_SCHEMA):
            _fail("A12_EXPORT_CLEARANCE_INVALID")

    def signing_bytes(self):
        payload = asdict(self)
        del payload["signature_hex"]
        return _canonical_bytes(payload)

    def dependency(self):
        return DependencyRef(
            DependencyKind.ARTIFACT,
            "a12-export:" + self.source_bundle_id + ":" + self.semantic_release,
        )

    @property
    def clearance_sha256(self):
        return sha256(self.signing_bytes()).hexdigest()


def validate_export_clearance_context(
        receipt, selection, source_frontier, artifact_digests):
    """Bind a verified owner receipt to the live selected release and rights state.

    Signature verification remains with C09's trusted host registry. This function
    proves that the signed statement describes the exact A12 selection, the exact
    live source frontier, and the exact artifacts a consumer intends to export.
    """
    if (type(receipt) is not ExportClearanceReceipt
            or type(selection) is not AtlasArtifactSelection
            or type(source_frontier) is not SourceFrontier
            or not _digests(artifact_digests)):
        _fail("A12_EXPORT_CLEARANCE_CONTEXT_INVALID")
    receipt.__post_init__()
    source_frontier.__post_init__()
    _require_registered_source_pin(selection)
    if (receipt.atlas_bundle_id != selection.bundle_id
            or receipt.semantic_release != selection.release_sha256
            or receipt.source_bundle_id != selection.source_bundle_id):
        _fail("A12_EXPORT_CLEARANCE_RELEASE_DRIFT")
    if (receipt.rights_epoch != source_frontier.rights_epoch
            or receipt.correction_generation != source_frontier.correction_generation
            or receipt.source_frontier_sha256 != contract_digest(source_frontier)):
        _fail("A12_EXPORT_CLEARANCE_FRONTIER_DRIFT")
    if any(grant.rights_epoch != source_frontier.rights_epoch
           or grant.correction_generation != source_frontier.correction_generation
           or grant.semantic_release != receipt.semantic_release
           for grant in source_frontier.grants):
        _fail("A12_EXPORT_CLEARANCE_GRANT_DRIFT")
    if artifact_digests != receipt.export_artifact_digests:
        _fail("A12_EXPORT_CLEARANCE_ARTIFACT_DRIFT")
    return receipt.clearance_sha256
