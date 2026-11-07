"""Adversaries for B14.4 owner-bound cache rebuild eligibility."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.atlas_cache_codec import (
    HEAD_WIDTH, CacheBinding, CacheQualityObservation, CacheQualityPolicy,
    codec_manifest, decode_cache, encode_cold_cache, interactive_cache_inference,
    issue_cache_eligibility, rebuild_revoked_cache,
)
from bilqis_mlx.runtime.atlas_cache_eligibility import CacheEligibilityInputs
from bilqis_mlx.runtime.atlas_cache_records import _encode_cold_cache
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.model.attention.cache.authority_fixture import (
    OWNER_ID, PUBLIC_KEY_HEX, authority_for_registry, install_test_owner,
)
from bilqis_mlx.runtime.tests.model.attention.cache.test_atlas_cache_authority_integration import (
    _A12_OWNER, _A12_PUBLIC, _EXPORTED, _cache_shape_patch, _clearance,
    _context, _selection,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.context_eligibility import project_context
from bilqis_mlx.semantics.domains import contract_digest


def _registry() -> SourceAuthorityRegistry:
    return SourceAuthorityRegistry(tuple(sorted((
        SourceAuthorityKey(
            OWNER_ID, PUBLIC_KEY_HEX,
            (SourceAuthorityScope(DependencyKind.ARTIFACT, "cache:"),)),
        SourceAuthorityKey(
            _A12_OWNER, _A12_PUBLIC,
            (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),)),
    ), key=lambda item: item.owner_id)))


def _source(selection, frontier, *, run_id="fixture-run"):
    source = candidate(parent_state())
    return replace(
        source,
        run_id=run_id,
        provenance=replace(
            source.provenance, release_digest=selection.release_sha256),
        correction_frontier={
            **source.correction_frontier,
            "release_digest": selection.release_sha256,
            "rights_epoch": frontier.rights_epoch,
            "correction_generation": frontier.correction_generation,
        },
        compiler_features={
            **source.compiler_features,
            "rights_epoch": frontier.rights_epoch,
            "correction_generation": frontier.correction_generation,
        },
    )


def _publish(run, source):
    with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
        return publish_bamf_generation(run, source, acceptance=acceptance(source))


def _inputs(run, clearance, selection, frontier, frames, task, policy):
    return CacheEligibilityInputs(
        run / "bamf-state.json", clearance, selection, frontier,
        _EXPORTED, frames, task, policy,
        lambda binding: np.zeros((256, HEAD_WIDTH), dtype=np.float32),
    )


def _binding_for(pointer, source, selection, clearance, frontier, frames, task, policy):
    projection = project_context(frames, task, frontier, policy)
    purpose = contract_digest({
        "purpose": task.purpose, "jurisdiction": task.jurisdiction,
        "scope": task.scope,
    })
    policy_digest = contract_digest({
        "policy_id": policy.policy_id,
        "policy_epoch": policy.policy_epoch,
        "rights_epoch": policy.rights_epoch,
    })
    lineage = contract_digest({
        "schema": "bilqis.mlx.bamf-cache-lineage/v1",
        "run_id": source.run_id,
    })
    with _cache_shape_patch():
        inference = execution_generation_digest(
            source.retained_state.optimizer.parameters,
            spec=source.topology,
            extents=source.extents,
        )
    return CacheBinding(
        codec_manifest(), pointer["manifest_sha256"], lineage,
        source.topology.digest, selection.source_bundle_id,
        selection.release_sha256, clearance.clearance_sha256, purpose,
        policy_digest, projection.digest, "a" * 64, "b" * 64,
        "c" * 64, "d" * 64, inference, 17, OWNER_ID, PUBLIC_KEY_HEX,
    )


class CacheAuthorityCurrentnessTests(unittest.TestCase):
    def setUp(self):
        install_test_owner(self, eligibility=False, current_binding=False)
        self.selection = _selection()
        self.frames, self.task, self.frontier, self.policy = _context(
            self.selection.release_sha256)
        self.clearance = _clearance(self.selection, self.frontier)

    def _run(self, root, *, run_id="fixture-run"):
        run = Path(root) / run_id
        source = _source(self.selection, self.frontier, run_id=run_id)
        pointer = _publish(run, source)
        binding = _binding_for(
            pointer, source, self.selection, self.clearance, self.frontier,
            self.frames, self.task, self.policy,
        )
        return run, source, binding

    def test_valid_other_run_cannot_replace_authority_bound_b13_run(self):
        with TemporaryDirectory() as temporary, patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}):
            run, _, binding = self._run(temporary)
            _, _, other_binding = self._run(temporary, run_id="other-run")
            inputs = _inputs(
                run, self.clearance, self.selection, self.frontier,
                self.frames, self.task, self.policy)
            authority = authority_for_registry(
                _registry(), eligibility_source=lambda: inputs)
            with _cache_shape_patch():
                issue_cache_eligibility(authority, binding)
                with self.assertRaises(BilqisError):
                    issue_cache_eligibility(authority, other_binding)

    def test_matching_caller_policy_and_context_cannot_replace_owner_policy(self):
        with TemporaryDirectory() as temporary, patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")}):
            run, source, binding = self._run(temporary)
            inputs = _inputs(
                run, self.clearance, self.selection, self.frontier,
                self.frames, self.task, self.policy)
            authority = authority_for_registry(
                _registry(), eligibility_source=lambda: inputs)
            changed_policy = replace(
                self.policy, policy_id="caller:policy",
                policy_epoch=self.policy.policy_epoch + 1)
            changed_frames = tuple(replace(
                frame, policy_epoch=changed_policy.policy_epoch)
                for frame in self.frames)
            caller_binding = _binding_for(
                {"manifest_sha256": binding.generation_sha256}, source,
                self.selection, self.clearance, self.frontier,
                changed_frames, self.task, changed_policy)
            with _cache_shape_patch(), self.assertRaises(BilqisError):
                issue_cache_eligibility(authority, caller_binding)

    def test_post_issue_policy_drift_rejects_before_rebuild_persist(self):
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
            changed_policy = replace(
                self.policy, policy_id="owner:next-policy",
                policy_epoch=self.policy.policy_epoch + 1)
            changed_frames = tuple(replace(
                frame, policy_epoch=changed_policy.policy_epoch)
                for frame in self.frames)
            current[0] = replace(
                current[0], frames=changed_frames, policy=changed_policy)
            stale_binding = replace(binding, generation_sha256="f" * 64)
            stale = _encode_cold_cache(
                np.ones((256, HEAD_WIDTH), dtype=np.float32),
                stale_binding.codec_manifest, binding=stale_binding,
                authority=authority)
            persisted = []
            with _cache_shape_patch(), self.assertRaises(BilqisError):
                rebuild_revoked_cache(
                    authority, stale, binding, eligibility_receipt=receipt,
                    persist=persisted.append)
            self.assertEqual(persisted, [])

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
                    policy=CacheQualityPolicy(0.01),
                )
            self.assertEqual(
                (result.value, result.used_cache, result.fallback_reason),
                ("FP32", False, "BINDING_MISMATCH"),
            )

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
