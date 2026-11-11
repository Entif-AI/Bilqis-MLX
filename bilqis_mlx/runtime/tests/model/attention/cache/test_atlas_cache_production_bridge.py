"""Production B14 bridge from B13 custody through the source-backed B11 cache owner."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import semantic_bank_views
from bilqis_mlx.learning.source_atoms.backbone import (
    complete_source_backbone_producer,
    start_source_backbone_producer,
)
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.atlas_cache_codec import (
    attention_cache_binding,
    attention_cache_handles,
    bind_accepted_cache_authority,
    decode_cache,
    encode_attention_cache,
    rebuild_attention_cache,
)
from bilqis_mlx.runtime.atlas_cache_runtime import _capture_forward_attention_caches
from bilqis_mlx.runtime.atlas_cache_runtime import (
    _capture_production_records, _production_authority_state,
)
from bilqis_mlx.runtime.atlas_cache_production_custody import _capture_handle
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle import admission
from bilqis_mlx.runtime.tests.model.attention.cache.cache_authority_integration_fixture import (
    _accepted_registry,
    _cache_shape_patch,
    _context,
    _publish_cache_fixture,
    _selection,
    _source,
)
from bilqis_mlx.runtime.tests.model.attention.cache.cache_production_source_fixture import (
    source_backed_production_fixture,
)


class RealAcceptedCustodyBridgeTests(unittest.TestCase):
    def test_one_b14_authority_is_resolved_from_real_b13_custody(self):
        selection = _selection()
        _frames, _task, frontier, _policy = _context(selection.release_sha256)
        source = _source(selection, frontier)
        authority_registry = _accepted_registry()
        with TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}
        ):
            run = Path(temporary) / "accepted-run"
            with patch.object(mlx_checkpoint, "assert_headroom"):
                _publish_cache_fixture(
                    run, source, host_registry=authority_registry)
            with _cache_shape_patch(), patch(
                "bilqis_mlx.runtime.bamf_bundle.source_authority_custody."
                "read_host_system_source_authority_registry",
                return_value=authority_registry,
            ):
                accepted = admission.bind_accepted_execution_cache(run)
                first = bind_accepted_cache_authority(accepted)
                second = bind_accepted_cache_authority(accepted)
                self.assertIs(first, second)
                self.assertEqual(attention_cache_handles(first), ())


@unittest.skipUnless(
    os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
    "real repo-pinned A01 artifact supplied at source turn-in",
)
class SourceBackedProductionCaptureTests(unittest.TestCase):
    def _retained_fixture(self):
        return source_backed_production_fixture()

    def test_real_b11_caches_supply_kv_bindings_and_causal_currentness(self):
        cache, batch, producer, _parameters, _snapshot = self._retained_fixture()
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache",
            return_value=cache,
        ):
            authority = _capture_forward_attention_caches(cache, batch, producer)
            self.assertIs(authority, bind_accepted_cache_authority(cache))
            handles = attention_cache_handles(authority)
            self.assertEqual(len(handles), 24)
            self.assertEqual(len(set(handles)), 24)
            artifact, binding = encode_attention_cache(authority, handles[0])
            decoded = decode_cache(authority, artifact, binding)
            self.assertEqual(decoded.shape[-1], 24)

            tampered = replace(binding, causal_prefix_sha256="f" * 64)
            with patch(
                "bilqis_mlx.runtime.atlas_cache_records._decode_cache"
            ) as raw_decode, self.assertRaises(BilqisError):
                decode_cache(authority, artifact, tampered)
            raw_decode.assert_not_called()

    def test_captured_generation_matches_source_owned_execution(self):
        cache, batch, producer, parameters, _snapshot = self._retained_fixture()
        expected = execution_generation_digest(
            parameters, spec=producer._topology, extents=batch.compiled.extents)
        self.assertEqual(producer._generation, expected)
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache",
            return_value=cache,
        ):
            authority = _capture_forward_attention_caches(cache, batch, producer)
            handle = attention_cache_handles(authority)[0]
            _artifact, binding = encode_attention_cache(authority, handle)
            self.assertEqual(binding.inference_state_sha256, expected)

    def test_fresh_owner_capture_rebuilds_stale_bytes_without_decoding_them(self):
        cache, batch, producer, _parameters, _snapshot = self._retained_fixture()
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache",
            return_value=cache,
        ):
            authority = _capture_forward_attention_caches(cache, batch, producer)
            first, second = attention_cache_handles(authority)[:2]
            stale, stale_binding = encode_attention_cache(authority, first)
            fresh_binding = attention_cache_binding(authority, second)
            self.assertNotEqual(stale_binding.key_sha256, fresh_binding.key_sha256)
            persisted = []
            with patch(
                "bilqis_mlx.runtime.atlas_cache_records._decode_cache"
            ) as raw_decode:
                rebuilt = rebuild_attention_cache(
                    authority, stale, second, persist=persisted.append)
            raw_decode.assert_not_called()
            self.assertEqual(persisted, [rebuilt.artifact])
            self.assertEqual(
                decode_cache(authority, rebuilt.artifact, fresh_binding).shape[-1], 24)

    def test_new_current_slot_supersedes_old_causal_binding(self):
        cache, batch, producer, _parameters, _snapshot = self._retained_fixture()
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache", return_value=cache,
        ):
            authority = _capture_forward_attention_caches(cache, batch, producer)
            handle = attention_cache_handles(authority)[0]
            artifact, binding = encode_attention_cache(authority, handle)
            entry = _production_authority_state(authority)
            old = entry[3][handle]
            current = replace(
                old[1], causal_prefix_sha256="f" * 64)
            new_handle = _capture_handle(current)
            _capture_production_records(
                authority, {new_handle: (old[0], current, *old[2:])})
            with patch(
                "bilqis_mlx.runtime.atlas_cache_records._decode_cache"
            ) as raw_decode, self.assertRaises(BilqisError):
                decode_cache(authority, artifact, binding)
            raw_decode.assert_not_called()

    def test_non_retained_or_mismatched_batch_cannot_be_blessed_by_b13(self):
        cache, batch, _retained, parameters, snapshot = self._retained_fixture()
        ordinary = start_source_backbone_producer(
            batch.compiled,
            parameters,
            batch.sources,
            batch.feature_schema,
            semantic_bank_views(
                parameters,
                batch.compiled.extents,
                batch.compiled.features.semantic_release,
                tuple(entry.index for entry in snapshot.abi_entries if entry.active),
            ),
            batch.atlas_feature_artifact_owner,
        )
        complete_source_backbone_producer(ordinary)
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache",
            return_value=cache,
        ):
            with self.assertRaises(BilqisError):
                _capture_forward_attention_caches(cache, batch, ordinary)
            mismatched = replace(
                batch,
                sources=(replace(batch.sources[0], source_seed=99),),
            )
            with self.assertRaises(BilqisError):
                _capture_forward_attention_caches(cache, mismatched, _retained)


if __name__ == "__main__":
    unittest.main()
