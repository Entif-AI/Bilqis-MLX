"""Resume metadata retains the selected retention contract."""
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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

    def test_historical_settings_without_margin_inherit_new_default(self):
        old = asdict(Settings())
        old.pop('mastery_debt_min_utility')
        receipt = {'learning_experiment': {'version': VERSION, 'settings': old}}
        self.assertIs(
            _reconcile_learning_settings(None, receipt, None, Settings(), None),
            receipt)

    def test_resume_rejects_lower_mastery_debt_margin(self):
        receipt = {'learning_experiment': {
            'version': VERSION,
            'settings': asdict(Settings(mastery_debt_min_utility=0.08)),
        }}
        with self.assertRaisesRegex(
                ValueError, 'LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN'):
            _reconcile_learning_settings(
                None, receipt, None,
                Settings(mastery_debt_min_utility=0.05), None)

    def test_resume_allows_higher_mastery_debt_margin(self):
        old = Settings(mastery_debt_min_utility=0.05)
        new = Settings(mastery_debt_min_utility=0.08)
        receipt = {
            'run_id': 'resume-margin-test',
            'generation': 7,
            'school': {},
            'learning_experiment': {'version': VERSION, 'settings': asdict(old)},
        }
        school = SimpleNamespace(
            current_student=SimpleNamespace(optimizer_step=12, sha256='s' * 64))
        optimizer = SimpleNamespace(
            state={'step': SimpleNamespace(item=lambda: 12)})
        with patch(
                'bilqis_mlx.runtime.resume_metadata._runtime_release_adoption._schedule_for_receipt',
                return_value=object()), patch(
                'bilqis_mlx.runtime.resume_metadata._runtime_state._state_from_json',
                return_value=school), patch(
                'bilqis_mlx.runtime.resume_metadata._runtime_checkpoints._advance',
                side_effect=lambda _run, value, _school, persist=False: {
                    **value, 'generation': 8}), patch(
                'bilqis_mlx.runtime.resume_metadata._runtime_checkpoints._persist',
                side_effect=lambda _run, value: value), patch(
                'bilqis_mlx.runtime.resume_metadata._runtime_checkpoints._reconcile_delivery_outbox'):
            result = _reconcile_learning_settings(
                None, receipt, None, new, optimizer)
        self.assertEqual(
            result['learning_experiment']['settings']['mastery_debt_min_utility'],
            0.08)
