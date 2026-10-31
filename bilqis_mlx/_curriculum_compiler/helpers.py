"""Typed curriculum compiler helper operations."""
from __future__ import annotations
import hashlib
import random
from bilqis_mlx.semantics.core import Apply, Expression, Operation
from bilqis_mlx.curriculum_compiler import CapabilityNode

def _coverage_debt(code: str, *parts: str) -> ValueError:
    return ValueError("CURRICULUM_GENERIC_COVERAGE_DEBT:" + code + ":" + ":".join(parts))

def _seeded_rng(seed: int, node_id: str, split: str, ordinal: int) -> random.Random:
    material = f"{seed}:{node_id}:{split}:{ordinal}".encode()
    return random.Random(int(hashlib.sha256(material).hexdigest()[:16], 16))

def _operations(expression: Expression) -> tuple[Operation, ...]:
    if not isinstance(expression, Apply):
        return ()
    return (expression.operator, *(
        operation for argument in expression.arguments for operation in _operations(argument)))

def _validate_answer_type(node: CapabilityNode, expression: Expression) -> None:
    supported = {"binary": "Boolean"}
    if not node.answers or any(answer not in supported for answer in node.answers):
        raise _coverage_debt("UNSUPPORTED_ANSWER_TYPE", node.id)
    if expression.type_name not in {supported[answer] for answer in node.answers}:
        raise _coverage_debt("SOURCE_OUTPUT_ANSWER_TYPE_MISMATCH", node.id)
