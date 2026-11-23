"""Source preparation and candidate-local reuse for Factory training."""
from __future__ import annotations

from dataclasses import dataclass, field

from bilqis_mlx.factory.teaching import DeliveredTeaching, content_digest
from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate
from bilqis_mlx.runtime.source_execution import SourceExecutionContext

from .atlas_training_contracts import BamfVisitProvenance, _invalid
from .factory_training_source import (
    _prepare_factory_source_rows,
    _prepare_learning_first_model_sources,
)
from .learning_first_source import prepare_learning_first_source_rows


@dataclass
class LearningFirstPreparationCache:
    """Candidate-local reuse of exact row preparation for ordinary learning."""

    _binding: tuple | None = None
    _rows: dict = field(default_factory=dict)
    _task_inputs: dict = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    task_hits: int = 0
    task_misses: int = 0

    def bind(self, source_context, authenticated) -> None:
        binding = (
            str(source_context.run_dir),
            source_context.release.release_sha256,
            authenticated.snapshot.release_sha256,
            authenticated.snapshot.bundle_id,
            authenticated.snapshot.source_bundle_id,
            authenticated.features.semantic_release,
            authenticated.features.digest,
        )
        if self._binding is None:
            self._binding = binding
        elif self._binding != binding:
            self._binding = binding
            self._rows.clear()
            self._task_inputs.clear()

    @staticmethod
    def key(row, eligibility_digest=None) -> str:
        suffix = "" if eligibility_digest is None else ":" + str(eligibility_digest)
        return content_digest((row,)) + suffix

    def get(self, row, eligibility_digest):
        value = self._rows.get(self.key(row, eligibility_digest))
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
        return value

    def put(self, row, eligibility_digest, model_source) -> None:
        self._rows[self.key(row, eligibility_digest)] = model_source

    def get_task_inputs(self, key):
        value = self._task_inputs.get(key)
        if value is None:
            self.task_misses += 1
        else:
            self.task_hits += 1
        return value

    def put_task_inputs(self, key, value) -> None:
        self._task_inputs[key] = value


def _target_source_count(rows, rehearsal_by_id):
    return len(rows) - len(rehearsal_by_id)


def _validated_training_request(
        source_context, candidate, delivered_rows, generation_binding, *,
        capability, delivery, requested_count, source_seed, source_each,
        optimizer_step_seed, visit_provenance, teacher_strategy,
        rehearsal_by_id=None):
    rows = tuple(delivered_rows) if isinstance(delivered_rows, (tuple, list)) else ()
    rehearsal_by_id = {} if rehearsal_by_id is None else dict(rehearsal_by_id)
    target_source_count = _target_source_count(rows, rehearsal_by_id)
    if (type(source_context) is not SourceExecutionContext
            or not isinstance(candidate, BamfBundleCandidate)
            or not rows or any(type(row) is not dict for row in rows)
            or not isinstance(capability, str) or not capability
            or not isinstance(delivery, DeliveredTeaching)
            or type(requested_count) is not int or requested_count < len(rows)
            or type(source_seed) is not int or source_seed < 0
            or type(source_each) is not int or source_each != target_source_count
            or target_source_count < 1
            or type(optimizer_step_seed) is not int or optimizer_step_seed < 0
            or type(visit_provenance) is not BamfVisitProvenance
            or visit_provenance.capability_id != capability
            or not isinstance(teacher_strategy, dict)
            or not isinstance(generation_binding, str) or not generation_binding
            or source_context.source_root is None):
        _invalid("FACTORY_TRAINING_BRIDGE_INPUT_INVALID")
    return rows


def _learning_first_source_inputs(
        source_context, authenticated, rows, *, source_seed, source_each,
        learning_first_cache):
    source_rows = prepare_learning_first_source_rows(
        source_context, authenticated, rows,
        source_seed=source_seed, source_each=source_each)
    if learning_first_cache is None:
        return source_rows, _prepare_learning_first_model_sources(
            authenticated, source_rows)
    if type(learning_first_cache) is not LearningFirstPreparationCache:
        _invalid("LEARNING_FIRST_PREPARATION_CACHE_INVALID")
    learning_first_cache.bind(source_context, authenticated)
    prepared_model_sources = []
    for row, source_row in zip(rows, source_rows, strict=True):
        eligibility_digest = source_row.projection.digest
        model_source = learning_first_cache.get(row, eligibility_digest)
        if model_source is None:
            model_source = _prepare_learning_first_model_sources(
                authenticated, (source_row,))[0]
            if model_source.eligibility_digest != eligibility_digest:
                _invalid("LEARNING_FIRST_PREPARATION_ELIGIBILITY_DRIFT")
            learning_first_cache.put(row, eligibility_digest, model_source)
        prepared_model_sources.append(model_source)
    return source_rows, tuple(prepared_model_sources)


def _prepared_source_inputs(
        prepared_source, source_context, authenticated, rows, *, capability,
        source_seed, source_each, delivery=None, rehearsal_by_id=None,
        rehearsal_bindings=None, rehearsal_authorities=None,
        selected_source_authority=None, learning_first_cache=None):
    if prepared_source is None:
        rehearsal_by_id = rehearsal_by_id or {}
        rehearsal_bindings = rehearsal_bindings or {}
        rehearsal_authorities = rehearsal_authorities or {}
        target_rows = tuple(row for row in rows if row.get("id") not in rehearsal_by_id)
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )
        strict = strict_evidence_enabled()
        if not strict:
            source_rows, prepared_model_sources = _learning_first_source_inputs(
                source_context, authenticated, rows,
                source_seed=source_seed, source_each=source_each,
                learning_first_cache=learning_first_cache)
            profile = source_rows[0].profile if len(source_rows) == 1 else None
            return (
                None, source_rows[0].source_adapter, None, profile, source_rows,
                prepared_model_sources, None, None, None,
            )
        source_authority = (
            source_context.bind_rows(
                target_rows, seed=source_seed, capability=capability, each=source_each)
            if delivery is None or len(delivery.specimen_ids) == len(target_rows) else
            source_context.bind_delivery_rows(
                target_rows, seed=source_seed, capability=capability,
                direct_each=len(delivery.specimen_ids)))
        for identity, authority in rehearsal_authorities.items():
            row = next((item for item in rows if item.get("id") == identity), None)
            binding = rehearsal_bindings.get(identity)
            if (row is None or not isinstance(binding, dict)
                    or authority.capability_id != binding.get("capability")
                    or authority.seed != binding.get("seed")
                    or authority.each != binding.get("each")):
                _invalid("FACTORY_REHEARSAL_SOURCE_AUTHORITY_INVALID")
            source_context.require_bound_rows((row,), authority)
        adapter, manifest, profile, source_rows = _prepare_factory_source_rows(
            source_context, authenticated, rows, capability=capability,
            source_seed=source_seed, source_each=source_each,
            source_authority=source_authority,
            source_authorities_by_id=rehearsal_authorities,
            source_bindings_by_id=rehearsal_bindings,
            issue_b11_proofs=strict)
        from bilqis_mlx.runtime.priority_source_materialization import (
            _prepare_model_sources,
        )
        prepared_model_sources, _configs = _prepare_model_sources(
            source_context, authenticated, manifest, source_rows)
        return (
            source_authority,
            adapter, manifest, profile, source_rows, prepared_model_sources,
            None, None, None,
        )
    from bilqis_mlx.runtime.priority_source_materialization import (
        PreparedPrioritySourceMaterialization,
    )
    if (type(prepared_source) is not PreparedPrioritySourceMaterialization
            or prepared_source.semantic_context is not authenticated
            or prepared_source.offer.capability_id != capability
            or prepared_source.offer.source_seed != source_seed
            or prepared_source.offer.source_each != source_each
            or prepared_source.rows != rows):
        _invalid("FACTORY_TRAINING_PREPARED_SOURCE_INVALID")
    prepared_source.require_current()
    source_context.require_bound_rows(
        rows, prepared_source.offer.source_authority)
    return (
        prepared_source.offer.source_authority,
        prepared_source.adapter,
        prepared_source.manifest,
        prepared_source.profile,
        prepared_source.source_rows,
        prepared_source.model_sources,
        prepared_source.motif_inputs,
        prepared_source.b11_sources,
        prepared_source.packed_owner,
    )


__all__ = (
    "LearningFirstPreparationCache", "_prepared_source_inputs",
    "_validated_training_request",
)
