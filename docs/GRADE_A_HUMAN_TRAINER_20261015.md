# Accepted Grade A: experimental human MLX trainer

**Private / 2026-10-15 / user-authorized Grade A only**

## Scope and authority

The user explicitly accepted the existing six direct, source-defined Grade A
capabilities rather than continuing to defer training until the full NI grammar
is complete. The release is `bilqis.mlx.grade-a-user-accepted/20261015` and
rests on the unchanged candidate manifest
`docs/GRADE_A_CANDIDATE_MANIFEST_V2.json`. That source artifact intentionally
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

The trainer defaults to **48 maximum complete visits per command**, **16
optimizer steps per visit**, **32 source-backed examples per step**, **100 GiB
disk reserve**, and one recorded full-state checkpoint after every complete
visit. Tune using `--max-visits`, `--steps-per-visit`, `--batch-size` and
`--reserve-gib`. Setting max visits to 0 removes only the per-command visit
cap; disk reserve and minute limit remain in effect. Save files are never
silently pruned. The default run directory is
`runs/school-mlx-v1`, always separate from the historical source run.

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
- `states/0000001.json`, `states/0000002.json`, and successors retain an
  append-only school/teacher/pointer snapshot per committed transaction.
- `state.json` is the atomic latest pointer. Only this file is replaced
  after a numbered immutable snapshot was fully written and verified.
- `events.jsonl` is an append-only human-readable progress record.
- `.grade-a-operator.lock` is an exclusive OS lock, not a claim of a
  distributed lease.

Interrupted *mid-visit* in-memory steps are intentionally **not** claimed as
committed. A human `--resume` restarts from the latest complete, source-bound
model+own-optimizer state. No bundle or historical checkpoint is overwritten.
If a process dies after a complete bundle write but before pointer promotion,
an orphan bundle may remain as evidence; it is not automatically selected,
deleted or treated as a student. Reserve checks prevent unbounded growth
below the agreed 100 GiB headroom.

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
The 24-item-per-capability teaching inventory is intentionally finite;
future lessons can increase diversity under new versioned admission, without
silently replacing the frozen examination or historical token semantics.
