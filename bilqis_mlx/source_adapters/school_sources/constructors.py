"""School source constructors."""
from __future__ import annotations

from ...curriculum import BOOLEAN_OPERATORS
from ...boolean_composite import CAPABILITY as B_COMPOSITE_CAPABILITY, draw_composite
from ...boolean_identification import CAPABILITY as B_IDBOOLOPS_CAPABILITY, draw_identification
from ...live_grade_b import draw_connectives
from ...live_grade_c import PLANS
from ...numeric_curriculum import draw_numeric
from .common import BOOLEAN_RUNTIME_SAMPLER
from .checks import check_boolean_composite, check_connective


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
