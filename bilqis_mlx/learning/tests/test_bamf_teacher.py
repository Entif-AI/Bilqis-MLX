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


class BamfTeacherRegionTest(unittest.TestCase):
    def test_geometry_epoch_invalidates_context_and_archives_history(self):
        from dataclasses import replace
        import json
        from bilqis_mlx.learning.teacher_vnext_replay import refresh_teacher_region
        prior, _, _ = _teacher()
        epoch = bind_teacher_successor(prior,
            {'schema': 'bilqis.bamf.student-reference/v1', 'student_sha256': 'b' * 64, 'region': 'new'},
            {'schema': 'bilqis.bamf.teacher-binding/v1', 'source_head': 'd21797e72365bf93ea7cad3a4ef9020ec9817f23', 'prior_region': 'old'})
        active = epoch.teacher()
        active['causal_experiment'] = prior['causal_experiment']
        epoch = replace(epoch, current_json=json.dumps(active))
        changed = refresh_teacher_region(epoch, bank_identity='bank-2', plasticity_identity='FAST-v1')
        self.assertNotEqual(changed.current_region, epoch.current_region)
        self.assertEqual(changed.teacher()['causal_experiment']['contexts'], {})
        self.assertEqual(changed.teacher()['bamf_region_history'][-1]['evidence'], prior['causal_experiment'])
        self.assertEqual(refresh_teacher_region(changed, bank_identity='bank-2', plasticity_identity='FAST-v1'), changed)
        self.assertEqual(changed.prior_teacher(), prior)

    def test_shadow_ladder_does_not_issue_execution_authority(self):
        from bilqis_mlx.learning.teacher_multifidelity import DEFAULT_SHADOW_POLICY, evaluate_shadow
        review = evaluate_shadow(DEFAULT_SHADOW_POLICY, probes=((2, 0), (4, 0), (8, 0), (16, 1)),
                                 final_retained=True, full_budget_steps=16)
        self.assertEqual(review['mode'], 'SHADOW')
        self.assertFalse(review['actual_authority_changed'])
        self.assertEqual(review['actual_steps_spent'], 16)
        self.assertEqual(review['rungs'], [2, 4, 8, 16])

    def test_typed_mentor_votes_are_source_gold_gated(self):
        import numpy as np
        from bilqis_mlx.learning.champion_confidence import vote_targets_typed
        logits = np.array([[0., 10.], [0., 10.]])
        original = logits.copy()
        _, weight = vote_targets_typed(((1, logits),), np.array([1, 0]), classes=2,
                                      eligible_capabilities=1, teacher_distill=1.)
        self.assertGreater(weight[0], 0)
        self.assertEqual(weight[1], 0)
        self.assertTrue(np.array_equal(logits, original))

    def test_health_comes_from_recorded_outcome_counts(self):
        from bilqis_mlx.learning.teacher_observations import summarize_observations
        report = summarize_observations([{'retention': {'value': 'RETAINED'},
            'attempted_steps': 4, 'retained_steps': 4, 'wall_seconds': 2.0}])
        self.assertEqual(report['observation_count'], 1)
        self.assertEqual(report['retention_yield']['value'], 1.)
        self.assertEqual(report['wall_seconds']['value'], 2.)


if __name__ == '__main__':
    unittest.main()
