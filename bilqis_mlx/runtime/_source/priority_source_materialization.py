"""Visit-scoped heavy source preparation for one selected C03 offer."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import time

from bilqis_mlx.runtime.source_execution import _invalid_source_batch
from bilqis_mlx.runtime.priority_source_materialization_cache import (
    PreparedPrioritySourceArtifacts,
    priority_source_materialization_identity,
    rebind_priority_source_rows,
)
from bilqis_mlx.semantics.frame_compiler import (
    CompiledFrameRows, validate_partial_visible_forest,
)
from bilqis_mlx.source_adapters.atoms.admission import (
    authorize_public_formal_prefix,
)


@dataclass(frozen=True)
class PreparedPrioritySourceMaterialization:
    """Immutable source/compiler inputs shared by every candidate step in a visit."""

    offer: object
    rows: tuple
    adapter: object
    manifest: object
    profile: object
    source_rows: tuple
    model_sources: tuple
    motif_inputs: tuple
    b11_sources: tuple
    prefixes: tuple
    semantic_context: object
    feature_owner: object
    packed_owner: object
    source_owner: object
    _registered: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self):
        count = len(self.rows)
        if (count < 1
                or any(type(value) is not tuple for value in (
                    self.rows, self.source_rows, self.model_sources,
                    self.motif_inputs, self.b11_sources, self.prefixes))
                or any(len(value) != count for value in (
                    self.source_rows, self.model_sources, self.motif_inputs,
                    self.b11_sources, self.prefixes))):
            _invalid_source_batch("BAMF_PRIORITY_SOURCE_MATERIALIZATION_INVALID")

    def require_current(self):
        started = time.perf_counter()
        self.__post_init__()
        stage_started = time.perf_counter()
        self.feature_owner.require(self.semantic_context.features)
        feature_owner_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        self.source_owner.require()
        source_owner_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        for source in self.b11_sources:
            source.require_current()
        b11_sources_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        for prefix in self.prefixes:
            self.packed_owner.require_row(prefix)
        packed_frames_seconds = time.perf_counter() - stage_started
        total_seconds = time.perf_counter() - started
        measured_seconds = (
            feature_owner_seconds + source_owner_seconds
            + b11_sources_seconds + packed_frames_seconds)
        object.__setattr__(self, "_performance_observation", {
            "source_currentness_feature_owner_wall_seconds": float(
                feature_owner_seconds),
            "source_currentness_source_owner_wall_seconds": float(
                source_owner_seconds),
            "source_currentness_b11_sources_wall_seconds": float(
                b11_sources_seconds),
            "source_currentness_packed_frames_wall_seconds": float(
                packed_frames_seconds),
            "source_currentness_materialized_other_wall_seconds": float(max(
                0.0, total_seconds - measured_seconds)),
        })
        return self


def _prepare_model_sources(source_context, authenticated, manifest, source_rows):
    from bilqis_mlx.runtime.atlas_training_adapter import (
        prepare_model_source_input,
    )

    prepared, configs, atlas_features = [], [], None
    for item in source_rows:
        visible = tuple(item.row["tokens"])
        frames = (() if item.projection is None else item.projection.envelopes)
        current, atlas_features = prepare_model_source_input(
            item.row, item.row["capability"], visible,
            source_context=source_context, source_ast=item.ast, frames=frames,
            task_scope=item.task, source_frontier=item.frontier,
            eligibility_policy=item.policy, compiler_config=item.config,
            atlas_selection=authenticated.selection, feature_artifact_path=None,
            semantic_context=authenticated,
            released_manifest=getattr(item, "manifest", manifest),
            atlas_features=atlas_features,
            prepared_inventory=item.source_inventory,
            source_graph=item.source_graph)
        config = (item.config if item.projection is None
                  else replace(item.config, approved=item.projection))
        config = authorize_public_formal_prefix(item.ast, current.prefix, config)
        if item.projection is not None:
            validate_partial_visible_forest(current.prefix, item.ast, config)
        prepared.append(current)
        configs.append(config)
    return tuple(prepared), tuple(configs)


def _owners(offer, authenticated, rows, prefixes):
    from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
    from bilqis_mlx.runtime.atlas_packed_frame_owner import PackedFrameArtifactOwner
    from bilqis_mlx.runtime.salience_evidence_owner import SalienceEvidenceArtifactOwner

    width = max(len(prefix.positions) for prefix in prefixes)
    compiled = CompiledFrameRows(
        prefixes,
        tuple(prefix.positions + (None,) * (width - len(prefix.positions))
              for prefix in prefixes),
        tuple((True,) * len(prefix.positions) + (False,) * (width - len(prefix.positions))
              for prefix in prefixes))
    return (
        AtlasFeatureArtifactOwner(authenticated.features, authenticated.schema),
        PackedFrameArtifactOwner(compiled),
        SalienceEvidenceArtifactOwner.for_source_offer(
            offer.source_authority, rows, prefixes),
    )


def _build_prepared_artifacts(
        offer, source_context, authenticated, rows, *, identity=()):
    from bilqis_mlx.runtime.factory_training_bridge import _prepare_factory_source_rows

    timings = {}
    stage_started = time.perf_counter()
    source_context._source_preparation_metrics.source_context_builds += 1
    adapter, manifest, profile, source_rows = _prepare_factory_source_rows(
        source_context, authenticated, rows, capability=offer.capability_id,
        source_seed=offer.source_seed, source_each=offer.source_each,
        source_authority=offer.source_authority)
    timings["source_materialization_factory_source_wall_seconds"] = (
        time.perf_counter() - stage_started)
    if len({tuple(item.row["tokens"]) for item in source_rows}) != len(rows):
        _invalid_source_batch("FACTORY_TRAINING_AMBIGUOUS_SOURCE_PREFIX")

    stage_started = time.perf_counter()
    model_sources, b11_configs = _prepare_model_sources(
        source_context, authenticated, manifest, source_rows)
    timings["source_materialization_model_source_wall_seconds"] = (
        time.perf_counter() - stage_started)
    if (len(model_sources) != len(source_rows)
            or len(b11_configs) != len(source_rows)):
        _invalid_source_batch("BAMF_PRIORITY_SOURCE_MATERIALIZATION_INVALID")

    prefixes = tuple(item.prefix for item in model_sources)
    source_context._source_preparation_metrics.compiled_source_builds += 1
    artifacts = PreparedPrioritySourceArtifacts(
        identity, manifest, source_rows, model_sources, b11_configs, prefixes)
    if identity:
        artifacts.require_exact(offer)
    return artifacts, timings, adapter, profile


def _prepared_artifacts(offer, source_context, authenticated, rows):
    cache = getattr(offer, "_materialization_cache", None)
    identity = (
        priority_source_materialization_identity(offer)
        if cache is not None else ())
    lookup_started = time.perf_counter()
    artifacts = None if cache is None else cache.get(identity)
    timings = {
        "source_materialization_cache_lookup_wall_seconds": (
            time.perf_counter() - lookup_started),
        "source_materialization_cache_hit": int(artifacts is not None),
        "source_materialization_wait_wall_seconds": 0.0,
    }
    if artifacts is None:
        artifacts, build_timings, adapter, profile = _build_prepared_artifacts(
            offer, source_context, authenticated, rows, identity=identity)
        timings.update(build_timings)
        if cache is None:
            return artifacts, timings, adapter, profile, artifacts.source_rows
        cache.put(artifacts)
    else:
        artifacts.require_exact(offer)
    adapter, profile, source_rows = rebind_priority_source_rows(
        offer, source_context, authenticated, rows, artifacts)
    return artifacts, timings, adapter, profile, source_rows


def _register_and_require(offer, materialized):
    registration_seconds = 0.0
    if not materialized._registered:
        started = time.perf_counter()
        registrar = offer._planning_generation._target_registrar
        for kind, owner in (
                ("ATLAS_FEATURE", materialized.feature_owner),
                ("PACKED_FRAME", materialized.packed_owner),
                ("SALIENCE_EVIDENCE", materialized.source_owner)):
            registrar.register(kind, owner)
        object.__setattr__(materialized, "_registered", True)
        registration_seconds = time.perf_counter() - started
    materialized = materialized.require_current()
    observation = dict(
        getattr(materialized, "_performance_observation", {}) or {})
    observation["source_currentness_registration_wall_seconds"] = float(
        registration_seconds)
    object.__setattr__(
        materialized, "_performance_observation", observation)
    return materialized


def _attach_currentness_observation(
        materialized, qualification_seconds, qualification_observation, started,
        materialization_observation=None):
    observation = dict(getattr(materialized, "_performance_observation", {}) or {})
    observation.update(materialization_observation or {})
    observation["source_currentness_qualification_wall_seconds"] = float(
        qualification_seconds)
    observation.update(qualification_observation)
    direct_currentness_seconds = sum(float(observation.get(key, 0.0) or 0.0) for key in (
        "source_currentness_feature_owner_wall_seconds",
        "source_currentness_source_owner_wall_seconds",
        "source_currentness_b11_sources_wall_seconds",
        "source_currentness_packed_frames_wall_seconds",
        "source_currentness_materialized_other_wall_seconds",
        "source_currentness_registration_wall_seconds",
    ))
    finished = time.perf_counter()
    total_seconds = max(0.0, finished - started)
    observation["source_currentness_internal_other_wall_seconds"] = float(max(
        0.0, total_seconds - qualification_seconds - direct_currentness_seconds))
    observation["source_materialization_total_wall_seconds"] = float(total_seconds)
    object.__setattr__(materialized, "_performance_observation", observation)
    return materialized


def prepare_priority_source_materialization(
        offer, source_context, parent, *, prepared_rows=None):
    """Build source AST/formal/prefix state once after the option is selected."""
    started = time.perf_counter()
    stage_started = time.perf_counter()
    rows = offer.require_qualified_current(
        source_context, parent, prepared_rows=prepared_rows)
    qualification_seconds = time.perf_counter() - stage_started
    qualification_observation = dict(
        getattr(offer, "_performance_observation", {}) or {})
    cached = offer._materialized.get("value")
    if cached is not None:
        if (type(cached) is not PreparedPrioritySourceMaterialization
                or cached.offer is not offer or cached.rows != rows):
            _invalid_source_batch("BAMF_PRIORITY_SOURCE_MATERIALIZATION_DRIFT")
        materialized = _register_and_require(offer, cached)
        return _attach_currentness_observation(
            materialized, qualification_seconds, qualification_observation, started)

    authenticated = offer._planning_generation._authenticated_features
    artifacts, materialization_observation, adapter, profile, source_rows = _prepared_artifacts(
        offer, source_context, authenticated, rows)
    from bilqis_mlx.runtime.factory_training_bridge import (
        _motif_planning_input, _prepare_b11_source_binding,
    )
    b11_started = time.perf_counter()
    b11_sources = tuple(
        _prepare_b11_source_binding(
            source_context, authenticated, profile, item,
            model.prefix, config,
            source_seed=getattr(item, "source_seed", offer.source_seed),
            source_each=getattr(item, "source_each", offer.source_each))
        for item, model, config in zip(
            source_rows, artifacts.model_sources, artifacts.b11_configs)
    )
    materialization_observation["source_materialization_b11_binding_wall_seconds"] = (
        time.perf_counter() - b11_started)
    motif_started = time.perf_counter()
    motif_inputs = tuple(_motif_planning_input(
        source_context, authenticated, item.source_adapter,
        getattr(item, "profile", profile), item,
        source_seed=getattr(item, "source_seed", offer.source_seed),
        source_each=getattr(item, "source_each", offer.source_each))
        for item in source_rows)
    materialization_observation["source_materialization_motif_planning_wall_seconds"] = (
        time.perf_counter() - motif_started)
    owner_started = time.perf_counter()
    feature_owner, packed_owner, source_owner = _owners(
        offer, authenticated, rows, artifacts.prefixes)
    materialization_observation["source_materialization_owner_build_wall_seconds"] = (
        time.perf_counter() - owner_started)
    materialized = PreparedPrioritySourceMaterialization(
        offer, rows, adapter, artifacts.manifest, profile,
        source_rows, artifacts.model_sources, motif_inputs,
        b11_sources, artifacts.prefixes, authenticated, feature_owner,
        packed_owner, source_owner)
    offer._materialized["value"] = materialized
    currentness_started = time.perf_counter()
    materialized = _register_and_require(offer, materialized)
    materialization_observation[
        "source_materialization_registration_currentness_wall_seconds"] = (
            time.perf_counter() - currentness_started)
    return _attach_currentness_observation(
        materialized, qualification_seconds, qualification_observation, started,
        materialization_observation)


def source_materialization_observation(offer) -> dict:
    materialized = getattr(offer, "_materialized", {}).get("value")
    return ({} if type(materialized) is not PreparedPrioritySourceMaterialization else
            dict(getattr(materialized, "_performance_observation", {}) or {}))


__all__ = (
    "PreparedPrioritySourceMaterialization",
    "prepare_priority_source_materialization",
    "source_materialization_observation",
)
