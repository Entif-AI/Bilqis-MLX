# Semantic vocabulary growth: source audit and nontraining MLX proof

**Status:** append-only model/corpus transition tested; actual root admissions and neural teaching not started. **Authority:** protected IPR-0220 and the user's 2026-10-15 lexical-growth instruction. This implementation and its evidence are private.

## Why 222

The complete historical FP32 checkpoint `student-116760-7e9af4651f28.pt` contains a **222-token** graph, not an architectural maximum. The first **113** tokens came from the original Boolean, relational and typed finite-world graph (`bilqis_micro.graph` plus `bilqis_development.registry`). The subsequent **109** came from `bilqis_school.arithmetic.extend_graph`: one math syntax token, seven arithmetic/comparison operator tokens (`ADD`, `SUB`, `MUL`, `MOD`, `EQ`, `LT`, `LE`) and 101 numeric identities from `school.number.0` through `school.number.100`. The original `bilqis_micro.graph.append_catalog` and `bilqis_development.continuation.expand` already supported append-only growth with retained trained embedding rows and expanded native AdamW moments. This is an actual historical implementation, not a new conjecture.

The prior checkpoint's vocabulary is finite because embedding and moment tensors have shapes tied to that snapshot. The surrounding software **can grow** the shapes. Historic root or token addition was code/lesson-driven, not automatic discovery by the trained neural model. The current MLX successor likewise **does not automatically import, attest or learn new semantic roots**.

## Registry scale and meaning

The live native Google Sheet `Bilqis Curriculum Registry - Version, Lessons, Prerequisites and Champion States`, tab `Semantic Bridges`, was inspected read-only on 2026-10-15. The cells `A2:A331` have **330 nonempty unique candidate identifiers**, ending with `NI-GATE-0330`. This counts *registry entries*, not precisely 330 existing neural tokens or approved roots. The sheet mixes New Ithkuil morphology, affixes, semantic alignments, mathematical constructs, dependencies and grounding gates; many rows explicitly remain proposed/blocked. Record identity, source meaning, linguistic root, formative/stem, model token and mastered capability remain separate types.

Authoritative New Ithkuil source references:
- New Ithkuil Ch. 2, §2.4 (root, stem and formative): https://www.ithkuil.net/newithkuil_02_morpho-phonology.htm
- New Ithkuil lexicon: https://ithkuil.net/New_Ithkuil_Lexicon.pdf

Chapter 2 permits **over 33,000 phonotactically possible** root shapes. That is potential form capacity, not a statement that all these roots have defined meanings or are trained. Bilqis is not limited by Ithkuil's available surface forms: concepts from logic, mathematics, external sources and lexicalized distinctions can have independent semantic IDs even if no New Ithkuil root is currently assigned.

The user's examples `enshittification` and `shibboleth` are recorded as research seeds with an **atomic representation candidate**. That does not assert a specific New Ithkuil translation, canonical definition or mastery. A standalone semantic identity is appropriate to investigate when decomposition loses a distinctive social/pragmatic mechanism, becomes confusing, or increases explanation load relative to an atomic label. Admission still requires a source-grounded contrast, independent evaluation, and prerequisite-respecting teaching.

## Implemented growth contract

`bilqis_mlx.vocabulary_growth` implements:

1. A **research seed** separate from an attested, still-untrained *semantic token admission*. Neither research seed nor candidate label automatically becomes a neural vocabulary row.
2. **Stable append-only IDs**: existing catalog token order, semantic node descriptors and row contracts are preserved exactly; duplicate/reordered/mutated prefixes are rejected.
3. **Finite explicit admissions** with source, teaching, independent-oracle and admission receipt digests, capability owner, prerequisites and representation type (`atomic`, `compositional`, `hybrid`). Syntactically valid digests do *not* prove the sources true; source/oracle validation is an independent upstream gate.
4. **Deterministic new FP32 embedding rows**, initially just untrained seeds; copied FP32 old embedding rows; expanded AdamW `exp_avg`/`exp_avg_sq` with original moment rows exact and newly added moments zero. All other parameter tensors and optimizer moments are carried unchanged, with the old optimizer step retained.
5. New metadata makes no claim that added roots were taught, mastered or learned. Fixture identities are rejected for real catalog admission except when explicitly running disposable probes.
6. **No hard-coded vocabulary ceiling** in the allocation contract. Hardware, MLX integer indexing, context/answer-readout architecture, source curation and disk budgets remain practical limits. The existing checkpoint bundle's **4,096 limit is on distinct named model parameters, not vocabulary rows**.
7. **Semantic-bound checkpoint recovery**: `mlx_checkpoint.save_new_bundle(..., semantic_catalog=...)` writes the complete token catalog into an exclusive new bundle. Its hash is recorded in the manifest. `load_semantically_bound_bundle()` rejects a missing, modified or row-incompatible catalog. Older unbound fixture bundles remain readable through the permissive loader but cannot serve as provenance-complete semantic checkpoint receipts.

At the saved model width of **384** with FP32 weights and two FP32 AdamW moment matrices, every new embedding token adds **4,608 bytes** of persistent core tensor data *per saved complete checkpoint*, before tensor metadata, replicas, teacher states, activation buffers, repeated archives and software overhead. Batching curriculum admissions and deduplicating identical champion checkpoint pointers prevents unchecked disk growth. A composite meaning often requires multiple individually interpretable tokens; not every registry bridge requires allocation of a new token. All tokens must have distinct pasigraphy identities.

## Direct real-student proof

On 2026-10-15, `npm run vocabulary:preflight` verified the full historical checkpoint SHA `646d8590cf8fddb7b3c412ecead4ac185a0578f93baadf24e05f92dd15068a78`, loaded the complete model and all 39 AdamW moment entries on CPU, and appended **one test-only untrained token in memory** (222 to 223). No new official or proposed real root was admitted. For the exact old input and evidence readout tokens used by this preflight, the old and expanded model logits were bit-for-bit identical: **maximum absolute difference 0.0**. Original token indices, embedding rows, AdamW moments and step 116760 remained exact. The historical on-disk checkpoint SHA remained unchanged. **Zero neural optimizer updates and zero checkpoint writes.**

Separate disposable unit tests appended 3,400 synthetic candidate records to a three-token fixture catalog and showed 3,403 total IDs with no prefix changes. This is a data-model scaling test, not a test of root meanings, live training or a 3,403-token checkpoint. Synthetic new embeddings on an enlarged tiny model survived safe MLX bundle save/reload, and all old rows and moments remained exact.

The same fixture tests loaded its bound semantic graph and rejected a modified catalog file on readback. A weight bundle without a semantic catalog is rejected by the strict loader.

Reproduce the read-only original-checkpoint proof (the preserved legacy worktree must be mounted):

```sh
npm run vocabulary:preflight -- \
  --legacy-code-root ../bilqis-triplets-v16 \
  --checkpoint ../bilqis-triplets-v16/runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt
npm run test
```

## Still blocked

- Promotion of any of the 330 research/bridge entries to approved New Ithkuil or external semantic roots without source and independent lesson/oracle attestation.
- Teaching or examination of any newly allocated symbol before its semantic lesson and prerequisite grades are mastered. Existing root/token knowledge is not inferred from the vocabulary alone.
- Extending the existing five-state evidence output to other semantic answer types without a sourced, separately tested answer contract.
- Actual native whole-network MLX optimizer continuation, qualification of new semantic roots, retention after learning, or human-controlled neural training. The current `npm run train` guard remains in force.
