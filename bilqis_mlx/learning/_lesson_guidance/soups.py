"""Frozen grade-soup construction over accepted champion custody."""
from __future__ import annotations

import bilqis_mlx.learning.grade_soup as _learning_grade_soup
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.runtime.mlx_checkpoint as _runtime_mlx_checkpoint
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.source as _bilqis_mlx_source

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
