from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from collections import Counter
from unittest.mock import patch

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics import atlas_projection
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry,
    BANK_SIZE,
    FormalDomainBinding,
    compile_atlas_release,
    load_atlas_snapshot,
    persist_atlas_release,
    validate_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.publication import json_bytes


ROOT = Path(__file__).resolve().parents[5]
FIXTURES = ROOT / "lib/ithkuil/tests/fixtures"
LEGACY_ABI = ROOT / "bilqis_mlx/semantics/legacy_abi_v1.json"
PRIOR_ABI = ROOT / "bilqis_mlx/semantics/copular_registry_v1.json"
NUMERIC = ROOT / "bilqis_mlx/semantics/numeric_v1.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bindings():
    return (
        FormalDomainBinding(
            "boolean", "bilqis_mlx/semantics/legacy_abi_v1.json", _sha(LEGACY_ABI),
            ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
            ("B.NOT", "B.AND"),
        ),
        FormalDomainBinding(
            "numeric", "bilqis_mlx/semantics/numeric_v1.json", _sha(NUMERIC),
            ("bilqis.numeric/v1:school.op.COUNT", "bilqis.numeric/v1:school.op.SUCC"),
            ("C.COUNT", "C.SUCCESSOR"),
        ),
    )


def _fixture_bundle(root: Path):
    source_id = "NI-LEXICON-CURRICULUM"
    root_id = Identity("root", (source_id, "ROOT-TEST")).iri
    sense_a = Identity("sense", (source_id, "ROOT-TEST", "STEM 1", "BSC")).iri
    sense_b = Identity("sense", (source_id, "ROOT-TEST", "STEM 2", "OBJ")).iri
    held_id = Identity("sense", (source_id, "ROOT-HELD", "STEM 1", "BSC")).iri

    graph = Graph()
    for subject, label in ((root_id, "source root"), (sense_a, "first sense"),
                           (sense_b, "second sense"), (held_id, "tempting held sense")):
        iri = URIRef(subject)
        graph.add((iri, RDF.type, SKOS.Concept))
        graph.add((iri, SKOS.prefLabel, Literal(label, lang="en")))
        graph.add((iri, DCTERMS.source, URIRef("urn:fixture:source")))
    graph.add((URIRef(root_id), SKOS.notation, Literal("-T-")))
    graph.add((URIRef(root_id), SKOS.notation, Literal("-T-", datatype=XSD.string)))
    graph.add((URIRef(root_id), SKOS.notation, Literal("-Tʼ-")))
    graph.add((URIRef(root_id), SKOS.altLabel, Literal("variant")))
    graph.add((URIRef(root_id), SKOS.altLabel, Literal("variant", lang="en")))
    graph.add((URIRef(root_id), SKOS.narrower, URIRef(sense_a)))
    graph.add((URIRef(root_id), SKOS.narrower, URIRef(sense_b)))
    canonical = canonicalize(graph)

    coverage = json.loads((FIXTURES / "coverage_valid.json").read_text())
    coverage["canonical_rdf"] = {"sha256": canonical.sha256,
                                 "triple_count": canonical.triple_count}
    lexical = coverage["domains"]["lexicon"]["rows"]
    lexical[0]["semantic_iri"] = root_id
    lexical[1]["semantic_iri"] = sense_a
    lexical.append({
        "key": "LEXSENSE-L3",
        "owner": "#55",
        "reason_code": "EMITTED_LEXICON_SENSE",
        "semantic_iri": sense_b,
        "status": "EMITTED",
        "table": "lexicon_root_senses",
    })
    coverage["domains"]["lexicon"]["source_rows"] += 1
    coverage["domains"]["lexicon"]["dispositions"]["EMITTED"] = 3
    coverage["domains"]["lexicon"]["semantic_counts"]["senses"] = 2
    mapping = coverage["domains"]["mapping"]["rows"]
    mapping[0]["semantic_iri"] = held_id
    coverage["totals"]["dispositions"]["EMITTED"] += 1

    source_rows = [
        {"domain": domain, "table": row["table"], "key": row["key"]}
        for domain, receipt in coverage["domains"].items() for row in receipt["rows"]
    ]
    self_count = len(source_rows)
    coverage["totals"]["source_rows"] = self_count
    coverage_payload = json_bytes(coverage)
    gates = [
        {"gate": "coverage", "version": "1.0.0", "status": "passed",
         "evidence": {"canonical_rdf": coverage["canonical_rdf"], "build_status": "partial"}},
        {"gate": "no-omission", "version": "1.0.0", "status": "passed",
         "evidence": {"source_rows": self_count, "accounted_rows": self_count}},
        {"gate": "determinism", "version": "1.0.0", "status": "passed",
         "evidence": {"equal": True}},
        {"gate": "shacl", "version": "1.0.0", "status": "passed",
         "evidence": {"conforms": True}},
    ]
    conformance = {
        "schema": "bilqis.skos.conformance/v1", "status": "complete",
        "canonical_sha256": canonical.sha256, "failed_gates": [], "gates": gates,
        "coverage_status": "partial",
    }
    files = {
        "canonical.nt": canonical.payload,
        "comparison.nt": canonical.payload,
        "coverage.json": coverage_payload,
        "source-rows.json": json_bytes(source_rows),
        "conformance.json": json_bytes(conformance),
        "admitted-mappings.nt": b"",
        "gate-coverage.json": json_bytes(gates[0]),
        "gate-no-omission.json": json_bytes(gates[1]),
        "gate-determinism.json": json_bytes(gates[2]),
        "gate-shacl.json": json_bytes(gates[3]),
    }
    manifest = {name: hashlib.sha256(payload).hexdigest()
                for name, payload in sorted(files.items())}
    manifest_payload = json_bytes(manifest)
    bundle = root / hashlib.sha256(manifest_payload).hexdigest()
    bundle.mkdir()
    for name, payload in files.items():
        (bundle / name).write_bytes(payload)
    (bundle / "manifest.json").write_bytes(manifest_payload)
    return bundle, coverage, root_id, sense_a, sense_b, held_id


def _rewrite_bundle(bundle: Path, name: str, value) -> Path:
    content = value if isinstance(value, bytes) else json_bytes(value)
    (bundle / name).write_bytes(content)
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest[name] = hashlib.sha256(content).hexdigest()
    manifest_payload = json_bytes(manifest)
    (bundle / "manifest.json").write_bytes(manifest_payload)
    target = bundle.parent / hashlib.sha256(manifest_payload).hexdigest()
    bundle.rename(target)
    return target


def _rewrite_artifact(bundle: Path, name: str, value) -> Path:
    content = value if isinstance(value, bytes) else json_bytes(value)
    (bundle / name).write_bytes(content)
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["files"][name] = {
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }
    manifest_payload = json_bytes(manifest)
    (bundle / "manifest.json").write_bytes(manifest_payload)
    target = bundle.parent / hashlib.sha256(manifest_payload).hexdigest()
    bundle.rename(target)
    return target


