"""Current accepted-learner C05 observations, not certification authority."""
from dataclasses import asdict, dataclass
from fractions import Fraction

from bilqis_mlx.runtime.state import _fingerprint


@dataclass(frozen=True)
class CompetenceScore:
    correct: int
    total: int
    kind: str
    outcome_sha256: str

    @property
    def accuracy(self):
        return Fraction(self.correct, self.total)


@dataclass(frozen=True)
class CapabilityCompetence:
    reference: CompetenceScore | None = None
    target: CompetenceScore | None = None
    reference_conflict: bool = False

    @property
    def deficit(self):
        if self.reference is not None and self.reference.accuracy < 1:
            return self.reference
        if self.target is not None and self.target.accuracy < 1:
            return self.target
        return None

    @property
    def priority(self):
        deficit = self.deficit
        if deficit is not None:
            return 0, deficit.accuracy, int(deficit.kind != "FIXED_REFERENCE")
        if self.reference is None:
            return 1, Fraction(0), 0
        return 2, Fraction(1), 0

    def to_record(self):
        deficit = self.deficit
        if deficit is not None:
            reason = deficit.kind + "_DEFICIT"
        elif self.reference is not None:
            reason = "REFERENCE_PERFECT_CERTIFICATION_DEBT"
        elif self.reference_conflict:
            reason = "REFERENCE_CONFLICT"
        elif self.target is not None:
            reason = "TARGET_PERFECT_UNCONFIRMED"
        else:
            reason = "UNMEASURED"
        return {**asdict(self), "reason": reason}


UNKNOWN_COMPETENCE = CapabilityCompetence()


def instructional_members(ready, competence):
    """Defer perfect references while actionable deficits or unknowns remain.

    Contrary target-sample evidence remains an actionable deficit. If all
    references are perfect, the lawful frontier still owns certification debt.
    """
    ready = tuple(ready)
    active = tuple(cap for cap in ready
                   if competence.get(cap, UNKNOWN_COMPETENCE).priority[0] < 2)
    return active or ready


def _score_rows(observation, target, accepted, members):
    scores = observation.get("scores")
    protected = observation.get("protected_capabilities")
    digest = observation.get("outcome_sha256")
    if (not isinstance(scores, (list, tuple))
            or not isinstance(protected, (list, tuple))
            or not isinstance(digest, str) or len(digest) != 64):
        return ()
    result, seen = [], set()
    for row in scores:
        if not isinstance(row, (tuple, list)) or len(row) != 4:
            return ()
        cap, before, after, total = row
        if (not isinstance(cap, str) or cap in seen
                or any(type(value) is not int for value in (before, after, total))
                or total <= 0 or not 0 <= before <= total or not 0 <= after <= total):
            return ()
        seen.add(cap)
        if cap not in members:
            continue
        if cap == target:
            kind = "TARGET_SAMPLE"
        elif (cap in protected and "candidate_evidence" in observation
              and observation["candidate_evidence"] is None
              and observation.get("proposal_id") is None
              and isinstance(observation["decision"].get(
                  "retention_protection_plan_sha256"), str)):
            # Ordinary C05 uses deterministic run/release/capability peers.
            # Its independently drawn target is not a fixed reference.
            kind = "FIXED_REFERENCE"
        else:
            continue
        result.append((cap, CompetenceScore(
            after if accepted else before, total, kind, digest)))
    return tuple(result)


def _compatible(observation, target, visit_id, generation, manifest,
                accepted, release_sha256, contexts):
    if not isinstance(observation, dict):
        return False
    context = observation.get("context")
    visit = observation.get("teacher_visit")
    decision = observation.get("decision")
    if not all(isinstance(item, dict) for item in (context, visit, decision)):
        return False
    expected = contexts.get(target)
    return (
        expected is not None
        and visit.get("capability_id") == target
        and visit.get("visit_id") == visit_id
        and visit.get("generation") == generation
        and visit.get("accepted_manifest_sha256") == manifest
        and decision.get("decision") == ("PROVISIONAL" if accepted else "REJECT")
        and context.get("factory_release_sha256") == release_sha256
        and all(context.get(key) == value for key, value in expected.items())
    )


def current_competence(parent, cache, release, program, members, rejections):
    """Read accepted-after and authenticated current-parent-before scores."""
    members = set(members)
    bindings = release.source_bindings.by_capability
    grades = {cap.id: grade for grade in program.grades for cap in grade.capabilities}
    contexts = {}
    reference, target_scores, conflicts = {}, {}, set()

    def consume(observation, target, visit_id, generation, manifest, accepted):
        if target not in contexts and target in grades and target in bindings:
            grade = grades[target]
            contexts[target] = {
                "grade": grade.id, "rubric_sha256": grade.assessment_sha256,
                "grade_definition_sha256": _fingerprint(asdict(grade)),
                "source_binding_sha256": _fingerprint(asdict(bindings[target])),
            }
        if not _compatible(observation, target, visit_id, generation, manifest,
                           accepted, release.release_sha256, contexts):
            return
        for cap, score in _score_rows(observation, target, accepted, members):
            if score.kind == "TARGET_SAMPLE":
                target_scores[cap] = score
                continue
            prior = reference.get(cap)
            if prior is not None and (prior.correct, prior.total) != (
                    score.correct, score.total):
                # Conflicting fixed scores at one checkpoint are not authority.
                conflicts.add(cap)
            reference[cap] = score

    for event in parent.outbox:
        if (isinstance(event, dict)
                and event.get("event") == "BAMF_C16_3_ACCEPTED"
                and event.get("parent_generation") == parent.generation - 1
                and event.get("accepted_manifest_sha256") == parent.parent_manifest_sha256
                and event.get("optimizer_step") == parent.retained_state.optimizer_step):
            consume(event.get("how_outcome"), event.get("capability"),
                    event.get("visit_id"), parent.generation - 1,
                    parent.parent_manifest_sha256, True)
    for capability, visit_id, _reason, _receipt, evidence in rejections:
        consume(evidence.get("how_outcome"), capability, visit_id,
                cache.generation, cache.accepted_manifest_sha256, False)
    return {
        cap: CapabilityCompetence(
            None if cap in conflicts else reference.get(cap), target_scores.get(cap),
            cap in conflicts)
        for cap in members
    }


def priority_competence_snapshot(run_dir, parent, cache, release, program, members):
    """Project competence and recency from one authenticated rejection read."""
    if program is None:
        return {}, None
    from .priority_rejection_replay import rejection_priority_snapshot
    snapshot = rejection_priority_snapshot(run_dir, parent, cache)
    return current_competence(parent, cache, release, program, members, snapshot[2]), snapshot
