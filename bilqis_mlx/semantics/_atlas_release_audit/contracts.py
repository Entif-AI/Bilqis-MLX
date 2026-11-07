"""Typed A12 authority-audit records and deterministic binding helpers."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from ..atlas_projection import HEX64, _canonical_bytes, _fail

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
    path = Path(__file__).resolve().parents[1] / "copular_registry_v1.json"
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
                       for value in (self.semantic_release, self.source_bundle_id,
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
                for value in (self.source_release_sha256, self.source_bundle_id,
                              self.atlas_bundle_id, self.graph_projection_sha256,
                              self.prior_abi_sha256, self.audit_sha256))
                or type(self.consumer_bindings) is not tuple
                or tuple(item.consumer for item in self.consumer_bindings)
                != ("abi", "ast_frames", "lessons", "graph_projection",
                    "registry_mirror")
                or any(type(item) is not ConsumerBinding for item in self.consumer_bindings)
                or not _digests(self.formal_domain_digests, allow_empty=True)
                or self.source_dispositions[:len(SOURCE_DISPOSITIONS)] != SOURCE_DISPOSITIONS
                or any(type(item) is not tuple or len(item) != SOURCE_DISPOSITION_PARTS
                       or not all(type(value) is str and value for value in item)
                       or item[1] != "DECLARED_FORMAL_DOMAIN"
                       for item in self.source_dispositions[len(SOURCE_DISPOSITIONS):])
                or self.status != AUTHORITY_AUDIT_STATUS
                or self.schema_version != AUTHORITY_AUDIT_SCHEMA):
            _fail("A12_AUTHORITY_RECEIPT_INVALID")


def graph_projection_digest(snapshot) -> str:
    return _sha({
        "schema": "bilqis.a12.graph-projection/v1",
        "semantic_release": snapshot.release_sha256,
        "source_bundle_id": snapshot.source_bundle_id,
        "semantic_lookup": snapshot.semantic_lookup,
        "concept_lookup": snapshot.concept_lookup,
        "relations": [asdict(item) for item in snapshot.relations],
    })


def consumer_bindings(snapshot, abi, ast, lessons, mirror, graph_digest):
    manifest = ast.manifest
    return (
        ConsumerBinding("abi", abi.schema_version, snapshot.release_sha256,
                        snapshot.source_bundle_id, _sha(asdict(abi))),
        ConsumerBinding("ast_frames", manifest.schema_version, snapshot.release_sha256,
                        snapshot.source_bundle_id, ast.trusted_sha256),
        ConsumerBinding("lessons", lessons.schema, snapshot.release_sha256,
                        snapshot.source_bundle_id, _sha(asdict(lessons))),
        ConsumerBinding("graph_projection", "bilqis.a12.graph-projection/v1",
                        snapshot.release_sha256, snapshot.source_bundle_id, graph_digest),
        ConsumerBinding("registry_mirror", mirror.schema_version, snapshot.release_sha256,
                        snapshot.source_bundle_id, mirror.digest),
    )
