# C07.1a — persisted lease contracts and unleased staging protection

Leaf status: **PARTIAL_PENDING_UPSTREAM_AND_C07.1b**. The bounded software slice
is implemented/reviewed; this is not complete #509 acceptance or actual admission.
IPR-0220. Lane codex/bamf02-c-runtime; base357aa3a136b091107f908f7c821cceed72832e41.
Consumed reviewed unified7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4, unchanged on fetch.
PR #550 remains draft/unmerged; #509 and parent #508 remain open.

## Implemented slice

`AtlasAdmissionLease` binds a path-independent lineage/initial-generation identity,
native BAMF topology digest and origin Checkpoint, exact approved Atlas digest,
source-family/operator sets, rights receipt/epoch, distinct prerequisite and
progression policy digests, authority-audit receipt/pass, resource ceilings and
explicit human-request identity/time. Operator sets may be empty for lookup-only
scope. Initial versioned delta budget is at most9 capabilities/16 new semantic
identities; separately approved policy versions can change the identity budget.
Bank/page count, total allocated semantic identities and disk/memory bytes are
separate post-admission totals, not per-delta budgets or semantic capacity limits.

All A09/A12/run-owner projections are explicitly C-owned DISPOSABLE_CONTRACT
records. Actual C09 scoped Ed25519 verification is reused. These are not claimed
A09/A12/B13 runtime classes or production-qualified authority. Fixture lease
persistence refuses existing saved learner custody and unsafe paths. It uses the
existing durable JSON writer, content-addressed immutable records, an immutable
current reference, exact verified reload and independently supplied run identity.
Same lease is idempotent; unequal renewal, copied identity, missing/tampered
reference and scope/signature mismatch fail closed. Current references cannot
silently degrade into no-lease staging.

The policy adapter validates actual native CurriculumDeltaProposal and exact
StagedCandidate through resolve_ready_candidate. Signed scope/envelope bindings
cover declared families/operators/resource totals. Run, source/rights, policy,
post-total resource ceilings and per-delta budgets precede the executor boundary.
Authorized fixtures truthfully return STAGED/ADOPTION_EXECUTOR_UNAVAILABLE.
No arbitrary callback can claim admission or publish a generation.

Native CLI adds --admission-policy {staged,atlas-release} and
--atlas-admission-scope. Explicit requests validate human selection/file/schema,
then reject unavailable accepted run authority before topology/learner
initialization or lease writes. This is not a working production BAMF command.

The actual operating_loop PROPOSAL branch now calls the staging helper, records
its idempotent decision and stops the frontier attempt. It cannot repeatedly
propose the same staged delta in that loop. No unleased _adopt_jit_proposal call
remains at that callsite, including the old unleased #296 flywheel. Known profile
transitions retain their separate existing path. The concrete native
_adopt_jit_proposal/_adopt_prepared_successor chain remains for #510 integration.
The new ATLAS_ADMISSION_STAGED stop term and error category are registered.

## Proof and review

`tests.txt`: **11 new tests pass**, zero failures/errors/skips. Native helper proof
plus static callsite inspection establishes unleased routing; tests do not invoke
operate. The three-proposal witness changes checkpoint step under the same current
release/staged candidate and lease. It proves repeated proposal evaluation, not
three distinct admitted successors or resume after second committed admission.

`owner-tests.txt`: **57 passed,2 errors**. Both environment errors require unavailable
mlx: PreparedSuccessorTests.test_append_only_materialization_preserves_native_rows_moments_and_frontier
and test_same_grade_native_growth_adopts_exact_staged_release_without_append_grade.
No affected owner suite is claimed fully green.

Fresh Goldfish /root/c07_1a_goldfish used pinned Google EGM
b3a35956759bf7f024af2ff061b2e0b44b438e4c. Cold interface concerns were resolved
before implementation. Bounded turn-in PASS, no blocker/major. Reviewer inspected
source,11-test and57-pass/2-error receipts; reviewer executed no tests.

## Exact remaining ownership

#509 clause3 committed adoption and actual run-backed lease enrollment remain
pending accepted A09/A12/B13 authority plus #510's sole concrete adoption executor.
#510 must recheck current checkpoint/step, source/answer implementations, source
frontier and lease immediately before native adoption. It must consume the actual
prepared-successor transaction, then prove disposable repeated successors and
resume without duplicate allocation. #509 authorization is not a reusable token.
C07.2/.3 retain their release/debt/history and recursive frontier obligations.

No actual trainer, persistent student/own AdamW, graph or accepted generation was
read or changed. Actual backend/custody and disposable serialized MLX proofs remain
pending. Do not convert this partial receipt to completion until those boundaries
are implemented and requalified. Continue C07.1b #510.
