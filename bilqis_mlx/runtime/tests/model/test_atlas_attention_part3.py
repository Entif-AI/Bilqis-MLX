"""Structural test shard from test_atlas_attention.py; assertions preserved."""
from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_attention import (
    ATTENTION_PARAMETER_NAMES, AttentionScope, attention_parameter_view,
    ccgqa, project_convolved_qkv,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, initialize_bamf_parameter,
)
from bilqis_mlx.runtime.tests.model.test_atlas_attention_helpers import (digest, fixture, oracle)

class AtlasGQATests(unittest.TestCase):
        def setUp(self):
            self.params, self.hidden = fixture()
            self.ids = mx.array([[7, 7, 9, 9, 9], [7, 7, 7, 7, 7]])
            self.valid = mx.array([[True, True, True, True, True], [True, True, True, False, False]])
            self.starts = mx.array([[False]*5, [False, False, True, False, False]])

        def scope(self, ids=None, starts=None, prefix="full", parent=None):
            return AttentionScope(ids=self.ids if ids is None else ids, layer=0,
                                  generation=digest("generation"), prefix_digest=digest(prefix),
                                  parent_prefix_digest=None if parent is None else digest(parent),
                                  sequence_starts=self.starts if starts is None else starts)

        def test_attention_view_rejects_missing_extra_or_malformed_b01_tensors(self):
            spec = ModelTopologySpecV2()
            extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
            parameters = {
                item.name: mx.zeros(item.shape, dtype=mx.float32)
                for item in expected_bamf_shapes(spec, extents)
            }
            changes = (
                {"blocks.0.output": None},
                {"blocks.0.conv_q": mx.zeros((384, 2), dtype=mx.float32)},
                {"features.norm": mx.zeros((768,), dtype=mx.float16)},
                {"unexpected.trainable": mx.zeros((1,), dtype=mx.float32)},
            )
            for change in changes:
                malformed = dict(parameters)
                malformed.update(change)
                if "blocks.0.output" in change:
                    malformed.pop("blocks.0.output")
                with self.subTest(change=tuple(change)), self.assertRaises(BilqisError):
                    attention_parameter_view(
                        malformed, spec=spec, extents=extents, layer=0)
            for layer in (-1, 12, True):
                with self.assertRaises(BilqisError):
                    attention_parameter_view(
                        parameters, spec=spec, extents=extents, layer=layer)
