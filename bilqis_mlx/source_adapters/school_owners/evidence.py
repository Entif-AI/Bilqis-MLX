"""Evidence callbacks for the historical school source contract."""
from __future__ import annotations
from .shared import (B_COMPOSITE_CAPABILITY, B_IDBOOLOPS_CAPABILITY, CONNECTIVES, PLANS, SupplementalEvidenceSpec, inspect_boolean_identification, inspect_source_query,)


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


def witness_numeric_obligation(row, obligation, *, source_root, graph, course):
    """Certify finite-numeric dependency transfer from the source lesson plan."""
    del source_root, graph
    capability = row.get("capability")
    plan = next((item for item in PLANS if item.capability == capability), None)
    if (plan is None or row.get("lesson_id") != plan.lesson_id or
            capability not in course.capability_map):
        raise ValueError("FACTORY_NUMERIC_EVIDENCE_PLAN_DRIFT")
    kind = getattr(getattr(obligation, "kind", None), "value", None)
    if kind == "PREREQUISITE":
        return getattr(obligation, "key", None) in plan.prerequisites
    if kind == "COMPOSITION":
        return getattr(obligation, "key", None) in course.capability_map[
            capability].composed_of
    raise ValueError("FACTORY_NUMERIC_EVIDENCE_KIND_UNSUPPORTED")


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

for _callback in (witness_micro_obligation, witness_numeric_obligation, boolean_evidence_dependencies,):
    _callback.__module__ = "bilqis_mlx.source_adapters.school"
