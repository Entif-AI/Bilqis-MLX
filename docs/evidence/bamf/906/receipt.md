# #906 A13 production temporal context-transition remediation

Issue: #906  
Parent authority: #354 / A13  
Downstream consumer: #752 / C09  
Reviewed unified base: `5f8f3d4b42cc4656020e4427c7d8e822825a36f9`  
Semantic candidate: `ee644401d12275c98e454156fd49193e57e5cead`  
Branch: `codex/bamf02-a-906-temporal-context-20261107`  
Review disposition: `EGM_PENDING`

## Outcome

#906 adds the missing production-side A13 validity producer without changing the
canonical A13 leaf registry or inventing a new correction authority.

The Factory source-context owner can now issue an explicit finite
`SourceContextPolicyWindow`. The declaration is:

- bound to the exact A01 Atlas bundle, semantic release and source bundle;
- bound to principal, tenant, purpose, jurisdiction and scope;
- bound to policy epoch, rights epoch and correction generation;
- expressed as absolute `observed_at`, `effective_from` and
  `effective_until` values rather than a wall-clock TTL;
- sealed by the source-context policy owner and rejected when caller-constructed;
- allowed only to narrow a currently valid source context.

The existing source-row issuer projects that same finite boundary into both
`ContextEligibility` and every issued `SourceGrant`. Existing callers that do
not supply a finite policy window remain exactly timeless
(`effective_until=None`).

`source_lesson_expiry_task(...)` crosses only the explicitly declared
`effective_until` boundary. Moving `observed_frontier` alone cannot manufacture
expiry. Crossing the declared boundary causes A13 `transition_context(...)` to
emit its existing typed `C09ContextInvalidation`; no `CorrectionEvent`, signer,
or alternate event ontology is introduced.

## Scope-drift audit

The remediation exceeded the repository's automatic audit threshold because the
authority record, source-row projection, public export and focused regressions
span seven files. Audit disposition: **DECOMPOSE / PROCEED, no EXPAND**.

Every changed production path serves the single inherited #906 obligation:
declare source/policy-owned finite validity, project it into A13 source grants,
and expose the exact boundary transition. Test changes cover the corresponding
positive, timeless, scope-isolation and non-fabrication behavior. The Lane-A
flow-control change only records writer ownership. No second independent defect,
new acceptance criterion, new source ontology, or new C09 authority was found.

## Focused proof

Local environment used an isolated ignored `.venv` with the repository test
dependencies, Ithkuil semantic requirements, MLX 0.32.4 and NumPy 2.5.4.

- `.venv/bin/python -B scripts/run_tests.py bilqis_mlx/factory/tests/skos/test_source_context.py`
  - 8 passed, 0 failed, 0 skipped.
- `.venv/bin/python -B scripts/run_tests.py bilqis_mlx/semantics/tests/context`
  - 25 passed, 0 failed, 0 skipped.
- `.venv/bin/python -B scripts/run_tests.py bilqis_mlx/semantics/tests/frame_adapters`
  - 16 passed, 0 failed, 0 skipped.
- combined source-context / source-row run:
  - 11 passed, 0 failed, 3 skipped.
  - the three skips are the pre-existing real-A01-artifact tests, including the
    new finite-validity witness, because `BILQIS_A01_ATLAS_BUNDLE` is not
    mounted in this worktree. The tests skip explicitly when absent and fail
    when a mounted artifact is invalid.
- `BILQIS_QUALITY_BASE_REF=origin/codex/bamf-unified-base-20261028 npm run quality:structure`
  - structure and governance integrity PASS.
- `BILQIS_QUALITY_BASE_REF=origin/codex/bamf-unified-base-20261028 npm run quality:changed`
  - six changed Python files scanned, zero new findings;
  - legacy-trainer authority 6/6 PASS;
  - flow-control 15/15 PASS.
- `git diff --check`
  - PASS.

The focused non-skipped source tests use the tracked canonical New Ithkuil CSV
row bytes through the existing `source_row_byte_witness` owner while stubbing
only the unavailable frozen Atlas mount. This is not represented as a replacement
for the separately mount-gated full A01 artifact witness.

## Joined #906 -> #752 production proof

A disposable detached worktree merged semantic candidate
`ee644401d12275c98e454156fd49193e57e5cead` with #752 head
`03e7a3c060bc49962ccfe049417090ea2c1c6ec0`. Disposable merge head:
`95e062191965971681401719467503a6cc2f014b`.

The reusable disposable proof:

1. issued two tracked-source A13 row contexts under one finite
   `SourceContextPolicyWindow`;
2. projected the approved context and retained an actual C09
   `PackedFrameArtifactOwner` whose TIME dependency was that exact context
   digest;
3. registered that owner with #752's accepted-runtime correction target;
4. crossed exactly the declared source validity boundary;
5. called `AcceptedRuntimeHost.record_context_transition(...)`;
6. observed one durable `BAMF_C09_CONTEXT_INVALIDATION` ledger record with no
   correction payload;
7. observed `BAMF_C09_ARTIFACT_HELD` before the retained packed frame could be
   reused;
8. cleared process-local accepted runtime/cache state, re-bound the same accepted
   generation, re-registered the physical owner and observed the same hold after
   cold replay.

Result: `906_752_JOINED_PROOF_OK`.

The native #752 accepted-runtime suite on that same disposable combined
candidate passed 9/9:

`scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/authority/test_accepted_correction_runtime.py`.

No #752 code is merged into the #906 feature branch. The proof worktree is
integration evidence only.

## Safety and authority

- No wall-clock expiry or TTL was derived.
- No observation/evidence timestamp was reinterpreted as a rights expiry.
- No correction signer or `CorrectionEvent` was minted.
- Generic PUBLIC_FORMAL callers remain timeless unless an explicit finite policy
  window is supplied.
- No source release, semantic admission, durable learner, optimizer, teacher,
  champion, checkpoint, or live training state was mutated.
- No merge to reviewed unified was performed.
