from __future__ import annotations
from dataclasses import replace
import unittest
from unittest.mock import patch
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.model import CapabilityDefinition, ConstructionProgram, SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.generation import execute_release_family_program
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.teaching import describe_delivered_teaching, draw_teaching_option_rows
from bilqis_mlx.factory.skos_curriculum.registry import (
    IMPLEMENTATION_UNCOVERED, PROGRAM_BOUND, BoundFamilyProgram,
    FamilyProgramRegistry, RegisteredFamilyProgram, bind_existing_family_program,
    bind_factory_release_families, default_family_program_registry,
    execute_bound_family_program, uncovered_family_obligations,
)
from bilqis_mlx.factory.skos_curriculum.inventory import _inventory_source_families
from bilqis_mlx.factory.skos_curriculum.curriculum import LearnedFrontier, _compile_semantic_curriculum_snapshot
from bilqis_mlx.factory.skos_curriculum.lesson_compiler import (
    _compile_source_constructive_lessons_snapshot,
)
from bilqis_mlx.factory.tests.sources.test_skos_curriculum import _snapshot
from bilqis_mlx.factory.tests.support import synthetic_release_inputs
from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.source_adapters.world_rules import (
    GENERATOR as WORLD_GENERATOR, ORACLE as WORLD_ORACLE,
    projected_graph, registered_adapter as world_adapter,
)
from bilqis_mlx.factory.skos_curriculum.programs.tests.fixtures import (ADAPTER, GENERATOR, ORACLE, _source_registry, _family, _capability, _program, _stable_binding_stub)
class FamilyExecutionTests(unittest.TestCase):
    def test_qualified_world_fixture_uses_common_factory_release_boundary(self):
        graph = projected_graph(registry_graph())
        adapter = world_adapter()
        source_registry = SourceAdapterRegistry((adapter,))
        roots = {
            "WORLD.ACTOR_OF": "ithkuil:ATOM-5d7116db8e1508",
            "WORLD.BEFORE": "ithkuil:ATOM-ef7cf17b427af9",
            "WORLD.IS_OCCURRED": "ithkuil:LEXSENSE-294d00be074a56",
            "WORLD.DIRECT_CAUSE": "ithkuil:LEXSENSE-59819df75e3137",
        }
        capabilities = tuple(
            Capability(
                capability_id, "qualified-world",
                "repo:lib/ithkuil/_data/csv/lexicon_root_senses.csv",
                (roots[capability_id],), (roots[capability_id],), (), (),
                (AnswerFamily("binary", BINARY),), WORLD_GENERATOR, WORLD_ORACLE)
            for capability_id in (
                "WORLD.ACTOR_OF", "WORLD.BEFORE", "WORLD.IS_OCCURRED",
                "WORLD.DIRECT_CAUSE"))
        course = Course(
            (Grade("D", capabilities, "1" * 64,
                   tuple((capability.id, 12) for capability in capabilities),
                   (tuple(capability.id for capability in capabilities),)),),
            "bamf-a08-world-fixture/v1", "2" * 64, "3" * 64)
        release = compile_factory_release(course, source_registry)
        curriculum, source_bindings = from_legacy_course(course)
        executable = compile_executable_factory_release(curriculum, source_bindings,
            CurriculumProfile.full(), source_registry, live_answer_registry(),
            source_root=None, graph=graph, verification_seed=420)
        census = _inventory_source_families(_snapshot())
        frontier = LearnedFrontier(census.semantic_release)
        candidate = _compile_semantic_curriculum_snapshot(
            _snapshot(), (), frontier)
        lessons = _compile_source_constructive_lessons_snapshot(_snapshot())
        with patch(
            "bilqis_mlx.factory.curriculum.capability_identity."
            "bind_factory_release_capability_identity",
            side_effect=_stable_binding_stub), patch.multiple(
            "bilqis_mlx.factory.skos_curriculum.programs.binding",
            inventory_source_families=lambda _selection: census,
            compile_semantic_curriculum=lambda *_args: candidate,
            compile_source_constructive_lessons=lambda _selection: lessons,
            assert_family_inventory_current=lambda *_args: None,
            assert_curriculum_candidate_current=lambda *_args: None,
            assert_source_lesson_set_current=lambda *_args: None,
        ):
            bindings = bind_factory_release_families(
                release, default_family_program_registry(), source_registry,
                object(), frontier)
            artifacts = (execute_release_family_program(
                release, source_registry, default_family_program_registry(),
                object(), frontier, "WORLD.IS_OCCURRED",
                construct_kwargs={"graph": graph, "seed": 420, "each": 12},
                check_kwargs={"graph": graph}),)
        self.assertEqual(
            {item.capability_id for item in bindings.bound_programs},
            {"WORLD.IS_OCCURRED"})
        self.assertEqual(
            {artifact.capability_id for artifact in artifacts},
            {"WORLD.IS_OCCURRED"})
        self.assertTrue(all(len(artifact.rows) == 12 for artifact in artifacts))
        self.assertTrue(all(
            {row["gold"] for row in artifact.rows} == {"TRUE", "FALSE"}
            for artifact in artifacts))
        deliveries = tuple(describe_delivered_teaching(executable,
            artifact.capability_id, "source.direct/" + artifact.capability_id,
            artifact.rows) for artifact in artifacts)
        self.assertTrue(all(delivery.specimen_ids for delivery in deliveries))
        teacher_rows = draw_teaching_option_rows(
            None, graph, executable, source_registry,
            capability="WORLD.IS_OCCURRED",
            option_id="source.direct/WORLD.IS_OCCURRED", seed=421, each=12)
        self.assertEqual(len(teacher_rows), 12)
        self.assertEqual({row["capability"] for row in teacher_rows},
                         {"WORLD.IS_OCCURRED"})
        self.assertEqual({row["gold"] for row in teacher_rows}, {"TRUE", "FALSE"})
        self.assertTrue(all(artifact.learning_state == "LEARNING_UNVERIFIED" for artifact in artifacts))
    def test_qualified_world_rejects_provider_and_answer_modality_substitution(self):
        graph = projected_graph(registry_graph())
        adapter = world_adapter()
        capabilities = (
            Capability(
                "WORLD.IS_OCCURRED", "qualified-world",
                "repo:lib/ithkuil/_data/csv/lexicon_root_senses.csv",
                ("ithkuil:LEXSENSE-294d00be074a56",),
                ("ithkuil:LEXSENSE-294d00be074a56",), (), (),
                (AnswerFamily("binary", BINARY),), WORLD_GENERATOR, WORLD_ORACLE),
        )
        course = Course(
            (Grade("D", capabilities, "1" * 64,
                   (("WORLD.IS_OCCURRED", 12),), (("WORLD.IS_OCCURRED",),)),),
            "bamf-a08-world-fixture/v1", "2" * 64, "3" * 64)
        release = compile_factory_release(
            course, SourceAdapterRegistry((adapter,)))
        census = _inventory_source_families(_snapshot())
        frontier = LearnedFrontier(census.semantic_release)
        candidate = _compile_semantic_curriculum_snapshot(
            _snapshot(), (), frontier)
        lessons = _compile_source_constructive_lessons_snapshot(_snapshot())
        forged = replace(
            adapter,
            draw=lambda **_: ({"capability": "WORLD.IS_OCCURRED", "forged": True},),
            check=lambda *_args, **_kwargs: True)
        with patch.multiple(
            "bilqis_mlx.factory.skos_curriculum.programs.binding",
            inventory_source_families=lambda _selection: census,
            compile_semantic_curriculum=lambda *_args: candidate,
            compile_source_constructive_lessons=lambda _selection: lessons,
            assert_family_inventory_current=lambda *_args: None,
            assert_curriculum_candidate_current=lambda *_args: None,
            assert_source_lesson_set_current=lambda *_args: None,
        ):
            with self.assertRaises(ValueError):
                execute_release_family_program(
                    release, SourceAdapterRegistry((forged,)),
                    default_family_program_registry(), object(), frontier,
                    "WORLD.IS_OCCURRED",
                    construct_kwargs={"graph": graph, "seed": 420, "each": 12},
                    check_kwargs={"graph": graph})
            with self.assertRaises(ValueError):
                bind_existing_family_program(
                    default_family_program_registry().require(
                        "qualified_world_model"),
                    CapabilityDefinition(
                        "WORLD.IS_OCCURRED", "D", (),
                        adapter.descriptor.adapter_id, WORLD_ORACLE,
                        ("integer",)),
                    ConstructionProgram(
                        "WORLD.IS_OCCURRED", adapter.descriptor.adapter_id,
                        WORLD_GENERATOR, WORLD_ORACLE, ()),
                    SourceAdapterRegistry((adapter,)))
    def test_qualified_world_rejects_substituted_family_program_registry(self):
        graph = projected_graph(registry_graph())
        adapter = world_adapter()
        source_registry = SourceAdapterRegistry((adapter,))
        capability = Capability(
            "WORLD.IS_OCCURRED", "qualified-world",
            "repo:lib/ithkuil/_data/csv/lexicon_root_senses.csv",
            ("ithkuil:LEXSENSE-294d00be074a56",),
            ("ithkuil:LEXSENSE-294d00be074a56",), (), (),
            (AnswerFamily("binary", BINARY),), WORLD_GENERATOR, WORLD_ORACLE)
        release = compile_factory_release(Course(
            (Grade("D", (capability,), "1" * 64, ((capability.id, 12),),
                   ((capability.id,),)),),
            "bamf-a08-world-fixture/v1", "2" * 64, "3" * 64), source_registry)
        forged = RegisteredFamilyProgram(
            "qualified_world_model", (adapter.descriptor.adapter_id,),
            "bilqis.factory.source-registry-draw/v1",
            "bilqis.factory.source-registry-check/v1",
            lambda **_: ({"forged": True},), lambda *_args, **_kwargs: True)
        census = _inventory_source_families(_snapshot())
        frontier = LearnedFrontier(census.semantic_release)
        candidate = _compile_semantic_curriculum_snapshot(_snapshot(), (), frontier)
        lessons = _compile_source_constructive_lessons_snapshot(_snapshot())
        with patch.multiple(
            "bilqis_mlx.factory.skos_curriculum.programs.binding",
            inventory_source_families=lambda _selection: census,
            compile_semantic_curriculum=lambda *_args: candidate,
            compile_source_constructive_lessons=lambda _selection: lessons,
            assert_family_inventory_current=lambda *_args: None,
            assert_curriculum_candidate_current=lambda *_args: None,
            assert_source_lesson_set_current=lambda *_args: None,
        ):
            with self.assertRaises(ValueError):
                execute_release_family_program(
                    release, source_registry, FamilyProgramRegistry((forged,)),
                    object(), frontier, capability.id,
                    construct_kwargs={"graph": graph, "seed": 420, "each": 1},
                    check_kwargs={"graph": graph})
            shadowed = default_family_program_registry()
            with patch("bilqis_mlx.factory.curriculum.capability_identity.bind_factory_release_capability_identity", side_effect=_stable_binding_stub):
                artifact = execute_release_family_program(
                    release, source_registry, shadowed, object(), frontier,
                    capability.id,
                    construct_kwargs={"graph": graph, "seed": 420, "each": 1},
                    check_kwargs={"graph": graph})
            self.assertEqual(artifact.capability_id, capability.id)
    def test_production_execution_rejects_noncanonical_family_registry(self):
        course, source_registry = synthetic_release_inputs()
        release = compile_factory_release(course, source_registry)
        census = _inventory_source_families(_snapshot())
        frontier = LearnedFrontier(census.semantic_release)
        family = RegisteredFamilyProgram(
            "caller_invented_family", ("fixture.adapter/v1",),
            "fixture.constructor/v1", "fixture.checker/v1",
            lambda: {"forged": True}, lambda *_args, **_kwargs: True)
        with self.assertRaises(ValueError):
            execute_release_family_program(
                release, source_registry, FamilyProgramRegistry((family,)),
                object(), frontier, release.capabilities[0].capability_id)
    def test_release_family_execution_runs_registered_constructor_and_checker(self):
        family = RegisteredFamilyProgram(
            "fixture_family", ("fixture.adapter/v1",),
            "fixture.constructor/v1", "fixture.checker/v1",
            lambda value: {"answer": value},
            lambda artifact, expected: artifact == {"answer": expected})
        binding = BoundFamilyProgram(
            family.family_id, "fixture.capability", "fixture.adapter/v1",
            "fixture.generator/v1", "fixture.oracle/v1",
            family.constructor_ref, family.checker_ref)
        artifact = execute_bound_family_program(
            FamilyProgramRegistry((family,)), binding,
            construct_args=(7,), check_args=(7,))
        self.assertEqual(artifact, {"answer": 7})
    def test_release_family_execution_rejects_checker_disagreement(self):
        family = RegisteredFamilyProgram(
            "fixture_family", ("fixture.adapter/v1",),
            "fixture.constructor/v1", "fixture.checker/v1",
            lambda value: value, lambda _artifact, _expected: False)
        binding = BoundFamilyProgram(
            family.family_id, "fixture.capability", "fixture.adapter/v1",
            "fixture.generator/v1", "fixture.oracle/v1",
            family.constructor_ref, family.checker_ref)
        with self.assertRaises(ValueError):
            execute_bound_family_program(
                FamilyProgramRegistry((family,)), binding,
                construct_args=(7,), check_args=(7,))
