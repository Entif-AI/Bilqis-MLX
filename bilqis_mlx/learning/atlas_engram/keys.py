"""Keys for the existing atlas engram contract."""
from __future__ import annotations

import json
from .contracts import (
    CHILD_SCHEMA, CONCEPT_SCHEMA, FRAME_INPUT_SCHEMA, FRAME_INSTANCE_SCHEMA, FRAME_SCHEMA,
    MotifFrameInput, MotifKey, MotifMember, _SHA, _STATES,
    _digest, _invalid,
)


def _state(binding) -> str:
    value = getattr(binding.state, "value", binding.state)
    if value not in _STATES:
        _invalid("BAMF_MOTIF_BINDING_STATE_INVALID")
    return value


def _member(binding, role, release: str, structural: bool) -> MotifMember:
    state = _state(binding)
    if (binding.role_id != role.role_id
            or type(binding.occurrence_index) is not int
            or binding.occurrence_index < 0):
        _invalid("BAMF_MOTIF_ROLE_INVALID")
    concept = binding.concept
    child = binding.child_frame
    if state == "VALUE":
        if (concept is None) == (child is None):
            _invalid("BAMF_MOTIF_TARGET_INVALID")
        if concept is not None:
            if (concept.schema_version != CONCEPT_SCHEMA
                    or concept.semantic_release != release
                    or not concept.semantic_id
                    or not concept.source_reference
                    or not set(concept.type_ids).intersection(role.allowed_type_ids)):
                _invalid("BAMF_MOTIF_CONCEPT_SOURCE_INVALID")
            kind = "TYPE" if structural else "CONCEPT"
            ids = tuple(concept.type_ids) if structural else (concept.semantic_id,)
            types = tuple(concept.type_ids)
        else:
            if (child.schema_version != CHILD_SCHEMA
                    or not _SHA.fullmatch(child.occurrence_id)
                    or not _SHA.fullmatch(child.content_digest)
                    or not set(child.type_ids).intersection(role.allowed_type_ids)):
                _invalid("BAMF_MOTIF_CHILD_SOURCE_INVALID")
            kind = "CHILD_TYPE" if structural else "CHILD_FRAME"
            ids = (tuple(child.type_ids) if structural else
                   (child.occurrence_id, child.content_digest))
            types = tuple(child.type_ids)
    elif state == "ALTERNATIVES":
        alternatives = tuple(binding.alternatives)
        if not alternatives or concept is not None or child is not None:
            _invalid("BAMF_MOTIF_ALTERNATIVES_INVALID")
        if any(item.schema_version != CONCEPT_SCHEMA
               or item.semantic_release != release
               or not set(item.type_ids).intersection(role.allowed_type_ids)
               for item in alternatives):
            _invalid("BAMF_MOTIF_ALTERNATIVE_SOURCE_INVALID")
        kind = "ALTERNATIVE_TYPES" if structural else "ALTERNATIVE_CONCEPTS"
        ids = (tuple(json.dumps(item.type_ids, separators=(",", ":"))
                     for item in alternatives)
               if structural else tuple(item.semantic_id for item in alternatives))
        types = ()
    else:
        if concept is not None or child is not None or binding.alternatives:
            _invalid("BAMF_MOTIF_UNKNOWN_TARGET_INVALID")
        kind, ids, types = state, (), ()
    return MotifMember(binding.role_id, binding.occurrence_index,
                       state, kind, ids, types)


def motif_keys(source: MotifFrameInput, release: str) -> tuple[MotifKey, MotifKey]:
    """Derive exact and typed structural identities from the A03-owned wire shape."""
    if (not isinstance(source, MotifFrameInput)
            or source.schema_version != FRAME_INPUT_SCHEMA
            or not _SHA.fullmatch(release)):
        _invalid("BAMF_MOTIF_FRAME_INPUT_INVALID")
    frame, schema = source.frame, source.schema
    try:
        role_order = tuple(role.role_id for role in schema.roles)
        bindings = tuple(frame.bindings)
        if (frame.schema_version != FRAME_INSTANCE_SCHEMA
                or schema.schema_version != FRAME_SCHEMA
                or (frame.frame_schema_id, frame.frame_schema_revision)
                != (schema.schema_id, schema.revision)
                or frame.schema_role_order != role_order
                or not schema.scope or not schema.ast_construct
                or not _SHA.fullmatch(frame.occurrence_id)
                or not _SHA.fullmatch(frame.content_digest)):
            _invalid("BAMF_MOTIF_FRAME_SCHEMA_MISMATCH")
        role_map = {role.role_id: role for role in schema.roles}
        if len(role_map) != len(role_order):
            _invalid("BAMF_MOTIF_ROLE_ORDER_INVALID")
        rank = {role: index for index, role in enumerate(role_order)}
        keys = tuple((binding.role_id, binding.occurrence_index)
                     for binding in bindings)
        if (any(role not in role_map for role, _ in keys)
                or keys != tuple(sorted(keys, key=lambda k: (rank[k[0]], k[1])))
                or len(keys) != len(set(keys))):
            _invalid("BAMF_MOTIF_ROLE_ORDER_INVALID")
        exact = tuple(_member(binding, role_map[binding.role_id], release, False)
                      for binding in bindings)
        structural = tuple(_member(binding, role_map[binding.role_id], release, True)
                           for binding in bindings)
        exact_relations = tuple(
            (binding.role_id, binding.occurrence_index,
             binding.child_frame.occurrence_id,
             binding.child_frame.content_digest)
            for binding in bindings if binding.child_frame is not None)
        structural_relations = tuple(
            (binding.role_id, binding.occurrence_index,
             tuple(binding.child_frame.type_ids))
            for binding in bindings if binding.child_frame is not None)
        signature_base = (
            schema.ast_construct, schema.ast_contract_sha256,
            schema.order_mode)
        exact_signature = _digest((*signature_base, exact_relations))
        structural_signature = _digest((*signature_base, structural_relations))
    except (AttributeError, TypeError, ValueError) as error:
        _invalid("BAMF_MOTIF_FRAME_INPUT_INVALID:" + type(error).__name__)
    return (
        MotifKey("EXACT", release, schema.schema_id, schema.revision,
                 exact, exact_signature, schema.scope),
        MotifKey("STRUCTURAL", release, schema.schema_id, schema.revision,
                 structural, structural_signature, schema.scope),
    )
