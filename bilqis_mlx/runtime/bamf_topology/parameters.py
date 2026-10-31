"""B01 parameters owner."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
from bilqis_mlx.errors import ErrorBus, SCHOOL
from .config import MATRIX_RANK, FEATURE_RESERVED_ROWS, SHA256_HEX_LENGTH, IDENTITY_BANK_SHAPE, MOTIF_PAGE_SHAPE, ModelTopologySpecV2


class ParameterGroup(str, Enum):
    FAST = "FAST"
    SLOW = "SLOW"
    IDENTITY_ROW_AGE = "IDENTITY_ROW_AGE"


class ParameterCategory(str, Enum):
    DENSE_MATRICES = "DENSE_MATRICES"
    SEMANTIC_TABLES = "SEMANTIC_TABLES"
    MOTIF_TABLES = "MOTIF_TABLES"
    ADAPTER_MATRICES = "ADAPTER_MATRICES"
    AUXILIARY = "AUXILIARY"


class AdapterMatrixComponent(str, Enum):
    """Existing low-rank matrix wire suffixes, independent of curriculum grades."""
    INPUT = "A"
    OUTPUT = "B"


ADAPTER_MATRIX_SUFFIXES = frozenset(item.value for item in AdapterMatrixComponent)


class Initializer(str, Enum):
    MATRIX = "M"
    EMBEDDING = "E"
    FEATURE_TABLE = "FEATURE_TABLE"
    ZERO = "ZERO"
    ONE = "ONE"
    CONV_IDENTITY = "CONV_IDENTITY"
    MINUS_TWO = "MINUS_TWO"
    MINUS_FOUR = "MINUS_FOUR"
    LOG_ONE_NINTH = "LOG_ONE_NINTH"
    IDENTITY_BANK = "IDENTITY_BANK"
    MOTIF_PAGE = "MOTIF_PAGE"


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    shape: tuple[int, ...]
    initializer: Initializer
    group: ParameterGroup
    decay: bool
    dtype: str = "float32"

    def __post_init__(self) -> None:
        if (not isinstance(self.name, str) or not self.name or type(self.shape) is not tuple or
                not self.shape or any(type(value) is not int or value <= 0 for value in self.shape) or
                type(self.initializer) is not Initializer or type(self.group) is not ParameterGroup or
                type(self.decay) is not bool or self.dtype != "float32"):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        if ((self.initializer is Initializer.MATRIX and len(self.shape) != MATRIX_RANK) or
                (self.initializer is Initializer.CONV_IDENTITY and
                 (len(self.shape) != MATRIX_RANK or self.shape[1] != ModelTopologySpecV2.convolution_kernel)) or
                (self.initializer is Initializer.FEATURE_TABLE and
                 (len(self.shape) != MATRIX_RANK or self.shape[0] < FEATURE_RESERVED_ROWS)) or
                (self.initializer is Initializer.IDENTITY_BANK and self.shape != IDENTITY_BANK_SHAPE) or
                (self.initializer is Initializer.MOTIF_PAGE and self.shape != MOTIF_PAGE_SHAPE)):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def parameter_count(self) -> int:
        return math.prod(self.shape)

    @property
    def category(self) -> ParameterCategory:
        if self.initializer is Initializer.IDENTITY_BANK:
            return ParameterCategory.SEMANTIC_TABLES
        if self.initializer is Initializer.MOTIF_PAGE:
            return ParameterCategory.MOTIF_TABLES
        suffix = self.name.rsplit(".", 1)[-1]
        if self.name.startswith("blocks.") and suffix in (
                "query", "key", "value", "output", "ffn_in", "ffn_out"):
            return ParameterCategory.DENSE_MATRICES
        if self.name.startswith("plastic.group.") and suffix in ADAPTER_MATRIX_SUFFIXES:
            return ParameterCategory.ADAPTER_MATRICES
        return ParameterCategory.AUXILIARY


@dataclass(frozen=True)
class ParameterCensus:
    topology_digest: str
    extents_digest: str
    parameters: tuple[ParameterSpec, ...]

    def __post_init__(self) -> None:
        if (type(self.parameters) is not tuple or not self.parameters or
                any(type(item) is not ParameterSpec for item in self.parameters) or
                len({item.name for item in self.parameters}) != len(self.parameters)):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        for value in (self.topology_digest, self.extents_digest):
            if (not isinstance(value, str) or len(value) != SHA256_HEX_LENGTH or
                    any(character not in "0123456789abcdef" for character in value)):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def total(self) -> int:
        return sum(item.parameter_count for item in self.parameters)

    @property
    def subtotals(self) -> dict[ParameterCategory, int]:
        result = dict.fromkeys(ParameterCategory, 0)
        for item in self.parameters:
            result[item.category] += item.parameter_count
        return result

    def to_record(self) -> dict:
        return {
            "schema": "bilqis.mlx.bamf-parameter-census/v1",
            "topology_digest": self.topology_digest,
            "generation_extents_digest": self.extents_digest,
            "total_parameters": self.total,
            "subtotals": {kind.value: count for kind, count in self.subtotals.items()},
            "parameters": [{"name": item.name, "shape": list(item.shape),
                            "parameters": item.parameter_count, "category": item.category.value,
                            "dtype": item.dtype, "group": item.group.value}
                           for item in self.parameters],
        }
