"""Resume metadata retains the selected retention contract."""
from dataclasses import asdict
import unittest

from bilqis_mlx.learning.learning_experiment import Settings, VERSION
from bilqis_mlx.runtime.resume_metadata import _reconcile_learning_settings


class ResumeMetadataTests(unittest.TestCase):
    def test_unchanged_settings_return_original_receipt_without_optimizer_access(self):
        settings = Settings()
        receipt = {'learning_experiment': {'version': VERSION, 'settings': asdict(settings)}}
        self.assertIs(_reconcile_learning_settings(None, receipt, None, settings, None), receipt)

    def test_missing_opt_in_fails_before_any_optimizer_or_persistence_access(self):
        receipt = {'learning_experiment': {'version': VERSION, 'settings': asdict(Settings())}}
        with self.assertRaisesRegex(ValueError, 'LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN'):
            _reconcile_learning_settings(None, receipt, None, None, None)
