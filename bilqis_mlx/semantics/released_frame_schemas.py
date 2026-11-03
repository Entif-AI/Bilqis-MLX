"""A03 source-release frame-schema body witnesses.

The issuer freezes the existing FrameSchema bodies and SchemaTagMap; it does
not define a second schema registry. A consumer must load the frozen bytes
against the digest supplied by the accepted A03 release, never a digest
invented alongside an untrusted candidate schema.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re

from ..errors import BilqisError, ErrorBus, SEMANTIC_FRAME
from .atlas_projection import FrozenAtlasSnapshot
from .atlas_snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from .frame_codec import (
    SchemaTagEntry, SchemaTagMap, _canonical_bytes,
)
from .frame_schema import FrameSchema, frame_schema_from_bytes


from .released_schemas.common import (
    MANIFEST_SCHEMA, BODY_SCHEMA, WITNESS_SCHEMA, SOURCE_PIN_REGISTRY_SCHEMA, SOURCE_PIN_REGISTRY_SHA256, SOURCE_PIN_STATUS, _SHA, _fail, _sha, _unique_pairs, _json,
)
from .released_schemas.records import (
    ReleasedSchemaBody, ReleasedFrameSchemaManifest, ReleasedSchemaBodyWitness,
)
from .released_schemas.verification import (
    VerifiedReleasedFrameSchemas, load_released_frame_schemas,
)
from .released_schemas.artifacts import (
    seal_released_frame_schemas, persist_released_frame_schemas,
)
from .released_schemas.source_pins import (
    _source_pins, _load_pinned_released_frame_schemas, lookup_source_pinned_frame_schema, verify_source_pinned_frame_schema, verify_source_pinned_frame_schema_bytes,
)


# Preserve published class/function identities for pickle and annotations.
for _value in (
    ReleasedSchemaBody,
    ReleasedFrameSchemaManifest,
    ReleasedSchemaBodyWitness,
    VerifiedReleasedFrameSchemas,
    seal_released_frame_schemas,
    load_released_frame_schemas,
    persist_released_frame_schemas,
    lookup_source_pinned_frame_schema,
    verify_source_pinned_frame_schema,
    verify_source_pinned_frame_schema_bytes,
):
    _value.__module__ = __name__
del _value
