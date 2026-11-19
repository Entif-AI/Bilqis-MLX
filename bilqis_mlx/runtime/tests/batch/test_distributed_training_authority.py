"""Portable C08 evidence reconstructs exact B11 execution-extended authority."""
import json
import unittest

from bilqis_mlx.runtime.atlas_training_authority import (
    extend_training_dependencies,
)
from bilqis_mlx.runtime.c08_distributed_evidence import (
    DistributedB11Evidence, evidence_training_extension,
)
from bilqis_mlx.runtime.tests.correction.capability_support_owner_support import (
    training_authority,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyKind, DependencyRef,
)


class DistributedTrainingAuthorityTests(unittest.TestCase):
    def test_execution_extension_reconstructs_exact_final_b11_digest(self):
        base = training_authority()
        dependency = DependencyRef(DependencyKind.OPERATOR, "operator:runtime-read")
        node = ArtifactNode(
            "artifact:runtime-read", ArtifactKind.MOTIF, "a" * 64, True,
            (dependency,), 2, 1)
        final = extend_training_dependencies(
            base, (dependency, node.reference), artifact_nodes=(node,))
        artifact_json = json.dumps([{
            "artifact_id": node.artifact_id, "kind": node.kind.value,
            "content_digest": node.content_digest, "eligible": node.eligible,
            "immediate_dependencies": [
                [ref.kind.value, ref.key] for ref in node.immediate_dependencies],
            "impact": node.impact, "exigency": node.exigency,
        }], sort_keys=True, separators=(",", ":"))
        evidence = DistributedB11Evidence(
            "b" * 64, 0, 0, base.source_row_id, base.generation_binding,
            "fixture-run", 1, "c" * 64, ((0, 0),), (), (), (), (), (), (), (),
            (), final.digest,
            tuple((ref.kind.value, ref.key) for ref in final.immediate_dependencies),
            artifact_json)
        dependencies, artifacts = evidence_training_extension(evidence)
        reconstructed = extend_training_dependencies(
            base, dependencies, artifact_nodes=artifacts)
        self.assertEqual(reconstructed.digest, final.digest)
        self.assertEqual(reconstructed.artifact_nodes, final.artifact_nodes)


if __name__ == "__main__":
    unittest.main()
