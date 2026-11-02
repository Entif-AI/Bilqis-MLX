"""Pure stable capability identity contracts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.foundation.core import Signature


CAPABILITY_IDENTITY_SCHEMA = "bilqis.capability-identity/v1"
_CAPABILITY_ID = re.compile(r"cap:[0-9a-f]{64}\Z")


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CapabilityIdentityInput:
    """Only semantic/operator meaning participates in stable identity."""

    semantic_id: str
    family_id: str
    operator_id: str
    signature: Signature
    answer_kinds: tuple[str, ...]
    schema: str = CAPABILITY_IDENTITY_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_id, str) or not self.semantic_id
                or not isinstance(self.family_id, str) or not self.family_id
                or not isinstance(self.operator_id, str) or not self.operator_id
                or type(self.signature) is not Signature
                or not isinstance(self.answer_kinds, tuple)
                or not self.answer_kinds
                or self.answer_kinds != tuple(sorted(set(self.answer_kinds)))
                or any(not isinstance(item, str) or not item
                       for item in self.answer_kinds)
                or self.schema != CAPABILITY_IDENTITY_SCHEMA):
            _fail("FACTORY_CAPABILITY_IDENTITY_INPUT_INVALID")

    def canonical_payload(self) -> tuple:
        return (
            self.schema, self.semantic_id, self.family_id, self.operator_id,
            self.signature.inputs, self.signature.output, self.answer_kinds,
        )


@dataclass(frozen=True)
class StableCapabilityIdentity:
    capability_id: str
    identity: CapabilityIdentityInput

    def __post_init__(self) -> None:
        if (not isinstance(self.capability_id, str)
                or not _CAPABILITY_ID.fullmatch(self.capability_id)
                or self.capability_id != stable_capability_id(self.identity)):
            _fail("FACTORY_CAPABILITY_IDENTITY_DIGEST_MISMATCH")


@dataclass(frozen=True)
class ReleaseCapabilityIdentityBinding:
    factory_release_sha256: str
    release_capability_id: str
    stable_identity: StableCapabilityIdentity

    def __post_init__(self) -> None:
        if (not isinstance(self.factory_release_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", self.factory_release_sha256)
                or not isinstance(self.release_capability_id, str)
                or not self.release_capability_id
                or type(self.stable_identity) is not StableCapabilityIdentity):
            _fail("FACTORY_CAPABILITY_IDENTITY_RELEASE_BINDING_INVALID")


def stable_capability_id(identity: CapabilityIdentityInput) -> str:
    """Derive identity without grade, provider, source path, or root ordinal."""
    if type(identity) is not CapabilityIdentityInput:
        _fail("FACTORY_CAPABILITY_IDENTITY_REQUIRED")
    CapabilityIdentityInput.__post_init__(identity)
    return "cap:" + _digest(identity.canonical_payload())


def bind_stable_capability_identity(
    semantic_id: str, family_id: str, operator_id: str,
    signature: Signature, answer_kinds: tuple[str, ...],
) -> StableCapabilityIdentity:
    identity = CapabilityIdentityInput(
        semantic_id, family_id, operator_id, signature, answer_kinds)
    return StableCapabilityIdentity(stable_capability_id(identity), identity)
