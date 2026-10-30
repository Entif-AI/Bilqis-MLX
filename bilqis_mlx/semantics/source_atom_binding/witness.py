"""Immutable source-row evidence used by raw-atom resolution."""
from __future__ import annotations

from dataclasses import dataclass

from ..domains import contract_digest
from .common import SOURCE_ATOM_MAPPING_SCHEMA, SOURCE_ROW_WITNESS_SCHEMA
from .common import invalid, is_text


@dataclass(frozen=True)
class SourceRowWitness:
    """Canonical adapter-owned source row projected to ordered token indices."""

    source_adapter_id: str
    generator_id: str
    oracle_id: str
    capability_id: str
    source_sense_id: str
    token_indices: tuple[int, ...]
    schema_version: str = SOURCE_ROW_WITNESS_SCHEMA

    def __post_init__(self) -> None:
        if (not all(is_text(item) for item in (
                self.source_adapter_id, self.generator_id, self.oracle_id,
                self.capability_id, self.source_sense_id))
                or not isinstance(self.token_indices, tuple)
                or not self.token_indices
                or any(type(item) is not int or item < 0
                       for item in self.token_indices)
                or self.schema_version != SOURCE_ROW_WITNESS_SCHEMA):
            invalid("BAMF_SOURCE_ATOM_ROW_WITNESS_INVALID")

    def mapping_digest(self, atom_index: int, token_index: int, token: str) -> str:
        return contract_digest((
            SOURCE_ATOM_MAPPING_SCHEMA,
            self.source_adapter_id,
            self.generator_id,
            self.oracle_id,
            self.capability_id,
            self.source_sense_id,
            atom_index,
            token_index,
            token,
        ))
