"""Read-only source, curriculum, and storage preflight."""
from __future__ import annotations
from bilqis_mlx.compatibility.operator_cli.defaults import start_behavior
from bilqis_mlx.compatibility.cli_preflight import legacy_boolean_revision_preflight, legacy_boolean_profile_request, legacy_ignored_boolean_revision_flags, legacy_boolean_association_bridge_fields, legacy_numeric_staircase_preflight, legacy_profile_label
from bilqis_mlx.runtime.disk import assert_headroom
from bilqis_mlx.source import AUDITED_PARENT
from bilqis_mlx.state_dag import read_current
from pathlib import Path
import json
from .settings import GRADE_A_MANIFEST, LEGACY_ROOT, ORIGINAL_CHECKPOINT, ROOT
from .inspection import _inspect, _print_status


def _source_paths(legacy_code_root: Path | None, champion_checkpoint: Path | None):
    legacy = legacy_code_root if legacy_code_root is not None else LEGACY_ROOT
    checkpoint = champion_checkpoint if champion_checkpoint is not None else (
        legacy / "runs" / "primitive-consolidation-v16-triplets" / AUDITED_PARENT.basename
        if legacy_code_root is not None else ORIGINAL_CHECKPOINT)
    return legacy, checkpoint


def _boolean_revision_preflight(run_dir: Path, legacy_root: Path, *, resume: bool,
                                boolean_composite: bool, boolean_idboolops: bool,
                                checkpoint_sha256: str | None) -> dict:
    """Compatibility facade retained for callers of the historical CLI seam."""
    return legacy_boolean_revision_preflight(
        resume=resume, boolean_composite=boolean_composite,
        boolean_idboolops=boolean_idboolops,
        checkpoint_sha256=checkpoint_sha256)


def preflight(run_dir: Path, *, resume=False, verify_source=False,
              legacy_code_root: Path | None = None, champion_checkpoint: Path | None = None,
              numeric_staircase=False, boolean_composite=False, boolean_idboolops=False,
              full_grade_b=True,
              retention_enabled=True,
              boolean_association_bridge=False, model_topology=None):
    from bilqis_mlx.runtime.model_topology import CURRENT_DEFAULT_TOPOLOGY
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
                     "model_topology": (snapshot.get("model_topology") if resume else
                         (model_topology or CURRENT_DEFAULT_TOPOLOGY).to_record()),
                     "start_behavior":start_behavior(resume),
                     "blockers":[],
                     "retention_mode": ("DEFAULT_PROTECTED" if retention_enabled else
                                        "EXPLICIT_UNPROTECTED"),
                     "experimental_risks":["FIRST_HUMAN_RUN_NOT_YET_OBSERVED",
                                           "FULL_NEW_ITHKUIL_MORPHOLOGY_NOT_YET_CERTIFIED"],
                     "operator_constraint":"HUMAN_ONLY_NEURAL_OPTIMIZER_UPDATES"})
    _profile_transition(snapshot, run_dir, resume, full_grade_b)
    snapshot["grade_a_source_manifest"] = "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"
    if numeric_staircase:
        if not resume:
            raise ValueError('NUMERIC_STAIRCASE_REQUIRES_RESUME')
        saved = read_current(run_dir)
        factory = snapshot.get("factory")
        maximum = saved.get("numeric_maximum")
        snapshot["numeric_staircase"] = legacy_numeric_staircase_preflight(
            saved, maximum=maximum,
            checkpoint_sha256=snapshot["checkpoint_sha256"], factory=factory)
    snapshot.update(_boolean_revision_preflight(
        run_dir, legacy_root, resume=resume,
        boolean_composite=(boolean_composite if full_grade_b else False),
        boolean_idboolops=(boolean_idboolops if full_grade_b else False),
        checkpoint_sha256=snapshot.get("checkpoint_sha256")))
    _resume_profile(snapshot, run_dir, resume, full_grade_b, boolean_composite, boolean_idboolops)
    _source_preflight(snapshot, run_dir, resume, verify_source, legacy_root, original_checkpoint)
    if boolean_association_bridge:
        from bilqis_mlx.runtime.admission import admitted_release_supports_teaching_option
        saved = read_current(run_dir)
        bridge = legacy_boolean_association_bridge_fields()
        if not admitted_release_supports_teaching_option(
                run_dir, saved, bridge["version"]):
            snapshot["blockers"].append(
                "TEACHING_ENRICHMENT_NOT_ADMITTED_BY_FACTORY_RELEASE")
        snapshot["boolean_association_bridge"] = bridge
    # The source remains unchanged. This probes only current disk headroom.
    snapshot["disk"] = assert_headroom(ROOT, required_bytes=0)
    return _print_status(snapshot)


def _profile_transition(snapshot, run_dir, resume, full_grade_b):
    if resume and snapshot.get("phase") in (
            "AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT"):
        saved = read_current(run_dir)
        factory = snapshot.get("factory")
        if factory is not None:
            active_count = len(factory["active_grades"])
            canonical = factory["canonical_grades"]
            snapshot["next_profile_transition"] = {
                "next_grade": (
                    canonical[active_count]["id"]
                    if active_count < len(canonical) else None),
                "authority": "EXECUTABLE_FACTORY_PROFILE",
                "semantic_catalog_growth": (
                    active_count >= 2 and active_count < len(canonical)),
                "neural_updates_before_teaching": 0,
            }
        else:
            snapshot["legacy_profile"] = legacy_profile_label(
                saved, full_grade_b=full_grade_b)


def _resume_profile(snapshot, run_dir, resume, full_grade_b, boolean_composite, boolean_idboolops):
    if resume:
        saved = read_current(run_dir)
        factory = snapshot.get("factory")
        requested_profile = legacy_boolean_profile_request(
            full_grade_b=full_grade_b)
        if factory is not None:
            active_profile_id = factory["profile_id"]
            migration_required = (
                active_profile_id.startswith("school/boolean-kernel/and-iff")
                if full_grade_b else
                (len(factory["active_grades"]) <= 2 and
                 active_profile_id.startswith("school/boolean/full")))
            snapshot["execution_profile"] = {
                "active_profile_id": active_profile_id,
                "requested_boolean_profile_id": requested_profile,
                "migration_required": migration_required,
                "active_capabilities": list(factory["active_capabilities"]),
                "neural_updates": 0,
            }
        else:
            snapshot["legacy_profile"] = legacy_profile_label(
                saved, full_grade_b=full_grade_b)
        snapshot.update(legacy_ignored_boolean_revision_flags(
            full_grade_b=full_grade_b,
            boolean_composite=boolean_composite,
            boolean_idboolops=boolean_idboolops))


def _source_preflight(snapshot, run_dir, resume, verify_source, legacy_root, original_checkpoint):
    if verify_source:
        from bilqis_mlx.grade_a_manifest import verify_manifest
        source = json.loads(GRADE_A_MANIFEST.read_text(encoding="utf-8"))
        receipt = verify_manifest(source, legacy_root, original_checkpoint)
        snapshot["source_manifest_preflight"] = {
            "status": "PINNED_HISTORICAL_SOURCE_VERIFIED",
            "verified_items": receipt["verified_items"],
            "exam_rubric_sha256": receipt["exam_rubric_sha256"],
            "original_candidate_manifest_release_flag": False,
            "grade_a_user_acceptance_is_separate": True,
        }
        if resume:
            from bilqis_mlx.runtime.checkpoints import _reconcile_delivery_outbox
            from bilqis_mlx.compatibility.executable_projection import preflight_sealed_v1_migration
            saved = read_current(run_dir)
            outbox = saved.get("delivery_outbox")
            delivered = _reconcile_delivery_outbox(
                run_dir, saved, publish_missing=False)
            snapshot["outbox_preflight"] = (
                "NO_OUTBOX" if outbox is None else
                "VERIFIED_ALL_PUBLISHED" if delivered else
                "PENDING_DELIVERY_REPLAY_ON_RESUME")
            compatibility = preflight_sealed_v1_migration(
                run_dir, saved, source, legacy_root)
            if compatibility is not None:
                snapshot["resume_compatibility"] = compatibility
            elif saved.get("factory_admission_v2") is not None:
                from bilqis_mlx.runtime.admission import _read_executable_factory_release_artifact
                from bilqis_mlx.runtime.assessment import _verify_saved_cohort
                executable = _read_executable_factory_release_artifact(
                    run_dir, saved)
                cohort = _verify_saved_cohort(run_dir, saved, None)
                snapshot["resume_compatibility"] = {
                    "status": "VERIFIED_EXISTING_V2_WITH_SAVED_EVIDENCE",
                    "factory_release_sha256": executable.release_sha256,
                    "last_cohort_sha256": None if cohort is None else cohort.digest,
                    "neural_updates": 0,
                }
    else:
        snapshot["source_manifest_preflight"] = "NOT_RERUN_USE_--verify-source"
