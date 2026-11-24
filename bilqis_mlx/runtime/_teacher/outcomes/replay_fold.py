"""Apply authenticated rejected HOW observations in journal order."""
from copy import deepcopy
from functools import partial

from bilqis_mlx.learning.teacher_visit_identity import TeacherVisitIdentity, require_teacher_visit_receipt
from bilqis_mlx.runtime.bamf_operator.evidence_parts.validation import read_candidate_horizon_evidence

from .observations import apply_replayed_outcome, invalid


PORTABLE_TEACHER_AUTHORITY = "_portable_teacher_authority_verified"


def fold_rejections(run_dir, cache, teacher, rows, recover_selected_teacher):
    # One private working tree for the fold, not a full copy for every row.
    teacher = deepcopy(teacher) if rows else teacher
    recover = partial(recover_selected_teacher, run_dir)
    for capability, visit_id, reason, receipt_sha, evidence in rows:
        observation = evidence.get('how_outcome')
        if observation is None:
            continue
        visit = TeacherVisitIdentity.from_record(observation['teacher_visit'])
        if evidence.get(PORTABLE_TEACHER_AUTHORITY) is not True:
            require_teacher_visit_receipt(visit)
        decision = observation['decision']
        candidate_evidence = evidence.get('candidate_evidence')
        if candidate_evidence is None:
            attempted = (
                evidence.get('candidate_optimizer_step', 0)
                - evidence.get('retained_optimizer_step', 0))
            invalid_record = (
                observation.get('candidate_evidence') is not None
                or observation.get('proposal_id') is not None
                or observation.get('attempted_steps') != attempted)
        else:
            payload = read_candidate_horizon_evidence(run_dir, candidate_evidence)
            proposal = payload['proposal']
            selected_teacher_matches = (
                observation.get('selected_teacher') == proposal.get('selected_teacher')
                if 'selected_teacher' in observation or 'selected_teacher' in proposal
                else observation.get('selected_teacher_sha256')
                     == proposal.get('selected_teacher_sha256'))
            invalid_record = (
                observation['attempt_id'] != payload['attempt_id']
                or observation['proposal_id'] != payload['proposal_id']
                or observation['candidate_evidence'] != candidate_evidence['object']
                or observation['context'] != proposal.get('how_context')
                or not selected_teacher_matches
                or observation['selected_policy'] != proposal['policy']
                or observation['teacher_visit'] != proposal['teacher_visit']
                or observation['context']['factory_release_sha256'] != proposal['factory_release_sha256']
                or payload['outcome'] != {'accepted': False, 'decision': decision}
                or proposal['candidate_attempt_ordinal'] != evidence['rejection_journal_ordinal']
                or observation['attempted_steps'] != len(payload['steps']))
        if (invalid_record
                or visit.generation != cache.generation
                or visit.accepted_manifest_sha256 != cache.accepted_manifest_sha256
                or visit.capability_id != capability or visit.visit_id != visit_id
                or decision != evidence['decision']
                or decision['decision'] != 'REJECT' or decision['reason'] != reason
                or observation['retained_steps'] != 0):
            invalid()
        teacher = apply_replayed_outcome(teacher, observation, recover)
        weaknesses = evidence.get('structural_weaknesses', ())
        if weaknesses or not isinstance(weaknesses, (list, tuple)):
            from bilqis_mlx.runtime.structural_weakness_replay import (
                apply_rejection_weaknesses,
            )
            teacher = apply_rejection_weaknesses(
                teacher, evidence, receipt_sha)
    return teacher
