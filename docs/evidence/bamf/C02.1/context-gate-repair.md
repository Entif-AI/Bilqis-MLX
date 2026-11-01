# C02.1 generic Factory eligibility gate: bounded security repair

Issue #490, parent C02 #371, cross-lane A13 parent #354.
**CANDIDATE / independent EGM pending**. No claim of
complete C02.1 Factory/neural integration.

## Reproduced fail-open boundary

The A13 parent independent audit found that
`compile_training_batch` accepted caller-injected
`check_context_eligibility` and `eligible_source_for`
callbacks with untyped task, policy and frontier.
A permissive callback could return a caller-chosen
64-hex digest and compile a model-input row even
when the nominal context was denied. The old
39/39 tests used these same fake callbacks and
did not prove the actual A13 gate.

## Scoped repair

The generic runtime adapter now imports and calls
the actual `check_context_eligibility` authority
directly. It no longer accepts injectable gate or
eligibility-result translation callbacks. It
requires exact A13 `TaskScope`, `SourceFrontier`
and `ContextPolicy` records, nonempty
`ContextEligibility` source envelopes and a
real `EligibleContext` result before constructing
any compiled input. The eligibility digest is
the actual A13 result digest, not a caller string.
The already source-visible AST is compiled only
after this gate passes; no second substitute AST
is accepted.

The tests now issue exact synthetic A13 source
grants with frame/member evidence digests and
rights/correction/temporal scope. They no longer
pretend a Boolean mock is the authority. New
adversaries prove that an injected callback
is rejected by the public API, malformed task
or policy is rejected, revoked or evidence-tampered
grants hold, and an empty or untyped frame adapter
cannot produce an eligible input.

Grade-label permutation changes the executable
release digest, so A13 correctly changes the
release-bound context digest while preserving
the actual source-visible prefix, features,
typed target and delivery provenance. This
is explicit rather than masking a release
identity change as a grade effect.

## Executed evidence

Base: C lane remote
`ead92a6b18b03ae98f549118cfc361d13f33b6b4`,
which already contains reviewed unified
`7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`.
No no-op merge and no shared C-lane writer mutation.

- Baseline provisional adapter: **39/39 passed**
  with fake eligibility callbacks, proving no
  real gate enforcement.
- Repaired owner suite:
  **45 passed, 0 failed, 0 skipped**.
- Repaired adapter plus real A13 context and A05
  compiler suites: **86 passed, 0 failed,
  0 skipped**.
- Static error-control/module-size checks and
  `git diff --check` found no new changed-file
  violations.

## Remaining integration and authority gate

The source AST and `frames_for_ast` bridge is
still a caller-supplied source adapter. A13
validates the exact frame and member evidence,
but this patch does **not independently prove**
that a supplied source AST is canonically
identical to the source-owned frame projection
for every Factory provider. A future
source-owned AST/frame binding must be added
and tested against cross-source substitution.

Therefore C02.1, A13 parent and C02 parent
remain **OPEN**. The full B10/B11 modality,
MLX gradient, F05 neural-logit and live
training acceptance are not claimed.
Independent EGM of this repair is pending.
No source admission, optimizer mutation,
live learner run or self-merge occurred.
