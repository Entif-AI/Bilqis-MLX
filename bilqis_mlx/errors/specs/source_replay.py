"""Typed source replay error contracts."""
from __future__ import annotations

from .base import _spec

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
