# Issue #520 structural interruption

This issue branch starts from Lane C `57f8d9d`, consumes reviewed unified `d468b1a`, and preserves the existing #610 repair through local commit `339c9cc`. Work Stack context is preserved in `bamf-c520-20261030`; feature qualification is paused. No merge or student start is authorized.

## Directory repair

The runtime directory has 53 direct Python files. Move the exact modules below into physical groups. Keep every established `bilqis_mlx.runtime.NAME` identity through the existing package search path. Physical group packages have empty search paths, preventing alternate module identities. Preserve source bytes except explicit filesystem lookup repairs. Mirror package-local test ownership; keep stable test helper import paths through the test package search path. Existing modules remain importable from any working directory.

- `_source/`: `source_development.py`, `source_execution.py`, `source_prefetch.py`.
- `_model/`: `atlas_attention.py`, `atlas_optimizer.py`, `atlas_refinement.py`, `backbone_group_numerical.py`, `backbone_source_bridge.py`, `model_topology.py`, `mlx_memory.py`, `mlx_parity.py`, `refinement_policy.py`, `salience_auxiliaries.py`, `topology_lifecycle.py`.
- `_custody/`: `boundary_commit.py`, `disk.py`, `experiment_runs.py`, `mlx_checkpoint.py`, `outbox_lineage.py`, `session.py`, `state.py`, `timing_trace.py`, `reconciliation.py`.
- `_operator/`: `admission.py`, `operator_recovery.py`, `operator_registry.py`, `qualification.py`, `qualification_manifest.py`, `qualification_results.py`.
- `_teacher/`: `teacher_observation_capture.py`, `teacher_observation_replay.py`, `teacher_policy_selection.py`.
- `_capability/`: `candidate_staging.py`, `capability_retention.py`.
- `_depth/`: `block_attnres.py`.
- `_correction/`: `atlas_requalification.py`, `atlas_temporal_revalidation.py`.
- `_batch/`: `atlas_training_adapter.py`, `candidate_evidence.py`, `atlas_memory_retry.py`.
- `_admission/`: `atlas_admission.py`.

Retain exactly `__init__.py`, `assessment.py`, `atlas_resources.py`, `atlas_revalidation.py`, `autonomy_live.py`, `checkpoints.py`, `cognitive_solver.py`, `exam_execution.py`, `model_topology_v2.py`, `operating_loop.py`, `release_adoption.py`, `visits.py` directly under runtime (12 files).

Move each existing `test_NAME.py` with its owner; shared integration tests stay at the root until the test-directory interruption. Extra custody tests move with state/checkpoint ownership. Preserve all original tests and assertions. Do not recursively sweep new groups.

`qualification.main` must still find the repository root after moving one level. Teacher epoch source keys stay unchanged; resolve runtime source bytes through their canonical module specs because physical files move. Test the exact original source keys and digest values. Moved tests with `__file__` root lookups gain one parent level.

Commit a resumable directory repair, then handle the individually encountered oversized modules in order: atlas_admission (416 lines), atlas_requalification (393), atlas_temporal_revalidation (443), atlas_training_adapter (402), block_attnres (365), candidate_evidence (415), capability_retention (377), reconciliation (367). Their original and companion tests must become <240 lines, split by cohesive ownership and without changing public signatures or patch targets. Detailed extraction decisions are recorded before each file repair. This list comes from the files directly relocated during directory repair; it is not a repository debt sweep.

## Proof and limits

Baseline: `BILQIS_ROSETTA_CONTRACT_ROOT=/Users/cr8s/Code/rosetta /tmp/bamf-c-codex-venv/bin/python -B scripts/run_tests.py bilqis_mlx/runtime/tests` reports 463 total,419 pass,1 failure,22 errors,21 skips. Preserve the individual failure identities rather than masking them. Run the same suite after grouping; run affected CPU owner tests separately. Test every grouped owner for canonical discoverability, alternate-path rejection and clean installed-package lookup outside the checkout. MLX-dependent imports need the designated backend; a find_spec witness is not neural execution.

Distribution qualification requires the Python package to include its actual subpackages. Inspect and prove the existing setuptools configuration before claiming installed support. New import/root behavior gets red/green regression evidence. Re-run the changed-path structure gate against unified and disclose pending file/test interruptions. Independent codebase/comprehension review remains required. Status remains PARTIAL / EGM_PENDING; upstream/service/retained-learning gates remain separate.

## Exact directory-phase test moves

- `bilqis_mlx/runtime/tests/test_atlas_attention.py` becomes `bilqis_mlx/runtime/tests/model/test_atlas_attention.py`.
- `bilqis_mlx/runtime/tests/test_atlas_optimizer.py` becomes `bilqis_mlx/runtime/tests/model/test_atlas_optimizer.py`.
- `bilqis_mlx/runtime/tests/test_atlas_refinement.py` becomes `bilqis_mlx/runtime/tests/model/test_atlas_refinement.py`.
- `bilqis_mlx/runtime/tests/test_backbone_group_numerical.py` becomes `bilqis_mlx/runtime/tests/model/test_backbone_group_numerical.py`.
- `bilqis_mlx/runtime/tests/test_backbone_source_bridge.py` becomes `bilqis_mlx/runtime/tests/model/test_backbone_source_bridge.py`.
- `bilqis_mlx/runtime/tests/test_model_topology.py` becomes `bilqis_mlx/runtime/tests/model/test_model_topology.py`.
- `bilqis_mlx/runtime/tests/test_mlx_memory.py` becomes `bilqis_mlx/runtime/tests/model/test_mlx_memory.py`.
- `bilqis_mlx/runtime/tests/test_mlx_parity.py` becomes `bilqis_mlx/runtime/tests/model/test_mlx_parity.py`.
- `bilqis_mlx/runtime/tests/test_refinement_policy.py` becomes `bilqis_mlx/runtime/tests/model/test_refinement_policy.py`.
- `bilqis_mlx/runtime/tests/test_salience_auxiliaries.py` becomes `bilqis_mlx/runtime/tests/model/test_salience_auxiliaries.py`.
- `bilqis_mlx/runtime/tests/test_topology_lifecycle.py` becomes `bilqis_mlx/runtime/tests/model/test_topology_lifecycle.py`.
- `bilqis_mlx/runtime/tests/test_experiment_runs.py` becomes `bilqis_mlx/runtime/tests/custody/test_experiment_runs.py`.
- `bilqis_mlx/runtime/tests/test_mlx_checkpoint.py` becomes `bilqis_mlx/runtime/tests/custody/test_mlx_checkpoint.py`.
- `bilqis_mlx/runtime/tests/test_timing_trace.py` becomes `bilqis_mlx/runtime/tests/custody/test_timing_trace.py`.
- `bilqis_mlx/runtime/tests/test_admission.py` becomes `bilqis_mlx/runtime/tests/operator/test_admission.py`.
- `bilqis_mlx/runtime/tests/test_operator_recovery.py` becomes `bilqis_mlx/runtime/tests/operator/test_operator_recovery.py`.
- `bilqis_mlx/runtime/tests/test_qualification.py` becomes `bilqis_mlx/runtime/tests/operator/test_qualification.py`.
- `bilqis_mlx/runtime/tests/test_teacher_observation_capture.py` becomes `bilqis_mlx/runtime/tests/teacher/test_teacher_observation_capture.py`.
- `bilqis_mlx/runtime/tests/test_teacher_observation_replay.py` becomes `bilqis_mlx/runtime/tests/teacher/test_teacher_observation_replay.py`.
- `bilqis_mlx/runtime/tests/test_block_attnres.py` becomes `bilqis_mlx/runtime/tests/depth/test_block_attnres.py`.
- `bilqis_mlx/runtime/tests/test_atlas_training_adapter.py` becomes `bilqis_mlx/runtime/tests/batch/test_atlas_training_adapter.py`.
- `bilqis_mlx/runtime/tests/test_state_archive.py` becomes `bilqis_mlx/runtime/tests/custody/test_state_archive.py`.
- `bilqis_mlx/runtime/tests/test_state_dag.py` becomes `bilqis_mlx/runtime/tests/custody/test_state_dag.py`.
- `bilqis_mlx/runtime/tests/test_backup.py` becomes `bilqis_mlx/runtime/tests/custody/test_backup.py`.
- `bilqis_mlx/runtime/tests/test_inherited_outbox.py` becomes `bilqis_mlx/runtime/tests/custody/test_inherited_outbox.py`.
- `bilqis_mlx/runtime/tests/test_data_plane.py` becomes `bilqis_mlx/runtime/tests/custody/test_data_plane.py`.
- `bilqis_mlx/runtime/tests/test_mlx_gradients.py` becomes `bilqis_mlx/runtime/tests/custody/test_mlx_gradients.py`.

Test search paths add exactly source, model, custody, operator, teacher, depth, correction, batch, admission, capability, projection. All existing helper imports retain their original module names. The timing-trace test root lookup changes parents[3] to parents[4].

Qualification root lookup uses the canonical bilqis_mlx package spec origin, then parent.parent; teacher package root uses that same spec origin.parent. Epoch hashing maps each runtime/NAME.py key through find_spec("bilqis_mlx.runtime.NAME").origin, retaining original keys; other owners resolve under the package root. No runtime owner is imported merely to hash it. Compare all unchanged owner hashes byte-for-byte before and after; intentionally edited capture code has its new actual digest.

Full-suite failure/error identities, normalized only for test file relocation/dynamic loader names, must match baseline exactly. Added import/root tests must pass.

## Companion test-directory interruption

After the reviewed owner grouping, runtime/tests has24 direct files. The following12 exact moves bring it to12; preserve shared imports through the already-declared search paths:

- `tests/test_autonomy_loop.py` becomes `tests/admission/test_autonomy_loop.py`.
- `tests/test_autonomy_state.py` becomes `tests/admission/test_autonomy_state.py`.
- `tests/test_jit_adoption.py` becomes `tests/admission/test_jit_adoption.py`.
- `tests/test_bamf_capability_retention.py` becomes `tests/capability/test_bamf_capability_retention.py`.
- `tests/test_cognitive_solver.py` becomes `tests/capability/test_cognitive_solver.py`.
- `tests/test_model_topology_v2.py` becomes `tests/model/test_model_topology_v2.py`.
- `tests/test_atlas_plasticity.py` becomes `tests/model/test_atlas_plasticity.py`.
- `tests/test_atlas_resources.py` becomes `tests/model/test_atlas_resources.py`.
- `tests/test_error_control_plane.py` becomes `tests/operator/test_error_control_plane.py`.
- `tests/test_explain_cli.py` becomes `tests/operator/test_explain_cli.py`.
- `tests/test_v2_source_dispatch.py` becomes `tests/source/test_v2_source_dispatch.py`.
- `tests/test_typed_answer_training.py` becomes `tests/source/test_typed_answer_training.py`.

For cognitive_solver, model_topology_v2(two sites), and typed_answer_training, repository-relative parents[3] changes to parents[4]. The371-line cognitive solver test and529-line model_topology_v2 test are subsequent file interruptions, not waived by moving.

## Packaging finding

The existing setuptools configuration explicitly included only bilqis_mlx. A freshly built0.5.0 wheel contains zero runtime files; this is observed baseline packaging debt. Replace that one-package list with package discovery restricted to bilqis_mlx*. Rebuild and install without dependencies into a disposable environment, then run the namespace/discovery proof outside the checkout. This proves inclusion and import identity, not complete application-resource packaging or executable model qualification.

## File interruption1: Atlas lease

Split atlas_admission.py416lines into atlas_lease_contracts.py (validation helpers, LeaseRunIdentity, DeltaBudgetPolicy, AtlasSourceApproval, ResourceCeiling, AtlasAdmissionLease) and atlas_lease_storage.py (_store, _lease_from_json, _read_atlas_lease, _persist_atlas_lease_locked, _atlas_lease_lock). Keep issue_atlas_lease, command request/staging, public read/persist wrappers and renew_atlas_lease in atlas_admission.py, with explicit imports preserving current callers. The storage helper uses its local reader directly; public read wrapper already delegates there. Renewal and its _durable_json patch seam stay in the original owner. All signatures, schemas, validation and write ordering remain unchanged.

Move scope/signature and lookup-only tests to test_atlas_lease_contracts.py; move roundtrip/idempotence, tampered payload and unsafe-root tests to test_atlas_lease_storage.py. Keep the original106-line test module's shared fixtures in place for existing consumers. Each resulting production and companion test must be<240lines. Before proof:41/41 admission tests. After proof:the identical41 tests plus grouped canonical import tests. Structural red is the recorded416-line file finding; no intentionally broken runtime behavior is needed for a behavior-preserving extraction.
