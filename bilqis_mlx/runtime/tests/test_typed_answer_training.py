"""Disposable typed-answer fixtures with the original frozen historical prefix.

The actual live Bilqis vocabulary is sourced from its evolving semantic graph,
not the size of this deliberately synthetic, predecessor-compatible fixture.
"""
import math
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.pedagogical_parity import build_plan, predecessor_teaching_batch
from bilqis_mlx.typed_answer_training import (
    evaluate_rows, prepare_typed_batches, typed_objective, typed_step,
)


ROOT = Path(__file__).resolve().parents[3] / "vendor" / "legacy-v16"


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
        self.assertEqual(set(batches), {"numeric_0_3", "evidence", "semantic_token"})
        self.assertEqual(batches["numeric_0_3"]["gold_labels"], ["3"])
        self.assertEqual(batches["evidence"]["gold_labels"], ["TRUE", "FALSE"])
        self.assertEqual(len(batches["numeric_0_3"]["answer_ids"]), 4)
        self.assertEqual(len(batches["evidence"]["answer_ids"]), 5)
        self.assertEqual(batches["semantic_token"]["answer_ids"], list(range(222)))
        target = self.plan["heads"]["semantic_token"]["values"].index("school.number.3")
        self.assertEqual(batches["semantic_token"]["target_indices"], [target])
        self.assertEqual(batches["semantic_token"]["row_ids"],
                         batches["numeric_0_3"]["row_ids"])

    def test_native_semantic_token_identity_is_not_a_four_class_label(self):
        head = self.plan["heads"]["semantic_token"]
        self.assertEqual(len(head["values"]), 222)
        self.assertEqual(head["token_ids"], list(range(222)))
        binding = self.rows[0]["native_output"]
        self.assertEqual(binding["identity"], "school.number.3")
        self.assertEqual(binding["token_id"], head["values"].index("school.number.3"))

    def test_incorrect_native_target_binding_is_rejected(self):
        for scenario in ("missing", "wrong_id", "wrong_name", "different_label"):
            with self.subTest(scenario=scenario):
                rows=deepcopy(self.rows)
                if scenario == "missing":
                    rows[0].pop("native_output")
                elif scenario == "wrong_id":
                    rows[0]["native_output"]["token_id"] = 7
                elif scenario == "wrong_name":
                    rows[0]["native_output"]["identity"] = "school.number.2"
                else:
                    rows[0]["gold"] = "2"
                with self.assertRaisesRegex(ValueError,"ANSWER_CASTE"):
                    prepare_typed_batches(rows,self.plan["heads"])
        self.assertEqual(int(self.optimizer.state["step"].item()),0)

    def test_loss_includes_full_vocab_and_both_restricted_answer_heads(self):
        import numpy as np
        from bilqis_mlx.runtime.mlx_parity import forward_arrays
        batches=prepare_typed_batches(self.rows,self.plan["heads"])
        manual=[]
        for part in batches.values():
            z=np.asarray(forward_arrays(self.mx,self.parameters,part["ids"],
                part["lengths"],heads=3,layers=1,answer_ids=part["answer_ids"]))
            largest=z.max(axis=-1)
            correct=z[np.arange(len(z)),part["target_indices"]]
            cross_entropy=(largest+np.log(np.exp(z-largest[:,None]).sum(axis=-1))
                           -correct).mean()
            manual.append(float(cross_entropy))
        self.assertEqual(len(manual),3)
        actual=typed_objective(self.mx,self.parameters,self.rows,
                               self.plan["heads"],{"heads":3,"layers":1})
        self.assertAlmostEqual(float(actual.item()),sum(manual)/3,places=4)

    def test_unrestricted_token_loss_avoids_quadratic_one_hot_allocation(self):
        with patch("bilqis_mlx.typed_answer_training.np.eye",
                   side_effect=AssertionError("DENSE_VOCAB_ONE_HOT")):
            loss=typed_objective(self.mx,self.parameters,self.rows,
                                 self.plan["heads"],{"heads":3,"layers":1})
        self.assertTrue(math.isfinite(float(loss.item())))

    def test_vocab_growth_never_silently_truncates_native_output_head(self):
        # Vocabulary growth must not inherit a silently narrowed output head.
        heads=deepcopy(self.plan["heads"])
        enlarged=dict(self.parameters)
        extra=self.mx.zeros((1,12),dtype=self.mx.float32)
        enlarged["embedding.weight"]=self.mx.concatenate(
            (self.parameters["embedding.weight"],extra),axis=0)
        with self.assertRaisesRegex(ValueError,"ANSWER_CASTE_MODEL_FULL_VOCAB"):
            evaluate_rows(self.mx,enlarged,self.rows,heads,{"heads":3,"layers":1})
        heads["semantic_token"]["values"].append("fixture.additional.source-attested")
        heads["semantic_token"]["token_ids"].append(222)
        measured=evaluate_rows(self.mx,enlarged,self.rows,heads,
                               {"heads":3,"layers":1})
        self.assertEqual(measured["semantic_token"]["answer_classes"],223)

    def test_later_oracled_number_42_can_train_without_four_value_ceiling(self):
        import sys
        base=str(ROOT.resolve())
        if base not in sys.path:
            sys.path.insert(0,base)
        from bilqis_school import arithmetic
        expression=arithmetic.operation("ADD",arithmetic.atom(40),arithmetic.atom(2))
        arithmetic.verify(expression)
        self.assertEqual(arithmetic.evaluate(expression),42)
        vocabulary=self.plan["heads"]["semantic_token"]["values"]
        token_id=vocabulary.index("school.number.42")
        record={"task":arithmetic.VERSION,"expression":expression}
        row={"id":"synthetic-source-oracled-42", "tokens":arithmetic.encode(
             record,{name:i for i,name in enumerate(vocabulary)}),
             "answer_kind":"numeric_full_101", "gold":"42",
             "native_output":{"identity":"school.number.42", "token_id":token_id}}
        groups=prepare_typed_batches([row],self.plan["heads"])
        self.assertEqual(set(groups),{"numeric_full_101","semantic_token"})
        self.assertEqual(groups["numeric_full_101"]["target_indices"],[42])
        self.assertEqual(groups["semantic_token"]["target_indices"],[token_id])

    def test_arbitrary_existing_semantic_token_has_generic_output_channel(self):
        vocabulary=self.plan["heads"]["semantic_token"]["values"]
        identity="micro.entity.A"
        target=vocabulary.index(identity)
        example={"id":"fixture-only-semantic-answer", "tokens":[1,2,3],
                 "answer_kind":"semantic_token", "gold":identity,
                 "native_output":{"identity":identity,"token_id":target}}
        groups=prepare_typed_batches([example],self.plan["heads"])
        self.assertEqual(set(groups),{"semantic_token"})
        self.assertEqual(groups["semantic_token"]["target_indices"],[target])
        forged=deepcopy(example)
        forged["native_output"]["token_id"]=7
        with self.assertRaisesRegex(ValueError,"ANSWER_CASTE_NATIVE_SEMANTIC"):
            prepare_typed_batches([forged],self.plan["heads"])

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
        self.assertEqual(set(before), {"numeric_0_3", "evidence", "semantic_token"})
        self.assertEqual(before["semantic_token"]["answer_classes"], 222)
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
        from bilqis_mlx.runtime.mlx_parity import forward

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

    def test_unrestricted_tied_token_logits_match_original_pytorch_model(self):
        import sys
        import numpy as np
        import torch
        from torch.nn import functional as F
        from bilqis_mlx.runtime.mlx_parity import forward
        root = str(ROOT.resolve())
        if root not in sys.path:
            sys.path.insert(0,root)
        from bilqis_ref.model import ModelConfig
        from bilqis_micro.model import MicroStudent
        torch.manual_seed(28)
        model = MicroStudent(ModelConfig(vocab_size=222,context=96,width=12,
            heads=3,layers=1,expansion=2,precision="fp32"))
        model.eval()
        row=self.rows[0]
        ids=torch.tensor([row["tokens"]],dtype=torch.long)
        lengths=torch.tensor([len(row["tokens"])],dtype=torch.long)
        with torch.no_grad():
            x=model.embedding(ids)+model.position(torch.arange(ids.shape[1]))[None]
            for block in model.blocks:
                x=block(x)
            hidden=model.norm(x)[0,lengths[0]-1][None]
            reference=F.linear(hidden,model.embedding.weight).numpy()
        weights={key:self.mx.array(v.detach().numpy())
                 for key,v in model.state_dict().items()}
        full=forward(self.mx,weights,ids.numpy(),lengths.numpy(),heads=3,layers=1,
            answer_ids=self.plan["heads"]["semantic_token"]["token_ids"])
        restricted=self.plan["heads"]["numeric_0_3"]["token_ids"]
        four=forward(self.mx,weights,ids.numpy(),lengths.numpy(),heads=3,layers=1,
            answer_ids=restricted)
        self.assertEqual(full.shape,(1,222))
        self.assertLessEqual(float(np.max(np.abs(full-reference))),.0002)
        self.assertLessEqual(float(np.max(np.abs(full[:,restricted]-four))),.00001)

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
                         {"evidence": 42, "numeric_0_3": 6,
                          "semantic_token": 6})
        loss, _ = typed_step(self.mx, self.parameters, self.optimizer,
                             rows, self.plan["heads"],
                             {"heads": 3, "layers": 1})
        self.assertTrue(math.isfinite(loss))
        self.assertEqual(int(self.optimizer.state["step"].item()), 1)


if __name__ == "__main__":
    unittest.main()
