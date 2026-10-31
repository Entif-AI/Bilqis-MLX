"""Typed source grade a error contracts."""
from __future__ import annotations

from .base import _spec

class GRADE_A:
    CONTEXT_ORACLE_DRIFT = _spec(
        ('SOURCE', 'GRADE_A', 'CONTEXT_ORACLE_DRIFT'), owner='source_adapters.grade_a_presentation',
        title='Grade A contextual presentation oracle drift',
        message_template='A contextual Grade A row changed source-oracled meaning.',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Preserve the run and inspect the contextual presentation constructor and source oracle agreement.",
        legacy_codes=('FACTORY_GRADE_A_CONTEXT_ORACLE_DRIFT',),
    )
    MICRO_CONTEXT_SOURCE_SHAPE_INVALID = _spec(
        ('SOURCE', 'GRADE_A', 'MICRO_CONTEXT_SOURCE_SHAPE_INVALID'), owner='source_adapters.grade_a_presentation',
        title='Grade A Micro contextual source shape invalid',
        message_template='A Micro Grade A row cannot accept the admitted irrelevant relation context.',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Preserve the row and inspect the source world shape before contextualization.",
        legacy_codes=('FACTORY_GRADE_A_MICRO_CONTEXT_SOURCE_SHAPE_INVALID',),
    )
    MICRO_CONTEXT_EXHAUSTED = _spec(
        ('SOURCE', 'GRADE_A', 'MICRO_CONTEXT_EXHAUSTED'), owner='source_adapters.grade_a_presentation',
        title='Grade A Micro contextual source space exhausted',
        message_template='No source-valid irrelevant relation fact remains for the Micro Grade A row.',
        disposition="REGENERATE_SOURCE",
        next_action="Regenerate from a fresh source-valid base row; do not weaken source or oracle requirements.",
        legacy_codes=('FACTORY_GRADE_A_MICRO_CONTEXT_EXHAUSTED',),
    )
    DEVELOPMENT_CONTEXT_SOURCE_SHAPE_INVALID = _spec(
        ('SOURCE', 'GRADE_A', 'DEVELOPMENT_CONTEXT_SOURCE_SHAPE_INVALID'), owner='source_adapters.grade_a_presentation',
        title='Grade A Development contextual source shape invalid',
        message_template='A Development Grade A row cannot accept the admitted irrelevant set context.',
        disposition="CORRECT_INPUT_OR_STATE",
        next_action="Preserve the row and inspect the source world shape before contextualization.",
        legacy_codes=('FACTORY_GRADE_A_DEVELOPMENT_CONTEXT_SOURCE_SHAPE_INVALID',),
    )
    CONTEXT_IDENTITY_COLLISION = _spec(
        ('SOURCE', 'GRADE_A', 'CONTEXT_IDENTITY_COLLISION'), owner='source_adapters.grade_a_presentation',
        title='Grade A contextual identity collision',
        message_template='A contextual Grade A draw produced duplicate specimen identities.',
        disposition="REGENERATE_SOURCE",
        next_action="Regenerate the source-valid contextual cohort and preserve the conflicting rows for diagnosis.",
        legacy_codes=('FACTORY_GRADE_A_CONTEXT_IDENTITY_COLLISION',),
    )
