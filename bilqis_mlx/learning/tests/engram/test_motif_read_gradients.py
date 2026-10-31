"""Test motif read gradients."""
from bilqis_mlx.learning.tests.test_atlas_engram_reads import (
    MotifFrameInput, MotifManifest, MotifSlot, RELEASE,
    TestCase, _parameters, _read, _source,
    motif_keys, motif_parameter_view, mx,
)


class MotifReadGradientsTests(TestCase):
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
