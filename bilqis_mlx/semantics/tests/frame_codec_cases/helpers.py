from __future__ import annotations

from dataclasses import replace
import hashlib
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import (
    ATOMIC_CODEC_ID,
    COMPACT_CODEC_ID,
    CODEC_VERSION,
    EXTENDED_CODEC_ID,
    FallbackReason,
    PackDisposition,
    PRESENCE_MASK,
    PRESENCE_SHIFT,
    SCHEMA_SHIFT,
    VERSION_SHIFT,
    CompactFrameBytes,
    SchemaTagMap,
    classify_frame,
    deserialize_u64,
    pack4,
    pack_frame,
    role_index,
    serialize_u64,
    unpack_frame,
    unpack4,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry,
    AtlasConcept,
    AtlasCounts,
    CorpusCoverageRow,
    FrozenAtlasConcept,
    FrozenAtlasSnapshot,
)
from bilqis_mlx.semantics.frame_schema import (
    AtomicFrame,
    BindingState,
    ChildFrameRef,
    ConceptRef,
    FrameSchema,
    RoleOccurrence,
    RoleSpec,
    SourceSpan,
    atomic_fallback,
    make_frame_instance,
)


RELEASE = "1" * 64


def _schema(name: str) -> FrameSchema:
    return FrameSchema(
        schema_id="frame:" + name,
        revision=1,
        ast_construct="source:" + name,
        roles=tuple(
            RoleSpec("slot" + str(index), ("Entity",), 1, 1)
            for index in range(4)
        ),
        order_mode="ORDERED",
        scope="fixture",
    )


def _concept(index: int, *, semantic_id: str | None = None) -> ConceptRef:
    return ConceptRef(
        semantic_id=semantic_id or "formal:entity." + str(index),
        semantic_release=RELEASE,
        abi_index=index,
        type_ids=("Entity",),
        source_reference="fixture:" + str(index),
    )


def _frame(
    schema: FrameSchema,
    concepts: tuple[ConceptRef, ...],
    *,
    source_instance_id: str = "frame-1",
) -> object:
    return make_frame_instance(
        schema,
        source_instance_id=source_instance_id,
        structural_path=(),
        source_span=SourceSpan(0, 8),
        parent_occurrence_id=None,
        bindings=tuple(
            RoleOccurrence(role.role_id, 0, concept=concept)
            for role, concept in zip(schema.roles, concepts)
        ),
        causal_prefix_end=8,
    )


def _snapshot(*, inactive: tuple[int, ...] = (), held_id: str | None = None):
    entries = tuple(AbiEntry(
        index=index,
        bank=0,
        row=index,
        semantic_id="formal:entity." + str(index),
        symbol="fixture.entity." + str(index),
        source="FORMAL_DOMAIN",
        active=index not in inactive,
        teaching_candidate=index not in inactive,
        reason=("PRIOR_ACCEPTED_ABI" if index not in inactive
                else "IMPLEMENTATION_UNCOVERED"),
    ) for index in range(5))
    withheld = ()
    if held_id is not None:
        withheld = (CorpusCoverageRow(
            domain="mapping",
            table="fixture",
            key="held",
            semantic_id=held_id,
            source_disposition="SOURCE_HELD",
            implementation_status="NOT_APPLICABLE",
            teaching_candidate=False,
            reason_code="MAPPING_REVIEW_PENDING",
            teaching_reason="MAPPING_REVIEW_PENDING",
            owner="fixture",
        ),)
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
        counts=AtlasCounts(
            source_rows=1,
            rdf_terms=1,
            semantic_concepts=0,
            abi_entries=len(entries),
            abi_banks=1,
            active_abi_indices=sum(entry.active for entry in entries),
            trainable_capabilities=0,
            source_held=len(withheld),
            source_ir_only=0,
            implementation_uncovered=len(inactive),
        ),
        formal_domain_bindings=(),
        abi_entries=entries,
        concepts=(),
        relations=(),
        withheld_rows=withheld,
        semantic_lookup=tuple(sorted(
            (entry.semantic_id, entry.index) for entry in entries)),
        concept_lookup=(),
    )


def _snapshot_with_concept_type(type_ids: tuple[str, ...]) -> FrozenAtlasSnapshot:
    snapshot = _snapshot()
    concept = AtlasConcept(
        semantic_id="formal:entity.0",
        kind="FORMAL",
        types=type_ids,
        labels=(),
        realizations=(),
        source_loci=(),
        relations=(),
        source_rows=(),
    )
    frozen = FrozenAtlasConcept(
        concept=concept,
        abi_index=0,
        abi_bank=0,
        abi_row=0,
        active=True,
        implementation_status="ADMITTED",
        teaching_candidate=True,
        teaching_reason="fixture",
    )
    return replace(
        snapshot,
        counts=replace(snapshot.counts, semantic_concepts=1),
        concepts=(frozen,),
        concept_lookup=((concept.semantic_id, 0),),
    )


def _snapshot_with_authoritative_types(
    *, inactive: tuple[int, ...] = (),
) -> FrozenAtlasSnapshot:
    snapshot = _snapshot(inactive=inactive)
    concepts = tuple(
        FrozenAtlasConcept(
            concept=AtlasConcept(
                semantic_id=entry.semantic_id,
                kind="FORMAL",
                types=("Entity",),
                labels=(),
                realizations=(),
                source_loci=(),
                relations=(),
                source_rows=(),
            ),
            abi_index=entry.index,
            abi_bank=entry.bank,
            abi_row=entry.row,
            active=entry.active,
            implementation_status=(
                "ADMITTED" if entry.active else "IMPLEMENTATION_UNCOVERED"
            ),
            teaching_candidate=entry.teaching_candidate,
            teaching_reason="fixture",
        )
        for entry in snapshot.abi_entries
    )
    return replace(
        snapshot,
        counts=replace(snapshot.counts, semantic_concepts=len(concepts)),
        concepts=concepts,
        concept_lookup=tuple(
            (item.concept.semantic_id, index)
            for index, item in enumerate(concepts)
        ),
    )

__all__ = tuple(name for name in globals() if not name.startswith('__'))
