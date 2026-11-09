"""Disposable compatible-delta candidates are screened before activation."""
from dataclasses import replace
from hashlib import sha256
import unittest

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.cognitive_package import (
    DeltaSlice, PackageArtifact, PackageKind, ReceiverTensor,
    encode_plastic_delta, export_capability,
    receiver_parameter_schema_digest, receiver_weight_digest, screen_delta_candidate,
)
from bilqis_mlx.runtime.cognitive_package.delta import _apply_delta_tensors, _issue_candidate
from bilqis_mlx.runtime.cognitive_package.tests.export_authority_fixtures import grant
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import digest, snapshot
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import _evidence


def _sha(data):
    return sha256(data).hexdigest()


def _tensor(name, values):
    array = np.asarray(values, dtype="<f4")
    return ReceiverTensor(name, array.shape, array.tobytes())


def _package(tensors):
    source, _ = snapshot(PackageKind.WEIGHT_DELTA)
    by_name = {value.parameter_name: value for value in tensors}
    parent = np.frombuffer(by_name["weights"].values_fp32, dtype="<f4")
    changed = parent[1:3].tobytes()
    delta = np.asarray((0.5, -1.0), dtype="<f4").tobytes()
    payload = encode_plastic_delta((DeltaSlice("weights", 1, 3, _sha(changed), delta),))
    artifact = PackageArtifact("weights", PackageKind.WEIGHT_DELTA, payload)
    binding = replace(
        source.binding,
        base_weight_digest=receiver_weight_digest(tensors),
        parameter_schema_digest=receiver_parameter_schema_digest(tensors),
    )
    source = replace(source, binding=binding, artifacts=(artifact,) + source.artifacts[1:])
    return export_capability(source, source.signature, grant(source)), source


def apply_plastic_delta(package, binding, parent, tensors):
    """Exercise pure delta mechanics separately from receiver authority."""
    tensors = tuple(sorted(tensors, key=lambda value: value.parameter_name))
    return _issue_candidate(parent, package, binding, tensors,
                            _apply_delta_tensors(package, binding, tensors))


def _retarget_evidence(evidence, parent, candidate):
    def pair(value):
        parent_results = tuple(replace(result, generation_digest=parent)
                               for result in value.parent.results)
        candidate_results = tuple(replace(result, generation_digest=candidate)
                                  for result in value.candidate.results)
        return replace(
            value,
            parent=replace(value.parent, generation_digest=parent,
                           results=parent_results),
            candidate=replace(value.candidate, generation_digest=candidate,
                              results=candidate_results),
        )
    return replace(evidence, target=pair(evidence.target),
                   fresh_lesson=pair(evidence.fresh_lesson),
                   fixed_school=pair(evidence.fixed_school))


class DisposableDeltaCandidateTests(unittest.TestCase):
    def test_compatible_delta_applies_only_declared_slice_without_parent_mutation(self):
        parent = _tensor("weights", (1.0, 2.0, 3.0, 4.0))
        untouched = _tensor("other", (7.0, 8.0))
        package, source = _package((parent, untouched))
        candidate = apply_plastic_delta(
            package, source.binding, "a" * 64, (parent, untouched))

        tensors = {value.parameter_name: value for value in candidate.tensors}
        actual = np.frombuffer(tensors["weights"].values_fp32, dtype="<f4")
        self.assertEqual(tuple(actual), (1.0, 2.5, 2.0, 4.0))
        self.assertEqual(np.frombuffer(parent.values_fp32, dtype="<f4").tolist(),
                         [1.0, 2.0, 3.0, 4.0])
        self.assertIs(tensors["other"], untouched)
        self.assertEqual(candidate.parent_generation, "a" * 64)
        self.assertEqual(candidate.package_digest, package.digest)

    def test_parent_slice_digest_and_existing_parameter_are_required(self):
        parent = _tensor("weights", (1.0, 2.0, 3.0, 4.0))
        package, source = _package((parent,))
        with self.assertRaises(BilqisError):
            apply_plastic_delta(package, source.binding, "a" * 64,
                                (_tensor("weights", (1.0, 9.0, 3.0, 4.0)),))
        with self.assertRaises(BilqisError):
            apply_plastic_delta(package, source.binding, "a" * 64,
                                (_tensor("other", (1.0, 2.0, 3.0, 4.0)),))

    def test_caller_selected_c05_inputs_are_not_a_screening_interface(self):
        parent = _tensor("weights", (1.0, 2.0, 3.0, 4.0))
        package, source = _package((parent,))
        candidate = apply_plastic_delta(
            package, source.binding, "a" * 64,
            (parent,))
        with self.assertRaises(TypeError):
            screen_delta_candidate(
                candidate, parent_solver=object(), candidate_solver=object(),
                target_capability="A", policy=object(), cohorts=())

    def test_binding_mismatch_rejects_before_any_delta_application(self):
        parent = _tensor("weights", (1.0, 2.0, 3.0, 4.0))
        package, source = _package((parent,))
        wrong = replace(source.binding, motif_key_map_digest=digest("foreign"))
        with self.assertRaises(BilqisError):
            apply_plastic_delta(package, wrong, "a" * 64,
                                (parent,))

    def test_receiver_bytes_must_match_claimed_base_weight_identity(self):
        weights = _tensor("weights", (1.0, 2.0, 3.0, 4.0))
        other = _tensor("other", (7.0, 8.0))
        package, source = _package((weights, other))
        forged_other = _tensor("other", (7.0, 99.0))
        with self.assertRaises(BilqisError):
            apply_plastic_delta(package, source.binding, "a" * 64,
                                (weights, forged_other))

    def test_candidate_and_screened_result_cannot_be_caller_minted_or_replaced(self):
        from bilqis_mlx.runtime.cognitive_package import (
            DisposableDeltaCandidate, ScreenedDeltaCandidate,
        )
        weights = _tensor("weights", (1.0, 2.0, 3.0, 4.0))
        package, source = _package((weights,))
        candidate = apply_plastic_delta(package, source.binding, "a" * 64, (weights,))

        with self.assertRaises(BilqisError):
            DisposableDeltaCandidate()
        with self.assertRaises(BilqisError):
            replace(candidate, generation_digest="f" * 64)
        with self.assertRaises(BilqisError):
            ScreenedDeltaCandidate()

    def test_caller_retargeted_retention_evidence_is_not_a_screening_input(self):
        parent = _tensor("weights", (1.0, 2.0, 3.0, 4.0))
        package, source = _package((parent,))
        candidate = apply_plastic_delta(package, source.binding, "a" * 64, (parent,))
        forged = _retarget_evidence(
            _evidence(), candidate.parent_generation, candidate.generation_digest)

        with self.assertRaises(TypeError):
            screen_delta_candidate(candidate, paired_retention_evidence=forged)

    def test_noncanonical_delta_wire_uses_structured_package_error(self):
        payload = encode_plastic_delta((DeltaSlice(
            "weights", 0, 1, "a" * 64,
            np.asarray((1.0,), dtype="<f4").tobytes()),)) + b" "
        source, _ = snapshot(PackageKind.WEIGHT_DELTA)
        artifact = PackageArtifact("weights", PackageKind.WEIGHT_DELTA, payload)
        source = replace(source, artifacts=(artifact,) + source.artifacts[1:])
        package = export_capability(source, source.signature, grant(source))
        with self.assertRaises(BilqisError):
            apply_plastic_delta(package, source.binding, "a" * 64,
                                (_tensor("weights", (1.0,)),))


if __name__ == "__main__":
    unittest.main()
