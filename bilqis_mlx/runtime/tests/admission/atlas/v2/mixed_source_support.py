"""A09/source construction support for mixed v2 admission witnesses."""
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import replace
import hashlib
from unittest.mock import patch

import numpy as np

from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.atlas_frontier import (
    AtlasCoverageEpoch, AtlasLearnerEvidence, bind_realized_snapshot,
    next_atlas_delta,
)
from bilqis_mlx.factory.atlas_frontier_closure import resolve_frontier_closure
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.candidate_staging import (
    candidate_source_anchor, compile_candidate_successor,
)
from bilqis_mlx.factory.curriculum_definition import (
    CurriculumDefinition, SourceBindingSet, from_legacy_course,
)
from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
from bilqis_mlx.factory.skos_curriculum import (
    SOURCE_FAMILY_ADAPTERS, LearnedFrontier, _compile_semantic_curriculum_snapshot,
)
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate, _closure, _snapshot,
)
from bilqis_mlx.factory.tests.events.support import EventCandidateRealizationFixture, LEGACY
from bilqis_mlx.factory.tests.sources.test_skos_curriculum import _snapshot as source_atlas_snapshot
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_course
from bilqis_mlx.runtime.bamf_bundle.genesis import foundation as genesis_foundation
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _REGISTRY
from bilqis_mlx.semantics.atlas_projection import (
    SHAPE_POLICY,
    _canonical_bytes as _atlas_bytes,
    _digest as _atlas_sha256,
)
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.source_adapters import event_frames
from bilqis_mlx.source_adapters.formal_identity import (
    OperatorDispositionKind, SourceOperatorDisposition,
)


class MixedSourceSupport(EventCandidateRealizationFixture):
    @staticmethod
    def z_operator_authority(staged):
        execution = staged.successor.execution_plan.capability_map["Z.C6"]
        descriptor = next(
            item for item in staged.successor.source_adapters
            if item.adapter_id == execution.provider_id)
        disposition = SourceOperatorDisposition(
            capability_id="Z.C6", source_adapter_id=descriptor.adapter_id,
            kind=OperatorDispositionKind.NON_OPERATOR, operator_id=None,
            semantic_root=None, generator_id=descriptor.generator_id,
            accepted_oracle_ids=descriptor.accepted_oracle_ids,
            implementation_sha256=descriptor.implementation_sha256)
        return patch(
            "bilqis_mlx.factory.atlas_delta_scope.source_operator_disposition",
            return_value=disposition)

    def combined_source_registry(self):
        return SourceAdapterRegistry((
            *self.source_registry._by_generator.values(),
            *self.z.staging.fixture.fixture.registry._by_generator.values(),
        ))

    def zero_id_stage(self):
        selected = self.z.frontier.candidates[0]
        z_curriculum, z_bindings = from_legacy_course(_synthetic_course(7))
        z6 = replace(
            z_bindings.by_capability["Z.C6"],
            source_anchor=candidate_source_anchor(self.z.frontier, selected.candidate_id),
        )
        bindings = SourceBindingSet((
            *self.current.source_bindings.bindings,
            *(z6 if item.capability_id == "Z.C6" else item
              for item in z_bindings.bindings),
        ))
        curriculum = CurriculumDefinition(
            "mixed-event-z/v1", (*self.current.curriculum.grades, *z_curriculum.grades),
            program_complete=False)
        profile = CurriculumProfile(
            "event-plus-zc6",
            grades=(*self.current.profile.grades,
                    GradeProfile("Z", enabled_capabilities=("Z.C6",))))
        return compile_candidate_successor(
            self.z.frontier, self.current, selected.candidate_id,
            curriculum=curriculum, source_bindings=bindings, profile=profile,
            source_registry=self.combined_source_registry(),
            answer_registry=self.answer_registry, source_root=LEGACY,
            graph=self.parent_graph, verification_seed=20261110)

    def capability_handoff(self, staged):
        snapshot = rehash(
            _snapshot(self.current),
            candidate_frontier_sha256=self.z.frontier.release_sha256,
            staged_factory_release_sha256s=(staged.successor.release_sha256,))
        closure = _closure(snapshot, tuple(
            _candidate(snapshot, identity)
            for identity in snapshot.source_eligible_concept_ids))
        plan = compile_autonomy_plan(self.current)
        learner = AtlasLearnerEvidence(
            initial_evidence_ledger(self.current, plan=plan), "e" * 64, 0)
        def authority(semantic_id, current):
            if current.release_sha256 != self.current.release_sha256 or semantic_id != "z.op.0":
                raise ValueError
            return (staged.successor.transition.added_capabilities, ())

        with patch(
                "bilqis_mlx.factory.candidate_realizations.project_realized_target",
                side_effect=authority), patch(
                    "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
                    side_effect=authority), patch(
                    "bilqis_mlx.factory.candidate_realizations.realized_source_sense_id",
                    return_value=staged.source_sense_id), self.z_operator_authority(staged):
            handoff = next_atlas_delta(
                AtlasCoverageEpoch(
                    snapshot, closure, self.z.frontier, self.current, (staged,), None),
                learner, plan)
            handoff.verify()
        return handoff, plan, learner

    def common_atlas(self):
        definitions = [
            ("urn:formal:boolean:AND", None, None),
            ("urn:formal:numeric:ADD", None, None),
            *((event_frames.atlas_semantic_id(capability),
               ("lexicon", "lexicon_root_senses", spec.sense_id), None)
              for capability, spec in event_frames.SOURCE_SPECS.items()),
        ]
        snapshot = source_atlas_snapshot(tuple(definitions))
        target_semantic_id = event_frames.atlas_semantic_id("D.EVENT_OCCURRENCE")
        # A02 may add identity rows, not grow the accepted feature-factor tables.
        # Keep this prospective source identity untyped so the mixed witness tests
        # parameter extension rather than an unsupported factor-table extension.
        concepts = tuple(
            replace(
                item,
                concept=replace(item.concept, types=()),
            ) if item.concept.semantic_id == target_semantic_id else item
            for item in snapshot.concepts
        )
        active_indices = [entry.index for entry in snapshot.abi_entries if entry.active]
        snapshot = replace(
            snapshot,
            concepts=concepts,
            shape_policy_sha256=_atlas_sha256(_atlas_bytes(SHAPE_POLICY)),
            active_set_sha256=_atlas_sha256(_atlas_bytes(active_indices)),
        )
        candidate = _compile_semantic_curriculum_snapshot(
            snapshot, SOURCE_FAMILY_ADAPTERS, LearnedFrontier(snapshot.release_sha256))
        schema = FeatureSchema((), ())
        return snapshot, candidate, schema, build_feature_manifest(snapshot, schema)

    def source_replay(self, snapshot, schema, features):
        stack = ExitStack()
        selection = AtlasArtifactSelection(
            "/artifact", snapshot.bundle_id, snapshot.release_sha256,
            snapshot.source_bundle_id)
        stack.enter_context(patch.multiple(
            genesis_foundation,
            _source_owned_feature_schema=lambda _selection: (snapshot, schema),
            build_feature_manifest=lambda _snapshot, _schema: features))
        for target, value in (
                ("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                 "resolve_atlas_artifact_selection", selection),
                ("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                 "load_pinned_atlas_snapshot", snapshot),
                ("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                 "build_feature_manifest", features),
                ("bilqis_mlx.semantics.atlas.snapshot."
                 "resolve_atlas_artifact_selection", selection),
                ("bilqis_mlx.semantics.atlas.snapshot."
                 "load_pinned_atlas_snapshot", snapshot)):
            stack.enter_context(patch(target, return_value=value))
        stack.enter_context(self.host_registry())
        return stack

    @staticmethod
    def host_registry():
        return patch(
            "bilqis_mlx.runtime.bamf_bundle.source_authority_custody."
            "read_host_system_source_authority_registry", return_value=_REGISTRY)

    def run_fingerprint(self):
        rows = []
        for path in sorted(self.run.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            rows.append((
                str(path.relative_to(self.run)),
                hashlib.sha256(path.read_bytes()).hexdigest(),
                stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino,
            ))
        return tuple(rows)

    @staticmethod
    def neural_fingerprint(student):
        from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
        return (
            student.retained_state.optimizer_step,
            student.extents.digest,
            candidate_identity_digest(student.retained_state),
        )

    @staticmethod
    def assert_tree_prefix(
            test_case, parent, child, *, mutable_rows_by_key=None,
            mutable_rows=()):
        if isinstance(parent, Mapping):
            test_case.assertIsInstance(child, Mapping)
            test_case.assertEqual(set(child), set(parent))
            for key in parent:
                MixedSourceSupport.assert_tree_prefix(
                    test_case, parent[key], child[key],
                    mutable_rows=(
                        () if mutable_rows_by_key is None
                        else mutable_rows_by_key.get(key, ())))
            return
        before, after = np.asarray(parent), np.asarray(child)
        test_case.assertEqual(after.dtype, before.dtype)
        test_case.assertEqual(after.ndim, before.ndim)
        test_case.assertTrue(
            all(new >= old for old, new in zip(before.shape, after.shape)))
        prefix = tuple(slice(0, size) for size in before.shape)
        if mutable_rows:
            test_case.assertGreater(before.ndim, 0)
            rows = tuple(sorted(set(mutable_rows)))
            test_case.assertEqual(rows, tuple(mutable_rows))
            test_case.assertTrue(all(0 <= row < before.shape[0] for row in rows))
            stable_rows = np.array(
                [row for row in range(before.shape[0]) if row not in rows],
                dtype=np.intp)
            if stable_rows.size:
                child_prefix = (stable_rows, *prefix[1:])
                np.testing.assert_array_equal(
                    after[child_prefix], before[stable_rows])
            return
        np.testing.assert_array_equal(after[prefix], before)

    def event_handoff(
            self, current_release, *, capability="D.EVENT_OCCURRENCE",
            mastered=None, graph=None):
        candidate, source_frontier, policy = self.atlas_fixture()
        semantic_id = event_frames.atlas_semantic_id(capability)
        current_graph = self.parent_graph if graph is None else graph
        staged = candidate_realizations.prepare_realized_candidate(
            self.frontier, current_release, current_graph, semantic_id,
            source_root=LEGACY, source_registry=self.combined_source_registry(),
            answer_registry=self.answer_registry)
        snapshot = self.build_snapshot(
            candidate, source_frontier, policy, current_release, staged)
        snapshot = bind_realized_snapshot(
            snapshot, candidate, self.frontier, current_release, (staged,))
        plan, checkpoint_sha256, step, ledger, learner = self.learner_evidence(
            current_release, {"A.IDENTITY"} if mastered is None else set(mastered),
            capability)
        closure = resolve_frontier_closure(
            snapshot, candidate.census, current_release=current_release,
            evidence_ledger=ledger, autonomy_plan=plan,
            checkpoint_sha256=checkpoint_sha256, optimizer_step=step)
        handoff = next_atlas_delta(
            AtlasCoverageEpoch(
                snapshot, closure, self.frontier, current_release, (staged,), None),
            learner, plan)
        handoff.verify()
        return semantic_id, handoff, plan, ledger, checkpoint_sha256, step
