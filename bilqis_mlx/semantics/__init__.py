"""Pure, typed Bilqis meaning structures and composable functions."""

from .foundation.catalog import Catalog
from .foundation.core import (
    Apply, Expression, Literal, Operation, Signature, TypedError,
    expression_digest, literal,
)
from .foundation.functions import Curried, compose, curry, lift2, partial_apply
from .foundation.laws import LawCandidate, SourceLocator

__all__ = (
    "Apply", "Catalog", "Curried", "Expression", "LawCandidate", "Literal",
    "Operation", "Signature", "SourceLocator", "TypedError", "compose", "curry",
    "expression_digest", "lift2", "literal", "partial_apply",
)

# Compose the public source API outside the byte-sealed arithmetic kernel.
# Its original implementation still owns meaning and validates every new key.
from .foundation import numeric as _numeric
from .foundation.memo import memoize_source as _memoize_source

_numeric.evaluate = _memoize_source(semantics=(
    _numeric.CONTRACT, _numeric.NUMBER_MAX))(_numeric.evaluate)
