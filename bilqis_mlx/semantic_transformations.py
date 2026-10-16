"""Typed Grade A semantic transformations and source-oracled candidate probes.

Transformation laws generate contrasts, not neural training permission. They
preserve the existing 144/72 source manifest, checkpoint and AdamW intact.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from collections import defaultdict
import hashlib
from itertools import permutations
import json

from .grade_a_oracle import evaluate as independent_evaluate


@dataclass(frozen=True)
class SemanticLaw:
    capability: str
    name: str
    effect: str  # preserve or flip the two-valued answer
    source_axiom: str


# The names encode *source-defined* properties, not New Ithkuil homonyms.
# Only independently defined Grade A finite-world semantics are included.
LAWS = (
    SemanticLaw("A.IDENTITY", "alpha_rename", "preserve", "entity-renaming-bijection"),
    SemanticLaw("A.IDENTITY", "reverse_query", "preserve", "equality-commutativity"),
    SemanticLaw("A.PARENT", "alpha_rename", "preserve", "entity-renaming-bijection"),
    SemanticLaw("A.PARENT", "reverse_query", "flip", "single-directed-parent-fact"),
    SemanticLaw("A.LINK", "alpha_rename", "preserve", "entity-renaming-bijection"),
    SemanticLaw("A.LINK", "reverse_query", "preserve", "symmetric-link-relation"),
    SemanticLaw("A.MEMBER", "alpha_rename", "preserve", "entity-renaming-bijection"),
    SemanticLaw("A.MEMBER", "toggle_membership", "flip", "finite-set-membership-counterexample"),
    SemanticLaw("A.EDGE", "alpha_rename", "preserve", "entity-renaming-bijection"),
    SemanticLaw("A.EDGE", "reverse_query", "flip", "single-directed-edge-fact"),
    SemanticLaw("A.MAPS", "alpha_rename", "preserve", "entity-renaming-bijection"),
    SemanticLaw("A.MAPS", "toggle_mapping", "flip", "single-function-mapping-counterexample"),
)


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _id(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _entities(record: dict) -> list[str]:
    world = record["world"]
    base = world if "entities" in world else world["base"]
    entities = base["entities"]
    if not 3 <= len(entities) <= 4 or len(set(entities)) != len(entities):
        raise ValueError("SEMANTIC_LAW_WORLD_UNSUPPORTED")
    return entities


def _rename(record: dict, mapping: dict[str, str]) -> dict:
    """Only referent IDs change; typed operators and set/function IDs stay."""
    def change(value):
        if isinstance(value, str):
            return mapping.get(value, value)
        if isinstance(value, list):
            return [change(v) for v in value]
        if isinstance(value, dict):
            return {k: change(v) for k, v in value.items()}
        return value

    changed = change(record)
    world = changed["world"]
    base = world if "entities" in world else world["base"]
    base["entities"].sort()
    for values in world.get("sets", {}).values():
        values.sort()
    return changed


def canonical_orbit(record: dict) -> str:
    """Structural fingerprint invariant to a bijective renaming of entities."""
    entities = sorted(_entities(record))
    target = tuple("ABCDE"[:len(entities)])
    representations = (_canonical(_rename(record, dict(zip(entities, perm))))
                       for perm in permutations(target))
    return hashlib.sha256(min(representations).encode("utf-8")).hexdigest()


def _law(capability: str, name: str) -> SemanticLaw:
    result = next((x for x in LAWS if x.capability == capability and x.name == name), None)
    if result is None:
        raise ValueError("UNSUPPORTED_SEMANTIC_LAW:" + capability + ":" + name)
    return result


def apply_law(record: dict, capability: str, name: str) -> dict:
    """Execute a bounded typed axiom; independent oracles check its result."""
    _law(capability, name)
    # Reject malformed/unrecognized source forms before transformation.
    independent_evaluate(record, capability)
    result = deepcopy(record)
    if name == "alpha_rename":
        return _rename(record, dict(zip("ABCDE", "BCDEA")))

    query = result["query"]
    world = result["world"]
    if name == "reverse_query":
        args = query["args"]
        if len(args) != 2:
            raise ValueError("SEMANTIC_LAW_QUERY_ARITY_DRIFT")
        if capability in ("A.PARENT", "A.EDGE"):
            # The Grade A source constrains each world to one directed fact.
            facts = world["facts"] if capability == "A.PARENT" else world["edges"]
            if len(facts) != 1:
                raise ValueError("SEMANTIC_LAW_NON_SINGLE_DIRECTED_FACT")
        query["args"] = [args[1], args[0]]
        return result

    if name == "toggle_membership":
        element = query["args"][0]["name"]
        set_name = query["args"][1]["name"]
        members = world["sets"][set_name]
        if element in members:
            substitutes = sorted(set(_entities(record)) - set(members))
            if not substitutes:
                raise ValueError("SEMANTIC_LAW_NO_FINITE_SET_COUNTEREXAMPLE")
            members.remove(element)
            members.append(substitutes[0])
        else:
            if not members:
                raise ValueError("SEMANTIC_LAW_EMPTY_SET_CANNOT_PRESERVE_CARDINALITY")
            members[0] = element
        members.sort()
        return result

    if name == "toggle_mapping":
        function = query["args"][0]["name"]
        source = query["args"][1]["name"]
        target = query["args"][2]["name"]
        pairs = world["functions"][function]
        if len(pairs) != 1 or pairs[0][0] != source:
            raise ValueError("SEMANTIC_LAW_NON_SINGLE_FUNCTION_MAPPING")
        if pairs[0][1] == target:
            alternatives = sorted(set(_entities(record)) - {source, target})
            if not alternatives:
                raise ValueError("SEMANTIC_LAW_NO_FUNCTION_COUNTEREXAMPLE")
            pairs[0][1] = alternatives[0]
        else:
            pairs[0][1] = target
        return result

    raise ValueError("UNSUPPORTED_SEMANTIC_LAW:" + name)


def compile_transformations(training_rows, *, ast, micro, development, graph,
                            exam_ids):
    """Produce independently verified, unreleased metamorphic teaching candidates.

    The only inputs may be existing teaching records. Exam item IDs are an
    exclusion set only, never examples or adaptive teacher reward material.
    """
    from .grade_a_probe import FAMILIES

    nodes = {node.id: node for node in ast.nodes}
    roots = {cap: root for cap, root, _, _ in FAMILIES}
    if ast.authorized_for_training:
        raise ValueError("SEMANTIC_COMPILER_CANNOT_AUTHORIZE_TRAINING")
    for cap, root in roots.items():
        node = nodes.get(cap)
        if (node is None or node.roots != (root,) or node.answers != ("binary",)
                or node.requires or node.composed_of):
            raise ValueError("SEMANTIC_COMPILER_AST_UNSUPPORTED:" + cap)
    forbidden = set(exam_ids)
    existing = {r["id"] for r in training_rows}
    result = []
    seen = set(existing) | forbidden
    for row in training_rows:
        if row.get("partition") != "train":
            raise ValueError("SEMANTIC_COMPILER_TRAINING_SOURCES_ONLY")
        cap = row["capability"]
        if cap not in nodes or _id(row["record"]) != row["id"] or row["id"] in forbidden:
            raise ValueError("SEMANTIC_COMPILER_SOURCE_ID_OR_AST_DRIFT")
        library = micro if row["record"]["task"] == "micro" else development
        actual = independent_evaluate(row["record"], cap)
        if actual != row["gold"] or library.evaluate(row["record"]) != actual:
            raise ValueError("SEMANTIC_COMPILER_SOURCE_ORACLE_DRIFT")
        for law in (x for x in LAWS if x.capability == cap):
            changed = apply_law(row["record"], cap, law.name)
            new_id = _id(changed)
            if new_id in seen:
                continue
            expected = (actual if law.effect == "preserve" else
                        "FALSE" if actual == "TRUE" else "TRUE")
            if (independent_evaluate(changed, cap) != expected or
                    library.evaluate(changed) != expected or
                    library.independent_evaluate(changed) != expected):
                raise ValueError("SEMANTIC_COMPILER_METAMORPHIC_LAW_FALSE:" + law.name)
            tokens = list(library.encode(changed))
            if not tokens or len(tokens) > 96 or min(tokens) < 0 or max(tokens) >= len(graph["tokens"]):
                raise ValueError("SEMANTIC_COMPILER_INVALID_HISTORICAL_TOKEN")
            seen.add(new_id)
            result.append({"id": new_id, "capability": cap, "record": changed,
                           "tokens": tokens, "gold": expected, "answer_kind": "binary",
                           "parent_id": row["id"], "law": law.name,
                           "source_axiom": law.source_axiom, "effect": law.effect,
                           "semantic_orbit": canonical_orbit(changed),
                           "admitted": False})
    return tuple(result)


def audit_structural_coverage(rows) -> dict:
    """Count semantic structures modulo bijective entity-name permutations.

    A curriculum with 24 different serialized samples may still present only
    four mathematical structures. Counting records alone misses this defect.
    """
    groups = defaultdict(list)
    seen_ids = set()
    for row in rows:
        if row["id"] in seen_ids:
            raise ValueError("SEMANTIC_COMPILER_REUSED_RECORD_ID")
        seen_ids.add(row["id"])
        if _id(row["record"]) != row["id"]:
            raise ValueError("SEMANTIC_COMPILER_RECORD_ID_MISMATCH")
        if row["gold"] != independent_evaluate(row["record"], row["capability"]):
            raise ValueError("SEMANTIC_COMPILER_ORACLE_MISMATCH")
        groups[row["capability"]].append(row)
    result = {}
    for capability, records in sorted(groups.items()):
        classes = defaultdict(set)
        for row in records:
            factor = (len(_entities(row["record"])), row["gold"])
            classes[factor].add(canonical_orbit(row["record"]))
        family_count = len(set().union(*classes.values()))
        counts = {f"world-{size}/{label}": len(orbits)
                  for (size, label), orbits in sorted(classes.items())}
        result[capability] = {
            "example_count": len(records),
            "isomorphic_family_count": family_count,
            "families_per_factor": counts,
            "repeated_isomorphic_examples": len(records) - family_count,
            "underspecified_factors": tuple(k for k, v in counts.items() if v < 2),
            "diagnosis": "SEMANTIC_VARIATION_EXHAUSTED" if any(v < 2 for v in counts.values())
                         else "MULTIPLE_STRUCTURAL_FAMILIES",
            "training_authorized": False,
        }
    return result


def diagnose_growth(*, train_before: float, train_after: float,
                    validation_before: float, validation_after: float,
                    validation_family_count: int) -> dict:
    """Classify *mechanisms to investigate*, never automatically schedule SGD."""
    for value in (train_before, train_after, validation_before, validation_after):
        if not isinstance(value, (float, int)) or not 0 <= value <= 1:
            raise ValueError("SEMANTIC_COMPILER_SCORE_OUT_OF_RANGE")
    if type(validation_family_count) is not int or validation_family_count < 0:
        raise ValueError("SEMANTIC_COMPILER_INVALID_VALIDATION_FAMILY_COUNT")
    in_sample = train_after - train_before
    transfer = validation_after - validation_before
    if validation_family_count == 0:
        failure, action = ("NO_INDEPENDENT_VALIDATION", "CONSTRUCT_HELD_OUT_FAMILIES")
    elif in_sample >= .10 and transfer <= .02:
        failure, action = ("GENERALIZATION_GAP", "RECOMPILE_VARIATION_FAMILIES")
    elif transfer < -.05:
        failure, action = ("HELD_OUT_REGRESSION", "INVESTIGATE_INTERFERENCE")
    else:
        failure, action = ("INCONCLUSIVE_OR_TRANSFER", "CONTINUE_INDEPENDENT_PROBES")
    return {"failure_mode": failure, "action": action,
            "training_gain": in_sample, "held_out_gain": transfer,
            "validation_family_count": validation_family_count,
            "training_authorized": False}
