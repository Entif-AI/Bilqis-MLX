"""Source-preserving typed SKOS notation; see SKOS_PROFILE.md section 3."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
import re
import unicodedata

from rdflib import Literal, URIRef

from .errors import ProfileError
from .identity import Identity


NEW_ITHKUIL_DATATYPE_IRI = Identity("datatype", ("new-ithkuil",)).iri
GRAMMAR_CODE_DATATYPE_IRI = Identity("datatype", ("grammar-code",)).iri
CANONICAL_NOTATION_DATATYPE_IRIS = frozenset(
    {NEW_ITHKUIL_DATATYPE_IRI, GRAMMAR_CODE_DATATYPE_IRI}
)
ABSOLUTE_IRI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
IRI_FORBIDDEN = frozenset('<>"{}|\\^') | {chr(96)}


def _canonical_datatype_iri(datatype: str | URIRef) -> str:
    iri = str(datatype)
    if iri not in CANONICAL_NOTATION_DATATYPE_IRIS:
        raise ProfileError("UNKNOWN_NOTATION_DATATYPE", iri)
    return iri


def _validate_lexical(lexical: str) -> str:
    if not isinstance(lexical, str):
        raise ProfileError("INVALID_NOTATION_LEXICAL_TYPE", repr(lexical))
    if lexical == "":
        raise ProfileError("EMPTY_NOTATION")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in lexical):
        raise ProfileError("NOTATION_SURROGATE_FORBIDDEN", repr(lexical))
    if lexical != lexical.strip():
        raise ProfileError("NOTATION_SURROUNDING_WHITESPACE", repr(lexical))
    return lexical


def _validate_claim_iri(value: str, code: str) -> str:
    if not isinstance(value, str) or not value or not ABSOLUTE_IRI.match(value):
        raise ProfileError(code, repr(value))
    if any(
        char.isspace()
        or char in IRI_FORBIDDEN
        or 0xD800 <= ord(char) <= 0xDFFF
        or unicodedata.category(char) in {"Cc", "Cs"}
        for char in value
    ):
        raise ProfileError(code, repr(value))
    return value


def typed_notation(lexical: str, datatype: str | URIRef) -> Literal:
    """Build an exact-code-point typed notation literal."""
    lexical = _validate_lexical(lexical)
    datatype_iri = _canonical_datatype_iri(datatype)
    return Literal(lexical, datatype=URIRef(datatype_iri), normalize=False)


def validate_notation_literal(literal: Literal) -> Literal:
    """Validate an already parsed/constructed notation literal without rewriting it."""
    if not isinstance(literal, Literal):
        raise ProfileError("NOTATION_LITERAL_REQUIRED", repr(literal))
    if literal.language is not None:
        raise ProfileError("NOTATION_LANGUAGE_TAG_FORBIDDEN", literal.language)
    if literal.datatype is None:
        raise ProfileError("NOTATION_DATATYPE_REQUIRED", repr(str(literal)))
    _canonical_datatype_iri(literal.datatype)
    _validate_lexical(str(literal))
    return literal


@dataclass(frozen=True, order=True)
class NotationKey:
    """Exact collision key: governing scheme, datatype, and lexical code points."""

    scheme_iri: str
    datatype_iri: str
    lexical: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.scheme_iri, self.datatype_iri, self.lexical)


@dataclass(frozen=True)
class NotationClaim:
    """One semantic resource claiming one notation inside one governing scheme."""

    scheme_iri: str
    resource_iri: str
    literal: Literal
    expected_unique: bool = True

    def __post_init__(self) -> None:
        _validate_claim_iri(self.scheme_iri, "INVALID_NOTATION_SCHEME_IRI")
        _validate_claim_iri(self.resource_iri, "INVALID_NOTATION_RESOURCE_IRI")
        if not isinstance(self.expected_unique, bool):
            raise ProfileError(
                "NOTATION_UNIQUENESS_FLAG_INVALID", repr(self.expected_unique)
            )
        validate_notation_literal(self.literal)

    @property
    def key(self) -> NotationKey:
        return NotationKey(
            self.scheme_iri,
            str(self.literal.datatype),
            str(self.literal),
        )


@dataclass(frozen=True)
class NotationConflict:
    """Two or more distinct resources sharing one exact notation key."""

    key: NotationKey
    resource_iris: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "key_tuple": list(self.key.as_tuple()),
            "scheme_iri": self.key.scheme_iri,
            "datatype_iri": self.key.datatype_iri,
            "lexical": self.key.lexical,
            "resource_iris": list(self.resource_iris),
        }


@dataclass(frozen=True)
class NotationReport:
    collisions: tuple[NotationConflict, ...]
    allowed_homographs: tuple[NotationConflict, ...]

    def as_dict(self) -> dict:
        return {
            "collisions": [entry.as_dict() for entry in self.collisions],
            "allowed_homographs": [
                entry.as_dict() for entry in self.allowed_homographs
            ],
        }


def analyze_notation_claims(claims: Iterable[NotationClaim]) -> NotationReport:
    """Classify exact homographs deterministically without rewriting notation."""
    grouped: dict[NotationKey, list[NotationClaim]] = defaultdict(list)
    for claim in claims:
        if not isinstance(claim, NotationClaim):
            raise ProfileError("NOTATION_CLAIM_REQUIRED", repr(claim))
        grouped[claim.key].append(claim)

    collisions: list[NotationConflict] = []
    allowed_homographs: list[NotationConflict] = []
    for key in sorted(grouped):
        group = grouped[key]
        resource_iris = tuple(sorted({claim.resource_iri for claim in group}))
        if len(resource_iris) < 2:
            continue
        conflict = NotationConflict(key, resource_iris)
        if any(claim.expected_unique for claim in group):
            collisions.append(conflict)
        else:
            allowed_homographs.append(conflict)
    return NotationReport(tuple(collisions), tuple(allowed_homographs))


def validate_notation_collisions(
    claims: Iterable[NotationClaim],
) -> NotationReport:
    """Return the homograph report or fail on the first deterministic collision."""
    report = analyze_notation_claims(claims)
    if report.collisions:
        conflict = report.collisions[0]
        key = conflict.key
        raise ProfileError(
            "NOTATION_COLLISION",
            f"key={key.as_tuple()!r}",
            f"scheme={key.scheme_iri}",
            f"datatype={key.datatype_iri}",
            f"lexical={key.lexical!r}",
            *(f"resource={iri}" for iri in conflict.resource_iris),
        )
    return report
