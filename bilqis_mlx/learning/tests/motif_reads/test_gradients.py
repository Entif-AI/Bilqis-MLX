"""B08.1 real A13-gated exact/structural reads and B01 gate arithmetic."""
from __future__ import annotations

from unittest import TestCase

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import (
    MotifManifest, MotifSlot, MotifFrameInput, motif_keys,
)
from bilqis_mlx.learning.atlas_engram_parameters import motif_parameter_view
from bilqis_mlx.learning.atlas_engram_reads import _read_motif_unqualified_candidate as read_motif


RELEASE = "a" * 64

from .fixtures import RELEASE, _source, _parameters, _read

class GradientsReadTests(TestCase):
    def test_hit_gradients_reach_page_projection_and_gate_at_each_site(self):
        position, task, frontier, policy = _source()
        exact, _structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, exact),))
        for site in (0, 1):
            spec, extents, params, _view = _parameters(site=site)
            for name in (
                "motif.page.0",
                f"motif.site.{site}.projection",
                f"motif.site.{site}.bias",
            ):
                def loss(tensor):
                    changed = dict(params)
                    changed[name] = tensor
                    view = motif_parameter_view(
                        changed, spec=spec, extents=extents,
                        site_index=site)
                    return mx.sum(_read(
                        position, task, frontier, policy, manifest,
                        view, site=site)[1].hidden)
                gradient = mx.grad(loss)(params[name])
                self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
                self.assertGreater(float(mx.sum(mx.abs(gradient))), 0)


    def test_nonzero_gate_inputs_train_norm_and_both_gate_vectors(self):
        position, task, frontier, policy = _source()
        exact, _structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, exact),))
        hidden = mx.zeros((1, 2, 768), dtype=mx.float32)
        hidden[0, 0, 0] = 1.0
        for site in (0, 1):
            spec, extents, params, _view = _parameters(site=site)
            params = dict(params)
            for suffix, width in (("gate_hidden", 768), ("gate_feature", 128)):
                vector = mx.zeros((width,), dtype=mx.float32)
                vector[0] = 0.2
                params[f"motif.site.{site}.{suffix}"] = vector
            for suffix in ("norm", "gate_hidden", "gate_feature"):
                name = f"motif.site.{site}.{suffix}"
                def loss(tensor):
                    changed = dict(params)
                    changed[name] = tensor
                    view = motif_parameter_view(
                        changed, spec=spec, extents=extents, site_index=site)
                    return mx.sum(_read(
                        position, task, frontier, policy, manifest, view,
                        site=site, hidden=hidden)[1].hidden)
                gradient = mx.grad(loss)(params[name])
                self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
                self.assertGreater(float(mx.sum(mx.abs(gradient))), 0)


    def test_wrong_site_or_invalid_tensor_rejects_before_gather(self):
        position, task, frontier, policy = _source()
        _spec, _extents, _params, view = _parameters()
        with self.assertRaises(BilqisError):
            _read(position, task, frontier, policy, MotifManifest(RELEASE),
                  view, site=1)
        with self.assertRaises(BilqisError):
            read_motif(
                site_index=0,
                hidden=mx.zeros((1, 2, 768), dtype=mx.float32),
                features=mx.ones((1, 2, 127), dtype=mx.float32),
                positions=((position, None),), tasks=(task,),
                frontiers=(frontier,), policies=(policy,),
                manifest=MotifManifest(RELEASE), parameters=view)
