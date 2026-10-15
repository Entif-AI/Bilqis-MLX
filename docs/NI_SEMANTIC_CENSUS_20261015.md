# Bilqis historical-to-New-Ithkuil semantic census
**Private research draft | 2026-10-15 | 222/222 historical tokens | No adoption or lessons authorized**

## Purpose and governing decision

The user directed Bilqis to **map as much of the existing semantic vocabulary as possible to official New Ithkuil now**, BEFORE adding lessons or advancing toward training. The first source for a proposed primitive is **both** the current official lexicon and grammatical description at `ithkuil.net`, not our own English glosses or solely the 330 already-curated Semantic Bridges suggestions. A unique project root is exceptional and requires a documented search and an explanatory semantic necessity.

The result is a **research crosswalk**, not a curriculum release, not an approved meaning change, and not a claim that Bilqis has learned New Ithkuil. Every historical token keeps its exact numeric ID, identity, graph hash, trained weights, and own native AdamW. The live catalog changes by versioned review and approval as specified in ADR-007; a pending catalog proposal cannot invalidate an existing student.

## Canonical live results and inspection

[Bilqis Curriculum Registry](https://docs.google.com/spreadsheets/d/1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so/edit) is the source of research proposals, with distinct tables:

- `Token Atlas!A1:P223`: 222 preserved pre-repair source token identities, indices 0..221, bound to the original complete FP32 student's graph.
- `Semantic Bridges!A1:L331`: 330 user/project-sourced candidate lexicon and grammar bridges (research; not 330 trained tokens).
- `Token Mapping Reviews!A1:P223`: **222 unique individual source-grounded candidate alignments**, all `PROPOSED_REVIEW`, 0 approved. Ten prior proposals remain intact; 212 further provisional rows added in this work. Each row retains exact historical symbol, index, meaning and pasigraphy identity, then records a candidate NI lexeme/construction, relation class, official primary source URL, locus, semantic counterexample or scope difference, and blank human-approval/version-applied columns. The workbook remains a living review system, not a frozen exam or a substitution for the historical graph.
- `Token Ledger Versions!A1:J4`: source-pinned `legacy-source/v1`, prior draft `mapping-draft/20261015-a`, and new draft `mapping-draft/20261015-b` covering all 222 candidates. Neither draft replaces the student's approved semantic ABI.
- `Start Here!A32:B32`: records the mapping milestone and **pause on further lessons and neural training**.

The research ledger was re-read after the native writes and reconciled against the complete Token Atlas: 222 proposals, 222 distinct index values, zero mismatched original IDs/symbols/pasigraphy identities/descriptions, zero missing source loci or official-domain source URLs, zero entries marked approved. There are 62 fine-grained provisional classification labels; this does **not** mean 62 validated New Ithkuil morphemes.

## Source basis and morphological precision

**Official Lexicon:** https://ithkuil.net/New_Ithkuil_Lexicon.pdf (currently identified on the PDF cover as *Lexicon for New Ithkuil*, v1.0.1.1, 570 pp.). Relevant entries: §1.1 carrier `-S-`, §1.3 copula `-Č-`, §1.4 demonstration/proof `-MŢT-`, §4.1 deduction/inference `-MSL-` and interpretation, §4.2 functional kinship `-MP-` vs genetic `-MM-`, and §6.4 mathematical variable `-NTHW-`, abstract object/structure/operation `-ŇZX-`. The source defines distinctions by root, stem and Specification, so a superficial English translation is not semantic identity.

**Official Grammar:** 
- https://ithkuil.net/newithkuil_03_morphology.htm (configuration, grouping and grammatical context)
- https://ithkuil.net/newithkuil_04_case.htm (typed semantic roles)
- https://ithkuil.net/newithkuil_05_verbs.htm (mood, aspect and event framing)
- https://ithkuil.net/newithkuil_06_more_verbs.htm (illocution and validation)
- https://ithkuil.net/newithkuil_07_affixes.htm (negation and further compositional scope)
- https://ithkuil.net/newithkuil_09_referentials.htm (referents)
- https://ithkuil.net/newithkuil_11_syntax.htm (phrase/clause organization)
- https://ithkuil.net/newithkuil_13_numbers.htm (base-100 numbers, roots and TNX)

**Not formally validated:** full phonological/morphotactic realization, exact grammatical slots/case/affix sequencing, reverse decoding, minimal pair legality, and independent proficiency or same-checkpoint mastery. The catalog's proposed spellings are **root and affix schemata**, not well-formed rendered words certified by a compiler.

## The important structural findings

### 101 integer tokens and a single New Ithkuil numeric system

The legacy student has **101 exact integer symbols**, 0 through 100 (indices 121..221). Official New Ithkuil §13 uses its own centesimal numerical scheme and number formatives. Roots for 0..10 are `-VR-, -LL-, -KS-, -Z-, -PŠ-, -ST-, -CP-, -NS-, -ČK-, -LẒ-, -J-`; the root for 100 is `-GZ-`. Values 11..99 are typically constructed with numerical root plus the 9-degree TNX `-rs` affix for tens; 11..15 also have optional specialized roots `-CG-, -JD-, -ĻJ-, -BC-, -ŢẒ-` in other-base counting contexts. The registered 101 individual Bilqis symbols remain intact. NI compositional expression for a given number does NOT mean it was trained as multiple NI tokens or that its correct word-form is already assessed. Exact cardinal/ordinal/abstract semantic stem and specification are pending review.

### 121 other historical tokens: semantic functions, typed symbols and formal constructs

- **Protocol syntax:** internal padding, field boundaries, named world sections and task delimiters are interpretable *protocol functions*. The official NI grammar may offer analogous phrase/slot structures but a specific internal separator need not be an NI lexical root. Flagged explicitly as `STRUCTURAL_SERIALIZATION_REVIEW`; never fabricated a lexeme.
- **Boolean values and logic:** source truth tables for NOT/AND/OR/XOR/XNOR/IMPLIES/IFF are mathematical propositions with exact operators. NI negation, coordination, mood and copula provide grammar-research candidates, but they cannot be assumed Boolean-equivalent without independent truth-functional scope tests. NI validation is not the same as Bilqis's typed TRUE/FALSE or evidence-status outputs.
- **Binding, variables and quantifiers:** `syntax.bind` (token3) separates Boolean expression from the P/Q assignment environment in the original codec. `-NTHW-` is **variable/coefficient/constant**, not the delimiter: `cogal.variable.P/Q` are closer typed lexical candidates. Classical universal/existential quantifiers and de Bruijn indices `micro.bound.0/1` require explicitly scoped binding, not just NI plural/perspective or pronouns.
- **Named entities, functions, sets, events and propositions:** `A`..`E`, `K0/K1`, `F0/F1`, `E0`..`E3`, `J0`..`J2` are typed referent IDs, not new unrelated NI root concepts for each name. NI carrier `-S-`, referentials and abstract `-ŇZX-` provide paths, subject to typed graph and case requirements.
- **Kinship:** NI `-MP-` marks *functional* parent/child/grandparent (raised/raising), NI `-MM-` marks *genetic* counterparts. Historic Bilqis parent/child/grandparent are generic graph predicates; using either root would narrow the meaning unless the domain is refined or a formal relation interpretation is constructed.
- **Mathematical sets and functions:** `-ŇZX-` covers abstract object, abstract structure and abstract operation, `-NTHW-` includes mathematical function sense. Those form promising families for set intersection/difference/domain/range/inverse/composition, but NI generic abstract-operation sense does not assert the formal set-theoretic equation. For `school.op.MOD`, division `-ẒV-` is related but **not modulo**; a remainder/quotient composition or different exact root remains to be checked.
- **Evidence, inference and change:** `-MSL-` relates to inference and deduction, `-MŢT-` to demonstrating/proving, `-RCT-` to observation, `-ÇN-` to source/origin, with morphology for status and temporality. Neither proof-as-an-act nor validation-as-a-grammatical marker automatically equals classical semantic entailment or Bilqis's four-valued evidence states. Lexicon `-ŇTÇ-` labelled *proposition* is actually **a proposal** in its listed stem, NOT a formal truth-evaluable proposition; this lexical false friend is specifically flagged in rows for `J0/J1/J2`.

### What is NOT a proven New Ithkuil root or lexical gap

No custom new primitive is approved or even established to be necessary by this census. Cases with only a broad NI root or a grammar analogy remain research-open. The correct next operation is **semantic differential review and formal construction of exact NI expressions** or a well-evidenced incompatibility finding, not automatically making novel pasigraphy roots.

The uploaded Metacognitive Atlas Rationality roadmap and control workbook explicitly record a research-cartography/source-genealogy stage, not an adopted semantics ontology. Rosetta/Entif/MCA-specific terms are potential future **research candidates** requiring the same search-first discipline.

## Review gate prior to any new lessons

1. For each of the 222 rows, inspect actual official lexicon root **stem, specification and scope**, or identify the exact applicable NI grammar mechanism. Confirm exact original Bilqis source graph meaning and its independent oracle; correct source citations and distinguish unrelated false friends.
2. Classify as exact same meaning, narrower/broader lexical sense, grammar construction, named referent, protocol-only function, requires compound, or unresolved. Preserve aliases/alternative senses without merging historical token IDs or inventing neural mastery. There may be multiple NI formants for one Bilqis concept and reuse of a single NI root across many typed historical tokens.
3. For promising alignments, author formally well-formed NI expressions only **after** validating morphology, ordering, scope, case and all component prerequisites; test reverse parsing and minimal pairs. Distinguish lexical alignment from grammatical form certification.
4. Human approval is required in the versioned `Token Mapping Reviews` and `Token Ledger Versions` system before adoption. A compatible approved annotation may advance the catalog without changing the student. A true meaning change requires separately taught/reassessed successor semantics, never an unapproved relabel of old weights.
5. Only **after** meaningful alignment/approval clarity return to curriculum design, source-attested lessons, and eventual MLX human-only training qualification. Existing student, optimizer, six-panel dashboard and disk-safe backups remain unchanged.

**Status at this checkpoint:** full initial *token coverage achieved*; individual *semantic validation remains open*, 0 approvals. This is a foundation for human and automated review, not a course graduation or new neural result.
