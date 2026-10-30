"""Registry import controls: a spreadsheet planning row is not a train permit."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bilqis_mlx.curriculum_compiler import compile_ast
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.registry_ast import (bind_course_tokens, load_registry,
                                      parse_registry, stage_plan,
                                      construction_frontier, compiler_report)


ROOT = Path(__file__).resolve().parents[4]
SNAPSHOT = ROOT / 'docs/provenance/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json'
MANIFEST = ROOT / 'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json'


class RegistryASTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry(SNAPSHOT)
        cls.course = compile_ast(accepted_grade_a(json.loads(MANIFEST.read_text())))

    def test_real_sheet_snapshot_has_individually_bound_semantic_ids(self):
        graph = self.registry
        self.assertEqual(len(graph.tokens), 222)
        self.assertEqual(len(graph.lessons), 111)
        self.assertEqual(len(graph.bridges), 330)
        self.assertEqual(len(graph.grades), 14)
        self.assertEqual(len(graph.prerequisites), 54)
        self.assertEqual(len(graph.supplemental_constraints), 22)
        self.assertEqual(len(graph.prerequisites) + len(graph.supplemental_constraints), 76)
        self.assertEqual(tuple(t.id for t in graph.tokens), tuple(range(222)))
        self.assertEqual(graph.tokens[42].symbol, 'micro.compare.EQ')
        self.assertEqual(graph.tokens[42].identity, 'legacy:micro.compare.EQ')
        self.assertEqual(graph.lessons[0].origin.tab, 'Lessons')
        self.assertEqual(graph.lessons[0].origin.row, 2)
        self.assertEqual(graph.digest(), load_registry(SNAPSHOT).digest())

    def test_old_letter_alias_is_not_the_new_training_grade_a(self):
        grade_a = stage_plan(self.registry, 'A')
        self.assertFalse(grade_a.training_authorized)
        self.assertIn('HISTORICAL CONTINUITY', grade_a.status)
        self.assertEqual(grade_a.lessons, ())
        self.assertTrue(any('HISTORICAL' in x for x in grade_a.blockers))

    def test_next_proposed_stage_is_an_actual_dependency_ordered_work_plan(self):
        plan = stage_plan(self.registry, 'C')
        self.assertFalse(plan.training_authorized)
        self.assertEqual([x.id for x in plan.lessons],
                         ['LESSON-058', 'LESSON-059', 'LESSON-060',
                          'LESSON-061', 'LESSON-062'])
        self.assertEqual(plan.lessons[2].requires_lessons, ('LESSON-059',))
        self.assertEqual(plan.lessons[2].requires_grades, ('A', 'B'))
        self.assertTrue(any('A' in x and 'B' in x for x in plan.blockers))
        self.assertEqual(plan.digest(), stage_plan(self.registry, 'C').digest())

    def test_frontier_derives_next_authoring_step_from_explicit_dependencies(self):
        plan = stage_plan(self.registry, 'C')
        initial = construction_frontier(plan)
        self.assertEqual(sum(t.ready_to_construct for t in initial), 0)
        supplied = construction_frontier(plan, mastered_grades=('A', 'B'))
        self.assertEqual([t.id for t in supplied if t.ready_to_construct], ['LESSON-058'])
        self.assertFalse(supplied[0].training_authorized)
        progress = construction_frontier(plan, mastered_grades=('A', 'B'),
                                         constructed_lessons=('LESSON-058',))
        self.assertEqual([t.id for t in progress if t.ready_to_construct], ['LESSON-059'])
        self.assertIn('number tokens', progress[0].instruction.lower())

    def test_grade_a_semantics_bind_to_same_222_historical_tokens(self):
        bound = bind_course_tokens(self.course, self.registry)
        self.assertEqual(len(bound), 6)
        self.assertEqual(bound['A.IDENTITY'], (42,))
        self.assertEqual(bound['A.PARENT'], (34,))
        self.assertEqual(bound['A.LINK'], (36,))
        self.assertEqual(bound['A.MEMBER'], (88,))
        self.assertEqual(bound['A.MAPS'], (96,))
        self.assertEqual(bound['A.EDGE'], (98,))

    def test_token_swap_and_duplicate_identity_fail_closed(self):
        original = json.loads(SNAPSHOT.read_text())
        forged = deepcopy(original)
        table = forged['tabs']['Token Atlas']['rows']
        table[42][1], table[43][1] = table[43][1], table[42][1]
        with self.assertRaisesRegex(ValueError, 'TOKEN_IDENTITY_DRIFT'):
            parse_registry(forged)
        forged = deepcopy(original)
        forged['tabs']['Token Atlas']['rows'][2][2] = 'legacy:syntax.pad'
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_TOKEN_IDENTITY'):
            parse_registry(forged)

    def test_forged_prerequisite_and_missing_lesson_fail_closed(self):
        original = json.loads(SNAPSHOT.read_text())
        forged = deepcopy(original)
        # C's second lesson: introduce a forward dependency on C's last lesson.
        forged['tabs']['Prerequisites']['rows'][17][10] = 'LESSON-062'
        with self.assertRaisesRegex(ValueError, 'FORWARD_OR_CYCLIC_LESSON_DEPENDENCY'):
            parse_registry(forged)
        forged = deepcopy(original)
        forged['tabs']['Lessons']['rows'][58][1] = 'LESSON-999'
        with self.assertRaisesRegex(ValueError, 'UNRESOLVED_LESSON_REFERENCE'):
            parse_registry(forged)

    def test_sheet_status_must_not_authorize_neural_training(self):
        forged = json.loads(SNAPSHOT.read_text())
        forged['tabs']['Grade Tranches']['rows'][3][7] = 'TRAINING APPROVED'
        plan = stage_plan(parse_registry(forged), 'C')
        self.assertFalse(plan.training_authorized)
        self.assertTrue(plan.blockers)

    def test_mood_pragmatics_are_still_blocked_by_extra_prerequisite_rows(self):
        plan = stage_plan(self.registry, 'J')
        self.assertTrue(any('UNCOMPILED_QUALIFICATION_CONSTRAINTS' in b
                            for b in plan.blockers))
        self.assertFalse(plan.training_authorized)
        self.assertFalse(any(t.ready_to_construct for t in construction_frontier(
            plan, mastered_grades=tuple('ABCDEFGHI'),
            constructed_lessons=())))

    def test_sheet_column_reorder_refuses_to_reinterpret_status(self):
        forged = json.loads(SNAPSHOT.read_text())
        head = forged['tabs']['Lessons']['rows'][0]
        head[8], head[9] = head[9], head[8]
        with self.assertRaisesRegex(ValueError, 'HEADER_DRIFT'):
            parse_registry(forged)

    def test_compiler_report_combines_verified_old_tokens_and_future_frontier(self):
        report = compiler_report(SNAPSHOT)
        self.assertEqual(report['registered_semantic_tokens'], 222)
        self.assertEqual(report['recorded_prerequisite_rows'], 76)
        self.assertEqual(report['unreleased_grade_a_source_probe_plans'], 96)
        self.assertEqual(report['active_grade_a_token_binding']['A.IDENTITY'], (42,))
        self.assertFalse(report['training_authorized_by_this_report'])
        self.assertEqual(report['neural_optimizer_updates'], 0)
        self.assertEqual(sum(t['ready_to_construct'] for t in
                             report['proposed_construction_tasks']), 0)

    def test_hypothetical_frontier_cannot_erase_admission_gate(self):
        report = compiler_report(SNAPSHOT, assumed_mastered_grades=('A', 'B'))
        ready = [t['id'] for t in report['proposed_construction_tasks']
                 if t['ready_to_construct']]
        self.assertEqual(ready, ['LESSON-058'])
        self.assertFalse(report['training_authorized_by_this_report'])


if __name__ == '__main__':
    unittest.main()
