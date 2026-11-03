"""Canonical source-root and semantic frame fixtures."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasConcept, AtlasCounts, FrozenAtlasConcept, FrozenAtlasSnapshot,
    SourceRecordRef,
)
from bilqis_mlx.semantics.frame_schema import ConceptRef, FrameSchema, RoleSpec


RELEASE = "1" * 64



ROOT = Path(__file__).resolve().parents[4]



def _concept(name: str, index: int, type_name: str = "Entity") -> ConceptRef:
    return ConceptRef(
        semantic_id="formal:" + name,
        semantic_release=RELEASE,
        abi_index=index,
        type_ids=(type_name,),
        source_reference="fixture:" + name,
    )



def _transfer_schema() -> FrameSchema:
    return FrameSchema(
        schema_id="formal.frame.TRANSFER",
        revision=1,
        ast_construct="apply:formal.operator.TRANSFER",
        roles=(
            RoleSpec("agent", ("Entity",), 1, 1),
            RoleSpec("recipient", ("Entity",), 1, 1),
            RoleSpec("theme", ("Entity",), 1, 1),
        ),
        order_mode="ORDERED",
        scope="source-expression",
    )



def _snapshot(*concepts: ConceptRef) -> FrozenAtlasSnapshot:
    entries = tuple(AbiEntry(
        index=item.abi_index,
        bank=0,
        row=item.abi_index,
        semantic_id=item.semantic_id,
        symbol=None,
        source="FORMAL_DOMAIN",
        active=True,
        teaching_candidate=True,
        reason="fixture",
    ) for item in sorted(concepts, key=lambda item: item.abi_index))
    frozen_concepts = tuple(FrozenAtlasConcept(
        concept=AtlasConcept(
            semantic_id=item.semantic_id,
            kind="concept",
            types=item.type_ids,
            labels=(),
            realizations=(),
            source_loci=(),
            relations=(),
            source_rows=(SourceRecordRef("fixture", "fixture", item.semantic_id),),
        ),
        abi_index=item.abi_index,
        abi_bank=0,
        abi_row=item.abi_index,
        active=True,
        implementation_status="ADMITTED",
        teaching_candidate=True,
        teaching_reason="fixture",
    ) for item in concepts)
    return FrozenAtlasSnapshot(
        schema="bilqis.semantic-atlas-snapshot/v1",
        bundle_id="a" * 64,
        release_sha256=RELEASE,
        source_bundle_id="b" * 64,
        canonical_rdf_sha256="c" * 64,
        coverage_sha256="d" * 64,
        source_rows_sha256="e" * 64,
        conformance_sha256="f" * 64,
        prior_abi_sha256="0" * 64,
        shape_policy_sha256="1" * 64,
        active_set_sha256="2" * 64,
        counts=AtlasCounts(1, 1, 1, len(entries), 1, len(entries), 0, 0, 0, 0),
        formal_domain_bindings=(),
        abi_entries=entries,
        concepts=tuple(sorted(
            frozen_concepts, key=lambda item: item.concept.semantic_id)),
        relations=(),
        withheld_rows=(),
        semantic_lookup=tuple(sorted((entry.semantic_id, entry.index) for entry in entries)),
        concept_lookup=tuple(
            (item.concept.semantic_id, index)
            for index, item in enumerate(sorted(
                frozen_concepts, key=lambda item: item.concept.semantic_id))),
    )
