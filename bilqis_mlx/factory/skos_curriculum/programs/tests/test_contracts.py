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


class FamilyContractsTests(unittest.TestCase):
    def test_same_family_binding_is_grade_neutral(self):
        family = _family()
        registry = _source_registry()
        b = bind_existing_family_program(
            family, _capability("B"), _program(), registry)
        z = bind_existing_family_program(
            family, _capability("Z"), _program(), registry)
        self.assertEqual(b, z)
        self.assertEqual(b.implementation_status, PROGRAM_BOUND)
        self.assertEqual(b.learning_state, "LEARNING_UNVERIFIED")
        self.assertEqual(b.capability_id, "B.AND")


    def test_cross_family_dispatch_never_inspects_grade(self):
        registry = _source_registry()
        cases = (
            ("boolean_composition", "B.AND", "B"),
            ("numeric_composition", "C.SUCCESSOR", "C"),
            ("source_world_fixture", "D.COPULAR_IDENTITY", "D"),
        )
        for family_id, capability_id, grade in cases:
            with self.subTest(family_id=family_id):
                family = _family(family_id)
                cap = replace(_capability(grade, capability_id), prerequisites=())
                program = replace(_program(capability_id), prerequisites=())
                bound = bind_existing_family_program(family, cap, program, registry)
                self.assertEqual(bound.family_id, family_id)
                self.assertEqual(bound.capability_id, capability_id)
                self.assertNotIn(grade, bound.constructor_ref)


    def test_default_registry_switches_by_family_not_grade(self):
        registry = default_family_program_registry()
        self.assertEqual(
            registry.require("boolean_composition").constructor_ref,
            registry.require("numeric_composition").constructor_ref)
        self.assertEqual(
            registry.require("source_world_fixture").checker_ref,
            "bilqis.factory.source-registry-check/v1")


    def test_missing_constructor_and_wrong_checker_fail_before_ready(self):
        registry = FamilyProgramRegistry((_family(),))
        with self.assertRaises(Exception):
            registry.require("morphology_composition")
        with self.assertRaises(ValueError) as caught:
            bind_existing_family_program(
                _family(), _capability(), _program(oracle="wrong.oracle"),
                _source_registry())
        self.assertIn("FACTORY_SOURCE_ORACLE_NOT_ADAPTER_OWNED", str(caught.exception))


    def test_identity_or_adapter_mismatch_never_becomes_ready(self):
        with self.assertRaises(Exception):
            bind_existing_family_program(
                _family(), _capability(), _program("B.NOT"), _source_registry())
        wrong = RegisteredFamilyProgram(
            "boolean_composition", ("different.adapter",),
            "fixture.constructor/v1", "fixture.checker/v1",
            lambda: None, lambda *_: True)
        with self.assertRaises(Exception):
            bind_existing_family_program(
                wrong, _capability(), _program(), _source_registry())


    def test_unbound_census_keeps_exact_denominator_and_source_holds(self):
        census = _inventory_source_families(_snapshot())
        coverage = uncovered_family_obligations(census)
        self.assertEqual(len(coverage.dispositions), len(census.obligations))
        self.assertEqual(coverage.source_held_rows, census.counts.source_held_rows)
        self.assertEqual(coverage.census_digest, census.digest)
        self.assertTrue(all(
            item.implementation_status == IMPLEMENTATION_UNCOVERED
            and item.learning_state == "LEARNING_UNVERIFIED"
            for item in coverage.dispositions))
        self.assertEqual(
            {(item.obligation.semantic_id, item.obligation.family_id)
             for item in coverage.dispositions},
            {(item.semantic_id, item.family_id) for item in census.obligations})


    def test_learning_state_cannot_be_forged(self):
        bound = bind_existing_family_program(
            _family(), _capability(), _program(), _source_registry())
        with self.assertRaises(Exception):
            replace(bound, learning_state="LEARNING_VERIFIED")
        self.assertIsInstance(bound, BoundFamilyProgram)
