"""Fail-closed A05 raw-atom handoff toward B02/B03 semantic embeddings.

Current source adapters can prove source rows and A01 can prove semantic ABI
rows, but no production source owner currently issues the raw ``SourceAtom``
``source_reference``/grant bridge between those authorities.  This module
therefore records verified candidates without converting them to ``ConceptRef``
or embedding authority.  A future source-owner bridge can add a BOUND path
without changing the held handoff schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from ..errors import BilqisError, ErrorBus, SEMANTIC_FRAME
from .atlas_projection import FrozenAtlasSnapshot
from .domains import contract_digest
from .frame_compiler import (
    CompiledFrameBatch, FrameCompilerConfig, PositionKind,
    _grant_allows, atom_evidence_digest,
)


SOURCE_ROW_WITNESS_SCHEMA = "bilqis.source-row-token-witness/v1"
SOURCE_ATOM_BINDING_SCHEMA = "bilqis.source-atom-semantic-binding/v1"
SOURCE_ATOM_HANDOFF_SCHEMA = "bilqis.source-atom-semantic-handoff/v1"
SOURCE_ATOM_RIGHTS_SCHEMA = "bilqis.source-atom-rights-state/v1"
SOURCE_ATOM_MAPPING_SCHEMA = "bilqis.source-atom-mapping-record/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<source-atom-binding>",
        span_start=0, span_end=0,
    )


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


class AtomBindingDisposition(str, Enum):
    BOUND = "BOUND"
    SOURCE_HELD = "SOURCE_HELD"
    UNMAPPED = "UNMAPPED"


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
        if (not all(_text(item) for item in (
                self.source_adapter_id, self.generator_id, self.oracle_id,
                self.capability_id, self.source_sense_id))
                or not isinstance(self.token_indices, tuple)
                or not self.token_indices
                or any(type(item) is not int or item < 0
                       for item in self.token_indices)
                or self.schema_version != SOURCE_ROW_WITNESS_SCHEMA):
            _invalid("BAMF_SOURCE_ATOM_ROW_WITNESS_INVALID")

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


def _binding_projection(binding: "SourceAtomBinding") -> tuple:
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


def _binding_values_projection(values: dict) -> tuple:
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
        if (not _text(self.source_instance_id)
                or type(self.atom_index) is not int or self.atom_index < 0
                or not _text(self.token) or not _text(self.source_reference)
                or any(not isinstance(item, str) or not _SHA.fullmatch(item)
                       for item in (
                           self.source_evidence_digest, self.semantic_release,
                           self.a01_bundle_id, self.a01_source_bundle_id,
                           self.mapping_record_digest, self.rights_digest,
                           self.binding_digest))
                or not _text(self.source_adapter_id)
                or (self.source_token_index is not None
                    and (type(self.source_token_index) is not int
                         or self.source_token_index < 0))
                or ((self.candidate_semantic_id is None)
                    != (self.candidate_abi_index is None))
                or (self.candidate_semantic_id is not None
                    and not _text(self.candidate_semantic_id))
                or (self.candidate_abi_index is not None
                    and (type(self.candidate_abi_index) is not int
                         or self.candidate_abi_index < 0))
                or not isinstance(self.candidate_type_ids, tuple)
                or self.candidate_type_ids != tuple(sorted(set(self.candidate_type_ids)))
                or any(not _text(item) for item in self.candidate_type_ids)
                or type(self.rights_epoch) is not int or self.rights_epoch < 0
                or type(self.correction_generation) is not int
                or self.correction_generation < 0
                or self.visible_at_prefix != self.atom_index + 1
                or not isinstance(self.disposition, AtomBindingDisposition)
                or not isinstance(self.reason_codes, tuple)
                or self.reason_codes != tuple(sorted(set(self.reason_codes)))
                or any(not _text(item) for item in self.reason_codes)
                or self.schema_version != SOURCE_ATOM_BINDING_SCHEMA):
            _invalid("BAMF_SOURCE_ATOM_BINDING_INVALID")
        if (self.disposition is AtomBindingDisposition.BOUND
                and (not candidate_present or not self.candidate_type_ids
                     or self.reason_codes)):
            _invalid("BAMF_SOURCE_ATOM_BOUND_AUTHORITY_INVALID")
        if (self.disposition is AtomBindingDisposition.SOURCE_HELD
                and (not candidate_present or not self.reason_codes)):
            _invalid("BAMF_SOURCE_ATOM_HELD_CANDIDATE_MISSING")
        if (self.disposition is AtomBindingDisposition.UNMAPPED
                and (candidate_present or not self.reason_codes)):
            _invalid("BAMF_SOURCE_ATOM_UNMAPPED_HAS_CANDIDATE")
        if self.binding_digest != contract_digest(_binding_projection(self)):
            _invalid("BAMF_SOURCE_ATOM_BINDING_DIGEST_MISMATCH")


def _handoff_projection(handoff: "SourceAtomHandoff") -> tuple:
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


def _handoff_values_projection(values: dict) -> tuple:
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
        if (not _text(self.source_instance_id)
                or type(self.visible_end) is not int or self.visible_end < 0
                or any(not isinstance(item, str) or not _SHA.fullmatch(item)
                       for item in (
                           self.semantic_release, self.a01_bundle_id,
                           self.a01_source_bundle_id, self.digest))
                or not _text(self.source_adapter_id)
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
            _invalid("BAMF_SOURCE_ATOM_HANDOFF_INVALID")
        for item in self.bindings:
            item.__post_init__()
        if self.digest != contract_digest(_handoff_projection(self)):
            _invalid("BAMF_SOURCE_ATOM_HANDOFF_DIGEST_MISMATCH")

    @property
    def embedding_ready(self) -> bool:
        return bool(self.bindings) and all(
            item.disposition is AtomBindingDisposition.BOUND
            for item in self.bindings)


def _rights_digest(config: FrameCompilerConfig, atom, source_id: str) -> tuple[str, bool]:
    evidence = atom_evidence_digest(source_id, atom, config.task.semantic_release)
    grant = next((item for item in config.frontier.grants
                  if item.source_handle == atom.source_reference), None)
    task = config.task
    state = (
        SOURCE_ATOM_RIGHTS_SCHEMA,
        (
            task.principal_id, task.tenant_id, task.purpose,
            task.semantic_release, task.jurisdiction, task.scope,
            task.observed_frontier, task.effective_time,
        ),
        config.policy,
        config.frontier.rights_epoch,
        config.frontier.correction_generation,
        grant,
    )
    return contract_digest(state), _grant_allows(
        grant, evidence, config, config.task.semantic_release)


def _make_binding(**values) -> SourceAtomBinding:
    digest = contract_digest(_binding_values_projection(values))
    return SourceAtomBinding(binding_digest=digest, **values)


def _make_handoff(**values) -> SourceAtomHandoff:
    digest = contract_digest(_handoff_values_projection(values))
    return SourceAtomHandoff(digest=digest, **values)


def _resolve_visible_atoms(
    compiled: CompiledFrameBatch,
    config: FrameCompilerConfig,
    snapshot: FrozenAtlasSnapshot,
    witness: SourceRowWitness,
    graph: dict,
) -> SourceAtomHandoff:
    """Resolve only candidates; no current path may mint a BOUND atom."""
    if (type(compiled) is not CompiledFrameBatch
            or type(config) is not FrameCompilerConfig
            or type(snapshot) is not FrozenAtlasSnapshot
            or type(witness) is not SourceRowWitness
            or not isinstance(graph, dict)
            or not isinstance(graph.get("tokens"), list)
            or compiled.semantic_release != snapshot.release_sha256
            or config.task.semantic_release != compiled.semantic_release
            or config.schema_map.semantic_release != compiled.semantic_release
            or config.frontier.rights_epoch != config.policy.rights_epoch):
        _invalid("BAMF_SOURCE_ATOM_AUTHORITY_INPUT_INVALID")
    compiled.__post_init__()
    config.__post_init__()
    witness.__post_init__()
    atoms = tuple(
        item.atom for item in compiled.positions
        if item.kind is PositionKind.ATOM)
    if (len(atoms) != compiled.visible_end
            or tuple(atom.index for atom in atoms) != tuple(range(compiled.visible_end))):
        _invalid("BAMF_SOURCE_ATOM_COMPILED_PREFIX_INVALID")

    bindings = []
    for atom in atoms:
        rights_digest, rights_ok = _rights_digest(
            config, atom, compiled.source_instance_id)
        source_evidence = atom_evidence_digest(
            compiled.source_instance_id, atom, compiled.semantic_release)
        reasons = set()
        token_index = None
        candidate_semantic_id = None
        candidate_abi_index = None
        candidate_type_ids: tuple[str, ...] = ()

        if atom.index >= len(witness.token_indices):
            reasons.add("SOURCE_ATOM_ROW_POSITION_UNMAPPED")
        else:
            token_index = witness.token_indices[atom.index]
            graph_tokens = graph.get("tokens")
            if (token_index >= len(graph_tokens)
                    or graph_tokens[token_index] != atom.token):
                reasons.add("SOURCE_ATOM_ROW_TOKEN_MISMATCH")
            else:
                try:
                    entry = snapshot.abi(token_index)
                except BilqisError:
                    entry = None
                if (entry is None or entry.symbol != atom.token or not entry.active):
                    reasons.add("SOURCE_ATOM_A01_ABI_UNMAPPED")
                else:
                    candidate_semantic_id = entry.semantic_id
                    candidate_abi_index = entry.index
                    concept = next((item for item in snapshot.concepts
                                    if item.concept.semantic_id == entry.semantic_id), None)
                    if concept is not None:
                        candidate_type_ids = tuple(sorted(set(concept.concept.types)))
                    if not candidate_type_ids:
                        reasons.add("SOURCE_ATOM_TYPE_AUTHORITY_UNAVAILABLE")

        if not rights_ok:
            reasons.add("SOURCE_ATOM_CURRENT_RIGHTS_HELD")

        candidate_present = candidate_semantic_id is not None
        if candidate_present:
            # The source row proves its ordered token and A01 proves the ABI row,
            # but no live producer owns the raw SourceAtom reference/grant join.
            # Do not promote that missing law from string equality.
            reasons.add("SOURCE_ATOM_REFERENCE_AUTHORITY_UNAVAILABLE")
            reasons.add("SOURCE_ATOM_INSTANCE_AUTHORITY_UNAVAILABLE")
            disposition = AtomBindingDisposition.SOURCE_HELD
        else:
            disposition = AtomBindingDisposition.UNMAPPED

        mapping_digest = witness.mapping_digest(
            atom.index,
            token_index if token_index is not None else 0,
            atom.token,
        )
        bindings.append(_make_binding(
            source_instance_id=compiled.source_instance_id,
            atom_index=atom.index,
            token=atom.token,
            source_reference=atom.source_reference,
            source_evidence_digest=source_evidence,
            semantic_release=compiled.semantic_release,
            a01_bundle_id=snapshot.bundle_id,
            a01_source_bundle_id=snapshot.source_bundle_id,
            source_adapter_id=witness.source_adapter_id,
            source_token_index=token_index,
            mapping_record_digest=mapping_digest,
            candidate_semantic_id=candidate_semantic_id,
            candidate_abi_index=candidate_abi_index,
            candidate_type_ids=candidate_type_ids,
            rights_epoch=config.frontier.rights_epoch,
            correction_generation=config.frontier.correction_generation,
            rights_digest=rights_digest,
            visible_at_prefix=atom.index + 1,
            disposition=disposition,
            reason_codes=tuple(sorted(reasons)),
        ))
    return _make_handoff(
        source_instance_id=compiled.source_instance_id,
        visible_end=compiled.visible_end,
        semantic_release=compiled.semantic_release,
        a01_bundle_id=snapshot.bundle_id,
        a01_source_bundle_id=snapshot.source_bundle_id,
        source_adapter_id=witness.source_adapter_id,
        bindings=tuple(bindings),
    )


def _revalidate_from_verified_snapshot(
    handoff: SourceAtomHandoff,
    compiled: CompiledFrameBatch,
    config: FrameCompilerConfig,
    snapshot: FrozenAtlasSnapshot,
    witness: SourceRowWitness,
    graph: dict,
) -> SourceAtomHandoff:
    expected = _resolve_visible_atoms(compiled, config, snapshot, witness, graph)
    if handoff != expected:
        _invalid("BAMF_SOURCE_ATOM_HANDOFF_AUTHORITY_DRIFT")
    return expected


def require_embedding_ready(
    handoff: SourceAtomHandoff,
    compiled: CompiledFrameBatch,
    config: FrameCompilerConfig,
    snapshot: FrozenAtlasSnapshot,
    witness: SourceRowWitness,
    graph: dict,
) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """Internal B02/B03 seam: held/unmapped atoms can never authorize raw vectors."""
    expected = _revalidate_from_verified_snapshot(
        handoff, compiled, config, snapshot, witness, graph)
    if not expected.embedding_ready:
        _invalid("BAMF_SOURCE_ATOM_BINDING_HELD")
    return tuple(
        (item.candidate_abi_index, item.candidate_type_ids)
        for item in expected.bindings
        if item.candidate_abi_index is not None)
