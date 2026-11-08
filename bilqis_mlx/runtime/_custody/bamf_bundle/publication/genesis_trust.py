"""External B13 trust root for accepted generation-zero custody."""
from __future__ import annotations

import json

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH, data_plane
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest

from ..records import CompleteStudent, canonical, invalid


GENESIS_TRUST_SCHEMA = "bilqis.mlx.bamf-genesis-trust/v1"
_REFERENCE_PREFIX = "bamf-genesis-trust-v1:"


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _reference(run_id: str, manifest_sha256: str) -> str:
    if not isinstance(run_id, str) or not run_id or not _hex(manifest_sha256):
        invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_INVALID")
    return f"{_REFERENCE_PREFIX}{run_id}:{manifest_sha256}"


def _trust_record(prepared, manifest_sha256: str) -> dict:
    """Project one accepted-custody receipt from the live prepared capability."""
    from ..genesis import PreparedInitialGeneration, validate_initial_generation_binding

    if type(prepared) is not PreparedInitialGeneration:
        invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
    prepared.__post_init__()
    candidate = prepared.candidate
    validate_initial_generation_binding(candidate, prepared.binding)
    identity = candidate.run_identity
    factory = prepared.factory_authority
    return {
        "schema": GENESIS_TRUST_SCHEMA,
        "run_id": candidate.run_id,
        "generation": 0,
        "manifest_sha256": manifest_sha256,
        "acceptance_sha256": prepared.binding.digest,
        "run_identity_sha256": identity.digest,
        "candidate_identity_sha256": candidate_identity_digest(candidate.retained_state),
        "topology_digest": candidate.topology.digest,
        "extents_digest": candidate.extents.digest,
        "implementation_sha256": candidate.implementation_sha256,
        "factory_state_sha256": factory.current_state_sha256,
        "factory_release_sha256": identity.factory_release_sha256,
        "semantic_graph_sha256": identity.semantic_graph_sha256,
        "source_identity": identity.initial_source_identity,
        "release_digest": identity.initial_release_digest,
        "teacher_identity": identity.initial_teacher_identity,
        "teacher_epoch": identity.initial_teacher_epoch,
    }


def publish_initial_generation_trust_root(prepared, manifest_sha256: str) -> None:
    """Persist one append-only acceptance witness outside the BAMF package."""
    record = _trust_record(prepared, manifest_sha256)
    raw = canonical(record)
    reference = _reference(record["run_id"], manifest_sha256)
    plane = data_plane()
    existing = plane.get_object_reference(reference)
    if existing is not None:
        if existing[1] != raw:
            invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_DRIFT")
        return
    plane.put_object_reference(reference, raw)
    readback = plane.get_object_reference(reference)
    if readback is None or readback[1] != raw:
        invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_DRIFT")


def require_initial_generation_trust_root(
        pointer: dict, student: CompleteStudent, binding) -> None:
    """Require the external owner-issued witness before granting cold authority."""
    identity = student.run_identity
    reference = _reference(student.run_id, pointer.get("manifest_sha256"))
    stored = data_plane().get_object_reference(reference)
    if stored is None:
        invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_REQUIRED")
    try:
        record = json.loads(stored[1])
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_INVALID")
    expected = {
        "schema": GENESIS_TRUST_SCHEMA,
        "run_id": student.run_id,
        "generation": 0,
        "manifest_sha256": pointer["manifest_sha256"],
        "acceptance_sha256": binding.digest,
        "run_identity_sha256": identity.digest,
        "candidate_identity_sha256": candidate_identity_digest(student.retained_state),
        "topology_digest": student.topology.digest,
        "extents_digest": student.extents.digest,
        "implementation_sha256": student.implementation_sha256,
        "factory_release_sha256": identity.factory_release_sha256,
        "semantic_graph_sha256": identity.semantic_graph_sha256,
        "source_identity": identity.initial_source_identity,
        "release_digest": identity.initial_release_digest,
        "teacher_identity": identity.initial_teacher_identity,
        "teacher_epoch": identity.initial_teacher_epoch,
    }
    if (not isinstance(record, dict)
            or set(record) != set(expected) | {"factory_state_sha256"}
            or any(record.get(name) != value for name, value in expected.items())
            or not _hex(record.get("factory_state_sha256"))):
        invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_INVALID")


__all__ = (
    "publish_initial_generation_trust_root", "require_initial_generation_trust_root",
)
