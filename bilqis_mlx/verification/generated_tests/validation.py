"""Source-oracle verification of generated evaluation cases."""
from __future__ import annotations
from bilqis_mlx.integer_curriculum import (IntegerScope, _partition,
                                 generate_integer_curriculum)
from bilqis_mlx.pedagogical_parity import _source_stack, build_plan
from pathlib import Path
import hashlib
import json
from .contracts import select_families
from .storage import _read_release
from .publication import status


def _validate_case(case: dict, arithmetic, graph, scope, family):
    if family == "boolean.constants":
        if case["expected"] not in (True, False) or case["law"] != "boolean_constant":
            raise ValueError("SEMANTIC_TEST_INTEGRITY_BOOLEAN_GOLD")
        return
    record = case["record"]
    expression = record["expression"]
    arithmetic.verify(expression)
    value = arithmetic.evaluate(expression)
    law = case["law"]
    # The integer cap constrains every operand as well as the answer.
    def assert_integer_atoms(node):
        if node["kind"] == "number":
            if (type(node["value"]) is not int or
                    not 0 <= node["value"] <= scope.maximum):
                raise ValueError("SEMANTIC_TEST_INTEGRITY_INTEGER_INPUT_BOUNDS")
        else:
            for child in node["args"]:
                assert_integer_atoms(child)
    assert_integer_atoms(expression)
    base = (record if law == "typed_direct_number" else
            {"task":record["task"],"expression":expression["args"][0]})
    # Source ownership is stable over seeds and independent of test bounds.
    source_digest = hashlib.sha256(json.dumps(base,sort_keys=True,
                separators=(",", ":")).encode()).hexdigest()
    if case["source_id"] != source_digest:
        raise ValueError("SEMANTIC_TEST_INTEGRITY_SOURCE_IDENTITY_DRIFT")
    if law == "typed_direct_number":
        expect = case["native_output"]
        vocabulary = {v:i for i,v in enumerate(graph["tokens"])}
        if (type(value) is not int or value != case["expected"] or
                not 0 <= value <= scope.maximum or
                expect != {"identity":"school.number."+str(value),
                           "token_id":vocabulary["school.number."+str(value)]}):
            raise ValueError("SEMANTIC_TEST_INTEGRITY_INTEGER_GOLD")
    elif law == "typed_equality_truth":
        if type(value) is not bool or value != case["expected"]:
            raise ValueError("SEMANTIC_TEST_INTEGRITY_TRUTH_GOLD")
    elif law == "equality_symmetric":
        alternative = case["comparison"]["expression"]
        arithmetic.verify(alternative)
        if (expression["name"] != "EQ" or
                alternative["args"] != list(reversed(expression["args"])) or
                type(value) is not bool or
                arithmetic.evaluate(alternative) != value or value != case["expected"]):
            raise ValueError("SEMANTIC_TEST_INTEGRITY_EQUIVALENCE_LAW")
    elif law == "boolean_double_negation":
        if (type(value) is not bool or case["expected"] != value or
                case["negated"] != (not value) or
                case["double_negated"] != value or
                case["neural_codec_admitted"] is not False):
            raise ValueError("SEMANTIC_TEST_INTEGRITY_NEGATION_LAW")
    else:
        raise ValueError("SEMANTIC_TEST_INTEGRITY_UNKNOWN_LAW")


def check_generated(parity: dict, legacy_root: Path, folder: Path, *,
                    selector="generated") -> bool:
    manifest, suites = _read_release(Path(folder))
    if not manifest or not suites:
        raise ValueError("SEMANTIC_TEST_STALE_NO_GENERATED_TESTS")
    if selector != "generated":
        required = select_families(selector)
        if set(required) - set(suites):
            raise ValueError("SEMANTIC_TEST_STALE_MISSING_REQUIRED_FAMILIES")
    else:
        required = tuple(suites)
    state = status(parity, folder, selector=selector if selector != "generated" else "all")
    if any(family in state["stale"] for family in required):
        raise ValueError("SEMANTIC_TEST_STALE_REGENERATE_REQUIRED:" + ",".join(state["stale"]))
    _, arithmetic, _, _, graph, provenance = _source_stack(legacy_root)
    if provenance != parity["source_sha256"]:
        raise ValueError("SEMANTIC_TEST_INTEGRITY_SOURCE_DRIFT")
    scope = IntegerScope.from_environment(parity)
    seen = {}
    for family, suite in suites.items():
        for case in suite["cases"]:
            if case["partition"] not in ("development", "sealed_proposed"):
                raise ValueError("SEMANTIC_TEST_INTEGRITY_NON_EVALUATION_PARTITION")
            partition = ("sealed" if case["partition"] == "sealed_proposed" else
                         case["partition"])
            if (family != "boolean.constants" and
                    _partition(case["source_id"]) != partition):
                raise ValueError("SEMANTIC_TEST_INTEGRITY_SOURCE_PARTITION_DRIFT")
            if (case["source_id"] in seen and seen[case["source_id"]] != partition):
                raise ValueError("SEMANTIC_TEST_INTEGRITY_SOURCE_LEAK")
            seen[case["source_id"]] = partition
            _validate_case(case, arithmetic, graph, scope, family)
    return True
