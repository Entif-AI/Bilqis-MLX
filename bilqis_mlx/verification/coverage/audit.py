"""Bounded source-generator exposure auditing without neural authority."""
from .contracts import require_coverage_audit_budget
from .witnesses import verify_micro_composition_witnesses

def audit_pinned_micro_generator(plan: dict, source_root, *,
                                 seed: int = 2026101601, max_rounds: int = 4,
                                 each: int = 12) -> dict:
    """Exercise the existing B constructor until proof or bounded coverage debt.

    The adapter reuses the pinned original source interpreter and independent
    oracle. It records *generated* exposure, not lessons delivered to a model.
    """
    from ...grade_a_probe import read_sources
    from ...live_grade_b import draw_connectives, constructor_digest

    require_coverage_audit_budget(max_rounds, each)
    micro, _, graph, source_hashes, source_graph_sha = read_sources(source_root)
    collected = {}
    report = plan
    rounds = 0
    in_scope = set(plan.get("capabilities", ()))
    for index in range(max_rounds):
        sample = draw_connectives(source_root, graph, seed=seed + index, each=each)
        collected.update((row["id"], row) for row in sample
                         if row.get("capability") in in_scope)
        report = verify_micro_composition_witnesses(
            plan, tuple(collected.values()), micro=micro, graph=graph)
        rounds += 1
        if all(edge["status"] == "SOURCE_CONTRAST_COVERED"
               for edge in report["obligations"]
               if edge["consumer_root"].startswith("cogal.operator.") and
                  edge["status"] in ("SOURCE_CONTRAST_COVERED",
                                     "SOURCE_CONTRAST_PARTIAL",
                                     "AWAITING_SOURCE_WITNESS")):
            break
    return {**report,
            "source_sha256_by_file": source_hashes,
            "source_graph_sha256": source_graph_sha,
            "generator_code_sha256": constructor_digest(),
            "first_seed": seed, "rounds_used": rounds,
            "constructed_record_count": len(collected),
            "student_exposure_measured": False,
            "training_authorized": False}
