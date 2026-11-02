"""Checkpoint custody, immutable generations and idempotent event delivery."""
from __future__ import annotations

import bilqis_mlx.backup as _bilqis_mlx_backup
import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.data_plane as _data_plane
import bilqis_mlx.learning.capability_frontier as _learning_capability_frontier
import bilqis_mlx.learning.champions as _learning_champions
import bilqis_mlx.learning.epoch_championships as _learning_epoch_championships
import bilqis_mlx.learning.grade_soup as _learning_grade_soup
import bilqis_mlx.runtime.mlx_checkpoint as _runtime_mlx_checkpoint
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.state_dag as _state_dag
import bilqis_mlx.source as _bilqis_mlx_source
import contextlib as _contextlib
import dataclasses as _dataclasses
import json as _json
import os as _os
import pathlib as _pathlib
import sys as _sys


from .checkpoint_parts.journal import operator_view, _event_view, _record, _notify_viewer
from .checkpoint_parts.bundles import (
    _bundle_pointer, _clean_staged_bundles, _quarantine_newer_uncommitted_bundles,
)
from .checkpoint_parts.references import (
    _mentor_epoch_references, _regression_recovery_checkpoint,
    _verify_frozen_soup_custody, _verify_best_custody,
)
from .checkpoint_parts.boundary_events import _boundary_delivery_events
from .checkpoint_parts.outbox import (
    _with_delivery_outbox, _require_outbox_lineage, _ordinary_outbox_lineage,
    _outbox_source_generation, _expected_outbox_events, _observed_outbox_events,
    _reconcile_delivery_outbox,
)
from .checkpoint_parts.publication import _publish_boundary

_ADVANCE_SOURCE_FIELDS = (
    "delivery_outbox", "generation", "model_bundle", "run_id", "school",
    "source_manifest_sha256", "teacher_source_sha256",
)


def _persist(run_dir: _pathlib.Path, receipt: dict):
    """Persist one logical generation through the immutable Merkle state DAG."""
    return _state_dag.persist(run_dir, receipt)


def _recover_orphaned_commit(run_dir: _pathlib.Path, latest: dict) -> dict:
    """Complete a fully written generation whose state.json pointer lost a race to a crash.

    Call only under the exclusive operator lock and only with an already checked
    live source manifest; no model or optimizer is mutated here.
    """
    target = run_dir / "states" / f"{latest['generation']+1:07d}.json"
    if not target.exists():
        return latest
    if target.is_symlink() or not target.is_file():
        raise ValueError("HUMAN_TRAINER_RECOVERY_UNSAFE_GENERATION")
    proposed = _state_dag.read_generation(run_dir, latest["generation"] + 1)
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
        inspect_resume_topology(run_dir, proposed,
            ModelTopologySpec.from_record(latest["model_topology"]))
    # Verify every retained old/new whole-student pointer before publication.
    _verify_best_custody(run_dir, proposed)
    proposed = _state_dag.persist(run_dir, proposed)
    # Publish the recovered generation's original causal events before its
    # recovery annotation, retaining a legible ordered School50 history.
    _reconcile_delivery_outbox(run_dir, proposed)
    _record(run_dir, {"event": "SCHOOL_INTERRUPT_POINTER_RECOVERED", "grade": "A",
                      "generation": proposed["generation"],
                      "student_sha256": proposed["school"]["current_student"]["sha256"],
                      "optimizer_step": proposed["school"]["current_student"]["optimizer_step"]})
    return proposed


def _advance(run_dir, old: dict, school: _curriculum_scheduler.SchoolState, *,
             teacher=None, model_bundle=None, last_exam=None, result=None,
             frontier=None, persist=True):
    # One snapshot captures teacher learning, school progress and model pointer.
    if old.get("delivery_outbox") is not None:
        # A generation's event IDs cannot be inherited by a successor. First
        # prove this generation was durably committed, then reconcile the
        # original intent or fail before state mutation. Uncommitted event
        # intents must never be published on the strength of a transient dict.
        old_path = (_pathlib.Path(run_dir) / "states" /
                    f"{old['generation']:07d}.json")
        if old_path.is_symlink() or not old_path.is_file():
            raise ValueError("HUMAN_TRAINER_OUTBOX_ADVANCE_UNCOMMITTED_SOURCE")
        durable = _state_dag.read_generation_fields(
            run_dir, old["generation"], _ADVANCE_SOURCE_FIELDS)
        if not _ordinary_outbox_lineage(durable, durable.get("delivery_outbox")):
            durable = _state_dag.read_generation(run_dir, old["generation"])
        # Only *durable* outbox events have delivery authority. Transient
        # callers may carry a subsequently edited copy of a committed event;
        # requiring payload-object equality here mistakes a working copy for
        # its signed owner. Instead bind the ordered event IDs, run and
        # checkpoint to the immutable snapshot, then validate its original
        # exact payloads against the journal below. Never publish the caller's
        # potentially edited copy, and never lose/ignore an extra event ID.
        source_outbox = durable.get("delivery_outbox")
        candidate_outbox = old["delivery_outbox"]
        source_ids = (tuple(event.get("event_id") for event in source_outbox)
                      if isinstance(source_outbox, list) and
                      all(isinstance(event, dict) for event in source_outbox)
                      else None)
        candidate_ids = (tuple(event.get("event_id") for event in candidate_outbox)
                         if isinstance(candidate_outbox, list) and
                         all(isinstance(event, dict) for event in candidate_outbox)
                         else None)
        if (durable.get("run_id") != old.get("run_id") or
                durable.get("generation") != old.get("generation") or
                not source_ids or candidate_ids != source_ids or
                durable.get("model_bundle") != old.get("model_bundle") or
                durable.get("school", {}).get("current_student") !=
                old.get("school", {}).get("current_student") or
                durable.get("source_manifest_sha256") !=
                old.get("source_manifest_sha256") or
                durable.get("teacher_source_sha256") !=
                old.get("teacher_source_sha256")):
            raise ValueError("HUMAN_TRAINER_OUTBOX_ADVANCE_SOURCE_DRIFT")
        # Reconcile the *committed* owner, not the caller's proposed in-memory
        # next-generation metadata. A resume-time championship repair can
        # legitimately change unrelated fields before _advance is invoked;
        # using that transient dict would falsely fail signed v1->v2 lineage.
        _reconcile_delivery_outbox(run_dir, durable)
    record = dict(old)
    record.pop("delivery_outbox", None)
    record["generation"] = old["generation"] + 1
    record["school"] = _dataclasses.asdict(school)
    if teacher is not None:
        record["teacher"] = teacher
    if model_bundle is not None:
        record["model_bundle"] = model_bundle
    if last_exam is not None:
        record["last_exam"] = last_exam
        record.pop("fixed_frontier_exam", None)
    if result is not None:
        record["result"] = result
    if frontier is not None:
        record["capability_best"] = frontier
    if persist:
        record.pop("_pending_visit_events", None)
        if old.get("delivery_outbox") is not None:
            event = {"event": "SCHOOL_STATE_ADVANCED",
                     "generation": record["generation"],
                     "source_generation": old["generation"],
                     "student_sha256": school.current_student.sha256,
                     "optimizer_step": school.current_student.optimizer_step}
            record = _persist(run_dir, _with_delivery_outbox(record, (event,)))
            _reconcile_delivery_outbox(run_dir, record)
            return record
        return _persist(run_dir, record)
    return record
