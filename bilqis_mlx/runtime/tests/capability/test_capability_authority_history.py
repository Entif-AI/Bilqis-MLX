"""Cold accepted-history progression authority regressions for C09."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.learning.capability_championship import ReplayBinding
from bilqis_mlx.runtime.accepted_corrections import (
    _RUNTIME_OWNER, record_accepted_correction,
)
from bilqis_mlx.runtime.bamf_bundle.admission import accept_and_publish
from bilqis_mlx.runtime.capability_authority import (
    AuthorityKind, evaluate_accepted_progression_authority,
)
from bilqis_mlx.runtime.tests.capability.test_capability_authority import (
    GENERATION, GRAPH, _authority, _evidence, _release,
)
from bilqis_mlx.runtime.tests.correction.test_atlas_capability_support_owner import (
    _source_qualified_state,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, retention_decision, shape_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _ref,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind


SOURCE_ROW = "source:accepted-progression:target"


class AcceptedProgressionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def _publish_support_and_correction(self):
        parent, transaction, retained, _training_authority = _source_qualified_state(
            capability="target",
            source_row=SOURCE_ROW,
            source_family="source-family:accepted-progression",
            episode="episode:accepted-progression",
            generation_binding=GENERATION,
        )
        bundle = candidate(retained)
        decision = retention_decision(parent=parent, retained=retained)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            accept_and_publish(
                self.run, bundle, retained, decision=decision,
                feature_sha256=bundle.extents.factor_map_digest,
                training_authorities=transaction.training_authorities,
            )
            record_accepted_correction(
                self.run,
                _event(_ref(DependencyKind.SOURCE, SOURCE_ROW)),
                AUTHORITY,
            )
        _RUNTIME_OWNER.clear()

    def _evaluate(self, correction_registry=None):
        release, checkpoint, admission = _release()
        solver, target = _evidence(release, "target")
        replay = ReplayBinding(
            solver, GENERATION, checkpoint, "C",
            tuple(sorted(set(target.assessment.solver_contracts))),
            lambda generation, pointer:
                generation == GENERATION and pointer == checkpoint,
        )
        authorities = dict(
            admission=admission,
            semantic_graph_sha256=GRAPH,
            prerequisite_thresholds=(),
            source_rights=_authority(AuthorityKind.SOURCE_RIGHTS),
            promotion_policy=_authority(AuthorityKind.PROMOTION_POLICY),
            admission_lease=_authority(AuthorityKind.ADMISSION_LEASE),
        )
        if correction_registry is not None:
            authorities["correction_authority_registry"] = correction_registry
        with shape_patch():
            return evaluate_accepted_progression_authority(
                self.run, release, "target", target, (), replay, **authorities)

    def test_cold_accepted_correction_history_fails_closed_without_authority(self):
        self._publish_support_and_correction()
        gate = self._evaluate()
        self.assertEqual(gate.status, "HELD")
        self.assertEqual(gate.reason, "CURRENT_CAPABILITY_SUPPORT_REQUIRED")

        with_authority = self._evaluate(AUTHORITY)
        self.assertEqual(with_authority.status, "HELD")
        self.assertEqual(with_authority.reason, "CURRENT_CAPABILITY_SUPPORT_HELD")


if __name__ == "__main__":
    unittest.main()
