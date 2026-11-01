# BAMF-0.2 operator observation commands

Status: **C11.2 staged reader, production launch pending C11.1 #522**.
This document does not authorize a durable student start or certify BAMF learning.

## Read-only cockpit

Use the exact run directory. The existing watcher reads saved state and complete
journal records; it does not acquire the trainer lock or update the student,
optimizer, teacher, admission lease or journal.

```sh
npm run dashboard -- --run-dir /absolute/path/to/run --once
npm run dashboard -- --run-dir /absolute/path/to/run --once --atlas-details
npm run dashboard -- --run-dir /absolute/path/to/run --atlas-details
```

The first two commands render one snapshot. The third follows the journal until
interrupted. `--atlas-details` expands the BAMF observation panel when a compatible
observation is present. It does not make a historical run a BAMF run. A fresh
subprocess test exercises the expanded snapshot against a disposable journal and
checks its bytes, modification time and directory contents remain unchanged.

The two-row main cockpit keeps its existing metric owners. The additional Atlas
panel shows the complete declared source-eligible denominator, source-held and
implementation-uncovered counts, ready/staged counts, active concepts and banks.
Expansion shows admitted/exposed/qualified counts, atoms per frame, fallback,
expansion and motif-hit fractions, plasticity mode, memory use/budget, and exact
source/model/evaluator/rights/census digests. A source-qualified implementation
hole remains in the denominator. Source-held concepts remain a separate count.
The status counts form a disjoint partition of the declared eligible census.

The learning line reads existing SchoolTelemetry GREW and retained-step counters.
Ten retained steps with no measured capability change display GREW +0. Staging,
retention, measured gain, debt, perfect mastery and transfer remain separate.
Missing debt, mastery and transfer measurements explicitly say NOT MEASURED.
This reader does not schedule fresh generalization, confer promotion authority,
or introduce a grade-specific teaching policy.

## Observation receipt

The reader accepts `bilqis.bamf.operator-status/v1` under saved-state key
`bamf_operator_status`, or an append-only journal event named
`BAMF_OPERATOR_STATUS_OBSERVED` with a `receipt` object. This is a proposed
presentation boundary, not an implemented B13/A12 producer contract. It validates
schema, complete nonnegative coverage counts, source/model/evaluator/rights/census
SHA256 syntax and finite observations before replacing the last valid view.
A malformed journal observation leaves that view intact and the watcher reports
the failure through its existing log channel.

Structural validation does not verify the referenced source release, producer,
checkpoint, evaluator or rights artifact. Actual source/custody owners must issue
and qualify these observations before production use. The current tests use
explicit synthetic receipts and do not establish producer acceptance or learning.

## Preflight, launch and resume boundary

C11.1 #522 / draft PR #632 owns production BAMF create, preflight, saved admission
policy/manifest and conflicting-override rejection. Those interfaces are not yet
accepted on the consumed unified baseline. Therefore this runbook deliberately
publishes no executable BAMF start/resume recommendation. Existing trainer help
can be inspected without a neural update:

```sh
npm run train -- --help
```

Complete C11.2 turn-in still requires #522's actual parser-tested preflight,
owner-start and resume commands, accepted source/custody receipts, and a real
operator-state readback. The operator alone starts or resumes the durable student.
The existing 100 GiB reserve remains unchanged.
