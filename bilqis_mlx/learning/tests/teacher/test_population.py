"""Population."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, _active_effective_strategy_keys, _effective_policy_key,
    contextual_pick, decide, observe_context, random,
    strategy_population_teacher,
)


class PopulationTests(CausalTeacherExperimentTests):
    def test_preview_only_variants_share_effective_context_evidence(self):
        common = {
            "contrast": .5, "depth": 2, "distill": .15,
            "lr": .00008, "old": 12,
        }
        teacher = {
            "strategies": {
                "preview0": {**common, "preview": 0},
                "preview4": {**common, "preview": 4},
                "legacy": {
                    "contrast": 1., "depth": 4, "distill": .65,
                    "lr": .0003, "old": 4, "preview": 2,
                },
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 0., "reward_ema": 0.,
                      "latest": 0.}
                for key in ("preview0", "preview4", "legacy")
            },
            "grade_stats": {},
            "events": 60,
        }
        mild_reject = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        for key in ("preview0", "preview4"):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_2",
                policy_key=key, decision=mild_reject, local_gain=0.,
                curriculum_scope="scope")

        worse_reject = decide({
            "C.SUB": {"before": 22, "after": 18, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        for _ in range(2):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_2",
                policy_key="legacy", decision=worse_reject, local_gain=-.4,
                curriculum_scope="scope")

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "legacy", _teacher["strategies"]["legacy"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope")
        self.assertIn(picked, {"preview0", "preview4"})

    def test_active_strategy_population_is_bounded_and_preserves_proven_incumbent(self):
        teacher = strategy_population_teacher()
        proven = "policy-023"
        retained = decide({
            "C.ADD": {"before": 3, "after": 5, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        for _ in range(5):
            observe_context(
                teacher, capability="C.ADD", phase="MAIN",
                policy_key=proven, decision=retained, local_gain=.4,
                curriculum_scope="scope")
        scope = teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"]

        active, inventory = _active_effective_strategy_keys(
            teacher, "C", scope)

        self.assertLessEqual(len(active), 16)
        self.assertGreater(len(inventory), len(active))
        self.assertIn(
            _effective_policy_key(teacher["strategies"][proven]), active)

    def test_contextual_pick_keeps_strategy_archive_immutable(self):
        import bilqis_mlx.compatibility.historical_teacher_policy as policy_engine
        teacher = strategy_population_teacher()
        before_keys = set(teacher["strategies"])
        before_mutations = teacher["mutations"]

        for seed in range(12):
            contextual_pick(
                policy_engine, teacher, "C.ADD", "MAIN", random.Random(seed),
                curriculum_scope="scope")

        self.assertEqual(set(teacher["strategies"]), before_keys)
        self.assertEqual(teacher["mutations"], before_mutations)
        _, _, metadata = contextual_pick(
            policy_engine, teacher, "C.ADD", "MAIN", random.Random(99),
            curriculum_scope="scope", return_metadata=True)
        self.assertEqual(
            metadata["selection_policy"],
            "bilqis.mlx.teacher-selection/349-replay-v1")
