"""Typed state identity error contracts."""
from __future__ import annotations

from .base import _spec

class StateIdentity:
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

    INVALID_MATURE_CAPABILITY_DEBT = _spec(
        ("SCHOOL", "STATE", "INVALID_MATURE_CAPABILITY_DEBT"), owner="curriculum.state",
        title='Invalid mature capability debt', message_template='Invalid mature capability debt',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Inspect the mature capability debt ledger; preserve student and AdamW state.",
        legacy_codes=('INVALID_MATURE_CAPABILITY_DEBT',),
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
