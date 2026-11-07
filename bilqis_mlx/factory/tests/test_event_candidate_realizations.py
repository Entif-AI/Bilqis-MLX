import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.compatibility.executable_projection import compile_projected_executable_release
from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.factory.candidate_frontier import load_candidate_frontier
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.source_adapters import event_frames
from bilqis_mlx.source_adapters.school import live_source_registry


ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / 'vendor/legacy-v16'


class EventCandidateRealizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        output = Path(cls.temp.name)
        builder = ROOT / 'lib/ithkuil/src/build_curriculum_frontier.py'
        subprocess.run(
            [sys.executable, str(builder)], check=True, capture_output=True,
            env={**os.environ, 'BILQIS_CURRICULUM_FRONTIER_OUT': str(output)},
        )
        cls.frontier = load_candidate_frontier(
            output, ROOT / 'lib/ithkuil/_data/csv',
            expected_builder_sha256=hashlib.sha256(builder.read_bytes()).hexdigest(),
        )
        cls.parent_graph = registry_graph()
        course = accepted_grade_a(json.loads(
            (ROOT / 'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json').read_text()))
        cls.current, _, _ = compile_projected_executable_release(
            course, course, LEGACY, cls.parent_graph)
        cls.source_registry = live_source_registry()
        cls.answer_registry = live_answer_registry()

    def test_three_source_qualified_event_successors_stage_successively(self):
        current = self.current
        graph = self.parent_graph
        observed = []
        for index, capability in enumerate(event_frames.SOURCE_SPECS):
            staged = candidate_realizations.prepare_realized_candidate(
                self.frontier, current, graph, event_frames.atlas_semantic_id(capability),
                source_root=LEGACY, source_registry=self.source_registry,
                answer_registry=self.answer_registry,
            )
            self.assertEqual(staged.source_sense_id,
                             event_frames.SOURCE_SPECS[capability].sense_id)
            self.assertEqual(staged.successor.transition.added_capabilities, (capability,))
            expected = (event_frames.SYMBOLS[capability],)
            if index == 0:
                from bilqis_mlx.source_adapters import copular_curriculum
                expected = (
                    copular_curriculum.PROJECTION_ADMISSION_TOKEN,
                    *expected,
                )
            self.assertEqual(
                staged.successor.semantic_catalog[len(current.semantic_catalog):],
                expected,
            )
            graph = candidate_realizations.admitted_candidate_graph(staged, graph)
            current = staged.successor
            observed.append(capability)
        self.assertEqual(tuple(observed), tuple(event_frames.SOURCE_SPECS))

    def test_each_successive_event_stage_restarts_as_the_same_candidate(self):
        from bilqis_mlx.runtime.candidate_staging import (
            load_staged_candidates, persist_staged_candidate,
        )

        current = self.current
        graph = self.parent_graph
        for capability in event_frames.SOURCE_SPECS:
            staged = candidate_realizations.prepare_realized_candidate(
                self.frontier, current, graph, event_frames.atlas_semantic_id(capability),
                source_root=LEGACY, source_registry=self.source_registry,
                answer_registry=self.answer_registry,
            )
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                persist_staged_candidate(root, staged, self.frontier, current)
                self.assertEqual(
                    load_staged_candidates(root, self.frontier, current),
                    (staged,),
                )
            graph = candidate_realizations.admitted_candidate_graph(staged, graph)
            current = staged.successor

    def test_event_atlas_projection_and_source_identity_share_one_owner(self):
        current = self.current
        graph = self.parent_graph
        for index, capability in enumerate(event_frames.SOURCE_SPECS):
            semantic_id = event_frames.atlas_semantic_id(capability)
            added, identities = candidate_realizations.project_realized_target(
                semantic_id, current)
            self.assertEqual(added, (capability,))
            expected = (event_frames.SYMBOLS[capability],)
            if index == 0:
                from bilqis_mlx.source_adapters import copular_curriculum
                expected = (
                    copular_curriculum.PROJECTION_ADMISSION_TOKEN,
                    *expected,
                )
            self.assertEqual(identities, expected)
            self.assertEqual(
                candidate_realizations.realized_source_sense_id(semantic_id),
                event_frames.SOURCE_SPECS[capability].sense_id,
            )
            staged = candidate_realizations.prepare_realized_candidate(
                self.frontier, current, graph, semantic_id,
                source_root=LEGACY, source_registry=self.source_registry,
                answer_registry=self.answer_registry,
            )
            self.assertEqual(
                staged.successor.semantic_catalog[len(current.semantic_catalog):],
                identities,
            )
            graph = candidate_realizations.admitted_candidate_graph(staged, graph)
            current = staged.successor

    def test_foreign_same_name_event_row_cannot_be_reused_as_source_authority(self):
        graph = event_frames.projected_graph(
            self.parent_graph, ('D.EVENT_OCCURRENCE',))
        token = event_frames.SYMBOLS['D.EVENT_OCCURRENCE']
        index = graph['tokens'].index(token)
        foreign = dict(graph['nodes'][index], semantic_id='foreign:event-occurrence')
        graph['nodes'][index] = foreign
        graph['row_contract_sha256'][token] = hashlib.sha256(json.dumps(
            foreign, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
            allow_nan=False).encode()).hexdigest()
        with self.assertRaises(BilqisError):
            event_frames.projected_graph(graph, ('D.EVENT_OCCURRENCE',))

    def test_event_grade_container_is_selected_from_structure_not_grade_name(self):
        from bilqis_mlx.factory.executable_release import compile_executable_factory_release

        curriculum = self.current.curriculum
        relabel = {'A': 'D', 'B': 'A', 'C': 'B'}
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
        self.assertEqual(event_frames.event_grade_id(curriculum), 'D')
        self.assertEqual(event_frames.event_grade_id(relabeled), 'C')
        staged = candidate_realizations.prepare_realized_candidate(
            self.frontier, relabeled_current, self.parent_graph,
            event_frames.atlas_semantic_id('D.EVENT_OCCURRENCE'),
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        self.assertEqual(staged.target_capability_id, 'D.EVENT_OCCURRENCE')
        self.assertEqual(
            staged.successor.transition.added_capabilities,
            ('D.EVENT_OCCURRENCE',),
        )
        self.assertIn(
            'D.EVENT_OCCURRENCE',
            staged.successor.execution_plan.grade_map['C'].capabilities,
        )

    def test_event_first_preserves_later_copular_activation(self):
        from bilqis_mlx.source_adapters import copular_curriculum

        occurrence = candidate_realizations.prepare_realized_candidate(
            self.frontier, self.current, self.parent_graph,
            event_frames.atlas_semantic_id('D.EVENT_OCCURRENCE'),
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
                 if 'D.EVENT_OCCURRENCE' in {
                     cap.capability_id for cap in grade.capabilities}),
        )

    def test_copular_first_preserves_later_event_activation(self):
        from bilqis_mlx.source_adapters import copular_curriculum

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
            event_frames.atlas_semantic_id('D.EVENT_OCCURRENCE'),
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        self.assertEqual(occurrence.successor.transition.added_capabilities,
                         ('D.EVENT_OCCURRENCE',))

    def test_frontier_source_order_does_not_change_event_successor(self):
        from dataclasses import replace

        semantic_id = event_frames.atlas_semantic_id('D.EVENT_OCCURRENCE')
        expected = candidate_realizations.prepare_realized_candidate(
            self.frontier, self.current, self.parent_graph, semantic_id,
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        reversed_frontier = replace(
            self.frontier, candidates=tuple(reversed(self.frontier.candidates)))
        reversed_frontier = replace(
            reversed_frontier,
            release_sha256=reversed_frontier.expected_digest(),
        )
        observed = candidate_realizations.prepare_realized_candidate(
            reversed_frontier, self.current, self.parent_graph, semantic_id,
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        self.assertEqual(observed.candidate_id, expected.candidate_id)
        self.assertEqual(observed.successor, expected.successor)


if __name__ == '__main__':
    unittest.main()
