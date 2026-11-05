"""Released frame-schema contracts with source-owned authority."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.released_frame_schemas")
import hashlib
import json
import re
from ...errors import BilqisError, ErrorBus, SEMANTIC_FRAME


MANIFEST_SCHEMA = "bilqis.released-frame-schema-manifest/v1"
BODY_SCHEMA = "bilqis.released-frame-schema-body/v1"
WITNESS_SCHEMA = "bilqis.released-frame-schema-body-witness/v1"
SOURCE_PIN_REGISTRY_SCHEMA = "bilqis.frame-schema-source-pins/v1"
SOURCE_PIN_REGISTRY_SHA256 = (
    "101cf62df6f6dcf5f84c605782b33e069d3e3e026017f2f15e69d683ea2b73f0")
SOURCE_PIN_STATUS = "A03_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _fail(reason: str) -> None:
    ErrorBus.raise_(SEMANTIC_FRAME.CODEC.INVALID, reason=reason)



def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()



def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _public()._fail("FRAME_RELEASED_SCHEMA_JSON_DUPLICATE_KEY")
        result[key] = value
    return result



def _json(payload: bytes) -> dict:
    if not isinstance(payload, bytes):
        _public()._fail("FRAME_RELEASED_SCHEMA_BYTES_REQUIRED")
    try:
        value = json.loads(payload, object_pairs_hook=_public()._unique_pairs)
    except BilqisError:
        raise
    except (ValueError, UnicodeError, TypeError):
        _public()._fail("FRAME_RELEASED_SCHEMA_JSON_INVALID")
    if not isinstance(value, dict):
        _public()._fail("FRAME_RELEASED_SCHEMA_JSON_INVALID")
    return value
