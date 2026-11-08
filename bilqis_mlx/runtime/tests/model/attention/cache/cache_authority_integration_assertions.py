"""Behavior assertions for accepted-cache authority integration."""
from dataclasses import replace

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import atlas_cache_runtime
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost, _RUNTIME_OWNER
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, CacheQualityObservation, CacheQualityPolicy,
    encode_cold_cache, issue_cache_eligibility, rebuild_revoked_cache,
)
from bilqis_mlx.runtime.atlas_cache_records import _encode_cold_cache
from bilqis_mlx.runtime.bamf_bundle import admission
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import _reset_execution_cache_owner_for_tests
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_cache_authority,
    interactive_accepted_cache_inference,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import _event, _ref
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

from .cache_authority_integration_fixture import _cache_shape_patch


def _assert_exact_rebuild(test, authority, binding):
    with _cache_shape_patch():
        receipt = issue_cache_eligibility(authority, binding)
    stale_binding = replace(binding, generation_sha256="f" * 64)
    stale = _encode_cold_cache(
        np.ones((256, HEAD_WIDTH), dtype=np.float32),
        stale_binding.codec_manifest, binding=stale_binding,
        authority=authority)
    persisted = []
    with _cache_shape_patch():
        rebuilt = rebuild_revoked_cache(
            authority, stale, binding, eligibility_receipt=receipt,
            persist=persisted.append)
    test.assertTrue(rebuilt.persisted)
    test.assertEqual(persisted, [rebuilt.artifact])


def _assert_live_cache_use(
    test, run, authority, registry, eligibility_source, binding,
):
    values = np.ones((256, HEAD_WIDTH), dtype=np.float32)
    with _cache_shape_patch():
        live_artifact = encode_cold_cache(
            authority, values, binding.codec_manifest, binding=binding)
        live = AcceptedRuntimeHost(run).cache_inference(
            live_artifact, binding,
            cached_infer=lambda _: "CACHE", fp32_recompute=lambda: "FP32",
            quality_check=lambda _: CacheQualityObservation(True, 0.0),
            policy=CacheQualityPolicy(0.01), eligibility_source=eligibility_source)
    test.assertTrue(live.used_cache)
    return live_artifact


def _assert_correction_hold(
    test, run, registry, eligibility_source, binding, live_artifact,
):
    correction = _event(_ref(
        DependencyKind.RIGHTS, "rights:" + binding.source_rights_sha256))
    with _cache_shape_patch():
        host = AcceptedRuntimeHost(run)
        host.record_correction(correction)
        held = host.cache_inference(
            live_artifact, binding,
            cached_infer=lambda _: test.fail("held cache influenced output"),
            fp32_recompute=lambda: "FP32",
            quality_check=lambda _: CacheQualityObservation(True, 0.0),
            policy=CacheQualityPolicy(0.01), eligibility_source=eligibility_source)
    test.assertFalse(held.used_cache)


def _assert_cold_replay_hold(test, run, registry, eligibility_source, binding):
    _reset_execution_cache_owner_for_tests()
    _RUNTIME_OWNER.clear()
    atlas_cache_runtime._reset_accepted_cache_authority_owner_for_tests()
    values = np.ones((256, HEAD_WIDTH), dtype=np.float32)
    with _cache_shape_patch():
        _cold_cache, cold_authority = bind_accepted_cache_authority(
            run, eligibility_source)
        cold_artifact = encode_cold_cache(
            cold_authority, values, binding.codec_manifest, binding=binding)
        cold_held = interactive_accepted_cache_inference(
            run, cold_artifact, binding,
            cached_infer=lambda _: test.fail(
                "cold-replayed held cache influenced output"),
            fp32_recompute=lambda: "FP32",
            quality_check=lambda _: CacheQualityObservation(True, 0.0),
            policy=CacheQualityPolicy(0.01), eligibility_source=eligibility_source)
    test.assertFalse(cold_held.used_cache)


def _assert_binding_drift_rejected(test, authority, binding):
    for changed in (
        replace(binding, generation_sha256="0" * 64),
        replace(binding, lineage_sha256="0" * 64),
        replace(binding, source_release_sha256="0" * 64),
        replace(binding, semantic_release_sha256="0" * 64),
        replace(binding, source_rights_sha256="0" * 64),
        replace(binding, rights_purpose_sha256="0" * 64),
        replace(binding, policy_epoch_sha256="0" * 64),
        replace(binding, context_eligibility_sha256="0" * 64),
        replace(binding, inference_state_sha256="0" * 64),
    ):
        with test.subTest(changed=changed), test.assertRaises(BilqisError), \
                _cache_shape_patch():
            issue_cache_eligibility(authority, changed)
