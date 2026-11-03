"""Occurrence-aware frame-schema source_authority with source-owned authority."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.frame_schema")

from ..atlas_projection import FrozenAtlasSnapshot
from ..core import Signature
from .contracts import _fail, source_node_digest
from .schema import SourceSpan
from .roles import ConceptRef
from .errors import _binding_fail


def concept_ref_from_snapshot(
    snapshot: FrozenAtlasSnapshot,
    semantic_id: str,
    *,
    source_reference: str,
    type_ids: tuple[str, ...] | None = None,
) -> ConceptRef:
    if not isinstance(snapshot, FrozenAtlasSnapshot):
        _public()._fail("FRAME_ATLAS_SNAPSHOT_REQUIRED")
    abi = snapshot.abi_for_semantic(semantic_id)
    matching = tuple(
        item for item in snapshot.concepts
        if item.concept.semantic_id == semantic_id)
    if len(matching) != 1:
        _public()._fail("FRAME_CONCEPT_TYPES_REQUIRED")
    authoritative = matching[0].concept.types
    if type_ids is not None and tuple(type_ids) != tuple(authoritative):
        _public()._fail("FRAME_CONCEPT_TYPE_AUTHORITY_MISMATCH")
    type_ids = authoritative
    return ConceptRef(
        semantic_id=semantic_id,
        semantic_release=snapshot.release_sha256,
        abi_index=abi.index,
        type_ids=tuple(sorted(set(type_ids))),
        source_reference=source_reference,
    )



def _formal_source_types(
    snapshot: FrozenAtlasSnapshot,
    concept: ConceptRef,
    source_graph: dict | None,
    source_adapter_id: str | None,
    source_span: SourceSpan,
    role_id: str,
) -> tuple[str, ...]:
    if source_graph is None or not source_adapter_id:
        _public()._binding_fail("FRAME_CONCEPT_TYPE_AUTHORITY_MISSING", source_span, role_id)
    entry = snapshot.abi_for_semantic(concept.semantic_id)
    symbol = entry.symbol
    if not symbol or concept.source_reference != source_adapter_id + ":" + symbol:
        _public()._binding_fail("FRAME_CONCEPT_TYPE_AUTHORITY_MISSING", source_span, role_id)
    try:
        index = source_graph["tokens"].index(symbol)
        node = source_graph["nodes"][index]
        if (index != entry.index or node.get("id") != symbol
                or source_graph["row_contract_sha256"][symbol]
                != _public().source_node_digest(node)):
            _public()._binding_fail("FRAME_CONCEPT_TYPE_AUTHORITY_MISSING", source_span, role_id)
        raw_signature = node["signature"]
        if (isinstance(raw_signature, str) and raw_signature
                and "->" not in raw_signature
                and "(" not in raw_signature):
            output_type = raw_signature
        else:
            output_type = Signature.parse(raw_signature).output
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        _public()._binding_fail("FRAME_CONCEPT_TYPE_AUTHORITY_MISSING", source_span, role_id)
    return (output_type,)
