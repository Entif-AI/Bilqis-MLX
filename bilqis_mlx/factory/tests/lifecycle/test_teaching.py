"""Optional joint instruction stays inside declared, source-checked prerequisites."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.teaching import draw_teaching_option_rows, optional_teaching_rows


def closed_source_fixture():
    from dataclasses import replace
    from bilqis_mlx.factory.adapters import SourceAdapterRegistry
    from bilqis_mlx.factory.curriculum_definition import from_legacy_course
    from bilqis_mlx.factory.executable_release import compile_executable_factory_release
    from bilqis_mlx.factory.execution import CurriculumProfile
    from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_course, _synthetic_registry
    from bilqis_mlx.factory.tests.test_executable_release import _answers
    course = _synthetic_course(6)
    curriculum, bindings = from_legacy_course(course)
    base = _synthetic_registry().require("fixture.z-generator/v1", "fixture.z-oracle/v1")
    def draw(**kwargs):
        operator = ("future.root" if kwargs["seed"] == 999 else
                    "z.op." + kwargs["capability"].partition(".C")[2])
        return tuple({**row, "record": {"operator": operator}}
                     for row in base.draw(**kwargs))
    def enrich(**kwargs):
        return draw(**kwargs, each=1)
    registry = SourceAdapterRegistry((replace(
        base, descriptor=replace(base.descriptor, teaching_option_ids=("fixture.enrich",)),
        draw=draw, enrich=enrich,
        semantic_footprint=lambda row: (row["record"]["operator"],)),))
    graph = {"tokens": ["fixture.padding", "cogal.value.false", "cogal.value.true"]}
    answers = _answers()
    release = compile_executable_factory_release(
        curriculum, bindings, CurriculumProfile.full(), registry, answers,
        source_root=None, graph=graph, verification_seed=17)
    return course, graph, registry, answers, release


class ClosedTeachingTests(unittest.TestCase):
    def test_seed_specific_enrichment_leak_fails_after_source_verification(self):
        _, graph, registry, _, release = closed_source_fixture()
        rows = optional_teaching_rows(None, graph, release, registry,
            capability="Z.C0", seed=17, enabled=True)
        self.assertEqual(rows[0]["record"]["operator"], "z.op.0")
        with self.assertRaisesRegex(ValueError, "CLOSURE:Z.C0:future.root"):
            optional_teaching_rows(None, graph, release, registry,
                capability="Z.C0", seed=999, enabled=True)

    def test_enrichment_provider_accepts_the_typed_curriculum(self):
        from dataclasses import replace
        from bilqis_mlx.curriculum import AnswerFamily
        from bilqis_mlx.source_adapters.school import enrich_boolean, BOOLEAN_ASSOCIATION_OPTION
        _, _, _, _, release = closed_source_fixture()
        grade = release.curriculum.grades[0]
        numeric = replace(grade.capabilities[-1], answer_families=(
            AnswerFamily("numeric_active", ("0", "1", "2", "3")),))
        curriculum = replace(release.curriculum, grades=(replace(
            grade, capabilities=(*grade.capabilities[:-1], numeric)),))
        with patch("bilqis_mlx.source_adapters.school.draw_b_grade_bridges",
                   return_value=()) as draw:
            enrich_boolean(source_root=None, graph={}, course=curriculum,
                capability="Z.C0", seed=17, option_id=BOOLEAN_ASSOCIATION_OPTION)
        self.assertEqual(draw.call_args.kwargs["maximum"], 3)

    def test_direct_teaching_option_uses_normal_closed_generation(self):
        _, graph, registry, _, release = closed_source_fixture()
        with self.assertRaisesRegex(ValueError, "CLOSURE:Z.C0:future.root"):
            draw_teaching_option_rows(None, graph, release, registry,
                capability="Z.C0", option_id="source.direct/Z.C0", seed=999, each=4)


class JointTeachingTests(unittest.TestCase):
    def draw(self, row, *, foreign=False):
        execution = SimpleNamespace(prerequisites=('Z.PRIOR',),
            provider_id='same-provider', provider_implementation_sha256='a' * 64,
            teaching_option_ids=('contrast',),
            answer_families=(SimpleNamespace(kind='binary', values=('TRUE', 'FALSE')),))
        names = ('Z.TARGET', 'Z.PRIOR', 'Z.UNRELATED')
        executions = {cap: SimpleNamespace(**vars(execution), capability_id=cap,
            grade_id='Z', stage=0 if cap == 'Z.PRIOR' else 1) for cap in names}
        roots = {cap: (cap + '.root',) for cap in names}
        release = SimpleNamespace(verify=lambda: None,
            curriculum=SimpleNamespace(capability_map={cap: SimpleNamespace(taught_roots=roots[cap])
                                                       for cap in names}),
            execution_plan=SimpleNamespace(capability_map=executions,
                capabilities=tuple(executions.values()), grades=(SimpleNamespace(grade_id='Z'),)))
        if foreign:
            release.execution_plan.capability_map["Z.PRIOR"] = SimpleNamespace(
                **{**vars(execution), "provider_id": "foreign-provider"})
        adapter = SimpleNamespace(
            descriptor=SimpleNamespace(teaching_option_ids=('contrast',)),
            enrich=lambda **kwargs: (row,), check=lambda r, **_: r.get('gold') == 'TRUE',
            semantic_footprint=lambda r: roots[r['capability']])
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
