"""Exact numeric provider compatibility across the school owner extraction."""
from dataclasses import replace
import unittest

from bilqis_mlx.compatibility.legacy.source_adapter_resume import resume_adapter_compatible
from bilqis_mlx.source_adapters.school import C_ORACLE, live_source_registry


class NumericProviderCompatibilityTests(unittest.TestCase):
    def test_exact_prior_provider_can_resume_without_weakening_descriptor_checks(self):
        current = live_source_registry().require(
            "bilqis_mlx.numeric_curriculum.draw_numeric", C_ORACLE).descriptor
        prior = replace(current, implementation_sha256=
            "2758cf678e9d2a45f3f5a1b5edd85d5ae513e54506c0d98853b9402b91572754")
        self.assertTrue(resume_adapter_compatible(prior, current))
        self.assertFalse(resume_adapter_compatible(current, prior))
        for changed in (
                replace(current, implementation_sha256="f" * 64),
                replace(current, profile_dimensions=(("numbers", ("0",)),)),
                replace(current, accepted_oracle_ids=("foreign-oracle",))):
            with self.subTest(changed=changed):
                self.assertFalse(resume_adapter_compatible(prior, changed))
