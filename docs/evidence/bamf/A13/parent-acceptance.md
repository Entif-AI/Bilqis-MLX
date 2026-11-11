# A13 parent #354: integration acceptance crosswalk

## Current acceptance — 2026-11-11

Baseline: reviewed unified `036e0aa3c2bec184481a4f009d8c31e16b9495f5`.
Worktree: existing A13 checkout on `codex/354-a13-prefix-inventory-20261107`,
fast-forwarded from `efcaf2d4` to that baseline before changes.
Issue #354 remains open until human review and integration; implementation
verification is complete below, and independent turn-in review is pending.
The earlier audit preserved below is historical and its callback-bypass finding
has been repaired in the consumed baseline.

### Reconciled owner contracts

Original children #430/#431/#432 and remediation follow-ons #906/#916/#956
are closed. A03 #349 is closed. The integrated C02 source-lineage implementation
is `253efc4c2a554f4af9a3f789e8491129b21115cc`; A13/A05 prefix ownership includes
`37417f9e80921e0b9be040eaf48da8f0940e8ed9`; current schema-right issuance is
`349da6d3dcb67e9b710d080c82ba410ff84aca50`. These are consumed source,
not new admissions or neural-learning receipts.

| A13 obligation | Current implementation and executable evidence |
| --- | --- |
| Individual and combined joins, including forbidden pairs/sets | `check_context_eligibility`; context suite rejects individually legal frames in forbidden combinations before projection |
| Source rights, purpose, release, temporal and prefix checks | `_context_eligibility` gate/projection; context suite checks revocation, future constituents, actor/scope isolation and missing member evidence |
| Immutable approved projection and cache identity | `project_context`, `ApprovedContextProjection`; order-invariant membership digest, preserved frame/member ordering and distinct policy/time keys |
| Existing PUBLIC_FORMAL A/B/C constructors without NLP/network | `test_real_public_formal_a_b_c_source_constructors`; genuine registered constructors with synthetic actors/scopes |
| Factory source AST/frame equivalence before A05/B11 input | `require_source_lineage` and production `prepare_factory_training_batch`; cross-source/frame negatives, real pinned-A01 positive and A/B/C Factory-to-B11 witness |
| Atomic input also belongs to the delivered row | `test_granted_atomic_prefix_must_match_the_delivered_source_row`; canonical atomic rows pass; another already-granted row's atomic AST rejects with `CONTEXT_SOURCE_LINEAGE_MISMATCH` |
| Eligibility changes emit typed C09 invalidations | source-context tests exercise owner-issued expiry/revocation; accepted-context temporal test cold-reads the exact four source-owned times and event identity |
| Current schema-right state survives fresh/cold preparation | `test_public_formal_schema_rights_owner.py` exercises revoked grants, cold owner reissue, distinct epochs and invalid restoration |
| Motif reads preserve hidden state when held | seven `test_numerical.py` cases exercise exact/structural hits, missing/revoked grants, nested-child revocation and unavailable-scope safe returns |

The source schemas remain `bilqis.context-eligibility/v1`,
`bilqis.context-source-frontier/v1`, `bilqis.context-task-scope/v1`,
`bilqis.context-policy/v1`; approved/held outputs remain
`bilqis.eligible-context/v1`, `bilqis.context-hold/v1` and
`bilqis.context-approved-projection/v1`. Existing C09 v1/v2 compatibility
is retained. No schema, token identity, semantic meaning or teacher policy changes.

### Correction and proof

Incident **PM-2026-11-11-001** was filed and native-Sheet read back before repair.
The new real-source regression failed because the atomic cross-row substitution
raised no error. The adapter now applies its existing lineage validator to both
framed and atomic inputs, preserving the missing-frame error contract.
The cold-replay fixture now uses existing production `publish_genesis` rather
than attempting to replace the generation-zero source authority in a successor.
Three pre-existing evidence documents receive only their omitted provenance
reference; their original check outcomes remain historical.

Observed verification, zero skips in each group:

- Context plus source-context and original adapter selection: **49/49**.
- Complete affected training directory plus adapter: **64/64**.
- Real A/B/C Factory-to-B11 preparation: **1/1**, three capability subcases.
- Motif numerical reads: **7/7**.
- Accepted-context temporal identity/cold read: **2/2** after fixture correction.

Full commands, original RED and failed-fixture receipts are preserved locally in
`.local/a13-completion-20261111/`. Pinned A01 bundle
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`, release
`58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`, source bundle
`f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`
were mounted for real-source tests. Environment variables are
`BILQIS_ATLAS_REAL_ARTIFACT` and `BILQIS_A01_ATLAS_BUNDLE`.
Use `scripts/run_tests.py` with the paths/test names above; the source-only
Python 3.13 environment ran the first group and initial RED/GREEN, and native
Python 3.14/MLX 0.31.1 on the Studio ran the final training/integration groups.

The current legacy-trainer adaptation authority remains the preserved Factory replay
`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`.
The ABI guard passes with zero scattered literals; external expected fingerprint
is absent locally, so enforcement remains advisory. No actual learner,
optimizer, teacher, original checkpoint or human-run was changed. IPR-0220
remains open for its broader coverage/learning obligations; actual retained
learning is unmeasured by this source/integration proof. Human merge is required.

## Historical parent audit (preserved)

Status: **EGM MAJOR / parent acceptance blocked**.
This is a parent-level evidence reconciliation, not a new A13
implementation, source admission, learner run or merge approval.

## Immutable integration context

- Lane A source head at audit start:
  `9fa752b6410c8248aa784a361247a8a7230fb748`.
- Reviewed unified source:
  `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`,
  already an ancestor of Lane A. No redundant merge.
- Reviewed implementation landed through human-merged PR #546;
  all three A13 children #430, #431, #432 are CLOSED with
  individual immutable EGM PASS receipts in
  `docs/evidence/bamf/A13/egm.md`.
- Original owner contract: A13 #354, with direct A03 dependency #349.
  A03's closed leaves and reviewed implementation are present in
  unified; A03 parent closure remains a separate integration audit.

## Original parent acceptance: executable crosswalk

| Original A13 obligation | Actual boundary and discriminating proof |
| --- | --- |
| Two individually legal frames with forbidden joint scope produce ContextHold before pooling or lookup | `check_context_eligibility`; `test_individually_allowed_frames_cannot_bypass_forbidden_pair_join`, `test_all_pairs_do_not_override_a_forbidden_three_frame_set` |
| Revocation invalidates an approved view; unrelated grants do not spuriously invalidate | `project_context` and `transition_context`; `test_revocation_and_missing_member_grant_hold_before_readout`, `test_c09_revocation_and_policy_time_changes_emit_exact_local_receipts`, `test_unrelated_source_grant_does_not_invalidate_approved_context` |
| Policy/time frontier changes have distinct cache identity | `EligibleContext.digest`, `ApprovedContextProjection`; `test_time_and_policy_changes_produce_distinct_cache_identities` |
| A future constituent never receives an eligible handle | `check_context_eligibility`; `test_invisible_constituent_and_future_source_are_never_eligible`, `test_public_formal_future_prefix_never_mints_handles` |
| Existing direct formal A/B/C source constructors work without NLP/network | `frame_adapters` and source-owned PUBLIC_FORMAL grant path; `test_real_public_formal_a_b_c_source_constructors` |
| Full-set positive digest is invariant to input enumeration order while member/source order survives | `check_context_eligibility`; `test_public_formal_full_set_is_order_invariant_but_members_keep_order` |
| Purpose, release, principal/tenant, jurisdiction, scope and source evidence must be checked before use | `project_context`, `check_context_eligibility`, `transition_context`; `test_release_purpose_and_rights_are_independent_denial_reasons`, `test_c09_public_fixture_actor_and_scope_isolation`, `test_source_locus_tampering_is_detected_even_when_content_id_is_same` |
| Local invalidation events are typed, correction-safe and do not mutate the learner | `C09ContextInvalidation`, `ContextTransition`, `transition_context`; `test_c09_boundary_rejects_malformed_event`, `test_c09_transition_is_pure_and_unchanged_or_reordered_views_do_not_invalidate` |
| Approved context is the sole public input to frame compilation and exact operators | `frame_compiler.compile_prefix` consumes `project_context`; `cognitive_operators.execute_pure` consumes `check_context_eligibility`; `test_revoked_frame_grant_blocks_closure_not_raw_atom_prefix`. **Generic Factory runtime path is NOT yet proven: see Major below.** |

The broader shared-contract text on Rosetta/Akasha durable outbox,
reverse dependency graph and external projections belongs to the
declared C09 and existing-owner integration boundaries. A13.3 emits
pure local C09 events and **does not claim** to deliver the durable
outbox, mutate external graph state or prove B08 neural motif reads.
The downstream B08/B11/C13 integration and F05 logit-equivalence
witness remain separate, not silently accepted by this parent audit.

## Fresh prime executable evidence

At the reviewed unified worktree, using
`/Users/emilie/Code/bamf-planning-20261027/.venv/bin/python`:

- `python -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_context_eligibility.py`:
  **21 passed, 0 failed, 0 skipped**.
- `python -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_compiler.py`:
  **20 passed, 0 failed, 0 skipped**.
- Combined context, frame-compiler and cognitive-operator owner suites:
  **64 passed, 0 failed, 0 skipped**.

These are observed source-level and pure-boundary results, not proof
of live neural execution or independent parent EGM. The reviewer must
check original parent acceptance against these tests and current
implementation before the parent is eligible for closure.

## Independent parent EGM: one integration Major

Fresh-context Goldfish worker-11 independently inspected immutable
`9fa752b` and executed **114/114** combined context, adapter,
compiler, operator and Factory adapter tests. It found one
**Major** outside the six local acceptance examples:

- `bilqis_mlx/runtime/atlas_training_adapter.py:142-153,227-235`
  accepts arbitrary caller-provided eligibility and source-check
  functions, with untyped task/frontier/policy. A permissive callback
  can return a caller-selected 64-hex digest and allow a model-input
  row even when the nominal eligibility policy denies access.
- Independent negative reproduction passed a fake
  `check_context_eligibility` and `eligible_source_for` with
  `eligibility_policy='DENY'`, malformed task and revoked/unknown
  frontier, and observed **one compiled row** with the injected
  eligibility digest. Existing adapter tests use injected mocks,
  so their denial case does not prove real A13 enforcement.

This is a genuine **generic Factory-path authority bypass** and
prevents A13 parent EGM PASS or closure, despite all three child
EGM PASS receipts and the green local suites. The fix must bind
the runtime adapter to the actual A13 source-owned gate, enforce
typed task/frontier/policy and fail closed on unsupported context.
The runtime adapter is a shared Lane C coordination surface:
do not silently mutate it in this Lane A documentation-only audit.

## Remaining gate

Route the Factory adapter Major to the shared runtime owner,
add an adversarial fail-closed regression using the real A13
gate, and obtain a fresh independent re-review after the
runtime integration lands. Parent #354 stays OPEN. This
documentation candidate can be reviewed separately; it
does not grant code merge, source admission or learner authority.
