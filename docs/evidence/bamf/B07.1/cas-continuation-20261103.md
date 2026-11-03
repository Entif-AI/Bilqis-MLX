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

The complete candidate still requires fresh exact-head merge-readiness review.
IPR-0220 governs. No actual student, matching AdamW, teacher, champion,
checkpoint or human-run state was changed; no self-merge is authorized.

## 2026-11-03 current-unified continuation

Reviewed unified advanced to
`9bf47289e9ed0a64d275b31c3a7de42c55a8b83e` after the #770 verifier and A08.3
lifecycle integrations. The preserved #783 repair
`17be8a3d5aebfaba0a88b4190a41027eb6daedfb` was therefore continued on a new
isolated branch and merge-forwarded, without rebase, in synchronization commit
`c4dffbf1acf543378ce673f35be23c05163eebf4`. Production code merged without
conflict; only Lane-B flow bookkeeping required reconciliation to current live
inventory.

The exact joined pinned-source -> CAS save/load -> one disposable next update ->
source-qualified continuation selection was rerun against the current-unified
tree: **14/14 PASS, zero skips**. The broader #456 selection then ran the complete
B07 motif key/preparation/transaction owners, retained-state custody, canonical
motif-read package, B13 codec/continuation witness, released-schema source
authority and public-formal type composition: **103/103 PASS, zero skips**.

The prior two motif-read file-entrypoint failures were reproduced exactly as
package-relative fixture-import errors under the canonical file runner. The two
companion tests now use canonical absolute fixture imports, matching the already
accepted runner contract. AST comparison with all imports removed is identical
before/after for both files; no test body or production behavior changed. The
motif-read package itself is now **11/11 PASS, zero skips** under the canonical
runner.

No source artifact was regenerated, no repository dependency changed, and no
real learner, optimizer, teacher, champion, checkpoint or human-run state was
mutated. Final acceptance remains the parent #456 exact-head quality/hosted gates
and fresh pinned merge-readiness review after push/readback.

## Fresh EGM authority repair

Fresh exact-head EGM on `f8d4471607b14052e57385de6cd997f3856f3082`
found that the retained-state issuer helper was still a raw-component mint: a
caller that already possessed optimizer, policy, motif-allocation and step values
could ask that helper to stamp them as retained authority. The joined continuation
witness also used that helper directly, so CAS preservation was stronger than the
authority chain the test claimed.

The repair removes that mint rather than hiding it. B07 source preparation is now
genesis-only at its public surface. Non-genesis source continuation is owned by the
B13 custody boundary and requires an immutable bundle root plus the exact expected
manifest SHA-256. B13 validates the manifest, sidecars, motif allocation, policy,
CAS-or-legacy tensor binding and optimizer step through the existing bundle loader
before the B07 planner receives the loaded allocation snapshot. Accepted candidate
transitions may continue such already-authoritative state while preserving the exact
allocation object. No production API accepts raw non-genesis `CandidateState`, raw
`MotifAllocationSnapshot`, or raw `(optimizer, policy, allocations, step)` values as
retained authority.

The joined witness now starts with a serialized immutable custody fixture carrying
the real source-proposed motif allocation. Production B13 validation rehydrates that
state, one disposable accepted update preserves the allocation, the updated state is
serialized again, and the B13 continuation adapter re-enters real pinned source
qualification from that exact second bundle. This proves custody-bound continuity;
it does **not** promote B07.1 into B07.2/B07.3 accepted-generation publication
authority.

Focused repaired proof is **14/14 PASS, zero skips** for custody, retained-state and
split-entry regressions; the real-source custody/source selection is **13/13 PASS,
zero skips**. The broadened affected selection is **119/119 PASS, zero skips** across
B07 key/preparation/transaction owners, retained candidate state, motif reads, B13
codec/publication/CAS custody, real public-formal source authority and released-frame
schema authority. Structure, governance, Factory architecture, docs, changed-scope
smell, error-control, live flow, 13/13 flow regressions and `git diff --check` are
green on the repaired working tree before the final push.

The same repair also removes the split-module recurrence exposed by #783: the
retention tests import `CandidateState` only through its canonical public module,
and the surviving legacy motif-preparation test delegates to the canonical
decomposed owner rather than patching a private symbol on the old facade.
