"""Production answer-modality registry, independent of grade/release identity."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..curriculum import BINARY, BOOLEAN_OPERATORS, INT_0_3
from .answers import (
    AnswerModality,
    AnswerModalityRegistry,
    RegisteredAnswerModality,
    fixed_domain,
    merge_prefix_domain,
)


def _implementation_sha256(kind: str) -> str:
    root = Path(__file__).resolve().parent
    material = {
        "kind": kind,
        "registry": hashlib.sha256(
            (root / "live_answers.py").read_bytes()).hexdigest(),
        "framework": hashlib.sha256(
            (root / "answers.py").read_bytes()).hexdigest(),
    }
    return hashlib.sha256(json.dumps(
        material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _number_identity(value: str) -> str:
    return "school.number." + value


def _binary_identity(value: str) -> str:
    return {
        "FALSE": "cogal.value.false",
        "TRUE": "cogal.value.true",
    }[value]


def _boolean_operator_identity(value: str) -> str:
    return "cogal.operator." + value


def live_answer_registry() -> AnswerModalityRegistry:
    """Return the production answer extension boundary for current semantics."""
    return AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality(
                "binary", "answer.binary/v1",
                _implementation_sha256("binary")),
            fixed_domain(BINARY),
            _binary_identity),
        RegisteredAnswerModality(
            AnswerModality(
                "integer_0_3", "answer.integer-0-3/v1",
                _implementation_sha256("integer_0_3")),
            fixed_domain(INT_0_3),
            _number_identity),
        RegisteredAnswerModality(
            AnswerModality(
                "numeric_active", "answer.numeric-active/v1",
                _implementation_sha256("numeric_active")),
            merge_prefix_domain,
            _number_identity),
        RegisteredAnswerModality(
            AnswerModality(
                "boolean_operator", "answer.boolean-operator/v1",
                _implementation_sha256("boolean_operator")),
            fixed_domain(BOOLEAN_OPERATORS),
            _boolean_operator_identity),
    ))
