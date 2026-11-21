# Issue #1504 | BAMF production throughput restoration

## Problem

The real four-row BAMF training path regressed from the previously demonstrated
roughly 10-second class to sustained 41-46 second candidate steps. The vectorized
path is still active: one gradient launch, one vectorized microbatch, zero scalar
fallback rows. The regression is redundant hot-path work around that neural step,
not a return to four scalar training launches.

Live evidence from the `aspirant` run showed, over one four-step visit:

- `candidate_identity_binding_reuses = 0`
- `candidate_identity_full_computations = 24`
- `candidate_identity_numerical_bytes_hashed = 22892358336`
- `candidate_identity_full_hash_wall_seconds = 15.73613845789805`

Representative current timing also shows B11 preflight around 10.3-11.3 seconds,
B11 autodiff around 10.3-11.2 seconds, and C08 logical-batch wall around
25.7-27.9 seconds. These spans are nested and must not be added as independent
serial costs.

## Existing authority and prior proof

Issue #1238 established the candidate-identity contract: a cold accepted-state
load may pay for one canonical full proof, then same-process consumers reuse an
immutable process-local binding instead of rescanning parameter and optimizer
bytes. Its receipt records one cold full computation and zero full computations
for same-process accepted publication.

The repair MUST reuse the existing `CandidateIdentityBinding` lifecycle rather
than add a digest/object memoization side channel. Owner-protected BINDABLE state,
UNBINDABLE/unsupported-runtime canonical fallback, stale or poisoned binding
rejection, durable expected-digest checking, and mutation/currentness guards stay
fail-closed exactly as #1238 specified.

Issue #1388 establishes the missing apples-to-apples live performance anchor. Its
2026-11-17 `trainer-observed/v5` B.COMPOSITE trace recorded a four-row production
candidate path at about **9.78 seconds median full optimizer step**, with about
4.09 seconds median `b11_autodiff_wall_seconds`, 5.35 seconds median
`c08_logical_batch_wall_seconds`, 0.027 seconds median
`b11_preflight_wall_seconds`, approximately 49 compiled positions, one gradient
launch, one vectorized microbatch, and zero scalar fallbacks. The same issue's
later isolated MLX 0.32.4 throughput witness measured focused B11 preflight at
about 0.20 seconds and B11 autodiff/evidence at about 2.29 seconds. Its cold
disposable full candidate-step median was 33.6231 seconds because that fixture also
paid fresh-run source compilation; it is not the warm production-step baseline.

The current live trainer is on MLX 0.31.1. That version difference may matter to
the remaining neural delta, but #1238 already passed identity-binding tests on
both 0.31.1 and 0.32.4, so it cannot explain the observed zero binding reuses.

The closest retained warm production-shaped planning baseline is #1171: the same
live-fixture `select_foundation_priority_visit(...)` entrypoint reported warm
samples of 10.081268 s, 9.823177 s and 10.296672 s, median 10.081268 s, with a
predeclared ceiling of 15.088 s. This is a pre-neural planning witness, not a
claim that #1388's disposable cold full candidate-step fixture was 10 seconds.

## Required repair

### Candidate-identity callsite classification

Before reducing full-hash counts, classify each observed computation by authority:

- **Current accepted generation, same process:** `accepted_execution_cache` is the
  owner for warm in-process consumers. Checkpoint projection, current Factory/
  obligation reads, cadence replay and current-support census MUST reuse an already
  authenticated hydration/binding when one exists. They fall back to the canonical
  cold proof when no process-local hydration has yet been established.
- **Canonical public acceptance/publication boundary:** `accepted_generation(...)`
  and `load_bamf_generation_authority(...)` remain independently validating cold
  proof surfaces. They MUST continue to reject acceptance loss, re-signed drift and
  synthetic run-identity drift even though the ordinary warm operator path avoids
  repeatedly re-entering them.
- **Historical accepted ancestor:** an independently loaded immutable ancestor may
  require its own canonical proof. The repair does not turn historical lineage
  traversal into current-object aliasing.
- **New retained candidate:** the candidate pays one canonical full computation when
  its owner first binds that new immutable state; downstream teacher/successor
  consumers reuse that binding and add no second scan.
- **Admission/publication/currentness proof boundary:** raw digest use remains legal
  where that owner is proving independently loaded state rather than consuming an
  already-issued binding. These callsites are not subject to blanket replacement.

The focused regression therefore has two numeric oracles: the already-bound parent
path adds 0 full computations / 0 numerical bytes through priority selection and
candidate currentness; a newly changed retained candidate adds exactly 1 full
computation when bound, after which C03 successor custody adds 0 further full
computations / bytes.

1. Preserve the canonical full candidate-identity proof at real proof boundaries.
2. Restore reuse for same-process consumers that already operate on the exact
   bound immutable state. Do not globally replace `candidate_identity_digest`.
3. Add a focused regression that exercises the operator/currentness/teacher
   ownership path and proves expensive identity multiplicity cannot return.
   For one already-bound accepted parent, same-process projection/currentness/
   teacher consumers MUST add zero full candidate-identity computations and zero
   numerical bytes hashed; at least one binding validation/reuse MUST be observed.
   A cold bind remains allowed exactly one full computation for that immutable
   state. A reduction from 24 full computations to merely fewer repeated scans
   is not acceptance.
4. Add low-overhead B11 preflight subspan/counter telemetry before changing
   semantic preparation work. At minimum distinguish execution rebinding,
   refinement selection / prefix-context preparation, route preparation, and
   remaining preflight.
5. Remove repeated row-common semantic preparation only when source identity,
   accepted/currentness authority, exact causal context, and refinement-policy
   inputs prove the work equivalent.
6. Preserve one gradient launch, one vectorized microbatch, zero scalar fallback,
   source-gold independence, custody, currentness, candidate atomicity, and
   fail-closed mismatch behavior.

## Performance qualification

Reopened acceptance tightens the candidate-step target to **<=1.000 second** on
the real operator path where physically achievable. The witness MUST include
terminal publication/staging mechanics owned by the candidate path; a non-terminal
or prepared-owner surrogate cannot satisfy this gate. If the target is not reached,
the remaining wall must be covered by a non-overlapping millisecond-level necessity
ledger rather than waived by the earlier roughly ten-second baseline.

Deterministic regression gates should enforce expensive-work multiplicity rather
than brittle heterogeneous-CI wall time. Final acceptance also requires one
production-shaped, disposable four-row timing witness recording the exact frozen
implementation commit containing the runtime code under test, topology/extents,
row and compiled-position counts, MLX/MLX-Metal/Python
versions, machine class, total candidate-step wall, pre-neural source/compile,
currentness/binding, B11 subspans, C08 wall, optimizer/admission/publication,
identity full-hash/reuse/byte counters, gradient launches, vectorized
microbatches, and scalar fallbacks. The receipt MUST distinguish nested spans
from serial owner spans so no timing is double-counted.

Do not run a competing full-model MLX witness while the sovereign live trainer is
active. Any local witness plausibly exceeding five minutes uses the repository's
detached long-run wrapper and durable receipt path.

## Acceptance

- The real operator path reuses candidate identity after the one justified cold
  proof: same-process hot-path consumers add exactly 0 full computations and 0
  numerical identity bytes for the already-bound immutable parent, with binding
  validation/reuse observed.
- #1238 mutation, stale-binding, poisoned-binding, unsupported-runtime fallback,
  and cold expected-identity regressions remain green. The binding capability
  remains valid on both the installed 0.31.1 line and an isolated 0.32.4 line
  before turn-in; the live trainer environment is never mutated to obtain this.
- B11 preflight cost has attributable subspans and any removed repeated work is
  guarded by exact authority/context identity.
- The four-row production-shaped path remains one-launch vectorized with zero
  scalar fallback rows.
- The retained warm production-shaped planning workload is <= 15.088 seconds
  median on the same M3 Ultra class host, with ~10.08 seconds as the historical
  planning reference. The stronger end-to-end target is the #1388 live
  B.COMPOSITE four-row production baseline: about 9.78 seconds median full optimizer
  step at ~49 compiled positions, one launch, one vectorized microbatch and zero
  scalar fallback. The final #1504 witness must return the matched warm workload to
  that roughly 10-second class or better. This historical requirement is now a
  lower bar than the reopened acceptance gate: the real terminal operator candidate
  must be <=1.000 second where physically achievable.
- No correctness, custody, provenance, currentness, source, retention, or
  fail-closed invariant is weakened.
