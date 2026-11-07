# C03 parent integration readiness — 2026-11-07

Issue: #376  
Branch: `codex/bamf02-c03-376-20261107`  
Reviewed-unified baseline consumed: `bb8e83f03e38b64018cfe357addd90a0a6d67297`  
C03 candidate head: `31582efffc422628ac9b64a50859801fa066d346`  
Status: **IMPLEMENTED_WAITING_B13_ADOPTION**

## Scope completed on the C03 owner

The four decomposed C03 implementation children (#494–#497) were already merged
and closed under ADR-121. This parent pass requalified their behavior against the
current runtime and filled the parent-only integration gaps that do not belong to
B13.

The branch now provides:

- a typed C03 teacher-lineage custody projection that preserves the immutable
  historical replay baseline `d21797e72365bf93ea7cad3a4ef9020ec9817f23`
  separately from the current legacy-trainer adaptation authority;
- canonical digest binding of the checked-in
  `bilqis.bamf.legacy-trainer-authority/v1` record plus an independently
  observed current source head, without hard-coding one current head as
  historical truth;
- exact cold JSON restore with nested teacher-state digests and fail-closed
  tamper/adaptation-authority checks;
- changed-student epoch binding that resets checkpoint-local causal evidence
  while preserving strategy priors and historical evidence;
- a parent grade-neutral metamorphic witness over executable Factory releases,
  source-qualified rows, delivered teaching, compiled model input/target/
  provenance, mastery debt, explicit prerequisites and absent implied
  grade-order edges;
- repository-mandated structural splits for the oversized
  `teacher_strategy_population.py`, its companion test surface, and
  `lesson_guidance.py`, all behind the stable import surfaces.

## Current causal-chain evidence

The current production visit path already records more than a teacher proposal.
`runtime/tests/visits/test_orchestration.py` wraps and delegates to the real MLX
training step, then records the actual delivered source rows, optimizer attempts,
retention outcome and realized cost, publishes the checkpoint-bound observation
outbox, cold-reads it, and reconciles it exactly once after restart.

`runtime/tests/teacher/test_teacher_observation_replay.py` independently covers
crash-before-emission recovery, duplicate rejection and exactly-once committed
observation replay. C03 therefore reuses the C02-owned realized-delivery chain
instead of inventing a second capture path.

## Parent BAMF-REQ-017 / ADR-BAMF02-004 witness

`test_c03_parent_acceptance.py` recompiles the same source/capability fixture
under actual valid grade IDs A, B, C and Z. With equal source qualification,
teacher evidence, priority context and carried mastery debt, the following are
identical across permutations:

- teacher policy key, policy and selection metadata;
- cold JSON teacher state;
- source row identities;
- delivered-teaching provider, option, variation axes, specimen identities and
  specimen-content digest;
- compiled model input, target and provenance;
- all semantic student-region fields other than the explicitly descriptive
  grade/debt labels.

The diagnostic grade and debt-shape fields relabel as expected, but
`mastery_debt_band` and the semantic selection remain unchanged.

The same parent witness permutes the two-grade executable prerequisite fixture.
A true explicit `foundation -> target` prerequisite blocks with insufficient
or missing evidence and permits with sufficient evidence under every grade-name
permutation. Capability-ID mastery debt still returns `foundation`. Removing
the explicit prerequisite leaves `target` eligible, proving that grade order
does not fabricate an edge.

## Mentor and health disposition

The existing C03 tests retain the historical six-layer mentor only as read-only,
source-gold-gated typed advice. Resume, weight import and optimizer import remain
rejected. Production lesson guidance continues to use current frozen
champion/soup custody rather than importing historical mentor tensors.

Teacher health continues to derive from recorded target/protected outcomes and
attempt/retention counts. Stale geometry cannot qualify a canary and checkpoint
changes reset checkpoint-local retirement evidence while preserving prior
strategy history.

## Structural verification

The encountered oversized project-authored owners were split before further
feature work, per `AGENTS.md`:

- `teacher_strategy_population.py`: 461 lines -> stable facade plus population,
  cooldown and selection owners, each below 240 lines;
- `test_teacher_vnext_replay.py`: 380 lines -> three bounded suites plus shared
  fixture, each below 240 lines;
- `lesson_guidance.py`: 415 lines -> stable facade plus selection, soup and
  mentor-guidance owners, each below 240 lines.

Direct structural/behavior proof recorded during this pass:

- split strategy owner suite: 12/12 PASS before the final import repair;
- C03 teacher/replay surface after import repair: 25/25 PASS;
- champion-confidence + grade-soup: 21/21 PASS;
- patch-sensitive mentor fidelity/mentor epoch integration: 13/13 PASS;
- parent grade-neutral acceptance: 6/6 PASS;
- C03 lineage/teacher + real MLX visit orchestration + observation replay:
  26/26 PASS;
- development structure gate: PASS;
- governance integrity gate: PASS;
- changed-file code-smell gate: zero new findings;
- static legacy-trainer authority contract/tests: PASS;
- BAMF flow-control contract/tests: PASS;
- `git diff --check`: PASS.

The differential leaf test selector also exercised a broad baseline-sensitive
integration slice and is **not green** in this workspace. Its complete output
includes failures across curriculum, historical Factory lifecycle/scheduler,
topology, numeric, retention, teaching and system fixtures that are outside the
C03 changed-file surface. A representative failure set was replayed on untouched
reviewed unified `bb8e83f0` and reproduced unchanged: the two
`curriculum/test_school.py` assertions, ten historical Factory
lifecycle/scheduler errors, and the topology cold-resume error. This receipt does
not claim that every broad differential failure was individually replayed on the
baseline. The non-green broad gate remains recorded as a limitation; focused C03
behavior plus the changed-file structure/governance gates are the passing
evidence used for this WAITING checkpoint.

## Legacy trainer authority truth

This worktree cannot execute the live operator preflight because the governing
record points at
`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026`, which is
not mounted on this machine. Prometheus was not substituted.

The live #376 authority clarification records the current preserved source as
branch `codex/337-replay-349-20261026`, head
`d84d2ab9e2d79817c131ef7e0d4ec0d574e57b32`, generation 24254. Current
A09.5 realization PR #891 also records a successful mandated live preflight
against that preserved replay. The C03 projection stores current adaptation
authority as a separately attested reference so a future legitimate source head
can advance without rewriting the immutable historical replay provenance.

## Remaining dependency-owned gate

C03 must ultimately persist its teacher projection atomically with the accepted
B13 student generation and cold-resume identity. That write belongs to B13, not
to C03.

At this receipt:

- B13 parent #372 is open.
- B13.1 #478 / PR #885 is open, draft and conflict-bearing.
- #478 remains `EGM-Failed` while its A02.1 dependency is unresolved.
- A02.1 #399 is open.
- C07.1b #510 is open.
- A09.5 #395 is open; realization PR #891 is open/draft with green hosted
  portable and semantic-ABI checks.

Accordingly this branch does **not** patch B13's moving successor-publication or
admission owner. The C03 projection is deliberately an input contract for that
future accepted seam.

## Resume trigger and future hook

Resume only after B13.1 #478 / PR #885 and its A02.1/C07.1b/A09.5 dependency
chain are accepted into reviewed unified.

On resume:

1. sync the then-current reviewed unified exactly once;
2. after accepted-generation load and before teacher selection, restore the C03
   projection from the B13-owned teacher-state sidecar;
3. after candidate retention acceptance and before successor publication, bind
   the next C03 teacher epoch to the accepted new student;
4. let B13's canonical owner atomically persist teacher identity/epoch/state
   with matching generation provenance; rejected candidates keep the parent
   projection unchanged;
5. run the exact parent/B13 cold-resume witness, premerge verification and one
   fresh exact-head EGM;
6. open the ready PR to `codex/bamf-unified-base-20261028` only after those
   gates are green.

No PR is opened from this WAITING state because repository policy forbids using
a draft PR as a dependency queue marker.
