"""A08.3 semantic-family rule registry contracts."""
import unittest

from bilqis_mlx.factory.curriculum.capability_identity import CapabilityIdentityInput
from bilqis_mlx.factory.curriculum.rule_registry import (
    BOOLEAN_COVERAGE,
    NUMERIC_COVERAGE,
    WORLD_COVERAGE,
    SemanticRuleRegistry,
    default_semantic_rule_registry,
    world_rule_profile,
)
from bilqis_mlx.semantics.cognitive_operators.registry import default_registry
from bilqis_mlx.semantics.foundation.core import Signature
from bilqis_mlx.source_adapters.world_rules import registered_adapter


class SemanticRuleRegistryTests(unittest.TestCase):
    RELEASE = "a" * 64

    def test_boolean_and_integer_rules_are_keyed_without_grade(self):
        registry = default_semantic_rule_registry(self.RELEASE)
        boolean = registry.require(CapabilityIdentityInput(
            "legacy:cogal.operator.AND", "boolean_composition", "BOOL_AND",
            Signature(("Boolean", "Boolean"), "Boolean"),
            ("binary",),
        ))
        numeric = registry.require(CapabilityIdentityInput(
            "bilqis.numeric/v1:school.op.ADD", "numeric_composition", "ADD",
            Signature(("Number", "Number"), "Number"),
            ("integer",),
        ))
        self.assertEqual(boolean.coverage, BOOLEAN_COVERAGE)
        self.assertEqual(numeric.coverage, NUMERIC_COVERAGE)
        self.assertEqual(
            boolean.operator_ids,
            ("BOOL_AND", "BOOL_IFF", "BOOL_IMPLIES", "BOOL_OR", "BOOL_XOR"),
        )
        self.assertEqual(numeric.operator_ids, ("ADD", "DIV", "MOD", "MUL", "SUB"))
        self.assertFalse(any(
            token in repr(item).lower()
            for item in registry.profiles
            for token in ("grade_a", "grade_b", "grade_c")
        ))

    def test_signature_and_answer_modality_are_part_of_lookup_key(self):
        registry = default_semantic_rule_registry(self.RELEASE)
        with self.assertRaisesRegex(
                ValueError, "FACTORY_SEMANTIC_RULE_MISSING"):
            registry.require(CapabilityIdentityInput(
                "legacy:cogal.operator.AND", "boolean_composition", "BOOL_AND",
                Signature(("Boolean", "Boolean"), "Boolean"),
                ("integer",),
            ))

    def test_world_profile_requires_and_binds_source_owned_world_authority(self):
        operators = default_registry(self.RELEASE)
        with self.assertRaisesRegex(ValueError,
                                    "FACTORY_WORLD_RULE_SOURCE_AUTHORITY_UNAVAILABLE"):
            world_rule_profile(operators)
        profile = world_rule_profile(operators, registered_adapter())
        self.assertEqual(profile.coverage, WORLD_COVERAGE)
        self.assertEqual(profile.source_adapter_id, "source.bamf.qualified-world/v1")
        self.assertEqual(
            profile.operator_ids,
            ("BEFORE", "IS_OCCURRED", "ROLE_LOOKUP"))
        self.assertEqual(
            profile.source_capability_ids,
            ("WORLD.ACTOR_OF", "WORLD.BEFORE", "WORLD.DIRECT_CAUSE",
             "WORLD.IS_OCCURRED"))
        registry = default_semantic_rule_registry(
            self.RELEASE, registered_adapter())
        self.assertEqual(
            {item.identity.family_id for item in registry.profiles},
            {"boolean_composition", "numeric_composition",
             "qualified_world_model"})

    def test_registry_rejects_duplicate_semantic_keys(self):
        registry = default_semantic_rule_registry(self.RELEASE)
        with self.assertRaisesRegex(
                ValueError, "FACTORY_SEMANTIC_RULE_DUPLICATE"):
            SemanticRuleRegistry(
                registry.version,
                (registry.profiles[0], registry.profiles[0]),
            )


if __name__ == "__main__":
    unittest.main()
