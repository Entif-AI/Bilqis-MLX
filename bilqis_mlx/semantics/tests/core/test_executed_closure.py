import unittest

from bilqis_mlx.semantics.cognitive_dependencies import ArtifactKind, ArtifactNode, DependencyKind, DependencyRef
from bilqis_mlx.semantics.dependencies.closure import canonical_closure_bytes, closure_digest, decode_closure_nodes, encode_closure_nodes


class ExecutedClosureTests(unittest.TestCase):
    def test_literal_and_roundtrip(self):
        node = ArtifactNode('salience:test', ArtifactKind.SALIENCE_EVIDENCE, '0' * 64, True,
                            (DependencyRef(DependencyKind.SOURCE, 'source:test'),), 2, 3)
        self.assertEqual(closure_digest((node,)), 'ffed07eed66c4b179ce71c2d8fcf5272969dc1088389a7d0d1980e8e4f047d5a')
        self.assertFalse(canonical_closure_bytes((node,)).endswith(b'\n'))
        self.assertEqual(decode_closure_nodes(encode_closure_nodes((node,))), (node,))

    def test_missing_artifact_fails(self):
        node = ArtifactNode('root', ArtifactKind.SALIENCE_EVIDENCE, '0' * 64, True,
                            (DependencyRef(DependencyKind.ARTIFACT, 'absent'),), 2, 3)
        with self.assertRaises(Exception):
            closure_digest((node,))
