"""Neural-inert, source-bound typed composition discovery and witness accounting.

The approved Course and versioned Token Atlas supply candidate semantics.
Source interpreters, not matching answer types, decide whether a particular
construction actually works. No result of this module admits lessons or changes
the live model, its teacher, or historical grade release definitions.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from itertools import product
import json
import re

from .curriculum_compiler import CurriculumAST
from .registry_ast import RegistryAST


SCHEMA = "bilqis.mlx.semantic-composition-coverage/v1"
_TYPE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def _signature(value: str) -> tuple[tuple[str, ...], str]:
    """Read formal Token Atlas signatures without guessing an unknown grammar."""
    parts = value.split("->")
    if len(parts) != 2 or not _TYPE.fullmatch(parts[1]):
        raise ValueError("SEMANTIC_COVERAGE_UNSUPPORTED_SIGNATURE:" + value)
    args = tuple(parts[0].split("*"))
    if not args or any(not _TYPE.fullmatch(arg) for arg in args):
        raise ValueError("SEMANTIC_COVERAGE_UNSUPPORTED_SIGNATURE:" + value)
    return args, parts[1]


def _source_dialect(source: str) -> str | None:
    if not source.startswith("repo:") or "::" not in source:
        return None
    return source.split("::", 1)[0]


def discover_composition_obligations(ast: CurriculumAST,
                                     registry: RegistryAST) -> dict:
    """Discover candidate edges from source-typed input/output contracts.

    Each operand position is a distinct obligation. This also surfaces edges
    absent from hand-authored prerequisite lists. Type compatibility is a
    *candidate*, never an assertion of grammar legality or instructional need.
    """
    indexed = {node.id: node for node in ast.nodes}
    if len(indexed) != len(ast.nodes):
        raise ValueError("SEMANTIC_COVERAGE_DUPLICATE_CAPABILITY")
    token_by_symbol = {token.symbol: token for token in registry.tokens}
    typed = {}
    unresolved = []
    unverifiable = set()
    for node in ast.nodes:
        if len(node.roots) != 1 or node.roots[0] not in token_by_symbol:
            unresolved.append({"capability": node.id,
                               "failure": "MISSING_UNIQUE_TYPED_SOURCE_ROOT"})
            continue
        token = token_by_symbol[node.roots[0]]
        try:
            operands, result = _signature(token.signature)
            if int(token.arity) != len(operands):
                raise ValueError("SEMANTIC_COVERAGE_ARITY_CONFLICT")
        except (ValueError, TypeError):
            unresolved.append({"capability": node.id,
                               "failure": "INVALID_SOURCE_SIGNATURE_OR_ARITY"})
            continue
        if not node.oracle or not node.source:
            unresolved.append({"capability": node.id,
                               "failure": "MISSING_ORACLE_OR_SOURCE_ANCHOR"})
            unverifiable.add(node.id)
        if result == "Boolean" and "binary" not in node.answers:
            unresolved.append({"capability": node.id,
                               "failure": "BOOLEAN_OUTPUT_WITHOUT_BINARY_ANSWER_CASTE"})
            unverifiable.add(node.id)
        typed[node.id] = (token, operands, result)

    obligations = []
    for consumer in ast.nodes:
        if consumer.id not in typed:
            continue
        consumer_token, inputs, _ = typed[consumer.id]
        declared = set(consumer.requires) | set(consumer.composed_of)
        accounted = set()
        for producer in ast.nodes:
            if producer.grade >= consumer.grade or producer.id not in typed:
                continue
            producer_token, _, output = typed[producer.id]
            for slot, expected in enumerate(inputs):
                if expected != output:
                    continue
                accounted.add(producer.id)
                same_dialect = bool(_source_dialect(consumer.source) and
                                    _source_dialect(consumer.source) ==
                                    _source_dialect(producer.source))
                obligations.append({
                    "consumer": consumer.id, "producer": producer.id,
                    "operand_slot": slot, "operand_type": expected,
                    "declared_prerequisite": producer.id in declared,
                    "consumer_root": consumer_token.symbol,
                    "producer_root": producer_token.symbol,
                    "consumer_token_id": consumer_token.id,
                    "producer_token_id": producer_token.id,
                    "consumer_contract_sha256": consumer_token.contract_sha256,
                    "producer_contract_sha256": producer_token.contract_sha256,
                    "status": ("CAPABILITY_CONTRACT_UNVERIFIED"
                               if consumer.id in unverifiable or producer.id in unverifiable
                               else "AWAITING_SOURCE_WITNESS" if same_dialect
                               else "CROSS_SOURCE_AST_BRIDGE_UNVERIFIED"),
                    "coverage_debt": True, "witness_ids": (),
                    "training_authorized": False,
                })
        for prerequisite in sorted(declared - accounted):
            unresolved.append({"capability": consumer.id,
                               "prerequisite": prerequisite,
                               "failure": "DECLARED_PREREQUISITE_HAS_NO_TYPED_COMPOSITION"})

    return {"schema": SCHEMA, "ast_sha256": ast.digest(),
            "registry_sha256": registry.source_sha256,
            "capabilities": tuple(sorted(indexed)),
            "obligations": tuple(sorted(obligations,
                key=lambda r: (r["consumer"], r["producer"], r["operand_slot"]))),
            "unresolved": tuple(sorted(unresolved,
                key=lambda r: (r["capability"], r["failure"],
                               r.get("prerequisite", "")))),
            "training_authorized": False}


def verify_micro_composition_witnesses(plan: dict, rows: tuple[dict, ...],
                                       *, micro, graph: dict) -> dict:
    """Independently check observed legacy micro ASTs, golds and constituents.

    This adapter is only for the existing source-pinned micro Boolean slice.
    Other AST dialects require a separately source-attested bridge/adapter.
    No synthetic witness silently discharges a declared coverage obligation.
    """
    from .grade_a_oracle import evaluate as direct_oracle
    from .grade_b_oracle import (VERSION as B_ORACLE, evaluate as composed_oracle,
                                 operand_truth)
    from .live_grade_b import GENERATOR as B_GENERATOR

    if plan.get("schema") != SCHEMA:
        raise ValueError("SEMANTIC_COVERAGE_PLAN_VERSION_MISMATCH")
    if plan["unresolved"]:
        raise ValueError("SEMANTIC_COVERAGE_UNRESOLVED_CONTRACT_PROOF_BLOCKED")
    candidates = {(e["consumer"], e["producer_root"], e["operand_slot"]): e
                  for e in plan["obligations"]
                  if e["status"] == "AWAITING_SOURCE_WITNESS"}
    for edge in candidates.values():
        for root, index in ((edge["consumer_root"], edge["consumer_token_id"]),
                            (edge["producer_root"], edge["producer_token_id"])):
            if not 0 <= index < len(graph["tokens"]) or graph["tokens"][index] != root:
                raise ValueError("SEMANTIC_COVERAGE_SOURCE_TOKEN_IDENTITY_DRIFT")
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
        missing_cases = tuple(case for case in expected if case not in observed_cases)
        status = ("SOURCE_CONTRAST_COVERED" if witnesses and not missing_cases else
                  "SOURCE_CONTRAST_PARTIAL" if witnesses else edge["status"])
        completed.append({**edge, "status": status,
                          "coverage_debt": status != "SOURCE_CONTRAST_COVERED",
                          "expected_truth_pairs": expected,
                          "observed_truth_pairs": observed_cases,
                          "missing_truth_pairs": missing_cases,
                          "witness_ids": tuple(sorted({identity for identity, _, _ in witnesses})),
                          "training_authorized": False})
    return {**plan, "obligations": tuple(completed),
            "source_witness_cohort_sha256": _digest(sorted(seen)),
            "training_authorized": False}


def audit_pinned_micro_generator(plan: dict, source_root, *,
                                 seed: int = 2026101601, max_rounds: int = 4,
                                 each: int = 12) -> dict:
    """Exercise the existing B constructor until proof or bounded coverage debt.

    The adapter reuses the pinned original source interpreter and independent
    oracle. It records *generated* exposure, not lessons delivered to a model.
    """
    from .grade_a_probe import read_sources
    from .live_grade_b import draw_connectives, constructor_digest

    if not 1 <= max_rounds <= 32 or each < 4 or each % 2:
        raise ValueError("SEMANTIC_COVERAGE_INVALID_AUDIT_BUDGET")
    micro, _, graph, source_hashes, source_graph_sha = read_sources(source_root)
    collected = {}
    report = plan
    rounds = 0
    for index in range(max_rounds):
        sample = draw_connectives(source_root, graph, seed=seed + index, each=each)
        collected.update((row["id"], row) for row in sample)
        report = verify_micro_composition_witnesses(
            plan, tuple(collected.values()), micro=micro, graph=graph)
        rounds += 1
        if all(edge["status"] == "SOURCE_CONTRAST_COVERED"
               for edge in report["obligations"]
               if edge["consumer_root"].startswith("cogal.operator.") and
                  edge["status"] in ("SOURCE_CONTRAST_COVERED",
                                     "SOURCE_CONTRAST_PARTIAL",
                                     "AWAITING_SOURCE_WITNESS")):
            break
    return {**report,
            "source_sha256_by_file": source_hashes,
            "source_graph_sha256": source_graph_sha,
            "generator_code_sha256": constructor_digest(),
            "first_seed": seed, "rounds_used": rounds,
            "constructed_record_count": len(collected),
            "student_exposure_measured": False,
            "training_authorized": False}


def affected_typed_dependency_closure(plan: dict, changed: tuple[str, ...]) -> tuple[str, ...]:
    """Regenerate descendants of newly *discovered* as well as declared edges."""
    if plan.get("schema") != SCHEMA:
        raise ValueError("SEMANTIC_COVERAGE_PLAN_VERSION_MISMATCH")
    reverse: dict[str, set[str]] = {}
    for edge in plan["obligations"]:
        reverse.setdefault(edge["producer"], set()).add(edge["consumer"])
        reverse.setdefault(edge["consumer"], set())
    known = set(reverse) | set(plan.get("capabilities", ()))
    if set(changed) - known:
        raise ValueError("SEMANTIC_COVERAGE_UNKNOWN_CHANGED_CAPABILITY")
    impacted = set(changed)
    pending = list(changed)
    while pending:
        for dependent in reverse.get(pending.pop(), ()):
            if dependent not in impacted:
                impacted.add(dependent)
                pending.append(dependent)
    return tuple(sorted(impacted))


def main(argv=None) -> int:
    """Read-only coverage audit of the currently admitted A+B source slice."""
    import argparse
    from collections import Counter
    from pathlib import Path
    from .curriculum_compiler import compile_ast
    from .grade_a_release import accepted_grade_a
    from .live_grade_b import live_course
    from .registry_ast import load_registry

    parser = argparse.ArgumentParser(description=__doc__)
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--legacy-code-root", type=Path,
                        default=project / "vendor" / "legacy-v16")
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2026101601)
    parser.add_argument("--each", type=int, default=12)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args(argv)
    manifest = json.loads((project / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
    approved = live_course(accepted_grade_a(manifest), args.legacy_code_root)
    ast = compile_ast(approved)
    registry = load_registry(project / "docs/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json")
    plan = discover_composition_obligations(ast, registry)
    verified = audit_pinned_micro_generator(
        plan, args.legacy_code_root, seed=args.seed,
        max_rounds=args.max_rounds, each=args.each)
    counts = Counter(e["status"] for e in verified["obligations"])
    result = {
        "schema": verified["schema"],
        "ast_sha256": verified["ast_sha256"],
        "registry_sha256": verified["registry_sha256"],
        "source_graph_sha256": verified["source_graph_sha256"],
        "generator_code_sha256": verified["generator_code_sha256"],
        "generated_record_count": verified["constructed_record_count"],
        "generated_rounds": verified["rounds_used"],
        "source_witness_cohort_sha256": verified["source_witness_cohort_sha256"],
        "candidate_operand_slot_count": len(verified["obligations"]),
        "undeclared_compatible_families": sorted({e["producer"] for e in
              verified["obligations"] if not e["declared_prerequisite"]}),
        "coverage_by_status": dict(sorted(counts.items())),
        "unresolved_registry_contracts": verified["unresolved"],
        "student_exposure_measured": False,
        "training_authorized": False,
    }
    if args.details:
        result["obligations"] = verified["obligations"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
