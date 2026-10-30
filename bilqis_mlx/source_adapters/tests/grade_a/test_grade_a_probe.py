"""Real symbolic source curriculum draft, tested without optimizer updates."""
from pathlib import Path
import random
import subprocess
import sys
import unittest

from bilqis_mlx.grade_a_probe import (FAMILIES, PINNED_GRAPH_SHA256,
  PINNED_SOURCES, PINNED_FULL_STUDENT_GRAPH_SHA256, candidate_course,
  make_record, probe, read_sources)

LEGACY_ROOT = Path(__file__).resolve().parents[4] / "vendor" / "legacy-v16"


@unittest.skipUnless(LEGACY_ROOT.joinpath("bilqis_micro/kernel.py").is_file(),
                     "Original source archive is not locally mounted")
class GradeAProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.micro,cls.development,cls.graph,cls.hashes,cls.graph_sha = read_sources(LEGACY_ROOT)

    def test_six_candidate_capabilities_have_real_independent_oracles(self):
        self.assertEqual(len(FAMILIES),6)
        self.assertEqual(self.hashes,PINNED_SOURCES)
        self.assertEqual(self.graph_sha,PINNED_GRAPH_SHA256)
        self.assertEqual(len(candidate_course().grades[0].capabilities),6)
        self.assertFalse(candidate_course().executable)
        for ident,root,_,_ in FAMILIES:
            chosen=[]
            for positive in (False,True):
                record,lib = make_record(ident,random.Random(1234),positive,
                        split="train",micro=self.micro,development=self.development)
                gold=lib.evaluate(record)
                self.assertEqual(gold,lib.independent_evaluate(record))
                self.assertEqual(gold,"TRUE" if positive else "FALSE")
                self.assertIn(root,self.graph['tokens'])
                chosen.append(record)
            self.assertNotEqual(chosen[0],chosen[1],f"{ident} used an incidental label flip")

    def test_train_and_new_world_exam_rows_are_disjoint_and_source_closed(self):
        result = probe(LEGACY_ROOT)
        self.assertEqual(result['state'],"SOURCE_ATTESTED_DRAFT_NOT_TRAINING_ADMITTED")
        self.assertTrue(result['all_independent_oracle_pairs_agree'])
        self.assertTrue(result['all_exam_semantic_tokens_taught'])
        self.assertEqual(result['capability_count'],6)
        self.assertEqual(result['neural_updates'],0)
        for cap,record in result['capabilities'].items():
            self.assertEqual(record['train_rows'],24)
            self.assertEqual(record['exam_rows'],12)
            self.assertEqual(record['train_exam_input_overlap'],0)
            self.assertEqual(record['unintroduced_exam_tokens'],0)
            self.assertEqual(record['train_world_sizes'],[3,4])
            self.assertEqual(record['exam_world_sizes'],[3,4])
            self.assertEqual(record['train_truth_counts'],{'TRUE':12,'FALSE':12})
            self.assertEqual(record['exam_truth_counts'],{'TRUE':6,'FALSE':6})
            self.assertLessEqual(record['max_context_tokens'],96)
        self.assertEqual(probe(LEGACY_ROOT),result)

    def test_old_source_never_qualifies_as_new_training_grade_without_signatures(self):
        course = candidate_course()
        self.assertFalse(course.executable)
        self.assertIsNone(course.source_attestation_sha256)
        self.assertIsNone(course.assessment_manifest_sha256)

    def test_symbolic_source_probe_does_not_require_torch(self):
        """Portable source verification must not require the legacy neural stack."""
        code = r'''
import importlib.abc
import sys
from pathlib import Path
from bilqis_mlx.grade_a_probe import read_sources

class BlockTorch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "torch" or fullname.startswith("torch."):
            raise ModuleNotFoundError("blocked torch import")
        return None

sys.meta_path.insert(0, BlockTorch())
micro, development, graph, hashes, graph_sha = read_sources(Path(r"'''+str(LEGACY_ROOT)+r'''"))
print(len(graph["tokens"]), graph_sha, micro.evaluate(micro.record(micro.world(["A","B"]), micro.compare("EQ", micro.entity("A"), micro.entity("A")))))
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], cwd=Path(__file__).resolve().parents[4],
            text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(PINNED_GRAPH_SHA256, result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith("TRUE"))

    def test_sealed_manifest_verification_does_not_require_torch(self):
        """Runtime startup may verify the audited legacy checkpoint without PyTorch."""
        manifest = Path(__file__).resolve().parents[4] / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"
        checkpoint = (LEGACY_ROOT / "runs/primitive-consolidation-v16-triplets" /
                      "student-116760-7e9af4651f28.pt")
        if not checkpoint.is_file():
            self.skipTest("Historical full student checkpoint not mounted")
        code = r'''
import importlib.abc
import json
import sys
from pathlib import Path
from bilqis_mlx.grade_a_manifest import verify_manifest

class BlockTorch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "torch" or fullname.startswith("torch."):
            raise ModuleNotFoundError("blocked torch import")
        return None

sys.meta_path.insert(0, BlockTorch())
manifest = json.loads(Path(r"'''+str(manifest)+r'''").read_text())
result = verify_manifest(manifest, Path(r"'''+str(LEGACY_ROOT)+r'''"), Path(r"'''+str(checkpoint)+r'''"))
print(result["verified_items"], result["model_unchanged"])
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], cwd=Path(__file__).resolve().parents[4],
            text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "216 True")

    def test_exact_frozen_graph_prefix_matches_complete_historical_student(self):
        source = LEGACY_ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
        if not source.is_file():
            self.skipTest("Historical full student checkpoint not mounted")
        result = probe(LEGACY_ROOT,champion_checkpoint=source)
        binding=result['historic_student_graph_binding']
        self.assertEqual(binding['full_student_graph_sha256'],PINNED_FULL_STUDENT_GRAPH_SHA256)
        self.assertEqual(binding['student_vocab_size'],222)
        self.assertEqual(binding['preserved_legacy_semantic_prefix'],113)
        self.assertTrue(binding['prefix_identity_preserved'])
        self.assertFalse(binding['checkpoint_written'])
        self.assertFalse(binding['optimizer_updated'])


if __name__=="__main__":
    unittest.main()
