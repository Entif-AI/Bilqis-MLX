"""Focused contracts for BAMF publication test authority helpers."""
from unittest import TestCase

from bilqis_mlx.runtime.bamf_bundle import source_authority_custody
from bilqis_mlx.runtime.tests.custody.bamf_bundle.publication.publication_helpers import (
    host_source_authority_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY


class PublicationHelperTests(TestCase):
    def test_host_source_authority_patch_accepts_explicit_registry(self):
        with host_source_authority_patch(AUTHORITY):
            self.assertIs(
                source_authority_custody.read_host_system_source_authority_registry(),
                AUTHORITY,
            )
