"""Neural-inert qualification of the full Registry Grade C teaching release."""
from __future__ import annotations

import json
from pathlib import Path

from .grade_a_release import accepted_grade_a
from .live_grade_a import live_course as a_course
from .live_grade_b import live_course as b_course
from .live_grade_c import (PLANS, REGISTRY_COUNTING_TARGET, RELEASE, admissions,
                          draw, prepare_course)
from .paths import LEGACY_SOURCE


def qualify(legacy_root, manifest, *, previous=None):
    if previous is None:
        previous = b_course(a_course(accepted_grade_a(manifest)), legacy_root)
    course, graph = prepare_course(previous, maximum=REGISTRY_COUNTING_TARGET)
    rows = draw(graph, seed=2026101602, maximum=REGISTRY_COUNTING_TARGET)
    return {"release": RELEASE, "source_only": True, "neural_updates": 0,
        "parent_course_sha256": previous.digest(),
        "source_executable": course.executable,
        "registry_counting_target": REGISTRY_COUNTING_TARGET,
        "grade_c_items": len(rows),
        "cumulative_grade_test_items": sum(n for g in course.grades for _,n in g.exam_item_counts),
        "stages": [dict(capability=p.capability, original_lesson=p.lesson_id,
                        operation=p.operation, prerequisites=p.prerequisites) for p in PLANS],
        "new_token_symbols": [a.token_id for a in admissions()],
        "runtime_admission": "ONE_COMPLETE_CUMULATIVE_A_B_144_OF_144_CHECKPOINT_THEN_HUMAN_RESUME",
        "operator_scope": "Set BILQIS_INTEGER_MAX="+str(REGISTRY_COUNTING_TARGET)+" before C admission; the saved release pins it",
        "actual_grade_c_learning": "NOT_MEASURED",
        "semantic_mode": "SCOPED_TYPED_FORMAL_ADAPTER_NOT_NI_WORDFORM"}


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
    print(json.dumps(qualify(LEGACY_SOURCE, manifest), indent=2))


if __name__ == "__main__":
    main()
