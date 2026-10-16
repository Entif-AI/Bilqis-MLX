"""MLX typed-answer capability parity on a disposable 222-token toy model."""
import math
from pathlib import Path
import unittest

from bilqis_mlx.pedagogical_parity import build_plan, predecessor_teaching_batch
from bilqis_mlx.typed_answer_training import (
    evaluate_rows, prepare_typed_batches, typed_objective, typed_step,
)


ROOT = Path(__file__).resolve().parents[2] / "bilqis-triplets-v16"


class TypedAnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = build_plan(ROOT)

    def setUp(self):
        import mlx.core as mx
        import numpy as np
        import mlx.optimizers as optim
        mx.set_default_device(mx.cpu)
        rng = np.random.default_rng(27)
        d = 12
        shapes = {"embedding.weight": (222, d), "position.weight": (96, d),
                  "norm.weight": (d,), "blocks.0.n1.weight": (d,),
                  "blocks.0.n2.weight": (d,),
                  "blocks.0.qkv.weight": (3*d, d),
                  "blocks.0.proj.weight": (d, d),
                  "blocks.0.up.weight": (2*d, d),
                  "blocks.0.down.weight": (d, 2*d)}
        self.mx = mx
        self.parameters = {name: mx.array(
            rng.normal(0, 0.025, shape).astype(np.float32)
            if len(shape) == 2 else np.ones(shape, dtype=np.float32))
            for name, shape in shapes.items()}
        self.optimizer = optim.AdamW(learning_rate=.00013, bias_correction=True)
        self.rows = [self.plan["pairs"]["train"][4]["rows"][0],
                     *self.plan["pairs"]["train"][4]["rows"][1:]]

    def test_numeric_and_five_class_evidence_have_separate_heads(self):
        batches = prepare_typed_batches(self.rows, self.plan["heads"])
        self.assertEqual(set(batches), {"numeric_0_3", "evidence"})
        self.assertEqual(batches["numeric_0_3"]["gold_labels"], ["3"])
        self.assertEqual(batches["evidence"]["gold_labels"], ["TRUE", "FALSE"])
        self.assertEqual(len(batches["numeric_0_3"]["answer_ids"]), 4)
        self.assertEqual(len(batches["evidence"]["answer_ids"]), 5)

    def test_wrong_answer_caste_fails_before_optimizer_mutation(self):
        from copy import deepcopy
        broken = deepcopy(self.rows)
        broken[0]["gold"] = "TRUE"
        with self.assertRaisesRegex(ValueError, "ANSWER_CASTE"):
            prepare_typed_batches(broken, self.plan["heads"])
        self.assertEqual(int(self.optimizer.state["step"].item()), 0)
        self.assertEqual(set(self.optimizer.state), {"step", "learning_rate"})
        broken = deepcopy(self.rows)
        broken[1]["answer_kind"] = "numeric_full_101"
        with self.assertRaisesRegex(ValueError, "ANSWER_CASTE"):
            prepare_typed_batches(broken, self.plan["heads"])

    def test_one_joint_toy_update_preserves_original_model_geometry(self):
        before = evaluate_rows(self.mx, self.parameters, self.rows,
                               self.plan["heads"], {"heads": 3, "layers": 1})
        self.assertEqual(set(before), {"numeric_0_3", "evidence"})
        value = typed_objective(self.mx, self.parameters, self.rows,
                                self.plan["heads"], {"heads": 3, "layers": 1})
        self.assertTrue(math.isfinite(float(value.item())))
        loss, norm = typed_step(self.mx, self.parameters, self.optimizer,
                                self.rows, self.plan["heads"],
                                {"heads": 3, "layers": 1})
        self.assertTrue(math.isfinite(loss))
        self.assertTrue(math.isfinite(norm))
        self.assertEqual(int(self.optimizer.state["step"].item()), 1)
        self.assertEqual(self.parameters["embedding.weight"].shape, (222, 12))
        self.assertEqual(set(self.optimizer.state)-{"learning_rate", "step"},
                         set(self.parameters))

    def test_full_101_numeric_probe_is_distinct_from_four_way_learning(self):
        four = evaluate_rows(self.mx, self.parameters, self.rows,
                             self.plan["heads"], {"heads": 3, "layers": 1})
        full = evaluate_rows(self.mx, self.parameters, self.rows,
                             self.plan["heads"], {"heads": 3, "layers": 1},
                             numeric_scope="numeric_full_101")
        self.assertEqual(four["numeric_0_3"]["answer_classes"], 4)
        self.assertEqual(full["numeric_full_101"]["answer_classes"], 101)
        self.assertEqual(int(self.optimizer.state["step"].item()), 0)
        self.assertEqual(set(self.optimizer.state), {"step", "learning_rate"})

    def test_tied_numeric_and_evidence_logits_match_predecessor_torch(self):
        import sys
        import numpy as np
        import torch
        from bilqis_mlx.mlx_parity import forward

        root = str(ROOT.resolve())
        if root not in sys.path:
            sys.path.insert(0, root)
        from bilqis_ref.model import ModelConfig
        from bilqis_micro.model import MicroStudent
        from bilqis_school.numeric_answer_contract import readout
        torch.manual_seed(27)
        config = ModelConfig(vocab_size=222, context=96, width=12,
                             heads=3, layers=1, expansion=2, precision="fp32")
        model = MicroStudent(config)
        model.eval()
        source_rows = self.plan["pairs"]["train"][4]["rows"]
        for row,kind in ((source_rows[0], "numeric_0_3"),
                         (source_rows[1], "evidence")):
            tokens = torch.tensor([row["tokens"]], dtype=torch.long)
            lengths = torch.tensor([len(row["tokens"])], dtype=torch.long)
            with torch.no_grad():
                expected = readout(model, tokens, lengths,
                    answer_kind="numeric" if kind == "numeric_0_3" else "evidence",
                    number_ids=self.plan["heads"]["numeric_0_3"]["token_ids"]).numpy()
            weights = {key: self.mx.array(value.detach().numpy())
                       for key,value in model.state_dict().items()}
            actual = forward(self.mx,weights,tokens.numpy(),lengths.numpy(),
                             heads=3,layers=1,
                             answer_ids=self.plan["heads"][kind]["token_ids"])
            self.assertEqual(expected.shape, actual.shape)
            self.assertLessEqual(float(np.max(np.abs(actual-expected))), .0002)

    def test_whole_predecessor_batch_trains_typed_without_collapsing_five_states(self):
        group = predecessor_teaching_batch(ROOT, grade="B01", seed=2001,
                                            method="standard")
        self.assertFalse(group["training_authorized"])
        rows = group["rows"]
        self.assertTrue({"UNKNOWN", "AMBIGUOUS"} <=
                        {r["gold"] for r in rows})
        batches = prepare_typed_batches(rows, self.plan["heads"])
        self.assertEqual({name: len(batch["row_ids"])
                          for name,batch in batches.items()},
                         {"evidence": 42, "numeric_0_3": 6})
        loss, _ = typed_step(self.mx, self.parameters, self.optimizer,
                             rows, self.plan["heads"],
                             {"heads": 3, "layers": 1})
        self.assertTrue(math.isfinite(loss))
        self.assertEqual(int(self.optimizer.state["step"].item()), 1)


if __name__ == "__main__":
    unittest.main()
