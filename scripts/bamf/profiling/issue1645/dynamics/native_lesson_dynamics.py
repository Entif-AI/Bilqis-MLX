"""Observe the ordinary native lesson boundary; abort before candidate admission."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import json
import time
from unittest.mock import patch

from scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics import custody, file_digest
from scripts.bamf.profiling.issue1645.reservation import require


class Captured(BaseException):
    """Intentional stop; never return a candidate to the horizon owner."""


def capture_selected(run, parent, context, atlas, feature, selection, cache, destination):
    import mlx.core as mx
    from bilqis_mlx.runtime.candidate import execution
    from bilqis_mlx.runtime.bamf_operator.session_parts.native_session import execute_selected_visit

    capability = selection.offer.capability_id
    captured = {}
    original_admit = execution._learning_first_admit

    def record_batch(parent, cache, candidate, gradient, teacher_hparams, max_norm, prepared):
        require(candidate is None, "not the first candidate update")
        from bilqis_mlx.learning._atlas_candidate import step
        from scripts.bamf.profiling.issue1645.dynamics.displacement_analysis import write_update

        def observe_step(transaction, gradients, losses, group_eligible, hparams, *,
                         training_source_coordinates, spec, extents, max_norm):
            # The actual admission owner has validated the row coordinates.
            rows = prepared.training_batch.rows
            captured["delivery"] = {
                "selected_capability": capability,
                "row_count": len(rows),
                "rows_by_capability": dict(Counter(row.provenance.capability_id for row in rows)),
                "rows_by_role": dict(Counter(row.provenance.rehearsal or
                                             row.provenance.auxiliary_role or "direct" for row in rows)),
                "source_families": sorted({row.provenance.source_family_id for row in rows}),
                "episode_ids": [row.provenance.episode_id for row in rows],
                "validated_training_coordinates": training_source_coordinates,
            }
            captured["hyperparameters"] = asdict(hparams)
            mask, decay, authority = step._learning_first_optimizer_inputs(
                transaction, losses, group_eligible, spec, extents)
            captured["update"] = write_update(
                destination, transaction.optimizer, gradients,
                mask, decay, authority, hparams, max_norm=max_norm)
            raise Captured()

        with patch.object(step, "learning_first_candidate_step", observe_step):
            return original_admit(parent, cache, candidate, gradient,
                                  teacher_hparams, max_norm, prepared)
    roles = (getattr(parent, "championship_state", None) or {}).get("active_roles", {})
    policy = getattr(selection, "policy", None)
    captured["active_adviser_roles"] = len(roles)
    captured["policy"] = policy
    captured["visit_id"] = selection.visit.identity.visit_id
    started = time.monotonic()
    mx.reset_peak_memory()
    try:
        with patch.object(execution, "_learning_first_admit", record_batch):
            outcome = execute_selected_visit(
                run, parent, context, atlas, feature, selection, cache, 1, 100,
                None, 0, None, None, None, emit_progress=lambda *_: None,
                invalid=lambda reason: require(False, reason))
            captured["status"] = outcome.status
            require(outcome.status == "PERFECT_TARGET_SKIPPED", "unexpected un-intercepted outcome")
    except Captured:
        captured["stopped_before_candidate_admission"] = True
    require(captured.get("stopped_before_candidate_admission") or
            captured.get("status") == "PERFECT_TARGET_SKIPPED", "native boundary not reached")
    destination.mkdir(exist_ok=True)
    captured["wall_seconds"] = time.monotonic() - started
    captured["mlx_peak_bytes"] = mx.get_peak_memory()
    (destination / "receipt.json").write_text(json.dumps(captured, indent=2))
    return captured


def select_and_capture(run, parent, context, atlas, feature, cache, destination, capabilities):
    from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
    from bilqis_mlx.runtime.accepted_priority_visit import accepted_priority_school
    from bilqis_mlx.runtime.foundation_teacher_owner import select_foundation_priority_visit
    import mlx.core as mx

    program = schedule_program_from_executable_release(context.release)
    school = accepted_priority_school(
        parent, program, candidate_identity_sha256=cache._candidate_identity_sha256)
    receipts = {}
    selected = select_foundation_priority_visit(
        run, context, atlas, program=program, school=school,
        accepted_parent=parent, accepted_cache=cache, logical_batch_size=32)
    natural = selected.offer.capability_id if selected.status == "TEACHER_SELECTED" else None
    ordered = ((natural,) + tuple(cap for cap in capabilities if cap != natural)
               if natural in capabilities else capabilities)
    for capability in ordered:
        other = frozenset(cap for cap in context.release.execution_plan.capability_map
                          if cap != capability)
        selection = selected if capability == natural else select_foundation_priority_visit(
            run, context, atlas, program=program, school=school,
            accepted_parent=parent, accepted_cache=cache,
            logical_batch_size=32, resource_holds=other)
        if selection.status != "TEACHER_SELECTED":
            receipts[capability] = {"status": selection.status, "holds": list(selection.holds)}
        else:
            require(selection.offer.capability_id == capability, "unexpected selection")
            receipts[capability] = capture_selected(
                run, parent, context, atlas, feature, selection, cache, destination / capability)
        receipts[capability]["selection_scope"] = "natural" if capability == natural else "diagnostic restriction, other capabilities held"
        print(json.dumps({"target": capability, "status": receipts[capability].get("status", "CAPTURED"),
                          "delivery": receipts[capability].get("delivery")}), flush=True)
        mx.clear_cache()
    return receipts


def main():
    import argparse
    import resource
    import mlx.core as mx
    from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES
    from scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics import isolated_copy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("plane", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--capability", choices=CAPABILITIES, action="append")
    parser.add_argument("--protected", type=Path, required=True)
    parser.add_argument("--protected-result-sha256", required=True)
    parser.add_argument("--cadence-projection-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    destination = args.destination.resolve()
    result_path = args.protected / "result.json"
    require(file_digest(result_path) == args.protected_result_sha256,
            "protected result digest mismatch")
    reference = json.loads(result_path.read_text())
    require(reference["source_custody"] == custody(args.source),
            "protected probe source custody mismatch")
    require(reference["manifest_sha256"] ==
            json.loads((args.source / "bamf-state.json").read_text())["manifest_sha256"],
            "protected probe parent mismatch")
    run, before = isolated_copy(args.source.resolve(), args.plane.resolve(), destination)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
    from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
    mx.set_memory_limit(12*1024**3)
    mx.set_cache_limit(0)
    try:
        with evidence_mode(strict=False):
            # The projection is path-bound. A clone has no durable cadence
            # projection at its new path; use the official replay owner, not
            # a fabricated cadence or an edit to the original run.
            from bilqis_mlx.runtime.active_grade_cadence_replay import (
                authenticated_cadence_attempts, rebuild_authenticated_cadence_attempts,
            )
            if args.cadence_projection_root is None:
                rebuild_authenticated_cadence_attempts(run)
                cadence = {"mode": "full_authenticated_replay"}
            else:
                from scripts.bamf.profiling.issue1645.dynamics.cadence_custody import (
                    restore_disposable_projection,
                )
                cadence = restore_disposable_projection(
                    args.cadence_projection_root.resolve(), run, destination / "data-plane.sqlite3")
            authenticated_cadence_attempts(run)
            (destination / "cadence-preflight.json").write_text(json.dumps(cadence, indent=2))
            print(json.dumps({"cadence_preflight": cadence}), flush=True)
            if args.preflight_only:
                return
            parent, context, atlas, feature = _execution_context(run)
            cache = context._accepted_runtime_host._accepted_cache
            receipts = select_and_capture(run, parent, context, atlas, feature, cache,
                                          destination, tuple(args.capability or CAPABILITIES))
        from scripts.bamf.profiling.issue1645.dynamics.displacement_analysis import interference_matrix
        targets = tuple(cap for cap, item in receipts.items() if item.get("stopped_before_candidate_admission"))
        manifest = json.loads((run / "bamf-state.json").read_text())["manifest_sha256"]
        require(reference["manifest_sha256"] == manifest, "protected probe parent mismatch")
        require(reference["source_custody"] == before, "protected probe source custody mismatch")
        matrix = interference_matrix(destination, targets, args.protected, CAPABILITIES)
        (destination/"mixed.json").write_text(json.dumps({
            "manifest_sha256":json.loads((run/"bamf-state.json").read_text())["manifest_sha256"],
            "source_custody":before, "cadence":cadence, "native_lessons":receipts, "interference":matrix,
            "process_peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "learning_gain":None,
        },indent=2))
    finally:
        require(custody(run)==before==custody(args.source),"accepted custody changed")


if __name__ == "__main__":
    main()
