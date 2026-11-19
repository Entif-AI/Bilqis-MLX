"""Source-qualified fixture assembly for the #1300 integrated witness."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.compatibility.executable_projection import LIVE_V2_VERIFICATION_SEED
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
from bilqis_mlx.factory.skos_curriculum import issue_source_context_transition_authority
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.runtime.atlas_admission import (
    AtlasSourceApproval,
    ResourceCeilingV2,
    _accepted_run_lease_identity,
    issue_atlas_lease_v2,
)
from bilqis_mlx.runtime.grade_certification_authority import (
    historical_mean_stability_policy,
)
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityRegistry,
    SourceAuthorityScope,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _REGISTRY
from bilqis_mlx.runtime.tests.admission.atlas.v2 import (
    mixed_source_support as mixed_support,
)
from bilqis_mlx.runtime.tests.admission.atlas.v2.atlas_flywheel_human_resume_support import (
    AcceptedAtlasFlywheelHumanResumeSupport,
)
from bilqis_mlx.runtime.tests.operator.pre_neural_journey_support import (
    AUTHORIZED_ATLAS,
    COPULAR_REGISTRY,
    journey_source,
)
from bilqis_mlx.semantics.tests.frame_adapters.helpers import (
    _snapshot as accepted_abi_snapshot,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.source_adapters import event_frames
from .constants import SUCCESSOR, TARGET

CONFORMANCE_1300_REGISTRY = SourceAuthorityRegistry((
    replace(
        _REGISTRY.keys[0],
        allowed_scopes=tuple(sorted(
            (
                *_REGISTRY.keys[0].allowed_scopes,
                SourceAuthorityScope(
                    DependencyKind.ARTIFACT,
                    "salience-event:",
                ),
            ),
            key=lambda scope: (scope.kind.value, scope.key_prefix),
        )),
    ),
))


class Conformance1300FixtureSupport(AcceptedAtlasFlywheelHumanResumeSupport):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        profile = CurriculumProfile(
            "conformance-1300/a-identity-foundation",
            grades=(
                GradeProfile("A", enabled_capabilities=("A.IDENTITY",)),
                GradeProfile("B", enabled_capabilities=()),
                GradeProfile("C", enabled_capabilities=()),
            ),
        )
        cls.current = compile_executable_factory_release(
            cls.current.curriculum,
            cls.current.source_bindings,
            profile,
            cls.source_registry,
            cls.answer_registry,
            source_root=mixed_support.LEGACY,
            graph=cls.parent_graph,
            verification_seed=LIVE_V2_VERIFICATION_SEED,
        )

    def issue_mixed_lease(
        self,
        h1,
        event_candidate,
        snapshot,
        event_capabilities=(TARGET,),
    ):
        """Issue the disposable lease with the repository's implemented grade policy."""
        event_operators = {
            event_frames.SYMBOLS[capability] for capability in event_capabilities
        }
        approval = _signed(
            replace(
                AtlasSourceApproval(
                    "mixed-v2-witness-approval",
                    snapshot.release_sha256,
                    tuple(
                        sorted(
                            set(h1.family_ids)
                            | set(event_candidate.census.required_source_family_ids)
                        )
                    ),
                    tuple(sorted(set(h1.operator_ids) | event_operators)),
                    "b" * 64,
                    1,
                    "c" * 64,
                    historical_mean_stability_policy().policy_sha256,
                    "e" * 64,
                    True,
                    True,
                    "fixture:salience-owner",
                    "0" * 128,
                ),
                signature_hex="0" * 128,
            )
        )
        lease = issue_atlas_lease_v2(
            "mixed-v2-witness-lease",
            _accepted_run_lease_identity(self.run),
            approval,
            ResourceCeilingV2(8, 8, 65536, 1 << 44, 1 << 44),
            requested_at="2026-11-10T20:45:00Z",
            human_command_sha256="9" * 64,
            human_started=True,
            registry=CONFORMANCE_1300_REGISTRY,
        )
        # Keep generation zero in the staged admission epoch. Production C11
        # publishes this prepared scope only after the newborn grade bootstrap
        # and first retained foundation visit have completed.
        return approval, lease, None

    @staticmethod
    def host_registry():
        return patch(
            "bilqis_mlx.runtime.bamf_bundle.source_authority_custody."
            "read_host_system_source_authority_registry",
            return_value=CONFORMANCE_1300_REGISTRY,
        )

    def _production_parameter_fixture(self):
        staged_seed = self.zero_id_stage()
        seed_handoff, _seed_plan, _seed_learner = self.capability_handoff(staged_seed)
        fixture = self._source_fixture()
        self.publish_matching_genesis(
            fixture.snapshot, fixture.schema, fixture.features)
        _approval, lease, _source_authority = self.issue_mixed_lease(
            seed_handoff,
            fixture.event_candidate,
            fixture.snapshot,
            event_capabilities=(TARGET, SUCCESSOR),
        )
        return SimpleNamespace(**vars(fixture), lease=lease)

    def _source_fixture(self):
        """Rebuild the deterministic source world without touching run custody."""
        snapshot, event_candidate, schema, features = self.common_atlas()
        selection = mixed_support.AtlasArtifactSelection(
            "/artifact",
            snapshot.bundle_id,
            snapshot.release_sha256,
            snapshot.source_bundle_id,
        )
        combined = self.combined_source_registry()
        source_ids = tuple(
            event_frames.atlas_semantic_id(capability)
            for capability in (TARGET, SUCCESSOR)
        )
        source_nt = b"".join(
            f'<{semantic_id}> <http://www.w3.org/2004/02/skos/core#definition> '
            f'"c07 proof semantic role"@en .\n'.encode("utf-8")
            for semantic_id in source_ids
        )
        return SimpleNamespace(
            snapshot=snapshot,
            event_candidate=event_candidate,
            schema=schema,
            features=features,
            selection=selection,
            source_authority=issue_source_context_transition_authority(selection),
            combined=combined,
            source_nt=source_nt,
        )

    def common_atlas(self):
        """Expose two source-known D semantics; C07 still admits them one at a time."""
        base = accepted_abi_snapshot()
        definitions = tuple(
            (
                event_frames.atlas_semantic_id(capability),
                (
                    "lexicon",
                    "lexicon_root_senses",
                    event_frames.SOURCE_SPECS[capability].sense_id,
                ),
                None,
            )
            for capability in (TARGET, SUCCESSOR)
        )
        source = mixed_support.source_atlas_snapshot(definitions)
        offset = len(base.abi_entries)
        appended_entries = tuple(
            replace(entry, index=offset + index, row=offset + index)
            for index, entry in enumerate(source.abi_entries)
        )
        concepts_by_semantic = {
            item.concept.semantic_id: item for item in source.concepts
        }
        appended_concepts = tuple(
            replace(
                concepts_by_semantic[entry.semantic_id],
                # A02 adds identity rows, not categorical factor-table rows;
                # keep disposable proof semantics source-qualified but untyped.
                concept=replace(
                    concepts_by_semantic[entry.semantic_id].concept,
                    types=(),
                ),
                abi_index=entry.index,
                abi_row=entry.row,
            )
            for entry in appended_entries
        )
        entries = (*base.abi_entries, *appended_entries)
        active_indices = [item.index for item in entries if item.active]
        counts = replace(
            base.counts,
            source_rows=len(appended_entries),
            rdf_terms=len(appended_entries),
            semantic_concepts=len(appended_concepts),
            abi_entries=len(entries),
            implementation_uncovered=len(appended_entries),
        )
        snapshot = replace(
            base,
            bundle_id=AUTHORIZED_ATLAS[0],
            release_sha256=AUTHORIZED_ATLAS[1],
            source_bundle_id=AUTHORIZED_ATLAS[2],
            prior_abi_sha256=hashlib.sha256(COPULAR_REGISTRY.read_bytes()).hexdigest(),
            shape_policy_sha256=mixed_support._atlas_sha256(
                mixed_support._atlas_bytes(mixed_support.SHAPE_POLICY)
            ),
            active_set_sha256=mixed_support._atlas_sha256(
                mixed_support._atlas_bytes(active_indices)
            ),
            counts=counts,
            abi_entries=entries,
            concepts=appended_concepts,
            semantic_lookup=tuple(
                sorted(
                    (
                        *base.semantic_lookup,
                        *((entry.semantic_id, entry.index) for entry in appended_entries),
                    )
                )
            ),
            concept_lookup=tuple(
                (concept.concept.semantic_id, index)
                for index, concept in enumerate(appended_concepts)
            ),
        )
        candidate = mixed_support._compile_semantic_curriculum_snapshot(
            snapshot,
            mixed_support.SOURCE_FAMILY_ADAPTERS,
            mixed_support.LearnedFrontier(snapshot.release_sha256),
        )
        schema, features, _selection = journey_source(snapshot)
        return snapshot, candidate, schema, features

