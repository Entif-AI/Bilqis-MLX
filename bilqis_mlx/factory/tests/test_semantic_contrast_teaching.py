from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.teaching import (
    describe_delivered_teaching,
    draw_teaching_option_rows,
)
from bilqis_mlx.factory.semantic_contrasts import (
    CHOICE_REGISTRY_KEY,
    OPTION_ID,
    AllowedVariation,
    ContrastFamily,
    ContrastTeachingChoice,
    check_contrast_row,
    contrast_semantic_footprint,
    enrich_contrasts,
)
from bilqis_mlx.factory.tests.test_semantic_contrasts import source_frame


class SemanticContrastTeacherBridgeTests(unittest.TestCase):
    def choice(self):
        return ContrastTeachingChoice(
            source_frame(),
            ContrastFamily.ROLE_SWAP,
            (AllowedVariation.role_swap(
                "actor", "patient", query_role="actor"),),
            "semantic-role",
            ("role.actor", "role.patient"),
        )

    def release(self):
        execution = SimpleNamespace(
            capability_id="A.CONTRAST",
            prerequisites=(),
            provider_id="fixture.semantic-contrast/v1",
            provider_implementation_sha256="a" * 64,
            variation_axes=("source-valid", "semantic-contrast"),
            teaching_option_ids=(OPTION_ID,),
            answer_families=(SimpleNamespace(
                kind="semantic-role",
                values=("urn:test:alice", "urn:test:bob")),),
            grade_id="A",
            stage=1,
        )
        return SimpleNamespace(
            verify=lambda: None,
            curriculum=SimpleNamespace(capability_map={
                "A.CONTRAST": SimpleNamespace(
                    taught_roots=("role.actor", "role.patient")),
            }),
            execution_plan=SimpleNamespace(
                capability_map={"A.CONTRAST": execution},
                capabilities=(execution,),
                grades=(SimpleNamespace(grade_id="A"),),
            ),
        )

    def adapter(self):
        return SimpleNamespace(
            descriptor=SimpleNamespace(
                teaching_option_ids=(OPTION_ID,)),
            enrich=enrich_contrasts,
            check=check_contrast_row,
            semantic_footprint=contrast_semantic_footprint,
        )

    def test_contrast_choice_runs_through_existing_factory_teaching_option_interface(self):
        graph = {CHOICE_REGISTRY_KEY: {"A.CONTRAST": self.choice()}}
        release = self.release()
        with patch(
            "bilqis_mlx.factory.teaching.runtime_adapter_for_release",
            return_value=self.adapter(),
        ):
            rows = draw_teaching_option_rows(
                None, graph, release, None,
                capability="A.CONTRAST",
                option_id=OPTION_ID,
                seed=7,
                each=1,
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gold"], "urn:test:bob")
        self.assertEqual(rows[0]["capability"], "A.CONTRAST")
        self.assertTrue(check_contrast_row(rows[0], graph=graph))

        delivery = describe_delivered_teaching(
            release, "A.CONTRAST", OPTION_ID, rows)
        self.assertEqual(delivery.option_id, OPTION_ID)
        self.assertEqual(delivery.specimen_ids, (rows[0]["id"],))

    def test_teacher_bridge_is_seed_reproducible_and_does_not_mutate_source(self):
        choice = self.choice()
        graph = {CHOICE_REGISTRY_KEY: {"A.CONTRAST": choice}}
        first = enrich_contrasts(
            graph=graph, capability="A.CONTRAST", seed=11, option_id=OPTION_ID)
        second = enrich_contrasts(
            graph=graph, capability="A.CONTRAST", seed=11, option_id=OPTION_ID)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["source_id"], choice.source_frame.frame.occurrence_id)

    def test_existing_teacher_source_checker_rejects_tampered_gold(self):
        graph = {CHOICE_REGISTRY_KEY: {"A.CONTRAST": self.choice()}}
        row = enrich_contrasts(
            graph=graph, capability="A.CONTRAST", seed=7, option_id=OPTION_ID)[0]
        self.assertFalse(check_contrast_row(
            {**row, "gold": "urn:test:alice"}, graph=graph))

    def test_existing_instructional_closure_rejects_foreign_semantic_root(self):
        graph = {CHOICE_REGISTRY_KEY: {
            "A.CONTRAST": replace(self.choice(), source_roots=("foreign.root",)),
        }}
        with patch(
            "bilqis_mlx.factory.teaching.runtime_adapter_for_release",
            return_value=self.adapter(),
        ):
            with self.assertRaisesRegex(
                ValueError, "FACTORY_INSTRUCTIONAL_CONSTITUENT_CLOSURE",
            ):
                draw_teaching_option_rows(
                    None, graph, self.release(), None,
                    capability="A.CONTRAST",
                    option_id=OPTION_ID,
                    seed=7,
                    each=1,
                )

    def test_bridge_refuses_unreleased_or_untyped_choices(self):
        graph = {CHOICE_REGISTRY_KEY: {"A.CONTRAST": self.choice()}}
        with self.assertRaises(Exception):
            enrich_contrasts(
                graph=graph, capability="A.CONTRAST", seed=1,
                option_id="source.not-released/v1")
        with self.assertRaises(Exception):
            enrich_contrasts(
                graph={CHOICE_REGISTRY_KEY: {"A.CONTRAST": "not-typed"}},
                capability="A.CONTRAST", seed=1, option_id=OPTION_ID)


if __name__ == "__main__":
    unittest.main()
