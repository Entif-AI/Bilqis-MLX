"""Pure, typed Bilqis meaning structures and composable functions."""

import sys as _sys

# Register legacy foundation module identities before importing any sibling that
# still resolves them during package initialization. Physical ownership lives
# under foundation/; the aliases preserve the public import contract.
from .foundation import abi as abi, catalog as catalog, copular as copular
from .foundation import core as core, domains as domains, functions as functions
from .foundation import laws as laws, memo as memo, numeric as numeric


def _preserve_logical_identity(legacy_name, module):
    physical_name = module.__name__
    logical_name = f"{__name__}.{legacy_name}"
    for value in vars(module).values():
        if getattr(value, "__module__", None) == physical_name:
            value.__module__ = logical_name


for _legacy_name, _module in (
    ("abi", abi), ("catalog", catalog), ("copular", copular), ("core", core),
    ("domains", domains), ("functions", functions), ("laws", laws),
    ("memo", memo), ("numeric", numeric),
):
    _preserve_logical_identity(_legacy_name, _module)
    _sys.modules[f"{__name__}.{_legacy_name}"] = _module

from . import dependencies as cognitive_dependencies
_preserve_logical_identity("cognitive_dependencies", cognitive_dependencies)
_sys.modules[f"{__name__}.cognitive_dependencies"] = cognitive_dependencies

from .foundation.catalog import Catalog
from .foundation.core import (
    Apply, Expression, Literal, Operation, Signature, TypedError,
    expression_digest, literal,
)
from .foundation.functions import Curried, compose, curry, lift2, partial_apply
from .foundation.laws import LawCandidate, SourceLocator
from .foundation.memo import memoize_source as _memoize_source

__all__ = (
    "Apply", "Catalog", "Curried", "Expression", "LawCandidate", "Literal",
    "Operation", "Signature", "SourceLocator", "TypedError", "compose", "curry",
    "expression_digest", "lift2", "literal", "partial_apply",
)

# Compose the public source API outside the byte-sealed arithmetic kernel.
numeric.evaluate = _memoize_source(semantics=(
    numeric.CONTRACT, numeric.NUMBER_MAX))(numeric.evaluate)

# Atlas aliases are registered after foundation aliases because Atlas internals
# still import those stable semantic identities during initialization.
from .atlas import feature_io as atlas_feature_io, snapshot as atlas_snapshot
from .atlas import vocabulary as atlas_vocabulary
from .atlas import vocabulary_resources as atlas_vocabulary_resources
from .atlas import vocabulary_transaction as atlas_vocabulary_transaction

for _legacy_name, _module in (
    ("atlas_feature_io", atlas_feature_io), ("atlas_snapshot", atlas_snapshot),
    ("atlas_vocabulary", atlas_vocabulary),
    ("atlas_vocabulary_resources", atlas_vocabulary_resources),
    ("atlas_vocabulary_transaction", atlas_vocabulary_transaction),
):
    _sys.modules[f"{__name__}.{_legacy_name}"] = _module
