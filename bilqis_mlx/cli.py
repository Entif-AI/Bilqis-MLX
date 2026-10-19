"""Human-facing MLX operator commands; live training still gated by proof."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
import json
from pathlib import Path
import signal
import sys

from bilqis_mlx.runtime.disk import assert_headroom
from .source import AUDITED_PARENT
from .grade_a_release import RELEASE as GRADE_A_RELEASE
from .factory.live_releases import (
    INITIAL_RELEASE as LIVE_GRADE_A_RELEASE,
    BOOLEAN_RELEASE as LIVE_GRADE_B_RELEASE,
    BOOLEAN_COMPOSITE_RELEASE as LIVE_GRADE_B_COMPOSITE_RELEASE,
    BOOLEAN_IDENTIFICATION_RELEASE as LIVE_GRADE_B_IDBOOLOPS_RELEASE,
    NUMERIC_RELEASE as LIVE_GRADE_C_RELEASE,
)
from .numeric_staircase import RELEASE as STAIRCASE_RELEASE
from .paths import REPO_ROOT, LEGACY_SOURCE, LEGACY_CHECKPOINTS, active_run_dir
from bilqis_mlx.presentation.spiral_dashboard import Dashboard, TABLES

ROOT = REPO_ROOT
DEFAULT_RUN = active_run_dir()
GRADE_A_MANIFEST = ROOT / "docs" / "provenance" / "GRADE_A_CANDIDATE_MANIFEST_V2.json"
LEGACY_ROOT = LEGACY_SOURCE
ORIGINAL_CHECKPOINT = LEGACY_CHECKPOINTS / AUDITED_PARENT.basename


def _qualification_scope() -> dict:
    """Report prior evidence accurately without replaying neural steps."""
    return {
        "disposable_full_student_optimizer_continuation": {
            "status": "PREVIOUSLY_VERIFIED_CPU_AND_APPLE_GPU",
            "scope": "ONE_DETACHED_STEP_AND_COMPLETE_39_TENSOR_ADAMW_RESTART",
            "evidence": "docs/evidence/grades/GRADE_A_REPAIR_AND_BACKEND_20261015.md",
            "recheck": "npm run mlx:qualify",
            "freshly_rerun_by_this_command": False,
        },
        "human_live_grade_a_trainer_end_to_end_qualified": False,
        "human_experimental_trainer_implemented": True,
        "operator_release": "HUMAN_EXPLICIT_--human-run_ONLY",
    }


def _latest_session_stop(run_dir: Path, generation: int, step: int) -> dict | None:
    """The append-only event ledger owns per-invocation stop reasons."""
    events = run_dir / "events.jsonl"
    if not events.is_file():
        return None
    lines = events.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    event = json.loads(lines[-1])
    if (event.get("event") not in ("GRADE_A_SESSION_STOPPED", "SCHOOL_SESSION_STOPPED") or
            event.get("generation") != generation or
            event.get("optimizer_step") != step):
        return None
    return {"reason": event["stop_reason"],
            "visits_this_command": event["visits_this_command"],
            "elapsed_seconds": event["elapsed_seconds"],
            "time_limit_minutes": event["minutes"],
            "max_visits": event["max_visits"],
            "disk_free_gib": round(event["free_bytes"]/1024**3, 3)
                if "free_bytes" in event else None}


def _inspect(run_dir: Path) -> dict:
    state = run_dir / "state.json"
    if state.is_file():
        saved = json.loads(state.read_text(encoding="utf-8"))
        if saved.get("schema") == "bilqis.mlx.human-grade-a-trainer/v1":
            school = saved["school"]
            active = school["active_grades"]
            grade = active[school["grade_index"]]
            student = school["current_student"]
            # The historical ABI prefix is not the active student's size.
            # Read the actual checkpoint-bound parameter geometry, and show
            # stale pre-growth metadata without silently rewriting evidence.
            saved_embedding_shape = saved.get("parameter_shapes", {}).get("embedding.weight")
            actual_tokens = (saved_embedding_shape[0] if saved_embedding_shape else None)
            reported_tokens = saved.get("config", {}).get("vocab_size")
            return {
                "status": saved["result"],
                "grade": grade, "phase": school["stage"],
                "revalidation_target_grade": school.get("revalidation_target_grade"),
                "visits": school["visits"],
                "optimizer_step": student["optimizer_step"],
                "checkpoint_sha256": student["sha256"],
                "vocabulary": {
                    "active_checkpoint_token_count": actual_tokens,
                    "declared_config_token_count": reported_tokens,
                    "metadata_reconciliation_needed": (
                        reported_tokens != actual_tokens
                        if actual_tokens is not None and reported_tokens is not None
                        else "NOT_MEASURED"),
                },
                "champion_pointer_count": len(school["champions"]),
                "championship_epoch": ({
                    "introduced_grade": saved["mentor_epoch"]["introduced_grade"],
                    "baseline_sha256": saved["mentor_epoch"]["baseline"]["sha256"],
                    "baseline_optimizer_step":
                        saved["mentor_epoch"]["baseline"]["optimizer_step"],
                    "earned_active_roles":
                        len(saved["mentor_epoch"].get("active_roles", {})),
                    "active_soup_votes": {
                        grade: item["vote_count"]
                        for grade, item in saved["mentor_epoch"].get(
                            "active_grade_soups", {}).items()},
                    "archived_champion_roles":
                        len(saved.get("graduation_perfect", {})),
                    "archived_soup_grades":
                        sorted(saved.get("grade_soups", {})),
                    "active_baseline_advisers": 0 if saved["mentor_epoch"].get(
                        "guidance_policy") == "bilqis.mlx.earned-champions-only/v1"
                        else "LEGACY_POLICY_REQUIRES_RESET",
                    "championship_eligibility_after_step":
                        saved["mentor_epoch"].get(
                            "championship_eligibility_after_step"),
                    "administrative_empty_reset":
                        saved["mentor_epoch"].get("active_championship_reset"),
                    "legacy_mid_grade_activation":
                        saved["mentor_epoch"].get("experimental_refresh") ==
                        "MID_GRADE_FROZEN_CURRENT_STUDENT",
                } if saved.get("mentor_epoch") is not None else None),
                "capability_best_pointer_count": len(saved.get("capability_best", {})),
                "capability_best_bundle_count": len({
                    item["checkpoint"]["sha256"]
                    for item in saved.get("capability_best", {}).values()}),
                "teacher_events": saved["teacher"]["events"],
                "teacher_strategy_count": len(saved["teacher"]["strategies"]),
                "whole_student_peaks": [{
                    "scope_sha256": peak["scope_sha256"],
                    "numeric_maximum": peak.get("numeric_maximum"),
                    "correct": peak["correct"], "total": peak["total"],
                    "optimizer_step": peak["checkpoint"]["optimizer_step"],
                    "checkpoint_sha256": peak["checkpoint"]["sha256"]}
                    for peak in saved.get("whole_student_peaks", ())],
                "experimental_retention_settings": (saved.get("learning_experiment") or {}).get("settings"),
                "retention_settings": (saved.get("learning_experiment") or {}).get("settings"),
                "last_exam": saved["last_exam"],
                "last_session_stop": _latest_session_stop(
                    run_dir, saved["generation"], student["optimizer_step"]),
                "grade_a_release": LIVE_GRADE_A_RELEASE if saved.get("curriculum_mode") in (LIVE_GRADE_B_RELEASE, LIVE_GRADE_B_COMPOSITE_RELEASE, LIVE_GRADE_B_IDBOOLOPS_RELEASE) else saved.get("curriculum_mode") or GRADE_A_RELEASE,
                "historical_source_release": GRADE_A_RELEASE,
                "grade_a_curriculum_mode": (LIVE_GRADE_A_RELEASE if saved.get("curriculum_mode") in (LIVE_GRADE_B_RELEASE, LIVE_GRADE_B_COMPOSITE_RELEASE, LIVE_GRADE_B_IDBOOLOPS_RELEASE)
                                             else saved.get("curriculum_mode", "HISTORICAL_FIXED_72")),
                "grade_b_curriculum_mode": saved.get("curriculum_mode") if saved.get("curriculum_mode") in (LIVE_GRADE_B_RELEASE, LIVE_GRADE_B_COMPOSITE_RELEASE, LIVE_GRADE_B_IDBOOLOPS_RELEASE) else None,
                "grade_b_source_admitted": saved.get("curriculum_mode") in (LIVE_GRADE_B_RELEASE, LIVE_GRADE_B_COMPOSITE_RELEASE, LIVE_GRADE_B_IDBOOLOPS_RELEASE, LIVE_GRADE_C_RELEASE, STAIRCASE_RELEASE),
                "grade_c_curriculum_mode": saved.get("curriculum_mode") if saved.get("curriculum_mode") in (LIVE_GRADE_C_RELEASE, STAIRCASE_RELEASE) else None,
                "introduction_stage": school.get("introduction_stage", 0),
                "numeric_maximum": saved.get("numeric_maximum"),
                "assessment_cohort_sha256": (saved.get("last_exam") or {}).get("cohort_sha256"),
                "source_grounded_grade_a_admitted": True,
                **_qualification_scope(),
                "human_live_grade_a_trainer_end_to_end_qualified": "A" in school["champions"],
                "neural_training_started_by_this_command": False,
                "run_dir": str(run_dir),
                "repository_local_source": str(LEGACY_ROOT),
            }
        if saved.get("schema") != "bilqis.mlx.letter-grade/v1":
            raise ValueError("UNRECOGNIZED_SCHOOL_RUN_SCHEMA")
        grade_index = saved.get("grade_index", 0)
        active_grades = saved.get("active_grades") or []
        grade = active_grades[grade_index] if 0 <= grade_index < len(active_grades) else "INVALID"
        return {"status":"PREPARED_SOURCE_STATE_READ_ONLY",
                "grade":grade,"phase":saved.get("stage"),
                "revalidation_target_grade":saved.get("revalidation_target_grade"),
                "visits":saved.get("visits",0),
                "optimizer_step":(saved.get("current_student") or {}).get("optimizer_step"),
                "checkpoint_sha256":(saved.get("current_student") or {}).get("sha256"),
                "champion_pointer_count":len(saved.get("champions") or {}),
                **_qualification_scope(),
                "neural_training_started_by_this_command":False,
                "run_dir":str(run_dir)}
    return {"status":"GRADE_A_EXPERIMENTAL_HUMAN_LAUNCH_AVAILABLE",
            "grade":"A","phase":"READY_FOR_HUMAN_GRADE_A_START",
            "historical_seed":AUDITED_PARENT.__dict__,
            "grade_a_release": LIVE_GRADE_A_RELEASE,
            "historical_source_release": GRADE_A_RELEASE,
            "grade_a_curriculum": "SIX_SOURCE_TYPED_PREDICATES_FRESH_GENERATED_COHORTS",
            "grade_a_curriculum_mode": LIVE_GRADE_A_RELEASE,
            **_qualification_scope(),
            "source_grounded_grade_a_admitted":True,
            "neural_training_started_by_this_command":False,
            "run_dir":str(run_dir)}


def _print_status(result: dict) -> int:
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def status(run_dir: Path):
    return _print_status(_inspect(run_dir))


def _source_paths(legacy_code_root: Path | None, champion_checkpoint: Path | None):
    legacy = legacy_code_root if legacy_code_root is not None else LEGACY_ROOT
    checkpoint = champion_checkpoint if champion_checkpoint is not None else (
        legacy / "runs" / "primitive-consolidation-v16-triplets" / AUDITED_PARENT.basename
        if legacy_code_root is not None else ORIGINAL_CHECKPOINT)
    return legacy, checkpoint


def _boolean_revision_preflight(run_dir: Path, legacy_root: Path, *, resume: bool,
                                boolean_composite: bool, boolean_idboolops: bool,
                                checkpoint_sha256: str | None) -> dict:
    """Describe optional same-grade Boolean revisions without neural mutation."""
    if not boolean_composite and not boolean_idboolops:
        return {}
    if not resume:
        if boolean_composite:
            raise ValueError("BOOLEAN_COMPOSITE_REQUIRES_RESUME")
        raise ValueError("BOOLEAN_IDBOOLOPS_REQUIRES_RESUME")
    if not isinstance(checkpoint_sha256, str) or not checkpoint_sha256:
        raise ValueError("BOOLEAN_REVISION_SOURCE_STUDENT_MISSING")

    from .boolean_composite import CAPABILITY as COMPOSITE_CAPABILITY
    from .boolean_composite import RELEASE as COMPOSITE_RELEASE
    from .boolean_composite import build_course as build_composite
    from .boolean_identification import CAPABILITY as ID_CAPABILITY
    from .boolean_identification import RELEASE as ID_RELEASE
    from .boolean_identification import build_course as build_identification
    from .curriculum import BOOLEAN_OPERATORS
    from .factory.live_releases import initial_course, boolean_successor
    from .grade_a_release import accepted_grade_a

    saved = json.loads((run_dir / "state.json").read_text())
    mode = saved.get("curriculum_mode")
    accepted = accepted_grade_a(json.loads(GRADE_A_MANIFEST.read_text()))
    parent_b = boolean_successor(initial_course(accepted), legacy_root)
    composite = build_composite(parent_b, legacy_root)
    result = {}
    if boolean_composite:
        if mode not in (LIVE_GRADE_B_RELEASE, COMPOSITE_RELEASE):
            raise ValueError("BOOLEAN_COMPOSITE_REQUIRES_EXISTING_GRADE_B")
        result["boolean_composite"] = {
            "release": composite.version,
            "already_enrolled": mode == COMPOSITE_RELEASE,
            "next_capability": None if mode == COMPOSITE_RELEASE else COMPOSITE_CAPABILITY,
            "grade_b_exam_items": sum(count for _, count in composite.grades[-1].exam_item_counts),
            "cumulative_exam_items": sum(count for grade in composite.grades
                                         for _, count in grade.exam_item_counts),
            "source_student_sha256": checkpoint_sha256,
            "neural_updates": 0,
        }
    if boolean_idboolops:
        allowed = (LIVE_GRADE_B_COMPOSITE_RELEASE, ID_RELEASE)
        if mode not in allowed and not (boolean_composite and mode == LIVE_GRADE_B_RELEASE):
            raise ValueError("BOOLEAN_IDBOOLOPS_REQUIRES_COMPOSITE_GRADE_B")
        proposal = build_identification(composite, legacy_root)
        result["boolean_idboolops"] = {
            "release": proposal.version,
            "already_enrolled": mode == ID_RELEASE,
            "next_capability": None if mode == ID_RELEASE else ID_CAPABILITY,
            "answer_choices": len(BOOLEAN_OPERATORS),
            "random_guess_probability": 1 / len(BOOLEAN_OPERATORS),
            "grade_b_exam_items": sum(count for _, count in proposal.grades[-1].exam_item_counts),
            "cumulative_exam_items": sum(count for grade in proposal.grades
                                         for _, count in grade.exam_item_counts),
            "source_student_sha256": checkpoint_sha256,
            "neural_updates": 0,
        }
    return result


def preflight(run_dir: Path, *, resume=False, verify_source=False,
              legacy_code_root: Path | None = None, champion_checkpoint: Path | None = None,
              numeric_staircase=False, boolean_composite=False, boolean_idboolops=False,
              retention_enabled=True,
              boolean_association_bridge=False):
    legacy_root, original_checkpoint = _source_paths(legacy_code_root, champion_checkpoint)
    existing = (run_dir / "state.json").is_file()
    if resume and not existing:
        raise ValueError("RESUME_EXPLICIT_BUT_NO_SAVED_NEW_SCHOOL_RUN")
    if not resume and existing:
        raise ValueError("NEW_RUN_WOULD_OVERWRITE_SAVED_SCHOOL_USE_RESUME")
    if boolean_association_bridge and not resume:
        raise ValueError("BOOLEAN_ASSOCIATION_BRIDGE_REQUIRES_RESUME")
    snapshot = _inspect(run_dir)
    snapshot.update({"result":"PREFLIGHT_ONLY_NO_NEURAL_UPDATES",
                     "start_behavior":"EXPLICIT_SAVED_STATE_RESUME" if resume else "GRADE_A_NEW_RUN",
                     "blockers":[],
                     "retention_mode": ("DEFAULT_PROTECTED" if retention_enabled else
                                        "EXPLICIT_UNPROTECTED"),
                     "experimental_risks":["FIRST_HUMAN_RUN_NOT_YET_OBSERVED",
                                           "FULL_NEW_ITHKUIL_MORPHOLOGY_NOT_YET_CERTIFIED"],
                     "operator_constraint":"HUMAN_ONLY_NEURAL_OPTIMIZER_UPDATES"})
    if resume and snapshot.get("phase") == "AWAITING_NEXT_GRADE":
        # Source-only preflight is release/provider driven. The CLI never picks
        # a successor from a hard-coded grade letter.
        from .factory.live_releases import (
            course_for_mode, initial_course, preflight_successor,
            resolve_admitted_courses,
        )
        from .grade_a_release import accepted_grade_a
        manifest = json.loads(GRADE_A_MANIFEST.read_text(encoding="utf-8"))
        saved = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        accepted = accepted_grade_a(manifest)
        initial = initial_course(accepted)
        admitted = resolve_admitted_courses(
            accepted, legacy_root, saved, include_prospective=False)
        current = course_for_mode(admitted, saved.get("curriculum_mode"), initial)
        successor = preflight_successor(current, legacy_root, manifest, saved)
        snapshot.update(successor["details"])
        snapshot["blockers"].extend(successor["blockers"])
    snapshot["grade_a_source_manifest"] = "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"
    if numeric_staircase:
        if not resume:
            raise ValueError('NUMERIC_STAIRCASE_REQUIRES_RESUME')
        from .factory.live_releases import numeric_registry_graph as registry_graph
        from .numeric_staircase import build_course, INITIAL_MAXIMUM, FINAL_MAXIMUM
        from .grade_a_release import accepted_grade_a
        from .compatibility.historical_live_release import resume_grade_courses
        from .factory.live_releases import boolean_successor as admitted_b
        saved = json.loads((run_dir/'state.json').read_text())
        if saved.get('curriculum_mode') not in (LIVE_GRADE_C_RELEASE, STAIRCASE_RELEASE):
            raise ValueError('NUMERIC_STAIRCASE_REQUIRES_EXISTING_C')
        parent_a, parent_b = resume_grade_courses(accepted_grade_a(
            json.loads(GRADE_A_MANIFEST.read_text())), legacy_root, saved)
        maximum = saved['numeric_maximum'] if saved['curriculum_mode'] == STAIRCASE_RELEASE else INITIAL_MAXIMUM
        proposal = build_course(parent_b or admitted_b(parent_a, legacy_root),
                                registry_graph(), maximum=maximum)
        snapshot['numeric_staircase'] = {'release': proposal.version,
            'initial_maximum': INITIAL_MAXIMUM, 'final_maximum': FINAL_MAXIMUM,
            'resume_maximum': maximum, 'source_student_sha256': snapshot['checkpoint_sha256'],
            'neural_updates': 0, 'next_capability': 'C.COUNT' if saved['curriculum_mode'] != STAIRCASE_RELEASE else None}
    snapshot.update(_boolean_revision_preflight(
        run_dir, legacy_root, resume=resume,
        boolean_composite=boolean_composite, boolean_idboolops=boolean_idboolops,
        checkpoint_sha256=snapshot.get("checkpoint_sha256")))
    if verify_source:
        from .grade_a_manifest import verify_manifest
        source = json.loads(GRADE_A_MANIFEST.read_text(encoding="utf-8"))
        receipt = verify_manifest(source, legacy_root, original_checkpoint)
        snapshot["source_manifest_preflight"] = {
            "status": "PINNED_HISTORICAL_SOURCE_VERIFIED",
            "verified_items": receipt["verified_items"],
            "exam_rubric_sha256": receipt["exam_rubric_sha256"],
            "original_candidate_manifest_release_flag": False,
            "grade_a_user_acceptance_is_separate": True,
        }
    else:
        snapshot["source_manifest_preflight"] = "NOT_RERUN_USE_--verify-source"
    if boolean_association_bridge:
        from .boolean_association import VERSION, constructor_digest
        from .runtime.admission import admitted_release_supports_teaching_option
        saved = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        if not admitted_release_supports_teaching_option(run_dir, saved, VERSION):
            snapshot["blockers"].append("TEACHING_ENRICHMENT_NOT_ADMITTED_BY_FACTORY_RELEASE")
        snapshot["boolean_association_bridge"] = {
            "enabled_for_next_human_command": True,
            "version": VERSION,
            "generator_code_sha256": constructor_digest(),
            "authority": "FACTORY_RELEASE_TEACHING_OPTION",
            "exam_rubric_changed": False,
            "grade_a_pass_fail_changed": False,
            "grade_c_pass_fail_changed": False,
            "neural_updates": 0,
        }
    # The source remains unchanged. This probes only current disk headroom.
    snapshot["disk"] = assert_headroom(ROOT, required_bytes=0)
    return _print_status(snapshot)


def dashboard(run_dir: Path):
    from bilqis_mlx.presentation.dashboard import render
    render(run_dir)
    return 0


def diagnostics(run_dir: Path):
    from .diagnostics.audit import audit_saved_run
    return _print_status(audit_saved_run(run_dir))


def human_stop_summary(result: dict) -> str:
    """A legible termination receipt for the human-operated live terminal."""
    explanations = {
        "TIME_LIMIT_REACHED": "The requested time budget was reached.",
        "VISIT_LIMIT_REACHED": "The explicitly configured --max-visits cap was reached.",
        "GRADE_A_AWAITING_NEXT_GRADE": "Grade A is mastered; the admitted Grade B starts when the human operator resumes.",
        "GRADE_B_AWAITING_NEXT_GRADE": "Grades A and B passed cumulative revalidation; awaiting Grade C admission.",
        "WHOLE_SCHOOL_MASTERED": "Every grade in the explicitly complete school program passed at one whole student.",
        "AWAITING_TEACHER_SOUP": "Whole-school consolidation requires a separately verified frozen teacher-soup continuation.",
        "STAGNATION_REVIEW_REQUIRED": "The remaining required capabilities were withheld after repeated failed recovery rounds; they remain unqualified mastery debt for the next measured recovery run.",
        "DISK_RESERVE_REACHED": "Free space cannot cover the protected disk reserve plus another checkpoint.",
    }
    reason = result["stop_reason"]
    message = ("TRAINING STOPPED NORMALLY: " + reason + "\n" +
               explanations[reason] +
               f" Completed {result['visits_this_command']} visits in "
               f"{result['elapsed_seconds']:.1f} seconds, "
               f"optimizer step {result['optimizer_step']}.")
    if reason == "DISK_RESERVE_REACHED":
        message += (f"\nDisk: {result['disk_free_gib']:.2f} GiB free, "
                    f"{result['disk_reserve_gib']:.1f} GiB reserve + "
                    f"{result['disk_next_visit_gib']:.2f} GiB estimated next checkpoint. "
                    "No checkpoint cleanup or reserve reduction was performed.")
    quarantined = result.get("stagnation_quarantined") or ()
    if quarantined:
        message += ("\nStagnation review: withheld for this completed run: " +
                    ", ".join(quarantined) +
                    ". These capabilities still count against graduation and "
                    "will be eligible for measured re-entry on resume.")
    grace = result.get("stagnation_grace")
    if grace and result.get("optimizer_step", 0) < grace.get("until_optimizer_step", 0):
        remaining = grace["until_optimizer_step"] - result["optimizer_step"]
        message += ("\nStagnation grace: " + grace["grade"] +
                    " quarantine actuator suppressed for " + str(remaining) +
                    " more retained optimizer steps; diagnostics remain active.")
    if result.get("flash_mode"):
        message += ("\nFlash mode: fresh routine scheduling assessments remained active; "
                    "championship and promotion qualification work was deferred. "
                    "A saved ASSESS_* boundary remains real debt and will be evaluated on resume. "
                    "If flash reaches an all-perfect curriculum, a non-flash authoritative exam "
                    "is still required before qualification can advance.")
    if reason not in ("GRADE_A_AWAITING_NEXT_GRADE", "GRADE_B_AWAITING_NEXT_GRADE",
                      "WHOLE_SCHOOL_MASTERED", "AWAITING_TEACHER_SOUP"):
        message += ("\nTo continue: " +
                    result.get("safe_resume_command",
                               "npm run train -- --human-run --resume") +
                    " --minutes 90")
    return message + "\nHistorical dashboard: npm run dashboard"


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest="action",required=True)
    for name in ("status","dashboard","diagnostics","train"):
        p=actions.add_parser(name)
        p.add_argument("--run-dir",type=Path,default=DEFAULT_RUN)
        if name=="train":
            p.add_argument("--legacy-code-root", type=Path,
                           help="Explicit pinned predecessor source for an independent worktree")
            p.add_argument("--champion-checkpoint", type=Path,
                           help="Explicit original checkpoint; the existing source fingerprint still applies")
            p.add_argument("--dry-run",action="store_true")
            p.add_argument("--verify-source",action="store_true",
                           help="Recheck all 216 candidate records against the pinned source (neural-inert)")
            p.add_argument("--resume",action="store_true")
            p.add_argument('--numeric-staircase', action='store_true',
                           help='Warm-start C at 0..3, grow to 6 before MUL/DIV')
            p.add_argument('--boolean-composite', action='store_true',
                           help='Neural-inertly enroll B.COMPOSITE into the current Grade-B release')
            p.add_argument('--boolean-idboolops', action='store_true',
                           help='Neural-inertly enroll inverse Boolean primitive identification into Grade B')
            retention = p.add_mutually_exclusive_group()
            retention.add_argument('--no-retention', action='store_true',
                                   help='Explicit unprotected legacy teaching (separate independent --run-dir only)')
            # Existing terminal histories from human-run sessions can still
            # be replayed without accidentally changing the retention mode.
            retention.add_argument('--experimental-retention', action='store_true',
                                   help=argparse.SUPPRESS)
            p.add_argument('--retention-probe-each', '--experiment-probe-each',
                           dest='experiment_probe_each', type=int, default=6,
                           help='Source-oracled same-cohort rows per admitted capability')
            p.add_argument('--retention-mature-max-loss', '--experiment-mature-max-loss',
                           dest='experiment_mature_max_loss', type=int, default=1,
                           help='PROVISIONAL max new wrong answers on any protected capability')
            p.add_argument('--retention-introduction-extra-loss', '--experiment-introduction-extra-loss',
                           dest='experiment_introduction_extra_loss', type=int, default=2,
                           help='Additional tolerable losses during first acquisition')
            p.add_argument('--retention-protected-cap-limit', '--experiment-protected-cap-limit',
                           dest='experiment_protected_cap_limit', type=int, default=8,
                           help='Bounded grade-stratified sentinel panel per visit')
            p.add_argument("--human-run",action="store_true",
                           help="Explicitly authorizes actual optimizer steps by the human operator")
            p.add_argument("--minutes",type=int,default=90)
            p.add_argument("--steps-per-visit",type=int,default=16)
            p.add_argument("--max-visits",type=int,default=0,
                           help="Optional complete visit cap (default 0: use --minutes and disk reserve)")
            p.add_argument("--timing-trace", action="store_true",
                           help="Write low-overhead nanosecond timing markers under runs/.timing-traces")
            p.add_argument("--source-prefetch-workers", type=int, choices=(0, 1, 2), default=2,
                           help="Pure host-side lesson prep workers; 2 workers + main MLX lane = 3 lanes")
            p.add_argument("--flash-mode", action="store_true",
                           help="Defer expensive assessments while training; stop owing a real assessment")
            p.add_argument("--boolean-association-bridge", action="store_true",
                           help="Add 8 B-owned bridge questions per B step: 4 borrowing A assertions and 4 borrowing C assertions")
            p.add_argument("--batch-size",type=int,default=32)
            p.add_argument("--reserve-gib",type=float,default=100.)
            p.add_argument("--stagnation-grace-grade",type=str,default=None,
                           help="Human-authorized grade whose stagnation quarantine actuator is temporarily suppressed")
            p.add_argument("--stagnation-grace-steps",type=int,default=0,
                           help="Retained optimizer-step budget for the persisted stagnation grace")
            p.add_argument("--triplets","--triples",dest="triples",action="store_true",
                           help="Global weakest-three recovery is intrinsic to the new scheduler")
    return parser.parse_args(argv)


def _guard_independent_no_retention(args):
    if not args.no_retention:
        return
    target = args.run_dir.expanduser().resolve()
    if target == DEFAULT_RUN.expanduser().resolve():
        raise ValueError("NO_RETENTION_REQUIRES_INDEPENDENT_RUN_DIR")
    saved_path = target / "state.json"
    if (saved_path.is_symlink() or
            (saved_path.is_file() and
             json.loads(saved_path.read_text(encoding="utf-8")).get(
                 "learning_experiment") is not None)):
        raise ValueError("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN")


def _report_retention_plan(args):
    if args.no_retention:
        return
    from bilqis_mlx.learning.learning_experiment import Settings
    settings = Settings(
        probe_each=args.experiment_probe_each,
        mature_max_loss=args.experiment_mature_max_loss,
        introduction_extra_loss=args.experiment_introduction_extra_loss,
        protected_cap_limit=args.experiment_protected_cap_limit)
    print("DEFAULT RETENTION PLAN, NO NEURAL UPDATES: "+str(settings), file=sys.stderr)


def _timing_context(args):
    if not args.timing_trace:
        return None, nullcontext()
    from bilqis_mlx.runtime.timing_trace import TimingTrace, default_trace_path
    path = default_trace_path(args.run_dir)
    context = TimingTrace(
        path,
        metadata={
            "run_dir": str(args.run_dir),
            "max_visits": args.max_visits,
            "steps_per_visit": args.steps_per_visit,
            "batch_size": args.batch_size,
        })
    return path, context


def _report_timing_trace(path, *, stream):
    if path is not None and Path(path).exists():
        print("Timing trace: " + str(path), file=stream, flush=True)


def _prepare_live_board(args, build, ingest):
    visual = sys.stdout.isatty()
    board = build(args.run_dir, reserve_gib=args.reserve_gib) if visual else None
    live_mode = "FLASH" if args.flash_mode else "LIVE"
    def on_event(event):
        ingest(board, event)
        if event.get("event") not in ("GRADE_A_SESSION_STOPPED", "SCHOOL_SESSION_STOPPED"):
            board.mode = live_mode
            board.state["stop"] = "RUNNING"
        if event.get("_dashboard_redraw", True):
            board.draw()
    if board is not None:
        board.time_budget_seconds = (
            args.minutes * 60 if type(args.minutes) is int and args.minutes > 0
            else None
        )
        board.school_telemetry.begin_execution(
            grade=board.state.get("prefix"), step=board.state.get("step"))
        board.mode = (("FLASH | " if args.flash_mode else "") +
                      ("RESUMING" if args.resume else "STARTING"))
        board.state["stop"] = "PREPARING"
        board.state["attempted_steps"] = 0
        board.state["retained_steps"] = 0
        board.state["retained_visits"] = 0
        board.state["_rate_sample_eligible"] = True
        system_rows = board.rows["SYSTEM & QUALIFICATION"]
        previous = [row for row in system_rows if row.get("kind") != "STOP"]
        system_rows.clear()
        system_rows.extend(previous)
        board.draw()
    return board, on_event if visual else None


@contextmanager
def _human_sigint_guard():
    """Treat one terminal interrupt as the stop request; ignore cleanup echoes."""
    previous = signal.getsignal(signal.SIGINT)
    interrupted = False

    def handle_interrupt(_signum, _frame):
        nonlocal interrupted
        if interrupted:
            return
        interrupted = True
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def _main(args):
    trace_path = None
    try:
        if args.action=="status":return status(args.run_dir)
        if args.action=="dashboard":return dashboard(args.run_dir)
        if args.action=="diagnostics":return diagnostics(args.run_dir)
        _guard_independent_no_retention(args)
        if args.dry_run:
            _report_retention_plan(args)
            return preflight(args.run_dir,resume=args.resume,
                             verify_source=args.verify_source,
                             legacy_code_root=args.legacy_code_root,
                             champion_checkpoint=args.champion_checkpoint,
                             numeric_staircase=args.numeric_staircase,
                             boolean_composite=args.boolean_composite,
                             boolean_idboolops=args.boolean_idboolops,
                             retention_enabled=not args.no_retention,
                             boolean_association_bridge=args.boolean_association_bridge)
        if args.verify_source:
            raise ValueError("VERIFY_SOURCE_REQUIRES_DRY_RUN")
        if not args.human_run:
            print("TRAINING REQUIRES EXPLICIT HUMAN OPERATOR: add --human-run; "
                  "agents may run only --dry-run and tests. "
                  "Use npm run train -- --dry-run for preflight.",file=sys.stderr)
            return 2
        if args.flash_mode and not args.resume:
            raise ValueError("FLASH_MODE_REQUIRES_RESUME")
        if (args.legacy_code_root is not None and
                not args.legacy_code_root.expanduser().resolve().is_relative_to(ROOT)):
            raise ValueError("HUMAN_TRAINER_EXTERNAL_SOURCE_ROOT_FORBIDDEN")
        from .trainer import operate, operator_view
        from bilqis_mlx.presentation.dashboard import build, ingest
        board, on_event = _prepare_live_board(args, build, ingest)
        with operator_view(on_event):
            legacy_root, original_checkpoint = _source_paths(args.legacy_code_root, args.champion_checkpoint)
            trace_path, timing_context = _timing_context(args)
            with timing_context:
                result = operate(
                    args.run_dir, legacy_root, original_checkpoint, GRADE_A_MANIFEST,
                    resume=args.resume, minutes=args.minutes,
                    steps_per_visit=args.steps_per_visit, max_visits=args.max_visits,
                    batch_size=args.batch_size, reserve_gib=args.reserve_gib,
                    numeric_staircase=args.numeric_staircase,
                    boolean_composite=args.boolean_composite,
                    boolean_idboolops=args.boolean_idboolops,
                    retention_enabled=not args.no_retention,
                    experiment_probe_each=args.experiment_probe_each,
                    experiment_mature_max_loss=args.experiment_mature_max_loss,
                    experiment_introduction_extra_loss=args.experiment_introduction_extra_loss,
                    experiment_protected_cap_limit=args.experiment_protected_cap_limit,
                    stagnation_grace_grade=args.stagnation_grace_grade,
                    stagnation_grace_steps=args.stagnation_grace_steps,
                    source_prefetch_workers=args.source_prefetch_workers,
                    flash_mode=args.flash_mode,
                    boolean_association_bridge=args.boolean_association_bridge)
            if trace_path is not None:
                result["timing_trace_file"] = str(trace_path)
        if board is not None:
            board = build(args.run_dir, reserve_gib=args.reserve_gib)
            board.time_budget_seconds = (
                args.minutes * 60 if type(args.minutes) is int and args.minutes > 0
                else None
            )
            elapsed = result.get("elapsed_seconds")
            if isinstance(elapsed, (int, float)) and elapsed >= 0:
                board.started = board.clock() - elapsed
            board.mode = "STOPPED | " + result["stop_reason"]
            board.draw()
            print("\n" + human_stop_summary(result), flush=True)
            _report_timing_trace(result.get("timing_trace_file"), stream=sys.stdout)
            return 0
        return _print_status(result)
    except KeyboardInterrupt:
        print("HUMAN TRAINING INTERRUPTED: the last completed visit/checkpoint "
              "remains the resume point. Run npm run train -- --human-run --resume.",
              file=sys.stderr)
        _report_timing_trace(trace_path, stream=sys.stderr)
        return 130
    except (ValueError,RuntimeError,OSError,KeyError,IndexError) as err:
        print("OPERATOR BLOCKED: "+str(err),file=sys.stderr)
        _report_timing_trace(trace_path, stream=sys.stderr)
        if "HUMAN_TRAINER_NEW_RUN_HAS_EXISTING_CONTENT" in str(err):
            print("Saved school exists. To continue it, use: "
                  "npm run train -- --human-run --resume --minutes 90", file=sys.stderr)
        return 2


def main(argv=None):
    args=parse_args(argv)
    interrupt_guard = (
        _human_sigint_guard()
        if args.action == "train" and args.human_run and not args.dry_run
        else nullcontext()
    )
    with interrupt_guard:
        return _main(args)


if __name__=="__main__":
    raise SystemExit(main())
