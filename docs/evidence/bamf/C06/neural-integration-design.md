# C06 supervised salience integration design

Status: revision 3 design approved after targeted fresh EGM re-audit.
Implementation and behavioral verification remain outstanding.
Authority: #379, BAMF-REQ-018, inherited C06.1–C06.4 acceptance. This is
DECOMPOSE of required parent integration, new_acceptance=false.
Baseline: reviewed unified 036e0aa3c. Integration consumes accepted C03/B11 interfaces.

## Current gap

The accepted C06 helpers derive signed labels and B01 head projections, but
B11's actual forward/gradient path never reads those heads. C02's Factory bridge
already compiles real A05 prefixes and carries B13/C09 source authority. Reuse it.

## Interfaces and ownership

Add runtime/_model/salience_training.py, with mirrored tests under
runtime/tests/model/salience/. Keep every new file below 240 lines.

`SalienceSupervision` retains the original issued C02 batch, signed row records,
its AuthoritySnapshot, SourceExecutionContext, and existing-auxiliary verifier.
It is an ephemeral execution input, never an accepted generation or source issuer.

`prepare_salience_training(prepared, source_context, records, snapshot,
verify_existing)` calls existing attach_salience_labels. It rebinds each actual
BamfCompiledBatch through bind_compiled_training_batch to the labelled C02 batch,
using unchanged source rows, A05 inputs, feature schema and active semantic rows.
Register rebound batches with the same source context for C09 correction tracking.
Return the same PreparedFactoryTrainingBatch shape plus SalienceSupervision.

`SalienceSupervision.labels_for(compiled)` re-enters attach_salience_labels on
its original batch at consuming time. Require current SourceExecutionContext via
`require_accepted_runtime(source_context.run_dir)` and resolve verifier material
inside runtime using `_accepted_correction_registry(run_dir)`. Require the
AuthoritySnapshot registry digest to equal that accepted registry digest and its
context generation to equal the current cache.generation_binding. Re-register
compiled owners to replay pending accepted corrections; call
compiled.atlas_feature_artifact_owner.require(compiled.compiled.features) and
compiled.compiled.packed_frame_artifact_owner.require_row(the exact prefix).

Create SalienceEvidenceArtifactOwner under runtime/_correction/owners. Append
SALIENCE_EVIDENCE to ArtifactKind and add owner_priority mapping `(2, 3)` in
atlas_revalidation_common.py; these queue ordinals never grant source authority.
Use a valid closed DependencyIndex with one node per policy, signed fact and row
binding, plus one derived-label node. Policy nodes depend on the signed POLICY
salience-policy:<id> key. Each fact node is named salience-fact:<id> and depends
on its policy node plus exact C02 row provenance non-ARTIFACT dependencies.
SOURCE-origin facts additionally depend on SOURCE salience-fact:<id>. Outcome
fact nodes use their own content digest and verified artifact signature; never
add a self ARTIFACT reference. Row binding nodes are named salience-row:<row-id>,
with signed binding content, and depend on every relevant fact/policy node. The
derived-label node depends on these row-binding nodes. No ARTIFACT edge points
outside this same index; every such reference resolves to its content-checked
node. All nodes additionally carry the exact C02 row provenance dependencies.
These are existing owner-derived keys from `_row_immediate_dependencies`:
SOURCE row/source ID, RELEASE release:<semantic-release>, POLICY
policy:<digest(scope, policy_version[0:2])>, RIGHTS
rights:<digest(policy_version[2:4])>, OPERATOR operator:<operation-id>, and when
contextual TIME time:asof:context:<prefix.context_digest>. Copy the actual
DependencyRef objects from provenance rather than reconstructing these keys.

Register through register_accepted_target(run_dir, accepted_manifest_sha256,
"SALIENCE_EVIDENCE", owner). Its generic `_route` already routes corrections;
no new ingress branch. Implement apply_correction/advance/require with existing
C09 queues and read_artifact. For every read, require_pending_corrections runs
on all required nodes in dependency order. Source/rights corrections therefore
reach the same keys as actual C02/A05. Accepted A13 context transitions match
TIME time:asof:context:<old-context>, exactly as apply_context_invalidation does;
the copied row context dependency makes those invalidations reach this owner.
Implement `_install_context_revalidation` to retain the generic updated index,
but never materialize changed labels from metadata alone: changed policy, rights
or context requires new signed C06 evidence and prepare. A stale supervision
record rejects; recreate only through the real owner-signing/validation path.
No unavailable current authority or changed registry/generation is accepted.

Compare re-derived labelled_batch.authority_digest specifically to
compiled.training_authority.training_batch_sha256. That digest binds provenance,
not labels. Add optional auxiliary_labels_sha256 to BamfTrainingAuthority, populated
by bind_compiled_training_batch from canonical digest of the exact row.auxiliaries
when nonempty; copy it in extend_training_dependencies and conditionally include
it in authority.digest. With no auxiliaries use None and preserve old digest bytes.
Compare canonical digest of re-derived row.auxiliaries with that separate field.
Require exact source-row ID/content, capability, generation, family and A05 prefix
equality. Select labels only from re-derived row tuples; never from a raw caller
map. Changing a label, origin or receipt without its signed binding rejects.

Factory `execute_factory_candidate_step` accepts optional keyword-only
`salience_provider=None`. When supplied it must be callable; after real C02 prepare
it receives the immutable PreparedFactoryTrainingBatch and returns
`SalienceLabelRequest(records, snapshot, verify_existing)`. This is the explicit
source/evaluator-owned signing opportunity for the exact prepared rows; the
callback grants no trust. prepare_salience_training validates its result and binds
current host-owned authority before resource planning or gradient execution.
Pass the resulting supervision into `_execute_prepared_candidate` and B11. Keep the existing
path byte-equivalent when omitted. No persistent student starts or publication.

## Query, forward and loss

The three heads classify the whole visible source event/task. Use the final
visible prefix hidden state from the common B11 backbone, before decoder
feedback, refinement, and targets. Require a nonempty visible prefix. Do not add
an answer token, alternate backbone, hidden-size option or separate optimizer.

The B11-issued _ForwardRecord retains `salience_hidden=row_hidden[-1]` captured
before `_prediction_local_refinement`, plus the current params mapping;
public inference output remains ModelOutput. During supervised gradient execution
only, project the three existing B01 heads with project_salience_heads. Never
accept labels in forward_bamf. Changing labels must leave typed inference logits
unchanged.

Extend LossParts with optional impact/exigency/novelty fields (default None for
existing B10-only calls). For each supplied label j, use
`.05 * (logsumexp(logits) - logits[j])`; validate exact integer 0..4. Absent heads
contribute exact differentiable zero and have no head parameter participation.
Explicit signed UNKNOWN is class 0 and receives the ordinary .05 term. Sum these
terms with the unchanged typed-answer, role and epistemic loss. No learned score
becomes a semantic target or source truth.

`bamf_value_and_grad`, Backend.value_and_grad, and loss_bearing_bamf gain an
optional keyword-only supervision input. Verify it before forward execution and
again before issuing the loss. Add only labelled salience head weight/bias names
to the issued loss participation census. Retain existing source/custody dependency
accounting and candidate-step/AdamW ownership. No-label calls preserve their prior
loss and census. When supervision is supplied, salience-only objectives cannot authorize candidate
updates. Before issuing loss require one executed output decision of kind VALUE,
CONTROL, OPERATOR or OPERAND with matching target.decision_id, true mask and a
legal exact-typed target. Missing/unmatched/masked-out or ROLE/EPISTEMIC-only
supervision rejects BAMF_SALIENCE_PRIMARY_TARGET_REQUIRED. Keep the old no-salience
entrypoint behavior unchanged; this is a guard on the new supervised path.

No-label head components are mx.array(0., dtype=mx.float32); omitted heads are never
projected into the objective. `_issue_loss_execution` accepts optional labelled
head names and adds only `readout.salience.<name>` and
`readout.salience_bias.<name>` to record.dense_parameter_names. Before issuing,
extend record.training_authority dependencies with the salience evidence node
reference and all its immediate dependencies. The forward registry weak-lifetime
already retains records until output collection; the query/params follow it.
LossParts optional fields expose weighted components, never speculative scores.

## Proof obligations

1. Portable verified C02 attachment: absent labels stay absent, signed UNKNOWN
   stays zero, cross-row/release/generation substitutions fail, current source
   holds reject before returning optimizer input. Reuse existing signed fixtures.
2. Real A01/A05/C02/B13 Factory preparation binds one exact source row; attach
   source-qualified labels and run actual B11 gradients on disposable Studio
   state. Use an isolated directory and the shared serialized Studio lane.
3. Impact label produces literal .05 log(5) under zero logits and nonzero head
   bias gradient; absent novelty produces zero gradient and no participation.
   Explicit UNKNOWN novelty produces nonzero gradient. Check all three heads.
4. Compare identical real typed forward outputs under different salience labels;
   losses differ without changing inference logits. Plain inference receives no
   labels. Revoked rights/correction rejects before neural execution.
5. No-label actual B11 behavior and candidate custody remain covered by affected
   owner tests; do not rerun unrelated expensive suites without invalidation.

## File plan and stable checkpoints

No deletions. Modify:
- runtime/_model/atlas_training_authority.py: optional auxiliary digest issuance,
  copy and digest; focused portable digest/substitution regression.
- semantics/dependencies/__init__.py: append SALIENCE_EVIDENCE artifact kind.
- runtime/_correction/atlas_revalidation_common.py: queue priority `(2, 3)`.
- runtime/_correction/owners/salience_evidence_owner.py (create): C09 node/holds;
  mirrored correction owner tests, including prepare then source/rights revoke.
- runtime/_model/salience_training.py (create): request/supervision, exact signed
  re-derivation, C02 row rebinding and current-host checks; mirrored portable tests.
- runtime/_model/backbone/atlas_model_contracts.py: forward query/params and
  loss-specific head names/dependencies in issued execution.
- runtime/_model/backbone/atlas_model_forward.py: capture last prefix state
  before refinement; no target parameter or public inference shape change.
- runtime/_model/backbone/atlas_model_backend.py and atlas_model_training.py:
  optional keyword `salience_supervision=None` on gradient/loss plumbing;
  pre-forward verification, .05 CE, primary-target guard, consuming recheck.
- learning/atlas_readout/decoder/losses.py: optional weighted salience fields.
- runtime/_batch/factory_candidate_training.py: provider callback after prepare,
  supervision into private candidate executor, before resource or neural work.

Checkpoints: (1) portable label identity and C09 owner; (2) B11 objective with
focused numeric/gradient tests; (3) Factory opt-in composition. Each has red/green
focused tests before proceeding. Perform inherited-scope audit past three files
or 250 net lines; all changes implement the same missing #379 execution seam.
Only at stable completion run real serialized Studio witness, then drift and
premerge. Changed dependency-selection metadata belongs to the owner tests.

## Integration gate

This design supplies only the neural seam of parent #379. Host-bound priority,
A09 option mapping, retained history, and causal observations are specified in
integration-design.md. Parent completion requires both designs' full acceptance,
focused engineering proof, reconciled drift, valid premerge evidence and human PR
review. Existing child closure is not parent completion.
