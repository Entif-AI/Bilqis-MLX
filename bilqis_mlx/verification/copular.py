"""Independent serialized-record oracle, without AST/generator interpretation."""
from __future__ import annotations


VERSION = "bilqis.ithkuil-reference-identity-oracle/v1"


def independent_answer(record: dict) -> str:
    if (not isinstance(record, dict) or
            set(record) != {"task", "entities", "denotations", "query"} or
            record["task"] != "bilqis.ithkuil-reference-identity/v1"):
        raise ValueError("COPULAR_ORACLE_INVALID_RECORD")
    entities, pairs, query = record["entities"], record["denotations"], record["query"]
    if (not isinstance(entities, list) or not 2 <= len(entities) <= 5 or
            any(type(e) is not str or e not in ("A", "B", "C", "D", "E") for e in entities) or
            len(set(entities)) != len(entities) or not isinstance(pairs, list) or
            len(pairs) != len(entities) or
            any(not isinstance(p, list) or len(p) != 2 or
                any(type(v) is not str or v not in entities for v in p) for p in pairs) or
            sorted(p[0] for p in pairs) != sorted(entities)):
        raise ValueError("COPULAR_ORACLE_INVALID_DENOTATIONS")
    if (not isinstance(query, dict) or set(query) != {"operator", "arguments"} or
            query["operator"] != "ithkuil.op.COPULAR_IDENTITY" or
            not isinstance(query["arguments"], list) or len(query["arguments"]) != 2 or
            any(type(arg) is not str or arg not in entities for arg in query["arguments"])):
        raise ValueError("COPULAR_ORACLE_UNSUPPORTED_QUERY")
    # Compare the two literal source facts; no generator or AST evaluation call.
    left = next(p[1] for p in pairs if p[0] == query["arguments"][0])
    right = next(p[1] for p in pairs if p[0] == query["arguments"][1])
    return "TRUE" if left == right else "FALSE"
