from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY
from bilqis_mlx.factory.answers import (
    AnswerModality,
    AnswerModalityRegistry,
    RegisteredAnswerModality,
    fixed_domain,
)
from bilqis_mlx.factory.curriculum_definition import (
    CapabilitySourceBinding,
    CapabilitySpec,
    CurriculumDefinition,
    GradeSpec,
    SourceBindingSet,
)
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.semantic_contrasts import (
    CHOICE_REGISTRY_KEY,
    OPTION_ID,
    AllowedVariation,
    ContrastFamily,
    ContrastTeachingChoice,
    check_contrast_row,
    enrich_contrasts,
)
from bilqis_mlx.factory.teaching import (
    describe_delivered_teaching,
    draw_teaching_option_rows,
)
from bilqis_mlx.factory.tests.semantic_contrast.test_semantic_contrasts import source_frame
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.source_adapters import event_frames
from bilqis_mlx.source_adapters.school import live_source_registry


CAPABILITY = "D.EVENT_OCCURRENCE"


def _answers():
    return AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality("binary", "answer.binary/v1", "a" * 64),
            fixed_domain(BINARY),
            lambda value: {
                "FALSE": "cogal.value.false",
                "TRUE": "cogal.value.true",
            }[value],
        ),
    ))


class SemanticContrastTeacherBridgeTests(unittest.TestCase):
    def setUp(self):
        self.registry = live_source_registry()
        self.graph = event_frames.expanded_graph(registry_graph())
        sense = event_frames.source_senses()[CAPABILITY]
        self.curriculum = CurriculumDefinition(
            "bamf-a11-teacher-bridge/v1",
            (GradeSpec(
                "A",
                (CapabilitySpec(
                    CAPABILITY,
                    "finite-event-frame",
                    (event_frames.SYMBOLS[CAPABILITY],),
                    (event_frames.SYMBOLS[CAPABILITY],),
                    (),
                    (),
                    (AnswerFamily("binary", BINARY),),
                ),),
                ((CAPABILITY, 4),),
                ((CAPABILITY,),),
            ),),
        )
        self.bindings = SourceBindingSet((
            CapabilitySourceBinding(
                CAPABILITY,
                "ithkuil:sense/" + sense["lexicon_sense_id"]
                + "@sha256:" + sense["source_text_sha256"],
                event_frames.GENERATOR,
                event_frames.ORACLE,
            ),
        ))
        self.release = compile_executable_factory_release(
            self.curriculum,
            self.bindings,
            CurriculumProfile.full(),
            self.registry,
            _answers(),
            source_root=None,
            graph=self.graph,
            verification_seed=426,
        )

    def choice(self):
        source = replace(
            source_frame(),
            source_morphology="TRUE",
            authorized_morphology_alternatives=("TRUE", "FALSE"),
        )
        return ContrastTeachingChoice(
            source,
            ContrastFamily.MORPHOLOGY_ALTERNATIVE,
            (AllowedVariation.morphology("FALSE"),),
            "binary",
            (event_frames.SYMBOLS[CAPABILITY],),
        )

    def graph_with_choice(self):
        return {
            **self.graph,
            CHOICE_REGISTRY_KEY: {CAPABILITY: self.choice()},
        }

    def test_real_event_frame_release_contains_semantic_contrast_teaching_option(self):
        execution = self.release.execution_plan.capability_map[CAPABILITY]
        self.assertEqual(execution.provider_id, "source.ithkuil-event-frames/v1")
        self.assertIn(OPTION_ID, execution.teaching_option_ids)
        adapter = self.registry.require(event_frames.GENERATOR, event_frames.ORACLE)
        self.assertIs(adapter.enrich, enrich_contrasts)

    def test_provider_identity_binds_semantic_contrast_teaching_implementation(self):
        baseline = event_frames.provider_implementation_digest()
        drifted = event_frames.provider_implementation_digest({
            "factory/semantic_contrast/teaching.py": b"drifted teaching implementation",
        })
        self.assertNotEqual(baseline, drifted)
        self.assertEqual(
            event_frames.registered_adapter().descriptor.implementation_sha256,
            baseline,
        )

    def test_release_rejects_semantic_contrast_provider_identity_drift(self):
        adapter = event_frames.registered_adapter()
        drifted = replace(
            adapter,
            descriptor=replace(
                adapter.descriptor,
                implementation_sha256="f" * 64,
            ),
        )
        registry = SourceAdapterRegistry((drifted,))
        with self.assertRaisesRegex(
            ValueError, "FACTORY_TEACHING_PROVIDER_DRIFT",
        ):
            draw_teaching_option_rows(
                None,
                self.graph_with_choice(),
                self.release,
                registry,
                capability=CAPABILITY,
                option_id=OPTION_ID,
                seed=7,
                each=1,
            )

    def test_contrast_choice_runs_through_real_factory_teaching_option_interface(self):
        graph = self.graph_with_choice()
        rows = draw_teaching_option_rows(
            None,
            graph,
            self.release,
            self.registry,
            capability=CAPABILITY,
            option_id=OPTION_ID,
            seed=7,
            each=1,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gold"], "FALSE")
        self.assertEqual(rows[0]["capability"], CAPABILITY)
        self.assertTrue(check_contrast_row(rows[0], graph=graph))
        delivery = describe_delivered_teaching(
            self.release, CAPABILITY, OPTION_ID, rows)
        self.assertEqual(delivery.option_id, OPTION_ID)
        self.assertEqual(delivery.specimen_ids, (rows[0]["id"],))

    def test_direct_event_frame_generation_remains_exact_count_and_oracle_checked(self):
        rows = event_frames.draw(
            None, self.graph, seed=426, each=12, capability=CAPABILITY)
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(event_frames.check(row, graph=self.graph) for row in rows))

    def test_contrast_source_checker_binds_gold_metadata_and_roots(self):
        graph = self.graph_with_choice()
        row = enrich_contrasts(
            graph=graph, capability=CAPABILITY, seed=7, option_id=OPTION_ID)[0]
        self.assertTrue(check_contrast_row(row, graph=graph))
        self.assertFalse(check_contrast_row(
            {**row, "gold": "TRUE"}, graph=graph))
        self.assertFalse(check_contrast_row(
            {**row, "answer_kind": "other-family"}, graph=graph))
        self.assertFalse(check_contrast_row(
            {**row, "source_roots": ("foreign.root",)}, graph=graph))

    def test_instructional_closure_rejects_foreign_contrast_root(self):
        graph = {
            **self.graph,
            CHOICE_REGISTRY_KEY: {
                CAPABILITY: replace(
                    self.choice(), source_roots=("foreign.root",)),
            },
        }
        with self.assertRaisesRegex(
            ValueError, "FACTORY_INSTRUCTIONAL_CONSTITUENT_CLOSURE",
        ):
            draw_teaching_option_rows(
                None,
                graph,
                self.release,
                self.registry,
                capability=CAPABILITY,
                option_id=OPTION_ID,
                seed=7,
                each=1,
            )


if __name__ == "__main__":
    unittest.main()
