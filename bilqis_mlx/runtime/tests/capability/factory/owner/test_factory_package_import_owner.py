"""C05 package-import screening stays inside the Factory retention owner."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.learning.atlas_package_import import PackageImportTransaction
import bilqis_mlx.runtime.factory_retention_owner as owner
from bilqis_mlx.runtime.factory_retention_owner import evaluate_factory_package_import


class FactoryPackageImportOwnerTests(unittest.TestCase):
    def test_foundation_import_uses_owner_fixed_school_without_training_claims(self):
        release_sha = "a" * 64
        target = "B.IDBOOLOPS"
        capabilities = (
            SimpleNamespace(capability_id="B.AND", grade_id="B"),
            SimpleNamespace(capability_id=target, grade_id="B"),
        )
        release = SimpleNamespace(
            release_sha256=release_sha,
            execution_plan=SimpleNamespace(
                capabilities=capabilities,
                capability_map={item.capability_id: item for item in capabilities},
            ),
        )
        accepted_runtime = Mock()
        source = SimpleNamespace(
            __post_init__=lambda: None,
            require_accepted_runtime=accepted_runtime,
            release=release,
        )
        transaction = object.__new__(PackageImportTransaction)
        fixed = (SimpleNamespace(case=SimpleNamespace()),)
        foundation = Mock(return_value="evaluation")
        with patch.multiple(
                owner,
                _package_import_from_live_parent=Mock(return_value=(
                    object(), object(), object(), object())),
                _fixed_school_instruments=Mock(return_value=fixed),
                _foundation_retention_evaluation=foundation,
                _adaptive_retention_evaluation=Mock(side_effect=AssertionError(
                    "foundation package import entered adaptive C05 path")),
        ):
            result = evaluate_factory_package_import(
                source, transaction, "artifact", target,
                run_dir=Path("unused"))

        self.assertEqual(result, "evaluation")
        accepted_runtime.assert_called_once_with(Path("unused"))
        foundation.assert_called_once()
        args = foundation.call_args.args
        self.assertEqual(args[7], ((), ()))

    def test_package_import_rejects_caller_policy_surface(self):
        with self.assertRaises(TypeError):
            evaluate_factory_package_import(
                object(), object(), "artifact", "B.IDBOOLOPS",
                run_dir=Path("unused"), policy=object(), cohorts=())

    def test_package_import_custody_failure_stops_before_c05_work(self):
        transaction = object.__new__(PackageImportTransaction)
        source = SimpleNamespace(
            __post_init__=lambda: None,
            require_accepted_runtime=Mock(side_effect=RuntimeError("held")),
        )
        with patch.object(
                owner, "_package_import_from_live_parent",
                side_effect=AssertionError("C05 work started before accepted custody")):
            with self.assertRaisesRegex(RuntimeError, "held"):
                evaluate_factory_package_import(
                    source, transaction, "artifact", "B.IDBOOLOPS",
                    run_dir=Path("unused"))

    def test_historical_package_import_stays_on_legacy_fixed_school_path(self):
        release_sha = "a" * 64
        target = "B.IDBOOLOPS"
        capability = SimpleNamespace(capability_id=target, grade_id="B")
        release = SimpleNamespace(
            release_sha256=release_sha,
            execution_plan=SimpleNamespace(
                capabilities=(capability,), capability_map={target: capability}),
        )
        source = SimpleNamespace(
            __post_init__=lambda: None,
            require_accepted_runtime=Mock(),
            release=release,
        )
        transaction = object.__new__(PackageImportTransaction)
        parent = SimpleNamespace(run_identity=None)
        candidate = object()
        state = object()
        cache = object()
        fixed = SimpleNamespace(rows=(SimpleNamespace(),), seed=17)
        legacy_receipt = {"factory_release_sha256": release_sha}
        fixed_exam = {"factory_release_sha256": release_sha}
        sentinel = object()
        foundation = Mock(return_value=sentinel)
        read_current = Mock(return_value=legacy_receipt)
        load_frontier = Mock(return_value=fixed)
        bamf_school = Mock(side_effect=AssertionError(
            "historical package import entered BAMF trust custody"))
        with patch.multiple(
                owner,
                _package_import_from_live_parent=Mock(return_value=(
                    parent, candidate, state, cache)),
                read_current=read_current,
                frontier_exam=Mock(return_value=fixed_exam),
                load_frontier_cohort=load_frontier,
                _bamf_fixed_school_cohort=bamf_school,
                _instruments=Mock(return_value=(object(),)),
                _foundation_retention_evaluation=foundation,
        ):
            result = evaluate_factory_package_import(
                source, transaction, "artifact", target,
                run_dir=Path("unused"))

        self.assertIs(result, sentinel)
        read_current.assert_called_once_with(Path("unused"))
        load_frontier.assert_called_once_with(Path("unused"), fixed_exam)
        bamf_school.assert_not_called()


if __name__ == "__main__":
    unittest.main()
