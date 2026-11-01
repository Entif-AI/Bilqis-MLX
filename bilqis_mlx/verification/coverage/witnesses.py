"""Independent historical interpreter checks and witness accounting."""
from collections import defaultdict
from itertools import product
from ...errors import ErrorBus, SEMANTIC_COVERAGE
from ...semantic_sampling import missing_coverage_cases
from .contracts import SCHEMA, _digest

_UNRESOLVED_CONTRACT_PROOF_BLOCKED = "SEMANTIC_COVERAGE_UNRESOLVED_CONTRACT_PROOF_BLOCKED"


def _candidate_witness_obligations(plan, graph):
    if plan.get("schema") != SCHEMA:
        ErrorBus.Raise(
            SEMANTIC_COVERAGE.PLAN.VERSION_MISMATCH,
            actual_schema=plan.get("schema"),
            expected_schema=SCHEMA,
        )
    hard_unresolved = {
        "MISSING_ORACLE_OR_SOURCE_ANCHOR",
        "INVALID_SOURCE_SIGNATURE_OR_ARITY",
        "BOOLEAN_OUTPUT_WITHOUT_BINARY_ANSWER_CASTE",
    }
    if any(item.get("failure") in hard_unresolved
           for item in plan["unresolved"] if isinstance(item, dict)):
        raise ValueError(_UNRESOLVED_CONTRACT_PROOF_BLOCKED)
    unresolved_consumers = {
        item["capability"] for item in plan["unresolved"]
        if isinstance(item, dict) and isinstance(item.get("capability"), str)
    }
    if any(edge["consumer"] in unresolved_consumers
           for edge in plan["obligations"]
           if edge["status"] == "AWAITING_SOURCE_WITNESS"):
        raise ValueError(_UNRESOLVED_CONTRACT_PROOF_BLOCKED)
    candidates = {(e["consumer"], e["producer_root"], e["operand_slot"]): e
                  for e in plan["obligations"]
                  if e["status"] == "AWAITING_SOURCE_WITNESS"}
    for edge in candidates.values():
        for root, index in ((edge["consumer_root"], edge["consumer_token_id"]),
                            (edge["producer_root"], edge["producer_token_id"])):
            if not 0 <= index < len(graph["tokens"]) or graph["tokens"][index] != root:
                raise ValueError("SEMANTIC_COVERAGE_SOURCE_TOKEN_IDENTITY_DRIFT")
    return candidates


def _observe_witness_rows(rows, candidates, *, micro, graph, direct_oracle,
                          composed_oracle, operand_truth, B_GENERATOR, B_ORACLE):
    observed = defaultdict(list)
    seen = set()
    for row in rows:
        record = row["record"]
        identity = _digest(record)
        if (row["id"] != identity or row.get("source_id") != identity or
                identity in seen):
            raise ValueError("SEMANTIC_COVERAGE_WITNESS_IDENTITY_DRIFT")
        seen.add(identity)
        query = record["query"]
        if record.get("task") != "micro" or query.get("kind") != "apply":
            raise ValueError("SEMANTIC_COVERAGE_WITNESS_AST_UNSUPPORTED")
        if (row.get("root") != "cogal.operator." + query["operator"] or
                row.get("generator") != B_GENERATOR or
                row.get("oracle") != B_ORACLE or
                row.get("answer_kind") != "binary" or
                row.get("universe_size") != len(record["world"]["entities"])):
            raise ValueError("SEMANTIC_COVERAGE_WITNESS_SOURCE_CONTRACT_DRIFT")
        if (not 1 <= len(row["tokens"]) <= 96 or
                list(micro.encode(record)) != list(row["tokens"]) or
                min(row["tokens"]) < 0 or max(row["tokens"]) >= len(graph["tokens"])):
            raise ValueError("SEMANTIC_COVERAGE_WITNESS_TOKEN_DRIFT")
        gold = micro.evaluate(record)
        if (gold != row["gold"] or gold != micro.independent_evaluate(record)
                or gold != composed_oracle(record, row["capability"])):
            raise ValueError("SEMANTIC_COVERAGE_COMPOSED_ORACLE_DRIFT")
        for slot, operand in enumerate(query["args"]):
            if operand.get("kind") == "compare":
                root = "micro.compare." + operand.get("operator", "")
            elif operand.get("kind") == "relation":
                root = "micro.relation." + operand.get("name", "")
            else:
                raise ValueError("SEMANTIC_COVERAGE_UNSUPPORTED_OPERAND_AST")
            key = (row["capability"], root, slot)
            if key not in candidates:
                raise ValueError("SEMANTIC_COVERAGE_WITNESS_WITHOUT_TYPED_OBLIGATION")
            edge = candidates[key]
            if edge["consumer_root"] != row["root"]:
                raise ValueError("SEMANTIC_COVERAGE_WITNESS_CONSUMER_CONTRACT_DRIFT")
            direct = micro.record(record["world"], operand)
            operand_gold = micro.evaluate(direct)
            if (operand_gold != micro.independent_evaluate(direct) or
                    operand_gold != direct_oracle(direct, edge["producer"]) or
                    operand_gold != ("TRUE" if operand_truth(record["world"], operand)
                                     else "FALSE") or
                    row["operand_truths"][slot] != (operand_gold == "TRUE")):
                raise ValueError("SEMANTIC_COVERAGE_OPERAND_ORACLE_DRIFT")
            observed[key].append((identity, operand_gold, gold))

    return observed, seen


def _complete_witness_obligations(plan, observed, *, micro):
    completed = []
    for edge in plan["obligations"]:
        key = (edge["consumer"], edge["producer_root"], edge["operand_slot"])
        witnesses = observed.get(key, ())
        expected = ()
        if witnesses:
            # The pinned original Boolean interpreter establishes reachable
            # cases through its independently implemented table and algebra.
            op = edge["consumer_root"].removeprefix("cogal.operator.")
            arity = 1 if op == "NOT" else 2
            def expected_gold(bits):
                original = micro.boolean
                expr = original.apply(op, *(original.literal(v) for v in bits))
                truth = original.evaluate(expr, {})
                if truth != original.independent_evaluate(expr, {}):
                    raise ValueError("SEMANTIC_COVERAGE_SOURCE_TRUTH_TABLE_DISAGREEMENT")
                return "TRUE" if truth else "FALSE"
            expected = tuple(sorted({
                ("TRUE" if bits[edge["operand_slot"]] else "FALSE",
                 expected_gold(bits))
                for bits in product((False, True), repeat=arity)}))
        observed_cases = tuple(sorted({(direct, composed) for _, direct, composed
                                       in witnesses}))
        missing_cases = missing_coverage_cases(expected, observed_cases)
        status = ("SOURCE_CONTRAST_COVERED" if witnesses and not missing_cases else
                  "SOURCE_CONTRAST_PARTIAL" if witnesses else edge["status"])
        completed.append({**edge, "status": status,
                          "coverage_debt": status != "SOURCE_CONTRAST_COVERED",
                          "expected_truth_pairs": expected,
                          "observed_truth_pairs": observed_cases,
                          "missing_truth_pairs": missing_cases,
                          "witness_ids": tuple(sorted({identity for identity, _, _ in witnesses})),
                          "training_authorized": False})
    return completed


def verify_micro_composition_witnesses(plan: dict, rows: tuple[dict, ...],
                                       *, micro, graph: dict) -> dict:
    """Independently check observed legacy micro ASTs, golds and constituents.

    This adapter is only for the existing source-pinned micro Boolean slice.
    Other AST dialects require a separately source-attested bridge/adapter.
    No synthetic witness silently discharges a declared coverage obligation.
    """
    from ...grade_a_oracle import evaluate as direct_oracle
    from ...grade_b_oracle import (VERSION as B_ORACLE, evaluate as composed_oracle,
                                 operand_truth)
    from ...live_grade_b import GENERATOR as B_GENERATOR

    candidates = _candidate_witness_obligations(plan, graph)
    observed, seen = _observe_witness_rows(
        rows, candidates, micro=micro, graph=graph, direct_oracle=direct_oracle,
        composed_oracle=composed_oracle, operand_truth=operand_truth,
        B_GENERATOR=B_GENERATOR, B_ORACLE=B_ORACLE)
    completed = _complete_witness_obligations(plan, observed, micro=micro)
    return {**plan, "obligations": tuple(completed),
            "source_witness_cohort_sha256": _digest(sorted(seen)),
            "training_authorized": False}
