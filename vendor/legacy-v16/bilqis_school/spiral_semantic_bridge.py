"""Versioned cross-domain School50 grammar over *existing* graph tokens.

The historic arithmetic, Boolean and finite-world ASTs are separate types.
This adapter composes their already-defined encodings and independently
checked oracles; it does not alter a token ID, historic grade, or P43 weight.
"""
from __future__ import annotations

import copy

from bilqis_development import kernel as finite
from bilqis_logic.kernel import TABLES, digest
from bilqis_micro.graph import STATES
from . import arithmetic, lessons

VERSION = "bilqis.school50.semantic-bridge/v1"
FAMILIES = ("iff_math", "implies_math", "membership", "subset")
ENTITIES = "ABCD"


def split_of(expression):
    """The unchanged numeric partition, owned by source, never projection."""
    bucket = int(digest(expression)[:12], 16) % 10
    return "train" if bucket < 6 else "development" if bucket < 8 else "sealed"


def source_id(expression):
    arithmetic.verify(expression)
    return digest(["shared-math-source/v1", expression])


def value(expression):
    arithmetic.verify(expression)
    result = arithmetic.evaluate(expression)
    if type(result) is not int or not 0 <= result <= arithmetic.MAX_NUMBER:
        raise ValueError("BRIDGE_SOURCE_NOT_ABI_INTEGER")
    return result


def _comparison(expression, expected):
    return arithmetic.operation("EQ", copy.deepcopy(expression), arithmetic.atom(expected))


def _truth(operator, left, right):
    if operator not in ("IFF", "IMPLIES") or type(left) is not bool or type(right) is not bool:
        raise ValueError("BRIDGE_LOGIC_OPERAND_TYPE")
    # The original COGAL truth-table order is TT, TF, FT, FF.
    table_result = TABLES[operator][(not left) * 2 + (not right)]
    independent = (left == right) if operator == "IFF" else ((not left) or right)
    if table_result != independent:
        raise ValueError("BRIDGE_BOOLEAN_ORACLE_DIVERGENCE")
    return table_result


def _set_record(expression, family, rng, truth):
    """Use real G11/G12 finite-world types and their independent oracles."""
    if family not in ("membership", "subset"):
        raise ValueError("BRIDGE_UNKNOWN_SET_FAMILY")
    anchor = ENTITIES[value(expression) % len(ENTITIES)]
    others = [entity for entity in ENTITIES if entity != anchor]
    rng.shuffle(others)
    if family == "membership":
        members = rng.sample(others,rng.randrange(len(others)+1)) + ([anchor] if truth else [])
        witness = rng.sample(list(ENTITIES),rng.randrange(len(ENTITIES)+1))
        world = finite.world(ENTITIES, sets={"K0": sorted(members), "K1": sorted(witness)})
        query = finite.op("MEMBER", finite.const("Entity", anchor), finite.const("Set", "K0"))
    else:
        first = sorted([anchor] + rng.sample(others,rng.randrange(len(others)+1)))
        if truth:
            second = sorted(first + rng.sample([x for x in ENTITIES if x not in first],
                                                rng.randrange(len(ENTITIES)-len(first)+1)))
        else:
            removed = rng.choice(first)
            second = sorted([x for x in ENTITIES if x != removed and
                             (x in first or bool(rng.randrange(2)))])
        world = finite.world(ENTITIES, sets={"K0": first, "K1": second})
        query = finite.op("SUBSET", finite.const("Set", "K0"), finite.const("Set", "K1"))
    record = finite.record(world, query)
    if (finite.evaluate(record) != finite.independent_evaluate(record) or
            finite.evaluate(record) != ("TRUE" if truth else "FALSE")):
        raise ValueError("BRIDGE_SET_ORACLE_DIVERGENCE")
    return record


def record(expression, candidate, relation, right):
    result = {"task": VERSION, "math_expression": copy.deepcopy(expression),
              "candidate": candidate, "logical_operator": relation,
              "right": copy.deepcopy(right)}
    evaluate(result)
    return result


def _operands(record_data, independent):
    if set(record_data) != {"task", "math_expression", "candidate", "logical_operator", "right"}:
        raise ValueError("BRIDGE_RECORD_FIELDS")
    if record_data["task"] != VERSION:
        raise ValueError("BRIDGE_RECORD_TASK")
    math_expr = record_data["math_expression"]
    numeric_value = value(math_expr)
    candidate = record_data["candidate"]
    if type(candidate) is not int or not 0 <= candidate <= arithmetic.MAX_NUMBER:
        raise ValueError("BRIDGE_CANDIDATE_NOT_INTEGER")
    predicate = _comparison(math_expr, candidate)
    left = (arithmetic.independent_evaluate if independent else arithmetic.evaluate)(predicate)
    right = record_data["right"]
    if set(right) != {"kind", "record"}:
        raise ValueError("BRIDGE_RIGHT_FIELDS")
    if right["kind"] == "math":
        arithmetic.verify(right["record"])
        response = (arithmetic.independent_evaluate if independent else arithmetic.evaluate)(right["record"])
    elif right["kind"] == "set":
        response = (finite.independent_evaluate if independent else finite.evaluate)(right["record"])
        if response not in ("TRUE", "FALSE"):
            raise ValueError("BRIDGE_SET_REQUIRES_BOOLEAN_ANSWER")
        response = response == "TRUE"
    else:
        raise ValueError("BRIDGE_RIGHT_KIND")
    if type(left) is not bool or type(response) is not bool:
        raise ValueError("BRIDGE_PREDICATE_NOT_BOOLEAN")
    return left, response


def evaluate(record_data):
    left, right = _operands(record_data, False)
    result = _truth(record_data["logical_operator"], left, right)
    independent_left, independent_right = _operands(record_data, True)
    if result != _truth(record_data["logical_operator"], independent_left, independent_right):
        raise ValueError("BRIDGE_COMPOSITE_ORACLE_DIVERGENCE")
    return "TRUE" if result else "FALSE"


def necessary_factors(record_data):
    """Demonstrate that toggling either proposition changes the gold."""
    left, right = _operands(record_data, False)
    operator = record_data["logical_operator"]
    base = _truth(operator, left, right)
    return (base != _truth(operator, not left, right) and
            base != _truth(operator, left, not right))


def encode(record_data, graph):
    evaluate(record_data)
    mapping = {token: index for index, token in enumerate(graph["tokens"])}
    math_input = {"task": arithmetic.VERSION,
                  "expression": _comparison(record_data["math_expression"], record_data["candidate"])}
    left = arithmetic.encode(math_input, mapping)[1:-1]
    right = record_data["right"]
    if right["kind"] == "math":
        rhs = arithmetic.encode({"task": arithmetic.VERSION, "expression": right["record"]}, mapping)[1:-1]
    else:
        # Finite-world records are encoded by their authoritative codec.
        # Remap through stable token names instead of assuming identical IDs.
        rhs = [mapping[finite.TOKENS[index]] for index in finite.encode(right["record"])[:-1]]
    result = [mapping["school.syntax.math"], mapping["cogal.operator." + record_data["logical_operator"]]]
    result.extend(left)
    result.extend(rhs)
    result.append(mapping["syntax.end"])
    if len(result) > 96:
        raise ValueError("BRIDGE_96_TOKEN_CONTEXT_OVERFLOW")
    return result


def _meta(grade, concept, source, family, difficulty, tranche, projection):
    return {"grade": grade, "concept": concept, "difficulty": difficulty,
            "tranche": tranche, "triplet_id": source_id(source),
            "semantic_source_id": source_id(source), "split": split_of(source),
            "mutation_mode": "cross_domain_composition", "projection": projection,
            "bridge_family": family}


def linked_triplet(grade, concept, expression, family, graph, rng, *, tranche="nonlocal", split="train"):
    """Low number / medium relation / hard logical composition, one source."""
    if family not in FAMILIES or split_of(expression) != split:
        raise ValueError("BRIDGE_FAMILY_OR_SOURCE_PARTITION")
    numeric = value(expression)
    if numeric >= arithmetic.MAX_NUMBER:
        raise ValueError("BRIDGE_CANNOT_MAKE_MINIMAL_FALSE_NUMBER")
    number = {"task": arithmetic.VERSION, "expression": copy.deepcopy(expression)}
    first = {"id": digest(number), "input": number, "gold": numeric,
             "answer_kind": "numeric", "family": f"spiral-numeric:{grade}",
             "course_meta": _meta(grade, concept, expression, family, "low", tranche, "numeric_value")}
    left_candidate = numeric if family == "implies_math" or bool(rng.randrange(2)) else numeric+1
    if family in ("iff_math", "implies_math"):
        rewritten = arithmetic.operation("ADD", copy.deepcopy(expression), arithmetic.atom(0))
        arithmetic.verify(rewritten)
        if arithmetic.evaluate(rewritten) != numeric:
            raise ValueError("BRIDGE_MATH_REWRITE_FAILED")
        if family == "iff_math":
            middle = arithmetic.row(_comparison(expression,left_candidate), 20)
            other_expected = numeric + rng.randrange(2)
            consequent = {"kind": "math", "record": _comparison(rewritten, other_expected)}
            composite = record(expression,left_candidate,"IFF",consequent)
            if not necessary_factors(composite):
                raise ValueError("BRIDGE_COMPOSITION_FACTOR_NOT_NECESSARY")
            projection = "logical_math"
        else:
            # A false-only implication curriculum is solvable by class bias.
            # Teach TRUE and FALSE on the *same source* by changing exactly
            # one consequent comparison. The false variant is sensitive to
            # both factors; the paired contrast makes the true case meaningful.
            second = arithmetic.operation("ADD",copy.deepcopy(rewritten),arithmetic.atom(0))
            arithmetic.verify(second)
            first_false = bool(rng.randrange(2))
            middle = record(expression,numeric,"IMPLIES",{
                "kind":"math", "record":_comparison(rewritten,numeric+int(first_false))})
            composite = record(expression,numeric,"IMPLIES",{
                "kind":"math", "record":_comparison(second,numeric+int(not first_false))})
            if ({evaluate(middle),evaluate(composite)}!={"TRUE","FALSE"} or
                    not necessary_factors(middle if evaluate(middle)=="FALSE" else composite)):
                raise ValueError("BRIDGE_IMPLICATION_COUNTERFACTUAL_UNVERIFIED")
            middle={"id":digest(middle),"input":middle,"gold":evaluate(middle),
                    "answer_kind":"evidence","family":"spiral-bridge:implies_math"}
            projection = "implication_counterfactual"
    else:
        truth = bool(rng.randrange(2))
        # A stand-alone finite-world query can be identical across distinct
        # numerical expressions. It therefore owns an *additional* partition
        # check, preventing projection alias leakage across source families.
        for _ in range(300):
            set_record = _set_record(expression, family, rng, truth)
            if split_of(set_record) == split:
                break
        else:
            raise ValueError("BRIDGE_SET_PARTITION_EXHAUSTED")
        middle = {"id": digest(set_record), "input": set_record,
                  "gold": finite.evaluate(set_record), "answer_kind": "evidence",
                  "family": f"spiral-set:{family}"}
        consequent = {"kind": "set", "record": set_record}
        composite = record(expression,left_candidate,"IFF",consequent)
        if not necessary_factors(composite):
            raise ValueError("BRIDGE_COMPOSITION_FACTOR_NOT_NECESSARY")
        projection = "logical_set"
    middle = dict(middle, answer_kind="evidence", course_meta=_meta(grade, concept, expression, family,
                                           "medium", tranche, "set_relation" if family in
                                           ("membership", "subset") else
                                           "implication_contrast" if family == "implies_math"
                                           else "math_equality"))
    last = {"id": digest(composite), "input": composite, "gold": evaluate(composite),
            "answer_kind": "evidence", "family": f"spiral-bridge:{family}",
            "course_meta": _meta(grade, concept, expression, family, "hard", tranche, projection)}
    rows = [first, middle, last]
    validate_rows(rows, graph, partition=split)
    return rows


def validate_rows(rows, graph, *, partition=None):
    if not rows:
        raise ValueError("BRIDGE_EMPTY_ROWS")
    seen = set()
    for item in rows:
        if item["id"] in seen:
            raise ValueError("BRIDGE_DUPLICATE_ROWS")
        seen.add(item["id"])
        kind = item["answer_kind"]
        r = item["input"]
        if r.get("task") == VERSION:
            if kind != "evidence" or item["gold"] != evaluate(r):
                raise ValueError("BRIDGE_TARGET_MISMATCH")
            encoded = encode(r, graph)
            source = r["math_expression"]
        elif r.get("task") == arithmetic.VERSION:
            source = r["expression"]
            if kind == "numeric":
                if item["gold"] != value(source):
                    raise ValueError("BRIDGE_NUMBER_MISMATCH")
            elif kind == "evidence" and item["gold"] == ("TRUE" if arithmetic.evaluate(source) else "FALSE"):
                pass
            else:
                raise ValueError("BRIDGE_ARITHMETIC_TARGET_MISMATCH")
            encoded = arithmetic.encode(r, {t:i for i,t in enumerate(graph["tokens"])})
        else:
            if kind != "evidence":
                raise ValueError("BRIDGE_SET_OUTPUT_TYPE")
            lessons.valid_rows([item], graph)
            source = None
            encoded = lessons.encode(item, graph)
        if not encoded or len(encoded) > 96:
            raise ValueError("BRIDGE_ENCODING_INVALID")
        if item["gold"] not in STATES and type(item["gold"]) is not int:
            raise ValueError("BRIDGE_INVALID_GOLD")
        meta = item["course_meta"]
        if partition is not None and meta["split"] != partition:
            raise ValueError("BRIDGE_PARTITION_VIOLATION")
        if source is None and meta["split"] != split_of(r):
            raise ValueError("BRIDGE_SET_SOURCE_ALIAS_PARTITION_DRIFT")
        if source is not None and meta["split"] != split_of(source):
            # EQ wrappers in the middle project the *underlying* source AST.
            if not (kind == "evidence" and r.get("task") == arithmetic.VERSION
                    and source.get("name") == "EQ" and
                    split_of(source["args"][0]) == meta["split"]):
                raise ValueError("BRIDGE_SOURCE_PARTITION_DRIFT")
