"""Metadata-only source intent used before ordinary priority selection."""
from dataclasses import dataclass, field
from pathlib import Path

from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
    strict_mode_enabled,
)
from bilqis_mlx.runtime.priority_planning_generation import (
    PriorityPlanningGeneration,
    _PLANNING_ISSUER,
    _require_planning_generation_identity,
    bind_priority_planning_generation,
)
from bilqis_mlx.runtime.source_execution import _invalid_source_batch
from bilqis_mlx.semantics.domains import contract_digest


_INTENT_ISSUER = object()


@dataclass(frozen=True, init=False, eq=False)
class PrioritySourceIntent:
    accepted_manifest_sha256: str
    generation_binding: str
    release_sha256: str
    capability_id: str
    source_seed: int
    source_each: int
    source_binding_digest: str
    _run_dir: Path = field(repr=False)
    _materialization_cache: object = field(repr=False, compare=False)
    _planning_generation: PriorityPlanningGeneration = field(repr=False, compare=False)
    _issuance: object = field(repr=False)

    def __init__(self, *args, **kwargs):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_CALLER_CONSTRUCTION_FORBIDDEN')

    def _validate(self):
        if (getattr(self, '_issuance', None) is not _INTENT_ISSUER
                or not all(isinstance(value, str) and value for value in (
                    self.accepted_manifest_sha256, self.generation_binding,
                    self.release_sha256, self.capability_id,
                    self.source_binding_digest))
                or type(self.source_seed) is not int or self.source_seed < 0
                or type(self.source_each) is not int or self.source_each < 1
                or type(self._planning_generation) is not PriorityPlanningGeneration
                or getattr(self._planning_generation, '_issuance', None) is not _PLANNING_ISSUER):
            _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_INVALID')
        if self._materialization_cache is not None:
            from bilqis_mlx.runtime.priority_source_materialization_cache import (
                PrioritySourceMaterializationCache,
            )
            if type(self._materialization_cache) is not PrioritySourceMaterializationCache:
                _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_INVALID')
        return self


def plan_priority_source_intent(source_context, parent, atlas_artifact_path, *,
                                capability, source_seed, source_each,
                                planning_generation=None,
                                materialization_cache=None):
    if strict_mode_enabled():
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_STRICT_MODE_FORBIDDEN')
    if planning_generation is None:
        planning_generation = bind_priority_planning_generation(
            source_context, parent, atlas_artifact_path)
    cache, _authenticated = _require_planning_generation_identity(
        planning_generation, source_context, parent)
    if (not isinstance(capability, str) or not capability
            or type(source_seed) is not int or source_seed < 0
            or type(source_each) is not int or source_each < 1
            or capability not in source_context.release.execution_plan.capability_map):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_INPUT_INVALID')
    binding_digest = contract_digest(
        source_context.release.source_bindings.by_capability[capability])
    intent = object.__new__(PrioritySourceIntent)
    for name, value in (
        ('accepted_manifest_sha256', cache.accepted_manifest_sha256),
        ('generation_binding', cache.generation_binding),
        ('release_sha256', source_context.release.release_sha256),
        ('capability_id', capability), ('source_seed', source_seed),
        ('source_each', source_each), ('source_binding_digest', binding_digest),
        ('_run_dir', Path(source_context.run_dir).resolve()),
        ('_materialization_cache', materialization_cache),
        ('_planning_generation', planning_generation), ('_issuance', _INTENT_ISSUER),
    ):
        object.__setattr__(intent, name, value)
    return intent._validate()


def materialize_priority_source_intent(
        intent, source_context, parent, *, source_each=None):
    if type(intent) is not PrioritySourceIntent:
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_REQUIRED')
    if strict_mode_enabled():
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_STRICT_MODE_FORBIDDEN')
    intent._validate()
    cache, _authenticated = _require_planning_generation_identity(
        intent._planning_generation, source_context, parent)
    each = intent.source_each if source_each is None else source_each
    if (type(each) is not int or each < intent.source_each
            or Path(source_context.run_dir).resolve() != intent._run_dir
            or source_context.release.release_sha256 != intent.release_sha256
            or cache.accepted_manifest_sha256 != intent.accepted_manifest_sha256
            or cache.generation_binding != intent.generation_binding
            or contract_digest(source_context.release.source_bindings.by_capability[
                intent.capability_id]) != intent.source_binding_digest):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_STALE')
    from bilqis_mlx.runtime.priority_source_offer import prepare_priority_source_offer
    offer = prepare_priority_source_offer(
        source_context, parent, None,
        capability=intent.capability_id, source_seed=intent.source_seed,
        source_each=each, planning_generation=intent._planning_generation,
        materialization_cache=intent._materialization_cache)
    if (offer.accepted_manifest_sha256 != intent.accepted_manifest_sha256
            or offer.generation_binding != intent.generation_binding
            or offer.release_sha256 != intent.release_sha256
            or offer.capability_id != intent.capability_id
            or offer.source_seed != intent.source_seed
            or offer.source_binding_digest != intent.source_binding_digest):
        _invalid_source_batch('BAMF_PRIORITY_SOURCE_INTENT_MATERIALIZATION_DRIFT')
    return offer


__all__ = (
    'PrioritySourceIntent', 'plan_priority_source_intent',
    'materialize_priority_source_intent',
)
