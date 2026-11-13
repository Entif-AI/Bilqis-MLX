# B10.1 output-head contract

Issue #467 owns pure output heads over the decoder's already-computed FP32
768-wide state `z`. B10.3 owns `predict_typed`, dependency feedback, causal
attention and `answer_loss`; B10.2 owns CONTROL and completed-frame publication.
This slice does not claim those siblings' acceptance.

## Concrete interface

Create `learning/atlas_readout/values.py`, `roles.py`, `records.py` and their
mirrored package-local tests. Reuse B02 `semantic_logits` and the Factory's
`live_answer_registry`; do not introduce a second semantic or role registry.
`bind_value_head(kind, values, snapshot, registry)` resolves existing Boolean,
numeric and native-token labels to active snapshot ABI entries.
`value_logits(z, binding, banks)` uses those exact tied identity rows, preserving
label order. Inactive/missing/foreign-release rows fail through ErrorBus.

`compile_frame_output(schema, released_schemas, features)` validates the actual
schema body through A03 `VerifiedReleasedFrameSchemas.require_schema` and binds
the A06 feature digest and release. The immutable frame-output domain retains
that exact schema and witness. `role_logits(z, domain, occurrence, parameters,
features)` fixes the occurrence index supplied by the typed decision, and scores
only schema roles for which `0 <= occurrence < max_cardinality`. This follows
DecisionSpec's existing explicit occurrence field. Candidate keys retain schema
ID/revision, role ID and occurrence; a role at occurrence 0 never silently binds
occurrence 1. There is no occurrence classifier or new learned tensor.

The ROLE head is `(z @ readout.role_query.T) @ released_role_vectors.T`, using
B01 `[128,768]` query and the shared `[512,128]` `features.role` table. Category
overflow uses the existing A06 deterministic overflow vector. Candidate order is
the released schema's role order. The output carries candidates alongside FP32
logits; exact ties use the first released candidate when selected by a caller.
Inputs may have arbitrary leading batch dimensions.

## Registry boundary

Factory `compile_answer_heads` continues to describe semantic-token heads.
ROLE and structured-frame domains are typed structural outputs derived by the
new B10 compiler, not fabricated semantic tokens. Their explicit modality IDs
are `answer.role-selection/v1` and `answer.structured-frame/v1`. A frame domain
provides role-selection domains to the downstream bounded decoder. It does not
publish an unchecked completed answer, admit a source release, or alter legacy
training dispatch. Existing native bindings remain `answer.binary/v1`,
`answer.numeric-active/v1`, their other registered versions, and the native
`semantic_token` binding. Result and binding schemas are versioned frozen
records. Boundary failures reuse `SCHOOL.MODEL_TOPOLOGY.INVALID`.

## Proof

RED/GREEN tests cover unchanged Boolean/numeric mappings, sparse bank-1 tied
prediction and inactive-row rejection, shared-role-table gradients, role swaps,
fixed repeated occurrences, invalid occurrence/cardinality, foreign release,
schema-body alteration and malformed tensor rejection. CONTROL tensors cannot
influence ROLE because the pure head reads only the prescribed role query/table.
No full model, persistent student, teacher or optimizer mutation is involved.

Consumed unified: `a02b9ed45ead1801be6dff655866b73be0ffc8ff`.
Parent B02/B03/B10 acceptance and the real learning path remain open.

## Record definitions

`ValueHeadBinding` (`bilqis.mlx.value-head-binding/v1`) stores `kind`,
`modality_id`, ordered `values`, registry-resolved `identities`, corresponding
`abi_indices`, and the exact `FrozenAtlasSnapshot`. The snapshot's active
`AbiEntry.symbol -> index` map supplies existing native identities; its sorted
active-index list must hash to `active_set_sha256` using canonical A01 JSON.
Bank semantic release and active-set digest must match the snapshot on every
read. The binding is derived data, not permission to activate rows.

`FrameOutputDomain` (`bilqis.mlx.frame-output-domain/v1`) stores the exact
`FrameSchema`, `VerifiedReleasedFrameSchemas`, A06 `feature_digest`, and
`answer.structured-frame/v1` modality. Schema ID/revision and A03 body/manifest
witness are recoverable from those exact source records and checked per read.
`RoleCandidate` stores `(schema_id, revision, role_id, occurrence_index)`.
`TypedHeadLogits` (`bilqis.mlx.typed-head-logits/v1`) stores finite FP32 `logits`,
ordered exact `candidates`, `modality_id`, and `semantic_release`.

Tests live at `learning/atlas_readout/tests/test_values.py` and `test_roles.py`;
shared disposable fixtures live in `tests/helpers.py`. All tests select MLX CPU
and do not compete for the sovereign GPU writer. Canonical package prefix is
`bilqis_mlx/`; no alternate installed package or whole-model tensor is created.

Change posture: CONFORMANCE. Agent interface disposition: NOT_AGENT_FACING;
these pure numerical functions are internal model components, with no new
CLI, service, network, storage or agent tool surface.

## Boundary validation details

The snapshot is A01's immutable semantic release: `FrozenAtlasSnapshot` in
`semantics.atlas_projection`. `AbiEntry.symbol` preserves native identity;
`active_set_sha256` hashes sorted active ABI indices with
`lib.ithkuil.src.skos.publication.json_bytes` (sorted-key compact UTF-8 JSON with
its canonical trailing newline). B02 is `learning.frame_embeddings.banks`;
A03 is `semantics.released_frame_schemas`; A06 is `semantics.atlas_features`.
B01 is `runtime.model_topology_v2`, the normative tensor ledger.
Factory is the existing `factory.lifecycle.answers` registry/compiler.
ErrorBus is `errors.bus`, which raises the typed `BilqisError` for a catalog code.

`ValueHeadBinding` additionally retains the exact `RegisteredAnswerModality`
`adapter` used for native labels, or `None` for `semantic_token`. Its constructor
requires the v1 schema, nonempty kind/modality, exact snapshot type, lowercase
64-hex release/active-set digests, nonempty equal-length tuples of unique nonempty
labels/identities and nonnegative integer ABI indices (booleans excluded), and
an adapter for registered kinds only. Every score re-derives identities and
modality from that adapter and rejects changed labels, adapter identity, ABI
indices, release or active-set binding. The registry's own domain validator may
raise its existing ValueError; malformed B10 records use ErrorBus.

`FrameOutputDomain` construction validates its v1 schema, exact structural
modality, exact schema/release types, 64-hex feature digest, and A03 schema-body
witness. Scoring additionally requires the same A06 feature digest and matching
semantic/Atlas/source bundle IDs, with every schema role mapped to a legal
shared-table row. `RoleCandidate` requires nonempty schema/role IDs, a positive
integer revision, and a nonnegative integer occurrence; booleans are excluded.

`TypedHeadLogits` construction requires its v1 schema, nonempty modality,
64-hex semantic release, finite nonempty FP32 tensor, and a nonempty tuple of
unique candidates with a single type (`str` or `RoleCandidate`). String candidates
are nonempty. The final tensor axis equals candidate count. Constructors and
read paths use the existing `SCHOOL.MODEL_TOPOLOGY.INVALID` ErrorBus code for
invalid B10 boundaries. Source/schema witnesses preserve their A03 error codes.
Additional malformed-record tests live in `tests/test_records.py`.
