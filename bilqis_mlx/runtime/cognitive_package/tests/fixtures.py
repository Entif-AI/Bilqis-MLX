"""Synthetic public source snapshots; no production qualification authority."""
from hashlib import sha256
from bilqis_mlx.runtime.cognitive_package import (
    PackageArtifact, PackageBinding, PackageKind, ExportSnapshot,
)
from .export_authority_fixtures import grant


def digest(value):
    return sha256(value.encode()).hexdigest()


def snapshot(kind=PackageKind.EXACT_TRANSFORM):
    binding = PackageBinding(*(digest(str(i)) for i in range(7)))
    artifacts = tuple(
        PackageArtifact(name, artifact_kind, data)
        for name, artifact_kind, data in (
            ('operator', kind, b'x + 1'),
            ('fixture', PackageKind.FIXTURE, b'1 -> 2'),
            ('counterexample', PackageKind.COUNTEREXAMPLE, b'0 != 2'),
            ('behavior', PackageKind.BEHAVIORAL_DIFF, b'gains=1;regressions=0'),
        )
    )
    source = ExportSnapshot('successor-test-generation', 'increment-signature', binding,
                            'exact-increment/v1', artifacts, 1024, 2048)
    return source, grant(source)


class PackageAssertions:
    def assertPackageError(self, reason):
        from contextlib import contextmanager
        from bilqis_mlx.errors import BilqisError, SCHOOL

        @contextmanager
        def check():
            with self.assertRaises(BilqisError) as caught:
                yield
            self.assertIs(caught.exception.spec, SCHOOL.BAMF_PACKAGE.INVALID)
            self.assertIn(reason, caught.exception.context['reason'])
        return check()
