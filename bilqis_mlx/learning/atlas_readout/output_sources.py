"""Active output identity checks supplement the source frame's type rules."""
from bilqis_mlx.semantics.frame_schema import ConceptRef, RoleOccurrence
from .records import invalid


def require_active_value(snapshot, value):
    if type(value) is ConceptRef:
        values = (value,)
    elif type(value) is RoleOccurrence:
        values = ((value.concept,) if value.concept is not None else value.alternatives)
    else:
        invalid()
    for concept in values:
        if type(concept) is not ConceptRef or concept.semantic_release != snapshot.release_sha256:
            invalid()
        try:
            entry = snapshot.abi_for_semantic(concept.semantic_id)
        except (IndexError, TypeError):
            invalid()
        if (entry.index != concept.abi_index or entry.semantic_id != concept.semantic_id
                or entry.active is not True):
            invalid()
