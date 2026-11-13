"""Typed semantic error contracts."""
from __future__ import annotations

from .base import _spec

class SEMANTIC_COVERAGE:
    class PLAN:
        VERSION_MISMATCH = _spec(
            ("SEMANTIC_COVERAGE", "PLAN", "VERSION_MISMATCH"),
            owner="semantic_coverage",
            title="Semantic coverage plan schema does not match the active reader",
            message_template=(
                "Coverage plan schema {actual_schema!r} does not match "
                "{expected_schema!r}."),
            disposition="PRESERVE_AND_MIGRATE",
            next_action=(
                "Load or regenerate the plan with its schema-owned reader. "
                "Do not overwrite the schema field or historical receipts."),
            self_heal_owner="semantic_coverage.plan_reader",
            legacy_codes=("SEMANTIC_COVERAGE_PLAN_VERSION_MISMATCH",),
        )

    class AUDIT:
        INVALID_BUDGET = _spec(
            ("SEMANTIC_COVERAGE", "AUDIT", "INVALID_BUDGET"),
            owner="semantic_coverage",
            title="Semantic coverage audit budget violates sampling policy",
            message_template=(
                "Audit budget rounds={max_rounds}, samples_per_capability={each} "
                "does not satisfy {policy}."),
            disposition="CORRECT_INPUT_OR_STATE",
            next_action=(
                "Use a bounded positive round count and a counterbalanced even "
                "sample size large enough to exercise both truth classes."),
            operator_steps=(
                "Choose rounds within the named audit-round policy.",
                "Choose an even sample size at or above the named contrast minimum.",
            ),
            legacy_codes=("SEMANTIC_COVERAGE_INVALID_AUDIT_BUDGET",),
        )


class SEMANTIC_FRAME:
    class BINDING:
        INVALID = _spec(
            ("SEMANTIC_FRAME", "BINDING", "INVALID"),
            owner="semantics.frame_schema",
            title="Semantic frame binding violates the released schema",
            message_template=(
                "Frame binding failed for role {role_id!r} at source span "
                "[{span_start}, {span_end}]: {reason}."),
            disposition="CORRECT_INPUT_OR_STATE",
            next_action=(
                "Preserve the source row and semantic release; correct the role, "
                "type, scope, release, occurrence, or causal-prefix binding."),
        )

    class ADAPTER:
        INVALID_SOURCE = _spec(
            ("SEMANTIC_FRAME", "ADAPTER", "INVALID_SOURCE"),
            owner="semantics.frame_adapters",
            title="Semantic frame adapter cannot bind the source row",
            message_template=(
                "Frame adapter {adapter_id!r} rejected role {role_id!r} at source "
                "span [{span_start}, {span_end}]: {reason}."),
            disposition="CORRECT_INPUT_OR_STATE",
            next_action=(
                "Preserve the source row and use the released source adapter and "
                "frame schema that own this source dialect."),
        )

    class CODEC:
        INVALID = _spec(
            ("SEMANTIC_FRAME", "CODEC", "INVALID"),
            owner="semantics.frame_codec",
            title="Semantic frame codec input violates the released codec contract",
            message_template="Frame codec rejected the value: {reason}.",
            disposition="CORRECT_INPUT_OR_STATE",
            next_action=(
                "Preserve the frame sidecar and semantic release; correct the "
                "index, schema tag, codec version, presence mask, or release-local "
                "schema map before retrying."),
        )
