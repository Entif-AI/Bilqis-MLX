# Accepted Grade A: experimental human MLX trainer

**Current operation after ADR-023:** The six admitted source-defined Boolean predicates now use the live source-generated trainer, automatically selected by the ordinary human `--human-run` path. On each visit fresh examples are checked by three oracles; each due assessment draws a seeded 72-item complete cohort and stores its questions, SHA and seed for replay. Every distinct retained whole-student incumbent is scored on the same cohort before champion promotion. Misses are supplied to subsequent instruction. Original 144+72 specimens, fixed-exam scores and their legacy receipts remain historical evidence rather than an ongoing embargo. Human `--resume` automatically migrates old saved `v1` states, protecting model+own AdamW and original teacher. Generated assessment admission remains 100% of all 72 items at one complete checkpoint; no new numeric Grade A competence is assumed. This paragraph supersedes any old fixed-exam training description below without modifying its historical evidence.

**Private / 2026-10-15 / user-authorized Grade A only**

## Scope and authority

The user explicitly accepted the existing six direct, source-defined Grade A
capabilities rather than continuing to defer training until the full NI grammar
is complete. The release is `bilqis.mlx.grade-a-user-accepted/20261015` and
rests on the unchanged candidate manifest
`docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json`. That source artifact intentionally
retains its older candidate wording and digest. No historical source is silently
relabeled. This approval is for **experimental learning of the known typed
pasigraphy semantics**, not proof that arbitrary New Ithkuil surface wordforms,
complex grammar or independent neural mastery already exist.

**Only the human operator may invoke the real-model training command.**
Agents may run `npm run test`, `npm run train -- --dry-run`, `npm run
grade-a:verify`, `npm run mlx:qualify` and disposable synthetic fixture tests,
but must never supply `--human-run` themselves.

## Operator commands

```sh
cd ~/Code/bilqis-mlx
npm run test
npm run train -- --dry-run --verify-source
npm run train -- --human-run --minutes 90
# Explicit later continuation of the same independent run:
npm run train -- --human-run --resume --minutes 90
npm run status
npm run dashboard
```

The trainer defaults to **no hidden per-command visit cap**, **16 optimizer
steps per visit**, **32 source-backed examples per step**, **100 GiB disk
reserve**. Per ADR-018, ordinary visits remain in memory until the next
scheduled examination; only tested best-scoring capability candidates become
permanent champion binaries. A complete working-student recovery bundle is
still preserved at each assessment or human stop, even when not a champion.
The human-selected `--minutes` is the default session limit; an operator can
add `--max-visits N` to request an additional explicit visit cap. Setting
`--max-visits 0` (the default) disables only that cap, not the minute or disk
reserve limits. Superseded unreferenced run-local bundle directories are
retired once their replacement pointer is durable; historical receipts remain.
The default run directory is
`runs/school-mlx-v1`, always separate from the historical source run.

On an interactive terminal, the human training command uses that terminal for
the six-panel School50 live dashboard. It refreshes on **committed** model
assessment/recovery boundaries, not in-flight optimizer steps. On normal stop the
trainer appends a `GRADE_A_SESSION_STOPPED` event identifying the actual
reason (`TIME_LIMIT_REACHED`, explicitly requested `VISIT_LIMIT_REACHED`, or
`GRADE_A_AWAITING_NEXT_GRADE`, or protected `DISK_RESERVE_REACHED`), elapsed seconds, visit count, and latest
optimizer step. A due complete-grade exam finishes before normal stopping.
Disk stops include measured free GiB, protected reserve and estimated next
checkpoint allowance. They never reduce the reserve or overwrite a protected
current student or champion. The dashboard also independently
reads and shows live disk headroom even if an older run lacks a stop receipt.
A final read-only snapshot remains. `npm run dashboard` independently replays
the persisted events and renders the complete latest snapshot after the
training command has exited. Non-TTY training preserves machine-readable
JSON event lines plus the final result with stop reason. `npm run status`
reports the most recent completed stop when its event matches the saved
student generation and optimizer step. Running the fresh command with an existing run does not
reset anything: the guard instructs the human to use `--resume`.

The original native PyTorch source is pinned to exact SHA-256
`646d8590cf8fddb7b3c412ecead4ac185a0578f93baadf24e05f92dd15068a78`
and optimizer step 116760. At the initial launch the model and all AdamW
moments are loaded, converted to MLX, and saved as a complete independent
bundle without replacing that source file.

The adaptive teacher is imported from original
`bilqis_school.engine.pick/observe`. It retains the historical teacher's
4,288 observations and 390 strategies from the original v16 run state.
The latest teacher state originated at **step 116952**, later than the
selected best complete student at **116760**. That difference is recorded
as provenance, not misrepresented as a same-step model/teacher pair.
Teacher policies retain all six original knobs. In Grade A there are no
previously passed or future prereq-admitted grades, so old-grade rehearsal,
future preview and prior-grade distillation have no eligible material.
Grade A currently uses the policy's learning rate, depth and contrast
selection, and returns a reward from **training rows only**. The fixed
72-question graduation exam is never used to reward or update the teacher.
Later grades must implement all remaining teacher focus branches before
those curricula become active.

## Durable state model

- `runs/school-mlx-v1/bundles/<unique>/` contains one complete FP32 model,
  optimizer AdamW moments, step, parameter-order manifest and semantic catalog
  SHA-bound to the historical source.
- `states/<generation>.json` contains immutable committed assessment,
  migration or operator-stop receipts. Interim training visits do not need
  their own weight files or restorable state receipts.
- `state.json` is the atomic latest pointer. Only this file is replaced
  after a numbered immutable snapshot was fully written and verified.
- `events.jsonl` is an append-only human-readable progress record.
- `.grade-a-operator.lock` is an exclusive OS lock, not a claim of a
  distributed lease.

Interrupted in-memory visits since the last scored checkpoint boundary may be
lost on a crash. A human `--resume` restarts from the most recent complete,
source-bound model+own-optimizer and teacher state. Earlier numbered receipts
remain historical evidence even after binaries with no remaining champion or
working role have been retired.
If a process dies after a complete bundle write but before pointer promotion,
an orphan bundle may temporarily remain; it is never automatically selected
as student or champion. Future successful scored commits can retire orphaned
complete bundles under the exclusive lock and checked reference plan.

## Graduation and generalization

Each current capability has exactly **24 source-backed instructional items**
and **12 held-out examination items**. All 72 exam items remain fixed and
include individually correct typed binary answers validated against three
source interpreters. Grade A can pass only when **one complete student** at
**one exact optimizer step and bundle SHA** scores **12/12 on all six
capabilities simultaneously**. A pass records its champion and enters
`AWAITING_NEXT_GRADE`, **not** whole-school mastery. If incomplete, the
existing school state machine performs one full pass followed by two
globally weakest-three recovery rounds, with fresh re-ranking.

The model's *typed binary* output head is used for these six capabilities,
not the historical unrestricted five-state evaluation. Both readouts remain
distinguishable in the separate read-only baseline report.

## Verification scope and known limitations

- Existing original model+AdamW parity against PyTorch on Apple GPU passed
  one disposable full-39-tensor step and a full semantic snapshot restart.
- The unchanged original full student scored **34/72** on the frozen Grade A
  exam in a read-only Apple GPU run, both on its native five-state argmax and
  on the separately reported typed binary readout. Maximum PyTorch versus
  MLX absolute logit difference was **0.0001316070556640625**, within 0.002.
  This is the starting baseline, not a passing score.
- A disposable test of the real source model **without training** passed
  initializer -> complete MLX bundle -> state pointer -> validated reload;
  the original source SHA and optimizer step remained unchanged.
- The actual trainer executed six graded synthetic model updates/visits,
  complete source-bound fixture bundles and one 72-question exam end-to-end
  through the production scheduler, without training Bilqis.
- No agent launched an optimizer update on the actual preserved student.

This is the first experimental human trainer, not a measured successful
real-student long session. It is expected to improve through observation.
The original 24-item-per-capability teaching inventory was a provisional
experimental constraint, subsequently retired by ADR-031's exposure-aware
miss replay. The current grade exam remains fixed only during a single grade
enrollment, with fresh examination on return after passing; historical token
semantics remain unchanged.
