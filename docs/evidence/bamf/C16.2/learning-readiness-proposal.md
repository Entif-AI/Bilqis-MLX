# C16.2 foundation launch-readiness proposal

Status: IMPLEMENTED / BOUNDED-VERIFICATION / TURN-IN-REVIEW
Issue: #544 / C16.2
Reviewed unified base consumed by the current execution branch:
`505dfdd1ea2cfe57d6e4418f7b6faed7428b71b6`
Execution branch: `codex/544-c16-learning-readiness-20261111`
Pinned EGM: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`

The first EGM review rejected the original raw fixed-school-pointer design. The
work was therefore decomposed instead of self-granting C16.2 authority over C05:

- #992 / C16.2a owns accepted Factory release custody and is complete;
- #993 / C16.2b owns the C05-native whole-school custody seam;
- #994 / C16.2c owns the aggregate retained/rejected/cold-resume launch witness
  and owner-start command contract.

Live issue amendments on those children are the controlling detailed contracts.
This document records their integrated shape and MUST NOT be read as authority
for the rejected pre-decomposition pointer design.

## Outcome

C16.2 owns the evidence gate immediately before the first durable BAMF student
is handed to the human-operated learning loop. It does not own that durable
handoff. C16.3/#545 is the direct consumer and owns the exact persistent
human-started lineage.

The C16.2 deliverable is therefore:

1. make the existing real source-qualified BAMF retention path executable on a
   disposable accepted BAMF run without creating legacy `state.json` custody;
2. compose exact-head evidence across the already implemented
   C03 -> C02/C08/B11 -> C05 -> B13 owners, using accepted owner receipts and
   bounded seam checks rather than one full-model pytest witness;
3. prove retained source-valid behavior, complete rejected-candidate rollback
   and cold-resume equivalence;
4. publish and verify the exact owner-start and cold-resume command shape that
   C16.3 will consume;
5. leave C16.1a create/dry-run/resume validation neural-inert.

Under the current `FOUNDATION_EVIDENCE_POLICY_ACTIVE`, source-valid acquired or
retained taught behavior is sufficient for this launch gate. Fresh episodes,
independent source families, unseen fillers, novel composition and a strictly
improved fresh-target score remain diagnostics and cannot veto C16.2.

ADR-141 and the owner correction recorded on #544/#994 also control the proof
method. No agent-launched test may exceed two hours, and two hours is a ceiling,
not a target. Exact accepted owner evidence may be composed when its assumptions
remain current. A still-uncertain adapter seam receives the smallest bounded
integration check that can resolve it. A whole-system exercise that cannot fit
the ceiling is deferred to a human-operated, dashboarded non-test run after
assembly; it is not a hidden C16.2 prerequisite.

## Boundary with C16.1 and C16.3

C16.1a owns persistent create, dry-run, resume validation and optional C07
enrollment. Its lifecycle report continues to carry
`ready_for_training=false` and `neural_updates=0`.

C16.2 does not route that report into neural execution. Its bounded verification
uses the existing runtime owners and exact accepted owner receipts under isolated
test custody.

C16.3/#545 owns the production handoff from validated BAMF resume into the
human-operated learning loop. The command published by C16.2 is a reviewed
handoff contract, not executable neural authority added by this leaf.

## Existing owner chain to account for

The production mechanisms already exist. C16.2 must account for their composition
rather than replace them:

`accepted B13 generation`
`-> AcceptedRuntimeHost/source context`
`-> C03 accepted teacher visit identity`
`-> C02/C08/B10/B11 candidate step`
`-> C05 source-qualified retention evaluation`
`-> C05 retention decision`
`-> candidate resolution`
`-> C03 successor teacher custody`
`-> B13 publication or observational rejection`

Accepted owner receipts may be reused when they are exact and their production
assumptions are unchanged. Package-local fixtures may prove narrow composition
seams. A check must not mock a production result that the same check claims to
observe.

## C16.2b / #993: C05-owned fixed-school custody

`factory_retention_owner._fixed_school_instruments(...)` currently obtains its
fixed-school exam by calling `state_dag.read_current(run_dir)` and then
`frontier_exam(receipt)`. That is correct for the legacy operator path, but it
makes the otherwise BAMF-native C05 retention owner require a target
`state.json` merely to evaluate an accepted BAMF candidate.

C16.2b removes that representation leak without changing C05 decision semantics.

### C05 fixed-school authority

The public C05 APIs remain unchanged. No caller may supply a cohort, pointer,
seed, rubric, scope, policy, solver, source manifest or coverage map.

For accepted BAMF parents (`run_identity is not None`), C05 itself derives the
whole-school cohort from the accepted Factory release and persists one immutable
receipt keyed by `run_identity.digest`. The cohort covers the complete ordered
capability tuple from the release execution plan. Its source identity is the
Factory `source_attestation_sha256` when present, otherwise the exact
`SourceBindingSet.digest()`. That source identity MUST equal
`run_identity.initial_source_identity`; the B13 generation manifest is never
substituted for it.

The fixed-school seed is run-stable and contains only run identity, Factory
release, source identity, semantic catalog, complete capability scope, rubric
and source contract. It MUST NOT include the current generation, accepted parent,
candidate, target capability, grade or score.

C05 additionally owns one minimal write-once integrity anchor,
`.c05-fixed-school.anchor.json`, which binds the accepted B13 parent present at
first materialization. The anchor is not retention authority and is not a seed
input. `.c05-fixed-school.lock` is synchronization only and carries no authority
payload. Missing, malformed, symlinked, rewritten or conflicting anchor/receipt
state fails closed. Later accepted generations reuse the same receipt/cohort
while current-parent authority is authenticated independently on every C05
evaluation.

For historical parents (`run_identity is None`), C05 preserves the legacy
`state.json -> frontier_exam -> load_frontier_cohort` path unchanged. A BAMF
parent never falls back to target `state.json`.

Candidate and package-import evaluation share this private owner path. Package
import remains explicitly non-training and therefore contributes no training
source-exclusion claim.

### Alternatives considered

1. **Caller-supplied fixed-school pointer. Rejected.** It violates the existing
   C05 no-caller-cohort contract and permits same-release subset substitution.
2. **Treat the B13 parent manifest as source-manifest identity. Rejected.** B13
   custody and Factory source provenance are different authorities.
3. **Recompute a mutable fixed school on every evaluation. Rejected.** This makes
   retention evidence depend on later source drift and breaks cold equivalence.
4. **C05-owned immutable whole-school custody. Selected.** It preserves C05
   authority, exact source provenance, whole-release scope and cold reuse without
   changing public API authority.

### Risks & mitigations

- **Scope substitution:** verify persisted row coverage against the complete
  admitted capability set, not metadata alone.
- **Release/source drift:** bind run identity, exact Factory release, source
  identity, semantic catalog, rubric and source contract on every cold load.
- **First-parent provenance rewrite:** use the write-once C05 integrity anchor and
  require exact anchor/receipt agreement after restart.
- **Concurrent first materialization:** serialize under the C05-only lock and
  fail closed on conflicting custody.
- **Legacy contamination:** branch on accepted `run_identity`; never use file
  existence as the BAMF/legacy selector.
- **Package-import side effects:** reuse the same C05 fixed school while keeping
  the package-import training-exclusion set empty.

## Disposable foundation witness

Add one cohesive witness to the prescribed C16 package-local test surface. It
must exercise the actual owner chain rather than merely combine synthetic
decision objects.

### Accepted path

The witness must:

1. create or publish an isolated accepted BAMF generation zero using existing
   B13/C16.1 owners;
2. bind the exact source context and accepted runtime host;
3. select a source-qualified visit through the real C03 owner;
4. construct C03 visit provenance and execute the real C02/C08/B11 candidate
   step;
5. let the real C05 owner materialize or cold-load its BAMF-native whole-school
   custody without target `state.json`;
6. evaluate the candidate through the unchanged public C05 Factory retention
   owner;
7. issue the existing owner retention decision and resolve the candidate;
8. derive the C03 successor through the existing B13 successor constructor;
9. publish through the existing B13 acceptance path;
10. cold-load the accepted successor and compare the next legal C03 selection
    with uninterrupted execution.

The receipt must bind literal parent/retained generation identities, optimizer
steps, selected capability/visit identity, fixed-school cohort identity and the
source-valid developmental evidence disposition.

### Rejected path

Using a disposable copy, deliberately produce a candidate that the real C05
screen rejects. Resolve it through the normal rejection path and prove:

- the accepted B13 pointer bytes are unchanged;
- the accepted parent bundle bytes remain unchanged;
- the retained optimizer identity/step remain unchanged;
- observational rejection evidence is recorded;
- cold load returns the exact accepted parent.

The witness must not weaken C05 thresholds or bypass its decision owner merely
to obtain a rejection.

## Grade-neutral and first-start negatives

The cohesive C16.2 acceptance ring must retain the already implemented C16
first-start evidence:

- differently named admitted grade declarations produce equivalent
  source-qualified scheduling/debt behavior when semantic inputs are equal;
- a real prerequisite hold remains enforced independent of grade naming;
- a non-admitted future capability remains blocked by source authority rather
  than an A/B/C-only architecture;
- historical B-only quota/turn state is ignored or explicitly rejected and is
  never silently re-enabled;
- dry-run performs zero neural updates;
- cold resume restores the same accepted optimizer custody and next teacher
  selection identity.

Existing `test_bamf_first_start_witness.py` already covers much of this negative
surface. C16.2 should reuse that evidence rather than duplicate it.

## Owner-start and cold-resume command contract

C16.2 publishes the exact command shape that C16.3 will make neural-active:

`npm run train -- --human-run --resume --run-dir <accepted-bamf-run>`

The cold-resume command is the same command after interruption.

Until C16.3 integrates the durable handoff, current C16.1a routing must continue
to stop at `READY_TO_RESUME`; `_invoke_learner` must remain unreachable for BAMF
v2 in #544.

The C16.2 tests must verify that:

- parser/preflight accepts the command as ordinary BAMF v2 human resume;
- accepted run identity/topology/Atlas/optimizer settings are inherited from
  B13 custody when omitted;
- dry-run and explicit enrollment requests remain neural-inert;
- the current command cannot fall through to the legacy `state.json` learner;
- the same command is documented as the C16.3 handoff point, not falsely claimed
  as neural-active before #545.

No new CLI flag is introduced by #544.

## Required implementation surface

Production:

- **Modify** `bilqis_mlx/runtime/_capability/factory/factory_retention_owner.py` only to
  route accepted BAMF parents into the private C05-owned whole-school path while
  preserving the legacy historical path;
- **Add** bounded private C05 support modules for fixed-school orchestration,
  receipt/scope verification, and synchronization/integrity-anchor custody.

Tests/evidence:

- **Modify** the package-local C16 first-student acceptance surface, primarily
  `bilqis_mlx/runtime/tests/test_bamf_first_student.py` and/or a bounded mirrored
  companion if the repository line-count rule requires one;
- reuse existing C03/C02/C08/B11/C05/B13 fixtures and owners, but do not replace
  the claimed real candidate/retention/publication operations with mocks;
- retain `bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/`
  regressions proving C16.1a remains neural-inert;
- **Modify** `docs/operations/BAMF_0_2_FIRST_STUDENT.md` to publish the exact
  future owner-start/cold-resume command and the #544 readiness verification
  command;
- add a compact C16.2 receipt after implementation and review.

If implementation reveals that another production owner must change, stop that
seam and amend this design before editing it.

## Verification ladder

The minimum sufficient evidence set is:

1. focused C05 unit regression proving explicit fixed-school custody works with
   no target `state.json` and legacy fallback remains unchanged;
2. cohesive disposable C16.2 retained-path witness using real candidate step,
   real C05 evaluation and real B13 publication;
3. destructive-candidate rollback witness;
4. cold-restart next-selection/optimizer equivalence;
5. existing C16.1 first-start grade-neutral/prerequisite/legacy-B negatives;
6. operator routing regressions proving BAMF v2 remains neural-inert in #544;
7. changed-surface structure/governance/error-control/diff checks;
8. fresh post-implementation EGM drift review;
9. premerge aggregate gate only at final turn-in, with reviewed-unified baseline
   classification for inherited failures.

No real persistent learner, teacher episode or operator optimizer run is part of
this implementation session.

## Incremental implementation phases

1. **#992 / C16.2a.** Persist and recover the accepted exact Factory release in
   B13 custody. Complete.
2. **#993 / C16.2b.** Add C05-owned immutable whole-school custody and prove the
   public candidate/package-import routes remain owner-controlled and state-free.
3. **#994 / C16.2c.** Compose the real retained/rejected/cold-restart disposable
   proof and publish the owner-start/cold-resume command contract.
4. **Parent turn-in.** Run aggregate exact-head controls, fresh EGM,
   diff/premerge checks and publish the #544 receipt for human review.

Each phase must finish importable and testable. There is no production neural
dispatch change in #544.

## Explicit non-goals

C16.2 does not:

- change C16.1a `ready_for_training` or `neural_updates` reporting;
- make BAMF resume enter `_invoke_learner`;
- create a new persistent scheduler or BAMF `state.json`;
- persist a new Factory execution capsule or teacher-adaptation capsule;
- own long-running multi-visit continuation;
- require a C07 `atlas-release` lease for staged launch;
- repair unrelated trust-row-only interrupted-resume or C07 unsafe-lock error
  surfaces unless exact #544 verification proves they invalidate this witness.

## EGM gate

Before production mutation beyond the already committed flow-control checkpoint,
fresh independent Design/Structural, Codebase Details and Implementation
Readiness review must reach zero unresolved Blockers and Majors for this proposal.
Any semantic repair returns only the affected scope to review.
