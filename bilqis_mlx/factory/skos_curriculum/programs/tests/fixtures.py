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


ADAPTER = "bilqis.fixture-source/v1"
GENERATOR = "bilqis.fixture-generator/v1"
ORACLE = "bilqis.fixture-oracle/v1"


def _source_registry(oracle=ORACLE):
    descriptor = SourceAdapter(
        ADAPTER, GENERATOR, (oracle,), "a" * 64,
        teaching_option_ids=("fixture:teach",))
    return SourceAdapterRegistry((RegisteredSourceAdapter(
        descriptor, lambda **_: (), lambda *_args, **_kwargs: True),))


def _family(name="boolean_composition"):
    return RegisteredFamilyProgram(
        name, (ADAPTER,), "fixture.constructor/v1", "fixture.checker/v1",
        lambda *args, **kwargs: args, lambda *args, **kwargs: True)


def _capability(grade="B", capability_id="B.AND"):
    return CapabilityDefinition(
        capability_id, grade, ("A.IDENTITY",), ADAPTER, ORACLE,
        ("BOOLEAN",))


def _program(capability_id="B.AND", oracle=ORACLE):
    return ConstructionProgram(
        capability_id, ADAPTER, GENERATOR, oracle, ("A.IDENTITY",))
