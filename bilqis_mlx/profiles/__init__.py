"""Declarative execution-profile authoring surfaces."""

from .school import (
    boolean_entry_profile,
    boolean_kernel_profile,
    full_boolean_profile,
    numeric_foundation_profile,
    with_disabled_future_grades,
)
from .catalog import CatalogProfileTransition, numeric_entry_transition

__all__ = (
    "boolean_entry_profile",
    "boolean_kernel_profile",
    "full_boolean_profile",
    "numeric_foundation_profile",
    "with_disabled_future_grades",
    "CatalogProfileTransition",
    "numeric_entry_transition",
)
