"""Compatibility providers for the currently admitted A/B/C source releases.

Generic runtime code may depend on this release-provider boundary. It MUST NOT
import the historical ``live_grade_*`` constructor modules directly. Those
modules remain source-domain implementations while their callers are migrated.
"""

from ..factory.model import FactoryRelease
from ..factory.release import compile_factory_release
from .source_adapters import historical_source_registry
from .live_release_parts.providers import (
    INITIAL_RELEASE, BOOLEAN_RELEASE, BOOLEAN_COMPOSITE_RELEASE,
    BOOLEAN_IDENTIFICATION_RELEASE, MINIMAL_BOOLEAN_RELEASE, NUMERIC_RELEASE,
    NUMERIC_STAIRCASE_RELEASE, KNOWN_RELEASES, FULL_BOOLEAN_RELEASES,
    REGISTRY_COUNTING_TARGET, numeric_registry_graph,
    initial_course, boolean_successor, minimal_boolean_successor,
    boolean_composite_successor, boolean_identification_successor,
    boolean_identification_answer_heads, minimal_boolean_answer_heads,
    numeric_answer_heads, rebind_same_grade_config, numeric_successor,
    staircase_successor, graph_matches_release, release_generator,
    release_code_digest,
)
from .live_release_parts.reconstruction import (
    resolve_admitted_courses, course_for_mode, predecessor_course,
)
from .live_release_parts.succession import (
    SuccessorPlan, SAME_GRAPH_TRANSITION, SAME_GRADE_TRANSITION,
    GRAPH_GROWTH_TRANSITION, default_resume_replacement, next_successor_plan,
)
from .live_release_parts.preflight import preflight_successor
from .live_release_parts.receipts import legacy_receipt_fields, verify_release_receipt


def compile_live_release(course) -> FactoryRelease:
    return compile_factory_release(course, historical_source_registry())
