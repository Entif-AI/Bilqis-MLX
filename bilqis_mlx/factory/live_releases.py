"""Compatibility providers for the currently admitted A/B/C source releases.

Generic runtime code may depend on this release-provider boundary. It MUST NOT
import the historical ``live_grade_*`` constructor modules directly. Those
modules remain source-domain implementations while their callers are migrated.
"""
from __future__ import annotations

from .model import FactoryRelease
from .release import compile_factory_release
from .adapters import live_source_registry
from ..live_grade_a import (
    GENERATOR as _INITIAL_GENERATOR,
    RELEASE as INITIAL_RELEASE,
    generator_source_digest as _initial_digest,
    live_course as _initial_course,
)
from ..live_grade_b import (
    GENERATOR as _BOOLEAN_GENERATOR,
    RELEASE as BOOLEAN_RELEASE,
    constructor_digest as _boolean_digest,
    live_course as _boolean_course,
)
from ..live_grade_c import (
    RELEASE as NUMERIC_RELEASE,
    answer_heads as numeric_answer_heads,
    constructor_digest as _numeric_digest,
    prepare_course as _prepare_numeric_course,
    registry_graph as numeric_registry_graph,
)
from ..numeric_staircase import (
    RELEASE as NUMERIC_STAIRCASE_RELEASE,
    build_course as _build_staircase_course,
    constructor_digest as _staircase_digest,
)


KNOWN_RELEASES = (
    INITIAL_RELEASE,
    BOOLEAN_RELEASE,
    NUMERIC_RELEASE,
    NUMERIC_STAIRCASE_RELEASE,
)


def initial_course(accepted):
    return _initial_course(accepted)


def boolean_successor(previous, source_root):
    return _boolean_course(previous, source_root)


def numeric_successor(previous, *, maximum=None):
    return _prepare_numeric_course(previous, maximum=maximum)


def staircase_successor(previous, *, maximum):
    return _build_staircase_course(previous, numeric_registry_graph(), maximum=maximum)


def release_generator(version: str) -> str:
    if version == INITIAL_RELEASE:
        return _INITIAL_GENERATOR
    if version == BOOLEAN_RELEASE:
        return _BOOLEAN_GENERATOR
    # Numeric source identity is carried by the factory SourceAdapter. Runtime
    # telemetry only needs the historical A/B generator labels.
    raise ValueError("FACTORY_RELEASE_HAS_NO_LEGACY_GENERATOR_LABEL:" + str(version))


def release_code_digest(version: str) -> str:
    providers = {
        INITIAL_RELEASE: _initial_digest,
        BOOLEAN_RELEASE: _boolean_digest,
        NUMERIC_RELEASE: _numeric_digest,
        NUMERIC_STAIRCASE_RELEASE: _staircase_digest,
    }
    try:
        return providers[version]()
    except KeyError as exc:
        raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version)) from exc


def verify_release_receipt(receipt: dict, course) -> None:
    """Verify historical provider fingerprints without grade-letter dispatch."""
    version = course.version
    if version == INITIAL_RELEASE:
        return
    field_by_release = {
        BOOLEAN_RELEASE: "grade_b_code_sha256",
        NUMERIC_RELEASE: "grade_c_code_sha256",
        NUMERIC_STAIRCASE_RELEASE: "staircase_code_sha256",
    }
    field = field_by_release.get(version)
    if field is None:
        raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version))
    if receipt.get(field) != release_code_digest(version):
        raise ValueError("FACTORY_RELEASE_PROVIDER_DIGEST_DRIFT:" + version)


def compile_live_release(course) -> FactoryRelease:
    return compile_factory_release(course, live_source_registry())
