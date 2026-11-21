"""Planning-custody currentness guards for the neural-inert production journey."""
from types import MappingProxyType
import unittest
from unittest.mock import patch

from .pre_neural_journey_support import PreNeuralJourneySupport


class PreNeuralJourneyPlanningCustodyTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_priority_planning_deep_custody_binds_once_then_uses_currentness(self):
        from bilqis_mlx.runtime import bamf_bundle
        from bilqis_mlx.runtime.bamf_operator import session_support
        from bilqis_mlx.runtime.bamf_bundle import currentness_transaction
        from bilqis_mlx.runtime.bamf_bundle.source_authority_custody import currentness
        from bilqis_mlx.runtime.priority_source_offer import _require_planning_generation

        c09_original = currentness_transaction.bind_source_authority_currentness
        context_features_original = session_support.bind_accepted_execution_feature_context
        planning_features_original = bamf_bundle.authenticate_bamf_execution_feature_context
        counts = {"c09": 0, "context_features": 0, "planning_features": 0}

        def c09_counted(*args, **kwargs):
            counts["c09"] += 1
            return c09_original(*args, **kwargs)

        def context_features_counted(*args, **kwargs):
            counts["context_features"] += 1
            return context_features_original(*args, **kwargs)

        def planning_features_counted(*args, **kwargs):
            counts["planning_features"] += 1
            return planning_features_original(*args, **kwargs)

        with patch.object(
                currentness_transaction, "bind_source_authority_currentness",
                side_effect=c09_counted), patch.object(
                    session_support, "bind_accepted_execution_feature_context",
                    side_effect=context_features_counted), patch.object(
                        bamf_bundle, "authenticate_bamf_execution_feature_context",
                        side_effect=planning_features_counted):
            (_pointer, _before, _after, context, selected, _rows,
             _pointer_bytes, _event_bytes) = self.exercise_journey()

        binding = selected.offer._planning_generation
        parent = binding._parent
        self.assertEqual(counts, {
            "c09": 1, "context_features": 1, "planning_features": 0})
        self.assertEqual(
            currentness_transaction.currentness_metrics(binding._accepted_currentness)[
                "deep_authentication_count"],
            1,
        )
        stable_trust_root = binding._accepted_currentness._source_currentness._trust_root

        with patch.object(
                currentness_transaction, "bind_source_authority_currentness",
                side_effect=AssertionError("deep C09 validation repeated")), patch.object(
                    currentness, "resolve_source_authority_registry",
                    side_effect=AssertionError("deep C09 resolution repeated")), patch.object(
                        currentness, "_trust_root_snapshot",
                        return_value=stable_trust_root), patch.object(
                            session_support, "bind_accepted_execution_feature_context",
                            side_effect=AssertionError(
                                "execution context reauthenticated features")), patch.object(
                            bamf_bundle, "authenticate_bamf_execution_feature_context",
                            side_effect=AssertionError(
                                "feature context reauthenticated")):
            for _ in range(3):
                cache, authenticated = _require_planning_generation(
                    binding, context, parent)
                self.assertIs(cache, binding._cache)
                self.assertIs(authenticated, binding._authenticated_features)

    def test_priority_planning_currentness_rejects_b13_and_c09_drift(self):
        from bilqis_mlx.runtime.bamf_bundle import bundle_currentness
        from bilqis_mlx.runtime.bamf_bundle import currentness_transaction
        from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
            refresh_accepted_currentness,
        )
        from bilqis_mlx.runtime.bamf_bundle.source_authority_custody import currentness

        (_pointer, _before, _after, context, selected, _rows,
         _pointer_bytes, _event_bytes) = self.exercise_journey()
        binding = selected.offer._planning_generation
        parent = binding._parent
        transaction = binding._accepted_currentness

        with patch.object(
                bundle_currentness, "_stat_identity",
                return_value=(9, 9, 9, 9, 9)):
            with self.assertRaises(ValueError):
                refresh_accepted_currentness(transaction, parent)

        with patch.object(
                currentness, "_trust_root_snapshot",
                return_value=("HOST_SYSTEM_V1", 9, 9, 9, 9, 9)):
            with self.assertRaises(ValueError):
                refresh_accepted_currentness(transaction, parent)

        with patch.object(
                currentness_transaction, "contract_digest", return_value="9" * 64):
            with self.assertRaises(ValueError):
                refresh_accepted_currentness(transaction, parent)

    def test_planning_generation_rejects_in_memory_parent_mutation(self):
        from bilqis_mlx.runtime.priority_source_offer import _require_planning_generation

        (_pointer, _before, _after, context, selected, _rows,
         _pointer_bytes, _event_bytes) = self.exercise_journey()
        binding = selected.offer._planning_generation
        parent = binding._parent
        optimizer = parent.retained_state.optimizer
        parameters = optimizer.parameters
        name = next(iter(parameters))
        original_parameter = parameters[name]
        original_identity = parent.run_identity

        changed_parameters = dict(parameters)
        changed_parameters[name] = original_parameter + 1
        object.__setattr__(optimizer, "parameters", MappingProxyType(changed_parameters))
        try:
            with self.assertRaises(ValueError):
                _require_planning_generation(binding, context, parent)
        finally:
            object.__setattr__(optimizer, "parameters", parameters)

        object.__setattr__(parent, "run_identity", None)
        try:
            with self.assertRaises(ValueError):
                _require_planning_generation(binding, context, parent)
        finally:
            object.__setattr__(parent, "run_identity", original_identity)


if __name__ == "__main__":
    unittest.main()
