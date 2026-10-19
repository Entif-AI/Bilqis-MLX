# Bilqis curriculum authority convergence and executable-factory plan

**Status:** Governing architecture record for the factory-closure branch.
**Date:** 2026-10-19.
**Scope:** Curriculum semantics, execution profiles, factory releases, assessment, championship dependencies, New Ithkuil ingestion, telemetry, and migration sequencing.
**Training authority:** This document does not authorize neural optimization. The human operator alone starts or resumes the real Bilqis trainer.

## Purpose

Bilqis has accumulated several valid but differently scoped authorities: direct user decisions, protected operational requirements, repository specifications, the Specs and Failures Ledger, the Curriculum Registry, research roadmaps, New Ithkuil source artifacts, and historical release evidence.

The immediate factory repair must not create another authority layer that competes with them. This document records the current interpretation, conflicts, design, and migration order before additional implementation work proceeds.

The target is one executable curriculum authority:

```text
source-grounded semantic definition
        +
source bindings
        +
execution profile
        |
        v
compile_execution_plan(...)
        |
        v
ExecutionPlan
        |
        v
FactoryRelease
        |
        +--> source generation / oracle
        +--> answer modalities
        +--> scheduler / assessment
        +--> retention / stagnation
        +--> championship evidence identity
        +--> telemetry / dashboard
        +--> checkpoint compatibility
```

No generic runtime subsystem may maintain an independent curriculum ontology.

## Authority roles

These sources do not have equal jobs. They remain aligned by preserving those roles.

1. **Latest direct user instruction** controls when it explicitly changes an earlier decision.
2. **Protected IPR-0220 requirements** preserve private curriculum, trainer, custody, and remediation requirements.
3. **Current repository specifications** define executable desired state for this codebase.
4. **Specs and Failures Ledger** normalizes decisions, supersessions, failures, and evidence. It is a requirements index, not a runtime allocator.
5. **Code-resident semantic definitions and immutable ABI manifests** own executable semantic identity after admission.
6. **Curriculum Registry** preserves semantic inventory, mappings, prerequisites, review state, lineage, and source evidence. It does not allocate live runtime identity by spreadsheet position.
7. **New Ithkuil source corpus** preserves source-addressable linguistic evidence and deterministic extracted structure.
8. **Roadmaps and research seeds** define sequencing, research intent, and candidate future work. They do not override later admitted runtime contracts.
9. **Historical releases, comments, and run receipts** remain immutable evidence and compatibility inputs. They do not define new live policy.

When these sources disagree, record the disagreement and supersession explicitly. Do not merge incompatible rules into a compromise.

## Findings that already align

### The roadmap and SPEC-0001 describe the same program

The October roadmap already separates the semantic ABI, New Ithkuil donor map, deterministic compiler/codecs, token ABI, source-backed generators/oracle, prerequisite graph/stage contracts, and learner admission gates. SPEC-0001 makes the missing executable connection mandatory.

The current factory repair therefore implements an existing program requirement. It does not create a new curriculum philosophy.

### The alpha supplement is experimental precedent, not production authority

The alpha supplement explicitly permits a small vertical slice before the full pre-language substrate is complete. It also explicitly states that the slice does not complete the broad New Ithkuil, full foundation, or confirmatory contracts.

Alpha artifacts may supply fixtures, failure evidence, or implementation lessons. They do not become the canonical production ontology.

### The New Ithkuil Semantic Bridge is a research seed

The bridge correctly requires source-bound roots, morphological factors, deterministic evaluation, held-out composition, append-only identity, and prerequisite-aware teaching. It also labels itself a research seed rather than a token ABI or executable specification.

The factory may compile admitted descendants of that material. It must not silently promote research-seed mappings into training gold.

### The current Ithkuil corpus is useful but incomplete

`lib/ithkuil/_data/csv` provides source-addressable grammar records, atomic morphology, compositions, components, allomorph rules, source assertions, crosswalks, semantic bridges, and a limited set of root senses.

The New Ithkuil lexicon and affix PDFs are fetched and SHA-pinned. They are not yet systematically parsed into a complete canonical lexical source graph. Registry-derived lexicon bridge rows are enrichment evidence, not proof of complete lexicon ingestion.

### The Ledger already supports the factory direction

Current Ledger rules support code-resident AST authority, append-only identity, source/oracle truth, typed answer families, prerequisite-safe composition, deterministic generation, and explicit current-versus-historical status.

The Ledger should index the factory authority and its supersessions. It should not duplicate executable logic.

## Current conflicts and required normalization

### C-01: reduced B is implemented as a release lineage but must converge to profile data

Current human-run history includes separate reduced/minimal B release identities and migration logic. That history is valid evidence and may require compatibility decoding.

The target architecture does not extend that design.

Canonical B remains the semantic curriculum. A reduced AND/IFF experiment is a `CurriculumProfile` over canonical B:

- active: `B.AND`, `B.IFF`, `B.COMPOSITE`, `B.IDBOOLOPS`;
- COMPOSITE provider domain: `AND, IFF`;
- IDBOOLOPS provider domain: `AND, IFF`;
- Boolean-operator answer domain: `AND, IFF`.

The normal full-B source providers remain the providers. There is no canonical `minimal_boolean` source domain.

Historical minimal-B releases remain readable only through explicit compatibility logic after cutover.

### C-02: title ownership and teaching advice were incorrectly conflated

The 2026-10-19 championship correction makes capability title ownership and title challenges grade-isolated. A checkpoint whose retained optimizer update originated in Grade B cannot own or defend a Grade A title.

That rule does not by itself revoke the separately explicit 2026-10-18 teaching rule:

- each active **maxed capability role** contributes one direct source-gold-gated advisory vote to lessons in any admitted grade;
- shared checkpoint inference may be deduplicated, but vote multiplicity remains per qualifying role;
- non-max roles contribute zero direct role votes;
- the frozen grade soup remains a separate adviser;
- same-grade soup advice uses its full frozen base votes;
- foreign-grade soup advice uses `base_votes / admitted_grade_count`.

Title geography and teaching geography are different contracts.

The Oct-19 Ledger/Registry wording that inferred “same-grade title ownership” to mean “same-grade direct advice only” is an overbroad supersession unless a later direct user instruction explicitly revokes the 2026-10-18 cross-grade advisory rule.

### C-03: holistic school change resets live championship authority

Any change that breaks apples-to-apples school comparison archives and clears all active champions and soups before further advice or title defense.

The school identity includes at minimum:

- admitted course/question inventory;
- executable factory-release identity;
- semantic graph/catalog identity;
- model parameter-shape geometry.

The causal student and its matching AdamW continue unless a separate authorized operation changes them. Historical championship evidence and the settled-match ledger remain immutable history.

### C-04: Curriculum Registry is evidence authority, not live execution authority

The Registry remains essential for semantic coverage, mapping review, prerequisite evidence, lineage, and source reconciliation.

Runtime behavior must not depend on spreadsheet row order, spreadsheet-only IDs, or uncompiled sheet state. Admitted semantics move into code-resident typed definitions and immutable ABI manifests.

Registry updates must preserve historical rows and mark supersession rather than rewriting history.

### C-05: assessment metadata is not a verified rubric

`ExecutionPlan` may contain an assessment blueprint digest. That digest records declared scope and answer contract.

Only `FactoryRelease` admission may mint the executable assessment seal after source generation, oracle verification, coverage checks, and admitted question/rubric construction succeed.

No metadata-only hash may masquerade as source-verified assessment authority.

### C-06: profiles may narrow execution, not rewrite pedagogy or semantics

A `CurriculumProfile` may:

- enable or disable admitted capabilities;
- narrow provider dimensions explicitly declared by the provider;
- narrow registered answer-domain values.

A profile may not:

- invent semantic identities;
- invent source providers or provider dimensions;
- add unknown answer labels;
- rewrite prerequisites or `composed_of`;
- disable a prerequisite or constituent required by an active capability;
- hand-author teaching stages.

Teaching stages derive from the canonical curriculum and are filtered by active capability inventory.

## Canonical executable model

### CurriculumDefinition

`CurriculumDefinition` is the canonical admitted semantic curriculum declaration. It owns stable capability identity, grade membership, prerequisites, composition, answer-family declarations, exam-count intent, and canonical teaching stages.

`Course` remains a compatibility input during migration. New canonical semantics must not originate from release-specific `Course` builders.

### SourceBindingSet

`SourceBindingSet` binds each capability to a typed source provider, oracle, source provenance, and implementation identity.

Provider specialization is valid where the source domain differs. Grade or release identity is not a provider boundary.

### CurriculumProfile

`CurriculumProfile` is an execution overlay over admitted semantics. It selects a legal subset and legal provider/answer narrowing.

Temporary experiments belong here when the semantics themselves have not changed.

### ExecutionPlan

`compile_execution_plan(...)` produces the sole live executable curriculum contract.

The plan contains:

- active capability inventory;
- derived teaching stages;
- prerequisites and composition;
- provider IDs and implementation digests;
- validated provider parameters;
- answer families and active values;
- assessment blueprint metadata;
- source, coverage, and teaching metadata;
- global and capability-scoped dependency digests.

The plan carries scoped projections for roster, schedule, assessment, source, answer schema, coverage, and teaching.

A change to B must not invalidate unrelated A evidence unless an A-bound dependency actually changed.

### Answer modality registry

Answer behavior is selected by answer kind, not grade or release.

`binary`, `boolean_operator`, `numeric_active`, and later modalities resolve through typed modality adapters. The adapter validates the active value domain and binds answer labels to semantic-token identities.

Adding a modality adds one modality adapter. Adding a grade must not require a new answer-head branch.

### FactoryRelease

`FactoryRelease` becomes the immutable admission artifact that binds semantic curriculum provenance, source bindings, profile identity, compiled `ExecutionPlan`, provider implementation digests, answer-modality descriptors, semantic lineage/geometry, generated source and coverage receipts, and the final admitted assessment seal.

Generic runtime consumers read this artifact or its typed projections. They do not reconstruct curriculum from release names or concrete provider modules.

## New Ithkuil ingestion target

The New Ithkuil program must eventually become this deterministic path:

```text
official grammar + lexicon + affix sources
        |
        v
pinned source snapshot
        |
        v
deterministic parsers
        |
        v
canonical Ithkuil source graph
        |
        +--> lexical roots / stems / specifications
        +--> morphology / categories / allomorphy
        +--> source-licensed composition rules
        +--> provenance and uncertainty state
        |
        v
semantic admission / bridge review
        |
        v
CurriculumDefinition + AdmittedToken additions
        |
        v
append-only semantic ABI
        |
        v
SourceBindingSet + CurriculumProfile
        |
        v
ExecutionPlan -> FactoryRelease
        |
        +--> lessons
        +--> routine assessment
        +--> understanding probes
        +--> dashboard inventory
        +--> generated conformance tests
```

The parser may discover source facts. It does not decide learner exposure by source order. Curriculum ordering remains a separate prerequisite/admission problem.

## Runtime state validity

Persistent subsystem state must bind only to the compiled projections it consumes.

- scheduler and stagnation state bind schedule projections;
- cohort and assessment evidence bind assessment, source, and coverage projections;
- championship evidence binds assessment and source identity plus the separate championship school identity;
- answer-head metadata binds answer schema and modality implementation;
- telemetry active inventory binds roster.

On plan transition:

1. unchanged dependency: preserve state;
2. changed dependency with a proven generic reconciliation: reconcile;
3. changed dependency without such proof: invalidate the dependent state;
4. incompatible neural semantic geometry: fail closed.

No reconciliation function may dispatch on concrete grade, capability, or release IDs.

## Migration plan

### Governance wave: current work

Before more factory implementation:

1. land this convergence record;
2. point `README.md` and `AGENTS.md` at it;
3. correct reduced-B wording so implementation history is not described as the target architecture;
4. separate championship title isolation from cross-grade maxed-role advisory rights;
5. checkpoint the same interpretation into the protected tracker and normalized sheets;
6. preserve historical roadmap and experiment documents as snapshots instead of rewriting them to look current.

### Wave 0.5: falsifiable compiler proof

Finish the isolated proof without runtime cutover:

- canonical `CurriculumDefinition`;
- `SourceBindingSet`;
- `CurriculumProfile`;
- `ExecutionPlan`;
- dependency-closed profiles;
- derived teaching stages;
- scoped projection digests;
- provider implementation identity;
- typed answer modalities;
- explicit plan lineage and semantic-geometry classification;
- real full-B providers constrained to AND/IFF through the same provider identities;
- stronger closure-checker adversarial tests.

The reduced Boolean proof must not import or create a minimal-B provider.

### Wave 1: FactoryRelease integration

Make `FactoryRelease` carry the compiled execution plan and final source-verified assessment authority.

Historical manifests decode through compatibility projection. Compatibility decoding must not select live successors.

**Current checkpoint:** schema `bilqis.mlx.factory-release/v2` is implemented as the target executable artifact while historical v1 remains byte-stable compatibility. V2 binds `CurriculumDefinition`, `SourceBindingSet`, `CurriculumProfile`, `ExecutionPlan`, semantic catalog identity, provider and answer-modality implementation descriptors, compiled semantic-token answer heads, source-verified capability specimen receipts, cumulative verified assessment seals, and predecessor transition metadata. Runtime admission still consumes v1 and has not been cut over.

The v2 admission specimens are verification evidence, not a permanent test bank. They prove minimum source/oracle/answer-contract generation under the compiled release and bind the coverage projection. They do not claim exhaustive semantic-axis coverage or replace fresh routine cohorts.

Dedicated v2 custody/admission primitives now persist and cold-read the content-addressed artifact, verify the actual loaded semantic catalog, and bind the release to the exact causal student, optimizer step and semantic graph. Existing live v1 admission remains unchanged. V2 release transitions carry `UNCHANGED` and `APPEND_ONLY_EXPANSION`; `INCOMPATIBLE` geometry fails closed.

### Wave 2: runtime consumers

Migrate consumers by dependency:

1. generation and answer schema;
2. scheduler and assessment scope;
3. stagnation and retention;
4. championship evidence identity;
5. telemetry and dashboard current inventory;
6. CLI preflight/status.

Changing only a profile must change disposable live behavior without editing those consumers.

**Current scheduler checkpoint:** `ScheduleProgram` is now the scheduler-owned runtime view. It is compiled from the admitted v2 release's roster/schedule projections and exact grade-scope assessment identities; historical `Course` scheduling input is isolated behind compatibility. The next cutover step is to make the human trainer admit/read v2 and pass that projection explicitly, then delete the scheduler's temporary legacy fallback.

**Current checkpoint:** generation and answer-schema consumers are release-driven and profile-neutral in the factory layer. Full Boolean versus AND/IFF behavior changes by swapping the admitted v2 release, with no consumer branch or minimal-B provider. The real pinned provider path also passes the resulting v2 answer heads into the generic typed batch adapter. Scheduler/assessment cohort lifetime and the existing human/live admission path remain unchanged pending the next migration slice.

Exact assessment scope now has a grade-neutral v2 contract. The rubric identity hashes only the selected capabilities' assessment projections. The source identity hashes only their source projections plus verified source receipts. The enclosing factory-release SHA and semantic-catalog SHA remain separate identities. This prevents the prior scope/rubric conflation where a broader admitted course could relabel evidence for a narrower scored scope.

Parallel v2 assessment custody now implements the governing lifetime distinctions without grade/release switches: fresh routine measurement, fixed-within-attempt promotion, and fresh/burnable generalization all receive the exact active capability scope explicitly. Persisted cohort evidence keeps scope rubric/source identities separate from holistic release identity. Existing human/live assessment callers still use the historical path; the next cutover must migrate callers rather than leave both paths canonical.

### Wave 3: typed release transitions

Replace named successor switches with structural plan/release diffs:

- `UNCHANGED`;
- prefix-preserving `APPEND_ONLY_EXPANSION`;
- `INCOMPATIBLE`.

Profile-only changes preserve neural semantic geometry by construction.

### Wave 4: delete parallel live authority

Remove canonical live use of minimal-B release/provider identity, compact-B validator exceptions, release-name answer-head selection, trainer release/capability successor branches, release-specific current-state event classes, and capability-ID policy tables in generic runtime.

Historical readers remain under compatibility boundaries only.

### Wave 5: disposable Grade Z

Run one synthetic grade through the same top-level orchestration used by the human shell: admission, teaching, routine assessment, recovery, promotion/generalization, championship, stagnation, telemetry, checkpoint/recovery, and stop handling.

Adding Grade Z must require no generic runtime edit.

### Wave 6: closure

`python3 scripts/check_factory_closure.py` must report `FACTORY_CLOSURE_OK`.

Static closure is necessary but insufficient. Real-provider behavior and the full Grade Z runtime proof are also required.

## Convergence matrix

| Domain | Governing interpretation | Evidence / planning sources | Current normalization need |
| --- | --- | --- | --- |
| Semantic identity | Code-resident typed definition + immutable append-only ABI after admission | Registry, Ledger, Ithkuil corpus, semantic bridge | Keep sheets as evidence/review surfaces, not live allocators |
| Curriculum order | Canonical prerequisites and stages; profiles only filter | Roadmap, SPEC-0001, IPR-0220 | Remove release-specific stage authorship |
| Factory compilation | One `ExecutionPlan` compiled from semantics + source bindings + profile | SPEC-0001, architecture 09 | Integrate into `FactoryRelease` |
| Answer modalities | Typed modality registry, grade-neutral | SPEC-0001 `10.4, typed-answer evidence | Remove grade/release head builders |
| Source/admission | Typed providers + independent oracle + coverage proof | IPR-0220, Ithkuil corpus, Bridge | Add complete lexicon parser and provider binding |
| ABI growth | Append-only admitted-token path | Roadmap, Registry, existing Grade C path | Ithkuil compiler must emit admitted identities |
| Assessment lifetime | Fresh routine cohorts; qualification attempts separately identified; release seal source-verified | championship spec, Ledger, factory spec | Keep blueprint hash separate from admitted seal |
| Championship | Same-grade title ownership; school-identity reset; advisory rights separate from title geography | SPEC-0002, governing Drive spec, protected tracker | Preserve cross-grade maxed-role advisory rule unless explicitly rescinded |
| Autonomy | Evidence/remediation over admitted release; cannot invent semantics | Oct-19 autonomy work | Consume `ExecutionPlan` projections after cutover |
| Ithkuil ingestion | Grammar corpus deterministic; lexicon PDF parsing incomplete | `lib/ithkuil`, Oct-19 Minutes, Bridge | Build canonical lexicon/affix ingestion |
| Telemetry | Current inventory comes from admitted executable plan | SPEC-0001, School50 contract | Stop reconstructing current curriculum from historical event names |
| Human-run custody | Human alone starts real optimizer updates | All current operational authorities | Preserve unchanged |

## Acceptance before further implementation

The factory branch may resume code work only when:

- this record is committed and pushed;
- root governance points here;
- the protected tracker carries the same current interpretation;
- normalized tracker rows distinguish the current rule from historical superseded rules;
- no unresolved source conflict is being silently encoded as implementation;
- the dirty Wave 0.5 proof remains preserved.

The next code change after this governance wave is verification and repair of the existing Wave 0.5 proof. It is not a trainer, CLI, or broad runtime cutover.
