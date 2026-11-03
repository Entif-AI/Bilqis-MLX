"""Exact one-way source-adapter compatibility for sealed historical receipts.

Compatibility lives here rather than in the generic factory or the provider
implementation. That keeps grade/provider history out of generic control flow and
avoids changing the provider fingerprint merely to explain an old receipt.
"""
from __future__ import annotations


_NUMERIC_ADAPTER_ID = "source.finite-numeric/v2"
_NUMERIC_IMPLEMENTATION = (
    "2758cf678e9d2a45f3f5a1b5edd85d5ae513e54506c0d98853b9402b91572754")
_NUMERIC_STAIRCASE_RELEASE = "bilqis.mlx.numeric-staircase/20261017-v1"
_PRE_ADR106_NUMERIC_STAIRCASE_DIGEST = (
    "ec3b5338fc1604a6250a847ee99eae09956b5a5bb269a63f3ac8372205133e74")
_ADR106_NUMERIC_STAIRCASE_DIGEST = (
    "9faf5dd6183657c91753394c0bfa6376849c47594f7e9eb4cb4e5f86c008b235")


def _numeric_adr106_pair(admitted, current) -> bool:
    """Recognize only the exact pre-ADR-106 -> ADR-106 staircase repair."""
    if (admitted is None or
            admitted.adapter_id != current.adapter_id or
            admitted.adapter_id != _NUMERIC_ADAPTER_ID or
            admitted.implementation_sha256 != current.implementation_sha256 or
            admitted.implementation_sha256 != _NUMERIC_IMPLEMENTATION):
        return False
    admitted_releases = dict(admitted.cohort_releases)
    current_releases = dict(current.cohort_releases)
    if (set(admitted_releases) != set(current_releases) or
            admitted_releases.get(_NUMERIC_STAIRCASE_RELEASE) !=
            _PRE_ADR106_NUMERIC_STAIRCASE_DIGEST or
            current_releases.get(_NUMERIC_STAIRCASE_RELEASE) !=
            _ADR106_NUMERIC_STAIRCASE_DIGEST):
        return False
    if any(
            admitted_releases[name] != current_releases[name]
            for name in admitted_releases
            if name != _NUMERIC_STAIRCASE_RELEASE):
        return False
    return (
        admitted.generator_id == current.generator_id and
        admitted.accepted_oracle_ids == current.accepted_oracle_ids and
        admitted.cohort_generator_id == current.cohort_generator_id and
        admitted.variation_axes == current.variation_axes and
        admitted.teaching_option_ids == current.teaching_option_ids and
        admitted.profile_dimensions == current.profile_dimensions)


def resume_adapter_compatible(admitted, current) -> bool:
    """Return true only for explicitly proven historical descriptor migrations."""
    return _numeric_adr106_pair(admitted, current)
