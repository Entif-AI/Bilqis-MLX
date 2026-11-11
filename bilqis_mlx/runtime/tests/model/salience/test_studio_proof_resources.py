"""Portable resource preflight checks; these tests never import MLX."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class StudioProofResourceTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name('run_studio_proof.py')
        spec = spec_from_file_location('c06_studio_resource_test', path)
        self.runner = module_from_spec(spec)
        spec.loader.exec_module(self.runner)

    def check_resources(self, swap, pressure, **kwargs):
        with patch.object(self.runner.subprocess, 'run', side_effect=(
                SimpleNamespace(stdout=swap), SimpleNamespace(stdout=pressure))), \
                patch('builtins.print'):
            return self.runner._resources_ready(**kwargs)

    def test_nearly_full_swap_holds_even_when_memory_is_free(self):
        self.assertFalse(self.check_resources(
            'vm.swapusage: total = 59392.00M used = 57933.81M free = 1458.19M',
            'System-wide memory free percentage: 83%'))

    def test_explicit_24_gib_concurrent_budget_allows_nearly_full_swap(self):
        self.assertTrue(self.check_resources(
            'vm.swapusage: total = 102400.00M used = 80000.00M free = 22400.00M',
            'System-wide memory free percentage: 40%',
            allow_concurrent_mlx=True, max_memory_gib=24))

    def test_concurrent_budget_must_not_exceed_24_gib(self):
        self.assertFalse(self.check_resources(
            'vm.swapusage: total = 102400.00M used = 80000.00M free = 22400.00M',
            'System-wide memory free percentage: 40%',
            allow_concurrent_mlx=True, max_memory_gib=24.01))

    def test_safe_pressure_and_swap_allow_stage(self):
        self.assertTrue(self.check_resources(
            'vm.swapusage: total = 1024.00M used = 128.00M free = 896.00M',
            'System-wide memory free percentage: 83%'))

    def test_low_memory_and_unrecognized_status_hold(self):
        self.assertFalse(self.check_resources(
            'vm.swapusage: total = 0.00M used = 0.00M free = 0.00M',
            'System-wide memory free percentage: 9%'))
        self.assertFalse(self.check_resources('unavailable', 'unavailable'))
