"""Live CT-056 qualification of one consolidated Falkor service using isolated graphs."""
from __future__ import annotations

import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid

from bilqis_mlx.runtime.akasha_domains import DOMAIN_CONTRACTS
from bilqis_mlx.runtime.akasha_qualification import (
    AkashaQualificationReceipt, QualificationDataset, QualificationEnvironment,
    QualificationMeasurements, QualificationOutcomes,
)
from bilqis_mlx.runtime.akasha_security import AkashaNamespaceScope, DOMAIN_SECURITY_POLICIES
from .akasha_support import canonical_bytes, fault_phase, materialization_phase, sha256


SOURCE_HEADS = (
    ("#297", "331caf4b79bbbd6d2c9bcc55754aa47869c9e373"),
    ("#300", "da24efdc5be09915d5a835b4cda6e7e349069fad"),
    ("#301", "0bb3002d2ba815a0af4975bc06ae8f124ad4cb77"),
    ("#302", "b17a20873db1b76bc4a46e12aa868819fa7a3e15"),
)
EXPECTED_LOGICAL_DOMAIN_COUNT = 6


def _logical_isolation(access) -> bool:
    scope = AkashaNamespaceScope("entif", "bilqis")
    namespaces = {scope.namespace_for(domain) for domain in DOMAIN_CONTRACTS}
    return (len(DOMAIN_CONTRACTS) == len(DOMAIN_SECURITY_POLICIES)
            == EXPECTED_LOGICAL_DOMAIN_COUNT
            and len(namespaces) == EXPECTED_LOGICAL_DOMAIN_COUNT
            and access["denials"].get("unrelated_graph") == "NoPermissionError")


def _environment(host, port):
    from redis import Redis
    admin = Redis(host=host, port=port, username=os.environ.get("BILQIS_FALKOR_USERNAME"),
                  password=os.environ.get("BILQIS_FALKOR_PASSWORD"))
    server = str(admin.info("server").get("redis_version", "unknown"))
    return QualificationEnvironment(
        platform=platform.platform(), machine=platform.machine(), python=platform.python_version(),
        falkordb_client=version("falkordb"), redis_client=version("redis"),
        server_version=server, endpoint=f"{host}:{port}")


def _dataset(bundle, suite_path, census, prior_bytes, canonical, manifest):
    return QualificationDataset(
        release_ref=census["release_revision"], canonical_rdf_sha256=sha256(canonical),
        canonical_triples=census["canonical_rdf"]["triple_count"],
        bundle_manifest_sha256=sha256(manifest), suite_sha256=sha256(suite_path.read_bytes()),
        prior_live_proof_sha256=sha256(prior_bytes))


def _receipt(candidate, command, environment, dataset, material, faults, canonical):
    first, second = material["first_import"], material["second_import"]
    measurements = QualificationMeasurements(
        rebuild_seconds=material["rebuild_seconds"], restore_seconds=material["restore_seconds"],
        idempotent_seconds=material["idempotent_seconds"], read_latency_ms=material["latency_ms"],
        nodes=first["nodes"], edges=first["edges"], indexes=len(material["first_receipt"]["indexes"]),
        canonical_rdf_bytes=len(canonical), backup_bytes=len(material["backup"]),
        idempotent_node_growth=second["nodes"] - first["nodes"],
        idempotent_edge_growth=second["edges"] - first["edges"])
    outcomes = QualificationOutcomes(
        backup_restore_identity_match=(material["restored_receipt"]["canonical_rdf_sha256"]
                                       == material["first_receipt"]["canonical_rdf_sha256"]),
        backup_restore_census_match=material["restored_matches"],
        backup_restore_query_match=bool(material["restored_query"]),
        clean_rebuild_match=(material["rebuilt_import"] == first
                             and material["rebuilt_receipt"]["canonical_rdf_sha256"]
                             == material["first_receipt"]["canonical_rdf_sha256"]),
        stale_detected=faults["stale_detected"], corruption_detected=faults["corruption_detected"],
        partial_recovery=faults["partial_recovery"], foreign_isolation=faults["foreign_isolation"],
        restart_reconnect=faults["restart_reconnect"],
        logical_domain_isolation=_logical_isolation(material["access"]))
    return AkashaQualificationReceipt.create(
        candidate_revision=candidate, environment=environment, dataset=dataset,
        measurements=measurements, outcomes=outcomes, prerequisite_heads=SOURCE_HEADS,
        commands=(command,), residual_debt=(
            "Server-process restart is not exercised; reconnect plus interrupted-materializer cold resume is qualified.",
            "Backup is an application-level owned projection snapshot, not a provider-native server image.",
            "Semantic coverage remains whatever the pinned release receipt reports; qualification does not upgrade coverage."))


def run(bundle: Path, suite_path: Path, census_path: Path, prior_path: Path,
        output: Path, host: str, port: int, command: str):
    from lib.ithkuil.src.skos.falkor_import import connect
    output.mkdir(parents=True, exist_ok=False)
    census, suite = json.loads(census_path.read_text()), json.loads(suite_path.read_text())
    prior_bytes, canonical = prior_path.read_bytes(), (bundle / "canonical.nt").read_bytes()
    manifest = (bundle / "manifest.json").read_bytes()
    if sha256(canonical) != census["canonical_rdf"]["sha256"]:
        raise AssertionError("QUALIFICATION_CANONICAL_IDENTITY_DRIFT")
    db, token = connect(host, port), uuid.uuid4().hex[:12]
    owner = "qual298_" + token
    names = {kind: "bilqis_qual298_" + kind + "_" + token
             for kind in ("source", "restore", "rebuild", "partial")}
    material = materialization_phase(db, bundle, suite_path, suite, names, owner,
                                     host, port, output)
    faults = fault_phase(db, bundle, suite_path, names, owner, host, port, material)
    candidate = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    receipt = _receipt(candidate, command, _environment(host, port),
                       _dataset(bundle, suite_path, census, prior_bytes, canonical, manifest),
                       material, faults, canonical)
    raw = {"first_receipt": material["first_receipt"],
           "restored_receipt": material["restored_receipt"],
           "rebuilt_receipt": material["rebuilt_receipt"],
           "partial_receipt": faults["resumed_receipt"], "reset_plan": faults["reset_plan"],
           "query_case": material["query_case"], "access": material["access"]}
    (output / "raw-evidence.json").write_bytes(canonical_bytes(raw))
    (output / "qualification.json").write_text(receipt.canonical_json + "\n")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "suite", "census", "prior-proof", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--host", required=True); parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    command = " ".join(sys.argv if argv is None else [sys.executable, "-m", __name__, *argv])
    receipt = run(args.bundle, args.suite, args.census, args.prior_proof,
                  args.output, args.host, args.port, command)
    print(receipt.canonical_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
