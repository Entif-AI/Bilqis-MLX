"""Compile semantic curriculum plus source bindings into one execution plan.

Canonical curriculum meaning is independent from source/provider implementation.
Legacy ``Course`` remains an input only through a compatibility projection while
callers migrate to ``CurriculumDefinition`` and ``SourceBindingSet``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json

from ..curriculum import AnswerFamily, Course
from .adapters import SourceAdapterRegistry
from .curriculum_definition import (
    CurriculumDefinition, SourceBindingSet, from_legacy_course,
    validate_curriculum_definition, validate_source_bindings,
)

from ._execution.common import (
    _digest,
    _pairs,
)
from ._execution.profiles import (
    CapabilityProfile,
    GradeProfile,
    CurriculumProfile,
)
from ._execution.records import (
    CapabilityExecution,
    GradeExecution,
    ProjectionDigests,
    CapabilityProjectionDigests,
    ExecutionPlan,
)
from ._execution.lineage import (
    SemanticGeometryChange,
    PlanLineage,
    CurriculumDelta,
    _verify_lineage_curriculum,
    diff_execution_plans,
)
from ._execution.profiling import (
    _profile_maps,
    _answer_families,
    _stages,
    _enabled_for_grade,
    _profiled_grade,
    _compile_profiled_grades,
)
from ._execution.projections import (
    _projection_digests,
    _capability_projection_digests,
)
from ._execution.compilation import (
    _normalize_inputs,
    compile_execution_plan,
)

# Keep canonical public identities, including owned descriptors and wrapped methods.
from types import FunctionType as _FunctionType

for _export in (
    _digest,
    _pairs,
    CapabilityProfile,
    GradeProfile,
    CurriculumProfile,
    CapabilityExecution,
    GradeExecution,
    ProjectionDigests,
    CapabilityProjectionDigests,
    ExecutionPlan,
    SemanticGeometryChange,
    PlanLineage,
    CurriculumDelta,
    _normalize_inputs,
    _profile_maps,
    _answer_families,
    _stages,
    _enabled_for_grade,
    _profiled_grade,
    _compile_profiled_grades,
    _projection_digests,
    _capability_projection_digests,
    compile_execution_plan,
    _verify_lineage_curriculum,
    diff_execution_plans,
):
    _origin = _export.__module__
    if isinstance(_export, type):
        _export.__module__ = __name__
        _members = vars(_export).values()
    else:
        _members = (_export,)
    for _member in _members:
        if isinstance(_member, (classmethod, staticmethod)):
            _functions = (_member.__func__,)
        elif isinstance(_member, property):
            _functions = (_member.fget, _member.fset, _member.fdel)
        else:
            _functions = (_member,)
        for _function in _functions:
            if (isinstance(_function, _FunctionType) and _function.__module__ == _origin
                    and (_function is _export or _function.__qualname__.startswith(_export.__qualname__ + '.'))):
                while isinstance(_function, _FunctionType) and _function.__module__ == _origin:
                    _function.__module__ = __name__
                    _function = getattr(_function, '__wrapped__', None)
del _export, _origin, _members, _member, _functions, _function, _FunctionType
