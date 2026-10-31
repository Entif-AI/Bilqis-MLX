"""Typed candidate discovery without semantic or instructional admission."""
import re
from ...curriculum_compiler import CurriculumAST
from ...registry_ast import RegistryAST
from .contracts import SCHEMA

_TYPE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")

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


def _typed_capabilities(ast, registry):
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

    return indexed, typed, unresolved, unverifiable


def discover_composition_obligations(ast: CurriculumAST,
                                     registry: RegistryAST) -> dict:
    """Discover candidate edges from source-typed input/output contracts.

    Each operand position is a distinct obligation. This also surfaces edges
    absent from hand-authored prerequisite lists. Type compatibility is a
    *candidate*, never an assertion of grammar legality or instructional need.
    """
    indexed, typed, unresolved, unverifiable = _typed_capabilities(ast, registry)

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
