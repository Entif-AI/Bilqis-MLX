"""Warm arithmetic answers cannot answer a checkpoint's examination."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import numpy as np

from bilqis_mlx import trainer, typed_answer_training
from bilqis_mlx.generated_assessment import make_cohort, score
from bilqis_mlx.semantics.foundation.numeric import calculate, evaluate, number
from bilqis_mlx.verification.numeric import independent_value


class SourceMemoExamTests(TestCase):
    def test_numeric_inference_ignores_even_a_warm_answer_and_conflicting_gold(self):
        expression = calculate("ADD", number(1), number(1))
        self.assertEqual(evaluate(expression), 2)
        self.assertEqual(independent_value(expression), 2)
        row = {"id": "same-equation", "capability": "C.ADD", "gold": "2",
               "answer_kind": "numeric_active", "tokens": [1, 2]}
        heads = {"semantic_token": {"values": ["school.number." + str(i) for i in range(4)],
                                    "token_ids": list(range(4))},
                 "numeric_active": {"values": [str(i) for i in range(4)], "token_ids": list(range(4))}}
        config = {"heads": 1, "layers": 1, "answer_heads": heads}
        mx = SimpleNamespace(eval=lambda *_: None)
        measured = []

        def network(_mx, parameters, ids, lengths, **_kwargs):
            self.assertEqual(ids.tolist(), [[1, 2]])
            self.assertEqual(lengths.tolist(), [2])
            return np.eye(4)[[parameters["answer"]]]

        with patch.object(typed_answer_training, "forward_arrays", side_effect=network) as forward:
            for answer in (0, 2, 1):
                weights = {"embedding.weight": np.zeros((4, 1)), "answer": answer}
                measured.append(trainer._predictions(mx, weights, [row], config, [0, 1]))
            conflicting = trainer._predictions(mx, weights, [{**row, "gold": "0"}], config, [0, 1])
        self.assertEqual(forward.call_count, 4)
        self.assertEqual([result[row["id"]] for result in measured], ["0", "2", "1"])
        self.assertEqual(conflicting, measured[-1])

    def test_warm_source_cache_still_requires_each_checkpoints_network_answer(self):
        expression = calculate("EQ", calculate("ADD", number(1), number(1)), number(2))
        evaluate.cache_clear()
        independent_value.cache_clear()
        self.assertIs(evaluate(expression), True)
        self.assertIs(independent_value(expression), True)
        row = {"id": "same-equation", "capability": "C.ADD", "gold": "TRUE",
               "tokens": [1, 2], "record": {"display": "1 + 1 = 2"}}
        cohort = make_cohort([row], generator_version="fixture/v1", seed=1,
                             rubric_version="fixture/v1")
        mx = SimpleNamespace(eval=lambda *_: None)
        config = {"heads": 1, "layers": 1}
        calls = []

        def network(_mx, parameters, ids, lengths, **kwargs):
            calls.append(parameters["identity"])
            self.assertEqual(ids.tolist(), [[1, 2]])
            self.assertEqual(lengths.tolist(), [2])
            self.assertEqual(kwargs["answer_ids"], [6, 7])
            return np.array([[0., 1.]] if parameters["correct"] else [[1., 0.]])

        results = []
        with patch('bilqis_mlx.runtime.mlx_parity.forward_arrays', side_effect=network):
            for identity, correct in (("weak", False), ("strong", True), ("later-weak", False)):
                predictions = trainer._predictions(
                    mx, {"identity": identity, "correct": correct}, [row], config, [6, 7])
                results.append(score(cohort, predictions, {
                    "sha256": identity, "optimizer_step": len(results),
                    "model_and_native_adamw": True})["scores"]["C.ADD"]["correct"])
        self.assertEqual(calls, ["weak", "strong", "later-weak"])
        self.assertEqual(results, [0, 1, 0])
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_PREDICTIONS"):
            score(cohort, {}, {"sha256": "missing", "optimizer_step": 4,
                              "model_and_native_adamw": True})
