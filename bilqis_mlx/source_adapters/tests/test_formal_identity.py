import unittest
from unittest.mock import patch

from bilqis_mlx.source_adapters import copular, event_frames, world_rules
from bilqis_mlx.source_adapters.formal_identity import (
    OperatorDispositionKind,
    source_operator_disposition,
)


class SourceOperatorDispositionTests(unittest.TestCase):
    def test_existing_boolean_and_numeric_coordinates_are_operator_dispositions(self):
        boolean = source_operator_disposition(
            "B.AND", "source.micro.boolean-connectives/v1")
        self.assertIs(boolean.kind, OperatorDispositionKind.OPERATOR)
        self.assertEqual(boolean.operator_id, "BOOL_AND")
        self.assertEqual(boolean.semantic_root, "cogal.operator.AND")

        for capability_id, operator_id in (
            ("C.COUNT", "COUNT"),
            ("C.SUCCESSOR", "SUCC"),
            ("C.ADD", "ADD"),
            ("C.SUB", "SUB"),
            ("C.MUL", "MUL"),
            ("C.DIV", "DIV"),
        ):
            with self.subTest(capability_id=capability_id):
                numeric = source_operator_disposition(
                    capability_id, "source.finite-numeric/v2")
                self.assertIs(numeric.kind, OperatorDispositionKind.OPERATOR)
                self.assertEqual(numeric.operator_id, operator_id)
                self.assertEqual(numeric.semantic_root, "school.op." + operator_id)

        number = source_operator_disposition(
            "C.NUMBER", "source.finite-numeric/v2")
        self.assertIs(number.kind, OperatorDispositionKind.NON_OPERATOR)
        self.assertIsNone(number.operator_id)
        self.assertIsNone(number.semantic_root)
        self.assertIsNone(source_operator_disposition(
            "C.MOD", "source.finite-numeric/v2"))

        for capability_id, adapter_id in (
            ("B.COMPOSITE", "source.micro.boolean-composite/v1"),
            ("B.IDBOOLOPS", "source.micro.boolean-identification/v1"),
        ):
            with self.subTest(capability_id=capability_id):
                derived = source_operator_disposition(capability_id, adapter_id)
                self.assertIs(derived.kind, OperatorDispositionKind.NON_OPERATOR)
                self.assertIsNone(derived.operator_id)
                self.assertIsNone(derived.semantic_root)

    def test_event_and_copular_operators_are_source_owned(self):
        event = source_operator_disposition(
            "D.EVENT_OCCURRENCE", event_frames.ADAPTER_ID)
        self.assertIs(event.kind, OperatorDispositionKind.OPERATOR)
        self.assertEqual(
            event.operator_id, event_frames.SYMBOLS["D.EVENT_OCCURRENCE"])
        self.assertEqual(event.semantic_root, event.operator_id)
        self.assertEqual(
            event.implementation_sha256,
            event_frames.registered_adapter().descriptor.implementation_sha256)

        identity = source_operator_disposition(
            copular.CAPABILITY, "source.ithkuil-reference-identity/v1")
        self.assertIs(identity.kind, OperatorDispositionKind.OPERATOR)
        self.assertEqual(identity.operator_id, copular.SYMBOL)
        self.assertEqual(identity.semantic_root, copular.SYMBOL)

    def test_world_operator_and_non_operator_are_explicit(self):
        occurred = source_operator_disposition(
            "WORLD.IS_OCCURRED", "source.bamf.qualified-world/v1")
        self.assertIs(occurred.kind, OperatorDispositionKind.OPERATOR)
        self.assertEqual(occurred.operator_id, "IS_OCCURRED")
        self.assertEqual(
            occurred.semantic_root,
            "ithkuil:LEXSENSE-294d00be074a56")

        disposition = source_operator_disposition(
            "WORLD.ACTOR_OF", "source.bamf.qualified-world/v1")
        self.assertIs(disposition.kind, OperatorDispositionKind.NON_OPERATOR)
        self.assertIsNone(disposition.operator_id)
        self.assertIsNone(disposition.semantic_root)
        self.assertEqual(disposition.generator_id, world_rules.GENERATOR)
        self.assertEqual(disposition.accepted_oracle_ids, (world_rules.ORACLE,))

        for capability_id in (
            "WORLD.ACTOR_OF", "WORLD.BEFORE", "WORLD.DIRECT_CAUSE",
        ):
            with self.subTest(capability_id=capability_id):
                non_operator = source_operator_disposition(
                    capability_id, "source.bamf.qualified-world/v1")
                self.assertIs(
                    non_operator.kind, OperatorDispositionKind.NON_OPERATOR)
                self.assertIsNone(non_operator.operator_id)

    def test_unknown_source_has_no_operator_authority(self):
        self.assertIsNone(source_operator_disposition(
            "Z.UNKNOWN", "source.unknown/v1"))

    def test_new_known_world_capability_is_not_inferred_non_operator(self):
        with patch.object(
            world_rules,
            "CAPABILITIES",
            world_rules.CAPABILITIES + ("WORLD.UNCLASSIFIED",),
        ):
            self.assertIsNone(source_operator_disposition(
                "WORLD.UNCLASSIFIED", "source.bamf.qualified-world/v1"))


if __name__ == "__main__":
    unittest.main()
