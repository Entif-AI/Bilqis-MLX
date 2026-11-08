"""Accepted-generation C09 correction and revalidation ingress."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .accepted_correction_ledger import (
    accepted_correction_id, accepted_corrections, append_record,
    CONTEXT_INVALIDATION_EVENT, context_invalidation_record,
    context_revalidation_record, correction_record, read_records,
    revalidation_record,
)
from .accepted_stale_replay_ledger import (
    derived_claim_record, remediation_record,
)
from .accepted_correction_runtime import (
    _RUNTIME_OWNER, bind_accepted_registry, register_accepted_target,
    register_compiled_batch, register_solve_context, runtime,
)
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_source_authority import SourceAuthorityRegistry
from .context_revalidation import (
    ContextRevalidatedArtifact, ContextRevalidationFrontier,
)
from .atlas_stale_replay import DerivedClaim, RemediationReceipt
from bilqis_mlx.semantics.cognitive_dependencies import (
    DependencyKind, DependencyRef,
)


@dataclass(frozen=True)
class AcceptedRuntimeHost:
    """Host-owned production ingress for one accepted run's C09 authority."""

    run_dir: Path
    registry: SourceAuthorityRegistry

    def __post_init__(self) -> None:
        if not isinstance(self.run_dir, Path) or not isinstance(
                self.registry, SourceAuthorityRegistry):
            _invalid("BAMF_C09_ACCEPTED_RUNTIME_HOST_INVALID")
        from bilqis_mlx.runtime.bamf_bundle.admission import (
            bind_accepted_correction_authority,
        )
        bind_accepted_correction_authority(self.run_dir, self.registry)

    def source_context(self, receipt: dict, *, graph: dict, source_root: Path | None):
        """Mint the admitted host context without granting authority to workers."""
        from bilqis_mlx.factory.live_answers import live_answer_registry
        from bilqis_mlx.runtime.source_execution import SourceExecutionContext
        from bilqis_mlx.source_adapters.school import live_source_registry

        return SourceExecutionContext.from_admitted_release(
            self.run_dir, receipt, graph=graph, source_root=source_root,
            source_registry=live_source_registry(),
            answer_registry=live_answer_registry(),
            correction_registry=self.registry,
            accepted_runtime_host=self,
        )

    def record_correction(self, event: CorrectionEvent) -> str:
        return record_accepted_correction(self.run_dir, event, self.registry)

    def record_context_transition(self, previous, contexts, *caller_state):
        return record_accepted_context_transition(
            self.run_dir, previous, contexts, *caller_state)

    def record_context_revalidation(
        self, frontier: ContextRevalidationFrontier,
    ) -> str:
        return record_accepted_context_revalidation(
            self.run_dir, frontier, self.registry)

    def record_revalidation(self, frontier: RevalidationFrontier) -> str:
        return record_accepted_revalidation(self.run_dir, frontier, self.registry)

    def record_remediation(self, remediation: RemediationReceipt) -> str:
        return record_accepted_remediation(self.run_dir, remediation, self.registry)

    def record_derived_claim(self, claim: DerivedClaim):
        return record_accepted_derived_claim(self.run_dir, claim, self.registry)

    def cache_inference(
        self, artifact, expected_binding, *, cached_infer, fp32_recompute,
        quality_check, policy, eligibility_source=None,
    ):
        """Consume exact-cache state through the same accepted host authority."""
        from bilqis_mlx.runtime.bamf_bundle.admission import (
            interactive_accepted_cache_inference,
        )
        return interactive_accepted_cache_inference(
            self.run_dir, self.registry, artifact, expected_binding,
            cached_infer=cached_infer, fp32_recompute=fp32_recompute,
            quality_check=quality_check, policy=policy,
            eligibility_source=eligibility_source,
        )


def record_accepted_correction(
    run_dir: Path, event: CorrectionEvent,
    registry: SourceAuthorityRegistry,
) -> str:
    """Persist and synchronously deliver one signed correction to live owners."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

    if not isinstance(event, CorrectionEvent):
        _invalid("BAMF_C09_CORRECTION_EVENT_REQUIRED")
    registry.verify_correction(event)
    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    record = correction_record(cache.accepted_manifest_sha256, event)
    append_record(run_dir, cache.accepted_manifest_sha256, record)
    runtime(run_dir, cache.accepted_manifest_sha256).deliver(
        record["event_id"], event, registry)
    object.__setattr__(cache, "_correction_registry", registry)
    return record["event_id"]


def record_accepted_context_transition(
    run_dir: Path, previous, contexts, *caller_state,
):
    """Persist only source-authorized A13 invalidations without correction authority."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
    from bilqis_mlx.factory.skos_curriculum.source_context import (
        SourceLessonContexts, source_lesson_expiry_task,
    )
    from bilqis_mlx.semantics.context_eligibility import transition_context
    from bilqis_mlx.semantics.context_eligibility import SourceFrontier

    if (caller_state or type(contexts) is not SourceLessonContexts
            or contexts.transition_authority is None):
        _invalid("BAMF_C09_CONTEXT_TRANSITION_AUTHORITY_REQUIRED")
    contexts.__post_init__()
    authority = contexts.transition_authority
    source_frontier = SourceFrontier(
        authority.frontier.rights_epoch,
        authority.frontier.correction_generation,
        contexts.grants,
    )
    task_scope = source_lesson_expiry_task(
        contexts, authority.task, source_frontier, authority.policy)
    frames = (contexts.positive.envelope, contexts.contrast.envelope)

    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    transition = transition_context(
        previous, frames, task_scope, source_frontier, authority.policy)
    if not transition.invalidations:
        return transition
    retained = runtime(run_dir, cache.accepted_manifest_sha256)
    for event in transition.invalidations:
        record = context_invalidation_record(
            cache.accepted_manifest_sha256, event, authority)
        append_record(run_dir, cache.accepted_manifest_sha256, record)
        retained.deliver_context_invalidation(record["event_id"], event)
    return transition


def record_accepted_revalidation(
    run_dir: Path, frontier: RevalidationFrontier,
    registry: SourceAuthorityRegistry,
) -> str:
    """Persist signed source recomputation evidence and advance live holds."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

    if not isinstance(frontier, RevalidationFrontier) or not frontier.results:
        _invalid("BAMF_C09_REVALIDATION_FRONTIER_REQUIRED")
    for result in frontier.results:
        registry.verify_revalidation(result)
    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    corrections = {
        event.event_id: event
        for _event_id, event in accepted_corrections(
            run_dir, cache.accepted_manifest_sha256, registry)
    }
    for result in frontier.results:
        correction = corrections.get(result.correction_event_id)
        if (correction is None
                or correction.source_receipt_sha256
                != result.correction_receipt_sha256):
            _invalid("BAMF_C09_REVALIDATION_CORRECTION_MISSING")
    record = revalidation_record(cache.accepted_manifest_sha256, frontier)
    append_record(run_dir, cache.accepted_manifest_sha256, record)
    runtime(run_dir, cache.accepted_manifest_sha256).deliver_revalidation(
        record["event_id"], frontier, registry)
    object.__setattr__(cache, "_correction_registry", registry)
    return record["event_id"]


def record_accepted_context_revalidation(
    run_dir: Path, frontier: ContextRevalidationFrontier,
    registry: SourceAuthorityRegistry,
) -> str:
    """Persist source-signed context recomputation without inventing a correction."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

    if (not isinstance(frontier, ContextRevalidationFrontier)
            or not frontier.results):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_FRONTIER_REQUIRED")
    if not isinstance(registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    records = read_records(run_dir, cache.accepted_manifest_sha256)
    invalidations = {
        item["context_invalidation"]["context_event_id"]: item
        for item in records
        if item["event"] == CONTEXT_INVALIDATION_EVENT
    }
    for result in frontier.results:
        invalidation = invalidations.get(result.context_event_id)
        if (invalidation is None
                or invalidation["event_id"]
                != result.context_invalidation_receipt_sha256):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_INVALIDATION_MISSING")
        registry.verify_detached(
            result.source_owner,
            DependencyRef(DependencyKind.ARTIFACT, result.artifact_id),
            result.source_signature_hex,
            result.signing_bytes(),
        )
    record = context_revalidation_record(
        cache.accepted_manifest_sha256, frontier)
    append_record(run_dir, cache.accepted_manifest_sha256, record)
    runtime(run_dir, cache.accepted_manifest_sha256).deliver_context_revalidation(
        record["event_id"], frontier, registry)
    object.__setattr__(cache, "_correction_registry", registry)
    return record["event_id"]


def record_accepted_remediation(
    run_dir: Path, remediation: RemediationReceipt,
    registry: SourceAuthorityRegistry,
) -> str:
    """Persist one claimed repair outcome against an accepted signed correction."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

    if not isinstance(remediation, RemediationReceipt):
        _invalid("BAMF_C09_REMEDIATION_RECEIPT_INVALID")
    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    corrections = {
        event.event_id: event
        for _event_id, event in accepted_corrections(
            run_dir, cache.accepted_manifest_sha256, registry)
    }
    correction = corrections.get(remediation.correction_event_id)
    if (correction is None
            or correction.source_receipt_sha256
            != remediation.correction_receipt_sha256):
        _invalid("BAMF_C09_REMEDIATION_CORRECTION_MISSING")
    record = remediation_record(cache.accepted_manifest_sha256, remediation)
    append_record(run_dir, cache.accepted_manifest_sha256, record)
    retained = runtime(run_dir, cache.accepted_manifest_sha256)
    retained.bind_registry(registry)
    from .accepted_stale_replay_runtime import replay_stale_evidence
    replay_stale_evidence(retained)
    return record["event_id"]


def record_accepted_derived_claim(
    run_dir: Path, claim: DerivedClaim,
    registry: SourceAuthorityRegistry,
) -> tuple[str, tuple[object, ...]]:
    """Persist later evidence and classify any proven post-remediation stale replay."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

    if not isinstance(claim, DerivedClaim):
        _invalid("BAMF_C09_DERIVED_CLAIM_INVALID")
    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    record = derived_claim_record(cache.accepted_manifest_sha256, claim)
    append_record(run_dir, cache.accepted_manifest_sha256, record)
    retained = runtime(run_dir, cache.accepted_manifest_sha256)
    retained.bind_registry(registry)
    from .accepted_stale_replay_runtime import replay_stale_evidence
    results = replay_stale_evidence(retained)
    return record["event_id"], results


__all__ = (
    "AcceptedRuntimeHost", "_RUNTIME_OWNER", "accepted_correction_id",
    "accepted_corrections", "ContextRevalidatedArtifact",
    "ContextRevalidationFrontier",
    "bind_accepted_registry", "record_accepted_correction",
    "record_accepted_context_transition",
    "record_accepted_context_revalidation",
    "record_accepted_derived_claim", "record_accepted_remediation",
    "record_accepted_revalidation", "register_accepted_target",
    "register_compiled_batch", "register_solve_context",
)
