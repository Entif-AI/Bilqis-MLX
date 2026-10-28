## RESULT

**NOT IMPLEMENTATION-READY — 2 blockers and 6 majors.** The selected architecture can be retained; these findings require concrete contract completion, not alternative models or new research experiments.

The plan preserves the principal 12×768 architecture, legitimate exact computation/retrieval, constituent recall, and complete-generation custody intent. However, several lower-tier implementers would still have to invent behavior affecting causality, learning, or interoperability.

## FINDINGS

### 1. Blocker — B06: refinement selection can depend on future frames
**Locators:** `public/issues/B06.md:30`; `public/issues/B06.md:44`; `public/BAMF_0_2.md:114`.

Selection uses the entire row’s `F`, a `ceil(F/8)` quota, and row-wide role/salience priority. Appending future frames can therefore change whether an earlier frame receives refinement—even when member attention is correctly masked. For example, increasing `F` from eight to nine changes the quota. This violates causal prefix invariance through the selection path.

**Minimal fix:** Specify selection and budget accounting against each prediction’s visible prefix, with deterministic prefix-local allocation. Add a test that appends high-priority future frames and crosses a quota boundary while asserting unchanged earlier selections and logits.

### 2. Blocker — B10/C04: dependent output generation has no executable state transition
**Locators:** `public/issues/B10.md:27`; `public/issues/B10.md:32`; `public/issues/C04.md:31`.

B10 requires dependent decisions to consume earlier committed outputs and permits teacher forcing, but its interface accepts only hidden states, an answer plan, and active semantics. It does not define output feedback, decoder state, positional treatment, or how the next decision is computed. C04 simultaneously permits only one backbone call. Implementers must choose a decoding architecture to reconcile these requirements.

**Minimal fix:** Freeze one output-construction algorithm compatible with the existing one-backbone budget. Specify its state/feedback tensors, role-occurrence addressing, legal-action masks, termination, and teacher-forced versus inference transitions. Add a two-dependent-decision fixture proving later targets cannot influence earlier predictions.

### 3. Major — B01: the promised complete tensor declaration is still delegated design
**Locators:** `public/issues/B01.md:28`; `public/issues/B01.md:33`; `public/issues/B03.md:31`; `public/issues/B08.md:30`; `public/BAMF_0_2.md:227`.

B01 instructs the implementer to declare every tensor, but the plan does not supply the complete declaration. Auxiliary frame queries/interactions, conditioned motif gates, and output-control heads still require shape and parameter-sharing decisions. “Recorded seed and fan-in scale” does not determine an initialization distribution. The shape API also exposes semantic-bank extent without an explicit motif-page extent input or equivalent declared state.

**Minimal fix:** Supply one normative tensor ledger containing names, shapes, sharing, bias presence, initializer distribution/scale/seed derivation, and update group. Include all variable extents in its input contract. Have initialization, validation, serialization, and parameter-count tests consume that ledger.

### 4. Major — A06: learned factor-row identity is not preserved across releases
**Locators:** `public/issues/A06.md:26`; `public/issues/A06.md:31`; `public/issues/A06.md:45`.

The feature manifest enumerates categorical values and persists a projection seed/vocabulary, but does not define stable type/role/schema-to-row allocation across releases. Deterministic rebuilding and source-file reordering tests do not prevent a newly introduced category from changing existing learned row meanings. The 64 graph coordinates, normalization, projection construction, and overflow representation also remain unspecified.

**Minimal fix:** Define append-only categorical ID maps, their predecessor binding, the exact 64-coordinate feature recipe, and the compositional/UNKNOWN overflow encoding. Test a successor release that inserts a lexically earlier category: existing categorical IDs and learned-row associations must remain unchanged.

### 5. Major — B09/B12: “touched row” and optimizer-mask semantics are unresolved
**Locators:** `public/issues/B09.md:30`; `public/issues/B12.md:32`; `public/issues/B12.md:46`.

Row establishment counts accepted updates that “actually touched” a row, whereas B12 increments eligible rows on actual steps. These differ for unused motif rows, zero gradients, and identity rows participating in tied output normalization without appearing as input tokens. The plan also does not specify whether masking precedes global clipping. The existing clip helper computes its norm over every supplied gradient leaf.

**Source evidence:** pinned replay `bilqis_mlx/runtime/mlx_parity.py:99`, particularly gradient enumeration at line 105.

**Minimal fix:** Define one row-participation/update mask and distinguish it from parameter-group eligibility. Specify treatment of zero-gradient rows, AdamW decay, moment/count advancement, establishment age, and mask-versus-clip order. Test an unused motif row, an output-only identity row, and frozen gradients large enough to affect clipping.

### 6. Major — B09: FOUNDATION never has a defined transition to ADAPTIVE
**Locators:** `public/issues/B09.md:25`; `public/issues/B09.md:30`; `public/BAMF_0_2.md:122`.

The two modes and eight-FAST cadence are described, but neither the initial mode transition nor its authoritative trigger is specified. There is also no explicit counter-reset rule after scheduled or teacher-requested FULL updates. Persisting unspecified state does not make the timescale policy reproducible.

**Minimal fix:** Declare the initial mode, exact FOUNDATION→ADAPTIVE trigger, and cadence-counter behavior for scheduled FULL, early FULL, rejection, and restart. This can be a fixed versioned policy or explicit owner-controlled transition; it does not require a learned scheduler.

### 7. Major — C12/B13: compatible weight-delta import lacks optimizer and memory adoption semantics
**Locators:** `public/BAMF_0_2.md:682`; `public/BAMF_0_2.md:684`; `public/issues/B13.md:37`.

Matching base weights, parameter schema, and semantic binding is insufficient to define a continued-learning state. C12 does not say whether affected AdamW moments/counts are retained, replaced, or reset, or how row ages, consolidation counters, and motif-slot bindings are reconciled. Two recipients with identical weights but different optimizer histories can otherwise interpret the same package differently.

**Minimal fix:** Specify a receiver-owned import transaction covering delta application, affected optimizer state, plasticity clocks, and memory-address compatibility. Bind the adoption receipt to the recipient generation. Extend the disposable import test through one subsequent optimizer step and rejection/cold-resume rollback.

### 8. Major — C04: operator registration does not determine route construction
**Locators:** `public/issues/C04.md:26`; `public/issues/C04.md:31`; `public/BAMF_0_2.md:420`.

The plan requires exact composition and neural interpretation followed by a pure operator, but leaves unspecified how task requests become bound DAG nodes. “Register applicability and deterministic tie order” does not define operand discovery, composition depth, intermediate-value selection, or cycle/ambiguity handling. These choices materially determine end-to-end capability.

**Minimal fix:** Define the initial task/goal and operator record schemas plus one bounded deterministic binding/composition procedure—or explicitly require an input DAG and define how unresolved nodes are filled. Specify operation-budget accounting and unresolved/ambiguous outcomes. Use the already-required two-operation and neural-then-pure fixtures as literal routing acceptance cases.

## SOURCE COVERAGE

- Read all four required reviewer documents and all 22 target documents: `public/BAMF_0_2.md`, B01–B14, A02/A05/A06, and C02/C04/C05/C16.
- Read the supplied BAMF-0.1 blueprint, `sources/AGENTS-replay.md`, and `sources/symbols.txt`. Checked relevant topology, training, optimizer, vocabulary-growth, checkpoint, and runtime seams at replay commit `d21797e72365bf93ea7cad3a4ef9020ec9817f23`. Confirmed A06’s relation owner at SKOS commit `175cdf6778b4eeaea23a5bd36ad7dc6664df3ae8`.
- **Missing source:** the private expanded BAV engineering specification referenced by `public/BAMF_0_2.md:318` was not present in the supplied workspace. Its 24-requirement continuity claims could not be independently verified against the original; the public crosswalk is not a substitute for that source.
- Reconciled concurrent document amendments and confirmed the final reviewed snapshot remained unchanged. Main-plan SHA-256: `5f155f174fd988324f40288dc7ee3cfa9984a8e8261d554d21262de7b0d3cea6`.
- Read-only review only: no edits, execution tests, publication, or conversation-memory retrieval. Resource figures and proposed acceptance witnesses were not treated as implemented results.