"""School source evidence."""
from __future__ import annotations

from ...factory.autonomy import SupplementalEvidenceSpec
from ...grade_b_oracle import CONNECTIVES
from ...boolean_composite import CAPABILITY as B_COMPOSITE_CAPABILITY
from ...boolean_identification import CAPABILITY as B_IDBOOLOPS_CAPABILITY
from ...live_grade_c import PLANS
from ..structure import inspect_boolean_identification, inspect_source_query


_PRODUCER_KEY_DRIFT = "FACTORY_MICRO_EVIDENCE_PRODUCER_KEY_DRIFT"


def witness_micro_obligation(row, obligation, *, source_root, graph, course):
    """Certify structural learner evidence in the finite-micro source dialect."""
    del source_root, graph
    required = tuple(getattr(obligation, "requires_capabilities", ()))
    if len(required) != 1:
        raise ValueError("FACTORY_MICRO_EVIDENCE_REQUIRES_ONE_PRODUCER")
    producer = course.capability_map.get(required[0])
    if producer is None or len(producer.examined_roots) != 1:
        raise ValueError("FACTORY_MICRO_EVIDENCE_PRODUCER_ROOT_UNRESOLVED")
    declared_producer_id = getattr(producer, "id", None)
    if declared_producer_id is None:
        declared_producer_id = getattr(producer, "capability_id", None)
    if not isinstance(declared_producer_id, str) or not declared_producer_id:
        raise ValueError("FACTORY_MICRO_EVIDENCE_PRODUCER_ID_UNRESOLVED")
    producer_root = producer.examined_roots[0]
    record = row.get("record")
    if not isinstance(record, dict):
        raise ValueError("FACTORY_MICRO_EVIDENCE_RECORD_MISSING")

    kind = getattr(getattr(obligation, "kind", None), "value", None)
    if kind == "PREREQUISITE":
        if record.get("task") == "identify_boolean_operator":
            shape = inspect_boolean_identification(record, row.get("root"))
        else:
            shape = inspect_source_query(record.get("query"))
        return producer_root in shape.rooted_operators

    if kind == "COMPOSITION":
        key = getattr(obligation, "key", "")
        if "@" not in key:
            if key != declared_producer_id:
                raise ValueError(_PRODUCER_KEY_DRIFT)
            if record.get("task") == "identify_boolean_operator":
                shape = inspect_boolean_identification(record, row.get("root"))
            else:
                shape = inspect_source_query(record.get("query"))
            return any(root in shape.rooted_operators
                       for root in producer.examined_roots)
        try:
            producer_id, slot_raw = key.rsplit("@", 1)
            slot = int(slot_raw)
        except (AttributeError, ValueError) as exc:
            raise ValueError("FACTORY_MICRO_EVIDENCE_COMPOSITION_KEY_INVALID") from exc
        if producer_id != declared_producer_id:
            raise ValueError(_PRODUCER_KEY_DRIFT)
        query = record.get("query")
        args = query.get("args") if isinstance(query, dict) else None
        if (query.get("kind") != "apply" if isinstance(query, dict) else True) or not isinstance(args, list):
            raise ValueError("FACTORY_MICRO_EVIDENCE_COMPOSITION_AST_INVALID")
        if not 0 <= slot < len(args):
            return False
        return inspect_source_query(args[slot]).root == producer_root

    raise ValueError("FACTORY_MICRO_EVIDENCE_KIND_UNSUPPORTED")




def boolean_evidence_dependencies(*, course, capability):
    """Resolve each direct Boolean producer from the declared curriculum."""
    if capability == B_COMPOSITE_CAPABILITY:
        kind = "COMPOSITION"
    elif capability == B_IDBOOLOPS_CAPABILITY:
        kind = "PREREQUISITE"
    else:
        return ()
    result = []
    for operator in CONNECTIVES:
        root = "cogal.operator." + operator
        producers = tuple(identity for identity, producer in course.capability_map.items()
                          if producer.examined_roots == (root,))
        if len(producers) != 1:
            raise ValueError("FACTORY_BOOLEAN_EVIDENCE_PRODUCER_UNRESOLVED:" + root)
        identity = producers[0]
        result.append(SupplementalEvidenceSpec(
            capability_id=capability, kind=kind, key=identity,
            requires_capabilities=(identity,)))
    return tuple(result)
