"""Minimal root-to-sense relation admitted through the #35 extension boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from rdflib import Graph, URIRef

from .errors import ProfileError
from .identity import Identity
from .lexicon_dimensions import LexiconDimensionProjection, project_lexicon_dimensions
from .lexicon_roots import LexiconRootProjection, project_lexicon_roots
from .lexicon_senses import LexiconSenseProjection, project_lexicon_senses
from .preflight import CompilerClosure
from .relations import ExtensionTerm, RelationDisposition, admit_extension, decide_relation, qualify_extension


PROFILE_VERSION = "bilqis-root-sense-relation/1"


@dataclass(frozen=True, order=True)
class RootSenseLinkIssue:
    code: str
    sense_iri: str
    source_sense_ids: tuple[str, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class RootSenseLinkProjection:
    graph: Graph
    predicate: str
    linked_sense_ids: tuple[str, ...]
    held_sense_ids: tuple[str, ...]
    issues: tuple[RootSenseLinkIssue, ...]


def load_root_sense_term(
    path: str | Path,
    *,
    source_csv_root: str | Path,
    negative_fixture_path: str | Path,
) -> ExtensionTerm:
    """Load and re-admit the one reviewed #53 extension term through #35."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ProfileError("ROOT_SENSE_RELATION_PROFILE_INVALID", type(error).__name__) from error
    if not isinstance(data, dict) or data.get("profile_version") != PROFILE_VERSION:
        raise ProfileError("ROOT_SENSE_RELATION_PROFILE_INVALID")
    raw = data.get("term")
    if not isinstance(raw, dict):
        raise ProfileError("ROOT_SENSE_RELATION_PROFILE_INVALID")
    try:
        term = ExtensionTerm(**raw)
    except (TypeError, ValueError) as error:
        raise ProfileError("ROOT_SENSE_RELATION_PROFILE_INVALID", type(error).__name__) from error

    baseline = decide_relation("root_sense", source_attested=True)
    if baseline.disposition is not RelationDisposition.RELATIONAL_IR_ONLY or baseline.predicate is not None:
        raise ProfileError("ROOT_SENSE_BASELINE_BOUNDARY_CHANGED")
    admitted = admit_extension(
        term,
        source_csv_root=source_csv_root,
        negative_fixture_path=negative_fixture_path,
    )
    qualified = qualify_extension(
        "root_sense",
        admitted,
        source_csv_root=source_csv_root,
        negative_fixture_path=negative_fixture_path,
    )
    if qualified.disposition is not RelationDisposition.BILQIS_EXTENSION or qualified.predicate != term.iri:
        raise ProfileError("ROOT_SENSE_RELATION_NOT_ADMITTED", term.key)
    return term


def project_root_sense_links(
    closure: CompilerClosure,
    term: ExtensionTerm,
    *,
    roots: LexiconRootProjection | None = None,
    senses: LexiconSenseProjection | None = None,
    dimensions: LexiconDimensionProjection | None = None,
) -> RootSenseLinkProjection:
    """Emit root→sense edges only when both endpoints and #52 dimensions are admitted."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    if not isinstance(term, ExtensionTerm) or term.relation_kind != "root_sense":
        raise ProfileError("ROOT_SENSE_EXTENSION_TERM_REQUIRED")
    if term.iri != Identity("term", ("hasSense",)).iri:
        raise ProfileError("ROOT_SENSE_PREDICATE_NOT_CANONICAL", term.iri)
    roots = roots or project_lexicon_roots(closure)
    senses = senses or project_lexicon_senses(closure)
    dimensions = dimensions or project_lexicon_dimensions(closure, senses)
    if not isinstance(roots, LexiconRootProjection):
        raise ProfileError("LEXICON_ROOT_PROJECTION_REQUIRED", type(roots).__name__)
    if not isinstance(senses, LexiconSenseProjection):
        raise ProfileError("LEXICON_SENSE_PROJECTION_REQUIRED", type(senses).__name__)
    if not isinstance(dimensions, LexiconDimensionProjection):
        raise ProfileError("LEXICON_DIMENSION_PROJECTION_REQUIRED", type(dimensions).__name__)

    root_iris = {record.identity.iri for record in roots.records}
    dimension_iris = {record.sense.iri for record in dimensions.records}
    graph = Graph()
    linked = set()
    held = set(senses.held_source_ids) | set(dimensions.held_source_ids)
    issues = []
    predicate = URIRef(term.iri)
    for record in senses.records:
        problems = []
        if record.parent_root.iri not in root_iris:
            problems.append(("ROOT_SENSE_PARENT_NOT_EMITTED", record.parent_root.iri))
        if record.identity.iri not in dimension_iris:
            problems.append(("ROOT_SENSE_DIMENSIONS_NOT_EMITTED", record.identity.iri))
        if problems:
            held.update(record.source_sense_ids)
            for problem in problems:
                issues.append(RootSenseLinkIssue(
                    problem[0], record.identity.iri, record.source_sense_ids, tuple(problem[1:])
                ))
            continue
        graph.add((URIRef(record.parent_root.iri), predicate, URIRef(record.identity.iri)))
        linked.update(record.source_sense_ids)
    return RootSenseLinkProjection(
        graph,
        term.iri,
        tuple(sorted(linked)),
        tuple(sorted(held)),
        tuple(sorted(set(issues))),
    )
