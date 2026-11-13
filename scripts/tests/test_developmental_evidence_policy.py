"""Regression coverage for ADR-133/ADR-134 machine-policy closure."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts import check_factory_architecture as checker


class DevelopmentalEvidencePolicyTests(unittest.TestCase):
    def _fixture_root(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)

        policy = json.loads((checker.REPO_ROOT / checker.DEVELOPMENTAL_POLICY).read_text())
        policy_path = root / checker.DEVELOPMENTAL_POLICY
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(json.dumps(policy) + "\n")

        for relative in checker.FOUNDATION_POLICY_DOCS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(checker.FOUNDATION_POLICY_MARKER + "\n")

        owner = root / "bilqis_mlx/runtime/_capability/factory/factory_retention_owner.py"
        owner.parent.mkdir(parents=True, exist_ok=True)
        owner.write_text(
            "CURRENT_EVIDENCE_STAGE = EvidenceStage.FOUNDATION_ACQUISITION\n")
        evaluation = root / "bilqis_mlx/runtime/_capability/capability_evaluation.py"
        evaluation.write_text(
            "STRICT_GENERALIZATION = \"STRICT_GENERALIZATION\"\n"
            "evidence_stage: EvidenceStage = EvidenceStage.FOUNDATION_ACQUISITION\n")
        return root

    def test_machine_policy_rejects_unlocked_adr_134_fields(self):
        root = self._fixture_root()
        policy_path = root / checker.DEVELOPMENTAL_POLICY
        baseline = json.loads(policy_path.read_text())
        self.assertEqual(checker._developmental_evidence_policy(root), ())

        mutations = (
            (("schema",), "bilqis.developmental-evidence-policy/v999"),
            (("current_acceptance", "allowed_evidence_kinds"), ["STRICT_HELD_OUT"]),
            (("alpha_advancement", "pool_growth"), "FIXED_HELD_OUT"),
            (("alpha_advancement", "complexity_growth"), "STATIC"),
            (("novelty_measurement", "record_pass_failure_ratios"), False),
            (("novelty_measurement", "axes"), ["SURFACE_IDENTITY"]),
        )
        for keys, value in mutations:
            with self.subTest(keys=keys):
                policy = json.loads(json.dumps(baseline))
                target = policy
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                policy_path.write_text(json.dumps(policy) + "\n")
                problems = checker._developmental_evidence_policy(root)
                self.assertTrue(
                    any("DEVELOPMENTAL_EVIDENCE_POLICY_DRIFT:" + ".".join(keys)
                        in problem for problem in problems),
                    problems,
                )

    def test_release_boundary_override_allows_only_exact_audited_issue_body(self):
        root = self._fixture_root()
        relative = Path("docs/tasks/bamf-0.2/issues/C13.md")
        body = "release-scoped owner rewrite\n"
        (root / relative).write_text(body)
        override = root / checker.RELEASE_BOUNDARY_OVERRIDES
        override.parent.mkdir(parents=True, exist_ok=True)
        override.write_text(json.dumps({
            "schema": "bilqis.bamf.release-boundary-overrides/v1",
            "entries": [{
                "key": "C13",
                "live_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            }],
        }) + "\n")
        self.assertFalse(any(
            str(relative) in problem and "DEVELOPMENTAL_POLICY_MARKER_MISSING" in problem
            for problem in checker._developmental_policy_docs(root)))

        (root / relative).write_text(body + "drift\n")
        self.assertTrue(any(
            str(relative) in problem and "DEVELOPMENTAL_POLICY_MARKER_MISSING" in problem
            for problem in checker._developmental_policy_docs(root)))


if __name__ == "__main__":
    unittest.main()
