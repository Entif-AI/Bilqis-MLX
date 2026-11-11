"""Capability-only Atlas v2 adoption and retry tests."""

from contextlib import ExitStack, nullcontext

from bilqis_mlx.runtime.tests.admission.atlas.v2.capability_support import *
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime


class CapabilityPublicationV2Tests(CapabilityV2Support):
    def _publication_stack(
            self, handoff, lease, pure, parent, transition, candidate, binding,
            pointer, parent_pointer, *, last_parent_pointer=None):
        successor = handoff.staged_candidate.successor.release_sha256
        predecessor = handoff.receipt.predecessor_release.release_sha256
        stack = ExitStack()
        lease_guard = stack.enter_context(patch(
            "bilqis_mlx.runtime.atlas_admission."
            "_hold_current_atlas_lease_v2_publication",
            return_value=nullcontext()))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease_v2",
            return_value=lease))
        issue_transition = stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.factory_release_adoption."
            "_issue_factory_release_adoption_transition", return_value=transition))
        derive = stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.factory_release_adoption."
            "derive_factory_release_adoption_candidate", return_value=candidate))
        issue_binding = stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.factory_release.admission."
            "_issue_factory_release_admission_binding", return_value=binding))
        persist = stack.enter_context(patch(
            "bilqis_mlx.runtime.admission._persist_executable_factory_release",
            return_value="factory-releases/" + successor + ".json"))
        publish = stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.publication."
            "publish_factory_release_adoption_generation", return_value=pointer))
        factory_release = stack.enter_context(patch(
            "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
            side_effect=[SimpleNamespace(release_sha256=predecessor),
                         SimpleNamespace(release_sha256=successor)]))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
            return_value=(parent, "a" * 64)))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.state._state_from_json",
            return_value=SimpleNamespace(current_student=pure.legacy.checkpoint)))
        stack.enter_context(patch(
            "bilqis_mlx.factory.schedule.schedule_program_from_executable_release",
            return_value=object()))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.atlas_capability_adoption_v2."
            "_accepted_capability_only_retry_state_v2",
            return_value=(None, parent_pointer)))
        accepted_generation = stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
            side_effect=[
                (parent_pointer, parent),
                (last_parent_pointer or parent_pointer, parent),
            ]))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.atlas_capability_facts_v2."
            "read_capability_only_admission_facts_v2"))
        stack.enter_context(patch(
            "bilqis_mlx.source_adapters.school.live_source_registry",
            return_value=object()))
        stack.enter_context(patch(
            "bilqis_mlx.factory.live_answers.live_answer_registry",
            return_value=object()))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.atlas_capability_adoption_v2."
            "verify_current_implementations"))
        exact_release = stack.enter_context(patch(
            "bilqis_mlx.runtime.atlas_capability_adoption_v2."
            "_require_exact_atlas_release"))
        return stack, (
            issue_transition, derive, issue_binding, persist, publish,
            factory_release, accepted_generation, exact_release, lease_guard)

    def _publication_case(self, *, last_parent_pointer=None):
        handoff = self._handoff()
        approval, lease = self._lease_authority(handoff)
        pure = self._context(handoff, approval)
        runtime = _PreparedSuccessorRuntime(
            None, pure.run_dir, {"school": {}}, None, None, {}, object(), object(), 0.)
        current = AtlasAdmissionContextV2(
            pure.legacy, pure.run_dir, runtime=runtime, source_authority=object())
        parent = SimpleNamespace(
            retained_state=SimpleNamespace(
                optimizer_step=pure.legacy.checkpoint.optimizer_step))
        transition = SimpleNamespace()
        candidate = SimpleNamespace()
        binding = SimpleNamespace()
        pointer = {"generation": 1, "manifest_sha256": "f" * 64}
        parent_pointer = {
            "generation": 0,
            "manifest_sha256": "a" * 64,
            "acceptance_sha256": "b" * 64,
        }
        stack, mocks = self._publication_stack(
            handoff, lease, pure, parent, transition, candidate, binding,
            pointer, parent_pointer, last_parent_pointer=last_parent_pointer)
        with stack:
            actual = publish_capability_only_factory_successor(
                current, handoff, lease, expected_parent_pointer=parent_pointer)
        return actual, pointer, handoff, parent, transition, candidate, binding, runtime, mocks

    def test_capability_only_publisher_binds_authenticated_predecessor_and_publishes_once(self):
        (actual, pointer, handoff, parent, transition, candidate, binding, runtime,
         mocks) = self._publication_case()
        (issue_transition, derive, issue_binding, _persist, publish,
         _factory_release, _accepted_generation, exact_release, lease_guard) = mocks
        self.assertEqual(actual, pointer)
        self.assertEqual(
            issue_transition.call_args.kwargs[
                "predecessor_factory_release_sha256"],
            handoff.receipt.predecessor_release.release_sha256)
        derive.assert_called_once_with(
            parent, parent_manifest_sha256="a" * 64, transition=transition)
        issue_binding.assert_called_once_with(
            candidate, parent, transition=transition)
        publish.assert_called_once_with(
            runtime.run_dir, candidate, admission=binding, reserve_gib=0.0)
        exact_release.assert_called_once()
        lease_guard.assert_called_once()
        self.assertEqual(lease_guard.call_args.args[0], runtime.run_dir)

    def test_capability_only_publisher_rejects_parent_pointer_advance_before_issue(self):
        advanced = {
            "generation": 1,
            "manifest_sha256": "c" * 64,
            "acceptance_sha256": "d" * 64,
        }
        with self.assertRaises(BilqisError) as failure:
            self._publication_case(last_parent_pointer=advanced)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_ATLAS_RUNTIME_CONTEXT_CHANGED",
        )

    def test_capability_only_publisher_recovers_after_release_persist_before_b13_publish(self):
        handoff = self._handoff()
        approval, lease = self._lease_authority(handoff)
        pure = self._context(handoff, approval)
        runtime = _PreparedSuccessorRuntime(
            None, pure.run_dir, {"school": {}}, None, None, {}, object(), object(), 0.)
        current = AtlasAdmissionContextV2(
            pure.legacy, pure.run_dir, runtime=runtime, source_authority=object())
        parent = SimpleNamespace(
            retained_state=SimpleNamespace(
                optimizer_step=pure.legacy.checkpoint.optimizer_step))
        transition = SimpleNamespace()
        candidate = SimpleNamespace()
        binding = SimpleNamespace()
        pointer = {"generation": 1, "manifest_sha256": "f" * 64}
        parent_pointer = {
            "generation": 0,
            "manifest_sha256": "a" * 64,
            "acceptance_sha256": "b" * 64,
        }
        stack, mocks = self._publication_stack(
            handoff, lease, pure, parent, transition, candidate, binding,
            pointer, parent_pointer)
        (_issue_transition, _derive, _issue_binding, persist, publish,
         factory_release, accepted_generation, _exact_release, _lease_guard) = mocks
        predecessor = handoff.receipt.predecessor_release.release_sha256
        successor = handoff.staged_candidate.successor.release_sha256
        accepted_generation.side_effect = [
            (parent_pointer, parent),
            (parent_pointer, parent),
            (parent_pointer, parent),
            (parent_pointer, parent),
        ]
        factory_release.side_effect = [
            SimpleNamespace(release_sha256=predecessor),
            SimpleNamespace(release_sha256=predecessor),
            SimpleNamespace(release_sha256=successor),
        ]
        publish.side_effect = [OSError("simulated B13 interruption"), pointer]

        with stack:
            with self.assertRaisesRegex(OSError, "simulated B13 interruption"):
                publish_capability_only_factory_successor(
                    current, handoff, lease,
                    expected_parent_pointer=parent_pointer)
            actual = publish_capability_only_factory_successor(
                current, handoff, lease,
                expected_parent_pointer=parent_pointer)

        self.assertEqual(actual, pointer)
        self.assertEqual(persist.call_count, 2)
        self.assertEqual(publish.call_count, 2)
