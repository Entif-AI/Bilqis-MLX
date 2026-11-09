"""B14.4 cache rebuild authority comes from live B13/A12/context owners."""
import os
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_cache_binding import binding_digest
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, CacheBinding, CacheEligibilityReceipt, codec_manifest,
    rebuild_revoked_cache,
)
from bilqis_mlx.runtime.atlas_cache_records import _encode_cold_cache
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    OWNER_ID, PUBLIC_KEY_HEX, authority_for_registry, install_test_owner,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

from .cache_authority_integration_assertions import (
    _assert_binding_drift_rejected, _assert_cold_replay_hold,
    _assert_correction_hold, _assert_exact_rebuild, _assert_live_cache_use,
)
from .cache_authority_integration_fixture import (
    _accepted_cache_authority, _binding, _clearance, _context,
    _publish_cache_fixture, _selection, _source,
)


class CacheAuthorityIntegrationTests(unittest.TestCase):
    def setUp(self):
        if self._testMethodName != (
                "test_live_b13_a12_and_context_authority_issue_exact_rebuild_receipt"):
            install_test_owner(self, eligibility=False, current_binding=False)

    def test_caller_matching_receipt_is_not_authority(self):
        binding = CacheBinding(
            codec_manifest(), *(value * 64 for value in "123456789abcde"),
            17, OWNER_ID, PUBLIC_KEY_HEX)
        forged = CacheEligibilityReceipt(
            binding_digest(binding).hex(), binding.source_release_sha256,
            binding.semantic_release_sha256, binding.source_rights_sha256,
            binding.rights_purpose_sha256, binding.policy_epoch_sha256,
            binding.context_eligibility_sha256, True)
        authority = authority_for_registry(SourceAuthorityRegistry((SourceAuthorityKey(
            OWNER_ID, PUBLIC_KEY_HEX,
            (SourceAuthorityScope(DependencyKind.ARTIFACT, "cache:"),)),)))
        stale = _encode_cold_cache(
            np.zeros((256, HEAD_WIDTH), dtype=np.float32), binding.codec_manifest,
            binding=binding, authority=authority)
        with self.assertRaises(BilqisError):
            rebuild_revoked_cache(
                authority,
                stale, replace(binding, policy_epoch_sha256="f" * 64),
                eligibility_receipt=forged,
                persist=lambda _: self.fail("caller receipt persisted"))

    def test_live_b13_a12_and_context_authority_issue_exact_rebuild_receipt(self):
        selection = _selection()
        frames, task, frontier, policy = _context(selection.release_sha256)
        clearance = _clearance(selection, frontier)
        with TemporaryDirectory() as temporary, patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}):
            run = Path(temporary) / "run"
            source = _source(selection, frontier)
            pointer, source = _publish_cache_fixture(run, source)
            authority, registry, eligibility_source = _accepted_cache_authority(
                run, selection, clearance, frames, task, frontier, policy)
            binding = _binding(
                pointer, source, selection, clearance, frames, task, frontier, policy)
            _assert_exact_rebuild(self, authority, binding)
            live_artifact = _assert_live_cache_use(
                self, run, authority, registry, eligibility_source, binding)
            _assert_correction_hold(
                self, run, registry, eligibility_source, binding, live_artifact)
            _assert_cold_replay_hold(
                self, run, registry, eligibility_source, binding)
            _assert_binding_drift_rejected(self, authority, binding)


if __name__ == "__main__":
    unittest.main()
