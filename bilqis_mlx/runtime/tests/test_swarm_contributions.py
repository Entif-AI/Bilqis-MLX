from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import copy
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.swarm_contributions import (
    AcceptanceContract,
    ContributionArtifact,
    ContributionClass,
    ContributionDisposition,
    EnvironmentIdentity,
    IndependentEvaluation,
    RemoteWorkManifest,
    ReplayLedger,
    ResourceBudget,
    WorkerIdentity,
    WorkerReceipt,
    admit_remote_contribution,
    dispatch_eligible_work,
    verify_remote_receipt,
)

GENERATION = "a" * 64
SOURCE = "b" * 64
TOPOLOGY = "c" * 64
MODEL = "d" * 64
ACCEPTANCE = "e" * 64
BINDING = "f" * 64
KEY = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("42" * 32))
PUBLIC = KEY.public_key().public_bytes_raw().hex()


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def manifest(kind: ContributionClass = ContributionClass.EVALUATION) -> RemoteWorkManifest:
    return RemoteWorkManifest.create(
        manifest_id="work:fixture-001",
        retained_generation=GENERATION,
        source_release=SOURCE,
        capability_id="capability:fixture",
        seed=73,
        partition_id="partition:0001",
        resource_budget=ResourceBudget(max_examples=32, max_steps=8, max_seconds=60, max_bytes=1_000_000),
        model_identity=MODEL,
        topology_identity=TOPOLOGY,
        mlx_identity="mlx:0.30.1",
        rights_scope="PUBLIC_FIXTURE",
        contribution_class=kind,
        acceptance=AcceptanceContract(
            contract_digest=ACCEPTANCE,
            minimum_score=0.75,
            requires_retention=True,
        ),
        expires_at=2_000,
        replay_id="replay:fixture-001",
        base_binding_digest=BINDING if kind is ContributionClass.ADAPTER_DELTA else None,
    )


def receipt(work: RemoteWorkManifest, *, score: float = 1.0,
            artifact: ContributionArtifact | None = None) -> WorkerReceipt:
    artifact = artifact or ContributionArtifact(
        artifact_type=work.expected_artifact_type,
        payload=b"public synthetic result",
        base_binding_digest=work.base_binding_digest,
        affected_parameter_ids=("adapter.0.A",) if work.contribution_class is ContributionClass.ADAPTER_DELTA else (),
    )
    unsigned = WorkerReceipt.unsigned(
        manifest=work,
        worker=WorkerIdentity(
            worker_id="worker:public-fixture",
            public_key_hex=PUBLIC,
            environment=EnvironmentIdentity(
                hardware="Apple M3 Ultra",
                os="macOS-fixture",
                mlx_version="0.30.1",
                backend="metal",
                device_count=1,
            ),
        ),
        artifact=artifact,
        claimed_score=score,
        completed_at=1_500,
    )
    return unsigned.with_signature(KEY.sign(unsigned.signing_bytes()).hex())


class SwarmContributionTests(unittest.TestCase):
    def test_disposable_worker_receives_frozen_manifest_and_returns_signed_content_addressed_receipt(self):
        work = manifest()
        result = receipt(work)
        self.assertEqual(result.manifest_digest, work.digest)
        self.assertEqual(result.artifact.digest, digest(b"public synthetic result"))
        self.assertEqual(result.worker.public_key_hex, PUBLIC)
        verify_remote_receipt(work, result, now=1_600, replay_ledger=ReplayLedger())

    def test_modified_replayed_expired_wrong_generation_or_source_result_is_rejected(self):
        work = manifest()
        result = receipt(work)
        ledger = ReplayLedger()
        verified = verify_remote_receipt(work, result, now=1_600, replay_ledger=ledger)
        self.assertEqual(verified.replay_ledger.consumed_replay_ids, (work.replay_id,))
        with self.assertRaises(BilqisError):
            verify_remote_receipt(work, result, now=1_601, replay_ledger=verified.replay_ledger)
        with self.assertRaises(BilqisError):
            verify_remote_receipt(work, result, now=2_001, replay_ledger=ReplayLedger())
        wrong_generation = replace(work, retained_generation="9" * 64)
        with self.assertRaises(BilqisError):
            verify_remote_receipt(wrong_generation, result, now=1_600, replay_ledger=ReplayLedger())
        wrong_source = replace(work, source_release="8" * 64)
        with self.assertRaises(BilqisError):
            verify_remote_receipt(wrong_source, result, now=1_600, replay_ledger=ReplayLedger())
        tampered = copy.copy(result)
        object.__setattr__(tampered, "claimed_score", 0.99)
        with self.assertRaises(BilqisError):
            verify_remote_receipt(work, tampered, now=1_600, replay_ledger=ReplayLedger())

    def test_signed_environment_and_resource_envelope_are_tamper_evident(self):
        work = manifest()
        result = receipt(work)
        changed = copy.copy(result)
        object.__setattr__(changed.worker, "environment", replace(
            result.worker.environment, hardware="forged-hardware"))
        with self.assertRaises(BilqisError):
            verify_remote_receipt(work, changed, now=1_600, replay_ledger=ReplayLedger())

        tiny = replace(work, resource_budget=replace(work.resource_budget, max_bytes=4))
        tiny_result = receipt(tiny)
        with self.assertRaises(BilqisError):
            verify_remote_receipt(tiny, tiny_result, now=1_600, replay_ledger=ReplayLedger())

    def test_retention_requirement_cannot_be_bypassed_by_passing_score(self):
        work = manifest()
        result = receipt(work)
        calls = []
        decision = admit_remote_contribution(
            work, result, now=1_600, replay_ledger=ReplayLedger(),
            independent_evaluator=lambda *_: IndependentEvaluation(
                True, 1.0, "6" * 64, "retention:failed"),
            canonical_admitter=lambda *_: calls.append("admitted"),
        )
        self.assertIs(decision.disposition, ContributionDisposition.REJECTED)
        self.assertEqual(calls, [])

    def test_worker_score_is_evidence_not_authority_for_non_neural_admission(self):
        work = manifest(ContributionClass.EVALUATION)
        result = receipt(work, score=1.0)
        calls = []
        def evaluator(_work, _receipt):
            calls.append("evaluated")
            return IndependentEvaluation(False, 0.25, "1" * 64, "retention:failed")
        decision = admit_remote_contribution(
            work, result, now=1_600, replay_ledger=ReplayLedger(),
            independent_evaluator=evaluator,
            canonical_admitter=lambda *_: self.fail("rejected contribution reached canonical admitter"),
        )
        self.assertEqual(calls, ["evaluated"])
        self.assertIs(decision.disposition, ContributionDisposition.REJECTED)
        self.assertEqual(decision.independent_score, 0.25)
        self.assertEqual(result.claimed_score, 1.0)

    def test_bounded_adapter_candidate_requires_exact_binding_and_independent_evaluation(self):
        work = manifest(ContributionClass.ADAPTER_DELTA)
        result = receipt(work, score=0.0)
        admitted = []
        decision = admit_remote_contribution(
            work, result, now=1_600, replay_ledger=ReplayLedger(),
            independent_evaluator=lambda *_: IndependentEvaluation(True, 0.9, "2" * 64, "retention:pass"),
            canonical_admitter=lambda w, r, e: admitted.append((w.digest, r.artifact.digest, e.evidence_digest)),
        )
        self.assertIs(decision.disposition, ContributionDisposition.ADMITTED)
        self.assertEqual(len(admitted), 1)
        wrong = receipt(work, artifact=ContributionArtifact(
            artifact_type=work.expected_artifact_type,
            payload=b"wrong binding delta",
            base_binding_digest="7" * 64,
            affected_parameter_ids=("adapter.0.A",),
        ))
        with self.assertRaises(BilqisError):
            admit_remote_contribution(
                work, wrong, now=1_600, replay_ledger=ReplayLedger(),
                independent_evaluator=lambda *_: IndependentEvaluation(True, 1.0, "2" * 64, "retention:pass"),
                canonical_admitter=lambda *_: None,
            )

    def test_dense_update_combination_remains_fail_closed(self):
        with self.assertRaises(BilqisError):
            manifest(ContributionClass.DENSE_UPDATE)

    def test_rejected_contribution_cannot_mutate_canonical_state(self):
        state = {"generation": GENERATION, "weights": "weights:stable", "optimizer": "optimizer:stable",
                 "motifs": "motifs:stable", "semantics": SOURCE, "teacher": "teacher:stable"}
        before = dict(state)
        work = manifest()
        result = receipt(work)
        decision = admit_remote_contribution(
            work, result, now=1_600, replay_ledger=ReplayLedger(),
            independent_evaluator=lambda *_: IndependentEvaluation(False, 0.1, "3" * 64, "bad"),
            canonical_admitter=lambda *_: state.update(generation="ILLEGAL"),
        )
        self.assertIs(decision.disposition, ContributionDisposition.REJECTED)
        self.assertEqual(state, before)

    def test_environment_identity_is_signed_and_materially_different_workers_remain_explainable(self):
        work = manifest()
        first = receipt(work)
        other_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("43" * 32))
        other_worker = replace(
            first.worker,
            public_key_hex=other_key.public_key().public_bytes_raw().hex(),
            environment=EnvironmentIdentity(
                hardware="NVIDIA CUDA fixture", os="Linux-fixture",
                mlx_version="not-mlx", backend="cuda-adapter-fixture", device_count=2,
            ),
        )
        unsigned = WorkerReceipt.unsigned(
            manifest=work, worker=other_worker, artifact=first.artifact,
            claimed_score=first.claimed_score, completed_at=first.completed_at)
        second = unsigned.with_signature(other_key.sign(unsigned.signing_bytes()).hex())
        self.assertNotEqual(first.worker.environment.digest, second.worker.environment.digest)
        verify_remote_receipt(work, first, now=1_600, replay_ledger=ReplayLedger())
        verify_remote_receipt(work, second, now=1_600, replay_ledger=ReplayLedger())

    def test_swarm_dispatch_is_opportunistic_not_local_training_prerequisite(self):
        work = manifest()
        self.assertEqual(dispatch_eligible_work((work,), available_workers=()), ())
        dispatched = dispatch_eligible_work((work,), available_workers=("worker:1",))
        self.assertEqual(dispatched, (("worker:1", work.digest),))

    def test_private_scope_is_not_dispatchable_in_public_worker_protocol(self):
        with self.assertRaises(BilqisError):
            replace(manifest(), rights_scope="PRIVATE_REAL")


if __name__ == "__main__":
    unittest.main()
