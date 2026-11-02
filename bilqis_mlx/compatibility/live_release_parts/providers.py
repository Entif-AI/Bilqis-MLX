"""Compatibility providers for the currently admitted A/B/C source releases.

Generic runtime code may depend on this release-provider boundary. It MUST NOT
import the historical ``live_grade_*`` constructor modules directly. Those
modules remain source-domain implementations while their callers are migrated.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...factory.model import FactoryRelease
from ...factory.release import compile_factory_release
from ..source_adapters import historical_source_registry
from ...live_grade_a import (
    GENERATOR as _INITIAL_GENERATOR,
    RELEASE as INITIAL_RELEASE,
    generator_source_digest as _initial_digest,
    live_course as _initial_course,
)
from ...live_grade_b import (
    GENERATOR as _BOOLEAN_GENERATOR,
    RELEASE as BOOLEAN_RELEASE,
    constructor_digest as _boolean_digest,
    live_course as _boolean_course,
)
from ...boolean_composite import (
    GENERATOR as _BOOLEAN_COMPOSITE_GENERATOR,
    RELEASE as BOOLEAN_COMPOSITE_RELEASE,
    build_course as _boolean_composite_course,
    constructor_digest as _boolean_composite_digest,
)
from ...boolean_identification import (
    GENERATOR as _BOOLEAN_IDENTIFICATION_GENERATOR,
    RELEASE as BOOLEAN_IDENTIFICATION_RELEASE,
    answer_heads as _boolean_identification_answer_heads,
    build_course as _boolean_identification_course,
    constructor_digest as _boolean_identification_digest,
)
from ...live_grade_c import (
    REGISTRY_COUNTING_TARGET,
    RELEASE as NUMERIC_RELEASE,
    answer_heads as _numeric_answer_heads,
    constructor_digest as _numeric_digest,
    prepare_course as _prepare_numeric_course,
    registry_graph as numeric_registry_graph,
)
from ...numeric_staircase import (
    RELEASE as NUMERIC_STAIRCASE_RELEASE,
    build_course as _build_staircase_course,
    constructor_digest as _staircase_digest,
)
from ...minimal_grade_b import (
    GENERATOR as _MINIMAL_BOOLEAN_GENERATOR,
    RELEASE as MINIMAL_BOOLEAN_RELEASE,
    answer_heads as _minimal_boolean_answer_heads,
    build_course as _minimal_boolean_course,
    constructor_digest as _minimal_boolean_digest,
)


KNOWN_RELEASES = (
    INITIAL_RELEASE,
    BOOLEAN_RELEASE,
    BOOLEAN_COMPOSITE_RELEASE,
    BOOLEAN_IDENTIFICATION_RELEASE,
    MINIMAL_BOOLEAN_RELEASE,
    NUMERIC_RELEASE,
    NUMERIC_STAIRCASE_RELEASE,
)

FULL_BOOLEAN_RELEASES = (
    BOOLEAN_RELEASE,
    BOOLEAN_COMPOSITE_RELEASE,
    BOOLEAN_IDENTIFICATION_RELEASE,
)


@dataclass(frozen=True)
class SuccessorPlan:
    successor: object
    transition: str




def initial_course(accepted):
    return _initial_course(accepted)


def boolean_successor(previous, source_root):
    return _boolean_course(previous, source_root)


def minimal_boolean_successor(previous, source_root):
    return _minimal_boolean_course(previous, source_root)


def boolean_composite_successor(previous, source_root):
    return _boolean_composite_course(previous, source_root)


def boolean_identification_successor(previous, source_root):
    return _boolean_identification_course(previous, source_root)


def boolean_identification_answer_heads(graph):
    return _boolean_identification_answer_heads(graph)


def minimal_boolean_answer_heads(graph):
    return _minimal_boolean_answer_heads(graph)


def numeric_answer_heads(graph, maximum, *, prior_heads=None):
    heads = _numeric_answer_heads(graph, maximum)
    if prior_heads and "boolean_operator" in prior_heads:
        prior = prior_heads["boolean_operator"]
        labels = list(prior.get("values") or ())
        token_ids = list(prior.get("token_ids") or ())
        if len(labels) < 2 or len(labels) != len(token_ids):
            raise ValueError("FACTORY_PRIOR_BOOLEAN_OPERATOR_HEAD_INVALID")
        heads["boolean_operator"] = {"values": labels, "token_ids": token_ids}
    return heads


def rebind_same_grade_config(version: str, config: dict, graph: dict) -> dict:
    """Provider-owned metadata changes for neural-inert same-grade revisions."""
    if version in (BOOLEAN_IDENTIFICATION_RELEASE, MINIMAL_BOOLEAN_RELEASE):
        if not isinstance(graph, dict):
            raise ValueError("FACTORY_TYPED_SAME_GRADE_REVISION_REQUIRES_GRAPH")
        provider = (_boolean_identification_answer_heads
                    if version == BOOLEAN_IDENTIFICATION_RELEASE
                    else _minimal_boolean_answer_heads)
        return {**config, "answer_heads": provider(graph)}
    return config


def numeric_successor(previous, *, maximum=None):
    return _prepare_numeric_course(previous, maximum=maximum)


def staircase_successor(previous, *, maximum):
    return _build_staircase_course(previous, numeric_registry_graph(), maximum=maximum)


def graph_matches_release(version: str | None, graph: dict, manifest: dict,
                          fingerprint) -> bool:
    """Release-owned graph policy; generic runtime never keys this by grade."""
    if version in (NUMERIC_RELEASE, NUMERIC_STAIRCASE_RELEASE):
        return graph == numeric_registry_graph()
    if version in (None, INITIAL_RELEASE, BOOLEAN_RELEASE, BOOLEAN_COMPOSITE_RELEASE,
                   BOOLEAN_IDENTIFICATION_RELEASE, MINIMAL_BOOLEAN_RELEASE):
        from ..semantics.abi import HISTORICAL_PREFIX_SIZE
        return (len(graph["tokens"]) == HISTORICAL_PREFIX_SIZE and
                fingerprint(graph) == manifest["parent_student"]["full_student_graph_sha256"])
    raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version))


def release_generator(version: str) -> str:
    if version == INITIAL_RELEASE:
        return _INITIAL_GENERATOR
    if version == BOOLEAN_RELEASE:
        return _BOOLEAN_GENERATOR
    if version == BOOLEAN_COMPOSITE_RELEASE:
        return _BOOLEAN_COMPOSITE_GENERATOR
    if version == BOOLEAN_IDENTIFICATION_RELEASE:
        return _BOOLEAN_IDENTIFICATION_GENERATOR
    if version == MINIMAL_BOOLEAN_RELEASE:
        return _MINIMAL_BOOLEAN_GENERATOR
    # Numeric source identity is carried by the factory SourceAdapter. Runtime
    # telemetry only needs the historical A/B generator labels.
    raise ValueError("FACTORY_RELEASE_HAS_NO_LEGACY_GENERATOR_LABEL:" + str(version))


def release_code_digest(version: str) -> str:
    providers = {
        INITIAL_RELEASE: _initial_digest,
        BOOLEAN_RELEASE: _boolean_digest,
        BOOLEAN_COMPOSITE_RELEASE: _boolean_composite_digest,
        BOOLEAN_IDENTIFICATION_RELEASE: _boolean_identification_digest,
        MINIMAL_BOOLEAN_RELEASE: _minimal_boolean_digest,
        NUMERIC_RELEASE: _numeric_digest,
        NUMERIC_STAIRCASE_RELEASE: _staircase_digest,
    }
    try:
        return providers[version]()
    except KeyError as exc:
        raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version)) from exc
