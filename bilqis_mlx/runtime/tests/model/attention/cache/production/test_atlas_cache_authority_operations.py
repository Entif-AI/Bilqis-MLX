"""Operation-time owner drift witnesses for B14.4 cache currentness."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, CacheQualityObservation, CacheQualityPolicy,
    decode_cache, encode_cold_cache, interactive_cache_inference,
    issue_cache_eligibility, rebuild_revoked_cache,
)
from bilqis_mlx.runtime.atlas_cache_records import _encode_cold_cache
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    authority_for_registry,
)
from bilqis_mlx.runtime.tests.model.attention.cache.test_atlas_cache_authority_currentness import (
    CacheAuthorityCurrentnessTests, _cache_shape_patch, _inputs, _registry,
)


class CacheAuthorityOperationCurrentnessTests(unittest.TestCase):
    def setUp(self):
        CacheAuthorityCurrentnessTests.setUp(self)

    _run = CacheAuthorityCurrentnessTests._run

    def test_decode_and_inference_reject_owner_drift_before_cache_use(self):
        with TemporaryDirectory() as temporary, patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}):
            run, _, binding = self._run(temporary)
            current = [_inputs(
                run, self.clearance, self.selection, self.frontier,
                self.frames, self.task, self.policy)]
            authority = authority_for_registry(
                _registry(), eligibility_source=lambda: current[0])
            with _cache_shape_patch():
                artifact = encode_cold_cache(
                    authority, np.ones((256, HEAD_WIDTH), dtype=np.float32),
                    binding.codec_manifest, binding=binding)
            changed_policy = replace(
                self.policy, policy_id="owner:next-policy",
                policy_epoch=self.policy.policy_epoch + 1)
            changed_frames = tuple(replace(
                frame, policy_epoch=changed_policy.policy_epoch)
                for frame in self.frames)
            current[0] = replace(
                current[0], frames=changed_frames, policy=changed_policy)
            with _cache_shape_patch(), self.assertRaises(BilqisError):
                encode_cold_cache(
                    authority, np.ones((256, HEAD_WIDTH), dtype=np.float32),
                    binding.codec_manifest, binding=binding)
            with _cache_shape_patch(), self.assertRaises(BilqisError):
                decode_cache(authority, artifact, binding)
            with _cache_shape_patch():
                result = interactive_cache_inference(
                    authority, artifact, binding,
                    cached_infer=lambda _: self.fail("stale cache reached attention"),
                    fp32_recompute=lambda: "FP32",
                    quality_check=lambda _: CacheQualityObservation(True, 0.0),
                    policy=CacheQualityPolicy(0.01))
            self.assertEqual(
                (result.value, result.used_cache, result.fallback_reason),
                ("FP32", False, "BINDING_MISMATCH"))

    def test_authority_drift_during_persist_cannot_make_stale_cache_usable(self):
        with TemporaryDirectory() as temporary, patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}):
            run, _, binding = self._run(temporary)
            current = [_inputs(
                run, self.clearance, self.selection, self.frontier,
                self.frames, self.task, self.policy)]
            authority = authority_for_registry(
                _registry(), eligibility_source=lambda: current[0])
            with _cache_shape_patch():
                receipt = issue_cache_eligibility(authority, binding)
            stale_binding = replace(binding, generation_sha256="f" * 64)
            stale = _encode_cold_cache(
                np.ones((256, HEAD_WIDTH), dtype=np.float32),
                stale_binding.codec_manifest, binding=stale_binding,
                authority=authority)
            changed_policy = replace(
                self.policy, policy_id="owner:during-persist",
                policy_epoch=self.policy.policy_epoch + 1)
            changed_frames = tuple(replace(
                frame, policy_epoch=changed_policy.policy_epoch)
                for frame in self.frames)
            persisted = []

            def persist(artifact):
                current[0] = replace(
                    current[0], frames=changed_frames, policy=changed_policy)
                persisted.append(artifact)

            with _cache_shape_patch(), self.assertRaises(BilqisError):
                rebuild_revoked_cache(
                    authority, stale, binding,
                    eligibility_receipt=receipt, persist=persist)
            self.assertEqual(len(persisted), 1)
            with _cache_shape_patch(), self.assertRaises(BilqisError):
                decode_cache(authority, persisted[0], binding)


if __name__ == "__main__":
    unittest.main()
