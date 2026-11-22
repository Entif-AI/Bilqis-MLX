"""Restart projection regression for active generated-grade ancestry."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from bilqis_mlx.runtime.tests.admission.atlas import test_active_generated_grade as support


def test_bootstrap_ancestry_memo_skips_historical_replay_after_validation():
    case = support.ActiveGeneratedGradeTests()
    proposal, definition = case._fixture()
    active = case._bootstrap_active_grade(proposal, definition)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        from bilqis_mlx.runtime import active_generated_grade_custody as custody

        memo = custody._ancestry_memo_path(root, active)
        memo.parent.mkdir(parents=True, exist_ok=True)
        memo.write_text(json.dumps({
            "schema": "bilqis.bamf.active-grade-ancestry-memo/v1",
            "run_id": active.run_id,
            "activation_sha256": active.activation_sha256,
            "activation_manifest_sha256": active.activation_manifest_sha256,
            "activation_acceptance_sha256": active.activation_acceptance_sha256,
            "activation_generation": active.activation_generation,
            "validated_checkpoint_sha256": "9" * 64,
        }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        with patch(
            "bilqis_mlx.runtime.bamf_bundle.publication."
            "accepted_authority_checkpoint."
            "accepted_authority_tip_extends_checkpoint",
            return_value=True,
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
            side_effect=AssertionError("validated ancestry memo replayed history"),
        ), patch(
            "bilqis_mlx.runtime.bamf_bundle.feature.historical_acceptance."
            "iter_accepted_bamf_history",
            side_effect=AssertionError("validated ancestry memo replayed history"),
        ):
            assert custody._activation_is_accepted_ancestor(root, active)
