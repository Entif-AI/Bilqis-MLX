"""Single code-owned semantic identity ledger and typed operator projections.

The tracked release artifact is authoritative for Bilqis machine identities.
Sheet snapshots and source interpreters are independently checked inputs, never
writers to this ledger. A catalog release alone cannot authorize training.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import re

from .core import Operation, TypedError


class CatalogErrorCode(str, Enum):
    INVALID_RELEASE = "CATALOG_INVALID_RELEASE"
    DUPLICATE_TOKEN_ID = "CATALOG_DUPLICATE_TOKEN_ID"
    DUPLICATE_TOKEN_IDENTITY = "CATALOG_DUPLICATE_TOKEN_IDENTITY"
    DUPLICATE_TOKEN_SYMBOL = "CATALOG_DUPLICATE_TOKEN_SYMBOL"
    DUPLICATE_LESSON_ID = "CATALOG_DUPLICATE_LESSON_ID"
    DUPLICATE_LESSON_ALIAS = "CATALOG_DUPLICATE_LESSON_ALIAS"
    TOKEN_GAP = "CATALOG_TOKEN_INDEX_GAP"
    UNKNOWN_LESSON = "CATALOG_UNKNOWN_LESSON"
    LEGACY_ABI_DRIFT = "CATALOG_LEGACY_ABI_DRIFT"
    SOURCE_GRAPH_DRIFT = "CATALOG_SOURCE_GRAPH_DRIFT"
    SOURCE_TOKEN_DRIFT = "CATALOG_SOURCE_TOKEN_DRIFT"
    SOURCE_MEANING_DRIFT = "CATALOG_SOURCE_MEANING_DRIFT"
    SNAPSHOT_IDENTITY_DRIFT = "CATALOG_SNAPSHOT_IDENTITY_DRIFT"
    SNAPSHOT_MEANING_CHANGE = "CATALOG_SNAPSHOT_MEANING_CHANGE"
    SNAPSHOT_LESSON_DRIFT = "CATALOG_SNAPSHOT_LESSON_DRIFT"
    SNAPSHOT_SCHEMA_DRIFT = "CATALOG_SNAPSHOT_SCHEMA_DRIFT"


def _sha256(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class SemanticToken:
    index: int
    identity: str
    symbol: str
    signature: str
    arity: int
    family: str
    subtype: str
    meaning: str
    contract_sha256: str

    def __post_init__(self) -> None:
        if (type(self.index) is not int or self.index < 0 or
                not all(isinstance(item, str) and item for item in (
                    self.identity, self.symbol, self.signature, self.family,
                    self.subtype, self.meaning)) or
                type(self.arity) is not int or self.arity < 0 or
                not _sha256(self.contract_sha256)):
            raise TypedError(CatalogErrorCode.INVALID_RELEASE.value)


@dataclass(frozen=True)
class SemanticLesson:
    identity: str
    legacy_alias: str
    intent: str

    def __post_init__(self) -> None:
        if (not self.identity or not isinstance(self.identity, str) or
                not isinstance(self.legacy_alias, str) or
                not isinstance(self.intent, str) or not self.intent):
            raise TypedError(CatalogErrorCode.INVALID_RELEASE.value)


@dataclass(frozen=True)
class SemanticCatalog:
    """One version's immutable identities, independent of sheet row position."""

    release: str
    source_graph_sha256: str
    historical_token_count: int
    tokens: tuple[SemanticToken, ...]
    lessons: tuple[SemanticLesson, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.release, str) or not self.release or
                not _sha256(self.source_graph_sha256) or
                type(self.historical_token_count) is not int or
                self.historical_token_count < 1 or
                len(self.tokens) < self.historical_token_count):
            raise TypedError(CatalogErrorCode.INVALID_RELEASE.value)
        ids = [t.index for t in self.tokens]
        identities = [t.identity for t in self.tokens]
        symbols = [t.symbol for t in self.tokens]
        lessons = [l.identity for l in self.lessons]
        aliases = [l.legacy_alias for l in self.lessons if l.legacy_alias]
        checks = (
            (len(ids) != len(set(ids)), CatalogErrorCode.DUPLICATE_TOKEN_ID),
            (len(identities) != len(set(identities)), CatalogErrorCode.DUPLICATE_TOKEN_IDENTITY),
            (len(symbols) != len(set(symbols)), CatalogErrorCode.DUPLICATE_TOKEN_SYMBOL),
            (len(lessons) != len(set(lessons)), CatalogErrorCode.DUPLICATE_LESSON_ID),
            (len(aliases) != len(set(aliases)), CatalogErrorCode.DUPLICATE_LESSON_ALIAS),
            (sorted(ids) != list(range(len(ids))), CatalogErrorCode.TOKEN_GAP),
        )
        for failed, reason in checks:
            if failed:
                raise TypedError(reason.value)

    @property
    def digest(self) -> str:
        """Machine meaning digest, independent of storage/Sheet row order."""
        payload = {
            "release": self.release, "source_graph_sha256": self.source_graph_sha256,
            "historical_token_count": self.historical_token_count,
            "tokens": [vars(item) for item in sorted(self.tokens, key=lambda t: t.index)],
            "lessons": [vars(item) for item in sorted(self.lessons, key=lambda l: l.identity)],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

    def token(self, index: int) -> SemanticToken:
        if type(index) is int:
            for item in self.tokens:
                if item.index == index:
                    return item
        raise TypedError("COMPOSITION_UNKNOWN_CATALOG_ID")

    def resolve_symbol(self, symbol: str) -> SemanticToken:
        for item in self.tokens:
            if item.symbol == symbol:
                return item
        raise TypedError("COMPOSITION_UNKNOWN_EXTERNAL_ALIAS")

    def lesson(self, identity: str) -> SemanticLesson:
        for item in self.lessons:
            if item.identity == identity:
                return item
        raise TypedError(CatalogErrorCode.UNKNOWN_LESSON.value)

    def validate_historical_prefix(self, original: "SemanticCatalog") -> None:
        """Future releases cannot change what an old student token means."""
        if (self.historical_token_count != original.historical_token_count or
                any(self.token(i) != original.token(i)
                    for i in range(original.historical_token_count))):
            raise TypedError(CatalogErrorCode.LEGACY_ABI_DRIFT.value)


CATALOG_PATH = Path(__file__).with_name("original_catalog_v1.json")


def load_catalog(path: Path = CATALOG_PATH) -> SemanticCatalog:
    """Load the tracked code-owned release, never a Sheet or external proposal."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "bilqis.semantic-catalog/v1":
        raise TypedError(CatalogErrorCode.INVALID_RELEASE.value)
    try:
        return SemanticCatalog(
            data["release"], data["source_graph_sha256"],
            data["historical_token_count"],
            tuple(SemanticToken(**item) for item in data["tokens"]),
            tuple(SemanticLesson(**item) for item in data["lessons"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TypedError(CatalogErrorCode.INVALID_RELEASE.value) from exc


class Catalog:
    """Read-only binding of upstream/canonical-assigned ID to typed operator."""

    def __init__(self, definitions: tuple[Operation, ...]):
        ids = [item.token_index for item in definitions]
        symbols = [item.symbol for item in definitions]
        if len(set(ids)) != len(ids) or len(set(symbols)) != len(symbols):
            raise TypedError("COMPOSITION_DUPLICATE_CATALOG_BINDING")
        self._by_id = {item.token_index: item for item in definitions}
        self._by_symbol = {item.symbol: item.token_index for item in definitions}

    def get(self, original_token_id: int) -> Operation:
        if type(original_token_id) is not int:
            raise TypedError("COMPOSITION_INVALID_CATALOG_ID")
        try:
            return self._by_id[original_token_id]
        except KeyError as exc:
            raise TypedError("COMPOSITION_UNKNOWN_CATALOG_ID") from exc

    def resolve_external_name(self, original_symbol: str) -> Operation:
        """For ingress only. Internals use original catalog-assigned token ID."""
        try:
            return self.get(self._by_symbol[original_symbol])
        except KeyError as exc:
            raise TypedError("COMPOSITION_UNKNOWN_EXTERNAL_ALIAS") from exc
