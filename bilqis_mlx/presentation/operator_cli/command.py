"""Human-gated dispatch to the existing training owner."""
from __future__ import annotations
from contextlib import nullcontext
from pathlib import Path
import sys
from .settings import GRADE_A_MANIFEST, ROOT
from .inspection import _print_status, status
from .preflight import _source_paths, preflight
from .parser import parse_args
from .lifecycle import _experiment_budget, _guard_independent_no_retention, _human_sigint_guard, _report_retention_plan, _report_timing_trace, _timing_context
from .terminal import _prepare_live_board, _render_stopped_board, _report_operator_blocked
from .explain import _explain_code


def dashboard(run_dir: Path):
    from bilqis_mlx.presentation.dashboard import render
    render(run_dir)
    return 0


def diagnostics(run_dir: Path):
    from bilqis_mlx.diagnostics.audit import audit_saved_run
    return _print_status(audit_saved_run(run_dir))


def _main(args):
    trace_path = None
    try:
        if args.action=="status":return status(args.run_dir)
        if args.action=="dashboard":return dashboard(args.run_dir)
        if args.action=="diagnostics":return diagnostics(args.run_dir)
        if args.action in ("explain", "explain-error"):
            return _explain_code(args.code)
        from bilqis_mlx.runtime.atlas_admission import validate_atlas_command_request
        validate_atlas_command_request(args)
        _guard_independent_no_retention(args)
        from bilqis_mlx.runtime.topology_lifecycle import topology_from_file, operator_topology
        topology = topology_from_file(args.model_topology)
        if topology is not None:
            operator_topology(args.run_dir, resume=args.resume, requested=topology)
        if args.dry_run:
            _report_retention_plan(args)
            return preflight(args.run_dir,resume=args.resume,
                             verify_source=args.verify_source,
                             legacy_code_root=args.legacy_code_root,
                             champion_checkpoint=args.champion_checkpoint,
                             numeric_staircase=args.numeric_staircase,
                             boolean_composite=args.boolean_composite,
                             boolean_idboolops=args.boolean_idboolops,
                             full_grade_b=args.full_grade_b,
                             retention_enabled=not args.no_retention,
                             boolean_association_bridge=args.boolean_association_bridge, model_topology=topology)
        if args.verify_source:
            raise ValueError("VERIFY_SOURCE_REQUIRES_DRY_RUN")
        if not args.human_run:
            print("TRAINING REQUIRES EXPLICIT HUMAN OPERATOR: add --human-run; "
                  "ordinary and long-running training is human-operated. "
                  "User-authorized agent repair tests must be explicitly finite "
                  "and preserve the current student and own AdamW. "
                  "Use npm run train -- --dry-run for preflight.",file=sys.stderr)
            return 2
        if args.flash_mode and not args.resume:
            raise ValueError("FLASH_MODE_REQUIRES_RESUME")
        if (args.legacy_code_root is not None and
                not args.legacy_code_root.expanduser().resolve().is_relative_to(ROOT)):
            raise ValueError("HUMAN_TRAINER_EXTERNAL_SOURCE_ROOT_FORBIDDEN")
        from bilqis_mlx.runtime.checkpoints import operator_view
        from bilqis_mlx.presentation.dashboard import build, ingest
        board, on_event = _prepare_live_board(args, build, ingest)
        with operator_view(on_event):
            legacy_root, original_checkpoint = _source_paths(args.legacy_code_root, args.champion_checkpoint)
            trace_path, timing_context = _timing_context(args)
            with timing_context:
                experiment_budget = _experiment_budget(args)
                result = _invoke_learner(args, legacy_root, original_checkpoint, topology, experiment_budget)
            if trace_path is not None:
                result["timing_trace_file"] = str(trace_path)
        rendered = _render_stopped_board(board, build, args, result)
        if rendered is not None:
            return rendered
        return _print_status(result)
    except KeyboardInterrupt:
        print("HUMAN TRAINING INTERRUPTED: the last completed visit/checkpoint "
              "remains the resume point. Run npm run train -- --human-run --resume.",
              file=sys.stderr)
        _report_timing_trace(trace_path, stream=sys.stderr)
        return 130
    except (ValueError,RuntimeError,OSError,KeyError,IndexError) as err:
        return _report_operator_blocked(err, trace_path)


def main(argv=None):
    args=parse_args(argv)
    interrupt_guard = (
        _human_sigint_guard()
        if args.action == "train" and args.human_run and not args.dry_run
        else nullcontext()
    )
    with interrupt_guard:
        return _main(args)


def _invoke_learner(args, legacy_root, original_checkpoint, topology, experiment_budget):
    from bilqis_mlx.runtime.operating_loop import operate
    return operate(
        args.run_dir, legacy_root, original_checkpoint, GRADE_A_MANIFEST,
        resume=args.resume, minutes=args.minutes, model_topology=topology,
        steps_per_visit=args.steps_per_visit, max_visits=args.max_visits,
        batch_size=args.batch_size, reserve_gib=args.reserve_gib,
        numeric_staircase=args.numeric_staircase,
        boolean_composite=args.boolean_composite,
        boolean_idboolops=args.boolean_idboolops,
        full_grade_b=args.full_grade_b,
        retention_enabled=not args.no_retention,
        experiment_probe_each=args.experiment_probe_each,
        experiment_mature_max_loss=args.experiment_mature_max_loss,
        experiment_introduction_extra_loss=args.experiment_introduction_extra_loss,
        experiment_protected_cap_limit=args.experiment_protected_cap_limit,
        stagnation_grace_grade=args.stagnation_grace_grade,
        stagnation_grace_steps=args.stagnation_grace_steps,
        admit_next_grade_with_debt=args.admit_next_grade_with_debt,
        source_prefetch_workers=args.source_prefetch_workers,
        flash_mode=args.flash_mode,
        boolean_association_bridge=args.boolean_association_bridge,
        autonomous_curriculum=args.autonomous_curriculum,
        experiment_budget=experiment_budget)
