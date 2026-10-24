"""Standards-first relation classification and extension qualification."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.exceptions import ParserError
from rdflib.namespace import DCTERMS, RDFS, SKOS

from .errors import ProfileError
from .identity import Identity


class RelationDisposition(str, Enum):
    SKOS_SEMANTIC_RELATION = "SKOS_SEMANTIC_RELATION"
    SKOS_MEMBERSHIP = "SKOS_MEMBERSHIP"
    BILQIS_EXTENSION = "BILQIS_EXTENSION"
    RELATIONAL_IR_ONLY = "RELATIONAL_IR_ONLY"
    HELD = "HELD"


SEMANTIC_PREDICATES = {
    "subsumption": str(SKOS.broader),
    "inverse_subsumption": str(SKOS.narrower),
    "association": str(SKOS.related),
    "contrast": str(SKOS.related),
}
STRUCTURAL_KINDS = frozenset({"root_sense", "composition_membership", "ordered_component", "allomorph"})
SOURCE_BINDINGS = {
    "allomorph": ("allomorph_rules.csv", "allomorph_rule_id", ("input_pattern", "output_pattern", "condition_summary")),
}
NEGATIVE_SKOS_SUBSTITUTES = {
    "root_sense": str(SKOS.broader),
    "composition_membership": str(SKOS.broader),
    "ordered_component": str(SKOS.broader),
    "allomorph": str(SKOS.related),
}


@dataclass(frozen=True)
class ExtensionTerm:
    key: str
    relation_kind: str
    definition: str
    domain: str
    range: str
    source_fixture: str
    source_justification: str
    skos_gap: str
    rdf_gap: str
    negative_fixture: str
    recurring: bool
    machine_required: bool
    subproperty_of: str | None = None
    specialization_proof: str | None = None

    @property
    def iri(self) -> str:
        return Identity("term", (self.key,)).iri


@dataclass(frozen=True)
class RelationDecision:
    disposition: RelationDisposition
    predicate: str | None
    reason: str


def admit_extension(
    term: ExtensionTerm, *, source_csv_root: str | Path, negative_fixture_path: str | Path,
    specialization_fixture_path: str | Path | None = None,
) -> ExtensionTerm:
    """Check a raw extension term against concrete source and RDF fixture evidence.

    This is the #35 checklist gate for fixture/profile qualification. It does not
    install a production vocabulary; #57-#60 own production term choices.
    """
    if not isinstance(term, ExtensionTerm):
        raise ProfileError("EXTENSION_TERM_REQUIRED", type(term).__name__)
    required_text = (term.key, term.relation_kind, term.definition, term.domain, term.range,
                     term.source_fixture, term.source_justification, term.skos_gap,
                     term.rdf_gap, term.negative_fixture)
    if any(not isinstance(value, str) or not value.strip() for value in required_text):
        raise ProfileError("EXTENSION_CONTRACT_INCOMPLETE", repr(term.key))
    if term.recurring is not True or term.machine_required is not True:
        raise ProfileError("EXTENSION_NOT_NECESSARY", term.key)
    if term.relation_kind == "family_membership":
        raise ProfileError("EXISTING_SKOS_PRIMITIVE_SUFFICES", term.key, str(SKOS.member))
    if term.relation_kind not in STRUCTURAL_KINDS | SEMANTIC_PREDICATES.keys():
        raise ProfileError("UNKNOWN_EXTENSION_RELATION_KIND", term.key, term.relation_kind)
    if term.relation_kind in SEMANTIC_PREDICATES and not term.subproperty_of:
        raise ProfileError("EXISTING_SKOS_PRIMITIVE_SUFFICES", term.key, SEMANTIC_PREDICATES[term.relation_kind])
    for role, iri in (("domain", term.domain), ("range", term.range)):
        if not iri.startswith(("http://", "https://", "urn:")) or any(c.isspace() for c in iri):
            raise ProfileError("INVALID_EXTENSION_TYPE_IRI", term.key, role)
    if term.subproperty_of:
        expected = SEMANTIC_PREDICATES.get(term.relation_kind)
        if (term.subproperty_of != expected or term.domain != str(SKOS.Concept)
                or term.range != str(SKOS.Concept) or not term.specialization_proof
                or specialization_fixture_path is None):
            raise ProfileError("UNPROVEN_SKOS_SPECIALIZATION", term.key, term.subproperty_of)
        try:
            proof_graph = Graph().parse(Path(specialization_fixture_path), format="turtle")
        except (OSError, ValueError, SyntaxError, ParserError) as exc:
            raise ProfileError("UNPROVEN_SKOS_SPECIALIZATION", term.key, term.subproperty_of) from exc
        term_iri = URIRef(term.iri)
        source_iri = URIRef(f"urn:source:{term.source_fixture}")
        if ((term_iri, RDFS.subPropertyOf, URIRef(expected)) not in proof_graph
                or (term_iri, DCTERMS.source, source_iri) not in proof_graph
                or (term_iri, DCTERMS.identifier, Literal(term.specialization_proof)) not in proof_graph):
            raise ProfileError("UNPROVEN_SKOS_SPECIALIZATION", term.key, term.subproperty_of)

    binding = SOURCE_BINDINGS.get(term.relation_kind)
    if binding is None:
        raise ProfileError("EXTENSION_SOURCE_BINDING_UNSUPPORTED", term.key, term.relation_kind)
    csv_name, primary_key, required_columns = binding
    source_path = Path(source_csv_root) / csv_name
    try:
        with source_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, strict=True)
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)) or not {primary_key, *required_columns} <= set(fields):
                raise ProfileError("EXTENSION_SOURCE_PROOF_MALFORMED", term.key, csv_name)
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ProfileError("EXTENSION_SOURCE_PROOF_MISSING", term.key, term.source_fixture) from exc
    source_rows = [row for row in rows if row.get(primary_key) == term.source_fixture]
    if len(source_rows) > 1:
        raise ProfileError("EXTENSION_SOURCE_PROOF_AMBIGUOUS", term.key, term.source_fixture)
    source_row = source_rows[0] if source_rows else None
    if source_row is None or any(not source_row.get(column, "").strip() for column in required_columns):
        raise ProfileError("EXTENSION_SOURCE_PROOF_MISSING", term.key, term.source_fixture)
    if len({row.get(primary_key) for row in rows if row.get(primary_key)}) < 2:
        raise ProfileError("EXTENSION_RECURRENCE_NOT_PROVEN", term.key, term.source_fixture)

    tempting_predicate = NEGATIVE_SKOS_SUBSTITUTES.get(term.relation_kind)
    if tempting_predicate is None:
        raise ProfileError("EXTENSION_NEGATIVE_PROOF_UNSUPPORTED", term.key, term.relation_kind)
    try:
        negative_graph = Graph().parse(Path(negative_fixture_path), format="turtle")
    except (OSError, ValueError, SyntaxError, ParserError) as exc:
        raise ProfileError("EXTENSION_NEGATIVE_PROOF_MISSING", term.key, term.negative_fixture) from exc
    negative_triple = (
        URIRef(f"urn:source:{term.source_fixture}"),
        URIRef(tempting_predicate),
        URIRef(f"urn:negative:{term.negative_fixture}"),
    )
    if negative_triple not in negative_graph:
        raise ProfileError("EXTENSION_NEGATIVE_PROOF_MISSING", term.key, term.negative_fixture)
    # Validate the canonical term component without admitting any graph assertion.
    term.iri
    return term


def qualify_extension(
    kind: str, term: ExtensionTerm, *, source_csv_root: str | Path,
    negative_fixture_path: str | Path, specialization_fixture_path: str | Path | None = None,
) -> RelationDecision:
    """Qualify one custom predicate by re-running the concrete #35 evidence gate."""
    if not isinstance(term, ExtensionTerm):
        raise ProfileError("EXTENSION_TERM_REQUIRED", type(term).__name__)
    if term.relation_kind != kind:
        return RelationDecision(RelationDisposition.HELD, None, "EXTENSION_RELATION_KIND_MISMATCH")
    try:
        admit_extension(
            term,
            source_csv_root=source_csv_root,
            negative_fixture_path=negative_fixture_path,
            specialization_fixture_path=specialization_fixture_path,
        )
    except ProfileError as exc:
        if exc.code == "UNPROVEN_SKOS_SPECIALIZATION":
            return RelationDecision(RelationDisposition.HELD, None, exc.code)
        raise
    return RelationDecision(RelationDisposition.BILQIS_EXTENSION, term.iri, "QUALIFIED_LINGUISTIC_RESIDUE")


def decide_relation(
    kind: str, *, source_attested: bool, semantic_proof: bool = False,
) -> RelationDecision:
    """Classify reviewed premises; this helper does not authorize or emit RDF."""
    if not isinstance(source_attested, bool) or not isinstance(semantic_proof, bool):
        raise ProfileError("INVALID_RELATION_REVIEW_PREMISE", kind)
    if not source_attested:
        return RelationDecision(RelationDisposition.HELD, None, "RELATION_SOURCE_NOT_ATTESTED")
    if kind == "family_membership":
        return RelationDecision(RelationDisposition.SKOS_MEMBERSHIP, str(SKOS.member), "SOURCE_FAMILY_MEMBERSHIP")
    if kind in SEMANTIC_PREDICATES:
        if semantic_proof:
            return RelationDecision(RelationDisposition.SKOS_SEMANTIC_RELATION,
                                    SEMANTIC_PREDICATES[kind], "SOURCE_SEMANTIC_RELATION")
        return RelationDecision(RelationDisposition.HELD, None, "SEMANTIC_RELATION_PROOF_MISSING")
    if kind in STRUCTURAL_KINDS:
        return RelationDecision(RelationDisposition.RELATIONAL_IR_ONLY, None, "LINGUISTIC_EXTENSION_NOT_ADMITTED")
    return RelationDecision(RelationDisposition.HELD, None, "UNKNOWN_RELATION_KIND")


def validate_predicate(kind: str, predicate: str, *, source_attested: bool,
                       semantic_proof: bool = False) -> None:
    """Check a declared SKOS predicate against reviewed premises; not an RDF emission gate."""
    decision = decide_relation(kind, source_attested=source_attested,
                               semantic_proof=semantic_proof)
    if decision.predicate != predicate:
        raise ProfileError("RELATION_PREDICATE_NOT_ADMITTED", kind, predicate, decision.reason)
