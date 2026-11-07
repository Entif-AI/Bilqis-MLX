# C09 issue #752 fresh EGM packet

This packet is intentionally limited to the final-candidate contract, named
source, authority boundaries, changed surface, and verification receipts. It
does not contain implementation-conversation history or prior reviewer
findings.

## Review target

- Repository: `Entif-AI/Bilqis-MLX`
- Issue: `#752` — EGM mitigation: connect dependency indexing and correction
  holds to artifact owners
- Named source: `#516` — BAMF-0.2 C09.1 | Index reverse dependencies of
  semantic and learned artifacts
- Reviewed integration trunk: `codex/bamf-unified-base-20261028`
- Consumed unified SHA: `aef69dae9179bb09f85f955b8a494f6582eac942`
- Candidate branch: `codex/752-final-prime-20261106`
- Implementation checkpoint: `6f75e97affb2d6166c3e11f4ab7c14dba7163ee4`

The Goldfish MUST resolve the candidate's exact HEAD itself before review and
report that SHA in its verdict.

## Leaf acceptance from #752

1. Populate direct dependencies from the actual atlas-feature, packed-frame,
   motif, exact-cache, operator-composition and capability-support owners.
2. Route affected production reads through the owning correction/eligibility
   gate; stale direct artifacts must be held before use.
3. Prove lazy impact/exigency ordering and propagation stopping when
   materialized output and eligibility remain unchanged, using actual
   producer/consumer paths.
4. Keep independent later evidence distinct from replay of a superseded
   belief.
5. Run focused tests and fresh isolated EGM on the final candidate.

Issue #752 does not authorize real student, matching optimizer, teacher,
champion, checkpoint, or neural-run mutation. IPR-0220 remains controlling.
No self-merge is authorized.

## Named-source obligations from #516

The C09.1 child owns these four clauses, in order:

1. Index immediate dependencies for atlas features, packed frames, motifs,
   exact caches, operator compositions and capability support.
2. Use immutable correction events and reverse direct edges.
3. Hold directly affected artifacts before their next use; revalidate lazily
   in impact/exigency order.
4. Propagation stops when materialized content and eligibility are unchanged.

Inherited recovery contract: reusable transforms and contexts declare
immediate input, operator, release, policy, time and rights dependencies.
Maintain reverse direct edges. On correction, hold directly affected reusable
artifacts, re-evaluate them, and propagate only when output identity or
eligibility changes. A correction invalidating learned support marks the
affected capability for focused requalification; it does not erase weights by
deleting a graph node. Reactivation requires current support and the same
operational assessment contract.

Inherited adversarial proof: a superseded belief replayed after remediation
must be held and faulted while the historical learner generation remains
intact but marked for requalification. A distinct later event with the same
wording and legitimate new evidence must not be treated as the stale replay.

## Authority boundaries to audit

- `ATLAS_FEATURE`: source/backbone compilation owns current materialization.
- `PACKED_FRAME`: compiled frame input owns current packed-frame
  materialization.
- `MOTIF`: authenticated B13 accepted-execution cache owns retained motif
  manifest state used by the retained source read path. Rebinding the same
  accepted run/generation returns the same retained execution-cache object, so
  motif correction custody cannot be reset by another same-generation bind.
- `EXACT_CACHE`: cache policy/runtime owns lossy exact-cache admission and must
  retain correction custody behind the opaque cache authority, keyed by the
  authenticated binding plus exact stored-artifact digest. Callers cannot mint
  or substitute a fresh empty-queue owner; held/changed/ineligible cache state
  fails closed to exact FP32 recomputation. The only production authority
  issuance path is rooted in authenticated B13 accepted-execution custody;
  the per-generation MAC secret is generated inside that custody while the
  host-provisioned source registry remains outside the public cache boundary.
- `OPERATOR_COMPOSITION`: `SolveContext` owns qualified reusable composition
  custody for the real cognitive-solver path. A neural composition enters that
  custody only after source/generation checks and successful DAG execution,
  then the retained context can reuse it without another neural call. Each
  retained composition binds the exact producing generation digest. If a
  correction is already active when another affected composition is learned,
  that new node joins the same hold queue immediately rather than escaping the
  correction window. No process-global authority is permitted.
- `CAPABILITY_SUPPORT`: accepted B13 generation custody plus source-qualified
  training authority/step-proof provenance owns learned-support
  materialization. The accepted progression entrypoint cold-loads this owner
  from B13 custody and also requires its exact training generation binding to
  equal the current replay generation. Progression may consume current support
  but must not mint it. Immediate dependency indexing includes the source row,
  source-row digest, source release, producing generation, training-batch
  identity and training-authority proof, in addition to retention policy and
  accepted-generation custody.
- Capability-support correction holds are journaled under the exact accepted
  generation/capability custody. A fresh accepted-progression load must
  re-verify and rehydrate the signed hold with the source authority registry,
  or fail closed. A never-deleted correction-seen marker distinguishes an
  uncorrected capability from missing/tampered state; equal and changed
  revalidations persist explicit signed-transition-backed `CLEARED` or
  `REQUALIFICATION_REQUIRED` states rather than authorizing by file deletion.
  The correction-seen commitment is also retained in the canonical Bilqis
  data plane, outside the run-local journal subtree, so deleting both local
  journal files still fails closed. Persisted transitions must bind their
  previous content, eligibility and dependencies to the current materialized
  capability-support node before a cleared or requalification state is
  accepted.
- Signed correction ingress routes only to owners with a direct dependent for
  the corrected dependency. An unrelated correction therefore cannot replace
  another owner's active hold queue.
- The production ingress is the accepted-run signed correction stream owned by
  `SourceExecutionContext.record_correction()`. It verifies the immutable C09
  event, appends it to the accepted run's durable `events.jsonl`, syncs the
  canonical data-plane event ledger, and synchronously delivers it to live
  registered owners. Real Factory compilation registers B11 ATLAS_FEATURE /
  PACKED_FRAME custody; real Factory solver construction registers C04
  OPERATOR_COMPOSITION custody; accepted motif, exact-cache and capability-
  support owners register on bind/load. Cold restart re-establishes the
  host-provisioned source authority and replays the same signed accepted-run
  ledger before those retained artifacts may influence output.
- Source-owner recomputation evidence returns through
  `SourceExecutionContext.record_revalidation()`. Revalidation artifacts are
  signature-verified, must bind an already accepted correction receipt, and
  are appended to the same accepted-run event ledger. Live dispatch advances
  only the owner whose actual next queued task is present in the signed
  frontier; cold replay applies correction and revalidation records in order,
  so a legitimately cleared hold stays cleared after process restart without
  granting the runtime authority to manufacture replacement evidence.
- Production owner nodes carry explicit reuse priorities instead of tie-only
  zeroes. The canonical queue still orders exigency before impact and preserves
  dependency-topology precedence over numeric priority.
- `BamfCompiledBatch` and `SolveContext` validation preserve already-issued
  owner objects; validation never replaces correction custody.
- Generic C09 fixtures are not sufficient evidence unless the corresponding
  production owner/read path is actually connected.

## Changed implementation surface

Review the complete diff from
`origin/codex/bamf-unified-base-20261028...HEAD`, with particular attention to:

- `bilqis_mlx/runtime/_correction/owners/atlas_artifact_owner.py`
- `bilqis_mlx/runtime/_correction/owners/atlas_cache_owner.py`
- `bilqis_mlx/runtime/_correction/owners/atlas_motif_owner.py`
- `bilqis_mlx/runtime/_correction/owners/operator_composition_owner.py`
- `bilqis_mlx/runtime/_correction/owners/atlas_capability_support_owner.py`
- `bilqis_mlx/runtime/_correction/owners/atlas_owner_ingress.py`
- `bilqis_mlx/runtime/_correction/accepted_corrections.py`
- `bilqis_mlx/runtime/_correction/accepted_correction_ledger.py`
- `bilqis_mlx/runtime/_correction/accepted_correction_runtime.py`
- `bilqis_mlx/learning/source_atoms/`
- `bilqis_mlx/learning/frame_encoder/compiled.py`
- `bilqis_mlx/runtime/_model/`
- `bilqis_mlx/runtime/_model/cache/`
- `bilqis_mlx/runtime/cognitive_solver*.py`
- `bilqis_mlx/learning/_retention/atlas_acceptance.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/admission.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/accepted_runtime.py`
- `bilqis_mlx/runtime/_capability/capability_authority.py`
- focused tests under `bilqis_mlx/runtime/tests/correction/`, capability,
  custody, cache, frame-encoder and source-atom test surfaces.
- `bilqis_mlx/runtime/tests/capability/factory/test_cognitive_solver_retention.py`
- `bilqis_mlx/runtime/tests/custody/bamf_bundle/test_accepted_runtime_custody.py`

## Verification receipts before EGM

- Focused C09/custody acceptance suite: `68 passed, 0 failed, 0 skipped` on
  implementation checkpoint `6f75e97affb2d6166c3e11f4ab7c14dba7163ee4`.
- `npm run quality:changed`: development structure OK; governance integrity
  OK; BAMF flow control OK; 15/15 flow-control tests passed; zero new
  changed-file smell findings against reviewed unified. Four inherited
  branch-density/long-function findings remain baseline debt in
  `capability_authority.py` and `cognitive_solver.py` and are not introduced by
  #752.
- `scripts/verify_bamf_0_2_contracts.py`: all 43 issue mirrors matched the
  workstack receipts; all 214 owner/child specs retained indexed identity and
  source fingerprints; no missing/cyclic dependencies. Eight pre-existing
  dependency-normalization holds remain reported by the workstack and are not
  claimed resolved by #752.
- ADR-132 detached `npm run verify:leaf`: **PASS**, return code `0`, source
  snapshot unchanged. Detached source/final snapshot SHA-256:
  `16ede1492b7339d228b44e1717a3326d43d75ee88cfe34c9eb135418705706bb`.
- `git diff --check`: clean.

## Required verdict

Report every finding as Blocker, Major, or Nit with concrete file/symbol
evidence. A clean round means no unsettled Blocker or Major. Do not modify the
candidate. Do not infer acceptance from test count alone: trace all six
artifact kinds into their real producer/consumer ownership and before-use
gate.
