"""B11.2 compact Factory reporting boundary."""
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_model import BamfGradientExecution
from bilqis_mlx.runtime.factory_candidate_training import (
    FactoryCandidateDiagnostics,
    _reporting_diagnostics,
)


class FactoryCandidateReportingTests(unittest.TestCase):
    def test_heavy_gradient_execution_is_retained_only_by_explicit_opt_in(self):
        execution = object.__new__(BamfGradientExecution)

        self.assertIsNone(_reporting_diagnostics(execution, False))

        diagnostics = _reporting_diagnostics(execution, True)
        self.assertIs(type(diagnostics), FactoryCandidateDiagnostics)
        self.assertIs(diagnostics.gradient_execution, execution)
        self.assertEqual(
            diagnostics.schema_version,
            "bilqis.mlx.b11-factory-diagnostics/v1")

        with self.assertRaises(BilqisError):
            _reporting_diagnostics(execution, 1)
