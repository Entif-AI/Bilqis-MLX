import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from bilqis_mlx.compatibility.executable_projection import compile_projected_executable_release
from bilqis_mlx.factory.atlas_frontier import AtlasLearnerEvidence, PlannerBudget, _build_snapshot
from bilqis_mlx.factory.autonomy import (
    EvidenceReceipt,
    compile_autonomy_plan,
    initial_evidence_ledger,
    obligations_for_capability,
    record_evidence,
)
from bilqis_mlx.factory.candidate_frontier import load_candidate_frontier
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.skos_curriculum import (
    LearnedFrontier,
    SOURCE_FAMILY_ADAPTERS,
    _compile_semantic_curriculum_snapshot,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier import _rights
from bilqis_mlx.factory.tests.sources.test_skos_curriculum import _snapshot as source_atlas_snapshot
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.source_adapters import event_frames
from bilqis_mlx.source_adapters.school import live_source_registry


ROOT = Path(__file__).resolve().parents[4]
LEGACY = ROOT / "vendor/legacy-v16"


class EventCandidateRealizationFixture:
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        output = Path(cls.temp.name)
        builder = ROOT / "lib/ithkuil/src/build_curriculum_frontier.py"
        subprocess.run(
            [sys.executable, str(builder)], check=True, capture_output=True,
            env={**os.environ, "BILQIS_CURRICULUM_FRONTIER_OUT": str(output)},
        )
        cls.frontier = load_candidate_frontier(
            output, ROOT / "lib/ithkuil/_data/csv",
            expected_builder_sha256=hashlib.sha256(builder.read_bytes()).hexdigest(),
        )
        cls.parent_graph = registry_graph()
        course = accepted_grade_a(json.loads(
            (ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text()))
        cls.current, _, _ = compile_projected_executable_release(
            course, course, LEGACY, cls.parent_graph)
        cls.source_registry = live_source_registry()
        cls.answer_registry = live_answer_registry()

    def atlas_fixture(self):
        definitions = [
            ("urn:formal:boolean:AND", None, None),
            ("urn:formal:numeric:ADD", None, None),
        ]
        definitions.extend(
            (event_frames.atlas_semantic_id(capability),
             ("lexicon", "lexicon_root_senses", spec.sense_id), None)
            for capability, spec in event_frames.SOURCE_SPECS.items())
        atlas = source_atlas_snapshot(tuple(definitions))
        candidate = _compile_semantic_curriculum_snapshot(
            atlas, SOURCE_FAMILY_ADAPTERS, LearnedFrontier(atlas.release_sha256))
        source_frontier, policy = _rights()
        return candidate, source_frontier, policy

    def learner_evidence(self, current, mastered, capability):
        plan = compile_autonomy_plan(current)
        checkpoint = "e" * 64
        step = 0
        ledger = initial_evidence_ledger(current, plan=plan)
        receipt_index = 0
        for prerequisite in sorted(mastered):
            for obligation in obligations_for_capability(current, prerequisite, plan=plan):
                receipt_index += 1
                ledger = record_evidence(
                    current,
                    ledger,
                    EvidenceReceipt(
                        obligation.obligation_id,
                        f"event-prerequisite-{capability}-{receipt_index}",
                        checkpoint,
                        step,
                        hashlib.sha256(
                            f"event-prerequisite:{capability}:{receipt_index}".encode()
                        ).hexdigest(),
                        obligation.minimum_specimens,
                        True,
                    ),
                    plan=plan,
                    current_checkpoint_sha256=checkpoint,
                    current_optimizer_step=step,
                )
        return plan, checkpoint, step, ledger, AtlasLearnerEvidence(ledger, checkpoint, step)

    def build_snapshot(self, candidate, source_frontier, policy, current, staged):
        return _build_snapshot(
            candidate, source_frontier, policy,
            budget=PlannerBudget(10, 100, 1000),
            candidate_frontier_sha256=self.frontier.release_sha256,
            staged_release_sha256s=(staged.successor.release_sha256,),
            admitted_release_sha256=current.release_sha256,
            admission_receipt_sha256="a" * 64,
        )
