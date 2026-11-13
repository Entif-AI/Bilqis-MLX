"""Public export must hold every uncleared or revoked payload."""
from dataclasses import replace
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.cognitive_package.tests.export_authority_fixtures import (
    REGISTRY, frontier, receipt, selection,
)
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import PackageAssertions, snapshot, digest
from bilqis_mlx.runtime.cognitive_package import (
    ExportClassification, PublicExportGrant, SourceRights, authorize_public_export,
    export_capability, stage_import,
)


class ClearanceTests(PackageAssertions, unittest.TestCase):
    def test_public_fixture_and_public_derived_are_the_only_export_classes(self):
        source, grant = snapshot()
        self.assertEqual(
            {classification for _digest, classification in grant.artifact_classifications},
            {ExportClassification.PUBLIC_FIXTURE, ExportClassification.PUBLIC_DERIVED},
        )
        package = export_capability(source, source.signature, grant)
        self.assertEqual(package.artifacts, source.artifacts)

    def test_private_and_unclassified_material_have_no_a12_export_grant(self):
        source, _grant = snapshot()
        held = source.artifacts[0].digest
        public = tuple(sorted(
            artifact.digest for artifact in source.artifacts if artifact.digest != held))
        for private in ((held,), ()):
            with self.subTest(private=bool(private)):
                with self.assertRaises(BilqisError) as caught:
                    authorize_public_export(
                        source,
                        receipt(source, exported=public, private=private),
                        selection(), frontier(), REGISTRY)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "A12_EXPORT_CLEARANCE_ARTIFACT_DRIFT")

    def test_caller_source_rights_or_direct_grant_construction_cannot_authorize_export(self):
        source, grant = snapshot()
        with self.assertPackageError('issued public export grant'):
            export_capability(source, source.signature, grant.rights)
        with self.assertPackageError('caller construction'):
            PublicExportGrant(grant.rights, grant.artifact_classifications)

    def test_every_payload_requires_public_clearance(self):
        source, _grant = snapshot()
        for artifact in source.artifacts:
            with self.subTest(artifact=artifact.artifact_id):
                exported = tuple(sorted(
                    item.digest for item in source.artifacts if item != artifact))
                with self.assertRaises(BilqisError) as caught:
                    authorize_public_export(
                        source, receipt(source, exported=exported),
                        selection(), frontier(), REGISTRY)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "A12_EXPORT_CLEARANCE_ARTIFACT_DRIFT")

    def test_revoked_payload_rejected(self):
        source, _grant = snapshot()
        held = source.artifacts[0].digest
        exported = tuple(sorted(
            artifact.digest for artifact in source.artifacts if artifact.digest != held))
        with self.assertRaises(BilqisError) as caught:
            authorize_public_export(
                source, receipt(source, exported=exported, revoked=(held,)),
                selection(), frontier(), REGISTRY)
        self.assertEqual(
            caught.exception.context["reason"], "A12_EXPORT_CLEARANCE_ARTIFACT_DRIFT")

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
        source, _grant = snapshot()
        for field in ('generation_id', 'signature', 'operator_identity'):
            with self.subTest(field=field):
                with self.assertPackageError('identity'):
                    replace(source, **{field: chr(0xD800)})
        with self.assertPackageError('clearance'):
            SourceRights(
                chr(0xD800), digest('clearance'),
                tuple(sorted(artifact.digest for artifact in source.artifacts)), (), ())

    def test_forged_surrogate_rejected_before_digest_and_staging(self):
        source, rights = snapshot()
        package = export_capability(source, source.signature, rights)
        object.__setattr__(package, 'operator_identity', chr(0xD800))
        with self.assertPackageError('identity'):
            _ = package.digest
        with self.assertPackageError('identity'):
            stage_import(package, source.binding)
