# BAMF-0.2 C13 integration handoff

Status: **prepared on #529 exact head; final unified merge SHA pending PR #1041**.

## Release boundary

C13 is the BAMF-0.2 integrated wiring gate for the sole 96 GB M3 Ultra trainer.
It does not require an extended learning soak before release. The long-form
integrated-learning and dashboard qualification moved to BAMF-0.3 #1039.

The BAMF-0.2 handoff proves that the live source, Factory, authority, teacher,
custody, and trainer surfaces compose. Existing bounded owner tests retain
responsibility for rollback, cold resume, correction, and accepted-generation
custody.

## Accepted inputs

- C13.1 #528 merged through PR #1040.
- PR #1040 merge commit: `47e57f05574b7702a85772003c5fc892ff206a33`.
- C13.2 #529 prepared head: `7dc5711aee26a2d2050153384622e2da4574711f`.
- C13.2 turn-in: PR #1041, pending human merge when this receipt was prepared.
- C13.1 real M3 Ultra evidence created and accepted disposable generation zero
  under the current ordinary-user C09/C06 path and B13 custody.
- The superseded long #528 probe was stopped after about 86 minutes at
  generation 0 / optimizer step 0. It is performance evidence, not a release
  failure.

## Bounded verification

After #528 merged into the unified branch, #529 consumed unified
`47e57f05574b7702a85772003c5fc892ff206a33` without conflicts.

- C13 owner ring: 13/13 PASS in 4.120 seconds.
- Rollback/custody ring: 54/54 PASS in 15.658 seconds.
- `git diff --check origin/codex/bamf-unified-base-20261028...HEAD`: PASS.

The existing #529 portable receipt also records Factory-architecture,
semantic-boundary, error-control, and changed-code-smell checks. No code repair
was required after consuming merged #528.

## Operator handoff

Use the accepted BAMF run directory for every command below.

Neural-inert resume preflight:

```bash
npm run train -- --dry-run --resume --run-dir <accepted-bamf-run>
```

Human-owned start or cold resume:

```bash
npm run train -- --human-run --resume --run-dir <accepted-bamf-run>
```

Read-only status:

```bash
npm run status -- --run-dir <accepted-bamf-run>
```

Read-only live dashboard:

```bash
npm run dashboard -- --run-dir <accepted-bamf-run>
```

Expanded read-only snapshot:

```bash
npm run dashboard -- --run-dir <accepted-bamf-run> --once --atlas-details
```

The dashboard follows the durable event journal and never owns neural state.
Its BAMF view exposes accepted optimizer step and visits, current capability and
grade context, teacher progress, source/implementation coverage, retained-step
evidence, debt, plasticity mode, and measured memory use when available. These
operating observations are the correct place to detect learning behavior and
resource problems after the owner starts the trainer.

## C13 completion rule

After PR #1041 merges, replace the pending #529 entry above with its exact merge
commit and current unified SHA. No additional long learner run is required.
That readback completes #530 and the release-scoped C13 handoff. C14 #386 and
C15 #387 may then consume C13 without waiting for BAMF-0.3 #1039.

