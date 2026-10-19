# Living Bilqis semantic ledger: versioning, review, and model continuity

**Status:** implemented as a pure reconciliation and approval-bound materialization contract, with its first protected Google Sheet review queue. No historical checkpoint was modified; the NI mappings listed here remain proposals, not adopted semantic or training changes.

## Correction that supersedes the initial fail-on-edit design

The canonical Bilqis curriculum spreadsheet is **alive**. An edit that adds a grammatical explanation, source citation, review status, or proposed NI alias is not an instruction to erase, discard, restart, or fail a model trained under a previous approved semantic contract. **Models bind to a pinned approved semantic version, not the mutable latest spreadsheet view.** A new ledger version can be proposed, reviewed, approved and adopted separately. The old approved binding remains verifiable and available for future continuation. Invalidating existing weights because today's ledger prose differs from yesterday's is forbidden.

The model's historical integer token ID, symbolic identity, semantic ID, source graph row hash, and source graph digest remain its immutable historical ABI. The graph itself is not silently rewritten in the name of semantic cleanup. An alias, grammar locus, better interpretation, evidence, training state, or human commentary can evolve via a **versioned sidecar**. When a correction would actually alter meaning rather than clarify it, the successor must be separately instructed and re-evaluated, with the old checkpoint and evidence preserved.

## Workbook organization and approval path

Canonical Google Sheet: https://docs.google.com/spreadsheets/d/1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so/edit

- **Token Atlas:** the 222 historical rows remain immutable source-indexed provenance. The historical source definition and hash are preserved. This is not a giant shared mutable switch that can retroactively redefine old checkpoints.
- **Semantic Bridges:** candidate New Ithkuil roots, grammatical categories, and sourced proposal IDs. One NI root may be related to multiple historical tokens with different operational functions, and one meaning may require several NI formants. Research adjacency does not establish semantic identity.
- **Token Mapping Reviews:** append-only per-token proposals, with original meaning, proposed interpretation, NI root/grammar locus, primary source, comparison reasoning and the human approval/denial outcome. New proposals begin `PROPOSED_REVIEW`; approval columns remain empty until authority exists. Never backfill approval because a model generated a suggestion.
- **Token Ledger Versions:** immutable historical baseline `legacy-source/v1`, plus new draft versions. An approved version requires a real reviewer, authoritative approval reference, version ID, and exact accepted proposal digest. A version may be `COMPATIBLE_ANNOTATION` or `MEANING_CHANGE_REQUIRES_RETEACH`.

**Lifecycle:** research → proposed review row → primary source + formal contrast/difference → human-approved or rejected change → versioned materialized view → model-version reconciliation → new lesson/assessment as required. A changed row must not skip those states by virtue of appearing in Sheets. When the last approved version and the live sheet differ, retain the pinned version and record `PENDING_REVIEW`; do not discard old competence.

**Collision handling:** missing/duplicated/swapped stable IDs or changed source graph hashes trigger `CONTINUE_PINNED_MODEL_HOLD_NEW_ALLOCATIONS`: preserve the model but stop adopting **new** token meanings until resolved. A missing latest sheet or an editorial text difference is likewise not evidence the previously saved student is broken. Never quietly adopt a substantive semantic redefinition under an old embedding row.

**Implemented pure enforcement:** `bilqis_mlx.registry_versions.reconcile_live_ledger` returns explicit compatibility/review receipts; `review_proposal` validates submitted changes; `approved_revision` requires externally verified approval provenance supplied by the caller; `materialize_approved_mapping` creates a **new** table view for compatible, approved annotation changes without mutating the source graph. `vocabulary_growth.append_catalog` now tolerates proposed edits while retaining old model meaning and requires an approved pinned version plus admission receipts before **new** allocations. Actual independent verification that approval references belong to the human authority must occur in the connected workflow before passing any approval receipt to the pure code. This integration is not yet a training capability and is not claimed complete.

## Priority source review: `syntax.bind` vs `NI-LX-009`

Historical source, `bilqis_logic/kernel.py`: `syntax.bind` is **token 3**, the delimiter between a Boolean prefix expression and a list of explicit `P` and `Q` variable assignments. The original encoder writes it before the assignment environment; the decoder requires it before consuming variable/value pairs. It is a *binding-syntax boundary*, not the variable object or its numerical value.

`Semantic Bridges!A21:L21` defines `NI-LX-009` as **`-NTHW-`**, from the official New Ithkuil Lexicon §6.4, covering the stem distinctions mathematical variable, coefficient and constant. Official lexicon (current observed v1.0.1.1): https://ithkuil.net/New_Ithkuil_Lexicon.pdf. For an actual *mathematical variable*, `cogal.variable.P` (token 8) and `cogal.variable.Q` (token 9) are **better candidate matches** to the variable sense of `-NTHW-` than the `syntax.bind` delimiter. They are still specifically Boolean placeholders, not the general lexical class.

**Disposition:** `syntax.bind` ↔ `NI-LX-009`: `PARTIAL_OR_RELATED`, **not** `EQUIVALENT` or `MERGE`; research an official New Ithkuil grammatical/argument binding expression. `P/Q` ↔ `-NTHW-` stem 1: `PARTIAL_OR_RELATED`, potentially a closer type-level bridge. Do not rename or merge any existing source token. No human approval or neural updates are implied by this review.

The NI grammar also distinguishes referential machinery in Chapter 9: https://ithkuil.net/newithkuil_09_referentials.htm. This describes reference, case, and combinations, **not** by itself a proof of equivalence with Boolean assignment syntax.

## Other early crosswalk proposals

The review tab contains ten versioned candidate alignments (including the above), preserving source meaning and differences, all unapproved. Primary reference for each: official lexicon https://ithkuil.net/New_Ithkuil_Lexicon.pdf.

| Historic Bilqis token | New Ithkuil candidate | Qualification |
| --- | --- | --- |
| `micro.compare.EQ` | `NI-LX-011` / `-Č-` | Typed entity identity versus NI's distinct ontological identity and epistemological equivalence stems |
| `school.op.ADD`, `school.op.SUB` | `NI-LX-004` / `-TF-` | Source stems for addition and subtraction; not one-to-one replacement of two distinct symbolic operations |
| `school.op.MUL` | `NI-LX-005` / `-ẒV-` | Multiplication stem with more general lexical uses |
| `school.op.MOD` | `NI-LX-005` / `-ẒV-` | Division stem is related; modulo/remainder is **not division** and requires explicit NI reconstruction or another root |
| `school.number.0` | `NI-LX-001` / `-VR-` | Exact integer zero versus null/empty meanings |
| `school.number.1` | `NI-LX-002` / `-LL-` | Integer one versus broader unity/singularity |

These are valuable *research links*, not grammar certified equivalences, and make no claim of proficiency. The early sample favors official New Ithkuil roots rather than inventing one new primitive per English name.

## Source priority and likely novelty seam

**For every potential semantic primitive, search the current official New Ithkuil grammar and lexicon at `ithkuil.net` FIRST.** Distinguish exact lexical root/stem, grammar category/function, permissible composition, only a partial analogy, and genuinely unsupported concept. Search the full lexicon and grammar, not merely the 330 already excerpted Semantic Bridges records. New project-created primitives should be exceptional and justified by proof of unmet semantic needs or impractical/paradoxical decomposition, not a failure to search.

Potentially distinctive *future* candidates may arise from Rosetta-specific protocol semantics, Entif-specific proper concepts, and the Metacognitive Atlas rationality/mapping corpus. **None is automatically a new root.** The uploaded `Metacognitive Atlas Rationality Roadmap Checkpoint v0.1` (2026-10-04) explicitly says this workstream is cartography and genealogy, **not yet semantic or technical architecture**, with three prior foundation-ledger boundaries. The companion `Metacognitive Atlas Rationality Control Sheet v0.1.xlsx` has source, coverage, blind-spot, work-node and dependency ledgers; it is not a fourth foundation and does not adopt doctrine or a canonical ontology. Preliminary rationality labels are research candidates to be matched first to NI and existing Entif/Rosetta semantics before any novel pasigraphy identity is proposed.

## Limitations and next work

The registry reconciler is local/pure and tested on fixtures. Automatic authenticated fetching of live sheet revisions and independent attestation of human approval remain an integration gate. Full lexicon-wide audit of all 222 source meanings and official grammar conformance cases remains a substantial source-qualified research stage. The ten review entries are a **first review pass**; neither semantic adoption nor curriculum mastery has been granted.
