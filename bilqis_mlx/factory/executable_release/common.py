"""Wire identities and canonical digest helpers for executable releases."""
from __future__ import annotations
import hashlib
import json

SCHEMA = "bilqis.mlx.factory-release/v2"


class _ReleaseError:
    """Stable legacy wire codes owned by the executable-release contract."""

    MODALITY_DRIFT = "FACTORY_EXECUTABLE_RELEASE_MODALITY_DRIFT"
    PROVIDER_DRIFT = "FACTORY_EXECUTABLE_RELEASE_PROVIDER_DRIFT"
    ANSWER_HEAD_DRIFT = "FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_DRIFT"
    CATALOG_INVALID = "FACTORY_EXECUTABLE_RELEASE_CATALOG_INVALID"
    CATALOG_DRIFT = "FACTORY_EXECUTABLE_RELEASE_CATALOG_DRIFT"
    SEMANTIC_GRAPH_INVALID = "FACTORY_EXECUTABLE_RELEASE_SEMANTIC_GRAPH_INVALID"
    SEMANTIC_GRAPH_DRIFT = "FACTORY_EXECUTABLE_RELEASE_SEMANTIC_GRAPH_DRIFT"
    SEMANTIC_CATALOG_REQUIRED = "FACTORY_EXECUTABLE_RELEASE_SEMANTIC_CATALOG_REQUIRED"
    VERIFICATION_INVALID = "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_INVALID"
    VERIFICATION_DRIFT = "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DRIFT"
    ASSESSMENT_DRIFT = "FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_DRIFT"
    LINEAGE_DRIFT = "FACTORY_EXECUTABLE_RELEASE_LINEAGE_DRIFT"


def _require(condition: bool, code: str) -> None:
    """Fail one named release invariant without duplicating its wire identity."""
    if not condition:
        raise ValueError(code)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def _require_sha256(value: str, code: str) -> str:
    if (not isinstance(value, str) or len(value) != 64 or
            any(char not in "0123456789abcdef" for char in value)):
        raise ValueError(code)
    return value


def _tuples(value):
    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuples(item) for key, item in value.items()}
    return value


