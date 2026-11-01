"""Two-consumer exchange and exact binding guards."""
from dataclasses import fields, replace
import unittest
from .fixtures import PackageAssertions, snapshot, digest
from bilqis_mlx.runtime.cognitive_package import (
    CognitivePackage, PackageKind, export_capability, stage_import,
)


class ExchangeTests(PackageAssertions, unittest.TestCase):
    def test_two_consumers_exchange_complete_exact_operator(self):
        source, rights = snapshot()
        package = export_capability(source, 'increment-signature', rights)
        receiver = CognitivePackage.from_canonical_json(package.canonical_json)
        self.assertEqual(receiver, package)
        self.assertEqual(receiver.artifacts[0].payload, b'x + 1')
        self.assertEqual(receiver.signature, 'increment-signature')
        self.assertEqual(receiver.operator_identity, 'exact-increment/v1')
        self.assertEqual(receiver.max_memory_bytes, 1024)
        self.assertEqual(receiver.max_storage_bytes, 2048)
        self.assertEqual(receiver.rights, rights)
        self.assertEqual(receiver.digest, digest(package.canonical_json))
        plan = stage_import(receiver, source.binding)
        self.assertEqual(plan.package_digest, package.digest)
        self.assertEqual(plan.disposition, 'EXACT_BINDING')
        self.assertEqual(plan.receiver, source.binding)

    def test_exact_transform_mismatch_falls_back_to_teaching(self):
        source, rights = snapshot()
        package = export_capability(source, source.signature, rights)
        plan = stage_import(package, replace(source.binding, base_weight_digest=digest('other')))
        self.assertEqual(plan.disposition, 'TEACHING_ONLY')

    def test_each_delta_binding_must_match_before_staging(self):
        for kind in (PackageKind.ADAPTER_DELTA, PackageKind.WEIGHT_DELTA):
            source, rights = snapshot(kind)
            package = export_capability(source, source.signature, rights)
            self.assertEqual(stage_import(package, source.binding).disposition, 'EXACT_BINDING')
            for field in fields(source.binding):
                with self.subTest(kind=kind, field=field.name):
                    other = replace(source.binding, **{field.name: digest('other')})
                    with self.assertPackageError('binding'):
                        stage_import(package, other)

    def test_ancestry_survives_roundtrip(self):
        source, rights = snapshot(PackageKind.PROCEDURE)
        rights = replace(rights, revocation_lineage=(digest('ancestor'),))
        package = export_capability(source, source.signature, rights)
        self.assertEqual(CognitivePackage.from_canonical_json(package.canonical_json).rights.revocation_lineage,
                         (digest('ancestor'),))

    def test_mixed_exact_and_delta_mismatch_rejects_whole_package(self):
        source, rights = snapshot(PackageKind.WEIGHT_DELTA)
        from bilqis_mlx.runtime.cognitive_package import PackageArtifact
        exact = PackageArtifact('exact', PackageKind.EXACT_TRANSFORM, b'identity')
        source = replace(source, artifacts=source.artifacts + (exact,))
        rights = replace(rights, public_artifact_digests=tuple(sorted(
            rights.public_artifact_digests + (exact.digest,))))
        package = export_capability(source, source.signature, rights)
        with self.assertPackageError('binding'):
            stage_import(package, replace(source.binding, topology_digest=digest('other')))
