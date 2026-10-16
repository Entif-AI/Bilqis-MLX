"""Disposable champion confidence tests; no real student updates."""
import unittest
import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from bilqis_mlx.champion_confidence import vote_targets, champion_roster


def record(cap, sha, perfect):
    return {"capability": cap, "rubric": "a" * 64,
            "checkpoint": {"sha256": sha * 64,
                           "filename": "bundles/" + sha,
                           "optimizer_step": 1,
                           "model_and_native_adamw": True},
            "correct": 12, "total": 12,
            "perfect_capabilities": list(perfect), "breadth": len(perfect)}


class ChampionConfidenceTests(unittest.TestCase):
    def test_only_frozen_soup_not_foreign_capability_champions_advises_grade_b(self):
        from bilqis_mlx.grade_a_trainer import (
            _frozen_confidence_champions, _frozen_grade_soup_votes,
        )
        a_champ = record("A.3", "1", ("A.3", "A.5"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            a_only = {"graduation_perfect": {"A.3": a_champ}}
            # The grade-A champion bundle is deliberately absent. The B
            # confidence reader must not even attempt to load it.
            self.assertEqual(_frozen_confidence_champions(root, a_only, "B", {}), ())
            path = root / "soups" / "A-frozen.safetensors"
            path.parent.mkdir()
            path.write_bytes(b"synthetic immutable path")
            soup = {"grade": "A", "filename": str(path.relative_to(root)),
                    "sha256": "c" * 64, "token_count": 12,
                    "recipe_sha256": "d" * 64, "vote_count": 7}
            with patch("bilqis_mlx.grade_a_trainer._cached_grade_soup",
                       return_value={"embedding.weight": "synthetic"}):
                mentors, receipts = _frozen_grade_soup_votes(
                    root, {"grade_soups": {"A": soup}}, "B", 3)
            self.assertEqual(len(mentors), 1)
            self.assertAlmostEqual(mentors[0]["breadth"], 7 / 3)
            self.assertEqual(receipts[0]["frozen_base_votes"], 7)
            self.assertAlmostEqual(receipts[0]["effective_votes"], 7 / 3)

    def test_mlx_supervised_step_absorbs_advice_without_modifying_exam_inference(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        from bilqis_mlx.grade_a_trainer import (
            _confidence_guidance, _predictions, _train_step,
        )
        mx.set_default_device(mx.cpu)
        rng = np.random.default_rng(41)
        width = 12
        shapes = {"embedding.weight": (32, width),
                  "position.weight": (12, width),
                  "norm.weight": (width,),
                  "blocks.0.n1.weight": (width,),
                  "blocks.0.n2.weight": (width,),
                  "blocks.0.qkv.weight": (3 * width, width),
                  "blocks.0.proj.weight": (width, width),
                  "blocks.0.up.weight": (2 * width, width),
                  "blocks.0.down.weight": (width, 2 * width)}
        original = {key: (rng.normal(0, .1, size=shape).astype(np.float32)
                          if len(shape) > 1 else np.ones(shape, dtype=np.float32))
                    for key, shape in shapes.items()}
        def student():
            weights = {key: mx.array(value) for key, value in original.items()}
            optimizer = optim.AdamW(learning_rate=.00013, bias_correction=True)
            optimizer.update(weights, {key: mx.zeros_like(value)
                                       for key, value in weights.items()})
            mx.eval(weights, optimizer.state)
            return weights, optimizer
        base, first = student()
        guided, second = student()
        rows = [{"id": "yes", "gold": "TRUE", "tokens": [1, 2, 3, 6]},
                {"id": "no", "gold": "FALSE", "tokens": [4, 5, 6, 7]}]
        config = {"heads": 3, "layers": 1}
        self.assertEqual(_predictions(mx, base, rows, config, [6, 7]),
                         _predictions(mx, guided, rows, config, [6, 7]))
        agreed = _predictions(mx, guided, rows, config, [6, 7])
        coaching_rows = [{**row, "gold": agreed[row["id"]]} for row in rows]
        prepared = _confidence_guidance(
            mx, ({"weights": guided, "graph": {"tokens": list(range(32))},
                  "breadth": 3},), coaching_rows, config, [6, 7],
            scope_size=6, teacher_distill=0.5)
        self.assertIsNotNone(prepared)
        np.testing.assert_allclose(prepared[1], [.02, .02], atol=1e-6)
        unassisted, _ = _train_step(mx, base, first, rows, config, [6, 7])
        advice = (np.array([[.1, .9], [.9, .1]], dtype=np.float32),
                  np.array([.06, .06], dtype=np.float32))
        assisted, _ = _train_step(mx, guided, second, rows, config, [6, 7],
                                  champion_guidance=advice)
        self.assertGreater(assisted, unassisted)
        self.assertEqual(int(first.state["step"].item()),
                         int(second.state["step"].item()))
        self.assertTrue(any(not np.array_equal(np.asarray(base[key]),
                                              np.asarray(guided[key]))
                            for key in original))

    def test_unique_checkpoint_receives_one_vote_at_its_true_breadth(self):
        roster = {"a" * 64 + ":A.3": record("A.3", "1", ("A.3", "A.5")),
                  "a" * 64 + ":A.5": record("A.5", "1", ("A.3", "A.5")),
                  "a" * 64 + ":B.IFF": record("B.IFF", "2", ("B.IFF",))}
        chosen = champion_roster(roster, "A")
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["breadth"], 2)
        self.assertEqual(len(champion_roster(roster, "B")), 1)
        self.assertEqual(champion_roster(roster, "B")[0]["breadth"], 1)
        self.assertEqual(champion_roster(roster, "C"), ())

    def test_gold_agreeing_logits_vote_proportional_to_breadth(self):
        labels = np.array([1, 0], dtype=np.int64)
        correct_logits = np.array([[0., 2.], [2., 0.]], dtype=np.float32)
        one = vote_targets([(1, correct_logits)], labels, eligible_capabilities=12,
                           teacher_distill=0.5)
        three = vote_targets([(3, correct_logits)], labels, eligible_capabilities=12,
                             teacher_distill=0.5)
        self.assertAlmostEqual(float(three[1][0] / one[1][0]), 3., places=5)
        self.assertLess(three[1][0], 0.08)
        np.testing.assert_allclose(three[0].sum(axis=1), [1., 1.])
        wrong_logits = -correct_logits
        mixed = vote_targets([(1, wrong_logits), (3, correct_logits)], labels,
                             eligible_capabilities=12, teacher_distill=0.5)
        np.testing.assert_allclose(mixed[1], three[1])
        zero = vote_targets([(3, correct_logits)], labels, eligible_capabilities=12,
                            teacher_distill=0.)
        self.assertEqual(float(zero[1].sum()), 0.)
