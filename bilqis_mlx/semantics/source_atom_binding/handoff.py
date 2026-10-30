"""Whole-prefix identity and ordering for raw-atom consumer handoffs."""
from __future__ import annotations

from dataclasses import dataclass

from ..domains import contract_digest
from .binding import SourceAtomBinding
from .common import AtomBindingDisposition, SHA256, SOURCE_ATOM_HANDOFF_SCHEMA
from .common import invalid, is_text


def handoff_projection(handoff: "SourceAtomHandoff") -> tuple:
    return (
        SOURCE_ATOM_HANDOFF_SCHEMA,
        handoff.source_instance_id,
        handoff.visible_end,
        handoff.semantic_release,
        handoff.a01_bundle_id,
        handoff.a01_source_bundle_id,
        handoff.source_adapter_id,
        tuple(item.binding_digest for item in handoff.bindings),
    )


def handoff_values_projection(values: dict) -> tuple:
    return (
        SOURCE_ATOM_HANDOFF_SCHEMA,
        values["source_instance_id"],
        values["visible_end"],
        values["semantic_release"],
        values["a01_bundle_id"],
        values["a01_source_bundle_id"],
        values["source_adapter_id"],
        tuple(item.binding_digest for item in values["bindings"]),
    )


@dataclass(frozen=True)
class SourceAtomHandoff:
    """Immutable B02/B03-facing raw-atom identity handoff."""

    source_instance_id: str
    visible_end: int
    semantic_release: str
    a01_bundle_id: str
    a01_source_bundle_id: str
    source_adapter_id: str
    bindings: tuple[SourceAtomBinding, ...]
    digest: str
    schema_version: str = SOURCE_ATOM_HANDOFF_SCHEMA

    def __post_init__(self) -> None:
        if (not is_text(self.source_instance_id)
                or type(self.visible_end) is not int or self.visible_end < 0
                or any(not isinstance(item, str) or not SHA256.fullmatch(item)
                       for item in (
                           self.semantic_release, self.a01_bundle_id,
                           self.a01_source_bundle_id, self.digest))
                or not is_text(self.source_adapter_id)
                or not isinstance(self.bindings, tuple)
                or any(not isinstance(item, SourceAtomBinding)
                       for item in self.bindings)
                or tuple(item.atom_index for item in self.bindings)
                   != tuple(range(self.visible_end))
                or any((item.source_instance_id, item.semantic_release,
                        item.a01_bundle_id, item.a01_source_bundle_id,
                        item.source_adapter_id)
                       != (self.source_instance_id, self.semantic_release,
                           self.a01_bundle_id, self.a01_source_bundle_id,
                           self.source_adapter_id)
                       for item in self.bindings)
                or self.schema_version != SOURCE_ATOM_HANDOFF_SCHEMA):
            invalid("BAMF_SOURCE_ATOM_HANDOFF_INVALID")
        for item in self.bindings:
            item.__post_init__()
        if self.digest != contract_digest(handoff_projection(self)):
            invalid("BAMF_SOURCE_ATOM_HANDOFF_DIGEST_MISMATCH")

    @property
    def embedding_ready(self) -> bool:
        return bool(self.bindings) and all(
            item.disposition is AtomBindingDisposition.BOUND
            for item in self.bindings)


def make_handoff(**values) -> SourceAtomHandoff:
    digest = contract_digest(handoff_values_projection(values))
    return SourceAtomHandoff(digest=digest, **values)
