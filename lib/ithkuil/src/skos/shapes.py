"""Immutable SKOS resource-shape contract; see SKOS_PROFILE.md section 2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Iterable, Union

from rdflib import BNode, Graph, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from .errors import ProfileError
from .identity import Identity


CONCEPT_KINDS = frozenset({"grammar", "sense"})


class OrderBasis(str, Enum):
    """Why a collection is ordered; only source semantics may enter RDF order."""

    SOURCE_SEMANTIC = "source_semantic"
    CSV_ROW = "csv_row"
    SOURCE_TABLE = "source_table"
    SOURCE_CHAPTER = "source_chapter"
    CURRICULUM = "curriculum"


def _require_kind(identity: Identity, allowed: frozenset[str], code: str) -> None:
    if not isinstance(identity, Identity):
        raise ProfileError(code, repr(identity))
    if identity.kind not in allowed:
        raise ProfileError(code, identity.kind, identity.iri)


def _require_unique(values: tuple[Identity, ...], code: str) -> None:
    if not isinstance(values, tuple):
        raise ProfileError("SHAPE_MEMBERS_MUST_BE_IMMUTABLE", code)
    if len(values) != len(set(values)):
        raise ProfileError(code, *(value.iri for value in values))


@dataclass(frozen=True)
class SchemeShape:
    """One independently governed semantic inventory."""

    identity: Identity

    def __post_init__(self) -> None:
        _require_kind(self.identity, frozenset({"scheme"}), "INVALID_SCHEME_IDENTITY")


@dataclass(frozen=True)
class ConceptShape:
    """One semantic concept and every scheme sharing that same identity."""

    identity: Identity
    schemes: tuple[Identity, ...]

    def __post_init__(self) -> None:
        _require_kind(self.identity, CONCEPT_KINDS, "INVALID_CONCEPT_IDENTITY")
        if not self.schemes:
            raise ProfileError("CONCEPT_REQUIRES_SCHEME", self.identity.iri)
        for scheme in self.schemes:
            _require_kind(scheme, frozenset({"scheme"}), "INVALID_SCHEME_IDENTITY")
        _require_unique(self.schemes, "DUPLICATE_SCHEME_MEMBERSHIP")


@dataclass(frozen=True)
class CollectionShape:
    """Unordered grouping whose membership does not assert semantic hierarchy."""

    identity: Identity
    members: tuple[Identity, ...]

    def __post_init__(self) -> None:
        _require_kind(self.identity, frozenset({"collection"}), "INVALID_COLLECTION_IDENTITY")
        for member in self.members:
            _require_kind(member, CONCEPT_KINDS, "INVALID_COLLECTION_MEMBER")
        _require_unique(self.members, "DUPLICATE_COLLECTION_MEMBER")


@dataclass(frozen=True)
class OrderedCollectionShape:
    """A source-semantic ordered paradigm represented with skos:memberList."""

    identity: Identity
    members: tuple[Identity, ...]
    order_basis: OrderBasis

    def __post_init__(self) -> None:
        _require_kind(
            self.identity,
            frozenset({"ordered_collection"}),
            "INVALID_ORDERED_COLLECTION_IDENTITY",
        )
        if self.order_basis is not OrderBasis.SOURCE_SEMANTIC:
            basis = self.order_basis.value if isinstance(self.order_basis, OrderBasis) else str(self.order_basis)
            raise ProfileError("ORDER_BASIS_NOT_SOURCE_SEMANTIC", basis, self.identity.iri)
        if not self.members:
            raise ProfileError("ORDERED_COLLECTION_REQUIRES_MEMBERS", self.identity.iri)
        for member in self.members:
            _require_kind(member, CONCEPT_KINDS, "INVALID_COLLECTION_MEMBER")
        _require_unique(self.members, "DUPLICATE_COLLECTION_MEMBER")


@dataclass(frozen=True)
class RootResourceShape:
    """Addressable notation-bearing root resource that is not coerced into a Concept."""

    identity: Identity

    def __post_init__(self) -> None:
        _require_kind(self.identity, frozenset({"root"}), "INVALID_ROOT_IDENTITY")


Shape = Union[SchemeShape, ConceptShape, CollectionShape, OrderedCollectionShape, RootResourceShape]


def _list_node(identity: Identity, index: int) -> BNode:
    digest = hashlib.sha256(identity.iri.encode("utf-8")).hexdigest()
    return BNode(f"member-list-{digest}-{index}")


def _emit_member_list(graph: Graph, shape: OrderedCollectionShape) -> None:
    head = _list_node(shape.identity, 0)
    graph.add((URIRef(shape.identity.iri), SKOS.memberList, head))
    for index, member in enumerate(shape.members):
        node = _list_node(shape.identity, index)
        graph.add((node, RDF.first, URIRef(member.iri)))
        graph.add((
            node,
            RDF.rest,
            RDF.nil if index + 1 == len(shape.members) else _list_node(shape.identity, index + 1),
        ))


def build_shape_graph(resources: Iterable[Shape]) -> Graph:
    """Emit only the RDF/SKOS class, scheme, membership, and source-order shape layer."""

    by_iri: dict[str, Shape] = {}
    for resource in resources:
        if not isinstance(resource, (SchemeShape, ConceptShape, CollectionShape,
                                     OrderedCollectionShape, RootResourceShape)):
            raise ProfileError("UNKNOWN_RESOURCE_SHAPE", type(resource).__name__)
        prior = by_iri.get(resource.identity.iri)
        if prior is not None and prior != resource:
            raise ProfileError("RESOURCE_IDENTITY_REDEFINED", resource.identity.iri)
        by_iri[resource.identity.iri] = resource

    schemes = {
        resource.identity.iri
        for resource in by_iri.values()
        if isinstance(resource, SchemeShape)
    }
    concepts = {
        resource.identity.iri
        for resource in by_iri.values()
        if isinstance(resource, ConceptShape)
    }
    for resource in by_iri.values():
        if isinstance(resource, ConceptShape):
            for scheme in resource.schemes:
                if scheme.iri not in schemes:
                    raise ProfileError("UNDECLARED_CONCEPT_SCHEME", resource.identity.iri, scheme.iri)
        if isinstance(resource, (CollectionShape, OrderedCollectionShape)):
            for member in resource.members:
                if member.iri not in concepts:
                    raise ProfileError("UNDECLARED_COLLECTION_MEMBER", resource.identity.iri, member.iri)

    graph = Graph()
    for resource in sorted(by_iri.values(), key=lambda item: item.identity.iri):
        subject = URIRef(resource.identity.iri)
        if isinstance(resource, SchemeShape):
            graph.add((subject, RDF.type, SKOS.ConceptScheme))
        elif isinstance(resource, ConceptShape):
            graph.add((subject, RDF.type, SKOS.Concept))
            for scheme in sorted(resource.schemes, key=lambda item: item.iri):
                graph.add((subject, SKOS.inScheme, URIRef(scheme.iri)))
        elif isinstance(resource, CollectionShape):
            graph.add((subject, RDF.type, SKOS.Collection))
            for member in resource.members:
                graph.add((subject, SKOS.member, URIRef(member.iri)))
        elif isinstance(resource, OrderedCollectionShape):
            graph.add((subject, RDF.type, SKOS.OrderedCollection))
            _emit_member_list(graph, resource)
        elif isinstance(resource, RootResourceShape):
            graph.add((subject, RDF.type, RDFS.Resource))
    return graph
