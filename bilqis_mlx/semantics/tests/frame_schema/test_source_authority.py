"""Frame-schema source_authority witnesses."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_projection import (
    FormalDomainBinding, compile_atlas_release, load_atlas_snapshot,
    persist_atlas_release,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    bind_frame_instance,
)
from bilqis_mlx.semantics.tests.frame_schema.fixtures import ROOT, _concept, _snapshot


class FrameSourceAuthorityTests(unittest.TestCase):
    def test_authoritative_concept_type_rejects_forged_role_allowed_type(self):
        entity = _concept("alice", 0, "Entity")
        snapshot = _snapshot(entity)
        schema = FrameSchema(
            "formal.frame.FORGED_TYPE",
            1,
            "source:forged",
            (RoleSpec("actor", ("Boolean",), 1, 1),),
            "ORDERED",
            "clause",
        )
        forged = ConceptRef(
            semantic_id=entity.semantic_id,
            semantic_release=entity.semantic_release,
            abi_index=entity.abi_index,
            type_ids=("Boolean",),
            source_reference=entity.source_reference,
        )
        with self.assertRaises(BilqisError) as caught:
            bind_frame_instance(
                schema,
                snapshot,
                source_instance_id="forged-type",
                structural_path=(),
                source_span=SourceSpan(5, 9),
                parent_occurrence_id=None,
                bindings=(RoleOccurrence("actor", 0, concept=forged),),
                causal_prefix_end=9,
                declared_scope="clause",
            )
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.BINDING.INVALID")
        self.assertEqual(caught.exception.context["role_id"], "actor")
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_CONCEPT_TYPE_AUTHORITY_MISMATCH",
        )


    @unittest.skipUnless(
        os.environ.get("BILQIS_ATLAS_REAL_CORPUS"),
        "real canonical Atlas bundle supplied only at turn-in",
    )
    def test_real_atlas_concept_rejects_forged_role_allowed_type(self):
        bundle = Path(os.environ["BILQIS_ATLAS_REAL_CORPUS"])
        legacy = ROOT / "bilqis_mlx/semantics/legacy_abi_v1.json"
        numeric = ROOT / "bilqis_mlx/semantics/numeric_v1.json"
        prior = ROOT / "bilqis_mlx/semantics/copular_registry_v1.json"
        sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        bindings = (
            FormalDomainBinding(
                "boolean",
                "bilqis_mlx/semantics/legacy_abi_v1.json",
                sha(legacy),
                ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
                ("B.NOT", "B.AND"),
            ),
            FormalDomainBinding(
                "numeric",
                "bilqis_mlx/semantics/numeric_v1.json",
                sha(numeric),
                ("bilqis.numeric/v1:school.op.COUNT",
                 "bilqis.numeric/v1:school.op.SUCC"),
                ("C.COUNT", "C.SUCCESSOR"),
            ),
        )
        release = compile_atlas_release(
            bundle, bundle / "coverage.json", prior, bindings)
        with tempfile.TemporaryDirectory() as directory:
            receipt = persist_atlas_release(release, Path(directory))
            snapshot = load_atlas_snapshot(
                receipt.path,
                expected_bundle_id=receipt.bundle_id,
                expected_release_sha256=release.digest,
                expected_source_bundle_id=release.source_bundle_id,
            )
            canonical = next(
                item for item in snapshot.concepts if item.concept.types)

        forged_type = "urn:forged:AllowedType"
        forged = ConceptRef(
            semantic_id=canonical.concept.semantic_id,
            semantic_release=snapshot.release_sha256,
            abi_index=canonical.abi_index,
            type_ids=(forged_type,),
            source_reference="attacker:forged-type",
        )
        schema = FrameSchema(
            "formal.frame.REAL_ATLAS_TYPE_PROBE",
            1,
            "source:type-probe",
            (RoleSpec("value", (forged_type,), 1, 1),),
            "ORDERED",
            "clause",
        )
        with self.assertRaises(BilqisError) as caught:
            bind_frame_instance(
                schema,
                snapshot,
                source_instance_id="real-type-probe",
                structural_path=(),
                source_span=SourceSpan(20, 30),
                parent_occurrence_id=None,
                bindings=(RoleOccurrence("value", 0, concept=forged),),
                causal_prefix_end=30,
                declared_scope="clause",
            )
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.BINDING.INVALID")
        self.assertEqual(caught.exception.context["role_id"], "value")
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_CONCEPT_TYPE_AUTHORITY_MISMATCH",
        )


    def test_formal_abi_without_source_type_authority_cannot_accept_forgery(self):
        real = _concept("alice", 0, "Entity")
        snapshot = replace(
            _snapshot(real), concepts=(), concept_lookup=())
        forged = replace(real, type_ids=("Number",))
        schema = FrameSchema(
            "frame:formal", 1, "source:formal",
            (RoleSpec("value", ("Number",), 1, 1),),
            "ORDERED", "source-expression",
        )
        with self.assertRaises(BilqisError) as caught:
            bind_frame_instance(
                schema, snapshot,
                source_instance_id="formal-type-forgery",
                structural_path=(),
                source_span=SourceSpan(0, 8),
                parent_occurrence_id=None,
                bindings=(RoleOccurrence("value", 0, concept=forged),),
                causal_prefix_end=8,
                declared_scope="source-expression",
            )
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_CONCEPT_TYPE_AUTHORITY_MISSING",
        )
