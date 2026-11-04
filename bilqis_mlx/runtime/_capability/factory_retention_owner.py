"""Production C05 owner: Factory cohorts, policy, solvers and paired screen."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

from bilqis_mlx.fixed_frontier import load_frontier_cohort
from bilqis_mlx.learning.atlas_candidate import CandidateTransaction, resolve_candidate
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.atlas_training_authority import BamfTrainingAuthority
from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_execution_cache, derive_successor_bundle,
    load_accepted_generation,
)
from bilqis_mlx.runtime.capability_retention import (
    Decision, EvidenceKind, EvaluationCohort, RetentionPolicy, case_census_digest,
    evaluate_retention_candidate,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.state_dag import read_current
from bilqis_mlx.fixed_frontier import frontier_exam

from .capability_evaluation import _invalid
from .factory_complete_solver import (
    FactoryEvaluationInstrument, factory_complete_solver,
    factory_evaluation_instrument,
)


C05_PROBE_EACH = 6
C05_PROTECTED_REFERENCE_LOSS = 1
C05_FRESH_TARGET_SEED_OFFSET = 104729
C05_FRESH_LESSON_SEED_OFFSET = 130363
_OWNER_ISSUER = object()


@dataclass(frozen=True, init=False)
class FactoryRetentionEvaluation:
    """Unforgeable evidence that the Factory-owned C05 screen actually ran."""
    decision: Decision
    parent_candidate_sha256: str
    candidate_candidate_sha256: str
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("BAMF_C05_FACTORY_EVALUATION_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _OWNER_ISSUER
                or type(self.decision) is not Decision
                or not all(isinstance(value, str) and len(value) == 64
                           for value in (self.parent_candidate_sha256,
                                         self.candidate_candidate_sha256))):
            _invalid("BAMF_C05_FACTORY_EVALUATION_INVALID")


def _issue_owner_evaluation(decision, parent, candidate):
    item = object.__new__(FactoryRetentionEvaluation)
    for name, value in (
        ("decision", decision),
        ("parent_candidate_sha256", candidate_identity_digest(parent.retained_state)),
        ("candidate_candidate_sha256", candidate_identity_digest(candidate.retained_state)),
        ("_issuance", _OWNER_ISSUER),
    ):
        object.__setattr__(item, name, value)
    item.__post_init__()
    return item


def _training_exclusions(candidate: CandidateTransaction):
    families, episodes = set(), set()
    if not candidate.training_authorities:
        _invalid("BAMF_C05_TRAINING_SOURCE_INDEPENDENCE_UNAVAILABLE")
    for proof, authority in zip(candidate.step_proofs, candidate.training_authorities):
        if (type(authority) is not BamfTrainingAuthority
                or proof.training_authority_sha256 != authority.digest
                or proof.source_family_id != authority.source_family_id
                or proof.episode_id != authority.episode_id):
            _invalid("BAMF_C05_TRAINING_SOURCE_INDEPENDENCE_UNAVAILABLE")
        authority.__post_init__()
        families.add(authority.source_family_id)
        episodes.add(authority.episode_id)
    if not families or not episodes:
        _invalid("BAMF_C05_TRAINING_SOURCE_INDEPENDENCE_UNAVAILABLE")
    return tuple(sorted(families)), tuple(sorted(episodes))


def _owner_seed(release_sha256, cache, target_capability, candidate_sha256):
    digest = contract_digest({
        "schema": "bilqis.mlx.c05-fresh-seed/v1",
        "factory_release": release_sha256,
        "run": cache.run_id,
        "parent_generation": cache.generation,
        "parent_manifest": cache.accepted_manifest_sha256,
        "candidate": candidate_sha256,
        "target_capability": target_capability,
    })
    return int(digest[:16], 16)


def _candidate_from_live_parent(run_dir: Path, transaction: CandidateTransaction):
    """Bind one speculative B12 transaction to the current accepted B13 parent."""
    parent = load_accepted_generation(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    custody = transaction.parent.custody
    if (transaction.update_steps < 1 or custody is None
            or candidate_identity_digest(transaction.parent)
            != candidate_identity_digest(parent.retained_state)
            or custody.run_id != cache.run_id
            or custody.generation != cache.generation
            or custody.manifest_sha256 != cache.accepted_manifest_sha256
            or custody.topology_digest != parent.topology.digest
            or custody.extents_digest != parent.extents.digest):
        _invalid("BAMF_C05_CANDIDATE_PARENT_CUSTODY_MISMATCH")
    # This is a pure hypothetical state used to score the proposed optimizer.
    # It grants no retention or publication authority; only the later C05 decision does.
    preview = resolve_candidate(transaction, accepted=True)
    successor = derive_successor_bundle(
        parent, preview,
        parent_manifest_sha256=cache.accepted_manifest_sha256,
        delivery_events=())
    return parent, successor, preview, cache


def _instruments(source_context, candidate, artifact_path, rows, *, seed, each=None):
    counts = {}
    if each is None:
        for row in rows:
            capability = row.get("capability")
            counts[capability] = counts.get(capability, 0) + 1
    return tuple(factory_evaluation_instrument(
        source_context, candidate, artifact_path, row,
        source_seed=seed,
        source_each=(each if each is not None else counts[row.get("capability")]),
    ) for row in rows)


def _fresh_rows(source_context, capabilities, *, seed):
    rows = []
    for capability in capabilities:
        rows.extend(source_context.draw_rows(
            seed=seed, capability=capability, each=C05_PROBE_EACH))
    return tuple(rows)


def _cohort(kind, instruments, groups, release, policy, training):
    cases = tuple(item.case for item in instruments)
    rubric = contract_digest(tuple(
        (item.grade_id, item.assessment_blueprint_sha256)
        for item in release.execution_plan.grades))
    scope = contract_digest((
        release.execution_plan.curriculum_sha256,
        release.execution_plan.profile_id,
        tuple(groups),
    ))
    source = release.execution_plan.projection_digests.source
    return EvaluationCohort(
        kind, cases, tuple(groups), rubric, scope, source, policy.digest(),
        training[0], training[1], case_census_digest(cases))


def evaluate_factory_retention_candidate(
    source_context,
    candidate: CandidateTransaction,
    artifact_path: str,
    target_capability: str,
    *,
    run_dir: Path,
):
    """Run C05 with no caller-selected solver, cohort, policy or coverage map."""
    if (type(candidate) is not CandidateTransaction
            or not isinstance(target_capability, str) or not target_capability
            or not isinstance(run_dir, Path)):
        _invalid("BAMF_C05_FACTORY_OWNER_INPUT_INVALID")
    source_context.__post_init__()
    release = source_context.release
    capability_map = release.execution_plan.capability_map
    if target_capability not in capability_map:
        _invalid("BAMF_C05_TARGET_CAPABILITY_NOT_ADMITTED")
    groups = tuple((item.capability_id, item.grade_id)
                   for item in release.execution_plan.capabilities)
    target_group = capability_map[target_capability].grade_id
    lesson_capabilities = tuple(capability for capability, group in groups
                                if group == target_group)
    training = _training_exclusions(candidate)
    if (any(authority.delivery_capability != target_capability
            or authority.release_sha256 != release.release_sha256
            for authority in candidate.training_authorities)):
        _invalid("BAMF_C05_TARGET_NOT_OWNED_BY_TRAINING")
    parent, candidate_bundle, candidate_state, cache = _candidate_from_live_parent(
        run_dir, candidate)
    candidate_sha256 = candidate_identity_digest(candidate_state)
    fresh_seed = _owner_seed(
        release.release_sha256, cache, target_capability, candidate_sha256)

    target_seed = fresh_seed + C05_FRESH_TARGET_SEED_OFFSET
    lesson_seed = fresh_seed + C05_FRESH_LESSON_SEED_OFFSET
    target_rows = _fresh_rows(source_context, (target_capability,), seed=target_seed)
    lesson_rows = _fresh_rows(source_context, lesson_capabilities, seed=lesson_seed)
    target_instruments = _instruments(
        source_context, candidate_bundle, artifact_path, target_rows,
        seed=target_seed, each=C05_PROBE_EACH)
    lesson_instruments = _instruments(
        source_context, candidate_bundle, artifact_path, lesson_rows,
        seed=lesson_seed, each=C05_PROBE_EACH)

    receipt = read_current(run_dir)
    if receipt.get("factory_release_sha256") != release.release_sha256:
        _invalid("BAMF_C05_FACTORY_RELEASE_DRIFT")
    fixed_exam = frontier_exam(receipt)
    fixed = load_frontier_cohort(run_dir, fixed_exam)
    if fixed is None:
        _invalid("BAMF_C05_FIXED_SCHOOL_COHORT_REQUIRED")
    if fixed_exam.get("factory_release_sha256") != release.release_sha256:
        _invalid("BAMF_C05_FIXED_SCHOOL_RELEASE_DRIFT")
    fixed_instruments = _instruments(
        source_context, candidate_bundle, artifact_path, fixed.rows,
        seed=fixed.seed)

    required = (
        (EvidenceKind.FRESH_TARGET,
         case_census_digest(tuple(item.case for item in target_instruments))),
        (EvidenceKind.FRESH_LESSON,
         case_census_digest(tuple(item.case for item in lesson_instruments))),
        (EvidenceKind.FIXED_SCHOOL,
         case_census_digest(tuple(item.case for item in fixed_instruments))),
    )
    policy = RetentionPolicy(
        groups, tuple(dict.fromkeys(group for _, group in groups)),
        tuple((capability, C05_PROTECTED_REFERENCE_LOSS)
              for capability, _ in groups if capability != target_capability),
        C05_PROBE_EACH, required)
    target_cohort = _cohort(
        EvidenceKind.FRESH_TARGET, target_instruments,
        ((target_capability, target_group),), release, policy, training)
    lesson_groups = tuple(pair for pair in groups if pair[1] == target_group)
    lesson_cohort = _cohort(
        EvidenceKind.FRESH_LESSON, lesson_instruments,
        lesson_groups, release, policy, training)
    fixed_cohort = _cohort(
        EvidenceKind.FIXED_SCHOOL, fixed_instruments,
        groups, release, policy, training)

    all_instruments = tuple(dict(
        (item.case.case_id, item)
        for item in (*target_instruments, *lesson_instruments, *fixed_instruments)
    ).values())
    parent_solver, parent_generation = factory_complete_solver(
        source_context, parent, artifact_path, all_instruments)
    candidate_solver, candidate_generation = factory_complete_solver(
        source_context, candidate_bundle, artifact_path, all_instruments)
    decision = evaluate_retention_candidate(
        parent_solver, candidate_solver, target_capability, policy,
        (target_cohort, lesson_cohort, fixed_cohort),
        parent_generation, candidate_generation)
    return _issue_owner_evaluation(decision, parent, candidate_bundle)


__all__ = ("FactoryRetentionEvaluation", "evaluate_factory_retention_candidate")
