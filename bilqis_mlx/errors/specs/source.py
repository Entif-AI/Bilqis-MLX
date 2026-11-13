"""Typed source error contracts."""
from __future__ import annotations

from .base import _spec

class SOURCE:
    class BAMF_C13_EPISODE:
        INVALID = _spec(
            ("SOURCE", "BAMF_C13_EPISODE", "INVALID"),
            owner="source_adapters.c13_episode",
            title="C13 episode source contract invalid",
            message_template="C13 episode source contract invalid: {reason}",
            disposition="CORRECT_INPUT_OR_STATE",
            next_action=(
                "Restore the admitted C13 episode source, profile, canonical graph, "
                "and source-visible episode facts before retrying."),
        )

    class BAMF_WORLD:
        INVALID = _spec(
            ("SOURCE", "BAMF_WORLD", "INVALID"),
            owner="source_adapters.world_rules",
            title="Qualified world source contract invalid",
            message_template="Qualified world source contract invalid: {reason}",
            disposition="CORRECT_INPUT_OR_STATE",
            next_action=(
                "Restore the pinned source rows, canonical provider, and exact "
                "world query contract before retrying."),
        )

    from .source_grade_a import GRADE_A as GRADE_A
    from .source_boolean import BOOLEAN as BOOLEAN
    from .source_replay import REPLAY as REPLAY
    from .source_sampling import SAMPLING as SAMPLING
