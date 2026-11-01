"""Atlas feature prospective owner; source-only and neural-inert."""
from __future__ import annotations

from ..atlas_projection import FrozenAtlasSnapshot


from .common import _SHA, _ADMITTED_GRAPH_PREDICATES, _invalid, _utf8, _sorted_ids, _factor_overflow, _category_map
from .records import ProspectiveIdentityFeature, ProspectiveIdentityFeatureSet, AtlasFeatures
from .sources import _graph_vector, _senses_by_root

def _validate_prospective_binding(release, current, semantic_ids, expected_feature_digest):
    if (not isinstance(release, FrozenAtlasSnapshot)
            or not isinstance(current, AtlasFeatures)
            or not isinstance(semantic_ids, tuple) or not semantic_ids
            or len(set(semantic_ids)) != len(semantic_ids)
            or any(not isinstance(identifier, str) or not identifier
                   for identifier in semantic_ids)
            or not isinstance(expected_feature_digest, str)
            or not _SHA.fullmatch(expected_feature_digest)
            or current.digest != expected_feature_digest
            or current.semantic_release != release.release_sha256
            or current.atlas_bundle_id != release.bundle_id
            or current.source_bundle_id != release.source_bundle_id):
        _invalid("BAMF_FEATURE_PROSPECTIVE_BINDING_INVALID")


def _prospective_entries(release, semantic_ids):
    abi_by_id = {entry.semantic_id: entry for entry in release.abi_entries}
    if len(abi_by_id) != len(release.abi_entries):
        _invalid("BAMF_FEATURE_PROSPECTIVE_ABI_INVALID")
    entries = {}
    for semantic_id in semantic_ids:
        entry = abi_by_id.get(semantic_id)
        if entry is None:
            _invalid("BAMF_FEATURE_PROSPECTIVE_IDENTITY_UNKNOWN")
        if entry.active or entry.source not in {"CANONICAL_SKOS", "FORMAL_DOMAIN"}:
            _invalid("BAMF_FEATURE_PROSPECTIVE_IDENTITY_NOT_INACTIVE")
        entries[semantic_id] = entry

    return entries


def _prospective_source_rows(release, entries, included):
    frozen_concepts = {
        item.concept.semantic_id: item
        for item in release.concepts
        if item.concept.semantic_id in included
    }
    for semantic_id, entry in entries.items():
        source = frozen_concepts.get(semantic_id)
        if entry.source == "CANONICAL_SKOS" and (
                source is None or source.active
                or source.abi_index != entry.index
                or source.concept.semantic_id != semantic_id):
            _invalid("BAMF_FEATURE_PROSPECTIVE_SOURCE_INVALID")
        coverage = tuple(
            item for item in release.withheld_rows
            if item.semantic_id == semantic_id)
        if coverage and any(
                getattr(item, "source_disposition", None) != "SOURCE_ELIGIBLE"
                for item in coverage):
            _invalid("BAMF_FEATURE_PROSPECTIVE_SOURCE_HELD")

    return {
        semantic_id: item.concept
        for semantic_id, item in frozen_concepts.items()
    }

def plan_prospective_identity_features(
    release: FrozenAtlasSnapshot,
    current: AtlasFeatures,
    semantic_ids: tuple[str, ...],
    *,
    expected_feature_digest: str,
) -> ProspectiveIdentityFeatureSet:
    """Project inactive source-known identities without granting admission.

    This is the A06/A02 authority seam that precedes neural row initialization.
    It extends only the categorical feature map needed by the proposed identities,
    leaves the accepted manifest untouched, and never activates an ABI row.
    """
    _validate_prospective_binding(release, current, semantic_ids, expected_feature_digest)

    active = {
        entry.semantic_id: entry for entry in release.abi_entries if entry.active
    }
    current_ids = {item.semantic_id for item in current.concepts}
    if (current_ids != set(active)
            or _category_map((), current.type_map) != current.type_map):
        _invalid("BAMF_FEATURE_PROSPECTIVE_PREDECESSOR_INVALID")

    entries = _prospective_entries(release, semantic_ids)

    included = set(active) | set(semantic_ids)
    source_concepts = _prospective_source_rows(release, entries, included)
    types_by_id = {
        semantic_id: _sorted_ids(source_concepts[semantic_id].types)
        if semantic_id in source_concepts else ()
        for semantic_id in included
    }
    relations = tuple(sorted((
        (edge.source_semantic_id, edge.predicate, edge.target_semantic_id)
        for edge in release.relations
        if (edge.source_semantic_id in included
            and edge.target_semantic_id in included
            and edge.predicate in _ADMITTED_GRAPH_PREDICATES)
    ), key=lambda edge: tuple(_utf8(part) for part in edge)))
    senses_by_root = _senses_by_root(source_concepts, relations)

    type_map = _category_map(
        tuple(type_id for semantic_id in included
              for type_id in types_by_id[semantic_id]),
        current.type_map)
    type_rows = dict(type_map)
    unresolved = {
        item.semantic_id for item in release.withheld_rows
        if item.semantic_id is not None
        and item.source_disposition == "SOURCE_HELD"
    }
    planned = []
    for semantic_id, entry in sorted(entries.items(), key=lambda item: item[1].index):
        source = source_concepts.get(semantic_id)
        identifiers = types_by_id[semantic_id]
        rows = tuple(type_rows[identifier] for identifier in identifiers)
        overflow = tuple(
            _factor_overflow("type", identifier) if row == 0 else None
            for identifier, row in zip(identifiers, rows))
        planned.append(ProspectiveIdentityFeature(
            semantic_id=semantic_id,
            abi_index=entry.index,
            type_ids=identifiers,
            type_rows=rows,
            type_overflow=overflow,
            graph64=_graph_vector(
                semantic_id, identifiers,
                len(source.realizations) if source else 0,
                len(senses_by_root.get(semantic_id, ())),
                semantic_id in unresolved or source is None,
                relations, types_by_id),
            source_status=("SOURCE_ELIGIBLE_NOT_ADMITTED"
                           if source is not None else "FORMAL_ABI_NOT_ADMITTED"),
        ))
    return ProspectiveIdentityFeatureSet(
        semantic_release=release.release_sha256,
        atlas_bundle_id=release.bundle_id,
        source_bundle_id=release.source_bundle_id,
        predecessor_feature_digest=current.digest,
        type_map=type_map,
        identities=tuple(planned),
    )
