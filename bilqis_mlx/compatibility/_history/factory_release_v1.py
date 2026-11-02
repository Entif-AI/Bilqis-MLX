"""Decoder for sealed ``bilqis.mlx.factory-release/v1`` artifacts.

The raw canonical payload owns its historical digest. Later Python model fields
may gain safe defaults, but those defaults must not rewrite the identity of a
previously sealed artifact.
"""
from __future__ import annotations

import hashlib
import json

from ..errors import ErrorBus, FACTORY
from ..factory.model import FactoryRelease


def _wire_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def decode_sealed_factory_release_v1(
    payload: dict, release_sha256: str,
) -> FactoryRelease:
    """Verify historical wire identity, then project into today's typed model."""
    if _wire_digest(payload) != release_sha256:
        ErrorBus.raise_(
            FACTORY.RELEASE.MANIFEST_CONTENT_DRIFT,
            release_sha256=release_sha256)
    release = FactoryRelease._decode_manifest(payload, release_sha256)
    if payload.get("course_sha256") != release.course.digest():
        ErrorBus.raise_(
            FACTORY.RELEASE.MANIFEST_CONTENT_DRIFT,
            release_sha256=release_sha256)
    release.verify_contract()
    return release
