"""Durable B13 accepted-authority checkpoints and protected current-tip ownership."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH, data_plane
from bilqis_mlx.errors import BilqisError

from ..records import canonical, invalid, sha


ACCEPTED_AUTHORITY_CHECKPOINT_SCHEMA = (
    "bilqis.mlx.bamf-accepted-authority-checkpoint/v1"
)
_CHECKPOINT_KINDS = frozenset({"GENESIS", "INCREMENTAL", "AUDIT_BACKFILL"})


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _optional_hex(value: object) -> bool:
    return value is None or _hex(value)


@dataclass(frozen=True)
class AcceptedAuthorityCheckpoint:
    """Compact durable commitment for one already-established accepted epoch."""

    run_id: str
    run_identity_sha256: str
    generation: int
    manifest_sha256: str
    acceptance_sha256: str
    pointer_sha256: str
    acceptance_file_sha256: str
    candidate_identity_sha256: str
    optimizer_step: int
    topology_sha256: str
    extents_sha256: str
    implementation_sha256: str
    feature_receipt_sha256: str
    feature_artifact_sha256: str
    source_authority_registry_sha256: str
    semantic_release_sha256: str
    atlas_bundle_sha256: str
    factory_release_sha256: str
    genesis_trust_sha256: str
    parent_checkpoint_sha256: str | None = None
    parent_manifest_sha256: str | None = None
    parent_acceptance_sha256: str | None = None
    parent_candidate_identity_sha256: str | None = None
    cadence_projection_sha256: str | None = None
    teacher_authority_sha256: str | None = None
    audit_receipt_sha256: str | None = None
    kind: str = "INCREMENTAL"
    schema_version: str = ACCEPTED_AUTHORITY_CHECKPOINT_SCHEMA

    def __post_init__(self) -> None:
        required_digests = (
            self.run_identity_sha256, self.manifest_sha256,
            self.acceptance_sha256, self.pointer_sha256,
            self.acceptance_file_sha256, self.candidate_identity_sha256,
            self.topology_sha256, self.extents_sha256,
            self.implementation_sha256, self.feature_receipt_sha256,
            self.feature_artifact_sha256,
            self.source_authority_registry_sha256,
            self.semantic_release_sha256, self.atlas_bundle_sha256,
            self.factory_release_sha256, self.genesis_trust_sha256,
        )
        optional_digests = (
            self.parent_checkpoint_sha256, self.parent_manifest_sha256,
            self.parent_acceptance_sha256,
            self.parent_candidate_identity_sha256,
            self.cadence_projection_sha256, self.teacher_authority_sha256,
            self.audit_receipt_sha256,
        )
        if (self.schema_version != ACCEPTED_AUTHORITY_CHECKPOINT_SCHEMA
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or self.kind not in _CHECKPOINT_KINDS
                or any(not _hex(value) for value in required_digests)
                or any(not _optional_hex(value) for value in optional_digests)):
            invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
        parent_identity = (
            self.parent_manifest_sha256, self.parent_acceptance_sha256,
            self.parent_candidate_identity_sha256,
        )
        if self.kind == "GENESIS":
            if (self.generation != 0 or self.parent_checkpoint_sha256 is not None
                    or any(value is not None for value in parent_identity)
                    or self.audit_receipt_sha256 is not None):
                invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
        elif self.kind == "INCREMENTAL":
            if (self.generation == 0 or self.parent_checkpoint_sha256 is None
                    or any(value is None for value in parent_identity)
                    or self.audit_receipt_sha256 is not None):
                invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
        elif self.kind == "AUDIT_BACKFILL":
            if (self.parent_checkpoint_sha256 is not None
                    or self.audit_receipt_sha256 is None
                    or (self.generation == 0
                        and any(value is not None for value in parent_identity))
                    or (self.generation > 0
                        and any(value is None for value in parent_identity))):
                invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")

    @property
    def payload(self) -> bytes:
        return canonical(asdict(self))

    @property
    def digest(self) -> str:
        return sha(self.payload)

    def to_record(self) -> dict:
        return {**asdict(self), "checkpoint_sha256": self.digest}

    @classmethod
    def from_record(cls, record) -> "AcceptedAuthorityCheckpoint":
        names = {field.name for field in fields(cls)}
        if (not isinstance(record, dict)
                or set(record) != names | {"checkpoint_sha256"}):
            invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
        checkpoint = cls(**{name: record[name] for name in names})
        if record["checkpoint_sha256"] != checkpoint.digest:
            invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
        return checkpoint


def issue_accepted_authority_checkpoint(
        *, run_id: str, run_identity_sha256: str, generation: int,
        manifest_sha256: str, acceptance_sha256: str, pointer_sha256: str,
        acceptance_file_sha256: str, candidate_identity_sha256: str,
        optimizer_step: int, topology_sha256: str, extents_sha256: str,
        implementation_sha256: str, feature_receipt_sha256: str,
        feature_artifact_sha256: str, source_authority_registry_sha256: str,
        semantic_release_sha256: str, atlas_bundle_sha256: str,
        factory_release_sha256: str, genesis_trust_sha256: str,
        parent_checkpoint_sha256: str | None = None,
        parent_manifest_sha256: str | None = None,
        parent_acceptance_sha256: str | None = None,
        parent_candidate_identity_sha256: str | None = None,
        cadence_projection_sha256: str | None = None,
        teacher_authority_sha256: str | None = None,
        audit_receipt_sha256: str | None = None,
        kind: str = "INCREMENTAL",
) -> AcceptedAuthorityCheckpoint:
    """Issue one canonical checkpoint record from already-authenticated B13 inputs."""
    return AcceptedAuthorityCheckpoint(
        run_id=run_id, run_identity_sha256=run_identity_sha256,
        generation=generation, manifest_sha256=manifest_sha256,
        acceptance_sha256=acceptance_sha256, pointer_sha256=pointer_sha256,
        acceptance_file_sha256=acceptance_file_sha256,
        candidate_identity_sha256=candidate_identity_sha256,
        optimizer_step=optimizer_step, topology_sha256=topology_sha256,
        extents_sha256=extents_sha256,
        implementation_sha256=implementation_sha256,
        feature_receipt_sha256=feature_receipt_sha256,
        feature_artifact_sha256=feature_artifact_sha256,
        source_authority_registry_sha256=source_authority_registry_sha256,
        semantic_release_sha256=semantic_release_sha256,
        atlas_bundle_sha256=atlas_bundle_sha256,
        factory_release_sha256=factory_release_sha256,
        genesis_trust_sha256=genesis_trust_sha256,
        parent_checkpoint_sha256=parent_checkpoint_sha256,
        parent_manifest_sha256=parent_manifest_sha256,
        parent_acceptance_sha256=parent_acceptance_sha256,
        parent_candidate_identity_sha256=parent_candidate_identity_sha256,
        cadence_projection_sha256=cadence_projection_sha256,
        teacher_authority_sha256=teacher_authority_sha256,
        audit_receipt_sha256=audit_receipt_sha256, kind=kind,
    )


def _parse_payload(raw: bytes, *, expected_sha256: str) -> AcceptedAuthorityCheckpoint:
    import json

    if sha(raw) != expected_sha256:
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_DRIFT")
    try:
        record = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
    checkpoint = AcceptedAuthorityCheckpoint(**record)
    if checkpoint.digest != expected_sha256:
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_DRIFT")
    return checkpoint


def store_accepted_authority_checkpoint(
        checkpoint: AcceptedAuthorityCheckpoint) -> str:
    """Persist one immutable checkpoint row without advancing accepted authority."""
    if type(checkpoint) is not AcceptedAuthorityCheckpoint:
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED")
    checkpoint.__post_init__()
    try:
        data_plane()._store_accepted_authority_checkpoint(
            checkpoint.digest, checkpoint.run_id, checkpoint.generation,
            checkpoint.manifest_sha256, checkpoint.parent_checkpoint_sha256,
            checkpoint.payload,
        )
    except ValueError as error:
        invalid(str(error))
    return checkpoint.digest


def load_accepted_authority_checkpoint(
        checkpoint_sha256: str) -> AcceptedAuthorityCheckpoint:
    """Load and content-verify one immutable checkpoint by exact identity."""
    if not _hex(checkpoint_sha256):
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
    try:
        row = data_plane()._accepted_authority_checkpoint(checkpoint_sha256)
    except ValueError as error:
        invalid(str(error))
    if row is None:
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED")
    run_id, generation, manifest_sha256, parent_checkpoint_sha256, raw = row
    checkpoint = _parse_payload(raw, expected_sha256=checkpoint_sha256)
    if (checkpoint.run_id != run_id or checkpoint.generation != generation
            or checkpoint.manifest_sha256 != manifest_sha256
            or checkpoint.parent_checkpoint_sha256 != parent_checkpoint_sha256):
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_DRIFT")
    return checkpoint


def read_protected_accepted_authority_tip(
        run_id: str) -> AcceptedAuthorityCheckpoint | None:
    """Read the B13-protected current checkpoint without using generic references."""
    if not isinstance(run_id, str) or not run_id:
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
    row = data_plane()._accepted_authority_tip(run_id)
    if row is None:
        return None
    checkpoint_sha256, generation = row
    checkpoint = load_accepted_authority_checkpoint(checkpoint_sha256)
    if checkpoint.run_id != run_id or checkpoint.generation != generation:
        invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")
    return checkpoint


def require_accepted_authority_checkpoint(
        run_id: str, current_manifest_sha256: str) -> AcceptedAuthorityCheckpoint:
    """Require the current manifest's checkpoint to be the protected accepted tip."""
    if (not isinstance(run_id, str) or not run_id
            or not _hex(current_manifest_sha256)):
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
    try:
        row = data_plane()._accepted_authority_checkpoint_for_manifest(
            run_id, current_manifest_sha256)
    except ValueError as error:
        invalid(str(error))
    if row is None:
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED")
    checkpoint_sha256, generation, parent_checkpoint_sha256, raw = row
    checkpoint = _parse_payload(raw, expected_sha256=checkpoint_sha256)
    if (checkpoint.run_id != run_id
            or checkpoint.generation != generation
            or checkpoint.manifest_sha256 != current_manifest_sha256
            or checkpoint.parent_checkpoint_sha256 != parent_checkpoint_sha256):
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_DRIFT")
    tip = read_protected_accepted_authority_tip(run_id)
    if tip is None or tip.digest != checkpoint.digest:
        invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")
    return checkpoint


def accepted_authority_tip_extends_checkpoint(
        run_id: str, checkpoint_sha256: str) -> bool:
    """Prove current protected B13 authority extends one accepted checkpoint.

    This walks only compact immutable checkpoint rows. It never substitutes for
    pre-checkpoint historical custody: an audit-backfill boundary returns False.
    """
    try:
        target = load_accepted_authority_checkpoint(checkpoint_sha256)
    except BilqisError:
        # The target identity comes only from a non-authoritative memo. A stale
        # or corrupt memo must miss, while corruption encountered walking the
        # actual protected tip remains fail-closed below.
        return False
    if target.run_id != run_id:
        return False
    current = read_protected_accepted_authority_tip(run_id)
    while current is not None and current.generation >= target.generation:
        if current.digest == target.digest:
            return True
        if current.kind != "INCREMENTAL" or current.parent_checkpoint_sha256 is None:
            return False
        parent = load_accepted_authority_checkpoint(current.parent_checkpoint_sha256)
        _require_incremental_parent(current, parent.digest)
        current = parent
    return False


def _require_incremental_parent(
        checkpoint: AcceptedAuthorityCheckpoint,
        expected_checkpoint_sha256: str) -> None:
    parent = load_accepted_authority_checkpoint(expected_checkpoint_sha256)
    if (checkpoint.kind != "INCREMENTAL"
            or checkpoint.run_id != parent.run_id
            or checkpoint.run_identity_sha256 != parent.run_identity_sha256
            or checkpoint.generation != parent.generation + 1
            or checkpoint.parent_checkpoint_sha256 != parent.digest
            or checkpoint.parent_manifest_sha256 != parent.manifest_sha256
            or checkpoint.parent_acceptance_sha256 != parent.acceptance_sha256
            or checkpoint.genesis_trust_sha256 != parent.genesis_trust_sha256):
        invalid("BAMF_ACCEPTED_AUTHORITY_PARENT_DRIFT")


def compare_and_swap_protected_accepted_authority_tip(
        checkpoint: AcceptedAuthorityCheckpoint, *,
        expected_checkpoint_sha256: str | None) -> str:
    """Advance the protected tip only from the exact authenticated parent checkpoint."""
    if type(checkpoint) is not AcceptedAuthorityCheckpoint:
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED")
    checkpoint.__post_init__()
    stored = load_accepted_authority_checkpoint(checkpoint.digest)
    if stored != checkpoint:
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_DRIFT")
    if expected_checkpoint_sha256 is None:
        if checkpoint.kind not in {"GENESIS", "AUDIT_BACKFILL"}:
            invalid("BAMF_ACCEPTED_AUTHORITY_PARENT_DRIFT")
    else:
        if not _hex(expected_checkpoint_sha256):
            invalid("BAMF_ACCEPTED_AUTHORITY_PARENT_DRIFT")
        _require_incremental_parent(checkpoint, expected_checkpoint_sha256)
    try:
        data_plane()._compare_and_swap_accepted_authority_tip(
            checkpoint.run_id, expected_checkpoint_sha256, checkpoint.digest)
    except ValueError as error:
        invalid(str(error))
    return checkpoint.digest


__all__ = (
    "ACCEPTED_AUTHORITY_CHECKPOINT_SCHEMA",
    "AcceptedAuthorityCheckpoint",
    "accepted_authority_tip_extends_checkpoint",
    "compare_and_swap_protected_accepted_authority_tip",
    "issue_accepted_authority_checkpoint",
    "load_accepted_authority_checkpoint",
    "read_protected_accepted_authority_tip",
    "require_accepted_authority_checkpoint",
    "store_accepted_authority_checkpoint",
)
