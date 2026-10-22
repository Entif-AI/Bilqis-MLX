"""Optional joint instruction stays inside declared, source-checked prerequisites."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.teaching import draw_teaching_option_rows


class JointTeachingTests(unittest.TestCase):
    def draw(self, row, *, foreign=False):
        execution = SimpleNamespace(prerequisites=('Z.PRIOR',),
            provider_id='same-provider', provider_implementation_sha256='a' * 64,
            teaching_option_ids=('contrast',),
            answer_families=(SimpleNamespace(kind='binary', values=('TRUE', 'FALSE')),))
        release = SimpleNamespace(verify=lambda: None,
            execution_plan=SimpleNamespace(capability_map={
                cap: execution for cap in ('Z.TARGET', 'Z.PRIOR', 'Z.UNRELATED')}))
        if foreign:
            release.execution_plan.capability_map["Z.PRIOR"] = SimpleNamespace(
                **{**vars(execution), "provider_id": "foreign-provider"})
        adapter = SimpleNamespace(
            descriptor=SimpleNamespace(teaching_option_ids=('contrast',)),
            enrich=lambda **kwargs: (row,), check=lambda r, **_: r.get('gold') == 'TRUE')
        with patch('bilqis_mlx.factory.teaching.runtime_adapter_for_release', return_value=adapter):
            return draw_teaching_option_rows(None, {}, release, None,
                capability='Z.TARGET', option_id='contrast', seed=1, each=12)

    def test_declared_prerequisite_is_a_legal_instructional_constituent(self):
        row = dict(id='prior-example', capability='Z.PRIOR', gold='TRUE')
        self.assertEqual(self.draw(row), (row,))

    def test_unrelated_admitted_capability_cannot_enter_the_option(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_ORACLE_DISAGREEMENT'):
            self.draw(dict(id='unrelated', capability='Z.UNRELATED', gold='TRUE'))

    def test_prerequisite_gold_still_requires_its_source_check(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_ORACLE_DISAGREEMENT'):
            self.draw(dict(id='wrong', capability='Z.PRIOR', gold='FALSE'))

    def test_declared_prerequisite_must_use_the_same_verified_provider(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_ORACLE_DISAGREEMENT'):
            self.draw(dict(id='foreign', capability='Z.PRIOR', gold='TRUE'), foreign=True)
