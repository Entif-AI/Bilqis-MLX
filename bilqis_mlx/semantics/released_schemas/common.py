"""Released frame-schema common."""
from __future__ import annotations

import hashlib
import json
import re
from ...errors import BilqisError, ErrorBus, SEMANTIC_FRAME


MANIFEST_SCHEMA = "bilqis.released-frame-schema-manifest/v1"



BODY_SCHEMA = "bilqis.released-frame-schema-body/v1"



WITNESS_SCHEMA = "bilqis.released-frame-schema-body-witness/v1"



SOURCE_PIN_REGISTRY_SCHEMA = "bilqis.frame-schema-source-pins/v1"



SOURCE_PIN_REGISTRY_SHA256 = (
    "4c8da914834f8dc5cadef67bbf9b7da1031f07cc80d4775a47d18b68af62a6c1")



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
            _fail("FRAME_RELEASED_SCHEMA_JSON_DUPLICATE_KEY")
        result[key] = value
    return result



def _json(payload: bytes) -> dict:
    if not isinstance(payload, bytes):
        _fail("FRAME_RELEASED_SCHEMA_BYTES_REQUIRED")
    try:
        value = json.loads(payload, object_pairs_hook=_unique_pairs)
    except BilqisError:
        raise
    except (ValueError, UnicodeError, TypeError):
        _fail("FRAME_RELEASED_SCHEMA_JSON_INVALID")
    if not isinstance(value, dict):
        _fail("FRAME_RELEASED_SCHEMA_JSON_INVALID")
    return value
