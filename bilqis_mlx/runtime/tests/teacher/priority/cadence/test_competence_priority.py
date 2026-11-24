"""Grade-neutral WHAT allocation from current accepted evidence."""
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.factory.schedule import ScheduleCapability, ScheduleGrade, ScheduleProgram
from bilqis_mlx.runtime._learning_first.priority_frontier import learning_first_priority_frontier
from bilqis_mlx.runtime.active_grade_cadence import issue_active_grade_cadence
from bilqis_mlx.runtime.active_grade_cadence_contracts import ActiveGradeCadencePhase
from bilqis_mlx.runtime.active_grade_cadence_policy import recovery_members
from bilqis_mlx.runtime.outcomes.issuance import selection_context
from bilqis_mlx.runtime.priority_competence import (
    CapabilityCompetence, CompetenceScore, current_competence, instructional_members,
)

from bilqis_mlx.runtime.tests.teacher.priority.test_active_grade_cadence import (
    _capability, _epoch, _frontier, _obligations, _record_terminal,
)

SHA = "a" * 64
PERFECT, MEDIUM, WEAK, UNMEASURED = "Z.A", "Z.M", "Z.W", "Z.U"
MEMBERS = (PERFECT, MEDIUM, WEAK, UNMEASURED)


@dataclass(frozen=True)
class Binding:
    capability: str


def _fixture():
    grade = ScheduleGrade("Z", tuple(ScheduleCapability(cap, 6) for cap in MEMBERS),
                          (), SHA)
    program = ScheduleProgram(SHA, (grade,), False)
    release = SimpleNamespace(
        release_sha256=SHA,
        source_bindings=SimpleNamespace(
            by_capability={cap: Binding(cap) for cap in MEMBERS}))
    parent = SimpleNamespace(
        generation=7, parent_manifest_sha256="b" * 64,
        retained_state=SimpleNamespace(optimizer_step=84), outbox=())
    cache = SimpleNamespace(generation=7, accepted_manifest_sha256="c" * 64)
    return parent, cache, release, program


def _outcome(release, program, target, rows, *, generation, manifest, accepted):
    return {
        "schema": "bilqis.bamf.teacher-outcome/v2",
        "teacher_visit": {
            "capability_id": target, "visit_id": "visit",
            "generation": generation, "accepted_manifest_sha256": manifest,
        },
        "context": selection_context(
            release, program, "Z", "MAIN", "factory/foundation", {}, target),
        "decision": {"decision": "PROVISIONAL" if accepted else "REJECT",
                     "retention_protection_plan_sha256": SHA},
        "scores": rows, "protected_capabilities": [row[0] for row in rows if row[0] != target],
        "candidate_evidence": None, "proposal_id": None, "outcome_sha256": SHA,
    }


def _accepted_fixture():
    parent, cache, release, program = _fixture()
    observation = _outcome(
        release, program, MEDIUM,
        [(MEDIUM, 4, 5, 6), (PERFECT, 5, 6, 6), (WEAK, 3, 2, 6)],
        generation=6, manifest=parent.parent_manifest_sha256, accepted=True)
    parent.outbox = ({
        "event": "BAMF_C16_3_ACCEPTED", "parent_generation": 6,
        "accepted_manifest_sha256": parent.parent_manifest_sha256,
        "optimizer_step": 84, "capability": MEDIUM, "visit_id": "visit",
        "how_outcome": observation,
    },)
    return parent, cache, release, program


def _project(fixture, rejections=()):
    return current_competence(*fixture, MEMBERS, rejections)


def _rejection(fixture, target, rows, **overrides):
    _, cache, release, program = fixture
    outcome = _outcome(release, program, target, rows, generation=cache.generation,
                       manifest=cache.accepted_manifest_sha256, accepted=False)
    outcome.update(overrides)
    return (target, "visit", "REJECT", SHA, {"how_outcome": outcome})


def test_measured_deficit_overrides_recency_and_certification_counts():
    competence = _project(_accepted_fixture())
    assert instructional_members(MEMBERS, competence) == (MEDIUM, WEAK, UNMEASURED)
    assert competence[WEAK].reference.correct == 2
    assert competence[PERFECT].reference.correct == 6
    assert competence[MEDIUM].target.correct == 5
    assert competence[UNMEASURED].to_record()["reason"] == "UNMEASURED"
    _, frontier = learning_first_priority_frontier(
        SHA, tuple((cap, None) for cap in MEMBERS), SimpleNamespace(selection=None),
        100, {WEAK: 100}, 12, {WEAK: 12}, competence=competence)
    assert tuple(option.stable_id for option in frontier.options) == (
        WEAK, MEDIUM, UNMEASURED, PERFECT)
    state = SimpleNamespace(recovery_retained_counts=((WEAK, 8),))
    assert recovery_members(state, MEMBERS, {PERFECT: 99, WEAK: 1},
                            MEMBERS, competence) == (WEAK, MEDIUM, UNMEASURED)


def test_current_rejection_uses_parent_not_candidate_and_stale_scores_do_not_survive():
    fixture = _accepted_fixture()
    rejection = _rejection(fixture, PERFECT, [(PERFECT, 3, 6, 6), (WEAK, 2, 6, 6)])
    competence = _project(fixture, (rejection,))
    assert competence[PERFECT].target.correct == 3
    assert competence[WEAK].reference.correct == 2
    assert PERFECT in instructional_members(MEMBERS, competence)
    assert competence[PERFECT].to_record()["reason"] == "TARGET_SAMPLE_DEFICIT"
    parent, cache, _, _ = fixture
    parent.generation += 1
    parent.retained_state.optimizer_step += 12
    cache.generation += 1
    cache.accepted_manifest_sha256 = "d" * 64
    assert all(score == CapabilityCompetence()
               for score in _project(fixture, (rejection,)).values())


def test_incompatible_rubric_and_conflicting_reference_do_not_supply_perfection():
    fixture = _accepted_fixture()
    wrong = _rejection(fixture, PERFECT, [(PERFECT, 1, 6, 6)])
    wrong[4]["how_outcome"]["context"]["rubric_sha256"] = "d" * 64
    assert _project(fixture, (wrong,))[PERFECT].target is None
    conflict = _rejection(fixture, MEDIUM, [(MEDIUM, 4, 5, 6), (WEAK, 6, 6, 6)])
    weak = _project(fixture, (conflict,))[WEAK]
    assert weak.reference is None
    assert weak.to_record()["reason"] == "REFERENCE_CONFLICT"


def test_main_and_recovery_skip_perfect_but_preserve_unknown_exploration(tmp_path):
    competence = _project(_accepted_fixture())
    frontier = _frontier(tuple(_capability(cap) for cap in MEMBERS))
    epoch = _epoch({PERFECT: 9, MEDIUM: 2, WEAK: 1, UNMEASURED: 1})
    with patch("bilqis_mlx.runtime.active_grade_cadence_policy.obligations_for_capability",
               side_effect=_obligations(epoch)):
        for cap in (WEAK, MEDIUM, UNMEASURED):
            issued = issue_active_grade_cadence(tmp_path, epoch, frontier,
                                                competence=competence)
            assert cap in issued.authorized_capability_ids
            assert PERFECT not in issued.authorized_capability_ids
            _record_terminal(tmp_path, issued, cap, "REJECTED")
        recovery = issue_active_grade_cadence(tmp_path, epoch, frontier,
                                              competence=competence)
        assert recovery.phase is ActiveGradeCadencePhase.RECOVERY_1
        assert recovery.authorized_capability_ids == (WEAK, MEDIUM, UNMEASURED)
        for cap in (WEAK, MEDIUM, UNMEASURED):
            issued = issue_active_grade_cadence(tmp_path, epoch, frontier,
                                                competence=competence)
            _record_terminal(tmp_path, issued, cap, "REJECTED")
        second = issue_active_grade_cadence(tmp_path, epoch, frontier,
                                            competence=competence)
        assert second.phase is ActiveGradeCadencePhase.RECOVERY_2
        assert second.authorized_capability_ids == (WEAK, MEDIUM, UNMEASURED)


def test_all_perfect_is_not_grade_certification():
    scores = {cap: CapabilityCompetence(CompetenceScore(6, 6, "FIXED_REFERENCE", SHA))
              for cap in MEMBERS}
    assert instructional_members(MEMBERS, scores) == MEMBERS
    assert scores[WEAK].to_record()["reason"] == "REFERENCE_PERFECT_CERTIFICATION_DEBT"


def test_legacy_cadence_migrates_once_and_preserves_history(tmp_path):
    competence = _project(_accepted_fixture())
    frontier = _frontier(tuple(_capability(cap) for cap in MEMBERS))
    epoch = _epoch({cap: 1 for cap in MEMBERS})
    with patch("bilqis_mlx.runtime.active_grade_cadence_policy.obligations_for_capability",
               side_effect=_obligations(epoch)):
        with patch("bilqis_mlx.runtime.active_grade_cadence_policy.CADENCE_POLICY_EPOCH", 2):
            legacy = issue_active_grade_cadence(tmp_path, epoch, frontier)
        assert legacy.state.policy_epoch == 2
        assert PERFECT in legacy.authorized_capability_ids
        migrated = issue_active_grade_cadence(tmp_path, epoch, frontier,
                                              competence=competence)
        resumed = issue_active_grade_cadence(tmp_path, epoch, frontier,
                                             competence=competence)
    assert migrated.state.policy_epoch == 3
    assert migrated.state.predecessor_sha256 == legacy.state.cadence_sha256
    assert migrated.state.cadence_epoch == legacy.state.cadence_epoch + 1
    assert PERFECT not in migrated.authorized_capability_ids
    assert resumed.state.cadence_sha256 == migrated.state.cadence_sha256
    assert resumed.authorized_capability_ids == migrated.authorized_capability_ids
