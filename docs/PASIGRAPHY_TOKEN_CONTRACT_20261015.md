# The Bilqis pasigraphy contract

**Foundational user instruction, 2026-10-15.** This is a private implementation companion to protected IPR-0220. The full user correction is preserved in the IPR-0220 GitHub thread, not replaced by this normalization. Earlier explanations that Bilqis can use semantically incidental, opaque tokenizer entries are superseded.

## Purpose

Bilqis is learning a shared *interpretable* semantic language, not post-hoc translating arbitrary neural symbols. This is intended to be a human-auditable and machine-interoperable metacognitive atlas shared across models, vendors, technologies, and security/governance/alignment research. It should enable dense, intentional communication without reliance on uninspectable emergent Neuralese.

### The indivisible invariant

**Every Bilqis token maps one-to-one to an explicitly interpretable semantic identity or function recorded in our governed pasigraphy catalog.** Each entry has one unique model token ID, one stable symbolic identity, a source-grounded semantic definition or typed operation, and verifiable provenance. Every token allocated or learned during the New Ithkuil curriculum appears in the canonical workbook before its use in neural training. Syntax, delimiters, references, operators and morphology have interpretable *functions* even when they are not independent lexical roots.

Token identity and conceptual meaning are not interchangeable categories: a **composite meaning** normally consists of several individually meaningful tokens assembled under compositional rules. One-to-one token identity does not require a one-token encoding for every meaning. It also does not require two extensionally equivalent operators to be the same token if their specified grammatical/operational functions differ. Ambiguous catalog identity or an unregistered token is a hard admission failure.

## Source-of-truth boundaries

- **Canonical corpus:** [Bilqis Curriculum Registry](https://docs.google.com/spreadsheets/d/1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so/edit), with new `Token Atlas` tab for one record per token. The `Semantic Bridges` tab contains 330 *candidate* mappings and remains distinct from confirmed token allocations.
- **Historical checkpoint:** whole FP32 model `student-116760-7e9af4651f28.pt`, SHA-256 `646d8590cf8fddb7b3c412ecead4ac185a0578f93baadf24e05f92dd15068a78`; graph SHA-256 `57ab0a141a9bfc25c6da8d0568f14e0a8beaab2c0c3fd33931e51e2624a0b16f`.
- **Historical inventory:** `Token Atlas!A1:P223` now has all **222** source-defined tokens, ordered by zero-based numerical ID. It maps each to a unique `legacy:<symbol>` pasigraphy identity, source-derived description and typed signature, provenance, node hash and explicit review/mastery status. Every field of all 222 rows was verified against the historical checkpoint's deterministic projection with **zero discrepancies**. None was retroactively relabeled to match a New Ithkuil root.
- **Unverified semantics remain visible:** old source nodes often specify their type and identifier without the full descriptive obligations of the New Ithkuil lexicon. Their `LEGACY_MEANING_NEEDS_HUMAN_REVIEW` marker is an honest outstanding semantic validation task, **not** a completed NI-conformance certificate. A model checkpoint containing an embedding row does not prove token-level mastery.
- **Future expansions:** unique catalog semantic IDs, normalized definitions, source anchors, prospective grade/capability, prereqs, independent teaching and oracle receipts. `source-attested`, `allocated`, `taught`, `examined`, `mastered` and `aligned to NI` are distinct statuses and cannot be interchanged.

## Curriculum is a New Ithkuil specification conformance program

Follow primary New Ithkuil lexicon and grammar rules, in their source-defined order and scope, instead of English approximation or a generic symbolic curriculum. Each curriculum rule or construction requires evidence for:

1. **Source provenance:** exact grammar edition, chapter/section, lexicon entry, morpheme/slot/variant and its formal meaning; conflicting or ungrounded interpretations are held for research.
2. **Constituent tokens:** every component has its own unambiguous registered meaning/function. The constituent semantics and prerequisites have been introduced and individually examined in earlier school grades before the compound form enters assessment.
3. **Generation and decoding:** constructive encoding of meaning into legal NI expressions, inverse decoding into typed meaning, and determinate treatment of grammatical variation, scope, disambiguation and context when introduced.
4. **Validity and contrast:** positive and negative well-formedness cases, minimal pairs changing the actual target relation, source-grounded invalid formations, and non-equivalence traps. Unrelated Boolean decoration cannot be used to create superficial label balance.
5. **Generalization and retention:** varied lawful compositions of *already taught* semantic units, unseen but admissible worlds/contexts, decomposition/recomposition agreement, independent oracle checks, and earlier-grade recovery/rehearsal receipts.
6. **Progression:** a formal conformance gate for each tested construct and full same-checkpoint grade mastery. No unseen lexical roots, grammar operations or composed prerequisites in a test.

The training regimen is **primarily a progressively staged executable test suite against the New Ithkuil design specification**, rather than an unstructured corpus of language-like prompts. The current Grade A source-predicate draft does not establish NI-grammar compliance; it remains a provisional mathematical foundation.

## Evolution beyond the initial dialect

New Ithkuil is the governed **starting dialect** and reference atlas. Source-grounded concepts from mathematics, logic and other disciplines may be reviewed, and a distinct lexicalized root may be preferred when compulsory decomposition obscures the concept's essential semantics. Such exceptions require an explicit rationale and tests. They are not a license for opaque tokens. After the complete New Ithkuil regimen, the user may allow evolution beyond the curated starter dialect. The runtime must not relax the dialect gate early or assume that later linguistic freedom means losing all semantic provenance and auditability.

## Enforceable technical contracts and known limits

`bilqis_mlx.token_atlas` projects the graph to 16 canonical spreadsheet columns and asserts a bijection between token IDs and pasigraphy semantic IDs, complete typed source descriptions, hashed per-node contracts, exact row ordering, and full source-backed workbook readback.

`bilqis_mlx.vocabulary_growth.append_catalog` refuses duplicate token or concept identities. For any **nonfixture allocation**, an exact readback of the *entire proposed graph* against the canonical workbook projection is required. In-memory disposable fixtures remain separately gated. The current real student remains unchanged and real neural training remains disabled. The separately versioned MLX checkpoint codec binds the complete token graph and its hash to the model/AdamW bundle; strict reload rejects missing or changed semantic catalogs.

**Not yet achieved:** independent NI semantic review of the 222 legacy descriptions, formal NI compiler/decoder and exhaustive grammar conformance tests, live end-to-end sheet credentials/automatic syncing in the human-operated CLI, native whole-student MLX training continuation, and any new token's independently verified learning. The workbook synchronization done in this milestone is source-backed, not a declaration of semantic-regimen completion.

## Minimal failure-oriented acceptance checks

- Model graph adds a token with no ledger row, reorders a token, changes a definition, or reuses an existing pasigraphy ID: **reject**.
- An external research idea appears in Semantic Bridges but has no admitted grammar/root semantics: **do not allocate, teach or examine**.
- A syntax or numeric token is absent from the atlas merely because it is not a conventional lexical root: **reject the incomplete inventory**.
- A composite exam refers to untaught constituents, uses a nonexistent grammar form or claims NI meaning from an analogous mathematical operation: **reject**.
- A root is allocated with valid JSON but no independently attested provenance/lesson/oracle: **hold for source validation**. Syntactically valid SHA strings are not evidence by themselves.
- A later autonomous vocabulary expansion happens without the active New Ithkuil completion gate or a reviewed dialect-extension decision: **do not claim authorized evolution beyond the starter dialect**.
