from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from collections import Counter

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry,
    BANK_SIZE,
    FormalDomainBinding,
    compile_atlas_release,
    load_atlas_snapshot,
    persist_atlas_release,
    validate_atlas_release,
)
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.publication import json_bytes


ROOT = Path(__file__).resolve().parents[3]
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


class AtlasProjectionTests(unittest.TestCase):
    def test_source_qualified_root_senses_realizations_and_hold_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, coverage, root_id, sense_a, sense_b, held_id = _fixture_bundle(Path(directory))
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            validation = validate_atlas_release(release)

        self.assertEqual(validation.status, "valid")
        self.assertEqual(release.digest, validation.release_sha256)
        self.assertEqual([item.semantic_id for item in release.concepts],
                         sorted(item.semantic_id for item in release.concepts))
        by_id = {item.semantic_id: item for item in release.concepts}
        self.assertEqual(by_id[root_id].kind, "root")
        self.assertEqual({value.value for value in by_id[root_id].realizations}, {"-T-", "-Tʼ-"})
        self.assertEqual([(label.value, label.language) for label in by_id[root_id].labels
                          if label.value == "variant"], [("variant", None), ("variant", "en")])
        self.assertEqual([(value.value, value.datatype) for value in by_id[root_id].realizations
                          if value.value == "-T-"],
                         [("-T-", None), ("-T-", str(XSD.string))])
        self.assertEqual(by_id[sense_a].kind, "sense")
        self.assertEqual(by_id[sense_b].kind, "sense")
        self.assertNotEqual(sense_a, sense_b)
        self.assertNotIn(held_id, by_id)
        held = next(item for item in release.held_mappings if item.semantic_id == held_id)
        self.assertEqual(held.reason_code, "MAPPING_REVIEW_PENDING")
        self.assertEqual({item.family for item in release.formal_domain_bindings},
                         {"boolean", "numeric"})
        self.assertEqual(release.counts.trainable_capabilities, 4)

    def test_same_pinned_inputs_are_byte_identity_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, coverage, *_ = _fixture_bundle(Path(directory))
            first = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            second = compile_atlas_release(bundle, coverage, PRIOR_ABI, tuple(reversed(_bindings())))
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.abi_entries, second.abi_entries)

    def test_append_only_abi_and_content_addressed_files_preserve_prior_bytes(self):
        prior_before = PRIOR_ABI.read_bytes()
        prior_rows = json.loads(prior_before)["rows"][1:]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, root_id, sense_a, sense_b, held_id = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            output = root / "artifacts"
            first = persist_atlas_release(release, output)
            second = persist_atlas_release(release, output)
            target = Path(first.path)
            files = {path.name for path in target.iterdir()}
            manifest_bytes = (target / "manifest.json").read_bytes()
            atlas = json.loads((target / "atlas.json").read_text())
            withheld = [json.loads(line) for line in (target / "held.jsonl").read_text().splitlines()]
            snapshot = load_atlas_snapshot(
                target,
                expected_bundle_id=first.bundle_id,
                expected_release_sha256=release.digest,
                expected_source_bundle_id=release.source_bundle_id,
            )

        self.assertEqual(PRIOR_ABI.read_bytes(), prior_before)
        self.assertEqual(first.bundle_id, hashlib.sha256(manifest_bytes).hexdigest())
        self.assertEqual(first, second)
        self.assertEqual(files, {"atlas.json", "concepts.jsonl", "relations.jsonl",
                                 "held.jsonl", "manifest.json"})
        self.assertEqual(len(prior_rows), 228)
        for index, row in enumerate(prior_rows):
            entry = release.abi_entries[index]
            self.assertEqual((entry.index, entry.bank, entry.row),
                             (index, index // BANK_SIZE, index % BANK_SIZE))
            self.assertEqual((entry.symbol, entry.semantic_id), (row[1], row[2]))
            self.assertTrue(entry.active)
        appended = release.abi_entries[len(prior_rows):]
        self.assertEqual([entry.semantic_id for entry in appended],
                         sorted((root_id, sense_a, sense_b)))
        self.assertTrue(all(not entry.active and entry.reason == "IMPLEMENTATION_UNCOVERED"
                            for entry in appended))
        self.assertNotIn(held_id, {entry.semantic_id for entry in release.abi_entries})
        self.assertEqual(atlas["counts"], {
            "abi_banks": 1,
            "abi_entries": 231,
            "active_abi_indices": 228,
            "implementation_uncovered": 3,
            "rdf_terms": release.rdf_term_count,
            "semantic_concepts": 3,
            "source_held": 4,
            "source_ir_only": 1,
            "source_rows": 11,
            "trainable_capabilities": 4,
        })
        held = next(row for row in withheld if row["semantic_id"] == held_id)
        self.assertEqual((held["source_disposition"], held["teaching_reason"]),
                         ("SOURCE_HELD", "MAPPING_REVIEW_PENDING"))
        uncovered = next(row for row in withheld if row["semantic_id"] == root_id)
        self.assertEqual((uncovered["source_disposition"], uncovered["implementation_status"],
                          uncovered["teaching_reason"]),
                         ("SOURCE_ELIGIBLE", "IMPLEMENTATION_UNCOVERED",
                          "IMPLEMENTATION_UNCOVERED"))
        self.assertEqual(snapshot.abi(227).semantic_id, prior_rows[227][2])
        self.assertEqual(snapshot.abi_for_semantic(root_id).semantic_id, root_id)
        self.assertEqual(snapshot.concept(root_id).concept.semantic_id, root_id)
        self.assertEqual(len(snapshot.source_hold_census()), 4)
        self.assertEqual(len({
            row.semantic_id for row in snapshot.implementation_uncovered_census()
            if row.semantic_id}), 3)
        with self.assertRaises(BilqisError):
            snapshot.abi_for_semantic(held_id)

    def test_forged_held_activation_is_rejected_without_artifact_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_, held_id = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            receipt = persist_atlas_release(release, root / "artifacts")
            manifest = Path(receipt.path) / "manifest.json"
            before = manifest.read_bytes()
            index = len(release.abi_entries)
            forged = replace(release, abi_entries=(*release.abi_entries, AbiEntry(
                index=index,
                bank=index // BANK_SIZE,
                row=index % BANK_SIZE,
                semantic_id=held_id,
                symbol="attacker.requested-held-meaning",
                source="CANONICAL_SKOS",
                active=True,
                teaching_candidate=True,
                reason="REQUESTED_LEARNER_ACTIVATION",
            )))
            with self.assertRaises(BilqisError) as caught:
                persist_atlas_release(forged, root / "artifacts")
            self.assertEqual(manifest.read_bytes(), before)
        self.assertIn("ATLAS_HELD_IDENTITY_ADMITTED",
                      str(caught.exception.context.get("reason")))

    def test_stale_coverage_is_rejected_before_release(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle, coverage, *_ = _fixture_bundle(Path(directory))
            stale = json.loads(json.dumps(coverage))
            stale["canonical_rdf"]["sha256"] = "0" * 64
            with self.assertRaises(BilqisError) as caught:
                compile_atlas_release(bundle, stale, PRIOR_ABI, _bindings())
        self.assertEqual(caught.exception.code, "SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID")
        self.assertIn("ATLAS_COVERAGE_RECEIPT_STALE", str(caught.exception.context.get("reason")))

    def test_bundle_admission_rejects_census_gate_manifest_and_symlink_attacks(self):
        cases = (
            ("census_wrong_identity", "ATLAS_SOURCE_CENSUS_IDENTITY_MISMATCH"),
            ("census_duplicate_identity", "ATLAS_SOURCE_CENSUS_DUPLICATE"),
            ("constituent_gate_disagreement", "ATLAS_CONFORMANCE_GATE_MISMATCH:shacl"),
            ("duplicate_conformance_gate", "ATLAS_CONFORMANCE_GATES_INVALID"),
            ("unexpected_manifest_member", "ATLAS_SOURCE_MANIFEST_INVALID"),
            ("symlink_manifest_member", "ATLAS_SOURCE_BUNDLE_MEMBER_SET_INVALID"),
        )
        for kind, reason in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                bundle, coverage, *_ = _fixture_bundle(Path(directory))
                if kind.startswith("census_"):
                    rows = json.loads((bundle / "source-rows.json").read_text())
                    if kind == "census_wrong_identity":
                        rows[0]["key"] = "ROW-NOT-IN-COVERAGE"
                    else:
                        rows[1] = dict(rows[0])
                    bundle = _rewrite_bundle(bundle, "source-rows.json", rows)
                elif kind == "constituent_gate_disagreement":
                    gate = json.loads((bundle / "gate-shacl.json").read_text())
                    gate["status"] = "failed"
                    gate["evidence"]["conforms"] = False
                    bundle = _rewrite_bundle(bundle, "gate-shacl.json", gate)
                elif kind == "duplicate_conformance_gate":
                    report = json.loads((bundle / "conformance.json").read_text())
                    report["gates"].append(dict(report["gates"][0]))
                    bundle = _rewrite_bundle(bundle, "conformance.json", report)
                elif kind == "unexpected_manifest_member":
                    bundle = _rewrite_bundle(bundle, "unexpected.json", {"note": "undeclared"})
                else:
                    canonical = bundle / "canonical.nt"
                    canonical.unlink()
                    canonical.symlink_to(bundle / "comparison.nt")
                with self.assertRaises(BilqisError) as caught:
                    compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
                self.assertIn(reason, str(caught.exception.context.get("reason")))

    def test_database_free_snapshot_rejects_tamper_missing_identity_and_latest_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_ = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            receipt = persist_atlas_release(release, root / "artifacts")
            artifact = Path(receipt.path)

            with self.assertRaises(BilqisError) as mismatch:
                load_atlas_snapshot(
                    artifact,
                    expected_release_sha256="0" * 64,
                    expected_source_bundle_id=release.source_bundle_id,
                )
            self.assertIn("ATLAS_SNAPSHOT_EXPECTED_RELEASE_MISMATCH",
                          str(mismatch.exception.context.get("reason")))

            with self.assertRaises(BilqisError) as source_mismatch:
                load_atlas_snapshot(
                    artifact,
                    expected_release_sha256=release.digest,
                    expected_source_bundle_id="0" * 64,
                )
            self.assertIn("ATLAS_SNAPSHOT_EXPECTED_SOURCE_RELEASE_MISMATCH",
                          str(source_mismatch.exception.context.get("reason")))

            latest = artifact.parent / "latest"
            artifact.rename(latest)
            with self.assertRaises(BilqisError) as alias:
                load_atlas_snapshot(latest)
            self.assertIn("ATLAS_SNAPSHOT_BUNDLE_PATH_INVALID",
                          str(alias.exception.context.get("reason")))
            latest.rename(artifact)

            atlas = json.loads((artifact / "atlas.json").read_text())
            atlas.pop("source_bundle_id")
            artifact = _rewrite_artifact(artifact, "atlas.json", atlas)
            with self.assertRaises(BilqisError) as missing:
                load_atlas_snapshot(artifact)
            self.assertIn("ATLAS_SNAPSHOT_ATLAS_INVALID",
                          str(missing.exception.context.get("reason")))

    def test_database_free_snapshot_rejects_payload_digest_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, coverage, *_ = _fixture_bundle(root)
            release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
            receipt = persist_atlas_release(release, root / "artifacts")
            artifact = Path(receipt.path)
            manifest_before = (artifact / "manifest.json").read_bytes()
            with (artifact / "concepts.jsonl").open("ab") as output:
                output.write(b" ")
            with self.assertRaises(BilqisError) as caught:
                load_atlas_snapshot(artifact)
            self.assertEqual((artifact / "manifest.json").read_bytes(), manifest_before)
        self.assertIn("ATLAS_SNAPSHOT_FILE_DIGEST_MISMATCH:concepts.jsonl",
                      str(caught.exception.context.get("reason")))

    @unittest.skipUnless(os.environ.get("BILQIS_ATLAS_REAL_CORPUS"),
                         "real canonical conformance bundle supplied only at turn-in")
    def test_real_corpus_witness(self):
        bundle = Path(os.environ["BILQIS_ATLAS_REAL_CORPUS"])
        coverage = json.loads((bundle / "coverage.json").read_text())
        release = compile_atlas_release(bundle, coverage, PRIOR_ABI, _bindings())
        validation = validate_atlas_release(release)
        with tempfile.TemporaryDirectory() as directory:
            receipt = persist_atlas_release(release, Path(directory))
            target = Path(receipt.path)
            real_manifest = (target / "manifest.json").read_bytes()
            real_files = {path.name for path in target.iterdir()}
            snapshot = load_atlas_snapshot(
                target,
                expected_bundle_id=receipt.bundle_id,
                expected_release_sha256=release.digest,
                expected_source_bundle_id=release.source_bundle_id,
            )
        self.assertEqual(release.canonical_rdf_sha256,
                         "7a0a0cd04133be41db69ca3fe1e2f09b4efbc8c965610b75c5ac30bc0954b50e")
        self.assertEqual(release.source_row_count, 25692)
        self.assertEqual(len(release.held_mappings), 552)
        self.assertEqual(Counter(item.kind for item in release.concepts),
                         Counter({"concept": 104, "root": 5967, "sense": 3008}))
        self.assertEqual(validation.concept_count, 9079)
        self.assertGreater(sum(len(item.realizations) for item in release.concepts), 0)
        self.assertEqual(validation.formal_binding_count, 2)
        self.assertEqual(release.prior_abi_sha256, _sha(PRIOR_ABI))
        self.assertIn(("prior_abi", "UNVERSIONED"), release.input_schemas)
        self.assertEqual(release.counts.abi_entries, 9307)
        self.assertEqual(release.counts.abi_banks, 2)
        self.assertEqual(release.counts.active_abi_indices, 228)
        self.assertEqual(release.counts.trainable_capabilities, 4)
        self.assertEqual(release.counts.source_held, 1052)
        self.assertEqual(release.counts.source_ir_only, 9488)
        self.assertEqual(release.counts.implementation_uncovered, 9079)
        self.assertGreater(release.counts.rdf_terms, 0)
        self.assertEqual(receipt.bundle_id, hashlib.sha256(real_manifest).hexdigest())
        self.assertEqual(real_files, {"atlas.json", "concepts.jsonl", "relations.jsonl",
                                      "held.jsonl", "manifest.json"})
        self.assertEqual(snapshot.counts, release.counts)
        self.assertEqual(snapshot.source_bundle_id, release.source_bundle_id)
        self.assertEqual(snapshot.abi(8192).index, 8192)
        witness = snapshot.concepts[0]
        self.assertEqual(
            snapshot.concept(witness.concept.semantic_id).abi_index,
            witness.abi_index)
        self.assertEqual(len(snapshot.source_hold_census()), 1052)


if __name__ == "__main__":
    unittest.main()
