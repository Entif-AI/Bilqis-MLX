"""Typed source boolean error contracts."""
from __future__ import annotations

from .base import _spec

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
