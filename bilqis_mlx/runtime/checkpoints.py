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

from contextvars import ContextVar

_event_view = ContextVar("grade_a_event_view", default=None)


@_contextlib.contextmanager
def operator_view(callback):
    token = _event_view.set(callback)
    try:
        yield
    finally:
        _event_view.reset(token)


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


def _record(run_dir: _pathlib.Path, event: dict):
    path = run_dir / "events.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(_runtime_state._canonical(event) + "\n")
        stream.flush()
        _os.fsync(stream.fileno())
    if _event_view.get() is None:
        print(_json.dumps(event, sort_keys=True), flush=True)
    else:
        _notify_viewer(event)


def _notify_viewer(event: dict):
    """Send ephemeral operator telemetry without making it training evidence."""
    viewer = _event_view.get()
    if viewer is None:
        return
    try:
        viewer(event)
    except Exception as exc:
        print("DASHBOARD UNAVAILABLE: " + str(exc), file=_sys.stderr, flush=True)


def _bundle_pointer(run_dir: _pathlib.Path, name: str, parameters, optimizer, graph,
                    *, reserve_gib: float):
    stage_root = run_dir / ".bundle-staging"
    if stage_root.is_symlink() or (stage_root.exists() and not stage_root.is_dir()):
        raise ValueError("HUMAN_TRAINER_UNSAFE_STAGING_ROOT")
    stage_root.mkdir(exist_ok=True)
    stage_directory = stage_root / name
    directory = run_dir / "bundles" / name
    if directory.exists() or directory.is_symlink():
        raise ValueError("HUMAN_TRAINER_BUNDLE_ALREADY_PUBLISHED")
    metadata = _runtime_mlx_checkpoint.save_new_bundle(
        stage_directory, parameters, optimizer, source_digest=_bilqis_mlx_source.AUDITED_PARENT.sha256,
        semantic_catalog=graph, reserve_gib=reserve_gib)
    restored, restored_optimizer, manifest, restored_graph = (
        _runtime_mlx_checkpoint.load_semantically_bound_bundle(stage_directory))
    if (metadata != manifest or restored_graph != graph or
            list(restored) != list(parameters) or
            int(restored_optimizer.state["step"].item()) != int(optimizer.state["step"].item())):
        raise ValueError("HUMAN_TRAINER_COMPLETE_CHECKPOINT_READBACK_DRIFT")
    for filename in ("model-and-own-adamw.safetensors",
                     "semantic-catalog.json", "manifest.json"):
        fd = _os.open(stage_directory / filename, _os.O_RDONLY)
        try:
            _os.fsync(fd)
        finally:
            _os.close(fd)
    dir_fd = _os.open(stage_directory, _os.O_RDONLY)
    try:
        _os.fsync(dir_fd)
    finally:
        _os.close(dir_fd)
    directory.parent.mkdir(exist_ok=True)
    # The published bundles namespace must contain ONLY complete, read-back
    # verified three-file bundles. Failed writes remain in isolated staging.
    stage_directory.rename(directory)
    fd = _os.open(directory.parent, _os.O_RDONLY)
    try:
        _os.fsync(fd)
    finally:
        _os.close(fd)
    stage_root.rmdir()
    return _learning_champions.Checkpoint(metadata["safetensors_sha256"],
                      str(directory.relative_to(run_dir)),
                      metadata["optimizer_step"], True)


def _clean_staged_bundles(run_dir: _pathlib.Path) -> dict[str, tuple[str, ...]]:
    """Reconcile unpublished bundles without losing a possibly valid student."""
    stage = run_dir / ".bundle-staging"
    if not stage.exists() and not stage.is_symlink():
        return {"discarded": (), "quarantined": ()}
    if stage.is_symlink() or not stage.is_dir():
        raise ValueError("HUMAN_TRAINER_UNSAFE_STAGING_ROOT")
    expected = {"model-and-own-adamw.safetensors", "semantic-catalog.json",
                "manifest.json"}
    discarded, quarantined = [], []
    for folder in stage.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("HUMAN_TRAINER_UNKNOWN_STAGED_BUNDLE")
        files = list(folder.iterdir())
        if any(file.is_symlink() or not file.is_file() or file.name not in expected
               for file in files):
            raise ValueError("HUMAN_TRAINER_UNKNOWN_STAGED_BUNDLE_CONTENT")
        if (folder / "model-and-own-adamw.safetensors").exists():
            # Even if its manifest is incomplete, this is the only surviving
            # binary for updates possibly completed just before a crash. Keep
            # it outside active bundles for human custody recovery.
            custody = run_dir / ".bundle-quarantine"
            if custody.is_symlink() or (custody.exists() and not custody.is_dir()):
                raise ValueError("HUMAN_TRAINER_UNSAFE_BUNDLE_QUARANTINE")
            custody.mkdir(exist_ok=True)
            target = custody / folder.name
            if target.exists() or target.is_symlink():
                raise ValueError("HUMAN_TRAINER_QUARANTINE_IDENTITY_COLLISION")
            folder.rename(target)
            quarantined.append(folder.name)
        else:
            for file in files:
                file.unlink()
            folder.rmdir()
            discarded.append(folder.name)
    stage.rmdir()
    return {"discarded": tuple(discarded), "quarantined": tuple(quarantined)}


def _mentor_epoch_references(receipt):
    if receipt.get("mentor_epoch") is None:
        return ()
    from bilqis_mlx.learning.mentor_epoch import reference_checkpoints
    epochs = (*receipt.get("championship_epoch_history", ()), receipt["mentor_epoch"])
    return tuple(pointer for epoch in epochs
                 for pointer in (
                     *reference_checkpoints(epoch),
                     *(item["checkpoint"] for item in _learning_epoch_championships.active_frontier(epoch).values())))


def _verify_frozen_soup_custody(run_dir, receipt):
    """Verify both archived and earned soups without blending their rosters."""
    epoch_soups = (entry.get("active_grade_soups", {})
                   for entry in (*receipt.get("championship_epoch_history", ()),
                                 receipt["mentor_epoch"])
                   ) if receipt.get("mentor_epoch") is not None else ()
    for grade, soup in (*receipt.get("grade_soups", {}).items(),
                        *(pair for soups in epoch_soups for pair in soups.items())):
        if grade != soup.get("grade"):
            raise ValueError("GRADE_SOUP_CUSTODY_GRADE_DRIFT")
        _learning_grade_soup.verify_frozen_soup(run_dir, soup)
        if soup.get("previous"):
            older = soup["previous"] if isinstance(soup["previous"], list) else [soup["previous"]]
            for old in older:
                previous = run_dir / old["filename"]
                if (previous.parent != run_dir / "soups" or previous.is_symlink() or
                        not previous.is_file() or
                        not _data_plane.verify_file_digest(previous, old["sha256"])):
                    raise ValueError("GRADE_SOUP_PREVIOUS_BACKUP_DRIFT")


def _verify_best_custody(run_dir, receipt):
    school = receipt["school"]
    historical_pending = (receipt.get("historical_capability_best", {})
                          if receipt.get("legacy_frontier_pending_replay") else {})
    sources = [school["current_student"], *school["champions"].values(),
               *receipt.get("historical_grade_champions", {}).values(),
               *(cap["checkpoint"] for cap in receipt.get("capability_best", {}).values()),
               *(cap["checkpoint"] for cap in receipt.get("graduation_perfect", {}).values()),
               *(cap["checkpoint"] for cap in historical_pending.values())]
    protected = _learning_capability_frontier.pinned(receipt.get("capability_best", {}),
                       school["current_student"], school["champions"])
    protected |= _learning_capability_frontier.pinned(receipt.get("graduation_perfect", {}),
                        school["current_student"], school["champions"])
    if historical_pending:
        protected |= _learning_capability_frontier.pinned(historical_pending,
                            school["current_student"], school["champions"])
    for item in receipt.get("historical_grade_champions", {}).values():
        protected |= _learning_capability_frontier.pinned({}, item, {})
    if receipt.get('curriculum_parent'):
        sources.append(receipt['curriculum_parent'])
        protected |= _learning_capability_frontier.pinned({}, receipt['curriculum_parent'], {})
    for peak in receipt.get("whole_student_peaks", ()):
        if peak.get("schema") != "bilqis.mlx.whole-student-retention/v1":
            raise ValueError("WHOLE_STUDENT_PEAK_SCHEMA_DRIFT")
        source = peak["checkpoint"]
        sources.append(source)
        protected |= _learning_capability_frontier.pinned({}, source, {})
    for source in _mentor_epoch_references(receipt):
        sources.append(source)
        protected |= _learning_capability_frontier.pinned({}, source, {})
    for name in sorted(protected):
        root = run_dir / name
        if root.is_symlink() or root.parent != run_dir / "bundles":
            raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_PATH_DRIFT")
        manifest = _json.loads((root / "manifest.json").read_text())
        if not _data_plane.verify_file_digest(
                root / "model-and-own-adamw.safetensors",
                manifest["safetensors_sha256"]):
            raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_SHA_DRIFT")
        for ref in sources:
            if (ref["filename"] == name and
                    (manifest["safetensors_sha256"] != ref["sha256"] or
                     manifest["optimizer_step"] != ref["optimizer_step"])):
                raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_REFERENCE_DRIFT")
    _verify_frozen_soup_custody(run_dir, receipt)


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
    return _json.loads(_runtime_state._canonical(record))


def _boundary_delivery_events(record, pending, roles, exam_event):
    """Freeze truthful source-scored events before publishing state.json."""
    school = record["school"]
    completed_grade = (exam_event["grade"] if exam_event is not None else
                       school["active_grades"][school["grade_index"]])
    events = []
    for provisional in pending:
        event = dict(provisional)
        event["recovered_at_student_sha256"] = school["current_student"]["sha256"]
        event["checkpoint_status"] = "RECORDED_AT_BOUNDARY"
        events.append(event)
    if roles:
        frontier = record["capability_best"]
        slots = [frontier[key] for key in sorted(frontier)
                 if frontier[key]["capability"] in roles and
                 frontier[key]["checkpoint"]["sha256"] ==
                 school["current_student"]["sha256"]]
        if ({slot["capability"] for slot in slots} != set(roles) or
                len({slot["rubric"] for slot in slots}) != 1):
            raise ValueError("HUMAN_TRAINER_CAPABILITY_BEST_RECEIPT_DRIFT")
        events.append({"event": "SCHOOL_CAPABILITY_BEST_COMMITTED",
                       "grade": completed_grade, "generation": record["generation"],
                       "capabilities": list(roles), "rubric": slots[0]["rubric"],
                       "scores": {entry["capability"]: {
                           "correct": entry["correct"], "total": entry["total"]}
                           for entry in slots},
                       "evaluation_ids": {entry["capability"]: entry["evaluation_id"]
                                          for entry in slots},
                       "student_sha256": school["current_student"]["sha256"],
                       "optimizer_step": school["current_student"]["optimizer_step"]})
    if exam_event is not None:
        # A freshly enrolled numeric staircase intentionally has no prior
        # grade examination. A stop-boundary candidate comparison is valid.
        active_soups = (record["mentor_epoch"].get("active_grade_soups", {})
                        if record.get("mentor_epoch") is not None
                        else record.get("grade_soups", {}))
        for grade in (record.get("last_exam") or {}).get("grade_soups_refreshed", ()):
            snapshot = active_soups[grade]
            for shard in _learning_grade_soup.soup_shards(snapshot):
                event = {
                    "event": "SCHOOL_GRADE_SOUP_FROZEN",
                    "generation": record["generation"], "grade": grade,
                    "filename": shard["filename"], "sha256": shard["sha256"],
                    "recipe_sha256": shard["recipe_sha256"],
                    "vote_count": shard["vote_count"],
                    "covered_capabilities": shard.get(
                        "covered_capabilities", shard["perfect_capabilities"]),
                    "source_champion_shas": [item["checkpoint"]["sha256"]
                                              for item in shard["members"]],
                    "frozen_source_weights_only": True,
                }
                if snapshot.get("schema") == _learning_grade_soup.PARTITIONED_SCHEMA:
                    event.update({
                        "logical_grade_recipe_sha256": snapshot["recipe_sha256"],
                        "logical_grade_vote_count": snapshot["vote_count"],
                        "source_graph_sha256": shard["source_graph_sha256"],
                    })
                events.append(event)
        events.append(dict(exam_event))
    return tuple(events)


def _with_delivery_outbox(record: dict, events) -> dict:
    """Commit event intent atomically with the immutable student generation."""
    if not record.get("run_id") or type(record.get("generation")) is not int:
        raise ValueError("HUMAN_TRAINER_OUTBOX_MISSING_LINEAGE")
    prepared = dict(record)
    prepared.pop("_pending_visit_events", None)
    if not events:
        raise ValueError("HUMAN_TRAINER_OUTBOX_REQUIRES_EVENT")
    outbox = []
    for index, event in enumerate(events):
        if not isinstance(event, dict) or not event.get("event") or "event_id" in event:
            raise ValueError("HUMAN_TRAINER_OUTBOX_UNTRUSTED_EVENT")
        copy = _json.loads(_runtime_state._canonical(event))
        copy["event_id"] = _runtime_state._fingerprint(["school-generation-event/v1",
                                         record["run_id"], record["generation"],
                                         index, copy])
        outbox.append(copy)
    prepared["delivery_outbox"] = outbox
    return prepared


def _require_outbox_lineage(condition: bool) -> None:
    if not condition:
        raise ValueError("HUMAN_TRAINER_OUTBOX_LINEAGE_DRIFT")


def _outbox_source_generation(run_dir: _pathlib.Path, record: dict, outbox: list):
    source_generation = record["generation"]
    ordinary_lineage = all(
        isinstance(event, dict) and "event_id" in event and
        event["event_id"] == _runtime_state._fingerprint([
            "school-generation-event/v1", record["run_id"], source_generation,
            index, {k: v for k, v in event.items() if k != "event_id"}])
        for index, event in enumerate(outbox)
    )
    inherited = None
    if not ordinary_lineage:
        from bilqis_mlx.runtime.outbox_lineage import verified_inherited_v1_generation
        inherited = verified_inherited_v1_generation(run_dir, record)
        if inherited is not None:
            source_generation = inherited
    return source_generation, inherited


def _expected_outbox_events(record: dict, outbox: list, source_generation: int):
    expected = {}
    for index, event in enumerate(outbox):
        if not isinstance(event, dict) or "event_id" not in event:
            raise ValueError("HUMAN_TRAINER_OUTBOX_EVENT_ID_MISSING")
        payload = {k: v for k, v in event.items() if k != "event_id"}
        identity = _runtime_state._fingerprint([
            "school-generation-event/v1", record["run_id"],
            source_generation, index, payload])
        _require_outbox_lineage(
            event["event_id"] == identity and identity not in expected)
        expected[identity] = event
    return expected


def _observed_outbox_events(run_dir: _pathlib.Path, expected: dict):
    observed = set()
    observed_counts = {}
    journal = run_dir / "events.jsonl"
    if not journal.exists():
        return observed, observed_counts
    if journal.is_symlink() or not journal.is_file():
        raise ValueError("HUMAN_TRAINER_OUTBOX_UNSAFE_LEDGER")
    with journal.open(encoding="utf-8") as stream:
        for line in stream:
            item = _json.loads(line)
            identity = item.get("event_id")
            if identity in expected:
                if item != expected[identity]:
                    raise ValueError("HUMAN_TRAINER_OUTBOX_LEDGER_CONTENT_DRIFT")
                observed.add(identity)
                observed_counts[identity] = observed_counts.get(identity, 0) + 1
    return observed, observed_counts


def _reconcile_delivery_outbox(
        run_dir: _pathlib.Path, record: dict, *, publish_missing: bool = True):
    """Replay missing events; never duplicate or amend prior ledger history.

    Caller must hold the exclusive operator lock. JSONL write+fsync can succeed
    even if the process dies before acknowledging it, so dedupe by the exact
    immutable generation event ID *and* payload rather than a stale boolean.
    """
    outbox = record.get("delivery_outbox")
    if outbox is None:
        return False
    if not isinstance(outbox, list) or not outbox:
        raise ValueError("HUMAN_TRAINER_OUTBOX_INVALID")
    # Ordinarily all outbox IDs are bound to the current generation. A single
    # historical v1->v2 migration erroneously copied the previous outbox into
    # an otherwise valid immutable successor; accept that *only* with proven
    # signed predecessor identity and fully published, unmodified journal rows.
    # Most valid generations are not compatibility migrations. Avoid rereading
    # a 47 MB immutable predecessor when the ordinary current-generation IDs
    # already validate; verify an inherited predecessor only upon actual drift.
    source_generation, inherited = _outbox_source_generation(
        run_dir, record, outbox)
    expected = _expected_outbox_events(record, outbox, source_generation)
    observed, observed_counts = _observed_outbox_events(run_dir, expected)
    if inherited is not None:
        _require_outbox_lineage(
            observed == set(expected) and
            all(count == 1 for count in observed_counts.values()))
        return True
    if not publish_missing:
        # Neural-inert operator preflight may inspect custody, but must never
        # replay missing events or alter the append-only journal.
        return observed == set(expected)
    for event in outbox:
        if event["event_id"] not in observed:
            _record(run_dir, event)
    return True


def _publish_boundary(run_dir, record, pending, roles, *, exam_event=None):
    """Publish visits only after model and teacher are durably recoverable."""
    student_school = record["school"]
    # The scheduler may have moved B -> A for cumulative revalidation before
    # this grade-B examination's capability winners are published. Preserve
    # the *completed assessment grade* instead of the next scheduled grade.
    active_grade = (exam_event["grade"] if exam_event is not None else
                    student_school["active_grades"][student_school["grade_index"]])
    if record.get("delivery_outbox") is not None:
        if pending or roles or exam_event is not None:
            expect = _with_delivery_outbox(
                record, _boundary_delivery_events(record, pending, roles, exam_event))
            if expect["delivery_outbox"] != record["delivery_outbox"]:
                raise ValueError("HUMAN_TRAINER_OUTBOX_BOUNDARY_ARGUMENT_DRIFT")
        _reconcile_delivery_outbox(run_dir, record)
    else:
        # Old Grade A states predate immutable event publication. Keep their
        # established behavior and their source receipts byte-for-byte.
        for event in _boundary_delivery_events(record, pending, roles, exam_event):
            _record(run_dir, event)
    school = student_school
    retained = _learning_capability_frontier.pinned(record.get("capability_best", {}), school["current_student"],
                      school["champions"])
    if record.get('curriculum_parent'):
        retained |= _learning_capability_frontier.pinned({}, record['curriculum_parent'], {})
    for peak in record.get("whole_student_peaks", ()):
        retained |= _learning_capability_frontier.pinned({}, peak["checkpoint"], {})
    for source in _mentor_epoch_references(record):
        retained |= _learning_capability_frontier.pinned({}, source, {})
    retained |= _learning_capability_frontier.pinned(record.get("graduation_perfect", {}),
                       school["current_student"], school["champions"])
    for item in record.get("historical_grade_champions", {}).values():
        retained |= _learning_capability_frontier.pinned({}, item, {})
    if record.get("legacy_frontier_pending_replay"):
        retained |= _learning_capability_frontier.pinned(record.get("historical_capability_best", {}),
                           school["current_student"], school["champions"])
    _quarantine_newer_uncommitted_bundles(run_dir, retained,
                                          school["current_student"]["optimizer_step"])
    removed = _learning_capability_frontier.retire_bundles(run_dir, retained)
    if removed:
        _record(run_dir, {"event": "SCHOOL_CHECKPOINTS_RETIRED", "grade": active_grade,
                          "generation": record["generation"],
                          "count": len(removed), "protected_count": len(retained)})
    # The old frozen recipes are unique experiment evidence, not debris.
    # Do not delete either historical or new-epoch soup bytes from this fork.
    retired_soups = (_learning_grade_soup.retire_stale_soups(run_dir, record.get("grade_soups", {}))
                     if record.get("mentor_epoch") is None else ())
    if retired_soups:
        _record(run_dir, {"event": "SCHOOL_OLD_GRADE_SOUPS_RETIRED",
                          "generation": record["generation"],
                          "grade": active_grade, "count": len(retired_soups)})


def _quarantine_newer_uncommitted_bundles(run_dir: _pathlib.Path, retained: set[str],
                                          current_optimizer_step: int) -> tuple[str, ...]:
    """Never prune a post-update model published before its pointer crashed."""
    root = run_dir / "bundles"
    if not root.exists():
        return ()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("HUMAN_TRAINER_UNCOMMITTED_BUNDLE_UNSAFE_PATH")
    quarantined = []
    for candidate in sorted(root.iterdir()):
        if candidate.name == ".DS_Store" and not candidate.is_symlink() and candidate.is_file():
            # Keep Finder's bookkeeping from aborting an otherwise valid
            # human-run checkpoint transaction. Never touch model files.
            candidate.unlink()
            continue
        relative = "bundles/" + candidate.name
        if relative in retained:
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError("HUMAN_TRAINER_UNCOMMITTED_BUNDLE_UNSAFE_PATH")
        weights, own_adamw, metadata, graph = _runtime_mlx_checkpoint.load_semantically_bound_bundle(candidate)
        if (metadata["source_digest"] != _bilqis_mlx_source.AUDITED_PARENT.sha256 or
                metadata["optimizer_step"] < 0):
            raise ValueError("HUMAN_TRAINER_UNCOMMITTED_BUNDLE_SOURCE_DRIFT")
        del weights, own_adamw, graph
        if metadata["optimizer_step"] <= current_optimizer_step:
            continue
        target_parent = run_dir / ".bundle-quarantine"
        if target_parent.is_symlink() or (target_parent.exists() and
                                          not target_parent.is_dir()):
            raise ValueError("HUMAN_TRAINER_UNSAFE_BUNDLE_QUARANTINE")
        target_parent.mkdir(exist_ok=True)
        target = target_parent / candidate.name
        if target.exists() or target.is_symlink():
            raise ValueError("HUMAN_TRAINER_QUARANTINE_IDENTITY_COLLISION")
        candidate.rename(target)
        quarantined.append(candidate.name)
        fd = _os.open(target_parent, _os.O_RDONLY)
        try:
            _os.fsync(fd)
        finally:
            _os.close(fd)
        _record(run_dir, {"event": "SCHOOL_NEWER_UNCOMMITTED_BUNDLE_QUARANTINED",
                          "grade": "A", "filename": str(target.relative_to(run_dir)),
                          "optimizer_step": metadata["optimizer_step"],
                          "student_sha256": metadata["safetensors_sha256"],
                          "prior_committed_optimizer_step": current_optimizer_step})
    return tuple(quarantined)
