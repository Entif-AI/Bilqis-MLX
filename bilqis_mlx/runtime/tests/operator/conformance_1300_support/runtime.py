"""Admission/operator helpers for the #1300 integrated witness."""
from __future__ import annotations

import hashlib
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.compatibility.legacy_trainer_authority import authority_record
from bilqis_mlx.factory.autonomy import (
    EvidenceReceipt,
    obligations_for_capability,
    record_evidence,
)
from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_flywheel_runtime import run_accepted_atlas_flywheel
from bilqis_mlx.runtime.autonomy_state import persist_autonomy_state
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.priority_source_offer import PreparedPrioritySourceOffer
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import (
    selection_teacher,
)

from .fixtures import Conformance1300FixtureSupport, TARGET
from .lifecycle import enroll_prepared_lease


def _record_fixture_evidence_once(release, ledger, receipt, *, plan, checkpoint, step):
    """Make disposable #1300 predecessor credit convergent at one checkpoint."""
    existing = next(
        (item for item in ledger.receipts if item.evidence_id == receipt.evidence_id),
        None,
    )
    if existing is not None:
        if existing != receipt:
            raise ValueError("CONFORMANCE_1300_FIXTURE_EVIDENCE_ID_COLLISION")
        return ledger
    return record_evidence(
        release,
        ledger,
        receipt,
        plan=plan,
        current_checkpoint_sha256=checkpoint,
        current_optimizer_step=step,
    )


class Conformance1300RuntimeSupport(Conformance1300FixtureSupport):
    def _production_parameter_context(self, fixture):
        """Virtualize files/resources while retaining production semantic owners."""
        stack = ExitStack()
        stack.enter_context(self.source_replay(
            fixture.snapshot, fixture.schema, fixture.features))
        patches = (
            (
                "bilqis_mlx.runtime.atlas_flywheel_runtime."
                "resolve_atlas_artifact_selection",
                fixture.selection),
            (
                "bilqis_mlx.factory.skos_curriculum.curriculum._load_pinned",
                fixture.snapshot),
            (
                "bilqis_mlx.runtime.atlas_flywheel_runtime.live_source_registry",
                fixture.combined),
            (
                "bilqis_mlx.runtime.atlas_flywheel_runtime.live_answer_registry",
                self.answer_registry),
            (
                "bilqis_mlx.source_adapters.school.live_source_registry",
                fixture.combined),
            (
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                self.answer_registry,
            ),
            (
                "bilqis_mlx.runtime.bamf_bundle.vocabulary.admission."
                "resolve_atlas_source_bundle",
                Path("/source"),
            ),
        )
        for target, value in patches:
            stack.enter_context(patch(target, return_value=value))
        for target in (
            "bilqis_mlx.runtime.bamf_bundle.feature_authority.load_pinned_atlas_snapshot",
            "bilqis_mlx.runtime.bamf_bundle.vocabulary.admission.load_pinned_atlas_snapshot",
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            "bilqis_mlx.semantics.atlas.vocabulary_resources.load_pinned_atlas_snapshot",
            "bilqis_mlx.source_adapters.atoms.admission.load_pinned_atlas_snapshot",
        ):
            stack.enter_context(patch(target, return_value=fixture.snapshot))
        stack.enter_context(patch(
            "bilqis_mlx.semantics.atlas.vocabulary_resources._verify_bundle",
            return_value=(fixture.snapshot.source_bundle_id,
                          {"canonical.nt": fixture.source_nt}),
        ))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.vocabulary.admission.shutil.disk_usage",
            return_value=SimpleNamespace(free=1 << 50),
        ))
        stack.enter_context(patch("bilqis_mlx.runtime.mlx_checkpoint.assert_headroom"))
        return stack

    def _admit_target(self, supervisor, fixture):
        # #1411 makes the accepted v2 lease part of the foundation identity
        # authority.  Credit evidence only after the production enrollment
        # owner has accepted that exact lease for this disposable lineage.
        with self.host_registry():
            enrolled = enroll_prepared_lease(
                self.run,
                fixture.lease,
                source_authority=AcceptedRuntimeHost(self.run).source_authority(),
            )
        self.assertEqual(enrolled.digest(), fixture.lease.digest())
        self._credit_identity_prerequisites(supervisor)
        parent = load_accepted_generation(self.run)
        parent_release = read_accepted_atlas_factory_release(self.run)
        first = run_accepted_atlas_flywheel(
            self.run,
            self.parent_graph,
            reserve_gib=0.0,
            max_advances=1,
        )
        self.assertEqual(first.advances, 1)
        admitted = load_accepted_generation(self.run)
        admitted_release = read_accepted_atlas_factory_release(self.run)
        self.assertNotEqual(
            admitted_release.release_sha256,
            parent_release.release_sha256,
        )
        self.assertIn(TARGET, admitted_release.execution_plan.capability_map)
        self.assertEqual(
            admitted.retained_state.optimizer_step,
            parent.retained_state.optimizer_step,
        )
        self.assertEqual(admitted.baseline_evidence, parent.baseline_evidence)
        return parent, parent_release, admitted, admitted_release

    def _activate_current_generated_grade(self):
        from bilqis_mlx.runtime.active_generated_grade import (
            ensure_active_generated_grade,
        )

        return ensure_active_generated_grade(self.run)

    def _credit_all_predecessor_learning(self, supervisor, *, exclude=(TARGET,)):
        """Fixture-credit admitted predecessors at the post-C07 checkpoint only."""
        state = supervisor.load_state()
        ledger = state.learner_evidence.ledger
        checkpoint = state.learner_evidence.checkpoint_sha256
        step = state.learner_evidence.optimizer_step
        index = 0
        for capability in state.epoch.current_release.execution_plan.capabilities:
            if capability.capability_id in set(exclude):
                continue
            for obligation in obligations_for_capability(
                state.epoch.current_release,
                capability.capability_id,
                plan=state.plan,
            ):
                index += 1
                identity = hashlib.sha256(
                    (
                        f"1300-predecessor:{checkpoint}:{step}:"
                        f"{obligation.obligation_id}"
                    ).encode()
                ).hexdigest()
                ledger = _record_fixture_evidence_once(
                    state.epoch.current_release,
                    ledger,
                    EvidenceReceipt(
                        obligation.obligation_id,
                        f"1300-predecessor-{identity}",
                        checkpoint,
                        step,
                        hashlib.sha256(
                            (
                                f"1300-predecessor-cohort:{checkpoint}:{step}:"
                                f"{obligation.obligation_id}:{index}"
                            ).encode()
                        ).hexdigest(),
                        obligation.minimum_specimens,
                        True,
                    ),
                    plan=state.plan,
                    checkpoint=checkpoint,
                    step=step,
                )
        persist_autonomy_state(
            self.run,
            state.epoch.current_release,
            plan=state.plan,
            ledger=ledger,
        )

    def _operator_context(self, fixture, *, teacher=None):
        stack = self._production_parameter_context(fixture)
        stack.enter_context(
            patch(
                "bilqis_mlx.runtime.bamf_operator.session_support.shutil.disk_usage",
                return_value=SimpleNamespace(
                    total=1 << 50,
                    used=1 << 30,
                    free=(1 << 50) - (1 << 30),
                ),
            )
        )
        # C03/A09 and C07 must consume the same complete source-qualified
        # curriculum. Active-grade and learner-evidence owners, not fixture
        # slicing, decide which source-known semantic is currently teachable.
        stack.enter_context(
            patch(
                "bilqis_mlx.runtime.foundation_teacher_owner.live_authority",
                return_value=(
                    authority_record(),
                    "d" * 40,
                    {"teacher": selection_teacher() if teacher is None else teacher},
                ),
            )
        )
        from bilqis_mlx.learning.tests import test_atlas_salience as salience_fixture

        class FixtureSourceAuthoritySigner:
            def __init__(self, registry):
                authority = registry.keys[0]
                self.owner_id = authority.owner_id
                self.public_key_hex = authority.public_key_hex
                self._registry = registry

            def sign(self, dependency, payload):
                self._registry.require_claimed_authority(
                    self.owner_id,
                    dependency,
                    self.public_key_hex,
                )
                return salience_fixture._KEY.sign(payload).hex()

        stack.enter_context(
            patch(
                "bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer."
                "read_host_system_source_authority_signer",
                side_effect=FixtureSourceAuthoritySigner,
            )
        )
        original_require_current = PreparedPrioritySourceOffer.require_current

        def require_current_or_explain(offer, source_context, parent, **kwargs):
            try:
                return original_require_current(
                    offer,
                    source_context,
                    parent,
                    **kwargs,
                )
            except ValueError as error:
                raise RuntimeError(
                    "1300_SOURCE_OFFER_VALUE_ERROR:" + str(error)
                ) from error

        stack.enter_context(
            patch.object(
                PreparedPrioritySourceOffer,
                "require_current",
                require_current_or_explain,
            )
        )
        for target in (
            "bilqis_mlx.factory.skos_curriculum.load_pinned_atlas_snapshot",
            "bilqis_mlx.semantics.atlas.feature_io_pins.load_pinned_atlas_snapshot",
            "bilqis_mlx.semantics.atlas_features.formal.load_pinned_atlas_snapshot",
            "bilqis_mlx.semantics.released_frame_schemas.load_pinned_atlas_snapshot",
            "bilqis_mlx.source_adapters.atoms.admission.load_pinned_atlas_snapshot",
            "bilqis_mlx.source_adapters.atom_binding.load_pinned_atlas_snapshot",
            "bilqis_mlx.learning.atlas_engram_source_context.load_pinned_atlas_snapshot",
            "bilqis_mlx.learning.source_atoms.embedding.load_pinned_atlas_snapshot",
            "bilqis_mlx.runtime.batch_training_authority.load_pinned_atlas_snapshot",
        ):
            stack.enter_context(patch(target, return_value=fixture.snapshot))
        return stack
