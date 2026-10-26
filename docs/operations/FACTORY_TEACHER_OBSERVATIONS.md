# Replayable Factory teacher observations

Issue #333 adds evidence to the existing visit path. It does not select an action,
change teacher credit, draw source rows, run inference or alter candidate retention.
The six-field `DeliveredTeaching` contract remains unchanged.

## Evidence chain

`runtime.teacher_observation_capture` records a pre-construction proposal after the
existing selector returns. Its immutable sidecar includes the released option and
provider, offered options/policies, effective controls, selection route, source
context, pre-action region, policy/evidence epoch and experimental partition.
The initial diagnostic source draw retains its original position before selection.

Each optimizer step records ordered content-addressed row references, including
repeated rows, role membership, source/provider identity, actual guidance and its
mentor provenance, and realized controls. The selected-option subrecord reuses
`DeliveredTeaching`; support, replay, prior rehearsal and enrichment remain visible
in the enclosing batch. Storing row bytes does not grant teaching or gold authority.

After the existing retention decision and teacher update, the observation records
raw paired scores/denominators, target and protected effects, fixed-grade/frontier
measurement states, attempted/retained steps and monotonic host wall time. The cost
boundary begins at visit entry and ends at observation finalization, including
existing source work/inference and capture overhead before finalization. It is not
GPU-only time or a prediction of cost. No additional inference is introduced.

The event initially describes a RAM outcome. Canonical checkpoint publication adds
a checkpoint/generation join through the existing outbox. `read_committed_observations`
verifies exact membership in the immutable generation before treating an observation
as durable. Journal plus current outbox read back as one logical observation, even
if the process stopped after state commit but before journal emission. Reconciliation
uses the existing idempotent outbox; the reader never repeats optimizer or teacher
work. Unpublished sidecars are staging evidence, not durable learner outcomes.

## Identities and missingness

Factory envelope: `bilqis.factory.teacher-observation/v1`.
Proposal: `bilqis.factory.teacher-proposal/v1`.
Policy/evidence epoch: `bilqis.factory.teacher-evidence-epoch/v1`.
Outcome: `bilqis.factory.teacher-outcome/v1`.
Summary: `bilqis.factory.teacher-observation-summary/v1`.

`MeasurementStatus` distinguishes `MEASURED` from `NOT_MEASURED`. Target-only
rejection and empty protected measurement scopes never imply zero loss. Partial
grade evidence is not a whole-grade band. Missing costs/predictions, undefined
ratios, calibration and shadow probes retain explicit missingness.

The bounded region uses portable v1 bands and declared capability ownership;
checkpoint/run/cohort/specimen identifiers remain provenance. #320's actual
`ModelTopologySpec` record, implementation and initialization origin/seed remain
separate experimental context. Topology and policy epochs partition comparisons,
without becoming predictive region keys. Evolving teacher statistics do not mint
a new policy epoch. Changed implementation, baseline controls or source/release
bindings do. Policy configuration is evidence, not teacher truth.

For fully measured compatible records, `portable_v1` uses the unchanged #321 v1
contract and fixture. Partial records carry `NOT_MEASURED` instead of a fabricated
fully measured portable record. No estimator or learned controller is imported.

## Read-only reconstruction

```python
from bilqis_mlx.runtime.teacher_observation_replay import read_committed_observations
from bilqis_mlx.learning.teacher_observations import summarize_observations

observations = read_committed_observations(run_directory)
summary = summarize_observations(observations)
```

This is an offline forensic/reporting API. It validates the immutable generation,
proposal and ordered delivery joins. It does not repair a corrupt artifact or
reinterpret a historical pre-v2 lineage as executable. The existing operator retains
neural-update authority. Three disposable test owners cover missingness, native
instrumentation-on/off equivalence, topology/epoch partitioning and crash replay.
