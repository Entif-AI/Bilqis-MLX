"""Training compiler regressions."""
import unittest
from bilqis_mlx.semantics.tests.frame_compilation.helpers import (HiddenAnswerTargets, RELEASE, SourceAtom, StreamingAST, _case, _with_atom_grants, compile_prefix, compile_prefix_rows, compile_training_example, replace)


class TrainingTests(unittest.TestCase):
    def test_hidden_teacher_targets_are_not_model_input_or_cache_identity(self):
        ast, config = _case()
        target_a = HiddenAnswerTargets(
            ast.source_instance_id, (3, 5), (True, True))
        target_b = HiddenAnswerTargets(
            ast.source_instance_id, (9, 0), (True, False))
        first = compile_training_example(
            ast, target_a, 7, RELEASE, config)
        second = compile_training_example(
            ast, target_b, 7, RELEASE, config)
        self.assertEqual(first.input_view, second.input_view)
        self.assertEqual(
            first.input_view.cache_key, second.input_view.cache_key)
        self.assertNotEqual(first.target_view, second.target_view)
        self.assertFalse(hasattr(first.input_view, "target_indices"))
        self.assertFalse(hasattr(first.input_view, "target_view"))

    def test_unequal_source_rows_have_separate_positions_and_cache_keys(self):
        ast, config = _case()
        left = compile_prefix(ast, 5, RELEASE, config)
        other = StreamingAST(
            "synthetic:second-row",
            tuple(SourceAtom(i, f"other:{i}", f"source:second:{i}")
                  for i in range(3)),
            ())
        right = compile_prefix(
            other, 3, RELEASE, _with_atom_grants(
                other, replace(
                    config, approved=None,
                    task=replace(config.task, causal_prefix_end=3))))
        self.assertEqual(
            tuple(item.atom.token for item in right.positions),
            ("other:0", "other:1", "other:2"))
        self.assertEqual(len(left.positions), 5)
        self.assertEqual(len(right.positions), 3)
        self.assertNotEqual(left.cache_key, right.cache_key)

    def test_padded_batch_rows_cannot_expose_other_row_or_future_content(self):
        ast, config = _case()
        other = StreamingAST(
            "synthetic:second-row",
            tuple(SourceAtom(i, f"other:{i}", f"source:second:{i}")
                  for i in range(3)), ())
        other_config = replace(
            config, approved=None,
            task=replace(config.task, causal_prefix_end=3))
        other_config = _with_atom_grants(other, other_config)
        batch = compile_prefix_rows((
            (ast, 8, config), (other, 3, other_config)), RELEASE)
        self.assertEqual(len(batch.rows), 2)
        self.assertEqual(tuple(map(len, batch.padded_positions)), (9, 9))
        self.assertEqual(batch.padding_mask[0], (True,) * 9)
        self.assertEqual(
            batch.padding_mask[1], (True,) * 3 + (False,) * 6)
        self.assertEqual(batch.padded_positions[1][3:], (None,) * 6)
        self.assertEqual(
            tuple(position.atom.token
                  for position in batch.padded_positions[1][:3]),
            ("other:0", "other:1", "other:2"))
        self.assertEqual(batch.rows[1].maps.role_access, ())
        self.assertEqual(batch.rows[1].maps.prefix_ends, (0, 1, 2, 3))
        changed_first = replace(
            ast, atoms=tuple(
                replace(atom, token=atom.token + ":changed")
                for atom in ast.atoms))
        altered = compile_prefix_rows((
            (changed_first, 8, _with_atom_grants(changed_first, config)),
            (other, 3, other_config)), RELEASE)
        self.assertEqual(altered.rows[1], batch.rows[1])
        self.assertEqual(altered.padded_positions[1],
                         batch.padded_positions[1])
