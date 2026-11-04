"""B13 accepted-generation feature authority.

Publication is not source authority. This owner mints one immutable receipt per
accepted generation and rederives the accepted feature identity from the
admitted source release, so a caller-created candidate can never ratify its own
factor-map digest.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    AcceptedCandidateBinding, candidate_identity_digest,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)

from .codec import load_bamf_bundle
from .publication import ACCEPTANCE_DIR, _pointer_lock, _read_pointer
from .records import canonical, invalid, sha

RECEIPT_SCHEMA = "bilqis.mlx.bamf-accepted-generation-feature-receipt/v1"
FEATURE_SOURCE_KEYS = frozenset({
    "atlas_bundle_id", "release_sha256", "source_bundle_id"})
FEATURE_SCHEMA_KEYS = frozenset({"role_ids", "schema_ids", "source_bindings"})
SOURCE_BINDING_WIDTH = 2


@dataclass(frozen=True)
class AcceptedGenerationFeatureReceipt:
    """One immutable binding between an accepted generation and its feature map."""

    run_id: str
    generation: int
    generation_manifest_sha256: str
    parent_generation_manifest_sha256: str | None
    semantic_release: str
    active_set_sha256: str
    feature_sha256: str
    predecessor_feature_sha256: str | None
    compiler_sha256: str
    implementation_sha256: str
    acceptance_sha256: str
    source_atlas_bundle_id: str
    source_release_sha256: str
    source_source_bundle_id: str
    schema_version: str = RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        digests = (
            self.generation_manifest_sha256, self.semantic_release,
            self.active_set_sha256, self.feature_sha256, self.compiler_sha256,
            self.implementation_sha256, self.acceptance_sha256,
            self.source_atlas_bundle_id, self.source_release_sha256,
            self.source_source_bundle_id,
        )
        if (self.schema_version != RECEIPT_SCHEMA
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or any(not _hex(value) for value in digests)
                or (self.parent_generation_manifest_sha256 is not None
                    and not _hex(self.parent_generation_manifest_sha256))
                or (self.predecessor_feature_sha256 is not None
                    and not _hex(self.predecessor_feature_sha256))):
            invalid("BAMF_FEATURE_RECEIPT_INVALID")

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))

    def to_record(self) -> dict:
        return {**asdict(self), "receipt_sha256": self.digest}

    @classmethod
    def from_record(cls, record) -> "AcceptedGenerationFeatureReceipt":
        names = {field.name for field in fields(cls)}
        if (not isinstance(record, dict)
                or set(record) != names | {"receipt_sha256"}):
            invalid("BAMF_FEATURE_RECEIPT_INVALID")
        receipt = cls(**{name: record[name] for name in names})
        if record["receipt_sha256"] != receipt.digest:
            invalid("BAMF_FEATURE_RECEIPT_INVALID")
        return receipt


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _feature_source(compiler_features: dict) -> dict:
    """Read the admitted source release identity recorded with the generation."""
    source = compiler_features.get("feature_source")
    if (not isinstance(source, dict) or set(source) != set(FEATURE_SOURCE_KEYS)
            or any(not _hex(source[name]) for name in FEATURE_SOURCE_KEYS)):
        invalid("BAMF_FEATURE_SOURCE_BINDING_MISSING")
    return dict(source)


def _feature_schema(compiler_features: dict) -> FeatureSchema:
    """Rebuild the recorded feature schema shape without any predecessor payload."""
    recorded = compiler_features.get("feature_schema")
    if (not isinstance(recorded, dict)
            or set(recorded) != set(FEATURE_SCHEMA_KEYS)):
        invalid("BAMF_FEATURE_SCHEMA_BINDING_MISSING")
    bindings = recorded["source_bindings"]
    if (not isinstance(recorded["role_ids"], list)
            or not isinstance(recorded["schema_ids"], list)
            or not isinstance(bindings, list)
            or any(not isinstance(row, list) or len(row) != SOURCE_BINDING_WIDTH
                   or not all(isinstance(value, str) and value for value in row)
                   for row in bindings)):
        invalid("BAMF_FEATURE_SCHEMA_BINDING_INVALID")
    try:
        return FeatureSchema(
            role_ids=tuple(recorded["role_ids"]),
            schema_ids=tuple(recorded["schema_ids"]),
            source_bindings=tuple((row[0], row[1]) for row in bindings))
    except BilqisError:
        invalid("BAMF_FEATURE_SCHEMA_BINDING_INVALID")


def _accepted_generation(pointer_path: Path):
    """Read the published accepted generation under the custody pointer lock."""
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        pointer = _read_pointer(pointer_path)
        if pointer is None:
            invalid("BAMF_FEATURE_POINTER_MISSING")
        student = load_bamf_bundle(
            pointer_path.parent / "bamf-bundles" / pointer["manifest_sha256"],
            expected_manifest_sha256=pointer["manifest_sha256"])
        if (student.run_id != pointer["run_id"]
                or student.generation != pointer["generation"]
                or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
            invalid("BAMF_FEATURE_POINTER_DRIFT")
    return pointer, student


def _accepted_binding(run_dir: Path, pointer: dict, student) -> AcceptedCandidateBinding:
    """Read the retention owner's acceptance binding for the accepted generation.

    Publication is not acceptance. Without a matching retention binding the
    generation may not mint accepted-generation authority.
    """
    path = run_dir / ACCEPTANCE_DIR / f"{pointer['manifest_sha256']}.json"
    if path.is_symlink() or not path.is_file():
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    try:
        record = json.loads(path.read_bytes())
        binding = AcceptedCandidateBinding.from_record(record)
    except (UnicodeDecodeError, json.JSONDecodeError, BilqisError):
        invalid("BAMF_GENERATION_ACCEPTANCE_INVALID")
    if (binding.run_id != pointer["run_id"]
            or binding.generation != pointer["generation"]
            or binding.feature_sha256 != student.extents.factor_map_digest
            or binding.optimizer_step != student.retained_state.optimizer_step
            or binding.candidate_identity_sha256
            != candidate_identity_digest(student.retained_state)
            or binding.step_proof_sha256 != tuple(
                proof.digest for proof in student.retained_state.step_proofs)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    return binding


def _authenticate_features(student, artifact_path: str):
    """Replay the admitted source release and rederive the accepted feature map."""
    compiler = student.compiler_features
    if compiler.get("factor_map_sha256") != student.extents.factor_map_digest:
        invalid("BAMF_FEATURE_BINDING_DRIFT")
    source = _feature_source(compiler)
    schema = _feature_schema(compiler)
    selection = AtlasArtifactSelection(
        str(artifact_path), source["atlas_bundle_id"],
        source["release_sha256"], source["source_bundle_id"])
    snapshot = load_pinned_atlas_snapshot(selection)
    try:
        features = build_feature_manifest(snapshot, schema)
    except BilqisError:
        invalid("BAMF_FEATURE_SOURCE_REPLAY_FAILED")
    if features.digest != student.extents.factor_map_digest:
        invalid("BAMF_FEATURE_SOURCE_REPLAY_MISMATCH")
    if (features.semantic_release != source["release_sha256"]
            or features.atlas_bundle_id != source["atlas_bundle_id"]
            or features.source_bundle_id != source["source_bundle_id"]):
        invalid("BAMF_FEATURE_SOURCE_IDENTITY_DRIFT")
    if student.provenance.release_digest != features.semantic_release:
        invalid("BAMF_FEATURE_RELEASE_DRIFT")
    return features


def read_accepted_generation_feature_receipt(
        pointer_path: Path, artifact_path: str) -> AcceptedGenerationFeatureReceipt:
    """Mint the receipt of the accepted generation from custody and source replay.

    The feature identity is rederived from the admitted source release, never
    taken from a caller candidate. A generation whose recorded feature map is
    not the replayed source map cannot mint a receipt.
    """
    pointer, student = _accepted_generation(pointer_path)
    binding = _accepted_binding(pointer_path.parent, pointer, student)
    features = _authenticate_features(student, artifact_path)
    predecessor = features.predecessor_digest
    if student.generation == 0:
        if predecessor is not None:
            invalid("BAMF_FEATURE_LINEAGE_DRIFT")
    elif predecessor is None:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    return AcceptedGenerationFeatureReceipt(
        run_id=student.run_id,
        generation=student.generation,
        generation_manifest_sha256=pointer["manifest_sha256"],
        parent_generation_manifest_sha256=student.parent_manifest_sha256,
        semantic_release=features.semantic_release,
        active_set_sha256=student.extents.active_semantic_digest,
        feature_sha256=features.digest,
        predecessor_feature_sha256=predecessor,
        compiler_sha256=student.compiler_features["compiler_sha256"],
        implementation_sha256=student.implementation_sha256,
        acceptance_sha256=binding.digest,
        source_atlas_bundle_id=features.atlas_bundle_id,
        source_release_sha256=features.semantic_release,
        source_source_bundle_id=features.source_bundle_id,
    )


def verify_accepted_generation_feature_receipt(
        pointer_path: Path, artifact_path: str,
        receipt: AcceptedGenerationFeatureReceipt) -> AcceptedGenerationFeatureReceipt:
    """Re-derive the live accepted receipt; a caller record alone is not authority."""
    if type(receipt) is not AcceptedGenerationFeatureReceipt:
        invalid("BAMF_FEATURE_RECEIPT_INVALID")
    expected = read_accepted_generation_feature_receipt(pointer_path, artifact_path)
    if receipt != expected:
        invalid("BAMF_FEATURE_RECEIPT_MISMATCH")
    return expected
