# Executable curriculum closure

**Authority note:** Read [`10_CURRICULUM_AUTHORITY_CONVERGENCE_20261019.md`](10_CURRICULUM_AUTHORITY_CONVERGENCE_20261019.md) with this design. That record owns the cross-source authority hierarchy, supersession conflicts, New Ithkuil integration boundary, and governance-first migration order. This file owns the executable-factory architecture.

## Problem

SPEC-0001 requires one declarative curriculum architecture in which new grades and capability changes flow through a common factory without edits to generic trainer, scheduler, evaluation, promotion, dashboard, checkpoint, or teacher runtime. The present implementation does not satisfy that contract. `FactoryRelease` is compiled and admission-gated, but much of live execution still reconstructs behavior from `Course`, concrete provider modules, release-name switches, CLI flags, and subsystem-local state assumptions. The reduced-Boolean experiment exposed the consequence: changing the active B roster required follow-up repairs in assessment rubric selection, championship source identity, dashboard replay, and stagnation scope.

The architecture therefore has two authorities in practice:

1. the declarative course/factory artifact; and
2. handwritten runtime/provider knowledge that independently interprets the current release.

The second authority must disappear from canonical execution. Historical compatibility may decode old receipts, but it must not remain an alternative live architecture.

## Usage

The caller chooses a semantic curriculum, source bindings, answer modalities, and an optional declarative execution profile. It does not choose trainer branches.

```python
curriculum = load_curriculum_definition("bilqis.school/core-v1")
bindings = load_source_bindings("bilqis.school/source-bindings-v1")
providers = provider_catalog()
answers = answer_modality_registry()

profile = CurriculumProfile(
    profile_id="boolean-kernel/and-iff",
    grades=(
        GradeProfile(
            grade_id="B",
            enabled_capabilities=(
                "B.AND",
                "B.IFF",
                "B.COMPOSITE",
                "B.IDBOOLOPS",
            ),
            capabilities=(
                CapabilityProfile(
                    "B.COMPOSITE",
                    provider_parameters=(("operators", ("AND", "IFF")),),
                ),
                CapabilityProfile(
                    "B.IDBOOLOPS",
                    provider_parameters=(("operators", ("AND", "IFF")),),
                    answer_family_values=(("boolean_operator", ("AND", "IFF")),),
                ),
            ),
        ),
    ),
)

plan = compile_execution_plan(
    curriculum,
    profile,
    providers,
    source_bindings=bindings,
    answer_registry=answers,
)
release = compile_factory_release(
    curriculum=curriculum,
    source_bindings=bindings,
    execution_plan=plan,
    answer_modalities=answers.descriptors_for(plan),
)
SchoolRuntime.from_release(release).resume(run_dir)
```

The same runtime call must work for an unfamiliar synthetic grade. No new grade, capability, or release name may be added to generic runtime source.

Changing the active Boolean kernel is profile data. The canonical B curriculum remains full and staged. Filtering the canonical stages by the active roster automatically produces `AND/IFF -> COMPOSITE -> IDBOOLOPS`.

Compiling a profile must alter only the downstream projections that depend on the changed declaration. The caller must not edit assessment, stagnation, championship, telemetry, answer-head, or migration code.

## Shape

### Semantic curriculum, source bindings, and executable profile are different things

The legacy `Course` object mixes several authorities: semantic capability structure, pedagogy, source generator/oracle IDs, release version, source attestation, and assessment seals. That is too much authority for one runtime-facing object.

The target split is:

1. `CurriculumDefinition`: semantic and pedagogical meaning only, including capability roster, prerequisites, composition, answer families, item counts, and teaching stages.
2. `SourceBindingSet`: capability-to-generator/oracle/source provenance bindings plus source attestation.
3. `CurriculumProfile`: active subset and allowed narrowing of provider/answer domains.
4. `ExecutionPlan`: compiled runtime projections and dependency digests.
5. `FactoryRelease`: immutable admission artifact that binds the four inputs above to sealed assessments, lineage, semantic geometry, and implementation evidence.

`Course` is a compatibility input during migration. New canonical declarations must not originate from it.

A profile may disable capabilities or narrow dimensions that the provider declares configurable. It may not invent semantics, source adapters, answer values, prerequisites, composition, teaching stages, or operations.

```python
@dataclass(frozen=True)
class CapabilityProfile:
    capability_id: str
    provider_parameters: tuple[tuple[str, tuple[str, ...]], ...] = ()
    answer_family_values: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class GradeProfile:
    grade_id: str
    enabled_capabilities: tuple[str, ...] | None = None
    capabilities: tuple[CapabilityProfile, ...] = ()
```

### The compiler produces the sole live execution contract

`ExecutionPlan` is compiled from `CurriculumDefinition + SourceBindingSet + CurriculumProfile + provider/answer registries`.

```python
@dataclass(frozen=True)
class CapabilityExecution:
    capability_id: str
    grade_id: str
    stage: int
    prerequisites: tuple[str, ...]
    composed_of: tuple[str, ...]
    source_anchor: str
    provider_id: str
    provider_implementation_sha256: str
    oracle_id: str
    provider_parameters: tuple[tuple[str, tuple[str, ...]], ...]
    variation_axes: tuple[str, ...]
    teaching_option_ids: tuple[str, ...]
    answer_families: tuple[AnswerFamily, ...]
    exam_item_count: int


@dataclass(frozen=True)
class ExecutionPlan:
    profile_id: str
    curriculum_sha256: str
    source_binding_sha256: str
    grades: tuple[GradeExecution, ...]
    capabilities: tuple[CapabilityExecution, ...]
    projection_digests: ProjectionDigests
    capability_projection_digests: tuple[CapabilityProjectionDigests, ...]
```

The plan carries both global and capability-scoped digests for `roster`, `schedule`, `assessment`, `source`, `answer_schema`, `coverage`, and `teaching`. A B-only profile revision therefore need not invalidate unrelated A evidence.

Assessment identity in the plan is a blueprint digest, not a final rubric seal. `FactoryRelease` must generate/verify the admitted assessment material and mint the executable seal. A metadata hash is never allowed to masquerade as source-verified assessment authority.

### Source specialization is a provider boundary, not a grade boundary

Concrete Boolean/numeric/etc. code is legitimate when it implements a real source-domain constructor or oracle. It belongs behind a provider catalog keyed by declared provider IDs.

The provider interface receives compiled constraints:

```python
class SourceProvider(Protocol):
    descriptor: SourceAdapter

    def draw(
        self,
        *,
        capability: CapabilityExecution,
        seed: int,
        each: int,
        source: SourceContext,
    ) -> tuple[Specimen, ...]: ...

    def check(
        self,
        specimen: Specimen,
        *,
        capability: CapabilityExecution,
        source: SourceContext,
    ) -> bool: ...
```

There is no `minimal_boolean` provider. The normal Boolean providers receive the `operators=("AND", "IFF")` constraint from the compiled execution plan.

Provider configuration is part of the source contract. A provider descriptor declares the dimensions that an execution profile may narrow and their canonical domains. The compiler rejects unknown dimensions, values outside the canonical domain, and reordered values. Plan-driven generation passes the compiled constraints to the provider. A profile therefore cannot claim AND/IFF-only execution while calling an unconstrained six-operator generator.

### Answer modality is an extension boundary

The execution plan declares answer families and active values. It does not contain grade-specific model-head code.

Each answer kind resolves through a typed answer-modality adapter. The adapter owns the mapping from answer labels to semantic-token identities and the training/evaluation mechanics for that modality. `binary`, `boolean_operator`, and `numeric_active` are modality identities, not Grade A/B/C branches.

For example, the Boolean-kernel profile compiles:

```text
answer kind: boolean_operator
values:      AND, IFF
```

The `boolean_operator` modality adapter maps those values to their existing semantic-token identities. No minimal-B answer-head builder exists.

Adding a new answer modality requires one new typed modality adapter, as SPEC-0001 §10.4 permits. Adding a grade or changing a capability roster does not.

### Release transitions are diffs, not version switches

Plan changes are compared structurally. Profile-only changes over the same semantic curriculum are geometry-neutral by construction. A semantic curriculum change requires explicit lineage, and the model ABI classifies the semantic-token catalog as unchanged, append-only expansion, or incompatible.

```python
class SemanticGeometryChange(Enum):
    UNCHANGED = "UNCHANGED"
    APPEND_ONLY_EXPANSION = "APPEND_ONLY_EXPANSION"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass(frozen=True)
class PlanLineage:
    previous_curriculum_sha256: str
    next_curriculum_sha256: str
    semantic_geometry: SemanticGeometryChange
```

No generic code asks whether the version is `MINIMAL_BOOLEAN_RELEASE`, `BOOLEAN_IDENTIFICATION_RELEASE`, or `NUMERIC_STAIRCASE_RELEASE`.

The transition executor ultimately has three cases:

1. semantic geometry unchanged: preserve model/AdamW exactly and reconcile only state whose bound projections changed;
2. append-only semantic expansion: invoke the one model-ABI vocabulary expansion boundary, then admit the plan;
3. incompatible geometry: fail closed. No automatic migration.

Same-grade revision, appended grade, provider revision, and profile revision are derived from the release diff rather than hard-coded release names.

### Persistent subsystem state is bound to compiler projections

Every durable control-plane structure that depends on curriculum geometry carries the global and/or capability-scoped projection digests it consumed. A subsystem binds only the dependencies it actually uses.

Examples:

- scheduler state binds `schedule` for its active capability set;
- stagnation state binds the same schedule nodes;
- assessment/cohort evidence binds `assessment + source + coverage` for represented capabilities;
- championship title evidence binds `assessment + source` for its capability;
- typed answer-head metadata binds `answer_schema` plus answer-modality implementation identity;
- dashboard active inventory binds `roster`.

On resume or release transition, generic runtime compares stored projection digests with the newly admitted plan.

If a dependency is unchanged, the state remains valid.

If a dependency changed, the generic policy is fail-closed invalidation. A subsystem may define a pure reconciliation function when preservation is semantically safe, such as retaining quarantined capabilities that remain in the new required scope. Reconciliation is keyed by projection kind, never by grade/release/capability names.

This is the structural mechanism that replaces the recent sequence of rubric, championship, dashboard, and stagnation repair patches.

### Telemetry consumes inventory, not historical assumptions

Every curriculum admission/revision event carries the exact executable inventory and projection digests.

The dashboard starts from the currently admitted inventory and overlays historical events only when those events' release/projection identity is compatible with the view being rendered. It does not reconstruct "current B" by replaying every historical B event.

Event names describe event class, not a grade-specific implementation path:

- `SCHOOL_CURRICULUM_ADMITTED`
- `SCHOOL_CURRICULUM_REVISED`
- `SCHOOL_EXAM_COMMITTED`
- `SCHOOL_VISIT_COMMITTED`
- `SCHOOL_CHAMPIONSHIP_UPDATED`

Grade and capability remain typed event fields.

### Tests compile from declarations

The core conformance proof is mutation-driven.

One synthetic `CurriculumDefinition` is compiled under multiple profiles and source-binding sets. Tests mutate:

- enabled capability roster;
- stage membership;
- prerequisite edge;
- source/provider binding;
- answer-family domain;
- construction constraint.

Each mutation must regenerate exactly the affected projection digests and runtime inventory.

A full synthetic Grade Z disposable system proof must run through the same generic runtime boundary used by the human shell, including:

- admission;
- teaching schedule;
- routine assessment;
- promotion/generalization lifecycle;
- championship evidence;
- stagnation containment;
- telemetry projection;
- crash/recovery.

The present Grade Z tests are insufficient because they directly exercise generation/admission/scheduler fragments and never prove the actual `operate()` path is grade-neutral.

### Architecture enforcement matches the real invariant

Static conformance must reject more than literal `if grade == "B"`.

Generic runtime modules must reject:

- control decisions on concrete release constants;
- imports of concrete grade/capability provider modules;
- capability-ID control dispatch;
- release-specific answer-head builders;
- release-specific successor selection;
- new grade-specific event classes;
- live provider registries that encode a release/profile as a separate source domain when it is only a constraint over an existing source domain.

Compatibility readers may contain historical identities under `compatibility/`, but canonical live execution cannot import them for policy.

## Synthesis decision

Two shapes were considered.

The selected base is a compiled `ExecutionPlan` inside `FactoryRelease`, plus declarative `CurriculumProfile` overlays and projection-digest-bound runtime state. It directly addresses the observed failure mode while preserving the existing scheduler, source providers, model custody, and immutable historical receipts.

The competing shape was a full event/program interpreter in which the curriculum compiler emits an executable command language and all school behavior becomes a reducer over those commands. That shape is cleaner in the abstract and could eventually subsume the scheduler, but it requires replacing too much verified behavior at once. It increases migration risk without being necessary to eliminate the current split authority.

The selected design borrows the interpreter candidate's most important property: runtime behavior is data-driven and content-addressed, and subsystem state derives validity from the compiled program rather than duplicated handwritten assumptions.

Rejected: a callback/plugin registry for every runtime subsystem. That would merely turn the current grade/release conditionals into registered callbacks and preserve information leakage across scheduler, telemetry, championships, and stagnation.

## Tradeoffs accepted

- We accept compiling a richer immutable release artifact in exchange for removing parallel runtime interpretation of `Course`.
- We accept invalidating some curriculum-bound evidence after a profile change in exchange for default-safe transition semantics and eliminating bespoke migration repair code.
- We accept keeping historical release readers under compatibility boundaries in exchange for preserving old receipts without letting history dictate new runtime architecture.
- We accept one explicit model-ABI graph-expansion boundary in exchange for keeping neural-shape mutation out of the curriculum compiler.

## Alternatives considered

**Full event/program interpreter.** Strongest theoretical closure, because the compiler emits all commands the runtime can execute. It lost for the first migration because it replaces the scheduler and event machinery simultaneously, expanding blast radius while the current experiment still depends on them.

**Registry of per-release/per-grade callbacks.** Small implementation diff, but shallow. Callers would still need to know which callback family applies, and policy would remain duplicated across callback registries. It would hide conditionals without removing them.

**Continue extending `FactoryRelease` as an admission certificate while patching consumers.** Rejected. This is the current architecture and is the demonstrated failure mode.

## Open questions and risks

- The real full-B COMPOSITE and IDBOOLOPS providers now accept an operator-domain profile and pass the pinned-source 48-row AND/IFF proof. Other current providers, especially numeric C, still need the same contract review.
- `typed_answer_training.py` still contains modality-specific runtime validation. It must move behind the typed answer-modality registry without weakening ABI checks.
- Persisted evidence needs an explicit dependency map before runtime cutover so reconciliation is scoped rather than global.
- Historical release IDs must decode into semantic curriculum + source bindings + full profile under `compatibility/`; they must not remain live successor policy.
- The target executable release artifact now exists as schema `bilqis.mlx.factory-release/v2`. It binds the canonical curriculum, source bindings, profile, compiled plan, provider implementation descriptors, answer-modality descriptors and semantic-token head bindings, semantic catalog digest, source-verified admission specimens, cumulative verified assessment seals, and optional predecessor delta. The historical v1 `Course`-based release hash/decoder remains byte-stable compatibility evidence and is not the target live authority.
- V2 admission specimens prove that the configured provider/oracle/answer contract can generate the required minimum verified sample under the compiled plan. Their hashes bind the declared coverage projection; they do **not** claim exhaustive semantic-axis saturation or become the routine exam cohort.
- Runtime admission still consumes v1. No trainer, scheduler, championship, telemetry or CLI consumer may be moved to v2 until the v2 artifact and transition tests are checkpointed and the admission boundary is migrated explicitly.
- V2 now has dedicated durable persist/readback and admission primitives. Cold readback reconstructs the artifact without rebuilding a `Course`, verifies the loaded semantic-token catalog and compiled answer-token bindings, and checks an admission receipt binding release, plan, curriculum, source bindings, semantic catalog, full graph identity, causal student and optimizer step. These primitives are not called by the existing live v1 path.
- Release-level transition tests cover profile-only `UNCHANGED`, prefix-preserving `APPEND_ONLY_EXPANSION`, and fail-closed `INCOMPATIBLE` geometry.

## Next implementation step

Wave 0.5 and the isolated Wave 1 v2 release/admission proof are complete. The next migration is Wave 2 consumer cutover by typed projection, beginning with source generation and answer schema. Existing human/live admission remains on v1 until an explicit consumer cutover changes it.

## Migration sequence

This redesign is an architectural cutover, not permission to maintain both execution paths indefinitely.

### Wave 0: prove the compiled dependency graph

Build `CurriculumDefinition`, `SourceBindingSet`, `CurriculumProfile`, `ExecutionPlan`, scoped projection digests, answer-modality adapters, lineage classification, and mutation tests. The reduced Boolean kernel must compile and generate from the real full-B providers and pinned source without importing or naming a minimal-B release/provider.

Exit gate: mutation tests distinguish roster, schedule, assessment, source, answer-schema, coverage, and teaching dependencies; unrelated capability digests remain unchanged; real pinned-source constrained generation passes; and `scripts/check_factory_closure.py` records the current split-authority baseline.

### Wave 1: make FactoryRelease carry the executable plan

Persist the profile identity and compiled execution plan in the immutable factory-release artifact. The v2 artifact also binds semantic catalog identity, exact provider/modality implementation descriptors, compiled answer-head identity, source-verified admission specimens and cumulative verified assessment seals. Dedicated v2 durable admission can read the plan from that artifact without reconstructing `Course`; the existing live v1 admission function has not been switched.

Historical v1 factory-release manifests and hashes remain byte-stable. Their decoder is a compatibility boundary only. It must not become a live successor selector or a second canonical factory path.

The verified assessment seal is not a frozen routine question bank. It proves that release compilation generated and independently source-checked the admitted minimum specimen set for every capability in the cumulative grade scope and binds those receipts to the assessment blueprint. Routine assessment still follows its own fresh-cohort lifetime contract.

Exit gate: a fresh v2 release has one content-addressed artifact containing semantic provenance, executable projections, implementation identities, semantic-catalog binding, source-verification receipts, assessment seals and predecessor transition metadata; v1 hashes remain unchanged.

**Exit evidence:** satisfied on the isolated factory branch. V2 JSON roundtrip, rehashed inconsistency rejection, real pinned Boolean profile compilation, source/oracle refusal, exact semantic-catalog readback, durable custody, admission baseline binding, and all three semantic-geometry transition classes are covered by tests. No live runtime consumer has been cut over.

### Wave 2: cut runtime consumers over by projection

Migrate consumers in dependency order:

1. source specimen generation and answer schema;
2. scheduler/assessment scope;
3. stagnation and retention scope;
4. championship evidence identity;
5. telemetry/current inventory;
6. CLI preflight/status.

Each consumer accepts the execution plan or its typed projection. It must not accept a release-name flag or rebuild a roster from concrete provider modules.

Exit gate: changing only `CurriculumProfile` changes the live disposable runtime behavior without edits to these consumers.

**Wave 2A checkpoint:** complete in the factory layer. `draw_executable_release_rows(...)` accepts one v2 release plus provider implementations, verifies the admitted provider descriptor before execution, and draws only from the release's compiled plan/source bindings. `answer_heads_from_executable_release(...)` reconstructs the generic typed training head from the admitted semantic-token bindings without grade/release dispatch. The same consumer calls produce the full six-operator IDBOOLOPS domain or the AND/IFF domain solely by changing the release profile. The real pinned Boolean path produces byte-identical rows to direct plan generation and feeds `prepare_typed_batches()` successfully. Runtime assessment lifetimes remain on the legacy `Course` boundary and belong to Wave 2B.

**Wave 2B scope-identity checkpoint:** `assessment_scope_contract(...)` derives two independent identities from the exact selected v2 capability projections: a rubric digest from assessment projections only, and a source digest from source projections plus source-verified capability receipts. Scope is canonicalized by execution-plan order. It does not select a grade seal, inspect a grade letter or fold the holistic release SHA into the rubric/source identity. Consequently, an unrelated B profile revision leaves A-only identity byte-stable, A+B.AND+B.IFF is identical across full/reduced B when those selected capabilities are unchanged, and narrowing IDBOOLOPS changes both identities. The holistic release SHA remains separate for school-wide compatibility.

**Wave 2C parallel lifecycle checkpoint:** v2 cohort custody and lifetime primitives now accept an explicit capability scope rather than deriving one from a grade. Cohort generation uses the scope's source digest as `generator_version`, so an unrelated release/profile change cannot perturb an unchanged scope's measurement identity. Persisted v2 cohort metadata keeps rubric, source, factory-release, semantic-catalog and external source-manifest identities separate. Current pointers fail closed across holistic release changes even when their narrow scope remains semantically identical. Routine cohorts redraw at every boundary; promotion remains fixed only within one explicit attempt epoch; generalization is distinct from promotion and from every burned prior generalization instrument. Burning a generalization cohort does not permanently embargo all of its unexposed specimens. The legacy runtime assessment functions remain unchanged and their lifecycle regression suite still passes.

**Wave 2D scheduler-projection checkpoint:** generic scheduling now has a dedicated `ScheduleProgram` projection instead of reading semantic/source/release authority from `Course`. The v2 projection carries only grade/capability roster, declared item counts, staged pedagogy, exact cumulative assessment rubrics and program-complete status; its durable program digest is derived from the execution plan's roster + schedule + assessment projections plus completion state. Historical `Course` projection and append/revise/replace-grade semantics live under `compatibility/`. The same scheduler state machine advances from A into full B or the AND/IFF profile solely from the projected release data. The compatibility adapter remains temporary until the live trainer admission boundary is switched to v2.

**Wave 3A profile/ABI checkpoint:** the canonical current school curriculum now declares A, B and C semantics once. A-only and B-only runtime states are executable profiles over that same curriculum with later grades disabled as a canonical prefix; they are not separate semantic releases. B entry and B inventory revision use generic v2 profile adoption, so COMPOSITE and IDBOOLOPS progression comes from canonical teaching stages instead of named B successor releases. C admission is split correctly: the canonical C semantics already exist, while the student semantic catalog grows append-only from the historical 222-token ABI and a numeric execution profile activates the admitted C prefix. Same-curriculum profile changes classify neural geometry as `UNCHANGED`; same-curriculum append-only token growth classifies `APPEND_ONLY_EXPANSION`. The real pinned source-provider proof now exercises A-only -> reduced B -> C(0..3) through one canonical curriculum and source-binding set.

**Wave 3B numeric-scope checkpoint:** the 0..3 -> 0..4 -> 0..5 -> 0..6 staircase is now a sequence of same-curriculum v2 profile revisions, not a numeric release ladder. Numeric providers declare a typed `numbers` profile dimension; answer-family domains and source generation consume the same canonical prefix. `ScheduleProgram` identity includes the assessment projection so a changed numeric domain cannot silently reuse old rubric state. The bounded-final policy is persisted as profile execution metadata (`numeric_scope_final_maximum`), including one-time translation of historical staircase receipts in `compatibility/`. No live loop dispatches on the staircase release identity.

**Wave 3C compatibility-boundary checkpoint:** the former `factory/live_releases.py` implementation has been retired from the current factory namespace and moved intact to `compatibility/live_releases.py`. The old import path is a deprecation shim for historical tests/external callers only. Current trainer/CLI compatibility reads import the compatibility module explicitly; live B/C progression already uses profiles, plan diffs and v2 admission. This relocation removed the 129-finding release-switchboard cluster from the closure ledger without deleting historical decode/replay evidence.

**Wave 3D CLI checkpoint:** current status/preflight no longer reconstructs Course/release/provider state from historical release names. It reads the admitted v2 artifact and reports profile ID, canonical versus active grades, active capabilities, answer domains, semantic-catalog identity, projection digests and typed transition metadata. Historical release labels remain available only through `compatibility/cli_preflight.py` for pre-v2 saved receipts. Legacy COMPOSITE/ID flags are reported as canonical teaching-stage requests, not release enrollments.

### Wave 3: replace release-name transitions with release diffs

Move successor lineage and runtime compatibility into typed release metadata. Generic transition execution consumes `CurriculumDelta` plus a semantic-geometry transition contract. Same-grade revision, appended grade, profile revision, and graph growth are derived facts.

Exit gate: `next_successor_plan`, resume reconstruction, and preflight contain no concrete current release IDs.

### Wave 4: delete the parallel architecture

Remove canonical-use paths for:

- minimal-B release/provider identity;
- exact compact-B validator exception;
- trainer Boolean-composite/IDBOOLOPS/numeric-staircase transition branches;
- release-name graph-policy dispatch;
- grade-specific current event classes;
- grade/capability-specific generic preservation policy.

Move only immutable historical decoding that remains necessary under `compatibility/`.

Exit gate: current training cannot reach an old live provider path except through explicit historical decoding.

### Wave 5: prove Grade Z through the real runtime

A test-only canonical course, profile, and source provider must run through the same disposable top-level orchestration as the human shell, exercising admission, visit scheduling, routine assessment, recovery, promotion/generalization, championship, stagnation, telemetry, checkpoint/recovery, and stop handling.

No generic source file may change when the test grade is introduced.

Exit gate: SPEC-0001 §11.1 is satisfied in the actual runtime rather than in isolated generation/admission/scheduler unit tests.

### Wave 6: close the checker to zero

`python3 scripts/check_factory_closure.py` must print `FACTORY_CLOSURE_OK`.

The existing weaker architecture checker remains useful for its original checks, but the closure checker becomes the acceptance gate for split curriculum authority.

Only after this gate reaches zero should the factory be described as ready for additional semantic grades or materially more complex curriculum composition.
