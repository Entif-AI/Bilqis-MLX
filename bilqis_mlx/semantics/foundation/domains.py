"""Unqualified finite-domain proposals on the existing literal/token ABI.

These declarations allocate no tokens and certify no source or morphology.
Decimal text preserves the wire representation used by semantics.foundation.numeric;
native integer results must be encoded explicitly at the adapter boundary.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import json
import re

from .core import Literal, TypedError, literal
from .laws import SourceLocator


def contract_digest(value) -> str:
    def canonical(item):
        if isinstance(item, Enum):
            return canonical(item.value)
        if is_dataclass(item) and not isinstance(item, type):
            return {field.name: canonical(getattr(item, field.name)) for field in fields(item)}
        if isinstance(item, Mapping):
            if any(type(key) is not str for key in item):
                raise TypedError("DOMAIN_CONTRACT_MAPPING_KEY_NOT_TEXT")
            return {key: canonical(item[key]) for key in item}
        if isinstance(item, (tuple, list)):
            return [canonical(child) for child in item]
        if item is None or type(item) in (str, bool, int):
            return item
        raise TypedError("DOMAIN_UNSERIALIZABLE_CONTRACT_VALUE:" + type(item).__name__)

    return hashlib.sha256(json.dumps(canonical(value), sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def require_sha256(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise TypedError("DOMAIN_INVALID_SHA256")


@dataclass(frozen=True)
class SourceBinding:
    locator: SourceLocator
    content_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.locator, SourceLocator):
            raise TypedError("DOMAIN_SOURCE_LOCATOR_REQUIRED")
        require_sha256(self.content_sha256)


class ValueCodec(str, Enum):
    LITERAL = "LITERAL"
    DECIMAL_INTEGER_TEXT = "DECIMAL_INTEGER_TEXT"


class AnswerMode(str, Enum):
    BINARY = "binary"
    FINITE_TYPED = "finite_typed"
    NATIVE_TOKEN = "native_token"


@dataclass(frozen=True)
class FiniteDomain:
    identity: str
    revision: str
    type_name: str
    values: tuple[Literal, ...]
    source: SourceBinding
    codec: ValueCodec = ValueCodec.LITERAL
    closed: bool = False
    world_contract: str | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.identity, str) or not self.identity.strip()
                or not isinstance(self.revision, str) or not self.revision.strip()
                or not isinstance(self.source, SourceBinding)
                or not isinstance(self.codec, ValueCodec) or type(self.closed) is not bool
                or not isinstance(self.values, tuple) or not self.values):
            raise TypedError("DOMAIN_INVALID_DECLARATION")
        for value in self.values:
            if (not isinstance(value, Literal) or value.type_name != self.type_name
                    or value.world_contract != self.world_contract):
                raise TypedError("DOMAIN_LITERAL_SCOPE_MISMATCH")
            if self.codec is ValueCodec.DECIMAL_INTEGER_TEXT:
                if (type(value.value) is not str
                        or re.fullmatch(r"0|-?[1-9][0-9]*", value.value) is None):
                    raise TypedError("DOMAIN_NONCANONICAL_DECIMAL_TEXT")
        keys = tuple(contract_digest(value) for value in self.values)
        if len(set(keys)) != len(keys):
            raise TypedError("DOMAIN_DUPLICATE_LITERAL")
        if self.type_name == "Boolean" and self.closed:
            if {value.value for value in self.values} != {False, True}:
                raise TypedError("DOMAIN_INCOMPLETE_CLOSED_BOOLEAN")

    def accepts(self, value: Literal) -> bool:
        return isinstance(value, Literal) and value in self.values

    def encode(self, result: str | bool | int) -> Literal:
        if self.codec is ValueCodec.DECIMAL_INTEGER_TEXT:
            if type(result) is not int:
                raise TypedError("DOMAIN_INTEGER_RESULT_REQUIRED")
            result = str(result)
        elif type(result) not in (str, bool):
            raise TypedError("DOMAIN_LITERAL_RESULT_REQUIRED")
        value = literal(result, self.type_name, world_contract=self.world_contract)
        if not self.accepts(value):
            raise TypedError("DOMAIN_RESULT_OUTSIDE_DECLARED_SCOPE")
        return value

    def decode(self, value: Literal) -> str | bool | int:
        if not self.accepts(value):
            raise TypedError("DOMAIN_LITERAL_OUTSIDE_DECLARED_SCOPE")
        return int(value.value) if self.codec is ValueCodec.DECIMAL_INTEGER_TEXT else value.value


@dataclass(frozen=True)
class AnswerContract:
    mode: AnswerMode
    domain: FiniteDomain
    native_tokens: tuple[tuple[Literal, int], ...] = ()
    catalog_sha256: str | None = None
    native_identities: tuple[tuple[Literal, str], ...] = ()

    def __post_init__(self) -> None:
        if (not isinstance(self.mode, AnswerMode) or not isinstance(self.domain, FiniteDomain)
                or not isinstance(self.native_tokens, tuple) or not isinstance(self.native_identities, tuple)):
            raise TypedError("DOMAIN_INVALID_ANSWER_CONTRACT")
        if self.mode is AnswerMode.BINARY:
            if (self.domain.type_name != "Boolean" or not self.domain.closed
                    or self.domain.codec is not ValueCodec.LITERAL):
                raise TypedError("DOMAIN_BINARY_CONTRACT_MISMATCH")
        if self.mode is AnswerMode.NATIVE_TOKEN:
            require_sha256(self.catalog_sha256)
            if (not isinstance(self.native_tokens, tuple) or any(
                    not isinstance(pair, tuple) or len(pair) != 2 or not isinstance(pair[0], Literal)
                    for pair in self.native_tokens)):
                raise TypedError("DOMAIN_NATIVE_MAPPING_NOT_BIJECTIVE")
            values = tuple(value for value, _ in self.native_tokens)
            indices = tuple(index for _, index in self.native_tokens)
            if (set(values) != set(self.domain.values) or len(values) != len(set(values))
                    or len(indices) != len(set(indices))
                    or any(type(index) is not int or index < 0 for index in indices)):
                raise TypedError("DOMAIN_NATIVE_MAPPING_NOT_BIJECTIVE")
            if self.native_identities:
                if (not isinstance(self.native_identities, tuple) or any(
                        not isinstance(pair, tuple) or len(pair) != 2 or not isinstance(pair[0], Literal)
                        or not isinstance(pair[1], str) or not pair[1].strip() for pair in self.native_identities)):
                    raise TypedError("DOMAIN_NATIVE_IDENTITY_BINDINGS_INVALID")
                if (len(self.native_identities) != len(values) or
                        set(value for value, _ in self.native_identities) != set(values) or
                        len(set(identity for _, identity in self.native_identities)) != len(values)):
                    raise TypedError("DOMAIN_NATIVE_IDENTITY_BINDINGS_INVALID")
        elif self.native_tokens or self.catalog_sha256 is not None or self.native_identities:
            raise TypedError("DOMAIN_UNEXPECTED_NATIVE_MAPPING")

    def token_for(self, value: Literal) -> int:
        if self.mode is not AnswerMode.NATIVE_TOKEN or not self.domain.accepts(value):
            raise TypedError("DOMAIN_NATIVE_TOKEN_NOT_DECLARED")
        return dict(self.native_tokens)[value]
