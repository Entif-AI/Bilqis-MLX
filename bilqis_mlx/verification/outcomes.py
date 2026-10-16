"""Shared, serialization-stable outcomes of independent semantic verification.

Use enum members rather than retyping their wire values in new code or tests.
"""
from enum import Enum


class ProofStatus(str, Enum):
    VERIFIED = "VERIFIED"


class CoverageStatus(str, Enum):
    EXHAUSTIVE_FINITE_TRUTH_TABLE = "EXHAUSTIVE_FINITE_TRUTH_TABLE"


class LawCheckStatus(str, Enum):
    VERIFIED_FINITE_SCOPE = "VERIFIED_FINITE_SCOPE"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    UNKNOWN_NO_APPLICABLE_CASES = "UNKNOWN_NO_APPLICABLE_CASES"
