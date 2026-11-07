"""B01-owned generation geometry and implementation authority."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import hashlib
import json

from .ledger import bamf_parameter_census
from .records import GenerationExtents, ParameterCensus
from .spec import ModelTopologySpecV2


AUTHORITY_SCHEMA = "bilqis.mlx.b01-generation-authority/v1"
IMPLEMENTATION_SCHEMA = "bilqis.mlx.bamf-model-implementation/v1"
IMPLEMENTATION_FILES = (
    "spec.py",
    "dimensions.py",
    "records.py",
    "ledger.py",
    "initialization.py",
    "factors.py",
    "validation.py",
    "construction.py",
    "serialization.py",
)


def _sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def b01_model_implementation_sha256(*, overrides: Mapping[str, bytes] | None = None) -> str:
    """Fingerprint the accepted B01 implementation surface, never a caller label."""
    root = Path(__file__).resolve().parent
    supplied = {} if overrides is None else dict(overrides)
    material = {
        "schema": IMPLEMENTATION_SCHEMA,
        "files": tuple(
            (name, hashlib.sha256(
                supplied[name] if name in supplied else (root / name).read_bytes()
            ).hexdigest())
            for name in IMPLEMENTATION_FILES
        ),
    }
    return hashlib.sha256(json.dumps(
        material, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def b01_generation_extents(*, semantic_abi: Mapping, compiler_features: Mapping,
                           motif_page_count: int,
                           motif_key_map_digest: str) -> GenerationExtents:
    """Project generation extents from the already-bound owner sidecars."""
    if (not isinstance(semantic_abi, Mapping)
            or semantic_abi.get("schema") != "bilqis.mlx.bamf-semantic-abi/v1"
            or type(semantic_abi.get("semantic_bank_count")) is not int
            or semantic_abi["semantic_bank_count"] < 1
            or not isinstance(semantic_abi.get("bank_identities"), (tuple, list))
            or len(semantic_abi["bank_identities"])
            != semantic_abi["semantic_bank_count"]
            or not _sha(semantic_abi.get("active_set_sha256"))
            or not isinstance(compiler_features, Mapping)
            or compiler_features.get("schema")
            != "bilqis.mlx.bamf-compiler-features/v1"
            or not _sha(compiler_features.get("factor_map_sha256"))
            or type(motif_page_count) is not int or motif_page_count < 1
            or not _sha(motif_key_map_digest)):
        raise ValueError("B01_GENERATION_EXTENTS_AUTHORITY_INVALID")
    return GenerationExtents(
        semantic_abi["semantic_bank_count"], motif_page_count,
        semantic_abi["active_set_sha256"], motif_key_map_digest,
        compiler_features["factor_map_sha256"])


@dataclass(frozen=True)
class B01GenerationAuthority:
    """B01 census plus implementation identity, rederived by B13 before use."""

    parameter_census: ParameterCensus
    implementation_sha256: str
    schema_version: str = AUTHORITY_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != AUTHORITY_SCHEMA
                or type(self.parameter_census) is not ParameterCensus
                or not _sha(self.implementation_sha256)):
            raise ValueError("B01_GENERATION_AUTHORITY_INVALID")


def b01_generation_authority(extents: GenerationExtents) -> B01GenerationAuthority:
    """Bind the accepted B01 census and current B01 implementation surface."""
    if type(extents) is not GenerationExtents:
        raise ValueError("B01_GENERATION_EXTENTS_TYPE_INVALID")
    topology = ModelTopologySpecV2()
    return B01GenerationAuthority(
        bamf_parameter_census(topology, extents),
        b01_model_implementation_sha256())


def validate_b01_generation_authority(
        authority: B01GenerationAuthority,
        extents: GenerationExtents) -> tuple[ModelTopologySpecV2, str]:
    """Reconstruct B01 authority; a matching caller record does not mint it."""
    if type(authority) is not B01GenerationAuthority:
        raise ValueError("B01_GENERATION_AUTHORITY_TYPE_INVALID")
    expected = b01_generation_authority(extents)
    if authority != expected:
        raise ValueError("B01_GENERATION_AUTHORITY_DRIFT")
    return ModelTopologySpecV2(), expected.implementation_sha256
