"""Source lesson selection and bounded frozen-mentor guidance."""
from __future__ import annotations

import bilqis_mlx.backup as _bilqis_mlx_backup
import bilqis_mlx.learning.champion_confidence as _learning_champion_confidence
import bilqis_mlx.learning.epoch_championships as _learning_epoch_championships
import bilqis_mlx.learning.grade_soup as _learning_grade_soup
import bilqis_mlx.learning.mentor_epoch as _learning_mentor_epoch
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.runtime.mlx_checkpoint as _runtime_mlx_checkpoint
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.source as _bilqis_mlx_source
import functools as _functools
import pathlib as _pathlib

from ._lesson_guidance import (
    _champion_directed_rows, _confidence_guidance, _cook_new_grade_soups,
    _mentor_vote_specs, _typed_confidence_guidance, choose_lesson_batch,
    replay_missed_lessons,
)

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
                            "breadth": votes, "soup_grade": grade})
            receipts.append({"soup_grade": grade,
                             "recipe_sha256": snapshot["recipe_sha256"],
                             "ingredient_recipe_sha256": shard["recipe_sha256"],
                             "frozen_base_votes": shard["vote_count"],
                             "effective_votes": votes,
                             "source_graph_sha256": shard.get("source_graph_sha256")})
    return tuple(mentors), tuple(receipts)

__all__ = (
    "_cached_frozen_champion", "_cached_grade_soup",
    "_champion_directed_rows", "_confidence_guidance",
    "_cook_new_grade_soups", "_frozen_confidence_champions",
    "_frozen_grade_soup_votes", "_mentor_sources_for_visit",
    "_mentor_vote_specs", "_typed_confidence_guidance",
    "choose_lesson_batch", "replay_missed_lessons",
)
