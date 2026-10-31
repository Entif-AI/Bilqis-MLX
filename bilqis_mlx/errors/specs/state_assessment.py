"""Typed state assessment error contracts."""
from __future__ import annotations

from .base import _spec

class StateAssessment:
    INVALID_INTRODUCTION_FRONTIER_HISTORY = _spec(
        ("SCHOOL", "STATE", "INVALID_INTRODUCTION_FRONTIER_HISTORY"), owner="curriculum.state",
        title='Invalid introduction frontier history', message_template='Invalid introduction frontier history',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the owning contract and inputs; preserve recorded state.",
        legacy_codes=('INVALID_INTRODUCTION_FRONTIER_HISTORY',),
    )

    INVALID_INTRODUCTION_STAGE = _spec(
        ("SCHOOL", "STATE", "INVALID_INTRODUCTION_STAGE"), owner="curriculum.state",
        title='Invalid introduction stage', message_template='Invalid introduction stage',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the owning contract and inputs; preserve recorded state.",
        legacy_codes=('INVALID_INTRODUCTION_STAGE',),
    )

    INVALID_MAIN_SWEEP_HISTORY = _spec(
        ("SCHOOL", "STATE", "INVALID_MAIN_SWEEP_HISTORY"), owner="curriculum.state",
        title='Invalid main sweep history', message_template='Invalid main sweep history',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the owning contract and inputs; preserve recorded state.",
        legacy_codes=('INVALID_MAIN_SWEEP_HISTORY',),
    )

    INVALID_PARTIAL_SCHOOL_COMPLETION = _spec(
        ("SCHOOL", "STATE", "INVALID_PARTIAL_SCHOOL_COMPLETION"), owner="curriculum.state",
        title='Invalid partial school completion', message_template='Invalid partial school completion',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the owning contract and inputs; preserve recorded state.",
        legacy_codes=('INVALID_PARTIAL_SCHOOL_COMPLETION',),
    )

    INVALID_SCHOOL_COUNTER = _spec(
        ("SCHOOL", "STATE", "INVALID_SCHOOL_COUNTER"), owner="curriculum.state",
        title='Invalid school counter', message_template='Invalid school counter',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the owning contract and inputs; preserve recorded state.",
        legacy_codes=('INVALID_SCHOOL_COUNTER',),
    )

    QUEUE_CAPABILITY_OUTSIDE_ACTIVE_AND_PASSED_GRADES = _spec(
        ("SCHOOL", "STATE", "QUEUE_CAPABILITY_OUTSIDE_ACTIVE_AND_PASSED_GRADES"), owner="curriculum.state",
        title='Queue capability outside active and passed grades', message_template='Queue capability outside active and passed grades',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the owning contract and inputs; preserve recorded state.",
        legacy_codes=('QUEUE_CAPABILITY_OUTSIDE_ACTIVE_AND_PASSED_GRADES',),
    )

    WEAKEST_THREE_INCOMPLETE_POOL = _spec(
        ("SCHOOL", "STATE", "WEAKEST_THREE_INCOMPLETE_POOL"), owner="curriculum.state",
        title='Weakest three incomplete pool', message_template='Weakest three incomplete pool',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the owning contract and inputs; preserve recorded state.",
        legacy_codes=('WEAKEST_THREE_INCOMPLETE_POOL',),
    )

    WHOLE_SCHOOL_CANNOT_COMPLETE_PARTIAL_COURSE = _spec(
        ("SCHOOL", "STATE", "WHOLE_SCHOOL_CANNOT_COMPLETE_PARTIAL_COURSE"), owner="curriculum.state",
        title='Whole school cannot complete partial course', message_template='Whole school cannot complete partial course',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the owning contract and inputs; preserve recorded state.",
        legacy_codes=('WHOLE_SCHOOL_CANNOT_COMPLETE_PARTIAL_COURSE',),
    )

    HISTORICAL_NOT_RESUMABLE = _spec(
        ("SCHOOL", "STATE", "HISTORICAL_NOT_RESUMABLE"),
        owner="runtime.session",
        title="Historical evidence cannot resume under Factory v2",
        message_template="The verified pre-v2 run remains read-only historical evidence.",
        disposition="READ_ONLY_HISTORICAL_EVIDENCE",
        next_action="Inspect historical provenance; use a supported Factory v2 run for current execution.",
    )

    HISTORICAL_ARTIFACT_INVALID = _spec(
        ("SCHOOL", "STATE", "HISTORICAL_ARTIFACT_INVALID"),
        owner="compatibility.resume_migration",
        title="Historical artifact validation failed",
        message_template="Historical evidence failed validation: {reason}.",
        disposition="PRESERVE_AND_INSPECT",
        next_action="Inspect the recorded bytes and provenance; do not rewrite or resume the artifact.",
    )

    SCHEMA_MISMATCH = _spec(
        ("SCHOOL", "STATE", "SCHEMA_MISMATCH"),
        owner="curriculum.scheduler",
        title="Saved school schema is not supported",
        message_template=(
            "Saved school schema {actual_schema!r} does not match "
            "the supported schema {expected_schema!r}."),
        disposition="PRESERVE_AND_MIGRATE",
        next_action=(
            "Use the schema-owned compatibility migration before resuming; "
            "do not edit the saved school JSON by hand."),
        self_heal_owner="runtime.state",
        legacy_codes=("INVALID_OR_DRIFTED_SCHOOL_STATE",),
    )

    COURSE_DIGEST_MISMATCH = _spec(
        ("SCHOOL", "STATE", "COURSE_DIGEST_MISMATCH"),
        owner="curriculum.scheduler",
        title="Saved school and runtime schedule disagree",
        message_template=(
            "Saved school is bound to course {saved_course_digest}; runtime "
            "loaded {runtime_course_digest}."),
        disposition="PRESERVE_AND_REPAIR",
        next_action=(
            "Reconstruct the schedule from the immutable admitted factory "
            "artifact that owns the saved course digest, then perform any "
            "successor migration explicitly."),
        operator_steps=(
            "Do not delete, rewrite, or re-hash the saved checkpoint.",
            "Inspect the admitted factory release recorded in state.json.",
            "Resume only after its schedule digest matches the saved school.",
        ),
        self_heal_owner="runtime.resume_reconciliation",
        legacy_codes=("INVALID_OR_DRIFTED_SCHOOL_STATE",),
    )

    STAGE_INVALID = _spec(
        ("SCHOOL", "STATE", "STAGE_INVALID"),
        owner="curriculum.scheduler",
        title="Saved school stage is not recognized",
        message_template="Saved stage {actual_stage!r} is outside the admitted state machine.",
        disposition="PRESERVE_AND_MIGRATE",
        next_action=(
            "Run the state-schema migration that owns this stage or restore "
            "the exact code release that created it."),
        self_heal_owner="runtime.state",
        legacy_codes=("INVALID_OR_DRIFTED_SCHOOL_STATE",),
    )

    ACTIVE_GRADES_EMPTY = _spec(
        ("SCHOOL", "STATE", "ACTIVE_GRADES_EMPTY"),
        owner="curriculum.scheduler",
        title="Saved school has no active grade",
        message_template="Saved school contains an empty active_grades sequence.",
        disposition="PRESERVE_AND_REPAIR",
        next_action=(
            "Recover active grades from the admitted schedule/factory artifact; "
            "do not fabricate a grade list."),
        self_heal_owner="runtime.resume_reconciliation",
        legacy_codes=("INVALID_OR_DRIFTED_SCHOOL_STATE",),
    )

    GRADE_INDEX_OUT_OF_RANGE = _spec(
        ("SCHOOL", "STATE", "GRADE_INDEX_OUT_OF_RANGE"),
        owner="curriculum.scheduler",
        title="Saved grade index is outside the active grade sequence",
        message_template=(
            "grade_index={grade_index} cannot address active_grades length "
            "{active_grade_count}."),
        disposition="PRESERVE_AND_REPAIR",
        next_action=(
            "Reconcile the saved scheduler state against its admitted schedule "
            "artifact; do not clamp the index."),
        self_heal_owner="runtime.resume_reconciliation",
        legacy_codes=("INVALID_OR_DRIFTED_SCHOOL_STATE",),
    )
