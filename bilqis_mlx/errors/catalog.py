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
    class RESUME:
        BOOLEAN_COMPOSITE_REQUIRES_RESUME = _spec(
            ('SCHOOL', 'RESUME', 'BOOLEAN_COMPOSITE_REQUIRES_RESUME'), owner='compatibility.cli_preflight',
            title='Boolean composite requires resume', message_template='Boolean composite requires resume',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('BOOLEAN_COMPOSITE_REQUIRES_RESUME',),
        )
        BOOLEAN_IDBOOLOPS_REQUIRES_RESUME = _spec(
            ('SCHOOL', 'RESUME', 'BOOLEAN_IDBOOLOPS_REQUIRES_RESUME'), owner='compatibility.cli_preflight',
            title='Boolean idboolops requires resume', message_template='Boolean idboolops requires resume',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('BOOLEAN_IDBOOLOPS_REQUIRES_RESUME',),
        )
        BOOLEAN_REVISION_SOURCE_STUDENT_MISSING = _spec(
            ('SCHOOL', 'RESUME', 'BOOLEAN_REVISION_SOURCE_STUDENT_MISSING'), owner='compatibility.cli_preflight',
            title='Boolean revision source student missing', message_template='Boolean revision source student missing',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('BOOLEAN_REVISION_SOURCE_STUDENT_MISSING',),
        )

    class SCHEDULE:
        PRIOR_GRADE_EXPANSION_CHANGED_EXISTING_CAPABILITY = _spec(
            ('SCHOOL', 'SCHEDULE', 'PRIOR_GRADE_EXPANSION_CHANGED_EXISTING_CAPABILITY'), owner='curriculum.scheduler',
            title='Factory schedule prior grade expansion changed existing capability', message_template='Factory schedule prior grade expansion changed existing capability',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_SCHEDULE_PRIOR_GRADE_EXPANSION_CHANGED_EXISTING_CAPABILITY',),
        )
        PRIOR_GRADE_EXPANSION_INVALID = _spec(
            ('SCHOOL', 'SCHEDULE', 'PRIOR_GRADE_EXPANSION_INVALID'), owner='curriculum.scheduler',
            title='Factory schedule prior grade expansion invalid', message_template='Factory schedule prior grade expansion invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_SCHEDULE_PRIOR_GRADE_EXPANSION_INVALID',),
        )
        PRIOR_GRADE_EXPANSION_NOT_ADDITIVE = _spec(
            ('SCHOOL', 'SCHEDULE', 'PRIOR_GRADE_EXPANSION_NOT_ADDITIVE'), owner='curriculum.scheduler',
            title='Factory schedule prior grade expansion not additive', message_template='Factory schedule prior grade expansion not additive',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_SCHEDULE_PRIOR_GRADE_EXPANSION_NOT_ADDITIVE',),
        )
        PROGRAM_REQUIRED = _spec(
            ('SCHOOL', 'SCHEDULE', 'PROGRAM_REQUIRED'), owner='curriculum.scheduler',
            title='Factory schedule program required', message_template='Factory schedule program required',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_SCHEDULE_PROGRAM_REQUIRED',),
        )
        INVALID_DEBT_CADENCE_POLICY = _spec(
            ('SCHOOL', 'SCHEDULE', 'INVALID_DEBT_CADENCE_POLICY'), owner='curriculum.scheduler',
            title='Invalid debt cadence policy', message_template='Invalid debt cadence policy',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('INVALID_DEBT_CADENCE_POLICY',),
        )

    class STATE:
        ASSESSMENT_HAS_NO_REPRESENTED_GRADE = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_HAS_NO_REPRESENTED_GRADE"), owner="curriculum.state",
            title='Assessment has no represented grade', message_template='Assessment has no represented grade',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_HAS_NO_REPRESENTED_GRADE',),
        )
        ASSESSMENT_INVALID_SCORE_TYPE = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_INVALID_SCORE_TYPE"), owner="curriculum.state",
            title='Assessment invalid score type', message_template='Assessment invalid score type',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_INVALID_SCORE_TYPE',),
        )
        ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL"), owner="curriculum.state",
            title='Assessment not complete active pool', message_template='Assessment not complete active pool',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL',),
        )
        ASSESSMENT_NOT_COURSE_SEALED_RUBRIC = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_NOT_COURSE_SEALED_RUBRIC"), owner="curriculum.state",
            title='Assessment not course sealed rubric', message_template='Assessment not course sealed rubric',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_NOT_COURSE_SEALED_RUBRIC',),
        )
        ASSESSMENT_NOT_GRADE_SEALED_RUBRIC = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_NOT_GRADE_SEALED_RUBRIC"), owner="curriculum.state",
            title='Assessment not grade sealed rubric', message_template='Assessment not grade sealed rubric',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_NOT_GRADE_SEALED_RUBRIC',),
        )
        ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE"), owner="curriculum.state",
            title='Assessment not same checkpoint or course', message_template='Assessment not same checkpoint or course',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE',),
        )
        ASSESSMENT_RUBRIC_IDENTITY_MISSING = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_RUBRIC_IDENTITY_MISSING"), owner="curriculum.state",
            title='Assessment rubric identity missing', message_template='Assessment rubric identity missing',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_RUBRIC_IDENTITY_MISSING',),
        )
        ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL"), owner="curriculum.state",
            title='Assessment rubric scope does not cover active pool', message_template='Assessment rubric scope does not cover active pool',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL',),
        )
        ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT = _spec(
            ("SCHOOL", "STATE", "ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT"), owner="curriculum.state",
            title='Assessment total differs from sealed item count', message_template='Assessment total differs from sealed item count',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT',),
        )
        CARRIED_MASTERY_DEBT_AT_COMPLETION_BOUNDARY = _spec(
            ("SCHOOL", "STATE", "CARRIED_MASTERY_DEBT_AT_COMPLETION_BOUNDARY"), owner="curriculum.state",
            title='Carried mastery debt at completion boundary', message_template='Carried mastery debt at completion boundary',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('CARRIED_MASTERY_DEBT_AT_COMPLETION_BOUNDARY',),
        )
        INVALID_CAPABILITY_SCORE = _spec(
            ("SCHOOL", "STATE", "INVALID_CAPABILITY_SCORE"), owner="curriculum.state",
            title='Invalid capability score', message_template='Invalid capability score',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('INVALID_CAPABILITY_SCORE',),
        )
        INVALID_CARRIED_MASTERY_DEBT = _spec(
            ("SCHOOL", "STATE", "INVALID_CARRIED_MASTERY_DEBT"), owner="curriculum.state",
            title='Invalid carried mastery debt', message_template='Invalid carried mastery debt',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('INVALID_CARRIED_MASTERY_DEBT',),
        )
        INVALID_GRADE_PROGRAM_OR_CHAMPIONS = _spec(
            ("SCHOOL", "STATE", "INVALID_GRADE_PROGRAM_OR_CHAMPIONS"), owner="curriculum.state",
            title='Invalid grade program or champions', message_template='Invalid grade program or champions',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('INVALID_GRADE_PROGRAM_OR_CHAMPIONS',),
        )
        INVALID_GRADE_REVALIDATION_STATE = _spec(
            ("SCHOOL", "STATE", "INVALID_GRADE_REVALIDATION_STATE"), owner="curriculum.state",
            title='Invalid grade revalidation state', message_template='Invalid grade revalidation state',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('INVALID_GRADE_REVALIDATION_STATE',),
        )
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

    class LEARNING:
        BINARY_CLASS_MISSING = _spec(
            ("SCHOOL", "LEARNING", "BINARY_CLASS_MISSING"), owner="learning.source_selection",
            title='Learning experiment binary class missing', message_template='Learning experiment binary class missing',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('LEARNING_EXPERIMENT_BINARY_CLASS_MISSING',),
        )
        BINARY_PATTERN_CAPACITY = _spec(
            ("SCHOOL", "LEARNING", "BINARY_PATTERN_CAPACITY"), owner="learning.source_selection",
            title='Learning experiment binary pattern capacity', message_template='Learning experiment binary pattern capacity',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('LEARNING_EXPERIMENT_BINARY_PATTERN_CAPACITY',),
        )
        MISSING_SOURCE_ROWS = _spec(
            ("SCHOOL", "LEARNING", "MISSING_SOURCE_ROWS"), owner="learning.source_selection",
            title='Learning experiment missing source rows', message_template='Learning experiment missing source rows',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('LEARNING_EXPERIMENT_MISSING_SOURCE_ROWS',),
        )
        MISSING_FRESH_CURRENT_ROWS = _spec(
            ('SCHOOL', 'LEARNING', 'MISSING_FRESH_CURRENT_ROWS'), owner='learning.learning_experiment',
            title='Learning experiment missing fresh current rows', message_template='Learning experiment missing fresh current rows',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('LEARNING_EXPERIMENT_MISSING_FRESH_CURRENT_ROWS',),
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
    class BOOLEAN:
        COMPOSITE_ORACLE_COMPOSITION_WIDTH = _spec(
            ('SOURCE', 'BOOLEAN', 'COMPOSITE_ORACLE_COMPOSITION_WIDTH'), owner='boolean_composite_oracle',
            title='Composite oracle composition width', message_template='Composite oracle composition width',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_COMPOSITE_ORACLE_COMPOSITION_WIDTH',),
        )
        COMPOSITE_ORACLE_UNKNOWN_TASK_OR_CAPABILITY = _spec(
            ('SOURCE', 'BOOLEAN', 'COMPOSITE_ORACLE_UNKNOWN_TASK_OR_CAPABILITY'), owner='boolean_composite_oracle',
            title='Composite oracle unknown task or capability', message_template='Composite oracle unknown task or capability',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_COMPOSITE_ORACLE_UNKNOWN_TASK_OR_CAPABILITY',),
        )
        IDBOOLOPS_OBSERVATION_SHAPE = _spec(
            ('SOURCE', 'BOOLEAN', 'IDBOOLOPS_OBSERVATION_SHAPE'), owner='boolean_identification',
            title='Idboolops observation shape', message_template='Idboolops observation shape',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_IDBOOLOPS_OBSERVATION_SHAPE',),
        )
        IDBOOLOPS_RECORD_SHAPE = _spec(
            ('SOURCE', 'BOOLEAN', 'IDBOOLOPS_RECORD_SHAPE'), owner='boolean_identification',
            title='Idboolops record shape', message_template='Idboolops record shape',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_IDBOOLOPS_RECORD_SHAPE',),
        )
        IDBOOLOPS_ORACLE_DIRECT_OPERAND_INVALID = _spec(
            ('SOURCE', 'BOOLEAN', 'IDBOOLOPS_ORACLE_DIRECT_OPERAND_INVALID'), owner='boolean_identification_oracle',
            title='Idboolops oracle direct operand invalid', message_template='Idboolops oracle direct operand invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_IDBOOLOPS_ORACLE_DIRECT_OPERAND_INVALID',),
        )
        ORACLE_ASSIGNMENTS_INVALID = _spec(
            ('SOURCE', 'BOOLEAN', 'ORACLE_ASSIGNMENTS_INVALID'), owner='grade_b_oracle',
            title='Oracle assignments invalid', message_template='Oracle assignments invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_ORACLE_ASSIGNMENTS_INVALID',),
        )
        ORACLE_CONNECTIVE_SHAPE = _spec(
            ('SOURCE', 'BOOLEAN', 'ORACLE_CONNECTIVE_SHAPE'), owner='grade_b_oracle',
            title='Oracle connective shape', message_template='Oracle connective shape',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_ORACLE_CONNECTIVE_SHAPE',),
        )
        ORACLE_DIRECT_EXPRESSION_INVALID = _spec(
            ('SOURCE', 'BOOLEAN', 'ORACLE_DIRECT_EXPRESSION_INVALID'), owner='grade_b_oracle',
            title='Oracle direct expression invalid', message_template='Oracle direct expression invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_ORACLE_DIRECT_EXPRESSION_INVALID',),
        )
        ORACLE_UNKNOWN_TASK_OR_CAPABILITY = _spec(
            ('SOURCE', 'BOOLEAN', 'ORACLE_UNKNOWN_TASK_OR_CAPABILITY'), owner='grade_b_oracle',
            title='Oracle unknown task or capability', message_template='Oracle unknown task or capability',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_ORACLE_UNKNOWN_TASK_OR_CAPABILITY',),
        )
        BOOLEAN_CONTEXT_LENGTH = _spec(
            ('SOURCE', 'BOOLEAN', 'BOOLEAN_CONTEXT_LENGTH'), owner='live_grade_b',
            title='Grade b boolean context length', message_template='Grade b boolean context length',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_BOOLEAN_CONTEXT_LENGTH',),
        )
        BOOLEAN_SOURCE_ROOT_MISMATCH = _spec(
            ('SOURCE', 'BOOLEAN', 'BOOLEAN_SOURCE_ROOT_MISMATCH'), owner='live_grade_b',
            title='Grade b boolean source root mismatch', message_template='Grade b boolean source root mismatch',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_BOOLEAN_SOURCE_ROOT_MISMATCH',),
        )
        BOOLEAN_TOKEN_ABI_DRIFT = _spec(
            ('SOURCE', 'BOOLEAN', 'BOOLEAN_TOKEN_ABI_DRIFT'), owner='live_grade_b',
            title='Grade b boolean token abi drift', message_template='Grade b boolean token abi drift',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_BOOLEAN_TOKEN_ABI_DRIFT',),
        )
        UNKNOWN_OPERATOR = _spec(
            ('SOURCE', 'BOOLEAN', 'UNKNOWN_OPERATOR'), owner='live_grade_b',
            title='Grade b unknown operator', message_template='Grade b unknown operator',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_UNKNOWN_OPERATOR',),
        )
        NATIVE_REGISTRY_ADMISSION_NOT_VERIFIED = _spec(
            ('SOURCE', 'BOOLEAN', 'NATIVE_REGISTRY_ADMISSION_NOT_VERIFIED'), owner='live_grade_c',
            title='Grade c native registry admission not verified', message_template='Grade c native registry admission not verified',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_C_NATIVE_REGISTRY_ADMISSION_NOT_VERIFIED',),
        )
        MINIMAL_IDBOOLOPS_ORACLE_DRIFT = _spec(
            ('SOURCE', 'BOOLEAN', 'MINIMAL_IDBOOLOPS_ORACLE_DRIFT'), owner='minimal_grade_b',
            title='Grade b minimal idboolops oracle drift', message_template='Grade b minimal idboolops oracle drift',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_B_MINIMAL_IDBOOLOPS_ORACLE_DRIFT',),
        )

    class REPLAY:
        PRESERVATION_EXAM_ROW_LEAK = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_EXAM_ROW_LEAK'), owner='learning.fragile_replay',
            title='Fragile preservation exam row leak', message_template='Fragile preservation exam row leak',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_EXAM_ROW_LEAK',),
        )
        PRESERVATION_MIXED_REPRESENTATION = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_MIXED_REPRESENTATION'), owner='learning.fragile_replay',
            title='Fragile preservation mixed representation', message_template='Fragile preservation mixed representation',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_MIXED_REPRESENTATION',),
        )
        REPLAY_U7C_PATTERN_DRIFT = _spec(
            ('SOURCE', 'REPLAY', 'REPLAY_U7C_PATTERN_DRIFT'), owner='learning.fragile_replay',
            title='Fragile replay u7c pattern drift', message_template='Fragile replay u7c pattern drift',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_REPLAY_U7C_PATTERN_DRIFT',),
        )
        PRESERVATION_POLICY_INVALID = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_POLICY_INVALID'), owner='profiles.retention',
            title='Fragile preservation policy invalid', message_template='Fragile preservation policy invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_POLICY_INVALID',),
        )
        RETENTION_SUPPORT_ROTATION_INVALID = _spec(
            ('SOURCE', 'REPLAY', 'RETENTION_SUPPORT_ROTATION_INVALID'), owner='runtime.candidate_evidence',
            title='Retention support rotation invalid', message_template='Retention support rotation invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('RETENTION_SUPPORT_ROTATION_INVALID',),
        )
        RETENTION_SUPPORT_ROW_INVALID = _spec(
            ('SOURCE', 'REPLAY', 'RETENTION_SUPPORT_ROW_INVALID'), owner='runtime.candidate_evidence',
            title='Retention support row invalid', message_template='Retention support row invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('RETENTION_SUPPORT_ROW_INVALID',),
        )
        PRESERVATION_OPERAND_KIND_INVALID = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_OPERAND_KIND_INVALID'), owner='source_adapters.school',
            title='Fragile preservation operand kind invalid', message_template='Fragile preservation operand kind invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_OPERAND_KIND_INVALID',),
        )
        PRESERVATION_OPERAND_PATTERN_INVALID = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_OPERAND_PATTERN_INVALID'), owner='source_adapters.school',
            title='Fragile preservation operand pattern invalid', message_template='Fragile preservation operand pattern invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_OPERAND_PATTERN_INVALID',),
        )
        PRESERVATION_SOURCE_GOLD_DRIFT = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_SOURCE_GOLD_DRIFT'), owner='source_adapters.school',
            title='Fragile preservation source gold drift', message_template='Fragile preservation source gold drift',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_SOURCE_GOLD_DRIFT',),
        )
        PRESERVATION_SOURCE_POLICY_UNKNOWN = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_SOURCE_POLICY_UNKNOWN'), owner='source_adapters.school',
            title='Fragile preservation source policy unknown', message_template='Fragile preservation source policy unknown',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_SOURCE_POLICY_UNKNOWN',),
        )
        PRESERVATION_STRUCTURAL_SIGNATURE_INVALID = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_STRUCTURAL_SIGNATURE_INVALID'), owner='source_adapters.school',
            title='Fragile preservation structural signature invalid', message_template='Fragile preservation structural signature invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_STRUCTURAL_SIGNATURE_INVALID',),
        )
        PRESERVATION_U7C_PATTERN_CONTRACT_INVALID = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_U7C_PATTERN_CONTRACT_INVALID'), owner='source_adapters.school',
            title='Fragile preservation u7c pattern contract invalid', message_template='Fragile preservation u7c pattern contract invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_U7C_PATTERN_CONTRACT_INVALID',),
        )
        PRESERVATION_U7C_STRUCTURAL_REQUEST_INVALID = _spec(
            ('SOURCE', 'REPLAY', 'PRESERVATION_U7C_STRUCTURAL_REQUEST_INVALID'), owner='source_adapters.school',
            title='Fragile preservation u7c structural request invalid', message_template='Fragile preservation u7c structural request invalid',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_PRESERVATION_U7C_STRUCTURAL_REQUEST_INVALID',),
        )
        REPLAY_ORACLE_OR_COMPOSITION_DRIFT = _spec(
            ('SOURCE', 'REPLAY', 'REPLAY_ORACLE_OR_COMPOSITION_DRIFT'), owner='source_adapters.school',
            title='Fragile replay oracle or composition drift', message_template='Fragile replay oracle or composition drift',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT',),
        )

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
    class ADMISSION:
        COMPLETE_PRIOR_EXAM_REQUIRED = _spec(
            ('FACTORY', 'ADMISSION', 'COMPLETE_PRIOR_EXAM_REQUIRED'), owner='compatibility.grade_transition',
            title='Grade admission requires complete perfect cumulative exam', message_template='Grade admission requires complete perfect cumulative exam',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('GRADE_ADMISSION_REQUIRES_COMPLETE_PERFECT_CUMULATIVE_EXAM',),
        )

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

    class EXECUTION:
        CURRICULUM_DEFINITION_REQUIRED = _spec(
            ('FACTORY', 'EXECUTION', 'CURRICULUM_DEFINITION_REQUIRED'), owner='factory.curriculum_definition',
            title='Factory curriculum definition required', message_template='Factory curriculum definition required',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_CURRICULUM_DEFINITION_REQUIRED',),
        )
        CURRICULUM_UNKNOWN_CAPABILITY = _spec(
            ('FACTORY', 'EXECUTION', 'CURRICULUM_UNKNOWN_CAPABILITY'), owner='factory.curriculum_definition',
            title='Factory curriculum unknown capability', message_template='Factory curriculum unknown capability',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_CURRICULUM_UNKNOWN_CAPABILITY',),
        )
        ASSESSMENT_SOURCE_CONTEXT_REQUIRED = _spec(
            ('FACTORY', 'EXECUTION', 'ASSESSMENT_SOURCE_CONTEXT_REQUIRED'), owner='runtime.assessment',
            title='Factory assessment source context required', message_template='Factory assessment source context required',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_ASSESSMENT_SOURCE_CONTEXT_REQUIRED',),
        )
        EXECUTABLE_PROFILE_TRANSITION_UNSUPPORTED = _spec(
            ('FACTORY', 'EXECUTION', 'EXECUTABLE_PROFILE_TRANSITION_UNSUPPORTED'), owner='runtime.release_adoption',
            title='Factory executable profile transition unsupported', message_template='Factory executable profile transition unsupported',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_EXECUTABLE_PROFILE_TRANSITION_UNSUPPORTED',),
        )
        EXPECTED_A_SOURCEADAPTERREGISTRY = _spec(
            ('FACTORY', 'EXECUTION', 'EXPECTED_A_SOURCEADAPTERREGISTRY'), owner='runtime.source_execution',
            title='Expected a sourceadapterregistry', message_template='Expected a sourceadapterregistry',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('Expected a SourceAdapterRegistry',),
        )
        EXPECTED_AN_ANSWERMODALITYREGISTRY = _spec(
            ('FACTORY', 'EXECUTION', 'EXPECTED_AN_ANSWERMODALITYREGISTRY'), owner='runtime.source_execution',
            title='Expected an answermodalityregistry', message_template='Expected an answermodalityregistry',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('Expected an AnswerModalityRegistry',),
        )
        EXPECTED_AN_EXECUTABLEFACTORYRELEASE = _spec(
            ('FACTORY', 'EXECUTION', 'EXPECTED_AN_EXECUTABLEFACTORYRELEASE'), owner='runtime.source_execution',
            title='Expected an executablefactoryrelease', message_template='Expected an executablefactoryrelease',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('Expected an ExecutableFactoryRelease',),
        )
        EXECUTABLE_GENERATION_UNKNOWN_CAPABILITY = _spec(
            ('FACTORY', 'EXECUTION', 'EXECUTABLE_GENERATION_UNKNOWN_CAPABILITY'), owner='runtime.source_execution',
            title='Factory executable generation unknown capability', message_template='Factory executable generation unknown capability',
            disposition="CORRECT_INPUT_OR_STATE",
            next_action="Inspect the owning contract and inputs; preserve recorded state.",
            legacy_codes=('FACTORY_EXECUTABLE_GENERATION_UNKNOWN_CAPABILITY',),
        )


CATALOG = (
    SCHOOL.STATE.INVALID_GRADE_PROGRAM_OR_CHAMPIONS,
    SCHOOL.STATE.QUEUE_CAPABILITY_OUTSIDE_ACTIVE_AND_PASSED_GRADES,
    SCHOOL.STATE.INVALID_SCHOOL_COUNTER,
    SCHOOL.STATE.INVALID_INTRODUCTION_FRONTIER_HISTORY,
    SCHOOL.STATE.INVALID_MAIN_SWEEP_HISTORY,
    SCHOOL.STATE.INVALID_CARRIED_MASTERY_DEBT,
    SCHOOL.STATE.CARRIED_MASTERY_DEBT_AT_COMPLETION_BOUNDARY,
    SCHOOL.STATE.INVALID_INTRODUCTION_STAGE,
    SCHOOL.STATE.INVALID_PARTIAL_SCHOOL_COMPLETION,
    SCHOOL.STATE.WHOLE_SCHOOL_CANNOT_COMPLETE_PARTIAL_COURSE,
    SCHOOL.STATE.WEAKEST_THREE_INCOMPLETE_POOL,
    SCHOOL.STATE.INVALID_CAPABILITY_SCORE,
    SCHOOL.STATE.ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE,
    SCHOOL.STATE.ASSESSMENT_RUBRIC_IDENTITY_MISSING,
    SCHOOL.STATE.ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL,
    SCHOOL.STATE.ASSESSMENT_HAS_NO_REPRESENTED_GRADE,
    SCHOOL.STATE.ASSESSMENT_NOT_GRADE_SEALED_RUBRIC,
    SCHOOL.STATE.ASSESSMENT_NOT_COURSE_SEALED_RUBRIC,
    SCHOOL.STATE.ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL,
    SCHOOL.STATE.ASSESSMENT_INVALID_SCORE_TYPE,
    SCHOOL.STATE.ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT,
    SCHOOL.STATE.INVALID_GRADE_REVALIDATION_STATE,
    SCHOOL.LEARNING.BINARY_PATTERN_CAPACITY,
    SCHOOL.LEARNING.BINARY_CLASS_MISSING,
    SCHOOL.LEARNING.MISSING_SOURCE_ROWS,
    FACTORY.EXECUTION.CURRICULUM_DEFINITION_REQUIRED,
    FACTORY.EXECUTION.CURRICULUM_UNKNOWN_CAPABILITY,
    SCHOOL.LEARNING.MISSING_FRESH_CURRENT_ROWS,
    SOURCE.BOOLEAN.BOOLEAN_CONTEXT_LENGTH,
    SOURCE.BOOLEAN.BOOLEAN_SOURCE_ROOT_MISMATCH,
    SOURCE.BOOLEAN.BOOLEAN_TOKEN_ABI_DRIFT,
    SOURCE.BOOLEAN.UNKNOWN_OPERATOR,
    SOURCE.BOOLEAN.NATIVE_REGISTRY_ADMISSION_NOT_VERIFIED,
    SOURCE.BOOLEAN.MINIMAL_IDBOOLOPS_ORACLE_DRIFT,
    SOURCE.REPLAY.PRESERVATION_POLICY_INVALID,
    FACTORY.EXECUTION.ASSESSMENT_SOURCE_CONTEXT_REQUIRED,
    SOURCE.REPLAY.RETENTION_SUPPORT_ROTATION_INVALID,
    SOURCE.REPLAY.RETENTION_SUPPORT_ROW_INVALID,
    FACTORY.EXECUTION.EXECUTABLE_PROFILE_TRANSITION_UNSUPPORTED,
    FACTORY.EXECUTION.EXPECTED_A_SOURCEADAPTERREGISTRY,
    FACTORY.EXECUTION.EXPECTED_AN_ANSWERMODALITYREGISTRY,
    FACTORY.EXECUTION.EXPECTED_AN_EXECUTABLEFACTORYRELEASE,
    FACTORY.EXECUTION.EXECUTABLE_GENERATION_UNKNOWN_CAPABILITY,
    SOURCE.REPLAY.PRESERVATION_OPERAND_KIND_INVALID,
    SOURCE.REPLAY.PRESERVATION_OPERAND_PATTERN_INVALID,
    SOURCE.REPLAY.PRESERVATION_SOURCE_GOLD_DRIFT,
    SOURCE.REPLAY.PRESERVATION_SOURCE_POLICY_UNKNOWN,
    SOURCE.REPLAY.PRESERVATION_STRUCTURAL_SIGNATURE_INVALID,
    SOURCE.REPLAY.PRESERVATION_U7C_PATTERN_CONTRACT_INVALID,
    SOURCE.REPLAY.PRESERVATION_U7C_STRUCTURAL_REQUEST_INVALID,
    SOURCE.REPLAY.REPLAY_ORACLE_OR_COMPOSITION_DRIFT,

    SOURCE.BOOLEAN.COMPOSITE_ORACLE_COMPOSITION_WIDTH,
    SOURCE.BOOLEAN.COMPOSITE_ORACLE_UNKNOWN_TASK_OR_CAPABILITY,
    SOURCE.BOOLEAN.IDBOOLOPS_OBSERVATION_SHAPE,
    SOURCE.BOOLEAN.IDBOOLOPS_RECORD_SHAPE,
    SOURCE.BOOLEAN.IDBOOLOPS_ORACLE_DIRECT_OPERAND_INVALID,
    SCHOOL.RESUME.BOOLEAN_COMPOSITE_REQUIRES_RESUME,
    SCHOOL.RESUME.BOOLEAN_IDBOOLOPS_REQUIRES_RESUME,
    SCHOOL.RESUME.BOOLEAN_REVISION_SOURCE_STUDENT_MISSING,
    FACTORY.ADMISSION.COMPLETE_PRIOR_EXAM_REQUIRED,
    SCHOOL.SCHEDULE.PRIOR_GRADE_EXPANSION_CHANGED_EXISTING_CAPABILITY,
    SCHOOL.SCHEDULE.PRIOR_GRADE_EXPANSION_INVALID,
    SCHOOL.SCHEDULE.PRIOR_GRADE_EXPANSION_NOT_ADDITIVE,
    SCHOOL.SCHEDULE.PROGRAM_REQUIRED,
    SCHOOL.SCHEDULE.INVALID_DEBT_CADENCE_POLICY,
    SOURCE.BOOLEAN.ORACLE_ASSIGNMENTS_INVALID,
    SOURCE.BOOLEAN.ORACLE_CONNECTIVE_SHAPE,
    SOURCE.BOOLEAN.ORACLE_DIRECT_EXPRESSION_INVALID,
    SOURCE.BOOLEAN.ORACLE_UNKNOWN_TASK_OR_CAPABILITY,
    SOURCE.REPLAY.PRESERVATION_EXAM_ROW_LEAK,
    SOURCE.REPLAY.PRESERVATION_MIXED_REPRESENTATION,
    SOURCE.REPLAY.REPLAY_U7C_PATTERN_DRIFT,

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
