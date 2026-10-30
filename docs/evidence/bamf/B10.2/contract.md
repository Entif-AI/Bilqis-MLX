# B10.2 finite CONTROL and structured output

Issue #468, parent #367, Lane B. Consumed unified/Lane B:
`a02b9ed45ead1801be6dff655866b73be0ffc8ff`. Issue branch starts there and merges
the exact same-lane B10.1 dependency `569bc43531921c6c1ac6178d5ed953b006039800`
(PR #619, independently EGM-clear). Shared Lane B and unified are unchanged.
PR targets unified and identifies this dependency; no cross-lane merge is used.

Change posture CONFORMANCE; interface NOT_AGENT_FACING (internal model records).
B10.3 retains neural decoder-state computation, causal feedback and answer_loss.
This child implements final CONTROL logits, immutable structured answer plans,
dependency-ready scheduling, output budgets and validated frame publication.

## Files and records

Create `learning/atlas_readout/control.py`, `plan.py`, `decisions.py` and `frames.py`,
with mirrored package-local tests. Extend only the existing readout __init__ exports.
Retain the B10.1 heads, registry adapters, source schemas and all B01 tensor paths.
All boundary failures use existing ErrorBus SCHOOL.MODEL_TOPOLOGY.INVALID; source
frame validators retain their own typed errors. Frozen records validate their
versions, exact field types, duplicate identities and immutable tuple members.

`ControlAction` is an ordered string enum: EMIT_VALUE, EMIT_UNKNOWN,
EMIT_ALTERNATIVES, END_FRAME. `control_logits(z, parameters, semantic_release,
can_end)` reads only `readout.control[4,768]` and `readout.control_bias[4]` from B01.
It returns B10.1 TypedHeadLogits, omitting END_FRAME when can_end is false.
Parameter and input tensors are FP32, finite and correctly shaped. ROLE tensors
never enter CONTROL. Selected CONTROL output is an enum, never a role string.

`DecisionKind` is VALUE, ROLE, CONTROL, EPISTEMIC. `DecisionSpec` contains decision_id,
role_id (str or None), occurrence (nonnegative int), kind, legal_values (nonempty
immutable tuple), and depends_on (unique IDs tuple). VALUE legal values in this
structured slice are ConceptRef or RoleOccurrence; ROLE values are RoleCandidate;
CONTROL values are ControlAction; EPISTEMIC values are nonempty strings. All
choices within a decision have the same type and are unique. RoleOccurrence
supports explicit NONE/UNKNOWN/ALTERNATIVES without inventing a semantic token.

`AnswerPlan` uses schema `bilqis.mlx.answer-plan/v2`, with modality_id,
input_prefix_end (0..1024), ordered decisions, allowed_output_schema
(B10.1 FrameOutputDomain), snapshot (A01 FrozenAtlasSnapshot), maximum_decisions
(1..64, default64), and generation_binding (nonempty string). Snapshot release
and Atlas/source bundle IDs match the domain's A03 release. Missing parents,
duplicate IDs and cycles reject at construction. Topological order uses ready
sets sorted by decision_id; it is independent of input tuple order.

The plan only authorizes schema roles and occurrence indices below their released
maximum cardinality. ROLE choice keys must match exact schema ID/revision and the
decision's occurrence. VALUE, UNKNOWN and ALTERNATIVES bind the decision's declared
role coordinate. A missing coordinate rejects these bindings; a global END_FRAME
CONTROL may use role_id=None. This child never creates an input FrameInstance or
source grant from a predicted answer.

## State transition

`DecisionOutput` freezes a decision ID and selected value. `DecodeState` contains
one AnswerPlan and the ordered committed outputs. Records use v1 schema strings.
`start_decoding(plan)` yields empty state. `ready_decisions(state)` returns only
uncommitted decisions whose parents were already committed, sorted by ID and
bounded by remaining output/position capacity. Independent decisions may be
committed together; a parent and its child cannot commit in the same batch.
`parent_outputs(state,id)` returns only previously committed parents in the
DecisionSpec's declared dependency order; missing parents reject.

`commit_decisions(state, outputs)` requires a nonempty unique-ID tuple drawn only
from the prior ready set. Every selected value must exactly match a legal value,
including its concrete type. It returns a new state and preserves the parent.
Each committed output consumes one decision and one generated position.
Remaining capacity is min(maximum_decisions,1024-input_prefix_end)-committed_count.
At exhaustion without END_FRAME, status is PARTIAL; no unchecked answer is
published. If no legal ready decision remains before END_FRAME, status is
UNRESOLVED. Otherwise status is ACTIVE. END_FRAME makes status COMPLETE only
after full source-schema validation. No commits follow END_FRAME.

`frame_bindings(state)` derives exact RoleOccurrence values from committed VALUE
and UNKNOWN controls in schema-role/occurrence order. ALTERNATIVES is supplied as
a typed RoleOccurrence VALUE and requires a prior EMIT_ALTERNATIVES control for
that same coordinate; ordinary concept VALUE similarly requires prior EMIT_VALUE.
EMIT_UNKNOWN itself commits UNKNOWN. CONTROL decisions selecting EMIT_VALUE or
EMIT_ALTERNATIVES reserve no completed binding by themselves. Duplicate completed
coordinates reject. A role-prediction output is an exact reference, not a value
binding. NONE is an explicit RoleOccurrence value, distinct from UNKNOWN and
from an empty-set ConceptRef.

`can_end_frame(state)` checks the accumulated bindings with the existing
semantics.frame_schema.validate_frame_bindings, A01 snapshot, schema.scope and
input-prefix span. A validation failure means END_FRAME is currently unavailable.
`publish_frame(state)` requires COMPLETE and returns frozen FrameAnswer containing
schema ID/revision, validated bindings, semantic_release and generation_binding.
Only existing source validation decides active identity/types/cardinality; no
second schema or semantic registry is introduced. B10.3 will supply decoder
states/selected outputs and the training/inference feedback distinction.

## Tests

Use disposable MLX CPU tensors. RED/GREEN covers four fixed CONTROL outputs and
ROLE/control weight separation, schema occurrence bounds, stable topological
ordering, cycles/missing parents, independent batching vs dependent waits,
parent-only feedback exposure, early END_FRAME rejection,64-decision and combined
1024-position exhaustion with typed PARTIAL, immutable parent state, complete
source-schema validation, duplicate role bindings and UNKNOWN vs explicit NONE.
Full neural decoder, supervised feedback/loss and human-run learning stay separate.

## Readiness clarifications

CONTROL head candidates are the exact string values of ControlAction, preserving
B10.1 TypedHeadLogits unchanged. The caller converts the selected string to the
enum before committing DecisionOutput; the scheduler never accepts a plain role
string as a control. No records.py union change is needed.

AnswerPlan additionally retains `source_span: SourceSpan` from the source task
contract, with `source_span.end <= input_prefix_end`. It is propagated unchanged
to the existing binding validator. Publication does not turn this interval into
an input-source frame or a grant.

Each VALUE decision must directly depend on exactly one CONTROL decision whose
role_id/occurrence is the same coordinate. That direct dependency is the pairing
key; arbitrary earlier commit order is insufficient. Each output coordinate has
at most one binding-producing CONTROL decision and one VALUE decision. A global
END_FRAME-only CONTROL has no coordinate. A coordinate CONTROL may choose VALUE,
UNKNOWN, ALTERNATIVES (and END only when the whole frame validates). UNKNOWN
produces its binding immediately and makes the paired VALUE decision unavailable.
A ConceptRef or explicit NONE VALUE requires its direct paired parent to have
selected EMIT_VALUE; typed ALTERNATIVES requires EMIT_ALTERNATIVES. A concrete
RoleOccurrence VALUE must match the decision coordinate, never carry a child
frame, and may not encode UNKNOWN through the VALUE path. Source validation is
still required before END/publication. No pairing state is inferred from grade
names, role spelling or an unrelated control event.

Additional executable details: END_FRAME is a publication barrier and must commit
alone, even if optional sibling decisions are dependency-ready. The output-source
helper `output_sources.require_active_value` checks active A01 ABI identity at
plan construction and publication, supplementing the existing frame validator's
role/type rules. No inactive row can be published merely because its semantic ID
and type exist. Output records preserve the complete typed plan for validation;
FrameAnswer exposes schema ID/revision, source release and generation as properties.

## Exact carrier and validation details

CONTROL results have modality_id `answer.control/v1`. For input shape
`[...,768]`, CONTROL logits retain every leading dimension and have final axis4
when END_FRAME is permitted, otherwise3. Candidates are the corresponding ordered
string tuple. This reuses [B10.1 TypedHeadLogits](../B10.1/contract.md): finite
nonempty FP32 data, uniform unique candidate type, matching final axis and
64-hex source release. No softmax or argmax is applied by this head.

The new records are immutable in-memory dataclasses with explicit schema fields;
this slice does not add a checkpoint serializer or storage publication format.
`DecisionOutput(decision_id,value,schema_version)` defaults to
`bilqis.mlx.decision-output/v1`. The ID is a nonempty exact str. Value is exactly
ControlAction, ConceptRef, RoleOccurrence, RoleCandidate or nonempty str;
source record constructors are rerun. DecisionKind then narrows that union and
commit validates exact type plus equality against the declared legal values.

`DecodeState(plan,committed,schema_version)` defaults to
`bilqis.mlx.decode-state/v1`; committed defaults to the empty tuple. It requires
an exact AnswerPlan and tuple of exact DecisionOutput records, not exceeding the
plan's combined capacity. Construction replays every output in order: reject
unknown/duplicate IDs, missing earlier dependencies, illegal values, mismatched
control/value pairs, any output after END_FRAME, and duplicate bound coordinates.
This validates externally reconstructed state as well as normal commit returns.

`FrameAnswer(plan,bindings,schema_version)` defaults to
`bilqis.mlx.frame-answer/v1`. Both plan and each RoleOccurrence are exact typed
records; bindings is a tuple. Construction reruns plan and full source binding
validation and requires canonical schema-role/occurrence ordering. The plan
supplies schema ID/revision, semantic release and generation properties. Only
`publish_frame` additionally requires a COMPLETE DecodeState; callers cannot
publish an unchecked or budget-exhausted state through that API.

Active-source validation inspects a ConceptRef itself, a RoleOccurrence's concept,
or each of its alternatives. NONE/UNKNOWN carry no concepts to inspect. Every
concept must have the snapshot's semantic release; snapshot.abi_for_semantic must
return its exact semantic ID and ABI index with active **is True**. A malformed
snapshot lookup IndexError/TypeError becomes the existing topology ErrorBus error;
canonical source lookup failures retain their own typed errors. The same checks
run on all VALUE choices before execution and on actual bindings before ending
or constructing an answer. Existing source validation separately checks type,
cardinality, repeated indices, source release and scope. These checks do not
issue rights, context grants or semantic admission.

Terminology and owners: A01 is the canonical semantic Atlas snapshot
(`semantics.atlas_projection.FrozenAtlasSnapshot`), ABI is its stable semantic
index allocation, A03 is the immutable released frame-schema authority
(`semantics.released_frame_schemas`), and B01 is the frozen neural tensor ledger
(`runtime.model_topology_v2`). A source bundle is the snapshot's immutable source
artifact identity. B10.1 FrameOutputDomain retains a schema and its A03 witness;
its complete contract and definitions are linked above. ErrorBus is the existing
`errors.bus` typed catalog boundary, raising BilqisError. The overarching owner
prescription is [BAMF architecture section25.2](../../../architecture/BAMF_0_2.md)
and the public issue #468; this document describes this child's bounded API.
