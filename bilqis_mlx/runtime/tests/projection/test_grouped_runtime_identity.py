"""Physical runtime groups preserve public imports and source provenance."""
import hashlib
import importlib
import importlib.util
from pathlib import Path
from pkgutil import iter_modules
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime as runtime


GROUPS = {
    "_source": ("source_development", "source_execution", "source_prefetch"),
    "_model": ("atlas_attention", "atlas_optimizer", "atlas_refinement",
               "backbone_group_numerical", "backbone_source_bridge", "model_topology",
               "mlx_memory", "mlx_parity", "refinement_policy", "salience_auxiliaries",
               "topology_lifecycle"),
    "_custody": ("boundary_commit", "disk", "experiment_runs", "mlx_checkpoint",
                 "outbox_lineage", "session", "state", "timing_trace", "reconciliation"),
    "_operator": ("admission", "operator_recovery", "operator_registry", "qualification",
                  "qualification_manifest", "qualification_results"),
    "_teacher": ("teacher_observation_capture", "teacher_observation_replay",
                 "teacher_policy_selection"),
    "_depth": ("block_attnres",),
    "_correction": ("atlas_requalification", "atlas_temporal_revalidation",
                    "atlas_correction_branches", "atlas_requalification_contracts",
                    "atlas_temporal_contracts", "atlas_stale_replay"),
    "_batch": ("atlas_training_adapter", "candidate_evidence", "atlas_memory_retry"),
    "_admission": ("atlas_admission", "atlas_admission_policy", "atlas_debt",
                   "autonomy_loop", "autonomy_state", "frontier_refresh", "jit_adoption",
                   "atlas_lease_contracts", "atlas_lease_storage"),
    "_capability": ("capability_authority", "capability_evidence_history",
                    "candidate_staging", "capability_retention"),
    "_projection": ("akasha_outbox", "akasha_staging", "bamf_projection",
                    "generation_projection", "owner_receipt_fixture", "rosetta_observation"),
}


class GroupedRuntimeIdentityTests(unittest.TestCase):
    def test_public_module_discovery_and_physical_groups(self):
        available = {entry.name for entry in iter_modules(runtime.__path__)}
        for group, names in GROUPS.items():
            for name in names:
                with self.subTest(name=name):
                    self.assertIn(name, available)
                    spec = importlib.util.find_spec("bilqis_mlx.runtime." + name)
                    self.assertIn(group, Path(spec.origin).parts)

    def test_alternate_names_fail_before_and_after_canonical_discovery(self):
        probe = """
import importlib, importlib.util, json, sys
groups = json.loads(sys.argv[1])
for group, names in groups.items():
    for name in names:
        alternate = 'bilqis_mlx.runtime.' + group + '.' + name
        for discovery_first in (False, True):
            if discovery_first:
                assert importlib.util.find_spec('bilqis_mlx.runtime.' + name)
            try:
                importlib.import_module(alternate)
            except ModuleNotFoundError as error:
                assert error.name == alternate, (alternate, error.name)
            else:
                raise AssertionError(alternate)
"""
        import json
        result = subprocess.run([sys.executable, "-B", "-c", probe, json.dumps(GROUPS)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_teacher_epoch_hashes_canonical_owner_bytes(self):
        from bilqis_mlx.runtime.teacher_observation_capture import policy_epoch
        epoch = policy_epoch({}, SimpleNamespace(release_sha256="a" * 64),
                             configured_steps=1, batch_size=1, settings=None, enrichment=False)
        for name in ("source_prefetch", "teacher_observation_capture", "state"):
            spec = importlib.util.find_spec("bilqis_mlx.runtime." + name)
            self.assertEqual(epoch["implementation"]["runtime/" + name + ".py"],
                             hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest())

    def test_source_context_has_one_class_identity(self):
        from bilqis_mlx.runtime.source_execution import SourceExecutionContext
        module = importlib.import_module("bilqis_mlx.runtime.source_execution")
        self.assertIs(module.SourceExecutionContext, SourceExecutionContext)
        self.assertEqual(SourceExecutionContext.__module__, "bilqis_mlx.runtime.source_execution")

    def test_qualification_root_uses_canonical_package_location(self):
        from bilqis_mlx.runtime import qualification
        package = importlib.util.find_spec("bilqis_mlx")
        expected = Path(package.origin).parent.parent
        with patch.object(qualification, "execute", return_value={}) as execute:
            self.assertEqual(qualification.main([
                "--manifest", "fixture.json", "--arm", "baseline",
                "--expected-digest", "a" * 64, "--dry-run",
            ]), 0)
        self.assertEqual(execute.call_args.kwargs["root"], expected)
