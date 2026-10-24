"""Stable source-key identity; see lib/ithkuil/SKOS_PROFILE.md, section 1."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import unicodedata
from urllib.parse import quote

from .errors import ProfileError


BASE = "https://github.com/Entif-AI/Bilqis-MLX/"
KEY_FIELDS = {
    "scheme": ("scheme_id",),
    "grammar": ("category_code", "value_code"),
    "collection": ("family_id",),
    "ordered_collection": ("collection_id",),
    "root": ("source_id", "root_id"),
    "sense": ("source_id", "root_id", "stem", "specification"),
    "datatype": ("notation_system",),
    "term": ("term",),
}


def _component(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProfileError("MISSING_OR_INVALID_IDENTITY_KEY", repr(value))
    if value in {".", ".."} or any(unicodedata.category(c).startswith("C") for c in value):
        raise ProfileError("INVALID_IDENTITY_KEY", repr(value))
    if unicodedata.normalize("NFC", value) != value:
        raise ProfileError("IDENTITY_KEY_NOT_NFC", repr(value))
    return quote(value, safe="-._~", encoding="utf-8", errors="strict")


@dataclass(frozen=True, order=True)
class Identity:
    kind: str
    keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in KEY_FIELDS:
            raise ProfileError("UNKNOWN_IDENTITY_KIND", str(self.kind))
        if not isinstance(self.keys, tuple) or len(self.keys) != len(KEY_FIELDS[self.kind]):
            raise ProfileError("IDENTITY_KEY_ARITY", self.kind)
        for key in self.keys:
            _component(key)

    @property
    def iri(self) -> str:
        prefix = "vocab/" if self.kind == "term" else f"id/{self.kind}/"
        return BASE + prefix + "/".join(_component(key) for key in self.keys)


def from_record(kind: str, record: Mapping[str, str]) -> Identity:
    """Select declared source keys only; labels and row/store coordinates are ignored."""
    if kind not in KEY_FIELDS:
        raise ProfileError("UNKNOWN_IDENTITY_KIND", kind)
    missing = [field for field in KEY_FIELDS[kind] if not record.get(field)]
    if missing:
        raise ProfileError("MISSING_IDENTITY_KEY", kind, *missing)
    keys = tuple(record[field] for field in KEY_FIELDS[kind])
    if kind == "sense":
        # These are source structural codes, not lexical labels. Both source
        # extractors use case variants of STEM; they denote the same coordinate.
        for key in keys:
            _component(key)
        if not all(key.isascii() for key in keys[2:]):
            raise ProfileError("INVALID_SENSE_COORDINATE", *keys[2:])
        keys = (*keys[:2], keys[2].upper(), keys[3].upper())
    return Identity(kind, keys)


def sense_from_source(table: str, record: Mapping[str, str]) -> Identity:
    """Map explicit extractor coordinates, including their declared blank scopes."""
    root_fields = {"lexicon_root_senses": "lexicon_root_id", "root_senses": "atomic_id"}
    if table not in root_fields:
        raise ProfileError("UNKNOWN_SENSE_SOURCE_SHAPE", table)
    for field in ("stem", "specification"):
        if field not in record or not isinstance(record[field], str):
            raise ProfileError("MISSING_SENSE_COORDINATE", table, field)
    stem, specification = record["stem"].upper(), record["specification"].upper()
    if stem not in {"", "STEM 1", "STEM 2", "STEM 3", "STEMS 1-3"}:
        raise ProfileError("INVALID_SENSE_COORDINATE", table, stem)
    allowed_specs = {"BSC", "CTE", "CSV", "OBJ"}
    if table == "root_senses":
        allowed_specs.add("")
    if specification not in allowed_specs:
        raise ProfileError("INVALID_SENSE_COORDINATE", table, specification)
    return from_record("sense", {
        "source_id": record.get("source_id", ""),
        "root_id": record.get(root_fields[table], ""),
        "stem": stem or "ROOT-WIDE",
        "specification": specification or "UNSPECIFIED",
    })


def validate_assignments(assignments: Iterable[tuple[Identity, str]]) -> dict[Identity, str]:
    """Validate persisted/imported assignments before they can become identity truth."""
    by_identity: dict[Identity, set[str]] = defaultdict(set)
    by_iri: dict[str, set[Identity]] = defaultdict(set)
    for identity, iri in assignments:
        by_identity[identity].add(iri)
        by_iri[iri].add(identity)
    for iri, identities in sorted(by_iri.items()):
        if len(identities) > 1:
            raise ProfileError("IRI_COLLISION", iri, *(repr(i) for i in sorted(identities)))
    for identity, iris in sorted(by_identity.items()):
        if len(iris) > 1:
            raise ProfileError("IDENTITY_DRIFT", repr(identity), *sorted(iris))
        if iris != {identity.iri}:
            raise ProfileError("NONCANONICAL_IRI", repr(identity), *sorted(iris))
    return {identity: identity.iri for identity in sorted(by_identity)}


def identity_map(identities: Iterable[Identity]) -> dict[Identity, str]:
    return validate_assignments((identity, identity.iri) for identity in identities)


def check_successor(
    old: Identity, new: Identity, *, meaning_changed: bool, successor_recorded: bool = False
) -> None:
    """Enforce a declared semantic-change decision, without trying to infer meaning."""
    if meaning_changed and old == new:
        raise ProfileError("MEANING_CHANGE_REUSES_IRI", old.iri)
    if meaning_changed and not successor_recorded:
        raise ProfileError("SUCCESSOR_RECORD_REQUIRED", old.iri, new.iri)
