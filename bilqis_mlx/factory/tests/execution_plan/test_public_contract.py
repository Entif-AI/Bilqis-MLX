"""Public import, introspection, pickle and patch seams survive owner extraction."""
from dataclasses import asdict
from enum import Enum
import inspect
import pickle
import typing
import unittest
from unittest.mock import patch

import bilqis_mlx.factory.execution as execution
from bilqis_mlx.factory.tests.execution_plan.fixtures import (
    _synthetic_course, _synthetic_registry,
)


class PublicExecutionContractTests(unittest.TestCase):
    def compile(self):
        return execution.compile_execution_plan(
            _synthetic_course(), execution.CurriculumProfile.full(),
            _synthetic_registry())

    def test_public_metadata_and_annotations_resolve_at_the_historical_module(self):
        for name in (
                "CapabilityProfile", "GradeProfile", "CurriculumProfile",
                "CapabilityExecution", "GradeExecution", "ProjectionDigests",
                "CapabilityProjectionDigests", "ExecutionPlan",
                "SemanticGeometryChange", "PlanLineage", "CurriculumDelta"):
            with self.subTest(name=name):
                value = getattr(execution, name)
                self.assertEqual(value.__module__, "bilqis_mlx.factory.execution")
                self.assertEqual(value.__qualname__, name)
                typing.get_type_hints(value)
        for function in (
                execution.compile_execution_plan, execution.diff_execution_plans,
                execution.ExecutionPlan.grade_map.fget,
                execution.ExecutionPlan.digest,
                execution.PlanLineage.from_semantic_catalogs.__func__,
                inspect.unwrap(execution.ExecutionPlan.__repr__)):
            self.assertEqual(function.__module__, "bilqis_mlx.factory.execution")
            typing.get_type_hints(function)
        self.assertEqual(Enum.__new__.__module__, "enum")
        self.assertEqual(
            tuple(inspect.signature(execution.compile_execution_plan).parameters),
            ("curriculum", "profile", "registry", "source_bindings", "answer_registry"))

    def test_canonical_plan_digest_and_pickle_globals_remain_public(self):
        plan = self.compile()
        self.assertEqual(
            plan.digest(),
            "adf3811c39759a4fa02e347f2e8eab7454f72cb77351969a33702f4145024fbe")
        payload = pickle.dumps(plan, protocol=4)
        self.assertIn(b"bilqis_mlx.factory.execution", payload)
        self.assertNotIn(b"bilqis_mlx.factory._execution", payload)
        self.assertEqual(pickle.loads(payload), plan)

    def test_public_digest_patch_reaches_records_and_projection_owners(self):
        digest = "e" * 64
        with patch.object(execution, "_digest", return_value=digest):
            plan = self.compile()
            self.assertEqual(plan.digest(), digest)
            self.assertEqual(set(asdict(plan.projection_digests).values()), {digest})
            self.assertEqual(plan.grades[0].assessment_blueprint_sha256, digest)
            self.assertEqual(plan.capability_projection_digests[0].source, digest)

    def test_public_source_validation_patch_remains_a_compilation_boundary(self):
        with patch.object(execution, "validate_source_bindings",
                          side_effect=ValueError("SOURCE_BINDING_SENTINEL")):
            with self.assertRaisesRegex(ValueError, "^SOURCE_BINDING_SENTINEL$"):
                self.compile()
