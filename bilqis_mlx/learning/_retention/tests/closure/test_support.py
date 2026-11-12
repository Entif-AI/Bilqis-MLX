import unittest

from bilqis_mlx.runtime.atlas_capability_support_owner import _issue_owner
from bilqis_mlx.runtime.atlas_requalification_contracts import CapabilitySupport, RequalificationStatus
from bilqis_mlx.semantics.cognitive_dependencies import ArtifactKind, ArtifactNode, DependencyKind, DependencyRef


class ClosureSupportTests(unittest.TestCase):
    def test_closed_index_and_transitive_ineligibility(self):
        leaf = ArtifactNode('leaf', ArtifactKind.SALIENCE_EVIDENCE, '0'*64, False,
                            (DependencyRef(DependencyKind.SOURCE, 'source'),), 2, 3)
        root = ArtifactNode('root', ArtifactKind.SALIENCE_EVIDENCE, '1'*64, True,
                            (DependencyRef(DependencyKind.ARTIFACT, 'leaf'),), 2, 3)
        node = ArtifactNode('cap-support', ArtifactKind.CAPABILITY_SUPPORT, '2'*64, True,
                            (DependencyRef(DependencyKind.ARTIFACT, 'root'),), 2, 3)
        support = CapabilitySupport('cap', ('cap-support',), ('source',), '3'*64,
                                    ('observation',), RequalificationStatus.QUALIFIED)
        with self.assertRaises(Exception):
            _issue_owner(support, node, ('4'*64,))
        owner = _issue_owner(support, node, ('4'*64,), closure_nodes=(leaf, root))
        self.assertEqual(tuple(n.artifact_id for n in owner.index.nodes), ('cap-support', 'leaf', 'root'))
        with self.assertRaises(Exception):
            owner.require('cap', '4'*64)

    def test_signed_leaf_correction_holds_transitive_support(self):
        from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY, _event
        source = DependencyRef(DependencyKind.SOURCE, 'source:leaf')
        leaf = ArtifactNode('leaf', ArtifactKind.SALIENCE_EVIDENCE, '0'*64, True, (source,), 2, 3)
        root = ArtifactNode('root', ArtifactKind.SALIENCE_EVIDENCE, '1'*64, True,
                            (DependencyRef(DependencyKind.ARTIFACT, 'leaf'),), 2, 3)
        node = ArtifactNode('cap-support', ArtifactKind.CAPABILITY_SUPPORT, '2'*64, True,
                            (DependencyRef(DependencyKind.ARTIFACT, 'root'),), 2, 3)
        support = CapabilitySupport('cap', ('cap-support',), ('source:leaf',), '3'*64,
                                    ('observation',), RequalificationStatus.QUALIFIED)
        owner = _issue_owner(support, node, ('4'*64,), closure_nodes=(leaf, root))
        self.assertEqual(owner.require('cap', '4'*64), support)
        owner.apply_correction(_event(source), AUTHORITY)
        self.assertEqual(owner.queue.held_artifact_ids, ('leaf',))
        with self.assertRaises(Exception):
            owner.require('cap', '4'*64)
