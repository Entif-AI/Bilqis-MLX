from __future__ import annotations

from bilqis_mlx.presentation.spiral_dashboard import Column

# Same six historical panel identities, new-school labels that describe what
# the data actually measures. The old School50 TABLES constant is untouched.
LETTER_TABLES = (
    ("CANDIDATES", (
        Column("CAPABILITY", 10, "capability"),
        Column("VISIT", 5, "attempt", right=True),
        Column("POLICY", 10, "strategy", optional=True),
        Column("LR", 2, "lr", optional=True, right=True),
        Column("WAS/CHP/NOW/ALL", 15, "score_line", right=True),
        Column("REWARD", 6, "reward", right=True),
        Column("LOSS", 5, "loss"),
        Column("GRAD", 5, "gradient", right=True),
        Column("METHOD", 6, "method"),
        Column("OLD pp", 6, "old", optional=True, right=True),
        Column("RESULT", 6, "result"),
        Column("REASON", 27, "reason"),
        Column("WARNINGS", 12, "warnings"))),
    ("SENTINEL & RETENTION", (
        Column("CAPABILITY", 10, "capability"),
        Column("VISIT", 5, "attempt", right=True),
        Column("TARGET", 8, "target", right=True),
        Column("DTG", 3, "target_delta", right=True),
        Column("PRT", 3, "protected", right=True),
        Column("WRS", 3, "worst", right=True),
        Column("RSULT", 5, "result"),
        Column("EVIDENCE", 20, "evidence", optional=True))),
    ("SOUP & TEACHER", (
        Column("CAPABILITY", 10, "capability"),
        Column("VISIT", 5, "attempt", right=True),
        Column("POLICY", 10, "policy", optional=True),
        Column("LR", 2, "lr", right=True),
        Column("D", 1, "depth", right=True),
        Column("C", 1, "contrast", right=True),
        Column("OLD", 3, "old", optional=True, right=True),
        Column("DSTIL", 5, "distill", optional=True, right=True),
        Column("CREDIT", 7, "credit", right=True), Column("P(RET)", 6, "p_ret", optional=True, right=True), Column("HEALTH", 9, "health", optional=True))),
    ("GRADES & MASTERY", (
        Column("CAPABILITY", 10, "subject"),
        Column("WAS/TOP/NOW/ALL", 15, "score_line", right=True),
        Column("GOOD [GREW]", 11, "right_grew", right=True),
        Column("OUTCOME", 26, "outcome"))),
    ("SYSTEM & QUALIFICATION", (
        Column("TYPE", 7, "kind"),
        Column("DETAILS", 32, "detail"))),
)



EVENT_KINDS = {
    "SCHOOL_NEW_RUN_INITIALIZED": "init",
    "SCHOOL_NEXT_GRADE_COURSE_ADMITTED": "init",
    "SCHOOL_EXECUTION_PROFILE_ADOPTED": "curriculum",
    "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED": "curriculum",
    "SCHOOL_TEACHER_VISIT_COMMITTED": "visit",
    "SCHOOL_LIVE_EXAM_COMMITTED": "exam",
    "SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED": "exam",
    "SCHOOL_COURSE_ADMITTED": "init",
    "SCHOOL_RUN_INITIALIZED": "init",
    "SCHOOL_VISIT_COMMITTED": "visit",
    "SCHOOL_EXAM_COMMITTED": "exam",
    "SCHOOL_SESSION_STOPPED": "stop",
    "SCHOOL_SESSION_STARTED": "start",
    "SCHOOL_SENTINEL_COMMITTED": "sentinel",
    "SCHOOL_SOUP_COMMITTED": "soup",
    "SCHOOL_FAMILY_PROBE_COMMITTED": "family",
    "SCHOOL_RESOURCE_OBSERVED": "resource",
    "SCHOOL_CAPABILITY_BEST_COMMITTED": "capability_best",
    "SCHOOL_LIVE_CANDIDATE_COMPARED": "candidate",
    "SCHOOL_QUALIFICATION_COMMITTED": "qualification",
    "SCHOOL_FLASH_ASSESSMENT_DEFERRED": "progress",
    "SCHOOL_GRADE_RELEASE_REPLACED": "curriculum",
    "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED": "autonomy",
    "SCHOOL_AUTONOMY_EVIDENCE_RECORDED": "autonomy",
    "SCHOOL_AUTONOMY_EVIDENCE_VISIT_COMPLETED": "autonomy",
    "SCHOOL_AUTONOMY_QUALIFIED_VISIT_COMPLETED": "autonomy",
    "SCHOOL_AUTONOMY_TEACHING_RECORDED": "autonomy",
}

TELEMETRY_VERSION = "bilqis.school50.telemetry/v1"
