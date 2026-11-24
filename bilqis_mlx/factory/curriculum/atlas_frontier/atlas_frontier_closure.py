"""A09.2 deterministic typed prerequisite closure over immutable snapshots."""
from bilqis_mlx.factory.autonomy import AutonomyPlan, EvidenceLedger
from .atlas_frontier_contracts import CurriculumSnapshot
from .skos_curriculum import (
    SOURCE_FAMILY_ADAPTERS, SemanticFamilyInventory, SourceFamilyAdapter,
)
from .atlas_frontier_closure_support import (
    CandidateClosure, ClosureReason, ClosureStatus, FrontierClosure, SourceHold,
    _coverage, _dependency_status, _direct_status, _graph, _merge_status, _rules,
    _source_holds, _verified_evidence_context,
    semantic_roots_for_mastered_capabilities,
)

def resolve_frontier_closure(
    snapshot: CurriculumSnapshot,
    census: SemanticFamilyInventory,
    domain_rule_registry: tuple[SourceFamilyAdapter, ...] = SOURCE_FAMILY_ADAPTERS,
    *,
    current_release=None,
    evidence_ledger: EvidenceLedger | None = None,
    autonomy_plan: AutonomyPlan | None = None,
    checkpoint_sha256: str | None = None,
    optimizer_step: int | None = None,
) -> FrontierClosure:
    """Return grade-neutral, constituent-first closure without ranking or admission."""
    return _resolve_frontier_closure(
        snapshot, census, domain_rule_registry,
        current_release=current_release,
        evidence_ledger=evidence_ledger,
        autonomy_plan=autonomy_plan,
        checkpoint_sha256=checkpoint_sha256,
        optimizer_step=optimizer_step,
        prevalidated=False,
    )


def resolve_frontier_closure_prevalidated(
    snapshot: CurriculumSnapshot,
    census: SemanticFamilyInventory,
    domain_rule_registry: tuple[SourceFamilyAdapter, ...] = SOURCE_FAMILY_ADAPTERS,
    *,
    current_release=None,
    evidence_ledger: EvidenceLedger | None = None,
    autonomy_plan: AutonomyPlan | None = None,
    checkpoint_sha256: str | None = None,
    optimizer_step: int | None = None,
) -> FrontierClosure:
    """Compute closure from exact owner-derived inputs without recursively proving them."""
    return _resolve_frontier_closure(
        snapshot, census, domain_rule_registry,
        current_release=current_release,
        evidence_ledger=evidence_ledger,
        autonomy_plan=autonomy_plan,
        checkpoint_sha256=checkpoint_sha256,
        optimizer_step=optimizer_step,
        prevalidated=True,
    )


def _resolve_frontier_closure(
    snapshot: CurriculumSnapshot,
    census: SemanticFamilyInventory,
    domain_rule_registry: tuple[SourceFamilyAdapter, ...],
    *,
    current_release,
    evidence_ledger,
    autonomy_plan,
    checkpoint_sha256,
    optimizer_step,
    prevalidated: bool,
) -> FrontierClosure:
    if type(snapshot) is not CurriculumSnapshot:
        _fail("BAMF_PLANNER_SNAPSHOT_INPUT_INVALID")
    if not prevalidated:
        snapshot.verify()
    rules = _rules(domain_rule_registry)
    evidence_semantic_ids, evidence_sha256 = _verified_evidence_context(
        snapshot,
        current_release,
        evidence_ledger,
        autonomy_plan,
        checkpoint_sha256,
        optimizer_step,
        verify_release=not prevalidated,
    )
    graph, order = _graph(snapshot)
    direct = _direct_status(snapshot, rules)
    resolved: dict[str, tuple[ClosureStatus, ...]] = {}
    candidates = []
    rows = _coverage(snapshot, census)
    families_by_semantic: dict[str, list[str]] = {}
    for semantic_id, family_id in rows:
        families_by_semantic.setdefault(semantic_id, []).append(family_id)
    families_by_semantic = {
        semantic_id: sorted(family_ids)
        for semantic_id, family_ids in families_by_semantic.items()
    }
    for semantic_id in order:
        current = []
        for family_id in families_by_semantic.get(semantic_id, ()):
            row = rows[(semantic_id, family_id)]
            status = direct[(semantic_id, family_id)]
            reasons = []
            if status is ClosureStatus.IMPLEMENTATION_UNCOVERED:
                reasons.append(ClosureReason(
                    "FAMILY_IMPLEMENTATION_UNCOVERED", f"family:{family_id}"))
            elif status is ClosureStatus.WAITING_FOR_EVIDENCE:
                reasons.append(ClosureReason("LEARNING_EVIDENCE_REQUIRED", "learner:evidence"))
            for prerequisite in graph[semantic_id]:
                blocked = _dependency_status(
                    resolved[prerequisite],
                    evidence_complete=prerequisite in evidence_semantic_ids,
                )
                if blocked is not None:
                    status = _merge_status(status, blocked)
                    reasons.append(ClosureReason(
                        "PREREQUISITE_" + blocked.value, "factory:prerequisite", prerequisite))
            candidates.append(CandidateClosure(
                semantic_id, family_id, row.source_evidence_sha256, status,
                graph[semantic_id], tuple(sorted(set(reasons)))))
            current.append(status)
        resolved[semantic_id] = tuple(current)
    provisional = FrontierClosure(
        snapshot.snapshot_sha256, evidence_sha256, tuple(sorted(rules)), order,
        tuple(sorted(candidates)), _source_holds(snapshot), "0" * 64)
    result = FrontierClosure(
        provisional.snapshot_sha256, provisional.prerequisite_evidence_sha256,
        provisional.rule_families,
        provisional.constituent_order, provisional.candidates,
        provisional.source_holds, provisional.expected_digest())
    if not prevalidated:
        result.verify()
    return result
