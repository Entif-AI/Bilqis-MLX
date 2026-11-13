from dataclasses import replace
import unittest

from bilqis_mlx.curriculum import (
    AnswerFamily, BINARY, BOOLEAN_OPERATORS, Capability, Course, Grade,
)
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.execution import (
    CapabilityProfile, CurriculumProfile, GradeProfile, PlanLineage,
    compile_execution_plan, diff_execution_plans,
)
from bilqis_mlx.factory.generation import draw_execution_rows
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.tests.execution_plan.fixtures import (
    _fixture_rows,
    _fixture_check,
    _boolean_fixture_rows,
    _boolean_fixture_check,
    _synthetic_course,
    _synthetic_registry,
    _synthetic_boolean_course,
)

from bilqis_mlx.factory.tests.execution_plan.test_roster import ExecutionPlanTests as _roster
from bilqis_mlx.factory.tests.execution_plan.test_profiles import ExecutionPlanTests as _profiles
from bilqis_mlx.factory.tests.execution_plan.test_validation import ExecutionPlanTests as _validation
from bilqis_mlx.factory.tests.execution_plan.test_projections import ExecutionPlanTests as _projections
from bilqis_mlx.factory.tests.execution_plan.test_source_projection import ExecutionPlanTests as _source_projection
from bilqis_mlx.factory.tests.execution_plan.test_lineage import ExecutionPlanTests as _lineage


class ExecutionPlanTests(_roster, _profiles, _validation, _projections, _source_projection, _lineage):
    """Historical aggregate entrypoint; focused cases live with their owners."""


del _roster, _profiles, _validation, _projections, _source_projection, _lineage


if __name__ == "__main__":
    unittest.main()
