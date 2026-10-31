"""Atlas feature manifest owner; source-only and neural-inert."""
from __future__ import annotations

from ..atlas_projection import FrozenAtlasSnapshot


from .common import _SHA, _ADMITTED_GRAPH_PREDICATES, _invalid, _utf8, _sorted_ids, _category_map
from .records import FeatureSchema, ConceptFeature, AtlasFeatures
from .sources import _source_rule_categories, _graph_vector, _senses_by_root

def build_feature_manifest(
    release: FrozenAtlasSnapshot,
    feature_schema: FeatureSchema,
) -> AtlasFeatures:
    """Compile all admitted identities, preserving predecessor factor rows."""
    if (not isinstance(release, FrozenAtlasSnapshot)
            or not isinstance(feature_schema, FeatureSchema)
            or not _SHA.fullmatch(release.release_sha256)):
        _invalid("BAMF_FEATURE_RELEASE_INVALID")
    prior = feature_schema.predecessor
    if prior is not None and (
            prior.semantic_release == release.release_sha256
            or release.prior_abi_sha256 != prior.atlas_bundle_id):
        _invalid("BAMF_FEATURE_PREDECESSOR_LINEAGE_INVALID")
    if (_sorted_ids(feature_schema.role_ids)
            != _source_rule_categories(release, feature_schema.source_bindings)):
        _invalid("BAMF_FEATURE_SOURCE_ROLE_UNVERIFIED")
    active = {
        entry.semantic_id: entry for entry in release.abi_entries if entry.active
    }
    if len(active) != sum(entry.active for entry in release.abi_entries):
        _invalid("BAMF_FEATURE_DUPLICATE_ADMITTED_ID")
    source_concepts = {
        item.concept.semantic_id: item.concept for item in release.concepts
        if item.active and item.concept.semantic_id in active
    }
    types_by_id = {
        identifier: _sorted_ids(source_concepts[identifier].types)
        if identifier in source_concepts else ()
        for identifier in active
    }
    admitted_relations = tuple(sorted((
        (edge.source_semantic_id, edge.predicate, edge.target_semantic_id)
        for edge in release.relations
        if (edge.source_semantic_id in active
            and edge.target_semantic_id in active
            and edge.predicate in _ADMITTED_GRAPH_PREDICATES)
    ), key=lambda edge: tuple(_utf8(part) for part in edge)))
    senses_by_root = _senses_by_root(source_concepts, admitted_relations)
    type_map = _category_map(
        tuple(type_id for types in types_by_id.values() for type_id in types),
        prior.type_map if prior else None)
    role_map = _category_map(
        feature_schema.role_ids, prior.role_map if prior else None)
    schema_map = _category_map(
        feature_schema.schema_ids, prior.schema_map if prior else None)
    # A01 records implementation-uncovered, source-eligible rows in held.jsonl
    # too. Only a source-owned hold can represent unresolved source mapping;
    # missing downstream teaching machinery is not a graph feature.
    unresolved = {
        item.semantic_id for item in release.withheld_rows
        if item.semantic_id is not None
        and item.source_disposition == "SOURCE_HELD"
    }
    concept_rows = []
    for identifier in _sorted_ids(tuple(active)):
        source = source_concepts.get(identifier)
        forms = len(source.realizations) if source else 0
        senses = len(senses_by_root.get(identifier, ()))
        concept_rows.append(ConceptFeature(
            identifier, active[identifier].index, types_by_id[identifier],
            _graph_vector(
                identifier, types_by_id[identifier], forms, senses,
                identifier in unresolved or source is None,
                admitted_relations, types_by_id),
            "ADMITTED_SOURCE" if source else "ADMITTED_FORMAL_ABI_UNTYPED",
        ))
    held_reasons = tuple(sorted((
        (item.semantic_id or item.key, item.reason_code)
        for item in release.withheld_rows
    ), key=lambda item: (_utf8(item[0]), _utf8(item[1]))))
    return AtlasFeatures(
        release.release_sha256, release.bundle_id, release.source_bundle_id,
        prior.digest if prior else None,
        type_map, role_map, schema_map, tuple(concept_rows),
        held_reasons,
    )
