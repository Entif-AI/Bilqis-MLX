"""Occurrence-aware frame-schema ast_identity with source-owned authority."""
from __future__ import annotations

from dataclasses import asdict
import json

from ..core import Apply, Expression, Literal, expression_digest
from .contracts import _fail, _digest
from .schema import SourceSpan
from .instances import AtomicFrame, occurrence_id


def ast_construct_id(expression: Expression) -> str:
    """Name native AST constructors without inventing a second expression tree."""
    if isinstance(expression, Literal):
        return "literal:" + expression.type_name
    if isinstance(expression, Apply):
        return "apply:" + expression.operator.symbol
    _fail("FRAME_NATIVE_AST_CONSTRUCT_INVALID")



def source_ast_construct_id(ast: object) -> str:
    if isinstance(ast, (Literal, Apply)):
        return ast_construct_id(ast)
    if isinstance(ast, dict):
        kind = ast.get("kind")
        if isinstance(kind, str) and kind:
            return "source:" + kind
        task = ast.get("task")
        if isinstance(task, str) and task:
            return "source-task:" + task
    _fail("FRAME_SOURCE_AST_CONSTRUCT_INVALID")



def native_ast_content_digest(expression: Expression) -> str:
    """Reuse the existing semantic AST's canonical content identity."""
    return expression_digest(expression)



def _source_payload(ast: object) -> object:
    if isinstance(ast, (Literal, Apply)):
        return {"native_expression": asdict(ast)}
    if isinstance(ast, (dict, list, str, int, float, bool)) or ast is None:
        return ast
    _fail("FRAME_ATOMIC_SOURCE_UNSERIALIZABLE")



def atomic_fallback(
    ast: object,
    *,
    source_instance_id: str,
    structural_path: tuple[int, ...],
    source_span: SourceSpan,
    parent_occurrence_id: str | None,
    causal_prefix_end: int,
) -> AtomicFrame:
    payload = _source_payload(ast)
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False)
    construct = source_ast_construct_id(ast)
    return AtomicFrame(
        occurrence_id=occurrence_id(source_instance_id, structural_path),
        content_digest=_digest({
            "ast_construct": construct,
            "source_payload": json.loads(canonical),
        }),
        source_instance_id=source_instance_id,
        structural_path=structural_path,
        source_span=source_span,
        parent_occurrence_id=parent_occurrence_id,
        ast_construct=construct,
        source_payload=canonical,
        causal_prefix_end=causal_prefix_end,
    )
