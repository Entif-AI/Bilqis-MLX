# B07/B13 CAS continuation integration

Current source baseline: reviewed unified
`aa828eb5cb8822a5614aa3353864bf187f83444d`.
Original B07 candidate: `203c53eb1252ada8fba8ed6f1e9c7c5c57ca6cde`.

## CAS reader reconciliation

The preserved B07 reader passed its inline payload binding directly to the tensor
loader. Under current CAS storage that produces three failures in the four-test
codec selection, including `BAMF_BUNDLE_TENSOR_BINDING_INVALID`.

Integration `f101c290` retains current `_tensor_read_path` CAS/legacy lookup and
passes its resolved path/binding into the tensor loader. B07's authenticated
retained-state issuance follows the existing manifest and sidecar validation.
The same four tests then pass. Existing custody validation is unchanged.

## Canonical CandidateState identity

Joined red regression `82806ab55b5eef7afbc09ad6c22f8f61c399a427` constructs actual
pinned-source motifs, saves/loads through CAS, performs one disposable update,
then re-enters source-qualified motif preparation. This exposed a second seam:
the source bridge expected the physical-module CandidateState, while B13 returned
the public-module CandidateState. Both names execute the same file, but class and
issuer identities differ. Source re-entry rejected the valid loaded state.

Issue #783 changes the source bridge and its source fixtures to the canonical
public import. Exact type validation and issuance checks remain unchanged.
Incident **PM-2026-11-03-003 / RC-147 / PAT-101** was filed and native-readback
verified before repair.

With `BILQIS_ATLAS_REAL_ARTIFACT` set to the external A01 artifact whose bundle is
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`, run:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_motif_source_continuation.py \
  bilqis_mlx/learning/_engram/tests/test_atlas_engram_source.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_codec.py
```

Observed: **14/14 PASS, zero skips**. The joined witness checks that tensor bytes
really reside in CAS, exact motif slots survive cold read and one next update,
no existing motif is reallocated, and replay increases observed-use counts.
The numerical body is the existing tiny B13 fixture; source motifs use the actual
pinned source replay. This does not qualify a complete learner or B13 learning
generation. The source/forged-history negatives remain in the same selection.

## Remaining gate

The complete candidate still requires its other affected tests and fresh scoped
merge-readiness review. Two motif-read files expose the known package-context
test-runner defect; their file-entrypoint failures are not passing motif-read
proof. IPR-0220 governs. No actual student, matching AdamW, teacher, champion,
checkpoint or human-run state was changed; no self-merge is authorized.
