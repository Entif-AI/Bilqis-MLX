"""Recovery of fully written checkpoint generations whose pointer was interrupted."""
from __future__ import annotations


def recover_orphaned_commit(run_dir, latest: dict, *, verify_best_custody,
                            persist, reconcile_delivery_outbox, record_event) -> dict:
    target = run_dir / "states" / f"{latest['generation']+1:07d}.json"
    if not target.exists():
        return latest
    if target.is_symlink() or not target.is_file():
        raise ValueError("HUMAN_TRAINER_RECOVERY_UNSAFE_GENERATION")
    from bilqis_mlx import state_dag
    proposed = state_dag.read_generation(run_dir, latest["generation"] + 1)
    if (proposed.get("generation") != latest["generation"] + 1 or
            proposed.get("run_id") != latest.get("run_id") or
            proposed.get("schema") != latest.get("schema") or
            proposed.get("source_manifest_sha256") != latest.get("source_manifest_sha256") or
            proposed.get("teacher_source_sha256") != latest.get("teacher_source_sha256") or
            proposed.get("accepted_authority") != latest.get("accepted_authority")):
        raise ValueError("HUMAN_TRAINER_RECOVERY_INCONSISTENT_LINEAGE")
    if proposed.get("model_topology") != latest.get("model_topology"):
        from ..errors import ErrorBus, SCHOOL
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
    if latest.get("model_topology") is not None:
        from .topology_lifecycle import inspect_resume_topology
        from .model_topology import ModelTopologySpec
        inspect_resume_topology(
            run_dir, proposed, ModelTopologySpec.from_record(latest["model_topology"]))
    verify_best_custody(run_dir, proposed)
    proposed = persist(run_dir, proposed)
    reconcile_delivery_outbox(run_dir, proposed)
    record_event(run_dir, {
        "event": "SCHOOL_INTERRUPT_POINTER_RECOVERED", "grade": "A",
        "generation": proposed["generation"],
        "student_sha256": proposed["school"]["current_student"]["sha256"],
        "optimizer_step": proposed["school"]["current_student"]["optimizer_step"]})
    return proposed
