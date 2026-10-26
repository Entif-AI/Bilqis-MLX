import unittest
from types import SimpleNamespace
import random


def _prometheus_canary_fixture():
    from bilqis_mlx.learning.learning_experiment import VERSION
    from bilqis_mlx.learning.teacher_outcomes import (
        observe, proposed_action, student_region,
    )
    from bilqis_mlx.learning.teacher_strategy_population import effective_policy_key

    strategies = {
        "policy-a": {"lr": .00008, "old": 8, "preview": 0,
                     "depth": 1, "contrast": 0., "distill": .15},
        "policy-b": {"lr": .0003, "old": 20, "preview": 0,
                     "depth": 4, "contrast": 1., "distill": .65},
    }
    ordered = sorted(strategies, key=lambda key: effective_policy_key(strategies[key]))
    vnext_key, legacy_key = ordered[0], ordered[-1]
    teacher = {
        "strategies": strategies,
        "global_stats": {key: {"trials": 0, "reward_sum": 0., "reward_ema": 0.,
                               "latest": None} for key in strategies},
        "grade_stats": {}, "events": 0, "mutations": 0,
        "causal_experiment": {"version": VERSION, "contexts": {},
                              "negative_archetypes": [], "events": 0},
    }
    region = student_region(
        capability="C.SUB", phase="RECOVERY_1", lesson_grade="C",
        curriculum_scope="scope/7", geometry_epoch="integer-v1",
        numeric_maximum=7, capability_correct=20, capability_total=33,
        grade_correct=145, grade_total=165, rejection_streak=0,
        attempts_since_retained=0, mastery_debt_count=2,
        mastery_debt_capabilities=("B.AND", "C.SUB"))
    action = proposed_action(
        family="GLOBAL_CHALLENGER",
        effective_policy_key=effective_policy_key(strategies[vnext_key]),
        policy_key=vnext_key,
        parameters={"lr": strategies[vnext_key]["lr"], "old": strategies[vnext_key]["old"],
                    "distill": strategies[vnext_key]["distill"],
                    "depth": "DEEP" if strategies[vnext_key]["depth"] >= 3 else "SHALLOW",
                    "contrast": "DIVERSE" if strategies[vnext_key]["contrast"] >= .5 else "RANDOM",
                    "candidate_steps": 16, "batch_size": 32})
    for index in range(11):
        observe(
            teacher, region=region, action=action, retained=index < 4,
            rejection_reason=("PAIRED_SCREEN_WITHIN_BUDGET"
                              if index < 4 else "NO_MEASURABLE_TARGET_GAIN"),
            target_delta=2 if index < 4 else 0, protected_net_delta=0,
            worst_protected_loss=0, attempted_steps=16,
            retained_steps=16 if index < 4 else 0, wall_seconds=1.)
    receipt = {"generation": 100, "numeric_maximum": 7, "last_exam": {"scores": {
        "C.SUB": {"correct": 20, "total": 33},
        "C.COUNT": {"correct": 32, "total": 33}}}}
    school = SimpleNamespace(
        current_student=SimpleNamespace(sha256="a" * 64),
        carried_mastery_debt=("B.AND", "C.SUB"))
    return teacher, strategies, vnext_key, legacy_key, receipt, school


class TeacherOutcomeContractTests(unittest.TestCase):
    def test_student_region_generalizes_across_exact_student_and_batch_identity(self):
        from bilqis_mlx.learning.teacher_outcomes import student_region

        common = dict(
            capability="C.ADD", phase="RECOVERY_1", lesson_grade="C",
            curriculum_scope="prometheus/7/geometry=integer-v1",
            geometry_epoch="integer-v1", numeric_maximum=7,
            capability_correct=28, capability_total=33,
            grade_correct=205, grade_total=231,
            rejection_streak=5, attempts_since_retained=7,
            mastery_debt_count=3,
        )
        first = student_region(**common)
        second = student_region(**common)

        self.assertEqual(first, second)
        self.assertNotIn("student_sha256", first)
        self.assertNotIn("cohort_sha256", first)
        self.assertEqual(first["capability_score_band"], "P070_084")
        self.assertEqual(first["grade_score_band"], "P085_094")
        self.assertEqual(first["rejection_pressure_band"], "R04_07")

    def test_student_region_distinguishes_grade_and_debt_shape_without_checkpoint_identity(self):
        from bilqis_mlx.learning.teacher_outcomes import student_region

        common = dict(
            capability="B.AND", phase="MAIN", lesson_grade="B",
            curriculum_scope="scope/geometry=outer-v1",
            geometry_epoch="outer-v1", numeric_maximum=7,
            capability_correct=7, capability_total=12,
            grade_correct=65, grade_total=96,
            rejection_streak=10, attempts_since_retained=10,
        )
        historical = student_region(
            **common,
            mastery_debt_count=13,
            grade_capability_scores={
                "B.AND": (7, 12), "B.IFF": (7, 12),
                "B.IMPLIES": (6, 12), "B.IDBOOLOPS": (5, 12),
            },
            mastery_debt_capabilities=(
                "A.LINK", "A.MEMBER", "B.AND", "B.IMPLIES", "B.IFF",
                "B.COMPOSITE", "B.IDBOOLOPS", "C.COUNT", "C.NUMBER",
                "C.ADD", "C.SUB", "C.MUL", "C.DIV",
            ))
        later = student_region(
            **common,
            mastery_debt_count=17,
            grade_capability_scores={
                "B.AND": (7, 12), "B.IFF": (4, 12),
                "B.IMPLIES": (5, 12), "B.IDBOOLOPS": (8, 12),
            },
            mastery_debt_capabilities=(
                "A.LINK", "A.MEMBER", "B.NOT", "B.AND", "B.OR", "B.XOR",
                "B.IMPLIES", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS",
                "C.COUNT", "C.NUMBER", "C.SUCCESSOR", "C.ADD", "C.SUB",
                "C.MUL", "C.DIV",
            ))

        self.assertNotEqual(historical["key"], later["key"])
        self.assertNotEqual(
            historical["grade_score_shape"], later["grade_score_shape"])
        self.assertNotEqual(
            historical["mastery_debt_shape"], later["mastery_debt_shape"])
        self.assertNotIn("student_sha256", historical)

    def test_outcome_ledger_keeps_retention_gain_risk_and_cost_separate(self):
        from bilqis_mlx.learning.teacher_outcomes import (
            observe, predict, student_region,
        )

        teacher = {}
        region = student_region(
            capability="B.AND", phase="MAIN", lesson_grade="B",
            curriculum_scope="scope", geometry_epoch="atomic-v1",
            numeric_maximum=7, capability_correct=6, capability_total=12,
            grade_correct=70, grade_total=96, rejection_streak=0,
            attempts_since_retained=0, mastery_debt_count=4)
        action = {"family": "INCUMBENT_REPLAY", "effective_policy_key": "abc123"}

        observe(
            teacher, region=region, action=action, retained=False,
            rejection_reason="NO_MEASURABLE_TARGET_GAIN", target_delta=0,
            protected_net_delta=0, worst_protected_loss=0,
            attempted_steps=16, retained_steps=0, wall_seconds=2.0)
        observe(
            teacher, region=region, action=action, retained=True,
            rejection_reason="PAIRED_SCREEN_WITHIN_BUDGET", target_delta=2,
            protected_net_delta=-1, worst_protected_loss=1,
            attempted_steps=16, retained_steps=16, wall_seconds=3.0)

        estimate = predict(teacher, region=region, action=action)
        self.assertEqual(estimate["trials"], 2)
        self.assertEqual(estimate["retained"], 1)
        self.assertAlmostEqual(estimate["retention_probability"], 0.5)
        self.assertAlmostEqual(estimate["expected_target_delta"], 1.0)
        self.assertAlmostEqual(estimate["expected_protected_net_delta"], -0.5)
        self.assertAlmostEqual(estimate["expected_candidate_steps"], 16.0)
        self.assertAlmostEqual(estimate["expected_wall_seconds"], 2.5)
        self.assertLessEqual(
            estimate["retention_interval"][0], estimate["retention_probability"])
        self.assertGreaterEqual(
            estimate["retention_interval"][1], estimate["retention_probability"])

    def test_health_status_calls_prolonged_zero_yield_exhausted(self):
        from bilqis_mlx.learning.teacher_outcomes import health_summary

        observations = [
            {
                "retained": False,
                "target_delta": 0,
                "protected_net_delta": 0,
                "worst_protected_loss": 0,
                "attempted_steps": 16,
                "retained_steps": 0,
                "wall_seconds": 1.0,
            }
            for _ in range(20)
        ]
        summary = health_summary(observations)
        self.assertEqual(summary["status"], "SEARCH_NEIGHBORHOOD_EXHAUSTED")
        self.assertEqual(summary["retained_candidates"], 0)
        self.assertEqual(summary["attempted_candidates"], 20)
        self.assertEqual(summary["optimizer_steps_per_retention"], None)

    def test_shadow_ladder_waits_through_step_eight_for_late_bloomer(self):
        from bilqis_mlx.learning.teacher_multifidelity import (
            DEFAULT_SHADOW_POLICY, evaluate_shadow,
        )

        review = evaluate_shadow(
            DEFAULT_SHADOW_POLICY,
            probes=((2, 0), (4, 0), (8, 1), (16, 2)),
            final_retained=True,
            full_budget_steps=16)

        self.assertEqual(review["mode"], "SHADOW")
        self.assertIsNone(review["first_would_stop_step"])
        self.assertFalse(review["false_kill"])
        self.assertEqual(review["actual_steps_spent"], 16)
        self.assertEqual(review["shadow_steps_if_active"], 16)
        self.assertEqual(review["actual_authority_changed"], False)

    def test_shadow_ladder_stops_at_eight_after_persistent_target_inertia(self):
        from bilqis_mlx.learning.teacher_multifidelity import (
            DEFAULT_SHADOW_POLICY, evaluate_shadow,
        )

        review = evaluate_shadow(
            DEFAULT_SHADOW_POLICY,
            probes=((2, 0), (4, 0), (8, 0), (16, 0)),
            final_retained=False,
            full_budget_steps=16)

        self.assertEqual(review["first_would_stop_step"], 8)
        self.assertEqual(review["shadow_steps_if_active"], 8)
        self.assertEqual(review["shadow_steps_saved"], 8)
        self.assertFalse(review["false_kill"])

    def test_shadow_ladder_preserves_earlier_gain_even_if_step_eight_is_inert(self):
        from bilqis_mlx.learning.teacher_multifidelity import (
            DEFAULT_SHADOW_POLICY, evaluate_shadow,
        )

        review = evaluate_shadow(
            DEFAULT_SHADOW_POLICY,
            probes=((2, 0), (4, 1), (8, 0), (16, 2)),
            final_retained=True,
            full_budget_steps=16)

        self.assertIsNone(review["first_would_stop_step"])
        self.assertEqual(review["shadow_steps_if_active"], 16)
        self.assertFalse(review["false_kill"])

    def test_shadow_ladder_preserves_promising_candidate_to_full_budget(self):
        from bilqis_mlx.learning.teacher_multifidelity import (
            DEFAULT_SHADOW_POLICY, evaluate_shadow,
        )

        review = evaluate_shadow(
            DEFAULT_SHADOW_POLICY,
            probes=((2, 1), (4, 1), (8, 2), (16, 3)),
            final_retained=True,
            full_budget_steps=16)

        self.assertIsNone(review["first_would_stop_step"])
        self.assertFalse(review["false_kill"])
        self.assertEqual(review["shadow_steps_if_active"], 16)

    def test_prometheus_adapter_uses_coarse_scores_and_retained_incumbent_family(self):
        from bilqis_mlx.runtime.teacher_outcome_runtime import (
            build_action, build_region,
        )

        policy = {"lr": .0001, "old": 8, "preview": 1,
                  "depth": 3, "contrast": .5, "distill": .15}
        teacher = {
            "strategies": {"policy-1": policy},
            "causal_experiment": {
                "contexts": {
                    "C.ADD|RECOVERY_1|scope": {
                        "policy-1": {"trials": 3, "retained": 1},
                    },
                },
                "capability_stagnation": {
                    "C.ADD|scope": {
                        "rejection_streak": 2,
                        "attempts_since_retained": 2,
                    },
                },
            },
        }
        receipt = {
            "numeric_maximum": 7,
            "last_exam": {
                "scores": {
                    "C.ADD": {"correct": 28, "total": 33},
                    "C.SUB": {"correct": 30, "total": 33},
                },
            },
        }
        school = SimpleNamespace(carried_mastery_debt=("A.IDENTITY", "B.AND"))

        region = build_region(
            receipt, school, teacher, capability="C.ADD", phase="RECOVERY_1",
            lesson_grade="C", curriculum_scope="scope",
            geometry_epoch="integer-v1")
        action = build_action(
            teacher, capability="C.ADD", phase="RECOVERY_1",
            curriculum_scope="scope", policy_key="policy-1", policy=policy)

        self.assertEqual(region["capability_score_band"], "P070_084")
        self.assertEqual(region["grade_score_band"], "P085_094")
        self.assertEqual(region["mastery_debt_band"], "D01_03")
        self.assertEqual(action["family"], "INCUMBENT_REPLAY")
        self.assertNotIn("preview", action["parameters"])

    def test_prometheus_adapter_prepares_shadow_rungs(self):
        from bilqis_mlx.runtime.teacher_outcome_runtime import prepare_candidate

        policy = {"lr": .0001, "old": 8, "preview": 1,
                  "depth": 3, "contrast": .5, "distill": .15}
        teacher = {
            "strategies": {"policy-1": policy},
            "causal_experiment": {"contexts": {}, "capability_stagnation": {}},
        }
        receipt = {
            "numeric_maximum": 7,
            "last_exam": {
                "scores": {
                    "C.ADD": {"correct": 28, "total": 33},
                    "C.SUB": {"correct": 30, "total": 33},
                },
            },
        }
        school = SimpleNamespace(carried_mastery_debt=("A.IDENTITY", "B.AND"))

        prepared = prepare_candidate(
            receipt, school, teacher,
            capability="C.ADD", phase="RECOVERY_1", lesson_grade="C",
            curriculum_scope="scope", geometry_epoch="integer-v1",
            policy_key="policy-1", policy=policy,
            candidate_steps=16, batch_size=8, shadow_enabled=True)

        self.assertEqual(prepared.shadow_rungs, (2, 4, 8, 16))

    def test_shadow_proposals_mutate_locally_without_mutating_historical_archive(self):
        from bilqis_mlx.learning.teacher_proposals import candidate_proposals

        strategies = {}
        global_stats = {}
        for index, lr in enumerate((.00004, .00008, .00013, .0002, .0003)):
            key = f"policy-{index}"
            strategies[key] = {
                "old": 8, "preview": 0, "depth": 1,
                "contrast": 0., "lr": lr, "distill": 0.,
            }
            global_stats[key] = {
                "trials": 1, "reward_sum": 0., "reward_ema": 0., "latest": 0.,
            }
        teacher = {
            "strategies": strategies,
            "global_stats": global_stats,
            "grade_stats": {}, "events": 5, "mutations": 0,
            "causal_experiment": {
                "contexts": {
                    "C.ADD|MAIN|scope": {
                        "policy-0": {"trials": 4, "retained": 2,
                                     "reward_sum": 1.0, "unsafe": 2,
                                     "no_target_gain_streak": 0},
                    },
                },
            },
        }
        before = {key: dict(value) for key, value in teacher["strategies"].items()}

        proposals = candidate_proposals(
            teacher, capability="C.ADD", phase="MAIN",
            curriculum_scope="scope", candidate_steps=16, batch_size=32)

        families = {proposal["family"] for proposal in proposals}
        self.assertIn("INCUMBENT_REPLAY", families)
        self.assertIn("LOCAL_INCUMBENT_MUTATION", families)
        self.assertIn("GLOBAL_CHALLENGER", families)
        local = [proposal for proposal in proposals
                 if proposal["family"] == "LOCAL_INCUMBENT_MUTATION"]
        self.assertTrue(any(not proposal["already_in_historical_archive"]
                            for proposal in local))
        self.assertEqual(teacher["strategies"], before)

    def test_shadow_acquisition_prefers_productive_low_risk_evidence(self):
        from bilqis_mlx.learning.teacher_outcomes import (
            observe, proposed_action, student_region,
        )
        from bilqis_mlx.learning.teacher_proposals import (
            AcquisitionPolicy, acquire,
        )

        teacher = {}
        region = student_region(
            capability="C.ADD", phase="MAIN", lesson_grade="C",
            curriculum_scope="scope", geometry_epoch="integer-v1",
            numeric_maximum=7, capability_correct=20, capability_total=33,
            grade_correct=150, grade_total=198, rejection_streak=0,
            attempts_since_retained=0, mastery_debt_count=2)
        good = proposed_action(
            family="LOCAL_INCUMBENT_MUTATION", effective_policy_key="good",
            parameters={"candidate_steps": 8})
        bad = proposed_action(
            family="GLOBAL_CHALLENGER", effective_policy_key="bad",
            parameters={"candidate_steps": 16})
        productive_trials = 28
        for index in range(40):
            observe(
                teacher, region=region, action=good,
                retained=index < productive_trials,
                rejection_reason=("PAIRED_SCREEN_WITHIN_BUDGET"
                                  if index < productive_trials else "NO_MEASURABLE_TARGET_GAIN"),
                target_delta=2 if index < productive_trials else 0,
                protected_net_delta=0, worst_protected_loss=0,
                attempted_steps=8,
                retained_steps=8 if index < productive_trials else 0,
                wall_seconds=1.0)
            observe(
                teacher, region=region, action=bad,
                retained=index < 4,
                rejection_reason=("PAIRED_SCREEN_WITHIN_BUDGET"
                                  if index < 4 else "PROTECTED_CAPABILITY_REGRESSION"),
                target_delta=1 if index < 4 else 0,
                protected_net_delta=-2, worst_protected_loss=2,
                attempted_steps=16, retained_steps=16 if index < 4 else 0,
                wall_seconds=2.0)
        policy = AcquisitionPolicy(
            version="test", exploration_weight=0.,
            protected_risk_weight=1., target_prior_gain=.5)

        decision = acquire(
            teacher, region=region, proposals=(bad, good),
            rng=random.Random(7), policy=policy)

        self.assertEqual(decision["mode"], "SHADOW")
        self.assertEqual(decision["selected"]["proposal"]["key"], good["key"])
        self.assertFalse(decision["actual_authority_changed"])

    def test_multifidelity_activation_gate_stays_closed_until_shadow_is_safe(self):
        from bilqis_mlx.learning.teacher_multifidelity import (
            ActivationPolicy, qualify_activation,
        )

        policy = ActivationPolicy(
            version="test", minimum_reviews=4,
            maximum_false_kill_rate=.05,
            minimum_mean_steps_saved=2.)
        clean = {
            "mode": "SHADOW", "first_would_stop_step": 4,
            "false_kill": False, "false_continue": False,
            "shadow_steps_saved": 12,
        }
        too_little = qualify_activation((clean, clean, clean), policy=policy)
        qualified = qualify_activation((clean, clean, clean, clean), policy=policy)
        unsafe = qualify_activation((clean, clean, clean, {
            **clean, "false_kill": True,
        }), policy=policy)

        self.assertEqual(too_little["status"], "NOT_QUALIFIED")
        self.assertEqual(qualified["status"], "QUALIFIED")
        self.assertEqual(unsafe["status"], "NOT_QUALIFIED")
        self.assertEqual(unsafe["false_kill_rate"], .25)
        self.assertFalse(qualified["authority_changed"])

    def test_learned_local_distribution_can_leave_historical_strategy_grid(self):
        from bilqis_mlx.learning.teacher_distribution import (
            DistributionPolicy, learned_proposals,
        )
        from bilqis_mlx.learning.teacher_outcomes import (
            observe, proposed_action, student_region,
        )

        teacher = {}
        region = student_region(
            capability="C.ADD", phase="MAIN", lesson_grade="C",
            curriculum_scope="scope", geometry_epoch="integer-v1",
            numeric_maximum=7, capability_correct=20, capability_total=33,
            grade_correct=150, grade_total=198, rejection_streak=0,
            attempts_since_retained=0, mastery_debt_count=2)
        for lr in (.00004, .00008):
            action = proposed_action(
                family="INCUMBENT_REPLAY", effective_policy_key=str(lr),
                parameters={
                    "lr": lr, "old": 8, "depth": "SHALLOW",
                    "contrast": "DIVERSE", "distill": .15,
                    "candidate_steps": 16, "batch_size": 32,
                })
            for _ in range(4):
                observe(
                    teacher, region=region, action=action, retained=True,
                    rejection_reason="PAIRED_SCREEN_WITHIN_BUDGET",
                    target_delta=2, protected_net_delta=0,
                    worst_protected_loss=0, attempted_steps=16,
                    retained_steps=16, wall_seconds=1.)
        policy = DistributionPolicy(
            version="test", minimum_observations=8,
            minimum_retained=2, samples=1, log_lr_jitter=0.)

        result = learned_proposals(
            teacher, region=region, rng=random.Random(1), policy=policy,
            candidate_steps=16, batch_size=32)

        self.assertEqual(result["status"], "QUALIFIED")
        self.assertFalse(result["actual_authority_changed"])
        proposal = result["proposals"][0]
        self.assertEqual(proposal["family"], "LEARNED_LOCAL_DISTRIBUTION")
        self.assertGreater(proposal["parameters"]["lr"], .00004)
        self.assertLess(proposal["parameters"]["lr"], .00008)

    def test_backoff_prediction_pools_same_capability_without_aliasing_region_identity(self):
        from bilqis_mlx.learning.teacher_outcomes import (
            BackoffPolicy, observe, predict_backoff, proposed_action, student_region,
        )

        teacher = {}
        action = proposed_action(
            family="INCUMBENT_REPLAY", effective_policy_key="same-policy",
            parameters={"lr": .00013, "old": 8, "depth": "DEEP",
                        "contrast": "RANDOM", "distill": .15,
                        "candidate_steps": 16, "batch_size": 32})
        regions = []
        for rejection_streak in (0, 5):
            region = student_region(
                capability="C.SUB", phase="RECOVERY_1", lesson_grade="C",
                curriculum_scope="scope/7", geometry_epoch="integer-v1",
                numeric_maximum=7, capability_correct=20, capability_total=33,
                grade_correct=145, grade_total=165,
                rejection_streak=rejection_streak,
                attempts_since_retained=rejection_streak,
                mastery_debt_count=4,
                grade_capability_scores={"C.SUB": (20, 33), "C.COUNT": (32, 33)},
                mastery_debt_capabilities=("A.LINK", "B.AND", "C.ADD", "C.SUB"))
            regions.append(region)
            for index in range(4):
                observe(
                    teacher, region=region, action=action,
                    retained=index == 0,
                    rejection_reason=("PAIRED_SCREEN_WITHIN_BUDGET"
                                      if index == 0 else "NO_MEASURABLE_TARGET_GAIN"),
                    target_delta=1 if index == 0 else 0,
                    protected_net_delta=0, worst_protected_loss=0,
                    attempted_steps=16, retained_steps=16 if index == 0 else 0,
                    wall_seconds=1.)

        self.assertNotEqual(regions[0]["key"], regions[1]["key"])
        result = predict_backoff(
            teacher, region=regions[0], action=action,
            policy=BackoffPolicy(version="test", minimum_observations=8))

        self.assertEqual(result["trials"], 8)
        self.assertEqual(result["retained"], 2)
        self.assertEqual(result["evidence_level"], "CAPABILITY_PHASE")
        self.assertEqual(result["evidence_region_count"], 2)

    def test_learned_distribution_qualifies_from_nearest_compatible_backoff_level(self):
        from bilqis_mlx.learning.teacher_distribution import (
            DistributionPolicy, learned_proposals,
        )
        from bilqis_mlx.learning.teacher_outcomes import (
            observe, proposed_action, student_region,
        )

        teacher = {}
        regions = []
        for rejection_streak in (0, 5):
            regions.append(student_region(
                capability="B.IDBOOLOPS", phase="MAIN", lesson_grade="B",
                curriculum_scope="scope/7", geometry_epoch="boolean-v1",
                numeric_maximum=7, capability_correct=8, capability_total=12,
                grade_correct=70, grade_total=96,
                rejection_streak=rejection_streak,
                attempts_since_retained=rejection_streak,
                mastery_debt_count=3,
                mastery_debt_capabilities=("A.LINK", "B.AND", "B.IDBOOLOPS")))
        action = proposed_action(
            family="INCUMBENT_REPLAY", effective_policy_key="productive",
            parameters={"lr": .00013, "old": 8, "depth": "SHALLOW",
                        "contrast": "DIVERSE", "distill": .15,
                        "candidate_steps": 16, "batch_size": 32})
        for region in regions:
            for index in range(8):
                observe(
                    teacher, region=region, action=action,
                    retained=index < 2,
                    rejection_reason=("PAIRED_SCREEN_WITHIN_BUDGET"
                                      if index < 2 else "NO_MEASURABLE_TARGET_GAIN"),
                    target_delta=1 if index < 2 else 0,
                    protected_net_delta=0, worst_protected_loss=0,
                    attempted_steps=16, retained_steps=16 if index < 2 else 0,
                    wall_seconds=1.)
        policy = DistributionPolicy(
            version="test", minimum_observations=16,
            minimum_retained=3, samples=1, log_lr_jitter=0.)

        result = learned_proposals(
            teacher, region=regions[0], rng=random.Random(2), policy=policy,
            candidate_steps=16, batch_size=32)

        self.assertEqual(result["status"], "QUALIFIED")
        self.assertEqual(result["observations"], 16)
        self.assertEqual(result["retained"], 4)
        self.assertEqual(result["evidence_level"], "CAPABILITY_PHASE")

    def test_vnext_canary_is_bounded_and_falls_back_when_evidence_is_underpowered(self):
        from bilqis_mlx.learning.teacher_outcomes import (
            observe, proposed_action, student_region,
        )
        from bilqis_mlx.learning.teacher_proposals import select_canary_proposal

        region = student_region(
            capability="C.SUB", phase="RECOVERY_1", lesson_grade="C",
            curriculum_scope="scope/7", geometry_epoch="integer-v1",
            numeric_maximum=7, capability_correct=20, capability_total=33,
            grade_correct=145, grade_total=165, rejection_streak=2,
            attempts_since_retained=2, mastery_debt_count=2,
            mastery_debt_capabilities=("B.AND", "C.SUB"))
        teacher = {
            "strategies": {
                "good": {"lr": .00013, "old": 8, "preview": 0,
                         "depth": 3, "contrast": 0., "distill": .15},
                "bad": {"lr": .0003, "old": 20, "preview": 0,
                        "depth": 4, "contrast": 1., "distill": .65},
            },
        }
        good = proposed_action(
            family="INCUMBENT_REPLAY", effective_policy_key="placeholder",
            policy_key="good", parameters={"lr": .00013, "old": 8,
            "depth": "DEEP", "contrast": "RANDOM", "distill": .15,
            "candidate_steps": 16, "batch_size": 32})
        bad = proposed_action(
            family="GLOBAL_CHALLENGER", effective_policy_key="placeholder-2",
            policy_key="bad", parameters={"lr": .0003, "old": 20,
            "depth": "DEEP", "contrast": "DIVERSE", "distill": .65,
            "candidate_steps": 16, "batch_size": 32})

        underpowered = select_canary_proposal(
            teacher, region=region, proposals=(good, bad),
            candidate_ordinal=8, rng=random.Random(1))
        self.assertEqual(underpowered["status"], "FALLBACK_UNDERPOWERED")
        self.assertFalse(underpowered["actual_authority_changed"])

        for index in range(8):
            observe(
                teacher, region=region, action=good,
                retained=index < 3,
                rejection_reason=("PAIRED_SCREEN_WITHIN_BUDGET"
                                  if index < 3 else "NO_MEASURABLE_TARGET_GAIN"),
                target_delta=2 if index < 3 else 0,
                protected_net_delta=0, worst_protected_loss=0,
                attempted_steps=16, retained_steps=16 if index < 3 else 0,
                wall_seconds=1.)
            observe(
                teacher, region=region, action=bad,
                retained=False, rejection_reason="PROTECTED_CAPABILITY_REGRESSION",
                target_delta=0, protected_net_delta=-2, worst_protected_loss=2,
                attempted_steps=16, retained_steps=0, wall_seconds=1.)

        not_due = select_canary_proposal(
            teacher, region=region, proposals=(good, bad),
            candidate_ordinal=9, rng=random.Random(1))
        self.assertEqual(not_due["status"], "NOT_SCHEDULED")
        selected = select_canary_proposal(
            teacher, region=region, proposals=(good, bad),
            candidate_ordinal=12, rng=random.Random(1))
        self.assertEqual(selected["status"], "SELECTED")
        self.assertTrue(selected["actual_authority_changed"])
        self.assertEqual(selected["selected"]["proposal"]["policy_key"], "good")

        retired = select_canary_proposal(
            teacher, region=region, proposals=(good, bad),
            candidate_ordinal=12, rng=random.Random(1),
            allowed_effective_policy_keys={"placeholder-2"})
        self.assertEqual(retired["status"], "FALLBACK_UNDERPOWERED")
        self.assertFalse(retired["actual_authority_changed"])

    def test_prometheus_selector_canary_overrides_legacy_only_on_supported_slot(self):
        from bilqis_mlx.runtime.teacher_outcome_runtime import select_policy_and_prepare

        teacher, strategies, vnext_key, legacy_key, receipt, school = (
            _prometheus_canary_fixture())

        class LegacyEngine:
            @staticmethod
            def pick_existing(_teacher, _grade, _rng, exclude=None):
                self.assertNotIn(legacy_key, set(exclude or ()))
                return legacy_key, strategies[legacy_key]

        policy_key, _policy, selection, prepared = select_policy_and_prepare(
            LegacyEngine(), teacher, random.Random(3), receipt, school,
            capability="C.SUB", phase="RECOVERY_1", lesson_grade="C",
            curriculum_scope="scope/7", geometry_epoch="integer-v1",
            diagnostics={}, learning_settings=object(),
            candidate_steps=16, batch_size=32)

        self.assertEqual(selection["origin"], "TEACHER_VNEXT_CANARY")
        self.assertTrue(selection["actual_authority_changed"])
        self.assertEqual(selection["legacy_policy_key"], legacy_key)
        self.assertEqual(policy_key, vnext_key)
        self.assertEqual(prepared.action["policy_key"], vnext_key)


if __name__ == "__main__":
    unittest.main()
