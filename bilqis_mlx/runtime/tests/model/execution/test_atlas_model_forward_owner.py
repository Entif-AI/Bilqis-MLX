"""B11 source-producer owner threading across cache modes."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.runtime.atlas_model_forward as forward_impl


class AtlasModelOwnerThreadingTests(TestCase):
    def _batch(self, owner):
        compiled = SimpleNamespace(
            extents=SimpleNamespace(motif_key_map_digest="motif-digest"),
            features=SimpleNamespace(semantic_release="semantic-release"))
        return SimpleNamespace(
            compiled=compiled,
            sources=("source",),
            feature_schema=object(),
            active_semantic_rows=SimpleNamespace(
                active_indices=(0,), run_id="test-run", generation=0),
            atlas_feature_artifact_owner=owner,
        )

    def test_source_producer_threads_compiled_batch_owner_in_every_cache_mode(self):
        owner = object()
        batch = self._batch(owner)
        params = object()
        producer = object()
        with patch.object(
                forward_impl, "semantic_bank_views", return_value=("banks",)), patch.object(
                forward_impl, "start_source_backbone_producer",
                return_value=producer) as start:
            actual, accepted = forward_impl._source_producer(
                params, batch, "generation", None)
        self.assertIs(actual, producer)
        self.assertIsNone(accepted)
        self.assertIs(start.call_args.args[-1], owner)

        empty_cache = SimpleNamespace(
            run_id="test-run", generation=0,
            generation_binding="generation",
            motif_manifest=SimpleNamespace(digest="motif-digest", slots=()),
        )
        with patch.object(
                forward_impl, "semantic_bank_views", return_value=("banks",)), patch.object(
                forward_impl, "require_accepted_execution_cache",
                return_value=empty_cache), patch.object(
                forward_impl, "bind_motif_artifact_owner") as bind, patch.object(
                forward_impl, "start_retained_source_backbone_producer",
                return_value=producer) as start:
            actual, accepted = forward_impl._source_producer(
                params, batch, "generation", object())
        self.assertIs(actual, producer)
        self.assertIs(accepted, empty_cache)
        bind.assert_called_once_with(empty_cache, batch.compiled)
        self.assertIs(start.call_args.args[-1], owner)

        foreign_cache = SimpleNamespace(
            run_id="foreign-run", generation=0,
            generation_binding="generation",
            motif_manifest=SimpleNamespace(digest="motif-digest", slots=()),
        )
        with patch.object(
                forward_impl, "semantic_bank_views", return_value=("banks",)), patch.object(
                forward_impl, "require_accepted_execution_cache",
                return_value=foreign_cache):
            with self.assertRaises(BilqisError):
                forward_impl._source_producer(
                    params, batch, "generation", object())

        retained_cache = SimpleNamespace(
            run_id="test-run", generation=0,
            generation_binding="generation",
            motif_manifest=SimpleNamespace(
                digest="motif-digest", slots=(object(),)),
        )
        with patch.object(
                forward_impl, "semantic_bank_views", return_value=("banks",)), patch.object(
                forward_impl, "require_accepted_execution_cache",
                return_value=retained_cache), patch.object(
                forward_impl, "bind_motif_artifact_owner") as bind, patch.object(
                forward_impl, "start_retained_source_backbone_producer",
                return_value=producer) as start:
            actual, accepted = forward_impl._source_producer(
                params, batch, "generation", object())
        self.assertIs(actual, producer)
        self.assertIs(accepted, retained_cache)
        bind.assert_called_once_with(retained_cache, batch.compiled)
        self.assertIs(start.call_args.args[-1], owner)
