"""A08 formal source/operator resolution, not a lesson or rights grant.

A01 owns which Boolean/numeric semantic IDs exist. A07 owns pure
operator signatures and source contracts. A13 owns live permissions.
This module joins the first two without claiming the third.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas_projection import AbiEntry, FormalDomainBinding
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from bilqis_mlx.semantics.cognitive_operators import (
    CognitiveOperatorSpec, OperatorRegistry, operator_grant_digest,
)
from bilqis_mlx.semantics.domains import contract_digest


FORMAL_SOURCE_SCHEMA = "bilqis.formal-source-operator/v1"
FORMAL_SOURCE_UNVERIFIED_SCHEMA = "bilqis.formal-source-operator-unverified/v1"
FORMAL_SOURCE_SET_SCHEMA = "bilqis.formal-source-operator-set/v1"
FORMAL_SOURCE_SET_UNVERIFIED_SCHEMA = (
    "bilqis.formal-source-operator-set-unverified/v1")
FORMAL_SOURCE_ONLY = "SOURCE_BOUND_NOT_EXECUTABLE"
SOURCE_AUTHORITY_UNVERIFIED = "UNVERIFIED_SOURCE_PROJECTION"
SOURCE_AUTHORITY_PINNED = "A01_PINNED_SOURCE_ATTESTED"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_OPERATOR_SUFFIX = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_PREFIXES = {
    "boolean": ("legacy:cogal.operator.", "urn:formal:boolean:"),
    "numeric": ("bilqis.numeric/v1:school.op.", "urn:formal:numeric:"),
}
_FORMAL_ABI_SOURCES = frozenset({
    "FORMAL_DOMAIN", "PRIOR_ACCEPTED_NATIVE_REGISTRY"})


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


@dataclass(frozen=True)
class FormalSourceOperator:
    semantic_id: str
    family: str
    abi_index: int
    operator: CognitiveOperatorSpec
    source_binding_sha256: str
    operator_grant_sha256: str
    capability_ids: tuple[str, ...]
    source_authority: str = SOURCE_AUTHORITY_UNVERIFIED
    schema: str = FORMAL_SOURCE_UNVERIFIED_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_id, str) or not self.semantic_id
                or self.family not in _PREFIXES
                or type(self.abi_index) is not int or self.abi_index < 0
                or not isinstance(self.operator, CognitiveOperatorSpec)
                or any(not isinstance(value, str) or not _SHA.fullmatch(value)
                       for value in (
                           self.source_binding_sha256, self.operator_grant_sha256))
                or not isinstance(self.capability_ids, tuple)
                or (self.source_authority, self.schema) not in {
                    (SOURCE_AUTHORITY_UNVERIFIED, FORMAL_SOURCE_UNVERIFIED_SCHEMA),
                    (SOURCE_AUTHORITY_PINNED, FORMAL_SOURCE_SCHEMA)}):
            _fail("BAMF_FORMAL_SOURCE_RECORD_INVALID")


@dataclass(frozen=True)
class FormalSourceOperatorSet:
    semantic_release: str
    atlas_bundle_id: str
    witnesses: tuple[FormalSourceOperator, ...]
    uncovered: tuple[tuple[str, str], ...]
    status: str = FORMAL_SOURCE_ONLY
    source_authority: str = SOURCE_AUTHORITY_UNVERIFIED
    schema: str = FORMAL_SOURCE_SET_UNVERIFIED_SCHEMA

    def __post_init__(self) -> None:
        ids = tuple(item.semantic_id for item in self.witnesses)
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not isinstance(self.atlas_bundle_id, str)
                or not _SHA.fullmatch(self.atlas_bundle_id)
                or any(not isinstance(item, FormalSourceOperator)
                       or item.source_authority != self.source_authority
                       for item in self.witnesses)
                or len(ids) != len(set(ids))
                or tuple(sorted(ids)) != ids
                or not isinstance(self.uncovered, tuple)
                or self.status != FORMAL_SOURCE_ONLY
                or (self.source_authority, self.schema) not in {
                    (SOURCE_AUTHORITY_UNVERIFIED,
                     FORMAL_SOURCE_SET_UNVERIFIED_SCHEMA),
                    (SOURCE_AUTHORITY_PINNED, FORMAL_SOURCE_SET_SCHEMA)}):
            _fail("BAMF_FORMAL_SOURCE_SET_INVALID")

    @property
    def digest(self) -> str:
        return contract_digest(self)


def _operator_id(family: str, semantic_id: str) -> str | None:
    for prefix in _PREFIXES.get(family, ()):
        if semantic_id.startswith(prefix):
            suffix = semantic_id[len(prefix):]
            if _OPERATOR_SUFFIX.fullmatch(suffix):
                return "BOOL_" + suffix if family == "boolean" else suffix
    return None


def _resolve_from_bindings(
    bindings: tuple[FormalDomainBinding, ...],
    abi_entries: tuple[AbiEntry, ...],
    registry: OperatorRegistry,
    *, semantic_release: str, atlas_bundle_id: str,
) -> FormalSourceOperatorSet:
    """Pure A01/A07 contract join. No solver, evaluator or A13 grant is called."""
    if (not isinstance(registry, OperatorRegistry)
            or registry.semantic_release != semantic_release
            or not _SHA.fullmatch(semantic_release)
            or not _SHA.fullmatch(atlas_bundle_id)):
        _fail("BAMF_FORMAL_SOURCE_RELEASE_MISMATCH")
    by_id = {entry.semantic_id: entry for entry in abi_entries}
    available = {spec.operator_id for spec in registry.specs}
    witnesses = []
    uncovered = []
    seen = set()
    for binding in bindings:
        if binding.family not in _PREFIXES:
            uncovered.extend(
                (semantic_id, "FORMAL_FAMILY_UNSUPPORTED")
                for semantic_id in binding.semantic_ids)
            continue
        for semantic_id in binding.semantic_ids:
            if semantic_id in seen:
                _fail("BAMF_FORMAL_SOURCE_ID_DUPLICATE")
            seen.add(semantic_id)
            abi = by_id.get(semantic_id)
            if (abi is None or abi.source not in _FORMAL_ABI_SOURCES
                    or not abi.active):
                uncovered.append((semantic_id, "FORMAL_ABI_NOT_ACTIVE"))
                continue
            operator_id = _operator_id(binding.family, semantic_id)
            if operator_id is None or operator_id not in available:
                uncovered.append((semantic_id, "OPERATOR_UNREGISTERED"))
                continue
            spec = registry.resolve(operator_id)
            witnesses.append(FormalSourceOperator(
                semantic_id, binding.family, abi.index, spec,
                contract_digest(binding), operator_grant_digest(spec),
                binding.capability_ids))
    return FormalSourceOperatorSet(
        semantic_release, atlas_bundle_id,
        tuple(sorted(witnesses, key=lambda item: item.semantic_id)),
        tuple(sorted(uncovered)))


def resolve_formal_source_operators(
    atlas: AtlasArtifactSelection,
    registry: OperatorRegistry,
) -> FormalSourceOperatorSet:
    """Resolve only independently pinned A01 identities against A07 contracts."""
    snapshot = load_pinned_atlas_snapshot(atlas)
    raw = _resolve_from_bindings(
        snapshot.formal_domain_bindings, snapshot.abi_entries, registry,
        semantic_release=snapshot.release_sha256,
        atlas_bundle_id=snapshot.bundle_id)
    return replace(
        raw,
        witnesses=tuple(
            replace(item, source_authority=SOURCE_AUTHORITY_PINNED,
                    schema=FORMAL_SOURCE_SCHEMA)
            for item in raw.witnesses),
        source_authority=SOURCE_AUTHORITY_PINNED,
        schema=FORMAL_SOURCE_SET_SCHEMA)
