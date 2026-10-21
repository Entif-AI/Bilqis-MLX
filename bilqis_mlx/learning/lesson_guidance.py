"""Source lesson selection and bounded frozen-mentor guidance."""
from __future__ import annotations

import bilqis_mlx.backup as _bilqis_mlx_backup
import bilqis_mlx.learning.champion_confidence as _learning_champion_confidence
import bilqis_mlx.learning.epoch_championships as _learning_epoch_championships
import bilqis_mlx.learning.grade_soup as _learning_grade_soup
import bilqis_mlx.learning.mentor_epoch as _learning_mentor_epoch
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.runtime.mlx_checkpoint as _runtime_mlx_checkpoint
import bilqis_mlx.runtime.mlx_parity as _runtime_mlx_parity
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.source as _bilqis_mlx_source
import functools as _functools
import pathlib as _pathlib
import random as _random


def choose_lesson_batch(rows: list[dict], policy: dict,
                        seed: int, *, batch_size=32) -> list[dict]:
    """Balance both truth values; policy shapes selection, never gold answers."""
    if not rows or batch_size < 2 or batch_size % 2:
        raise ValueError("HUMAN_TRAINER_INVALID_LESSON_BATCH_SIZE")
    rng = _random.Random(seed)
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


@_functools.lru_cache(maxsize=16)
def _cached_frozen_champion(path_string, sha, step, file_size, file_mtime_ns):
    """Bound repeat source reads; never cache optimizer moments."""
    weights, own_optimizer, meta, source_graph = _runtime_mlx_checkpoint.load_semantically_bound_bundle(
        _pathlib.Path(path_string))
    if (meta["safetensors_sha256"] != sha or
            meta["optimizer_step"] != step or
            meta["source_digest"] != _bilqis_mlx_source.AUDITED_PARENT.sha256):
        raise ValueError("CHAMPION_CONFIDENCE_BUNDLE_DRIFT")
    del own_optimizer
    return weights, source_graph


def _frozen_confidence_champions(run_dir, receipt, grade, graph):
    """Read active perfect capability specialists for this lesson's own grade only."""
    mentors = []
    frontier = receipt.get("graduation_perfect", {})
    soups = receipt.get("grade_soups", {})
    if frontier and not soups:
        raise ValueError("CHAMPION_CONFIDENCE_GRADE_SOUPS_MISSING_FOR_ACTIVE_ROLES")
    for item in _learning_champion_confidence.perfect_role_roster(frontier, soups):
        votes = item.get("source_grade_votes", {}).get(grade, 0)
        capabilities = tuple(
            cap for cap in item.get("capabilities", ()) if cap.startswith(grade + "."))
        if not votes or len(capabilities) != votes:
            continue
        pointer = item["checkpoint"]
        path = run_dir / pointer["filename"]
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not pointer["filename"].startswith("bundles/")):
            raise ValueError("CHAMPION_CONFIDENCE_UNSAFE_BUNDLE")
        content = (path / "model-and-own-adamw.safetensors").stat()
        weights, source_graph = _cached_frozen_champion(
            str(path), pointer["sha256"], pointer["optimizer_step"],
            content.st_size, content.st_mtime_ns)
        if not _learning_student_ops._compatible_graphs(source_graph, graph):
            raise ValueError("CHAMPION_CONFIDENCE_BUNDLE_DRIFT")
        mentors.append({"weights": weights, "graph": source_graph,
                        "breadth": votes,
                        "source_grade_votes": {grade: votes},
                        "capabilities": capabilities,
                        "checkpoint_sha256": pointer["sha256"]})
    return tuple(mentors)


def _mentor_sources_for_visit(run_dir, receipt, grade, graph, grade_count):
    """Select only current-epoch champions and soups after curriculum reset."""
    epoch = receipt.get("mentor_epoch")
    if epoch is None:
        return (_frozen_confidence_champions(run_dir, receipt, grade, graph),
                *_frozen_grade_soup_votes(run_dir, receipt, grade, grade_count))
    if epoch.get("source_graph_sha256") != _runtime_state._fingerprint(graph):
        raise ValueError("MENTOR_EPOCH_SOURCE_GRAPH_DRIFT")
    epoch_identity = epoch.get("championship_school_identity")
    receipt_identity = receipt.get("championship_school_identity")
    if (not isinstance(epoch_identity, dict) or
            not isinstance(receipt_identity, dict) or
            epoch_identity != receipt_identity):
        raise ValueError("MENTOR_EPOCH_SCHOOL_IDENTITY_RESET_REQUIRED")
    for capability, role in epoch.get("active_roles", {}).items():
        if role.get("origin_grade") != capability.partition(".")[0]:
            raise ValueError("MENTOR_EPOCH_TITLE_ORIGIN_PROVENANCE_INVALID")
    if epoch.get("guidance_policy") != _learning_mentor_epoch.EARNED_ONLY_POLICY:
        raise ValueError("MENTOR_EPOCH_FRESH_CHAMPIONS_RESET_REQUIRED")
    active = {"graduation_perfect": _learning_epoch_championships.active_frontier(epoch),
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
    program = _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course)
    for grade in program.grades:
        plan = _learning_grade_soup.grade_soup_recipe(
            frontier, grade.id, tuple(cap.id for cap in grade.capabilities))
        if not _learning_grade_soup.needs_refresh(current.get(grade.id), plan):
            continue
        members = []
        catalogs = {}
        graph_digests = {}
        for item in plan["members"]:
            pointer = item["checkpoint"]
            path = run_dir / pointer["filename"]
            if path.is_symlink() or path.parent != run_dir / "bundles":
                raise ValueError("GRADE_SOUP_UNSAFE_CHAMPION_BUNDLE")
            weights, own_adamw, manifest, original_graph = _runtime_mlx_checkpoint.load_semantically_bound_bundle(path)
            if (manifest["source_digest"] != _bilqis_mlx_source.AUDITED_PARENT.sha256 or
                    manifest["safetensors_sha256"] != pointer["sha256"] or
                    manifest["optimizer_step"] != pointer["optimizer_step"] or
                    not _learning_student_ops._compatible_graphs(original_graph, graph)):
                raise ValueError("GRADE_SOUP_CHAMPION_CUSTODY_DRIFT")
            sha = pointer["sha256"]
            graph_digest = _runtime_state._fingerprint(original_graph)
            if (graph_digest in catalogs and
                    original_graph != catalogs[graph_digest]):
                raise ValueError("GRADE_SOUP_INGREDIENT_GRAPH_DIGEST_COLLISION")
            catalogs[graph_digest] = original_graph
            graph_digests[sha] = graph_digest
            members.append((sha, item["votes"], weights))
            del own_adamw
        if len(catalogs) == 1:
            graph_digest, catalog = next(iter(catalogs.items()))
            combined = _learning_grade_soup.weighted_average(mx, [
                (votes, weights) for _, votes, weights in members])
            snapshot = _learning_grade_soup.save_frozen_soup(run_dir, plan, combined,
                                        reserve_gib=reserve_gib,
                                        token_count=len(catalog["tokens"]))
            snapshot["source_graph_sha256"] = graph_digest
        else:
            # Each exact source graph owns its own frozen weight mixture.
            # Append-only older prefixes may advise their supported tokens,
            # but must never masquerade as expanded embedding matrices.
            by_sha = {sha: (votes, weights) for sha, votes, weights in members}
            shards = []
            for shard_plan in _learning_grade_soup.partitioned_recipe(plan, graph_digests):
                graph_digest = shard_plan["source_graph_sha256"]
                combined = _learning_grade_soup.weighted_average(mx, [
                    by_sha[item["checkpoint"]["sha256"]]
                    for item in shard_plan["members"]])
                frozen = _learning_grade_soup.save_frozen_soup(
                    run_dir, shard_plan, combined, reserve_gib=reserve_gib,
                    token_count=len(catalogs[graph_digest]["tokens"]))
                frozen["source_graph_sha256"] = graph_digest
                shards.append(frozen)
            snapshot = {**plan, "schema": _learning_grade_soup.PARTITIONED_SCHEMA,
                        "shards": shards,
                        "partition_policy": "EXACT_SOURCE_GRAPH_NO_MIXED_PARAMETER_AVERAGE"}
        previous = current.get(grade.id)
        if previous is not None:
            snapshot["coverage_peak"] = max(
                previous["coverage_peak"], snapshot["coverage_peak"])
            snapshot["previous"] = [
                {"filename": part["filename"], "sha256": part["sha256"]}
                for part in _learning_grade_soup.soup_shards(previous)]
        current[grade.id] = snapshot
        refreshed.append(grade.id)
    return current, tuple(refreshed)


@_functools.lru_cache(maxsize=12)
def _cached_grade_soup(path_string, sha, token_count, stat_size, stat_mtime_ns):
    """Verify a frozen soup once per exact file identity for repeated lessons."""
    import mlx.core as mx
    path = _pathlib.Path(path_string)
    if _bilqis_mlx_backup.digest_file(path) != sha:
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
        for shard in _learning_grade_soup.soup_shards(snapshot):
            path = run_dir / shard["filename"]
            if (path.parent != run_dir / "soups" or path.is_symlink()):
                raise ValueError("GRADE_SOUP_UNSAFE_SAVED_PATH")
            stat = path.stat()
            weights = _cached_grade_soup(
                str(path), shard["sha256"], shard["token_count"],
                stat.st_size, stat.st_mtime_ns)
            votes = _learning_grade_soup.soup_vote_count(shard, lesson_grade, school_grade_count)
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
    ids, lengths, labels = _learning_student_ops._make_batch(picked)
    vote_logits = []
    for mentor in mentors:
        vocabulary = (mentor.get("vocab_size") or len(mentor["graph"]["tokens"]))
        if (max(answer_ids) >= vocabulary or
                any(max(row["tokens"]) >= vocabulary for row in picked)):
            continue
        logits = _runtime_mlx_parity.forward_arrays(mx, mentor["weights"], ids, lengths,
                                heads=config["heads"], layers=config["layers"],
                                answer_ids=answer_ids)
        mx.eval(logits)
        vote_logits.append((mentor["breadth"], np.asarray(logits)[:, :2]))
    target, influence = _learning_champion_confidence.vote_targets(vote_logits, labels,
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
    from bilqis_mlx.typed_answer_training import prepare_typed_batches
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
            logits = _runtime_mlx_parity.forward_arrays(
                mx, mentor["weights"], batch["ids"], batch["lengths"],
                heads=config["heads"], layers=config["layers"], answer_ids=answer_ids)
            mx.eval(logits)
            eligible.append((mentor["breadth"], np.asarray(logits)))
        if not eligible:
            continue
        target, weight = _learning_champion_confidence.vote_targets_typed(
            eligible, batch["target_indices"], classes=len(answer_ids),
            eligible_capabilities=scope_size, teacher_distill=teacher_distill)
        if np.any(weight):
            guidance[kind] = (target, weight)
    return guidance or None
