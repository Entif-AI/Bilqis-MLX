"""Central compositional Bilqis error catalog.

Use these objects directly:

    ErrorBus.raise_(SCHOOL.STATE.COURSE_DIGEST_MISMATCH, ...)

Never copy the rendered code into a new string literal.
"""
from __future__ import annotations

from .model import ErrorSpec, RecoveryContract


def _spec(
    path: tuple[str, ...], *,
    owner: str,
    title: str,
    message_template: str,
    disposition: str,
    next_action: str,
    operator_steps: tuple[str, ...] = (),
    self_heal_owner: str | None = None,
    legacy_codes: tuple[str, ...] = (),
) -> ErrorSpec:
    key = ".".join(path).lower()
    return ErrorSpec(
        path=path,
        owner=owner,
        title=title,
        message_key="errors." + key + ".message",
        message_template=message_template,
        recovery_key="errors." + key + ".recovery",
        recovery=RecoveryContract(
            disposition=disposition,
            next_action=next_action,
            operator_steps=operator_steps,
            preserve_state=True,
            self_heal_owner=self_heal_owner,
        ),
        legacy_codes=legacy_codes,
    )


class SCHOOL:
    class STATE:
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


class SOURCE:
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


class FACTORY:
    class RELEASE:
        MANIFEST_CONTENT_DRIFT = _spec(
            ("FACTORY", "RELEASE", "MANIFEST_CONTENT_DRIFT"),
            owner="runtime.admission",
            title="Sealed factory release content does not match its wire identity",
            message_template=(
                "Factory release {release_sha256} does not match the canonical "
                "payload or embedded course identity that minted it."),
            disposition="PRESERVE_AND_REPAIR",
            next_action=(
                "Preserve the artifact. Decode it with the schema version that "
                "minted it; restore the original bytes if that verification fails."),
            self_heal_owner="compatibility.factory_release_v1",
            legacy_codes=("FACTORY_RELEASE_MANIFEST_CONTENT_DRIFT",),
        )


CATALOG = (
    SCHOOL.STATE.HISTORICAL_NOT_RESUMABLE,
    SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID,
    SCHOOL.STATE.SCHEMA_MISMATCH,
    SCHOOL.STATE.COURSE_DIGEST_MISMATCH,
    SCHOOL.STATE.STAGE_INVALID,
    SCHOOL.STATE.ACTIVE_GRADES_EMPTY,
    SCHOOL.STATE.GRADE_INDEX_OUT_OF_RANGE,
    SEMANTIC_COVERAGE.PLAN.VERSION_MISMATCH,
    SEMANTIC_COVERAGE.AUDIT.INVALID_BUDGET,
    SOURCE.SAMPLING.BALANCED_BINARY_COUNT_INVALID,
    FACTORY.RELEASE.MANIFEST_CONTENT_DRIFT,
)


BY_CODE = {spec.code: spec for spec in CATALOG}
BY_LEGACY_CODE = {
    code: tuple(spec for spec in CATALOG if code in spec.legacy_codes)
    for code in {code for spec in CATALOG for code in spec.legacy_codes}
}
