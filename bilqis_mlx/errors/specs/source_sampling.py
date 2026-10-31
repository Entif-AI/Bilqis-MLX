"""Typed source sampling error contracts."""
from __future__ import annotations

from .base import _spec

class SAMPLING:
    BALANCED_BINARY_COUNT_INVALID = _spec(
        ("SOURCE", "SAMPLING", "BALANCED_BINARY_COUNT_INVALID"),
        owner="semantic_sampling",
        title="Balanced binary sample count is invalid",
        message_template=(
            "Sample count {sample_count} violates {policy_name}: minimum "
            "{minimum_samples}, balance period {balance_period}."),
        disposition="CORRECT_INPUT_OR_STATE",
        next_action=(
            "Use the shared balanced-binary sampling policy rather than "
            "hand-selecting a count at the caller."),
        legacy_codes=(
            "GRADE_B_BALANCED_EVEN_SAMPLE_REQUIRED",
            "LIVE_GRADE_A_INVALID_DRAW",
        ),
    )
