"""Human-operated Grade A MLX training; never invoked by agent test paths.

The in-memory student can perform several lessons between full assessments.
Only tested capability leaders receive permanent binary status.  One bounded
working recovery snapshot preserves the continuously learning student at
assessment and operator-stop boundaries; other routine visits are provisional.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, replace
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
from .capability_frontier import (
    candidate_roles, graduation_perfect, historical_frontier, pinned, promote, retire_bundles,
)
from .disk import assert_headroom, headroom_snapshot
from .diagnostics.teaching import inspect_lesson_step, summarize_teaching_visit
from .diagnostics.exam_events import summarize_completed_exam_safely
from .generated_assessment import GRADE_TEST_LIFECYCLE, make_cohort, score as score_cohort
from .grade_a_manifest import verify_manifest
from .grade_a_oracle import evaluate as grade_a_record_oracle
from .grade_a_probe import read_sources
from .grade_a_release import AUTHORITY, accepted_grade_a
from .live_grade_a import (GENERATOR as LIVE_GENERATOR, RELEASE as LIVE_RELEASE,
                           draw_predicates, live_course, generator_source_digest)
from .live_grade_b import (GENERATOR as B_GENERATOR, RELEASE as B_RELEASE,
                           draw_connectives, live_course as live_b_course,
                           constructor_digest as b_constructor_digest)
from .live_curriculum import cohort_contract, draw_course_rows, lesson_contract, numeric_maximum
from .live_grade_c import RELEASE as C_RELEASE
from .mlx_checkpoint import save_new_bundle, load_semantically_bound_bundle
from .mlx_parity import (clip_gradients, forward_arrays,
                         native_optimizer_to_mlx)
from .school import (start_new, visit, assess, next_capability, append_next_grade,
                     teacher_vote_weights, assessment_capabilities, SchoolState, Assessment, Score)
from .semantics.abi import HISTORICAL_PREFIX_SIZE
from .source import AUDITED_PARENT
from .teacher_feedback import (
    FairMissRequest, TeacherDecisionInput, active_warning_signals, reconcile_unresolved_misses,
    select_fair_miss_window, summarize_teacher_decision,
    summarize_teacher_outcomes,
)

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
            len(payload["graph"]["tokens"]) != HISTORICAL_PREFIX_SIZE):
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
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        from .typed_answer_training import predict_rows
        return predict_rows(mx, parameters, rows, config["answer_heads"], config)
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
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        # Sample linked direct/TRUE/FALSE views from the same verified meaning.
        # This is an answer contract, independent of old/new lesson allocation.
        sources = {}
        for row in rows:
            sources.setdefault(row["source_id"], []).append(row)
        chosen = []
        groups = list(sources.values())
        while len(chosen) < batch_size:
            chosen.extend(rng.choice(groups))
        chosen = chosen[:batch_size]
        rng.shuffle(chosen)
        return chosen
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


def replay_missed_lessons(chosen: list[dict], missed: list[dict]) -> list[dict]:
    """Guarantee every requested missed construction reaches this optimizer batch."""
    if len(missed) > len(chosen):
        raise ValueError("HUMAN_TRAINER_MISS_REPLAY_EXCEEDS_BATCH")
    result = list(chosen)
    consumed = set()
    for item in missed:
        replacement = next((i for i, row in enumerate(result)
                            if i not in consumed and row["gold"] == item["gold"]), None)
        if replacement is None:
            raise ValueError("HUMAN_TRAINER_MISS_REPLAY_ANSWER_CLASS_CAPACITY")
        result[replacement] = item
        consumed.add(replacement)
    return result


def champion_directed_lessons(chosen: list[dict], candidates: list[dict],
                              votes: dict[str, int], *, capacity: int) -> list[dict]:
    """Let prior-grade champion votes nominate teaching rows, never golds.

    Each retained grade is one vote for practicing a source-verifiably missed
    construction. Keep the policy's existing TRUE/FALSE balance unchanged.
    """
    if capacity < 0 or len({r["id"] for r in candidates}) != len(candidates):
        raise ValueError("HUMAN_TRAINER_CHAMPION_VOTE_INPUT_INVALID")
    if any(type(count) is not int or count < 0 for count in votes.values()):
        raise ValueError("HUMAN_TRAINER_CHAMPION_VOTE_COUNT_INVALID")
    result = list(chosen)
    used = set()
    for example in sorted(candidates, key=lambda r: (-votes.get(r["id"], 0), r["id"])):
        if not votes.get(example["id"]) or len(used) >= capacity:
            break
        if any(row["id"] == example["id"] for row in result):
            continue
        location = next((i for i, row in enumerate(result)
                         if i not in used and row["gold"] == example["gold"]), None)
        if location is not None:
            result[location] = example
            used.add(location)
    return result


def _champion_teacher_votes(mx, run_dir: Path, school: SchoolState, course,
                            rows: list[dict], graph, config, answer_ids) -> dict[str, int]:
    """Score frozen, own-optimizer grade champions as teachers, not students.

    Load each distinct bundle once. Every grade pointer contributes a vote,
    including when several grade pointers identify the same physical bundle.
    Champion mistakes on source-oracle-verified lessons receive teaching
    priority. Do not expose these guesses as examination answers.
    """
    weights = teacher_vote_weights(course, school)
    if not weights:
        return {}
    by_sha = {cp.sha256: cp for cp in school.champions.values()}
    if set(weights) != set(by_sha):
        raise ValueError("HUMAN_TRAINER_CHAMPION_VOTE_POINTER_DRIFT")
    scores = {row["id"]: 0 for row in rows}
    for sha, multiplicity in sorted(weights.items()):
        pointer = by_sha[sha]
        parts = Path(pointer.filename).parts
        path = run_dir / pointer.filename
        if (len(parts) != 2 or parts[0] != "bundles" or
                parts[1] in (".", "..") or path.is_symlink() or
                path.parent != run_dir / "bundles" or
                not pointer.model_and_native_adamw):
            raise ValueError("HUMAN_TRAINER_CHAMPION_VOTE_UNSAFE_CHECKPOINT")
        parameters, optimizer, meta, loaded_graph = load_semantically_bound_bundle(path)
        if (not _compatible_graphs(loaded_graph, graph) or meta["safetensors_sha256"] != sha or
                meta["optimizer_step"] != pointer.optimizer_step or
                meta["source_digest"] != AUDITED_PARENT.sha256):
            raise ValueError("HUMAN_TRAINER_CHAMPION_VOTE_CHECKPOINT_DRIFT")
        readable = [row for row in rows if max(row["tokens"]) < len(loaded_graph["tokens"])]
        guesses = _predictions(mx, parameters, readable,
            _compatible_answer_config(config, loaded_graph), answer_ids) if readable else {}
        for row in readable:
            if guesses[row["id"]] != row["gold"]:
                scores[row["id"]] += multiplicity
        del parameters, optimizer
    return scores


def _compatible_graphs(earlier, current):
    """A frozen earlier teacher retains its exact historical semantic prefix."""
    count = len(earlier["tokens"])
    return (earlier["tokens"] == current["tokens"][:count] and
            earlier["nodes"] == current["nodes"][:count] and
            all(current["row_contract_sha256"].get(s) == value
                for s, value in earlier["row_contract_sha256"].items()))


def _compatible_answer_config(config, graph):
    if "answer_heads" not in config:
        return config
    from .live_grade_c import answer_heads
    maximum = len(config["answer_heads"]["numeric_active"]["values"])-1
    return {**config, "answer_heads": answer_heads(graph, maximum)}


def _train_step(mx, parameters, optimizer, rows, config, answer_ids):
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        from .typed_answer_training import typed_step
        return typed_step(mx, parameters, optimizer, rows, config["answer_heads"], config)
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
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text(encoding="utf-8")) != receipt:
            raise ValueError("HUMAN_TRAINER_IMMUTABLE_GENERATION_COLLISION")
    else:
        _durable_json(path, receipt)
    if json.loads(path.read_text(encoding="utf-8")) != receipt:
        raise ValueError("HUMAN_TRAINER_SNAPSHOT_POSTWRITE_MISMATCH")
    _durable_json(run_dir / "state.json", receipt, replace_existing=True)
    if json.loads((run_dir / "state.json").read_text(encoding="utf-8")) != receipt:
        raise ValueError("HUMAN_TRAINER_LATEST_POINTER_NOT_DURABLE")
    return receipt


def _recover_orphaned_commit(run_dir: Path, latest: dict) -> dict:
    """Complete a fully written generation whose state.json pointer lost a race to a crash.

    Call only under the exclusive operator lock and only with an already checked
    live source manifest; no model or optimizer is mutated here.
    """
    target = run_dir / "states" / f"{latest['generation']+1:07d}.json"
    if not target.exists():
        return latest
    if target.is_symlink() or not target.is_file():
        raise ValueError("HUMAN_TRAINER_RECOVERY_UNSAFE_GENERATION")
    proposed = json.loads(target.read_text(encoding="utf-8"))
    if (proposed.get("generation") != latest["generation"] + 1 or
            proposed.get("run_id") != latest.get("run_id") or
            proposed.get("schema") != latest.get("schema") or
            proposed.get("source_manifest_sha256") != latest.get("source_manifest_sha256") or
            proposed.get("teacher_source_sha256") != latest.get("teacher_source_sha256") or
            proposed.get("accepted_authority") != latest.get("accepted_authority")):
        raise ValueError("HUMAN_TRAINER_RECOVERY_INCONSISTENT_LINEAGE")
    # Verify every retained old/new whole-student pointer before publication.
    _verify_best_custody(run_dir, proposed)
    _durable_json(run_dir / "state.json", proposed, replace_existing=True)
    if json.loads((run_dir / "state.json").read_text()) != proposed:
        raise ValueError("HUMAN_TRAINER_RECOVERY_POINTER_NOT_DURABLE")
    # Publish the recovered generation's original causal events before its
    # recovery annotation, retaining a legible ordered School50 history.
    _reconcile_delivery_outbox(run_dir, proposed)
    _record(run_dir, {"event": "SCHOOL_INTERRUPT_POINTER_RECOVERED", "grade": "A",
                      "generation": proposed["generation"],
                      "student_sha256": proposed["school"]["current_student"]["sha256"],
                      "optimizer_step": proposed["school"]["current_student"]["optimizer_step"]})
    return proposed


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
    stage_root = run_dir / ".bundle-staging"
    if stage_root.is_symlink() or (stage_root.exists() and not stage_root.is_dir()):
        raise ValueError("HUMAN_TRAINER_UNSAFE_STAGING_ROOT")
    stage_root.mkdir(exist_ok=True)
    stage_directory = stage_root / name
    directory = run_dir / "bundles" / name
    if directory.exists() or directory.is_symlink():
        raise ValueError("HUMAN_TRAINER_BUNDLE_ALREADY_PUBLISHED")
    metadata = save_new_bundle(
        stage_directory, parameters, optimizer, source_digest=AUDITED_PARENT.sha256,
        semantic_catalog=graph, reserve_gib=reserve_gib)
    restored, restored_optimizer, manifest, restored_graph = (
        load_semantically_bound_bundle(stage_directory))
    if (metadata != manifest or restored_graph != graph or
            list(restored) != list(parameters) or
            int(restored_optimizer.state["step"].item()) != int(optimizer.state["step"].item())):
        raise ValueError("HUMAN_TRAINER_COMPLETE_CHECKPOINT_READBACK_DRIFT")
    for filename in ("model-and-own-adamw.safetensors",
                     "semantic-catalog.json", "manifest.json"):
        fd = os.open(stage_directory / filename, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    dir_fd = os.open(stage_directory, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    directory.parent.mkdir(exist_ok=True)
    # The published bundles namespace must contain ONLY complete, read-back
    # verified three-file bundles. Failed writes remain in isolated staging.
    stage_directory.rename(directory)
    fd = os.open(directory.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    stage_root.rmdir()
    return Checkpoint(metadata["safetensors_sha256"],
                      str(directory.relative_to(run_dir)),
                      metadata["optimizer_step"], True)


def _clean_staged_bundles(run_dir: Path) -> dict[str, tuple[str, ...]]:
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


def _init(run_dir, manifest, course, policy_sha, historical_teacher,
          teacher_provenance, checkpoint,
          *, reserve_gib):
    import mlx.core as mx
    _clean_staged_bundles(run_dir)
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
        "curriculum_mode": LIVE_RELEASE,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "teacher_source_sha256": policy_sha,
        "school": asdict(state),
        "model_bundle": initial_pointer.filename,
        "capability_best": {},
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
    init_event = {"event": "GRADE_A_NEW_RUN_INITIALIZED", "generation": 1,
                      "grade": "A",
                      "student": initial_pointer.sha256,
                      "optimizer_step": initial_pointer.optimizer_step,
                      "exam_rubric": course.grades[0].assessment_sha256,
                      "historical_rubric": manifest["exam_rubric_sha256"],
                      "generator_version": LIVE_GENERATOR,
                      "generator_code_sha256": generator_source_digest(),
                      "source_version": course.version}
    receipt = _persist(run_dir, _with_delivery_outbox(receipt, (init_event,)))
    _reconcile_delivery_outbox(run_dir, receipt)
    return parameters, optimizer, graph, receipt


def _resume(run_dir, manifest, course, policy_sha, *, successor_course=None, admitted_courses=None):
    import mlx.core as mx
    path = run_dir / "state.json"
    if not path.is_file():
        raise ValueError("HUMAN_TRAINER_RESUME_REQUIRES_PRIOR_RUN")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (receipt.get("schema") != VERSION or receipt.get("accepted_authority") != AUTHORITY
            or receipt.get("source_manifest_sha256") != manifest["manifest_sha256"]
            or receipt.get("teacher_source_sha256") != policy_sha):
        raise ValueError("HUMAN_TRAINER_RESUME_SOURCE_OR_POLICY_DRIFT")
    reconciled = _clean_staged_bundles(run_dir)
    if any(reconciled.values()):
        _record(run_dir, {"event": "SCHOOL_UNPUBLISHED_STAGING_RECONCILED",
                          "grade": "A", "generation": receipt["generation"],
                          **reconciled})
    receipt = _recover_orphaned_commit(run_dir, receipt)
    saved_mode = receipt.get("curriculum_mode")
    old_mode = saved_mode is None
    if saved_mode not in (None, LIVE_RELEASE, B_RELEASE, C_RELEASE):
        raise ValueError("HUMAN_TRAINER_UNKNOWN_CURRICULUM_MODE")
    old_course = ((admitted_courses or {})[saved_mode] if saved_mode in (admitted_courses or {}) else
                  accepted_grade_a(manifest) if old_mode else
                  live_course(accepted_grade_a(manifest)) if saved_mode == LIVE_RELEASE
                  else successor_course if successor_course is not None else course)
    if saved_mode == B_RELEASE and (len(old_course.grades) != 2 or
                                    old_course.version != B_RELEASE or
                                    receipt.get("grade_b_code_sha256") != b_constructor_digest()):
        raise ValueError("HUMAN_TRAINER_GRADE_B_COURSE_NOT_LOADED")
    if saved_mode == C_RELEASE:
        from .live_grade_c import constructor_digest
        if (old_course.version != C_RELEASE or len(old_course.grades) != 3 or
                receipt.get("grade_c_code_sha256") != constructor_digest()):
            raise ValueError("HUMAN_TRAINER_GRADE_C_COURSE_NOT_LOADED")
    school = _state_from_json(receipt["school"], old_course)
    directory = (run_dir / receipt["model_bundle"]).resolve(strict=True)
    if directory.parent != (run_dir / "bundles").resolve(strict=True):
        raise ValueError("HUMAN_TRAINER_BUNDLE_PATH_ESCAPES_RUN")
    parameters, optimizer, bundle, graph = load_semantically_bound_bundle(directory)
    if saved_mode == C_RELEASE:
        from .live_grade_c import registry_graph
        source_graph_ok = graph == registry_graph()
    else:
        source_graph_ok = (len(graph["tokens"]) == HISTORICAL_PREFIX_SIZE and
            _fingerprint(graph) == manifest["parent_student"]["full_student_graph_sha256"])
    if (bundle["source_digest"] != AUDITED_PARENT.sha256 or
            bundle["safetensors_sha256"] != school.current_student.sha256 or
            bundle["optimizer_step"] != school.current_student.optimizer_step or
            school.current_student.filename != receipt["model_bundle"] or
            not source_graph_ok or
            _fingerprint(graph) != receipt["semantic_graph_sha256"] or
            {name:list(value.shape) for name,value in parameters.items()} !=
            receipt["parameter_shapes"] or
            len(parameters) != 39):
        raise ValueError("HUMAN_TRAINER_RESUME_MODEL_ADAMW_OR_SEMANTIC_DRIFT")
    if json.loads((run_dir / "states" /
                   f"{receipt['generation']:07d}.json").read_text()) != receipt:
        raise ValueError("HUMAN_TRAINER_RESUME_IMMUTABLE_STATE_DIVERGED")
    if not old_mode:
        _verify_saved_cohort(run_dir, receipt, old_course)
    mx.eval(parameters, optimizer.state)
    if "capability_best" not in receipt:
        # Existing full-history run: reconstruct bests from actual sealed
        # checkpoint receipts before permitting reference-aware retirement.
        counts = {cap.id: dict(old_course.grades[0].exam_item_counts)[cap.id]
                  for cap in old_course.grades[0].capabilities}
        frontier = historical_frontier(
            run_dir, expected_rubric=manifest["exam_rubric_sha256"],
            expected_capabilities=counts)
        _verify_best_custody(run_dir, {**receipt, "capability_best": frontier})
        receipt = _advance(run_dir, receipt, school, frontier=frontier)
        _record(run_dir, {"event": "SCHOOL_CAPABILITY_FRONTIER_MIGRATED",
                          "grade": "A", "generation": receipt["generation"],
                          "champion_roles": len(frontier),
                          "whole_student_unchanged": True})
    if old_mode:
        # Historical immutable receipts keep their 72-item identity and model
        # custody. Move pointers to an archival namespace, with all historic
        # bests pinned until independently rescored on a fresh full cohort.
        from dataclasses import replace
        legacy_frontier = receipt.get("capability_best", {})
        _verify_best_custody(run_dir, receipt)
        historical_champions = dict(school.champions)
        if historical_champions:
            # A perfect score on the old 72 remains historical evidence, but
            # cannot certify the successor generated semantic rubric.
            school = replace(school, champions={}, stage="MAIN",
                             queue=tuple(c.id for c in course.grades[0].capabilities),
                             first_recovery=(), pending_failures=())
        school = replace(school, course_digest=old_course.digest() if not old_mode
                         else course.digest(),
                         latest_rubric_digest=None)
        record = dict(receipt)
        record["historical_capability_best"] = legacy_frontier
        record["historical_grade_champions"] = {
            key: asdict(item) for key, item in historical_champions.items()}
        record["capability_best"] = {}
        record["curriculum_mode"] = LIVE_RELEASE
        record["legacy_frontier_pending_replay"] = bool(legacy_frontier)
        receipt = _advance(run_dir, record, school)
        _record(run_dir, {"event": "SCHOOL_LIVE_GRADE_A_MIGRATED",
                          "generation": receipt["generation"],
                          "historical_rubric": manifest["exam_rubric_sha256"],
                          "live_rubric": course.grades[0].assessment_sha256,
                          "legacy_best_slots": len(legacy_frontier),
                          "source_student_unchanged": True})
    _verify_best_custody(run_dir, receipt)
    # Also finishes a retirement interrupted after the prior state commit.
    _publish_boundary(run_dir, receipt, (), ())
    return parameters, optimizer, graph, receipt


def _activate_next_admitted_grade(run_dir, receipt, previous_course, successor):
    """Preserve the already-mastered student and teacher at a grade boundary."""
    school = _state_from_json(receipt["school"], previous_course)
    if (not successor.executable or successor.version != B_RELEASE or
            school.stage != "AWAITING_NEXT_GRADE" or
            school.grade != "A" or "A" not in school.champions or
            receipt.get("curriculum_mode") != LIVE_RELEASE):
        raise ValueError("HUMAN_TRAINER_GRADE_B_ADMISSION_BOUNDARY_NOT_MET")
    next_state = append_next_grade(previous_course, successor, school)
    candidate = {**receipt, "curriculum_mode": B_RELEASE,
                 "live_rubric_sha256": successor.grades[-1].assessment_sha256,
                 "grade_b_code_sha256": b_constructor_digest()}
    record = _advance(run_dir, candidate, next_state, result="ACTIVE_GRADE_B",
                      persist=False)
    admitted = {"event": "SCHOOL_GRADE_B_COURSE_ADMITTED",
                      "generation": record["generation"], "grade": "B",
                      "previous_cohort_sha256": (record.get("last_exam") or {}).get("cohort_sha256"),
                      "grade_a_champion_sha256": school.champions["A"].sha256,
                      "student_sha256": school.current_student.sha256,
                      "optimizer_step": school.current_student.optimizer_step,
                      "teacher_events": record["teacher"]["events"],
                      "grade_b_rubric": successor.grades[-1].assessment_sha256,
                      "grade_b_generator": B_GENERATOR,
                      "model_and_own_adamw_unchanged": True}
    record = _persist(run_dir, _with_delivery_outbox(record, (admitted,)))
    _reconcile_delivery_outbox(run_dir, record)
    return record


def _verify_best_custody(run_dir, receipt):
    school = receipt["school"]
    historical_pending = (receipt.get("historical_capability_best", {})
                          if receipt.get("legacy_frontier_pending_replay") else {})
    sources = [school["current_student"], *school["champions"].values(),
               *receipt.get("historical_grade_champions", {}).values(),
               *(cap["checkpoint"] for cap in receipt.get("capability_best", {}).values()),
               *(cap["checkpoint"] for cap in receipt.get("graduation_perfect", {}).values()),
               *(cap["checkpoint"] for cap in historical_pending.values())]
    protected = pinned(receipt.get("capability_best", {}),
                       school["current_student"], school["champions"])
    protected |= pinned(receipt.get("graduation_perfect", {}),
                        school["current_student"], school["champions"])
    if historical_pending:
        protected |= pinned(historical_pending,
                            school["current_student"], school["champions"])
    for item in receipt.get("historical_grade_champions", {}).values():
        protected |= pinned({}, item, {})
    for name in sorted(protected):
        root = run_dir / name
        if root.is_symlink() or root.parent != run_dir / "bundles":
            raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_PATH_DRIFT")
        manifest = json.loads((root / "manifest.json").read_text())
        if digest_file(root / "model-and-own-adamw.safetensors") != manifest["safetensors_sha256"]:
            raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_SHA_DRIFT")
        for ref in sources:
            if (ref["filename"] == name and
                    (manifest["safetensors_sha256"] != ref["sha256"] or
                     manifest["optimizer_step"] != ref["optimizer_step"])):
                raise ValueError("HUMAN_TRAINER_CAPABILITY_CUSTODY_REFERENCE_DRIFT")


def _advance(run_dir, old: dict, school: SchoolState, *,
             teacher=None, model_bundle=None, last_exam=None, result=None,
             frontier=None, persist=True):
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
    if frontier is not None:
        record["capability_best"] = frontier
    if persist:
        record.pop("_pending_visit_events", None)
        return _persist(run_dir, record)
    return json.loads(_canonical(record))


def _draw_live_rows(source_root, graph, *, seed, capability=None, each=None, course=None):
    """Draw A only or cumulative A+B with identical source-oracle standards."""
    if course is not None:
        return draw_course_rows(source_root, graph, course, seed=seed,
                                capability=capability, each=each)
    each = 12 if each is None else each
    scopes = {"A"}
    if scopes not in ({"A"}, {"A", "B"}):
        raise ValueError("HUMAN_TRAINER_UNADMITTED_GRADE_SOURCE")
    selected = {capability.split(".", 1)[0]} if capability else scopes
    if not selected <= scopes:
        raise ValueError("HUMAN_TRAINER_CAPABILITY_NOT_IN_COURSE")
    rows = []
    if "A" in selected:
        rows.extend(draw_predicates(source_root, graph, seed=seed,
                                   capability=capability if capability else None, each=each))
    if "B" in selected:
        rows.extend(draw_connectives(source_root, graph, seed=seed,
                                    capability=capability if capability else None, each=each))
    expected = ({cap.id: each for grade in course.grades for cap in grade.capabilities}
                if course else {cap: each for cap in (
                  "A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS")})
    if capability:
        expected = {capability: each}
    actual = {cap: sum(r["capability"] == cap for r in rows) for cap in expected}
    if actual != expected or len(rows) != sum(expected.values()):
        raise ValueError("HUMAN_TRAINER_LIVE_GRADE_NOT_COMPREHENSIVE")
    return list(rows)


def _cohort_contract(course):
    return cohort_contract(course)


def _persist_live_cohort(run_dir, manifest, course, cohort):
    """Make generation retry safe if a crash follows cohort publication."""
    rubric, release, generator, code_sha = _cohort_contract(course)
    if cohort.generator_version != generator or cohort.rubric_version != release:
        raise ValueError("HUMAN_TRAINER_COHORT_VERSION_MISMATCH")
    path = run_dir / "cohorts" / (cohort.digest + ".json")
    payload = {"schema": release,
               "source_manifest_sha256": manifest["manifest_sha256"],
               "rubric_sha256": rubric,
               "generator_version": generator,
               "generator_code_sha256": code_sha,
               "seed": cohort.seed,
               "cohort_sha256": cohort.digest, "rows": list(cohort.rows)}
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text()) != payload:
            raise ValueError("HUMAN_TRAINER_GENERATED_COHORT_CUSTODY_DRIFT")
    else:
        _durable_json(path, payload)
    if json.loads(path.read_text()) != payload:
        raise ValueError("HUMAN_TRAINER_GENERATED_COHORT_WRITEBACK_DRIFT")
    return str(path.relative_to(run_dir))


def _verify_saved_cohort(run_dir, receipt, course):
    exam = receipt.get("last_exam") or {}
    sha = exam.get("cohort_sha256")
    if sha is None:
        return  # Migration may still point at an archived fixed-rubric exam.
    if (not isinstance(sha, str) or len(sha) != 64 or
            exam.get("cohort_file") != "cohorts/" + sha + ".json"):
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_REFERENCE_DRIFT")
    path = run_dir / exam["cohort_file"]
    if path.is_symlink() or not path.is_file():
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_MISSING")
    stored = json.loads(path.read_text())
    # The archived A cohort remains verifiable after explicitly admitting B;
    # neither its historic source hash nor its old release bytes are rewritten.
    prior_a = stored.get("schema") == LIVE_RELEASE
    if prior_a:
        from dataclasses import replace
        rubric, release, generator, code_sha = _cohort_contract(
            replace(course, grades=course.grades[:1]))
    elif stored.get("schema") == B_RELEASE and len(course.grades) > 2:
        rubric, release, generator, code_sha = (
            course.grades[1].assessment_sha256, B_RELEASE, B_GENERATOR, b_constructor_digest())
    else:
        rubric, release, generator, code_sha = _cohort_contract(course)
    if (stored.get("rubric_sha256") != rubric or
            stored.get("source_manifest_sha256") != receipt["source_manifest_sha256"] or
            stored.get("generator_version") != generator or
            stored.get("generator_code_sha256") != code_sha or
            stored.get("cohort_sha256") != sha or
            stored.get("seed") != exam.get("cohort_seed") or
            stored.get("schema") != release):
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_METADATA_DRIFT")
    cohort = make_cohort(stored["rows"], generator_version=generator,
                         seed=stored["seed"], rubric_version=release)
    if cohort.digest != sha:
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_CONTENT_DRIFT")
    return cohort


def _grade_test_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Reuse the enrolled grade's test until passed; generate anew on a return."""
    school = _state_from_json(receipt["school"], course)
    rubric, release, generator, _ = _cohort_contract(course)
    pointer = receipt.get("qualification_cohort")
    if pointer is not None:
        if (not isinstance(pointer, dict) or pointer.get("policy") != GRADE_TEST_LIFECYCLE or
                type(pointer.get("grade_exam_epoch")) is not int):
            raise ValueError("HUMAN_TRAINER_GRADE_TEST_POLICY_DRIFT")
        if (pointer.get("assessment_grade") == school.grade and
                pointer["grade_exam_epoch"] == school.grade_exam_epoch):
            cohort = _verify_saved_cohort(run_dir, {**receipt, "last_exam": pointer}, course)
            if cohort is None:
                raise ValueError("HUMAN_TRAINER_GRADE_TEST_MISSING")
            return cohort, pointer

    # Adopt a saved failed exam when upgrading the old rotating-test trainer.
    # The original immutable state and questions remain unchanged.
    previous = receipt.get("last_exam") or {}
    previous_grade = previous.get("assessment_grade")
    if previous_grade is None:
        for event in receipt.get("delivery_outbox", ()):
            if (event.get("cohort_sha256") == previous.get("cohort_sha256") and
                    event.get("optimizer_step") == previous.get("optimizer_step")):
                previous_grade = event.get("grade")
        if previous_grade is None and len(course.grades) == 1:
            previous_grade = course.grades[0].id
    own_caps = next(g.capabilities for g in course.grades if g.id == school.grade)
    scores = previous.get("scores", {})
    failed_current = (all(c.id in scores for c in own_caps) and
                      any(scores[c.id]["correct"] < scores[c.id]["total"] for c in own_caps))
    if (pointer is None and previous.get("cohort_sha256") and failed_current and
            previous_grade == school.grade and
            previous.get("grade_exam_epoch", 0) == school.grade_exam_epoch and
            previous.get("exam_rubric_sha256") == rubric):
        cohort = _verify_saved_cohort(run_dir, receipt, course)
        cohort_file = previous["cohort_file"]
    else:
        seed = _seed(receipt, capability=f"GRADE_TEST:{school.grade}:{school.grade_exam_epoch}")
        rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
        cohort = make_cohort(rows, generator_version=generator, seed=seed, rubric_version=release)
        cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort, {"policy": GRADE_TEST_LIFECYCLE, "assessment_grade": school.grade,
                    "grade_exam_epoch": school.grade_exam_epoch,
                    "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                    "cohort_seed": cohort.seed}


def _candidate_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Fresh randomized qualification for checkpoint candidates, not graduation."""
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(receipt, capability="CANDIDATE_CHECKPOINT")
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(rows, generator_version=generator, seed=seed,
                         rubric_version=release)
    _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort


def _seed(receipt: dict, *, capability: str, step: int = 0) -> int:
    return int(_fingerprint([receipt["run_id"], receipt["generation"],
                             capability, step])[:16], 16)


def _introduced_cohort(run_dir, manifest, course, school, cohort):
    """Activate taught portions of one fixed enrollment exam without redrawing."""
    eligible = set(assessment_capabilities(course, school))
    rows = tuple(row for row in cohort.rows if row["capability"] in eligible)
    selected = cohort if rows == cohort.rows else make_cohort(rows,
        generator_version=cohort.generator_version, seed=cohort.seed,
        rubric_version=cohort.rubric_version)
    return selected, _persist_live_cohort(run_dir, manifest, course, selected)


def _take_visit(mx, run_dir, receipt, manifest, course, engine,
                params, optimizer, graph, *, steps_per_visit, batch_size, reserve_gib,
                source_root=None):
    school = _state_from_json(receipt["school"], course)
    cap = next_capability(school)
    if cap is None:
        raise ValueError("HUMAN_TRAINER_NO_SCHEDULED_CAPABILITY")
    introduction_pass = school.stage == "MAIN"
    lesson_grade = cap.split(".", 1)[0]
    if lesson_grade not in {grade.id for grade in course.grades}:
        raise ValueError("HUMAN_TRAINER_UNKNOWN_LESSON_GRADE")
    teacher = json.loads(_canonical(receipt["teacher"]))
    rng = random.Random(_seed(receipt, capability=cap))
    policy_key, policy = engine.pick(teacher, lesson_grade, rng)
    optimizer.learning_rate = float(policy["lr"])
    if source_root is None:
        raise ValueError("HUMAN_TRAINER_LIVE_SOURCE_REQUIRED")
    rows = _draw_live_rows(source_root, graph,
                           seed=_seed(receipt, capability=cap),
                           capability=cap, each=max(32, batch_size), course=course)
    champion_votes = _champion_teacher_votes(
        mx, run_dir, school, course, rows, graph,
        receipt["config"], receipt["answer_ids"])
    teacher_candidates = [r for r in rows if champion_votes.get(r["id"], 0)]
    # Every unsuccessful examination construction can become direct teaching
    # material once scoring has completed. No held-out embargo survives.
    priority = [r for r in receipt.get("teacher_misses", ())
                if r["capability"] == cap]
    miss_exposures = dict(receipt.get("teacher_miss_exposures", {}))
    if any(type(count) is not int or count < 0 for count in miss_exposures.values()):
        raise ValueError("HUMAN_TRAINER_MISS_EXPOSURE_STATE_INVALID")
    selected_misses = set()
    rows.extend(priority)
    before = _train_score(mx, params, rows, receipt["config"],
                          receipt["answer_ids"])
    last_loss = 0.0
    last_norm = 0.0
    methodology_steps = []
    methodology_unavailable = None
    replayed_misses = 0
    champion_prioritized = 0
    step_before = int(optimizer.state["step"].item())
    for step in range(steps_per_visit):
        fresh = _draw_live_rows(source_root, graph,
            seed=_seed(receipt, capability=cap, step=step+1),
            capability=cap, each=max(32, batch_size), course=course)
        fresh.extend(priority)
        picked = choose_lesson_batch(
            fresh, policy, _seed(receipt, capability=cap, step=step+1),
            batch_size=batch_size)
        before_champion = list(picked)
        picked = champion_directed_lessons(
            picked, teacher_candidates, champion_votes, capacity=batch_size)
        inserted_by_champion = {
            after_row["id"] for before_row, after_row in zip(before_champion, picked)
            if before_row["id"] != after_row["id"] and
               champion_votes.get(after_row["id"], 0)
        }
        window = select_fair_miss_window(
            priority, FairMissRequest(
                exposures=miss_exposures,
                selected_this_visit=frozenset(selected_misses),
                remaining_steps=steps_per_visit-step,
                batch_size=batch_size,
                gold_capacity={
                gold: sum(row["gold"] == gold for row in picked)
                for gold in {row["gold"] for row in picked}
                },
            ))
        picked = replay_missed_lessons(picked, window)
        for row in window:
            identity = row["id"]
            miss_exposures[identity] = miss_exposures.get(identity, 0) + 1
            selected_misses.add(identity)
        replayed_misses += len(window)
        champion_prioritized += sum(row["id"] in inserted_by_champion for row in picked)
        if methodology_unavailable is None:
            try:
                methodology_steps.append(inspect_lesson_step(
                    course, cap, [*fresh, *teacher_candidates], picked))
            except ValueError as exc:
                # A diagnostic implementation gap must not invent a new
                # training gate or silently change the evolved teacher.
                methodology_unavailable = str(exc)
        last_loss, last_norm = _train_step(
            mx, params, optimizer, picked, receipt["config"],
            receipt["answer_ids"])
    after = _train_score(mx, params, rows, receipt["config"],
                         receipt["answer_ids"])
    remaining_priority = priority
    if priority:
        miss_guesses = _predictions(
            mx, params, priority, receipt["config"], receipt["answer_ids"])
        remaining_priority = reconcile_unresolved_misses(
            priority, priority, miss_guesses)
    remaining_priority_ids = {row["id"] for row in remaining_priority}
    resolved_priority_ids = {row["id"] for row in priority} - remaining_priority_ids
    for identity in resolved_priority_ids:
        miss_exposures.pop(identity, None)
    all_teacher_misses = [
        row for row in receipt.get("teacher_misses", ())
        if row["capability"] != cap
    ] + remaining_priority
    all_teacher_misses.sort(key=lambda row: (row["capability"], row["id"]))
    reward = after - before
    engine.observe(teacher, lesson_grade, policy_key, reward)
    if int(optimizer.state["step"].item()) != step_before+steps_per_visit:
        raise ValueError("HUMAN_TRAINER_OPTIMIZER_STEP_DRIFT")
    # No new archive exists yet. The retained checkpoint is the last complete
    # recovery point, NOT a representation of these newly updated RAM weights.
    school = visit(course, school, cap, school.current_student)
    methodology = summarize_teaching_visit(
        course, cap, tuple(methodology_steps),
        introductory=introduction_pass,
        unmeasured_reason=methodology_unavailable)
    previous_methodology = next((
        member.get("lesson_methodology")
        for member in reversed(receipt.get("delivery_outbox", ()))
        if member.get("capability") == cap and "lesson_methodology" in member
    ), None)
    warnings = active_warning_signals(receipt.get("last_exam"), previous_methodology, cap)
    teacher_decision = summarize_teacher_decision(TeacherDecisionInput(
        capability=cap, policy_key=policy_key, warnings=warnings,
        unresolved_miss_count=len(priority),
        champion_candidate_count=len(teacher_candidates),
        prerequisite_capabilities=course.capability_map[cap].prerequisites,
        methodology=methodology,
        delivered_examples=steps_per_visit*batch_size,
        replayed_misses=replayed_misses,
        resolved_exam_misses=len(resolved_priority_ids),
        champion_prioritized=champion_prioritized,
        seed=_seed(receipt, capability=cap),
    ))
    event = {
        "event": ("SCHOOL_TEACHER_VISIT_COMMITTED" if lesson_grade not in ("A", "B") else
                  "GRADE_A_TEACHER_VISIT_COMMITTED" if lesson_grade == "A"
                  else "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED"),
        "grade": lesson_grade,
        "active_grade": school.grade,
        "generation": receipt["generation"] + 1,
        "capability": cap, "teacher_policy": policy_key,
        "strategy": policy, "loss": last_loss, "gradient_norm": last_norm,
        "source_training_accuracy_before": before,
        "source_training_accuracy_after": after,
        "teacher_reward": reward,
        "generator_version": lesson_contract(course, lesson_grade)[2],
        "generator_code_sha256": lesson_contract(course, lesson_grade)[3],
        "lesson_source_sha256": manifest["manifest_sha256"],
        "lesson_seed": _seed(receipt, capability=cap),
        "prior_exam_misses_available": len(priority),
        "prior_exam_misses_remaining": len(remaining_priority),
        "prior_grade_champion_votes": teacher_vote_weights(course, school),
        "champion_directed_examples_available": len(teacher_candidates),
        "lesson_methodology": methodology,
        "teacher_decision": teacher_decision,
        "optimizer_step": int(optimizer.state["step"].item()),
        "next_phase": school.stage,
        "checkpoint_status": "PROVISIONAL_UNTIL_NEXT_RECOVERY_BOUNDARY",
        "unavailable_teacher_dimensions": ["old", "preview", "distill"],
    }
    pending = list(receipt.get("_pending_visit_events", ()))
    pending.append(event)
    result = _advance(run_dir, receipt, school, teacher=teacher, persist=False)
    result["teacher_misses"] = all_teacher_misses
    result["teacher_miss_exposures"] = miss_exposures
    result.pop("teacher_miss_cursor", None)
    result["_pending_visit_events"] = pending
    return result


def _compare_incumbents(mx, run_dir, receipt, cohort, config, answer_ids, graph):
    """Replay every unique historical and current leader on this exact cohort."""
    historic = receipt.get("historical_capability_best", {}) if receipt.get(
        "legacy_frontier_pending_replay") else {}
    current = receipt.get("capability_best", {})
    references = list(current.values()) + list(historic.values()) + list(receipt.get("graduation_perfect", {}).values())
    references.extend({"checkpoint": p} for p in
                      receipt.get("historical_grade_champions", {}).values())
    # A graduate keeps a teacher/champion vote even if its current capability
    # best slot was superseded under a newer multi-grade rubric.
    references.extend({"checkpoint": p} for p in
                      receipt["school"]["champions"].values())
    unique = {}
    for item in references:
        pointer = item["checkpoint"]
        unique[pointer["sha256"]] = pointer
    best = {}
    comparisons = []
    for sha, pointer in sorted(unique.items()):
        path = run_dir / pointer["filename"]
        if (path.parent != run_dir / "bundles" or path.is_symlink()):
            raise ValueError("HUMAN_TRAINER_INCUMBENT_UNSAFE_PATH")
        weights, own_optimizer, meta, loaded_graph = load_semantically_bound_bundle(path)
        if (not _compatible_graphs(loaded_graph, graph) or meta["safetensors_sha256"] != sha or
                meta["optimizer_step"] != pointer["optimizer_step"]):
            raise ValueError("HUMAN_TRAINER_INCUMBENT_CHECKPOINT_DRIFT")
        supported = {cap for cap in {r["capability"] for r in cohort.rows}
            if all(max(r["tokens"]) < len(loaded_graph["tokens"])
                   for r in cohort.rows if r["capability"] == cap)}
        readable = tuple(r for r in cohort.rows if r["capability"] in supported)
        if not readable:
            continue
        subset = make_cohort(readable, generator_version=cohort.generator_version,
                             seed=cohort.seed, rubric_version=cohort.rubric_version)
        guesses = _predictions(mx, weights, readable,
            _compatible_answer_config(config, loaded_graph), answer_ids)
        measured = score_cohort(subset, guesses, pointer)
        comparisons.append({"checkpoint": dict(pointer),
                            "cohort_sha256": cohort.digest,
                            "scored_capabilities": sorted(supported),
                            "unsupported_capabilities": sorted(
                                {r["capability"] for r in cohort.rows}-supported),
                            "scores": measured["scores"]})
        for cap, value in measured["scores"].items():
            prior = best.get(cap)
            if prior is None or value["correct"] > prior["correct"]:
                best[cap] = {"rubric": receipt["live_rubric_sha256"],
                             "capability": cap, **value, "checkpoint": dict(pointer),
                             "evaluation_id": "same-cohort-incumbent/" + cohort.digest}
        del weights, own_optimizer
    frontier = {item["rubric"] + ":" + cap: item for cap, item in best.items()}
    return frontier, comparisons


def _commit_scored_student(mx, run_dir, receipt, manifest, course, school,
                           cohort, predictions, parameters, optimizer, graph, *,
                           reserve_gib):
    """Only evaluated best scores mint permanent capability candidates.

    If none improve, the single live student still needs a replaceable
    recovery point. This is NOT a champion or an additional archive slot.
    """
    rubric, cohort_release, _, _ = _cohort_contract(course)
    allowed = set(assessment_capabilities(course, school))
    expected = {cap: count for grade in course.grades
                for cap, count in grade.exam_item_counts if cap in allowed}
    if (receipt.get("live_rubric_sha256", rubric) != rubric or
            cohort.rubric_version != cohort_release or
            len(cohort.rows) != sum(expected.values())):
        raise ValueError("HUMAN_TRAINER_LIVE_RUBRIC_SCOPE_DRIFT")
    grades = score_cohort(cohort, predictions, {
        "sha256": "IN_MEMORY_CANDIDATE", "optimizer_step": int(optimizer.state["step"].item()),
        "model_and_native_adamw": True})["scores"]
    if ({cap: row["total"] for cap, row in grades.items()} != expected or
            any({r["gold"] for r in cohort.rows if r["capability"] == cap} !=
                {"TRUE", "FALSE"} or
                {r["universe_size"] for r in cohort.rows if r["capability"] == cap}
                != {3, 4} for cap in expected if not cap.startswith("C."))):
        raise ValueError("HUMAN_TRAINER_LIVE_EXAM_INCOMPLETE_FACTORS")
    replay_receipt = {**receipt, "live_rubric_sha256": rubric}
    frontier, incumbent_comparisons = _compare_incumbents(
        mx, run_dir, replay_receipt, cohort, receipt["config"], receipt["answer_ids"], graph)
    roles = candidate_roles(frontier, grades, rubric)
    name = ("best-" if roles else "working-") + str(school.visits) + "-" + uuid.uuid4().hex[:12]
    candidate = _bundle_pointer(run_dir, name, parameters, optimizer, graph,
                                reserve_gib=reserve_gib)
    if roles:
        proof = _fingerprint({"manifest": manifest["manifest_sha256"],
                              "rubric": rubric, "cohort": cohort.digest,
                              "predictions": sorted(predictions.items()),
                              "student_sha256": candidate.sha256,
                              "optimizer_step": candidate.optimizer_step})
        frontier = promote(frontier, grades, rubric, asdict(candidate),
                           "capability-evaluation/" + proof, roles)
    return (replace(school, current_student=candidate), frontier, roles,
            incumbent_comparisons)


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
        copy = json.loads(_canonical(event))
        copy["event_id"] = _fingerprint(["school-generation-event/v1",
                                         record["run_id"], record["generation"],
                                         index, copy])
        outbox.append(copy)
    prepared["delivery_outbox"] = outbox
    return prepared


def _reconcile_delivery_outbox(run_dir: Path, record: dict):
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
    expected = {}
    for index, event in enumerate(outbox):
        if not isinstance(event, dict) or "event_id" not in event:
            raise ValueError("HUMAN_TRAINER_OUTBOX_EVENT_ID_MISSING")
        payload = {k:v for k,v in event.items() if k != "event_id"}
        identity = _fingerprint(["school-generation-event/v1", record["run_id"],
                                 record["generation"], index, payload])
        if event["event_id"] != identity or identity in expected:
            raise ValueError("HUMAN_TRAINER_OUTBOX_LINEAGE_DRIFT")
        expected[identity] = event
    observed = set()
    journal = run_dir / "events.jsonl"
    if journal.exists():
        if journal.is_symlink() or not journal.is_file():
            raise ValueError("HUMAN_TRAINER_OUTBOX_UNSAFE_LEDGER")
        with journal.open(encoding="utf-8") as stream:
            for line in stream:
                item = json.loads(line)
                identity = item.get("event_id")
                if identity in expected:
                    if item != expected[identity]:
                        raise ValueError("HUMAN_TRAINER_OUTBOX_LEDGER_CONTENT_DRIFT")
                    observed.add(identity)
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
    retained = pinned(record.get("capability_best", {}), school["current_student"],
                      school["champions"])
    retained |= pinned(record.get("graduation_perfect", {}),
                       school["current_student"], school["champions"])
    for item in record.get("historical_grade_champions", {}).values():
        retained |= pinned({}, item, {})
    if record.get("legacy_frontier_pending_replay"):
        retained |= pinned(record.get("historical_capability_best", {}),
                           school["current_student"], school["champions"])
    _quarantine_newer_uncommitted_bundles(run_dir, retained,
                                          school["current_student"]["optimizer_step"])
    removed = retire_bundles(run_dir, retained)
    if removed:
        _record(run_dir, {"event": "SCHOOL_CHECKPOINTS_RETIRED", "grade": active_grade,
                          "generation": record["generation"],
                          "count": len(removed), "protected_count": len(retained)})


def _quarantine_newer_uncommitted_bundles(run_dir: Path, retained: set[str],
                                          current_optimizer_step: int) -> tuple[str, ...]:
    """Never prune a post-update model published before its pointer crashed."""
    root = run_dir / "bundles"
    if not root.exists():
        return ()
    quarantined = []
    for candidate in sorted(root.iterdir()):
        relative = "bundles/" + candidate.name
        if relative in retained:
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError("HUMAN_TRAINER_UNCOMMITTED_BUNDLE_UNSAFE_PATH")
        weights, own_adamw, metadata, graph = load_semantically_bound_bundle(candidate)
        if (metadata["source_digest"] != AUDITED_PARENT.sha256 or
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
        fd = os.open(target_parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        _record(run_dir, {"event": "SCHOOL_NEWER_UNCOMMITTED_BUNDLE_QUARANTINED",
                          "grade": "A", "filename": str(target.relative_to(run_dir)),
                          "optimizer_step": metadata["optimizer_step"],
                          "student_sha256": metadata["safetensors_sha256"],
                          "prior_committed_optimizer_step": current_optimizer_step})
    return tuple(quarantined)


def _take_exam(mx, run_dir, receipt, manifest, course, source_root,
               source_checkpoint, parameters, optimizer, graph, *, reserve_gib):
    school = _state_from_json(receipt["school"], course)
    if not school.stage.startswith("ASSESS_"):
        raise ValueError("HUMAN_TRAINER_EXAM_OUTSIDE_SCHEDULED_BOUNDARY")
    rubric, release, generator, _ = _cohort_contract(course)
    cohort, qualification = _grade_test_cohort(
        run_dir, receipt, manifest, course, source_root, graph)
    cohort, cohort_file = _introduced_cohort(run_dir, manifest, course, school, cohort)
    seed, rows = cohort.seed, list(cohort.rows)
    candidate_cohort = _candidate_cohort(
        run_dir, receipt, manifest, course, source_root, graph)
    candidate_cohort, _ = _introduced_cohort(
        run_dir, manifest, course, school, candidate_cohort)
    candidate_guesses = _predictions(
        mx, parameters, list(candidate_cohort.rows),
        receipt["config"], receipt["answer_ids"])
    school, frontier, roles, compared = _commit_scored_student(
        mx, run_dir, receipt, manifest, course, school,
        candidate_cohort, candidate_guesses,
        parameters, optimizer, graph, reserve_gib=reserve_gib)
    guesses = _predictions(mx, parameters, rows,
                           receipt["config"], receipt["answer_ids"])
    measured = score_cohort(cohort, guesses, asdict(school.current_student))
    assessment = Assessment(
        checkpoint_sha256=school.current_student.sha256,
        optimizer_step=school.current_student.optimizer_step,
        course_digest=course.digest(),
        rubric_digest=rubric,
        scores={cap: Score(**entry) for cap, entry in measured["scores"].items()},
        evaluation_id="source-oracled-live-cohort/" + cohort.digest + "/" +
                      school.current_student.sha256)
    advanced = assess(course, school, assessment)
    scores = {k: {"correct": v.correct, "total": v.total}
              for k, v in assessment.scores.items()}
    perfect, perfect_roles = graduation_perfect(
        receipt.get("graduation_perfect", {}), scores, rubric, cohort.digest,
        asdict(school.current_student), assessment.evaluation_id)
    last_exam = {
        "assessment_grade": school.grade,
        "grade_exam_epoch": school.grade_exam_epoch,
        "grade_test_lifecycle": GRADE_TEST_LIFECYCLE,
        "assessment_scope_sha256": _fingerprint(assessment_capabilities(course, school)),
        "evaluation_id": assessment.evaluation_id,
        "exam_rubric_sha256": assessment.rubric_digest,
        "cohort_sha256": cohort.digest,
        "cohort_file": cohort_file,
        "cohort_seed": seed,
        "candidate_cohort_sha256": candidate_cohort.digest,
        "graduation_perfect_roles": list(perfect_roles),
        "generator_version": generator,
        "incumbent_comparisons": compared,
        "misses_for_teacher": list(measured["misses_for_teacher"]),
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "scores": scores,
    }
    pending = receipt.get("_pending_visit_events", ())
    exam_warnings = summarize_completed_exam_safely(run_dir, receipt, last_exam)
    last_exam["learning_diagnostics"] = exam_warnings
    teacher_outcomes = summarize_teacher_outcomes(receipt.get("last_exam"), last_exam, pending)
    last_exam["teacher_outcomes"] = teacher_outcomes
    # Exam golds become eligible *after* the complete examination. Retain
    # tokens and source provenance so the next weakest-three visits can train
    # directly on missed semantics, with no answer leakage during scoring.
    priority = reconcile_unresolved_misses(
        receipt.get("teacher_misses", ()), rows, guesses)
    unresolved_ids = {row["id"] for row in priority}
    miss_exposures = {
        identity: count for identity, count in
        receipt.get("teacher_miss_exposures", {}).items()
        if identity in unresolved_ids and type(count) is int and count >= 0
    }
    for identity in unresolved_ids:
        miss_exposures.setdefault(identity, 0)
    migrated_receipt = {**receipt, "teacher_misses": priority,
                        "graduation_perfect": perfect,
                        "qualification_cohort": qualification,
                        "teacher_miss_exposures": miss_exposures,
                        "legacy_frontier_pending_replay": False,
                        "live_rubric_sha256": assessment.rubric_digest}
    migrated_receipt.pop("teacher_miss_cursor", None)
    result = _advance(
        run_dir, migrated_receipt, advanced, frontier=frontier,
        model_bundle=school.current_student.filename, last_exam=last_exam,
        result=(("GRADE_"+advanced.grade+"_MASTERED_AWAITING_GRADE_"+chr(ord(advanced.grade)+1))
                if advanced.stage == "AWAITING_NEXT_GRADE" else
                ("GRADE_" + advanced.revalidation_target_grade +
                 "_REVALIDATING_" + advanced.grade)
                if advanced.revalidation_target_grade else
                "ACTIVE_GRADE_" + advanced.grade), persist=False)
    exam_event = {
        "event": ("SCHOOL_LIVE_EXAM_COMMITTED" if len(course.grades) > 2 else
                  "GRADE_A_LIVE_EXAM_COMMITTED" if len(course.grades) == 1
                  else "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED"),
        "grade": school.grade, "generation": result["generation"],
        "grade_exam_epoch": school.grade_exam_epoch,
        "grade_test_lifecycle": GRADE_TEST_LIFECYCLE,
        "assessment_scope_sha256": last_exam["assessment_scope_sha256"],
        "qualification_cohort_sha256": qualification["cohort_sha256"],
        "introduction_stage": school.introduction_stage,
        "scores": scores, "phase": advanced.stage,
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "rubric": assessment.rubric_digest,
        "cohort_sha256": cohort.digest, "generator_version": generator,
        "cohort_seed": seed, "cohort_file": last_exam["cohort_file"],
        "incumbent_comparisons": compared,
        "teacher_miss_count": len(priority),
        "learning_diagnostics": exam_warnings,
        "teacher_outcomes": teacher_outcomes,
    }
    result = _persist(run_dir, _with_delivery_outbox(
        result, _boundary_delivery_events(result, pending, roles, exam_event)))
    _publish_boundary(run_dir, result, pending, roles, exam_event=exam_event)
    return result


def _flush_working_student(mx, run_dir, receipt, manifest, course, parameters,
                           optimizer, graph, *, reserve_gib, source_root):
    """Protect an unfinished grade cycle when the human stops mid-cycle."""
    pending = receipt.get("_pending_visit_events", ())
    if not pending:
        return receipt
    school = _state_from_json(receipt["school"], course)
    rubric, release, generator, _ = _cohort_contract(course)
    cohort, qualification = _grade_test_cohort(
        run_dir, receipt, manifest, course, source_root, graph)
    cohort = _candidate_cohort(run_dir, receipt, manifest, course, source_root, graph)
    cohort, _ = _introduced_cohort(run_dir, manifest, course, school, cohort)
    rows = list(cohort.rows)
    guesses = _predictions(mx, parameters, rows, receipt["config"], receipt["answer_ids"])
    current, frontier, roles, compared = _commit_scored_student(
        mx, run_dir, receipt, manifest, course, school, cohort, guesses,
        parameters, optimizer, graph, reserve_gib=reserve_gib)
    record = _advance(run_dir, {**receipt, "legacy_frontier_pending_replay": False,
                                "qualification_cohort": qualification,
                                "live_rubric_sha256": rubric},
                      current, frontier=frontier,
                      model_bundle=current.current_student.filename, persist=False)
    comparison_event = {
        "event": "SCHOOL_LIVE_CANDIDATE_COMPARED", "grade": school.grade,
        "generation": record["generation"],
        "rubric": rubric,
        "cohort_sha256": cohort.digest, "generator_version": generator,
        "scores": score_cohort(cohort, guesses,
            asdict(current.current_student))["scores"],
        "student_sha256": current.current_student.sha256,
        "optimizer_step": current.current_student.optimizer_step,
        "incumbent_comparisons": compared}
    record = _persist(run_dir, _with_delivery_outbox(
        record, _boundary_delivery_events(record, pending, roles, comparison_event)))
    _publish_boundary(run_dir, record, pending, roles, exam_event=comparison_event)
    return record


def session_stop_reason(*, stage: str, elapsed_seconds: float, minutes: int,
                        visits: int, max_visits: int, grade: str = "A") -> str | None:
    """State-machine stop condition; a due exam must not be silently skipped."""
    if stage == "WHOLE_SCHOOL_MASTERED":
        return "WHOLE_SCHOOL_MASTERED"
    if stage == "AWAITING_TEACHER_SOUP":
        # Future full-program releases must not accidentally invoke a lesson
        # with no scheduled capability or convert a soup into a student.
        return "AWAITING_TEACHER_SOUP"
    if stage == "AWAITING_NEXT_GRADE":
        return "GRADE_" + grade + "_AWAITING_NEXT_GRADE"
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
    manifest, historical_course, engine, teacher_sha, historical_teacher, provenance = prepare_source(
        source_root, source_checkpoint, manifest_path)
    course_a = live_course(historical_course)
    # Build only verified source-bound metadata; no student, optimizer or
    # checkpoint is touched while preparing a future grade's course.
    course_b = None
    course_c = None
    course = course_a
    run_dir = Path(run_dir).expanduser().resolve()
    start = time.monotonic()
    with operator_lock(run_dir):
        if resume:
            saved = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            # Source-neutral ABI constant extraction changed the byte-derived
            # A fingerprint, cascading into B's course seal. Preserve the
            # exact archived A/B contract when its known digest is present.
            from .historical_live_release import (
                HISTORICAL_B_COURSE_SHA256, historical_grade_a_course,
                historical_grade_b_course,
            )
            saved_digest = saved["school"]["course_digest"]
            if saved_digest == HISTORICAL_B_COURSE_SHA256:
                course_a, course_b = historical_grade_b_course(
                    historical_course, source_root)
            elif (saved.get("curriculum_mode") == LIVE_RELEASE and
                  saved_digest != course_a.digest()):
                historical_a = historical_grade_a_course(historical_course)
                if saved_digest == historical_a.digest():
                    course_a = historical_a
            pending = run_dir / "states" / f"{saved['generation'] + 1:07d}.json"
            if pending.exists() and (pending.is_symlink() or not pending.is_file()):
                raise ValueError("HUMAN_TRAINER_PENDING_GENERATION_UNSAFE_PATH")
            pending_mode = (json.loads(pending.read_text(encoding="utf-8")).get(
                "curriculum_mode") if pending.exists() else None)
            # A trainer still acquiring A must never depend on readiness of a
            # *future* B release. Only a B run, graduated A, or prospective B
            # orphan needs B's source construction and version guard.
            if (saved.get("curriculum_mode") in (B_RELEASE, C_RELEASE) or
                    pending_mode in (B_RELEASE, C_RELEASE) or
                    saved["school"]["stage"] == "AWAITING_NEXT_GRADE"):
                if course_b is None:
                    course_b = live_b_course(course_a, source_root)
            if saved.get("curriculum_mode") == B_RELEASE:
                course = course_b
            if (saved.get("curriculum_mode") == C_RELEASE or pending_mode == C_RELEASE or
                    (saved.get("curriculum_mode") == B_RELEASE and
                     saved["school"]["stage"] == "AWAITING_NEXT_GRADE")):
                from .live_grade_c import prepare_course
                pinned_maximum = saved.get("numeric_maximum")
                if pending_mode == C_RELEASE and pinned_maximum is None:
                    pinned_maximum = json.loads(pending.read_text())["numeric_maximum"]
                course_c, _ = prepare_course(course_b, maximum=pinned_maximum)
                if saved.get("curriculum_mode") == C_RELEASE:
                    course = course_c
            params, optimizer, graph, receipt = _resume(
                run_dir, manifest, course, teacher_sha,
                successor_course=course_b,
                admitted_courses={c.version: c for c in (course_a, course_b, course_c) if c is not None})
            # A fully written B migration might have survived a crash before
            # publishing the latest state pointer. _resume recovers it under
            # operator_lock; do not interpret recovered B as an A-only run.
            if receipt.get("curriculum_mode") == B_RELEASE:
                course = course_b
            elif receipt.get("curriculum_mode") == C_RELEASE:
                course = course_c
            # A previously graduated human student is the only admissible B
            # starter. Never reset its whole weights, AdamW or teacher policy.
            if (course == course_a and
                    receipt["school"]["stage"] == "AWAITING_NEXT_GRADE"):
                # An A graduation itself can be the recovered orphan rather
                # than the state originally read before _resume's recovery.
                if course_b is None:
                    course_b = live_b_course(course_a, source_root)
                receipt = _activate_next_admitted_grade(
                    run_dir, receipt, course_a, course_b)
                course = course_b
            elif (course == course_b and receipt["school"]["stage"] == "AWAITING_NEXT_GRADE"):
                from .live_grade_c import prepare_course
                from .grade_transition import activate_numeric_grade
                if course_c is None:
                    course_c, _ = prepare_course(course_b)
                params, optimizer, graph, receipt = activate_numeric_grade(
                    mx, run_dir, receipt, course_b, course_c, params, optimizer, graph,
                    reserve_gib=reserve_gib)
                course = course_c
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
                minutes=minutes, visits=visits, max_visits=max_visits,
                grade=school.grade)
            if reason is not None:
                break
            if school.stage.startswith("ASSESS_"):
                receipt = _take_exam(
                    mx, run_dir, receipt, manifest, course, source_root,
                    source_checkpoint, params, optimizer, graph,
                    reserve_gib=reserve_gib)
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
                batch_size=batch_size, reserve_gib=reserve_gib,
                source_root=source_root)
            visits += 1
        receipt = _flush_working_student(
            mx, run_dir, receipt, manifest, course, params, optimizer, graph,
            reserve_gib=reserve_gib, source_root=source_root)
        school = _state_from_json(receipt["school"], course)
        budget = headroom_snapshot(run_dir, required_bytes=600_000_000,
                                   reserve_gib=reserve_gib)
        elapsed_seconds = round(time.monotonic() - start, 3)
        _record(run_dir, {
            "event": "GRADE_A_SESSION_STOPPED" if len(course.grades) == 1
                     else "SCHOOL_SESSION_STOPPED", "stop_reason": reason,
            "generation": receipt["generation"], "run_id": receipt["run_id"],
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "visits_this_command": visits, "committed_total_visits": school.visits,
            "minutes": minutes, "max_visits": max_visits,
            "elapsed_seconds": elapsed_seconds,
            "grade_phase": school.stage, "grade": school.grade,
            "resume_required": school.stage != "AWAITING_NEXT_GRADE",
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
