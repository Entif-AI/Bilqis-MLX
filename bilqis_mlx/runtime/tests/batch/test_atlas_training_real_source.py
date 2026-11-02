"""Real Factory row reaches C02 through pinned A01/A03/A06 authority."""
from dataclasses import replace
import json
import os
from pathlib import Path
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.live_releases import initial_course
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.runtime.atlas_training_adapter import compile_training_batch
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.tests.test_atlas_training_adapter import answer_plan_for
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from bilqis_mlx.semantics.context_eligibility import PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope
from bilqis_mlx.semantics.frame_adapters import bind_registered_source_row, public_formal_context
from bilqis_mlx.semantics.frame_compiler import FrameCompilerConfig, SourceAtom, StreamingAST, atom_evidence_digest
from bilqis_mlx.semantics.frame_schema import FrameInstance, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import _load_pinned_released_frame_schemas
from bilqis_mlx.source_adapters.school import A_ORACLE, live_source_registry

ARTIFACT = os.environ.get('BILQIS_ATLAS_REAL_ARTIFACT')

@unittest.skipUnless(ARTIFACT, 'real pinned A01 artifact not mounted')
class RealTrainingAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[4]
        source = root / 'vendor/legacy-v16'
        graph = read_sources(source)[2]
        course = initial_course(accepted_grade_a(json.loads((root / 'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json').read_text())))
        curriculum, bindings = from_legacy_course(course)
        registry, answers = live_source_registry(), live_answer_registry()
        release = compile_executable_factory_release(curriculum, bindings, CurriculumProfile.full(),
            registry, answers, source_root=source, graph=graph, verification_seed=31)
        cls.context = SourceExecutionContext(release, graph, source, registry, answers)
        cls.row = cls.context.draw_rows(seed=31, capability='A.IDENTITY', each=2)[0]
        cls.selection = AtlasArtifactSelection(ARTIFACT,
            '5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7',
            '58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306',
            'f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec')
        snapshot = load_pinned_atlas_snapshot(cls.selection)
        end = len(cls.row['tokens'])
        task = TaskScope('p', 't', 'TRAINING', snapshot.release_sha256, 'r', 's', 3, 5, end)
        policy = ContextPolicy('p', 1, 1, ('TRAINING',), (PUBLIC_FORMAL,), ('r',), ('s',),
            (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
            tuple((PUBLIC_FORMAL,) * count for count in range(3, 25)))
        adapter = registry.require('bilqis_mlx.grade_a_probe.make_record', A_ORACLE)
        projection, frontier = public_formal_context(adapter, cls.row, snapshot, source_root=source,
            graph=graph, task_scope=task, source_frontier=SourceFrontier(1, 1, ()),
            policy=policy, source_seed=31, source_each=2)
        tree = bind_registered_source_row(adapter, cls.row, snapshot, source_root=source, graph=graph,
            source_span=SourceSpan(0, end), causal_prefix_end=end)
        source_id = tree.root.source_instance_id
        atoms = tuple(SourceAtom(i, graph['tokens'][token], f'{source_id}#atom:{i}')
                      for i, token in enumerate(cls.row['tokens']))
        ast = StreamingAST(source_id, atoms, (tree,))
        grants = tuple(SourceGrant(atom.source_reference, 'p', 't', PUBLIC_FORMAL,
            snapshot.release_sha256, atom_evidence_digest(source_id, atom, snapshot.release_sha256),
            ('TRAINING',), ('r',), ('s',), 1, 1, 0, 0) for atom in atoms)
        frontier = replace(frontier, grants=tuple(sorted((*frontier.grants, *grants), key=lambda item: item.source_handle)))
        frames = tuple(item for item in projection.envelopes if type(item.frame) is FrameInstance)
        schema_ids = tuple(sorted({item.frame.frame_schema_id for item in frames}))
        roles = tuple(sorted({binding.role_id for item in frames for binding in item.frame.bindings}))
        cls.feature_schema = FeatureSchema(roles, schema_ids, source_bindings=tuple(
            (schema_id, adapter.descriptor.adapter_id) for schema_id in schema_ids))
        cls.features = build_feature_manifest(snapshot, cls.feature_schema)
        manifest = _load_pinned_released_frame_schemas('micro', cls.selection).manifest
        cls.config = FrameCompilerConfig(tuple(body.parse() for body in manifest.bodies),
            manifest.schema_map, None, task, frontier, policy)
        cls.args = dict(delivery=describe_delivered_teaching(release, 'A.IDENTITY', 'source.direct/A.IDENTITY', (cls.row,)),
            delivery_capability='A.IDENTITY', delivery_release_sha256=release.release_sha256,
            teacher_strategy={}, requested_count=1, optimizer_step_seed=1, rehearsal_by_id={},
            visible_ends={cls.row['id']: end}, source_ast_for=lambda _: ast,
            answer_plan_for=lambda *args: answer_plan_for(*args), frames_for_ast=lambda _: projection.envelopes,
            task_scope=task, source_frontier=frontier, eligibility_policy=policy,
            generation_binding=release.release_sha256, atlas_selection=cls.selection,
            feature_schema=cls.feature_schema)

    def compile(self, config, features):
        return compile_training_batch((self.row,), self.context, {'context': 1024},
            compiler_config=config, atlas_features=features, **self.args)

    def test_real_row_accepts_canonical_and_rejects_both_forged_authorities(self):
        batch = self.compile(self.config, self.features)
        self.assertTrue(batch.rows[0].model_input.features)
        self.assertTrue(all(row.source_status == 'ADMITTED_FORMAL_ABI_UNTYPED'
                            and row.type_ids for row in batch.rows[0].model_input.features))
        row = self.features.concepts[0]
        forged = replace(row, graph64=(9.0,) + row.graph64[1:])
        with self.assertRaises(BilqisError):
            self.compile(self.config, replace(self.features, concepts=(forged,) + self.features.concepts[1:]))
        entries = self.config.schema_map.entries
        swapped = tuple(sorted((replace(entries[0], tag=entries[1].tag),
                                replace(entries[1], tag=entries[0].tag), *entries[2:])))
        with self.assertRaises(BilqisError):
            self.compile(replace(self.config, schema_map=replace(self.config.schema_map, entries=swapped)), self.features)
