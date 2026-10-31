'Neural-inert, source-bound typed composition discovery and witness accounting.\n\nThe approved Course and versioned Token Atlas supply candidate semantics.\nSource interpreters, not matching answer types, decide whether a particular\nconstruction actually works. No result of this module admits lessons or changes\nthe live model, its teacher, or historical grade release definitions.'
import json
from ...paths import REPO_ROOT
from .discovery import discover_composition_obligations
from .audit import audit_pinned_micro_generator

def main(argv=None) -> int:
    """Read-only coverage audit of the currently admitted A+B source slice."""
    import argparse
    from collections import Counter
    from pathlib import Path
    from ...curriculum_compiler import compile_ast
    from ...grade_a_release import accepted_grade_a
    from ...live_grade_b import live_course
    from ...registry_ast import load_registry

    parser = argparse.ArgumentParser(description=__doc__)
    project = REPO_ROOT
    parser.add_argument("--legacy-code-root", type=Path,
                        default=project / "vendor" / "legacy-v16")
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2026101601)
    parser.add_argument("--each", type=int, default=12)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args(argv)
    manifest = json.loads((project / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
    approved = live_course(accepted_grade_a(manifest), args.legacy_code_root)
    ast = compile_ast(approved)
    registry = load_registry(project / "docs/provenance/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json")
    plan = discover_composition_obligations(ast, registry)
    verified = audit_pinned_micro_generator(
        plan, args.legacy_code_root, seed=args.seed,
        max_rounds=args.max_rounds, each=args.each)
    counts = Counter(e["status"] for e in verified["obligations"])
    result = {
        "schema": verified["schema"],
        "ast_sha256": verified["ast_sha256"],
        "registry_sha256": verified["registry_sha256"],
        "source_graph_sha256": verified["source_graph_sha256"],
        "generator_code_sha256": verified["generator_code_sha256"],
        "generated_record_count": verified["constructed_record_count"],
        "generated_rounds": verified["rounds_used"],
        "source_witness_cohort_sha256": verified["source_witness_cohort_sha256"],
        "candidate_operand_slot_count": len(verified["obligations"]),
        "undeclared_compatible_families": sorted({e["producer"] for e in
              verified["obligations"] if not e["declared_prerequisite"]}),
        "coverage_by_status": dict(sorted(counts.items())),
        "unresolved_registry_contracts": verified["unresolved"],
        "student_exposure_measured": False,
        "training_authorized": False,
    }
    if args.details:
        result["obligations"] = verified["obligations"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
