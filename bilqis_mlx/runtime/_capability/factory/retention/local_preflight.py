"""C05 prospective FOUNDATION target assessment, before candidate execution."""
from dataclasses import dataclass, replace
from weakref import WeakKeyDictionary

from bilqis_mlx.runtime._factory_retention_support import (
    C05_FRESH_TARGET_SEED_OFFSET, C05_PROBE_EACH, _cohort, _fresh_rows, _instruments,
)
from bilqis_mlx.runtime.baseline.currentness import baseline_coverage
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLedger
from bilqis_mlx.runtime.capability_retention import EvidenceKind, evaluate_capabilities
from bilqis_mlx.runtime.capability_evaluation import EvidenceStage, _answer_identity, _invalid
from bilqis_mlx.runtime.factory_complete_solver import (
    factory_complete_solver, factory_evaluation_case_from_source,
)
from bilqis_mlx.runtime.source_execution import SourceBatchAuthority, source_content_digest
from bilqis_mlx.semantics.domains import contract_digest

from .local_screen_support import comparison_epoch, foundation_policy, split_cached_rows


_ISSUED = WeakKeyDictionary()
_EXACT_MISS_PAIR_ARITY = 2  # Source row and its authenticated subset grant.


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


@dataclass(frozen=True)
class ExactMissInstruction:
    """Host-only proposal backed by the existing issued prospective assessment."""

    preflight: ProspectiveTarget
    pairs: tuple[tuple[dict, SourceBatchAuthority], ...]
    digest: str


def _eligible_exact_misses(preflight, context, parent, cache, selection,
                          plan, target_plan, journal_ordinal):
    from bilqis_mlx.runtime.accepted_priority_visit_contracts import (
        require_priority_cadence_authorization,
    )
    from bilqis_mlx.runtime.structural_weakness_capture import _provider_for_context
    from bilqis_mlx.source_adapters.lesson_geometry import geometry_for_adapter

    require_preflight(preflight)
    authorization = require_priority_cadence_authorization(selection)
    identity = selection.visit.identity
    target = selection.offer.capability_id
    release = context.release
    cohort = preflight.assessment.cohort
    if (authorization is None or selection.status != "TEACHER_SELECTED"
            or target not in authorization.authorized_capability_ids
            or identity.capability_id != target
            or identity.generation != parent.generation
            or identity.accepted_manifest_sha256 != cache.accepted_manifest_sha256
            or identity.student_sha256 != cache._candidate_identity_sha256
            or preflight.visit != identity
            or preflight.cadence != authorization.to_record()
            or type(journal_ordinal) is not int or journal_ordinal < 1
            or preflight.journal_ordinal != journal_ordinal
            or preflight.binding != _binding(parent, cache, release, plan, target_plan)
            or preflight.release_sha256 != release.release_sha256
            or preflight.plan_sha256 != plan.digest
            or cohort.kind is not EvidenceKind.FRESH_TARGET
            or cohort.evidence_stage is not EvidenceStage.FOUNDATION_ACQUISITION
            or plan.evidence_stage != EvidenceStage.FOUNDATION_ACQUISITION
            or cohort.capability_groups != ((target, target_plan.target_grade_id),)
            or cohort.rubric_sha256 != plan.rubric_sha256
            or cohort.scope_sha256 != target_plan.comparison_scope_sha256
            or cohort.source_sha256 != plan.source_sha256
            or cohort.training_family_ids or cohort.training_episode_ids
            or len(preflight.rows) != C05_PROBE_EACH
            or len(preflight.rows) != len(cohort.cases)):
        _invalid("BAMF_C05_EXACT_MISS_AUTHORITY_DRIFT")
    _, adapter, _ = _provider_for_context(context, target)
    geometry = geometry_for_adapter(adapter)
    if geometry is None or geometry.layout != "singleton" or geometry.provider != "predicate":
        return ()
    semantic_release = context._accepted_feature_context.features.semantic_release
    cases = tuple(factory_evaluation_case_from_source(
        context, row, semantic_release=semantic_release) for row in preflight.rows)
    if (cases != cohort.cases
            or len({case.case_id for case in cases}) != len(cases)
            or len({case.episode_id for case in cases}) != len(cases)):
        _invalid("BAMF_C05_EXACT_MISS_CENSUS_DRIFT")
    return tuple(row for row, case, result in zip(
        preflight.rows, cases, preflight.assessment.results, strict=True)
        if _answer_identity(result.answer) != _answer_identity(case.gold))


def _grant_coordinates(grant):
    return (grant.release_sha256, grant.capability_id, grant.provider_id,
            grant.provider_implementation_sha256, grant.seed, grant.each,
            grant.content_sha256, grant.source_family_id, grant.episode_ids)


def _instruction_digest(preflight, pairs):
    return contract_digest((
        preflight.assessment.digest(), preflight.binding, preflight.visit.visit_id,
        preflight.journal_ordinal,
        tuple((row["id"], source_content_digest((row,)), _grant_coordinates(grant))
              for row, grant in pairs)))


def issue_exact_miss_instruction(preflight, context, parent, cache, selection,
                                 plan, target_plan, journal_ordinal):
    """Reissue the existing source draw once, without further solver inference."""
    rows = _eligible_exact_misses(
        preflight, context, parent, cache, selection, plan, target_plan, journal_ordinal)
    if not rows:
        return None
    authority = context.bind_rows(
        preflight.rows, seed=preflight.seed,
        capability=selection.offer.capability_id, each=len(preflight.rows))
    pairs = tuple((row, context.bind_authorized_subset_rows(
        preflight.rows, (row,), authority)) for row in rows)
    return ExactMissInstruction(preflight, pairs, _instruction_digest(preflight, pairs))


def exact_miss_marker(preflight):
    return {
        "exact_miss_assessment_sha256": preflight.assessment.digest(),
        "exact_miss_visit_id": preflight.visit.visit_id,
        "exact_miss_journal_ordinal": preflight.journal_ordinal,
    }


def require_exact_miss_delivery(instruction, context, selection, observation,
                                rows, roles, bindings, authorities, *, reserved_rows=()):
    """Derive actual replay from owner evidence, never from a caller's marker."""
    from bilqis_mlx.runtime.bamf_operator.evidence_parts.support import candidate_attempt_id
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import strict_mode_enabled
    from bilqis_mlx.runtime.factory_retention_owner import require_current_retention_plan

    marker_keys = ("exact_miss_assessment_sha256", "exact_miss_visit_id",
                   "exact_miss_journal_ordinal")
    if any(key in observation.controls for key in (
            "exact_miss_delivery_ids", "exact_miss_replay_delivered")):
        _invalid("BAMF_C05_EXACT_MISS_CONTROL_SPOOFED")
    if instruction is None:
        if any(any(key in record for key in marker_keys) for record in bindings.values()):
            _invalid("BAMF_C05_EXACT_MISS_INSTRUCTION_REQUIRED")
        return ()
    if type(instruction) is not ExactMissInstruction or strict_mode_enabled():
        _invalid("BAMF_C05_EXACT_MISS_AUTHORITY_DRIFT")
    preflight = instruction.preflight
    generation = selection.offer._planning_generation
    parent, cache = generation._parent, generation._cache
    capability = selection.offer.capability_id
    plan, target_plan = require_current_retention_plan(cache, context.release, capability)
    if type(preflight) is not ProspectiveTarget:
        _invalid("BAMF_C05_PROSPECTIVE_TARGET_INVALID")
    eligible = _eligible_exact_misses(
        preflight, context, parent, cache, selection, plan, target_plan,
        preflight.journal_ordinal)
    expected_attempt = candidate_attempt_id(
        cache.generation, cache.accepted_manifest_sha256,
        selection.visit.identity.visit_id, preflight.journal_ordinal)
    if observation.capture.attempt_id != expected_attempt:
        _invalid("BAMF_C05_EXACT_MISS_ATTEMPT_DRIFT")
    pairs = instruction.pairs
    if (not eligible or type(pairs) is not tuple or len(pairs) != len(eligible)
            or any(type(pair) is not tuple or len(pair) != _EXACT_MISS_PAIR_ARITY
                   or type(pair[1]) is not SourceBatchAuthority for pair in pairs)
            or tuple(row for row, _ in pairs) != eligible):
        _invalid("BAMF_C05_EXACT_MISS_CENSUS_DRIFT")
    for row, grant in pairs:
        context.require_bound_rows((row,), grant)
        if grant.seed != preflight.seed or grant.capability_id != capability:
            _invalid("BAMF_C05_EXACT_MISS_SOURCE_DRIFT")
    if instruction.digest != _instruction_digest(preflight, pairs):
        _invalid("BAMF_C05_EXACT_MISS_AUTHORITY_DRIFT")
    expected = {row["id"]: (row, grant) for row, grant in pairs}
    marker = exact_miss_marker(preflight)
    delivered = []
    for row in rows:
        row_id = row["id"]
        record, grant = bindings[row_id], authorities[row_id]
        issued = expected.get(row_id)
        tagged = any(key in record for key in marker_keys)
        exact_grant = issued is not None and grant == issued[1]
        if not tagged and not exact_grant:
            continue
        if (not exact_grant or roles[row_id] != "preservation"
                or "weakness_debt_key" in record
                or source_content_digest((row,)) != source_content_digest((issued[0],))
                or record != {
                    "row_id": row_id, "role": "preservation", "capability": capability,
                    "seed": grant.seed, "each": grant.each,
                    "source_family_id": grant.source_family_id,
                    "episode_id": grant.episode_ids[0], **marker}):
            _invalid("BAMF_C05_EXACT_MISS_DELIVERY_DRIFT")
        context.require_bound_rows((row,), grant)
        delivered.append(row_id)
    if len(set(delivered)) != len(delivered):
        _invalid("BAMF_C05_EXACT_MISS_DELIVERY_DRIFT")
    if delivered and sum(role == "preservation" for role in roles.values()) > selection.offer.source_each:
        _invalid("BAMF_C05_EXACT_MISS_DELIVERY_CAPACITY")
    actual_ids = set(delivered)
    reserved = (*reserved_rows, *(row for row in rows if row["id"] not in actual_ids))
    used_ids = {row["id"] for row in reserved}
    used_tokens = {tuple(row["tokens"]) for row in reserved}
    for row in rows:
        if row["id"] not in actual_ids:
            continue
        tokens = tuple(row["tokens"])
        if row["id"] in used_ids or tokens in used_tokens:
            _invalid("BAMF_C05_EXACT_MISS_DELIVERY_COLLISION")
        used_ids.add(row["id"])
        used_tokens.add(tokens)
    return tuple(delivered)


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
