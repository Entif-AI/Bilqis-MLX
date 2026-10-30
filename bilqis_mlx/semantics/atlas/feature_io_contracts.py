"""Contracts and canonical primitives for AtlasFeatures/v2 artifacts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from ...errors import ErrorBus, SEMANTIC_FRAME

ARTIFACT_SCHEMA = "bilqis.atlas-feature-artifact/v2"
RECEIPT_SCHEMA = "bilqis.atlas-feature-artifact-receipt/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FILES = frozenset({"features.json", "manifest.json"})


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<feature-artifact>",
        span_start=0, span_end=0,
    )


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _reject_nonfinite(value: str) -> None:
    raise ValueError("non-finite JSON literal: " + value)


@dataclass(frozen=True)
class FeatureArtifactReceipt:
    bundle_id: str
    path: str
    feature_digest: str
    semantic_release: str
    predecessor_digest: str | None
    schema_version: str = RECEIPT_SCHEMA
