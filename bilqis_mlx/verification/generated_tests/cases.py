"""Source-case construction for proposed generated tests."""
from __future__ import annotations
from .contracts import Family, SCHEMA, _dependency_state, _object_hash


def _case(source_id, partition, law, expected, **details):
    if partition == "train":
        raise ValueError("SEMANTIC_TEST_LEAKED_TRAINING_SOURCE")
    name = "sealed_proposed" if partition == "sealed" else partition
    return {"id": _object_hash([law, source_id, details]),
            "source_id": source_id, "partition": name,
            "law": law, "expected": expected, **details}


def _generated_cases(family: Family, sampled: dict, arithmetic,
                     source_graph: dict) -> list[dict]:
    cases = []
    if family.name == "boolean.constants":
        for value in (False, True):
            cases.append({"id": _object_hash(["Boolean", value]),
                          "source_id": _object_hash(["Boolean", value]),
                          "partition": "development", "law": "boolean_constant",
                          "expected": value, "type": "Boolean"})
        return cases
    not_node = next((node for node in source_graph["nodes"]
                     if node["id"] == "cogal.operator.NOT"), None)
    if (family.name == "integer.inverse_negation" and
            (not_node is None or not_node["signature"] != "Boolean->Boolean" or
             not_node["truth_signature"] != [False, True])):
        raise ValueError("SEMANTIC_TEST_NEGATION_TYPE_OR_TRUTH_TABLE_DRIFT")
    for source in sampled["rows"]:
        if source["partition"] == "train":
            continue
        ident = source["source_id"]
        split = source["partition"]
        direct, positive, negative = source["views"]
        value = source["value"]
        if family.name == "integer.direct":
            cases.append(_case(ident, split, "typed_direct_number", value,
                               record=direct["record"],
                               answer_kind=direct["answer_kind"],
                               native_output=direct["native_output"]))
        elif family.name == "integer.truth":
            for row in (positive, negative):
                cases.append(_case(ident, split, "typed_equality_truth",
                                   row["gold"] == "TRUE", record=row["record"],
                                   answer_kind="evidence"))
        elif family.name == "integer.equivalence":
            for row in (positive, negative):
                expression = row["record"]["expression"]
                swapped = arithmetic.operation("EQ", *reversed(expression["args"]))
                arithmetic.verify(swapped)
                cases.append(_case(ident, split, "equality_symmetric",
                                   row["gold"] == "TRUE",
                                   record=row["record"],
                                   comparison={"task":arithmetic.VERSION,
                                               "expression":swapped}))
        elif family.name == "integer.inverse_negation":
            for row in (positive, negative):
                original = row["gold"] == "TRUE"
                cases.append(_case(ident, split, "boolean_double_negation",
                                   original, record=row["record"],
                                   negated=not original,
                                   double_negated=not(not original),
                                   neural_codec_admitted=False))
        else:
            raise ValueError("SEMANTIC_TEST_MISSING_GENERATOR:" + family.name)
    if not cases:
        raise ValueError("SEMANTIC_TEST_NO_INDEPENDENT_EVALUATION_SOURCES:" + family.name)
    return cases


def _suite(family: Family, sampled, arithmetic, graph, scope, parity,
           seed: int, count: int):
    return {"schema": SCHEMA, "family": family.name,
            "dependencies": list(family.dependencies),
            "dependency_state": _dependency_state(family, scope, parity),
            "seed": seed, "sample_count": count,
            "status": "PROPOSED_GENERATED_TESTS_NOT_GRADE_QUALIFICATION",
            "cases": _generated_cases(family, sampled, arithmetic, graph)}
