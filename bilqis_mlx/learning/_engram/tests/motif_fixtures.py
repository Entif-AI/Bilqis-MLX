"""Frozen source protocols and full-page fixture for motif owner tests."""
from dataclasses import dataclass, replace
from functools import lru_cache
from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY, MotifFrameInput, MotifManifest, MotifSlot, motif_keys

RELEASE = "a" * 64

SCOPE = "source:scope:1"

_COUNT = 0

@dataclass(frozen=True)
class Role:
    role_id: str
    allowed_type_ids: tuple[str, ...]
    min_cardinality: int = 0
    max_cardinality: int = 1

@dataclass(frozen=True)
class Schema:
    roles: tuple[Role, ...]
    schema_id: str = "source:relation"
    revision: int = 1
    ast_construct: str = "apply:relation"
    ast_contract_sha256: str = "b" * 64
    order_mode: str = "ORDERED"
    scope: str = SCOPE
    schema_version: str = "bilqis.semantic-frame-schema/v1"

@dataclass(frozen=True)
class Concept:
    semantic_id: str
    type_ids: tuple[str, ...]
    semantic_release: str = RELEASE
    source_reference: str = "source:approved:row"
    schema_version: str = "bilqis.semantic-concept-ref/v1"

@dataclass(frozen=True)
class Child:
    occurrence_id: str = "c" * 64
    content_digest: str = "d" * 64
    type_ids: tuple[str, ...] = ("Frame",)
    schema_version: str = "bilqis.semantic-child-frame-ref/v1"

@dataclass(frozen=True)
class Binding:
    role_id: str
    occurrence_index: int
    concept: Concept | None = None
    child_frame: Child | None = None
    state: str = "VALUE"
    alternatives: tuple[Concept, ...] = ()

@dataclass(frozen=True)
class Frame:
    bindings: tuple[Binding, ...]
    schema_role_order: tuple[str, ...]
    occurrence_id: str = "1" * 64
    content_digest: str = "2" * 64
    frame_schema_id: str = "source:relation"
    frame_schema_revision: int = 1
    schema_version: str = "bilqis.semantic-frame-instance/v2"

def source(
    actor="urn:actor:alice", patient="urn:patient:bob", *,
    scope=SCOPE, state="VALUE", child=False, types=("Person",),
    occurrence="1" * 64,
):
    schema = Schema((
        Role("actor", ("Frame", "Person")),
        Role("patient", ("Person",)),
    ), scope=scope)
    actor_binding = (
        Binding("actor", 0, child_frame=Child()) if child else
        Binding("actor", 0, concept=Concept(actor, types)))
    patient_binding = Binding("patient", 0, concept=Concept(patient, ("Person",)))
    if state == "NONE":
        actor_binding = Binding("actor", 0, state="NONE")
    elif state == "UNKNOWN":
        actor_binding = Binding("actor", 0, state="UNKNOWN")
    elif state == "ALTERNATIVES":
        actor_binding = Binding(
            "actor", 0, state="ALTERNATIVES",
            alternatives=(Concept(actor, types), Concept("urn:actor:carol", types)))
    frame = Frame((actor_binding, patient_binding),
                  ("actor", "patient"), occurrence_id=occurrence)
    return MotifFrameInput(frame, schema)

@lru_cache(maxsize=1)
def full_first_page() -> MotifManifest:
    base = motif_keys(source(), RELEASE)[0]
    return MotifManifest(
        RELEASE,
        tuple(MotifSlot(index, replace(base, relation_signature=f"{index:064x}"))
              for index in range(INITIAL_MOTIF_CAPACITY)),
    )

if __name__ == "__main__":
    import unittest
    unittest.main()
