# BAMF-0.2 EGM, implementation verification, and drift lifecycle

<!-- BAMF02:DESIGN-VERIFY-DRIFT-LIFECYCLE:20261108 -->

## Purpose

BAMF uses Google's Elephant-Goldfish Model for review of designs and
implementation plans before those plans are executed.

After implementation, BAMF uses differential engineering verification to prove
behavior and EGM drift analysis to compare the approved design with the
implemented result.

The lifecycle is:

`DESIGN -> EGM REVIEW -> IMPLEMENT -> VERIFY -> DRIFT -> PREMERGE -> HUMAN REVIEW`

Each stage answers a different question. A result from one stage does not stand
in for another.

## Pinned EGM dependency

Use Google [Elephant-Goldfish Model](https://github.com/google/elephant-goldfish-model)
at commit `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

The local checkout is `../bamf02-egm-b3a359/`. If it is missing, obtain and
pin it before review:

```sh
git clone https://github.com/google/elephant-goldfish-model.git ../bamf02-egm-b3a359
git -C ../bamf02-egm-b3a359 checkout --detach b3a35956759bf7f024af2ff061b2e0b44b438e4c
git -C ../bamf02-egm-b3a359 rev-parse HEAD
```

Require the exact pinned SHA. Read the pinned integration instructions and use
personas and standards according to their declared purpose. The pinned checkout
is a review-tool dependency; Bilqis repository governance remains controlling
for Bilqis scope, ownership, verification, and publication.

## Domain-precise language

Bilqis is an ML/runtime, provenance, lifecycle, and state-consistency project.
Describe the software relationships actually being evaluated.

This wording discipline is operationally important. Automated systems and human
reviewers may classify work partly from the terminology used to describe it.
When benign ML/runtime work is phrased with vocabulary imported from unrelated
technical domains, the work can be misclassified. That can create avoidable
warnings, latency, resource consumption, and workflow interruptions. Clear
domain-specific wording makes the work easier to understand and classify while
preserving the exact engineering requirement.

Review and implementation language should center on:

- ownership;
- provenance;
- lineage;
- canonical sources of truth;
- state consistency;
- identity consistency;
- lifecycle transitions;
- validation order;
- acceptance and publication;
- retry and recovery behavior;
- compatibility;
- reproducibility;
- design fidelity;
- invalid or mismatched inputs;
- deterministic proof.

When describing a negative case, state the concrete input variation and expected
result.

For example:

> Change the prepared candidate's `outbox` while holding all other fields
> constant and verify that publication detects the identity mismatch.

This wording identifies exactly what must be measured without adding a second,
less accurate conceptual frame.

Apply the same discipline to design documents, issue text, implementation plans,
review assignments, findings, test descriptions, commit messages, pull request
descriptions, handoffs, and durable receipts.

Existing code symbols, schema names, issue identifiers, and externally defined
terms remain verbatim where necessary. Surrounding prose should explain their
actual software role.

## Stage 1: Design and issue shaping

Before substantive implementation, establish one reviewable
design/specification artifact.

For a bounded BAMF leaf this may be the live issue plus an implementation
specification when the issue alone cannot contain the necessary design detail.

The design must identify:

- owned outcome and inherited requirements;
- boundaries with upstream and downstream owners;
- required interfaces and existing code surfaces;
- state and data-model changes;
- provenance and source-of-truth relationships;
- compatibility and migration behavior;
- failure semantics;
- implementation locations;
- concrete acceptance tests or proof obligations.

Do not leave material architectural choices to the coding agent.

If material design decisions arise during implementation, return those decisions
to this stage instead of silently absorbing them into code.

## Stage 2: Fresh EGM design review

EGM review occurs before implementation.

The Elephant holds the project context and prepares the design. Each Goldfish
starts in fresh context.

Supply only:

- the target design or specification;
- the explicit review mode and persona;
- the appropriate EGM standard;
- source or codebase files genuinely required to evaluate statements made by
  the design;
- required public or opaque project references.

Do not supply:

- the implementation conversation;
- prior Goldfish conclusions;
- hidden reasoning;
- Session Minutes;
- unrelated postmortems;
- answers that the design itself is expected to explain.

### Reviewer routing

Use the minimum reviewer set that answers the unresolved design questions.

Examples:

- **Comprehension** when the design must be understandable without unstated
  institutional knowledge.
- **Design/Structural** for architecture, decomposition, ownership, interfaces,
  and failure handling.
- **Codebase Details** when the design claims particular existing files, APIs,
  helpers, or reuse opportunities.
- **Implementation Readiness** only for the implementation plan, asking whether
  an engineer can execute it without making new design choices.

Do not automatically run every persona merely because it exists.

### Reviewer questions

Ask reviewers questions such as:

- Does each important value come from its intended owning component?
- Are provenance and lineage preserved through the described lifecycle?
- Can values that are supposed to identify the same object diverge?
- Is every required transition represented?
- Does the plan explain retry and cold-load behavior?
- Is the source of truth unambiguous?
- Is required validation performed at the correct stage?
- Does the design accurately describe existing interfaces it intends to use?
- Does the implementation plan leave unresolved design choices?
- Are compatibility and recovery cases represented?

Reviewer prompts should be tailored to the specific uncertainty being resolved.

### Review convergence

A complete first design review should expose the major unknowns. Repair the
complete known finding set before further broad review.

After design changes:

- `NONSEMANTIC`: no re-review;
- `MECHANICAL`: deterministic check only;
- `LOCAL_DESIGN`: re-review the affected section and relevant persona only;
- `SHARED_CONTRACT`: re-review the changed contract plus affected consumer
  design;
- `ARCHITECTURE`: perform another whole-design review.

Do not repeatedly rerun the entire EGM pipeline after local edits.

If review repeatedly changes the same architectural boundary, stop and redesign
that boundary before continuing.

### EGM state

`EGM-Pending`, `EGM-Passed`, and `EGM-Failed` describe
design/specification review.

`EGM-Passed` means the reviewed design is ready for implementation. It does not
mean the finished code is correct or ready to merge.

`EGM-Mitigation` is reserved for bounded work created specifically to resolve a
design-review finding before implementation. Implementation defects discovered
later use the ordinary issue/remediation lifecycle rather than EGM state.

Record:

- design artifact identity, digest, or immutable issue revision reference;
- pinned EGM SHA;
- reviewer set;
- unresolved Blocker and Major count;
- disposition of each material finding.

A later semantic design amendment invalidates only the affected review scope
unless it changes architecture.

Historical EGM comments and labels created under the earlier
implementation-review convention remain provenance. Do not rewrite history.
Apply these semantics to new state transitions after this process cutover.

## Stage 3: Implementation

Implement against the EGM-approved design. The approved design is the
implementation contract.

During implementation, EGM does not run in the ordinary inner loop. Use focused
engineering verification instead.

If implementation shows that the approved design is impossible, incorrect,
materially incomplete, or incompatible with an established project constraint,
stop only the affected implementation seam and amend the design. Review the
changed design scope before implementing the new decision.

Keep design evolution explicit.

## Stage 4: Claim-first differential verification

Every test or audit must answer a named question.

Before running a check, identify:

- `claim`: what fact the check will establish;
- `changed_surface`: what code or input changed;
- `prior_evidence`: existing proof relevant to that claim;
- `invalidation`: what changed in the assumptions of that proof;
- `cheapest_next`: the least expensive proof capable of resolving the remaining
  uncertainty.

If there is no invalidation, reuse prior evidence.

### Verification ladder

Escalate only as required:

1. deterministic or static check;
2. focused regression;
3. directly affected owner tests;
4. dependency-closure integration tests;
5. hardware, full-model, or end-to-end witness;
6. premerge aggregate gate.

A lower tier that decisively resolves the claim stops escalation.

Repository-wide execution is not the default discovery mechanism for local
defects.

### Differential gate

Use the existing differential test gate as the normal implementation-loop
selector.

Its job is to:

- compare against the last relevant passing receipt or explicit test base;
- identify changed Python surfaces;
- map them to affected tests;
- use testmon when its dependency data is valid;
- exclude tests explicitly marked detached-only;
- persist a reusable exact-workspace receipt.

When a production path repeatedly falls through to an unnecessarily broad
nearest-test scope, improve `dependency_map.py` or add a focused contract test.
Do not normalize expensive over-selection.

### Passing evidence reuse

A passing result remains valid while its assumptions remain unchanged.

Invalidate evidence only when the changed diff can affect the code, fixture,
dependency, generator, configuration, environment, or test harness on which that
proof depends.

Do not invalidate evidence because:

- a new chat started;
- another agent resumed;
- time passed;
- an issue comment changed;
- labels changed;
- a pull request was opened;
- unrelated documentation changed;
- an equivalent merge changed topology without changing the relevant proof
  surface.

Record reuse instead of rerunning.

### Failure handling

When a broad affected run fails:

1. determine whether failures share one underlying cause;
2. identify the earliest relevant failing boundary;
3. reduce to the smallest reproducible test or diagnostic;
4. repair that boundary;
5. rerun the focused proof;
6. widen only if the repair changed a wider dependency surface or relevant
   uncertainty remains.

Do not repeatedly rerun a broad red suite to observe the same known failure.

Do not open one remediation issue per failed test until distinct failure
mechanisms have been demonstrated.

## Stage 5: Expensive and detached proof

An expensive witness is used only for a claim that cheaper evidence cannot
establish.

Examples include clean-process cold-resume, large Factory/MLX execution, real
hardware behavior, or another acceptance-scale runtime invariant.

Before launching one:

- focused proof is green;
- the candidate surface relevant to the witness is stable;
- prior equivalent witness evidence has been checked for reuse;
- expected runtime and duplicated setup cost have been considered.

For runs plausibly longer than five minutes, use the snapshot-pinned detached
runner.

One exact immutable snapshot gets one canonical launch.

Do not poll it.

Do not launch a duplicate because an agent resumed.

If it fails, inspect the receipt and produce the cheapest diagnostic that can
isolate the failure before another full-cost run.

After two full-cost failures for the same unresolved hypothesis, another full
witness requires evidence that the relevant failing stage has been isolated or
materially changed.

## Stage 6: Post-implementation drift analysis

When the implementation is behaviorally stable, compare it with the
EGM-approved design.

Use EGM drift detection for this phase.

The drift target is the approved design plus the implementation surfaces that
realize it. Do not default to scanning every design document in the repository.
Broaden drift scope only when the implementation changed shared architecture or
a shared contract.

Report differences, not confirmations.

For each difference classify:

### `IMPLEMENTATION_DEFECT`

The approved design specifies one behavior and the implementation produces
another.

Action: repair the implementation and prove the repair with focused engineering
verification.

### `DESIGN_DRIFT`

The implementation contains a semantic choice not represented in the approved
design.

Action: restore the approved design or explicitly amend the design.

If the design is amended, re-run only the affected EGM review scope before
retaining the implementation change.

### `DESIGN_EVOLUTION`

Implementation revealed a real requirement or constraint that makes the approved
design materially incomplete.

Action: return the affected scope to design, record the new decision, and review
it before continuing.

### `DOCUMENTATION_STALE`

The implementation remains within approved meaning but descriptive details in
the design are obsolete.

Action: update the document. No EGM rerun is required unless semantics changed.

### `NO_DRIFT`

No action.

A clean drift result is evidence of design-to-code fidelity. It is not a
substitute for tests.

## Stage 7: Premerge integration gate

Run the premerge aggregate gate only at the actual integration or turn-in
boundary.

Before running it:

- design review is complete;
- known implementation defects are repaired;
- affected differential tests are green or validly reused;
- required detached witnesses are green or validly reused;
- drift is reconciled;
- current required integration dependencies have been consumed;
- candidate head is stable.

If an exact-workspace premerge receipt is already reusable, do not rerun it.

Open the pull request only after these conditions are satisfied.

Hosted pull-request checks are the final integration gate.

A hosted failure does not automatically invalidate design EGM or unrelated
passing proofs.

Reproduce the hosted failure at the smallest affected scope, repair it, and
rerun only evidence whose assumptions changed.

A repair that changes approved design semantics returns the affected design
scope to EGM.

No self-merge.

## Proof economy

BAMF verification optimizes for information, not test count.

For every unit of compute or reviewer attention, prefer the action with the
highest expected reduction in decision uncertainty.

Operationally:

- ask one precise question before selecting a proof;
- prefer discriminating tests over broad correlated test sets;
- reuse immutable evidence;
- hoist expensive invariant setup;
- parameterize repeated cases in one process;
- stop once the decision is determined;
- distinguish environment or harness failures from product failures;
- route recurring manual proof selection into dependency maps or validators;
- avoid expensive proof when the relevant fact is already established.

The objective is not minimum testing.

The objective is the **minimum sufficient evidence set that makes the current
decision defensible**.

## Durable evidence

Keep durable receipts small and machine-readable where possible.

For each important proof preserve:

- candidate head or workspace identity;
- claim proved;
- command or mechanism;
- selected scope;
- base or invalidation range;
- result;
- reusable or stale status;
- expensive-run snapshot digest when applicable.

For design review preserve:

- approved design identity;
- EGM version;
- reviewer set;
- material finding disposition.

For drift preserve:

- approved design identity;
- implementation head;
- compared surfaces;
- material differences and classifications.

These receipts exist so the next agent can continue from established evidence
rather than reconstructing or rerunning it.

## Lane ownership and dependency checks

The existing long-lived branches are `codex/bamf02-a-semantics`,
`codex/bamf02-b-neural`, and `codex/bamf02-c-runtime`. Lane A owns new
semantics and Factory modules; B owns new neural modules; C owns shared trainer,
CLI, checkpoint, and integration surfaces.

Run the workstack and issue-contract checks from the repository root:

```sh
python3 -B scripts/check_bamf_workstack.py docs/tasks/bamf-0.2/workstack.json
python3 -B scripts/verify_bamf_0_2_contracts.py
```

These checks validate repository planning contracts. They do not replace live
dependency readback, engineering verification, drift analysis, or human review.
