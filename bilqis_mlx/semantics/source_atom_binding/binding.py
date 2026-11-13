"""Canonical records for one source-visible atom and its semantic candidate."""
from __future__ import annotations

from dataclasses import dataclass

from ..domains import contract_digest
from .common import AtomBindingDisposition, SHA256, SOURCE_ATOM_BINDING_SCHEMA
from .common import invalid, is_text


def binding_projection(binding: "SourceAtomBinding") -> tuple:
    return (
        SOURCE_ATOM_BINDING_SCHEMA,
        binding.source_instance_id,
        binding.atom_index,
        binding.token,
        binding.source_reference,
        binding.source_evidence_digest,
        binding.semantic_release,
        binding.a01_bundle_id,
        binding.a01_source_bundle_id,
        binding.source_adapter_id,
        binding.source_token_index,
        binding.mapping_record_digest,
        binding.candidate_semantic_id,
        binding.candidate_abi_index,
        binding.candidate_type_ids,
        binding.rights_epoch,
        binding.correction_generation,
        binding.rights_digest,
        binding.visible_at_prefix,
        binding.disposition,
        binding.reason_codes,
    )


def binding_values_projection(values: dict) -> tuple:
    return (
        SOURCE_ATOM_BINDING_SCHEMA,
        values["source_instance_id"],
        values["atom_index"],
        values["token"],
        values["source_reference"],
        values["source_evidence_digest"],
        values["semantic_release"],
        values["a01_bundle_id"],
        values["a01_source_bundle_id"],
        values["source_adapter_id"],
        values["source_token_index"],
        values["mapping_record_digest"],
        values["candidate_semantic_id"],
        values["candidate_abi_index"],
        values["candidate_type_ids"],
        values["rights_epoch"],
        values["correction_generation"],
        values["rights_digest"],
        values["visible_at_prefix"],
        values["disposition"],
        values["reason_codes"],
    )


@dataclass(frozen=True)
class SourceAtomBinding:
    """One source-visible atom's verified candidate or explicit held state."""

    source_instance_id: str
    atom_index: int
    token: str
    source_reference: str
    source_evidence_digest: str
    semantic_release: str
    a01_bundle_id: str
    a01_source_bundle_id: str
    source_adapter_id: str
    source_token_index: int | None
    mapping_record_digest: str
    candidate_semantic_id: str | None
    candidate_abi_index: int | None
    candidate_type_ids: tuple[str, ...]
    rights_epoch: int
    correction_generation: int
    rights_digest: str
    visible_at_prefix: int
    disposition: AtomBindingDisposition
    reason_codes: tuple[str, ...]
    binding_digest: str
    schema_version: str = SOURCE_ATOM_BINDING_SCHEMA

    def __post_init__(self) -> None:
        candidate_present = (
            self.candidate_semantic_id is not None
            and self.candidate_abi_index is not None)
        if (not is_text(self.source_instance_id)
                or type(self.atom_index) is not int or self.atom_index < 0
                or not is_text(self.token) or not is_text(self.source_reference)
                or any(not isinstance(item, str) or not SHA256.fullmatch(item)
                       for item in (
                           self.source_evidence_digest, self.semantic_release,
                           self.a01_bundle_id, self.a01_source_bundle_id,
                           self.mapping_record_digest, self.rights_digest,
                           self.binding_digest))
                or not is_text(self.source_adapter_id)
                or (self.source_token_index is not None
                    and (type(self.source_token_index) is not int
                         or self.source_token_index < 0))
                or ((self.candidate_semantic_id is None)
                    != (self.candidate_abi_index is None))
                or (self.candidate_semantic_id is not None
                    and not is_text(self.candidate_semantic_id))
                or (self.candidate_abi_index is not None
                    and (type(self.candidate_abi_index) is not int
                         or self.candidate_abi_index < 0))
                or not isinstance(self.candidate_type_ids, tuple)
                or self.candidate_type_ids != tuple(sorted(set(self.candidate_type_ids)))
                or any(not is_text(item) for item in self.candidate_type_ids)
                or type(self.rights_epoch) is not int or self.rights_epoch < 0
                or type(self.correction_generation) is not int
                or self.correction_generation < 0
                or self.visible_at_prefix != self.atom_index + 1
                or not isinstance(self.disposition, AtomBindingDisposition)
                or not isinstance(self.reason_codes, tuple)
                or self.reason_codes != tuple(sorted(set(self.reason_codes)))
                or any(not is_text(item) for item in self.reason_codes)
                or self.schema_version != SOURCE_ATOM_BINDING_SCHEMA):
            invalid("BAMF_SOURCE_ATOM_BINDING_INVALID")
        if (self.disposition is AtomBindingDisposition.BOUND
                and (not candidate_present or not self.candidate_type_ids
                     or self.reason_codes)):
            invalid("BAMF_SOURCE_ATOM_BOUND_AUTHORITY_INVALID")
        if (self.disposition is AtomBindingDisposition.SOURCE_HELD
                and (not candidate_present or not self.reason_codes)):
            invalid("BAMF_SOURCE_ATOM_HELD_CANDIDATE_MISSING")
        if (self.disposition is AtomBindingDisposition.UNMAPPED
                and (candidate_present or not self.reason_codes)):
            invalid("BAMF_SOURCE_ATOM_UNMAPPED_HAS_CANDIDATE")
        if self.binding_digest != contract_digest(binding_projection(self)):
            invalid("BAMF_SOURCE_ATOM_BINDING_DIGEST_MISMATCH")


def make_binding(**values) -> SourceAtomBinding:
    digest = contract_digest(binding_values_projection(values))
    return SourceAtomBinding(binding_digest=digest, **values)
