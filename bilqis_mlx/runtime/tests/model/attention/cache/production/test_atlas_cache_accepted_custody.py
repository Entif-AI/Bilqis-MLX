"""Actual B13 publication owns B14 use and revokes it on accepted rollover."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, attention_cache_handles, bind_accepted_cache_authority,
    decode_cache, encode_attention_cache,
)
from bilqis_mlx.runtime.atlas_cache_runtime import _capture_production_records
from bilqis_mlx.runtime.atlas_cache_eligibility import _AuthoritativeCacheIdentity
from bilqis_mlx.runtime.atlas_cache_production_custody import _capture_handle
from bilqis_mlx.runtime.bamf_bundle import (
    admission, load_bamf_generation, publish_bamf_generation,
)
from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, accepted_state,
)
from bilqis_mlx.runtime.tests.model.attention.cache.cache_authority_integration_fixture import (
    _accepted_registry, _cache_shape_patch, _context, _publish_cache_fixture,
    _selection, _source,
)
from bilqis_mlx.semantics.context_eligibility import project_context
from bilqis_mlx.semantics.domains import contract_digest


class _RowOwner:
    def require_row(self, row):
        return (row,)


def _advance_accepted_generation(run):
    parent = load_bamf_generation(Path(run) / "bamf-state.json")
    retained = accepted_state(
        parent.retained_state, parent.extents, spec=parent.topology)
    successor = derive_successor_bundle(
        parent, retained,
        parent_manifest_sha256=parent.retained_state.custody.manifest_sha256,
        delivery_events=({"event": "B14_CUSTODY_ROLLOVER"},))
    return publish_bamf_generation(
        run, successor,
        acceptance=acceptance(successor, parent=parent.retained_state),
        reserve_gib=0.)


class AcceptedCustodyCacheTests(unittest.TestCase):
    def test_actual_b13_cache_uses_b14_then_rollover_rejects_before_decode(self):
        selection = _selection()
        frames, task, frontier, policy = _context(selection.release_sha256)
        source = _source(selection, frontier)
        registry = _accepted_registry()
        with TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}
        ), patch.object(mlx_checkpoint, "assert_headroom"):
            run = Path(temporary) / "accepted-run"
            _publish_cache_fixture(run, source, host_registry=registry)
            with _cache_shape_patch(), patch(
                "bilqis_mlx.runtime.bamf_bundle.source_authority_custody."
                "read_host_system_source_authority_registry",
                return_value=registry,
            ):
                accepted = admission.bind_accepted_execution_cache(run)
                student = admission.load_accepted_generation(run)
                authority = bind_accepted_cache_authority(accepted)
                projection = project_context(frames, task, frontier, policy)
                rights = contract_digest(
                    (frontier.rights_epoch, frontier.correction_generation))
                identity = _AuthoritativeCacheIdentity(
                    accepted.accepted_manifest_sha256,
                    contract_digest({
                        "schema": "bilqis.mlx.bamf-cache-lineage/v1",
                        "run_id": accepted.run_id}),
                    student.topology.digest, selection.source_bundle_id,
                    selection.release_sha256, rights,
                    contract_digest({
                        "purpose": task.purpose,
                        "jurisdiction": task.jurisdiction,
                        "scope": task.scope}),
                    contract_digest({
                        "policy_id": policy.policy_id,
                        "policy_epoch": policy.policy_epoch,
                        "rights_epoch": policy.rights_epoch}),
                    projection.digest, "a" * 64, "b" * 64, "c" * 64, "d" * 64,
                    accepted.generation_binding, 0)
                handle = _capture_handle(identity)
                _capture_production_records(authority, {
                    handle: (
                        np.ones((256, HEAD_WIDTH), dtype=np.float32),
                        identity, _RowOwner(), object(), (0, "key"), None)
                })
                artifact, binding = encode_attention_cache(authority, handle)
                self.assertEqual(attention_cache_handles(authority), (handle,))
                self.assertEqual(
                    decode_cache(authority, artifact, binding).shape,
                    (256, HEAD_WIDTH))
                _advance_accepted_generation(run)
                with patch(
                    "bilqis_mlx.runtime.atlas_cache_records._decode_cache"
                ) as raw_decode, self.assertRaises(BilqisError):
                    decode_cache(authority, artifact, binding)
                raw_decode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
