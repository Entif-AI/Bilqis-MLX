"""The training path uses full-vocabulary numeric answers without inference gold."""
from copy import deepcopy
import unittest

from bilqis_mlx.typed_answer_training import predict_rows
from bilqis_mlx.runtime.tests.test_typed_answer_training import TypedAnswerTests


class SchoolNumericAnswersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TypedAnswerTests.setUpClass.__func__(cls)

    setUp = TypedAnswerTests.setUp
    def test_numeric_inference_never_reads_gold_or_native_target(self):
        row = self.rows[0]
        inputs = [{key: row[key] for key in ("id", "tokens", "answer_kind")}]
        expected = predict_rows(self.mx, self.parameters, inputs,
            self.plan["heads"], {"heads": 3, "layers": 1})
        changed = deepcopy(inputs)
        changed[0].update(gold="untrusted-answer", native_output={"token_id": -1})
        self.assertEqual(predict_rows(self.mx, self.parameters, changed,
            self.plan["heads"], {"heads": 3, "layers": 1}), expected)
        self.assertEqual(set(expected), {row["id"]})
