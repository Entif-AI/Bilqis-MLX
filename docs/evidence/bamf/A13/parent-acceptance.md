# A13 parent #354: integration acceptance crosswalk

## Current acceptance — 2026-11-11

Baseline: reviewed unified `f9aa79b6cececdedd28a0e80db1256f8a70a9d7f`.
Worktree: existing A13 checkout on `codex/354-a13-prefix-inventory-20261107`,
with the current reviewed unified consumed by merge after the semantic repair.
The exact semantic candidate exercised by the final detached qualification is
`a3bd22c2fb0a0c10da7e3578125ed8c072ef2479`. The later verification-harness
repair is `7d9f11396e4f7ec890b709ed4a4a8184b8b95dfb`; it changes only detached-run
mutation accounting plus its focused regression test, not A13 runtime semantics.
Issue #354 remains open until human review and integration. Focused implementation
verification, independent repair re-audit, the resource-safe final gate, and the
exact-baseline classification of that gate are recorded below.
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
| Atomic input belongs to its row and only the source owner chooses empty frames | Shared `source_frame_inventory` rederives row identity and complete trees from the registered adapter and pinned schema manifest; real-source negatives reject cross-row substitution and same-row frame stripping; Factory preserves genuine B.IDBOOLOPS atomic fallback |
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
raised no error. The initial repair applied the existing lineage validator to both
framed and atomic inputs, preserving the missing-frame error contract. Fresh review
found this still admitted same-row frame stripping; a second RED test reproduced it.
The adapter and Factory bridge now share `source_frame_inventory`: re-enter the
registered adapter, canonical graph, pinned A01 snapshot and A03 schema manifest;
bind the full source row; return its source-instance ID and complete frame trees,
or an empty tuple only when the source tree has no fully released schema representation.
The adapter compares source ID and exact inventory before selecting its framed/atomic
path, then checks visible atom tokens and all admitted envelope roots as before.
Synthetic adapter fixtures explicitly provide their source-inventory oracle; mounted
real-source tests and the Factory witness use the actual owner unmocked.
The cold-replay fixture now uses existing production `publish_genesis` rather
than attempting to replace the generation-zero source authority in a successor.
Four pre-existing evidence documents receive only their omitted provenance
reference; their original check outcomes remain historical.

Observed verification, zero skips in each group:

- Context plus source-context and original adapter selection: **49/49**.
- Complete affected training directory plus adapter: **65/65** after inventory repair.
- Real A/B/C Factory-to-B11 preparation: **1/1**, three capability subcases,
  including a literal all-ATOM assertion for source-owned B.IDBOOLOPS fallback.
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
`quality:changed` passes (structure/governance, changed-file smells, source-authority
guard, 7 authority and 15 flow tests). Final lineage command:
`python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/batch/test_atlas_training_adapter.py bilqis_mlx/runtime/tests/batch/training`.
Factory witness:
`python3 -B scripts/run_tests.py bilqis_mlx.runtime.tests.batch.factory.test_factory_training_bridge.FactoryTrainingBridgeTests.test_current_a_b_c_draws_bind_exact_c02_rows_into_b11`.
The aggregate `npm run verify:premerge` was executed by the resource-safe r3 gate
described below. Its absolute repository result is red because reviewed unified is
already red on the same failure families; no branch-owned A13 regression was found.

The first detached differential-leaf/premerge attempt on 2026-11-11 is **not**
acceptance evidence. It launched the dependency-selected MLX-capable leaf under
four pytest-xdist workers. On the 96 GiB Studio, installed MLX 0.31.1 exposed a
default memory/free-buffer-cache allowance of about 91.2 GiB per process, so the
four-worker topology admitted roughly 364.8 GiB of aggregate MLX-managed demand.
macOS produced repeated out-of-memory warnings, swap reached about 65.2 GiB used,
workers died, and the owned process group was terminated to protect the host.
ADR-138 and the corresponding root `AGENTS.md` rules now require MLX-capable
verification to run serially unless an explicit aggregate budget is enforced.
The replacement gate must therefore run with one worker, MLX free-buffer caching
disabled in the long-lived test process, and an explicit bounded MLX test memory
limit. The failed parallel run is preserved as a resource incident, not classified
as an A13 semantic regression.

### Resource-safe final gate r3 and exact-baseline classification

Detached r3 ran from semantic candidate `a3bd22c2fb0a0c10da7e3578125ed8c072ef2479`
against reviewed unified `f9aa79b6cececdedd28a0e80db1256f8a70a9d7f`, with
`BILQIS_TEST_WORKERS=1`, MLX free-buffer cache disabled, an explicit 24 GiB MLX
memory limit inherited by Python children, and the accepted A01 artifact mounted.
The run completed without the prior OOM/worker-death failure mode.

The differential leaf executed the selected 283-file cone and reported **1327
passed, 93 failed, 2 errors, 12 skipped, 559 subtests passed**. The aggregate
premerge then executed 4118 tests and reported **3963 passed, 4 assertion failures,
92 errors, 59 skipped**. Both command exits were nonzero. These absolute red totals
are not being relabelled as green.

Classification is against the exact reviewed-unified commit, not against a guessed
historical baseline. Earlier recovery already reproduced nine sampled
custody/source-authority failures identically on pristine `f9aa79b6`. After r3, a
fresh tracked-only archive of exact `f9aa79b6` was run under the same cache-zero /
24 GiB MLX limit for six discriminating failures spanning every assertion-failure
family plus representative C09 and Factory error families. All six failed on
pristine unified with the same observed reasons:

- learning owner inventory: expected 42, observed 49;
- importing `bilqis_mlx.learning` eagerly imports `mlx`;
- generic BAMF publication returns `BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID`
  where the test expects `BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED`;
- public facade late-binding reports the same unresolved prefix-inventory routes;
- accepted A13 correction-runtime fixture fails at publication with
  `BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID`;
- Factory training-execution fixture fails at publication with
  `BAMF_INITIAL_GENERATION_BOOTSTRAP_REQUIRED`.

The aggregate error population is dominated by those same inherited custody/
bootstrap families: 72 `SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID` errors, plus
missing historical runtime state and five imports of the already-absent
`bilqis_mlx.runtime.bamf_bundle.vocabulary_registry_export`. Both the legacy state
and that module are absent from pristine `f9aa79b6` as well. None of the four A13
production files changed by this candidate appears in an r3 failure traceback;
their only r3 log occurrence is the test-selection command. The exact focused A13
proof above remains green and the independent source-inventory re-audit remains
PASS — 0 Blockers / 0 Majors / 0 Nits.

R3 also exposed a verification-harness defect unrelated to A13 semantics. The
detached snapshot created ordinary ignored `runs/` and `vendor/legacy-v16/runs/`
runtime state, so the mutation guard reported `source_mutated=true` and overrode
the command return with exit 86 even though the actual feature worktree remained
Git-clean. Existing ignored historical `runs` data must still be copied into a
snapshot when present, so the repair does not exclude `runs` from snapshot input.
Instead `7d9f11396e4f7ec890b709ed4a4a8184b8b95dfb` excludes `runs` only from the
post-command mutation guard. A focused regression failed before the repair with
exit 86, then the complete detached-runner suite passed **6/6** after it; `git
diff --check` also passed.

Disposition: r3 is an **absolute repository-gate failure with zero identified
#354-owned failures**. Its inherited failures remain baseline debt and are not
repaired or masked in A13. Its false snapshot-mutation classification is repaired
in the verification harness. This evidence is sufficient to classify the A13
candidate as differential-clean relative to the exact reviewed unified baseline;
it is not a claim that `f9aa79b6` itself has a green repository-wide premerge.

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
