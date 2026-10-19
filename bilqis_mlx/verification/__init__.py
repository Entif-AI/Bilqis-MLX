"""Independent semantic interpretation, finite coverage and falsifiers."""

from .cases import BooleanCase, BooleanCoverage, exhaustive_boolean_cases, verify_constituents
from .expressions import Backend, Proof, verify
from .laws import LawCheck, check_finite_equivalence
from .outcomes import CoverageStatus, LawCheckStatus, ProofStatus

__all__ = (
    "Backend", "BooleanCase", "BooleanCoverage", "CoverageStatus",
    "LawCheck", "LawCheckStatus", "Proof", "ProofStatus",
    "check_finite_equivalence", "exhaustive_boolean_cases", "verify",
    "verify_constituents",
)

# Independent checking owns a separate cache from the source implementation.
from . import numeric as _numeric
from ..semantics.memo import memoize_source as _memoize_source

_numeric.independent_value = _memoize_source(
    semantics="bilqis.independent-finite-numeric/v1")(_numeric.independent_value)
