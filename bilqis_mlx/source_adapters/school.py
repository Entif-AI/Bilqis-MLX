"""Admitted finite-world, Boolean and numeric source adapters and independent checks."""
from __future__ import annotations

import hashlib
import random

from ..factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from ..factory.model import SourceAdapter
from ..factory.verification import (
    check_boolean_composite, check_connective, check_numeric, check_predicate,
)

from ..grade_a_oracle import VERSION as A_ORACLE


from ..live_grade_a import (GENERATOR as A_COHORT_GENERATOR, RELEASE as A_RELEASE,
                            draw_predicates, generator_source_digest)


from ..grade_b_oracle import VERSION as B_ORACLE

from ..boolean_composite import (
    CAPABILITY as B_COMPOSITE_CAPABILITY,
    GENERATOR as B_COMPOSITE_GENERATOR,
    ORACLE as B_COMPOSITE_ORACLE,
    RELEASE as B_COMPOSITE_RELEASE,
    constructor_digest as b_composite_digest,
    draw_composite,
)


from ..live_grade_b import (GENERATOR as B_COHORT_GENERATOR, RELEASE as B_RELEASE,
                            draw_connectives, constructor_digest as b_digest)


from ..live_grade_c import (GENERATOR as C_COHORT_GENERATOR, RELEASE as C_RELEASE,
                            PLANS, constructor_digest as c_digest)


from ..numeric_curriculum import ORACLE as C_ORACLE, draw_numeric


from ..numeric_staircase import RELEASE as STAIRCASE_RELEASE, constructor_digest as staircase_digest


from ..boolean_association import (
    VERSION as BOOLEAN_ASSOCIATION_OPTION,
    draw_b_grade_bridges,
)


BOOLEAN_RUNTIME_SAMPLER = "bilqis.mlx.grade-b-runtime-sampler/v2"








def draw_a(*, source_root, graph, course, capability, seed, each):
    return draw_predicates(source_root, graph, seed=seed,
                           capability=capability, each=each)


def _sample_boolean_runtime(rows, *, capability: str, seed: int, each: int):
    if each < 4:
        raise ValueError("FACTORY_BOOLEAN_MINIMUM_SAMPLE_REQUIRED")
    by_pattern = {}
    for row in rows:
        by_pattern.setdefault(tuple(row["operand_truths"]), []).append(row)
    expected_patterns = ({(False,), (True,)} if capability == "B.NOT" else
                         {(False, False), (False, True), (True, False), (True, True)})
    if set(by_pattern) != expected_patterns:
        raise ValueError("FACTORY_BOOLEAN_TRUTH_PATTERN_COVERAGE_MISSING")

    material = f"{BOOLEAN_RUNTIME_SAMPLER}:{seed}:{capability}:{each}".encode()
    rng = random.Random(int(hashlib.sha256(material).hexdigest(), 16))
    selected = []
    for pattern in sorted(expected_patterns):
        candidates = list(by_pattern[pattern])
        rng.shuffle(candidates)
        selected.append(candidates[0])

    minimum_true = sum(row["gold"] == "TRUE" for row in selected)
    minimum_false = sum(row["gold"] == "FALSE" for row in selected)
    lower_true = max(minimum_true, each // 3)
    upper_true = min(each - minimum_false, each - each // 3)
    true_counts = [count for count in range(lower_true, upper_true + 1)
                   if count * 2 != each]
    if not true_counts:
        true_counts = list(range(lower_true, upper_true + 1))
    target_true = rng.choice(true_counts)

    selected_ids = {row["id"] for row in selected}
    remaining = [row for row in rows if row["id"] not in selected_ids]
    rng.shuffle(remaining)
    need = {
        "TRUE": target_true - minimum_true,
        "FALSE": (each - target_true) - minimum_false,
    }
    for row in remaining:
        gold = row["gold"]
        if need[gold] <= 0:
            continue
        selected.append(row)
        need[gold] -= 1
        if not any(need.values()):
            break
    if any(need.values()) or len(selected) != each:
        raise ValueError("FACTORY_BOOLEAN_RUNTIME_SAMPLE_EXHAUSTED")
    rng.shuffle(selected)
    return tuple({**row, "runtime_sampler": BOOLEAN_RUNTIME_SAMPLER}
                 for row in selected)


def draw_b(*, source_root, graph, course, capability, seed, each):
    pool_each = max(8, each * 2)
    if pool_each % 2:
        pool_each += 1
    rows = draw_connectives(source_root, graph, seed=seed,
                            capability=capability, each=pool_each)
    return _sample_boolean_runtime(rows, capability=capability, seed=seed, each=each)


def draw_b_composite_release(*, source_root, graph, course, capability, seed, each):
    if capability == B_COMPOSITE_CAPABILITY:
        return draw_composite(source_root, graph, seed=seed,
                              capability=capability, each=each)
    return draw_b(source_root=source_root, graph=graph, course=course,
                  capability=capability, seed=seed, each=each)


def check_b_composite_release(row, **kwargs):
    if row.get("capability") == B_COMPOSITE_CAPABILITY:
        return check_boolean_composite(row, **kwargs)
    return check_connective(row, **kwargs)


def draw_c(*, source_root, graph, course, capability, seed, each):
    cap = course.capability_map[capability]
    numeric = next((family for family in cap.answer_families
                    if family.kind == "numeric_active"), None)
    if numeric is None:
        raise ValueError("FACTORY_NUMERIC_CAPABILITY_HAS_NO_ACTIVE_DOMAIN")
    maximum = len(numeric.values) - 1
    return draw_numeric(PLANS, graph, seed=seed, maximum=maximum,
                        capability=capability, each=each)


def enrich_boolean(*, source_root, graph, course, capability, seed, option_id):
    if option_id != BOOLEAN_ASSOCIATION_OPTION:
        raise ValueError("FACTORY_UNKNOWN_BOOLEAN_TEACHING_OPTION")
    cap = course.capability_map[capability]
    if cap.lesson_generator != "bilqis_mlx.live_grade_b.draw_connectives":
        return ()
    numeric_caps = [member for member in course.capability_map.values()
                    if any(family.kind == "numeric_active"
                           for family in member.answer_families)]
    if not numeric_caps:
        raise ValueError("BOOLEAN_ASSOCIATION_REQUIRES_NUMERIC_SOURCE_ADAPTER")
    maximum = max(
        len(next(family for family in member.answer_families
                 if family.kind == "numeric_active").values) - 1
        for member in numeric_caps)
    return draw_b_grade_bridges(
        source_root, graph, seed=seed, maximum=maximum,
        per_source=4, capability=capability)


def live_source_registry() -> SourceAdapterRegistry:
    return SourceAdapterRegistry((
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.predicates/v1", "bilqis_mlx.grade_a_probe.make_record",
            (A_ORACLE,), generator_source_digest(),
            cohort_generator_id=A_COHORT_GENERATOR,
            cohort_releases=((A_RELEASE, generator_source_digest()),)), draw_a, check_predicate),
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.boolean-connectives/v1", "bilqis_mlx.live_grade_b.draw_connectives",
            (B_ORACLE,), b_digest(), cohort_generator_id=B_COHORT_GENERATOR,
            cohort_releases=((B_RELEASE, b_digest()),),
            teaching_option_ids=(BOOLEAN_ASSOCIATION_OPTION,)), draw_b, check_connective, enrich_boolean),
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.boolean-composite/v1", B_COMPOSITE_GENERATOR,
            (B_ORACLE, B_COMPOSITE_ORACLE), b_composite_digest(),
            cohort_generator_id=B_COMPOSITE_GENERATOR,
            variation_axes=("source-valid", "fresh-seed", "operator-composition",
                            "runtime-answer-balance"),
            cohort_releases=((B_COMPOSITE_RELEASE, b_composite_digest()),)),
            draw_b_composite_release, check_b_composite_release),
        RegisteredSourceAdapter(SourceAdapter(
            "source.finite-numeric/v1", "bilqis_mlx.numeric_curriculum.draw_numeric",
            (C_ORACLE,), c_digest(), cohort_generator_id=C_COHORT_GENERATOR,
            variation_axes=("source-valid", "fresh-seed", "typed-answer",
                            "numeric-scope", "construction-shape"),
            cohort_releases=((C_RELEASE, c_digest()),
                             (STAIRCASE_RELEASE, staircase_digest()))), draw_c, check_numeric),
    ))

