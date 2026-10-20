"""Declarative execution-profile authoring surfaces."""

from .school import (
    boolean_entry_profile,
    boolean_kernel_profile,
    full_boolean_profile,
    numeric_foundation_profile,
    with_disabled_future_grades,
)
from .catalog import (
    CatalogProfileTransition,
    next_numeric_scope_profile,
    numeric_row_in_scope,
    numeric_entry_transition,
)
from .retention import fragile_preservation_capabilities

__all__ = (
    "boolean_entry_profile",
    "boolean_kernel_profile",
    "full_boolean_profile",
    "numeric_foundation_profile",
    "with_disabled_future_grades",
    "CatalogProfileTransition",
    "next_numeric_scope_profile",
    "numeric_row_in_scope",
    "numeric_entry_transition",
    "fragile_preservation_capabilities",
)
