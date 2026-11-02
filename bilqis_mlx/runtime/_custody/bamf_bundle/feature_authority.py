"""B13 accepted-generation authority for predecessor semantic features."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .codec import load_bamf_bundle
from .publication import _pointer_lock, _read_pointer
from .records import canonical, invalid, sha

RECEIPT_SCHEMA = "bilqis.mlx.accepted-generation-feature-authority/v1"


@dataclass(frozen=True)
class AcceptedGenerationFeatureReceipt:
    run_id: str
    generation: int
    generation_manifest_sha256: str
    parent_generation_manifest_sha256: str | None
    semantic_release: str
    active_set_sha256: str
    predecessor_feature_sha256: str
    generation_extents_sha256: str
    compiler_sha256: str
    implementation_sha256: str
    schema_version: str = RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        digests = (
            self.generation_manifest_sha256,
            self.semantic_release,
            self.active_set_sha256,
            self.predecessor_feature_sha256,
            self.generation_extents_sha256,
            self.compiler_sha256,
            self.implementation_sha256,
        )
        if (self.schema_version != RECEIPT_SCHEMA
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or any(not _hex(value) for value in digests)
                or (self.parent_generation_manifest_sha256 is not None
                    and not _hex(self.parent_generation_manifest_sha256))):
            invalid("BAMF_ACCEPTED_FEATURE_RECEIPT_INVALID")

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))

    def to_record(self) -> dict:
        return {**asdict(self), "receipt_sha256": self.digest}

    @classmethod
    def from_record(cls, record: dict) -> "AcceptedGenerationFeatureReceipt":
        names = {field.name for field in fields(cls)}
        if (not isinstance(record, dict) or set(record) != names | {"receipt_sha256"}):
            invalid("BAMF_ACCEPTED_FEATURE_RECEIPT_INVALID")
        receipt = cls(**{name: record[name] for name in names})
        if record["receipt_sha256"] != receipt.digest:
            invalid("BAMF_ACCEPTED_FEATURE_RECEIPT_INVALID")
        return receipt


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _receipt(pointer: dict, student) -> AcceptedGenerationFeatureReceipt:
    compiler = student.compiler_features
    if compiler.get("factor_map_sha256") != student.extents.factor_map_digest:
        invalid("BAMF_ACCEPTED_FEATURE_BINDING_DRIFT")
    return AcceptedGenerationFeatureReceipt(
        run_id=student.run_id,
        generation=student.generation,
        generation_manifest_sha256=pointer["manifest_sha256"],
        parent_generation_manifest_sha256=student.parent_manifest_sha256,
        semantic_release=student.provenance.release_digest,
        active_set_sha256=student.extents.active_semantic_digest,
        predecessor_feature_sha256=student.extents.factor_map_digest,
        generation_extents_sha256=student.extents.digest,
        compiler_sha256=compiler["compiler_sha256"],
        implementation_sha256=student.implementation_sha256,
    )


def read_accepted_generation_feature_receipt(
    pointer_path: Path,
) -> AcceptedGenerationFeatureReceipt:
    """Derive the receipt only from the currently published, validated B13 generation."""
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        pointer = _read_pointer(pointer_path)
        if pointer is None:
            invalid("BAMF_ACCEPTED_FEATURE_POINTER_MISSING")
        student = load_bamf_bundle(
            pointer_path.parent / pointer["bundle"],
            expected_manifest_sha256=pointer["manifest_sha256"],
        )
        if (student.run_id != pointer["run_id"]
                or student.generation != pointer["generation"]
                or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
            invalid("BAMF_ACCEPTED_FEATURE_POINTER_DRIFT")
        return _receipt(pointer, student)


def verify_accepted_generation_feature_receipt(
    pointer_path: Path, receipt: AcceptedGenerationFeatureReceipt,
) -> AcceptedGenerationFeatureReceipt:
    """Re-derive B13's live accepted receipt; a matching caller record alone is not authority."""
    if type(receipt) is not AcceptedGenerationFeatureReceipt:
        invalid("BAMF_ACCEPTED_FEATURE_RECEIPT_INVALID")
    expected = read_accepted_generation_feature_receipt(pointer_path)
    if receipt != expected:
        invalid("BAMF_ACCEPTED_FEATURE_RECEIPT_MISMATCH")
    return expected
