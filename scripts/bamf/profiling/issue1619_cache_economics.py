"""#1619: disposable, non-authorizing parent artifact economics witness.

Run as a module from the checkout. Never opens the operational data plane.
Persisted assessments are audit records, not live C05 authority.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter_ns

from bilqis_mlx.data_plane import DataPlane
from bilqis_mlx.runtime.capability_retention import (
    CompleteSolver, EvidenceStage, evaluate_capabilities,
)
from bilqis_mlx.runtime.capability_retention_foundation import FoundationRetentionPolicy
from bilqis_mlx.runtime._factory_parent_assessment_cache import (
    clear_parent_assessment_cache, use_parent_assessment,
)
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
    PARENT, _screen_inputs,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.parent_assessment_cache_timing import (
    _identity,
)

MODULE = "scripts.bamf.profiling.issue1619_cache_economics"
TRIALS = 8
PREFIX = "issue1619-disposable/v1:"


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def key(identity):
    return PREFIX + digest(encode(identity))


def write(plane, identity, payload):
    return plane.put_object_reference(
        key(identity), encode({"identity": identity, "payload": payload}))


def read(plane, identity):
    reference = plane.get_object_reference(key(identity))
    if reference is None:
        return None
    sha, raw = reference
    if digest(raw) != sha:
        raise ValueError("object digest mismatch")
    envelope = json.loads(raw)
    if envelope["identity"] != identity:
        raise ValueError("dependency mismatch")
    return envelope["payload"]


def timed(call):
    start = perf_counter_ns()
    value = call()
    return value, perf_counter_ns() - start


def fixture():
    parent, _, target, _, cohorts = _screen_inputs(protected_loss=12)
    source = cohorts[2]
    groups = source.capability_groups
    policy = FoundationRetentionPolicy(
        groups, tuple(dict.fromkeys(group for _, group in groups)),
        tuple((cap, 1) for cap, _ in groups if cap != target),
        6, source.expected_case_digest,
    )
    cohort = replace(source, policy_sha256=policy.digest(),
                     evidence_stage=EvidenceStage.FOUNDATION_ACQUISITION)
    calls = []

    def context(goal, generation):
        calls.append(goal.goal_id)
        return parent.context_for(goal, generation)

    return CompleteSolver(context, parent.budget), cohort, calls


def audit_record(assessment):
    return {
        "assessment_sha256": assessment.digest(),
        "scores": {cap: list(assessment.score(cap))
                   for cap, _ in assessment.cohort.capability_groups},
        "results": [result.replay_record() for result in assessment.results],
        "solver_contracts": list(assessment.solver_contracts),
    }


def require_equal(actual, expected):
    if encode(actual) != encode(expected):
        raise AssertionError("artifact differs from recomputation")


def cold_read(path, identity_path):
    identity = json.loads(Path(identity_path).read_bytes())
    plane, open_ns = timed(lambda: DataPlane(Path(path)))
    try:
        record, read_ns = timed(lambda: read(plane, identity))
        if record is None:
            raise AssertionError("cold cache miss")
        return {"payload_sha256": digest(encode(record)),
                "open_ns": open_ns, "read_ns": read_ns}
    finally:
        plane.close()


def audit_trials(solver, cohort, calls, identity):
    baseline, memory = [], []
    expected = None
    for _ in range(TRIALS):
        record, elapsed = timed(lambda: audit_record(
            evaluate_capabilities(solver, cohort, PARENT)))
        if expected is not None:
            require_equal(record, expected)
        expected = record
        baseline.append(elapsed)
    recompute_calls = len(calls)
    calls.clear()
    clear_parent_assessment_cache()
    hits = []
    for _ in range(TRIALS):
        def memory_read():
            assessment, receipt = use_parent_assessment(
                identity, solver, cohort, PARENT)
            return audit_record(assessment), receipt.reused
        (record, reused), elapsed = timed(memory_read)
        require_equal(record, expected)
        memory.append(elapsed)
        hits.append(reused)
    if hits != [False] + [True] * (TRIALS - 1):
        raise AssertionError(hits)
    memory_calls = len(calls)
    if recompute_calls != TRIALS * len(cohort.cases) or memory_calls != len(cohort.cases):
        raise AssertionError("solver census drift")
    return expected, baseline, memory, recompute_calls, memory_calls, hits


def verify_audit_misses(plane, dependencies, expected):
    mutations = {}
    for field, value in dependencies["binding"].items():
        changed = ("other-run" if field == "run_id" else
                   value + 1 if type(value) is int else
                   "0" * 64 if value != "0" * 64 else "1" * 64)
        altered = {**dependencies, "binding": {**dependencies["binding"], field: changed}}
        result, elapsed = timed(lambda: read(plane, altered))
        if result is not None:
            raise AssertionError(field)
        mutations[field] = elapsed
    altered = {**dependencies, "branch_revision": "different-branch"}
    if read(plane, altered) is not None:
        raise AssertionError("branch cache hit")
    # Even an intact CAS object must not satisfy a different dependency key.
    plane.put_object_reference(key(altered), encode({
        "identity": dependencies, "payload": expected}))
    try:
        read(plane, altered)
    except ValueError:
        pass
    else:
        raise AssertionError("mismatched envelope accepted")
    return mutations


def assessment_economics(root, revision):
    solver, cohort, calls = fixture()
    identity = _identity(cohort)
    dependencies = {"branch_revision": revision, "kind": "c05-audit",
                    "binding": asdict(identity)}
    plane = DataPlane(root / "audit.sqlite3")
    try:
        expected, baseline, memory, recompute_calls, memory_calls, hits = audit_trials(
            solver, cohort, calls, identity)
        durable = []
        raw, encode_ns = timed(lambda: encode(expected))
        _, write_ns = timed(lambda: write(plane, dependencies, expected))
        for _ in range(TRIALS):
            record, elapsed = timed(lambda: read(plane, dependencies))
            require_equal(record, expected)
            durable.append(elapsed)
        mutations = verify_audit_misses(plane, dependencies, expected)
        stats = plane.stats()
    finally:
        plane.close()
    identity_path = root / "audit-identity.json"
    identity_path.write_bytes(encode(dependencies))
    output, cold_wall_ns = timed(lambda: subprocess.check_output([
        sys.executable, "-B", "-m", MODULE, "cold",
        str(root / "audit.sqlite3"), str(identity_path)], text=True, timeout=90))
    cold = json.loads(output)
    if cold["payload_sha256"] != digest(raw):
        raise AssertionError("cold record mismatch")
    return {
        "scope": "C05 deterministic fixed-school audit record; not restorable assessment authority",
        "cases": len(cohort.cases), "trials": TRIALS, "identity": dependencies,
        "recompute_ns": baseline, "memory_ns": memory, "durable_ns": durable,
        "recompute_solver_calls": recompute_calls, "memory_solver_calls": memory_calls,
        "memory_hits": sum(hits), "durable_hits": TRIALS,
        "encode_ns": encode_ns, "write_ns": write_ns, "cold": cold,
        "cold_process_wall_ns": cold_wall_ns,
        "payload_bytes": len(raw), "plane_stats": stats,
        "invalidations_ns": mutations, "branch_miss": True,
        "mismatched_envelope_rejected": True,
        "assessment_sha256": expected["assessment_sha256"],
        "payload_sha256": digest(raw),
        "memory_saved_ns": sum(baseline) - sum(memory),
        "durable_saved_ns_after_population": sum(baseline) - sum(durable) - write_ns - baseline[0],
        "median_recompute_ns": statistics.median(baseline),
        "median_memory_ns": statistics.median(memory),
        "median_durable_ns": statistics.median(durable),
    }


def main():
    if sys.argv[1] == "cold":
        print(json.dumps(cold_read(*sys.argv[2:])))
        return
    from scripts.bamf.profiling.issue1619_native_artifact import native_economics
    with tempfile.TemporaryDirectory(prefix="issue1619-") as temp:
        root = Path(temp)
        receipt = {"schema": "bilqis.spike.1619/v1", "authorizing": False,
                   "revision": sys.argv[1],
                   "assessment": assessment_economics(root, sys.argv[1]),
                   "native_artifact": native_economics(root, sys.argv[1])}
        print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
