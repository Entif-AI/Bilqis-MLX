# Frozen Factory learning qualification

Issue #324 qualifies the existing semantic workload under two controlled topologies.
Its prerequisites use exact-head engineering evidence. Open/draft/unmerged lifecycle
states do not block this lane and do not grant merge authority.

`runtime.qualification_manifest` validates immutable, content-addressed inputs before
model allocation. `runtime.qualification` uses the existing operator loop and profile
admission transactions. `runtime.qualification_results` performs inference only after
the finite training session. There is no parallel trainer or new learned selector.

The manifest binds an exact executable commit, production source hashes, prerequisite
heads, runtime/library versions, source files, a source-qualified FactoryRelease chain,
semantic graph and ABI, workload, policy controls/epochs, optimizer, initialization and
training seeds, two typed topologies, fixed evaluation fixtures and finite budgets.
The expected manifest digest is supplied independently on every invocation.

Both arms start with fresh seeded FP32 weights and zero native AdamW moments. The
historical model supplies source/optimizer configuration provenance only; neither its
weights nor moments initialize these arms. Historical teacher state is independently
pinned and inherited identically in both arms. Training RNG uses the same explicit
seed namespace without conflating the distinct run identities.

The released workload is staged through A, A+B and A+B+C prefixes. Initial assessments
cover only A. Existing prerequisite, promotion, debt and profile-admission rules govern
activation of each later prefix. Each prefix is source-qualified before freezing;
the semantic graph and the final numeric input ceiling remain fixed. Only these
predeclared same-ABI releases may be adopted. No Grade D, new source family, numeric
widening or SKOS intake enters qualification.

## Operator boundary

Run `python3 -B -m bilqis_mlx.runtime.qualification --manifest PATH --arm NAME
--expected-digest SHA --dry-run` from the pinned execution checkout. Without an explicit
`--human-run`, this command validates and exits with zero optimizer updates. Dry-run
wins even if both flags are present. It does not create a run directory. Launch has
no policy, topology, budget or scope override flags. Preflight also checks current
remote prerequisite heads, runtime environment, storage isolation and disk reserve.
A superseded head requires a new validated freeze, not a silent substitution.

Only the human supplies `--human-run` for a reviewed arm. The existing loop enforces
finite visits and its normal session time boundary; each candidate horizon is capped
by the frozen configured steps. The wall limit is soft at safe boundaries: due exams
and checkpoint publication finish. The manifest records this explicitly. The 100 GiB
reserve remains active. Finite post-session evaluation has its own row/draw ceilings.

Each arm is a fresh, independent current-Factory run. Reusing a populated target fails
before initialization. The qualification launcher deliberately offers no automatic
resume or budget refund. An interrupted arm retains its exact checkpoints/outbox for
inspection and requires an explicit experiment-epoch decision before continuation;
ordinary trainer resume must not be used to bypass qualification budgets.

## Scoring and diagnosis

The current promotion rule starts acquisition above the arithmetic mean threshold
and requires the running/post-acquisition mean at or above it. The manifest reads the
actual `PROMOTION_MEAN_FLOOR`; it does not redefine graduation or forgive debt.

After the fixed training budget, full-workload introduction is checked before any
unintroduced capability is examined. One frozen acquisition fixture must pass, then
three independently seeded full-workload sweeps preserve the declared target-grade
criterion. Per-capability predecessor and target results remain visible. This fixed
terminal design adds no active early stopping or teacher reward.

Each post sweep also draws bounded independent source probes. Exact training inputs
and labels are compared using capability/tokens/gold/answer-kind, rather than seeded
row IDs. Fresh probes exclude those already delivered inputs; no teaching item is
embargoed. Each post sweep requires fresh target witnesses; exhausted per-capability scopes
remain unmeasured. The full-grade mean remains the qualification criterion. Ordinary sweep overlap counts remain visible.
Scoring inference remains the existing student-only API. Qualification evaluation
never updates an optimizer, teacher, scheduler or champion.

#333 observations retain proposals, ordered realized batches, role/multiplicity,
source/provider identities, staged outcomes, explicit missingness, actual candidate
costs and durable checkpoint joins. Existing routine exams/events provide acquisition,
proficiency, debt, scheduling and resource history. Compare topology arms only within
their frozen policy/release partitions. A low-yield pattern can support competing
capacity, policy/runtime, interference or gate hypotheses; it does not prove one by
itself. Missing predictions, calibration, shadows and device metrics remain unmeasured.

The final result is `QUALIFIED` or `NOT_QUALIFIED` only after actual human runs.
Disposable tests and a valid manifest establish engineering readiness, not learning.
IPR-0220, source/oracle independence, custody and human-owned neural initiation apply.
