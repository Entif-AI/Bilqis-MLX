from dataclasses import replace
import unittest

from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.tests.events.support import (
    EventCandidateRealizationFixture,
    LEGACY,
)
from bilqis_mlx.source_adapters import copular_curriculum, event_frames


class EventCandidateOrderingTests(EventCandidateRealizationFixture, unittest.TestCase):
    def test_event_grade_container_is_selected_from_structure_not_grade_name(self):
        curriculum = self.current.curriculum
        relabel = {"A": "D", "B": "A", "C": "B"}
        relabeled = replace(
            curriculum,
            grades=tuple(
                replace(grade, grade_id=relabel[grade.grade_id])
                for grade in curriculum.grades
            ),
        )
        relabeled_profile = replace(
            self.current.profile,
            grades=tuple(
                replace(grade, grade_id=relabel[grade.grade_id])
                for grade in self.current.profile.grades
            ),
        )
        relabeled_current = compile_executable_factory_release(
            relabeled, self.current.source_bindings, relabeled_profile,
            self.source_registry, self.answer_registry,
            source_root=LEGACY, graph=self.parent_graph, verification_seed=2026110704,
        )
        self.assertEqual(event_frames.event_grade_id(curriculum), "D")
        self.assertEqual(event_frames.event_grade_id(relabeled), "C")
        staged = candidate_realizations.prepare_realized_candidate(
            self.frontier, relabeled_current, self.parent_graph,
            event_frames.atlas_semantic_id("D.EVENT_OCCURRENCE"),
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        self.assertEqual(staged.target_capability_id, "D.EVENT_OCCURRENCE")
        self.assertEqual(staged.successor.transition.added_capabilities,
                         ("D.EVENT_OCCURRENCE",))
        self.assertIn(
            "D.EVENT_OCCURRENCE",
            staged.successor.execution_plan.grade_map["C"].capabilities,
        )

    def test_event_first_preserves_later_copular_activation(self):
        occurrence = candidate_realizations.prepare_realized_candidate(
            self.frontier, self.current, self.parent_graph,
            event_frames.atlas_semantic_id("D.EVENT_OCCURRENCE"),
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        graph = candidate_realizations.admitted_candidate_graph(
            occurrence, self.parent_graph)
        current = occurrence.successor
        copular = candidate_realizations.prepare_realized_candidate(
            self.frontier, current, graph, copular_curriculum.atlas_semantic_id(),
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        self.assertEqual(copular.successor.transition.added_capabilities,
                         (copular_curriculum.CAPABILITY,))
        self.assertEqual(
            copular.successor.semantic_catalog[len(current.semantic_catalog):], ())
        self.assertNotEqual(
            next(grade.grade_id for grade in copular.successor.curriculum.grades
                 if copular_curriculum.CAPABILITY in {
                     cap.capability_id for cap in grade.capabilities}),
            next(grade.grade_id for grade in current.curriculum.grades
                 if "D.EVENT_OCCURRENCE" in {
                     cap.capability_id for cap in grade.capabilities}),
        )

    def test_copular_first_preserves_later_event_activation(self):
        copular = candidate_realizations.prepare_realized_candidate(
            self.frontier, self.current, self.parent_graph,
            copular_curriculum.atlas_semantic_id(),
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        graph = candidate_realizations.admitted_candidate_graph(
            copular, self.parent_graph)
        occurrence = candidate_realizations.prepare_realized_candidate(
            self.frontier, copular.successor, graph,
            event_frames.atlas_semantic_id("D.EVENT_OCCURRENCE"),
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        self.assertEqual(occurrence.successor.transition.added_capabilities,
                         ("D.EVENT_OCCURRENCE",))


if __name__ == "__main__":
    unittest.main()
