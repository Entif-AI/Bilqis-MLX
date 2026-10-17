"""Disposable native numeric-soup gradient tests, no human/student checkpoint."""
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx.champion_confidence import vote_targets_typed, MAX_INFLUENCE
from bilqis_mlx.grade_a_trainer import _typed_confidence_guidance
from bilqis_mlx.typed_answer_training import typed_objective, typed_step


class TypedSoupExperimentTests(unittest.TestCase):
    def setUp(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        mx.set_default_device(mx.cpu)
        self.mx = mx
        self.optim = optim
        vocab = [f"source.token.{i}" for i in range(27)]
        for i in range(4):
            vocab[23+i] = f"school.number.{i}"
        self.heads = {
            "semantic_token": {"values": vocab, "token_ids": list(range(27))},
            "numeric_0_3": {"values": [str(i) for i in range(4)],
                            "token_ids": list(range(23, 27))},
        }
        self.rows = [{"id": "one", "tokens": [1,2,3,4],
                      "answer_kind": "numeric_0_3", "gold": "1",
                      "native_output": {"identity": "school.number.1", "token_id":24}}]
        d = 12
        shapes = {
            "embedding.weight": (27,d), "position.weight": (8,d),
            "norm.weight": (d,), "blocks.0.n1.weight": (d,),
            "blocks.0.n2.weight": (d,), "blocks.0.qkv.weight": (3*d,d),
            "blocks.0.proj.weight": (d,d), "blocks.0.up.weight": (2*d,d),
            "blocks.0.down.weight": (d,2*d),
        }
        rng = np.random.default_rng(17)
        self.weights = {k: mx.array(rng.normal(0,.05,v).astype(np.float32)
                        if len(v)>1 else np.ones(v,dtype=np.float32))
                        for k,v in shapes.items()}
        self.config = {"layers":1, "heads":3, "answer_heads":self.heads}

    def test_multiclass_wrong_votes_are_not_reinforced(self):
        labels = [1, 2]
        right = np.array([[0,4,0], [0,0,4]],dtype=np.float32)
        wrong = np.array([[4,0,0], [4,0,0]],dtype=np.float32)
        actual = vote_targets_typed([(2,wrong),(2,right)],labels,classes=3,
                     eligible_capabilities=4,teacher_distill=.6)
        np.testing.assert_allclose(actual[1], [.024,.024],atol=1e-7)
        self.assertTrue((actual[1] <= MAX_INFLUENCE).all())
        self.assertTrue((actual[0].argmax(-1)==labels).all())
        self.assertEqual(float(vote_targets_typed(
            [(2,wrong)],labels,classes=3,
            eligible_capabilities=4,teacher_distill=.6)[1].sum()),0.)

    def test_numeric_soup_advice_is_applied_to_actual_typed_objective(self):
        mx = self.mx
        mentors = [{"weights":self.weights, "vocab_size":27, "breadth":2}]

        def oracle_logits(_mx, _weights, ids, lengths, *, heads, layers, answer_ids):
            data = np.zeros((len(ids),len(answer_ids)),dtype=np.float32)
            winning = answer_ids.index(24)
            data[:,winning] = 5.0
            return mx.array(data)

        with patch("bilqis_mlx.grade_a_trainer.forward_arrays", side_effect=oracle_logits):
            advice = _typed_confidence_guidance(
                mx, mentors, self.rows, self.config,scope_size=6,teacher_distill=.7)
        self.assertEqual(set(advice), {"numeric_0_3", "semantic_token"})
        self.assertGreater(float(advice["numeric_0_3"][1].sum()),0.)
        self.assertGreater(float(advice["semantic_token"][1].sum()),0.)
        base = float(typed_objective(mx,self.weights,self.rows,self.heads,self.config).item())
        guided = float(typed_objective(mx,self.weights,self.rows,self.heads,self.config,
                                       champion_guidance=advice).item())
        self.assertNotEqual(base,guided)
        from bilqis_mlx.learning_experiment import fork_student
        parent = self.optim.AdamW(learning_rate=.00013,bias_correction=True)
        parent.update(self.weights,{k:mx.zeros_like(v) for k,v in self.weights.items()})
        x, first = fork_student(mx,self.weights,parent)
        y, second = fork_student(mx,self.weights,parent)
        typed_step(mx,x,first,self.rows,self.heads,self.config)
        typed_step(mx,y,second,self.rows,self.heads,self.config,
                   champion_guidance=advice)
        self.assertTrue(any(not np.array_equal(np.asarray(x[k]),np.asarray(y[k]))
                            for k in x))

    def test_incompatible_historic_vocabulary_is_not_falsely_consulted(self):
        mx=self.mx
        mentors=[{"weights":self.weights,"vocab_size":23,"breadth":3}]
        with patch("bilqis_mlx.grade_a_trainer.forward_arrays",
                   side_effect=AssertionError("INCOMPATIBLE_OLD_SOUP_CALLED")):
            self.assertIsNone(_typed_confidence_guidance(
                mx,mentors,self.rows,self.config,scope_size=6,teacher_distill=.8))

    def test_bad_typed_target_rejected_before_optimizer_update(self):
        guidance = {"numeric_0_3": (
            np.ones((1,4),dtype=np.float32),
            np.array([.12],dtype=np.float32))}
        optimizer=self.optim.AdamW(learning_rate=.00013,bias_correction=True)
        with self.assertRaisesRegex(ValueError,"TYPED_CONFIDENCE"):
            typed_step(self.mx,self.weights,optimizer,self.rows,self.heads,
                       self.config,champion_guidance=guidance)
        self.assertEqual(int(optimizer.state["step"].item()),0)


if __name__=="__main__":
    unittest.main()
