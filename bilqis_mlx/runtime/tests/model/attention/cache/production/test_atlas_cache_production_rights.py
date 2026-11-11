"""Production B14 rights identity is owned by the compiled frame authority."""
import os
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.atlas_cache_codec import (
    attention_cache_handles, encode_attention_cache,
)
from bilqis_mlx.runtime.atlas_cache_runtime import _capture_forward_attention_caches
from bilqis_mlx.runtime.tests.model.attention.cache.production.cache_production_source_fixture import (
    source_backed_production_fixture,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind


@unittest.skipUnless(
    os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
    "real repo-pinned A01 artifact supplied at source turn-in",
)
class ProductionCacheRightsTests(unittest.TestCase):
    def test_binding_uses_compiled_owner_rights_identity(self):
        cache, batch, producer, _parameters, _snapshot = (
            source_backed_production_fixture())
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache."
            "require_accepted_execution_cache", return_value=cache,
        ):
            authority = _capture_forward_attention_caches(cache, batch, producer)
            _artifact, binding = encode_attention_cache(
                authority, attention_cache_handles(authority)[0])
        nodes = batch.compiled.packed_frame_artifact_owner.require_row(
            batch.compiled.compiled.rows[0])
        rights = {
            ref.key.removeprefix("rights:")
            for node in nodes for ref in node.immediate_dependencies
            if ref.kind is DependencyKind.RIGHTS and ref.key.startswith("rights:")
        }
        self.assertEqual(rights, {binding.source_rights_sha256})


if __name__ == "__main__":
    unittest.main()
