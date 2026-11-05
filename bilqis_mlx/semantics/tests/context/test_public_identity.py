"""Public compatibility of the context eligibility implementation split."""
from dataclasses import replace
import pickle
import typing
import unittest
from unittest.mock import patch

from bilqis_mlx.semantics import context_eligibility as api
from bilqis_mlx.semantics.tests.test_context_eligibility import _case


class ContextPublicIdentityTests(unittest.TestCase):
    def test_public_class_function_and_method_identity(self):
        for obj in (api.ContextEligibility, api.ApprovedContextProjection,
                    api.check_context_eligibility, api.project_context,
                    api.transition_context, api.frame_evidence_digest):
            with self.subTest(obj=obj):
                self.assertEqual(obj.__module__, api.__name__)
                self.assertIs(pickle.loads(pickle.dumps(obj)), obj)
                typing.get_type_hints(obj)
        method = api.ApprovedContextProjection.cache_key
        self.assertEqual(method.__module__, api.__name__)
        typing.get_type_hints(method)

    def test_public_gate_projection_and_digest_patch_points(self):
        frames, task, frontier, policy = _case()
        hold = api.ContextHold(('TEST_HOLD',), (), ())
        with patch.object(api, 'check_context_eligibility', return_value=hold) as gate:
            self.assertIs(api.project_context(frames, task, frontier, policy), hold)
            gate.assert_called_once_with(frames, task, frontier, policy)
        with patch.object(api, 'project_context', return_value=hold) as project:
            self.assertIs(api.transition_context(None, frames, task, frontier, policy).current, hold)
            project.assert_called_once_with(frames, task, frontier, policy)
        with patch.object(api, '_digest', return_value='sentinel'):
            self.assertEqual(api.frame_evidence_digest(frames[0].frame), 'sentinel')

    def test_combined_envelope_grant_and_join_denials_are_preserved(self):
        frames, task, frontier, policy = _case()
        frames = (replace(frames[0], correction_generation=0), frames[1])
        grants = tuple(
            replace(grant, revoked=True)
            if grant.source_handle == frames[0].source_handle else grant
            for grant in frontier.grants
        )
        result = api.check_context_eligibility(
            frames, task, replace(frontier, grants=grants),
            replace(policy, allowed_join_pairs=()))
        self.assertEqual(result, api.ContextHold(
            ('BAMF_CONTEXT_CORRECTION_STALE', 'BAMF_CONTEXT_FORBIDDEN_JOIN',
             'BAMF_CONTEXT_SOURCE_REVOKED'),
            ('source:frame:0', 'source:frame:1'),
            (('BAMF_CONTEXT_CORRECTION_STALE', 'source:frame:0'),
             ('BAMF_CONTEXT_FORBIDDEN_JOIN', 'source:frame:0'),
             ('BAMF_CONTEXT_FORBIDDEN_JOIN', 'source:frame:1'),
             ('BAMF_CONTEXT_SOURCE_REVOKED', 'source:frame:0')),
        ))
