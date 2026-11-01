"""A12 audit refuses invented admission and cross-consumer source drift."""
from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_authority_audit import audit_atlas_authority


class AtlasAuthorityAuditTests(TestCase):
    def test_untyped_untrusted_authority_fails_closed(self):
        with self.assertRaises(BilqisError):
            audit_atlas_authority({}, {}, {}, {}, {})

    def test_authority_must_not_be_minted_from_unpinned_selection(self):
        from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
        selection = AtlasArtifactSelection('missing', 'a' * 64, 'b' * 64, 'c' * 64)
        with self.assertRaises(BilqisError):
            audit_atlas_authority(selection, {}, {}, {}, {})
