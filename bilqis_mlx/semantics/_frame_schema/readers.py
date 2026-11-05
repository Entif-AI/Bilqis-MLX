"""Occurrence-aware frame-schema readers with source-owned authority."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.frame_schema")

import json

from ...errors import BilqisError
from .contracts import _fail
from .schema import SourceSpan, RoleSpec, FrameSchema
from .roles import BindingState, ConceptRef, ChildFrameRef, RoleOccurrence
from .instances import FrameInstance


def frame_schema_from_bytes(payload: bytes) -> FrameSchema:
    try:
        value = json.loads(payload)
        roles = tuple(RoleSpec(
            role_id=item["role_id"],
            allowed_type_ids=tuple(item["allowed_type_ids"]),
            min_cardinality=item["min_cardinality"],
            max_cardinality=item["max_cardinality"],
            schema_version=item["schema_version"],
        ) for item in value["roles"])
        schema = FrameSchema(
            schema_id=value["schema_id"],
            revision=value["revision"],
            ast_construct=value["ast_construct"],
            roles=roles,
            order_mode=value["order_mode"],
            scope=value["scope"],
            ast_contract_sha256=value.get("ast_contract_sha256"),
            schema_version=value["schema_version"],
        )
    except BilqisError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _public()._fail("FRAME_SCHEMA_SERIALIZATION_INVALID:" + type(error).__name__)
    if schema.canonical_bytes() != payload:
        _public()._fail("FRAME_SCHEMA_SERIALIZATION_NONCANONICAL")
    return schema



def frame_instance_from_bytes(payload: bytes) -> FrameInstance:
    try:
        value = json.loads(payload)
        bindings = []
        for item in value["bindings"]:
            concept_value = item["concept"]
            concept = (ConceptRef(
                semantic_id=concept_value["semantic_id"],
                semantic_release=concept_value["semantic_release"],
                abi_index=concept_value["abi_index"],
                type_ids=tuple(concept_value["type_ids"]),
                source_reference=concept_value["source_reference"],
                schema_version=concept_value["schema_version"],
            ) if concept_value is not None else None)
            child_value = item["child_frame"]
            child = (ChildFrameRef(
                occurrence_id=child_value["occurrence_id"],
                content_digest=child_value["content_digest"],
                type_ids=tuple(child_value["type_ids"]),
                schema_version=child_value["schema_version"],
            ) if child_value is not None else None)
            alternatives = tuple(ConceptRef(
                semantic_id=alternative["semantic_id"],
                semantic_release=alternative["semantic_release"],
                abi_index=alternative["abi_index"],
                type_ids=tuple(alternative["type_ids"]),
                source_reference=alternative["source_reference"],
                schema_version=alternative["schema_version"],
            ) for alternative in item.get("alternatives", ()))
            bindings.append(RoleOccurrence(
                role_id=item["role_id"],
                occurrence_index=item["occurrence_index"],
                concept=concept,
                child_frame=child,
                state=BindingState(item.get("state", BindingState.VALUE.value)),
                alternatives=alternatives,
                schema_version=item["schema_version"],
            ))
        instance = FrameInstance(
            frame_schema_id=value["frame_schema_id"],
            frame_schema_revision=value["frame_schema_revision"],
            occurrence_id=value["occurrence_id"],
            content_digest=value["content_digest"],
            source_instance_id=value["source_instance_id"],
            structural_path=tuple(value["structural_path"]),
            source_span=SourceSpan(**value["source_span"]),
            parent_occurrence_id=value["parent_occurrence_id"],
            bindings=tuple(bindings),
            schema_role_order=tuple(value["schema_role_order"]),
            causal_prefix_end=value["causal_prefix_end"],
            schema_version=value["schema_version"],
        )
    except BilqisError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _public()._fail("FRAME_INSTANCE_SERIALIZATION_INVALID:" + type(error).__name__)
    if instance.canonical_bytes() != payload:
        _public()._fail("FRAME_INSTANCE_SERIALIZATION_NONCANONICAL")
    return instance
