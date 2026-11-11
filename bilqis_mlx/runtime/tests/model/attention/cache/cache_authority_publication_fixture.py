"""Accepted-generation publication helper for B14 cache authority fixtures."""
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation, publish_bamf_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, accepted_state, genesis_preparation,
    provision_source_authority_registry, shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    genesis_feature_source_patch, issue_feature_authority, source_features,
)


def _publish_cache_fixture(run, source, *, host_registry=None):
    from .cache_authority_integration_fixture import _accepted_registry

    features = source_features(release=source.provenance.release_digest)
    feature_authority = issue_feature_authority(features)
    host_patch = (
        patch(
            "bilqis_mlx.runtime.bamf_bundle.source_authority_custody."
            "read_host_system_source_authority_registry",
            return_value=host_registry,
        ) if host_registry is not None else nullcontext()
    )
    with shape_patch(), host_patch, genesis_feature_source_patch(features), patch.object(
            mlx_checkpoint, "assert_headroom"):
        prepared = genesis_preparation(
            run_id=source.run_id, foundation_features=feature_authority)
        from bilqis_mlx.runtime.bamf_bundle import publish_initial_generation
        pointer = publish_initial_generation(run, prepared, reserve_gib=0.)
        parent = load_bamf_generation(Path(run) / "bamf-state.json")
        retained = accepted_state(
            parent.retained_state, parent.extents, spec=parent.topology)
        from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle
        successor = derive_successor_bundle(
            parent, retained, parent_manifest_sha256=pointer["manifest_sha256"],
            delivery_events=({"event": "FIXTURE_CACHE_AUTHORITY"},))
        correction_frontier = {
            **successor.correction_frontier,
            "rights_epoch": source.correction_frontier["rights_epoch"],
            "correction_generation": source.correction_frontier[
                "correction_generation"],
        }
        source_registry = source.correction_frontier.get(
            "source_authority_registry_sha256")
        source_registry_record = source.correction_frontier.get(
            "source_authority_registry")
        for name, value in (
                ("source_authority_registry_sha256", source_registry),
                ("source_authority_registry", source_registry_record)):
            if value is not None:
                correction_frontier[name] = value
        if host_registry is not None:
            from bilqis_mlx.runtime.bamf_bundle.source_authority_custody import (
                HOST_SYSTEM_SOURCE_AUTHORITY_ORIGIN,
            )
            correction_frontier["source_authority_registry_origin"] = (
                HOST_SYSTEM_SOURCE_AUTHORITY_ORIGIN)
        successor = replace(
            successor,
            correction_frontier=correction_frontier,
            compiler_features={
                **successor.compiler_features,
                "rights_epoch": source.compiler_features["rights_epoch"],
                "correction_generation": source.compiler_features[
                    "correction_generation"],
            },
        )
        if ((source_registry is not None or source_registry_record is not None)
                and host_registry is None):
            provision_source_authority_registry(run, _accepted_registry())
        published = publish_bamf_generation(
            run, successor,
            acceptance=acceptance(successor, parent=parent.retained_state),
            reserve_gib=0.)
        return published, load_bamf_generation(Path(run) / "bamf-state.json")
