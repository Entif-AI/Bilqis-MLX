"""C05 prospective FOUNDATION target assessment, before candidate execution."""
from dataclasses import dataclass, replace
from weakref import WeakKeyDictionary

from bilqis_mlx.runtime._factory_retention_support import (
    C05_FRESH_TARGET_SEED_OFFSET, C05_PROBE_EACH, _cohort, _fresh_rows, _instruments,
)
from bilqis_mlx.runtime.baseline.currentness import baseline_coverage
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLedger
from bilqis_mlx.runtime.capability_retention import EvidenceKind, evaluate_capabilities
from bilqis_mlx.runtime.capability_evaluation import _invalid
from bilqis_mlx.runtime.factory_complete_solver import (
    factory_complete_solver, factory_evaluation_case_from_source,
)
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.semantics.domains import contract_digest

from .local_screen_support import comparison_epoch, foundation_policy, split_cached_rows


_ISSUED = WeakKeyDictionary()


def prospective_seed(release, identity, cadence, journal_ordinal, plan, target_plan):
    return int(contract_digest({
        "schema": "bilqis.mlx.c05-prospective-target-seed/v2",
        "release": release.release_sha256,
        "visit": identity.visit_id,
        "phase": cadence["phase_sha256"],
        "journal_ordinal": journal_ordinal,
        "plan": plan.digest,
        "scope": target_plan.comparison_scope_sha256,
        "source": plan.source_sha256,
        "rubric": plan.rubric_sha256,
    })[:16], 16)


@dataclass(frozen=True, eq=False)
class ProspectiveTarget:
    binding: tuple
    seed: int
    rows: tuple
    assessment: object
    coverage: object
    comparison: object
    visit: object
    cadence: dict
    journal_ordinal: int
    release_sha256: str
    plan_sha256: str

    @property
    def skip(self):
        correct, total = self.assessment.score(self.visit.capability_id)
        return (self.visit.capability_id in self.coverage.measured_capabilities
                and total > 0 and correct == total)

    def require(self):
        if (type(self) is not ProspectiveTarget
                or _ISSUED.get(self) != _fingerprint(self)):
            _invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")


def _fingerprint(target):
    return contract_digest((
        target.binding, target.seed, source_content_digest(target.rows),
        target.assessment.digest(), target.coverage, target.comparison,
        target.visit.to_record(), target.cadence,
        target.journal_ordinal, target.release_sha256, target.plan_sha256))


def _binding(parent, cache, release, plan, target_plan):
    return (
        parent.run_id, parent.generation, parent.retained_state.optimizer_step,
        cache.accepted_manifest_sha256, cache.generation_binding,
        release.release_sha256, plan.digest, target_plan.comparison_scope_sha256,
    )


def prepare_factory_target_preflight(
        source_context, parent, cache, artifact_path, selection, journal_ordinal,
        *, mastery_debt_min_utility=0.05):
    """Draw once under C03/B13 identity and score the actual accepted parent."""
    from bilqis_mlx.runtime.accepted_priority_visit_contracts import (
        require_priority_cadence_authorization,
    )
    from bilqis_mlx.runtime.factory_retention_owner import (
        bind_current_retention_protection_plan, bind_current_retention_source_rows,
        require_current_retention_source_rows,
    )
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import strict_mode_enabled

    authorization = require_priority_cadence_authorization(selection)
    identity = selection.visit.identity
    if (authorization is None or selection.status != "TEACHER_SELECTED"
            or identity.capability_id not in authorization.authorized_capability_ids
            or identity.generation != parent.generation
            or identity.accepted_manifest_sha256 != cache.accepted_manifest_sha256
            or identity.student_sha256 != cache._candidate_identity_sha256):
        _invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    cadence = authorization.to_record()
    target = identity.capability_id
    release = source_context.release
    bind_current_retention_protection_plan(source_context, parent, cache)
    bind_current_retention_source_rows(source_context, cache, target)
    plan, target_plan, cached_rows = require_current_retention_source_rows(
        cache, release, target)
    authenticated = source_context._accepted_feature_context
    (reference_seed, reference_rows), _ = split_cached_rows(cached_rows, target_plan)
    if strict_mode_enabled():
        reference_cases = tuple(item.case for item in _instruments(
            source_context, parent, artifact_path, reference_rows, seed=reference_seed,
            release_prevalidated=True, authenticated=authenticated))
    else:
        reference_cases = tuple(factory_evaluation_case_from_source(
            source_context, row, semantic_release=authenticated.features.semantic_release)
            for row in reference_rows)
    epoch = comparison_epoch(release, plan, target_plan, reference_cases, parent, cache)
    groups = ((target, target_plan.target_grade_id),)
    coverage = baseline_coverage(
        BaselineLedger.from_optional_record(parent.baseline_evidence), epoch, groups)
    seed = prospective_seed(release, identity, cadence, journal_ordinal, plan, target_plan)
    draw = _fresh_rows(source_context, (target,), seed=seed + C05_FRESH_TARGET_SEED_OFFSET,
                       training=((), ()), require_independent=False)
    instruments = tuple(_instruments(
        source_context, parent, artifact_path, draw.rows, seed=draw.seed,
        each=C05_PROBE_EACH, release_prevalidated=True, authenticated=authenticated))
    policy = foundation_policy(
        groups, (), tuple(item.case for item in instruments), coverage, mastery_debt_min_utility)
    cohort = _cohort(
        EvidenceKind.FRESH_TARGET, instruments, groups, release, policy, ((), ()),
        rubric_sha256=plan.rubric_sha256, scope_sha256=target_plan.comparison_scope_sha256,
        source_sha256=plan.source_sha256)
    solver, generation = factory_complete_solver(
        source_context, parent, artifact_path, instruments, execution_cache=cache)
    assessment = evaluate_capabilities(solver, cohort, generation)
    issued = ProspectiveTarget(
        _binding(parent, cache, release, plan, target_plan), draw.seed,
        draw.rows, assessment, coverage, epoch.identity(target), identity, cadence, journal_ordinal,
        release.release_sha256, plan.digest)
    _ISSUED[issued] = _fingerprint(issued)
    return issued


def require_preflight(preflight):
    if type(preflight) is not ProspectiveTarget:
        _invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    preflight.require()


def reuse_parent_assessment(preflight, parent, cache, release, plan, target_plan,
                            cohort, coverage):
    """Attach actual delivered provenance to the unchanged parent measurements."""
    require_preflight(preflight)
    if (preflight.skip
            or preflight.binding != _binding(parent, cache, release, plan, target_plan)
            or preflight.coverage != coverage
            or replace(cohort, training_family_ids=(), training_episode_ids=())
            != preflight.assessment.cohort):
        _invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    return replace(preflight.assessment, cohort=cohort)
