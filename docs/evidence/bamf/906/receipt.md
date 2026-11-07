# #906 A13 production temporal context-transition remediation

Issue: #906
Parent authority: #354 / A13
Downstream consumer: #752 / C09
Reviewed unified base: `9301e41ef215b9d035449c3260c7cd0f8ee0b5a7`
Semantic repair commit: `3b80a76c`
Current synchronized branch head before evidence commit: `db27df4abb9471b1593da36e86401b636ec5d09a`
Branch: `codex/bamf02-a-906-temporal-context-20261107`
Review disposition: `EGM_FAILED_ROUND_1_REPAIRED_PENDING_REAUDIT`

## Outcome

#906 now supplies the missing production-side A13 temporal authority without
changing the canonical A13 leaf registry or inventing correction authority.

The Factory source-context owner issues an opaque
`SourceContextTransitionAuthority` for the pinned A01 source. Ordinary callers
supply only `AtlasArtifactSelection`. They cannot choose the task, policy,
frontier, current effective time, or validity window.

The authority is derived from
`source_context_transition_policy_v1.json`, whose exact bytes are pinned in
code by SHA-256
`6ac59c878f5e1ce5f0fafca4710669626b3e357d60b4c5d02edaee29f31d1ea9`.
The registry binds the A01 Atlas bundle, semantic release, source bundle,
principal, tenant, purpose, jurisdiction, scope, policy and rights epochs,
correction generation, observed frontier, current effective time, and the
finite effective interval. Direct construction is forbidden. Post-issue field
tampering fails when the authority is revalidated.

The source-context issuer projects the same finite boundary into
`ContextEligibility` and every issued `SourceGrant`. Callers without this
authority remain timeless with `effective_until=None`.

`source_lesson_expiry_task(...)` crosses only the owner-issued
`effective_until` boundary. Changing `observed_frontier` or supplying a
different effective time cannot mint an invalidation. Crossing the valid owner
boundary causes A13 `transition_context(...)` to emit the existing typed
`C09ContextInvalidation`.

No `CorrectionEvent`, signer, wall clock, evidence-time reinterpretation, or
alternate event ontology is introduced.

## EGM round 1 and repair

Fresh Google EGM review used pinned EGM commit
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

Round 1 reviewed semantic candidate `ee644401...` and failed with:

- Blocker: `declare_source_context_policy_window(...)` still accepted
  caller-selected task/policy/frontier and absolute time values. The producer
  could therefore fabricate the expiry it later consumed.
- Major: the real pinned-A01 witness skipped because no A01 artifact was mounted.

The repair removes the caller-owned declaration API. The new issuer accepts
only the pinned source selection and derives the full temporal contract from
the hash-pinned policy registry.

The previously skipped A01 artifact was reconstructed deterministically from the
accepted full conformance bundle
`f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`.
The reconstructed artifact is the exact pinned A01 bundle
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
for semantic release
`58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`.

## Verification after current-unified synchronization

The feature branch was merged forward to reviewed unified
`9301e41ef215b9d035449c3260c7cd0f8ee0b5a7` without conflict.

Focused verification on that synchronized tree:

- source-context authority and transition tests: **10/10 PASS**;
- A13/C09 context-boundary tests: **5/5 PASS**;
- real pinned-A01 source-context tests: **3/3 PASS, 0 skips**;
- `npm run quality:changed` against current reviewed unified: PASS;
- development structure: 0 violations;
- governance integrity: 0 violations;
- changed-file smell audit: 0 new findings;
- legacy-trainer authority: 6/6 PASS;
- BAMF flow-control: PASS; tests 15/15;
- `git diff --check`: PASS.

The repository-wide differential leaf gate remains unsuitable as feature evidence
in this local environment because unrelated collection requires unavailable
`torch`, `sympy`, and a historical legacy checkpoint fixture. The focused
#906 acceptance surface and changed-scope governance checks above are green.

## Joined #906 -> #752 proof

The authoritative #752 Major-3 consumer is the accepted Lane-C branch
`codex/752-post-egm-h1-fixes-20261107`, not stale PR #864.

A disposable detached proof merged #906 semantic repair commit
`3b80a76c` with the current accepted #752 consumer head
`03e7a3c060bc49962ccfe049417090ea2c1c6ec0`.
Disposable merge head:
`40d84d361b06169f51cc45ae33e3d1288e9a4e29`.

The joined proof:

1. issued source contexts under the opaque policy-owner temporal authority;
2. retained a real C09 `PackedFrameArtifactOwner` whose TIME dependency used
   that approved context digest;
3. registered the retained owner with #752 accepted-runtime custody;
4. crossed exactly the owner-issued boundary;
5. called `AcceptedRuntimeHost.record_context_transition(...)`;
6. persisted one `BAMF_C09_CONTEXT_INVALIDATION` record without correction
   payload or signer;
7. observed `BAMF_C09_ARTIFACT_HELD` before retained packed-frame reuse;
8. cleared process-local runtime state, rebound the accepted generation,
   re-registered the physical owner, and observed the same hold after cold replay.

Result: `906_752_JOINED_PROOF_OK`.

The accepted-runtime regression on the same disposable combination passed
**9/9**, including durable A13 invalidation, concurrent correction custody,
cross-process observation, deferred frontier replay, equal-output revalidation,
and cold-restart persistence.

The joined proof is integration evidence only. No #752 code is merged into the
#906 feature branch.

## Safety and authority

- No wall-clock expiry or TTL was derived.
- No evidence timestamp was treated as rights expiry.
- No correction signer or `CorrectionEvent` was minted.
- Timeless PUBLIC_FORMAL behavior remains unchanged without explicit policy
  authority.
- No live learner, trainer, optimizer, champion, checkpoint, or accepted neural
  state was mutated.
- No H4 was started.
- #752 remains open and its historical H3 verdict remains unchanged.
- #478 was not inspected, mutated, validated, or reviewed. Its already-reviewed
  unified integration was observed only because current reviewed unified moved.
- No self-merge was performed.
