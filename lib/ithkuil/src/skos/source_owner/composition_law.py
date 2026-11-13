"""Canonical source-owner witness for emitted composition laws."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from pathlib import Path

from rdflib import URIRef
from rdflib.namespace import DCTERMS

from ..build import LIB_ROOT
from ..canonical import canonicalize
from ..composition import (
    composition_iri, load_composition_profile, project_compositions,
)
from ..composition_components import (
    ordered_components, project_composition_components,
)
from ..errors import ProfileError
from ..preflight import CompilerClosure
from ..preflight import preflight
from ..publication import json_bytes
@dataclass(frozen=True)
class CompositionLawWitness:
    """Source-owner proof for one unconditional emitted composition law."""

    composition_id: str
    component_ids: tuple[str, ...]
    component_forms: tuple[str, ...]
    surface_form: str
    source_id: str
    source_table_id: str
    source_line: str
    source_loci: tuple[str, ...]
    composition_row_sha256: str
    component_rows_sha256: str
    atomic_rows_sha256: str
    projection_sha256: str
    owner: str = "#61"


def _row_dict(row) -> dict[str, str]:
    return dict(row.values)


def _tracked_rows(root: str | Path, name: str) -> tuple[dict[str, str], ...]:
    with (Path(root) / (name + ".csv")).open(
            encoding="utf-8", newline="") as handle:
        return tuple(csv.DictReader(handle))


def _composition_projections(root, closure, composition_id):
    fixtures = LIB_ROOT / "tests/fixtures"
    profile = load_composition_profile(
        LIB_ROOT / "src/skos/composition_profile.json",
        closure,
        fixtures / "skos_composition_negative.ttl",
    )
    parents = project_compositions(closure, profile)
    if composition_id not in parents.emitted_ids:
        raise ProfileError("COMPOSITION_LAW_PARENT_HELD", composition_id)
    component_rows = _tracked_rows(root, "composition_components")
    components = project_composition_components(
        closure, component_rows, parents)
    records = ordered_components(components.records, composition_id)
    if not records or any(
            record.component_id not in components.emitted_ids
            or not record.atomic_id or record.atomic_identity is None
            or record.condition for record in records):
        raise ProfileError("COMPOSITION_LAW_COMPONENT_HELD", composition_id)
    return parents, components, component_rows, records


def _composition_parent(closure, composition_id):
    rows = tuple(
        row for row in closure.table("morpheme_compositions").rows
        if row["composition_id"] == composition_id)
    if len(rows) != 1:
        raise ProfileError("COMPOSITION_LAW_PARENT_INVALID", composition_id)
    parent = rows[0]
    if (parent["derivation"] != "source_join"
            or parent["evidence_status"] != "official_source_join"
            or parent["condition"]
            or parent["surface_form_raw"] != parent["surface_form_normalized"]):
        raise ProfileError("COMPOSITION_LAW_SOURCE_HELD", composition_id)
    return parent


def _composition_atoms(closure, records, parent, composition_id):
    atom_map = {
        row["atomic_id"]: row for row in closure.table("morphemes_atomic").rows
    }
    try:
        atoms = tuple(atom_map[record.atomic_id] for record in records)
    except KeyError as error:
        raise ProfileError(
            "COMPOSITION_LAW_ATOM_UNAVAILABLE", composition_id,
            str(error)) from error
    forms = tuple(row["surface_form_normalized"] for row in atoms)
    if (not all(forms)
            or "".join(forms) != parent["surface_form_normalized"]
            or any(row["evidence_status"] != "official_source_observed"
                   or row["allomorph_condition"] for row in atoms)):
        raise ProfileError("COMPOSITION_LAW_ATOM_HELD", composition_id)
    return atoms, forms


def _composition_loci(parents, composition_id):
    resource = URIRef(composition_iri(composition_id))
    nodes = tuple(sorted(
        parents.graph.objects(resource, DCTERMS.source), key=str))
    loci = tuple(sorted(
        str(identifier)
        for node in nodes
        for identifier in parents.graph.objects(node, DCTERMS.identifier)))
    if not loci:
        raise ProfileError("COMPOSITION_LAW_SOURCE_LOCUS_MISSING", composition_id)
    return loci


def _witness_digests(
    composition_id, parent, component_rows, atoms, loci, parents, components,
):
    parent_dict = _row_dict(parent)
    component_dicts = tuple(
        dict(row) for row in component_rows
        if row["composition_id"] == composition_id)
    atom_dicts = tuple(_row_dict(row) for row in atoms)
    body = {
        "composition_id": composition_id,
        "parent": parent_dict,
        "components": component_dicts,
        "atoms": atom_dicts,
        "source_loci": loci,
        "parent_graph_sha256": canonicalize(parents.graph).sha256,
        "component_graph_sha256": canonicalize(components.graph).sha256,
        "owner": "#61",
    }

    def digest(value):
        return hashlib.sha256(json_bytes(value)).hexdigest()

    return (
        digest(parent_dict), digest(component_dicts), digest(atom_dicts),
        digest(body))


def composition_law_witness(
    root: str | Path, composition_id: str,
) -> CompositionLawWitness:
    """Resolve a composition only through the canonical #57/#58 source owners."""
    if not isinstance(composition_id, str) or not composition_id:
        raise ProfileError("COMPOSITION_LAW_ID_REQUIRED")
    closure = preflight(root).require_valid()
    parents, components, component_rows, records = _composition_projections(
        root, closure, composition_id)
    parent = _composition_parent(closure, composition_id)
    atoms, forms = _composition_atoms(
        closure, records, parent, composition_id)
    loci = _composition_loci(parents, composition_id)
    digests = _witness_digests(
        composition_id, parent, component_rows, atoms, loci,
        parents, components)
    return CompositionLawWitness(
        composition_id,
        tuple(record.atomic_id for record in records),
        forms,
        parent["surface_form_normalized"],
        parent["primary_source_id"],
        parent["primary_table_id"],
        parent["primary_source_line"],
        loci,
        *digests,
    )
