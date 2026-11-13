"""Released, occurrence-aware semantic frame records over the native typed AST."""
from __future__ import annotations

from ._public_identity.module_identity import restore_public_module as _restore_public_module

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import re

from ..errors import BilqisError, ErrorBus, SEMANTIC_FRAME, SCHOOL
from .atlas_projection import FrozenAtlasSnapshot
from .core import Apply, Expression, Literal, Signature, expression_digest

from ._frame_schema.contracts import (
    _fail, _bytes, _digest,
    source_node_digest, _occurrence_digest, _text,
    FRAME_SCHEMA_RECORD, FRAME_INSTANCE_RECORD, CONCEPT_REF_RECORD,
    ROLE_SPEC_RECORD, ROLE_OCCURRENCE_RECORD, CHILD_FRAME_REF_RECORD,
    SOURCE_SPAN_RECORD, FRAME_EDGE_RECORD, ATOMIC_FRAME_RECORD,
    FRAME_TREE_RECORD, _SHA256, _ORDER_MODES,
)
from ._frame_schema.schema import (
    SourceSpan, RoleSpec, FrameSchema,
)
from ._frame_schema.roles import (
    BindingState, ConceptRef, ChildFrameRef,
    RoleOccurrence, FrameEdge, _frame_content_digest,
    _binding_concepts,
)
from ._frame_schema.instances import (
    FrameInstance, AtomicFrame, FrameTree,
    occurrence_id, content_digest, make_frame_instance,
)
from ._frame_schema.errors import (
    _binding_fail,
)
from ._frame_schema.ast_identity import (
    ast_construct_id, source_ast_construct_id, native_ast_content_digest,
    _source_payload, atomic_fallback,
)
from ._frame_schema.source_authority import (
    concept_ref_from_snapshot, _formal_source_types,
)
from ._frame_schema.bindings import (
    validate_frame_bindings, bind_frame_instance,
)
from ._frame_schema.forest import (
    bind_ast_frames, validate_frame_tree,
)
from ._frame_schema.readers import (
    frame_schema_from_bytes, frame_instance_from_bytes,
)




# Preserve canonical identities for frame-schema public contracts.
for _public in (
    _fail, _bytes, _digest,
    source_node_digest, _occurrence_digest, _text,
    SourceSpan, RoleSpec, FrameSchema,
    BindingState, ConceptRef, ChildFrameRef,
    RoleOccurrence, FrameEdge, _frame_content_digest,
    _binding_concepts, FrameInstance, AtomicFrame,
    FrameTree, occurrence_id, content_digest,
    make_frame_instance, _binding_fail, ast_construct_id,
    source_ast_construct_id, native_ast_content_digest, _source_payload,
    atomic_fallback, concept_ref_from_snapshot, _formal_source_types,
    validate_frame_bindings, bind_frame_instance, bind_ast_frames,
    validate_frame_tree, frame_schema_from_bytes, frame_instance_from_bytes,
):
    _restore_public_module(_public, __name__)
