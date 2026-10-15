# Curriculum compiler: AST-first lesson and probe generation

## Controlling direction

Do not respond to failures by hand-authoring a fix for each narrow lesson.
Identify the general failure mechanism, encode the curriculum's dependency
and semantic structure once, and derive large families of deterministic
source-checked lessons, contrasts, counterexamples and probes from that AST.
Quality checks are compiler invariants, not a separate handcrafted checklist.

## Verified native spreadsheet inputs

Canonical `Bilqis Curriculum Registry - Version, Lessons, Prerequisites and
Champion States` (native spreadsheet ID
`1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so`) contains `Lessons`,
`Prerequisites`, `Grade Tranches`, `Token Atlas`, `Semantic Bridges`, and
version/decision/evidence tabs. Read by the native Google Sheets connector.

`Lessons` links legacy IDs, stable proposed lesson identities, mathematical
operations, construction intentions, assessment criteria and evidence status.
`Prerequisites` describes named earlier concepts, construction requirements,
allowable assessment, proposed grade and admission evidence gate. `Token Atlas`
binds the historical 222 token IDs to distinct interpretable identities,
semantic families and signatures. `Semantic Bridges` provides proposed NI
construction factors and assessment variations, explicitly marked research
seeds. `Grade Tranches` includes **historical 2026-10-14 labels** that differ
from the subsequent user-accepted six-capability experimental Grade A release.
Those rows are *not* an active scheduling authority. Do not ingest them as
approved grade membership without versioned reconciliation.

## Initial bounded implementation

`bilqis_mlx/curriculum_compiler.py` now represents each admitted `Course`
capability as a typed, immutable `CapabilityNode` inside `CurriculumAST`,
including semantic roots, grade, prerequisite edges, compositional
constituents, answer families, independent oracle and source anchor.
`compile_probe_plan()` composes a factorized diagnostic space for all six
already-accepted foundational Grade A operations. It varies truth label,
source-attested universe cardinality (3/4), and repeatable independent
world/query identities. `materialize_probes()` actually constructs and
encodes the probe worlds with the **pinned historical source**, rejects any
three-oracle disagreement, validates token/context limits and deduplicates
records. Repeated compilation yields byte-equivalent structured output.
`diagnose_coverage()` detects missing factor contrasts and single-identity
worlds before any model is run.

The initial 4-variant plan produces 96 independently oracle-checked records
(six capabilities by two truth classes by two world sizes by four variants).
These are **unreleased candidate records**. They never replace the frozen
144 teaching/72 examination manifest, never modify the human run, and do not
establish new neural mastery or NI morphology conformance.

## Next design layers

1. Build a versioned **Sheet-to-AST importer** from exact tab/column schemas,
   preserving cells' source row IDs, proposal status, source links and
   prerequisite graph. Fail closed on ambiguous historical tranche aliases,
   missing approvals or changed token meanings.
2. Generalize node-specific builders beyond Grade A using reusable typed
   mathematical axiom families, legal New Ithkuil morphosyntactic
   constructors and independently checked inverses; each needs an admitted
   domain plus a trustworthy oracle. Never promote exploratory NI bridges by
   treating a prose analogy as a semantic rule.
3. Add factor-coverage and metamorphic test families: variable renaming,
   permutations, directed-relation reversals, logical equivalence, cardinality
   controls, illegal structures and unseen recombinations. Differentiate
   *invariance* from semantic changes that should flip the answer.
4. Independently partition new candidate material into teaching, teacher
   reward-validation and sealed examination sets. Prevent near-duplicate
   worlds, lexical shortcuts, output-label skew and exposure of held-out
   answers. The *existing* Grade A exam remains frozen.
5. Treat weak held-out growth despite high teaching accuracy as a
   classifiable `GENERALIZATION_GAP`, with coverage and interference
   diagnostics. Generate a corrective *curriculum proposal*, not endless
   repetition of memorized rows. Learner-controlled self-organization is a
   future independently qualified scheduling change, not a current claim.

## Admission boundary

Compilation is not approval. The current source-accepted Grade A and its
exam seal remain unchanged. The existing human-operated trainer uses the
accepted inventory only. Agents may compile and validate probes and synthetic
fixtures but must never optimize the actual Bilqis student.
