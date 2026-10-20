"""Historical source adapters excluded from the canonical live registry."""
from __future__ import annotations

from ..boolean_composite import ORACLE as B_COMPOSITE_ORACLE
from ..boolean_identification import encode_record
from ..factory.adapters import RegisteredSourceAdapter
from ..factory.model import SourceAdapter
from ..grade_b_oracle import VERSION as B_ORACLE
from ..minimal_boolean_identification_oracle import (
    VERSION as B_MINIMAL_IDBOOLOPS_ORACLE,
    evaluate as evaluate_minimal_identification,
)
from ..minimal_grade_b import (
    GENERATOR as B_MINIMAL_GENERATOR,
    RELEASE as B_MINIMAL_RELEASE,
    constructor_digest as b_minimal_digest,
    draw_minimal,
)
from ..source_adapters.school import (
    B_COMPOSITE_CAPABILITY,
    B_IDBOOLOPS_CAPABILITY,
    check_boolean_composite,
    check_connective,
    live_source_registry,
)


def _draw_minimal(*, source_root, graph, course, capability, seed, each):
    return draw_minimal(
        source_root, graph, seed=seed, capability=capability, each=each)


def _check_minimal(row, **kwargs):
    if row.get("capability") == B_IDBOOLOPS_CAPABILITY:
        return (
            evaluate_minimal_identification(
                row["record"], row["capability"]) == row["gold"] and
            encode_record(
                row["record"], kwargs["source_root"], kwargs["graph"]) ==
            row["tokens"])
    if row.get("capability") == B_COMPOSITE_CAPABILITY:
        return check_boolean_composite(row, **kwargs)
    return check_connective(row, **kwargs)


def historical_source_registry():
    """Canonical providers plus adapters needed only to verify old manifests."""
    registry = live_source_registry()
    registry.register(RegisteredSourceAdapter(SourceAdapter(
        "source.micro.boolean-minimal/v1", B_MINIMAL_GENERATOR,
        (B_ORACLE, B_COMPOSITE_ORACLE, B_MINIMAL_IDBOOLOPS_ORACLE),
        b_minimal_digest(), cohort_generator_id=B_MINIMAL_GENERATOR,
        variation_axes=("source-valid", "fresh-seed", "balanced-gold",
                        "and-iff-only", "operator-composition"),
        cohort_releases=((B_MINIMAL_RELEASE, b_minimal_digest()),)),
        _draw_minimal, _check_minimal))
    return registry
