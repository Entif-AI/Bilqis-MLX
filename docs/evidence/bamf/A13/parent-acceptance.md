# A13 parent #354: integration acceptance crosswalk

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
