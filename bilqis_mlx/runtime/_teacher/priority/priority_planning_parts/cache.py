"""Cache state and exact invalidation keys for accepted priority planning."""
from dataclasses import dataclass, field
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.priority_source_materialization_cache import (
    PrioritySourceMaterializationCache,
)


def _invalid(reason):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


def _emit_progress(progress, message):
    if progress is not None:
        progress(message)


@dataclass(frozen=True)
class PriorityPlanningEpoch:
    current_release: object
    candidate_set: object
    snapshot: object
    closure: object
    requested_keys: tuple
    accepted_credit: object | None
    autonomy_plan: object
    evidence_ledger: object
    checkpoint: object
    source_authority: object


@dataclass
class PriorityPlanningCache:
    """Process-live derived planning products with exact invalidation keys."""

    run_dir: Path
    static_hits: int = 0
    static_misses: int = 0
    snapshot_hits: int = 0
    snapshot_misses: int = 0
    closure_hits: int = 0
    closure_misses: int = 0
    planning_hits: int = 0
    planning_misses: int = 0
    source_materialization_cache: PrioritySourceMaterializationCache = field(
        default_factory=PrioritySourceMaterializationCache, repr=False)
    _static_key: tuple | None = field(default=None, init=False, repr=False)
    _candidate_set: object | None = field(default=None, init=False, repr=False)
    _candidate_frontier: object | None = field(default=None, init=False, repr=False)
    _staged_candidates: tuple | None = field(default=None, init=False, repr=False)
    _autonomy_plan: object | None = field(default=None, init=False, repr=False)
    _snapshot_key: tuple | None = field(default=None, init=False, repr=False)
    _snapshot: object | None = field(default=None, init=False, repr=False)
    _closure_key: tuple | None = field(default=None, init=False, repr=False)
    _closure: object | None = field(default=None, init=False, repr=False)
    _planning_key: tuple | None = field(default=None, init=False, repr=False)
    _planning: object | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.run_dir = Path(self.run_dir).resolve()

    def metrics(self) -> dict[str, int]:
        metrics = {
            "static_hits": self.static_hits,
            "static_misses": self.static_misses,
            "snapshot_hits": self.snapshot_hits,
            "snapshot_misses": self.snapshot_misses,
            "closure_hits": self.closure_hits,
            "closure_misses": self.closure_misses,
            "planning_hits": self.planning_hits,
            "planning_misses": self.planning_misses,
        }
        metrics.update({
            "source_materialization_" + name: value
            for name, value in self.source_materialization_cache.metrics().items()
        })
        return metrics


def _require_cache(cache, run_dir):
    if cache is None:
        return None
    if (type(cache) is not PriorityPlanningCache
            or cache.run_dir != Path(run_dir).resolve()):
        _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
    return cache


def _static_key(
        current, selection, feature_receipt, source, frontier_trust_identity):
    from bilqis_mlx.semantics.domains import contract_digest

    return (
        current.release_sha256,
        selection.bundle_id,
        selection.release_sha256,
        selection.source_bundle_id,
        feature_receipt.source_atlas_bundle_id,
        feature_receipt.source_release_sha256,
        feature_receipt.source_source_bundle_id,
        contract_digest(source.frontier),
        contract_digest(source.policy),
        source.authority_registry_sha256,
        frontier_trust_identity,
    )


def _closure_key(snapshot, current, plan, checkpoint, ledger):
    from bilqis_mlx.factory.autonomy import evidence_complete_capabilities

    mastered = evidence_complete_capabilities(
        current, ledger, plan=plan,
        current_checkpoint_sha256=checkpoint.sha256,
        current_optimizer_step=checkpoint.optimizer_step,
    )
    return (
        snapshot.snapshot_sha256,
        current.release_sha256,
        plan.digest(),
        checkpoint.sha256,
        checkpoint.optimizer_step,
        mastered,
    )


def _snapshot_key(static_key, feature_receipt):
    return (
        static_key,
        feature_receipt.generation_manifest_sha256,
        feature_receipt.acceptance_sha256,
    )


def _accepted_credit_key(accepted_credit):
    if accepted_credit is None:
        return None
    accepted_credit.__post_init__()
    from bilqis_mlx.semantics.domains import contract_digest
    return contract_digest((
        "bilqis.bamf.priority-accepted-credit-key/v1",
        accepted_credit.schema,
        accepted_credit.factory_release_sha256,
        accepted_credit.acceptance_sha256,
        accepted_credit.obligation_keys,
    ))


def _planning_key(epoch):
    return (
        epoch.current_release.release_sha256,
        epoch.snapshot.snapshot_sha256,
        epoch.closure.closure_sha256,
        epoch.requested_keys,
        _accepted_credit_key(epoch.accepted_credit),
    )
