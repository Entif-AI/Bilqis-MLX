"""Boolean callbacks for the historical school source contract."""
from __future__ import annotations
from .shared import (BOOLEAN_ASSOCIATION_OPTION, BOOLEAN_OPERATORS, BOOLEAN_RUNTIME_SAMPLER, B_COMPOSITE_CAPABILITY, B_IDBOOLOPS_CAPABILITY, draw_b_grade_bridges, draw_composite, draw_connectives, draw_identification,)
from .checks import (check_boolean_composite, check_connective,)


def draw_b(*, source_root, graph, course, capability, seed, each):
    del course
    rows = draw_connectives(source_root, graph, seed=seed,
                            capability=capability, each=each)
    return tuple({**row, "runtime_sampler": BOOLEAN_RUNTIME_SAMPLER}
                 for row in rows)


def _boolean_profile_operators(
        profile_parameters, *, capability, scoped_capabilities) -> tuple[str, ...]:
    parameters = profile_parameters or {}
    if set(parameters) - {"operators"}:
        raise ValueError("FACTORY_BOOLEAN_PROFILE_PARAMETER_UNKNOWN")
    if parameters and capability not in scoped_capabilities:
        raise ValueError("FACTORY_BOOLEAN_PROFILE_PARAMETER_SCOPE_DRIFT")
    return tuple(parameters.get("operators", BOOLEAN_OPERATORS))


def draw_b_composite_release(*, source_root, graph, course, capability, seed, each,
                             profile_parameters=None):
    operators = _boolean_profile_operators(
        profile_parameters, capability=capability,
        scoped_capabilities={B_COMPOSITE_CAPABILITY})
    if capability == B_COMPOSITE_CAPABILITY:
        return draw_composite(source_root, graph, seed=seed,
                              capability=capability, each=each,
                              operators=operators)
    return draw_b(source_root=source_root, graph=graph, course=course,
                  capability=capability, seed=seed, each=each)


def check_b_composite_release(row, **kwargs):
    if row.get("capability") == B_COMPOSITE_CAPABILITY:
        return check_boolean_composite(row, **kwargs)
    return check_connective(row, **kwargs)


def draw_b_idboolops_release(*, source_root, graph, course, capability, seed, each,
                             profile_parameters=None):
    operators = _boolean_profile_operators(
        profile_parameters, capability=capability,
        scoped_capabilities={B_COMPOSITE_CAPABILITY, B_IDBOOLOPS_CAPABILITY})
    if capability == B_IDBOOLOPS_CAPABILITY:
        return draw_identification(source_root, graph, seed=seed,
                                   capability=capability, each=each,
                                   operators=operators)
    if capability == B_COMPOSITE_CAPABILITY:
        return draw_composite(source_root, graph, seed=seed,
                              capability=capability, each=each,
                              operators=operators)
    return draw_b(source_root=source_root, graph=graph, course=course,
                  capability=capability, seed=seed, each=each)


def check_b_idboolops_release(row, **kwargs):
    if row.get("capability") == B_IDBOOLOPS_CAPABILITY:
        from ...boolean_identification import encode_record
        from ...boolean_identification_oracle import evaluate
        return (
            evaluate(row["record"], row["capability"]) == row["gold"] and
            encode_record(
                row["record"], kwargs["source_root"], kwargs["graph"]) ==
            row["tokens"])
    if row.get("capability") == B_COMPOSITE_CAPABILITY:
        return check_boolean_composite(row, **kwargs)
    return check_connective(row, **kwargs)


def enrich_boolean(*, source_root, graph, course, capability, seed, option_id):
    if option_id != BOOLEAN_ASSOCIATION_OPTION:
        raise ValueError("FACTORY_UNKNOWN_BOOLEAN_TEACHING_OPTION")
    course.capability_map[capability]
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

for _callback in (draw_b, _boolean_profile_operators, draw_b_composite_release, check_b_composite_release, draw_b_idboolops_release, check_b_idboolops_release, enrich_boolean,):
    _callback.__module__ = "bilqis_mlx.source_adapters.school"
