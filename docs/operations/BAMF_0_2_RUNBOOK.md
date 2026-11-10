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

C16.1a/#542 owns the human-facing persistent v2 lifecycle over the generation-zero
boundary documented in `BAMF_0_2_FIRST_STUDENT.md`. Run these commands from the
repository root in an environment with the project's Python dependencies installed.
A fresh dry-run requires the complete foundation identity but does not create the
target directory:

```sh
npm run train -- --dry-run --model-topology configs/models/bamf-0.2.json \
  --atlas-release-manifest /absolute/path/to/manifest.json \
  --run-dir /absolute/path/to/new-bamf-run --run-id example-run --run-seed 543 \
  --learning-rate 0.0007 --adam-beta1 0.88 --adam-beta2 0.97 \
  --adam-eps 1e-7 --weight-decay 0.03 --source-prefetch-workers 0
```

Expected: exit **0** with JSON schema `bilqis.bamf.operator-lifecycle/v1`, result
`READY_TO_CREATE`, `ready_for_training: false`, `neural_updates: 0`, and the exact
run identity, topology, source-qualified Atlas identity, optimizer hyperparameters,
and prefetch setting. Dry-run replays the source/Factory and Atlas foundation
authority but publishes no generation and performs no optimizer update.

The default admission policy is `staged`. An actual create requires the same
foundation fields plus the explicit human gate:

```sh
npm run train -- --human-run --model-topology configs/models/bamf-0.2.json \
  --atlas-release-manifest /absolute/path/to/manifest.json \
  --run-dir /absolute/path/to/new-bamf-run --run-id example-run --run-seed 543 \
  --learning-rate 0.0007 --adam-beta1 0.88 --adam-beta2 0.97 \
  --adam-eps 1e-7 --weight-decay 0.03
```

This publishes B13 generation zero at optimizer step `0` and returns `CREATED`; it
still does not enter the learner. The Atlas manifest must be a canonical,
source-pinned release manifest. The target must be absent or empty. Existing BAMF
or legacy custody is never overwritten or coerced.

To enroll the new lineage in the C07 `atlas-release` admission policy, add both the
explicit policy and a versioned lease request:

```sh
npm run train -- --human-run --model-topology configs/models/bamf-0.2.json \
  --admission-policy atlas-release --atlas-admission-scope /absolute/path/to/lease.json \
  --atlas-release-manifest /absolute/path/to/manifest.json \
  --run-dir /absolute/path/to/new-bamf-run --run-id example-run --run-seed 543 \
  --learning-rate 0.0007 --adam-beta1 0.88 --adam-beta2 0.97 \
  --adam-eps 1e-7 --weight-decay 0.03
```

The scope file is request data, not authority. The lifecycle validates its known
lineage/topology/Atlas fields before publication, publishes generation zero through
B13, then obtains an opaque C09 capability from `AcceptedRuntimeHost` and asks the
C07 owner to persist and read back the exact lease against accepted run custody.
The CLI never receives or constructs a raw source-authority registry. Generation-zero
publication and C07 persistence remain sequential existing transactions: if the
post-genesis lease check fails, no `atlas-release` current reference is installed;
the lawful generation-zero run remains staged rather than being counterfeited as
admitted.

Resume derives saved settings from accepted custody and performs no neural update:

```sh
npm run train -- --dry-run --resume --run-dir /absolute/path/to/bamf-run
```

Expected: `READY_TO_RESUME` with the saved run id/seed, topology, Atlas identity,
optimizer hyperparameters, and effective admission policy. Explicit topology,
run-id, seed, optimizer, Atlas-manifest, or policy overrides must equal the saved
values or fail before writes. A caller may not substitute an Atlas lease scope on
resume. Historical v1 state is not coerced to v2.

Existing trainer help can also be inspected without a neural update:

```sh
npm run train -- --help
```

C11.2's bounded reader remains available for historical inspection. The persistent
v2 lifecycle above consumes accepted B13/C09/C07 custody and validates saved
topology/admission settings, but C16.1a still stops before later learner execution.
The existing 100 GiB reserve remains unchanged.

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
