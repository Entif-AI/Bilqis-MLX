"""Public export must hold every uncleared or revoked payload."""
from dataclasses import replace
import unittest
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import PackageAssertions, snapshot, digest
from bilqis_mlx.runtime.cognitive_package import (
    ExportClassification, export_capability, stage_import,
)


class ClearanceTests(PackageAssertions, unittest.TestCase):
    def test_public_fixture_and_public_derived_are_the_only_export_classes(self):
        source, rights = snapshot()
        self.assertEqual(
            {artifact.classification for artifact in source.artifacts},
            {ExportClassification.PUBLIC_FIXTURE, ExportClassification.PUBLIC_DERIVED},
        )
        package = export_capability(source, source.signature, rights)
        self.assertEqual(package.artifacts, source.artifacts)

        for classification in (
            ExportClassification.PRIVATE_REAL,
            ExportClassification.UNCLASSIFIED,
        ):
            with self.subTest(classification=classification):
                held = replace(
                    source,
                    artifacts=(
                        replace(source.artifacts[0], classification=classification),
                        *source.artifacts[1:],
                    ),
                )
                with self.assertPackageError('public export classification'):
                    export_capability(held, held.signature, rights)

    def test_public_allowlist_cannot_reclassify_private_material(self):
        source, rights = snapshot()
        private = replace(
            source,
            artifacts=(
                replace(
                    source.artifacts[0],
                    classification=ExportClassification.PRIVATE_REAL,
                ),
                *source.artifacts[1:],
            ),
        )
        self.assertIn(private.artifacts[0].digest, rights.public_artifact_digests)
        with self.assertPackageError('public export classification'):
            export_capability(private, private.signature, rights)

    def test_every_payload_requires_public_clearance(self):
        source, rights = snapshot()
        for artifact in source.artifacts:
            with self.subTest(artifact=artifact.artifact_id):
                held = replace(rights, public_artifact_digests=tuple(
                    d for d in rights.public_artifact_digests if d != artifact.digest))
                with self.assertPackageError('clearance'):
                    export_capability(source, source.signature, held)

    def test_revoked_payload_rejected(self):
        source, rights = snapshot()
        revoked = replace(rights, revoked_artifact_digests=(source.artifacts[0].digest,))
        with self.assertPackageError('revoked'):
            export_capability(source, source.signature, revoked)

    def test_signature_mismatch_rejected(self):
        source, rights = snapshot()
        with self.assertPackageError('signature'):
            export_capability(source, 'other-signature', rights)

    def test_nested_forgery_rechecked_before_export_and_import(self):
        source, rights = snapshot()
        object.__setattr__(source.binding, 'base_weight_digest', 'bad')
        with self.assertPackageError('binding'):
            export_capability(source, source.signature, rights)
        source, rights = snapshot()
        package = export_capability(source, source.signature, rights)
        object.__setattr__(package.artifacts[0], 'payload', bytearray(b'private'))
        with self.assertPackageError('artifact'):
            stage_import(package, source.binding)

    def test_duplicate_artifact_id_rejected(self):
        source, rights = snapshot()
        with self.assertPackageError('artifact'):
            replace(source, artifacts=source.artifacts + (source.artifacts[0],))

    def test_boolean_resource_limit_rejected(self):
        source, _ = snapshot()
        with self.assertPackageError('resource'):
            replace(source, max_memory_bytes=True)

    def test_surrogate_metadata_rejected_before_export(self):
        source, rights = snapshot()
        for field in ('generation_id', 'signature', 'operator_identity'):
            with self.subTest(field=field):
                with self.assertPackageError('identity'):
                    replace(source, **{field: chr(0xD800)})
        with self.assertPackageError('clearance'):
            replace(rights, authority_id=chr(0xD800))

    def test_forged_surrogate_rejected_before_digest_and_staging(self):
        source, rights = snapshot()
        package = export_capability(source, source.signature, rights)
        object.__setattr__(package, 'operator_identity', chr(0xD800))
        with self.assertPackageError('identity'):
            _ = package.digest
        with self.assertPackageError('identity'):
            stage_import(package, source.binding)
