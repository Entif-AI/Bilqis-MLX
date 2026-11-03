"""Immutable codec fixtures and the original per-case setup."""
from __future__ import annotations

import unittest

from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasCounts, CorpusCoverageRow, FrozenAtlasSnapshot,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
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


class CodecCase(unittest.TestCase):
    def setUp(self):
        self.schemas = tuple(_schema(name) for name in ("A", "B", "C", "D"))
        self.schema_map = SchemaTagMap.from_schemas(RELEASE, self.schemas)
