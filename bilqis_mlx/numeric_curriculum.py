"""Source-checked construction views for finite numeric lesson contracts.

The original lesson identity and dependencies bind the plan. Expressions use
the shared typed AST; direct and contrast views share one independent gold.
"""
from __future__ import annotations

from dataclasses import dataclass
import random

from .generated_assessment import digest
from .semantics.foundation.core import Literal
from .semantics.foundation.numeric import calculate, evaluate, number, number_set
from .source_adapters.numeric import DIALECT, encode
from .verification.numeric import independent_value
from .semantics.foundation.abi import HISTORICAL_ABI, fingerprint_graph_prefix
from .semantics.foundation.numeric import CONTRACT

GENERATOR = "bilqis.finite-numeric-constructions/v1"
ORACLE = "bilqis.independent-finite-numeric/v1"


@dataclass(frozen=True)
class NumericLesson:
    capability: str
    lesson_id: str
    operation: str
    prerequisites: tuple[str, ...]


def _finite_set(rng, count, maximum, *, members=None):
    values = list(range(count)) if members is None else list(members)
    rng.shuffle(values)
    return number_set(tuple(values))


def _expression(plan, rng, index, maximum):
    n = index % (maximum+1)
    if plan.operation == "NUMBER":
        return number(n), {"ordinal_members": list(range(n))}
    if plan.operation == "COUNT":
        return calculate("COUNT", _finite_set(rng, n, maximum)), {"ordinal_members": list(range(n))}
    if plan.operation == "SUCC":
        n = index % maximum
        return calculate("SUCC", number(n)), {"before": list(range(n)), "after": list(range(n+1))}
    pairs = [(a, b) for a in range(maximum+1) for b in range(maximum+1)
             if ((plan.operation == "ADD" and a+b <= maximum) or
                 (plan.operation == "SUB" and a >= b) or
                 (plan.operation == "MUL" and a*b <= maximum) or
                 (plan.operation == "DIV" and b > 0 and a % b == 0))]
    rng.shuffle(pairs)
    # Cover genuine arithmetic before zero/identity boundaries can dominate.
    genuine = [(a,b) for a,b in pairs if a > 0 and b > 0 and
               (b > 1 and a//b > 1 if plan.operation == "DIV" else
                a > 1 and b > 1 if plan.operation == "MUL" else
                a > b if plan.operation == "SUB" else True)]
    boundaries = [(a,b) for a,b in pairs if a == 0 or b == 0]
    candidates = genuine if index % 3 != 2 and genuine else boundaries or pairs
    a, b = rng.choice(candidates)
    # Actual set witnesses remain in student inputs, not just in metadata.
    left_members = range(a)
    right_members = range(a, a+b) if plan.operation == "ADD" else range(b)
    left = calculate("COUNT", _finite_set(rng, a, maximum, members=left_members))
    right = calculate("COUNT", _finite_set(rng, b, maximum, members=right_members))
    if plan.operation == "ADD" and a+b > maximum:
        raise ValueError("NUMERIC_DISJOINT_GROUP_OUTSIDE_SCOPE")
    witness = {
        "left_members": list(left_members), "right_members": list(right_members),
        "relation": ("DISJOINT_COMBINATION" if plan.operation == "ADD" else
                     "SUBSET_REMOVAL" if plan.operation == "SUB" else
                     "EQUAL_GROUP_PRODUCT" if plan.operation == "MUL" else "EXACT_GROUP_PARTITION"),
    }
    if plan.operation in ("MUL", "DIV"):
        group_count = a if plan.operation == "MUL" else a//b
        witness["groups"] = [list(range(i*b, (i+1)*b)) for i in range(group_count)]
    return calculate(plan.operation, left, right), witness


def draw_numeric(plans: tuple[NumericLesson, ...], graph: dict, *, seed: int,
                 maximum: int, each: int, capability: str | None = None) -> tuple[dict, ...]:
    if (type(seed) is not int or type(maximum) is not int or not 1 <= maximum <= 100 or
            type(each) is not int or each < 3):
        raise ValueError("NUMERIC_CONSTRUCTION_SCOPE_INVALID")
    if fingerprint_graph_prefix(graph) != HISTORICAL_ABI.index_contract_sha256:
        raise ValueError("NUMERIC_HISTORICAL_TOKEN_ABI_DRIFT")
    for definition in CONTRACT["operators"]:
        index, symbol = definition["token_index"], definition["symbol"]
        if index >= len(graph["tokens"]) or graph["tokens"][index] != symbol:
            raise ValueError("NUMERIC_TOKEN_BINDING_DRIFT")
        node = graph["nodes"][index]
        if digest(node) != graph["row_contract_sha256"].get(symbol):
            raise ValueError("NUMERIC_SOURCE_NODE_CONTENT_DRIFT")
        declared = next((n for n in CONTRACT["append_only_nodes"] if n["id"] == symbol), None)
        if declared and any(node.get(key) != declared[key]
                            for key in ("id", "semantic_id", "signature", "arity", "meaning")):
            raise ValueError("NUMERIC_NEW_OPERATION_MEANING_DRIFT")
        if (node["signature"] != definition["signature"] or
                (symbol not in {n["id"] for n in CONTRACT["append_only_nodes"]} and
                 graph["row_contract_sha256"][symbol] != definition["contract_sha256"])):
            raise ValueError("NUMERIC_OPERATOR_CONTRACT_DRIFT")
    selected = tuple(p for p in plans if capability is None or p.capability == capability)
    if not selected:
        raise ValueError("NUMERIC_CONSTRUCTION_UNKNOWN_CAPABILITY")
    mapping = {symbol: index for index, symbol in enumerate(graph["tokens"])}
    rows = []
    for plan in selected:
        rng = random.Random(digest((GENERATOR, seed, plan.capability)))
        for index in range((each+2)//3):
            expression, witness = _expression(plan, rng, index, maximum)
            truth = evaluate(expression)
            if type(truth) is not int or truth != independent_value(expression) or not 0 <= truth <= maximum:
                raise ValueError("NUMERIC_CONSTRUCTION_ORACLE_DISAGREEMENT")
            source_id = digest((plan.lesson_id, encode(expression)))
            wrong = (truth+1) % (maximum+1)
            views = ((expression, str(truth), "numeric_active"),
                     (calculate("EQ", expression, number(truth)), "TRUE", "binary"),
                     (calculate("EQ", expression, number(wrong)), "FALSE", "binary"))
            for view, gold, kind in views:
                if sum(r["capability"] == plan.capability for r in rows) >= each:
                    break
                if evaluate(view) != independent_value(view):
                    raise ValueError("NUMERIC_CONTRAST_ORACLE_DISAGREEMENT")
                symbols = encode(view, groups=witness.get("groups"))
                if any(symbol not in mapping for symbol in symbols):
                    raise ValueError("NUMERIC_UNREGISTERED_TOKEN")
                record = {"task": DIALECT, "symbols": symbols}
                row = dict(id=digest((seed, plan.capability, index, kind, gold, record)),
                    source_id=source_id, capability=plan.capability, lesson_id=plan.lesson_id,
                    answer_kind=kind, gold=gold, record=record,
                    tokens=[mapping[symbol] for symbol in symbols],
                    witness=witness, oracle=ORACLE, generator=GENERATOR,
                    integer_max=maximum)
                if kind == "numeric_active":
                    row["native_output"] = {"identity": "school.number." + gold,
                                             "token_id": mapping["school.number."+gold]}
                rows.append(row)
    return tuple(rows)
