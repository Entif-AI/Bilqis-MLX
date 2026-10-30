"""Stable capability identity from semantic family + typed operator signature."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from bilqis_mlx.semantics.foundation.core import Signature


CAPABILITY_IDENTITY_SCHEMA = "bilqis.capability-identity/v1"
_CAPABILITY_ID = re.compile(r"cap:[0-9a-f]{64}\Z")


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CapabilityIdentityInput:
    """Only semantic/operator meaning participates in stable identity."""

    family_id: str
    signature: Signature
    answer_kinds: tuple[str, ...]
    schema: str = CAPABILITY_IDENTITY_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.family_id, str) or not self.family_id
                or type(self.signature) is not Signature
                or not isinstance(self.answer_kinds, tuple)
                or not self.answer_kinds
                or self.answer_kinds != tuple(sorted(set(self.answer_kinds)))
                or any(not isinstance(item, str) or not item
                       for item in self.answer_kinds)
                or self.schema != CAPABILITY_IDENTITY_SCHEMA):
            raise ValueError("FACTORY_CAPABILITY_IDENTITY_INPUT_INVALID")

    def canonical_payload(self) -> tuple:
        return (
            self.schema,
            self.family_id,
            self.signature.inputs,
            self.signature.output,
            self.answer_kinds,
        )


@dataclass(frozen=True)
class StableCapabilityIdentity:
    capability_id: str
    identity: CapabilityIdentityInput

    def __post_init__(self) -> None:
        if (not isinstance(self.capability_id, str)
                or not _CAPABILITY_ID.fullmatch(self.capability_id)
                or self.capability_id != stable_capability_id(self.identity)):
            raise ValueError("FACTORY_CAPABILITY_IDENTITY_DIGEST_MISMATCH")


def stable_capability_id(identity: CapabilityIdentityInput) -> str:
    """Derive identity without grade, provider, source path, or root ordinal."""
    if type(identity) is not CapabilityIdentityInput:
        raise TypeError("FACTORY_CAPABILITY_IDENTITY_REQUIRED")
    CapabilityIdentityInput.__post_init__(identity)
    return "cap:" + _digest(identity.canonical_payload())


def bind_stable_capability_identity(
    family_id: str, signature: Signature, answer_kinds: tuple[str, ...],
) -> StableCapabilityIdentity:
    identity = CapabilityIdentityInput(family_id, signature, answer_kinds)
    return StableCapabilityIdentity(stable_capability_id(identity), identity)
