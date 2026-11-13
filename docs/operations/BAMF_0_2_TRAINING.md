# BAMF-0.2 continuing training program

Status: C14.2 operator contract. This document composes the already accepted BAMF
lifecycle, custody, source-admission and observation surfaces; it does not create a
second trainer, scheduler, source authority or learning gate. The durable student is
started or resumed only by the human operator.

## 1. Read the current program without learning

The continuing developmental program is the packaged
`bilqis.bamf.developmental-program/v1` manifest. Its L0-L4 labels describe semantic
complexity and optional capability packaging. They are not a grade-order scheduler.
The exact current stage intent is derived from the admitted Factory release plus the
current source-coverage/frontier evidence.

Before any owner-started session, inspect the accepted run and current observations:

```sh
npm run train -- --dry-run --resume --run-dir /absolute/path/to/bamf-run
npm run dashboard -- --run-dir /absolute/path/to/bamf-run --once --atlas-details
```

The dry-run must remain neural-inert. The dashboard snapshot is read-only. Missing
learning, mastery, debt or transfer measurements remain `NOT MEASURED`; neither
command may manufacture training results from source coverage, stage metadata or
grade names.

## 2. Source extension is an admission operation

A new source-qualified semantic release is staged through the existing C07 admission
surface. Do not edit the developmental program to smuggle in a new grade, bypass
source rights, or force scheduling precedence.

For an accepted run that needs first atlas-release enrollment, the human operator
uses the existing persisted-admission path:

```sh
npm run train -- --human-run --resume --run-dir /absolute/path/to/bamf-run \
  --admission-policy atlas-release \
  --atlas-admission-scope /absolute/path/to/enrollment-request.json
```

Expected first-enrollment boundary: `ENROLLED`, `ready_for_training: false`, and
`neural_updates: 0`. C07 derives authority from accepted B13/C09 custody; the request
file is not authority by itself. Later semantic releases remain subject to the same
source-qualified prerequisite, coverage, retained-debt and admission contracts.

## 3. Human start and resume

Only after the run is accepted and the operator deliberately chooses to begin or
continue retained learning:

```sh
npm run train -- --human-run --resume --run-dir /absolute/path/to/bamf-run \
  --minutes 90 --reserve-gib 100 --max-visits 1
```

`--minutes 90` is the default bounded wall-clock session. `--reserve-gib 100` is the
production disk floor and must not be reduced merely to make a run continue.
`--max-visits 1` is a conservative first-session bound, not a permanent curriculum
policy. The human may later choose a different finite visit bound while preserving
the same disk reserve and accepted custody.

The operator must never infer learning authority from L0-L4, a grade letter, source
list order, a staged release, or an attractive dashboard value. The admitted Factory,
retention and source authorities remain controlling.

## 4. Daily outcome snapshot

After an owner-started session, capture one read-only snapshot from the exact run:

```sh
npm run dashboard -- --run-dir /absolute/path/to/bamf-run --once --atlas-details
```

Record only values actually present in accepted evidence. A daily operator note may
attach the following fields when measured:

- exact accepted generation/checkpoint and optimizer step;
- admitted Factory release and developmental-program digests;
- source-eligible denominator, source-held count, implementation-uncovered count,
  ready/staged/admitted/exposed/qualified counts;
- selected semantic target and remediation owner when a stage intent exists;
- retained mastery/capability debt already present in accepted evidence;
- delivered visit count and retained optimizer-step change;
- measured capability or retention outcome, if the accepted producer supplies one;
- wall-clock session bound, actual terminal reason, and protected disk reserve.

Unknown fields stay `NOT MEASURED`. A source-qualified implementation hole remains in
the denominator. Source-held evidence remains distinct from implementation debt.
Grade labels are descriptive metadata only and may not change eligibility, debt
visibility, retest access, teacher scoring, promotion gates or delivered workload.

## 5. Result attachment boundary

C14.2 does not initiate a real learner in order to populate this document. Before the
human starts a session, the truthful training-result state is `NOT MEASURED`.

After owner initiation, attach results only from the real accepted run and retain the
exact source receipt or checkpoint identity. Software readiness, source coverage and
green tests are not neural-learning results. If a session stops on `HELD`, disk
reserve, explicit visit/time limit, source/admission failure or another terminal,
record that terminal rather than converting it into a success claim.

The full command semantics and observation schemas remain in
`docs/operations/BAMF_0_2_RUNBOOK.md`; this C14 guide only states how the continuing
developmental program composes those existing authorities.
