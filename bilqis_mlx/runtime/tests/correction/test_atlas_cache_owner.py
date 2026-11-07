"""C09 exact-cache ownership on the real B14 inference path."""
from dataclasses import replace
import unittest

import numpy as np

from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, CacheBinding, CacheQualityObservation, CacheQualityPolicy,
    apply_cache_correction, bind_cache_artifact_owner, codec_manifest,
    encode_cold_cache, interactive_cache_inference,
)
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    CACHE_AUTHORITY, OWNER_ID, PUBLIC_KEY_HEX, install_test_owner,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _result,
)


def _binding() -> CacheBinding:
    return CacheBinding(
        codec_manifest(),
        generation_sha256="1" * 64,
        lineage_sha256="2" * 64,
        topology_sha256="3" * 64,
        source_release_sha256="4" * 64,
        semantic_release_sha256="5" * 64,
        source_rights_sha256="6" * 64,
        rights_purpose_sha256="7" * 64,
        policy_epoch_sha256="8" * 64,
        context_eligibility_sha256="9" * 64,
        causal_prefix_sha256="a" * 64,
        masks_sha256="b" * 64,
        scope_sha256="c" * 64,
        key_sha256="d" * 64,
        inference_state_sha256="e" * 64,
        offset=17,
        artifact_authority_id=OWNER_ID,
        artifact_authority_public_key_hex=PUBLIC_KEY_HEX,
    )


class ExactCacheArtifactOwnerTests(unittest.TestCase):
    def setUp(self):
        install_test_owner(self)
        self.binding = _binding()
        values = np.ones((256, HEAD_WIDTH), dtype=np.float32)
        self.artifact = encode_cold_cache(
            CACHE_AUTHORITY, values, self.binding.codec_manifest,
            binding=self.binding)
        self.owner = bind_cache_artifact_owner(
            CACHE_AUTHORITY, self.artifact, self.binding)

    def infer(self, owner):
        return interactive_cache_inference(
            CACHE_AUTHORITY, self.artifact, self.binding, artifact_owner=owner,
            cached_infer=lambda _: "CACHE",
            fp32_recompute=lambda: "FP32",
            quality_check=lambda _: CacheQualityObservation(True, 0.0),
            policy=CacheQualityPolicy(0.0),
        )

    def test_signed_rights_correction_holds_cache_before_next_use(self):
        event = _event(self.owner.rights_dependency)
        queue = apply_cache_correction(
            CACHE_AUTHORITY, self.artifact, self.binding, event, AUTHORITY)
        self.assertEqual(queue.held_artifact_ids,
                         (self.owner.current_node.artifact_id,))
        held = self.infer(self.owner)
        self.assertEqual((held.value, held.used_cache, held.fallback_reason), (
            "FP32", False, "CORRECTION_HOLD_OR_OWNER_REQUIRED"))

        node = self.owner.current_node
        progress = self.owner.advance(_result(
            node, digest=node.content_digest, correction=event), AUTHORITY)
        self.assertEqual(progress.queue.held_artifact_ids, ())
        accepted = self.infer(self.owner)
        self.assertEqual((accepted.value, accepted.used_cache), ("CACHE", True))

    def test_changed_or_revoked_cache_cannot_influence_inference(self):
        for index, (digest, eligible) in enumerate((("b" * 64, True), (None, False))):
            with self.subTest(eligible=eligible):
                self.binding = replace(
                    self.binding, key_sha256=("c" if index else "d") * 64)
                values = np.ones((256, HEAD_WIDTH), dtype=np.float32)
                self.artifact = encode_cold_cache(
                    CACHE_AUTHORITY, values, self.binding.codec_manifest,
                    binding=self.binding)
                owner = bind_cache_artifact_owner(
                    CACHE_AUTHORITY, self.artifact, self.binding)
                event = _event(owner.rights_dependency)
                apply_cache_correction(
                    CACHE_AUTHORITY, self.artifact, self.binding, event, AUTHORITY)
                node = owner.current_node
                owner.advance(_result(
                    node,
                    digest=node.content_digest if digest is None else digest,
                    eligible=eligible,
                    correction=event,
                ), AUTHORITY)
                result = self.infer(owner)
                self.assertEqual((result.value, result.used_cache), ("FP32", False))

    def test_caller_cannot_replace_authority_owned_owner(self):
        from bilqis_mlx.runtime.atlas_revalidation import ExactCacheArtifactOwner
        with self.assertRaises(Exception):
            ExactCacheArtifactOwner(CACHE_AUTHORITY, self.artifact, self.binding)


if __name__ == "__main__":
    unittest.main()
