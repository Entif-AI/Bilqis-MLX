"""Source-owned rows prepared before a C03 priority policy is selected."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import time
from pathlib import Path

from bilqis_mlx.runtime.source_execution import SourceBatchAuthority, SourceExecutionContext, _invalid_source_batch
from bilqis_mlx.semantics.domains import contract_digest
from .priority_planning_generation import (
    PriorityPlanningGeneration,
    _PLANNING_ISSUER,
    _current_cache,
    _require_planning_generation,
    _require_planning_generation_identity,
    bind_priority_planning_generation,
)

_ISSUER = object()


def _json_value(value):
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_json_value(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _json_value(item) for key, item in value.items())
    return False


def _canonical_rows(rows):
    if (type(rows) is not tuple or not rows
            or any(type(row) is not dict or not _json_value(row) for row in rows)):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_ROWS_INVALID')
    try:
        wire = json.dumps(rows, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        wire.encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_ROWS_INVALID')
    return wire


def _decode_rows(wire):
    try:
        rows = tuple(json.loads(wire))
        if _canonical_rows(rows) != wire:
            _invalid_source_batch('BAMF_PRIORITY_SOURCE_ROWS_INVALID')
        return rows
    except (ValueError, TypeError):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_ROWS_INVALID')


@dataclass(frozen=True, init=False, eq=False)
class PreparedPrioritySourceOffer:
    source_authority: SourceBatchAuthority
    accepted_manifest_sha256: str
    generation_binding: str
    release_sha256: str
    capability_id: str
    source_seed: int
    source_each: int
    source_family_id: str
    source_binding_digest: str
    _rows_json: str = field(repr=False)
    _rows_sha256: str = field(repr=False)
    _rows_direct: tuple | None = field(repr=False, compare=False)
    _run_dir: Path = field(repr=False)
    _materialized: dict = field(repr=False, compare=False)
    _materialization_cache: object = field(repr=False, compare=False)
    _qualification_owner: object = field(repr=False, compare=False)
    _learning_first: bool = field(repr=False, compare=False)
    _planning_generation: PriorityPlanningGeneration = field(repr=False, compare=False)
    _issuance: object = field(repr=False)

    def __init__(self, *args, **kwargs):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_CALLER_CONSTRUCTION_FORBIDDEN')

    def _validate(self):
        if (getattr(self, '_issuance', None) is not _ISSUER
                or type(self.source_authority) is not SourceBatchAuthority
                or self.source_authority.release_sha256 != self.release_sha256
                or self.source_authority.capability_id != self.capability_id
                or self.source_authority.seed != self.source_seed
                or self.source_authority.each != self.source_each
                or self.source_authority.source_family_id != self.source_family_id
                or type(self._materialized) is not dict
                or any(key != 'value' for key in self._materialized)
                or type(self._learning_first) is not bool
                or (not self._learning_first and self._qualification_owner is None)
                or (self._learning_first and self._qualification_owner is not None)
                or type(self._planning_generation) is not PriorityPlanningGeneration
                or getattr(self._planning_generation, '_issuance', None) is not _PLANNING_ISSUER):
            _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_INVALID')
        if self._learning_first:
            if (type(self._rows_direct) is not tuple
                    or len(self._rows_direct) != self.source_each
                    or any(type(row) is not dict for row in self._rows_direct)):
                _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_INVALID')
        elif (self._rows_direct is not None
                or hashlib.sha256(self._rows_json.encode('utf-8')).hexdigest()
                != self._rows_sha256):
            _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_INVALID')
        if self._materialization_cache is not None:
            from .priority_source_materialization_cache import (
                PrioritySourceMaterializationCache,
            )
            if type(self._materialization_cache) is not PrioritySourceMaterializationCache:
                _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_INVALID')
        if not self._learning_first:
            self.source_authority.__post_init__()

    def rows(self):
        self._validate()
        if self._learning_first:
            return self._rows_direct
        return _decode_rows(self._rows_json)

    def require_current_parent(self, source_context):
        self._validate()
        parent = self._planning_generation._parent
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_mode_enabled,
        )
        require_generation = (
            _require_planning_generation
            if strict_mode_enabled() else _require_planning_generation_identity)
        cache, _authenticated = require_generation(
            self._planning_generation, source_context, parent)
        return parent, cache

    def require_qualified_current(self, source_context, parent, *, prepared_rows=None):
        """Verify source qualification/currentness without rebuilding source content."""
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_mode_enabled,
        )
        strict = strict_mode_enabled()
        if not strict:
            self._validate()
            cache, _authenticated = _require_planning_generation_identity(
                self._planning_generation, source_context, parent)
            if (Path(source_context.run_dir).resolve() != self._run_dir
                    or cache.accepted_manifest_sha256 != self.accepted_manifest_sha256
                    or cache.generation_binding != self.generation_binding
                    or source_context.release.release_sha256 != self.release_sha256
                    or self.capability_id
                    not in source_context.release.execution_plan.capability_map):
                _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_STALE')
            return self.rows() if prepared_rows is None else tuple(prepared_rows)
        stage_started = time.perf_counter()
        self._validate()
        offer_validate_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        require_generation = (
            _require_planning_generation
            if strict else _require_planning_generation_identity)
        cache, _authenticated = require_generation(
            self._planning_generation, source_context, parent)
        planning_generation_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        if (Path(source_context.run_dir).resolve() != self._run_dir
                or cache.accepted_manifest_sha256 != self.accepted_manifest_sha256
                or cache.generation_binding != self.generation_binding
                or source_context.release.release_sha256 != self.release_sha256
                or self.capability_id not in source_context.release.execution_plan.capability_map
                or contract_digest(source_context.release.source_bindings.by_capability[self.capability_id])
                != self.source_binding_digest):
            _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_STALE')
        static_binding_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        rows = self.rows() if prepared_rows is None else tuple(prepared_rows)
        row_decode_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        source_context.require_bound_rows(rows, self.source_authority)
        row_authority_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        if _canonical_rows(rows) != self._rows_json:
            _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_ROWS_DRIFT')
        row_canonical_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        self._qualification_owner.require()
        qualification_owner_seconds = time.perf_counter() - stage_started
        object.__setattr__(self, "_performance_observation", {
            "source_currentness_offer_validate_wall_seconds": float(
                offer_validate_seconds),
            "source_currentness_planning_generation_wall_seconds": float(
                planning_generation_seconds),
            "source_currentness_static_binding_wall_seconds": float(
                static_binding_seconds),
            "source_currentness_row_decode_wall_seconds": float(
                row_decode_seconds),
            "source_currentness_row_authority_wall_seconds": float(
                row_authority_seconds),
            "source_currentness_row_canonical_wall_seconds": float(
                row_canonical_seconds),
            "source_currentness_qualification_owner_wall_seconds": float(
                qualification_owner_seconds),
        })
        return rows

    def require_current(self, source_context, parent, *, prepared_rows=None):
        """Materialize the selected source once, then revalidate its cached owners."""
        from .priority_source_materialization import (
            prepare_priority_source_materialization,
        )
        return prepare_priority_source_materialization(
            self, source_context, parent, prepared_rows=prepared_rows)


def prepare_priority_source_offer(source_context, parent, atlas_artifact_path, *,
                                  capability, source_seed, source_each,
                                  planning_generation=None,
                                  materialization_cache=None):
    """Issue a current, source-qualified offer without constructing a teacher visit."""
    if planning_generation is None:
        planning_generation = bind_priority_planning_generation(
            source_context, parent, atlas_artifact_path)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    strict = strict_mode_enabled()
    require_generation = (
        _require_planning_generation
        if strict else _require_planning_generation_identity)
    cache, authenticated = require_generation(
        planning_generation, source_context, parent)
    if (not isinstance(capability, str) or not capability
            or type(source_seed) is not int or source_seed < 0
            or type(source_each) is not int or source_each < 1
            or capability not in source_context.release.execution_plan.capability_map
            or source_context.source_root is None):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_OFFER_INPUT_INVALID')
    rows, authority = source_context.draw_bound_rows(
        seed=source_seed, capability=capability, each=source_each)
    if len(rows) != source_each:
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_ROWS_INVALID')
    if authenticated.receipt.generation_manifest_sha256 != cache.accepted_manifest_sha256:
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_ACCEPTED_GENERATION_DRIFT')
    qualification_owner = None
    if strict:
        wire = _canonical_rows(rows)
        rows_sha256 = hashlib.sha256(wire.encode('utf-8')).hexdigest()
        rows_direct = None
        from bilqis_mlx.runtime.salience_evidence_owner import SalienceEvidenceArtifactOwner
        qualification_owner = SalienceEvidenceArtifactOwner.for_source_qualification(
            authority, rows, authenticated.features.semantic_release)
    else:
        wire = ''
        rows_sha256 = ''
        rows_direct = tuple(rows)
    offer = object.__new__(PreparedPrioritySourceOffer)
    for name, value in (
        ('source_authority', authority), ('accepted_manifest_sha256', cache.accepted_manifest_sha256),
        ('generation_binding', cache.generation_binding), ('release_sha256', source_context.release.release_sha256),
        ('capability_id', capability), ('source_seed', source_seed), ('source_each', source_each),
        ('source_family_id', authority.source_family_id),
        ('source_binding_digest', contract_digest(source_context.release.source_bindings.by_capability[capability])),
        ('_rows_json', wire), ('_rows_sha256', rows_sha256),
        ('_rows_direct', rows_direct),
        ('_run_dir', Path(source_context.run_dir).resolve()), ('_materialized', {}),
        ('_materialization_cache', materialization_cache),
        ('_qualification_owner', qualification_owner),
        ('_learning_first', not strict),
        ('_planning_generation', planning_generation),
        ('_issuance', _ISSUER)):
        object.__setattr__(offer, name, value)
    if strict:
        planning_generation._target_registrar.register(
            'SALIENCE_EVIDENCE', qualification_owner)
        offer.require_qualified_current(source_context, parent)
    else:
        offer._validate()
    return offer


def expand_selected_priority_source_offer(
        offer, source_context, parent, *, source_each):
    """Reissue one selected planning offer at its full training-row authority."""
    if (type(offer) is not PreparedPrioritySourceOffer
            or type(source_each) is not int
            or source_each < offer.source_each):
        _invalid_source_batch('BAMF_PRIORITY_SELECTED_SOURCE_EXPANSION_INVALID')
    if source_each == offer.source_each:
        offer.require_qualified_current(source_context, parent)
        return offer
    expanded = prepare_priority_source_offer(
        source_context, parent, None,
        capability=offer.capability_id,
        source_seed=offer.source_seed,
        source_each=source_each,
        planning_generation=offer._planning_generation,
        materialization_cache=offer._materialization_cache)
    continuity_fields = (
        'accepted_manifest_sha256', 'generation_binding', 'release_sha256',
        'capability_id', 'source_seed', 'source_family_id', 'source_binding_digest',
    )
    if (expanded._planning_generation is not offer._planning_generation
            or any(getattr(expanded, name) != getattr(offer, name)
                   for name in continuity_fields)
            or expanded.source_authority.provider_id
            != offer.source_authority.provider_id
            or expanded.source_authority.provider_implementation_sha256
            != offer.source_authority.provider_implementation_sha256):
        _invalid_source_batch('BAMF_PRIORITY_SELECTED_SOURCE_EXPANSION_DRIFT')
    return expanded


__all__ = (
    'PreparedPrioritySourceOffer', 'PrioritySourceIntent',
    'plan_priority_source_intent', 'materialize_priority_source_intent',
    'prepare_priority_source_offer', 'expand_selected_priority_source_offer',
)

from bilqis_mlx.runtime._learning_first.priority_source_intent import (
    PrioritySourceIntent,
    materialize_priority_source_intent,
    plan_priority_source_intent,
)
