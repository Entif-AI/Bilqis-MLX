# Bilqis Future-State Architecture Blueprint

## Semantic AST/ABI, Cognitive Compilation, Conditional Memory, and a Portable Neural Substrate

* **Working architectural whitepaper v0.1**  
* **Date:** 2026-10-19  
* **Status:** Internal architecture synthesis and proposed build blueprint  
* **Relationship to Prepaying Semantics:** Companion architecture paper intended to inform a proposed v0.6.0 revision of *Prepaying Semantics v0.5.1*. It is not itself a replacement for that paper, and it does not silently promote research hypotheses into published findings.

> The central move is to treat semantics as compilable infrastructure. Stable meaning is paid for once at source/admission/compile time, then reused as an address space, curriculum graph, memory key, evaluation contract, and model interface. The neural learner is left to spend scarce capacity on composition, generalization, uncertainty, and novelty rather than repeatedly reconstructing structure that the system already knows how to state exactly.

---

## Abstract

*Prepaying Semantics v0.5.1* asks whether a small learner can acquire reusable relational and compositional competence more efficiently when its developmental substrate exposes semantic structure directly rather than requiring that structure to be recovered repeatedly from irregular surface language. Bilqis turns that hypothesis into an executable developmental laboratory: a versioned semantic representation, append-only token identity, prerequisite-aware curriculum, deterministic generators and oracles, checkpointed teaching, competence gates, and later natural-language codecs.

The architecture has since matured beyond a representation experiment. The emerging system now suggests a more unified design: **semantic ahead-of-time compilation for cognition**.

In this design, source-grounded concepts are parsed into a canonical semantic graph, adjudicated for use, compiled into an admitted abstract syntax tree and semantic application binary interface, and then projected into several downstream products from one authority. Those products include the executable curriculum, source bindings, answer modalities, training/probe construction plans, assessment seals, model-vocabulary geometry, conditional-memory addresses, telemetry inventory, and release-transition contracts. The same identity that tells the teacher *what a concept means* can therefore tell the learner *which embedding row denotes it*, tell a memory system *where stable local knowledge belongs*, tell a probe *what distinction must be tested*, and tell a compiler *which downstream artifacts are invalidated when the meaning changes*.

The proposed future-state Bilqis is correspondingly not "a roughly 30-million-parameter Transformer" in isolation. It is a **small dense reasoning core** connected to a much larger structured semantic substrate and conditional memory. The dense core should remain small enough for local Apple Silicon development and edge-class experimentation, while its execution layer remains portable to rented NVIDIA accelerators through MLX's Metal and CUDA backends. An initial dense-core candidate is approximately eight Transformer layers at width 512, with an eight-head, 64-dimensional-head baseline, tied semantic embeddings sized for the expected 7,000-8,000-token ABI, extensible rotary positional encoding, and an intentionally ordinary attention/residual path as the reference implementation. Attention Residuals, grouped or compressed sequence attention, sparse/block memory, and conditional memory are designed as first-class extension boundaries rather than retrofits.

The memory layer is where total capacity can diverge sharply from active compute. Engram-style deterministic conditional memory suggests that static or locally reusable patterns need not be recreated through dense neural computation on every encounter. Bilqis has an unusually strong addressing primitive for such memory: the semantic ABI itself. A canonical semantic or frame signature can serve as an exact key, while a dense latent block stores learned local state. A hybrid block-coordinate representation can preserve globally sparse, locally dense structure and lower into backend-appropriate block-row or tiled layouts. TurboQuant-style vector quantization can later compress cold value stores or retrieval indices while semantic identity remains exact.

This creates two related but distinct compilation layers. **Semantic compilation** resolves meaning, provenance, typing, dependency, and stable identity. **Cognitive compilation** turns an admitted semantic frontier into executable teaching, assessment, memory, and model-interface plans. Neither compiler claims to dictate the neural model's internal algorithm. Instead, they shape the developmental environment and execution contracts around the model, so that the neural learner can be tested on whether it actually internalizes and composes the intended distinctions.

The build strategy is deliberately construction-oriented. Experiments are validation gates, not substitutes for architecture. We should build the semantic machine as a coherent system, then use small falsifiable probes at its boundaries to reject incorrect mechanisms before they propagate. The operative development rule is local: identify the smallest semantic slope that is currently reachable, keep only the next several steps in view, teach and test the current distinction, verify cognitive composition with mastered predecessors, preserve retention evidence, and advance. The final developmental road is expected to emerge only after its last steps have been laid.

## 1. Scope and Governing Intent

This paper synthesizes four streams that have previously appeared as partially separate work:

1. **The representation thesis of Prepaying Semantics.** Stable, explicit semantic structure may reduce some portion of the learning burden otherwise spent reconstructing task-relevant factors from variable surface forms.

2. **The AST/ABI and New Ithkuil work.** New Ithkuil provides a source-rich donor inventory of semantic distinctions; the current Bilqis crosswalk and bridge work supplies a path from source material into typed semantic identities without treating English labels or surface Ithkuil as the machine representation.

3. **The generative curriculum/factory architecture.** CurriculumDefinition, SourceBindingSet, CurriculumProfile, ExecutionPlan, typed answer modalities, FactoryRelease, projection digests, and source-verified admission are converging on one compiled executable authority rather than grade-specific runtime switchboards.

4. **The future neural substrate.** Bilqis must ultimately support thousands of semantic identities, deep cognitive composition, longer working contexts, conditional external memory, local Apple execution, rented accelerator training, and future distributed scaling without being redesigned around each hardware or model-fashion turn.

The architectural objective is not to maximize novelty density. It is to make the parts reinforce one another.

The semantic system should make the neural system easier to train and inspect. The neural system should provide the flexible generalization the semantic system cannot hand-author. Conditional memory should prevent either from wasting dense computation on stable local structure. The curriculum compiler should turn semantic authority into developmental experience without duplicating ontology in trainer code. The evaluation system should prove use, not just exposure. Distributed execution should accelerate the same school rather than silently changing the experiment.

This paper therefore distinguishes three levels of commitment:

- **Invariant:** a property the architecture should preserve unless a stronger source or user decision supersedes it.

- **Build default:** a concrete implementation we should construct now because it gives the system a useful spine while keeping alternatives replaceable.

- **Research extension:** a mechanism with enough fit to deserve a first-class interface or bounded implementation path, but not enough evidence to become the default before comparative proof.

This distinction is crucial. "Design for AttnRes" is not the same statement as "every Bilqis lineage must use AttnRes." "Design for distributed execution" is not the same as "pipeline an eight-layer model across eight H100s." "Use the ABI as a candidate deterministic memory address" is not the same as claiming that Engram has already demonstrated semantic-addressed memory.

## 2. The Architectural Thesis: Pay for Meaning Before Runtime

The phrase *prepaying semantics* becomes more precise when viewed through compiler architecture.

A conventional language-model pipeline frequently asks a neural network to perform several jobs at once:

- discover that two surface expressions refer to the same underlying relation;

- infer which participant fills which semantic role;

- recover scope and omitted defaults;

- infer which distinctions are relevant to the task;

- represent the resulting concept;

- retrieve relevant prior knowledge;

- compose the representation with other concepts;

- produce the requested answer.

Some of those jobs are irreducibly contextual. Others are not.

If an official grammar, formal algebra, deterministic world generator, or validated semantic catalog already tells us that an object is a specific operator with a specific type signature and prerequisite structure, then repeatedly asking a dense learner to infer that identity from a lossy surface rendering is optional work. We can perform the stable portion once, preserve provenance, and expose it through a canonical machine representation.

The architecture therefore moves stable work leftward:

~~~text

raw source / formal world

        |

        v

source parsing + provenance

        |

        v

semantic adjudication / admission

        |

        v

canonical semantic graph / AST

        |

        +------> stable semantic ABI

        |              |

        |              +------> model embedding identity

        |              +------> answer modality identity

        |              +------> deterministic memory key

        |              +------> telemetry / provenance identity

        |

        v

cognitive compiler

        |

        +------> CurriculumDefinition

        +------> SourceBindingSet

        +------> CurriculumProfile

        +------> ExecutionPlan

        +------> FactoryRelease

        +------> probe / assessment obligations

        +------> memory materialization plan

        |

        v

neural developmental runtime

        |

        +------> dense reasoning core

        +------> conditional semantic memory

        +------> teacher/champion advice

        +------> codec / natural-language surfaces

~~~

The dense model still learns. Nothing here makes Bilqis symbolic by decree. The design changes what the model is required to infer implicitly and which parts of the world arrive already typed, identified, source-grounded, and testable.

The useful compiler analogy is not "the Transformer executes an AST like a CPU executes bytecode." It is narrower and stronger: **the surrounding system should not rediscover executable facts that a compiler can derive deterministically from semantic authority.**

That principle already applies to the curriculum factory. A roster change should compile into affected schedules, source constraints, answer domains, assessment scope, retention/championship identity, and telemetry inventory. It should not require humans to synchronize trainer branches by hand. The same principle extends naturally to model vocabulary and memory.

## 3. Future-State Assumptions

Architecture should be designed around the intended Bilqis rather than today's larval artifact.

### 3.1 Semantic vocabulary

The planning envelope is approximately **7,000-8,000 admitted semantic ABI identities**, with explicit room beyond 8,000. These identities need not all be simple dictionary roots. The catalog may include formal operators, semantic roles, lexical senses, grammatical functions, answer values, relation types, and other machine-interpretable units that earn distinct stable identities.

Historical IDs are immutable. Growth is append-only unless an incompatible new model lineage is deliberately declared.

### 3.2 Developmental scope

The final curriculum order is not globally knowable in advance. The architecture instead maintains:

- a semantic graph describing meaning and relations;

- a prerequisite graph describing current developmental dependency hypotheses;

- mastery/evidence state describing what this student has demonstrated;

- a frontier of currently admissible next concepts;

- a local selection policy that prefers the smallest justified semantic slope.

Only the current step and a small look-ahead frontier need to be operationally settled.

### 3.3 Model scale

The working prior is a TinyStories-class **20-30M-ish dense reasoning core**, not a claim that total Bilqis capacity must remain under 30M forever. Conditional memory may increase total stored learned capacity substantially while keeping active dense computation small.

The baseline family should be fixed enough for meaningful lineage comparison, but its interfaces should not prevent later depth, context, memory, or distributed scaling.

### 3.4 Context

The current learned 96-position table is historical implementation detail, not a future-state limit. Semantic representations are information-dense, but serious composition still needs expandable working state. The new lineage should use an extensible positional scheme, with RoPE as the current default candidate, and should treat context length as a separately measured resource axis.

### 3.5 Hardware

Bilqis has at least three important execution environments:

- local Apple Silicon for daily development, small training, inference, probes, and edge-system work;

- rented single-node NVIDIA accelerators for faster training and architecture builds;

- future multi-device or multi-node execution when model depth, context, memory, or throughput warrants it.

No semantic or model authority should depend on one backend's storage format or custom kernel.

### 3.6 Custody

Actual neural optimizer execution remains an explicit human-run boundary unless separately authorized. The architecture must support dry compilation, source generation, probe construction, checkpoint inspection, telemetry, and disposable model experiments without implicitly taking custody of the live student.

## 4. The Semantic Machine: Authority Layers

A recurring source of Bilqis failures has been duplicated authority. The same principle that motivated executable curriculum closure applies to the larger architecture: one layer should own one kind of truth.

### 4.1 Source corpus

The source corpus contains evidence, not executable meaning.

For New Ithkuil this includes the official grammar, lexicon chapters, affix material, source manifests, and exact source locations. For formal mathematics it may include definitions and deterministic generators. For Rosetta-derived epistemic distinctions it includes the governing schema/ontology source and version.

A source record answers: *where did this proposed distinction come from?*

It does not answer: *is Bilqis allowed to use it yet?*

### 4.2 Source-grounded lexical/semantic graph

Parsing creates typed candidate objects such as:

~~~text

LexicalSense

  root_id

  stem_id

  source_form

  specification_pattern

  gloss / interpretation

  semantic_roles

  source_refs

  composition_constraints

  provenance_digest

~~~

This graph can be broad and exploratory. It may contain unresolved, conflicting, superseded, or research-only material.

A parsed source object is not automatically an ABI token.

### 4.3 Semantic admission

Admission is the boundary between "we have a source-grounded candidate" and "the executable Bilqis system may rely on this meaning."

An admitted object must have enough evidence for the role it will play:

- stable semantic identity;

- source/provenance binding;

- type and arity;

- prerequisite and composition constraints;

- answer/evaluation semantics where testable;

- legal and illegal witness families;

- compatibility classification relative to the current ABI.

Admission should fail locally. One unresolved lexical item should not invalidate unrelated semantics.

### 4.4 Canonical AST

The AST is the structured representation of an admitted semantic object or composition.

The New Ithkuil work strongly suggests that we preserve more than root/stem/gloss. Specification projections, roles, scope, composition, affected party, source/cause, process, manifestation, and related information can become typed structure rather than prose annotations.

A generic frame shape is useful:

~~~text

SemanticFrame

  frame_type: SemanticId

  slots:

    - role: SemanticId

      filler: SemanticNode | Literal | Variable

      cardinality: ...

      scope: ...

  modifiers: [...]

  provenance: [...]

  validation_state: ...

~~~

Examples of frames include Boolean operations, quantitative relations, cause/effect, kinship, disease, death, affective state, and eventually complex propositions composed from them.

The AST is not the curriculum. It is meaning.

### 4.5 Semantic ABI

The ABI is the stable numerical treaty between semantic meaning and executable systems.

For each admitted identity:

~~~text

AdmittedToken

  semantic_id

  token_id

  semantic_version

  type_signature

  source_digest

  introduction_release

  compatibility_class

~~~

The ABI provides:

- stable model embedding indices;

- stable answer-label bindings;

- stable memory keys or components of memory keys;

- stable serialization identities;

- stable telemetry/provenance references;

- append-only model vocabulary growth.

The ABI does **not** encode curriculum mastery. A token may be allocated and admitted before a student masters it. Likewise, a source candidate may exist without receiving a token.

### 4.6 Semantic geometry

Token identity and vector geometry are separate.

The ABI says that token 4,173 means one particular admitted semantic identity. It does not say that the learned vector at row 4,173 is semantically correct merely because it is nearby another embedding.

This distinction matters for semantic initialization. A new token may receive a deterministic initial vector derived from approved graph relations or a reproducible initialization function, but that is initialization evidence, not learned competence. The student must still demonstrate use.

## 5. Cognitive Compilation: Turning Meaning into an Executable School

The AST/ABI becomes valuable only when downstream behavior is derived from it instead of merely referencing it in documentation.

The target Bilqis factory architecture already supplies the right decomposition:

~~~text

CurriculumDefinition

        +

SourceBindingSet

        +

CurriculumProfile

        +

Provider Catalog

        +

Answer Modality Registry

        |

        v

compile_execution_plan(...)

        |

        v

ExecutionPlan

        |

        v

compile_factory_release(...)

        |

        v

FactoryRelease

        |

        v

generic school runtime

~~~

This should become the canonical cognitive compiler boundary.

### 5.1 CurriculumDefinition

`CurriculumDefinition` describes semantic and pedagogical meaning.

It owns:

- capability identities;

- prerequisite edges;

- composition edges;

- answer families;

- intended assessment counts;

- canonical teaching-stage relationships;

- semantic difficulty metadata when source-grounded;

- compatibility references into the semantic ABI.

It does not own concrete trainer branches, backend kernels, checkpoint paths, or human-run policy switches.

A capability should be understood as an executable learning objective over admitted semantics, not as a synonym for a token. One capability may involve several tokens and relations. One token may participate in many capabilities.

### 5.2 SourceBindingSet

`SourceBindingSet` binds a capability to the concrete source domain that can generate and adjudicate specimens.

It owns:

- provider identity;

- oracle identity;

- provider implementation digest;

- source/provenance manifest;

- configurable source dimensions;

- source attestation evidence;

- construction invariants.

The same provider should serve full and reduced profiles when the source domain is the same. A restricted Boolean experiment, for example, narrows the admitted operator domain of the normal Boolean provider rather than inventing a fake "minimal Boolean" source ontology.

This is a general rule: **execution profiles narrow admissible source behavior; they do not mint new meaning.**

### 5.3 CurriculumProfile

A `CurriculumProfile` describes which already-admitted portions of a canonical curriculum are active for a given execution.

A profile may:

- enable or disable optional capabilities while preserving prerequisite closure;

- narrow provider dimensions that the provider explicitly declares configurable;

- narrow answer-family values within the registered semantic domain;

- select authorized runtime resource profiles.

A profile may not:

- invent semantic identities;

- rewrite prerequisites;

- hand-author teaching stages;

- add unknown source-provider dimensions;

- invent answer labels;

- introduce a new model ABI by implication.

A profile is analogous to compiler configuration, not source code.

### 5.4 ExecutionPlan

The `ExecutionPlan` is the immutable compiled runtime projection.

For each active capability it should carry enough information that generic runtime code never needs to ask "is this Grade B?" or "is this the Boolean-identification release?"

Conceptually:

~~~text

CapabilityExecution

  capability_id

  grade_id

  stage

  prerequisites

  composed_of

  source_anchor

  provider_id

  provider_implementation_digest

  oracle_id

  provider_parameters

  variation_axes

  teaching_option_ids

  answer_families

  exam_item_count

  projection_digests

~~~

The plan should compile scoped digests for at least:

- roster;

- schedule;

- source;

- assessment blueprint;

- answer schema;

- coverage;

- teaching.

These digests are not decorative hashes. They are invalidation boundaries.

If a B-only source constraint changes, unrelated A evidence should not become stale. If an answer domain changes, answer-head and assessment state should invalidate without pretending the source provider changed. If a prerequisite edge changes, schedule-dependent state should invalidate even if semantic-token geometry remains identical.

This is the missing connection between declarative architecture and recoverability.

### 5.5 FactoryRelease

`FactoryRelease` is the executable admission artifact.

The release should bind:

- canonical semantic provenance;

- semantic ABI catalog digest;

- CurriculumDefinition digest;

- SourceBindingSet digest;

- CurriculumProfile identity;

- ExecutionPlan;

- provider descriptors and implementation hashes;

- answer-modality descriptors;

- source-verified admission specimens;

- cumulative verified assessment seals;

- release predecessor and structural delta;

- model-ABI geometry classification;

- runtime compatibility requirements.

A metadata-only assessment blueprint is not a rubric seal. The release compiler must actually generate and verify admitted source material before minting source-verified assessment authority.

This gives the system an explicit compile-time/runtime boundary:

**before FactoryRelease:** proposal, parsing, compilation, candidate generation, validation;

**after FactoryRelease:** generic execution over admitted artifacts.

### 5.6 Answer modalities

Answer behavior should be selected by answer semantics, not by grade identity.

An answer-modality registry owns mappings such as:

~~~text

binary:

  FALSE -> semantic ABI identity X

  TRUE  -> semantic ABI identity Y

boolean_operator:

  AND     -> semantic ABI identity A

  OR      -> semantic ABI identity B

  ...

  IFF     -> semantic ABI identity F

numeric_active:

  admitted numeric semantic identities -> token rows

~~~

The model can retain a tied semantic-embedding readout while each modality constrains the active comparison domain.

A future modality should require a new typed adapter because it is a genuinely new output interpretation. A new grade using an existing modality should require no new generic head code.

This matters enormously at 7,000-8,000 ABI identities. We cannot afford to grow a forest of hidden per-grade heads, each encoding its own local ontology.

## 6. The Developmental Topology: Build the Staircase from the Current Foot

The semantic graph and the teaching sequence are different objects.

A semantic graph is allowed to be richly cyclic:

~~~text

CANCER is-a DISEASE

DISEASE affects ORGANISM

CANCER can-cause DEATH

DEATH can-trigger BEREAVEMENT

BEREAVEMENT can-trigger GRIEF

MOTHER participates-in PARENT_RELATION

~~~

A prerequisite graph should be much more disciplined. It asks a different question:

> What must this particular learner already be able to discriminate and compose before a new capability can be taught and tested without smuggling in unmastered machinery?

That graph should evolve from evidence.

### 6.1 No final yellow-brick road in advance

We should not attempt to specify the complete developmental sequence from arithmetic through physics, chemistry, biology, social relation, grief, and narrative before training reaches those regions.

The right operating rule is local.

At any moment the compiler needs:

1. the mastered semantic closure;

2. the current active developmental obligations;

3. the frontier of source-admitted candidates whose hard prerequisites are satisfied;

4. a small look-ahead set of likely next candidates;

5. evidence about which candidate represents the shallowest useful slope.

The final road emerges from successive locally justified steps.

### 6.2 Candidate slope

For a candidate capability `c`, define a developmental cost vector rather than one arbitrary difficulty number:

~~~text

slope(c) = (

  count(new primitive identities),

  count(new relation kinds),

  new AST depth,

  new arity,

  new answer-modality burden,

  new source-domain burden,

  new working-memory span,

  prerequisite uncertainty,

  expected transfer value

)

~~~

The scheduler need not scalarize this vector permanently. It can use lexicographic or constrained selection such as:

- reject candidates with unresolved prerequisites;

- prefer zero-new-modality candidates;

- prefer smaller new AST depth;

- prefer candidates that reuse already-mastered operators;

- among comparably shallow candidates, prefer those that unlock several useful downstream nodes.

This is a concrete way to operationalize "the slightest-slope stair" without pretending difficulty is one universal number.

### 6.3 Teaching a primitive correctly

A capability is not taught merely because its token appeared in a batch.

For each new distinction, the teacher should compile several specimen families from the same admitted semantic rules:

- direct positive cases;

- direct negative cases;

- legal contrasts;

- illegal or contradictory constructions;

- boundary cases;

- decomposed constituents;

- reconstructed composition;

- inverse or metamorphic variants where the semantics permits;

- held-out permutations of mastered prerequisites.

The simplest certified witness comes first.

Progressive complexity should then be expressed in AST terms rather than English intuition: number of constituents, depth, scope nesting, distractors, source variation, and composition count.

### 6.4 Probe before composition, then probe composition itself

Every stair has at least two evidence obligations.

**Use proof:** can Bilqis apply the new semantic distinction on fresh source-valid cases?

**Composition proof:** can Bilqis combine it with already-mastered semantics without collapsing either component?

For example, learning `CAUSE` is not complete merely because the model distinguishes cause from non-cause in isolated examples. It should later discriminate cause inside a composed frame while preserving unrelated roles.

Likewise, learning a lexical frame for death is not enough if "cause of death" cannot be composed with a disease frame and a person relation.

This distinction should appear explicitly in the curriculum compiler:

~~~text

Capability

  direct_mastery_obligations

  compositional_obligations

  prerequisite_retention_obligations

  transfer_obligations

~~~

### 6.5 Retention and controlled forgetting

Development cannot require every earlier capability to remain perfect at every optimizer step. New learning may temporarily perturb earlier representations.

The school should therefore distinguish:

- immediate active-capability acquisition;

- protected prerequisite degradation;

- delayed fresh-source retention;

- whole-prefix requalification;

- terminal cumulative qualification.

Temporary forgetting is evidence for the teacher, not automatic failure.

The runtime already has a stronger conceptual basis for this than ordinary pretraining loops: one intact student checkpoint, its own optimizer state, explicit capability evidence, earlier champions, and cumulative revalidation.

That machinery should remain generic and compiler-driven.

### 6.6 Empirical prerequisite correction

The initial prerequisite graph is a source-informed hypothesis.

Candidate edge `A -> B` should become empirically stronger if controlled mastery of A reliably reduces acquisition cost for B or improves B's generalization/retention. It should weaken if matched controls show no benefit.

The architecture therefore supports versioned prerequisite evidence:

~~~text

PrerequisiteEvidence

  predecessor

  dependent

  source_basis

  transfer_trials

  acquisition_cost_delta

  retention_delta

  confidence

  disposition

~~~

This does not mean the curriculum should continuously rewrite itself from noisy short-run measurements. It means the dependency graph can improve through explicit, governed revisions instead of turning one human-authored ordering into dogma.

## 7. From Ithkuil Lexicon to Semantic Frame Graph

The New Ithkuil chapter split reveals why lexical ingestion should not stop at rows of roots and glosses.

Across the lexicon, specification patterns repeatedly rotate a root through semantic roles such as identity/essence, process/manifestation, affected party/result, source/agent, cause, and related functions. Other roots provide reusable relations for change, comparison, measurement, consequence, origin, component, function, and state.

Those patterns are the micro-level connective tissue between macro domains.

### 7.1 Preserve role structure at ingestion

A deterministic lexical importer should emit typed source objects containing at least:

- root identity;

- stem identity;

- source sense;

- specification projection;

- inherited specification pattern;

- semantic participants/roles;

- affix relations;

- composition constraints;

- explicit source/result/cause/component relationships;

- source location;

- provenance digest.

Only then should admission decide which senses are ready for the executable semantic graph.

### 7.2 Macro domain is not source chapter order

The lexicon's chapter sequence is a taxonomy, not a curriculum.

A plausible developmental macro progression may eventually include:

~~~text

number and abstract operation

  -> measurement and comparison

  -> geometry / spacetime

  -> physical quantities and dynamics

  -> matter / particles / atoms

  -> chemistry and composition

  -> biological organization

  -> physiology

  -> pathology / etiology

  -> life / death

  -> perception and cognition

  -> social relation / kinship

  -> affect

  -> complex narrative propositions

~~~

But that is a topological map, not a fixed lesson list.

The more fundamental curriculum is orthogonal to it:

~~~text

IDENTITY

TYPE

PART-OF

COMPOSED-OF

HAS-PROPERTY

MEASURED-AS

COMPARES-WITH

CHANGES-INTO

SOURCE-OF

CAUSES

RESULTS-IN

AGENT-OF

PATIENT-OF

RELATED-TO

EXPERIENCES

TRIGGERED-BY

EVIDENCE-FOR

~~~

Those relation families are the semantic bridges that let one domain reuse machinery learned in another.

### 7.3 A concrete compositional signpost

Consider the proposition:

> John is sad because his mother died of cancer.

A useful semantic decomposition might contain:

~~~text

PARENT_RELATION

  child = JOHN

  parent = MOTHER

NEOPLASTIC_DISEASE

  affected = MOTHER

DEATH_EVENT

  affected = MOTHER

  cause = NEOPLASTIC_DISEASE

BEREAVEMENT

  experiencer = JOHN

  lost_relation = MOTHER

AFFECTIVE_STATE

  experiencer = JOHN

  affect = SADNESS/GRIEF

  trigger = DEATH_EVENT

~~~

The point is not to encode this English sentence by hand.

The point is that the source lexicon already contains candidate structures for parent relations, neoplastic disease, disease/sufferer relations, death and cause/manner, bereavement, and sadness/grief with affective triggers. If our importer preserves those roles, a later cognitive compiler can discover that this seemingly "human" proposition is a composition of many earlier reusable frames.

That is the road from `1 + 2 = 3` to emotionally and socially meaningful propositions: not one miraculous jump, but a long chain of tiny reusable relation types.

## 8. Model ABI Growth and New Lineages

The curriculum compiler and model ABI must meet at one explicit boundary.

### 8.1 Three semantic-geometry cases

Every release transition should classify model semantic geometry as:

1. **UNCHANGED**  

   Same semantic token catalog. Curriculum/profile/source changes do not require model-shape mutation.

2. **APPEND_ONLY_EXPANSION**  

   Existing token IDs and meanings remain unchanged; new admitted IDs are appended.

3. **INCOMPATIBLE**  

   Existing IDs were reindexed, meanings changed in place, or the model contract is otherwise not safely extensible.

Only the second case invokes vocabulary expansion.

### 8.2 Append-only expansion

A model-vocabulary expansion operation should be explicit, content-addressed, and receipted.

It should:

- preserve every existing embedding row exactly;

- append new rows in catalog order;

- initialize new rows under a declared reproducible strategy;

- expand matching optimizer state in a specified way;

- preserve tied readout semantics if weight tying is active;

- bind the resulting checkpoint to the new ABI digest;

- verify old-token logits/behavior within the intended numerical tolerance before human-run continuation.

No curriculum code should directly resize tensors.

### 8.3 Initialization is not mastery

For semantic-aligned initialization, a compiler may use graph-local information such as admitted relations, compositional neighbors, or deterministic projections to seed new rows.

That can reduce a cold-start geometry problem, but it must remain labeled correctly:

**the compiler proposes an initial representation; the student proves competence.**

The strongest probe is not "does the new vector sit near an expected neighbor?" It is whether the student can use the newly admitted identity in source-valid direct and compositional tasks after authorized learning.

### 8.4 Major geometry changes create new student lineages

Changing hidden width, depth, head geometry, normalization, or another structural dimension is a new model lineage.

The existing student and champions remain historical evidence and potential teachers. They are not forcibly reshaped into an incompatible body.

This is especially relevant for the proposed move from the historical 6-layer, width-384, 24-head student to a future TinyStories-class architecture.

A lineage manifest should bind:

~~~text

ModelManifest

  architecture_id

  layers

  hidden_width

  attention_geometry

  ffn_geometry

  position_scheme

  semantic_abi_digest

  vocabulary_capacity

  numeric_precision

  memory_modules

  residual_mode

  backend_contract_version

  initialization_profile

  parent_teacher_refs

~~~

The model lineage and semantic release lineage are related but different. A semantic ABI can advance without changing dense architecture. A new dense architecture can begin against an already-frozen ABI prefix.

## 9. The Dense Reasoning Core

The future-state Bilqis neural architecture should be small enough to remain inspectable and locally runnable, but large enough that we are not deliberately starving the representational substrate we intend to build.

The core should therefore be sized around the expected semantic ABI and composition burden, not the current 227-token historical vocabulary.

### 9.1 Baseline geometry

The current reference candidate is:

~~~text

layers:              8

hidden width:        512

attention heads:     8 baseline

head dimension:      64

FFN expansion:       4x baseline

semantic vocabulary: 7,000-8,000 initial planning envelope

position scheme:     extensible rotary

readout:             tied semantic embedding baseline

precision:           implementation-dependent, explicitly recorded

~~~

This is a build default, not a forever constitution.

The motivation is architectural:

- eight layers provide substantially more compositional depth than the historical six-layer student while remaining tiny by modern standards;

- width 512 leaves enough channel capacity for thousands of semantic identities and their interactions;

- eight 64-dimensional heads are a clean hardware-oriented baseline for fused attention kernels and provide wider per-head subspaces than the current 16-dimensional heads;

- tied semantic embeddings keep input identity and answer-token geometry coupled unless evidence justifies separate output weights;

- rotary position encoding avoids freezing model geometry to a short learned position table.

At an 8,000-token ABI, this remains approximately a thirty-million-parameter dense model class, depending on exact context/normalization/FFN details.

The dense parameter budget should not be confused with total cognitive capacity once conditional memory is enabled.

### 9.2 TinyStories as a scale prior, not a blueprint

TinyStories is relevant because it demonstrated that changing the developmental environment can move coherent behavior into unusually small models. It should calibrate our expectations about what can be learned in a constrained developmental world.

It should not determine every Bilqis hyperparameter.

Our environment differs materially:

- the vocabulary is semantic rather than ordinary subword English;

- the curriculum is competence-gated rather than static next-token exposure;

- answer domains can be typed and narrow;

- source generators provide controlled recombination;

- later memory can externalize stable patterns;

- natural language arrives as a codec rather than the first representational world.

Accordingly, TinyStories gives us a useful scale neighborhood and evidence that depth/width tradeoffs matter, not a license to cargo-cult a released config.

### 9.3 The active-compute budget

Once conditional memory enters the design, we should report several budgets separately:

~~~text

dense_core_parameters

active_parameters_per_token

total_conditional_memory_parameters

hot_memory_working_set_bytes

cold_memory_bytes

KV_bytes_per_token

embedding_table_bytes

FLOPs_per_token

lookup_bytes_per_token

interconnect_bytes_per_optimizer_step

~~~

This is more informative than one total parameter count.

A system with a 30M dense core plus 300M sparsely addressed memory entries is not computationally equivalent to a 330M dense model.

That distinction is central to the future architecture.

## 10. Sequence and Depth Routing

The model has two independent communication problems:

1. which positions in the current sequence should exchange information;

2. which representations from earlier computational depth should remain available to later layers.

Standard Transformers solve the first with self-attention and the second with residual accumulation. Several of the mechanisms under consideration can now be located cleanly rather than treated as competing acronyms.

### 10.1 Reference path: ordinary fused attention

The reference implementation should use the framework's fast scaled-dot-product attention rather than hand-building QK-transpose, masking, softmax, and value projection unless parity demands otherwise.

MLX currently exposes fused scaled-dot-product attention with MHA, GQA, and MQA support, causal masks, and FP32 softmax accumulation. The portable reference path should therefore prefer that primitive.

The same principle applies to compilation. `mx.compile` can fuse work and shrink graph overhead; we should make the standard path fast before using custom kernels to rescue avoidable framework-level inefficiency.

### 10.2 Grouped-query attention as a cheap branch

GQA is architecturally attractive because it can reduce KV-state bandwidth without radically changing the attention algorithm.

It should be implemented behind the attention geometry contract early enough that MHA and GQA are configuration variants rather than separate model classes.

At Bilqis scale, GQA is not required to fit the model. Its value would be:

- smaller inference cache;

- cheaper longer-context decoding;

- a cleaner bridge toward CCGQA;

- a controlled test of whether reducing independent K/V heads harms semantic composition.

A GQA branch therefore earns an interface earlier than it earns default status.

### 10.3 Attention Residuals

Attention Residuals addresses depth communication.

A standard PreNorm residual stack adds layer contributions into one accumulating stream. AttnRes instead allows later layers to select among previous depth states with learned, input-dependent attention.

For Bilqis, the scientific attraction is not generic benchmark improvement. It is the match to our central task:

**a later semantic composition may need to recover a specific earlier representation rather than rely on the latest mixed residual state.**

That makes AttnRes unusually relevant to deep compositional probes.

The architecture should expose a residual-mode interface:

~~~text

ResidualMode

  STANDARD

  FULL_ATTNRES

  BLOCK_ATTNRES

~~~

For an eight-layer baseline, full AttnRes is practical enough to serve as the cleanest upper-bound comparison.

Block AttnRes is the scale-compatible form. Its block structure is especially interesting because it creates explicit depth groups that can later align with distributed pipeline stages and depth-local caches.

### 10.4 Compressed Convolutional Attention

CCA addresses the sequence axis.

It projects queries, keys, and values into a compressed shared latent space and performs attention there. CCGQA combines that compression with head sharing.

This is potentially valuable when context becomes long enough that ordinary attention FLOPs and KV state materially dominate training or inference.

The design should not wait until that day to make CCA impossible to integrate. The attention module should expose:

- Q/K/V projection contract;

- number of query and KV heads;

- latent attention width;

- cache representation;

- backend kernel identity;

- compatibility with semantic/probe instrumentation.

CCA remains a near-term research branch rather than the default because compression can change representational rank and information flow. Its published fused-kernel speedups are also hardware-specific evidence, principally from H100-class execution, not proof of local Apple speedup.

### 10.5 AttnRes plus CCA

These mechanisms are complementary in principle:

~~~text

CCA / GQA / MHA:

  communication across sequence

AttnRes / Block AttnRes:

  communication across depth

~~~

The combined architecture is therefore coherent.

But the combined model must be measured for a specific failure: **double bottlenecking**.

If sequence state is heavily compressed and depth routing repeatedly recirculates already-smoothed representations, we may produce a model that is cheap, stable, and semantically bland.

The combined branch must expose at least:

- effective hidden rank;

- attention entropy;

- sequence reachability;

- depth-routing entropy;

- residual RMS by layer;

- gradient norm by layer;

- representation similarity across depth;

- direct and compositional probe deltas.

No combined mechanism should become default merely because each component helped in isolation.

## 11. Conditional Semantic Memory

Conditional memory is where the architecture can move beyond the simplistic choice between "tiny model" and "large model."

The central proposition is:

> stable local structure should be retrievable when known, rather than reconstructed through dense computation every time it appears.

Engram makes this idea concrete in language models through deterministic conditional lookup. Bilqis has a different and potentially cleaner key space because semantic identity is already explicit.

### 11.1 Semantic Engram

A Bilqis-specific research extension can use canonical semantic signatures as deterministic memory addresses.

Examples:

~~~text

token identity:

  SEMANTIC_ID(cogal.operator.AND)

frame identity:

  FRAME(death; affected=MOTHER; cause=CANCER)

composition signature:

  COMPOSE(CAUSE, DEATH, NEOPLASTIC_DISEASE)

typed local pattern:

  BOOL_ASSOCIATION(AND, IFF, truth-shape=...)

~~~

The published Engram system uses N-gram-style addressing. Semantic Engram is therefore an explicit Bilqis extrapolation, not a claim about what the original paper proved.

The design advantage is substantial: if keys are deterministic, memory selection does not initially require a learned discrete router.

### 11.2 Exact identity versus semantic neighborhood

Two retrieval modes should remain distinct.

**Exact memory** uses a canonical semantic key or content address. It answers:

> Have we already stored state for this exact semantic object or canonical local pattern?

**Neighborhood retrieval** uses a learned projection or vector similarity. It answers:

> Which known semantic objects are probably nearby this new observation or partial frame?

The first can be authoritative for identity when the key is source-derived and exact.

The second is probabilistic candidate generation.

Do not allow a vector neighbor to silently become semantic identity.

### 11.3 Memory value structure

A memory entry should be capable of carrying more than one flat embedding vector.

A useful design is a dense block:

~~~text

MemoryBlock

  semantic_key

  value_matrix

  learned_usage_state

  provenance_refs

  semantic_version

  write_policy

  confidence / validation metadata

  last_compaction_version

~~~

The dense sub-block can preserve multiple learned channels or role-specific state around one sparse semantic address.

This is where the user's hybrid COO intuition becomes directly useful.

### 11.4 Sparse global structure, dense local blocks

The canonical authoring representation can be **block coordinate format**:

~~~text

BlockCOOEntry

  coordinate:

    semantic_row

    semantic_column_or_relation

    optional_context_partition

  dense_tile

~~~

One coordinate entry points to an entire dense tile.

This reduces index overhead when meaningful state occurs in locally dense blocks while the global semantic space remains sparse.

The canonical memory representation should emphasize semantic coordinates and coalescing rules, not one backend's sparse matrix format.

A compiler can lower block-COO into:

- BSR-like block rows on a backend with efficient block sparse kernels;

- CSR/COO plus packed tile payloads;

- custom Metal tiled buffers;

- CUDA block-sparse kernels;

- host-resident cold storage plus a contiguous hot cache.

The ontology does not care how the GPU wants its indices sorted.

### 11.5 Coalescing and write discipline

Sparse writes can become a correctness hazard if the same semantic coordinate appears multiple times.

The memory layer therefore needs deterministic coalescing:

1. canonicalize semantic coordinates;

2. sort entries;

3. merge duplicate coordinates under an explicit rule;

4. materialize a versioned packed layout;

5. bind the packed layout to the source semantic catalog digest;

6. expose a deterministic reverse map from packed offset to semantic coordinate.

No opaque compaction pass may destroy semantic traceability.

### 11.6 Hot, warm, and cold tiers

A future memory system should treat storage as hierarchical.

~~~text

HOT

  active exact semantic blocks

  accelerator memory

  high precision

  lowest latency

WARM

  recent / likely blocks

  unified or host memory

  optionally compressed

COLD

  large static or rarely accessed store

  host / disk / remote object storage

  quantized value representation

~~~

Deterministic semantic keys make prefetch unusually powerful. A compiler often knows which identities and composition families a lesson or probe will require before the forward pass begins.

This allows **curriculum-informed memory prefetch**.

That is a genuine synergy between the semantic compiler and neural systems layer: the compiler can stage likely memory blocks without knowing the model's answer.

### 11.7 Memory should not replace cognition

Conditional memory can become pathological if the model learns to perform table lookup instead of composition.

Every memory-enabled capability should therefore have at least three probe modes:

- memory available;

- relevant memory withheld;

- misleading or near-neighbor memory supplied as a negative control.

The goal is to distinguish:

- exact reuse of legitimately stored local knowledge;

- composition over stored pieces;

- brittle memorization of full answers.

A memory system earns its place when it makes stable knowledge cheap **without destroying novel recombination**.

## 12. TurboQuant and Quantized Memory

TurboQuant is particularly relevant to the memory architecture because it treats online high-dimensional vector compression while preserving geometric structure.

The appropriate first use is not "quantize everything."

It is to separate semantic identity from vector payload.

### 12.1 Exact keys, compressed values

Semantic IDs, frame signatures, catalog hashes, and content addresses remain exact.

Quantization applies to:

- cold memory value blocks;

- retrieval vectors;

- future KV caches;

- transmitted memory blocks between machines;

- large read-mostly semantic tables.

This preserves the integrity of the address space.

### 12.2 Master values and serving values

For trainable memory:

~~~text

high_precision_master

        |

        +--> hot working copy

        |

        +--> quantized cold copy

        |

        +--> retrieval index

~~~

The optimizer owns the master representation.

Quantized forms are derived artifacts unless and until a specific quantization-aware-training contract is validated.

This prevents silent optimizer interaction with lossy storage.

### 12.3 Inner-product preservation

TurboQuant's residual Quantized Johnson-Lindenstrauss construction is interesting when retrieval depends on approximate inner products.

That suggests two possible modes:

- exact semantic-key lookup followed by quantized value load;

- approximate candidate retrieval over quantized vectors followed by exact semantic validation.

The second mode should never skip semantic validation.

### 12.4 KV caches

When Bilqis gains longer autoregressive or interactive contexts, KV-cache compression can matter even for a small dense core.

GQA, CCA/CCGQA, and TurboQuant attack different aspects:

- GQA reduces number of KV heads;

- CCA reduces latent attention/cache dimension;

- TurboQuant reduces bits per stored vector.

These mechanisms can compose, but they also multiply approximation.

The systems rule is therefore sequential pressure relief:

1. measure the cache bottleneck;

2. apply structural reduction such as GQA or CCA;

3. remeasure;

4. add quantization only if memory/bandwidth remains material;

5. test semantic and long-context retrieval probes after every compression layer.

## 13. Learned Routing and Gradient Estimators

The architecture should make room for stochastic or discrete routing without introducing exotic gradients before the routing problem exists.

### 13.1 Ordinary backpropagation remains the default

The following need no special estimator by themselves:

- dense MHA/GQA;

- CCA with continuous projections;

- AttnRes with soft attention;

- deterministic semantic memory lookup with gradients to accessed values;

- dense feed-forward layers;

- exact compiler-selected memory prefetch.

These are differentiable or externally deterministic.

### 13.2 Pathwise derivatives

Pathwise or reparameterization estimators become useful when a model samples a continuous stochastic latent variable that can be expressed as a differentiable transformation of parameter-independent noise.

This is the classic VAE-style setting.

If future Bilqis uses stochastic continuous latent memory, uncertainty variables, or sampled latent plans, pathwise gradients may lower estimator variance relative to score-function methods.

That is a trigger condition, not a baseline feature.

### 13.3 Learned discrete routing

A harder case appears if the network learns a discrete action such as:

- choose one memory bank;

- choose one expert;

- choose a sparse block;

- choose one hard semantic candidate;

- choose one program branch.

A hard categorical sample interrupts ordinary backpropagation.

At that point we should compare:

- continuous soft routing;

- straight-through estimators;

- Gumbel-Softmax relaxation;

- unbiased/control-variate methods such as REBAR;

- task-specific estimators for sparse expert routing.

The comparison should consider bias, gradient variance, convergence, throughput, and final compositional competence.

### 13.4 Prefer deterministic semantics when the key is already known

A crucial restraint follows from the AST/ABI architecture.

If the semantic compiler already knows the exact memory address needed, **do not train a router to rediscover it**.

Learned routing is valuable for ambiguity, novelty, or non-symbolically specified choices.

Deterministic semantic identity is already a solved address.

This is another example of prepaying semantics: do not spend gradient budget on decisions already available from compiled meaning.

## 14. Draft-and-Prune as a Semantic Construction Service

Draft-and-Prune is best placed outside the dense learner.

Its architectural role is candidate generation and semantic validation.

### 14.1 Candidate generation

At a difficult semantic frontier, the system may need to propose:

- a lexical mapping;

- a frame decomposition;

- a new capability definition;

- a prerequisite edge;

- a probe family;

- a natural-language codec mapping;

- a complex formalization of an observed example.

A strong model can draft several alternatives.

### 14.2 Pruning

Candidates can then be rejected using increasingly expensive gates:

1. syntax/schema validity;

2. type checking;

3. ABI identity resolution;

4. source/provenance validity;

5. deterministic oracle constraints;

6. contradiction tests;

7. inverse/metamorphic checks;

8. cross-model or human review where exact machinery is insufficient.

The surviving candidates remain proposals until the relevant admission authority accepts them.

### 14.3 Frontier curriculum use

D&P-like machinery can help find the next smallest semantic stair.

Suppose the semantic graph exposes five prerequisite-satisfied candidates. A candidate generator can propose how each would be taught using already-mastered material. The compiler can reject plans that:

- introduce hidden unmastered semantics;

- require a new answer modality unnecessarily;

- contain unsupported source assumptions;

- skip simpler certified witnesses;

- fail to produce compositional probes.

The remaining plans become evidence-backed frontier choices.

This is a better use of a powerful LLM than allowing it to invent gold answers inside the live school.

### 14.4 Natural-language codecs

Later, D&P can also generate candidate mappings from English or another natural language into the canonical semantic AST.

Multiple parses can be drafted; deterministic and semantic validators prune impossible ones; unresolved ambiguity remains explicit.

That allows natural language to be a codec over the semantic machine instead of silently becoming its ontology.

## 15. Portable Execution: Apple Locality, CUDA Rental, One Model Contract

Hardware should be an execution concern, not a semantic concern.

The architecture should preserve one model/operator contract that can be lowered to the strongest available implementation on each backend.

### 15.1 MLX as the portability layer

Current MLX supports:

- Apple Silicon execution;

- JIT-compiled custom Metal kernels;

- a CUDA backend;

- JIT CUDA kernels;

- graph compilation;

- fast fused attention and RoPE;

- distributed communication backends including JACCL, ring, MPI, and NCCL.

That makes MLX a stronger strategic fit than treating the current Mac execution path as a local prototype that must later be rewritten in another framework.

The operating rule should be:

~~~text

portable model/operator contract

        |

        +--> built-in MLX primitive

        |

        +--> compiled MLX graph

        |

        +--> custom Metal implementation

        |

        +--> custom CUDA implementation

~~~

Custom kernels must have reference implementations and parity tests.

### 15.2 Why not make MPSGraph the canonical architecture?

Metal Performance Shaders and MPSGraph are valuable backend technology. Apple provides tuned GPU primitives, compiled compute graphs, and sparse COO/CSR/CSC representations.

But those APIs are Apple-specific.

Bilqis should use them when they are the best implementation of an operator, not let them define the operator's semantics.

For example, the canonical semantic memory can remain block-COO while an Apple lowering packs it into MPSGraph-compatible COO/CSR structures or a custom Metal tiled buffer.

This keeps hardware format below the semantic/compiler boundary.

### 15.3 Data parallelism

For a roughly 30M dense core, data parallelism is the first obvious rented-hardware strategy.

The model fits comfortably on one modern accelerator. Multiple devices can therefore increase throughput by processing deterministic disjoint specimen subsets and reducing gradients.

Bilqis needs a stronger contract than generic DDP because the school is part of the experiment.

One logical optimizer step should have:

~~~text

ControlPlaneStep

  curriculum_release

  active_capability

  teacher_strategy

  global_example_manifest

  deterministic_partition_seed

  world_size

  rank_partitions

  gradient_reduction_rule

  optimizer_step_before

  optimizer_step_after

  checkpoint_receipt

~~~

Changing world size must not silently change the meaning of one school visit.

Global batch, source distribution, capability mixture, and visit count remain logical training parameters.

### 15.4 Replica parallelism for build velocity

When rented hardware exceeds what one small model needs, the most valuable parallelism may be **scientific parallelism**:

- baseline lineage;

- AttnRes lineage;

- GQA lineage;

- memory-enabled lineage;

- alternate seed;

- alternate semantic initialization;

- diagnostic replication.

Eight GPUs running eight controlled builds can produce more architecture information than chopping one small model into eight inefficient pipeline stages.

The infrastructure should therefore distinguish:

~~~text

within-run parallelism

between-run parallelism

~~~

Both can use the same artifact store and curriculum compiler.

### 15.5 Tensor parallelism

Tensor parallelism becomes attractive when:

- hidden/FFN width grows substantially;

- a memory or output projection becomes too large for one device;

- larger future synthesis tiers reuse the same architecture;

- a specific kernel scales efficiently across device collectives.

The current 512-width core does not justify aggressive tensor sharding by itself.

But the module boundaries should avoid assumptions that make TP impossible later.

### 15.6 Pipeline parallelism

Pipeline parallelism is relevant to the architecture even if it is not immediately efficient for eight layers.

Future triggers include:

- substantially greater depth;

- long-context activation pressure;

- depth-routed caches;

- memory modules attached to specific stages;

- cross-host topologies where fewer large transfers beat frequent all-reduces;

- a larger Sheba-class descendant reusing the same contracts.

Block AttnRes creates a particularly interesting alignment opportunity: depth blocks can become pipeline stages, with explicit cached cross-stage representations rather than arbitrary residual dependencies.

That does not prove the combination is optimal. It makes the architecture composable.

### 15.7 Sequence/context parallelism

If context becomes the dominant activation cost, distributing sequence state may become more useful than splitting a tiny parameter set.

This is another reason context length should be a first-class resource metric rather than one baked constant.

Sequence parallelism should be introduced only after the attention/memory design is settled enough that we know what state actually must cross rank boundaries.

### 15.8 Memory sharding

Conditional semantic memory can scale independently of the dense core.

A deterministic semantic address creates simple sharding options:

- contiguous semantic-ID ranges;

- consistent hashing of canonical keys;

- domain partitioning where source locality justifies it;

- hot replicated cache plus cold sharded store.

Because addresses are deterministic, prefetch can often happen before model execution.

The sharding manifest must remain semantically reversible:

~~~text

MemoryShardManifest

  semantic_catalog_digest

  shard_function

  shard_count

  key_range_or_hash_contract

  value_codec

  quantization_profile

  replica_policy

  version

~~~

The model should never need to infer where a canonical key lives.

## 16. The Developmental Control Plane

The distributed data plane should not duplicate the school's authority.

One control plane owns:

- admitted FactoryRelease;

- current capability/frontier decision;

- teacher policy;

- source generation manifest;

- checkpoint lineage;

- evaluation/championship state;

- semantic-memory release;

- distributed execution manifest.

Workers execute bounded pieces of that plan.

This mirrors the broader factory doctrine: declarations compile into execution; execution does not reconstruct declarations.

### 16.1 One school, many workers

For a distributed optimizer step:

1. control plane selects the exact lesson plan;

2. source generation deterministically materializes or partitions examples;

3. each rank receives its shard;

4. each rank computes gradients;

5. gradients reduce under one declared rule;

6. one logical optimizer state advances;

7. checkpoint/probe events record global step identity;

8. later assessment uses source-valid independent cohorts.

A rank is not a miniature autonomous teacher.

### 16.2 Reproducibility

Every run should record enough distributed state to explain why two runs differ:

- MLX version;

- backend;

- device family;

- world size;

- parallelism mode;

- numeric precision;

- kernel identities;

- compilation flags;

- global batch;

- microbatch;

- accumulation;

- seed hierarchy;

- deterministic/nondeterministic operation declarations;

- memory layout and quantization profile.

Hardware acceleration is part of the implementation evidence, not part of semantic identity.

### 16.3 Backend parity

Portable execution requires three levels of parity.

**Semantic parity:** the same token IDs, source specimens, and gold semantics.

**Numerical parity:** outputs/gradients agree within declared tolerance for a reference fixture.

**Learning parity:** a controlled disposable training slice produces statistically compatible acquisition behavior.

We should not require bitwise identity across Metal and CUDA if different fused kernels make that unrealistic.

We should require any divergence material to curriculum conclusions to become observable.

## 17. Interaction Discipline: Preventing Clever Mechanisms from Eating Each Other

The future architecture intentionally contains several powerful compression/routing mechanisms:

- semantic factorization;

- tied embedding geometry;

- GQA or CCA;

- AttnRes;

- block sparsity;

- conditional memory;

- quantized memory;

- possible learned routing.

Each can improve efficiency.

Each can also remove information.

The system therefore needs an **information-bottleneck budget**.

### 17.1 Do not stack unknown bottlenecks

A new lineage should never simultaneously introduce AttnRes, CCA, memory lookup, sparse weights, and quantized KV while claiming that a changed benchmark score validates the architecture.

The build order should establish a strong ordinary reference implementation, then add one mechanism at a time behind stable interfaces.

"Less experiments, more building" means build the interfaces and system now; use experiments as acceptance gates for turning optional modules on by default.

### 17.2 Double normalization

Normalization is especially dangerous because it often hides inside independently motivated modules.

The architecture should record every normalization boundary:

~~~text

NormSite

  before_attention

  after_attention

  residual_router_key_norm

  residual_router_value_norm

  before_ffn

  memory_query_norm

  memory_value_norm

  output_norm

~~~

If AttnRes computes normalized keys for routing, that does not imply the routed value should be renormalized again.

If CCA normalizes compressed Q/K space, that does not authorize an additional global hidden-state normalization.

A model manifest should make these sites explicit enough to audit.

### 17.3 Over-regularization

Bilqis already faces unusually strong structural pressure from:

- explicit semantic factorization;

- constrained curricula;

- deterministic source worlds;

- tied embeddings;

- potentially structured initialization;

- memory retrieval;

- compressed attention.

Regularization that is benign on web-scale noisy language can become harmful in a tiny, highly structured school.

Dropout, weight decay, label smoothing, stochastic depth, memory dropout, routing entropy penalties, and sparsity penalties should therefore be treated as a combined regularization budget.

The failure mode is not merely underfitting.

It is making the student too smooth to preserve sharply distinct semantic identities.

### 17.4 Sparsification interaction

Sparse systems can create isolated subspaces.

If block-sparse memory or sparse attention is introduced, verify:

- graph connectivity;

- effective communication diameter;

- coverage of bridge nodes;

- cross-domain composition;

- gradient reachability;

- whether some semantic family can only communicate through one fragile route.

Possible structural antidotes include:

- periodic dense bridge layers;

- guaranteed global heads;

- reserved cross-block tiles;

- learned but connectivity-constrained routing.

The correct choice should follow measured topology.

### 17.5 Memory shortcut failure

A conditional memory can make probes easier while weakening the dense core.

Probe suites should therefore distinguish:

- retrieved-fact success;

- recombination of retrieved constituents;

- novel transformation;

- memory-free retention of mastered primitives;

- behavior when a plausible but wrong near-neighbor is retrieved.

This gives us a way to measure whether memory is a hippocampus or a cheat sheet.

## 18. Evidence Architecture: Proving Use Rather Than Decorating a Dashboard

A semantic machine is only useful if its evidence system can distinguish:

- source validity;

- exposure;

- in-lesson optimization;

- direct capability use;

- compositional use;

- retention;

- transfer;

- championship superiority;

- cumulative student qualification.

These must not collapse into one score.

### 18.1 Probe types

Each capability should compile probe obligations by evidence role.

A useful minimum taxonomy is:

**DIRECT**

: fresh cases that isolate the target distinction.

**CONTRASTIVE**

: minimal pairs that differ only in the target semantic factor.

**COMPOSITIONAL**

: target semantic combined with mastered constituents.

**DECOMPOSITION**

: recover the constituents/roles of a composed semantic object.

**COUNTEREXAMPLE**

: plausible-looking but invalid/contradictory construction.

**METAMORPHIC**

: transform source structure under a law while preserving predictable semantics.

**RETENTION**

: delayed fresh-source recheck after unrelated learning.

**TRANSFER**

: use the same semantic relation under an unfamiliar source renderer, domain, or codec.

A capability can require only the families that its semantics support.

### 18.2 Probes are compiled from the same authority, scored independently

Teaching and testing should share semantic rules but not leak generated answers into inference.

A provider can generate both lesson and exam specimens from the same admitted source law.

An oracle independently computes or verifies the gold.

The release records source/provider/oracle implementation identity and coverage receipts.

This is stronger than maintaining separate hand-authored "training" and "test" ontologies that drift apart.

### 18.3 Composition is first-class evidence

A student can memorize isolated answer patterns while failing to use the semantic relation compositionally.

The evidence model should therefore track direct mastery and composition mastery separately.

For example:

~~~text

CapabilityEvidence

  direct_score

  contrastive_score

  compositional_score

  decomposition_score

  retention_score

  transfer_score

  represented_source_families

  checkpoint_sha

  optimizer_step

  release_id

~~~

Promotion can then require the relevant subset rather than one undifferentiated accuracy.

### 18.4 Championship evidence

Championship machinery should remain separate from simple high-water observations.

A capability title belongs to the capability's semantic jurisdiction.

A challenger and incumbent must be compared on the same current source-valid evidence when the title moves.

Historical provenance such as the grade in which a checkpoint's optimizer updates occurred is not the same as title jurisdiction.

This generalizes elegantly under the compiler:

- capability identity defines title jurisdiction;

- assessment/source projection defines comparability;

- checkpoint origin is provenance;

- current champion pointer defines teacher/custody role.

No grade-specific branch is needed.

### 18.5 Golden ancestors and soups

Earlier strong checkpoints remain valuable even after the current student moves beyond them.

They can serve as:

- frozen teachers;

- regression references;

- distillation advisers;

- lineage branch points;

- source of comparative diagnostics.

A "soup" or aggregate adviser should remain a teacher artifact, not silently become the student.

The student remains one intact model plus its matching optimizer state.

### 18.6 Telemetry follows compiled inventory

The dashboard should consume the current admitted release inventory.

It should not infer "what B means" by replaying historical event names or hardcoded grade expectations.

Events should be generic in class and typed in payload:

~~~text

SCHOOL_CURRICULUM_ADMITTED

SCHOOL_VISIT_COMMITTED

SCHOOL_EXAM_COMMITTED

SCHOOL_CHAMPIONSHIP_UPDATED

SCHOOL_MEMORY_RELEASED

SCHOOL_MODEL_LINEAGE_CREATED

~~~

The same architecture should make unfamiliar future grades visible without a dashboard code change.

## 19. Build Blueprint: Construct the Machine, Then Let Evidence Tune It

The architecture is mature enough that the next phase should not be a sequence of disconnected research spikes.

We should build the common substrate and treat experiments as acceptance checks at the boundaries where several plausible implementations remain.

### 19.1 Parallel build lanes

Five work lanes can proceed in parallel while remaining governed by shared contracts.

~~~text

LANE A: Semantic Source + AST/ABI

  deterministic Ithkuil ingestion

  semantic frame graph

  admission

  append-only catalog

LANE B: Cognitive Compiler

  CurriculumDefinition

  SourceBindingSet

  CurriculumProfile

  ExecutionPlan

  FactoryRelease

  probe/coverage compiler

LANE C: Bilqis vNext Core

  8 x 512 baseline

  8-head MHA reference

  RoPE

  fused SDPA

  compiled MLX

  tied semantic readout

  model lineage manifest

LANE D: Conditional Memory + Storage

  exact semantic key

  block-COO canonical representation

  hot/warm/cold memory API

  backend lowering

  quantized derived-store interface

LANE E: Execution + Evidence

  Metal/CUDA parity

  distributed data-plane contract

  telemetry

  checkpoint lineage

  probe/championship evidence

~~~

The lanes integrate at explicit gates rather than waiting for one giant final merge.

### 19.2 Integration gate A: one semantic object end to end

Before parsing the full lexicon, prove one source-grounded semantic family through the complete chain:

~~~text

source excerpt

  -> parsed LexicalSense

  -> admitted SemanticFrame

  -> append-only AdmittedToken(s)

  -> CurriculumDefinition capability

  -> SourceBindingSet

  -> ExecutionPlan

  -> FactoryRelease

  -> generated lesson

  -> generated direct probe

  -> generated compositional probe

  -> model token/head binding

  -> telemetry identity

~~~

This is not a toy implementation path.

It is the vertical slice that proves there is only one semantic authority.

Once that slice works, corpus ingestion can scale horizontally.

### 19.3 Integration gate B: future vocabulary without trainer surgery

Compile a disposable catalog in the expected future size class.

It does not need 8,000 perfected Ithkuil meanings on day one. It can include source-grounded admitted fixtures plus reserved/disposable synthetic semantic identities for load testing.

The goal is to prove that:

- token IDs remain append-only;

- model construction accepts the catalog size;

- tied semantic readout works;

- answer modalities bind by semantic identity;

- ExecutionPlan and FactoryRelease remain generic;

- telemetry can render thousands of identities without hardcoded grade assumptions;

- checkpoint manifests carry semantic-catalog identity.

This distinguishes **architecture capacity proof** from **semantic admission**.

Synthetic load identities used for capacity testing never become real ABI semantics.

### 19.4 Integration gate C: Bilqis vNext model lineage

Create a new dense model lineage rather than resizing the current student.

The first vNext build should intentionally be boring:

~~~text

8 layers

512 hidden

8 attention heads

64 dimensions/head

4x feed-forward

RoPE

MHA

standard residual

fast SDPA

compiled MLX where stable

tied semantic embeddings

no Engram

no CCA

no learned sparse router

~~~

Why boring?

Because this model is the reference organism against which every later mechanism is judged.

It should support the final-scale vocabulary contract from the beginning even if its first authorized curriculum exposes only an early ABI prefix.

### 19.5 Integration gate D: exact semantic memory

Implement the memory interface with **exact deterministic semantic keys first**.

A first useful memory service can support:

~~~text

put(key, dense_block, metadata)

get_exact(key)

prefetch(keys)

invalidate(semantic_version_or_projection)

materialize_hot_set(keys)

serialize_layout()

verify_reverse_map()

~~~

This is already valuable infrastructure.

It does not need approximate nearest-neighbor retrieval, TurboQuant, or a learned router to prove the architecture.

Once exact semantic memory works, those become extensions instead of preconditions.

### 19.6 Integration gate E: distributed school invariance

Run the same disposable training slice on:

- one local Metal device;

- one CUDA device;

- multiple CUDA ranks with data parallelism.

The acceptance question is not "which is fastest?"

It is:

> Did distribution accelerate the same declared school, or did it change the learning intervention?

Check:

- same FactoryRelease;

- same global specimen manifest;

- same logical batch;

- same optimizer-step count;

- same global curriculum events;

- expected numerical tolerance;

- comparable probe trajectory.

Only then optimize throughput aggressively.

## 20. What We Build Now, Next, and Later

The architecture should distinguish urgency from possibility.

### 20.1 Build now

**Semantic type system**

- `LexicalSense`

- `SemanticFrame`

- `FrameRole`

- `SemanticRelation`

- `AdmittedToken`

- semantic-version/provenance records.

**Deterministic source ingestion**

- parse the split New Ithkuil lexicon/affix sources;

- preserve specification patterns and role structure;

- emit source-complete candidate graph;

- adjudicate separately from parsing.

**Append-only ABI compiler**

- stable semantic ID -> token ID;

- version/digest;

- compatibility classification;

- deterministic catalog export;

- model-expansion input.

**Factory closure**

- make ExecutionPlan/FactoryRelease the sole canonical runtime authority;

- finish source-provider constraints and answer-modality registry;

- remove release/grade switchboard authority from generic runtime;

- finish Grade-Z disposable closure proof.

**Bilqis vNext reference core**

- model manifest;

- 8 x 512 x 8 baseline;

- RoPE;

- fused SDPA;

- MLX compile;

- semantic vocabulary parameterized from catalog;

- backend-parity fixtures.

**Memory contract**

- exact semantic address;

- block-COO canonical object;

- hot-store implementation;

- deterministic coalescing;

- reverse semantic map.

**Evidence contracts**

- direct/composition/retention/transfer probe roles;

- compiler-generated coverage obligations;

- generic telemetry inventory.

### 20.2 Build next

Once those contracts exist:

**AttnRes implementation**

- standard/full/block residual modes behind one API;

- routing telemetry.

**GQA implementation**

- model-manifest geometry support;

- KV metrics.

**Distributed data parallel**

- NCCL rental profile;

- deterministic global-school partitioning;

- checkpoint/world-size receipts.

**Semantic Engram v1**

- exact ABI/frame signatures as keys;

- trainable dense memory values;

- curriculum-aware prefetch;

- memory ablation probes.

**Natural-language codec compiler**

- surface -> candidate semantic AST;

- D&P-style candidate generation;

- deterministic/source semantic pruning;

- unresolved ambiguity as explicit state.

### 20.3 Build after measured pressure appears

**CCA / CCGQA**

- when sequence attention FLOPs/KV dominate.

**TurboQuant**

- when cold/vector/KV memory is large enough for bandwidth/storage to matter.

**Approximate semantic retrieval**

- when exact keys cannot resolve novel observations.

**Learned discrete routing**

- when deterministic semantic selection is insufficient.

**Pathwise/Gumbel/REBAR estimator work**

- only after a concrete stochastic/discrete router exists.

**Tensor, pipeline, or sequence parallelism**

- activated by measured one-run resource pressure, not merely available hardware.

This is not postponing architecture.

It is using one architecture to avoid implementing expensive branches before their trigger exists.

## 21. Concrete Interfaces

A blueprint becomes useful when it constrains code.

The following interfaces should be considered architectural targets, with names adjustable to the repository's final module organization.

### 21.1 Semantic compiler

~~~python

class SemanticCompiler:

    def parse_sources(self, source_manifest) -> CandidateSemanticGraph: ...

    def validate_candidate(self, candidate, source_context) -> ValidationReport: ...

    def admit(self, candidate, authority) -> AdmittedSemanticObject: ...

    def compile_catalog(self, admitted_objects, previous_catalog=None) -> SemanticCatalog: ...

~~~

No method trains a model.

### 21.2 Cognitive compiler

~~~python

class CognitiveCompiler:

    def compile_curriculum(

        self,

        semantic_catalog,

        capability_declarations,

    ) -> CurriculumDefinition: ...

    def compile_execution(

        self,

        curriculum,

        source_bindings,

        profile,

        providers,

        answer_modalities,

    ) -> ExecutionPlan: ...

    def release(

        self,

        execution_plan,

        source_verification,

        assessment_receipts,

        lineage,

    ) -> FactoryRelease: ...

~~~

### 21.3 Model factory

~~~python

class ModelFactory:

    def build(self, manifest: ModelManifest, catalog: SemanticCatalog) -> Student: ...

    def expand_vocab(

        self,

        student,

        optimizer,

        old_catalog,

        new_catalog,

        expansion_profile,

    ) -> ExpandedStudentReceipt: ...

~~~

Model construction depends on catalog geometry.

It does not depend on grade names.

### 21.4 Memory service

~~~python

class SemanticMemory:

    def get_exact(self, key: SemanticMemoryKey) -> MemoryBlock | None: ...

    def put(self, key, block, metadata) -> MemoryReceipt: ...

    def prefetch(self, keys) -> PrefetchReceipt: ...

    def materialize(self, keys, device) -> HotSet: ...

    def compact(self, profile) -> CompactionReceipt: ...

~~~

A future approximate retriever can produce candidate keys, but exact lookup remains separately available.

### 21.5 Training backend

~~~python

class TrainingBackend:

    def compile_model(self, student, optimizer, backend_profile): ...

    def train_step(self, logical_batch, distributed_manifest) -> StepReceipt: ...

    def evaluate(self, probe_manifest) -> ProbeReceipt: ...

~~~

The backend consumes already-compiled school artifacts.

It does not select curriculum.

## 22. Failure Modes and Architectural Defenses

A novel architecture earns credibility by making its likely self-deceptions explicit.

### 22.1 Source graph inflation

**Failure:** parsed lexical material is mistaken for admitted semantics.

**Defense:** candidate graph and executable catalog are different types; admission is explicit and receipted.

### 22.2 ABI bloat

**Failure:** every lexical nuance gets a token, making the ABI an unprincipled dump.

**Defense:** stable identity requires an executable reason: distinct type/role/answer/memory behavior or justified lexicalized semantics. Composable meaning should remain composable where source semantics supports it.

### 22.3 Curriculum circularity

**Failure:** prerequisite graph contains hidden cycles or depends on untaught concepts.

**Defense:** compile prerequisite closure; fail admission for unresolved hard dependency cycles; allow semantic graph cycles without conflating them with developmental prerequisites.

### 22.4 Probe leakage

**Failure:** generated teaching and assessment share source code that accidentally leaks gold or memorized constructions.

**Defense:** shared semantic law, independent oracle path, source manifests, seed/content hashes, fresh construction families, and metamorphic/counterexample checks.

### 22.5 Factory theater

**Failure:** declarative files exist, but trainer/CLI/dashboard still encode release ontology.

**Defense:** Grade-Z system proof, closure checker, and runtime prohibition on concrete grade/release/capability control dispatch.

### 22.6 Embedding ontology

**Failure:** vector similarity becomes semantic truth.

**Defense:** semantic identity comes from ABI/source authority; embeddings are learned/projection state.

### 22.7 Memory as answer cache

**Failure:** conditional memory stores complete exercise answers and fakes reasoning.

**Defense:** store reusable local semantic state, trace writes, probe memory-withheld composition, test novel recombination.

### 22.8 Sparse islands

**Failure:** block sparsity or sparse attention isolates semantic regions.

**Defense:** connectivity metrics, cross-domain composition probes, guaranteed bridge paths where needed.

### 22.9 Compression pile-up

**Failure:** GQA + CCA + quantization + sparsity remove too much signal.

**Defense:** mechanism-by-mechanism activation and information-bottleneck telemetry.

### 22.10 Distributed experiment drift

**Failure:** more GPUs silently alter global batch, curriculum cadence, sampling, or optimizer semantics.

**Defense:** one logical school manifest with deterministic rank partitioning and global-step receipts.

### 22.11 Backend-specific ontology

**Failure:** Metal/CUDA sparse layouts leak into semantic representation.

**Defense:** backend-neutral semantic/block IR; lowering occurs below architecture authority.

### 22.12 Hidden publication leakage

**Failure:** protected trainer/governance mechanisms from private authority are copied into a public paper.

**Defense:** publication projection is a separate compile step. Public *Prepaying Semantics* receives only material whose authority/disclosure status permits publication. Protected IPR-0220 operational details remain protected even when they influenced internal architecture.

## 23. Architecture Acceptance Tests

The architecture should not be called closed until the following are demonstrably true.

### 23.1 Semantic addition

Add one new source-grounded semantic object.

Without editing generic runtime:

- source parser produces typed candidate;

- admission produces semantic identity;

- ABI appends token;

- curriculum compiler sees it;

- dependent capability/probe artifacts regenerate;

- model factory can build/expand for it;

- telemetry can name it.

### 23.2 Semantic edit

Change the meaning/version of a disposable semantic object.

The system must:

- refuse in-place mutation of historical token meaning;

- create a new compatible/incompatible semantic version as appropriate;

- invalidate affected compiler projections;

- preserve unrelated evidence;

- regenerate dependent tests;

- require new instruction where meaning changed.

### 23.3 Unknown grade

Introduce disposable Grade Z entirely in test declarations.

No production trainer, scheduler, dashboard, stagnation, championship, CLI, answer-head, or release-successor source file may require a Z branch.

### 23.4 Future-size vocabulary

Build and run a model against an 8K-class disposable catalog.

Verify:

- embedding/readout shapes;

- catalog digest binding;

- checkpoint round trip;

- answer modality subset scoring;

- no current-227-token assumptions.

### 23.5 Backend parity

Run the same fixture through Metal and CUDA paths.

Verify semantic identity and declared numerical tolerances.

### 23.6 Distributed invariance

Run a controlled training slice at world size 1 and world size N while preserving one global logical batch/step definition.

Verify school events and source manifests remain equivalent.

### 23.7 Exact memory

Store and retrieve ABI-keyed dense blocks.

Verify:

- deterministic address;

- coalescing;

- version invalidation;

- reverse semantic map;

- no confusion between exact key and vector-neighbor candidate.

### 23.8 Composition

For each newly admitted developmental step, pass both:

- direct use on fresh source-valid cases;

- composition with mastered prerequisites.

A 100% isolated classifier score is insufficient.

## 24. The Build Sequence

A practical build sequence should be aggressive without being reckless.

### Wave 1: Freeze contracts, not features

- finalize semantic source/candidate/admission types;

- finalize append-only ABI schema;

- finalize ModelManifest;

- finalize SemanticMemory key/block contract;

- finish ExecutionPlan/FactoryRelease authority closure.

Output: the interfaces through which every later feature must travel.

### Wave 2: Vertical semantic compiler

- deterministic importer for a small source slice;

- preserve Specification/frame roles;

- admit several semantic identities;

- generate ABI rows;

- compile one capability and probe suite end to end.

Output: meaning becomes executable without hand-written runtime ontology.

### Wave 3: Bilqis vNext dense core

- implement 8 x 512 x 8 reference lineage;

- RoPE;

- fused SDPA;

- tied semantic embedding/readout;

- MLX compile;

- model manifest and checkpoint receipts;

- build against future-scale catalog geometry.

Output: the body intended to carry the future curriculum.

### Wave 4: Factory/runtime closure

- cut generic consumers to FactoryRelease/ExecutionPlan;

- complete real provider constraint support;

- typed answer modality closure;

- projection-bound scheduler/assessment/championship/retention/telemetry;

- Grade-Z end-to-end.

Output: changing semantic/curriculum declarations changes downstream execution without whack-a-mole edits.

### Wave 5: Exact conditional memory

- block-COO canonical memory;

- hot store;

- deterministic ABI/frame keys;

- prefetch from execution plan;

- memory-aware but memory-optional model interface;

- memory-ablation probes.

Output: first real separation between dense compute and total learned memory capacity.

### Wave 6: Portable/rented acceleration

- CUDA backend parity;

- NCCL data-parallel school;

- replica orchestration;

- performance/resource telemetry;

- exact artifact portability.

Output: local development and rented training share one architecture.

### Wave 7: Depth and sequence efficiency

- full AttnRes;

- Block AttnRes;

- GQA;

- later CCA/CCGQA under context pressure;

- interaction telemetry.

Output: optimize communication only after the reference organism works.

### Wave 8: Memory scale and compression

- warm/cold tiers;

- TurboQuant-derived vector stores;

- approximate candidate retrieval where needed;

- memory sharding;

- bandwidth/prefetch optimization.

Output: large addressable semantic memory without proportionally large active compute.

### Wave 9: Codec and autonomous semantic expansion

- natural-language codec compiler;

- D&P candidate generation/pruning;

- ambiguity preservation;

- source-backed admission workflow;

- adaptive local-frontier curriculum selection.

Output: an architecture capable of growing its semantic road without abandoning source authority.

## 25. Relationship to Prepaying Semantics v0.5.1

The existing paper already contains many of this blueprint's conceptual seeds:

- semantic AST before surface language;

- stable semantic identity;

- grammar as curriculum generator;

- prerequisite topology as an empirical object;

- checkpointed developmental training;

- content-addressed cognition and external memory;

- routed assistance;

- natural language as a later codec;

- edge/federated downstream architecture.

A v0.6.0-scale revision should not simply paste this blueprint into the paper.

It should update the paper's **systems model**.

The major conceptual expansion is:

> Prepaying semantics is not only a representation intervention for a small learner. It can be implemented as a compilation architecture in which stable semantic work becomes reusable infrastructure across model identity, curriculum generation, conditional memory, evaluation, and distributed execution.

That expansion should remain falsifiable.

The paper must still distinguish:

- demonstrated engineering facts;

- implemented but unmeasured architecture;

- proposed architecture;

- external-paper findings;

- Bilqis-specific extrapolations.

### 25.1 Suggested paper changes

Astra should consider at least the following v0.6.0 changes:

1. Expand Section 4 from "semantic AST and developmental traversal" into an explicit **semantic compiler + ABI** model.

2. Expand Section 4.5 so the teacher program compiles from one admitted semantic authority into ExecutionPlan/FactoryRelease rather than merely generating exercises.

3. Update the experimental-program description to reflect the **local-frontier staircase** rather than a globally fixed developmental road.

4. Add future-state vocabulary planning around roughly 7-8K semantic identities without turning that estimate into a scientific claim.

5. Replace obsolete tiny reference-architecture numbers where the paper discusses the intended future Bilqis body, while preserving historical experiment descriptions as historical.

6. Expand Section 8.3 into a concrete **conditional semantic memory** architecture, clearly labeling Semantic Engram as a Bilqis extrapolation from published Engram.

7. Add block-coordinate sparse memory, hot/warm/cold tiers, and exact-key versus approximate-neighbor distinction.

8. Add a compact neural-systems subsection covering the future dense core, AttnRes depth routing, sequence-attention options, and interaction discipline.

9. Expand implementation architecture to cover MLX portability across Metal and CUDA, rental-hardware data parallelism, and scale-triggered tensor/pipeline/sequence parallelism.

10. Add the idea that distributed execution must preserve one logical developmental school.

11. Add TurboQuant as a candidate compression layer for cold vector/KV/memory values, not semantic identity.

12. Add D&P as a candidate semantic/codec/curriculum proposal-and-validation mechanism, not a gold oracle.

13. Add a clear build sequence that emphasizes architectural construction before optional optimization research.

14. Preserve the publication boundary: private IPR details inform internal architecture but are not copied into the public paper.

### 25.2 Novelty claim discipline

The most defensible novelty target is not "we invented ASTs, memory, sparse tensors, or curriculum learning."

It is the **composition**:

- an explicit source-grounded semantic ABI;

- a compiler that turns meaning into developmental/runtime artifacts;

- a small neural core trained against that compiled substrate;

- conditional memory addressed by canonical semantic cues;

- evidence that direct and compositional competence gates progression;

- hardware-portable execution where distribution does not change semantic treatment.

Each ingredient has precedents.

The research question is whether their disciplined integration changes the economics and reliability of acquiring reusable cognition.

## 26. Conclusion: A Semantic Computer Around a Small Learner

Bilqis began as a question about whether explicit semantic structure might make a small model learn more efficiently.

The emerging architecture suggests a stronger engineering thesis.

We can build a **semantic computer around the learner**.

The source graph tells us what meanings are available and where they came from.

The admission layer tells us which meanings the executable system may trust.

The AST tells us how admitted meanings compose.

The ABI gives those meanings stable machine addresses.

The cognitive compiler turns those meanings into lessons, probes, source constraints, answer domains, runtime projections, and release artifacts.

The dense neural core learns flexible transformations and generalization over that developmental substrate.

Conditional memory stores stable local patterns without forcing the dense core to reconstruct them every time.

Block-sparse storage makes a huge semantic space physically tractable while retaining dense local representations.

AttnRes can make depth history selectable.

GQA and CCA can reduce sequence-state cost when context pressure warrants them.

TurboQuant can compress value storage without quantizing semantic identity.

D&P can generate and prune candidate formalizations without becoming the oracle.

MLX lets the same high-level implementation develop on Apple Silicon and scale onto rented CUDA hardware.

The championship, retention, and probe systems answer the question that matters after every architectural flourish:

> Can the student actually use the new semantic machinery, compose it with what came before, and retain it on fresh evidence?

That is the governing loop.

~~~text

SOURCE

  -> ADMIT

  -> COMPILE

  -> BUILD

  -> TEACH

  -> PROBE

  -> COMPOSE

  -> RETAIN

  -> ADVANCE

~~~

We do not need to know the last stair before stepping onto the next one.

We do need every stair to attach to the same building.

# References and Source Notes

## Public / external technical sources

1. Ronen Eldan and Yuanzhi Li, **TinyStories: How Small Can Language Models Be and Still Speak Coherent English?** arXiv:2305.07759. https://arxiv.org/abs/2305.07759

2. Kimi Team et al., **Attention Residuals.** arXiv:2603.15031. https://arxiv.org/abs/2603.15031

3. Tomas Figliolia et al., **Compressed Convolutional Attention: Efficient Attention in a Compressed Latent Space.** arXiv:2510.04476. https://arxiv.org/abs/2510.04476

4. Xin Cheng et al., **Conditional Memory via Scalable Lookup: A New Axis of Sparsity for Large Language Models.** arXiv:2601.07372. https://arxiv.org/abs/2601.07372

5. Amir Zandieh et al., **TurboQuant: Online Vector Quantization with Near-optimal Distortion Rate.** arXiv:2504.19874. https://arxiv.org/abs/2504.19874

6. Zhiyu Ni et al., **Draft-and-Prune: Improving the Reliability of Auto-formalization for Logical Reasoning.** arXiv:2603.17233. https://arxiv.org/abs/2603.17233

7. Diederik P. Kingma and Max Welling, **Auto-Encoding Variational Bayes.** arXiv:1312.6114. https://arxiv.org/abs/1312.6114

8. Eric Jang, Shixiang Gu, and Ben Poole, **Categorical Reparameterization with Gumbel-Softmax.** arXiv:1611.01144. https://arxiv.org/abs/1611.01144

9. George Tucker et al., **REBAR: Low-variance, unbiased gradient estimates for discrete latent variable models.** arXiv:1703.07370. https://arxiv.org/abs/1703.07370

10. Apple MLX documentation, **Compilation.** https://ml-explore.github.io/mlx/build/html/usage/compile.html

11. Apple MLX documentation, **Distributed Communication.** https://ml-explore.github.io/mlx/build/html/usage/distributed.html

12. Apple MLX documentation, **Fast primitives / scaled dot-product attention / RoPE.** https://ml-explore.github.io/mlx/build/html/python/fast.html

13. Apple MLX documentation, **Build and Install / CUDA backend.** https://ml-explore.github.io/mlx/build/html/install.html

14. Apple Developer Documentation, **Metal Performance Shaders.** https://developer.apple.com/documentation/MetalPerformanceShaders

15. Apple Developer Documentation, **Metal Performance Shaders Graph.** https://developer.apple.com/documentation/metalperformanceshadersgraph

16. Apple Developer Documentation, **MPSGraphSparseStorageType.** https://developer.apple.com/documentation/metalperformanceshadersgraph/mpsgraphsparsestoragetype

17. PyTorch documentation, **torch.sparse.mm** gradient/storage-format support. https://docs.pytorch.org/docs/stable/generated/torch.sparse.mm.html

## Internal architecture/source lineage

The blueprint is also grounded in the current internal/project lineage, including:

- *Prepaying Semantics v0.5.1*;

- Bilqis roadmap and roadmap supplement;

- Bilqis New Ithkuil Semantic Bridge work;

- Bilqis Curriculum Registry;

- Bilqis MLX generative curriculum/factory specification;

- Executable Curriculum Closure architecture;

- Curriculum Authority Convergence record;

- Champions, Soups, Golden Ancestors & Grade Advancement governing specification;

- current factory/runtime evidence and the Grade-Z closure target;

- current New Ithkuil split lexicon source corpus and crosswalk/semantic bridge data.

Protected operational authority such as IPR-0220 is an internal governance source. Its private training/remediation mechanisms must not be copied into a public *Prepaying Semantics* revision merely because this architecture synthesis consulted them.

---
