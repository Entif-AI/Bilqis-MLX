"""Factory training visibility through the released adapter boundary."""

from bilqis_mlx.runtime.tests.test_atlas_training_adapter import (
    AtlasTrainingAdapterTest, BilqisError, Literal, replace,
)


class TrainingVisibilityTests(AtlasTrainingAdapterTest):
    def test_hidden_gold_and_future_tokens_cannot_change_model_input(self):
        first = self.compile(self.rows).rows[0]
        changed = [{**self.rows[0], 'gold': 'TRUE', 'tokens': [1, 2, 2],
                    'auxiliary_labels': {'role': 'different'},
                    'feature_requests': [('LEAKED_GOLD_TRUE', 'bad', 'bad', 'bad')]}]
        second = self.compile(changed).rows[0]
        self.assertEqual(first.model_input, second.model_input)
        self.assertNotEqual(first.target.value, second.target.value)

    def test_ineligible_source_is_held_before_compilation(self):
        with self.assertRaises(BilqisError):
            self.compile(self.rows, policy='deny')

    def test_injected_eligibility_callbacks_cannot_authorize_model_input(self):
        with self.assertRaises(TypeError):
            self.compile(
                self.rows,
                extra_kwargs={
                    "check_context_eligibility":
                        lambda *_: type("Forged", (), {"digest": "e" * 64})(),
                    "eligible_source_for":
                        lambda result: (Literal("forged", "TokenSequence"),
                                        result.digest),
                })

    def test_untyped_policy_or_revoked_source_grant_fails_closed(self):
        with self.assertRaises(BilqisError) as caught:
            self.compile(
                self.rows, context_mutator=lambda task, frontier, policy:
                ("not-a-task", frontier, policy))
        self.assertEqual(
            caught.exception.context["reason"], "CONTEXT_AUTHORITY_REQUIRED")
        with self.assertRaises(BilqisError) as caught:
            self.compile(
                self.rows, context_mutator=lambda task, frontier, policy:
                (task, frontier, "DENY"))
        self.assertEqual(
            caught.exception.context["reason"], "CONTEXT_AUTHORITY_REQUIRED")
        for mutation in (
                lambda grant: replace(grant, revoked=True),
                lambda grant: replace(grant, evidence_digest="e" * 64),
        ):
            with self.subTest(mutation=mutation):
                def revoke(task, frontier, policy):
                    grants = (mutation(frontier.grants[0]), *frontier.grants[1:])
                    return task, replace(frontier, grants=grants), policy
                with self.assertRaises(BilqisError) as caught:
                    self.compile(self.rows, context_mutator=revoke)
                self.assertEqual(
                    caught.exception.context["reason"], "CONTEXT_NOT_ELIGIBLE")

    def test_unverified_frame_adapter_cannot_supply_eligibility(self):
        for frames in (lambda ast: (), lambda ast: (ast,)):
            with self.subTest(frames=frames), self.assertRaises(BilqisError) as caught:
                self.compile(self.rows, frames_override=frames)
            self.assertEqual(
                caught.exception.context["reason"], "CONTEXT_SOURCE_FRAMES_REQUIRED")

    def test_gold_only_change_cannot_reach_input_or_features(self):
        first = self.compile(self.rows).rows[0]
        second = self.compile([{**self.rows[0], 'gold': 'TRUE', 'auxiliary_labels': {'role': 'x'}}]).rows[0]
        self.assertEqual(first.model_input, second.model_input)
        self.assertNotEqual(first.target, second.target)

    def test_sealed_holdout_identity_cannot_enter_training(self):
        with self.assertRaises(BilqisError):
            self.compile(self.rows, sealed=(self.rows[0]['id'],))
