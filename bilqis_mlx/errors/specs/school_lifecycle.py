"""Typed school lifecycle error contracts."""
from __future__ import annotations

from .base import _spec

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
