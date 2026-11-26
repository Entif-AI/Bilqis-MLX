"""Focused eligibility, ancestry and patch isolation checks for the spike."""
from collections import Counter
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prefix_census import count_positions


class CensusTests(unittest.TestCase):
    def test_scope_and_divergent_history(self):
        rows = (("a", (1, 2, 3)), ("a", (1, 4, 3)),
                ("a", (1, 2, 3)), ("b", (1, 2, 3)))
        self.assertEqual(count_positions(rows)["unique_prefix_positions"], 8)
        self.assertEqual(count_positions(rows)["repeated_positions"], 4)

    def test_empty(self):
        self.assertEqual(count_positions([])["positions"], 0)


class NativeLayoutTests(unittest.TestCase):
    def setUp(self):
        import mlx.core as mx
        self.mx = mx
        self.previous_device = mx.default_device()
        mx.set_default_device(mx.cpu)
        self.addCleanup(mx.set_default_device, self.previous_device)

    def test_ancestors_and_multiplicity(self):
        from prefix_dag import TrieLayout
        rows = (("a", (1, 2, 3)), ("a", (1, 2, 4)),
                ("a", (1, 2, 3)), ("b", (1, 2)))
        layout = TrieLayout.build(rows, gathered=True)
        self.assertEqual(layout.row_nodes.tolist(),
                         [[0, 1, 2], [0, 1, 3], [0, 1, 2], [4, 5, 0]])
        self.assertEqual(layout.parent.tolist(), [-1, 0, 1, 1, -1, 4])
        self.assertEqual(layout.grandparent.tolist(), [-1, -1, 0, 0, -1, -1])
        self.assertEqual(layout.ancestors.tolist(),
                         [[0, 0, 0], [0, 1, 0], [0, 1, 2],
                          [0, 1, 3], [4, 0, 0], [4, 5, 0]])
        self.assertEqual(layout.ancestor_valid.tolist(),
                         [[True, False, False], [True, True, False],
                          [True, True, True], [True, True, True],
                          [True, False, False], [True, True, False]])
        self.assertIsNone(layout.allowed)

    def test_closure_keeps_every_descendant_private(self):
        from intervention import layout_for
        atom = lambda index: NS(kind=NS(value="ATOM"), source_index=index)
        closure = NS(kind=NS(value="CLOSURE"), source_index=1)
        row = NS(visible_end=3, positions=(atom(0), closure, atom(2)),
                 semantic_release="release", policy_version="policy")
        config = NS(task=NS(scope="scope"))
        source = NS(learning_abi_indices=(1, 2, 3), source_row={"capability": "B.AND"})
        producer = NS(_trace=True, _input_motif_read=None, _motif_manifest=None,
                      _source_execution_authorities=None,
                      _compiled=NS(compiled=NS(rows=(row, row)),
                                   compiler_configs=(config, config)),
                      _sources=(source, source))
        self.assertEqual(layout_for(producer, gathered=True).row_nodes.tolist(),
                         [[0, 1, 2], [0, 3, 4]])
        for name in ("_input_motif_read", "_motif_manifest", "_source_execution_authorities"):
            setattr(producer, name, object())
            self.assertIsNone(layout_for(producer, gathered=True))
            setattr(producer, name, None)
        producer._trace = False
        self.assertIsNone(layout_for(producer, gathered=True))

    def test_patch_isolation(self):
        from intervention import instrument, microbatch, backbone_group_numerical, c08
        owners = ((microbatch, "_source_producer"),
                  (backbone_group_numerical.BackboneTraceSession, "advance"),
                  (c08, "bamf_microbatch_value_and_grad"))
        originals = [getattr(owner, name) for owner, name in owners]
        with self.assertRaisesRegex(RuntimeError, "witness failure"):
            with instrument("gathered", Counter(), [], True):
                self.assertTrue(all(getattr(owner, name) is not original
                                    for (owner, name), original in zip(owners, originals)))
                raise RuntimeError("witness failure")
        self.assertEqual([getattr(owner, name) for owner, name in owners], originals)


if __name__ == "__main__":
    unittest.main()
