"""B13.3 derived attention caches never cross accepted-generation custody."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.atlas_attention import AttentionScope, ccgqa
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, parent_state, publish_candidate, shape_patch,
)


def _digest(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _attention_case():
    rng = np.random.default_rng(754)
    params = {}
    for name, shape in (("query", (384, 768)), ("key", (192, 768)),
                        ("value", (192, 768)), ("output", (768, 384))):
        params[name] = mx.array(rng.normal(0, .02, shape).astype(np.float32))
    for name, channels in (("conv_q", 384), ("conv_k", 192), ("conv_v", 192)):
        params[name] = mx.array(rng.normal(0, .2, (channels, 3)).astype(np.float32))
    hidden = mx.array(rng.normal(0, .1, (1, 4, 768)).astype(np.float32))
    ids = mx.array([[7, 7, 7, 7]], dtype=mx.int32)
    valid = mx.ones((1, 4), dtype=mx.bool_)
    return params, hidden, ids, valid


class CacheSeparationTests(unittest.TestCase):
    def test_accepted_generation_swap_rejects_stale_cache_and_rebuilds_exactly(self):
        with TemporaryDirectory() as temporary, patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}):
            run = Path(temporary) / "run"
            parent = parent_state()
            with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                first = publish_candidate(run, candidate(parent))
                retained = accepted_state(parent)
                second = publish_candidate(
                    run, candidate(retained, 1, first["manifest_sha256"]))

            params, hidden, ids, valid = _attention_case()
            first_scope = AttentionScope(
                ids[:, :3], 0, first["manifest_sha256"], _digest("first"))
            first_values, cache = ccgqa(
                params, hidden[:, :3], valid[:, :3], first_scope)

            next_scope = AttentionScope(
                ids[:, 3:4], 0, second["manifest_sha256"], _digest("next"),
                parent_prefix_digest=_digest("first"))
            with self.assertRaises(BilqisError):
                ccgqa(
                    params, hidden[:, 3:4], valid[:, 3:4], next_scope,
                    cache=cache, offset=3)

            same_generation_scope = replace(
                next_scope, generation=first["manifest_sha256"])
            corrupted_cache = replace(cache, parameter_digest="0" * 64)
            with self.assertRaises(BilqisError):
                ccgqa(
                    params, hidden[:, 3:4], valid[:, 3:4],
                    same_generation_scope, cache=corrupted_cache, offset=3)

            swapped = dict(params)
            swapped["query"] = params["query"] + mx.array(.001, dtype=mx.float32)
            same_generation_scope = AttentionScope(
                ids[:, 3:4], 0, first["manifest_sha256"], _digest("next"),
                parent_prefix_digest=_digest("first"))
            with self.assertRaises(BilqisError):
                ccgqa(
                    swapped, hidden[:, 3:4], valid[:, 3:4],
                    same_generation_scope, cache=cache, offset=3)

            rebuilt_first_scope = AttentionScope(
                ids[:, :3], 0, second["manifest_sha256"], _digest("rebuilt-first"))
            rebuilt_next_scope = AttentionScope(
                ids[:, 3:4], 0, second["manifest_sha256"], _digest("rebuilt-next"),
                parent_prefix_digest=_digest("rebuilt-first"))
            rebuilt_first, rebuilt_cache = ccgqa(
                swapped, hidden[:, :3], valid[:, :3], rebuilt_first_scope)
            rebuilt_next, _ = ccgqa(
                swapped, hidden[:, 3:4], valid[:, 3:4], rebuilt_next_scope,
                cache=rebuilt_cache, offset=3)
            fresh, _ = ccgqa(
                swapped, hidden, valid,
                AttentionScope(ids, 0, second["manifest_sha256"], _digest("fresh")))
            np.testing.assert_allclose(
                np.asarray(mx.concatenate((rebuilt_first, rebuilt_next), axis=1)),
                np.asarray(fresh), atol=2e-6, rtol=3e-5)
            self.assertNotEqual(first["manifest_sha256"], second["manifest_sha256"])
            self.assertEqual(first_values.shape, rebuilt_first.shape)


if __name__ == "__main__":
    unittest.main()
