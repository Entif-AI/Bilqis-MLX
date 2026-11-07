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
        source = SimpleNamespace(__post_init__=lambda: None, release=release)
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
        foundation.assert_called_once()
        args = foundation.call_args.args
        self.assertEqual(args[7], ((), ()))

    def test_package_import_rejects_caller_policy_surface(self):
        with self.assertRaises(TypeError):
            evaluate_factory_package_import(
                object(), object(), "artifact", "B.IDBOOLOPS",
                run_dir=Path("unused"), policy=object(), cohorts=())


if __name__ == "__main__":
    unittest.main()
