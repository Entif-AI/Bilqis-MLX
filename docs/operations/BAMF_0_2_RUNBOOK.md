# BAMF-0.2 operator observation commands

Status: **C11.1 read-only configuration inspection and C11.2 reader integrated;
production launch pending C11.1 #522**.
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

C11.1's read-only v2 configuration inspection is integrated through PR #678.
Run these commands from the repository root in an environment with the project's
Python dependencies installed. Inspect the checked-in topology and a new,
explicit run path without creating that directory:

```sh
npm run train -- --dry-run --model-topology configs/models/bamf-0.2.json --run-dir /absolute/path/to/new-bamf-run --source-prefetch-workers 0
```

Expected: exit **2**, with JSON schema `bilqis.bamf.operator-preflight/v1`, result
`HELD_PENDING_SOURCE_AND_GENERATION_AUTHORITY`, `ready_for_training: false` and
`neural_updates: 0`. Exit 2 with that report means configuration inspection
completed and training remains held. Exit 2 with `BLOCKED` on stderr and no report
means a request was refused. Neither result grants training or admission authority.
The npm wrapper prints its command banner before the JSON report.

The default admission policy is `staged`. To inspect an existing Atlas manifest
reference, select its distinct policy explicitly:

```sh
npm run train -- --dry-run --model-topology configs/models/bamf-0.2.json --run-dir /absolute/path/to/new-bamf-run --source-prefetch-workers 0 --admission-policy atlas-release --atlas-release-manifest /absolute/path/to/manifest.json
```

The manifest must be an existing regular file, not a symlink. Inspection hashes
its raw bytes without interpreting its contents. The report records its absolute
path and SHA-256 with `qualification: NOT_VERIFIED`; a matching digest does not
qualify source rights, release semantics or generation custody. Supplying this
reference with `staged`, or selecting `atlas-release` without it, fails closed.
`--atlas-admission-scope` is a separate C07 lease request and is refused by this
configuration inspector.

For an existing BAMF run directory, add `--resume` to the same inspection command.
It checks only for a `bamf-state.json` path or symlink, including a dangling
symlink; it does not establish that the path is a valid pointer file. It does not
load or validate the pointer, checkpoint arrays, saved policy or optimizer. The
report stays held. An
existing BAMF pointer without `--resume`, a missing pointer with `--resume`, or
any legacy `state.json` is refused; inspection never coerces a legacy lineage.

Existing trainer help can also be inspected without a neural update:

```sh
npm run train -- --help
```

C11.2's bounded reader is integrated and closed under ADR-121. Production C11
acceptance still requires #522's actual create/resume path, persisted admission
policy and conflicting-override proof, accepted A12/B13/C05/C07 source/custody
receipts, and a real operator-state readback. These inspection commands do not
start or resume a learner, verify saved topology compatibility or measure runtime
memory and disk headroom. The operator alone starts or resumes the durable
student. The existing 100 GiB reserve remains unchanged.

The resource/rubric panel describes current Factory assessment as fresh routine,
fixed promotion and inactive generalization. Historical rubric descriptions are
labeled `Historical policy (lineage only)`; they do not select BAMF scheduling or
assessment. C11.3/#524 full candidate/source/delivery/debt/promotion/retention/transfer
provenance and launch/resource acceptance remain pending production observations.


## Separate operator evidence

The optional `evidence` mapping on `bilqis.bamf.operator-status/v1` provides a
read-only observation projection. Old records without it remain readable.
`--once --atlas-details` appends a complete observation report outside the fixed
terminal viewport. Redirect or scroll this snapshot to inspect every row and full
digest, even at 80x24 or with many debt/policy rows. The followed live panel remains
viewport-limited and points to that complete snapshot command. The report shows
candidate and parent SHA-256 identities, the delivered-work
receipt digest and actual delivered row count, grade debt, capability debt,
promotion-attempt count, whole-school fresh retention and learned-transfer counts
on separate lines. Each score has its own exact source and rubric digest lines.
These observations do not replace the existing retained-step or GREW owners.

The wire keys are `candidate_sha256`, `parent_sha256`, `delivered_work_sha256`,
`delivered_rows`, `grade_debt`, `capability_debt`, `promotion_attempts`,
`whole_school_fresh_retention`, `learned_transfer` and `historical_policies`.
Debt values are mappings from display labels to nonnegative counts; the reader
sorts labels for display and never gives a grade scheduling authority. Score
records contain exactly `correct`, `total`, `source_sha256` and `rubric_sha256`.
Missing observations display NOT MEASURED. Measured empty debt displays none.
Zero-total scores display NOT MEASURED and retain their source/rubric identities;
zero counts remain zero. A measured debt collection does not imply that an absent
sibling collection was measured. Historical policies are explicitly lineage only.

Labels accept 1..96 printable Unicode code points without controls or surrogates.
The existing terminal renderer uses ASCII. This panel preserves Unicode labels as
JSON Unicode escapes rather than collapsing distinct labels into question marks.
Frozen records detach the displayed view from mutable incoming mappings.
Malformed evidence rejects the complete incoming observation before replacing the
previous valid view. The detached watcher test exercises these lines and verifies
the journal bytes, modification time and directory membership stay unchanged.

These remain structurally checked supplied observations. This reader neither
verifies producer/source/evaluator authority nor fabricates measurement from
activity, retention counts or grade labels. A learned-transfer observation is not
a newly scheduled GENERALIZATION cohort or promotion authority. Current fresh
generalization remains inactive. Production observation issuance and complete
launch/resource custody still require #522/B13/A12 and the relevant C05 owner.
