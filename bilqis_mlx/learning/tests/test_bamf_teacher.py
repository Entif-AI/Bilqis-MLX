"""Pure successor binding reuses the replay teacher; no learner state is loaded."""
import copy
import random
from bilqis_mlx.errors import BilqisError
import unittest

from bilqis_mlx.learning.teacher_vnext_replay import bind_teacher_successor, select_canary
from bilqis_mlx.learning.tests.test_teacher_vnext_replay import _teacher
from bilqis_mlx.learning.teacher_strategy_population import active_effective_strategy_keys


class BamfTeacherTest(unittest.TestCase):
    def test_successor_preserves_prior_and_resets_checkpoint_local_evidence(self):
        teacher, _, _ = _teacher()
        teacher['causal_experiment']['student_policy_epoch'] = {'schema': 'bilqis.bamf.student-reference/v1', 'student_sha256': 'a' * 64, 'contexts': {'old': {'policy': 4}}}
        original = copy.deepcopy(teacher)
        epoch = bind_teacher_successor(teacher, {'schema': 'bilqis.bamf.student-reference/v1', 'student_sha256': 'b' * 64, 'region': 'new-region'},
            {'schema': 'bilqis.bamf.teacher-binding/v1', 'source_head': 'd21797e72365bf93ea7cad3a4ef9020ec9817f23', 'prior_region': 'old-region'})
        current = epoch.teacher()
        self.assertEqual(epoch.prior_teacher(), original)
        self.assertEqual(teacher, original)
        self.assertEqual(current['strategies'], original['strategies'])
        self.assertEqual(current['causal_experiment']['contexts'], {})
        self.assertEqual(current['causal_experiment']['student_policy_epoch']['student_sha256'], 'b' * 64)
        self.assertEqual(current['causal_experiment']['student_policy_epoch']['contexts'], {})
        self.assertEqual(epoch.prior_region, 'old-region')
        self.assertEqual(epoch.current_region, 'new-region')
        active, inventory = active_effective_strategy_keys(current, '', {})
        self.assertLessEqual(len(active), 16)
        self.assertEqual(set(inventory), set(active))
        canary = select_canary(current, capability='C.ADD', phase='RECOVERY_1', curriculum_scope='factory/7',
            candidate_ordinal=4, rng=random.Random(17), active_effective_policy_keys=active, inventory=inventory)
        self.assertEqual(canary['status'], 'FALLBACK_UNDERPOWERED')
        current['strategies'].clear()
        self.assertEqual(epoch.teacher()['strategies'], original['strategies'])


    def test_successor_bounds_ignore_dynamic_curriculum_size(self):
        teacher, _, _ = _teacher()
        base = next(iter(teacher['strategies'].values()))
        teacher['strategies'] = {str(i): {**base, 'lr': .00001 * (i + 1)} for i in range(30)}
        epoch = bind_teacher_successor(teacher, {'schema': 'bilqis.bamf.student-reference/v1', 'student_sha256': 'b' * 64, 'region': 'new'},
            {'schema': 'bilqis.bamf.teacher-binding/v1', 'source_head': 'd21797e72365bf93ea7cad3a4ef9020ec9817f23', 'prior_region': 'old'})
        active, _ = active_effective_strategy_keys(epoch.teacher(), '', {}, total_capabilities=20)
        self.assertLessEqual(len(active), 16)
        self.assertEqual(epoch.schema, 'bilqis.bamf.teacher-epoch/v1')

    def test_malformed_teacher_records_are_typed_failures(self):
        for mutation in ({'causal_experiment': None}, {'causal_experiment': {'student_policy_epoch': None}},
                         {'strategies': {'bad': None}}):
            teacher, _, _ = _teacher()
            with self.subTest(mutation=mutation), self.assertRaises(BilqisError):
                bind_teacher_successor({**teacher, **mutation}, {'schema': 'bilqis.bamf.student-reference/v1', 'student_sha256': 'b' * 64, 'region': 'new'},
                    {'schema': 'bilqis.bamf.teacher-binding/v1', 'source_head': 'd21797e72365bf93ea7cad3a4ef9020ec9817f23', 'prior_region': 'old'})


if __name__ == '__main__':
    unittest.main()
