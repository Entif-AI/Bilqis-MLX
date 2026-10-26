"""Versioned canonical RDF graph bytes and full-content SHA-256 (#41)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

import rdflib
from rdflib import BNode, ConjunctiveGraph, Dataset, Graph, Literal, URIRef
from rdflib.compare import to_canonical_graph

from .errors import ProfileError


ALGORITHM = "bilqis-rdflib-canonical-ntriples/v1"
RDFLIB_VERSION = "7.6.0"
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
FORBIDDEN_IRI = frozenset('<>"{}|^`\\')


@dataclass(frozen=True)
class CanonicalRdf:
    payload: bytes
    sha256: str
    triple_count: int

    def metadata(self) -> dict:
        return {
            "schema": "bilqis.skos.canonical-rdf/v1",
            "algorithm": ALGORITHM,
            "rdflib_version": RDFLIB_VERSION,
            "serialization": "application/n-triples",
            "encoding": "utf-8",
            "digest_algorithm": "sha256",
            "sha256": self.sha256,
            "triple_count": self.triple_count,
            "byte_count": len(self.payload),
            "scope": "complete-default-rdf-graph",
        }


def _valid_unicode(value: str) -> bool:
    return not any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _iri(value: URIRef) -> None:
    text = str(value)
    if (not SCHEME.match(text) or not _valid_unicode(text)
            or INVALID_PERCENT_ESCAPE.search(text)
            or any(ord(character) <= 0x20 or 0x7F <= ord(character) <= 0x9F
                   or character in FORBIDDEN_IRI for character in text)):
        raise ProfileError("NON_ABSOLUTE_OR_INVALID_RDF_IRI", repr(text))


def _validate_graph(graph: Graph) -> None:
    if not isinstance(graph, Graph) or isinstance(graph, (Dataset, ConjunctiveGraph)):
        raise ProfileError("CANONICALIZATION_REQUIRES_SINGLE_GRAPH")
    errors = []
    for subject, predicate, obj in graph:
        try:
            if not isinstance(subject, (URIRef, BNode)) or not isinstance(predicate, URIRef):
                raise ProfileError("INVALID_RDF_TRIPLE_POSITION", repr(subject), repr(predicate))
            if not isinstance(obj, (URIRef, BNode, Literal)):
                raise ProfileError("UNSUPPORTED_RDF_TERM", repr(obj))
            for term in (subject, predicate, obj):
                if isinstance(term, URIRef):
                    _iri(term)
                elif isinstance(term, Literal):
                    if not _valid_unicode(str(term)):
                        raise ProfileError("INVALID_RDF_LITERAL_UNICODE")
                    if term.datatype is not None:
                        _iri(term.datatype)
        except ProfileError as error:
            errors.append(error)
    if errors:
        raise min(errors, key=lambda error: (error.code, error.details))


def canonicalize(graph: Graph) -> CanonicalRdf:
    """Canonicalize all asserted triples; never entail, normalize text or select a subset."""
    if rdflib.__version__ != RDFLIB_VERSION:
        raise ProfileError("CANONICALIZER_VERSION_MISMATCH", rdflib.__version__, RDFLIB_VERSION)
    _validate_graph(graph)
    canonical = to_canonical_graph(graph)
    serialized = canonical.serialize(format="nt", encoding="utf-8")
    # Split ASCII LF bytes only: Unicode U+0085/U+2028 inside literal text are
    # source characters, not serialized triple separators.
    lines = [line for line in serialized.split(b"\n") if line]
    if len(lines) != len(graph):
        raise ProfileError("CANONICAL_TRIPLE_ACCOUNTING_MISMATCH")
    payload = b"" if not lines else b"\n".join(sorted(lines)) + b"\n"
    return CanonicalRdf(payload, hashlib.sha256(payload).hexdigest(), len(graph))


def canonical_diff(left: Graph, right: Graph, *, limit: int = 20) -> dict:
    """Bounded deterministic byte-level difference after the same canonicalization."""
    if not isinstance(limit, int) or limit < 0:
        raise ProfileError("INVALID_CANONICAL_DIFF_LIMIT", repr(limit))
    before, after = canonicalize(left), canonicalize(right)
    old_lines, new_lines = set(before.payload.split(b"\n")), set(after.payload.split(b"\n"))
    removed = sorted(old_lines - new_lines)
    added = sorted(new_lines - old_lines)
    return {
        "equal": before.payload == after.payload,
        "before_sha256": before.sha256,
        "after_sha256": after.sha256,
        "removed_count": len(removed),
        "added_count": len(added),
        "removed": [line.decode("utf-8") for line in removed[:limit]],
        "added": [line.decode("utf-8") for line in added[:limit]],
        "truncated": len(removed) > limit or len(added) > limit,
    }
