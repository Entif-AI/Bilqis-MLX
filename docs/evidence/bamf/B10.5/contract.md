# B10.5 causal bounded decoder and masked typed losses

Issue #635 (B10.5), parent #367, Lane B. Feature branch starts from synchronized
Lane B/unified `9104ce733e04fb9c82420428b18dfdbf5db49535`; B10.1/#619 and
B10.2/#623 are already merged in that lineage. The prior worker ended with a
systemError; its original worktree and uncommitted contract remain untouched.
The recovered candidate is composed with same-lane #633/#634 helpers and tensor
views. It does not compete to close #469/#470.
No main, sibling lane, real student or shared integration code is changed.

CONFORMANCE; NOT_AGENT_FACING. Extend the existing atlas_readout package in
cohesive numerical, decoder and loss owners, each below240 lines with mirrored
tests. Retain B01 tensor names/geometry and B10.1/2 source/output boundaries.
There is no second backbone or alternate architecture. The caller supplies the
already-computed causal hidden memory; this module computes only bounded readout.

## Concrete input boundary

`DecoderMemory` (frozen v1 record) contains FP32 hidden `[N,768]`, row_identities
(the ordered CompiledPosition.cache_identity tuple for each stored row), one
actual A05 CompiledFrameBatch for the selected prefix, generation_binding,
and optional `(decision_id, anchor_index)` tuple. The first P row identities must
exactly equal the compiled prefix's P position identities; later rows are never
read. P is the neural input count and must equal AnswerPlan.input_prefix_end.
The source-task SourceSpan ends within compiled.visible_end (raw source coordinate).
P may include closure positions in addition to raw atoms; budget counts neural
positions, never raw source length. Anchor defaults to P-1, and explicit anchors
are distinct known decision IDs and indices in [0,P). P must be positive.

The existing ApprovedContextProjection is required at prediction time. Its digest
must equal compiled.context_digest; compiled and plan releases match, and the
memory generation must equal the plan binding. Revalidate the actual compiled
and approved records. These inputs are computation/provenance data, not credentials
that authorize source access or B11 producer admission. B11/source owners still
supply the actual accepted hidden-state origin; fixtures do not confer it.

`ReadoutSemantics` contains the actual A06 AtlasFeatures and B02 SemanticBankView
objects. Their source release and A06 digest match the plan's FrameOutputDomain;
active banks match the plan snapshot active-set digest. Bank weights are borrowed
from the exact passed B01 `identity.bank.<n>` arrays. Feature rows and projections
come from the same parameter map. No shadow vectors, graph calls or learned
semantic identity are introduced.

Optional EPISTEMIC classification requires a B10.1 ValueHeadBinding containing
exactly five canonical released labels, their native semantic mapping and existing
registry adapter. No five-state taxonomy is invented here. If a plan requests
EPISTEMIC without that binding, prediction rejects before execution. Actual source
admission of a new classifier roster remains with its source owner.

## Numerical state and heads

For ready decision j, use the immutable last visible anchor (or its explicit
input anchor). Its role768 is the existing shared A06 role vector, including its
existing overflow feature, projected through features.project_role and scaled by
the existing sigmoid role gate. Global CONTROL uses the existing NONE role row.
Occurrence uses a deterministic768-wide sinusoid, with base10000 and the B02
sin/cos convention for every occurrence (including0..15; no trainable slot table).

Encode a ConceptRef with #633's exact active tied identity lookup. Structural
values delegate to the same `encode_feedback_value` owner, preserving its compact
typed JSON and 768-byte signed SHA256 expansion. The complete API introduces no
second structural encoder or incompatible identity path.

Feedback is the arithmetic mean of encoded already committed direct parents,
or zeros for no parents. Compute state RMSNorm(anchor+role+occurrence+
feedback @ readout.feedback.T) with readout.state_norm and epsilon1e-5.
Compute Q/K/V through existing `[192,768]` projections over that state and the
visible H only; softmax(QK.T/sqrt192), then attention @ V @ readout.output.T.
Final z is RMSNorm(state+attention_output) with readout.output_norm. Keep gradients
through H, identity feedback and all executed projections; immutable does not
mean stop_gradient. No future row, output target or descendant enters this path.

CONTROL uses B10.2 control_logits and the state's allowed control values.
Concept VALUE uses tied identity logits in the decision's legal concept order.
Structural VALUE uses dot(z,encode_value(value))/sqrt768 over its finite legal
RoleOccurrence values. ROLE uses B10.1 shared role-table head, filtered to the
exact legal candidates. EPISTEMIC uses readout.epistemic[5,768]/bias[5] with the
released five-label binding and masks to the decision's released legal subset.
Missing/invalid/empty legal domains reject, never emit NaNs or arbitrary roles.

## Inference and training

`predict_typed(memory,eligible_context,answer_plan,active_semantics,readout_params,
teacher_targets=None)` returns frozen ModelOutput: requested plan/generation,
ordered DecisionLogits records (id,kind,exact candidates,FP32 logits), actual
inference/training commits, DecodeStatus, optional validated FrameAnswer, and a
fallback_requested flag. It never computes or reruns a backbone.

Process B10.2 ready sets in stable ID order. All logits in a ready batch use only
previously committed parents. Inference commits argmax actual outputs, with stable
candidate-order ties. If teacher_targets is supplied, it is an immutable tuple of
DecisionOutput values. Each current target is used only AFTER computing that
decision's logits, to commit a teacher-forced value for later descendants.
Missing targets use the actual prediction. Future targets do not influence earlier
logits. Validate target IDs/types/legal values before neural execution, but do not
use their values to select ready sets before their own decision executes.

END_FRAME is committed alone. COMPLETE publishes only through B10.2 source
validation. A source-invalid neural answer returns UNRESOLVED with fallback=True;
PARTIAL preserves budget exhaustion and never publishes an unchecked frame.
Structural input/parameter errors retain the existing typed ErrorBus failure.
Only successfully committed decisions retain logits in ModelOutput. Construction
and loss revalidation replay the stable ready batches, require an exact typed
legal candidate tuple for every committed decision, and reject missing, reordered
or unexecuted records. A failed batch contributes no fabricated supervision.
Unknown/alternatives follow the existing B10.2 typed control/value transitions.

`answer_loss(output,targets,mask)` computes stable cross entropy only for executed
legal decisions with supplied targets and explicit true mask. Missing labels or
false masks contribute exact differentiable zero. The primary VALUE/CONTROL terms
have weight1; optional ROLE and EPISTEMIC terms have weight0.10 each. Mean within
each kind before weighting, so missing auxiliaries never fabricate supervision.
Return typed LossParts (primary,role,epistemic,total). Other optional salience and
frame/atomic consistency losses retain their existing owners and labels; no
supervision is invented for them. Gold is never an inference input or source grant.

## Proof

RED/GREEN CPU tests independently reconstruct the decoder equation with NumPy;
verify fixed-prefix invariance under changed future rows and current/descendant
targets; prove inference uses actual parent selection while training uses only
prior targets; test legal/active masking, invalid-source fallback, PARTIAL, UNKNOWN
and alternatives, exact completed-frame validation, missing auxiliary zero loss,
and finite gradients reaching executed identity/role/control/feedback/attention
weights and H. No real training or learner-state mutation occurs.

## Readiness freeze

Production owners live under `atlas_readout/decoder/`: `inputs.py` owns
DecoderMemory, ReadoutSemantics and source/context validation; `feedback.py` owns
typed value expansion, occurrence and shared role vectors; `math.py` owns B01
parameter validation, K/V precomputation and numerical state; `heads.py` owns
legal per-kind logits; `execution.py` replays causal commit receipts;
`prediction.py` owns ModelOutput and bounded execution; `losses.py` owns LossParts
and masked answer_loss. Tests mirror each owner as `decoder/tests/test_<owner>.py`;
`tests/helpers.py` supplies disposable fixtures, and `test_training.py` proves
cross-owner gradient flow. This corrects the recovered draft's provisional file
names without changing the frozen algorithm. Public exports extend only the
existing atlas_readout package. No shared trainer or C02 changes. Each new
production/test file remains below 240 lines.

`active_semantics` is exactly ReadoutSemantics, whose fields are `features:
AtlasFeatures`, `banks: tuple[SemanticBankView,...]`, `extents: GenerationExtents`,
and `epistemic_binding: ValueHeadBinding | None = None`. The optional binding is
explicitly assigned to this classifier by the source/head owner; it must retain
an actual registry adapter (not semantic_token), exactly five unique canonical
labels, matching release/active-set identity, and active mapped ABI entries.
Before any EPISTEMIC execution, revalidate it through the existing B10.1 binding
path and require every such decision's legal strings to be a nonempty subset of
its exact ordered five labels. Missing/foreign/mismatched bindings raise the
existing typed topology error before decoder execution. This adds no taxonomy.
Fixtures register a clearly synthetic five-label source adapter over a disposable
snapshot; they never assert a production release or source admission.

`DecoderMemory.anchors` is a tuple of `(decision_id: str, anchor_index: int)`
pairs, default empty. Reject duplicate IDs, nonexact types, unknown current-plan
IDs and anchors outside [0,P). Missing IDs use P-1. No future anchor is legal.

The prior plan check `source_span.end <= input_prefix_end` is retained: it is a
weaker preliminary bound, not a conflicting source/neural equality. A05's
`_canonical_position_order` requires every raw atom0..visible_end-1 and allows
additional closure positions, hence P>=compiled.visible_end. For raw8/P9,
source_span.end8 satisfies the existing check8<=9. Prediction adds the stronger
check span.end<=compiled.visible_end and exact P==plan.input_prefix_end; no source
interval is silently relabeled as a neural index.

Structural feedback serialization and signed-byte expansion are owned by #633's
`causal_training.encode_feedback_value`. Its canonical Enum representation of
EMIT_VALUE is compact UTF-8 JSON `{"enum":"ControlAction","value":"EMIT_VALUE"}`.
SHA256(payload + b"|" + ASCII decimal block) blocks 0..23 supply 768 bytes.
Each byte maps to `(byte/127.5-1)/sqrt(768)`, cast FP32. A literal full-vector
fingerprint pins this consumed owner. This replaces the recovered candidate's
provisional signed-bit/publication-JSON choice; no released format is changed.
Concept feedback remains its exact active tied identity row. `decision_hidden`
owns mean committed feedback and the state normalization; composition adds the
shared role/occurrence input and B01 norm gamma, attention and final norm.
`typed_decision_loss` owns per-head cross entropy. `bind_readout_parameters`
from #634 owns the complete readout name/shape/dtype/finite boundary.

RMSNorm is exactly `(x * rsqrt(mean(x*x)+1e-5)) * gamma`, using the corresponding
readout.state_norm or readout.output_norm vector. Projection uses row vectors
and stored output-input matrices, so every linear application is x @ weight.T.

ModelOutput records execution mode INFERENCE or TEACHER_FORCED explicitly.
Teacher-forced completed frames are training outputs and never evidence of
unassisted inference. No inference call receives the target tuple by default.

Current BindingState has VALUE, NONE, UNKNOWN and ALTERNATIVES. This child preserves
UNKNOWN/alternative states and does not invent an EMPTY_SET source identity.
The parent's broader empty-set semantics remain with actual source admission.
