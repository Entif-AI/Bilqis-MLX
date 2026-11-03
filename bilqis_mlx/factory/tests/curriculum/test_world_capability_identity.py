from __future__ import annotations

from types import MappingProxyType
from unittest.mock import patch
import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.curriculum.capability_identity import (
    bind_factory_release_capability_identity,
)
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.skos_curriculum.inventory import _inventory_source_families
from bilqis_mlx.factory.skos_curriculum.programs.contracts import (
    FactoryReleaseFamilyBindings, FamilyProgramCoverage,
)
from bilqis_mlx.factory.skos_curriculum.registry import (
    bind_existing_family_program, default_family_program_registry,
)
from bilqis_mlx.factory.tests.sources.test_skos_curriculum import _snapshot
from bilqis_mlx.semantics.cognitive_operators import default_registry
from bilqis_mlx.semantics.foundation.core import Signature
from bilqis_mlx.source_adapters.world_rules import (
    GENERATOR, ORACLE, registered_adapter,
)


ROOTS = MappingProxyType({
    "WORLD.ACTOR_OF": "ithkuil:ATOM-5d7116db8e1508",
    "WORLD.BEFORE": "ithkuil:ATOM-ef7cf17b427af9",
    "WORLD.IS_OCCURRED": "ithkuil:LEXSENSE-294d00be074a56",
    "WORLD.DIRECT_CAUSE": "ithkuil:LEXSENSE-59819df75e3137",
})
OPERATORS = MappingProxyType({"WORLD.IS_OCCURRED": "IS_OCCURRED"})


def _release(grade_id: str):
    adapter = registered_adapter()
    capabilities = tuple(Capability(
        capability_id, "qualified-world",
        "repo:lib/ithkuil/_data/csv/lexicon_root_senses.csv",
        (root,), (root,), (), (), (AnswerFamily("binary", BINARY),),
        GENERATOR, ORACLE,
    ) for capability_id, root in ROOTS.items())
    course = Course(
        (Grade(grade_id, capabilities, "1" * 64,
               tuple((item.id, 12) for item in capabilities),
               (tuple(item.id for item in capabilities),)),),
        "bamf-a08-world-identity/v1", "2" * 64, "3" * 64)
    registry = SourceAdapterRegistry((adapter,))
    return compile_factory_release(course, registry), registry


def _bindings(release, source_registry, census):
    family = default_family_program_registry().require("qualified_world_model")
    programs = {item.capability_id: item for item in release.construction_programs}
    capability = next(item for item in release.capabilities
                      if item.capability_id == "WORLD.IS_OCCURRED")
    bound = (bind_existing_family_program(
        family, capability, programs[capability.capability_id], source_registry,
        semantic_roots=release.course.capability_map[
            capability.capability_id].examined_roots,
    ),)
    coverage = FamilyProgramCoverage(
        census.semantic_release, census.digest, (), census.counts.source_held_rows)
    return FactoryReleaseFamilyBindings(
        release.release_sha256, census.semantic_release, census.digest,
        bound, coverage)


class WorldCapabilityIdentityTests(unittest.TestCase):
    def test_world_rules_use_canonical_stable_typed_identity(self):
        snapshot = _snapshot()
        census = _inventory_source_families(snapshot)
        registry = default_registry(census.semantic_release)
        release, sources = _release("D")
        bindings = _bindings(release, sources, census)
        with patch.multiple(
            "bilqis_mlx.factory.curriculum.capability_identity",
            inventory_source_families=lambda _atlas: census,
            assert_family_inventory_current=lambda *_args: None,
        ):
            binding = bind_factory_release_capability_identity(
                release, bindings, "WORLD.IS_OCCURRED", object(), registry)
        identity = binding.stable_identity.identity
        self.assertEqual(identity.semantic_id, ROOTS["WORLD.IS_OCCURRED"])
        self.assertEqual(identity.family_id, "qualified_world_model")
        self.assertEqual(identity.operator_id, OPERATORS["WORLD.IS_OCCURRED"])
        self.assertEqual(
            identity.signature, Signature(("EventStatus",), "Boolean"))
        self.assertEqual(identity.answer_kinds, ("binary",))

    def test_world_stable_identity_is_grade_neutral(self):
        snapshot = _snapshot()
        census = _inventory_source_families(snapshot)
        registry = default_registry(census.semantic_release)
        results = []
        with patch.multiple(
            "bilqis_mlx.factory.curriculum.capability_identity",
            inventory_source_families=lambda _atlas: census,
            assert_family_inventory_current=lambda *_args: None,
        ):
            for grade_id in ("D", "Z"):
                release, sources = _release(grade_id)
                bindings = _bindings(release, sources, census)
                results.append(bind_factory_release_capability_identity(
                    release, bindings, "WORLD.IS_OCCURRED", object(), registry
                ).stable_identity.capability_id)
        self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
