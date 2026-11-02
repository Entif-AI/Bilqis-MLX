"""Record a source-frontier proposal or a truthful autonomous hold."""
import bilqis_mlx.operator_vocabulary as _bilqis_mlx_operator_vocabulary


def _hold_autonomy(*, autonomy_session, school, graph, receipt, run_dir, action, record):
    frontier_result = (
        autonomy_session.propose_source_frontier_work(
            school.current_student, graph))
    if frontier_result is not None:
        proposal, proposal_file = frontier_result
        reason = (
            _bilqis_mlx_operator_vocabulary.AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED.code
            if proposal.disposition.value ==
            "SOURCE_DEVELOPMENT"
            else "AUTONOMY_JIT_PROPOSAL_READY")
        record(run_dir, {
            "event": (
                "SCHOOL_AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED"
                if proposal.disposition.value ==
                "SOURCE_DEVELOPMENT"
                else "SCHOOL_AUTONOMY_JIT_PROPOSAL_READY"),
            "generation": receipt["generation"],
            "grade": school.grade,
            "deferred_obligations":
                list(action.deferred_obligation_ids),
            "proposal_sha256": proposal.proposal_sha256,
            "proposal_file": proposal_file,
            "frontier_sha256": proposal.frontier_sha256,
            "candidate_gate_count":
                len(proposal.candidate_gates),
            "selected_candidate_ids":
                list(proposal.selected_candidate_ids),
            "student_sha256":
                school.current_student.sha256,
            "optimizer_step":
                school.current_student.optimizer_step,
            "model_and_optimizer_unchanged": True,
        })
    else:
        reason = _bilqis_mlx_operator_vocabulary.AUTONOMY_SAFE_HOLD.code
        record(run_dir, {
            "event": "SCHOOL_AUTONOMY_SAFE_HOLD",
            "generation": receipt["generation"],
            "grade": school.grade,
            "deferred_obligations":
                list(action.deferred_obligation_ids),
            "student_sha256":
                school.current_student.sha256,
            "optimizer_step":
                school.current_student.optimizer_step,
            "model_and_optimizer_unchanged": True,
        })
    return reason
