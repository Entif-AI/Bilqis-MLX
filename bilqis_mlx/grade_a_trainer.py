"""Human-operated Grade A MLX training; never invoked by agent test paths.

Transaction boundary = one complete capability visit or one full-grade exam.
Every committed visit owns a separate intact model+AdamW bundle and a
generation-numbered state receipt. An interrupted visit can be replayed from
its last committed boundary; no source or past student is overwritten.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
import uuid

from .backup import digest_file
from .champions import Checkpoint
from .disk import assert_headroom, headroom_snapshot
from .grade_a_evaluator import score_predictions
from .grade_a_manifest import verify_manifest
from .grade_a_release import AUTHORITY, accepted_grade_a
from .mlx_checkpoint import save_new_bundle, load_semantically_bound_bundle
from .mlx_parity import (clip_gradients, forward_arrays,
                         native_optimizer_to_mlx)
from .school import (start_new, visit, assess, next_capability, SchoolState)
from .source import AUDITED_PARENT

VERSION = "bilqis.mlx.human-grade-a-trainer/v1"
LOCKFILE = ".grade-a-operator.lock"
_event_view = ContextVar("grade_a_event_view", default=None)


@contextmanager
def operator_view(callback):
    token = _event_view.set(callback)
    try:
        yield
    finally:
        _event_view.reset(token)


def _canonical(data: object) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _fingerprint(data: object) -> str:
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def _durable_json(path: Path, data: dict, *, replace_existing=False):
    """fsync temporary bytes and containing folder; retain old state receipts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with tmp.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False,
                                allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if replace_existing:
        os.replace(tmp, path)
    else:
        try:
            os.link(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def operator_lock(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    fd = os.open(folder / LOCKFILE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("HUMAN_TRAINER_ANOTHER_OPERATOR_ACTIVE") from exc
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def prepare_source(legacy_root: Path, source_checkpoint: Path, manifest_path: Path):
    legacy_root = Path(legacy_root).resolve(strict=True)
    source_checkpoint = Path(source_checkpoint).resolve(strict=True)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    verified = verify_manifest(manifest, legacy_root, source_checkpoint)
    if (digest_file(source_checkpoint) != AUDITED_PARENT.sha256 or
            verified["verified_items"] != 216):
        raise ValueError("HUMAN_TRAINER_PINNED_SOURCE_NOT_VERIFIED")
    course = accepted_grade_a(manifest)
    if not course.executable or course.program_complete:
        raise ValueError("HUMAN_TRAINER_NOT_EXACT_ACCEPTED_GRADE_A")
    if str(legacy_root) not in sys.path:
        sys.path.insert(0, str(legacy_root))
    sys.dont_write_bytecode = True
    from bilqis_school import engine
    policy_path = legacy_root / "bilqis_school" / "engine.py"
    if Path(engine.__file__).resolve() != policy_path:
        raise ValueError("HUMAN_TRAINER_TEACHER_IMPLEMENTATION_ROOT_MISMATCH")
    # Pin the original adaptive policy and preserve its learned strategies.
    teacher_sha = digest_file(policy_path)
    teacher_path = (legacy_root / "runs" /
                    "primitive-consolidation-v16-triplets" / "state.json")
    historical_state = json.loads(teacher_path.read_text(encoding="utf-8"))
    teacher = historical_state.get("teacher")
    if (not isinstance(teacher, dict) or
            len(teacher.get("strategies", {})) < 4 or
            teacher.get("events", 0) < 1 or
            len(teacher.get("global_stats", {})) != len(teacher["strategies"])):
        raise ValueError("HUMAN_TRAINER_HISTORICAL_TEACHER_STATE_INCOMPLETE")
    provenance = {
        "teacher_state_file_sha256": digest_file(teacher_path),
        "teacher_origin_step": historical_state.get("optimizer_step"),
        "teacher_origin_events": teacher["events"],
        "teacher_origin_strategy_count": len(teacher["strategies"]),
    }
    return manifest, course, engine, teacher_sha, teacher, provenance


def _initial_model(source_checkpoint: Path):
    import mlx.core as mx
    from bilqis_development.continuation import load
    model, optimizer, payload = load(source_checkpoint)
    if (payload["config"]["precision"] != "fp32" or
            len(payload["graph"]["tokens"]) != 222):
        raise ValueError("HUMAN_TRAINER_HISTORICAL_SEMANTIC_ABI_INVALID")
    names = {id(p): name for name, p in model.named_parameters()}
    order = [names[id(p)] for p in optimizer.param_groups[0]["params"]]
    _, mlx_optimizer = native_optimizer_to_mlx(
        optimizer.state_dict(), model.state_dict(), parameter_order=order)
    parameters = {name: mx.array(weight.detach().numpy(), dtype=mx.float32)
                  for name, weight in model.state_dict().items()}
    mx.eval(parameters, mlx_optimizer.state)
    return parameters, mlx_optimizer, payload["config"], payload["graph"], (
        model.answer_ids.cpu().numpy().tolist())


def _make_batch(rows: list[dict]):
    import numpy as np
    if not rows:
        raise ValueError("HUMAN_TRAINER_EMPTY_BATCH")
    lengths = np.asarray([len(row["tokens"]) for row in rows], dtype=np.int32)
    if min(lengths) < 1 or max(lengths) > 96:
        raise ValueError("HUMAN_TRAINER_SEQUENCE_OUTSIDE_LEGACY_CONTEXT")
    ids = np.zeros((len(rows), int(lengths.max())), dtype=np.int32)
    labels = np.zeros(len(rows), dtype=np.int32)
    for i, row in enumerate(rows):
        ids[i, :lengths[i]] = row["tokens"]
        labels[i] = {"FALSE": 0, "TRUE": 1}[row["gold"]]
    return ids, lengths, labels


def _predictions(mx, parameters, rows, config, answer_ids):
    import numpy as np
    result = {}
    for offset in range(0, len(rows), 24):
        batch = rows[offset:offset+24]
        ids, lengths, _ = _make_batch(batch)
        logits = forward_arrays(mx, parameters, ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        mx.eval(logits)
        binary = np.asarray(logits)[:, :2].argmax(axis=-1)
        result.update({row["id"]: ("TRUE" if int(value) else "FALSE")
                       for row, value in zip(batch, binary)})
    return result


def _train_score(mx, parameters, rows, config, answer_ids) -> float:
    result = _predictions(mx, parameters, rows, config, answer_ids)
    return sum(result[r["id"]] == r["gold"] for r in rows) / len(rows)


def choose_lesson_batch(rows: list[dict], policy: dict,
                        seed: int, *, batch_size=32) -> list[dict]:
    """Balance both truth values; policy shapes selection, never gold answers."""
    if not rows or batch_size < 2 or batch_size % 2:
        raise ValueError("HUMAN_TRAINER_INVALID_LESSON_BATCH_SIZE")
    rng = random.Random(seed)
    truths = {label: [r for r in rows if r["gold"] == label]
              for label in ("FALSE", "TRUE")}
    if any(not values for values in truths.values()):
        raise ValueError("HUMAN_TRAINER_MISSING_BINARY_TRAINING_CLASS")
    if policy["depth"] >= 3:
        # No invented composite concepts: emphasize long *attested* records.
        for value in truths.values():
            value.sort(key=lambda r: (-len(r["tokens"]), r["id"]))
    if policy["contrast"] >= 0.5:
        chosen = [rng.choice(truths[label]) for _ in range(batch_size // 2)
                  for label in ("TRUE", "FALSE")]
    else:
        chosen = [rng.choice(rows) for _ in range(batch_size)]
    rng.shuffle(chosen)
    return chosen


def _train_step(mx, parameters, optimizer, rows, config, answer_ids):
    import numpy as np
    ids, lengths, labels = _make_batch(rows)
    expected = mx.array(np.eye(2, dtype=np.float32)[labels])

    def objective(weights):
        logits = forward_arrays(mx, weights, ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        typed = logits[:, :2]
        return mx.mean(mx.logsumexp(typed, axis=-1) -
                       mx.sum(typed * expected, axis=-1))

    loss, gradients = mx.value_and_grad(objective)(parameters)
    # Native torch.nn.Embedding(padding_idx=0) never trains padding row.
    pad_mask = mx.arange(parameters["embedding.weight"].shape[0])[:, None] != 0
    gradients["embedding.weight"] = mx.where(
        pad_mask, gradients["embedding.weight"],
        mx.zeros_like(gradients["embedding.weight"]))
    clipped, norm = clip_gradients(mx, gradients, max_norm=1.0)
    optimizer.update(parameters, clipped)
    mx.eval(parameters, optimizer.state, loss, norm)
    return float(loss.item()), float(norm.item())


def _state_from_json(value: dict, course) -> SchoolState:
    from .school import verify_state
    school = dict(value)
    for name in ("active_grades", "queue", "first_recovery", "pending_failures"):
        school[name] = tuple(school[name])
    school["current_student"] = Checkpoint(**school["current_student"])
    school["champions"] = {key: Checkpoint(**item)
                           for key, item in school["champions"].items()}
    result = SchoolState(**school)
    verify_state(course, result)
    return result


def _persist(run_dir: Path, receipt: dict):
    """One linearizable state pointer; immutable sequence copies remain."""
    receipt = json.loads(_canonical(receipt))
    generation = receipt["generation"]
    path = run_dir / "states" / f"{generation:07d}.json"
    _durable_json(path, receipt)
    if json.loads(path.read_text(encoding="utf-8")) != receipt:
        raise ValueError("HUMAN_TRAINER_SNAPSHOT_POSTWRITE_MISMATCH")
    _durable_json(run_dir / "state.json", receipt, replace_existing=True)
    if json.loads((run_dir / "state.json").read_text(encoding="utf-8")) != receipt:
        raise ValueError("HUMAN_TRAINER_LATEST_POINTER_NOT_DURABLE")
    return receipt


def _record(run_dir: Path, event: dict):
    path = run_dir / "events.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(_canonical(event) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    viewer = _event_view.get()
    if viewer is None:
        print(json.dumps(event, sort_keys=True), flush=True)
    else:
        try:
            viewer(event)
        except Exception as exc:
            print("DASHBOARD UNAVAILABLE: " + str(exc), file=sys.stderr, flush=True)


def _bundle_pointer(run_dir: Path, name: str, parameters, optimizer, graph,
                    *, reserve_gib: float):
    directory = run_dir / "bundles" / name
    metadata = save_new_bundle(
        directory, parameters, optimizer, source_digest=AUDITED_PARENT.sha256,
        semantic_catalog=graph, reserve_gib=reserve_gib)
    restored, restored_optimizer, manifest, restored_graph = (
        load_semantically_bound_bundle(directory))
    if (metadata != manifest or restored_graph != graph or
            list(restored) != list(parameters) or
            int(restored_optimizer.state["step"].item()) != int(optimizer.state["step"].item())):
        raise ValueError("HUMAN_TRAINER_COMPLETE_CHECKPOINT_READBACK_DRIFT")
    for filename in ("model-and-own-adamw.safetensors",
                     "semantic-catalog.json", "manifest.json"):
        fd = os.open(directory / filename, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    dir_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return Checkpoint(metadata["safetensors_sha256"],
                      str(directory.relative_to(run_dir)),
                      metadata["optimizer_step"], True)


def _init(run_dir, manifest, course, policy_sha, historical_teacher,
          teacher_provenance, checkpoint,
          *, reserve_gib):
    import mlx.core as mx
    if (run_dir / "state.json").exists() or any(
            p.name != LOCKFILE for p in run_dir.iterdir()):
        raise ValueError("HUMAN_TRAINER_NEW_RUN_HAS_EXISTING_CONTENT")
    assert_headroom(run_dir, required_bytes=600_000_000, reserve_gib=reserve_gib)
    parameters, optimizer, config, graph, answer_ids = _initial_model(checkpoint)
    initial_pointer = _bundle_pointer(
        run_dir, "initial-"+uuid.uuid4().hex[:12], parameters, optimizer, graph,
        reserve_gib=reserve_gib)
    state = start_new(course, initial_pointer)
    receipt = {
        "schema": VERSION,
        "generation": 1,
        "run_id": uuid.uuid4().hex,
        "accepted_authority": AUTHORITY,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "teacher_source_sha256": policy_sha,
        "school": asdict(state),
        "model_bundle": initial_pointer.filename,
        "teacher": json.loads(_canonical(historical_teacher)),
        "teacher_provenance": teacher_provenance,
        "config": config,
        "parameter_shapes": {name: list(param.shape)
                             for name, param in parameters.items()},
        "semantic_graph_sha256": _fingerprint(graph),
        "answer_ids": answer_ids,
        "result": "ACTIVE_GRADE_A",
        "last_exam": None,
    }
    receipt = _persist(run_dir, receipt)
    _record(run_dir, {"event": "GRADE_A_NEW_RUN_INITIALIZED", "generation": 1,
                      "student": initial_pointer.sha256,
                      "optimizer_step": initial_pointer.optimizer_step,
                      "exam_rubric": manifest["exam_rubric_sha256"],
                      "source_version": course.version})
    return parameters, optimizer, graph, receipt


def _resume(run_dir, manifest, course, policy_sha):
    import mlx.core as mx
    path = run_dir / "state.json"
    if not path.is_file():
        raise ValueError("HUMAN_TRAINER_RESUME_REQUIRES_PRIOR_RUN")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (receipt.get("schema") != VERSION or receipt.get("accepted_authority") != AUTHORITY
            or receipt.get("source_manifest_sha256") != manifest["manifest_sha256"]
            or receipt.get("teacher_source_sha256") != policy_sha):
        raise ValueError("HUMAN_TRAINER_RESUME_SOURCE_OR_POLICY_DRIFT")
    school = _state_from_json(receipt["school"], course)
    directory = (run_dir / receipt["model_bundle"]).resolve(strict=True)
    if directory.parent != (run_dir / "bundles").resolve(strict=True):
        raise ValueError("HUMAN_TRAINER_BUNDLE_PATH_ESCAPES_RUN")
    parameters, optimizer, bundle, graph = load_semantically_bound_bundle(directory)
    if (bundle["source_digest"] != AUDITED_PARENT.sha256 or
            bundle["safetensors_sha256"] != school.current_student.sha256 or
            bundle["optimizer_step"] != school.current_student.optimizer_step or
            school.current_student.filename != receipt["model_bundle"] or
            len(graph["tokens"]) != 222 or
            _fingerprint(graph) != receipt["semantic_graph_sha256"] or
            _fingerprint(graph) != manifest["parent_student"]["full_student_graph_sha256"] or
            {name:list(value.shape) for name,value in parameters.items()} !=
            receipt["parameter_shapes"] or
            len(parameters) != 39):
        raise ValueError("HUMAN_TRAINER_RESUME_MODEL_ADAMW_OR_SEMANTIC_DRIFT")
    if json.loads((run_dir / "states" /
                   f"{receipt['generation']:07d}.json").read_text()) != receipt:
        raise ValueError("HUMAN_TRAINER_RESUME_IMMUTABLE_STATE_DIVERGED")
    mx.eval(parameters, optimizer.state)
    return parameters, optimizer, graph, receipt


def _advance(run_dir, old: dict, school: SchoolState, *,
             teacher=None, model_bundle=None, last_exam=None, result=None):
    # One snapshot captures teacher learning, school progress and model pointer.
    record = dict(old)
    record["generation"] = old["generation"] + 1
    record["school"] = asdict(school)
    if teacher is not None:
        record["teacher"] = teacher
    if model_bundle is not None:
        record["model_bundle"] = model_bundle
    if last_exam is not None:
        record["last_exam"] = last_exam
    if result is not None:
        record["result"] = result
    return _persist(run_dir, record)


def _seed(receipt: dict, *, capability: str, step: int = 0) -> int:
    return int(_fingerprint([receipt["run_id"], receipt["generation"],
                             capability, step])[:16], 16)


def _take_visit(mx, run_dir, receipt, manifest, course, engine,
                params, optimizer, graph, *, steps_per_visit, batch_size, reserve_gib):
    school = _state_from_json(receipt["school"], course)
    cap = next_capability(school)
    if cap is None:
        raise ValueError("HUMAN_TRAINER_NO_SCHEDULED_CAPABILITY")
    teacher = json.loads(_canonical(receipt["teacher"]))
    rng = random.Random(_seed(receipt, capability=cap))
    policy_key, policy = engine.pick(teacher, "A", rng)
    optimizer.learning_rate = float(policy["lr"])
    rows = [r for r in manifest["training_rows"] if r["capability"] == cap]
    before = _train_score(mx, params, rows, receipt["config"],
                          receipt["answer_ids"])
    last_loss = 0.0
    last_norm = 0.0
    step_before = int(optimizer.state["step"].item())
    for step in range(steps_per_visit):
        picked = choose_lesson_batch(
            rows, policy, _seed(receipt, capability=cap, step=step+1),
            batch_size=batch_size)
        last_loss, last_norm = _train_step(
            mx, params, optimizer, picked, receipt["config"],
            receipt["answer_ids"])
    after = _train_score(mx, params, rows, receipt["config"],
                         receipt["answer_ids"])
    reward = after - before
    engine.observe(teacher, "A", policy_key, reward)
    if int(optimizer.state["step"].item()) != step_before+steps_per_visit:
        raise ValueError("HUMAN_TRAINER_OPTIMIZER_STEP_DRIFT")
    name = "visit-"+str(school.visits+1)+"-"+uuid.uuid4().hex[:12]
    next_student = _bundle_pointer(
        run_dir, name, params, optimizer, graph, reserve_gib=reserve_gib)
    school = visit(course, school, cap, next_student)
    result = _advance(
        run_dir, receipt, school, teacher=teacher,
        model_bundle=next_student.filename)
    _record(run_dir, {
        "event": "GRADE_A_TEACHER_VISIT_COMMITTED", "generation": result["generation"],
        "capability": cap, "teacher_policy": policy_key,
        "strategy": policy, "loss": last_loss, "gradient_norm": last_norm,
        "source_training_accuracy_before": before,
        "source_training_accuracy_after": after,
        "teacher_reward": reward, "optimizer_step": next_student.optimizer_step,
        "student_sha256": next_student.sha256,
        "next_phase": school.stage,
        "unavailable_teacher_dimensions": ["old", "preview", "distill"],
    })
    return result


def _take_exam(mx, run_dir, receipt, manifest, course, source_root,
               source_checkpoint, parameters):
    school = _state_from_json(receipt["school"], course)
    if not school.stage.startswith("ASSESS_"):
        raise ValueError("HUMAN_TRAINER_EXAM_OUTSIDE_SCHEDULED_BOUNDARY")
    guesses = _predictions(mx, parameters, manifest["examination_rows"],
                           receipt["config"], receipt["answer_ids"])
    assessment = score_predictions(
        manifest, course, school.current_student, guesses,
        legacy_root=source_root, source_checkpoint=source_checkpoint)
    advanced = assess(course, school, assessment)
    scores = {k: {"correct": v.correct, "total": v.total}
              for k, v in assessment.scores.items()}
    last_exam = {
        "evaluation_id": assessment.evaluation_id,
        "exam_rubric_sha256": assessment.rubric_digest,
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "scores": scores,
    }
    result = _advance(
        run_dir, receipt, advanced, last_exam=last_exam,
        result="GRADE_A_MASTERED_AWAITING_GRADE_B" if
        advanced.stage == "AWAITING_NEXT_GRADE" else "ACTIVE_GRADE_A")
    _record(run_dir, {"event": "GRADE_A_EXAM_COMMITTED",
                      "generation": result["generation"],
                      "scores": scores, "phase": advanced.stage,
                      "student_sha256": assessment.checkpoint_sha256,
                      "rubric": assessment.rubric_digest})
    return result


def session_stop_reason(*, stage: str, elapsed_seconds: float, minutes: int,
                        visits: int, max_visits: int) -> str | None:
    """State-machine stop condition; a due exam must not be silently skipped."""
    if stage == "AWAITING_NEXT_GRADE":
        return "GRADE_A_AWAITING_NEXT_GRADE"
    if stage.startswith("ASSESS_"):
        return None
    if elapsed_seconds >= minutes * 60:
        return "TIME_LIMIT_REACHED"
    if max_visits and visits >= max_visits:
        return "VISIT_LIMIT_REACHED"
    return None


def operate(run_dir: Path, source_root: Path, source_checkpoint: Path,
            manifest_path: Path, *, resume: bool = False, minutes: int = 90,
            max_visits: int = 0, steps_per_visit: int = 16,
            batch_size: int = 32, reserve_gib: float = 100.) -> dict:
    """ENTRYPOINT FOR THE HUMAN'S SHELL ONLY. Never call in agent tests."""
    if (type(minutes) is not int or not 1 <= minutes <= 1440 or
            type(steps_per_visit) is not int or not 1 <= steps_per_visit <= 2048 or
            type(max_visits) is not int or max_visits < 0 or
            type(batch_size) is not int or batch_size < 2 or batch_size % 2):
        raise ValueError("HUMAN_TRAINER_INVALID_OPERATOR_LIMITS")
    import mlx.core as mx
    mx.set_default_device(mx.gpu)
    manifest, course, engine, teacher_sha, historical_teacher, provenance = prepare_source(
        source_root, source_checkpoint, manifest_path)
    run_dir = Path(run_dir).expanduser().resolve()
    start = time.monotonic()
    with operator_lock(run_dir):
        if resume:
            params, optimizer, graph, receipt = _resume(
                run_dir, manifest, course, teacher_sha)
        else:
            params, optimizer, graph, receipt = _init(
                run_dir, manifest, course, teacher_sha,
                historical_teacher, provenance, source_checkpoint,
                reserve_gib=reserve_gib)
        visits = 0
        while True:
            school = _state_from_json(receipt["school"], course)
            reason = session_stop_reason(
                stage=school.stage, elapsed_seconds=time.monotonic() - start,
                minutes=minutes, visits=visits, max_visits=max_visits)
            if reason is not None:
                break
            if school.stage.startswith("ASSESS_"):
                receipt = _take_exam(
                    mx, run_dir, receipt, manifest, course, source_root,
                    source_checkpoint, params)
                continue
            budget = headroom_snapshot(run_dir, required_bytes=600_000_000,
                                       reserve_gib=reserve_gib)
            if not budget["sufficient"]:
                reason = "DISK_RESERVE_REACHED"
                break
            # Retain the original fail-closed checkpoint preflight against
            # disk changes between telemetry and the actual write boundary.
            assert_headroom(run_dir, required_bytes=600_000_000,
                            reserve_gib=reserve_gib)
            receipt = _take_visit(
                mx, run_dir, receipt, manifest, course, engine,
                params, optimizer, graph, steps_per_visit=steps_per_visit,
                batch_size=batch_size, reserve_gib=reserve_gib)
            visits += 1
        school = _state_from_json(receipt["school"], course)
        budget = headroom_snapshot(run_dir, required_bytes=600_000_000,
                                   reserve_gib=reserve_gib)
        elapsed_seconds = round(time.monotonic() - start, 3)
        _record(run_dir, {
            "event": "GRADE_A_SESSION_STOPPED", "stop_reason": reason,
            "generation": receipt["generation"], "run_id": receipt["run_id"],
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "visits_this_command": visits, "committed_total_visits": school.visits,
            "minutes": minutes, "max_visits": max_visits,
            "elapsed_seconds": elapsed_seconds,
            "grade_phase": school.stage, "resume_required": school.stage != "AWAITING_NEXT_GRADE",
            **{k: budget[k] for k in ("free_bytes", "reserve_bytes", "estimated_write_bytes")},
        })
        return {
            "status": receipt["result"],
            "stop_reason": reason,
            "elapsed_seconds": elapsed_seconds,
            "time_limit_minutes": minutes,
            "max_visits": max_visits,
            "disk_free_gib": round(budget["free_bytes"] / 1024**3, 3),
            "disk_reserve_gib": round(budget["reserve_bytes"] / 1024**3, 3),
            "disk_next_visit_gib": round(budget["estimated_write_bytes"] / 1024**3, 3),
            "grade": school.grade,
            "phase": school.stage,
            "visits_this_command": visits,
            "committed_total_visits": school.visits,
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "latest_exam": receipt["last_exam"],
            "safe_resume_command": "npm run train -- --human-run --resume",
            "original_source_checkpoint_modified": False,
        }
