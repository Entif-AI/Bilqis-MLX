"""Real Factory row reaches C02 through pinned A01/A03/A06 authority."""
from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
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
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance
from bilqis_mlx.runtime.tests.test_atlas_training_adapter import answer_plan_for
from bilqis_mlx.semantics.atlas.feature_io import persist_feature_manifest
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_features.formal import source_qualified_feature_row
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from bilqis_mlx.semantics.context_eligibility import PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope
from bilqis_mlx.semantics.frame_adapters import bind_registered_source_row, public_formal_context
from bilqis_mlx.semantics.frame_adapters import (
    BOOLEAN_CONNECTIVE_ADAPTER, FINITE_NUMERIC_ADAPTER, MICRO_PREDICATE_ADAPTER,
)
from bilqis_mlx.semantics.frame_compiler import FrameCompilerConfig, SourceAtom, StreamingAST, atom_evidence_digest
from bilqis_mlx.semantics.frame_schema import FrameInstance, SourceSpan
from bilqis_mlx.semantics.released_frame_schemas import _load_pinned_released_frame_schemas
from bilqis_mlx.source_adapters.school import A_ORACLE, live_source_registry

ARTIFACT = os.environ.get('BILQIS_ATLAS_REAL_ARTIFACT')


def _canonical_feature_schema(selection):
    adapters = {
        'boolean': BOOLEAN_CONNECTIVE_ADAPTER,
        'micro': MICRO_PREDICATE_ADAPTER,
        'numeric': FINITE_NUMERIC_ADAPTER,
    }
    roles, schemas, bindings = set(), [], []
    for family in ('boolean', 'micro', 'numeric'):
        manifest = _load_pinned_released_frame_schemas(family, selection).manifest
        for body in manifest.bodies:
            schema = body.parse()
            schemas.append(schema.schema_id)
            bindings.append((schema.schema_id, adapters[family]))
            roles.update(role.role_id for role in schema.roles)
    return FeatureSchema(
        tuple(sorted(roles)), tuple(sorted(schemas)),
        source_bindings=tuple(sorted(bindings)))


@unittest.skipUnless(ARTIFACT, 'real pinned A01 artifact not mounted')
class RealTrainingAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[5]
        source = root / 'vendor/legacy-v16'
        graph = read_sources(source)[2]
        course = initial_course(accepted_grade_a(json.loads((root / 'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json').read_text())))
        curriculum, bindings = from_legacy_course(course)
        registry, answers = live_source_registry(), live_answer_registry()
        release = compile_executable_factory_release(curriculum, bindings, CurriculumProfile.full(),
            registry, answers, source_root=source, graph=graph, verification_seed=31)
        cls.context = SourceExecutionContext(release, graph, source, registry, answers)
        cls.rows = tuple(cls.context.draw_rows(seed=31, capability='A.IDENTITY', each=2))
        cls.row = cls.rows[0]
        cls.source_authority = cls.context.bind_rows(
            cls.rows, seed=31, capability='A.IDENTITY', each=2)
        cls.selection = AtlasArtifactSelection(ARTIFACT,
            '5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7',
            '58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306',
            'f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec')
        snapshot = load_pinned_atlas_snapshot(cls.selection)
        cls.snapshot = snapshot
        end = len(cls.row['tokens'])
        task = TaskScope('p', 't', 'TRAINING', snapshot.release_sha256, 'r', 's', 3, 5, end)
        policy = ContextPolicy('p', 1, 1, ('TRAINING',), (PUBLIC_FORMAL,), ('r',), ('s',),
            (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
            tuple((PUBLIC_FORMAL,) * count for count in range(3, 25)))
        adapter = registry.require('bilqis_mlx.grade_a_probe.make_record', A_ORACLE)
        frontier = SourceFrontier(1, 1, ())
        ast_by_tokens, projection_by_source = {}, {}
        frames = ()
        for row in cls.rows:
            projection, frontier = public_formal_context(
                adapter, row, snapshot, source_root=source, graph=graph,
                task_scope=task, source_frontier=frontier, policy=policy,
                source_seed=31, source_each=2)
            tree = bind_registered_source_row(
                adapter, row, snapshot, source_root=source, graph=graph,
                source_span=SourceSpan(0, len(row['tokens'])),
                causal_prefix_end=len(row['tokens']))
            source_id = tree.root.source_instance_id
            atoms = tuple(SourceAtom(i, graph['tokens'][token], f'{source_id}#atom:{i}')
                          for i, token in enumerate(row['tokens']))
            ast = StreamingAST(source_id, atoms, (tree,))
            grants = tuple(SourceGrant(atom.source_reference, 'p', 't', PUBLIC_FORMAL,
                snapshot.release_sha256,
                atom_evidence_digest(source_id, atom, snapshot.release_sha256),
                ('TRAINING',), ('r',), ('s',), 1, 1, 0, 0) for atom in atoms)
            frontier = replace(frontier, grants=tuple(sorted(
                {*frontier.grants, *grants}, key=lambda item: item.source_handle)))
            ast_by_tokens[tuple(row['tokens'])] = ast
            projection_by_source[source_id] = projection
            if row is cls.row:
                frames = tuple(item for item in projection.envelopes
                               if type(item.frame) is FrameInstance)
        schema_ids = tuple(sorted({item.frame.frame_schema_id for item in frames}))
        roles = tuple(sorted({binding.role_id for item in frames for binding in item.frame.bindings}))
        cls.row_feature_schema = FeatureSchema(roles, schema_ids, source_bindings=tuple(
            (schema_id, adapter.descriptor.adapter_id) for schema_id in schema_ids))
        cls.features = build_feature_manifest(snapshot, _canonical_feature_schema(cls.selection))
        cls._feature_root = TemporaryDirectory()
        cls.feature_receipt = persist_feature_manifest(cls.features, cls._feature_root.name)
        cls.real_frame = frames[0].frame
        cls.real_scope = frames[0].scope
        manifest = _load_pinned_released_frame_schemas('micro', cls.selection).manifest
        cls.config = FrameCompilerConfig(tuple(body.parse() for body in manifest.bodies),
            manifest.schema_map, None, task, frontier, policy)
        cls.args = dict(delivery=describe_delivered_teaching(
                release, 'A.IDENTITY', 'source.direct/A.IDENTITY', cls.rows),
            delivery_capability='A.IDENTITY', delivery_release_sha256=release.release_sha256,
            teacher_strategy={}, requested_count=2, optimizer_step_seed=1, rehearsal_by_id={},
            visit_provenance=visit_provenance('A.IDENTITY'),
            source_authority=cls.source_authority,
            visible_ends={row['id']: len(row['tokens']) for row in cls.rows},
            source_ast_for=lambda tokens: ast_by_tokens[tuple(tokens)],
            answer_plan_for=lambda *args: answer_plan_for(*args),
            frames_for_ast=lambda ast: projection_by_source[ast.source_instance_id].envelopes,
            task_scope=task, source_frontier=frontier, eligibility_policy=policy,
            generation_binding=release.release_sha256, atlas_selection=cls.selection,
            feature_artifact_path=cls.feature_receipt.path)

    @classmethod
    def tearDownClass(cls):
        cls._feature_root.cleanup()

    def compile(self, config):
        return compile_training_batch(self.rows, self.context, ModelTopologySpecV2(),
            compiler_config=config, **self.args)

    def test_real_row_accepts_canonical_and_rejects_noncanonical_a05(self):
        batch = self.compile(self.config)
        self.assertTrue(batch.rows[0].model_input.features)
        self.assertTrue(all(row.source_status == 'ADMITTED_FORMAL_ABI_UNTYPED'
                            and row.type_ids for row in batch.rows[0].model_input.features))
        entries = self.config.schema_map.entries
        swapped = tuple(sorted((replace(entries[0], tag=entries[1].tag),
                                replace(entries[1], tag=entries[0].tag), *entries[2:])))
        with self.assertRaises(BilqisError):
            self.compile(replace(self.config, schema_map=replace(self.config.schema_map, entries=swapped)))

    def test_formal_owner_rejects_even_when_failure_callback_returns(self):
        binding = next(item for item in self.real_frame.bindings if item.concept is not None)
        with self.assertRaises(BilqisError):
            source_qualified_feature_row(self.features, binding.concept, binding.role_id,
                self.real_frame, self.real_scope, None, invalid=lambda: None)

    def test_caller_selected_source_valid_feature_schema_cannot_enter_batch(self):
        pinned = _load_pinned_released_frame_schemas('micro', self.selection).manifest
        extra = next(body.parse() for body in pinned.bodies
                     if body.schema_id not in self.row_feature_schema.schema_ids)
        adapter_id = self.row_feature_schema.source_bindings[0][1]
        alternate_schema = FeatureSchema(
            tuple(sorted({*self.row_feature_schema.role_ids,
                          *(role.role_id for role in extra.roles)})),
            tuple(sorted((*self.row_feature_schema.schema_ids, extra.schema_id))),
            source_bindings=tuple(sorted((*self.row_feature_schema.source_bindings,
                                          (extra.schema_id, adapter_id)))))
        alternate_features = build_feature_manifest(self.snapshot, alternate_schema)
        self.assertEqual(alternate_features.semantic_release, self.features.semantic_release)
        self.assertNotEqual(alternate_features.digest, self.features.digest)
        with self.assertRaises(TypeError):
            compile_training_batch((self.row,), self.context, ModelTopologySpecV2(),
                compiler_config=self.config, atlas_features=alternate_features,
                feature_schema=alternate_schema, **self.args)

    def test_alternate_source_valid_feature_artifact_rejected_before_model_input(self):
        pinned = _load_pinned_released_frame_schemas('micro', self.selection).manifest
        extra = next(body.parse() for body in pinned.bodies
                     if body.schema_id not in self.row_feature_schema.schema_ids)
        adapter_id = self.row_feature_schema.source_bindings[0][1]
        alternate_schema = FeatureSchema(
            tuple(sorted({*self.row_feature_schema.role_ids,
                          *(role.role_id for role in extra.roles)})),
            tuple(sorted((*self.row_feature_schema.schema_ids, extra.schema_id))),
            source_bindings=tuple(sorted((*self.row_feature_schema.source_bindings,
                                          (extra.schema_id, adapter_id)))))
        alternate_features = build_feature_manifest(self.snapshot, alternate_schema)
        self.assertEqual(alternate_features.semantic_release, self.features.semantic_release)
        self.assertEqual(alternate_features.atlas_bundle_id, self.features.atlas_bundle_id)
        self.assertEqual(alternate_features.source_bundle_id, self.features.source_bundle_id)
        self.assertNotEqual(alternate_features.digest, self.features.digest)
        with TemporaryDirectory() as root:
            alternate = persist_feature_manifest(alternate_features, root)
            def model_input_planning_entered(*_args):
                raise AssertionError('model-input planning entered before A06 authority rejection')
            args = {
                **self.args,
                'feature_artifact_path': alternate.path,
                'answer_plan_for': model_input_planning_entered,
            }
            with self.assertRaises(BilqisError):
                compile_training_batch(self.rows, self.context, ModelTopologySpecV2(),
                    compiler_config=self.config, **args)
