"""Literal A01/A07 formal source join witnesses, without learner credit."""
from __future__ import annotations

from dataclasses import fields, replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.formal_constructive import (
    FORMAL_SOURCE_ONLY, SOURCE_PROJECTION_ONLY,
    FormalSourceOperator, FormalSourceOperatorSet, _resolve_from_bindings,
    assert_formal_source_operator_set_current, resolve_formal_source_operators,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, FormalDomainBinding, compile_atlas_release, persist_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorRegistry, default_registry, operator_grant_digest,
)


RELEASE = "a" * 64
BUNDLE = "b" * 64
ROOT = Path(__file__).resolve().parents[4]
FORMAL = (
    ("legacy:cogal.operator.NOT", "boolean", "BOOL_NOT"),
    ("legacy:cogal.operator.AND", "boolean", "BOOL_AND"),
    ("bilqis.numeric/v1:school.op.COUNT", "numeric", "COUNT"),
    ("bilqis.numeric/v1:school.op.SUCC", "numeric", "SUCC"),
)


def _source():
    entries = tuple(
        AbiEntry(index, 0, index, semantic_id, semantic_id,
                 "PRIOR_ACCEPTED_NATIVE_REGISTRY", True, True, "SOURCE_ADMITTED")
        for index, (semantic_id, _, _) in enumerate(FORMAL))
    bindings = (
        FormalDomainBinding(
            "boolean", "synthetic:boolean-source", "c" * 64,
            tuple(item[0] for item in FORMAL if item[1] == "boolean"),
            ("B.NOT", "B.AND")),
        FormalDomainBinding(
            "numeric", "synthetic:numeric-source", "d" * 64,
            tuple(item[0] for item in FORMAL if item[1] == "numeric"),
            ("C.COUNT", "C.SUCCESSOR")),
    )
    return bindings, entries


class FormalSourceResolutionTests(unittest.TestCase):
    def test_exact_formal_ids_resolve_to_a07_contracts_without_rights(self):
        bindings, entries = _source()
        registry = default_registry(RELEASE)
        resolved = _resolve_from_bindings(
            bindings, entries, registry,
            semantic_release=RELEASE, atlas_bundle_id=BUNDLE)
        self.assertEqual(resolved.status, FORMAL_SOURCE_ONLY)
        self.assertEqual(
            resolved.source_authority, SOURCE_PROJECTION_ONLY)
        self.assertEqual(resolved.uncovered, ())
        self.assertEqual(
            {item.semantic_id: item.operator.operator_id
             for item in resolved.witnesses},
            {semantic_id: operator for semantic_id, _, operator in FORMAL})
        for item in resolved.witnesses:
            self.assertEqual(
                item.source_authority, SOURCE_PROJECTION_ONLY)
            self.assertEqual(
                item.operator_grant_sha256,
                operator_grant_digest(registry.resolve(item.operator.operator_id)))
            self.assertEqual(item.operator.semantic_release, RELEASE)
        self.assertEqual(resolved.digest, _resolve_from_bindings(
            bindings, entries, registry,
            semantic_release=RELEASE, atlas_bundle_id=BUNDLE).digest)

    def test_unknown_formal_operator_stays_uncovered_not_adapter_ready(self):
        bindings, entries = _source()
        unknown = "legacy:cogal.operator.MADE_UP"
        altered = replace(
            bindings[0], semantic_ids=(*bindings[0].semantic_ids, unknown))
        entries = (*entries, AbiEntry(
            len(entries), 0, len(entries), unknown, unknown,
            "PRIOR_ACCEPTED_NATIVE_REGISTRY", True, True, "SOURCE_ADMITTED"))
        resolved = _resolve_from_bindings(
            (altered, bindings[1]), entries, default_registry(RELEASE),
            semantic_release=RELEASE, atlas_bundle_id=BUNDLE)
        self.assertEqual(
            resolved.uncovered, ((unknown, "OPERATOR_UNREGISTERED"),))
        self.assertEqual(len(resolved.witnesses), len(FORMAL))
        self.assertEqual(resolved.status, FORMAL_SOURCE_ONLY)
        self.assertEqual(
            resolved.source_authority, SOURCE_PROJECTION_ONLY)

    def test_wrong_release_and_forged_operator_contract_fail_closed(self):
        bindings, entries = _source()
        with self.assertRaises(BilqisError) as mismatch:
            _resolve_from_bindings(
                bindings, entries, default_registry("f" * 64),
                semantic_release=RELEASE, atlas_bundle_id=BUNDLE)
        self.assertEqual(
            mismatch.exception.context["reason"],
            "BAMF_FORMAL_SOURCE_RELEASE_MISMATCH")
        registry = default_registry(RELEASE)
        forged = OperatorRegistry(
            RELEASE, tuple(
                replace(spec, source_contract_sha256="0" * 64)
                if spec.operator_id == "BOOL_NOT" else spec
                for spec in registry.specs))
        with self.assertRaises(BilqisError) as contract:
            _resolve_from_bindings(
                bindings, entries, forged,
                semantic_release=RELEASE, atlas_bundle_id=BUNDLE)
        self.assertEqual(
            contract.exception.context["reason"],
            "BAMF_OPERATOR_SOURCE_CONTRACT_DRIFT")

    def test_public_resolution_refuses_caller_self_attested_release(self):
        with self.assertRaises(BilqisError) as caught:
            resolve_formal_source_operators(
                AtlasArtifactSelection(
                    "/tmp/unapproved-formal", BUNDLE, RELEASE, "c" * 64),
                default_registry(RELEASE))
        self.assertEqual(
            caught.exception.context["reason"],
            "ATLAS_SOURCE_PIN_NOT_REGISTERED")

    def test_real_pinned_a01_formal_operators_if_supplied(self):
        corpus = os.environ.get("BILQIS_ATLAS_REAL_CORPUS")
        if not corpus:
            self.skipTest("real pinned A01 corpus not supplied")
        prior = ROOT / "bilqis_mlx/semantics/copular_registry_v1.json"
        boolean = ROOT / "bilqis_mlx/semantics/legacy_abi_v1.json"
        numeric = ROOT / "bilqis_mlx/semantics/numeric_v1.json"
        bindings = (
            FormalDomainBinding(
                "boolean", "bilqis_mlx/semantics/legacy_abi_v1.json",
                hashlib.sha256(boolean.read_bytes()).hexdigest(),
                ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
                ("B.NOT", "B.AND")),
            FormalDomainBinding(
                "numeric", "bilqis_mlx/semantics/numeric_v1.json",
                hashlib.sha256(numeric.read_bytes()).hexdigest(),
                ("bilqis.numeric/v1:school.op.COUNT",
                 "bilqis.numeric/v1:school.op.SUCC"),
                ("C.COUNT", "C.SUCCESSOR")),
        )
        release = compile_atlas_release(
            corpus, Path(corpus) / "coverage.json", prior, bindings)
        with tempfile.TemporaryDirectory() as directory:
            artifact = persist_atlas_release(release, directory)
            selection = AtlasArtifactSelection(
                artifact.path, artifact.bundle_id, release.digest,
                release.source_bundle_id)
            resolved = resolve_formal_source_operators(
                selection, default_registry(release.digest))
            self.assertIsNone(assert_formal_source_operator_set_current(
                resolved, selection, default_registry(release.digest)))
            with self.assertRaises(BilqisError) as forged:
                assert_formal_source_operator_set_current(
                    replace(resolved, witnesses=resolved.witnesses[:2]),
                    selection, default_registry(release.digest))
            self.assertEqual(
                forged.exception.context["reason"],
                "BAMF_FORMAL_SOURCE_PROPOSAL_DRIFT")
            class EqAnySet(FormalSourceOperatorSet):
                def __eq__(self, other):
                    return True
                def __ne__(self, other):
                    return False

            class EqAnyWitness(FormalSourceOperator):
                def __eq__(self, other):
                    return True
                def __ne__(self, other):
                    return False

            evil_set = EqAnySet(**{
                field.name: getattr(resolved, field.name)
                for field in fields(resolved)})
            evil_witness = EqAnyWitness(**{
                field.name: getattr(resolved.witnesses[0], field.name)
                for field in fields(resolved.witnesses[0])})
            nested_evil = replace(
                resolved, witnesses=(evil_witness, *resolved.witnesses[1:]))
            for proposal in (evil_set, nested_evil):
                with self.assertRaises(BilqisError):
                    assert_formal_source_operator_set_current(
                        proposal, selection, default_registry(release.digest))
        self.assertEqual(resolved.status, FORMAL_SOURCE_ONLY)
        self.assertEqual(resolved.source_authority, SOURCE_PROJECTION_ONLY)
        self.assertTrue(all(
            item.source_authority == SOURCE_PROJECTION_ONLY
            for item in resolved.witnesses))
        self.assertEqual(resolved.uncovered, ())
        self.assertEqual(
            {item.operator.operator_id for item in resolved.witnesses},
            {"BOOL_NOT", "BOOL_AND", "COUNT", "SUCC"})
        self.assertEqual(len(resolved.witnesses), len(FORMAL))
        with self.assertRaises(BilqisError):
            replace(
                resolved, source_authority="A01_PINNED_SOURCE_ATTESTED",
                schema="bilqis.formal-source-operator-set/v1")


if __name__ == "__main__":
    unittest.main()
