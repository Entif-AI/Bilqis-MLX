from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.model import CapabilityDefinition, ConstructionProgram, SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.generation import execute_release_family_program
from bilqis_mlx.factory.skos_curriculum.registry import (
    IMPLEMENTATION_UNCOVERED, PROGRAM_BOUND, BoundFamilyProgram,
    FamilyProgramRegistry, RegisteredFamilyProgram, bind_existing_family_program,
    bind_factory_release_families, default_family_program_registry,
    uncovered_family_obligations,
)
from bilqis_mlx.factory.skos_curriculum.inventory import _inventory_source_families
from bilqis_mlx.factory.skos_curriculum.curriculum import (
    LearnedFrontier, _compile_semantic_curriculum_snapshot,
)
from bilqis_mlx.factory.skos_curriculum.lesson_compiler import (
    _compile_source_constructive_lessons_snapshot,
)
from bilqis_mlx.factory.tests.sources.test_skos_curriculum import _snapshot
from bilqis_mlx.factory.tests.support import synthetic_release_inputs


from bilqis_mlx.factory.skos_curriculum.programs.tests.fixtures import (
    ADAPTER, GENERATOR, ORACLE, _source_registry, _family, _capability, _program,
)


class FamilyBindingTests(unittest.TestCase):
    def test_release_boundary_replays_a08_currentness_before_program_binding(self):
        course, source_registry = synthetic_release_inputs()
        release = compile_factory_release(course, source_registry)
        census = _inventory_source_families(_snapshot())
        frontier = LearnedFrontier(census.semantic_release)
        candidate = _compile_semantic_curriculum_snapshot(
            _snapshot(), (), frontier)
        lessons = _compile_source_constructive_lessons_snapshot(_snapshot())
        family = RegisteredFamilyProgram(
            "fixture_family", ("fixture.adapter/v1",),
            "fixture.constructor/v1", "fixture.checker/v1",
            lambda *args, **kwargs: args, lambda *args, **kwargs: True)
        with patch.multiple(
            "bilqis_mlx.factory.skos_curriculum.programs.binding",
            inventory_source_families=lambda _selection: census,
            compile_semantic_curriculum=lambda *_args: candidate,
            compile_source_constructive_lessons=lambda _selection: lessons,
            assert_family_inventory_current=lambda *_args: None,
            assert_curriculum_candidate_current=lambda *_args: None,
            assert_source_lesson_set_current=lambda *_args: None,
        ):
            result = bind_factory_release_families(
                release, FamilyProgramRegistry((family,)), source_registry,
                object(), frontier)
        self.assertEqual(len(result.bound_programs), len(release.capabilities))
        self.assertTrue(all(
            item.implementation_status == PROGRAM_BOUND
            and item.learning_state == "LEARNING_UNVERIFIED"
            for item in result.bound_programs))
        self.assertEqual(
            len(result.coverage.dispositions), len(census.obligations))
