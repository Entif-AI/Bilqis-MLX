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
- Candidate branch: `codex/752-egm-complete-20261106`

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
  manifest state used by the retained source read path.
- `EXACT_CACHE`: cache policy/runtime owns lossy exact-cache admission and must
  retain correction custody behind the opaque cache authority, keyed by the
  authenticated binding plus exact stored-artifact digest. Callers cannot mint
  or substitute a fresh empty-queue owner; held/changed/ineligible cache state
  fails closed to exact FP32 recomputation.
- `OPERATOR_COMPOSITION`: `SolveContext` owns qualified reusable composition
  custody for the real cognitive-solver path. A neural composition enters that
  custody only after source/generation checks and successful DAG execution,
  then the retained context can reuse it without another neural call. No
  process-global authority is permitted.
- `CAPABILITY_SUPPORT`: accepted B13 generation custody plus source-qualified
  training authority/step-proof provenance owns learned-support
  materialization. The accepted progression entrypoint cold-loads this owner
  from B13 custody and also requires its exact training generation binding to
  equal the current replay generation. Progression may consume current support
  but must not mint it.
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
- `bilqis_mlx/learning/source_atoms/`
- `bilqis_mlx/learning/frame_encoder/compiled.py`
- `bilqis_mlx/runtime/_model/`
- `bilqis_mlx/runtime/_model/cache/`
- `bilqis_mlx/runtime/cognitive_solver*.py`
- `bilqis_mlx/learning/_retention/atlas_acceptance.py`
- `bilqis_mlx/runtime/_custody/bamf_bundle/admission.py`
- `bilqis_mlx/runtime/_capability/capability_authority.py`
- focused tests under `bilqis_mlx/runtime/tests/correction/`, capability,
  custody, cache, frame-encoder and source-atom test surfaces.

## Verification receipts before EGM

- Focused C09/custody acceptance suite: `89 passed, 0 failed, 0 skipped`.
- `npm run quality:changed`: development structure OK; governance integrity
  OK; BAMF flow control OK; 15/15 flow-control tests passed; zero new
  changed-file smell findings.
- `scripts/verify_bamf_0_2_contracts.py`: all 43 issue mirrors matched the
  workstack receipts; all 214 owner/child specs retained indexed identity and
  source fingerprints; no missing/cyclic dependencies. Eight pre-existing
  dependency-normalization holds remain reported by the workstack and are not
  claimed resolved by #752.
- `git diff --check`: clean.

## Required verdict

Report every finding as Blocker, Major, or Nit with concrete file/symbol
evidence. A clean round means no unsettled Blocker or Major. Do not modify the
candidate. Do not infer acceptance from test count alone: trace all six
artifact kinds into their real producer/consumer ownership and before-use
gate.
