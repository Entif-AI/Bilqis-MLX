"""Generation setup and publication mechanics for disposable C05 witnesses."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime._factory_identity_evaluation import _raw_issue_owner_evaluation
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLedger
from bilqis_mlx.runtime.bamf_bundle import (
    issue_initial_foundation_feature_authority, prepare_initial_generation,
    publish_initial_generation,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, bind_accepted_execution_cache, derive_motif_successor_bundle,
    derive_successor_bundle, load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle.genesis.foundation import initial_foundation_sidecars
from bilqis_mlx.runtime.bamf_bundle.genesis.preparation_authority import (
    _factory_generation_provenance,
)
from bilqis_mlx.runtime.bamf_bundle.genesis.records import successor_candidate_identity_digest
from bilqis_mlx.runtime.capability_retention import Decision, DecisionStatus
from bilqis_mlx.runtime.factory_retention_owner import (
    bind_current_retention_protection_plan, bind_current_retention_source_rows,
    evaluate_factory_retention_candidate,
)
from bilqis_mlx.runtime.foundation_teacher_owner import derive_accepted_teacher_successor
from bilqis_mlx.runtime.model_topology_v2 import b01_generation_authority, b01_generation_extents
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    C05_GENESIS_SEED, HP,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.owner_live_candidate_support import TARGET
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    issue_factory_authority,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import retention_decision
from bilqis_mlx.runtime.tests.custody.bamf_bundle.publication.publication_helpers import (
    host_source_authority_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection


def _initialize_generation(run_dir: Path, source_context, snapshot, artifact):
    run_id = f"factory-c05-live-{run_dir.name}"
    selection = AtlasArtifactSelection(
        str(artifact), snapshot.bundle_id, snapshot.release_sha256,
        snapshot.source_bundle_id)
    features = issue_initial_foundation_feature_authority(selection)
    origin = Checkpoint("7" * 64, "bundles/c05-closeout-origin", 0, True)
    factory = issue_factory_authority(source_context.release, source_context.graph, origin)
    provenance = _factory_generation_provenance(source_context.release, features)
    with host_source_authority_patch(AUTHORITY):
        semantic, compiler, *_ = initial_foundation_sidecars(
            source_context.release, factory.admission, source_context.graph,
            run_seed=C05_GENESIS_SEED, feature_authority=features)
        motif = MotifManifest(provenance.release_digest)
        extents = b01_generation_extents(
            semantic_abi=semantic, compiler_features=compiler,
            motif_page_count=1, motif_key_map_digest=motif.digest)
        prepared = prepare_initial_generation(
            run_id=run_id, run_seed=C05_GENESIS_SEED,
            graph=source_context.graph, factory_authority=factory,
            model_authority=b01_generation_authority(extents),
            optimizer_hyperparameters=HP, provenance=provenance,
            foundation_features=features,
            delivery_events=({
                "event": "FACTORY_C05_GENESIS", "optimizer_step": 0},))
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom",
            return_value=None,
        ):
            publish_initial_generation(run_dir, prepared, reserve_gib=0.)
    parent = load_accepted_generation(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    accepted_context = AcceptedRuntimeHost(run_dir).source_context(
        graph=source_context.graph, source_root=source_context.source_root)
    bind_current_retention_protection_plan(accepted_context, parent, cache)
    bind_current_retention_source_rows(accepted_context, cache, TARGET)
    return parent, cache, accepted_context


def _publish_c05_successor(run_dir, source_context, parent, cache, artifact, transaction):
    evaluation = evaluate_factory_retention_candidate(
        source_context, transaction, str(artifact), TARGET, run_dir=run_dir)
    decision = issue_factory_retention_decision(evaluation)
    if not decision.accepted:
        raise AssertionError(
            "C05 Factory retention did not accept source-owned candidate: "
            f"reason={decision.reason} evidence={decision.evidence_sha256} "
            f"policy={decision.policy_sha256} "
            f"blocking_capability={evaluation.decision.blocking_capability}")
    retained = resolve_candidate(transaction, accepted=True)
    successor = derive_successor_bundle(
        parent, retained, parent_manifest_sha256=cache.accepted_manifest_sha256,
        delivery_events=({
            "event": "BAMF_GENERATION_ACCEPTED",
            "optimizer_step": retained.optimizer_step,
        },))
    with patch("bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom", return_value=None):
        published = accept_and_publish(
            run_dir, successor, retained, decision=decision,
            feature_sha256=successor.extents.factor_map_digest,
            training_authorities=transaction.training_authorities)
    return successor, retained, published


def _publish_disposable_source_qualified_successor(
        run_dir, parent, cache, transaction, *, visit=None):
    """Publish one source-trained step solely to create disposable accepted lineage."""
    retained = resolve_candidate(transaction, accepted=True)
    delivery_events = ({
        "event": "BAMF_GENERATION_ACCEPTED",
        "optimizer_step": retained.optimizer_step,
    },)
    if visit is not None:
        successor = derive_accepted_teacher_successor(
            run_dir, retained, visit, delivery_events=delivery_events,
            candidate_transaction=transaction)
    elif transaction.motif_transition is None:
        successor = derive_successor_bundle(
            parent, retained, parent_manifest_sha256=cache.accepted_manifest_sha256,
            delivery_events=delivery_events)
    else:
        successor = derive_motif_successor_bundle(
            parent, transaction, retained_state=retained,
            parent_manifest_sha256=cache.accepted_manifest_sha256,
            delivery_events=delivery_events)
    if transaction.motif_transition is None:
        decision = retention_decision(parent=parent.retained_state, retained=retained)
    else:
        evaluation = _raw_issue_owner_evaluation(
            Decision(
                DecisionStatus.ELIGIBLE, "PAIRED_SCREEN_WITHIN_BUDGET",
                "a" * 64, "b" * 64, "c" * 64, "d" * 64,
                evaluated_capability_ids=(TARGET,)),
            candidate_identity_digest(parent.retained_state),
            candidate_identity_digest(retained),
            successor_candidate_identity_digest(successor),
            None, parent_state=parent.retained_state, candidate_state=retained,
            parent_binding=None, candidate_binding=None, baseline_transition=None,
            baseline_ledger=BaselineLedger.from_optional_record(parent.baseline_evidence),
            championship_cohort=None, championship_assessment=None)
        decision = issue_factory_retention_decision(evaluation)
    with patch("bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom", return_value=None):
        published = accept_and_publish(
            run_dir, successor, retained, decision=decision,
            feature_sha256=successor.extents.factor_map_digest,
            reserve_gib=0., training_authorities=transaction.training_authorities)
    return successor, retained, published


def _assert_published_generation_one(run_dir, retained, published):
    cold = load_accepted_generation(run_dir)
    if (cold.generation != 1
            or candidate_identity_digest(cold.retained_state)
            != candidate_identity_digest(retained)
            or published["generation"] != 1):
        raise AssertionError("C05 source-owned generation-one publication drift")


__all__ = (
    "_assert_published_generation_one", "_initialize_generation",
    "_publish_c05_successor", "_publish_disposable_source_qualified_successor",
)
