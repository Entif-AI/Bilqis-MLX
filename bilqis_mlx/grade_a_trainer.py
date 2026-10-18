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
from functools import lru_cache
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import sys
import time
import uuid

from .backup import digest_file
from .champions import Checkpoint
from .champion_confidence import MAX_INFLUENCE as MAX_CHAMPION_INFLUENCE
from .champion_confidence import vote_targets_typed
from .champion_confidence import POLICY as CHAMPION_CONFIDENCE_POLICY
from .champion_confidence import champion_roster, vote_targets
from .grade_soup import (grade_soup_recipe, partitioned_recipe,
                         PARTITIONED_SCHEMA, soup_shards, needs_refresh, soup_vote_count,
                         weighted_average, save_frozen_soup, verify_frozen_soup,
                         retire_stale_soups)
from .learning_experiment import (
    VERSION as LEARNING_EXPERIMENT_VERSION, Settings as LearningSettings,
    contextual_pick, paired_outcomes, decide as decide_learning_trial,
    observe_context, selection_credit, fork_student, commit_trial,
    earlier_grade_capabilities, select_source_lesson, sampled_protection,
    missing_grade_capabilities,
)
from .whole_student_retention import advance_peaks
from .epoch_championships import (
    active_frontier as epoch_active_frontier,
    needed_incumbents as epoch_needed_incumbents,
    advance_epoch as advance_championship_epoch,
)
from .mentor_epoch import EARNED_ONLY_POLICY
from .capability_frontier import (
    candidate_roles, graduation_perfect, historical_frontier, pinned, promote,
    recover_graduation_breadth, retire_bundles,
)
from .disk import assert_headroom, headroom_snapshot
from .diagnostics.teaching import inspect_lesson_step, summarize_teaching_visit
from .diagnostics.exam_events import (apply_paired_checkpoint_s3,
                                      summarize_completed_exam_safely)
from .generated_assessment import (
    GRADE_TEST_LIFECYCLE, PROMOTION_ATTEMPT_LIFECYCLE,
    ROUTINE_EVAL_LIFECYCLE, make_cohort, score as score_cohort,
)
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
from .numeric_staircase import RELEASE as STAIRCASE_RELEASE
from .mlx_checkpoint import save_new_bundle, load_semantically_bound_bundle
from .mlx_parity import (clip_gradients, forward_arrays,
                         native_optimizer_to_mlx)
from .school import (start_new, visit, assess, assess_withheld, next_capability,
                     append_next_grade, assessment_capabilities,
                     reactivate_stagnation_debt, weakest_three,
                     SchoolState, Assessment, Score)
from .stagnation_control import (
    activate_sole_grade_rehabilitation,
    begin_recovery_cycle, complete_recovery_cycle, end_of_run_alerts,
    grace_suppressed_capabilities, reconcile_optimizer_step_grace,
    quarantined_capabilities, record_visit as record_stagnation_visit,
    start_session as start_stagnation_session,
)
from .semantics.abi import HISTORICAL_PREFIX_SIZE
from .source import AUDITED_PARENT
from .teacher_feedback import (
    FairMissRequest, TeacherDecisionInput, active_warning_signals, reconcile_unresolved_misses,
    select_fair_miss_window, summarize_teacher_decision,
    summarize_teacher_outcomes,
)
from .timing_trace import trace_mark, trace_span

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


def replay_missed_lessons(chosen: list[dict], missed: list[dict], *,
                          reserved_ids=()) -> list[dict]:
    """Guarantee every requested missed construction reaches this optimizer batch."""
    if len(missed) > len(chosen):
        raise ValueError("HUMAN_TRAINER_MISS_REPLAY_EXCEEDS_BATCH")
    result = list(chosen)
    reserved = set(reserved_ids)
    consumed = {index for index, row in enumerate(result)
                if row.get("id") in reserved}
    for item in missed:
        replacement = next((i for i, row in enumerate(result)
                            if i not in consumed and row["gold"] == item["gold"]), None)
        if replacement is None:
            raise ValueError("HUMAN_TRAINER_MISS_REPLAY_ANSWER_CLASS_CAPACITY")
        result[replacement] = item
        consumed.add(replacement)
    return result


@lru_cache(maxsize=16)
def _cached_frozen_champion(path_string, sha, step, file_size, file_mtime_ns):
    """Bound repeat source reads; never cache optimizer moments."""
    weights, own_optimizer, meta, source_graph = load_semantically_bound_bundle(
        Path(path_string))
    if (meta["safetensors_sha256"] != sha or
            meta["optimizer_step"] != step or
            meta["source_digest"] != AUDITED_PARENT.sha256):
        raise ValueError("CHAMPION_CONFIDENCE_BUNDLE_DRIFT")
    del own_optimizer
    return weights, source_graph


def _frozen_confidence_champions(run_dir, receipt, grade, graph):
    """Read each current-grade perfect champion once, without changing it."""
    mentors = []
    snapshot = receipt.get("grade_soups", {}).get(grade)
    if snapshot is None and any(
            role.get("capability", "").startswith(grade + ".")
            for role in receipt.get("graduation_perfect", {}).values()):
        raise ValueError("CHAMPION_CONFIDENCE_GRADE_SOUP_MISSING_FOR_ACTIVE_ROLES")
    for item in champion_roster(receipt.get("graduation_perfect", {}), grade,
                               snapshot=snapshot):
        pointer = item["checkpoint"]
        path = run_dir / pointer["filename"]
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not pointer["filename"].startswith("bundles/")):
            raise ValueError("CHAMPION_CONFIDENCE_UNSAFE_BUNDLE")
        content = (path / "model-and-own-adamw.safetensors").stat()
        weights, source_graph = _cached_frozen_champion(
            str(path), pointer["sha256"], pointer["optimizer_step"],
            content.st_size, content.st_mtime_ns)
        if not _compatible_graphs(source_graph, graph):
            raise ValueError("CHAMPION_CONFIDENCE_BUNDLE_DRIFT")
        mentors.append({"weights": weights, "graph": source_graph,
                        "breadth": item["breadth"]})
    return tuple(mentors)


def _mentor_sources_for_visit(run_dir, receipt, grade, graph, grade_count):
    """Select only current-epoch champions and soups after curriculum reset."""
    epoch = receipt.get("mentor_epoch")
    if epoch is None:
        return (_frozen_confidence_champions(run_dir, receipt, grade, graph),
                *_frozen_grade_soup_votes(run_dir, receipt, grade, grade_count))
    if epoch.get("source_graph_sha256") != _fingerprint(graph):
        raise ValueError("MENTOR_EPOCH_SOURCE_GRAPH_DRIFT")
    if epoch.get("guidance_policy") != EARNED_ONLY_POLICY:
        raise ValueError("MENTOR_EPOCH_FRESH_CHAMPIONS_RESET_REQUIRED")
    active = {"graduation_perfect": epoch_active_frontier(epoch),
              "grade_soups": epoch.get("active_grade_soups", {})}
    if not active["graduation_perfect"] and not active["grade_soups"]:
        return (), (), ()
    mentors = list(_frozen_confidence_champions(run_dir, active, grade, graph))
    soups, receipts = _frozen_grade_soup_votes(
        run_dir, active, grade, grade_count)
    return tuple(mentors), soups, receipts


def _cook_new_grade_soups(mx, run_dir, receipt, frontier, course, graph,
                          *, reserve_gib, existing=None):
    """Freeze newly broader or displaced grade-champion weight recipes."""
    current = dict(receipt.get("grade_soups", {}) if existing is None else existing)
    refreshed = []
    for grade in course.grades:
        plan = grade_soup_recipe(
            frontier, grade.id, tuple(cap.id for cap in grade.capabilities))
        if not needs_refresh(current.get(grade.id), plan):
            continue
        members = []
        catalogs = {}
        graph_digests = {}
        for item in plan["members"]:
            pointer = item["checkpoint"]
            path = run_dir / pointer["filename"]
            if path.is_symlink() or path.parent != run_dir / "bundles":
                raise ValueError("GRADE_SOUP_UNSAFE_CHAMPION_BUNDLE")
            weights, own_adamw, manifest, original_graph = load_semantically_bound_bundle(path)
            if (manifest["source_digest"] != AUDITED_PARENT.sha256 or
                    manifest["safetensors_sha256"] != pointer["sha256"] or
                    manifest["optimizer_step"] != pointer["optimizer_step"] or
                    not _compatible_graphs(original_graph, graph)):
                raise ValueError("GRADE_SOUP_CHAMPION_CUSTODY_DRIFT")
            sha = pointer["sha256"]
            graph_digest = _fingerprint(original_graph)
            if (graph_digest in catalogs and
                    original_graph != catalogs[graph_digest]):
                raise ValueError("GRADE_SOUP_INGREDIENT_GRAPH_DIGEST_COLLISION")
            catalogs[graph_digest] = original_graph
            graph_digests[sha] = graph_digest
            members.append((sha, item["votes"], weights))
            del own_adamw
        if len(catalogs) == 1:
            graph_digest, catalog = next(iter(catalogs.items()))
            combined = weighted_average(mx, [
                (votes, weights) for _, votes, weights in members])
            snapshot = save_frozen_soup(run_dir, plan, combined,
                                        reserve_gib=reserve_gib,
                                        token_count=len(catalog["tokens"]))
            snapshot["source_graph_sha256"] = graph_digest
        else:
            # Each exact source graph owns its own frozen weight mixture.
            # Append-only older prefixes may advise their supported tokens,
            # but must never masquerade as expanded embedding matrices.
            by_sha = {sha: (votes, weights) for sha, votes, weights in members}
            shards = []
            for shard_plan in partitioned_recipe(plan, graph_digests):
                graph_digest = shard_plan["source_graph_sha256"]
                combined = weighted_average(mx, [
                    by_sha[item["checkpoint"]["sha256"]]
                    for item in shard_plan["members"]])
                frozen = save_frozen_soup(
                    run_dir, shard_plan, combined, reserve_gib=reserve_gib,
                    token_count=len(catalogs[graph_digest]["tokens"]))
                frozen["source_graph_sha256"] = graph_digest
                shards.append(frozen)
            snapshot = {**plan, "schema": PARTITIONED_SCHEMA,
                        "shards": shards,
                        "partition_policy": "EXACT_SOURCE_GRAPH_NO_MIXED_PARAMETER_AVERAGE"}
        previous = current.get(grade.id)
        if previous is not None:
            snapshot["coverage_peak"] = max(
                previous["coverage_peak"], snapshot["coverage_peak"])
            snapshot["previous"] = [
                {"filename": part["filename"], "sha256": part["sha256"]}
                for part in soup_shards(previous)]
        current[grade.id] = snapshot
        refreshed.append(grade.id)
    return current, tuple(refreshed)


@lru_cache(maxsize=12)
def _cached_grade_soup(path_string, sha, token_count, stat_size, stat_mtime_ns):
    """Verify a frozen soup once per exact file identity for repeated lessons."""
    import mlx.core as mx
    path = Path(path_string)
    if digest_file(path) != sha:
        raise ValueError("GRADE_SOUP_SAVED_ARTIFACT_CHANGED")
    weights = mx.load(str(path))
    if ("embedding.weight" not in weights or
            weights["embedding.weight"].shape[0] != token_count or
            any(array.dtype != mx.float32 for array in weights.values())):
        raise ValueError("GRADE_SOUP_FROZEN_MODEL_SHAPE_DRIFT")
    return weights


def _frozen_grade_soup_votes(run_dir, receipt, lesson_grade, school_grade_count):
    """Use frozen base votes; only the foreign-grade divisor is live."""
    mentors, receipts = [], []
    for grade, snapshot in sorted(receipt.get("grade_soups", {}).items()):
        if grade != snapshot.get("grade"):
            raise ValueError("GRADE_SOUP_GRADE_POINTER_DRIFT")
        for shard in soup_shards(snapshot):
            path = run_dir / shard["filename"]
            if (path.parent != run_dir / "soups" or path.is_symlink()):
                raise ValueError("GRADE_SOUP_UNSAFE_SAVED_PATH")
            stat = path.stat()
            weights = _cached_grade_soup(
                str(path), shard["sha256"], shard["token_count"],
                stat.st_size, stat.st_mtime_ns)
            votes = soup_vote_count(shard, lesson_grade, school_grade_count)
            mentors.append({"weights": weights, "vocab_size": shard["token_count"],
                            "breadth": votes})
            receipts.append({"soup_grade": grade,
                             "recipe_sha256": snapshot["recipe_sha256"],
                             "ingredient_recipe_sha256": shard["recipe_sha256"],
                             "frozen_base_votes": shard["vote_count"],
                             "effective_votes": votes,
                             "source_graph_sha256": shard.get("source_graph_sha256")})
    return tuple(mentors), tuple(receipts)


def _confidence_guidance(mx, mentors, picked, config, answer_ids,
                         *, scope_size, teacher_distill):
    """Gold-agreeing frozen logits are small, policy-shaped gradient advice."""
    if not mentors or teacher_distill <= 0 or any(
            row.get("answer_kind", "binary") != "binary" for row in picked):
        return None
    import numpy as np
    ids, lengths, labels = _make_batch(picked)
    vote_logits = []
    for mentor in mentors:
        vocabulary = (mentor.get("vocab_size") or len(mentor["graph"]["tokens"]))
        if (max(answer_ids) >= vocabulary or
                any(max(row["tokens"]) >= vocabulary for row in picked)):
            continue
        logits = forward_arrays(mx, mentor["weights"], ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        mx.eval(logits)
        vote_logits.append((mentor["breadth"], np.asarray(logits)[:, :2]))
    target, influence = vote_targets(vote_logits, labels,
                                     eligible_capabilities=scope_size,
                                     teacher_distill=teacher_distill)
    return (target, influence) if np.any(influence) else None


def _typed_confidence_guidance(mx, mentors, picked, config, *, scope_size,
                               teacher_distill):
    """Source-gold-agreeing grade-soup/same-grade advice for typed heads.

    The trained student and the frozen mentors are distinct. Historical
    smaller-vocabulary soups participate only in heads their tokens support.
    """
    import numpy as np
    from .typed_answer_training import prepare_typed_batches
    if teacher_distill <= 0 or not mentors:
        return None
    batches = prepare_typed_batches(picked, config["answer_heads"])
    guidance = {}
    for kind, batch in batches.items():
        eligible = []
        answer_ids = batch["answer_ids"]
        if not answer_ids:
            continue
        for mentor in mentors:
            vocabulary = mentor.get("vocab_size") or len(mentor["graph"]["tokens"])
            if (max(answer_ids) >= vocabulary or
                    int(batch["ids"].max()) >= vocabulary):
                continue
            logits = forward_arrays(
                mx, mentor["weights"], batch["ids"], batch["lengths"],
                heads=config["heads"], layers=config["layers"], answer_ids=answer_ids)
            mx.eval(logits)
            eligible.append((mentor["breadth"], np.asarray(logits)))
        if not eligible:
            continue
        target, weight = vote_targets_typed(
            eligible, batch["target_indices"], classes=len(answer_ids),
            eligible_capabilities=scope_size, teacher_distill=teacher_distill)
        if np.any(weight):
            guidance[kind] = (target, weight)
    return guidance or None


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


def _train_step(mx, parameters, optimizer, rows, config, answer_ids,
                *, champion_guidance=None):
    if any(row.get("answer_kind", "binary") != "binary" for row in rows):
        from .typed_answer_training import typed_step
        return typed_step(mx, parameters, optimizer, rows, config["answer_heads"],
                          config, champion_guidance=champion_guidance)
    import numpy as np
    ids, lengths, labels = _make_batch(rows)
    expected = mx.array(np.eye(2, dtype=np.float32)[labels])
    advice = None
    if champion_guidance is not None:
        target, weight = champion_guidance
        target = np.asarray(target, dtype=np.float32)
        weight = np.asarray(weight, dtype=np.float32)
        if (target.shape != (len(rows), 2) or weight.shape != (len(rows),) or
                not np.isfinite(target).all() or not np.isfinite(weight).all() or
                (weight < 0).any() or (weight > MAX_CHAMPION_INFLUENCE + 1e-6).any() or
                (target < 0).any() or
                not np.allclose(target.sum(axis=-1), 1., atol=1e-6)):
            raise ValueError("CHAMPION_CONFIDENCE_TRAINING_GUIDANCE_INVALID")
        advice = (mx.array(target), mx.array(weight))

    def objective(weights):
        logits = forward_arrays(mx, weights, ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        typed = logits[:, :2]
        normalizer = mx.logsumexp(typed, axis=-1)
        loss = mx.mean(normalizer - mx.sum(typed * expected, axis=-1))
        if advice is not None:
            # Frozen confidence teaches only through this bounded gradient;
            # no exam inference ever reads the champion-adjusted logits.
            soft_target, strength = advice
            loss = loss + mx.mean(strength *
                 (normalizer - mx.sum(typed * soft_target, axis=-1)))
        return loss

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
    if saved_mode not in (None, LIVE_RELEASE, B_RELEASE, C_RELEASE, STAIRCASE_RELEASE):
        raise ValueError("HUMAN_TRAINER_UNKNOWN_CURRICULUM_MODE")
    old_course = ((admitted_courses or {})[saved_mode] if saved_mode in (admitted_courses or {}) else
                  accepted_grade_a(manifest) if old_mode else
                  live_course(accepted_grade_a(manifest)) if saved_mode == LIVE_RELEASE
                  else successor_course if successor_course is not None else course)
    if saved_mode == B_RELEASE and (len(old_course.grades) != 2 or
                                    old_course.version != B_RELEASE or
                                    receipt.get("grade_b_code_sha256") != b_constructor_digest()):
        raise ValueError("HUMAN_TRAINER_GRADE_B_COURSE_NOT_LOADED")
    if saved_mode in (C_RELEASE, STAIRCASE_RELEASE):
        from .live_grade_c import constructor_digest
        if (old_course.version != saved_mode or len(old_course.grades) != 3 or
                receipt.get("grade_c_code_sha256") != constructor_digest()):
            raise ValueError("HUMAN_TRAINER_GRADE_C_COURSE_NOT_LOADED")
    if saved_mode == STAIRCASE_RELEASE:
        from .numeric_staircase import constructor_digest as staircase_digest
        if receipt.get('staircase_code_sha256') != staircase_digest():
            raise ValueError('NUMERIC_STAIRCASE_SOURCE_DRIFT')
    school = _state_from_json(receipt["school"], old_course)
    directory = (run_dir / receipt["model_bundle"]).resolve(strict=True)
    if directory.parent != (run_dir / "bundles").resolve(strict=True):
        raise ValueError("HUMAN_TRAINER_BUNDLE_PATH_ESCAPES_RUN")
    parameters, optimizer, bundle, graph = load_semantically_bound_bundle(directory)
    if saved_mode in (C_RELEASE, STAIRCASE_RELEASE):
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
    if any("breadth" not in entry for entry in
           receipt.get("graduation_perfect", {}).values()):
        with (run_dir / "events.jsonl").open(encoding="utf-8") as history:
            ranked = recover_graduation_breadth(
                receipt["graduation_perfect"],
                (json.loads(line) for line in history if line.strip()))
        # Original immutable generations stay untouched until a new boundary.
        receipt = {**receipt, "graduation_perfect": ranked}
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
    from .mentor_epoch import begin_epoch
    exam = receipt.get("last_exam") or {}
    prior_caps = tuple(cap.id for grade in previous_course.grades
                       for cap in grade.capabilities)
    epoch = begin_epoch(
        previous_graduate=asdict(school.current_student),
        admitted_baseline=asdict(next_state.current_student),
        introduced_grade=successor.grades[-1].id,
        source_graph_sha256=receipt["semantic_graph_sha256"],
        previous_capabilities=prior_caps,
        previous_graduation_exam={
            "checkpoint_sha256": exam.get("student_sha256"),
            "rubric_sha256": exam.get("exam_rubric_sha256"),
            "cohort_sha256": exam.get("cohort_sha256"),
            "scores": exam.get("scores"),
        })
    history = list(receipt.get("championship_epoch_history", ()))
    if receipt.get("mentor_epoch") is not None:
        history.append(receipt["mentor_epoch"])
    candidate = {**receipt, "curriculum_mode": B_RELEASE,
                 "live_rubric_sha256": successor.grades[-1].assessment_sha256,
                 "grade_b_code_sha256": b_constructor_digest(),
                 "mentor_epoch": epoch,
                 "championship_epoch_history": history}
    record = _advance(run_dir, candidate, next_state, result="ACTIVE_GRADE_B",
                      persist=False)
    admitted = {"event": "SCHOOL_GRADE_B_COURSE_ADMITTED",
                      "generation": record["generation"], "grade": "B",
                      "previous_cohort_sha256": (record.get("last_exam") or {}).get("cohort_sha256"),
                      "grade_a_champion_sha256": school.champions["A"].sha256,
                      "student_sha256": school.current_student.sha256,
                      "optimizer_step": school.current_student.optimizer_step,
                      "teacher_events": record["teacher"]["events"],
                      "championship_baseline_sha256": epoch["baseline"]["sha256"],
                      "archived_championship_epochs": len(history),
                      "grade_b_rubric": successor.grades[-1].assessment_sha256,
                      "grade_b_generator": B_GENERATOR,
                      "model_and_own_adamw_unchanged": True}
    record = _persist(run_dir, _with_delivery_outbox(record, (admitted,)))
    _reconcile_delivery_outbox(run_dir, record)
    return record


def _mentor_epoch_references(receipt):
    if receipt.get("mentor_epoch") is None:
        return ()
    from .mentor_epoch import reference_checkpoints
    epochs = (*receipt.get("championship_epoch_history", ()), receipt["mentor_epoch"])
    return tuple(pointer for epoch in epochs
                 for pointer in (
                     *reference_checkpoints(epoch),
                     *(item["checkpoint"] for item in epoch_active_frontier(epoch).values())))


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
        verify_frozen_soup(run_dir, soup)
        if soup.get("previous"):
            older = soup["previous"] if isinstance(soup["previous"], list) else [soup["previous"]]
            for old in older:
                previous = run_dir / old["filename"]
                if (previous.parent != run_dir / "soups" or previous.is_symlink() or
                        not previous.is_file() or digest_file(previous) != old["sha256"]):
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
    protected = pinned(receipt.get("capability_best", {}),
                       school["current_student"], school["champions"])
    protected |= pinned(receipt.get("graduation_perfect", {}),
                        school["current_student"], school["champions"])
    if historical_pending:
        protected |= pinned(historical_pending,
                            school["current_student"], school["champions"])
    for item in receipt.get("historical_grade_champions", {}).values():
        protected |= pinned({}, item, {})
    if receipt.get('curriculum_parent'):
        sources.append(receipt['curriculum_parent'])
        protected |= pinned({}, receipt['curriculum_parent'], {})
    for peak in receipt.get("whole_student_peaks", ()):
        if peak.get("schema") != "bilqis.mlx.whole-student-retention/v1":
            raise ValueError("WHOLE_STUDENT_PEAK_SCHEMA_DRIFT")
        source = peak["checkpoint"]
        sources.append(source)
        protected |= pinned({}, source, {})
    for source in _mentor_epoch_references(receipt):
        sources.append(source)
        protected |= pinned({}, source, {})
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
    _verify_frozen_soup_custody(run_dir, receipt)


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


def _reconcile_vocabulary_metadata(run_dir, receipt, course, parameters,
                                   optimizer, graph):
    """Repair historical stale size metadata by a NEW immutable generation.

    A bound checkpoint's source-verified graph and embedding tensor, not the
    initial inherited model config, own the current active vocabulary size.
    Historical 222-token prefix evidence and previously saved states survive.
    """
    actual = len(graph["tokens"])
    embedded = int(parameters["embedding.weight"].shape[0])
    if actual != embedded or actual < 1:
        raise ValueError("HUMAN_TRAINER_CURRENT_VOCAB_GRAPH_EMBEDDING_DRIFT")
    native = receipt["config"].get("answer_heads", {}).get("semantic_token")
    if native is not None and (
            len(native["token_ids"]) != actual or
            native["token_ids"] != list(range(actual))):
        raise ValueError("HUMAN_TRAINER_CURRENT_VOCAB_ANSWER_HEAD_DRIFT")
    previous = receipt["config"].get("vocab_size")
    if previous == actual:
        return receipt
    if type(previous) is not int or previous < 1 or previous > actual:
        raise ValueError("HUMAN_TRAINER_UNVERIFIED_VOCAB_METADATA_MIGRATION")
    school = _state_from_json(receipt["school"], course)
    if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
        raise ValueError("HUMAN_TRAINER_VOCAB_RECONCILE_OWN_ADAMW_DRIFT")
    candidate = _advance(
        run_dir, {**receipt, "config": {**receipt["config"], "vocab_size": actual}},
        school, persist=False)
    event = {"event": "SCHOOL_CURRENT_VOCAB_METADATA_RECONCILED",
             "generation": candidate["generation"],
             "former_metadata_vocab_size": previous,
             "active_semantic_graph_vocab_size": actual,
             "student_sha256": school.current_student.sha256,
             "optimizer_step": school.current_student.optimizer_step,
             "model_and_optimizer_unchanged": True}
    result = _persist(run_dir, _with_delivery_outbox(candidate, (event,)))
    _reconcile_delivery_outbox(run_dir, result)
    return result


def _reconcile_learning_settings(run_dir, receipt, course, settings, optimizer):
    """Permit only narrower existing retention budgets on human resume.

    Previously selected strategy outcomes keep their historic settings. The
    full student and its AdamW are unchanged by this metadata-only boundary.
    An attempted loosening or an unreviewed probe redesign still fails closed.
    """
    inherited = receipt.get("learning_experiment")
    if inherited is None:
        return receipt
    if settings is None or inherited.get("version") != LEARNING_EXPERIMENT_VERSION:
        raise ValueError("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN")
    new = asdict(settings)
    previous = inherited.get("settings")
    if previous == new:
        return receipt
    if not isinstance(previous, dict):
        raise ValueError("LEARNING_EXPERIMENT_HISTORY_INVALID")
    old = asdict(LearningSettings(**previous))
    if (new["probe_each"] != old["probe_each"] or
            new["protected_cap_limit"] != old["protected_cap_limit"] or
            new["introduction_extra_loss"] != old["introduction_extra_loss"] or
            new["mature_max_loss"] >= old["mature_max_loss"]):
        raise ValueError("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN")
    school = _state_from_json(receipt["school"], course)
    if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
        raise ValueError("LEARNING_EXPERIMENT_POLICY_OWN_ADAMW_DRIFT")
    prior = list(receipt.get("learning_policy_revisions", ()))
    change = {"from": old, "to": new,
              "from_generation": receipt["generation"],
              "optimizer_step": school.current_student.optimizer_step,
              "student_sha256": school.current_student.sha256}
    candidate = _advance(run_dir, {**receipt,
        "learning_experiment": {"version": LEARNING_EXPERIMENT_VERSION,
                                "settings": new},
        "learning_policy_revisions": [*prior, change]}, school, persist=False)
    event = {"event": "SCHOOL_EXPERIMENTAL_RETENTION_POLICY_TIGHTENED",
             "generation": candidate["generation"], **change,
             "model_and_optimizer_unchanged": True}
    result = _persist(run_dir, _with_delivery_outbox(candidate, (event,)))
    _reconcile_delivery_outbox(run_dir, result)
    return result


def _seed_saved_whole_student_peak(run_dir, receipt, course, optimizer):
    """Protect the already saved live exam before the next neural visit.

    Only an exam belonging to the current, fully durable checkpoint qualifies.
    Earlier rubric scores, orphan bundles and mismatched AdamW cannot seed it.
    """
    if receipt.get("whole_student_peaks"):
        return receipt
    school = _state_from_json(receipt["school"], course)
    checkpoint = asdict(school.current_student)
    prior = receipt.get("last_exam") or {}
    if (not prior.get("scores") or
            prior.get("student_sha256") != checkpoint["sha256"] or
            prior.get("optimizer_step") != checkpoint["optimizer_step"]):
        return receipt
    if int(optimizer.state["step"].item()) != checkpoint["optimizer_step"]:
        raise ValueError("WHOLE_STUDENT_PEAK_SEED_ADAMW_DRIFT")
    peaks, outcome = advance_peaks(
        [], curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=prior["exam_rubric_sha256"],
        cohort_sha256=prior["cohort_sha256"],
        assessment_scope_sha256=prior["assessment_scope_sha256"],
        scores=prior["scores"], checkpoint=checkpoint)
    candidate = _advance(run_dir, {**receipt, "whole_student_peaks": peaks},
                         school, persist=False)
    event = {"event": "SCHOOL_EXISTING_WHOLE_STUDENT_PEAK_PRESERVED",
             "generation": candidate["generation"],
             "optimizer_step": checkpoint["optimizer_step"],
             "student_sha256": checkpoint["sha256"],
             "exam_correct": outcome["best_correct"],
             "exam_total": outcome["best_total"],
             "source_cohort_sha256": prior["cohort_sha256"],
             "model_and_optimizer_unchanged": True}
    result = _persist(run_dir, _with_delivery_outbox(candidate, (event,)))
    _reconcile_delivery_outbox(run_dir, result)
    return result


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
    """Draw a fresh routine school-evaluation cohort at every exam boundary.

    Routine MAIN/RECOVERY evaluation is deliberately distinct from any
    promotion/graduation qualification attempt. Persisting a prior
    qualification_cohort must never freeze ordinary school evaluation.
    """
    school = _state_from_json(receipt["school"], course)
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(
        receipt,
        capability=f"ROUTINE_GRADE_EVAL:{school.grade}:{school.grade_exam_epoch}",
    )
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(
        rows, generator_version=generator, seed=seed, rubric_version=release)
    cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort, {"policy": ROUTINE_EVAL_LIFECYCLE,
                    "assessment_grade": school.grade,
                    "grade_exam_epoch": school.grade_exam_epoch,
                    "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                    "cohort_seed": cohort.seed}


def _promotion_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Materialize one distinct promotion-attempt cohort.

    The attempt is deterministic and crash-retry safe within the same durable
    generation, but a later promotion attempt receives a new seed and cohort.
    """
    school = _state_from_json(receipt["school"], course)
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(
        receipt,
        capability=f"PROMOTION_ATTEMPT:{school.grade}:{school.grade_exam_epoch}",
    )
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(
        rows, generator_version=generator, seed=seed, rubric_version=release)
    cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort, {"policy": PROMOTION_ATTEMPT_LIFECYCLE,
                    "assessment_grade": school.grade,
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
    """Activate only already introduced concepts from this generated cohort."""
    eligible = set(assessment_capabilities(course, school))
    rows = tuple(row for row in cohort.rows if row["capability"] in eligible)
    selected = cohort if rows == cohort.rows else make_cohort(rows,
        generator_version=cohort.generator_version, seed=cohort.seed,
        rubric_version=cohort.rubric_version)
    return selected, _persist_live_cohort(run_dir, manifest, course, selected)


def _without_stagnant_capabilities(run_dir, manifest, course, cohort,
                                   control):
    """Remove current-session containment debt from ordinary evaluation only."""
    blocked = set(quarantined_capabilities(control))
    if not blocked:
        return cohort, _persist_live_cohort(run_dir, manifest, course, cohort)
    rows = tuple(row for row in cohort.rows if row["capability"] not in blocked)
    _require_active_stagnation_scope(rows)
    selected = make_cohort(
        rows, generator_version=cohort.generator_version, seed=cohort.seed,
        rubric_version=cohort.rubric_version)
    return selected, _persist_live_cohort(run_dir, manifest, course, selected)


def _require_active_stagnation_scope(scope) -> None:
    if not scope:
        raise ValueError("STAGNATION_ROUTINE_EVALUATION_HAS_NO_ACTIVE_CAPABILITIES")


def _rehabilitate_sole_grade_debt(
        course, school, stagnation, debt, *, generation):
    """Keep training when containment debt is the only work left in one grade."""
    if (stagnation is None or school.stage != "DEFERRED_STAGNATION" or
            not debt):
        return stagnation, school, ()
    grades = {capability.partition(".")[0] for capability in debt}
    if len(grades) != 1:
        return stagnation, school, ()
    stagnation, event = activate_sole_grade_rehabilitation(
        stagnation, capabilities=tuple(debt), generation=generation)
    school = reactivate_stagnation_debt(course, school, tuple(debt))
    return stagnation, school, (event,)


def _advance_stagnation_after_routine(
        *, course, school, routine_assessment, routine_advanced,
        stagnation, blocked_before, active_scope, routine_measured,
        routine_warnings, generation, quarantine_suppressed=()):
    """Apply one completed routine boundary to the current session containment."""
    events = ()
    if stagnation is None:
        return stagnation, events, routine_advanced, ()
    if (school.stage == "ASSESS_MAIN" and
            routine_advanced.stage == "RECOVERY_1"):
        stagnation = begin_recovery_cycle(
            stagnation, first_recovery=routine_advanced.first_recovery)
    elif school.stage == "ASSESS_RECOVERY_2":
        tail = weakest_three(routine_assessment.scores, active_scope)
        stagnation, events = complete_recovery_cycle(
            stagnation, weakest_tail=tail,
            scores=routine_measured["scores"],
            generation=generation,
            active_warnings=tuple(routine_warnings.get("active_warnings", ())),
            quarantine_suppressed=tuple(quarantine_suppressed))
        blocked_after = quarantined_capabilities(stagnation)
        if set(blocked_after) != set(blocked_before):
            retained_scores = {
                cap: score for cap, score in routine_assessment.scores.items()
                if cap not in set(blocked_after)}
            if not retained_scores:
                routine_advanced = replace(
                    school, stage="DEFERRED_STAGNATION", queue=(),
                    first_recovery=(),
                    latest_rubric_digest=routine_assessment.rubric_digest)
            else:
                reduced = Assessment(
                    checkpoint_sha256=routine_assessment.checkpoint_sha256,
                    optimizer_step=routine_assessment.optimizer_step,
                    course_digest=routine_assessment.course_digest,
                    rubric_digest=routine_assessment.rubric_digest,
                    scores=retained_scores,
                    evaluation_id=routine_assessment.evaluation_id +
                                  "/post-stagnation-filter")
                routine_advanced = assess_withheld(
                    course, school, reduced, blocked_after)
    if routine_advanced.stage == "DEFERRED_STAGNATION":
        stagnation, routine_advanced, rehabilitation_events = (
            _rehabilitate_sole_grade_debt(
                course, routine_advanced, stagnation,
                quarantined_capabilities(stagnation),
                generation=generation))
        events = (*events, *rehabilitation_events)
    return (
        stagnation, events, routine_advanced,
        quarantined_capabilities(stagnation))


def _learning_probe_rows(source_root, graph, receipt, course, school, capability,
                         settings):
    """Complete admitted target grade plus bounded cross-grade protection."""
    eligible = set(assessment_capabilities(course, school)) | {capability}
    scores = (receipt.get("last_exam") or {}).get("scores") or {}
    from .learning_experiment import whole_grade_protection
    selected = whole_grade_protection(
        eligible, capability, scores,
        cap_limit=settings.protected_cap_limit, rotation=school.visits)
    sampled = selected | {capability}
    # The target must show a positive change before a candidate is promoted.
    # A six-item panel is too coarse near mastery. Draw enough *fresh* source
    # questions to match the fixed examination's capability sample size,
    # capped at the existing maximum; keep protected probes inexpensive.
    exam_target_size = scores.get(capability, {}).get("total")
    target_each = (
        max(settings.probe_each, min(48, exam_target_size))
        if type(exam_target_size) is int and exam_target_size > 0
        else min(48, max(settings.probe_each, settings.probe_each * 2))
    )
    rows = []
    for name in sorted(sampled):
        rows.extend(_draw_live_rows(
            source_root, graph, course=course, capability=name,
            each=(target_each if name.partition(".")[0] ==
                  capability.partition(".")[0] else settings.probe_each),
            seed=_seed(receipt, capability="LEARNING_PROBE:"+name)))
    if {r["capability"] for r in rows} != sampled:
        raise ValueError("LEARNING_EXPERIMENT_PROBE_SCOPE_INCOMPLETE")
    return rows, selected, len(eligible)-len(sampled)


def _fixed_same_grade_rows(run_dir, receipt, course, school, capability, settings):
    """Reuse the last independently scored full-grade cohort, if available.

    No new test rows are generated here. The persisted cohort, rubric and
    content hash must all verify before the parent/challenger screen can
    claim a fixed-exam grade comparison.
    """
    own_grade = capability.partition(".")[0]
    exam = receipt.get("last_exam") or {}
    if (exam.get("assessment_grade") != own_grade or
            exam.get("grade_exam_epoch") != school.grade_exam_epoch):
        return ()
    required = {cap for cap in assessment_capabilities(course, school)
                if cap.partition(".")[0] == own_grade}
    exam_scores = exam.get("scores") or {}
    if not required <= set(exam_scores):
        return ()
    cohort = _verify_saved_cohort(run_dir, receipt, course)
    if cohort is None:
        raise ValueError("LEARNING_EXPERIMENT_FIXED_GRADE_COHORT_MISSING")
    rows = tuple(r for r in cohort.rows if r["capability"] in required)
    if (len(rows) != len({r["id"] for r in rows}) or
            len(rows) > len(required) * 48 or
            any(type(exam_scores[cap].get("total")) is not int or
                exam_scores[cap]["total"] < 1 or
                sum(row["capability"] == cap for row in rows) !=
                exam_scores[cap]["total"] for cap in required)):
        raise ValueError("LEARNING_EXPERIMENT_FIXED_GRADE_COHORT_INCOMPLETE")
    return rows


def _reusable_exam_identity(receipt, school, *, rubric_sha256,
                            assessment_scope_sha256):
    """Return the exact already-scored exam identity for an unchanged student."""
    exam = receipt.get("last_exam") or {}
    student = school.current_student
    if (exam.get("assessment_grade") != school.grade or
            exam.get("grade_exam_epoch") != school.grade_exam_epoch or
            exam.get("student_sha256") != student.sha256 or
            exam.get("optimizer_step") != student.optimizer_step or
            exam.get("exam_rubric_sha256") != rubric_sha256 or
            exam.get("assessment_scope_sha256") != assessment_scope_sha256):
        return None
    cohort_sha = exam.get("cohort_sha256")
    if (not isinstance(cohort_sha, str) or len(cohort_sha) != 64 or
            any(c not in "0123456789abcdef" for c in cohort_sha)):
        raise ValueError("HUMAN_TRAINER_REUSABLE_EXAM_COHORT_IDENTITY_INVALID")
    return (student.sha256, student.optimizer_step, cohort_sha,
            rubric_sha256, assessment_scope_sha256)


def _candidate_fixed_evidence(mx, run_dir, receipt, course, school, capability,
                              parent, candidate, settings):
    """Score only the fixed evidence needed after fresh grade gain is proven."""
    config, answer_ids = receipt["config"], receipt["answer_ids"]
    fixed = {"status": "NOT_MEASURED",
             "reason": "NO_COMPARABLE_COMPLETE_GRADE_EXAM"}
    frontier = {"status": "NOT_MEASURED",
                "reason": "NO_FIXED_WHOLE_SCHOOL_FRONTIER"}
    frontier_parent = frontier_candidate = {}
    from .fixed_frontier import load_frontier, screen_frontier
    frontier_rows, frontier_parent = load_frontier(
        run_dir, receipt,
        parent_sha256=school.current_student.sha256,
        parent_optimizer_step=school.current_student.optimizer_step)
    if frontier_rows:
        grade = capability.partition(".")[0]
        grade_rows = tuple(
            row for row in frontier_rows
            if row["capability"].partition(".")[0] == grade)
        if grade_rows:
            grade_parent = {
                row["id"]: frontier_parent[row["id"]] for row in grade_rows}
            grade_candidate = _predictions(
                mx, candidate, list(grade_rows), config, answer_ids)
            grade_scores = paired_outcomes(
                grade_rows, grade_parent, grade_candidate)
            fixed = {
                "status": "MEASURED", "grade": grade,
                "cohort_sha256": receipt["last_exam"]["cohort_sha256"],
                "before": sum(value["before"] for value in grade_scores.values()),
                "after": sum(value["after"] for value in grade_scores.values()),
                "total": sum(value["total"] for value in grade_scores.values()),
            }
            frontier_candidate = dict(grade_candidate)
        else:
            fixed = {
                "status": "NOT_MEASURED",
                "reason": "ACTIVE_GRADE_ABSENT_FROM_FIXED_FRONTIER",
            }
        other_rows = tuple(
            row for row in frontier_rows if row not in grade_rows)
        if other_rows:
            frontier_candidate.update(_predictions(
                mx, candidate, list(other_rows), config, answer_ids))
        frontier = screen_frontier(
            frontier_rows, frontier_parent, frontier_candidate,
            receipt["last_exam"]["cohort_sha256"])
    else:
        fixed_rows = _fixed_same_grade_rows(
            run_dir, receipt, course, school, capability, settings)
        if fixed_rows:
            parent_fixed = _predictions(
                mx, parent, list(fixed_rows), config, answer_ids)
            candidate_fixed = _predictions(
                mx, candidate, list(fixed_rows), config, answer_ids)
            scores = paired_outcomes(
                fixed_rows, parent_fixed, candidate_fixed)
            fixed = {
                "status": "MEASURED",
                "grade": capability.partition(".")[0],
                "cohort_sha256": receipt["last_exam"]["cohort_sha256"],
                "before": sum(value["before"] for value in scores.values()),
                "after": sum(value["after"] for value in scores.values()),
                "total": sum(value["total"] for value in scores.values()),
            }

    from .fragile_replay import load_replay_rows, screen_replay
    replay_rows = load_replay_rows(run_dir, receipt)
    replay = {"status": "NOT_MEASURED",
              "reason": "B_OR_XOR_EXAM_NOT_YET_ADMITTED"}
    if replay_rows:
        ids = {row["id"] for row in replay_rows}
        replay_parent = (
            {rid: frontier_parent[rid] for rid in ids}
            if ids <= frontier_parent.keys() else
            _predictions(mx, parent, list(replay_rows), config, answer_ids))
        replay_candidate = (
            {rid: frontier_candidate[rid] for rid in ids}
            if ids <= frontier_candidate.keys() else
            _predictions(mx, candidate, list(replay_rows), config, answer_ids))
        replay = screen_replay(
            replay_rows, replay_parent, replay_candidate,
            receipt["last_exam"]["cohort_sha256"])
    return fixed, replay, frontier


def _candidate_grade_evidence(mx, run_dir, receipt, course, school, capability,
                              parent, candidate, probe_rows, target_parent,
                              settings):
    """Complete missing candidate scores only after a target gain is observed.

    Parent/candidate predictions are never reused across candidate weights,
    AdamW steps, source questions or source-cohort identities. A target failure
    is conclusive rejection without running redundant peer and exam inference.
    """
    config, answer_ids = receipt["config"], receipt["answer_ids"]
    target_rows = [row for row in probe_rows if row["capability"] == capability]
    target_candidate = _predictions(mx, candidate, target_rows, config, answer_ids)
    target_pair = paired_outcomes(target_rows, target_parent, target_candidate)
    required = tuple(sorted(
        name for name in assessment_capabilities(course, school)
        if name.partition(".")[0] == capability.partition(".")[0]))
    if target_pair[capability]["after"] <= target_pair[capability]["before"]:
        return (target_pair, set(), (capability,), {
            "status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            {"status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            {"status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            "TARGET_ONLY_REJECTED")

    # This checkpoint has already been evaluated on its target. Score only
    # missing grade peers and independently selected cross-grade sentinels.
    missing = missing_grade_capabilities(required, target_pair)
    remaining = [row for row in probe_rows
                 if row["capability"] in missing or
                 row["capability"].partition(".")[0] != capability.partition(".")[0]]
    parent_scores = {**target_parent}
    candidate_scores = {**target_candidate}
    if remaining:
        parent_scores.update(_predictions(mx, parent, remaining, config, answer_ids))
        candidate_scores.update(_predictions(
            mx, candidate, remaining, config, answer_ids))
    pair = paired_outcomes(probe_rows, parent_scores, candidate_scores)
    if missing_grade_capabilities(required, pair):
        raise ValueError("LEARNING_EXPERIMENT_INCOMPLETE_SAME_GRADE_PROMOTION")
    protected = set(pair)-set(required)
    protected.update(name for name in required if name != capability)
    grade_net = sum(pair[name]["after"]-pair[name]["before"] for name in required)
    if grade_net < 0:
        return (pair, protected, required,
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                "GRADE_NET_REJECTED")

    fixed, replay, frontier = _candidate_fixed_evidence(
        mx, run_dir, receipt, course, school, capability, parent, candidate,
        settings)
    return (pair, protected, required, fixed, replay, frontier,
            "COMPLETE_SAME_GRADE")


def _fresh_fragile_preservation_rows(run_dir, source_root, graph, receipt,
                                     course, school, capability, *, step,
                                     batch_size, fixed_rows=None):
    """Generate fresh semantic siblings for the fixed B.OR/B.XOR safety rows.

    Rehearsal is active only after a source-verified B replay exam exists.
    The fixed examination rows themselves are never delivered to the optimizer.
    """
    from .fragile_replay import (
        CAPABILITIES, load_replay_rows, select_preservation_rows,
        select_structural_preservation_rows,
    )
    fixed = (tuple(fixed_rows) if fixed_rows is not None
             else load_replay_rows(run_dir, receipt))
    if not fixed:
        return ()
    admitted = set(assessment_capabilities(course, school))
    requested = tuple(name for name in CAPABILITIES if name in admitted)
    if not requested:
        return ()
    excluded = {row["id"] for row in fixed}
    selected = []
    for name in requested:
        fixed_capability = tuple(
            row for row in fixed if row["capability"] == name)
        fresh = []
        matched = ()
        for attempt in range(3):
            fresh.extend(_draw_live_rows(
                source_root, graph,
                seed=_seed(
                    receipt,
                    capability=f"FRAGILE_PRESERVE:{name}:{attempt}",
                    step=step),
                capability=name, each=max(96, batch_size * 3), course=course))
            matched = select_structural_preservation_rows(
                fresh, fixed_capability, excluded_ids=excluded,
                rotation=max(0, step - 1) * 4, limit=4)
            if len(matched) >= 4:
                break
        delivered = list(matched)
        if len(delivered) < 4:
            try:
                fallback = select_preservation_rows(
                    fresh, capabilities=(name,), excluded_ids=excluded)
            except ValueError as exc:
                if str(exc) != "FRAGILE_PRESERVATION_INCOMPLETE_TRUTH_TABLE":
                    raise
                fallback = ()
            used = {row["id"] for row in delivered}
            for row in fallback:
                if row["id"] not in used:
                    delivered.append(row)
                    used.add(row["id"])
                if len(delivered) >= 4:
                    break
        selected.extend(delivered[:4])
    if any(row["id"] in excluded for row in selected):
        raise ValueError("FRAGILE_PRESERVATION_EXAM_ROW_LEAK")
    return tuple(selected)


def _inject_preservation_rows(chosen, preservation, *, reserved_ids=()):
    """Reserve optimizer slots for preservation without displacing exam misses."""
    result = list(chosen)
    reserved = set(reserved_ids)
    consumed = {index for index, row in enumerate(result)
                if row.get("id") in reserved}
    delivered = []
    for item in preservation:
        replacement = next((
            index for index, row in enumerate(result)
            if index not in consumed and row.get("gold") == item.get("gold")
        ), None)
        if replacement is None:
            replacement = next((
                index for index in range(len(result)) if index not in consumed
            ), None)
        if replacement is None:
            break
        result[replacement] = item
        consumed.add(replacement)
        delivered.append(item)
    if len(delivered) != len(preservation):
        raise ValueError("FRAGILE_PRESERVATION_BATCH_CAPACITY_EXHAUSTED")
    return result, tuple(delivered)


def _skip_perfect_target_visit(run_dir, receipt, school, course, capability,
                               probe_total, optimizer_step, *, teacher=None):
    """Advance the in-memory schedule without checkpointing a provisional model."""
    skipped_school = visit(course, school, capability, school.current_student)
    result = _advance(run_dir, receipt, skipped_school, teacher=teacher, persist=False)
    event = {
        "event": "SCHOOL_PERFECT_TARGET_VISIT_SKIPPED",
        "capability": capability,
        "grade": capability.partition(".")[0],
        "active_grade": skipped_school.grade,
        "generation": result["generation"],
        "optimizer_step": optimizer_step,
        "target_probe_correct": probe_total,
        "target_probe_total": probe_total,
        "retained_optimizer_updates": 0,
        "reason": "NO_POSSIBLE_STRICT_TARGET_GAIN",
    }
    result["_pending_visit_events"] = [
        *receipt.get("_pending_visit_events", ()), event]
    return result


def _skip_stagnant_target_visit(run_dir, receipt, school, course, capability,
                                optimizer_step):
    """Advance past a current-session quarantined capability without teaching."""
    skipped_school = visit(course, school, capability, school.current_student)
    result = _advance(run_dir, receipt, skipped_school, persist=False)
    event = {
        "event": "SCHOOL_STAGNANT_CAPABILITY_VISIT_SKIPPED",
        "capability": capability,
        "grade": capability.partition(".")[0],
        "active_grade": skipped_school.grade,
        "generation": result["generation"],
        "optimizer_step": optimizer_step,
        "retained_optimizer_updates": 0,
        "teacher_updated": False,
        "reason": "CURRENT_SESSION_STAGNATION_QUARANTINE",
        "required_mastery_debt": True,
    }
    result["_pending_visit_events"] = [
        *receipt.get("_pending_visit_events", ()), event]
    return result


def _take_visit(mx, run_dir, receipt, manifest, course, engine,
                params, optimizer, graph, *, steps_per_visit, batch_size, reserve_gib,
                source_root=None, learning_settings: LearningSettings | None = None):
    school = _state_from_json(receipt["school"], course)
    cap = next_capability(school)
    if cap is None:
        raise ValueError("HUMAN_TRAINER_NO_SCHEDULED_CAPABILITY")
    stage_before = school.stage
    trace_mark(
        "VISIT_START", generation=receipt["generation"], capability=cap,
        phase=stage_before, optimizer_step=int(optimizer.state["step"].item()))
    if cap in set(quarantined_capabilities(receipt.get("stagnation_session"))):
        return _skip_stagnant_target_visit(
            run_dir, receipt, school, course, cap,
            int(optimizer.state["step"].item()))
    introduction_pass = school.stage == "MAIN"
    lesson_grade = cap.split(".", 1)[0]
    if lesson_grade not in {grade.id for grade in course.grades}:
        raise ValueError("HUMAN_TRAINER_UNKNOWN_LESSON_GRADE")
    teacher = json.loads(_canonical(receipt["teacher"]))
    rng = random.Random(_seed(receipt, capability=cap))
    teacher_curriculum_scope = (str(receipt.get("curriculum_mode", "")) + "/" +
                                str(receipt.get("numeric_maximum", "")))
    with trace_span("POLICY_SELECT", capability=cap):
        if learning_settings is not None:
            policy_key, policy = contextual_pick(
                engine, teacher, cap, school.stage, rng,
                curriculum_scope=teacher_curriculum_scope)
        else:
            policy_key, policy = engine.pick(teacher, lesson_grade, rng)
    original_learning_rate = optimizer.learning_rate
    optimizer.learning_rate = float(policy["lr"])
    if source_root is None:
        raise ValueError("HUMAN_TRAINER_LIVE_SOURCE_REQUIRED")
    with trace_span("VISIT_SOURCE_DRAW", capability=cap):
        rows = _draw_live_rows(source_root, graph,
                               seed=_seed(receipt, capability=cap),
                               capability=cap, each=max(32, batch_size), course=course)
    # Champion influence across grades belongs exclusively to frozen soups.
    # Individual capability champions advise only their own lesson grade.
    with trace_span("MENTOR_SOURCES_LOAD", capability=cap):
        confidence_champions, frozen_soups, soup_vote_receipts = _mentor_sources_for_visit(
            run_dir, receipt, lesson_grade, graph, len(course.grades))
    confidence_examples = 0
    confidence_total_weight = 0.0
    confidence_applied_steps = 0
    # Every unsuccessful examination construction can become direct teaching
    # material once scoring has completed. No held-out embargo survives.
    priority = [r for r in receipt.get("teacher_misses", ())
                if r["capability"] == cap]
    deferred_misses = []
    if receipt.get('curriculum_mode') == STAIRCASE_RELEASE:
        from .numeric_staircase import row_in_scope
        deferred_misses = [r for r in priority if not row_in_scope(r, receipt['numeric_maximum'])]
        priority = [r for r in priority if row_in_scope(r, receipt['numeric_maximum'])]
    miss_exposures = dict(receipt.get("teacher_miss_exposures", {}))
    if any(type(count) is not int or count < 0 for count in miss_exposures.values()):
        raise ValueError("HUMAN_TRAINER_MISS_EXPOSURE_STATE_INVALID")
    selected_misses = set()
    rows.extend(priority)
    with trace_span("TRAIN_SCORE_BEFORE", capability=cap, row_count=len(rows)):
        before = _train_score(mx, params, rows, receipt["config"],
                              receipt["answer_ids"])
    parent_parameters, parent_optimizer = params, optimizer
    probe_rows = protected_caps = parent_predictions = None
    if learning_settings is not None:
        with trace_span("RETENTION_PROBE_BUILD", capability=cap):
            probe_rows, protected_caps, unsampled_caps = _learning_probe_rows(
                source_root, graph, receipt, course, school, cap, learning_settings)
        target_rows = [row for row in probe_rows if row["capability"] == cap]
        with trace_span("RETENTION_PARENT_PREDICT", capability=cap,
                        row_count=len(target_rows)):
            parent_predictions = _predictions(
                mx, parent_parameters, target_rows, receipt["config"], receipt["answer_ids"])
        if target_rows and all(parent_predictions[row["id"]] == row["gold"]
                               for row in target_rows):
            # A strict positive-gain gate cannot admit a trial whose fresh
            # target panel already scores perfectly. Preserve any accepted
            # in-memory student updates until their normal checkpoint boundary.
            parent_optimizer.learning_rate = original_learning_rate
            return _skip_perfect_target_visit(
                run_dir, receipt, school, course, cap, len(target_rows),
                int(parent_optimizer.state["step"].item()), teacher=teacher)
        with trace_span("FORK_CANDIDATE", capability=cap):
            params, optimizer = fork_student(mx, parent_parameters, parent_optimizer)
    last_loss = 0.0
    last_norm = 0.0
    methodology_steps = []
    methodology_unavailable = None
    replayed_misses = 0
    policy_control_receipts = []
    step_before = int(optimizer.state["step"].item())
    fragile_fixed_rows = ()
    if learning_settings is not None:
        from .fragile_replay import load_replay_rows
        with trace_span("FRAGILE_REPLAY_LOAD", capability=cap):
            fragile_fixed_rows = load_replay_rows(run_dir, receipt)
    for step in range(steps_per_visit):
        trace_mark("OPTIMIZER_STEP_START", capability=cap, visit_step=step + 1,
                   optimizer_step=int(optimizer.state["step"].item()))
        lesson_control = None
        with trace_span("STEP_SOURCE_DRAW", capability=cap, visit_step=step + 1):
            fresh = _draw_live_rows(source_root, graph,
                seed=_seed(receipt, capability=cap, step=step+1),
                capability=cap, each=max(32, batch_size), course=course)
        fresh.extend(priority)
        lesson_seed = _seed(receipt, capability=cap, step=step+1)
        with trace_span("STEP_LESSON_SELECT", capability=cap, visit_step=step + 1):
            if learning_settings is not None:
                # The same source-bound old-grade policy applies to Boolean and
                # typed lessons. Never label the target's own grade as old.
                old_capabilities = earlier_grade_capabilities(
                    course, school.champions, cap)
                prior = []
                if int(policy.get("old", 0)) > 0 and old_capabilities:
                    selected = old_capabilities[(school.visits + step) % len(old_capabilities)]
                    prior = _draw_live_rows(source_root, graph, course=course,
                        capability=selected, each=max(batch_size, 6),
                        seed=_seed(receipt, capability="EXPERIMENT_OLD:"+selected, step=step))
                picked, control = select_source_lesson(
                    fresh, prior, policy, seed=lesson_seed, batch_size=batch_size)
                lesson_control = {**control, "eligible_prior_capabilities":
                                  len(old_capabilities)}
            else:
                picked = choose_lesson_batch(
                    fresh, policy, lesson_seed, batch_size=batch_size)
        preservation = ()
        delivered_preservation = ()
        if learning_settings is not None:
            with trace_span("STEP_FRAGILE_PRESERVATION", capability=cap,
                            visit_step=step + 1):
                preservation = _fresh_fragile_preservation_rows(
                    run_dir, source_root, graph, receipt, course, school, cap,
                    step=step + 1, batch_size=batch_size,
                    fixed_rows=fragile_fixed_rows)
                picked, delivered_preservation = _inject_preservation_rows(
                    picked, preservation)
        preservation_ids = {row["id"] for row in delivered_preservation}
        gold_capacity = {
            gold: sum(row["gold"] == gold and row.get("id") not in preservation_ids
                      for row in picked)
            for gold in {row["gold"] for row in picked}
        }
        with trace_span("STEP_MISS_REPLAY", capability=cap, visit_step=step + 1,
                        available_misses=len(priority)):
            window = select_fair_miss_window(
                priority, FairMissRequest(
                    exposures=miss_exposures,
                    selected_this_visit=frozenset(selected_misses),
                    remaining_steps=steps_per_visit-step,
                    batch_size=batch_size,
                    gold_capacity=gold_capacity,
                ))
            picked = replay_missed_lessons(
                picked, window, reserved_ids=preservation_ids)
        if lesson_control is not None:
            lesson_control["planned_old_grade_examples"] = lesson_control[
                "effective_old_grade_examples"]
            earlier_grades = {item.partition(".")[0] for item in old_capabilities}
            lesson_control["effective_old_grade_examples"] = sum(
                row["capability"].partition(".")[0] in earlier_grades for row in picked)
            lesson_control["selected_answer_kinds"] = sorted({
                row.get("answer_kind", "binary") for row in picked})
            lesson_control["fragile_preservation_requested"] = len(preservation)
            lesson_control["fragile_preservation_delivered"] = len(
                delivered_preservation)
            lesson_control["fragile_preservation_capabilities"] = sorted({
                row["capability"] for row in delivered_preservation})
            lesson_control["fragile_preservation_patterns"] = sorted({
                row["capability"] + ":" +
                "".join("1" if value else "0" for value in row["operand_truths"])
                for row in delivered_preservation})
            lesson_control["fragile_preservation_source"] = (
                "FRESH_SOURCE_TRUTH_TABLE_SIBLINGS")
            policy_control_receipts.append(lesson_control)
        for row in window:
            identity = row["id"]
            miss_exposures[identity] = miss_exposures.get(identity, 0) + 1
            selected_misses.add(identity)
        replayed_misses += len(window)
        with trace_span("STEP_DIAGNOSTIC_AND_GUIDANCE", capability=cap,
                        visit_step=step + 1):
            if methodology_unavailable is None:
                try:
                    methodology_steps.append(inspect_lesson_step(
                        course, cap, fresh, picked))
                except ValueError as exc:
                    # A diagnostic implementation gap must not invent a new
                    # training gate or silently change the evolved teacher.
                    methodology_unavailable = str(exc)
            typed_lesson = any(row.get("answer_kind", "binary") != "binary" for row in picked)
            if learning_settings is not None and typed_lesson:
                guidance = _typed_confidence_guidance(
                    mx, (*confidence_champions, *frozen_soups), picked, receipt["config"],
                    scope_size=len(course.capability_map),
                    teacher_distill=float(policy.get("distill", 0.0)))
            else:
                guidance = _confidence_guidance(
                    mx, (*confidence_champions, *frozen_soups), picked, receipt["config"],
                    receipt["answer_ids"], scope_size=len(course.capability_map),
                    teacher_distill=float(policy.get("distill", 0.0)))
        if guidance is not None:
            import numpy as np
            influences = ([item[1] for item in guidance.values()]
                          if isinstance(guidance, dict) else [guidance[1]])
            confidence_examples += sum(int(np.count_nonzero(item)) for item in influences)
            confidence_total_weight += sum(float(np.sum(item)) for item in influences)
            confidence_applied_steps += 1
        with trace_span("STEP_TRAIN", capability=cap, visit_step=step + 1,
                        batch_size=len(picked)):
            last_loss, last_norm = _train_step(
                mx, params, optimizer, picked, receipt["config"],
                receipt["answer_ids"], champion_guidance=guidance)
        trace_mark("OPTIMIZER_STEP_END", capability=cap, visit_step=step + 1,
                   optimizer_step=int(optimizer.state["step"].item()))
    with trace_span("TRAIN_SCORE_AFTER", capability=cap, row_count=len(rows)):
        after = _train_score(mx, params, rows, receipt["config"],
                             receipt["answer_ids"])
    attempted_step = int(optimizer.state["step"].item())
    if attempted_step != step_before+steps_per_visit:
        raise ValueError("HUMAN_TRAINER_OPTIMIZER_STEP_DRIFT")
    candidate_gain = after-before
    outcome = context_credit = None
    if learning_settings is not None:
        with trace_span("RETENTION_CANDIDATE_EVIDENCE", capability=cap):
            pair, probed, current_grade, fixed_grade_evidence, replay, frontier, stage = (
                _candidate_grade_evidence(
                    mx, run_dir, receipt, course, school, cap,
                    parent_parameters, params, probe_rows,
                    parent_predictions, learning_settings))
        with trace_span("RETENTION_DECIDE", capability=cap):
            outcome = decide_learning_trial(
                pair, active_capability=cap, phase=school.stage,
                protected=probed, settings=learning_settings,
                same_grade_capabilities=current_grade,
                fixed_grade_replay=fixed_grade_evidence,
                fixed_frontier_replay=frontier,
                active_school_grade=school.grade,
                mature_grades=frozenset(school.champions),
                negative_prototypes=teacher["causal_experiment"]["negative_archetypes"],
                source_cohort_sha256=_fingerprint([
                    (r["id"],r["capability"],r["gold"],r["tokens"]) for r in probe_rows
                    if r["capability"] in pair]),
                fragile_replay=replay)
        outcome["qualification_stage"] = stage
        from .matrix_strain import observe as observe_matrix_strain
        with trace_span("MATRIX_STRAIN", capability=cap):
            outcome["matrix_strain"] = observe_matrix_strain(
                mx, run_dir, receipt, parent_parameters, params)
        outcome["unsampled_admitted_capabilities"] = (
            len(set(assessment_capabilities(course, school)) | {cap})-len(pair))
        with trace_span("RETENTION_APPLY_DECISION", capability=cap,
                        decision=outcome["decision"]):
            context_credit = observe_context(
                teacher, capability=cap, phase=school.stage, policy_key=policy_key,
                decision=outcome, local_gain=candidate_gain,
                curriculum_scope=teacher_curriculum_scope)
            if outcome["decision"] == "PROVISIONAL":
                commit_trial(parent_parameters, parent_optimizer, params, optimizer)
            else:
                # The rejected candidate never owned the causal model, its
                # optimizer or the unresolved miss queue.
                parent_optimizer.learning_rate = original_learning_rate
                miss_exposures = dict(receipt.get("teacher_miss_exposures", {}))
                after = before
        params, optimizer = parent_parameters, parent_optimizer
    remaining_priority = priority
    if priority and (outcome is None or outcome["decision"] == "PROVISIONAL"):
        with trace_span("MISS_RECONCILE", capability=cap, miss_count=len(priority)):
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
    ] + deferred_misses + remaining_priority
    all_teacher_misses.sort(key=lambda row: (row["capability"], row["id"]))
    reward = after - before
    bandit_credit = selection_credit(reward, outcome, context_credit)
    with trace_span("TEACHER_OBSERVE", capability=cap):
        engine.observe(teacher, lesson_grade, policy_key, bandit_credit)
    expected_retained = (step_before if outcome is not None and
                         outcome["decision"] == "REJECT" else attempted_step)
    if int(optimizer.state["step"].item()) != expected_retained:
        raise ValueError("LEARNING_EXPERIMENT_RETAINED_ADAMW_STEP_DRIFT")
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
        champion_candidate_count=0,
        prerequisite_capabilities=course.capability_map[cap].prerequisites,
        methodology=methodology,
        delivered_examples=steps_per_visit*batch_size,
        replayed_misses=replayed_misses,
        resolved_exam_misses=len(resolved_priority_ids),
        champion_prioritized=0,
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
        "teacher_selection_reward": bandit_credit,
        **({"lesson_policy_controls": {
            "optimizer_batches_observed": len(policy_control_receipts),
            "old_grade_examples_delivered": sum(
                r["effective_old_grade_examples"] for r in policy_control_receipts),
            "last_batch_controls": policy_control_receipts[-1]}}
           if policy_control_receipts else {}),
        **({"typed_policy_controls": {
            "optimizer_batches_observed": len(policy_control_receipts),
            "old_grade_examples_delivered": sum(
                r["effective_old_grade_examples"] for r in policy_control_receipts),
            "last_batch_controls": policy_control_receipts[-1]}}
           if policy_control_receipts and any(
               kind != "binary" for r in policy_control_receipts
               for kind in r["selected_answer_kinds"]) else {}),
        **({"candidate_retention": outcome, "context_teacher_credit": context_credit,
            "candidate_source_training_gain": candidate_gain,
            "candidate_attempt_optimizer_step": attempted_step,
            "retained_optimizer_updates": expected_retained-step_before}
           if outcome is not None else {}),
        "generator_version": lesson_contract(course, lesson_grade)[2],
        "generator_code_sha256": lesson_contract(course, lesson_grade)[3],
        "lesson_source_sha256": manifest["manifest_sha256"],
        "lesson_seed": _seed(receipt, capability=cap),
        "prior_exam_misses_available": len(priority),
        "prior_exam_misses_deferred_by_scope": len(deferred_misses),
        "prior_exam_misses_remaining": len(remaining_priority),
        "prior_grade_champion_votes": {},
        "champion_directed_examples_available": 0,
        "champion_confidence": {
            "policy": CHAMPION_CONFIDENCE_POLICY,
            "frozen_unique_champions": len(confidence_champions),
            "frozen_grade_soups": list(soup_vote_receipts),
            "teacher_distill": float(policy.get("distill", 0.0)),
            "examples_with_gold_agreeing_advice": confidence_examples,
            "total_per_row_influence": round(confidence_total_weight, 8),
            "guided_optimizer_steps": confidence_applied_steps,
        },
        "lesson_methodology": methodology,
        "teacher_decision": teacher_decision,
        "optimizer_step": int(optimizer.state["step"].item()),
        "next_phase": school.stage,
        "checkpoint_status": "PROVISIONAL_UNTIL_NEXT_RECOVERY_BOUNDARY",
        "unavailable_teacher_dimensions": (
            (["old"] if not any(r["eligible_prior_capabilities"]
                                  for r in policy_control_receipts) else []) +
            ["preview"] + ([] if confidence_applied_steps else ["distill"])),
    }
    stagnation = receipt.get("stagnation_session")
    if stagnation is not None:
        retained_updates = (
            expected_retained - step_before if outcome is not None
            else attempted_step - step_before)
        stagnation = record_stagnation_visit(
            stagnation, capability=cap, phase=stage_before,
            decision=outcome.get("decision") if isinstance(outcome, dict) else None,
            retained_optimizer_updates=retained_updates,
            generation=event["generation"])
    pending = list(receipt.get("_pending_visit_events", ()))
    pending.append(event)
    with trace_span("VISIT_ADVANCE_STATE", capability=cap):
        result = _advance(run_dir, receipt, school, teacher=teacher, persist=False)
    if learning_settings is not None:
        result["learning_experiment"] = {
            "version": LEARNING_EXPERIMENT_VERSION,
            "settings": asdict(learning_settings),
        }
    result["teacher_misses"] = all_teacher_misses
    result["teacher_miss_exposures"] = miss_exposures
    if stagnation is not None:
        result["stagnation_session"] = stagnation
    result.pop("teacher_miss_cursor", None)
    result["_pending_visit_events"] = pending
    trace_mark(
        "VISIT_END", generation=result["generation"], capability=cap,
        optimizer_step=int(optimizer.state["step"].item()),
        decision=outcome.get("decision") if isinstance(outcome, dict) else None)
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


def _score_parent_for_paired_s3(mx, run_dir, receipt, parent, cohort, graph,
                                current_scores):
    """Read-only parent inference on this fresh cohort for S3 comparability."""
    path = run_dir / parent.filename
    try:
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not parent.filename.startswith("bundles/")):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_UNSAFE_PARENT")
        weights, own_adamw, meta, loaded_graph = load_semantically_bound_bundle(path)
        if (meta["safetensors_sha256"] != parent.sha256 or
                meta["optimizer_step"] != parent.optimizer_step or
                loaded_graph != graph):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_PARENT_DRIFT")
        del own_adamw
        predictions = _predictions(
            mx, weights, tuple(cohort.rows), receipt["config"],
            receipt["answer_ids"])
        measured = score_cohort(cohort, predictions, asdict(parent))["scores"]
        del weights
        if set(measured) != set(current_scores):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_SCOPE_DRIFT")
        return measured, None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, str(exc)


def _epoch_paired_examinations(mx, run_dir, receipt, course, school,
                               cohort, scores, graph):
    """Re-examine only potentially displaced epoch incumbents on these rows."""
    epoch = receipt["mentor_epoch"]
    if epoch["source_graph_sha256"] != _fingerprint(graph):
        raise ValueError("CHAMPIONSHIP_EPOCH_SOURCE_GRAPH_DRIFT")
    grades = {grade.id: tuple(cap.id for cap in grade.capabilities)
              for grade in course.grades}
    scope = assessment_capabilities(course, school)
    if set(scores) != set(scope):
        raise ValueError("CHAMPIONSHIP_EPOCH_INCOMPLETE_EXAM")
    rubric, _, _, _ = _cohort_contract(course)
    context = {
        "cohort_sha256": cohort.digest,
        "rubric_sha256": rubric,
        "assessment_scope_sha256": _fingerprint(scope),
        "source_graph_sha256": _fingerprint(graph),
        "source_oracle_sha256": receipt["source_manifest_sha256"],
    }
    challenger = {**context, "checkpoint": asdict(school.current_student),
                  "scores": scores}
    requested = epoch_needed_incumbents(
        epoch, grades=grades, challenger_exam=challenger)
    incumbents = {}
    for sha, pointer in sorted(requested.items()):
        if sha == school.current_student.sha256:
            incumbents[sha] = challenger
            continue
        path = run_dir / pointer["filename"]
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not pointer["filename"].startswith("bundles/")):
            raise ValueError("CHAMPIONSHIP_EPOCH_UNSAFE_INCUMBENT")
        weights, own_adamw, meta, loaded_graph = load_semantically_bound_bundle(path)
        if (meta["safetensors_sha256"] != sha or
                meta["optimizer_step"] != pointer["optimizer_step"] or
                loaded_graph != graph):
            raise ValueError("CHAMPIONSHIP_EPOCH_INCOMPARABLE_INCUMBENT_GRAPH")
        del own_adamw
        predictions = _predictions(
            mx, weights, tuple(cohort.rows), receipt["config"],
            receipt["answer_ids"])
        measured = score_cohort(cohort, predictions, pointer)
        if set(measured["scores"]) != set(scope):
            raise ValueError("CHAMPIONSHIP_EPOCH_INCUMBENT_INCOMPLETE")
        incumbents[sha] = {**context, "checkpoint": dict(pointer),
                           "scores": measured["scores"]}
        del weights
    return grades, challenger, incumbents


def _commit_scored_student(mx, run_dir, receipt, manifest, course, school,
                           cohort, predictions, parameters, optimizer, graph, *,
                           reserve_gib, allowed_capabilities=None):
    """Only evaluated best scores mint permanent capability candidates.

    If none improve, the single live student still needs a replaceable
    recovery point. This is NOT a champion or an additional archive slot.
    """
    rubric, cohort_release, _, _ = _cohort_contract(course)
    full_allowed = set(assessment_capabilities(course, school))
    allowed = (set(allowed_capabilities) if allowed_capabilities is not None
               else set(full_allowed))
    if not allowed or not allowed <= full_allowed:
        raise ValueError("HUMAN_TRAINER_PARTIAL_EVALUATION_SCOPE_DRIFT")
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
    complete_scope = allowed == full_allowed
    if complete_scope:
        replay_receipt = {**receipt, "live_rubric_sha256": rubric}
        frontier, incumbent_comparisons = _compare_incumbents(
            mx, run_dir, replay_receipt, cohort, receipt["config"],
            receipt["answer_ids"], graph)
        roles = candidate_roles(frontier, grades, rubric)
    else:
        # A quarantined capability remains mandatory graduation debt. Partial
        # ordinary scoring protects the causal student but cannot mint or move
        # championship authority from an incomplete capability inventory.
        frontier = dict(receipt.get("capability_best", {}))
        incumbent_comparisons = []
        roles = ()
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
        # A freshly enrolled numeric staircase intentionally has no prior
        # grade examination. A stop-boundary candidate comparison is valid.
        active_soups = (record["mentor_epoch"].get("active_grade_soups", {})
                        if record.get("mentor_epoch") is not None
                        else record.get("grade_soups", {}))
        for grade in (record.get("last_exam") or {}).get("grade_soups_refreshed", ()):
            snapshot = active_soups[grade]
            for shard in soup_shards(snapshot):
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
                if snapshot.get("schema") == PARTITIONED_SCHEMA:
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
    if record.get('curriculum_parent'):
        retained |= pinned({}, record['curriculum_parent'], {})
    for peak in record.get("whole_student_peaks", ()):
        retained |= pinned({}, peak["checkpoint"], {})
    for source in _mentor_epoch_references(record):
        retained |= pinned({}, source, {})
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
    # The old frozen recipes are unique experiment evidence, not debris.
    # Do not delete either historical or new-epoch soup bytes from this fork.
    retired_soups = (retire_stale_soups(run_dir, record.get("grade_soups", {}))
                     if record.get("mentor_epoch") is None else ())
    if retired_soups:
        _record(run_dir, {"event": "SCHOOL_OLD_GRADE_SOUPS_RETIRED",
                          "generation": record["generation"],
                          "grade": active_grade, "count": len(retired_soups)})


def _quarantine_newer_uncommitted_bundles(run_dir: Path, retained: set[str],
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


def _resume_command(run_dir: Path, source_root: Path,
                    learning_settings: LearningSettings | None) -> str:
    """Only name non-default options in the next human-owned shell command."""
    from .paths import LEGACY_SOURCE, active_run_dir

    command = "npm run train -- --human-run --resume"
    if learning_settings is None:
        command += " --no-retention"
    elif learning_settings != LearningSettings():
        command += (
            " --retention-probe-each " + str(learning_settings.probe_each) +
            " --retention-mature-max-loss " + str(learning_settings.mature_max_loss) +
            " --retention-introduction-extra-loss " +
                str(learning_settings.introduction_extra_loss) +
            " --retention-protected-cap-limit " +
                str(learning_settings.protected_cap_limit))
    if learning_settings is None or Path(run_dir).resolve() != active_run_dir().resolve():
        command += " --run-dir " + shlex.quote(str(run_dir))
    if Path(source_root).resolve() != LEGACY_SOURCE.resolve():
        command += " --legacy-code-root " + shlex.quote(str(source_root))
    return command


def _verified_reusable_exam(run_dir, receipt, course, school, optimizer, graph,
                            cohort, *, rubric_sha256, assessment_scope_sha256):
    """Validate one prior exam for scheduler reuse without neural inference.

    Reuse is legal only when the retained checkpoint, native AdamW step and
    complete fixed examination identity are unchanged and every pending visit
    retained zero optimizer updates. Saved wrong answers reconstruct the exact
    prior prediction map so scores and teacher misses can be revalidated.
    """
    identity = _reusable_exam_identity(
        receipt, school, rubric_sha256=rubric_sha256,
        assessment_scope_sha256=assessment_scope_sha256)
    if identity is None:
        return None
    live_step = int(optimizer.state["step"].item())
    if live_step != school.current_student.optimizer_step:
        return None
    pending = tuple(receipt.get("_pending_visit_events", ()))
    if any(event.get("retained_optimizer_updates", 0) != 0 for event in pending):
        return None
    recorded_graph = receipt.get("semantic_graph_sha256")
    if recorded_graph is not None and recorded_graph != _fingerprint(graph):
        raise ValueError("HUMAN_TRAINER_REUSABLE_EXAM_GRAPH_DRIFT")
    if cohort.digest != identity[2]:
        raise ValueError("HUMAN_TRAINER_REUSABLE_EXAM_COHORT_DRIFT")
    prior = receipt["last_exam"]
    by_id = {row["id"]: row for row in cohort.rows}
    guesses = {identity: row["gold"] for identity, row in by_id.items()}
    misses = list(prior.get("misses_for_teacher") or ())
    for miss in misses:
        row = by_id.get(miss.get("id"))
        if (row is None or miss.get("capability") != row["capability"] or
                miss.get("gold") != row["gold"] or
                miss.get("predicted") == row["gold"]):
            raise ValueError("HUMAN_TRAINER_REUSABLE_EXAM_MISS_DRIFT")
        guesses[row["id"]] = miss["predicted"]
    measured = score_cohort(cohort, guesses, asdict(school.current_student))
    if (measured["scores"] != prior.get("scores") or
            list(measured["misses_for_teacher"]) != misses):
        raise ValueError("HUMAN_TRAINER_REUSABLE_EXAM_SCORE_DRIFT")
    return guesses, measured


def _school_result_label(school):
    return (("GRADE_" + school.grade + "_MASTERED_AWAITING_GRADE_" +
             chr(ord(school.grade) + 1))
            if school.stage == "AWAITING_NEXT_GRADE" else
            ("GRADE_" + school.revalidation_target_grade +
             "_REVALIDATING_" + school.grade)
            if school.revalidation_target_grade else
            "ACTIVE_GRADE_" + school.grade)


def _reused_exam_feedback(run_dir, receipt, prior, last_exam, cohort, guesses):
    pending = receipt.get("_pending_visit_events", ())
    warnings = summarize_completed_exam_safely(run_dir, receipt, last_exam)
    last_exam["learning_diagnostics"] = warnings
    outcomes = summarize_teacher_outcomes(prior, last_exam, pending)
    last_exam["teacher_outcomes"] = outcomes
    priority = reconcile_unresolved_misses(
        receipt.get("teacher_misses", ()), list(cohort.rows), guesses)
    unresolved = {row["id"] for row in priority}
    exposures = {
        identity: count for identity, count in
        receipt.get("teacher_miss_exposures", {}).items()
        if identity in unresolved and type(count) is int and count >= 0
    }
    for identity in unresolved:
        exposures.setdefault(identity, 0)
    return pending, warnings, outcomes, priority, exposures


def _reused_exam_event(receipt, result, school, assessment, cohort, qualification,
                       scope_sha, scores, priority, warnings, outcomes,
                       retention_status, rubric, phase):
    event = {
        "event": "SCHOOL_LIVE_EXAM_REUSED_UNCHANGED_CHECKPOINT",
        "grade": school.grade,
        "generation": result["generation"],
        "grade_exam_epoch": school.grade_exam_epoch,
        "grade_test_lifecycle": GRADE_TEST_LIFECYCLE,
        "assessment_scope_sha256": scope_sha,
        "qualification_cohort_sha256": qualification["cohort_sha256"],
        "introduction_stage": school.introduction_stage,
        "scores": scores,
        "phase": phase,
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "rubric": rubric,
        "cohort_sha256": cohort.digest,
        "cohort_seed": cohort.seed,
        "cohort_file": receipt["last_exam"]["cohort_file"],
        "incumbent_comparisons": [],
        "teacher_miss_count": len(priority),
        "learning_diagnostics": warnings,
        "teacher_outcomes": outcomes,
        "whole_student_retention": retention_status,
        "reused_from_evaluation_id": receipt["last_exam"]["evaluation_id"],
        "neural_inference_reused": True,
        "candidate_checkpoint_replayed": False,
    }
    epoch = receipt.get("mentor_epoch")
    if epoch is not None:
        event["championship_epoch"] = {
            "baseline_sha256": epoch["baseline"]["sha256"],
            "earned_roles": [],
            "active_role_count": len(epoch.get("active_roles", {})),
            "active_soup_grades": sorted(epoch.get("active_grade_soups", {})),
            "cross_origin_decisions": [],
        }
    return event


def _reuse_unchanged_exam_boundary(run_dir, receipt, course, school, cohort,
                                   qualification, verified, graph):
    """Advance a scheduled boundary from an already verified unchanged exam."""
    guesses, measured = verified
    prior = receipt["last_exam"]
    rubric = prior["exam_rubric_sha256"]
    assessment = Assessment(
        checkpoint_sha256=school.current_student.sha256,
        optimizer_step=school.current_student.optimizer_step,
        course_digest=course.digest(),
        rubric_digest=rubric,
        scores={cap: Score(**entry) for cap, entry in measured["scores"].items()},
        evaluation_id=prior["evaluation_id"])
    advanced = assess(course, school, assessment)
    scores = {cap: {"correct": value.correct, "total": value.total}
              for cap, value in assessment.scores.items()}
    scope_sha = _fingerprint(assessment_capabilities(course, school))
    peaks, retention_status = advance_peaks(
        receipt.get("whole_student_peaks", []),
        curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=rubric, cohort_sha256=cohort.digest,
        assessment_scope_sha256=scope_sha, scores=scores,
        checkpoint=asdict(school.current_student))
    last_exam = json.loads(_canonical(prior))
    last_exam.update({
        "assessment_grade": school.grade,
        "grade_exam_epoch": school.grade_exam_epoch,
        "assessment_scope_sha256": scope_sha,
        "cohort_sha256": cohort.digest,
        "graduation_perfect_roles": [],
        "grade_soups_refreshed": [],
        "championship_decisions": [],
        "incumbent_comparisons": [],
        "misses_for_teacher": list(measured["misses_for_teacher"]),
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "scores": scores,
        "reused_unchanged_checkpoint": True,
        "reused_from_evaluation_id": prior["evaluation_id"],
        "reuse_count": int(prior.get("reuse_count", 0)) + 1,
        "whole_student_retention": retention_status,
    })
    pending, exam_warnings, teacher_outcomes, priority, miss_exposures = (
        _reused_exam_feedback(
            run_dir, receipt, prior, last_exam, cohort, guesses))
    migrated = {
        **receipt,
        "teacher_misses": priority,
        "whole_student_peaks": peaks,
        "qualification_cohort": qualification,
        "teacher_miss_exposures": miss_exposures,
        "legacy_frontier_pending_replay": False,
        "live_rubric_sha256": rubric,
    }
    migrated.pop("teacher_miss_cursor", None)
    result = _advance(
        run_dir, migrated, advanced,
        frontier=receipt.get("capability_best", {}),
        model_bundle=school.current_student.filename,
        last_exam=last_exam, result=_school_result_label(advanced),
        persist=False)
    event = _reused_exam_event(
        receipt, result, school, assessment, cohort, qualification, scope_sha,
        scores, priority, exam_warnings, teacher_outcomes, retention_status,
        rubric, advanced.stage)
    result = _persist(run_dir, _with_delivery_outbox(
        result, _boundary_delivery_events(result, pending, (), event)))
    _publish_boundary(run_dir, result, pending, (), exam_event=event)
    return result


def _promotion_due_after_routine(before, after) -> bool:
    """Whether a perfect routine evaluation would advance the school state.

    Passing an intermediate introduction tranche is not graduation. Moving to
    another grade, beginning/advancing a cumulative revalidation sweep, or
    reaching a curriculum boundary is.
    """
    return (
        after.grade != before.grade
        or after.revalidation_target_grade != before.revalidation_target_grade
        or after.stage in {
            "AWAITING_NEXT_GRADE", "AWAITING_TEACHER_SOUP",
            "WHOLE_SCHOOL_MASTERED",
        }
    )


def _take_exam(mx, run_dir, receipt, manifest, course, source_root,
               source_checkpoint, parameters, optimizer, graph, *, reserve_gib):
    school = _state_from_json(receipt["school"], course)
    if not school.stage.startswith("ASSESS_"):
        raise ValueError("HUMAN_TRAINER_EXAM_OUTSIDE_SCHEDULED_BOUNDARY")
    stagnation = receipt.get("stagnation_session")
    blocked_before = quarantined_capabilities(stagnation)
    full_scope = assessment_capabilities(course, school)
    active_scope = tuple(cap for cap in full_scope if cap not in set(blocked_before))
    _require_active_stagnation_scope(active_scope)
    parent_checkpoint = school.current_student
    rubric, release, generator, _ = _cohort_contract(course)
    routine_cohort, _ = _grade_test_cohort(
        run_dir, receipt, manifest, course, source_root, graph)
    routine_cohort, routine_file = _introduced_cohort(
        run_dir, manifest, course, school, routine_cohort)
    routine_cohort, routine_file = _without_stagnant_capabilities(
        run_dir, manifest, course, routine_cohort, stagnation)
    routine_rows = list(routine_cohort.rows)
    scope_sha = _fingerprint(active_scope)
    candidate_cohort = _candidate_cohort(
        run_dir, receipt, manifest, course, source_root, graph)
    candidate_cohort, _ = _introduced_cohort(
        run_dir, manifest, course, school, candidate_cohort)
    candidate_cohort, _ = _without_stagnant_capabilities(
        run_dir, manifest, course, candidate_cohort, stagnation)
    candidate_guesses = _predictions(
        mx, parameters, list(candidate_cohort.rows),
        receipt["config"], receipt["answer_ids"])
    school, frontier, roles, compared = _commit_scored_student(
        mx, run_dir, receipt, manifest, course, school,
        candidate_cohort, candidate_guesses,
        parameters, optimizer, graph, reserve_gib=reserve_gib,
        allowed_capabilities=active_scope)
    candidate_measured = score_cohort(
        candidate_cohort, candidate_guesses, asdict(school.current_student))

    routine_guesses = _predictions(
        mx, parameters, routine_rows, receipt["config"], receipt["answer_ids"])
    routine_measured = score_cohort(
        routine_cohort, routine_guesses, asdict(school.current_student))
    parent_routine_scores, parent_routine_issue = _score_parent_for_paired_s3(
        mx, run_dir, receipt, parent_checkpoint, routine_cohort, graph,
        routine_measured["scores"])
    routine_assessment = Assessment(
        checkpoint_sha256=school.current_student.sha256,
        optimizer_step=school.current_student.optimizer_step,
        course_digest=course.digest(),
        rubric_digest=rubric,
        scores={cap: Score(**entry)
                for cap, entry in routine_measured["scores"].items()},
        evaluation_id="source-oracled-routine-cohort/" + routine_cohort.digest + "/" +
                      school.current_student.sha256)
    routine_advanced = (
        assess_withheld(course, school, routine_assessment, blocked_before)
        if blocked_before else assess(course, school, routine_assessment))

    routine_last_exam = {
        "assessment_grade": school.grade,
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": "ROUTINE",
        "grade_test_lifecycle": ROUTINE_EVAL_LIFECYCLE,
        "assessment_scope_sha256": scope_sha,
        "evaluation_id": routine_assessment.evaluation_id,
        "exam_rubric_sha256": routine_assessment.rubric_digest,
        "cohort_sha256": routine_cohort.digest,
        "cohort_file": routine_file,
        "cohort_seed": routine_cohort.seed,
        "generator_version": generator,
        "misses_for_teacher": list(routine_measured["misses_for_teacher"]),
        "student_sha256": routine_assessment.checkpoint_sha256,
        "optimizer_step": routine_assessment.optimizer_step,
        "scores": routine_measured["scores"],
    }
    routine_warnings = summarize_completed_exam_safely(
        run_dir, receipt, routine_last_exam)
    routine_warnings = apply_paired_checkpoint_s3(
        routine_warnings,
        parent_scores=parent_routine_scores,
        current_scores=routine_measured["scores"],
        parent_sha256=parent_checkpoint.sha256,
        current_sha256=school.current_student.sha256,
        parent_step=parent_checkpoint.optimizer_step,
        current_step=school.current_student.optimizer_step,
        cohort_sha256=routine_cohort.digest,
        unavailable_reason=parent_routine_issue)
    quarantine_suppressed = grace_suppressed_capabilities(
        receipt.get("stagnation_grace"), required_capabilities=full_scope,
        optimizer_step=routine_assessment.optimizer_step)
    stagnation, stagnation_events, routine_advanced, blocked_after = (
        _advance_stagnation_after_routine(
            course=course, school=school,
            routine_assessment=routine_assessment,
            routine_advanced=routine_advanced,
            stagnation=stagnation, blocked_before=blocked_before,
            active_scope=active_scope, routine_measured=routine_measured,
            routine_warnings=routine_warnings,
            generation=receipt["generation"] + 1,
            quarantine_suppressed=quarantine_suppressed))

    qualification = None
    exam_plane = "ROUTINE"
    cohort = routine_cohort
    cohort_file = routine_file
    rows = routine_rows
    guesses = routine_guesses
    measured = routine_measured
    assessment = routine_assessment
    advanced = routine_advanced
    if _promotion_due_after_routine(school, routine_advanced):
        promotion_cohort, qualification = _promotion_cohort(
            run_dir, receipt, manifest, course, source_root, graph)
        promotion_cohort, promotion_file = _introduced_cohort(
            run_dir, manifest, course, school, promotion_cohort)
        promotion_rows = list(promotion_cohort.rows)
        promotion_guesses = _predictions(
            mx, parameters, promotion_rows,
            receipt["config"], receipt["answer_ids"])
        promotion_measured = score_cohort(
            promotion_cohort, promotion_guesses, asdict(school.current_student))
        promotion_assessment = Assessment(
            checkpoint_sha256=school.current_student.sha256,
            optimizer_step=school.current_student.optimizer_step,
            course_digest=course.digest(),
            rubric_digest=rubric,
            scores={cap: Score(**entry)
                    for cap, entry in promotion_measured["scores"].items()},
            evaluation_id="source-oracled-promotion-cohort/" +
                          promotion_cohort.digest + "/" +
                          school.current_student.sha256)
        exam_plane = "PROMOTION"
        cohort = promotion_cohort
        cohort_file = promotion_file
        rows = promotion_rows
        guesses = promotion_guesses
        measured = promotion_measured
        assessment = promotion_assessment
        advanced = assess(course, school, promotion_assessment)

    scores = {k: {"correct": v.correct, "total": v.total}
              for k, v in assessment.scores.items()}
    epoch = receipt.get("mentor_epoch")
    championship_decisions = ()
    graduation_roles = ()
    championship_roles = ()
    if epoch is None:
        perfect = receipt.get("graduation_perfect", {})
        frozen_soups = receipt.get("grade_soups", {})
        soup_changes = ()
        if qualification is not None:
            perfect, graduation_roles = graduation_perfect(
                perfect, scores, rubric, cohort.digest,
                asdict(school.current_student), assessment.evaluation_id)
            frozen_soups, soup_changes = _cook_new_grade_soups(
                mx, run_dir, receipt, perfect, course, graph,
                reserve_gib=reserve_gib)
    elif blocked_before or blocked_after:
        # Capability containment is session-local teaching authority. Preserve
        # all previously earned championship/soup evidence, but a routine exam
        # sampled under containment remains incomplete authority even if
        # rehabilitation releases that debt after scoring.
        perfect = receipt.get("graduation_perfect", {})
        frozen_soups = receipt.get("grade_soups", {})
        soup_changes = ()
    else:
        grades, challenger, incumbents = _epoch_paired_examinations(
            mx, run_dir, receipt, course, school, candidate_cohort,
            candidate_measured["scores"], graph)
        epoch, championship_roles, championship_decisions = advance_championship_epoch(
            epoch, grades=grades, challenger_exam=challenger,
            incumbent_exams=incumbents)
        new_soups, soup_changes = _cook_new_grade_soups(
            mx, run_dir, receipt, epoch_active_frontier(epoch), course, graph,
            existing=epoch.get("active_grade_soups", {}), reserve_gib=reserve_gib)
        epoch["active_grade_soups"] = new_soups
        # Keep all original champion/grade-soup evidence immutable in the
        # archival state fields. Only the epoch earns new active roles.
        perfect = receipt.get("graduation_perfect", {})
        frozen_soups = receipt.get("grade_soups", {})
    last_exam = {
        "assessment_grade": school.grade,
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": exam_plane,
        "grade_test_lifecycle": (
            PROMOTION_ATTEMPT_LIFECYCLE
            if qualification is not None else ROUTINE_EVAL_LIFECYCLE),
        "assessment_scope_sha256": scope_sha,
        "evaluation_id": assessment.evaluation_id,
        "exam_rubric_sha256": assessment.rubric_digest,
        "cohort_sha256": cohort.digest,
        "cohort_file": cohort_file,
        "cohort_seed": cohort.seed,
        "routine_cohort_sha256": routine_cohort.digest,
        "routine_cohort_file": routine_file,
        "routine_cohort_seed": routine_cohort.seed,
        "routine_scores": routine_measured["scores"],
        "candidate_cohort_sha256": candidate_cohort.digest,
        "graduation_perfect_roles": list(graduation_roles),
        "championship_roles": list(championship_roles),
        "grade_soups_refreshed": list(soup_changes),
        "championship_decisions": list(championship_decisions),
        "generator_version": generator,
        "incumbent_comparisons": compared,
        "misses_for_teacher": list(measured["misses_for_teacher"]),
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "scores": scores,
        "stagnation_quarantined": list(blocked_after),
        "routine_learning_diagnostics": routine_warnings,
    }
    peaks, retention_status = advance_peaks(
        receipt.get("whole_student_peaks", []),
        curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=assessment.rubric_digest,
        cohort_sha256=cohort.digest,
        assessment_scope_sha256=last_exam["assessment_scope_sha256"],
        scores=scores, checkpoint=asdict(school.current_student))
    last_exam["whole_student_retention"] = retention_status
    pending = (*receipt.get("_pending_visit_events", ()), *stagnation_events)
    exam_warnings = summarize_completed_exam_safely(run_dir, receipt, last_exam)
    if cohort.digest == routine_cohort.digest:
        paired_parent_scores = parent_routine_scores
        paired_parent_issue = parent_routine_issue
    else:
        paired_parent_scores, paired_parent_issue = _score_parent_for_paired_s3(
            mx, run_dir, receipt, parent_checkpoint, cohort, graph, scores)
    exam_warnings = apply_paired_checkpoint_s3(
        exam_warnings,
        parent_scores=paired_parent_scores,
        current_scores=scores,
        parent_sha256=parent_checkpoint.sha256,
        current_sha256=school.current_student.sha256,
        parent_step=parent_checkpoint.optimizer_step,
        current_step=school.current_student.optimizer_step,
        cohort_sha256=cohort.digest,
        unavailable_reason=paired_parent_issue)
    last_exam["learning_diagnostics"] = exam_warnings
    teacher_outcomes = summarize_teacher_outcomes(receipt.get("last_exam"), last_exam, pending)
    last_exam["teacher_outcomes"] = teacher_outcomes
    # Exam golds become eligible *after* the complete examination. Retain
    # tokens and source provenance so the next weakest-three visits can train
    # directly on missed semantics, with no answer leakage during scoring.
    priority = reconcile_unresolved_misses(
        receipt.get("teacher_misses", ()), rows, guesses)
    if blocked_after:
        blocked_set = set(blocked_after)
        priority = [row for row in priority if row["capability"] not in blocked_set]
    unresolved_ids = {row["id"] for row in priority}
    miss_exposures = {
        identity: count for identity, count in
        receipt.get("teacher_miss_exposures", {}).items()
        if identity in unresolved_ids and type(count) is int and count >= 0
    }
    for identity in unresolved_ids:
        miss_exposures.setdefault(identity, 0)
    migrated_receipt = {**receipt, "teacher_misses": priority,
                        "whole_student_peaks": peaks,
                        "graduation_perfect": perfect,
                        "grade_soups": frozen_soups,
                        "teacher_miss_exposures": miss_exposures,
                        "legacy_frontier_pending_replay": False,
                        "live_rubric_sha256": assessment.rubric_digest}
    if stagnation is not None:
        migrated_receipt["stagnation_session"] = stagnation
    if qualification is not None:
        migrated_receipt["qualification_cohort"] = qualification
        last_exam["promotion_cohort_sha256"] = qualification["cohort_sha256"]
    else:
        migrated_receipt.pop("qualification_cohort", None)
    if epoch is not None:
        migrated_receipt["mentor_epoch"] = epoch
    migrated_receipt.pop("teacher_miss_cursor", None)
    result = _advance(
        run_dir, migrated_receipt, advanced, frontier=frontier,
        model_bundle=school.current_student.filename, last_exam=last_exam,
        result=_school_result_label(advanced), persist=False)
    exam_event = {
        "event": ("SCHOOL_LIVE_EXAM_COMMITTED" if len(course.grades) > 2 else
                  "GRADE_A_LIVE_EXAM_COMMITTED" if len(course.grades) == 1
                  else "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED"),
        "grade": school.grade, "generation": result["generation"],
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": exam_plane,
        "grade_test_lifecycle": last_exam["grade_test_lifecycle"],
        "assessment_scope_sha256": last_exam["assessment_scope_sha256"],
        "introduction_stage": school.introduction_stage,
        "scores": scores, "phase": advanced.stage,
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "rubric": assessment.rubric_digest,
        "cohort_sha256": cohort.digest, "generator_version": generator,
        "cohort_seed": cohort.seed, "cohort_file": last_exam["cohort_file"],
        "routine_cohort_sha256": routine_cohort.digest,
        "incumbent_comparisons": compared,
        "teacher_miss_count": len(priority),
        "learning_diagnostics": exam_warnings,
        "teacher_outcomes": teacher_outcomes,
        "whole_student_retention": retention_status,
    }
    if qualification is not None:
        exam_event["qualification_cohort_sha256"] = qualification["cohort_sha256"]
    if epoch is not None:
        exam_event["championship_epoch"] = {
            "baseline_sha256": epoch["baseline"]["sha256"],
            "earned_roles": list(championship_roles),
            "active_role_count": len(epoch.get("active_roles", {})),
            "active_soup_grades": sorted(epoch.get("active_grade_soups", {})),
            "cross_origin_decisions": list(championship_decisions),
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
    stagnation = receipt.get("stagnation_session")
    blocked = quarantined_capabilities(stagnation)
    active_scope = tuple(
        cap for cap in assessment_capabilities(course, school)
        if cap not in set(blocked))
    if not active_scope:
        raise ValueError("STAGNATION_STOP_EVALUATION_HAS_NO_ACTIVE_CAPABILITIES")
    rubric, release, generator, _ = _cohort_contract(course)
    exam_cohort, _ = _grade_test_cohort(
        run_dir, receipt, manifest, course, source_root, graph)
    cohort = _candidate_cohort(run_dir, receipt, manifest, course, source_root, graph)
    cohort, _ = _introduced_cohort(run_dir, manifest, course, school, cohort)
    cohort, _ = _without_stagnant_capabilities(
        run_dir, manifest, course, cohort, stagnation)
    rows = list(cohort.rows)
    guesses = _predictions(mx, parameters, rows, receipt["config"], receipt["answer_ids"])
    current, frontier, roles, compared = _commit_scored_student(
        mx, run_dir, receipt, manifest, course, school, cohort, guesses,
        parameters, optimizer, graph, reserve_gib=reserve_gib,
        allowed_capabilities=active_scope)
    # The operator may stop between scheduled full exams. Score one fresh
    # routine cohort at this durable stop boundary; this records a recoverable
    # peak without creating or extending a promotion attempt.
    exam_cohort, _ = _introduced_cohort(
        run_dir, manifest, course, school, exam_cohort)
    exam_cohort, _ = _without_stagnant_capabilities(
        run_dir, manifest, course, exam_cohort, stagnation)
    exam_guesses = _predictions(
        mx, parameters, list(exam_cohort.rows), receipt["config"], receipt["answer_ids"])
    exam_scores = score_cohort(exam_cohort, exam_guesses,
                               asdict(current.current_student))["scores"]
    peaks, retention_status = advance_peaks(
        receipt.get("whole_student_peaks", []),
        curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=rubric, cohort_sha256=exam_cohort.digest,
        assessment_scope_sha256=_fingerprint(active_scope),
        scores=exam_scores, checkpoint=asdict(current.current_student))
    stop_receipt = {**receipt, "legacy_frontier_pending_replay": False,
                    "whole_student_peaks": peaks,
                    "live_rubric_sha256": rubric}
    stop_receipt.pop("qualification_cohort", None)
    record = _advance(run_dir, stop_receipt,
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
        "incumbent_comparisons": compared,
        "stagnation_quarantined": list(blocked)}
    comparison_event["whole_student_retention"] = retention_status
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
    if stage == "DEFERRED_STAGNATION":
        return "STAGNATION_REVIEW_REQUIRED"
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
            batch_size: int = 32, reserve_gib: float = 100.,
            numeric_staircase: bool = False,
            retention_enabled: bool = True,
            experiment_probe_each: int = 6,
            experiment_mature_max_loss: int = 1,
            experiment_introduction_extra_loss: int = 2,
            experiment_protected_cap_limit: int = 8,
            stagnation_grace_grade: str | None = None,
            stagnation_grace_steps: int = 0) -> dict:
    """ENTRYPOINT FOR THE HUMAN'S SHELL ONLY. Never call in agent tests."""
    trace_mark(
        "OPERATE_START", resume=resume, max_visits=max_visits,
        steps_per_visit=steps_per_visit, batch_size=batch_size)
    if (type(minutes) is not int or not 1 <= minutes <= 1440 or
            type(steps_per_visit) is not int or not 1 <= steps_per_visit <= 2048 or
            type(max_visits) is not int or max_visits < 0 or
            type(batch_size) is not int or batch_size < 2 or batch_size % 2):
        raise ValueError("HUMAN_TRAINER_INVALID_OPERATOR_LIMITS")
    grace_requested = stagnation_grace_grade is not None or stagnation_grace_steps != 0
    if grace_requested and (
            not resume or not isinstance(stagnation_grace_grade, str) or
            not stagnation_grace_grade or type(stagnation_grace_steps) is not int or
            stagnation_grace_steps <= 0):
        raise ValueError("STAGNATION_GRACE_REQUIRES_EXPLICIT_RESUME_REQUEST")
    if retention_enabled:
        # Experiments never attach to the canonical run in another checkout.
        # The independent snapshot/copy step is a deliberate operator action.
        isolated_root = (Path(__file__).resolve().parents[1] / "runs").resolve()
        target = Path(run_dir).expanduser().resolve()
        if target == isolated_root or isolated_root not in target.parents:
            raise ValueError("LEARNING_EXPERIMENT_REQUIRES_ISOLATED_WORKTREE_RUN")
    elif resume:
        # Fail before GPU loading, orphan recovery, or any state mutation when
        # a protected student's policy would otherwise be silently disabled.
        saved_path = Path(run_dir).expanduser().resolve() / "state.json"
        if (saved_path.is_file() and json.loads(saved_path.read_text()).get(
                "learning_experiment") is not None):
            raise ValueError("LEARNING_EXPERIMENT_PROTECTED_RESUME_REQUIRES_RETENTION")
    import mlx.core as mx
    mx.set_default_device(mx.gpu)
    with trace_span("PREPARE_SOURCE"):
        manifest, historical_course, engine, teacher_sha, historical_teacher, provenance = prepare_source(
            source_root, source_checkpoint, manifest_path)
    course_a = live_course(historical_course)
    # Build only verified source-bound metadata; no student, optimizer or
    # checkpoint is touched while preparing a future grade's course.
    course_b = None
    course_c = None
    staircase_course = None
    course = course_a
    run_dir = Path(run_dir).expanduser().resolve()
    start = time.monotonic()
    with operator_lock(run_dir):
        trace_mark("OPERATOR_LOCK_ACQUIRED")
        if resume:
            saved = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            from .historical_live_release import resume_grade_courses
            course_a, course_b = resume_grade_courses(historical_course, source_root, saved)
            course = course_a
            pending = run_dir / "states" / f"{saved['generation'] + 1:07d}.json"
            if pending.exists() and (pending.is_symlink() or not pending.is_file()):
                raise ValueError("HUMAN_TRAINER_PENDING_GENERATION_UNSAFE_PATH")
            pending_mode = (json.loads(pending.read_text(encoding="utf-8")).get(
                "curriculum_mode") if pending.exists() else None)
            # A trainer still acquiring A must never depend on readiness of a
            # *future* B release. Only a B run, graduated A, or prospective B
            # orphan needs B's source construction and version guard.
            if (saved.get("curriculum_mode") in (B_RELEASE, C_RELEASE, STAIRCASE_RELEASE) or
                    pending_mode in (B_RELEASE, C_RELEASE, STAIRCASE_RELEASE) or
                    saved["school"]["stage"] == "AWAITING_NEXT_GRADE"):
                if course_b is None:
                    course_b = live_b_course(course_a, source_root)
            if saved.get("curriculum_mode") == B_RELEASE:
                course = course_b
            numeric_modes = (C_RELEASE, STAIRCASE_RELEASE)
            if (saved.get('curriculum_mode') in numeric_modes or pending_mode in numeric_modes or
                    (saved.get('curriculum_mode') == B_RELEASE and
                     saved['school']['stage'] == 'AWAITING_NEXT_GRADE')):
                from .live_grade_c import prepare_course, registry_graph
                from .numeric_staircase import build_course
                if saved.get('curriculum_mode') != STAIRCASE_RELEASE:
                    pinned_maximum = saved.get('numeric_maximum')
                    if pending_mode == C_RELEASE and pinned_maximum is None:
                        pinned_maximum = json.loads(pending.read_text())['numeric_maximum']
                    course_c, _ = prepare_course(course_b, maximum=pinned_maximum)
                if saved.get('curriculum_mode') == STAIRCASE_RELEASE or pending_mode == STAIRCASE_RELEASE:
                    active = json.loads(pending.read_text()) if pending_mode == STAIRCASE_RELEASE else saved
                    staircase_course = build_course(course_b, registry_graph(),
                                                     maximum=active['numeric_maximum'])
                if saved.get('curriculum_mode') == C_RELEASE:
                    course = course_c
                elif saved.get('curriculum_mode') == STAIRCASE_RELEASE:
                    course = staircase_course
            with trace_span("RESUME_STUDENT"):
                params, optimizer, graph, receipt = _resume(
                    run_dir, manifest, course, teacher_sha,
                    successor_course=course_b,
                    admitted_courses={c.version: c for c in (course_a, course_b, course_c, staircase_course) if c is not None})
            # A fully written B migration might have survived a crash before
            # publishing the latest state pointer. _resume recovers it under
            # operator_lock; do not interpret recovered B as an A-only run.
            if receipt.get("curriculum_mode") == B_RELEASE:
                course = course_b
            elif receipt.get("curriculum_mode") == C_RELEASE:
                course = course_c
            elif receipt.get('curriculum_mode') == STAIRCASE_RELEASE:
                course = staircase_course
            if numeric_staircase and receipt.get('curriculum_mode') != STAIRCASE_RELEASE:
                from .numeric_staircase import enroll
                course, receipt = enroll(run_dir, receipt, course, course_b, graph)
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
            if numeric_staircase:
                raise ValueError('NUMERIC_STAIRCASE_REQUIRES_RESUME')
            params, optimizer, graph, receipt = _init(
                run_dir, manifest, course, teacher_sha,
                historical_teacher, provenance, source_checkpoint,
                reserve_gib=reserve_gib)
        with trace_span("RECONCILE_VOCABULARY"):
            receipt = _reconcile_vocabulary_metadata(
                run_dir, receipt, course, params, optimizer, graph)
        learning_settings = (LearningSettings(
            probe_each=experiment_probe_each,
            mature_max_loss=experiment_mature_max_loss,
            introduction_extra_loss=experiment_introduction_extra_loss,
            protected_cap_limit=experiment_protected_cap_limit)
            if retention_enabled else None)
        with trace_span("RECONCILE_LEARNING_SETTINGS"):
            receipt = _reconcile_learning_settings(
                run_dir, receipt, course, learning_settings, optimizer)
        if learning_settings is not None:
            with trace_span("SEED_WHOLE_STUDENT_PEAK"):
                receipt = _seed_saved_whole_student_peak(
                    run_dir, receipt, course, optimizer)
        school = _state_from_json(receipt["school"], course)
        if (stagnation_grace_grade is not None and
                stagnation_grace_grade not in set(school.active_grades)):
            raise ValueError("STAGNATION_GRACE_GRADE_NOT_ACTIVE")
        grace, grace_created = reconcile_optimizer_step_grace(
            receipt.get("stagnation_grace"),
            requested_grade=stagnation_grace_grade,
            requested_steps=stagnation_grace_steps,
            optimizer_step=school.current_student.optimizer_step)
        if grace != receipt.get("stagnation_grace"):
            receipt = _advance(
                run_dir, {**receipt, "stagnation_grace": grace}, school,
                result=receipt["result"])
            if grace_created:
                _record(run_dir, {
                    "event": "SCHOOL_STAGNATION_GRACE_CONFIGURED",
                    "generation": receipt["generation"],
                    "grade": grace["grade"],
                    "started_optimizer_step": grace["started_optimizer_step"],
                    "optimizer_step_budget": grace["optimizer_step_budget"],
                    "until_optimizer_step": grace["until_optimizer_step"],
                    "reason": grace["reason"],
                    "model_and_optimizer_unchanged": True,
                })
        previous_stagnation = receipt.get("stagnation_session")
        prior_debt = quarantined_capabilities(previous_stagnation)
        school = _state_from_json(receipt["school"], course)
        deferred_before_reentry = school.stage == "DEFERRED_STAGNATION"
        if prior_debt and deferred_before_reentry:
            school = reactivate_stagnation_debt(course, school, prior_debt)
            receipt = {**receipt, "school": asdict(school)}
        history = list(receipt.get("stagnation_history", ()))
        if previous_stagnation is not None:
            history.append({
                "session_id": previous_stagnation["session_id"],
                "started_generation": previous_stagnation["started_generation"],
                "ended_before_generation": receipt["generation"],
                "quarantined": list(prior_debt),
                "alerts": list(end_of_run_alerts(previous_stagnation)),
            })
        receipt["stagnation_history"] = history[-16:]
        receipt["stagnation_session"] = start_stagnation_session(
            session_id=uuid.uuid4().hex, generation=receipt["generation"],
            required_capabilities=assessment_capabilities(course, school))
        debt_grades = {capability.partition(".")[0] for capability in prior_debt}
        grace_reentry = grace_suppressed_capabilities(
            receipt.get("stagnation_grace"), required_capabilities=tuple(prior_debt),
            optimizer_step=school.current_student.optimizer_step)
        if (prior_debt and deferred_before_reentry and len(debt_grades) == 1 and
                set(grace_reentry) != set(prior_debt)):
            receipt["stagnation_session"], rehabilitation_event = (
                activate_sole_grade_rehabilitation(
                    receipt["stagnation_session"],
                    capabilities=tuple(prior_debt),
                    generation=receipt["generation"]))
            pending = list(receipt.get("_pending_visit_events", ()))
            pending.append(rehabilitation_event)
            receipt["_pending_visit_events"] = pending
        visits = 0
        while True:
            from .numeric_staircase import scope_advance_due, advance_scope
            if scope_advance_due(receipt, course):
                course, receipt = advance_scope(run_dir, receipt, course, course_b, graph)
            school = _state_from_json(receipt["school"], course)
            reason = session_stop_reason(
                stage=school.stage, elapsed_seconds=time.monotonic() - start,
                minutes=minutes, visits=visits, max_visits=max_visits,
                grade=school.grade)
            if reason is not None:
                break
            if school.stage.startswith("ASSESS_"):
                with trace_span(
                        "ASSESSMENT", generation=receipt["generation"],
                        phase=school.stage, grade=school.grade):
                    receipt = _take_exam(
                        mx, run_dir, receipt, manifest, course, source_root,
                        source_checkpoint, params, optimizer, graph,
                        reserve_gib=reserve_gib)
                continue
            with trace_span("DISK_HEADROOM", visit_index=visits + 1):
                budget = headroom_snapshot(run_dir, required_bytes=600_000_000,
                                           reserve_gib=reserve_gib)
            if not budget["sufficient"]:
                reason = "DISK_RESERVE_REACHED"
                break
            # Retain the original fail-closed checkpoint preflight against
            # disk changes between telemetry and the actual write boundary.
            with trace_span("DISK_HEADROOM_ASSERT", visit_index=visits + 1):
                assert_headroom(run_dir, required_bytes=600_000_000,
                                reserve_gib=reserve_gib)
            with trace_span(
                    "VISIT_TOTAL", visit_index=visits + 1,
                    generation=receipt["generation"], phase=school.stage,
                    grade=school.grade):
                receipt = _take_visit(
                    mx, run_dir, receipt, manifest, course, engine,
                    params, optimizer, graph, steps_per_visit=steps_per_visit,
                    batch_size=batch_size, reserve_gib=reserve_gib,
                    source_root=source_root, learning_settings=learning_settings)
            visits += 1
        with trace_span("FLUSH_WORKING_STUDENT", visits=visits):
            receipt = _flush_working_student(
                mx, run_dir, receipt, manifest, course, params, optimizer, graph,
                reserve_gib=reserve_gib, source_root=source_root)
        school = _state_from_json(receipt["school"], course)
        budget = headroom_snapshot(run_dir, required_bytes=600_000_000,
                                   reserve_gib=reserve_gib)
        elapsed_seconds = round(time.monotonic() - start, 3)
        stagnation_alerts = end_of_run_alerts(receipt.get("stagnation_session"))
        stagnation_quarantined = quarantined_capabilities(
            receipt.get("stagnation_session"))
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
            "stagnation_session_id": receipt.get("stagnation_session", {}).get(
                "session_id"),
            "stagnation_quarantined": list(stagnation_quarantined),
            "stagnation_alerts": list(stagnation_alerts),
            **{k: budget[k] for k in ("free_bytes", "reserve_bytes", "estimated_write_bytes")},
        })
        # Reclaim superseded JSON snapshot storage after the committed stop
        # receipt. Lossless compression retains exact source bytes and SHA
        # readback; all complete model/AdamW checkpoints remain untouched.
        from .state_archive import compact_states
        try:
            with trace_span("STATE_ARCHIVE_COMPACT"):
                maintenance = compact_states(run_dir, max_files=64)
        except (OSError, ValueError) as exc:
            maintenance = {"error": str(exc), "compressed_generations": 0}
            _record(run_dir, {"event": "SCHOOL_STATE_ARCHIVE_BLOCKED",
                              "generation": receipt["generation"],
                              "reason": str(exc)})
        trace_mark(
            "OPERATE_END", stop_reason=reason, visits=visits,
            optimizer_step=school.current_student.optimizer_step)
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
            "stagnation_quarantined": list(stagnation_quarantined),
            "stagnation_alerts": list(stagnation_alerts),
            "stagnation_grace": receipt.get("stagnation_grace"),
            "experimental_retention": learning_settings is not None,
            "retention_enabled": learning_settings is not None,
            "state_archive": maintenance,
            "safe_resume_command": _resume_command(run_dir, source_root, learning_settings),
            "original_source_checkpoint_modified": False,
        }
