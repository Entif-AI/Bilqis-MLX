"""Pure typed expression composition; source/admission lives outside this package."""

from .core import (
    Apply,
    Catalog,
    Curried,
    Literal,
    Operation,
    Proof,
    TypedError,
    compose,
    curry,
    lift2,
    literal,
    partial_apply,
    verify,
)
from .methods import BooleanCase, BooleanCoverage, exhaustive_boolean_cases, verify_constituents
from .source_micro import from_micro_query
from .catalog_bridge import bind_source_catalog

__all__ = (
    "Apply", "Catalog", "Curried", "Literal", "Operation", "Proof",
    "TypedError", "compose", "curry", "lift2", "literal", "partial_apply",
    "verify",
    "BooleanCase", "BooleanCoverage", "exhaustive_boolean_cases", "verify_constituents",
    "from_micro_query",
    "bind_source_catalog",
)
