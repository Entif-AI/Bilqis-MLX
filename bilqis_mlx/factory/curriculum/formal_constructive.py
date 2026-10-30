"""A08 formal source/operator resolution, not a lesson or rights grant.

A01 owns which Boolean/numeric semantic IDs exist. A07 owns pure
operator signatures and source contracts. A13 owns live permissions.
This module joins the first two without claiming the third.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas_projection import AbiEntry, FormalDomainBinding
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from bilqis_mlx.semantics.cognitive_operators import (
    CognitiveOperatorSpec, OperatorRegistry, operator_grant_digest,
)
from bilqis_mlx.semantics.core import Signature
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.foundation import numeric as released_numeric


FORMAL_SOURCE_SCHEMA = "bilqis.formal-source-operator-proposal/v1"
FORMAL_SOURCE_SET_SCHEMA = "bilqis.formal-source-operator-set-proposal/v1"
FORMAL_SOURCE_ONLY = "SOURCE_BOUND_NOT_EXECUTABLE"
SOURCE_PROJECTION_ONLY = "SOURCE_PROJECTION_NOT_AUTHORITY"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_OPERATOR_SUFFIX = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_PREFIXES = {
    "boolean": ("legacy:cogal.operator.", "urn:formal:boolean:"),
    "numeric": ("bilqis.numeric/v1:school.op.", "urn:formal:numeric:"),
}
_FORMAL_ABI_SOURCES = frozenset({
    "FORMAL_DOMAIN", "PRIOR_ACCEPTED_NATIVE_REGISTRY"})
_NUMERIC_SOURCE_OWNER = "bilqis_mlx/semantics/numeric_v1.json"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _strict_formal_primitive(value: object) -> object:
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is tuple:
        return [_strict_formal_primitive(item) for item in value]
    if type(value) in {
            FormalSourceOperator, FormalSourceOperatorSet,
            CognitiveOperatorSpec, Signature}:
        return {field.name: _strict_formal_primitive(getattr(value, field.name))
                for field in fields(value)}
    _fail("BAMF_FORMAL_SOURCE_PROPOSAL_NONCANONICAL_TYPE")


def _strict_formal_bytes(value: object) -> bytes:
    return (json.dumps(
        _strict_formal_primitive(value), sort_keys=True,
        ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")


@dataclass(frozen=True)
class FormalSourceOperator:
    semantic_id: str
    family: str
    abi_index: int
    operator: CognitiveOperatorSpec
    source_binding_sha256: str
    operator_grant_sha256: str
    capability_ids: tuple[str, ...]
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = FORMAL_SOURCE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_id, str) or not self.semantic_id
                or self.family not in _PREFIXES
                or type(self.abi_index) is not int or self.abi_index < 0
                or not isinstance(self.operator, CognitiveOperatorSpec)
                or any(not isinstance(value, str) or not _SHA.fullmatch(value)
                       for value in (
                           self.source_binding_sha256, self.operator_grant_sha256))
                or not isinstance(self.capability_ids, tuple)
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != FORMAL_SOURCE_SCHEMA):
            _fail("BAMF_FORMAL_SOURCE_RECORD_INVALID")


@dataclass(frozen=True)
class FormalSourceOperatorSet:
    semantic_release: str
    atlas_bundle_id: str
    witnesses: tuple[FormalSourceOperator, ...]
    uncovered: tuple[tuple[str, str], ...]
    status: str = FORMAL_SOURCE_ONLY
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = FORMAL_SOURCE_SET_SCHEMA

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
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != FORMAL_SOURCE_SET_SCHEMA):
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


def _numeric_source_signature(
    binding: FormalDomainBinding, semantic_id: str,
) -> Signature | None:
    """Return the exact released numeric signature, never infer it from a label."""
    if binding.family != "numeric":
        return None
    if binding.source_owner != _NUMERIC_SOURCE_OWNER:
        return None
    payload = released_numeric.CONTRACT_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != binding.source_sha256:
        _fail("BAMF_FORMAL_SOURCE_BINDING_DRIFT")
    node = next(
        (item for item in released_numeric.CONTRACT["append_only_nodes"]
         if item.get("semantic_id") == semantic_id),
        None,
    )
    if node is None or not isinstance(node.get("signature"), str):
        return None
    return Signature.parse(node["signature"])


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
            source_signature = _numeric_source_signature(binding, semantic_id)
            if binding.family == "numeric" and source_signature is None:
                uncovered.append(
                    (semantic_id, "SOURCE_SIGNATURE_UNAVAILABLE"))
                continue
            if source_signature is not None and source_signature != spec.signature:
                uncovered.append(
                    (semantic_id, "OPERATOR_SOURCE_SIGNATURE_MISMATCH"))
                continue
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
    return _resolve_from_bindings(
        snapshot.formal_domain_bindings, snapshot.abi_entries, registry,
        semantic_release=snapshot.release_sha256,
        atlas_bundle_id=snapshot.bundle_id)


def assert_formal_source_operator_set_current(
    proposal: FormalSourceOperatorSet,
    atlas: AtlasArtifactSelection,
    registry: OperatorRegistry,
) -> None:
    """No reusable source credential: rederive the entire A01/A07 join."""
    if (type(proposal) is not FormalSourceOperatorSet
            or _strict_formal_bytes(proposal)
            != _strict_formal_bytes(
                resolve_formal_source_operators(atlas, registry))):
        _fail("BAMF_FORMAL_SOURCE_PROPOSAL_DRIFT")
