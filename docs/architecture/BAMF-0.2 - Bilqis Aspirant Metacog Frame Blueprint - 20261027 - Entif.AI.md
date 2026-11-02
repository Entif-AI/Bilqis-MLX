# Bilqis Aspirant Metacog Frame: BAMF-0.2

## *Architecture and implementation recommendations*

27 October 2026  
Implementation specification   
Entif-AI/Bilqis-MLX

Design mandate: build one ambitious, internally coherent, locally operated student lineage. Start from admitted semantics and real Factory teaching. Exploit exact symbolic structure to reduce work the neural core must learn. No architecture tournament.

Document status: PROPOSED ARCHITECTURE / OWNER REVIEW. It does not claim this vNext model has been implemented, approved for production, benchmarked, or started training. The 26 October source baseline and the 27 October successor requirements are separately preserved. The deterministic resource calculations and selected configurations above are engineering estimates and decisions for implementation.

# 

# Table of Contents

[**EXECUTIVE DECISION	8**](#executive-decision)

[IMPLEMENTATION DECISION \| 27 OCTOBER 2026	10](#implementation-decision-|-27-october-2026)

[**1\. WHAT WE KNOW IS ALREADY BUILT	11**](#1.-what-we-know-is-already-built)

[1.1 The existing learning program	11](#1.1-the-existing-learning-program)

[1.2 The merged semantic substrate	11](#1.2-the-merged-semantic-substrate)

[1.3 Factory and deployment posture	12](#1.3-factory-and-deployment-posture)

[Inspected implementation baseline	13](#inspected-implementation-baseline)

[**2\. INTENDED OPERATING RESULT	15**](#2.-intended-operating-result)

[**3\. THE CORE BET: TWO PLANES, ONE SEMANTIC AUTHORITY	16**](#3.-the-core-bet:-two-planes,-one-semantic-authority)

[Architecture and ownership	17](#architecture-and-ownership)

[3.1 Dense topology and exact parameter geometry	18](#3.1-dense-topology-and-exact-parameter-geometry)

[**4\. LOSSLESS FRAME ADDRESSING AND COMPILATION	20**](#4.-lossless-frame-addressing-and-compilation)

[4.1 Address model	20](#4.1-address-model)

[4.2 Fast path for fixed-role frames	21](#4.2-fast-path-for-fixed-role-frames)

[4.3 Compiler algorithm	22](#4.3-compiler-algorithm)

[4.4 Compression economics	22](#4.4-compression-economics)

[Semantic identity and extensible capacity	24](#semantic-identity-and-extensible-capacity)

[Role-addressable frame and exact codec	24](#role-addressable-frame-and-exact-codec)

[**5\. FACTORIZED SEMANTIC EMBEDDINGS	25**](#5.-factorized-semantic-embeddings)

[Factorized semantic geometry	27](#factorized-semantic-geometry)

[**6\. NEURAL SPINE: 12 × 768 ATLAS-NATIVE TRANSFORMER	28**](#6.-neural-spine:-12-×-768-atlas-native-transformer)

[6.1 CCGQA in the MLX forward	28](#6.1-ccgqa-in-the-mlx-forward)

[6.2 Multi-resolution reasoning	29](#6.2-multi-resolution-reasoning)

[6.3 Positional system	29](#6.3-positional-system)

[Causal neural spine	30](#causal-neural-spine)

[Depth selection and bounded temporal refinement	30](#depth-selection-and-bounded-temporal-refinement)

[**7\. BLOCK ATTNRES: SELECT INFORMATION ACROSS DEPTH	32**](#7.-block-attnres:-select-information-across-depth)

[**8\. ATLAS-ADDRESSED CONDITIONAL MEMORY	33**](#8.-atlas-addressed-conditional-memory)

[Conditional motif memory	35](#conditional-motif-memory)

[**9\. TURBOQUANT: STRUCTURE-AWARE CACHE COMPRESSION	36**](#9.-turboquant:-structure-aware-cache-compression)

[Concrete derived cache codec	37](#concrete-derived-cache-codec)

[**10\. THE SEMANTIC RELEASE AND FACTORY BRIDGE	38**](#10.-the-semantic-release-and-factory-bridge)

[Generative curriculum across SKOS	40](#generative-curriculum-across-skos)

[Rosetta and Akasha integration	41](#rosetta-and-akasha-integration)

[Local correction and requalification	41](#local-correction-and-requalification)

[**11\. TRAINING POLICY: KEEP THE TEACHER WE’VE PAID FOR	43**](#11.-training-policy:-keep-the-teacher-we’ve-paid-for)

[Continual plasticity and optimizer clocks	45](#continual-plasticity-and-optimizer-clocks)

[Complete cognitive solver and typed outputs	46](#complete-cognitive-solver-and-typed-outputs)

[Teacher, losses, retention and progression	47](#teacher,-losses,-retention-and-progression)

[Salience and osmotic learning	48](#salience-and-osmotic-learning)

[**12\. MODEL IDENTITY, CHECKPOINTS AND TOOLCHAIN	49**](#12.-model-identity,-checkpoints-and-toolchain)

[12.1 Introduce ModelTopologySpec v2, leave v1 readable	49](#12.1-introduce-modeltopologyspec-v2,-leave-v1-readable)

[12.2 Minimal source layout	50](#12.2-minimal-source-layout)

[12.3 Actual MLX implementation	51](#12.3-actual-mlx-implementation)

[Durable generations and cold recovery	52](#durable-generations-and-cold-recovery)

[12.4 Interface completion details	52](#12.4-interface-completion-details)

[12.4.1 Shared input/output records	52](#12.4.1-shared-input/output-records)

[12.4.2 Parameter naming and initialization	53](#12.4.2-parameter-naming-and-initialization)

[12.4.3 Fast-state lifecycle	53](#12.4.3-fast-state-lifecycle)

[12.4.4 Output construction and legitimate answer reuse	54](#12.4.4-output-construction-and-legitimate-answer-reuse)

[**13\. HARDWARE AND RESOURCE ENVELOPE	55**](#13.-hardware-and-resource-envelope)

[13.1 Machines and ownership	55](#13.1-machines-and-ownership)

[13.2 Parameter and state estimate	55](#13.2-parameter-and-state-estimate)

[13.3 Resource allocation policy	56](#13.3-resource-allocation-policy)

[Hardware, batching and writer budgets	57](#hardware,-batching-and-writer-budgets)

[**14\. THREE BOUNDED DEVELOPMENT LANES	58**](#14.-three-bounded-development-lanes)

[Detailed implementation plan	59](#detailed-implementation-plan)

[Three simultaneous workstreams	59](#three-simultaneous-workstreams)

[Commit and handoff discipline	59](#commit-and-handoff-discipline)

[EGM execution profile	60](#egm-execution-profile)

[Verification budget	60](#verification-budget)

[Ready work	61](#ready-work)

[Workstream navigation	61](#workstream-navigation)

[**15\. SEQUENCE: ONE STUDENT, NO MODEL TOURNAMENT	62**](#15.-sequence:-one-student,-no-model-tournament)

[Slice A. Lock release and frame contracts	62](#slice-a.-lock-release-and-frame-contracts)

[Slice B. Build the real 12-layer model	62](#slice-b.-build-the-real-12-layer-model)

[Slice C. Add trainable memory and inherit the Factory	63](#slice-c.-add-trainable-memory-and-inherit-the-factory)

[Slice D. Bind SKOS and operationalize resources	63](#slice-d.-bind-skos-and-operationalize-resources)

[Slice E. Start the live BAMF-0.2 student (owner-initiated after slice D or once the A/B/C path of slice C is ready)	64](#slice-e.-start-the-live-bamf-0.2-student-\(owner-initiated-after-slice-d-or-once-the-a/b/c-path-of-slice-c-is-ready\))

[Training strategy derived from BRAVO	65](#training-strategy-derived-from-bravo)

[L0: acquire and use the foundations	65](#l0:-acquire-and-use-the-foundations)

[L1: expand through semantic structure and qualified evidence	65](#l1:-expand-through-semantic-structure-and-qualified-evidence)

[L2: deepen, specialize and adapt continuously	66](#l2:-deepen,-specialize-and-adapt-continuously)

[L3/L4: expand resources and exchange capabilities when useful	67](#l3/l4:-expand-resources-and-exchange-capabilities-when-useful)

[Training-session operating loop	67](#training-session-operating-loop)

[**16\. FIRST RUN AND OPERATING COMMANDS	68**](#16.-first-run-and-operating-commands)

[Operator command contract	70](#operator-command-contract)

[**17\. CHOICES WE HAVE NOW MADE	72**](#17.-choices-we-have-now-made)

[Owner decisions and reconciliation	74](#owner-decisions-and-reconciliation)

[**18\. NON-NEGOTIABLE EXECUTION INVARIANTS	76**](#18.-non-negotiable-execution-invariants)

[Completion and useful outcomes	77](#completion-and-useful-outcomes)

[**19\. EXECUTIVE HANDOFF	78**](#19.-executive-handoff)

[**20\. ARCHITECTURAL ARCHAEOLOGY AND SYNTHESIS	79**](#20.-architectural-archaeology-and-synthesis)

[Retained and amended mechanisms	79](#retained-and-amended-mechanisms)

[Detailed older-source dispositions	81](#detailed-older-source-dispositions)

[**21\. PREDECESSOR REQUIREMENT CONTINUITY	84**](#21.-predecessor-requirement-continuity)

[**22\. EGM-RESOLVED EXECUTION CONTRACTS	87**](#22.-egm-resolved-execution-contracts)

[22.1 Prefix-local refinement selection	87](#22.1-prefix-local-refinement-selection)

[22.2 Dependent typed-output state transition	87](#22.2-dependent-typed-output-state-transition)

[22.3 Stable factor IDs and exact graph channels	89](#22.3-stable-factor-ids-and-exact-graph-channels)

[22.4 Masking, clocks and row maturation	90](#22.4-masking,-clocks-and-row-maturation)

[22.5 Exact plasticity state machine	90](#22.5-exact-plasticity-state-machine)

[22.6 Receiver-owned plastic-delta adoption	91](#22.6-receiver-owned-plastic-delta-adoption)

[22.7 Bounded typed route construction	92](#22.7-bounded-typed-route-construction)

[22.8 Full-atlas completion denominator	93](#22.8-full-atlas-completion-denominator)

[22.9 First BRAVO evidence adapter and template	93](#22.9-first-bravo-evidence-adapter-and-template)

[22.10 First genuine learning target and advance rule	95](#22.10-first-genuine-learning-target-and-advance-rule)

[22.11 Normative complete tensor ledger	95](#22.11-normative-complete-tensor-ledger)

[**23\. LINKED IMPLEMENTATION SPECIFICATIONS	102**](#23.-linked-implementation-specifications)

[Lane A	102](#lane-a)

[A01: \#345\| Compile the pinned SKOS release into the BAMF semantic authority snapshot	102](#a01:-#345|-compile-the-pinned-skos-release-into-the-bamf-semantic-authority-snapshot)

[A02: \#348\| Implement append-only semantic banks and active-vocabulary allocation	103](#a02:-#348|-implement-append-only-semantic-banks-and-active-vocabulary-allocation)

[A03: \#349\| Bind typed AST semantics to role-addressable frame contracts	104](#a03:-#349|-bind-typed-ast-semantics-to-role-addressable-frame-contracts)

[A04: \#351\| Build the reversible four-slot frame codec and extended fallback	105](#a04:-#351|-build-the-reversible-four-slot-frame-codec-and-extended-fallback)

[A05: \#357\| Compile causally valid mixed frame and atomic sequences	105](#a05:-#357|-compile-causally-valid-mixed-frame-and-atomic-sequences)

[A06: \#352\| Compile source-grounded factorized features once per release	106](#a06:-#352|-compile-source-grounded-factorized-features-once-per-release)

[A07: \#353\| Register exact semantic and deterministic cognitive operators	107](#a07:-#353|-register-exact-semantic-and-deterministic-cognitive-operators)

[A08: \#358\| Generate capability and lesson programs across the full SKOS inventory	108](#a08:-#358|-generate-capability-and-lesson-programs-across-the-full-skos-inventory)

[A09: \#360\| Generate a resumable prerequisite-aware curriculum frontier	109](#a09:-#360|-generate-a-resumable-prerequisite-aware-curriculum-frontier)

[A10: \#361 \| Compile BRAVO evidence strata into Factory learning releases	110](#a10:-#361-|-compile-bravo-evidence-strata-into-factory-learning-releases)

[A11: \#362\| Generate lawful ambiguity and structural contrast lessons	111](#a11:-#362|-generate-lawful-ambiguity-and-structural-contrast-lessons)

[A12: \#364\| Complete the single-authority semantic cutover and release receipt	111](#a12:-#364|-complete-the-single-authority-semantic-cutover-and-release-receipt)

[A13: \#354\| Enforce combined context eligibility before neural or motif access	112](#a13:-#354|-enforce-combined-context-eligibility-before-neural-or-motif-access)

[Lane B	113](#lane-b)

[B01: \#346\| Declare BAMF v2 topology and generate the complete parameter manifest	113](#b01:-#346|-declare-bamf-v2-topology-and-generate-the-complete-parameter-manifest)

[B02: \#359\| Implement tied factorized semantic embeddings and paged readout	114](#b02:-#359|-implement-tied-factorized-semantic-embeddings-and-paged-readout)

[B03: \#363\| Build the role-aware frame encoder and constituent handles	115](#b03:-#363|-build-the-role-aware-frame-encoder-and-constituent-handles)

[B04: \#350\| Implement causal compressed-convolution GQA and incremental RoPE caches	115](#b04:-#350|-implement-causal-compressed-convolution-gqa-and-incremental-rope-caches)

[B05: \#355\| Implement three-group Block AttnRes with stable depth selection	116](#b05:-#355|-implement-three-group-block-attnres-with-stable-depth-selection)

[B06: \#365\| Add bounded recurrent constituent refinement with input recall	117](#b06:-#365|-add-bounded-recurrent-constituent-refinement-with-input-recall)

[B07: \#356\| Implement transactional motif-key allocation and structural fallback	118](#b07:-#356|-implement-transactional-motif-key-allocation-and-structural-fallback)

[B08: \#366\| Train two context-gated motif-memory reads inside the model	119](#b08:-#366|-train-two-context-gated-motif-memory-reads-inside-the-model)

[B09: \#368\| Provision fast adapters and explicit multi-timescale plasticity	120](#b09:-#368|-provision-fast-adapters-and-explicit-multi-timescale-plasticity)

[B10: \#367\| Implement typed scalar, slot and structured answer heads	121](#b10:-#367|-implement-typed-scalar,-slot-and-structured-answer-heads)

[B11: \#369\| Assemble the real atlas-native model and architecture dispatch	122](#b11:-#369|-assemble-the-real-atlas-native-model-and-architecture-dispatch)

[B12: \#370\| Extend native AdamW custody to masked plastic groups and candidate transactions	123](#b12:-#370|-extend-native-adamw-custody-to-masked-plastic-groups-and-candidate-transactions)

[B13: \#372\| Persist and cold-resume the complete BAMF learning generation	124](#b13:-#372|-persist-and-cold-resume-the-complete-bamf-learning-generation)

[B14: \#375\| Implement the derived low-bit KV-cache codec with FP32 fallback	125](#b14:-#375|-implement-the-derived-low-bit-kv-cache-codec-with-fp32-fallback)

[Lane C	126](#lane-c)

[C01: \#347\| Create the three-lane integration baseline and executable EGM work contract	126](#c01:-#347|-create-the-three-lane-integration-baseline-and-executable-egm-work-contract)

[C02: \#371\| Adapt ordinary Factory batches to BAMF inputs and targets	127](#c02:-#371|-adapt-ordinary-factory-batches-to-bamf-inputs-and-targets)

[C03: \#376\| Carry the replay-salvaged teacher into the new student lineage	128](#c03:-#376|-carry-the-replay-salvaged-teacher-into-the-new-student-lineage)

[C04: \#373\| Compose exact and neural mechanisms behind one capability solver	129](#c04:-#373|-compose-exact-and-neural-mechanisms-behind-one-capability-solver)

[C05: \#378\| Evaluate and retain end-to-end capabilities with current school safeguards	130](#c05:-#378|-evaluate-and-retain-end-to-end-capabilities-with-current-school-safeguards)

[C06: \#379\| Route attention and curriculum priorities with SÍ SÉ SON signals	130](#c06:-#379|-route-attention-and-curriculum-priorities-with-sí-sé-son-signals)

[C07: \#380\| Advance the Factory continuously under an explicit atlas admission lease	131](#c07:-#380|-advance-the-factory-continuously-under-an-explicit-atlas-admission-lease)

[C08: \#374\| Make batch preparation and resource budgets topology-aware	132](#c08:-#374|-make-batch-preparation-and-resource-budgets-topology-aware)

[C09: \#377\| Propagate corrections through reusable cognition and learned support	133](#c09:-#377|-propagate-corrections-through-reusable-cognition-and-learned-support)

[C10: \#383\| Publish BAMF learning and release events into Rosetta/Akasha projections	134](#c10:-#383|-publish-bamf-learning-and-release-events-into-rosetta/akasha-projections)

[C11: \#384\| Expose a usable BAMF cockpit and stable launch/resume commands	134](#c11:-#384|-expose-a-usable-bamf-cockpit-and-stable-launch/resume-commands)

[C12: \#381\| Package reusable cognitive capabilities and compatible plastic deltas	135](#c12:-#381|-package-reusable-cognitive-capabilities-and-compatible-plastic-deltas)

[C13: \#385\| Run the integrated disposable learning and recovery acceptance slice	136](#c13:-#385|-run-the-integrated-disposable-learning-and-recovery-acceptance-slice)

[C14: \#386\| Deliver the continuing BRAVO-to-full-atlas training program	137](#c14:-#386|-deliver-the-continuing-bravo-to-full-atlas-training-program)

[C15: \#387\| Close BAMF delivery with fresh EGM review and three-lane receipts	138](#c15:-#387|-close-bamf-delivery-with-fresh-egm-review-and-three-lane-receipts)

[C16: \#382\| Open the first durable BAMF student path before optional projection work	138](#c16:-#382|-open-the-first-durable-bamf-student-path-before-optional-projection-work)

[**SOURCE AND EVIDENCE REGISTER	141**](#source-and-evidence-register)

[**HISTORICAL SOURCE INVENTORY	143**](#historical-source-inventory)

[**SUPPLEMENTAL SOURCE AND EVIDENCE REGISTER	144**](#supplemental-source-and-evidence-register)

[External engineering references:	144](#external-engineering-references:)

[**24\. ARCHITECTURAL DECISION RECORD \| BAMF-0.2	146**](#24.-architectural-decision-record-|-bamf-0.2)

[ADR-BAMF02-001 \| 27 OCTOBER 2026 \| Current design and source-of-truth alignment	146](#adr-bamf02-001-|-27-october-2026-|-current-design-and-source-of-truth-alignment)

[ADR-BAMF02-002 \| 27 OCTOBER 2026 \| Behavioral acceptance over identifier references	147](#adr-bamf02-002-|-27-october-2026-|-behavioral-acceptance-over-identifier-references)

[ADR-BAMF02-003 \| 27 OCTOBER 2026 \| Motif fallback and EGM tensor equivalence	148](#adr-bamf02-003-|-27-october-2026-|-motif-fallback-and-egm-tensor-equivalence)

[ADR-BAMF02-004 \| 27 OCTOBER 2026 \| Functional, recursive, self-maintaining curriculum Factory	149](#adr-bamf02-004-|-27-october-2026-|-functional,-recursive,-self-maintaining-curriculum-factory)

[Implementation work-packaging clarification \| 27 OCTOBER 2026 \| Lossless recursive issue decomposition (non-normative navigation)	152](#implementation-work-packaging-clarification-|-27-october-2026-|-lossless-recursive-issue-decomposition-\(non-normative-navigation\))

[**BAMF-0.2 THREE-LANE IMPLEMENTATION ISSUE INDEX \| 27 OCTOBER 2026 \| WORK-PACKAGING RECEIPT, NOT AN ARCHITECTURAL AMENDMENT	153**](#bamf-0.2-three-lane-implementation-issue-index-|-27-october-2026-|-work-packaging-receipt,-not-an-architectural-amendment)

# EXECUTIVE DECISION {#executive-decision}

Build Bilqis Aspirant Metacog Frame (BAMF-0.2): a dual-plane semantic learner with a canonical exact-address plane and a learned contextual plane. The exact plane provides stable concept identity, typed frame roles, source and release lineage, local composition, and deterministic retrieval. The neural plane provides context-sensitive composition, hypothesis formation, generalization, and reasoning. A frame compiler converts source-qualified symbolic constructions into reversible, causally valid frame units. The student operates globally on frames and selectively expands constituents when precision demands it.

Fix the dense core at 12 Transformer layers, 768 hidden dimensions, 3,072-dimensional feed-forward networks, 16 query heads, 8 key/value heads, and a 1,024-position initial neural context. Use RoPE, 384 total query-attention channels, 192 K/V channels, causal compressed convolutional grouped-query attention (CCGQA), and three four-layer Block AttnRes groups. Tie the active semantic-ID readout to the identity embedding. Start with one 8,192-row semantic bank without inventing 8,192 meanings; extend by append-only banks as qualified semantics are admitted. Start conditional atlas-addressed memory at 16,384 learned 128-dimensional motif slots. Keep model weights, gradients, checkpoints and AdamW in authoritative FP32. Use TurboQuant-style compression only on derived inference caches and optional retrieval vectors, never as the canonical state.

These are chosen engineering settings, not a claim that all published paper gains add together. The commitment is to build the composite architecture and learn from the first durable student rather than fund a factorial benchmark program.

The implementation target is the existing Bilqis-MLX Python/MLX trainer and curriculum Factory. The source-of-truth substrate is the now-merged SKOS/RDF compiler, its source-pinned corpus, and the runtime-approved FactoryRelease chain. FalkorDB and Akasha provide derived graph lookup. They do not set semantic identities or grant lesson admission. Retain existing source-gold, checkpoint custody, isolated AdamW, whole-school retention, championship, promotion, and teacher-observation rules.

A first useful outcome is a fresh atlas-native student that can be created, trained on source-valid capabilities compiled from its current admitted FactoryRelease, survive checkpoint/resume, and continue into every source-qualified successor admitted by the same generic Factory policy with the replay-salvaged teacher. The SKOS bridge then supplies future approved concepts and frame schemas through the Factory. The old student remains intact as a source of teaching evidence and historical performance, not as an incompatible weight-soup donor.

# 

## IMPLEMENTATION DECISION \| 27 OCTOBER 2026 {#implementation-decision-|-27-october-2026}

27 October 2026\. Implementation specification and three-workstream delivery program. Root owner: Bilqis-MLX \#341 (https\://github.com/Entif-AI/Bilqis-MLX/issues/341).

Build one atlas-native, continually extensible cognitive learner on the existing M3 Ultra. Keep the chosen 12-layer, 768-wide neural spine; give it exact role-addressable semantic state, factorized embeddings, compressed causal attention, learned depth selection, conditional motif memory, bounded local recurrent refinement, and explicitly plastic parameter groups. Reuse the working generative Factory and replay teacher. The learner's education expands through the eligible SKOS corpus and qualified real-world evidence instead of ending at Grade C.

Capability belongs to the complete system. Exact retrieval, deterministic computation, neural prediction, learned memory and composition all earn credit for successful outcomes. Spend new training on gaps, useful transfer, routing and composition. Preserve acquired competence and cheap reusable computation. SÍ SÉ SON determines where attention and adaptation are useful; observed consequences determine what is retained.

The immediate target is a durable student that creates, learns, rejects a harmful candidate completely, resumes exactly, and continues through generated semantic additions. The first student path is C16: \#382 (https\://github.com/Entif-AI/Bilqis-MLX/issues/382). Full delivery includes low-bit derived caches, correction propagation, portable capability packages and Akasha projections. Those later components have independent implementation owners, so they can finish while the useful student already learns.

This document is the shared contract. Every linked implementation issue repeats its relevant contract, named code surfaces, algorithm, direct dependencies, focused checks and execution instructions. The machine-readable workstack and publication ledger bind the exact GitHub objects.

# 

# 1\. WHAT WE KNOW IS ALREADY BUILT {#1.-what-we-know-is-already-built}

## 1.1 The existing learning program {#1.1-the-existing-learning-program}

Bilqis currently teaches a bounded, concept-first staircase: Grade A identification and foundational associations; Grade B directly typed Boolean AST operations; and Grade C COUNT → NUMBER → SUCCESSOR → ADD → SUB, with later multiplicative capabilities admitted only as their prerequisites permit. The Boolean capabilities remain ordinary admitted curriculum content. Incomplete capabilities in any grade retain debt and receive ordinary source-grounded teaching attention under the same grade-neutral teacher policy. Current curriculum is not a generic next-word text corpus, a tiny world-model benchmark, or an excuse to teach invented future semantics. Constructive lessons must establish the constituent concept before testing compositions. \[P1, P2\]

The \#324 frozen qualification specimen describes A6/B8/C7 with numeric roots 0 through 8, but that is the scope of its frozen experimental workload, not a universal declaration of the latest live student's numeric scope. The active source-gold roster, released stages, numeric ceiling, cumulative assessments, and optimizer step must be read from the exact student/run manifest before a new epoch is launched. Do not substitute the old frozen control for the current model's current facts. \[P3\]

The valuable current teacher mechanics have real implementation provenance: a bounded active strategy population, retained-incumbent exploitation, capability-local rejection/interference accounting, stochastic but bounded challenger rotation, 2/4/8/16-step multi-fidelity probes, a bounded vNext canary, source-grounded fresh transfer, and candidate-retention screens protecting the whole school. Promotion retry is tied to changed learner state, and introduction-grade sweeps use 92% entry / 87% continuation hysteresis. The learner's own AdamW and accepted checkpoint remain sovereign. \[P4\]

## 1.2 The merged semantic substrate {#1.2-the-merged-semantic-substrate}

SKOS PR \#291 was merged on 26 October 2026\. Its \#19 root and \#22–\#27 parent gates are closed. The implemented program includes atomic morphology projection, root-versus-sense identity, Stem × Specification distinctions, affix degrees and composition, non-silent source-row coverage, canonical RDF determinism, admitted versus held mapping status, SHACL gates, derived FalkorDB materialization, and an Akasha read-only path. The currently parsed lexicon is bounded, notably Chapters 1–2 in the parent contracts; the entire New Ithkuil lexicon is not claimed complete. \[P5\]

This is a remarkable starting asset: the project has already paid the labor cost of making semantic meanings, forms, source loci and relationships addressable without assuming every similar gloss is the same concept. The atlas-native student should consume that structure, not create a competing ontology.

The semantic intake work \#292–\#295 remains open. Those issues govern generating the semantic ABI, typed AST bindings, lesson-addressable manifest and final single-authority cutover from one canonical SKOS release. Therefore, a merged SKOS corpus is not equivalent to all of its concepts being admitted as training gold today. BAMF-0.2 consumes current A/B/C Factory releases immediately and connects new SKOS semantics through the governed successor bridge as it is completed. \[P6\]

## 1.3 Factory and deployment posture {#1.3-factory-and-deployment-posture}

The Factory-v2 branch stack remains distinct from main: Factory closure PR \#290, topology PR \#334, replayable observation PR \#335, frozen qualification PR \#336, and the selective 349 replay PR \#340 are stacked draft work. The v3 frozen \#324 executable stays an immutable scientific control. The new BAMF-0.2 architecture is a successor lineage founded on the replay-salvaged Factory behavior; it must not rewrite the \#324 specimen. \[P3, P4, P7\]

The currently inspected v1 ModelTopologySpec records only layers, heads, width, FFN and context. The actual forward still uses learned absolute positions and manually materialized QK attention matrices. BAMF-0.2 therefore requires a versioned topology/implementation contract and a new MLX forward, not another JSON file for the old network. \[P8\]

# 

## Inspected implementation baseline {#inspected-implementation-baseline}

Surface: SKOS \#291  •  Exact observation: Merged as 175cdf6778b4eeaea23a5bd36ad7dc6664df3ae8  •  Use: Canonical source/IR/RDF, sense/morphology coverage, derived Falkor/Akasha adapters

Surface: Replay teacher \#340  •  Exact observation: d21797e72365bf93ea7cad3a4ef9020ec9817f23 on codex/337-replay-349-20261026  •  Use: New-student teacher/runtime baseline

Surface: Topology \#334/\#320  •  Exact observation: Versioned v1 topology already exists  •  Use: Extend explicitly to v2

Surface: Teacher observations \#335/\#333  •  Exact observation: Proposal/delivery/outcome/cost owner exists  •  Use: Consume, rather than replace

Surface: Factory \#290/\#150  •  Exact observation: Generic release, source execution, JIT candidate and admission machinery  •  Use: Same path for current and future grades

Surface: Semantic bridge \#292-\#295  •  Exact observation: Existing open implementation owners  •  Use: New lane-A leaves complete their outcomes

Surface: Factory \#296  •  Exact observation: Existing stage/notify flywheel owner  •  Use: Default staging plus explicit BAMF admission lease

Surface: Akasha \#297-\#302  •  Exact observation: Existing authority/projection/recovery owners  •  Use: BAMF event adapters and readback

Surface: Existing BAMF \#341  •  Exact observation: BAMF-0.1 root and expanded engineering specification  •  Use: Preserved root, new versioned amendment

Surface: Google EGM  •  Exact observation: b3a35956759bf7f024af2ff061b2e0b44b438e4c  •  Use: Real fresh-context review and faithful implementation handoffs

Actual inspected code includes ModelTopologySpec, expected\_parameter\_shapes, create\_student, SourceExecutionContext, CandidateFrontierRelease, propose\_curriculum\_delta, prepare\_realized\_candidates, AnswerModalityRegistry, \_train\_step, save\_new\_bundle, \_advance and the current scheduler/promotion functions. The present v1 forward still uses a learned absolute-position table and full QKV matrices. BAMF therefore receives a real new forward and backend dispatch, not just a configuration file.

# 

# 2\. INTENDED OPERATING RESULT {#2.-intended-operating-result}

The near-term product is a genuine small semantic learner with an unusually structured input representation. It learns to identify concepts, perform direct Boolean operations, construct numeric relations and transfer those capabilities to new source-generated examples. It is not an LLM trained on ordinary internet prose. The atlas supplies exact identity and permissible composition; the student learns which valid constructions are relevant, what follows from them, and how to handle novel combinations.

At the end of the first build:

* The same code can initialize a fresh BAMF-0.2 model and resume it exactly.  
* The same existing Factory pipeline compiles and teaches the admitted A/B/C curriculum without grade-specific branches.  
* A four-member frame can be addressed by its individual role without any lossy hash reconstruction.  
* Global attention operates over the compiled sequence of frames or atomic fallbacks.  
* The model learns with GQA/CCGQA, RoPE, Block AttnRes and conditional motif memory as normal components, not after-the-fact plugins.  
* The teacher observes proposal, delivered lesson, retention outcome and cost, and automatically allocates subsequent attempts under its existing controls.  
* A new approved SKOS semantic ID can enter through one versioned ABI/AST/FactoryRelease path without shifting prior indices or reinterpreting old meanings.  
* The dashboard tells an operator what the learner actually improved, not just how often it retained a candidate.

# 

# 3\. THE CORE BET: TWO PLANES, ONE SEMANTIC AUTHORITY {#3.-the-core-bet:-two-planes,-one-semantic-authority}

Exact plane. Canonical SKOS/RDF release and typed Factory AST own semantic identities, release digests, frame schemas, role cardinalities, occurrence IDs, ordered constituent references, and provenance. The exact plane is lossless, versioned and reproducible. A direct lookup resolves (frame instance, role, occurrence) to its admitted canonical concept identity and source-bound annotations. It does not make an ambiguous external utterance unambiguous by decree. External interpretations remain separate provisional constructions until admitted through the proper semantic boundary. \[P5, R7\]

Neural plane. Factorized identity/type/role/schema embeddings, learned frame composition, CCGQA global attention, Block AttnRes depth selection and Engram-like motif memory form an integrated MLX student. These are trainable approximation mechanisms. They consume exact addresses but never override them.

The bridge between planes is a causal, versioned FrameCompiler. It never changes the source meaning. It decides how many neural positions a source-valid construction needs and carries a sidecar allowing the original token identities, roles, order and scoping to be reconstructed. Later operations can ask for an exact slot directly or expand a frame into detailed constituent computation.

The payoff we choose to pursue is that neural computation grows with unresolved semantic structure, not mechanically with every raw atomic symbol. Familiar complete frames receive compact representations. Difficult constructions receive conditional fine-grained computation. We will build this behavior explicitly, rather than hoping attention heads discover it unaided.

## Architecture and ownership {#architecture-and-ownership}

The semantic plane owns exact admitted identities, role bindings, source evidence, temporal scope and reversible structure. The neural plane owns learned contextual composition and adaptation. The Factory owns lawful lessons and evaluation construction. The existing runtime owns admission, candidate retention, checkpoints and the one mutable learner. Akasha owns rebuildable views over immutable evidence and reusable cognitive products. Rosetta supplies the shared meaning/trace boundaries.

The forward path is:

Factory source-visible AST \-\> released exact frames/features \-\> factorized embeddings \-\> frame encoder and motif read \-\> 12 CCGQA/FFN blocks with three depth selectors/adapters \-\> bounded constituent refinement \-\> typed answer \-\> whole-system solver/evaluator \-\> accepted generation or complete rollback.

The expansion path is:

SKOS release \-\> canonical ABI and AST bindings \-\> reusable construction families \-\> prerequisite-ready candidate \-\> Factory verification/staging \-\> persisted admission lease \-\> atomic active-set/bank extension \-\> ordinary teaching \-\> outcomes \-\> new ready work.

The correction path is:

new source/evaluation evidence \-\> immediate dependent hold \-\> local recompute/requalification \-\> changed result propagates one edge \-\> unchanged result terminates propagation.

### 3.1 Dense topology and exact parameter geometry {#3.1-dense-topology-and-exact-parameter-geometry}

Component: Backbone  •  Selected setting: 12 blocks, width 768, pre-RMSNorm epsilon1e-5

Component: FFN  •  Selected setting: 768-\>3072-\>768, squared ReLU, two bias-free matrices

Component: Attention  •  Selected setting: 16 query heads,8 KV heads,24 channels/head; Q384,K192,V192

Component: Local attention preprocessing  •  Selected setting: Independent causal depthwise Q/K/V convolution, kernel 3

Component: Position  •  Selected setting: RoPE24 coordinates, base 10000, scale1, nontraditional layout, initial context 1024

Component: Depth selection  •  Selected setting: Groups4/4/4, shared128-wide normalized source selector

Component: Identity  •  Selected setting: Initial8192x768 table, tied active readout, append-only banks

Component: Feature factors  •  Selected setting: Type/role/schema512x128; graph features 64

Component: Frame/refinement  •  Selected setting: 768-wide local state with 192-channel role interaction; up to 2 local extra passes

Component: Motif memory  •  Selected setting: Initial16384x128, two gated reads, page growth to 65536

Component: Fast adapters  •  Selected setting: Three rank8 residual adapters, zero-output initialization

Component: State  •  Selected setting: Authoritative FP32 parameters, gradients and native AdamW

Component: Derived cache  •  Selected setting: rot3/v1,3-bit coordinates plus amortized norm/header metadata

The dense attention/FFN matrices total 67,239,936 parameters. Initial identity rows add 6,291,456 and motif vectors 2,097,152. Three adapter matrix pairs add 36,864. The generated manifest counts all remaining feature, normalization, routing, convolution, frame and answer-head tensors. The earlier79-85M estimate is an orientation; the actual declared tensor census is the release truth. Do not add unused parameters merely to hit an estimate.

Each additional semantic bank adds 6,291,456 parameters and matching optimizer/moment state. At FP32, weights+gradients+two moments cost approximately 16 bytes per scalar before activations and copies. The initial core is comfortably below the machine's96GB physical memory, but activation/candidate/mentor state determines practical microbatch size. A full1024-position KV cache across 12 layers is18MiB per sequence with the chosen8x24 geometry.

# 

# 4\. LOSSLESS FRAME ADDRESSING AND COMPILATION {#4.-lossless-frame-addressing-and-compilation}

## 4.1 Address model {#4.1-address-model}

Use the schema tuple (semantic\_release\_digest, frame\_schema\_id, frame\_instance\_id, role\_id, occurrence\_index). An exact constituent lookup returns (stable\_semantic\_id, local\_token\_index, source\_ref, role\_assignment). A frame has an immutable content fingerprint and a separate occurrence identity. Identical contents can recur at different positions and in different causal contexts without becoming the same event instance. Stable semantic identity remains distinct from a release digest or an implementation hash.

Define these internal records:

* ConceptRef: semantic\_id, release\_digest, active\_vocab\_index, semantic\_type\_ids, source locus.  
* RoleSpec: role\_id, allowed\_concept\_types, min\_count, max\_count, order\_mode, nesting policy.  
* FrameSchema: schema\_id, version, role\_specs, construct\_kind, approved\_source\_constraints.  
* FrameInstance: instance\_id, schema\_ref, role\_bindings, parent\_instance, source\_span, causal\_prefix\_end.  
* PackedFrame: schema\_ref, fast\_code or variable\_slots, exact\_role\_index, constituent\_order, occurrence\_lineage, compiler\_digest.  
* FrameToken: one neural position with a pointer to PackedFrame, a learned aggregate vector, and expansion handles.  
* ReleaseBinding: canonical RDF digest, ABI digest, typed-AST digest, FactoryRelease digest, teacher-policy epoch.  
* ModelLineage: neural geometry, module configuration, initialization seed, optimizer contract, active source/release binding.

Every non-syntactic proposed object belongs to Bilqis's compiled-model layer or a namespaced extension. Do not introduce a new Rosetta Core object for a frame already expressible under existing Concept/Frame semantics. A compiler implementation should consume canonical identities; it does not take authority to rename them. \[R7, P6\]

## 4.2 Fast path for fixed-role frames {#4.2-fast-path-for-fixed-role-frames}

For a vocabulary capacity of 8,192, each local vocabulary index needs 13 bits. A fixed, four-slot frame can place four indices in a 52-bit payload within a 64-bit word. The remaining 12 bits can carry a local layout/version flag, validity mask or compact schema tag. All extended metadata stays in its exact sidecar.

The 64-bit payload is a reversible representation of four slot indices, not a cryptographic hash and not a complete account of frame occurrence or nested structure. The packed integer is never published as a stable semantic ID. A canonical group CID is computed from the full typed canonical content. A stable member or frame identifier follows the project's accepted identity contract.

Use a fast fixed-slot representation for common constructions and a variable-length sidecar for greater arity, repeated roles, scopes, nested frames, negation, quantifier structure and unusual New Ithkuil morphology. Repeated broad semantic types are allowed when role assignments differ. Max-one applies to a role declared singular, not indiscriminately to all concepts of a category.

Example: TRANSFER(AGENT:Alice, ACTION:Give, RECIPIENT:Bob, THEME:Book). lookup(frame\_017, ACTION) returns the exact approved Give identity. A second frame with Alice and Bob swapped has different role bindings, despite reusing the same concept IDs. If two AGENT occupants are valid, the schema defines indexed membership or a nested collective-agent frame.

## 4.3 Compiler algorithm {#4.3-compiler-algorithm}

* Stage 1: read the exact admitted AST/semantic release and role schema.  
* Stage 2: validate role count, type admissibility, constituent source release, scoping & current prefix availability.  
* Stage 3: canonicalize ordered role bindings and issue a complete, lossless FrameInstance plus source lineage.  
* Stage 4: choose one neural frame position for a complete packable frame; otherwise retain atomic or nested-frame positions.  
* Stage 5: emit exact address and expansion tables, causal masks, frame/constituent position maps and a digest-bound compiler receipt.  
* Stage 6: provide bidirectional decoding to the original typed tokens and expected AST constituents.

The compiler must produce identical addresses and reconstructed AST semantics when given the same immutable release and input. It also provides fast access to arbitrary individual slots. This is a compiler contract and can be proven with literal typed examples and round trips. It does not require a research benchmark suite.

Causality is preserved at the prefix boundary. An incomplete frame exists as a partial frame, not a completed object with access to future constituents. The decoder can append slots as inputs arrive, close a frame when complete, and expose the exact constituents that are already present. Neither attention, convolution, lookup memory nor auxiliary features may inspect a token beyond the current prediction boundary.

## 4.4 Compression economics {#4.4-compression-economics}

Our target is to make the ordinary four-slot complete construction one neural position plus a compact symbolic sidecar. This implies up to four atomic identifiers per frame position for suitable structures. More complex constructions can expand to multiple positions, and unpackable constructions use ordinary atomic positions. The model's 1,024-position ceiling is the neural frame-position ceiling, not a claim that every example contains exactly 4,096 semantic atoms.

At 1,024 atomic positions versus 256 frame positions, the quadratic QK score count drops by 16× and linear sequence-wide activation volume drops about 4× for the globally attended path. These are design-derived resource multipliers under complete 4-to-1 packing, not promises about an actual mixed lesson. Keep telemetry for actual accepted frame count, underlying atoms, frame fill, fallback share and expansion work.

# 

## Semantic identity and extensible capacity {#semantic-identity-and-extensible-capacity}

Use the actual plural package bilqis\_mlx/semantics/. Canonical semantic IDs come from the admitted SKOS release and existing formal-domain authorities. Keep canonical identity, release content digest, ABI index, frame occurrence, model topology, implementation digest, teacher epoch and derived projection digest separate. The ABI is append-only; start with one 8192-row embedding bank and allocate additional 8192-row banks at accepted admission boundaries as required by the eligible corpus census. index \= 8192\*bank \+ row. Existing indices, tensors and moments remain unchanged. Extended frame addresses carry uint32 indices; the 13-bit fast codec applies only while each member fits. A shape-policy digest freezes bank size and allocation rules; each generation separately records bank count, active-set digest and exact tensor shapes. New rows stay masked until source admission. Reserve source-defined syntax and explicit UNKNOWN/UNRESOLVED representations through the same ABI, never by fabricating meanings for empty rows.

## Role-addressable frame and exact codec {#role-addressable-frame-and-exact-codec}

FrameSchema binds released schema ID/revision, AST construct, ordered roles, allowed concept types, min/max cardinality, order mode and scope. FrameInstance binds occurrence ID, content digest, source span, parent occurrence, exact (role, occurrence-index)-\>ConceptRef/child-frame bindings and causal\_prefix\_end. ConceptRef binds semantic ID, semantic release, ABI index, type IDs and source reference. A repeated type in different roles is legal; occurrence is separate from content identity. A complete four-member frame packs four 13-bit indices in bits 0..51; bits 52..55 are presence mask 1111, bits 56..59 the release-local schema tag, bits 60..63 codec version1. Preserve full schema and metadata in a sidecar. Extended or atomic encoding handles nesting, repeated occupants, \>4 slots, \>16 schema tags, partial frames and indices\>=8192. Original order, scope, negation, modality, time and source lineage round-trip exactly. A frame becomes one neural position only when all members are visible before the prediction boundary.

# 5\. FACTORIZED SEMANTIC EMBEDDINGS {#5.-factorized-semantic-embeddings}

Start with one learned 8,192-row identity bank of 768-dimensional entries, with append-only bank expansion bound to versioned allocation and optimizer state. Only admitted indices are active; unused rows cannot enter source-generation gold, logits, prediction or curriculum authority. Existing index ordering remains append-only. The active first bank absorbs ordinary admissions without a reshape; later banks extend the ABI without shifting existing semantic indices or erasing their optimizer state.

For each source-qualified constituent, construct:

`x_atom = LayerNorm(E_identity[id] + P_type(E_type[type]) + P_role(E_role[role]) + P_schema(E_schema[schema]) + P_rel(E_rel[relation_features]) + E_position_local[slot])`

where the semantic feature projection modules map into width 768 and carry bounded learned gates. The precise feature input is typed, stable and versioned. The identity table is tied to the active token readout head; inactive reserved IDs are masked. Frame-level prediction uses a typed role-selection head and the tied concept head for the selected slot.

Initialize new identity rows from typed feature composition and a small deterministic seed residual, rather than pretending unknown meanings have learned vectors. Learned identity parameters can then specialize without erasing shared category geometry. The graph feature extractor supplies bounded, reproducible local relations and prerequisite signatures from the exact compiled SKOS/RDF release; it does not query live FalkorDB during every optimizer step.

The frame encoder uses role-ordered gated pooling plus one small cross-role interaction layer. It converts a set of exact constituent embeddings into one 768-dimensional contextual frame seed. It also retains constituent embeddings for later selective refinement. A frame represents a specific role assignment, not an unordered bag of concept IDs. The encoder uses approved schema order, parent/child references, and explicit scope modifiers.

For concept families with multi-sense realizations, the compiler binds to source-grounded sense identity, not a superficial gloss or a root spelling. Distinct surface forms may map to one accepted sense, and superficially similar forms may denote different concepts. The SKOS mapping compiler's admitted/held distinction remains effective here. A broad taxonomy class is never substituted for the exact leaf identity required by an AST operator.

Structural embeddings are an optimization substrate, not a shortcut around acquiring a capability. An exact identity lookup can tell Bilqis which typed primitive appears in a question. The teacher's independent assessment still measures whether the student computes the required operation on fresh examples.

## Factorized semantic geometry {#factorized-semantic-geometry}

The neural input uses FP32 E\_identity\[bank,row,768\], tied to semantic output logits; only active admitted indices are emitted. Shared features: type/role/schema tables each512x128, type aggregation as an arithmetic mean, graph features 64, local slot embeddings\[16,768\] with extended slots represented by a deterministic sinusoid plus role/occurrence features. x=RMSNorm(Eid+Ptype(mean(Etypes))+Prole(Erole)+Pschema(Eschema)+Prel(g64)+Elocal), epsilon1e-5. Each projected term has a sigmoid gate whose raw logit is initialized to \-2 (effective gate approximately0.1192). Feature extraction is deterministic per semantic release and executed before training, not through live Falkor calls. New identity rows initialize from the released feature composition plus seeded residual N(0,0.001^2). Frame encoding is role-ordered pooling plus one single-head cross-role attention layer of width192 and a 192-\>768 projection. Exact constituent embeddings remain addressable for refinement.

# 

# 6\. NEURAL SPINE: 12 × 768 ATLAS-NATIVE TRANSFORMER {#6.-neural-spine:-12-×-768-atlas-native-transformer}

Choose a single BAMF-0.2 topology:

12 Transformer blocks; hidden width 768; feed-forward width 3,072; 16 query heads; 8 KV heads; attention latent width 384; per-query latent head width 24; per-KV head width 24; RoPE on all 24 latent head coordinates; maximum 1,024 neural positions; CCGQA with causal depthwise convolution kernel size 3; 3 depth-residual blocks of 4 layers; tied active semantic readout; frame-aware input and two-granularity output.

The 16 query heads preserve a broad learned query vocabulary. Eight KV heads create two-query sharing groups, keeping ample independent key/value channels for a 90M-class design while halving the ordinary GQA KV head count relative to MHA. Compression of the attention computation to 384 query channels is intentional. The exact symbolic sidecar carries identities and role bindings, relieving continuous vectors of responsibility for exact catalog lookup.

## 6.1 CCGQA in the MLX forward {#6.1-ccgqa-in-the-mlx-forward}

At every block, pre-normalize the hidden state and project Q to \[batch, 16 heads, sequence, 24\] and K/V to \[batch, 8 heads, sequence, 24\]. Apply depthwise causal convolution to compressed representations, with left-only input history and explicit frame-boundary/scope markers. Apply RoPE to Q and K. Invoke MLX fast scaled-dot-product attention using its native grouped-query head shape and a causal mask; never tile K/V into 16 copies. Recombine Q outputs, project from the 384-dimensional attended channels to 768, and continue through the ordinary 3,072-dimensional gated/squared FFN path. \[R1, R2, R3\]

The implementation must use causal boundary handling for convolution and RoPE offsets on resumed/chunked sequences. If the production MLX API cannot fuse a specific convolution/attention combination, retain the chosen mathematical operation and use a separate causal convolution followed by fast GQA SDPA. The architecture stays fixed; the kernel implementation is replaceable under numerical compatibility proof.

## 6.2 Multi-resolution reasoning {#6.2-multi-resolution-reasoning}

Each complete frame is represented by one global-attention position. A typed expansion request retrieves the exact member addresses and runs a small local constituent-resolution module. The output is merged into the frame hidden state through a learned residual gate. Expansion is decided from a budgeted gate conditioned on role-query need, source complexity and the current frame representation. A packed frame can be partially expanded, and the original atomic path always remains available for structures that do not fit the fast frame contract.

A local expansion never returns a teacher gold answer. It reveals the admitted input structure and computes a learned refinement. Exact AST evaluation stays in the source/oracle owner, not inside the inference path.

## 6.3 Positional system {#6.3-positional-system}

Use RoPE with 1,024 initially supported neural positions and versioned base/scale/offset parameters. The same lineage can accept greater context later through a separately versioned operating contract and training extension, without a learned absolute position table reshape. Do not claim 4,096-frame reasoning competence merely because the positional function can generate additional angles. This implementation commits to a 1,024-position trained target first. \[R1\]

## Causal neural spine {#causal-neural-spine}

Frozen dense topology:12 blocks, width 768, FFN3072, pre-RMSNorm(eps1e-5), squared-ReLU two-matrix FFN768-\>3072-\>768, no projection biases. Attention Q=16x24=384 channels; K=V=8x24=192; output384-\>768. Independently apply causal depthwise conv kernel 3 to projected Q/K/V; reset left history at sequence/scope boundaries. RoPE on all24 Q/K head coordinates, base 10000, traditional=False, scale1; initial trained context 1024 neural positions. Native MLX fast.scaled\_dot\_product\_attention uses16Q/8KV directly, scale1/sqrt(24), without physically repeating KV. Mask causal, padding and source scope together. All-masked queries return zeros. Every trainable tensor is declared once in the parameter manifest and saved in the same candidate transaction.

## Depth selection and bounded temporal refinement {#depth-selection-and-bounded-temporal-refinement}

Partition12 blocks into groups\[4,4,4\]. Preserve h0 and one normalized per-position summary after each completed group. At boundary k, source order is h0,g1,...,gk. Shared bias-free matrices Wq/Wk/Wv\[128,768\] and Wout\[768,128\] implement q=Wq\*RMSNorm(current+frame\_seed), key\_i=Wk\*RMSNorm(summary\_i+type\_role768), score\_i=dot(q,key\_i)/sqrt128, alpha=softmax over available source axis, mix=sum(alpha\_i\*(Wv\*summary\_i)). Merge current+g\_k\*Wout\*mix. Each boundary has gate\_vector\[768\] initialized 0 and gate\_bias=log(1/9), giving g\_k=0.1\*sigmoid(dot(gate\_vector,RMSNorm(current))+gate\_bias), initially0.01. The shared factor composer supplies type\_role768; source summaries retain the768-wide interface. At group1 apply the second motif read after layer4 and before capturing/selecting g1. Future groups are absent. Apply the group's adapter after selection. The local refinement module keeps a768-wide recurrent state and one compressed single-head192-channel attention block, up to 2 extra passes, with immutable input/member recall every pass. Refinement never reruns the 12-layer backbone. Budgeted selection is external/deterministic and selected neural paths retain soft-gate gradients. Refinement is a prediction-local computation. Let p be the query prediction boundary and V(p) the ordered frames with causal\_prefix\_end\<=p that passed context eligibility. Compute Fp=len(V(p)) and quota=min(32,ceil(Fp/8)) using only V(p). Rank requested-role matches, then source-visible salience, then stable source position within V(p). Refinement results are keyed by (input-generation,p,query-ID,frame-occurrence) and never overwrite a shared backbone hidden state used by an earlier prediction. Future frames, labels, row padding and future query requests do not enter selection. Parallel teacher-forced predictions each use their own p-local view. Derive recurrence choice from SHA256(run-seed,visit-ID,p,query-ID,frame-occurrence), never total batch length. Pass budget is 0/1/2 for the selected frame. Increasing a row from 8 to 9 complete frames can change the later query's quota but cannot change the earlier query at fixed p. The single backbone produces immutable causal hidden states; the small local refiner operates on prediction-specific copies.

# 

# 7\. BLOCK ATTNRES: SELECT INFORMATION ACROSS DEPTH {#7.-block-attnres:-select-information-across-depth}

Partition 12 blocks into three consecutive depth groups of four. Each group forms a retained block summary. At subsequent group boundaries, use a small normalized attention selector over available earlier group summaries and the current hidden state. The selector's input also includes a projected frame-schema/type/role summary. This makes depth routing content-dependent while keeping the number of retained depth sources small and fixed.

This is the Block AttnRes approach adapted to an atlas-native input. Earlier group states can preserve precise structural binding features while later groups develop higher-order relations and consequences. The model learns when to reread earlier states instead of accumulating every intermediate transform with fixed equal weight. \[R4\]

Implement three depth groups as a structural model property. Save the depth-router parameters with the student and its optimizer. Do not enable a configuration path that changes the number or identity of these groups on an existing checkpoint. Start routing weights near the standard residual behavior so that the first few lessons do not begin from unbounded depth amplification.

Depth groups are not permanent assignments such as 'grammar layers' or 'arithmetic layers'. Their learned functions can evolve. Type/role annotations are inputs to the selection mechanism, not hard-coded restrictions on what a layer is allowed to learn.

# 

# 8\. ATLAS-ADDRESSED CONDITIONAL MEMORY {#8.-atlas-addressed-conditional-memory}

Deploy a small trainable Engram-inspired motif memory as part of the first model lineage. Use 16,384 initial slots, each holding a 128-dimensional learned vector, and an extensible capacity design reaching 65,536 slots without redefining semantic identity. Initial memory parameters contain about 2.10 million scalars, approximately 8 MiB in FP32. The larger 65,536-slot target contains 8.39 million scalars, approximately 32 MiB in FP32. \[R5\]

The address is a typed semantic motif key:

`(memory_schema_version, semantic_release_digest, frame_schema_id, ordered [(role_id, canonical_semantic_id)], relation_signature).`

Retrieve by an exact canonical key mapped to an append-only internal slot ID. If a bounded probabilistic hash index is used for speed, verify the full key before returning a value and never reinterpret a collision as semantic identity. Common motifs can receive stable memory-slot assignments; novel combinations receive factorized fallback features and later promotion based on observed use.

Use two read sites: the input frame encoder and the first Block AttnRes boundary after layer four. An input-time lookup gives the backbone familiar local structure. The mid-depth lookup offers a stored prior to a partially developed reasoning state. Both are merged through a contextual gate:

`updated_hidden = hidden + sigmoid(gate(hidden, frame_features)) × projection(memory_vector).`

The gate can learn to ignore a familiar motif when this instance's context contradicts its usual continuation.

Maintain two logical contents, with different authority:

Exact atlas lookup gives identifiers, constituents, admitted relations and source/release provenance. It is read-only model input and compiler data.

Learned motif memory gives continuous priors, contextual tendencies and reusable patterns. It may evolve through optimizer updates but cannot rewrite the atlas or assert an authoritative answer.

A pattern such as TRANSFER(AGENT, ACTION, RECIPIENT, THEME) can supply a reusable compositional prior. A specific Alice-GIVE-Bob-BOOK pattern may acquire a more specialized memory only if repeated learning makes that representation useful. That is how the model gains combinatorial generalization without enumerating every possible semantic tuple as an independent table row.

On semantic release changes, preserve old keys and memory state with their original release identity. New approved releases use explicit migration/admission mappings. Reindexing the live memory table or changing old semantic meanings in place is forbidden. A source closure change either admits new entries append-only or starts a deliberate successor lineage when it invalidates learned semantics.

The motive is clear: spend Transformer depth on consequential novel computation rather than rederiving known, stable local semantic patterns. DeepSeek's Engram work supports the general conditional-lookup approach; our atlas-specific keying and role-conditioned gating are BAMF-0.2 engineering inventions. \[R5\]

## Conditional motif memory {#conditional-motif-memory}

Atlas motif memory starts16384x128 FP32 and extends by16384-slot pages up to 65536 under the same allocation transaction. A key contains key-schema version, semantic release, frame schema/revision, ordered role/occurrence/canonical IDs or abstract type IDs, relation signature and scope. Try exact instance motif then structural motif. On a miss, retain the already factorized hidden representation and add no gated motif residual, as specified by EGM 22.11. Hashing only indexes candidates; compare full canonical key before returning a slot. Stable slots are append-only. Allocate at candidate preparation, never inside differentiable forward; publish allocations only with accepted generation. Read sites are frame input and after layer4 before AttnRes. Each site has its own128-\>768 projection and sigmoid gate initialized-4. Learned vectors, allocation manifest, usage counters needed for allocation, gradients, native AdamW state and release binding share custody. Telemetry-only read counters may be outside neural state and never change answers.

# 

# 9\. TURBOQUANT: STRUCTURE-AWARE CACHE COMPRESSION {#9.-turboquant:-structure-aware-cache-compression}

Make exact semantic packing the default codec for all eligible frame sidecars. Exact IDs, roles, frame schemas and provenance are never quantized. They are compact by construction.

For continuous working state, implement a separate versioned inference-cache codec using TurboQuant-style quantization of keys, values and secondary retrieval vectors. Target approximately 3.5 bits per channel for cold or offloaded inference caches, with uncompressed working tensors retained when a kernel requires them. Keep the codec reversible only in the operational sense of decoding an approximation; do not claim bit-exact recovery from lossy vectors. The source paper studies low-distortion vector and KV-cache compression, not semantic conservation. \[R6\]

The training student, retained checkpoints, candidate-scoring reference, gold labels and native AdamW remain FP32. The cache codec cannot become the source of gradients or replace a canonical checkpoint. A cache object includes exact model lineage, semantic release, frame compiler version, attention version, causal prefix and quantizer version. A mismatch invalidates the derived cache and triggers recomputation from its authoritative sources.

This places quantization on a clean economic boundary. We include the cache interface and a concrete first codec in the vNext delivery, but it is not a condition for the first optimizer update. The learning architecture does not have to change when the quantizer gets faster or gains a better MLX kernel. This is a firm engineering sequence, not an invitation to postpone an undefined research program.

## Concrete derived cache codec {#concrete-derived-cache-codec}

Derived inference-cache codec bamf.rot3/v1 groups32 vectors of headwidth24 into 768 scalar blocks, zero-pads only the tail, normalizes each24-vector to unit length and stores an8-bit relative norm plus one FP32 maximum norm per32-vector block, applies a fixed seeded24x24 orthogonal transform and quantizes each coordinate to8 fixed Lloyd-Max normal-codebook levels using 3 bits. Header pins codebook, transform, dimensions, true length, lineage, prefix and masks; norms and padding count toward measured effective bits. Use at least 256 vectors per record and at most 64 bytes of per-record codec metadata (shared manifest referenced out of band); smaller records stay FP32. Full blocks cost3.375 bits/channel plus amortized header, at most3.459 for256 vectors. Decode by inverse rotation and renormalization; the primary candidate evaluator uses uncompressed state. A cached inference response falls back to FP32 recomputation if typed-answer validation or declared score-drift tolerance fails. Initial acceptance is\<=3.5bits/channel for full blocks and measured max attention-output relative L2 error\<=0.10 on the named fixture, with exact chosen-answer agreement; keep FP32 for records failing the bound. This is a concrete derived codec inspired by TurboQuant, not a claim of reproducing all paper bounds.

# 

# 10\. THE SEMANTIC RELEASE AND FACTORY BRIDGE {#10.-the-semantic-release-and-factory-bridge}

The canonical source-to-student path is:

Pinned New Ithkuil source and native mathematical/Boolean source-oracles  
→ extracted source IR and admitted SKOS/RDF corpus  
→ canonical release digest plus coverage/conformance receipt  
→ ABI projection (\#292)  
→ typed AST semantic binding (\#293)  
→ prerequisite/lesson manifest (\#294)  
→ single-authority cutover (\#295)  
→ ordinary FactoryRelease and current admission owner  
→ atlas/frame compiler  
→ BAMF-0.2 neural student plus existing teacher.

FalkorDB is a derived projection of canonical RDF; its indexes accelerate read-only graph lookups, source exploration and compile-time neighborhood preparation. Its internal node IDs and traversal order never define model token identity. Use Akasha's read-only integration for cross-system semantic navigation rather than permitting graph writes in a neural lesson hot path. \[P5, P6\]

The schema compiler extracts only source-backed type and relation features. It respects root identity versus root-sense identity, multiple realizations, affix degrees, composition order and allomorph descriptions. It doesn't convert unrelated SKOS broader/narrower edges into lesson prerequisites. It does not reinterpret source position as developmental readiness. Held, blocked and proposed mappings remain held, blocked and proposed until formally admitted.

Admit only semantics that have exact source oracles, lawful answer modalities, explicit constituents, and valid progression prerequisites. Use the generic Factory, not a new grade-specific trainer. The SKOS corpus supplies a larger addressable candidate atlas now; student admission happens at its normal teacher/curriculum gate.

This produces a useful distinction:

* Available in SKOS: a source-grounded semantic concept with a stable address and provenance.  
* Active in the neural ABI: a bound, append-only local ID in an admitted release.  
* Taught: a capability with factory-approved source generation, prerequisites and assessment.  
* Mastered: a cumulative neural result sustained under the actual school's assessment and retention policies.

One stage never automatically implies the next.

# 

## Generative curriculum across SKOS {#generative-curriculum-across-skos}

One generative Factory compiles the eligible SKOS atlas and existing formal domains into capability definitions, typed construction programs, teaching choices, assessments and executable releases. \#292 owns ABI projection, \#293 AST identity, \#294 lesson manifest, \#295 authority cutover, \#296 the staged flywheel. These leaves supply their BAMF implementation deltas, not a parallel runtime. Enumerate the entire pinned corpus into ACTIVE/READY/HELD/EXHAUSTED coverage entries with reason and prerequisite links. Ready selection is topological and deterministic; introduce the smallest justified distinction, positively teach constituents, then composition. Source list order and broader/narrower edges alone do not define prerequisites. In one delta add1-9 capabilities and an initial admission budget of16 total new semantic identities including newly required constituents; recursively split a larger eligible closure into successive deltas. A changing semantic release is a new coverage epoch, not a reset. Reuse current prepare\_realized\_candidates/propose\_curriculum\_delta/admission functions. The16-ID budget is versioned admission policy, not a semantic capacity limit. Split a larger closure into constructive constituent releases, then the dependent capability; preserve already qualified larger source families through an explicit policy version rather than silently dropping their members. Freeze source\_eligible\_concept\_ids and required\_source\_family\_ids using source/rights/semantic qualification alone. Maintain separate source\_disposition and implementation\_status. SOURCE\_HELD means missing source meaning, unresolved mapping, incompatible rights or unqualified semantics; it records an exact source reason. IMPLEMENTATION\_UNCOVERED means source-qualified but lacking a constructor/checker/binding and remains mandatory delivery debt. ADAPTER\_READY, STAGED, ADMITTED, EXPOSED and QUALIFIED are implementation/learning states, not changes to source eligibility. The atlas compiler emits a required coverage row for every source-eligible concept and family before inspecting adapter availability. A08 must implement every required reusable family in that frozen census; new roots within a covered family are data, not new per-root tickets. Generic positive identity/definition/contrast fixtures cover source-defined concepts; operator/fact application fixtures use the declared formal or source-attested relation contract. Uncovered families may be bypassed by the scheduler while independent work runs, but COMPLETE\_ATLAS\_COVERAGE requires zero source-qualified implementation debt and every required coverage obligation met. Keep counts for source-held, implementation-uncovered, ready, exposed and qualified independently visible. The full-delivery receipt binds the frozen eligible census so unsupported code cannot shrink the denominator.

## Rosetta and Akasha integration {#rosetta-and-akasha-integration}

Use Rosetta v3 existing Observation, Frame, Conjecture, Evaluation and Run/Action/ToolCall/Receipt semantics with application namespaced envelopes. Keep CID content identity, stable RID and external XID separate. Akasha consumes immutable source/release/learner events through a local outbox, projects them into declared namespaces, and is rebuildable. \#297 owns domain/authority contracts; \#299/\#300 own release and run/evidence projection; \#301 recovery. Store source/effective/observed/recorded times where relevant. A live Falkor service is not a training dependency: compile neighborhoods into a release artifact and enqueue observations locally. Mutation remains with the source/run owners. PRIVATE\_REAL data stays outside public worktrees, CI, issue bodies and exports; \#327 protects the private pilot. PUBLIC\_FIXTURE development continues independently.

## Local correction and requalification {#local-correction-and-requalification}

Reusable transforms and contexts declare immediate input, operator, release, policy, time and rights dependencies. Maintain reverse direct edges. On correction, hold directly affected reusable artifacts, re-evaluate them, and propagate only when their output identity or eligibility changes. Retain immutable originals and scoped competing interpretations. A correction invalidating learned support marks the affected capability for focused requalification; it does not claim to erase weights by deleting a graph node. Reactivation requires current support and the same operational assessment contract. The outbox's eventID+payload digest makes duplicate delivery harmless and divergent duplicates explicit. Projection failure leaves the last good active pointer intact.

# 

# 11\. TRAINING POLICY: KEEP THE TEACHER WE’VE PAID FOR {#11.-training-policy:-keep-the-teacher-we’ve-paid-for}

Run the new student under the post-349 replay-salvaged Factory behavioral contract, not under the frozen \#324 v3 teaching policy. Keep proposal → realized delivered rows → staged outcome → cost evidence attached to each visit. The full observation chain must include actual support, rehearsal, mentor guidance, multi-fidelity probes, attempted and retained steps, and precise reason for acceptance or rejection. \[P4, P7\]

Use the current bounded active strategy bench, retaining up to 16 effective strategies with up to eight proven incumbents and rotating challengers. Exploit retained strategy evidence while maintaining bounded exploration. Preserve separate no-target-gain and destructive-interference histories so the teacher does not throttle a merely ineffective target as though it damaged prior knowledge. Retire a repeatedly inert strategy only under the corrected same-student rule, resetting that debt on a new accepted student checkpoint.

Retain the 2/4/8/16 optimizer-step lesson ladder. The existing shadow stop recommendation does not gain unapproved early-stop authority just because the new student is architecturally different; carry measured shadow evidence into the actual teacher epoch. Use the approved bounded vNext canary rather than unbounded speculative policy mutation. This reduces wasted trial cycles without corrupting the causal reading of what was delivered.

Keep whole-school and same-grade transfer screens, source-gold answers, student and optimizer custody, historical champion/soup authority, and correct fresh-cohort evaluation. Candidate retention remains independent of championship title fights. Historical 6-layer champions and frozen soups may contribute validated output-level advice where the existing teacher contract permits, but no direct parameter averaging with a 12-layer BAMF-0.2 student is allowed.

For progression, retain the currently approved evidence-based promotion thresholds and bind retries to actual checkpoint or scope advancement. The BAMF-0.2 teacher samples and rechecks all eligible grades by the same source-grounded prerequisites, measured learning needs, retention obligations and independent outcomes. No grade letter defines a scheduling quota, special recovery cadence or presumptive priority; incomplete mastery remains visible and governed by the same generic rules.

The operator's dashboard must keep the hard-won distinction between visits retained and actual learning. Show whole-school growth, G/RTN, retained optimizer steps, candidate acceptance, per-grade mastery/debt, target/protected effects, P(RET), teacher health, strategy use, and command/lifetime GRAD triplets. Add BAMF-0.2 frame-coverage, average atoms per neural position, fallback fraction, Engram hit/gate rate, expansion count, active semantic-ID count and VRAM/unified-memory pressure as supplementary diagnostics, not alternate graduation authority.

## Continual plasticity and optimizer clocks {#continual-plasticity-and-optimizer-clocks}

Include three rank8 residual adapters from initialization, one after each group selector: h'=h+(1/8)B\*SiLU(A\*RMSNorm(h)); A\[8,768\] seeded, B\[768,8\] zero. FAST group contains adapters, motif vectors/projections/gates and newly activated identity rows; SLOW contains established embeddings and dense/core parameters. Foundation mode updates all groups. Adaptive mode updates FAST each candidate and offers a FULL candidate after 8 accepted FAST candidates, or when the existing teacher requests foundational remediation. Rejection leaves both clocks and all state at the retained parent. Keep native AdamW arithmetic and selected hyperparameters; the optimizer owner maintains per-parameter update counts so inactive/new parameters receive correct bias correction. Inactive parameters and their moments are byte-identical across a FAST candidate. No background neural writes: all adaptation occurs inside the existing human-started serialized visit transaction. The cadence policy is explicit versioned data; no learned meta-optimizer is required for delivery. Define group\_eligible at candidate start and row\_participates for each optimizer step. Identity rows participate when gathered as visible input/feedback OR included among the step's legal tied output candidates; active softmax denominator rows therefore participate even when not input tokens. Motif rows participate only if actually gathered by either read site. Type/role/schema rows participate if gathered or in a legal role-output denominator. Dense modules participate when executed on a nonzero loss-bearing path. Update mask=group\_eligible AND row\_participates AND active-admitted. Mask gradients BEFORE computing the global clipping norm. Ineligible/unparticipating rows get no weight decay, moment update, count increment or age increment, even when another row in the same tensor is updated. A participating eligible row with zero numerical gradient still advances AdamW moments/count and applicable decay, because it participated in the objective; numerical cancellation is not a different training history. Skip the complete optimizer step only when there is no loss-bearing target. Parameter moments/counts advance on each candidate optimizer step; publish them only if that candidate is retained. Row establishment age is distinct: increment once per accepted candidate if that row had any actual masked optimizer step in the candidate, independent of its2/4/8/16 internal steps. At age 8 an identity row is established for the NEXT candidate. Candidate rejection preserves parent weights,m/v/counts,establishment ages and consolidation counters exactly. This participation policy is serialized in the optimizer identity. Start every fresh run in FOUNDATION. The immutable initial admitted FactoryRelease defines foundation\_capability\_ids. Transition to ADAPTIVE only at an accepted current-generation promotion sweep that enters the 92% gate, sustains 87% through one sweep of every introduced foundation semantic, and emits the existing promoted/promoted-with-debt receipt. C05 passes that exact receipt to B09 after candidate retention; B09 persists ModeTransition and resets accepted\_fast\_since\_full=0. This mode transition does not clear carried debt or fabricate a perfect championship. A new foundation admission after the transition remains ADAPTIVE, with its new rows FAST for their first 8 accepted participating candidates; teacher remediation can request FULL. In ADAPTIVE choose FULL whenever teacher requests it or accepted\_fast\_since\_full\>=8, otherwise FAST. An accepted FAST candidate increments that counter once; an accepted FULL resets it to0. Rejected scheduled/teacher FULL retains the counter and mode; a failed scheduled FULL is still due, while independent legal teacher strategies continue. FOUNDATION accepted/rejected candidates never increment the FAST counter. Cold resume reads these exact fields, not inferred grade labels or elapsed time. An operator may explicitly restore FOUNDATION via a versioned run-policy event; no silent mode switch occurs.

## Complete cognitive solver and typed outputs {#complete-cognitive-solver-and-typed-outputs}

Expose solve(input\_frame, task\_contract, generation, budget)-\>TypedAnswer plus bounded execution receipt. Eligible runtime mechanisms are exact source-visible role/identity lookup, explicitly registered deterministic functions, qualified cached transforms and neural composition/prediction. Build a typed dependency DAG; run independent pure CPU operations in ready sets and serialize MLX operations. A deterministic operator declares semantic input/output signatures, applicability, version, effect=PURE, and independent literal fixtures. The evaluator's answer labels, scoring oracle and held evaluation records are not runtime inputs. Exact operators may compute answers from the task inputs, including arithmetic. Score the complete solver identically for parent and candidate. Skip optimizer work on already-perfect capabilities; use failure-targeted lessons to improve routing, binding, composition and remaining errors. Neural-only scores are optional debugging views, never a delivery gate.

## Teacher, losses, retention and progression {#teacher,-losses,-retention-and-progression}

Reuse the replay teacher at d21797e72365bf93ea7cad3a4ef9020ec9817f23: up to16 strategies, up to8 incumbents, bounded challengers, checkpoint-local no-gain retirement after4 outcomes, separate destructive-interference accounting, every-fourth eligible existing-policy canary, and2/4/8/16 shadow probes. Actual early termination stays with its existing owner; the shadow ladder is observational. Preserve proposal-\>delivered rows-\>outcome-\>cost through \#333. Promotion starts at active-grade mean\>=92%, continues\>=87%, revisits each introduced semantic once, and re-arms only on changed retained checkpoint or introduced scope. BAMF-0.2 uses strictly grade-neutral source-qualified lesson and retest selection. No inherited Grade-B scheduling quota, debt-turn exception or grade-based preference applies; debt in every grade follows the same generic retained-learning and evidence rules. Teacher controls strategy, rehearsal and LR. Loss primary typed answer1.0; supervised optional auxiliaries role.10, epistemic-state.10, each Impact/Exigency/Novelty.05, frame/atomic consistency.05; missing labels mask the corresponding term. Native output semantics and existing whole-school retention remain intact.

## Salience and osmotic learning {#salience-and-osmotic-learning}

SÍ SÉ SON supplies three independent ordinal signals: UNKNOWN, LOW, MODERATE, HIGH, CRITICAL for Impact, Exigency and expectation-relative Osmotic Novelty. Attach source/evaluator and basis rather than a universal weighted sum. The teacher receives legal options with these features and retains HOW authority. Dispatcher ordering is: required correction/invalidated state; urgent relevant work; ready capability with demonstrated downstream unlock; novelty-guided exploration; normal fair frontier rotation. Break ties by age then stable ID. Aggregate event-\>cluster-\>pattern-\>trend at fixed local windows, preserving the underlying observations. A missing expected event differs from a reported negative event. Persistent repeated errors nominate procedure repair, not repeated identical lessons. Auxiliary heads only learn from explicit labels or measured outcome-derived labels; speculative scores do not mint source gold.

# 

# 12\. MODEL IDENTITY, CHECKPOINTS AND TOOLCHAIN {#12.-model-identity,-checkpoints-and-toolchain}

## 12.1 Introduce ModelTopologySpec v2, leave v1 readable {#12.1-introduce-modeltopologyspec-v2,-leave-v1-readable}

The v1 topology is too narrow for an atlas-native student. Add an explicitly versioned v2 structural record, with no silent reinterpretation of v1 checkpoints.

Proposed v2 record values:

* schema \= bilqis.mlx.model-topology/v2  
* architecture \= bamf-atlas-v2  
* layers \= 12  
* width \= 768  
* ffn\_dimension \= 3072  
* query\_heads \= 16  
* kv\_heads \= 8  
* attention\_query\_channels \= 384  
* attention\_kv\_channels \= 192  
* attention\_conv\_kernel \= 3  
* attention\_method \= ccgqa-causal-v1  
* position\_method \= rope-v1  
* rope\_base \= 10000  
* context\_positions \= 1024  
* depth\_residual\_method \= block-attnres-v1  
* depth\_groups \= \[4, 4, 4\]  
* embedding\_method \= factorized-atlas-v1  
* frame\_compiler\_method \= typed-frame-v1  
* frame\_global\_attention \= true  
* frame\_local\_expansion \= selective-v1  
* memory\_method \= atlas-engram-v1  
* memory\_slots\_initial \= 16384  
* memory\_width \= 128  
* semantic\_id\_capacity \= 8192  
* training\_dtype \= float32  
* optimizer \= native-adamw  
* seed \= operator-selected-fresh-run-seed

Persist the record as canonical JSON and hash it. Exact tensor shape, RoPE/CCGQA/AttnRes variant, model implementation digest, optimizer hyperparameters, embedding capacity and memory shape all bind to one lineage identity. Separate them from canonical semantic release, local active vocabulary, teacher policy epoch and input compiler version. On resume, compare every category before any neural-state mutation. This retains \#320's immutable topology principle while extending its schema honestly.

Treat altered neural computation, depth routing and memory geometry as a new lineage, not a silent resize of a trained historical student. For the growing semantic ABI, token indices remain append-only within the reserved table, and checkpoint/outbox provenance retains the exact active set at each generation. Do not import historical 6-layer optimizer moments or active championship ownership into a new 12-layer student.

## 12.2 Minimal source layout {#12.2-minimal-source-layout}

Use the existing Python packages and test-owning modules. A compact target layout is:

* bilqis\_mlx/runtime/model\_topology\_v2.py: structural schema, shapes and lineage readback.  
* bilqis\_mlx/semantic/atlas\_projection.py: canonical SKOS/ABI to typed features and deterministic semantic IDs.  
* bilqis\_mlx/semantic/frame\_schema.py: RoleSpec, FrameSchema, FrameInstance and source adapters.  
* bilqis\_mlx/semantic/frame\_compiler.py: causal pack, unpack, address, masks and receipts.  
* bilqis\_mlx/learning/frame\_embeddings.py: factorized embeddings and typed readout.  
* bilqis\_mlx/learning/atlas\_engram.py: motif keys, append-only slots, memory gates.  
* bilqis\_mlx/runtime/atlas\_attention.py: RoPE, causal convolutions, CCGQA SDPA.  
* bilqis\_mlx/runtime/block\_attnres.py: grouped depth routing.  
* bilqis\_mlx/runtime/atlas\_model.py: integrated differentiable forward and local expansion.  
* bilqis\_mlx/runtime/atlas\_training\_adapter.py: consume existing Factory batch/answer contracts.  
* bilqis\_mlx/presentation/atlas\_metrics.py: supplementary neural/frame-memory telemetry.  
* configs/models/bilqis-atlas-native-v1.json: operator-visible structural intent.  
* docs/operations/ATLAS\_NATIVE\_TRAINING.md: exact launch, resume and recovery commands.  
* docs/evidence/atlas-native/: bounded proof receipts and demonstration traces.

These are proposed ownership locations, not claims that the current repository contains them. Reuse existing code wherever its contract is already adequate; modules should be small, direct and reversible. No new heavyweight framework, server, database, or parallel curriculum stack is necessary.

## 12.3 Actual MLX implementation {#12.3-actual-mlx-implementation}

Keep mlx.core arrays, current optimizer state and the repository's existing checkpoint/outbox contract. Extend tensor-shape declaration once and derive initialization, loading, gradient construction and serialization from declaration. Use mlx.core.fast.rope and mlx.core.fast.scaled\_dot\_product\_attention for RoPE and GQA, with the CCGQA compressed projections and causal convolution assembled in Python/MLX. \[R1, R2\]

All model-owned parameters, including factorized embeddings, depth routers and conditional memory, participate in the same atomic candidate transaction and AdamW update. A rejected candidate discards all of their prospective changes. There is no second uncheckpointed memory learner, independent optimizer, or separately authoritative sparse table.

Use a single generation/checkpoint ID to bind student weights, native AdamW, active semantic ABI, model-topology record, frame compiler, motif memory allocation, teacher observation epoch, candidate-retention evidence and run journal. The existing recovery path reconstructs an all-or-nothing retained student, not a mixture of pre- and post-transaction components.

# 

## Durable generations and cold recovery {#durable-generations-and-cold-recovery}

Every generation binds topology/implementation, parameter-bank extents, active semantic ABI, frame compiler, all tensors, per-parameter AdamW moments/counts/hyperparameters, motif allocation, teacher epoch, source/rights/correction frontier, evaluation contract and outbox. Stage immutable bundles, force array evaluation, fsync files/manifest, then atomically promote one pointer using the existing checkpoints/boundary\_commit/data\_plane owners. Rejected candidates publish observational failure evidence but retain complete parent neural and allocation state. Cold resume validates digest/shape/version/ownership before writes. v1 historical readers remain; old runs are not coerced into v2. Model swap or parameter extension records an explicit generation transition and invalidates derived caches. Existing 100GiB default disk reserve remains; the blueprint's 30-50GiB is additional planning space, not a lowered runtime safety reserve.

## 12.4 Interface completion details {#12.4-interface-completion-details}

### 12.4.1 Shared input/output records {#12.4.1-shared-input/output-records}

AtlasRelease carries semantic digest, source/coverage digests, stable concept records, approved formal-domain bindings, relation data, held ledger and ABI allocation provenance. CompiledFrameBatch carries frame/atom positions, exact sidecars, role access, visible prefix maps, scope/padding masks, expansion handles and compiler digest. AnswerPlan carries the registered typed modality, legal output roles/values, dependency order and output budget. ModelOutput contains typed logits/values plus optional route/refinement diagnostics. CapabilityResult contains the validated final typed answer, selected operator versions, cost and immediate dependencies. CompleteStudent contains every tensor and state field named in the generation contract.

All boundary records use versioned dataclasses or existing typed owners, canonical JSON for receipts, stable enum values and explicit optional fields. External data is parsed once at the boundary. Pure internal functions consume validated records. Error codes extend bilqis\_mlx.errors under one BAMF family and include the failing field/expected identity/recovery action. Avoid generic opaque operator-contract errors when a precise field mismatch can be reported.

### 12.4.2 Parameter naming and initialization {#12.4.2-parameter-naming-and-initialization}

Use stable paths identity.bank.\<n\>, features.\*, frame.\*, blocks.\<i\>.\*, depth.\*, motif.page.\<n\>, motif.site.\<n\>.\*, plastic.group.\<n\>.\*, refine.\* and readout.\*. B01 carries the complete normative Tensor ledger below, including both generation extents and every auxiliary head. Initialize norm scales to1, biases only where explicitly declared, ordinary linear weights from the recorded seed and fan-in scale, causal convolution as an identity kernel, memory gates at-4, feature gates at-2, depth/refinement residual gains near0.01 and adapter output matrices at0. All parameters appear in checkpoint and optimizer enumeration.

### 12.4.3 Fast-state lifecycle {#12.4.3-fast-state-lifecycle}

A FAST candidate changes its eligible parameters, row moments and local clocks. A FULL candidate changes the entire current active tree. A row's optimizer count begins when that row first updates, even if the global run already has many steps. Rejection restores parent parameter and allocation state. The saved generation includes the counters selecting the next cadence so a restart cannot speed up consolidation or reclassify a fresh row prematurely.

### 12.4.4 Output construction and legitimate answer reuse {#12.4.4-output-construction-and-legitimate-answer-reuse}

A question asking for an input frame's action should use exact role lookup. A declared addition operator may calculate a sum directly. An unseen role/context composition can use the neural and exact operators together. The assessment oracle remains independently callable on its own inputs; hidden gold is never a field in a solver request. This boundary measures actual capability without penalizing efficient cognition.

# 

# 13\. HARDWARE AND RESOURCE ENVELOPE {#13.-hardware-and-resource-envelope}

## 13.1 Machines and ownership {#13.1-machines-and-ownership}

Primary execution: the existing Mac Studio M3 Ultra with 96 GB unified memory. It owns the sole serialized MLX/student lane and the authoritative run directory. The existing laptop (M3 Macbook Pro) may orchestrate code work, prepare source artifacts, review dashboards and run CPU-only checks. Its established SSH alias m3-ultra and a scoped tunnel can access the already configured FalkorDB service without relocating the graph or the student.

Keep FalkorDB as the derived SKOS/Akasha projection on its existing host. It provides compile-time graph reads and inspections. It must not enter the per-batch gradient hot path as an availability dependency.

Continue the existing maximum of two host-side deterministic source-preparation workers plus one sovereign neural lane. Source workers never receive writable model state, optimizer state, teacher selection authority or checkpoint pointers. The MLX lane serializes training, inference, retention decisions and publication of accepted generations. \[P2\]

## 13.2 Parameter and state estimate {#13.2-parameter-and-state-estimate}

For orientation, the previously calculated 12×768×16 full-MHA historical tensor geometry is approximately 85.2M parameters at a 222-token vocabulary and learned 96-position table. Replacing each block's full 768-wide Q/K/V attention with Q=384, K=192, V=192 and output 384→768 removes approximately 17.7M attention-projection parameters across 12 layers. Replacing the historical 222-token table with an 8,192-entry 768-wide reserved identity table adds approximately 6.12M parameters.

Removing learned absolute positions saves approximately 0.074M. Before factorized feature projections, frame encoder, depth routing and motif memory, that yields roughly 73.6M parameters. The initial 16,384×128 motif memory adds 2.10M. The complete BAMF-0.2 design therefore targets approximately 79–85M trainable scalars, with final exact total taken from the generated tensor-shape manifest.

At 80–85M FP32 parameters, weights occupy roughly 305–324 MiB. Weights plus two FP32 AdamW moments and gradients occupy roughly 1.2–1.3 GiB, before activation graphs, temporary candidate copies, mentor state, caches, corpus data and MLX allocator headroom. Actual training memory is dominated by optimizer-session state and intermediate activations, not by the reserved 8K identity table.

A 1,024-position FP32 KV cache for 12 layers, eight KV heads and 24 channels/head is approximately 18 MiB per sequence. At 256 frame positions it is 4.5 MiB. The historical 16-head/48-channel 1,024-position MHA counterpart is approximately 72 MiB. This is a 4× reduction from compressed head geometry and another 4× from complete four-to-one frame packing, for 16× on this specific derived KV-cache component. The frame sidecars, transient expanded constituents and other activation costs are additional. \[R2, R3\]

## 13.3 Resource allocation policy {#13.3-resource-allocation-policy}

Budget unified memory deliberately instead of using every available byte. A practical starting operating envelope on the 96 GB machine is: up to 48 GB for student training and candidate/activation state; approximately 8 GB for semantic graph and cache services; approximately 8 GB for CPU source-preparation and helper processes; approximately 12 GB for macOS, filesystem cache and background applications; and at least 20 GB of spare headroom. These are scheduling reservations, not enforced OS partitions.

Begin with the current short A/B/C lesson lengths, where 16–32 source rows per batch remain plausible. Scale long composed examples down to 1–4 rows per batch when they approach the 1,024-frame ceiling. Use the existing length-aware batch path and replace its historical 96-token reference constants with topology-aware budgets. Do not pad every example to 1,024 frames.

For storage, plan at least 30–50 GB free in addition to the existing run and source corpus. A complete 80–85M-parameter FP32 student plus its two AdamW moments is about 0.9–1.0 GiB before receipts, mentor copies and snapshot overhead. Keep lossless checkpoint generations for retained learning and follow normal compaction/archival rather than disposing of custody evidence.

No new GPU, paid inference provider, database license or hardware procurement is required for the first BAMF-0.2 training run. Existing local MLX and CPU workers carry the compute. Respect the project's low external-spend posture; vendor inference is optional engineering assistance, not a new per-lesson dependency.

## Hardware, batching and writer budgets {#hardware,-batching-and-writer-budgets}

Use the existing 96GB M3 Ultra, one sovereign MLX writer and at most 2 CPU deterministic preparation workers. Workers receive only source/release/seed packets, never writable model/optimizer/teacher state. Batch actual lengths; start32 short rows and reduce through16/8/4/2/1 as frame/constituent activation estimates approach the 48 GiB trainer envelope. Keep a stable deterministic batching plan per visit. Full1024-frame workloads begin1-4 rows. Default context 1024 applies to compiled neural positions, not raw atoms. MLX peak allocated/cache memory, preparation cost, accepted steps/hour, actual capability gain and disk reserve are visible. CPU checks run on either device; real MLX and learning acceptance run only on the Mac Studio lane.

# 14\. THREE BOUNDED DEVELOPMENT LANES {#14.-three-bounded-development-lanes}

Choose three bounded development lanes:

* Semantic/compiler lane: typed SKOS release bridge, role schemas, reversible packing, factorized atlas features.  
* Model/runtime lane: v2 topology, RoPE/CCGQA/Block AttnRes, frame encoder/expansion, AdamW/serialization.  
* Teacher/operations lane: Factory lesson adapter, existing teacher retention custody, telemetry, launch commands and resource tuning.

The lanes may investigate and write isolation-safe changes concurrently, but each shared feature branch has one verified writer/coordinated merge owner. Use the current repository's writer-coordination method. Avoid extra worktrees when ordinary source edits and a running imported Python process are already isolated; don't interrupt human training to make code modifications. The existing Factory/SKOS seams remain as observed. 

Suggested allocation: 6–8 cycles for release/typed-frame compiler, 5–7 for factorized embeddings and frame encoder, 7–10 for CCGQA/RoPE and MLX kernel integration, 4–6 for Block AttnRes, 5–7 for Engram memory and optimizer custody, 4–6 for Factory/teacher and SKOS admission plumbing, 3–5 for cache codec and dashboard, and 6–9 for integration, real disposable source lessons, documentation and the first owner-started training epoch. The main savings come from reusing the existing teacher, AST/source/oracle, FactoryRelease, checkpoint/outbox and SKOS compiler instead of recreating them.

## Detailed implementation plan {#detailed-implementation-plan}

### Three simultaneous workstreams {#three-simultaneous-workstreams}

Lane A, semantic/curriculum: source release, ABI banking, frame schemas/codec/compiler, features, exact operators, generated capability families, coverage frontier, evidence adapters and single-authority cutover. Default writer surface is new modules under semantics/, factory/ and source\_adapters/ plus their package tests.

Lane B, neural/runtime: topology, embeddings, frame encoder, attention, depth selection, local recurrence, motif memory, plasticity, typed readout, full forward, AdamW custody, checkpoint payloads and derived caches. Own new neural modules; shared checkpoint/student dispatch edits are proposed to Lane C.

Lane C, integration/teacher/operations: exact-head integration, teacher reuse, whole-system solve and assessment, admission, salience, resource management, corrections, projections, CLI/cockpit, packages, integrated learning proof and owner training runbook. It owns shared root documentation and the integration branch.

Each branch has one writer. A task can prepare pure functions against the frozen contracts while its dependency is under review, but its turn-in receipt names the actual consumed commit. Use separate lane worktrees only for actual concurrent writers. Serialize MLX proof runs on the Studio; concurrent CPU source/spec work is independent of the sole neural lane. Merge/promotion into main remains a separate owner action.

### Commit and handoff discipline {#commit-and-handoff-discipline}

A leaf ends with working code, focused tests, a fresh review disposition and a commit. Push the branch, verify the remote SHA, comment on its issue and lane PR, and update the PR Development section with the issue's closing keyword. A branch receipt, not an OPEN/CLOSED label alone, proves a prerequisite. Keep progress committed and continue the next ready leaf. After context compaction, rehydrate only the active issue, its amendments, direct prerequisite receipts and listed files. The workstack is a bookmark/dependency controller, not an invitation to reread the entire archive.

### EGM execution profile {#egm-execution-profile}

Use the pinned Google Elephant-Goldfish checkout. This delivery uses a noninteractive, artifact-first review because the owner explicitly authorized completing the work without questions. The Elephant resolves against the owner's chosen architecture. Fresh Goldfish reviewers reconstruct the design from these artifacts and named code sources, looking for missing definitions, contradictory interfaces, impossible dependencies and excessive execution burden. Every major/blocker receives a repair or evidence-backed contest. Review findings and resolutions are durable files.

During implementation, one fresh turn-in review covers a leaf or a cohesive batch of at most three. Findings name issue keys and files. One targeted repair/re-audit is normally enough; a remaining actual correctness defect keeps only that leaf open. Cosmetic preferences are recorded without blocking other work. Tests protect source correctness, gradient connectivity, causal visibility and complete recovery. They are not a factorial research program.

### Verification budget {#verification-budget}

Run python3 \-B scripts/run\_tests.py \<named test paths\> for the leaf. Add one small real integration witness at the owning boundary. Run npm run quality:check, npm run abi:verify and the applicable Factory/SKOS gates once per integrated boundary, reusing valid content-addressed evidence for unchanged mature source artifacts where the repository supports it. The integrated disposable learning witness uses at most64 attempted optimizer steps initially; a failure becomes a concrete bug to repair. No second model architecture is trained merely to explain which component deserved credit.

### Ready work {#ready-work}

Start A01, B01 and C01 in parallel. A's compiler/feature pipeline and B's attention/depth modules can advance independently against the fixed contracts. B02 joins A's feature/ABI outputs; C02 then joins the source and neural paths. C16 opens the durable student path after teacher/retention/custody/resource integration. The full atlas expansion, projections, caches and packages finish concurrently around that student.

## Workstream navigation {#workstream-navigation}

Lane A: [LANE\_A: \#342](https://github.com/Entif-AI/Bilqis-MLX/issues/342). 

Lane B: [LANE\_B: \#343](https://github.com/Entif-AI/Bilqis-MLX/issues/343). 

Lane C: [LANE\_C: \#344](https://github.com/Entif-AI/Bilqis-MLX/issues/344). 

Section 26 links every build outcome to its executable issue. Each issue contains the implementation prescription, relevant shared contracts, named tests, EGM handoff and branch turn-in rules.

# 15\. SEQUENCE: ONE STUDENT, NO MODEL TOURNAMENT {#15.-sequence:-one-student,-no-model-tournament}

The implementation follows small deliverable slices. Each slice ends in usable, reviewable software rather than a speculative essay, a matrix of competing models, or a weeks-long benchmark gate.

## Slice A. Lock release and frame contracts {#slice-a.-lock-release-and-frame-contracts}

Consume merged SKOS PR \#291 and the current post-349 Factory head in a dedicated, coordinated feature branch. Add ModelTopologySpec v2, exact frame/role schemas, stable semantic-ID projection, 8K reserved identity allocation and a reversible 64-bit four-slot fast codec. Add the read-only release-binding adapter that consumes the currently admitted Factory semantic manifests, while the wider SKOS bridge stays governed by \#292–\#295.

Deliverables: one immutable configuration; one typed four-slot example; one nested/repeated-role fallback; one exact round-trip; one release-aware occurrence address; one negative causal-boundary case. No new grade admission or neural mutation yet.

## Slice B. Build the real 12-layer model {#slice-b.-build-the-real-12-layer-model}

Implement factorized semantic features, frame encoding and constituent expansion; RoPE; causal compressed-convolution Q/K/V; 16Q/8KV fused SDPA; three four-layer Block AttnRes groups; and the typed tied-readout head. Generate every tensor shape from v2 topology and use existing MLX/native AdamW owners. First run a disposable creation and a single differentiable forward/backward update.

Deliverables: exact parameter-count receipt; finite gradients through embeddings, attention, depth routing and FFN; literal causal prefix check; checkpoint save/load that restores the same outputs and AdamW state; no mutation of old runs.

## Slice C. Add trainable memory and inherit the Factory {#slice-c.-add-trainable-memory-and-inherit-the-factory}

Implement 16,384×128 motif slots, deterministic exact-key allocation, append-only slot IDs, context gates and integration at frame input plus the first depth boundary. Bind the module to the one candidate transaction. Adapt existing source lessons, answer modalities, target-probe scoring, retention and teacher-observation envelopes to the frame compiler. Preserve the replayed strategy population and operator dashboard. Use a disposable A/B/C source-bound release for the first real learned updates.

Deliverables: memory included in gradient and checkpoint custody; exact lookup versus learned memory clearly separated; one retained and one rejected disposable candidate leaving the correct complete student state; trainer emits existing teacher observation records; no Oracle-to-student answer path.

## Slice D. Bind SKOS and operationalize resources {#slice-d.-bind-skos-and-operationalize-resources}

Complete or consume the \#292–\#295 release-to-ABI/AST/lesson bridge without inventing a second runtime. Build the read-only compile-time neighborhood/features adapter from canonical RDF/Falkor. Extend the model manifest and dashboard. Implement a TurboQuant-style derived cache codec for inference. Route long examples through adaptive batch sizing. Produce an operator-friendly single command for a fresh BAMF-0.2 run and one cold-resume command.

Deliverables: a source-pinned semantic release readback; one append-only new semantic-ID activation within the 8K table; unchanged historical indices; exact derived graph digest; a cache round trip within the declared approximate codec; source and optimizer limits visible to the operator.

## Slice E. Start the live BAMF-0.2 student (owner-initiated after slice D or once the A/B/C path of slice C is ready) {#slice-e.-start-the-live-bamf-0.2-student-(owner-initiated-after-slice-d-or-once-the-a/b/c-path-of-slice-c-is-ready)}

Create a new run directory. Record the exact BAMF-0.2 topology and current admitted A/B/C semantic closure before initialization. The human operator starts a bounded first session, inspects the teaching/retention/evaluation dashboard, and resumes for longer epochs if the first saved generation is intact. This is the student we intend to keep, not an expendable model-size contestant.

The first training wave consumes the constructive source-valid foundations in the current admitted FactoryRelease, including identification, Boolean and numeric capabilities where eligible. Its lesson and promotion path is compiled from typed prerequisites and current policy, never from a letter-ordered A/B/C script. Preserve source-gold generators, currently effective admission rules and whole-school safeguards. Expand to SKOS-derived admitted semantics only after the \#292–\#295 release bridge and the successor learning-authority gate permit the exact release. The SKOS corpus can be searched and compiled ahead of this admission event without being treated as curriculum gold.

## Training strategy derived from BRAVO {#training-strategy-derived-from-bravo}

Start the persistent student as soon as C16 is complete. Use a new run directory and a single fresh seed. Initialize zero AdamW moments for every learned component and pin the source-visible semantic closure. Read the currently admitted foundations and numeric ceiling from the release; the old frozen0..8 qualification workload is historical, not a global maximum.

### L0: acquire and use the foundations {#l0:-acquire-and-use-the-foundations}

Teach positive identity and existing direct Boolean/numeric constructions. COUNT, NUMBER, SUCCESSOR, ADD and SUB retain their prerequisite order; multiplication/division and larger scopes follow their released foundations. The exact plane is allowed to supply definitions and evaluate declared functions. The learned work is interpreting, selecting, composing, transferring and repairing the parts the current solver cannot already complete. Perfect source-visible operations do not waste neural trials. Actual incorrect or incomplete outcomes feed the teacher's existing semantic miss queue.

Use FULL updates during the foundation stage. Preserve old-grade rehearsal choices and target coverage under the teacher. Target fresh gain and whole-school preservation decide acceptance. Use current promotion hysteresis to open the next released tier, carrying imperfect semantics as debt. The student keeps learning rather than waiting for all older capabilities to be perfect.

### L1: expand through semantic structure and qualified evidence {#l1:-expand-through-semantic-structure-and-qualified-evidence}

Activate small prerequisite-closed additions from the complete pinned SKOS inventory. The source atlas may contain more concepts than the current ABI, and the ABI may contain more than the taught frontier. The coverage ledger shows each count explicitly. The Factory introduces1-9 related capabilities at a time, an initial budget of16 total new identities including newly required constituents, and emits ordinary releases. Source coverage grows by supported semantic family, not by handwritten root-specific runtime code.

BRAVO's evidence strata are independent feeders. Structured category summaries come first, then exact time/activity records, structured AM/PM reflections and qualified narrative spans. A qualified category subset can be taught while narrative work continues. The first public exercise uses synthetic/source-cleared fixtures preserving numeric, temporal, role and epistemic structure. Private journal ingestion uses its existing privacy owner and stays in private storage.

Introduce typed reconstruction, role binding, unit conversion, time relations, modality and source-bound ambiguity only when their prerequisites are available. English initially appears through explicit template codecs tied to the same semantics; a general free-form language interface can later consume those foundations without changing the learner identity.

### L2: deepen, specialize and adapt continuously {#l2:-deepen,-specialize-and-adapt-continuously}

The same run expands its banks and motif pages at accepted boundaries. Structural motifs support new fillers; repeated successful reasoning can become an exact procedure or cognitive package. ADAPTIVE mode updates the fast parameter group, with periodic teacher-compatible FULL consolidation. Retain whole-school assessments across the growing scope. Requalify affected learned capabilities after source corrections rather than pretending that deleting a cache erased parametric influence.

Increase task composition only within taught scope. Fresh role bindings, alternative forms, reversed relations, nested scopes and corrected premises supply meaningful capability challenges. Outcome gains, fewer repeated failures, lower useful-work cost and improved future reuse are the success signals. Internal mechanism attribution stays optional.

### L3/L4: expand resources and exchange capabilities when useful {#l3/l4:-expand-resources-and-exchange-capabilities-when-useful}

The local machine is sufficient for the initial release. Additional devices, rental GPUs, alternate network architectures and KAN implementations remain optional consumers of the same semantic contract. The delivered package exporter already supports sharing exact procedures and compatible plastic deltas, with semantic teaching packages for heterogeneous recipients. This is the immediate GNOSIS inheritance path, not a requirement to deploy a global swarm before local learning.

### Training-session operating loop {#training-session-operating-loop}

Preflight verifies source/active-set/topology/optimizer/space and the next candidate frontier. The owner starts a bounded or continuing human-run session. The runtime creates ordinary visits, records actual delivery, evaluates candidate effects, publishes complete accepted generations and automatically adopts eligible additions under the saved atlas lease. At a safe boundary it reports the exact stopping reason, current capability scope, debt and next work. Resume reconstructs the saved state and continues; it never silently resets the student, teacher or admission clock.

The useful daily questions are: Which previously unsolved source-valid tasks can the complete system now finish? Which old capabilities degraded? Which ready semantic additions unlock the most useful next work? Did a correction actually change subsequent behavior? How much accepted learning and solved work was obtained for the elapsed time and memory budget? The cockpit answers these without JSON archaeology.

# 16\. FIRST RUN AND OPERATING COMMANDS {#16.-first-run-and-operating-commands}

The concrete operator commands below are TARGET COMMANDS for the new code after ModelTopologySpec v2 and the atlas-native training adapter land. They are not executable against the present v1 forward.

Repository: existing Bilqis-MLX checked-out feature lineage, not a newly invented worktree. Config: configs/models/bilqis-atlas-native-v1.json. Run directory: runs/bilqis-atlas-native-v1. Source/ABI: current factory-admitted release, validated and bound on creation.

Preflight command:

`npm run train -- --dry-run --verify-source --model-topology configs/models/bilqis-atlas-native-v1.json --run-dir runs/bilqis-atlas-native-v1 --source-prefetch-workers 2`

Human-started first session:

`npm run train -- --human-run --model-topology configs/models/bilqis-atlas-native-v1.json --run-dir runs/bilqis-atlas-native-v1 --source-prefetch-workers 2 --minutes 30`

Subsequent session after successful saved boundary:

`npm run train -- --human-run --resume --run-dir runs/bilqis-atlas-native-v1 --source-prefetch-workers 2 --minutes 180`

The new code must confirm that the exact CLI spelling matches its parser before these commands enter the operating manual. A resume must read topology, active semantic release, frame compiler identity, memory slot state, optimizer and checkpoint before performing a neural update. The old 349 run and old \#324 frozen arms are never overwritten or imported into BAMF-0.2's weights.

Operator-facing milestones during the first week of actual training:

The student creates complete checkpoint/AdamW state and resumes without identity drift.

A, B and C capabilities are exposed through existing grade-neutral Factory manifests.

The teacher can retain source-grounded gains without sacrificing mature A/B skills.

The dashboard reports accepted updates, GREW, G/RTN, GRAD, P(RET), per-grade debt, semantic capacity and actual frame compression.

The curriculum progresses only when the admitted foundation earns it; the owner can compare fresh transfer with retained score growth without mining raw JSON.

# 

## Operator command contract {#operator-command-contract}

C16/C11 implement and parser-test these command forms before they become executable launch instructions:

npm run train \-- \--dry-run \--verify-source \\

  \--model-topology configs/models/bamf-0.2.json \\

  \--run-dir runs/bamf-0.2 \--source-prefetch-workers 2

 

npm run train \-- \--human-run \\

  \--model-topology configs/models/bamf-0.2.json \\

  \--run-dir runs/bamf-0.2 \--source-prefetch-workers 2 \\

  \--admission-policy atlas-release \--atlas-release-manifest \<approved-manifest\>

 

npm run train \-- \--human-run \--resume \\

  \--run-dir runs/bamf-0.2 \--source-prefetch-workers 2

The initial foundation command can omit the atlas lease and train only its current admitted release. The operator selects a session budget using the repository's supported time/visit switches. Resume uses saved topology, source, optimizer, teacher and lease. The new directory is distinct from current live and frozen qualification runs. These are implementation targets, not a statement that today's v1 parser already supports the BAMF fields.

# 

# 17\. CHOICES WE HAVE NOW MADE {#17.-choices-we-have-now-made}

We choose an atlas-native network from fresh initialization rather than retrofitting the old 6-layer model. No attempted direct weight soup across incompatible geometry.

We choose typed role cardinality, reversible four-slot packing and nested-frame fallback rather than enforcing one token per broad semantic category. Same-type occupants can coexist in different role slots.

We choose factorized embeddings and a source-derived graph feature compiler rather than using one unstructured token embedding as the only representation.

We choose compressed 16Q/8KV attention with 384 Q channels, 192 KV channels, three-token causal convolution and RoPE. We do not run a 12-head versus 16-head contest, and we do not start with an ordinary full-MHA historical model.

We choose Block AttnRes at three four-layer groups, with learnable type/frame-conditioned depth selection. We do not hard-code specific cognitive jobs to particular network layers.

We choose Engram-style memory from initialization, with exact atlas keys and learned vector content. The atlas is semantic authority; memory is a learning aid.

We choose native frame global attention plus selective constituent refinement and an atomic fallback. Exact symbolic reversibility is guaranteed by the compiler, while contextual neural representations are learned.

We choose to implement TurboQuant on derived inference/cache vectors and leave canonical FP32 student/AdamW untouched. This is an explicit tiering decision.

We choose to reuse the current teacher population, fresh support, source-gold, staged retention, champion/mentor evidence, and graduation diagnostics. We do not build a second teacher or grade-specific pathway for this architecture.

We choose a new successor learning-authority gate for BAMF-0.2 after replay salvage, while keeping \#324 v3 unchanged as a historical controlled specimen. Existing \#324 issue dependencies and SKOS cutover contracts are not silently waived by this review document. If the owner accepts the successor path, record the gating change in its controlling issue/spec before changing live Factory admission authority.

We choose to keep the model local on M3 Ultra, the graph as a derived read substrate, and the laptop as a source/build/orchestration helper. No cloud training contract or new hardware is prerequisite.

# 

## Owner decisions and reconciliation {#owner-decisions-and-reconciliation}

The 27 October instruction selects an aggressive single architecture and a capability-first build. It supplies the following scoped successor decisions.

Decision: One selected model  •  Implemented direction: Keep 12x768, 16Q/8KV, CCGQA, RoPE, three Block AttnRes groups, motif memory and FP32 AdamW  •  Durable owner:[B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346)through[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372)

Decision: Whole-system capability  •  Implemented direction: Runtime exact functions and sidecars are legitimate cognition; independent scoring checks the answer, not neural purity  •  Durable owner:[A07: \#353](https://github.com/Entif-AI/Bilqis-MLX/issues/353),[C04: \#373](https://github.com/Entif-AI/Bilqis-MLX/issues/373),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378)

Decision: Extensible education  •  Implemented direction: A/B/C initialize; the generated frontier covers the complete pinned eligible SKOS corpus and later approved releases  •  Durable owner:[A08: \#358](https://github.com/Entif-AI/Bilqis-MLX/issues/358),[A09: \#360](https://github.com/Entif-AI/Bilqis-MLX/issues/360),[C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380),[C14: \#386](https://github.com/Entif-AI/Bilqis-MLX/issues/386)

Decision: Successor gate  •  Implemented direction: Build the SKOS bridge and new model now; BAMF uses its own retained-learning/recovery witness  •  Durable owner:[C01: \#347](https://github.com/Entif-AI/Bilqis-MLX/issues/347),[C16: \#382](https://github.com/Entif-AI/Bilqis-MLX/issues/382), root \#341

Decision: Historical \#324  •  Implemented direction: Keep its frozen manifests and any results intact as a separate controlled specimen  •  Durable owner: \#324 and[C01: \#347](https://github.com/Entif-AI/Bilqis-MLX/issues/347)

Decision: Capacity without relearning  •  Implemented direction: 8192 initial semantic rows become the first append-only bank, with generation-bound expansion  •  Durable owner:[A02: \#348](https://github.com/Entif-AI/Bilqis-MLX/issues/348),[B02: \#359](https://github.com/Entif-AI/Bilqis-MLX/issues/359),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372)

Decision: Plasticity from initialization  •  Implemented direction: Three small adapters and explicit FAST/FULL update groups, native AdamW arithmetic and complete rollback  •  Durable owner:[B09: \#368](https://github.com/Entif-AI/Bilqis-MLX/issues/368),[B12: \#370](https://github.com/Entif-AI/Bilqis-MLX/issues/370)

Decision: First useful run  •  Implemented direction: Owner can start the admitted foundation path before graph projection, compression or private corpus completion  •  Durable owner:[C16: \#382](https://github.com/Entif-AI/Bilqis-MLX/issues/382)

Decision: Teacher continuity  •  Implemented direction: Consume replay \#340 and existing \#333 evidence; retain policy choices and current promotion/debt mechanics  •  Durable owner:[C03: \#376](https://github.com/Entif-AI/Bilqis-MLX/issues/376),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378)

Decision: Three parallel lanes  •  Implemented direction: Separate semantic, neural and integration branches; one writer per branch and one shared-file integrator  •  Durable owner:[C01: \#347](https://github.com/Entif-AI/Bilqis-MLX/issues/347)

The uploaded roadmap's CT-039A/G-03B rows still hold \#292-\#295 behind the old \#324 comparison. The successor decision above is recorded as an append-only amendment on the root and affected existing owners. Historical workbook rows remain provenance. Their BAMF successor dependency points to this delivery's exact-head learning/custody receipt. This avoids a circular dependency in which the new architecture must wait for a superseded architecture to demonstrate the capability it was designed to improve.

The owner-approved BAMF-0.2 teacher is grade-neutral. Historical grade-specific scheduler decisions are retained only in the older trainer's provenance, not imported as successor requirements. Promotion retains independently qualified entry/continuation behavior, while mastery, championships and carried debt remain separate measured outcomes.

The resource baseline keeps the existing 100 GiB disk reserve. The earlier blueprint's 30-50 GiB figure is extra working-space planning, not a replacement reserve. Neural module paths use the repository's existing semantics/ package, correcting the singular illustrative path in older prose.

# 18\. NON-NEGOTIABLE EXECUTION INVARIANTS {#18.-non-negotiable-execution-invariants}

Source truth and neural prediction are distinct. Typed source/AST/oracle generates the target and independently evaluates responses; the student never receives a hidden answer through an exact lookup path.

A role-addressable frame is lossless as a symbolic object. Its compressed learned neural state is not declared exactly invertible. The exact sidecar resolves concept identity, order, scope and provenance whenever detailed information is required.

No read from a derived graph or approximate memory can mint a new canonical concept. New identities and mappings must enter through admitted release contracts.

Every accepted candidate atomically advances weights, AdamW, trainable motif memory, active semantic identity, checkpoint and teacher evidence. Every rejected candidate preserves the complete retained parent, including memory state.

Causal position masks are applied to frame construction, compressed convolution, global attention, constituent expansion and memory retrieval. No future constituent may influence an earlier prediction.

The new architecture's selected path is not conditioned on a benchmark tournament. Engineering correctness checks are required because they protect meaningful, potentially long-running training investment. They cover shape and semantic identity, gradient connectivity, exact frame reconstruction, causal prefix behavior, source gold isolation, checkpoint/resume and no regression of the governing teacher/custody interfaces.

## Completion and useful outcomes {#completion-and-useful-outcomes}

Software completion requires a real 12-layer model, exact semantic/causal packing, finite connected gradients, functional motif and fast-state learning, complete save/rollback/resume, current teacher behavior, ordinary full-system assessment, generated semantic successors, append-only bank growth, usable commands, source-linked correction, derived cache fallback and a portable package/projection path. Each property has an owning issue and focused witness.

The first persistent training milestone is a saved generation that improves source-valid capability and resumes intact. Subsequent milestones measure the expanding admitted atlas, older-skill retention, new compositional capability, useful corrective transfer and operational cost. Full SKOS coverage is a continuing learner outcome with an explicit source census, not a synonym for building the compiler. Held source meanings remain visible work rather than silently counted as taught or mastered.

# 

# 19\. EXECUTIVE HANDOFF {#19.-executive-handoff}

Proceed with implementation on the current post-replay Factory feature stack, in a new coordinated BAMF-0.2 feature branch only if the existing writer ownership and dependency stack require it. 

Preserve both the frozen \#324 specimen and the current live student. 

First produce the exact frame compiler and v2 topology. Then implement the integrated neural model with Engram and AttnRes. Reuse teacher and source contracts.

Incorporate the merged SKOS corpus through a single versioned admission bridge. Start a human-owned new BAMF-0.2 student as soon as the bounded learning path is coherent.

The architectural thesis is a wager worth taking: exact semantics should let the network spend less capacity on reconstructing what is already known and more capacity on learning implications, compositional transfer and novel reasoning. 

We are investing in that advantage now, with one well-chosen model, a bounded local compute budget, and an implementation plan a solo builder plus agents can execute.

# 20\. ARCHITECTURAL ARCHAEOLOGY AND SYNTHESIS {#20.-architectural-archaeology-and-synthesis}

## Retained and amended mechanisms {#retained-and-amended-mechanisms}

The donor documents are design lineage. Their useful mechanisms are assigned to an existing owner in this build, so the archive changes what is shipped rather than merely enlarging a reading list.

Donor: Nested Learning / sparse memory notes  •  Gap filled: Local adaptation without rewriting all established competence  •  Selected integration: FAST/FULL groups, dedicated rank8 adapters, local update clocks, complete rollback  •  Owner: B09,B12

Donor: TRM integration / HRM reasoning notes  •  Gap filled: More computation for difficult constituent queries  •  Selected integration: Shared local recurrence, fixed input recall,0/1/2pass budget  •  Owner: B06

Donor: CTM integration  •  Gap filled: Temporal process and constructive ambiguity  •  Selected integration: Bounded iterative refinement and recorded contrast/noise signatures  •  Owner: B06,A11

Donor: Engram discussion  •  Gap filled: Repeated semantic structure consumes avoidable deep compute  •  Selected integration: Exact/structural motif keys, two gated learned reads, page growth  •  Owner: B07,B08

Donor: mHC/Birkhoff discussion  •  Gap filled: Controlled routing and normalized mixing  •  Selected integration: Shared normalized depth selector in the chosen Block AttnRes design  •  Owner: B05

Donor: Cognitive Tiles / Tapestries  •  Gap filled: Reusable exact meaning and computation  •  Selected integration: Role-addressable sidecars, transform manifests and correction edges  •  Owner: A03-A07,C09

Donor: GNOSIS0.4  •  Gap filled: Cognitive inheritance across model generations  •  Selected integration: Semantic package contract, fixtures, behavioral diffs, compatible deltas  •  Owner: C12

Donor: SÍ SÉ SON  •  Gap filled: Attention, urgency and useful assimilation  •  Selected integration: Three ordinal signals plus outcome-driven attention dispatch  •  Owner: C06

Donor: BRAVO  •  Gap filled: Source-to-curriculum and progressive real-world intake  •  Selected integration: Qualified evidence strata and one generic teaching pipeline  •  Owner: A08-A10,C14

Donor: Rosetta v3  •  Gap filled: Stable interoperability and interpretation lineage  •  Selected integration: Existing Core meaning, application extensions, exact source/run identities  •  Owner: A03,C10,C12

Donor: Akasha blueprint  •  Gap filled: Persistent queryable state without hot-loop dependence  •  Selected integration: Durable outbox, rebuildable projection, local invalidation  •  Owner: C09,C10

Donor: SmallThinker / KAN / AgentSociety  •  Gap filled: Local/specialist or population experimentation  •  Selected integration: Preserve package/substrate interface; no extra engine in the initial runtime  •  Owner: C12

Donor: Refract / AuPair / ReasoningBank  •  Gap filled: Reusing useful examples and procedures  •  Selected integration: Existing teacher choices, motif generalization, source-family contrasts  •  Owner: A11,B07,C03

Donor: Historical energy/KL proposals  •  Gap filled: Adaptation objectives and cooperative prioritization  •  Selected integration: Retain as research provenance; current selected optimizer/loss is explicit  •  Owner: B12,C06

The selected system has enough distinct machinery already. Each adopted donor addresses a specific gap: memory access, local depth, continual plasticity, reusable semantics or operational feedback. No second optimizer, second curriculum authority, duplicate graph or separate society simulator is added to deliver this version.

## Detailed older-source dispositions {#detailed-older-source-dispositions}

The archive contributes executable mechanisms. Each entry states the source locus, recovered decision, chosen implementation and the artifact that carries it forward.

Source and locus: CTM integration, May13-14 2025: Temporal Dynamics Integration; user's ambiguity/noise questions  •  Recovered ingredient: Thought unfolds over bounded internal time; preserve multiple interpretations and learn from controlled ambiguity  •  Concrete delivery: Shared recurrent refinement with input recall; replayable structural-noise signatures and alternative-set targets  •  Owner:[B06: \#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365),[A11: \#362](https://github.com/Entif-AI/Bilqis-MLX/issues/362)

Source and locus: Entif TRM Integration, filename20251012: recursion.py and implementation notes  •  Recovered ingredient: A small shared refiner updates a provisional state over repeated passes; task input stays accessible  •  Concrete delivery: In-process MLX refiner, same production model, explicit0/1/2budget; the former service wrapper is replaced by the existing runtime  •  Owner:[B06: \#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365),[B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369)

Source and locus: Cases Where I Was Proven Right: recursive reasoning, five-paper synthesis and Design Deep Dive appendix  •  Recovered ingredient: Separate computation depth from parameter count; inject original input and train bounded recurrence  •  Concrete delivery: Reused local weights, fixed source seed, variable training passes and visible compute cost  •  Owner:[B06: \#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365),[C08: \#374](https://github.com/Entif-AI/Bilqis-MLX/issues/374),[C11: \#384](https://github.com/Entif-AI/Bilqis-MLX/issues/384)

Source and locus: Synthesizing2025, sections1-3/7/10 and SEAL section  •  Recovered ingredient: Dedicated memory parameters, multi-timescale consolidation and persistent optimizer state  •  Concrete delivery: Three rank8 adapters, FAST/FULL groups, per-row clocks, transactional nativeAdamW  •  Owner:[B09: \#368](https://github.com/Entif-AI/Bilqis-MLX/issues/368),[B12: \#370](https://github.com/Entif-AI/Bilqis-MLX/issues/370),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372)

Source and locus: Nested Learning comparison, sectionsII-IV/VI/X  •  Recovered ingredient: Explicit propose/evaluate/consolidate lifecycle for parameter changes  •  Concrete delivery: Candidate state includes all plastic memory and clocks; accepted update commits one generation; rejected update preserves parent  •  Owner:[B12: \#370](https://github.com/Entif-AI/Bilqis-MLX/issues/370),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378)

Source and locus: Deep Dive, principles3 and section5  •  Recovered ingredient: Keep neural adaptation online through bounded reversible updates  •  Concrete delivery: Same human-started run learns continuously; the learner changes selected groups between durable snapshots  •  Owner:[B09: \#368](https://github.com/Entif-AI/Bilqis-MLX/issues/368),[C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380),[C14: \#386](https://github.com/Entif-AI/Bilqis-MLX/issues/386)

Source and locus: mHC/Engram conversation, January22 2026, sections1-5  •  Recovered ingredient: Stable learned mixing and cheap conditional retrieval are complementary  •  Concrete delivery: Existing selected depth selector receives normalized source weights; motif reads exploit exact/structural keys  •  Owner:[B05: \#355](https://github.com/Entif-AI/Bilqis-MLX/issues/355),[B07: \#356](https://github.com/Entif-AI/Bilqis-MLX/issues/356),[B08: \#366](https://github.com/Entif-AI/Bilqis-MLX/issues/366)

Source and locus: Synthesizing2025, MLACS/ReasoningBank/Tapestries sections  •  Recovered ingredient: Reuse transformations and structured examples instead of reconstructing everything  •  Concrete delivery: Exact operator DAG, applicability-keyed reuse, teacher exemplar provenance and portable capability exports  •  Owner:[A07: \#353](https://github.com/Entif-AI/Bilqis-MLX/issues/353),[C03: \#376](https://github.com/Entif-AI/Bilqis-MLX/issues/376),[C04: \#373](https://github.com/Entif-AI/Bilqis-MLX/issues/373),[C12: \#381](https://github.com/Entif-AI/Bilqis-MLX/issues/381)

Source and locus: HRM/SmallThinker/KAN/AgentSociety comparison: integration loci  •  Recovered ingredient: Separate local efficiency, compute depth, operator substrate and population behavior  •  Concrete delivery: Local learner and substrate-independent package interface; current build uses the selectedMLX body  •  Owner:[B06: \#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365),[C08: \#374](https://github.com/Entif-AI/Bilqis-MLX/issues/374),[C12: \#381](https://github.com/Entif-AI/Bilqis-MLX/issues/381)

Source and locus: GNOSIS0.4, sections0.8/0.15/13/15  •  Recovered ingredient: Cognitive inheritance, immediate-edge correction and receiver-owned adoption  •  Concrete delivery: Local correction index, versioned package+fixtures+behavioral diff; compatible deltas or semantic teaching package  •  Owner:[C09: \#377](https://github.com/Entif-AI/Bilqis-MLX/issues/377),[C10: \#383](https://github.com/Entif-AI/Bilqis-MLX/issues/383),[C12: \#381](https://github.com/Entif-AI/Bilqis-MLX/issues/381)

Source and locus: SÍ SÉ SON, sections9-12/18-20  •  Recovered ingredient: Consequence, urgency, expectation-relative novelty and subsequent behavioral assimilation  •  Concrete delivery: Separate salience outputs; aggregate trend/correction handling; teacher records changed future behavior  •  Owner:[C06: \#379](https://github.com/Entif-AI/Bilqis-MLX/issues/379),[C11: \#384](https://github.com/Entif-AI/Bilqis-MLX/issues/384),[C14: \#386](https://github.com/Entif-AI/Bilqis-MLX/issues/386)

Source and locus: BRAVO0.3.3, source strata and section11  •  Recovered ingredient: Developmental training bridges structured semantics to real qualified evidence  •  Concrete delivery: Generated prerequisite closure, independent strata feeders, typed reconstruction and continual expansion  •  Owner:[A08: \#358](https://github.com/Entif-AI/Bilqis-MLX/issues/358),[A09: \#360](https://github.com/Entif-AI/Bilqis-MLX/issues/360),[A10: \#361](https://github.com/Entif-AI/Bilqis-MLX/issues/361),[C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380),[C14: \#386](https://github.com/Entif-AI/Bilqis-MLX/issues/386)

Source and locus: Rosetta v3 Core and Akasha blueprint  •  Recovered ingredient: Stable identities, source/interpretation lineage, rebuildable derived state  •  Concrete delivery: Exact semantic/runtime envelopes, set-level eligibility, durable local outbox and read-only projections  •  Owner:[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349),[A13: \#354](https://github.com/Entif-AI/Bilqis-MLX/issues/354),[C09: \#377](https://github.com/Entif-AI/Bilqis-MLX/issues/377),[C10: \#383](https://github.com/Entif-AI/Bilqis-MLX/issues/383)

A donor mechanism is carried once into its owning component. The selected Block AttnRes module supplies normalized depth mixing; the build therefore does not require a second residual-routing architecture. NativeAdamW plus sparse groups supplies the first controllable plasticity mechanism; learned optimizer internals remain a versioned future option. Recurrent refinement is local and shared rather than a secondTRM/CTM service. Semantic packages preserve optionalKAN or alternate-device implementations without making them a prerequisite. These dispositions keep the archive's intent while concentrating the initial investment on one functioning learner.

# 21\. PREDECESSOR REQUIREMENT CONTINUITY {#21.-predecessor-requirement-continuity}

The crosswalk below preserves the intent and disposition of earlier BAMF and Entif cognitive requirements, with later source-backed contracts superseding exploratory alternatives.

The private expanded BAV engineering specification is preserved as a predecessor. This successor carries its24 requirement IDs into explicit implementation owners. The public table records engineering obligations and dispositions; the private source text and research crosswalk remain at their original access boundary.

Predecessor obligation: BAMF-REQ-001/002 single semantic authority and identity  •  BAMF-0.2 implementation owners:[A01: \#345](https://github.com/Entif-AI/Bilqis-MLX/issues/345),[A02: \#348](https://github.com/Entif-AI/Bilqis-MLX/issues/348),[A12: \#364](https://github.com/Entif-AI/Bilqis-MLX/issues/364)•  Continuity: Canonical source, preserved senses/indices, deterministic rebuild

Predecessor obligation: BAMF-REQ-003/004 reversible frames and64-bit codec  •  BAMF-0.2 implementation owners:[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349),[A04: \#351](https://github.com/Entif-AI/Bilqis-MLX/issues/351),[A05: \#357](https://github.com/Entif-AI/Bilqis-MLX/issues/357)•  Continuity: Exact role/occurrence/order; extended encoding after first bank

Predecessor obligation: BAMF-REQ-005 causal prefix  •  BAMF-0.2 implementation owners:[A05: \#357](https://github.com/Entif-AI/Bilqis-MLX/issues/357),[B04: \#350](https://github.com/Entif-AI/Bilqis-MLX/issues/350),[B06: \#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365),[B08: \#366](https://github.com/Entif-AI/Bilqis-MLX/issues/366),[B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369)•  Continuity: Same visibility through every path

Predecessor obligation: BAMF-REQ-006 Rosetta meaning/identity  •  BAMF-0.2 implementation owners:[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349),[A10: \#361](https://github.com/Entif-AI/Bilqis-MLX/issues/361),[C10: \#383](https://github.com/Entif-AI/Bilqis-MLX/issues/383)•  Continuity: Existing interpretation and trace semantics

Predecessor obligation: BAMF-REQ-007/008 topology andCCGQA  •  BAMF-0.2 implementation owners:[B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346),[B04: \#350](https://github.com/Entif-AI/Bilqis-MLX/issues/350),[B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369)•  Continuity: Same12x768/16Q/8KV body and two-matrixFFN

Predecessor obligation: BAMF-REQ-009 Block AttnRes  •  BAMF-0.2 implementation owners:[B05: \#355](https://github.com/Entif-AI/Bilqis-MLX/issues/355)•  Continuity: Shared Q/K/V/output projections and three context gates

Predecessor obligation: BAMF-REQ-010/011 motif and active semantics  •  BAMF-0.2 implementation owners:[B07: \#356](https://github.com/Entif-AI/Bilqis-MLX/issues/356),[B08: \#366](https://github.com/Entif-AI/Bilqis-MLX/issues/366),[A02: \#348](https://github.com/Entif-AI/Bilqis-MLX/issues/348),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372),[A13: \#354](https://github.com/Entif-AI/Bilqis-MLX/issues/354)•  Continuity: Initial capacities retained; explicit generation-bound expansion

Predecessor obligation: BAMF-REQ-012/013 local/dependency refinement  •  BAMF-0.2 implementation owners:[B06: \#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365),[C04: \#373](https://github.com/Entif-AI/Bilqis-MLX/issues/373)•  Continuity: 768-wide local state,192-channel attention,0/1/2passes and typed DAG

Predecessor obligation: BAMF-REQ-014 derived cache  •  BAMF-0.2 implementation owners:[B14: \#375](https://github.com/Entif-AI/Bilqis-MLX/issues/375)•  Continuity: Versioned approximate cache; canonicalFP32 preserved

Predecessor obligation: BAMF-REQ-015 Factory teaching  •  BAMF-0.2 implementation owners:[C02: \#371](https://github.com/Entif-AI/Bilqis-MLX/issues/371),[C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380),[C14: \#386](https://github.com/Entif-AI/Bilqis-MLX/issues/386)•  Continuity: Current foundations followed by full eligible atlas

Predecessor obligation: BAMF-REQ-016 rollback  •  BAMF-0.2 implementation owners:[B12: \#370](https://github.com/Entif-AI/Bilqis-MLX/issues/370),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378)•  Continuity: Complete weights, moments, clocks, allocations and source state

Predecessor obligation: BAMF-REQ-017 replay teacher  •  BAMF-0.2 implementation owners:[C03: \#376](https://github.com/Entif-AI/Bilqis-MLX/issues/376)•  Continuity: Exact replay-policy behavior and delivered evidence

Predecessor obligation: BAMF-REQ-018 salience  •  BAMF-0.2 implementation owners:[C06: \#379](https://github.com/Entif-AI/Bilqis-MLX/issues/379)•  Continuity: OrthogonalI/E/N with task-relative consequences

Predecessor obligation: BAMF-REQ-019 correction chronology  •  BAMF-0.2 implementation owners:[A11: \#362](https://github.com/Entif-AI/Bilqis-MLX/issues/362),[C09: \#377](https://github.com/Entif-AI/Bilqis-MLX/issues/377),[C13: \#385](https://github.com/Entif-AI/Bilqis-MLX/issues/385)•  Continuity: Planned/missing/negative/corrected/stale states distinguished

Predecessor obligation: BAMF-REQ-020 descendants  •  BAMF-0.2 implementation owners:[C09: \#377](https://github.com/Entif-AI/Bilqis-MLX/issues/377),[C10: \#383](https://github.com/Entif-AI/Bilqis-MLX/issues/383)•  Continuity: Immediate dependencies and scoped requalification

Predecessor obligation: BAMF-REQ-021 source-family independence  •  BAMF-0.2 implementation owners:[A10: \#361](https://github.com/Entif-AI/Bilqis-MLX/issues/361),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378),[C12: \#381](https://github.com/Entif-AI/Bilqis-MLX/issues/381)•  Continuity: Root lineage preserved across derivatives

Predecessor obligation: BAMF-REQ-022 resources/commands  •  BAMF-0.2 implementation owners:[C08: \#374](https://github.com/Entif-AI/Bilqis-MLX/issues/374),[C11: \#384](https://github.com/Entif-AI/Bilqis-MLX/issues/384),[C16: \#382](https://github.com/Entif-AI/Bilqis-MLX/issues/382)•  Continuity: ExistingM3Ultra; local compiled input; verified operator commands

Predecessor obligation: BAMF-REQ-023 history  •  BAMF-0.2 implementation owners:[C01: \#347](https://github.com/Entif-AI/Bilqis-MLX/issues/347),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372)•  Continuity: Old runs and frozen qualification remain intact

Predecessor obligation: BAMF-REQ-024 actual capability  •  BAMF-0.2 implementation owners:[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378),[C11: \#384](https://github.com/Entif-AI/Bilqis-MLX/issues/384),[C14: \#386](https://github.com/Entif-AI/Bilqis-MLX/issues/386)•  Continuity: Whole-system gains/retention and changed later behavior

The selected successor adds dedicated plastic parameters, append-only semantic banks, an explicit admission lease and complete-solver capability credit. Exact source-visible retrieval and computation are intended successful behavior. Scoring data stays in the evaluator; the task definition states what the solver may access. The first useful student gate is[C16: \#382](https://github.com/Entif-AI/Bilqis-MLX/issues/382); wider projections and compression complete without delaying that gate. The neural body, FP32 custody and source/teacher ownership are preserved.

# 22\. EGM-RESOLVED EXECUTION CONTRACTS {#22.-egm-resolved-execution-contracts}

These constraints are normative. They reconcile and strengthen the predecessor design against independent EGM readiness findings without altering the selected 12-layer/768-wide topology.

These selected contracts resolve the independent readiness findings. Each affected standalone issue repeats the applicable text.

## 22.1 Prefix-local refinement selection {#22.1-prefix-local-refinement-selection}

Refinement is a prediction-local computation. Let p be the query prediction boundary and V(p) the ordered frames with causal\_prefix\_end\<=p that passed context eligibility. Compute Fp=len(V(p)) and quota=min(32,ceil(Fp/8)) using only V(p). Rank requested-role matches, then source-visible salience, then stable source position within V(p). Refinement results are keyed by (input-generation,p,query-ID,frame-occurrence) and never overwrite a shared backbone hidden state used by an earlier prediction. Future frames, labels, row padding and future query requests do not enter selection. Parallel teacher-forced predictions each use their own p-local view. Derive recurrence choice from SHA256(run-seed,visit-ID,p,query-ID,frame-occurrence), never total batch length. Pass budget is 0/1/2 for the selected frame. Increasing a row from 8 to 9 complete frames can change the later query's quota but cannot change the earlier query at fixed p. The single backbone produces immutable causal hidden states; the small local refiner operates on prediction-specific copies.

## 22.2 Dependent typed-output state transition {#22.2-dependent-typed-output-state-transition}

AnswerPlan/v2 contains modalityID, input\_prefix\_end, ordered DecisionSpec records, allowedOutputSchema, maximum\_decisions\<=64 and generation binding. DecisionSpec=(id,roleID,occurrence,kind,legalValues,depends\_on). kind is VALUE, ROLE, CONTROL or EPISTEMIC. Topologically sort by dependency and then stable ID; cycles are input errors. Run the12-block backbone once on the source-visible prefix. Freeze memory H and each node's anchor h\_anchor (the last visible task-query position, or explicit input position from the task contract). For decision j, dependency feedback is the arithmetic mean of encode\_value of already committed parent decisions, zero for no parents. encode\_value(ConceptRef)=its768 identity embedding; a source-visible literal or structural action uses a deterministic768-dimensional signed SHA256 expansion of its canonical typed JSON, divided by sqrt768. A missing earlier dependency prevents execution. Compute s\_j=RMSNorm(h\_anchor+role768+sinusoidal\_occurrence768+W\_feedback\*feedback). Compute c\_j=Wout\*softmax((Wq\*s\_j)\*(Wk\*H)^T/sqrt192+visibility\_mask)\*(Wv\*H), and z\_j=RMSNorm(s\_j+c\_j). Q/K/V have192 inner dimensions; output and feedback are768-wide. Concept values use the active tied identity table. Other native modality values are a finite released legal-value list scored by dot(z\_j,encode\_value(value))/sqrt768. ROLE uses a128-dimensional query against the shared role table, masking to the schema's role/occurrence candidates. CONTROL uses four fixed outcomes EMIT\_VALUE,EMIT\_UNKNOWN,EMIT\_ALTERNATIVES,END\_FRAME. EPISTEMIC uses the released five-state classifier. Independent decisions may share one ready batch; dependent decisions wait for parent output commitment. During training only earlier parent targets enter feedback; the current target and descendants stay exclusively in loss. Inference feeds selected actual outputs, never target values. END\_FRAME is legal only after required roles have committed; output budget exhaustion returns an explicit partial/unresolved answer. No extra backbone call is needed: only this shared bounded decoder and local refinement run. Input positions plus output decisions must fit the declared1024 budget.

## 22.3 Stable factor IDs and exact graph channels {#22.3-stable-factor-ids-and-exact-graph-channels}

AtlasFeatures/v2 fixes three independent append-only maps typeID-\>row,roleID-\>row,schemaID-\>row. Row0 is UNKNOWN, row1 is NONE; initially allocate UTF-8-byte-sorted canonical IDs into rows2..511. Successor releases preserve every prior assignment and append new IDs in UTF-8 order to unused rows. Persist predecessor digest; a removed category remains reserved. For an overflow ID, retain its exact ID and encode E\_UNKNOWN+f128(ID), where f128 is SHA256 expansion: concatenate SHA256(UTF8('bamf.factor.v2\|'+kind+'\|'+ID+'\|'+decimal(block))) for blocks0..3; read the128 bytes and map each to (byte/127.5-1)/sqrt128. Multiple types are averaged, including explicit overflow features; unknown does not silently become another learned row. The64 graph channels are:0 admitted incoming-edge count;1 outgoing;2 outgoing broader;3 outgoing narrower;4 admitted type count;5 source form/allomorph count;6 attested sense count for the root;7 unresolved-mapping flag. Channels0..6 are min(log1p(count)/log1025,1), with count\>=0; channel7 is0 or1. Channels8..63 are signed hashed one-hop structure. For each admitted directed incident edge, emit one signature per declared neighbor type (or UNKNOWN): direction+'\|'+predicateCanonicalID+'\|'+neighborTypeCanonicalID. Sort these signatures as UTF-8, retaining multiplicity. For each signature s, hash SHA256(UTF8('bamf.graph.v2\|'+s)); channel=8+little\_endian\_uint64(hash\[0:8\])%56; sign=+1 if(hash\[8\]&1)==0 else-1. Add sign/max(1,N) where N is signature count. The fixed prefix supplies the projection seed; no random backend operation is involved. Empty graph channels are zero except source counts/flag. Public fixture with one type, no forms, no senses, no edges and no unresolved mapping has only channel4=log2/log1025, approximately0.099985920039; every other channel is0. Categorical overflow and hashes are features only; exact semantic identity remains in the sidecar.

## 22.4 Masking, clocks and row maturation {#22.4-masking,-clocks-and-row-maturation}

Define group\_eligible at candidate start and row\_participates for each optimizer step. Identity rows participate when gathered as visible input/feedback OR included among the step's legal tied output candidates; active softmax denominator rows therefore participate even when not input tokens. Motif rows participate only if actually gathered by either read site. Type/role/schema rows participate if gathered or in a legal role-output denominator. Dense modules participate when executed on a nonzero loss-bearing path. Update mask=group\_eligible AND row\_participates AND active-admitted. Mask gradients BEFORE computing the global clipping norm. Ineligible/unparticipating rows get no weight decay, moment update, count increment or age increment, even when another row in the same tensor is updated. A participating eligible row with zero numerical gradient still advances AdamW moments/count and applicable decay, because it participated in the objective; numerical cancellation is not a different training history. Skip the complete optimizer step only when there is no loss-bearing target. Parameter moments/counts advance on each candidate optimizer step; publish them only if that candidate is retained. Row establishment age is distinct: increment once per accepted candidate if that row had any actual masked optimizer step in the candidate, independent of its2/4/8/16 internal steps. At age 8 an identity row is established for the NEXT candidate. Candidate rejection preserves parent weights,m/v/counts,establishment ages and consolidation counters exactly. This participation policy is serialized in the optimizer identity.

## 22.5 Exact plasticity state machine {#22.5-exact-plasticity-state-machine}

Start every fresh run in FOUNDATION. The immutable initial admitted FactoryRelease defines foundation\_capability\_ids. Transition to ADAPTIVE only at an accepted current-generation promotion sweep that enters the 92% gate, sustains 87% through one sweep of every introduced foundation semantic, and emits the existing promoted/promoted-with-debt receipt. C05 passes that exact receipt to B09 after candidate retention; B09 persists ModeTransition and resets accepted\_fast\_since\_full=0. This mode transition does not clear carried debt or fabricate a perfect championship. A new foundation admission after the transition remains ADAPTIVE, with its new rows FAST for their first 8 accepted participating candidates; teacher remediation can request FULL. In ADAPTIVE choose FULL whenever teacher requests it or accepted\_fast\_since\_full\>=8, otherwise FAST. An accepted FAST candidate increments that counter once; an accepted FULL resets it to0. Rejected scheduled/teacher FULL retains the counter and mode; a failed scheduled FULL is still due, while independent legal teacher strategies continue. FOUNDATION accepted/rejected candidates never increment the FAST counter. Cold resume reads these exact fields, not inferred grade labels or elapsed time. An operator may explicitly restore FOUNDATION via a versioned run-policy event; no silent mode switch occurs.

## 22.6 Receiver-owned plastic-delta adoption {#22.6-receiver-owned-plastic-delta-adoption}

PlasticDeltaPackage/v1 contains base\_weight\_digest,parameter\_schema\_digest,semantic\_release,active-set digest,factor-map digest,motif-key-map digest,changed tensor/row slices with parent slice digests,delta bytes,source-rights manifest and fixtures. Import requires exact match of the receiver's base weights and all listed address/binding identities; no new bank or motif allocation is transported in a v1 delta. The receiver creates a local candidate from its full current generation and applies the delta only to declared slices. Reset m,v and optimizer-count to0 for changed slices; preserve all untouched receiver state. Reset changed identity-row establishment age to0; preserve all other row ages. Preserve the receiver's FOUNDATION/ADAPTIVE mode but reset accepted\_fast\_since\_full=0 upon successful import, recording origin=PACKAGE\_IMPORT rather than an accepted training visit. Keep recipient teacher strategy knowledge and rebind its checkpoint-local retirement epoch normally. Validate and compare the complete solver before publication, using the same native retention owner. On acceptance commit weights, reset optimizer slices, row ages, clocks and import receipt atomically. On rejection/crash preserve the receiver's complete original state. A sender optimizer is never silently merged. A subsequent native optimizer step operates on the receiver's reset/imported state; its receipt identifies the receiver generation, package and reset policy. A mismatch yields a semantic teaching package or held import, not approximate weight arithmetic.

## 22.7 Bounded typed route construction {#22.7-bounded-typed-route-construction}

TaskGoal/v1=(goal\_id,output\_signature,source\_visible\_bindings,expression\_or\_holes,allowed\_operator\_ids,budget). The source adapter lowers a typed task AST into an explicit acyclic expression/DAG; it does not receive evaluation labels. Node=(node\_id,operator\_id\_or\_hole,ordered\_operand\_refs,expected\_output\_signature,scope). Operand refs are input(frameOccurrence,role,occurrence), literal(typed source value), or result(previous\_node\_id). Maximum64 nodes, maximum depth8. Validate all refs, types, scope and cycles first. Exact bound nodes execute in topological order; memoization keys include full immediate dependencies. A hole declares candidate operators, candidate visible operand refs and constraints, never the correct candidate. Fill holes once through the B10 typed decoder from the single backbone call: emit operator choice and operand references as dependent typed decisions. If a hole has exactly one legal candidate after independent type/applicability checks, bind it deterministically; if multiple remain, neural selection is permitted and evaluated by downstream outcome. Each pure operator call consumes1 operation unit, including a failed applicability call; memoized hits consume a counted lookup but0 compute-operation units. Maximum64 output decisions bounds neural selections. No automatic speculative tree enumeration is added. Unknown/invalid binding returns UNRESOLVED with the unsatisfied signature; a qualified alternative may be used only within the same declared budget. Output receipts retain selected bindings and executed nodes. A legal source problem represented as ADD(MUL(2,3),4) deterministically executes two nodes and returns10. For a context needing learned participant binding, the typed DAG contains a hole followed by an exact function. The solver learns to connect existing operations without giving up its exact operations.

## 22.8 Full-atlas completion denominator {#22.8-full-atlas-completion-denominator}

Freeze source\_eligible\_concept\_ids and required\_source\_family\_ids using source/rights/semantic qualification alone. Maintain separate source\_disposition and implementation\_status. SOURCE\_HELD means missing source meaning, unresolved mapping, incompatible rights or unqualified semantics; it records an exact source reason. IMPLEMENTATION\_UNCOVERED means source-qualified but lacking a constructor/checker/binding and remains mandatory delivery debt. ADAPTER\_READY, STAGED, ADMITTED, EXPOSED and QUALIFIED are implementation/learning states, not changes to source eligibility. The atlas compiler emits a required coverage row for every source-eligible concept and family before inspecting adapter availability. A08 must implement every required reusable family in that frozen census; new roots within a covered family are data, not new per-root tickets. Generic positive identity/definition/contrast fixtures cover source-defined concepts; operator/fact application fixtures use the declared formal or source-attested relation contract. Uncovered families may be bypassed by the scheduler while independent work runs, but COMPLETE\_ATLAS\_COVERAGE requires zero source-qualified implementation debt and every required coverage obligation met. Keep counts for source-held, implementation-uncovered, ready, exposed and qualified independently visible. The full-delivery receipt binds the frozen eligible census so unsupported code cannot shrink the denominator.

## 22.9 First BRAVO evidence adapter and template {#22.9-first-bravo-evidence-adapter-and-template}

BamfEvidenceSnapshot/v1 is the application adapter payload for the existing \#326/\#328-\#332 source-stratum contracts, not a new Rosetta Core kind. It binds snapshotID,sourceManifestCID,sourceByteDigest,interpretationRevision,semanticRelease,rights={regime,purpose,allowedTraining},records\[\]. Each record is {recordID,actorRef:string,sourceSpan:{start,end},categoryRef,status:PLANNED\|COMPLETED\|UNKNOWN,reportedValue:{decimal:string\|null,unitRef},eventTime:{startISO:null\|string,endISO:null\|string,timeZone},observedAt,alternatives:\[\],adjudicationRef}. The exact source bytes and source-native field labels remain in the source manifestation. Category/unit references are resolved against the pinned admitted release before lesson compilation; public fixture labels are not minted as runtime meanings. Minimal PUBLIC\_FIXTURE source text is 'actor=actor\_01; category=study; status=completed; duration=0.25 h'; record fixture-001 sets actorRef=actor\_01 from the explicit source field and selects the admitted study category and hour unit, COMPLETED,decimal='0.25',null event times,observedAt='2026-01-01T00:00:00Z',allowedTraining=true, and cites the exact span0..len(source). Expected frame binds the source-visible actor handle to its released AGENT role, then category,status,reported-duration; a derived exact unit transform yields15 minutes with separate derivation. Literal templates: T1 '{actor} completed {category} for {value} {unit}.'; T2 '{actor} plans {category} for {value} {unit}.'; T3 '{actor} reported {category}; duration is unknown.' actorRef is an explicit source-visible opaque symbolic actor handle, never an inferred person. Bind it through the existing released AGENT role. The fixture renders T1 exactly as actor\_01 completed study for 0.25 h. Its generated PLANNED contrast renders T2 as actor\_01 plans study for 0.25 h. Its generated null-duration contrast renders T3 as actor\_01 reported study; duration is unknown. The initial questions are 'What category?', 'Planned or completed?', 'What reported duration?' and 'Convert the reported duration to minutes.' Their typed goal contracts select existing pure/semantic operators. Null duration produces UNKNOWN, zero produces0; contradictory dates produce alternatives and no invented chronology. Checker compares exact rational unit conversion and released role/status IDs. Missing/unadjudicated stratum emits its own source hold; qualified public records continue. English templates are deterministic peripheral realizations of the typed frame, not a free-form language model requirement.

## 22.10 First genuine learning target and advance rule {#22.10-first-genuine-learning-target-and-advance-rule}

The foundation witness uses a constructive three-actor episode-binding family from admitted typed role and numeric/time primitives. Each visible input has actors A,B,C and two source-visible events per actor; a query supplies an explicitly introduced relation cue that chooses a role binding, then asks for that actor's later event duration or the sum of two visible durations. The source generator constructs all role bindings and an independent checker computes the answer. The runtime receives a TaskGoal DAG with a typed candidate-binding hole followed by the existing exact duration/add operator; it receives all input facts and legal exact tools, but not the correct binding as metadata. Teach constituents/role cue first, then the composition. Probe64 generated tasks from seeds0..63 at depth1 before training; measure the whole solver's genuine deficits. If all pass, advance deterministically to depth2,3,4 with additional admitted relation compositions, then continue the next prerequisite-ready family from A09. Select the first measured failing family, reuse the replay teacher, and allow up to64 attempted optimizer steps for the bounded witness, scoring fresh seeds64..127 and the existing retention cohort. A true retained gain must improve complete-solver performance; an exact successful route earns full credit and is never disabled to force a neural update. If all presently admitted families are already perfect, stage the next source-qualified family; the run records ALL\_ADMITTED\_CAPABILITIES\_SOLVED and awaits its ordinary admission rather than inventing failure. C16's retained-update acceptance remains open until an actual new gap is learned; solved-capability progress is still recorded. A synthetic destructive candidate used only to test rollback may perturb a disposable copy and must never contaminate the retained live lineage.

## 22.11 Normative complete tensor ledger {#22.11-normative-complete-tensor-ledger}

All matrices are stored\[out,in\]; row tables are\[num\_rows,channels\]. Every listed tensor is FP32. All omitted biases are absent, not implementation options. Linear(x,W)=x@W.T. RMSNorm means x\*rsqrt(mean(x\*x)+1e-5)\*scale. Norm scale tensors initialize1. M means independent Normal(0,1/sqrt(in\_features)); E means Normal(0,0.02^2); Z means0; O means1. Seed each tensor/row from the first8 bytes(little endian) of SHA256(UTF8('bamf.init.v2\|'+decimal(run\_seed)+'\|'+stable\_parameter\_path+'\|'+canonical\_row\_ID\_or\_empty)). Use NumPy Generator(PCG64(seed)).standard\_normal in float64 and cast once to float32; persist the initialization manifest. Default run\_seed=0; an operator-selected seed is run identity. Existing row initializers never depend on new bank count or enumeration order. Identity rows use the released factor sum plus N(0,0.001^2) and inactive rows remain0 until admitted; their feature compiler/source binding is recorded. Motif rows use E on accepted allocation. GenerationExtents=(semantic\_bank\_count,motif\_page\_count,active\_semantic\_digest,motif\_key\_map\_digest,factor\_map\_digest). expected\_bamf\_shapes(spec,GenerationExtents) consumes both variable extents, not only vocabulary size.

Stable tensor path / expansion: identity.bank.b, b=0..bank\_count-1  •  Shape: \[8192,768\]  •  Initialization: source-factor plus row-seeded residual; inactive0  •  Update group: FAST until row age8, then SLOW

Stable tensor path / expansion: features.type / role / schema  •  Shape: each\[512,128\]  •  Initialization: E; NONE row1=0,UNKNOWN row0=E  •  Update group: SLOW

Stable tensor path / expansion: features.project\_type / project\_role / project\_schema  •  Shape: each\[768,128\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: features.project\_graph  •  Shape: \[768,64\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: features.gates  •  Shape: \[4\]  •  Initialization: each-2  •  Update group: SLOW

Stable tensor path / expansion: features.local\_slot  •  Shape: \[16,768\]  •  Initialization: E  •  Update group: SLOW

Stable tensor path / expansion: features.norm  •  Shape: \[768\]  •  Initialization: O  •  Update group: SLOW

Stable tensor path / expansion: frame.query\_schema  •  Shape: \[192,128\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: frame.member\_key / member\_value  •  Shape: each\[192,768\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: frame.interact\_query / interact\_key / interact\_value / interact\_output  •  Shape: each\[192,192\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: frame.interact\_norm  •  Shape: \[192\]  •  Initialization: O  •  Update group: SLOW

Stable tensor path / expansion: frame.project\_output  •  Shape: \[768,192\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: frame.project\_summary  •  Shape: \[768,128\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: frame.pool\_gate  •  Shape: \[1\]  •  Initialization: \-2  •  Update group: SLOW

Stable tensor path / expansion: frame.empty\_seed  •  Shape: \[768\]  •  Initialization: E  •  Update group: SLOW

Stable tensor path / expansion: frame.norm  •  Shape: \[768\]  •  Initialization: O  •  Update group: SLOW

Stable tensor path / expansion: blocks.i.attn\_norm / ffn\_norm, i=0..11  •  Shape: each\[768\]  •  Initialization: O  •  Update group: SLOW

Stable tensor path / expansion: blocks.i.query  •  Shape: \[384,768\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: blocks.i.key / value  •  Shape: each\[192,768\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: blocks.i.output  •  Shape: \[768,384\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: blocks.i.conv\_q  •  Shape: \[384,3\]  •  Initialization: each channel\[0,0,1\] oldest-\>current  •  Update group: SLOW

Stable tensor path / expansion: blocks.i.conv\_k / conv\_v  •  Shape: each\[192,3\]  •  Initialization: each channel\[0,0,1\]  •  Update group: SLOW

Stable tensor path / expansion: blocks.i.ffn\_in / ffn\_out  •  Shape: \[3072,768\] / \[768,3072\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: depth.norm  •  Shape: \[768\]  •  Initialization: O, shared across all sources/queries/boundaries  •  Update group: SLOW

Stable tensor path / expansion: depth.query / key / value  •  Shape: each\[128,768\]  •  Initialization: M, shared across3 boundaries  •  Update group: SLOW

Stable tensor path / expansion: depth.output  •  Shape: \[768,128\]  •  Initialization: M, shared  •  Update group: SLOW

Stable tensor path / expansion: depth.gate.k.vector / bias, k=0..2  •  Shape: \[768\] / \[1\]  •  Initialization: Z / log(1/9)  •  Update group: SLOW

Stable tensor path / expansion: motif.page.b, b=0..page\_count-1  •  Shape: \[16384,128\]  •  Initialization: E for allocated rows,0 otherwise  •  Update group: FAST

Stable tensor path / expansion: motif.site.k.projection, k=0..1  •  Shape: \[768,128\]  •  Initialization: M  •  Update group: FAST

Stable tensor path / expansion: motif.site.k.norm  •  Shape: \[768\]  •  Initialization: O  •  Update group: FAST

Stable tensor path / expansion: motif.site.k.gate\_hidden / gate\_feature / bias  •  Shape: \[768\] / \[128\] / \[1\]  •  Initialization: Z / Z / \-4  •  Update group: FAST

Stable tensor path / expansion: plastic.group.k.norm, k=0..2  •  Shape: \[768\]  •  Initialization: O  •  Update group: FAST

Stable tensor path / expansion: plastic.group.k.A / B  •  Shape: \[8,768\] / \[768,8\]  •  Initialization: M / Z  •  Update group: FAST

Stable tensor path / expansion: refine.norm  •  Shape: \[768\]  •  Initialization: O  •  Update group: SLOW

Stable tensor path / expansion: refine.query / key / value  •  Shape: each\[192,768\]  •  Initialization: M, shared for both passes  •  Update group: SLOW

Stable tensor path / expansion: refine.output  •  Shape: \[768,192\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: refine.gate\_vector / bias  •  Shape: \[768\] / \[1\]  •  Initialization: Z / log(1/9)  •  Update group: SLOW

Stable tensor path / expansion: refine.route / route\_bias  •  Shape: \[3,768\] / \[3\]  •  Initialization: M / Z  •  Update group: SLOW

Stable tensor path / expansion: readout.state\_norm / output\_norm  •  Shape: each\[768\]  •  Initialization: O  •  Update group: SLOW

Stable tensor path / expansion: readout.query / key / value  •  Shape: each\[192,768\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: readout.output / feedback  •  Shape: \[768,192\] / \[768,768\]  •  Initialization: M  •  Update group: SLOW

Stable tensor path / expansion: readout.role\_query  •  Shape: \[128,768\]  •  Initialization: M; scores shared features.role table  •  Update group: SLOW

Stable tensor path / expansion: readout.control / control\_bias  •  Shape: \[4,768\] / \[4\]  •  Initialization: M / Z  •  Update group: SLOW

Stable tensor path / expansion: readout.epistemic / epistemic\_bias  •  Shape: \[5,768\] / \[5\]  •  Initialization: M / Z  •  Update group: SLOW

Stable tensor path / expansion: readout.salience.a / salience\_bias.a, a=impact,exigency,novelty  •  Shape: each\[5,768\] / \[5\]  •  Initialization: M / Z  •  Update group: SLOW

There is no independent learned semantic readout matrix: concept logits reuse identity.bank.b. Native Boolean/numeric finite answer candidates use their registered typed value encodings and shared readout state. EPISTEMIC output order is SUPPORTED,CONTRADICTED,UNRESOLVED,UNKNOWN,NOT\_APPLICABLE under the application's released label binding; these are assessment labels, not new Rosetta Core meanings. Salience order is UNKNOWN,LOW,MODERATE,HIGH,CRITICAL. Features.norm is shared at factor-composer calls. Stateless sinusoidal positions, canonical SHA256 literal features and all masks are nontrainable and are explicitly listed in the manifest's constants section.

FrameEncoder's precise pass is: u\_m=Linear(member\_m,frame.member\_value); q0=Linear(schema128,frame.query\_schema); k\_m=Linear(member\_m,frame.member\_key); a=softmax(q0\*k^T/sqrt192+member\_mask); p=a\*u. For cross-role interaction form U=stack(u\_m), apply single-head self-attention using frame.interact\_query/key/value/output, add U and RMSNorm with frame.interact\_norm to obtain V. Re-pool V with the same a. output=RMSNorm(Linear(p+sigmoid(pool\_gate)\*(a\*V),frame.project\_output)+Linear(mean(schema128,mean\_role128),frame.project\_summary),frame.norm). Empty legal structural nodes use frame.empty\_seed plus the schema summary. All means exclude absent/masked entries and return the explicit NONE feature when empty; atomic fallback preserves its atom vector unchanged.

Motif site gate is sigmoid(dot(gate\_hidden,RMSNorm(h))/sqrt768+dot(gate\_feature,mean(type128,role128,schema128))/sqrt128+bias). A valid slot emits h+gate\*Linear(slot128,projection); a miss returns h unchanged because factorized features are already in h. The local refiner uses q=Linear(RMSNorm(state+immutable\_seed+role768),query), k/v from the eligible constituent embeddings, then state'=state+0.1\*sigmoid(dot(gate\_vector,RMSNorm(state))+bias)\*Linear(attention(q,k,v),output). route logits are optional auxiliary diagnostics until a versioned routing policy explicitly consumes them; default selection remains the fixed prefix-local rule. Register those heads and provide labelled fixtures for their gradient tests.

No additional trainable tensor may be silently created by a convenience layer. B01's literal ledger expands the stated indices into ParameterSpec objects. Constructor, shape validator, optimizer registry, save/load and parameter-count check all consume that same list. Norm/bias parameters receive no weight decay; M/E weights follow the current selected AdamW decay. Conditional participation still determines whether any eligible tensor is updated.

# 23\. LINKED IMPLEMENTATION SPECIFICATIONS {#23.-linked-implementation-specifications}

Each leaf below is a compact, linked execution entry. The full source-backed issue specification remains authoritative at its GitHub issue, with prescribed implementation behavior, dependencies, tests, EGM review and turn-in receipts.

## Lane A {#lane-a}

### [A01: \#345](https://github.com/Entif-AI/Bilqis-MLX/issues/345)\| Compile the pinned SKOS release into the BAMF semantic authority snapshot {#a01:-#345|-compile-the-pinned-skos-release-into-the-bamf-semantic-authority-snapshot}

Depends on: Ready to start.

Deliver: Read the canonical release produced by \#291 and verify its source, coverage and RDF digests. Emit stable concept records, admitted types/relations, morphology/sense distinctions, source loci, held mappings and canonical ordering. Preserve root versus Stem x Specification sense identities; emit allomorph/form variants as realizations, not duplicate meanings. Retain the existing formal Boolean/numeric source owners with explicit domain bindings. Derive ABI entries in the prior accepted ordering followed by canonical new-ID ordering. Persist atlas.json, concepts.jsonl, relations.jsonl, held.jsonl and a content-addressed manifest using the repository canonical serializer. Count source rows, RDF terms, semantic concepts, active ABI indices and trainable capabilities separately. Attach an explicit reason to every corpus item that is not yet a teaching candidate. Complete \#292's projection contract through this leaf rather than implementing a second registry. The graph materialization receipt may witness the same digest, but canonical RDF/IR bytes supply the build. Expose a pure read API so neural workers consume a frozen snapshot without a database. Predecessor trace: BAMF-REQ-001/002; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Two clean builds from the same pinned release have identical digests. A literal root with two source-attested senses stays two senses. A held mapping stays held and absent from active indices. Reordering input files does not renumber prior indices. A stale coverage receipt yields an explicit source-owned error before output promotion. Record the real corpus census and one formal-domain binding; do not substitute an empty toy atlas for the corpus build.

### [A02: \#348](https://github.com/Entif-AI/Bilqis-MLX/issues/348)\| Implement append-only semantic banks and active-vocabulary allocation {#a02:-#348|-implement-append-only-semantic-banks-and-active-vocabulary-allocation}

Depends on:[A01: \#345](https://github.com/Entif-AI/Bilqis-MLX/issues/345),[B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346),[A06: \#352](https://github.com/Entif-AI/Bilqis-MLX/issues/352).

Deliver: Represent global ABI indices as bank\*8192+offset and keep a stable full-ID map. Start one bank; append another only when qualified admissions exceed existing capacity. Activation within a reserved bank initializes the row from its source features and creates zero moments/count0; inactive rows are not trained through tied softmax. Expansion binds previous generation, allocation-source digest and admitted IDs. Prepare tensors, active mask, output-domain map and registry-mirror delta together, then pass them to the existing admission transaction. Preserve all old row bytes and optimizer state. When count exceeds65535, uint32 extended indices continue without an address-codec redesign; validate uint32 bounds. Full output logits are the ordered concatenation of active bank projections, never a modulo alias. Mirror admitted token descriptions and allocation lineage into the existing Registry evidence/export contract; a spreadsheet remains a navigable mirror, not an independent semantic registry. Provide a resource estimate before materializing new banks and stage until it fits. Predecessor trace: BAMF-REQ-011; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Exercise indices 8191,8192 and 16384\. Existing rows/moments hash identically before and after accepted extension; inactive logits cannot win. Simulate rejection and crash before pointer publication and recover the exact old bank extent. A stable meaning receives the same index under source reordering; duplicate/mismatched meaning blocks only the new admission. Verify the tied readout and registry mirror have the same active set.

### [A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349)\| Bind typed AST semantics to role-addressable frame contracts {#a03:-#349|-bind-typed-ast-semantics-to-role-addressable-frame-contracts}

Depends on:[A01: \#345](https://github.com/Entif-AI/Bilqis-MLX/issues/345).

Deliver: Define frozen typed records with schema versions and canonical serialization. Reuse existing AST constructors and approved operator meanings. Introduce FrameInstance occurrence IDs derived from source-instance identity plus structural path, separate from canonical content digest. Use (role\_id,occurrence\_index) keys and explicit parent/child edges. Specify NONE, UNKNOWN and unresolved alternative bindings through declared typed states, not absent dictionary keys. Validate role counts, allowed types, scope and declared causal prefix. Preserve atomic fallback for AST constructs lacking an approved frame schema. Create released adapters for current A/B/C source ASTs without branching the trainer by grade. Bind each new schema to actual source rules; an executable formal operator may have a formal-domain schema when a New Ithkuil realization is not yet admitted. Return typed errors through the existing error catalog with source span and failed role. Predecessor trace: BAMF-REQ-003/006; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Literal TRANSFER fixtures swap agent/recipient and yield different bindings/content IDs. Repeated same-type members in distinct roles survive. Singular-role duplication fails; explicitly plural role with occurrence0/1 succeeds. Nested negation/scope round-trips without flattening. Unknown schema takes the atomic fallback with all source data preserved. A foreign semantic-release ID fails before neural use.

### [A04: \#351](https://github.com/Entif-AI/Bilqis-MLX/issues/351)\| Build the reversible four-slot frame codec and extended fallback {#a04:-#351|-build-the-reversible-four-slot-frame-codec-and-extended-fallback}

Depends on:[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349).

Deliver: Implement exact shifts/masks from the frame contract using integer operations. Validate ranges before packing, reserve version1 and record complete presence1111. Keep schema tag lookup release-local and content-addressed. Serialize the u64 in little-endian8 bytes with an explicit codec identifier; JSON may expose its decimal string to avoid floating-point loss. Encode all other frames in extended canonical slot arrays with uint32 indices, child references and occurrence metadata. Select fallback by a typed disposition, never by catching arbitrary exceptions. Use the same exact role-index accessor for both representations so downstream neural code is codec-neutral. Include original constituent order and full source metadata in the sidecar. Empty/zero indices are distinct. This is a compact representation, not a separate semantic identity. Predecessor trace: BAMF-REQ-004; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Round-trip\[0,1,8190,8191\], all-zero and all-max words against literal expected integers. Version mismatch and illegal presence mask reject.17th schema, index8192, five-slot frame and nested frame all choose extended encoding and reconstruct exactly. Two frame occurrences with identical contents share content identity but retain distinct occurrence IDs.

### [A05: \#357](https://github.com/Entif-AI/Bilqis-MLX/issues/357)\| Compile causally valid mixed frame and atomic sequences {#a05:-#357|-compile-causally-valid-mixed-frame-and-atomic-sequences}

Depends on:[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349),[A04: \#351](https://github.com/Entif-AI/Bilqis-MLX/issues/351),[A13: \#354](https://github.com/Entif-AI/Bilqis-MLX/issues/354).

Deliver: Implement a streaming partial-frame builder. Close and pack a frame only when its final required constituent is visible. Represent incomplete frames by the visible atoms or explicit partial node; never rewrite an already-consumed prefix position in an incremental cache. For append streaming, emit a closure reference at the closing position; full-prefix compilation may compact the complete frame only in a newly keyed cache epoch. Emit position-to-source maps, source-to-position maps, prefix ends, scope boundaries, padding mask, exact role access and expansion handles. Include policy version in compiler digest. Keep batch rows independent. Compile answers only as target tensors outside the model input view. Bound neural length to1024 and report overflow before padding/allocation; split lawful source sequences at existing boundaries rather than silently truncate. Return actual atoms/frame, fallback shares and sidecar bytes. Predecessor trace: BAMF-REQ-005; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Compile every prefix of a literal four-member frame and show unavailable members never appear in embeddings or handles. At A05 completion, prove exact compiler-only prefix/handle/mask/sidecar equivalence under changed future suffix; downstream B11 and C13 own the actual neural-logit F05 witness. Do not claim F05 neural PASS at A05 closure. Mixed atomic/nested/packed sequences reconstruct the same visible AST. Streamed closure changes cache identity rather than mutating old keys. A two-row batch with unequal lengths has no cross-row content or padding visibility.

### [A06: \#352](https://github.com/Entif-AI/Bilqis-MLX/issues/352)\| Compile source-grounded factorized features once per release {#a06:-#352|-compile-source-grounded-factorized-features-once-per-release}

Depends on:[A01: \#345](https://github.com/Entif-AI/Bilqis-MLX/issues/345),[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349).

Deliver: Implement AtlasFeatures/v2 exactly as specified in the shared Feature schema. Materialize maps, graph vectors, exact ID sidecars and predecessor binding for the full admitted corpus. Reuse canonical SKOS relation predicates without deriving curriculum prerequisites from taxonomy. Export the immutable feature manifest consumed by A02 initialization and B02 embeddings. Keep inference/training reads local and preserve held-source reasons. Tests below enforce successor identity stability. Use literal committed fixture vectors computed by a small independent reference script using the stated SHA256 byte rules.

Verify: Two builds have identical features. Swapping a role changes its feature while leaving concept identity unchanged. Held relations do not enter admitted feature inputs. A disconnected concept receives explicit zero neighborhood plus its own type features. No runtime function in the gradient path opens a network connection. The feature manifest survives source-file reordering. Insert a lexically earlier new category into a successor release; every old learned row retains the same ID. Test two categories beyond512, exact zero graph, signed collision accumulation and independent golden-vector agreement.

### [A07: \#353](https://github.com/Entif-AI/Bilqis-MLX/issues/353)\| Register exact semantic and deterministic cognitive operators {#a07:-#353|-register-exact-semantic-and-deterministic-cognitive-operators}

Depends on:[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349).

Deliver: Register role lookup, identity/type inspection, set membership, Boolean functions, bounded integer operations, exact rational duration/unit conversion and released structural relations. Each operator declares input/output signatures, applicability conditions, implementation digest and pure-effect contract. Operands come only from task-visible input and admitted knowledge. Independent evaluation owns target gold. Reuse independently verified source algorithms where runtime use is allowed but keep evaluator entrypoints unreachable from solver dependencies. Return UNKNOWN/UNSUPPORTED for an inapplicable operator rather than coercing null or interpreting a plan as an occurrence. Record operation count and source binding, not verbose internal prose. Known results may be memoized by complete input and operator identity. Make function composition and partial application ordinary typed DAG nodes.

Verify: Literal2+3=5, Boolean truth cases,0.25h=15min and role lookup work with no neural call. Null differs from0. Planned event cannot satisfy occurred-event predicate. Cached operation with changed release or operator version misses. A repository dependency test prevents solver imports of assessment/gold-label APIs. End-to-end scoring C05 gives full capability credit to this path.

### [A08: \#358](https://github.com/Entif-AI/Bilqis-MLX/issues/358)\| Generate capability and lesson programs across the full SKOS inventory {#a08:-#358|-generate-capability-and-lesson-programs-across-the-full-skos-inventory}

Depends on: [A01: \#345](https://github.com/Entif-AI/Bilqis-MLX/issues/345), [A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349), [A06: \#352](https://github.com/Entif-AI/Bilqis-MLX/issues/352), [A07: \#353](https://github.com/Entif-AI/Bilqis-MLX/issues/353).

Deliver: Build reusable family adapters for positive identity, typed role binding, source-attested relation recognition, morphology composition/decomposition, numeric/Boolean composition, scope/modality/time distinctions and released transformations. Enumerate every semantic concept in the pinned atlas and map it to required source-qualified construction families or a source-qualification hold; missing implementation remains IMPLEMENTATION\_UNCOVERED debt. For each family emit positive constructive teaching, source-valid contrasts, canonical answer modality, independent checker reference, prerequisite closure and variation axes. Definitions and source examples supply input facts; do not invent causal laws from English glosses. Qualified source facts can be looked up directly; harder tasks combine/rebind them. Store capability ID as a digest-stable semantic/operator signature, not root ordinal or grade letter. Use existing FactoryRelease/ExecutableFactoryRelease and factory verifier. 1-9 capability deltas are data. Additional root breadth reuses the same engine rather than creating one issue or trainer per root.

Verify: Build the actual full-atlas coverage ledger, with eligible/held counts reconciling to source concept census. Demonstrate current numeric/Boolean family plus one real source-attested morphology/role family. New concept within a supported family changes data only. Missing constructor/checker is IMPLEMENTATION\_UNCOVERED with exact owner/reason while unrelated ready families still compile. Teaching construction explicitly contains its declared constituents before composite tests.

### [A09: \#360](https://github.com/Entif-AI/Bilqis-MLX/issues/360)\| Generate a resumable prerequisite-aware curriculum frontier {#a09:-#360|-generate-a-resumable-prerequisite-aware-curriculum-frontier}

Depends on:[A08: \#358](https://github.com/Entif-AI/Bilqis-MLX/issues/358).

Deliver: Project A08 candidates into the existing CandidateFrontierRelease and CandidateBinding shapes. Resolve prerequisite closure using taught/current capability evidence. Rank eligible deltas first by smallest prerequisite slope, then released downstream unlock count, then oldest unvisited ready item and stable ID. Expose salience features to the existing teacher; priority never alters semantic gold. Resume from content-addressed coverage ledger and cursor; no root can vanish merely because a newer release arrived. Batch up to16 new IDs and1-9 capabilities; recursively schedule constituent introductions before composites. Emit COMPLETE\_ATLAS\_COVERAGE only when every frozen source-eligible concept has its requested task coverage and implementation-uncovered debt is zero; HELD entries remain enumerated with source/remediation owners. Propose and stage successors continuously. Runtime adoption remains C07's explicit lease/admission boundary.

Verify: Three successive generated deltas advance beyond A/B/C without grade-specific code. Restart after staged delta produces the same next candidate. A blocked prerequisite holds its dependents while unrelated ready work progresses. Corpus reordering changes neither capability IDs nor prior allocation. A release containing only held items returns actionable coverage status, not false graduation or an infinite empty loop.

### [A10: \#361](https://github.com/Entif-AI/Bilqis-MLX/issues/361) \| Compile BRAVO evidence strata into Factory learning releases {#a10:-#361-|-compile-bravo-evidence-strata-into-factory-learning-releases}

Depends on: [A08: \#358](https://github.com/Entif-AI/Bilqis-MLX/issues/358).

Deliver: Consume source-span-linked interpreted frames from the qualified VieDay stratum release. Begin with category/value/unit summaries, then time logs, structured reflections and narrative subsets as each is available. Use PUBLIC\_FIXTURE analogues for public tests; PRIVATE\_REAL intake uses \#327's private boundary. Bind source digest, interpretation revision, concept/role IDs, prerequisite capabilities, positive/negative families, checker, task modality and rights to each lesson. Preserve blank/zero, reported/computed values, planned/occurred status, negation, temporal disagreements and alternate interpretations. Train typed reconstruction and a small declared English template codec initially; free-form narrative stays separate until its qualified semantics exist. Split by the original immutable source-family/episode identity for fresh challenges before further grouping by template lineage, while ordinary post-exam errors remain teachable under the existing classroom policy. No all-strata gate: one qualified subset can feed an ordinary FactoryRelease. Commit the PUBLIC\_FIXTURE source, parsed record, expected Frame/lesson and exact checker result from Bravo fixture.

Verify: One public structured summary becomes a source-linked typed lesson and independent exact check.0.25h/15min match; blank differs from0; planned differs from completed; contradictory dates remain alternatives. Unclassified/private source is rejected by public export. One held narrative span does not block qualified structured summaries. A source interpretation correction changes only dependent lesson families. T1 emits completed and15-minute derived answer; T2 retains PLANNED and cannot satisfy an occurred predicate; T3 has UNKNOWN, not0. A missing qualified private stratum changes only its held count. Existing public snapshots continue through the same Factory.

### [A11: \#362](https://github.com/Entif-AI/Bilqis-MLX/issues/362)\| Generate lawful ambiguity and structural contrast lessons {#a11:-#362|-generate-lawful-ambiguity-and-structural-contrast-lessons}

Depends on:[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349),[A08: \#358](https://github.com/Entif-AI/Bilqis-MLX/issues/358).

Deliver: Implement typed transformations: role swap, cardinality change, scope/negation movement, known/unknown substitution, planned/occurred contrast, missing-versus-negative observation, and source-authorized morphology alternatives. Each transformation declares applicability and checker-derived outcome. Maintain original source and generated variant lineage separately. Add bounded ambiguity exploration with at most4 source-compatible interpretations per example, ranked deterministically; preserve unresolved alternatives as the target when evidence cannot choose. Controlled noise operates on presentation or available cues, not canonical identities/gold. Save the noise signature(type,location,amount,seed) so a later lesson can revisit a genuinely different weakness. Feed contrast choices to the teacher's existing strategy interface. Start with structural families already expressible in the current ABI.

Verify: A role-swapped frame changes the expected role answer. Removing decisive evidence produces UNKNOWN or an alternative set, not a guessed singleton. Re-running a noise seed reproduces the exact variant. Three contrast families pass literal oracle checks and original-source preservation. The same old failure is not relabeled as a novel example merely by paraphrasing.

### [A12: \#364](https://github.com/Entif-AI/Bilqis-MLX/issues/364)\| Complete the single-authority semantic cutover and release receipt {#a12:-#364|-complete-the-single-authority-semantic-cutover-and-release-receipt}

Depends on:[A02: \#348](https://github.com/Entif-AI/Bilqis-MLX/issues/348),[A05: \#357](https://github.com/Entif-AI/Bilqis-MLX/issues/357),[A08: \#358](https://github.com/Entif-AI/Bilqis-MLX/issues/358),[A09: \#360](https://github.com/Entif-AI/Bilqis-MLX/issues/360),[A11: \#362](https://github.com/Entif-AI/Bilqis-MLX/issues/362).

Deliver: Trace every current semantic input to one explicit admitted source release or separately declared formal domain. Verify ABI, AST, frames, lesson manifests, graph projection and registry mirror share that binding. Classify old catalogs as historical readers or generated derivatives; remove current-path overrides and duplicate aliases once callers migrate. Extend the existing semantic-boundary guard with declared imports and ownership rules, not a regex ban on every historical filename. Produce a compact source-to-consumer table and a rebuild receipt. Close \#295 only after its existing acceptance is met on the exact combined branch; this leaf's completion alone must identify any remaining existing-owner work. Keep the source-grade implementation generic and add one Grade-D-equivalent data-only successor witness.

Verify: Regenerate release/ABI/AST/lessons twice and compare hashes. A stale shadow catalog cannot alter current semantics. Historical receipts still decode. One new released semantic reaches compiled lesson and read-only graph projection with unchanged old indices. A deliberate mismatched digest is caught at the first consumer. Record exact code head and existing-owner completion disposition.

### [A13: \#354](https://github.com/Entif-AI/Bilqis-MLX/issues/354)\| Enforce combined context eligibility before neural or motif access {#a13:-#354|-enforce-combined-context-eligibility-before-neural-or-motif-access}

Depends on:[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349).

Deliver: Implement versioned ContextEligibility and EligibleContext records using the shared eligibility contract. Validate all member handles and pair/set joins before A05 packing and B08 motif reads. Produce stable reason codes for release mismatch, revoked source, temporal mismatch, forbidden join, unresolved purpose and invisible prefix. Retain blocked evidence only in the authorized source store; return source handles and bounded diagnostics to the caller. Emit a digest over the approved membership and relevant policy/time/rights projections. Runtime exact operators, neural attention and cached transforms consume only this approved view. Provide PUBLIC\_FORMAL envelopes for existing source-grounded A/B/C constructors. Public tests use independent synthetic actors/scopes. Changes to eligibility generate C09 invalidations; a live external policy service is not required for each gradient step because the visit pins one approved frontier. Predecessor trace: BAMF-REQ-010/F09; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Two individually allowed frames with a forbidden joint scope produce ContextHold before any pooling or lookup. Revocation invalidates a formerly permitted view. Different policy/time frontiers produce different cache identities. A future constituent has no eligible handle. PUBLIC\_FORMAL A/B/C fixtures remain executable without NLP or network calls. The full-set positive case produces an identical eligibility digest across input enumeration order while preserving source order inside each frame.

## Lane B {#lane-b}

### [B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346)\| Declare BAMF v2 topology and generate the complete parameter manifest {#b01:-#346|-declare-bamf-v2-topology-and-generate-the-complete-parameter-manifest}

Depends on: Ready to start.

Deliver: Implement explicit v1/v2 deserialization and a model factory dispatch keyed by architecture ID bamf-atlas-v2. Freeze dense geometry, modules, initializer seeds and shape policy. Declare every weight/norm/gate/head/convolution/adapter tensor centrally, with stable names, FP32 type and FAST/SLOW group. Generate initialization, shape validation, parameter count, optimizer tree and serialization order from this declaration. Preserve v1 reader behavior. Initial dense matrices count67,239,936, semantic table6,291,456 and motif table2,097,152; auxiliary tensors must be itemized and final total printed, not forced to a marketing estimate. Three rank8 adapters add 36,864 matrix parameters. Frame feature and type tables use their declared separate capacities. Version embedding-bank extents as generation state, while dense geometry remains immutable. Store source/release and teacher identities separately from topology. Make config self-describing and validate contradictory channels/heads, zero sizes and unsupported dtypes before allocation. Predecessor trace: BAMF-REQ-007; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Exact generated shapes agree with an instantiated tree and serialized tree. Seed equality reproduces initialization. Invalid16Q/7KV, oddRoPE24-mismatch or different FFN method rejects. v1 historical metadata still reads. v2 bank extension changes extent receipt but not stable dense-topology digest. Report all tensors and exact parameters without constructing alternative model sizes.

### [B02: \#359](https://github.com/Entif-AI/Bilqis-MLX/issues/359)\| Implement tied factorized semantic embeddings and paged readout {#b02:-#359|-implement-tied-factorized-semantic-embeddings-and-paged-readout}

Depends on:[B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346),[A02: \#348](https://github.com/Entif-AI/Bilqis-MLX/issues/348),[A06: \#352](https://github.com/Entif-AI/Bilqis-MLX/issues/352).

Deliver: Implement the factorized embedding equation and fixed feature shapes. Respect per-row active state both in lookup validation and readout masking. Assemble multi-bank logits in global ABI order and expose an index map so sparse active IDs remain correctly addressed. Treat learned feature gates as parameters. Use deterministic feature-composed initialization only for newly admitted identity rows, leaving established rows intact. Include structural role/schema/position vectors without conflating their IDs with semantic vocabulary. Gather constituent embeddings differentiably; exact indices/sidecar data are nondifferentiable input. Use stable masked logsumexp for loss; reject a task with no legal answers rather than emitNaNs. Record parameter-update coverage for identity, feature and gate tensors in a disposable proof. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: A changed role changes embedding while sameID identity component stays equal. Inactive row receives zero gradient and cannot be predicted. An active row in bank1 decodes to global8192+. Tied output reuses identical parameter object/name, not a copied head. Save/load reproduces logits to1e-6 FP32 on fixedCPU reference where available or declaredMLX tolerance.

### [B03: \#363](https://github.com/Entif-AI/Bilqis-MLX/issues/363)\| Build the role-aware frame encoder and constituent handles {#b03:-#363|-build-the-role-aware-frame-encoder-and-constituent-handles}

Depends on:[B02: \#359](https://github.com/Entif-AI/Bilqis-MLX/issues/359),[A05: \#357](https://github.com/Entif-AI/Bilqis-MLX/issues/357).

Deliver: Implement the exact FrameEncoder equations from B01 Tensor ledger using role-ordered members and explicit occurrence positions. Return global seeds, original member embeddings, immutable source handles and feature summaries. Preserve gradients through original members and the frame pass. Atomic fallback preserves its atom embedding; empty legal structural nodes use the specified seed. Partial frames include only visible members. Source/parent/scope handles preserve nesting. Record frame-fill/fallback counts.

Verify: Role swap yields a changed encoding and exact sidecar. Repeated concepts with different occurrences remain separately addressable. Nested and atomic paths both reach the same outputshape. Future member changes cannot influence partial-frame encoding. One lossbackward reaches identity, role and frameinteraction weights. Empty legal structural node remains finite.

### [B04: \#350](https://github.com/Entif-AI/Bilqis-MLX/issues/350)\| Implement causal compressed-convolution GQA and incremental RoPE caches {#b04:-#350|-implement-causal-compressed-convolution-gqa-and-incremental-rope-caches}

Depends on:[B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346).

Deliver: Project Q/K/V with frozen shapes and apply independent per-channel three-tap convolution to projected pre-RoPE arrays. Initialize kernel\[0,0,1\] under oldest-to-current ordering so initial behavior is identity. Use left padding only; keep last two pre-convolution projected values perhead in decode cache. Scope/sequence boundaries zero the history, including a boundary inside a batch. Apply MLX fast.rope toQ/K with exact offset, then native fast SDPA16:8GQA. Handle allmasked/paddedquery rows by an explicit zero-result mask. Recombine384 and outputproject768. Cache manifest carries layer,scope,prefix,RoPEvariant andgeneration. Include a tiny explicit FP32 reference implementation for equality testing only; production uses fusedSDPA. Store installedMLXversion in runtime identity and use its observed signature, not undocumented flags. Predecessor trace: BAMF-REQ-008; the implementation follows the explicit BAMF-0.2 contract repeated here. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: Compare fused and independent explicit references with actual production 16Q×24/8KV×24 geometry at short sequence length within declared tolerance. A reduced two-head helper does not replace the production test. Mismatched later-prefix decode history must be rejected or recomputed. Full-prefix versus chunked/single-token outputs agree within tolerance. Perturb future suffix and preserve earlier output exactly within tolerance. Confirm KV storage is8heads, not16tiled. Boundary reset,allmaskedrow and two unequal lengths remain finite. One backward reachesQ/K/V/conv/outputparameters.

### [B05: \#355](https://github.com/Entif-AI/Bilqis-MLX/issues/355)\| Implement three-group Block AttnRes with stable depth selection {#b05:-#355|-implement-three-group-block-attnres-with-stable-depth-selection}

Depends on:[B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346),[B04: \#350](https://github.com/Entif-AI/Bilqis-MLX/issues/350).

Deliver: Implement the exact Q/K/V/output and per-boundary gated residual equations in the depth contract. Retain h0 and summaries at layers4,8,12; shared selector projections have128 inner channels and the residual interface stays768. The type/role composition is computed by the released factor composer and uses no target labels. Source weights are normalized across h0 and completed groups only, with a fixed source order. Capture g1 after the second motif read; apply each plastic adapter after selection. Save all four shared projection matrices and the three gate vectors/biases in B01's registry and B13's checkpoint. Optional diagnostics expose alpha without assigning fixed cognitive functions to layers. Predecessor trace: BAMF-REQ-009; the implementation follows the explicit BAMF-0.2 contract repeated here. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: Source weights sum to1. Changing a future group cannot change an earlier boundary. All three boundaries remain finite. A nondegenerate loss reaches multiple source states and selector weights. Save/load preserves output. Assert that all three group boundaries execute the module, rather than merely declaring it in configuration.

### [B06: \#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365)\| Add bounded recurrent constituent refinement with input recall {#b06:-#365|-add-bounded-recurrent-constituent-refinement-with-input-recall}

Depends on:[B03: \#363](https://github.com/Entif-AI/Bilqis-MLX/issues/363),[B05: \#355](https://github.com/Entif-AI/Bilqis-MLX/issues/355).

Deliver: Use one shared768-wide recurrent-state module with a compressed single-head192-channel member-attention block for at most two additional local passes. Each pass receives current frame hidden state, immutable original frame seed, visible member vectors and requested-role features. Reinject the original input every pass and merge through a residual gate initialized 0.01. A small three-class0/1/2 routing head can learn from measured outcomes. Initial policy uses one pass for explicit member questions, zero otherwise, and permits two for unresolved nested queries. Use the prediction-local selection and quota defined in the Causal refinement contract. During training sample0/1/2 passes from the visit seed on eligible frames so the second pass receives training. Missing routing labels mask its auxiliary loss. Main answer loss still propagates through selected passes. Reuse one backbone result; refinement does not rerun all12 layers. Declare Q/K/V projections\[192,768\], attention output\[768,192\], recurrent residual gate and its bias in the tensor registry. Exact member handles return768-wide embeddings. For a selected frame, initialize state from the global frame hidden vector; query uses state+immutable\_frame\_seed+requested\_role768; keys/values use only legal visible members. This preserves the predecessor768-wide local-resolution interface while choosing192 inner attention channels. Predecessor trace: BAMF-REQ-012/013; the implementation follows the explicit BAMF-0.2 contract repeated here. Preserve immutable global hidden states and return a separate per-query refinement view. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: Zero passes is identity. One/two passes change only selected frames. Future members remain inaccessible. Original input is re-injected every pass. Backward reaches refinement parameters and two-pass save/resume repeats. Exhausted budget records remaining needs and returns the baseline answer path. One finite disposable update reduces a literal nested-role target loss. Append high-priority future frames across the8-to9 quota boundary; earlier selection IDs, pass counts and logits at fixed p are identical. Repeat with different batch padding and future teacher-forcing targets.

### [B07: \#356](https://github.com/Entif-AI/Bilqis-MLX/issues/356)\| Implement transactional motif-key allocation and structural fallback {#b07:-#356|-implement-transactional-motif-key-allocation-and-structural-fallback}

Depends on:[B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346),[A03: \#349](https://github.com/Entif-AI/Bilqis-MLX/issues/349).

Deliver: Canonicalize full typed keys. Derive structural keys by replacing permitted fillers with admitted type IDs while retaining roles, scope and relation structure. Look up exact instance first, then structural motif. Allocate missing structural keys before instance keys, ordered by observed use then key digest, at most64 new slots per candidate preparation. When full, add one16384-slot page up to 65536 if the resource budget permits; otherwise retain already encoded factorized structural features and pending-key evidence, with no additional motif residual. Initialize new vectors deterministically. Always compare full keys after hash lookup. Stable slots are append-only. Allocation and counters used for future allocation are copy-on-write candidate state, published only on acceptance. Preserve original release keys; accepted semantics-preserving alias maps are explicit artifacts. Predecessor trace: BAMF-REQ-010; the implementation follows the explicit BAMF-0.2 contract repeated here. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: Use a test-only injected deterministic bucket/index collision between two different canonical full motif keys. Require full-key comparison to select the correct slot or miss; do not require finding a cryptographic digest collision. Different fillers share a permitted structural motif; role swap changes the key. Rejection restores allocation, tensor and counters byte-for-byte. Restart reproduces pending slot IDs. Capacity exhaustion uses fallback without overwrite. Page growth preserves all old slots and moments.

### [B08: \#366](https://github.com/Entif-AI/Bilqis-MLX/issues/366)\| Train two context-gated motif-memory reads inside the model {#b08:-#366|-train-two-context-gated-motif-memory-reads-inside-the-model}

Depends on:[B03: \#363](https://github.com/Entif-AI/Bilqis-MLX/issues/363),[B05: \#355](https://github.com/Entif-AI/Bilqis-MLX/issues/355),[B07: \#356](https://github.com/Entif-AI/Bilqis-MLX/issues/356),[A13: \#354](https://github.com/Entif-AI/Bilqis-MLX/issues/354).

Deliver: Implement the two exact gated motif residual reads and the gate equation from B01 Tensor ledger. Check full-key/release/scope eligibility before batched gather. Missing keys return unchanged factorized hidden state. Save every allocated vector, projection, gate and norm; report exact/structural/miss counts and actual participating rows. The second site executes after layer4 and before capturing group1 summary.

Verify: Both read sites influence a nondegenerate loss and receive finite gradients. Changing a qualified slot affects its applicable frames. Held or foreign-release entries are not read. Miss fallback stays finite. Save/load restores values and gates. Rejection after both sites update restores the complete parent.

### [B09: \#368](https://github.com/Entif-AI/Bilqis-MLX/issues/368)\| Provision fast adapters and explicit multi-timescale plasticity {#b09:-#368|-provision-fast-adapters-and-explicit-multi-timescale-plasticity}

Depends on:[B01: \#346](https://github.com/Entif-AI/Bilqis-MLX/issues/346),[B05: \#355](https://github.com/Entif-AI/Bilqis-MLX/issues/355),[B08: \#366](https://github.com/Entif-AI/Bilqis-MLX/issues/366).

Deliver: Add three rank8 adapters at group boundaries. Zero B matrices make initial adapters identity. FAST includes adapters, motif parameters and newly activated semantic rows; SLOW includes established embeddings and dense parameters. A new identity row becomes established after 8 accepted candidates in which it participated under the shared update-mask contract. FOUNDATION updates the full tree. ADAPTIVE offers FAST candidates, then FULL after eight accepted FAST candidates; the existing teacher can request FULL earlier for foundational remediation. This policy selects update eligibility, while the teacher still selects targets, learning rate and pedagogy. Persist mode, counters, row ages and policy version. Advance clocks by accepted updates rather than wall time. Inference always consumes both groups. Freeze group eligibility at candidate preparation. Derive the final row-update mask separately for every optimizer step from actual participation and active/admitted state, before clipping and AdamW arithmetic. B12 owns optimizer moments and update counts. Apply the exact Plasticity transition contract at the retained promotion-event boundary. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: Initial adapter output equals its input. FAST changes only eligible parameters and rows. Rejected FAST candidates do not advance clocks. Eight accepted FAST candidates schedule FULL across restart. Row establishment age increments once per accepted participating CANDIDATE, not per internal optimizer step; a rejected candidate advances no age. Each step computes its own actual row-participation mask before clipping. Teacher-triggered FULL uses the same generic visit path. Test FOUNDATION promotion-with-debt transition, accepted/rejected FAST/FULL schedules, teacher early FULL reset, a new semantic row, and cold resume on either side of the transition.

### [B10: \#367](https://github.com/Entif-AI/Bilqis-MLX/issues/367)\| Implement typed scalar, slot and structured answer heads {#b10:-#367|-implement-typed-scalar,-slot-and-structured-answer-heads}

Depends on:[B02: \#359](https://github.com/Entif-AI/Bilqis-MLX/issues/359),[B03: \#363](https://github.com/Entif-AI/Bilqis-MLX/issues/363).

Deliver: Reuse current Boolean, numeric and native semantic-token answer bindings. Add released role-selection and structured frame-output modalities. Concept values use the tied semantic head. ROLE selection uses shared released role-table logits and schema-constrained occurrence indices. The separate finite CONTROL head emits only EMIT\_VALUE, EMIT\_UNKNOWN, EMIT\_ALTERNATIVES and END\_FRAME; it never selects role IDs. Legal roles come from the released schema; repeated roles include occurrence indices. Cap output at64 decisions, respecting the combined input/generated1024-position budget. Predict independent roles in parallel only when the answer dependency DAG allows it; dependent decisions consume earlier committed outputs. Teacher forcing exposes earlier targets only. Preserve UNKNOWN and unresolved alternative sets where allowed. Mask losses to legal active answers and actually supplied auxiliary labels. Validate a completed typed answer before publication; invalid neural output becomes an explicit solver failure/fallback request. Implement the exact AnswerPlan/v2 state transition in the Typed decoder contract. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: Current A/B/C answer mappings remain unchanged. Four-role outputs preserve binding under role swaps. A bank1 concept can be predicted and an inactive concept cannot. Earlier output positions cannot inspect later targets. UNKNOWN differs from empty set. The64-decision ceiling returns a typed budget status. Gradients reach identity and role heads. A two-step fixture first chooses a source actor and then its event role; changing step2 gold leaves step1 logits unchanged. Inference step2 receives predicted step1, training receives only prior teacher-forced step1. Missing parent, dependency cycle, END\_FRAME before a required role and64-step exhaustion are literal cases.

### [B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369)\| Assemble the real atlas-native model and architecture dispatch {#b11:-#369|-assemble-the-real-atlas-native-model-and-architecture-dispatch}

Depends on:[B03: \#363](https://github.com/Entif-AI/Bilqis-MLX/issues/363),[B04: \#350](https://github.com/Entif-AI/Bilqis-MLX/issues/350),[B05: \#355](https://github.com/Entif-AI/Bilqis-MLX/issues/355),[B06: \#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365),[B08: \#366](https://github.com/Entif-AI/Bilqis-MLX/issues/366),[B09: \#368](https://github.com/Entif-AI/Bilqis-MLX/issues/368),[B10: \#367](https://github.com/Entif-AI/Bilqis-MLX/issues/367).

Deliver: Compose factorized inputs, frame encoder, input motif read,12 CCGQA/FFN blocks, three AttnRes selectors, mid-depth motif read, three adapters, local refinement and typed readout. Derive geometry from B01 and assert exact parameter-name/shape agreement. Add one backend dispatch used by inference, gradient construction, retention and championship callers. Migrate existing direct-forward callers in the same patch. Preserve existing historical v1 reader/execution restrictions. Ordinary training returns only needed outputs; detailed diagnostics are opt-in so the reporting layer does not retain all activations. Use FP32 for authoritative computation. Exercise a real mixed atomic/packed/nested batch with MLX forward and backward. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: The actual12-layer forward runs and matches the parameter census. Demonstrate nonzero finite gradients in embeddings, attention, FFN, depth selector, memory, adapters and readout. Adapter A is seeded nonzero while B is initially exactly zero. On the first nondegenerate backward step, B must receive a finite nonzero gradient and A initially zero; after B changes, the next backward must reach A. A/B both zero fails the required wake-up. Prefix invariance holds. A complete update changes loss and saves. Old run files remain unchanged. All consumers use the architecture dispatch.

### [B12: \#370](https://github.com/Entif-AI/Bilqis-MLX/issues/370)\| Extend native AdamW custody to masked plastic groups and candidate transactions {#b12:-#370|-extend-native-adamw-custody-to-masked-plastic-groups-and-candidate-transactions}

Depends on:[B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369).

Deliver: Preserve native AdamW equations and the teacher-selected learning rate, betas, epsilon and weight decay. Maintain per-parameter update counts for correct bias correction under freezing and activation; identity/motif tables need per-row counts. Increment only eligible parameters on actual steps. Inactive parameters, moments and weight decay remain unchanged. One candidate owner publishes the entire tree as one generation. Accumulate FP32 gradients and apply the existing global norm clip. Newly activated rows begin with zero moments and count0. Rejection discards weights, moments, counts, allocations and plasticity counters together; observational teacher feedback follows its existing owner. Map historical scalar step to all parameter counts only when the historical contract updated them together. The run's global optimizer step remains the count of accepted optimizer steps. Apply participation masking before clip\_gradients and before any weight-decay or moment arithmetic. Persist separate per-step optimizer counts and per-retained-candidate row age. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: A FULL step matches existing native AdamW on identical arrays. Two FAST steps followed by FULL match an explicit reference using local counts. Frozen rows are bit-identical. First update of a new row uses count1. Rejection restores all hashes/clocks. A NaN gradient rejects without partial publication. An unused motif row is byte-identical after an update. An output-only semantic row receives its legitimate denominator gradient/update. Arbitrarily huge frozen gradients cannot change the active clipping factor. A zero-gradient participating row and a never-participating row have distinct expected clocks/decay. Reject a multi-step candidate and verify all ages/counts remain unchanged.

### [B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372)\| Persist and cold-resume the complete BAMF learning generation {#b13:-#372|-persist-and-cold-resume-the-complete-bamf-learning-generation}

Depends on:[B12: \#370](https://github.com/Entif-AI/Bilqis-MLX/issues/370),[A02: \#348](https://github.com/Entif-AI/Bilqis-MLX/issues/348),[B07: \#356](https://github.com/Entif-AI/Bilqis-MLX/issues/356).

Deliver: Extend the existing bundle with a versioned v2 section and sidecars for semantic banks, active ABI, motif keys, plasticity policy/counts, compiler/features and correction frontier. Hash payloads, persist through existing content-addressed storage and atomically publish one generation pointer. Reuse outbox reconciliation and references to unchanged objects. Validate sidecar census and tensor identities before constructing the optimizer. Cold resume in a clean process reconstructs the next visit selection and identical neural output. Keep the human-run lock and100GiB disk reserve. Inference caches remain disposable. Historical bundles retain their existing readers and immutable source bytes. Predecessor trace: BAMF-REQ-016/023; the implementation follows the explicit BAMF-0.2 contract repeated here. Use B01's normative Tensor ledger as the complete tensor/initializer authority. Each module owns only its named prefix; shared feature/depth/identity paths remain shared. Constructor output must match the expanded ParameterSpec list exactly.

Verify: Save/load reproduces parameters, moments, local counts, teacher context, active ABI and next seed. Crash before pointer keeps the old generation; crash after pointer before outbox delivery replays exactly once without another optimizer step. Wrong motif map, bank extent, compiler, topology or correction epoch fails before mutation. Accepted then rejected candidate followed by cold resume yields only accepted state.

### [B14: \#375](https://github.com/Entif-AI/Bilqis-MLX/issues/375)\| Implement the derived low-bit KV-cache codec with FP32 fallback {#b14:-#375|-implement-the-derived-low-bit-kv-cache-codec-with-fp32-fallback}

Depends on:[B04: \#350](https://github.com/Entif-AI/Bilqis-MLX/issues/350),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372).

Deliver: Implement bamf.rot3/v1 exactly as the cache contract specifies. Generate one seeded orthogonal24x24 transform with deterministic QR sign normalization and persist its digest. Scale rotated unit coordinates by sqrt24 before normal-codebook quantization. Pack3-bit codes little-endian. Per32-vector block store a FP32 maximum norm and8-bit relative norms; preserve zero vectors. Decode, inverse-rotate, renormalize direction and restore the norm. Compress cold K/V records only when at least 256 vectors amortize headers; smaller records remain FP32. Bind cache records to lineage, causal prefix, masks and codec manifest. Report actual byte costs. Reference candidate evaluation remains FP32. Interactive inference recomputes when a cache is incompatible or fails declared quality checks. Deliver this after the first complete learning path. Predecessor trace: BAMF-REQ-014; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Literal code sequence0..7 round-trips through bit packing. Zero vectors decode exactly zero. Full256-vector records use\<=3.5 effective bits/channel. The fixed attention fixture meets relative-L2\<=0.10 and exact chosen-answer agreement or selects FP32 fallback. Wrong generation/offset/scope/codebook rejects. No training gradient reads decoded cache tensors.

## Lane C {#lane-c}

### [C01: \#347](https://github.com/Entif-AI/Bilqis-MLX/issues/347)\| Create the three-lane integration baseline and executable EGM work contract {#c01:-#347|-create-the-three-lane-integration-baseline-and-executable-egm-work-contract}

Depends on: Ready to start.

Deliver: Create a successor integration branch from the exact post-324 replay head plus SKOS-bearing main, recording both commit IDs. Preserve the frozen \#324 specimen unchanged. Record the owner-authorized BAMF successor gate: the source bridge can be built now; first live adoption follows BAMF's own source/custody/retained-learning witness rather than waiting for the old model-size comparison. Add the scoped outcome-first evaluation and admission-lease amendments to AGENTS/ADR. Install or locate EGM at the pinned commit and create a project-local execution instruction pointing to its real persona/standard paths. Create three lane branches with one writer each: semantics, neural, integration. Lane A owns semantics/factory new modules, B owns neural new modules, C owns shared trainer/CLI/checkpoint wiring; B13 proposes checkpoint patches through C's shared-file queue. Validate the issue DAG and direct dependency receipts. Copy this delivered spec into repository docs without creating a fourth workstream. C16 owns the foundation successor launch witness: at least one source-valid end-to-end retained capability improvement, complete rollback of a deliberately damaging disposable candidate, and cold-resume equivalence. This exact-head receipt satisfies the BAMF foundation launch gate. C13 is the later expanded-system release qualification and is not a prerequisite of C16 or foundation training.

Verify: Record exact baseline and clean integration diff. Workstack detects a cycle, missing dependency and overlapping shared-file ownership. EGM path resolves and a genuinely fresh reviewer reads one leaf without transcript. Existing Factory/SKOS focused checks run once at the combined baseline; report actual failures by owner. No model/run data or private sources enter the commit. C16 acceptance records parent and retained generation IDs, strictly improved fresh complete-solver target score, preserved cumulative retention, rejected-candidate complete-state identity, and equivalent cold-resume output/next update.

### [C02: \#371](https://github.com/Entif-AI/Bilqis-MLX/issues/371)\| Adapt ordinary Factory batches to BAMF inputs and targets {#c02:-#371|-adapt-ordinary-factory-batches-to-bamf-inputs-and-targets}

Depends on:[A05: \#357](https://github.com/Entif-AI/Bilqis-MLX/issues/357),[A06: \#352](https://github.com/Entif-AI/Bilqis-MLX/issues/352),[B10: \#367](https://github.com/Entif-AI/Bilqis-MLX/issues/367),[B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369),[C01: \#347](https://github.com/Entif-AI/Bilqis-MLX/issues/347),[A13: \#354](https://github.com/Entif-AI/Bilqis-MLX/issues/354).

Deliver: Consume the delivered rows and answer bindings from the existing executable Factory release. Compile source-visible inputs through A05, attach deterministic atlas features, and build separately masked typed targets. Preserve source row IDs, operation/capability IDs, actual teacher strategy, requested/delivered counts, rehearsal provenance and optimizer-step seed. Support all current answer modalities and new B10 structured outputs through a registry, never a grade switch. Pad only actual batch maxima; cap constituent and frame work through C08. Auxiliary labels come from source or explicit outcome evidence and remain absent otherwise. Route inference and training through the same backend selection. Feed realized delivery into \#333's teacher observation capture, retaining exact row and cost attribution. The default path handles current A/B/C with atomic fallbacks before richer frame coverage arrives. Predecessor trace: BAMF-REQ-015; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Current A/B/C released fixtures compile and score through one adapter. Inference input contains no target fields. A changed source release rejects a stale prepared batch. A batch with packed, nested and atomic rows preserves each row's target and source identity. Report delivered rows after length packing and a finite MLX gradient step on a disposable model.

### [C03: \#376](https://github.com/Entif-AI/Bilqis-MLX/issues/376)\| Carry the replay-salvaged teacher into the new student lineage {#c03:-#376|-carry-the-replay-salvaged-teacher-into-the-new-student-lineage}

Depends on:[C01: \#347](https://github.com/Entif-AI/Bilqis-MLX/issues/347),[C02: \#371](https://github.com/Entif-AI/Bilqis-MLX/issues/371),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372).

Deliver: Port the exact replay behavior, using its current owner functions rather than rebuilding the selector. Preserve useful strategy history as prior evidence with explicit old/new student region labels; start checkpoint-local no-gain/interference counters for the new learner. Keep up to16 effective strategies and8 incumbents. Carry the every-fourth existing-policy canary, current UCB/retained exploitation and actual realized-delivery chain. The2/4/8/16 ladder stays shadow evidence under \#321/\#323 until its separate owner changes execution authority. New bank/plasticity epochs invalidate stale region matches without deleting the historical record. Old6-layer mentors may supply source-gold-checked typed advice under the championship contract; preserve their runtime as read-only and never average tensors into the 12-layer student. Expose teacher health from actual observations. Historical Factory-v1 student artifacts remain read-only evidence; mentor inference is allowed only through the currently supported compatibility evaluator and current source binding. Readability never silently enables historical resume or an incompatible optimizer/weight import. Predecessor trace: BAMF-REQ-017; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Replay a fixed observation sequence and match strategy eligibility, no-gain resets and canary fallback with the baseline functions. Changed retained checkpoint resets same-student retirement. Destructive interference and no-target-gain produce distinct histories. A stale teacher geometry region cannot qualify a canary. Actual proposed/delivered/outcome/cost records survive checkpoint/restart exactly once.

### [C04: \#373](https://github.com/Entif-AI/Bilqis-MLX/issues/373)\| Compose exact and neural mechanisms behind one capability solver {#c04:-#373|-compose-exact-and-neural-mechanisms-behind-one-capability-solver}

Depends on:[A07: \#353](https://github.com/Entif-AI/Bilqis-MLX/issues/353),[B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369),[C02: \#371](https://github.com/Entif-AI/Bilqis-MLX/issues/371).

Deliver: Implement a small typed route planner: use an applicable exact operator or qualified cached composition first; use neural role/semantic interpretation and learned composition for the unresolved portion; evaluate a bounded DAG and return one typed answer. Input handles remain source-bound and can be opaque outside the receiving operator's signature. Register applicability and deterministic tie order instead of free-form agent conversations. Initially allow maximum 64 pure DAG operations and one backbone call plus B06's local refinements per solve; budgets are explicit per task. Exact known answers receive full score. Neural invalid output routes to a legal deterministic fallback where available or explicit unresolved status. Record only the selected operator IDs, bindings, costs, dependencies and outcome needed for replay. Keep the golden-label evaluator outside the solve dependency graph. Implement TaskGoal/v1 with explicit source-lowered DAG and bounded neural holes; no free-form unbounded planner is part of this leaf.

Verify: Show three real routes: exact role lookup; deterministic composition of two arithmetic/temporal operations; neural interpretation followed by a pure operator. The complete pipeline solves a new role-binding composition. Wrong release/rights or invalid output is handled explicitly. No route reads evaluation labels. Parent/candidate solver runs have identical information and budgets. Literal ADD(MUL(2,3),4) yields 10 with 2 pure calls. A hole choosing the qualified actor from three visible candidates feeds an exact duration lookup. Wrong type, cycle, depth 9, missing binding and consumed-budget exhaustion are explicit cases. The same registered exact operators stay enabled during parent/candidate scoring.

### [C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378)\| Evaluate and retain end-to-end capabilities with current school safeguards {#c05:-#378|-evaluate-and-retain-end-to-end-capabilities-with-current-school-safeguards}

Depends on:[C03: \#376](https://github.com/Entif-AI/Bilqis-MLX/issues/376),[C04: \#373](https://github.com/Entif-AI/Bilqis-MLX/issues/373),[B12: \#370](https://github.com/Entif-AI/Bilqis-MLX/issues/370),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372).

Deliver: Evaluate the same complete solver for retained parent and challenger. Preserve source-correct typed answers, the existing fresh-target improvement rule, grade/school aggregate non-regression and scaled protected-capability loss allowances. For already-perfect exact capabilities, skip pointless neural candidates and advance/rehearse through existing scheduling rules; useful cache/configuration changes receive their own versioned outcome receipt rather than fabricated retained optimizer steps. Run fresh generated compositions inside taught semantic scope, including previously unseen role fillers and legal structural variants. Distinguish progression92/87 from perfect cumulative mastery and championship. Keep fresh same-cohort title inference and settled unordered-pair history. Optional path attribution is diagnostic; no neural-only gate or architecture control-arm requirement is introduced. A whole capability can improve through a changed route, adapter, motif or dense weight.

Verify: An exact answer and neural answer with the same correct semantics receive identical task credit. One target gain with admissible protected effects retains the whole candidate; a destructive candidate restores everything. A perfect source-visible lookup does not consume an optimizer visit. Same checkpoint/scope cannot rearm a failed promotion solely via new cohort. Old/new scopes and title evidence remain separated.

### [C06: \#379](https://github.com/Entif-AI/Bilqis-MLX/issues/379)\| Route attention and curriculum priorities with SÍ SÉ SON signals {#c06:-#379|-route-attention-and-curriculum-priorities-with-sí-sé-son-signals}

Depends on:[A06: \#352](https://github.com/Entif-AI/Bilqis-MLX/issues/352),[A09: \#360](https://github.com/Entif-AI/Bilqis-MLX/issues/360),[B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369),[C03: \#376](https://github.com/Entif-AI/Bilqis-MLX/issues/376).

Deliver: Build three five-class ordinal heads and a deterministic evidence adapter. Impact uses declared task consequences and measured downstream dependency/coverage effects; Exigency uses deadlines, blocked useful work and active repair needs; Novelty compares the event/structure with the current expectation and observed outcomes. UNKNOWN is explicit. Use the dispatcher ordering in the shared contract, not a weighted global sum. The teacher consumes admissible priority features and continues selecting HOW. Maintain local aggregation windows by20 events and capability epoch; repeated small defects can become a process-level candidate. Label source-backed examples and outcome-derived bins by a versioned rule, masking unlabeled heads. Track whether accepted lessons change later actions/routes and whether corrections stop recurring. A surprising assertion stays a conjecture until its ordinary source/admission route qualifies it. Predecessor trace: BAMF-REQ-018; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: A time-critical known problem can outrank a novel low-impact curiosity; a useful new cross-domain relation can outrank routine repetition when deadlines are equal. Missing expected report differs from explicitnegative report. Repeated identical failure triggers one grouped repair candidate, not20newdiscoveries. Head losses mask UNKNOWN-without-label cases. Priority changes do not override teacher strategy or fabricate semantic truth.

### [C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380)\| Advance the Factory continuously under an explicit atlas admission lease {#c07:-#380|-advance-the-factory-continuously-under-an-explicit-atlas-admission-lease}

Depends on:[A09: \#360](https://github.com/Entif-AI/Bilqis-MLX/issues/360),[A12: \#364](https://github.com/Entif-AI/Bilqis-MLX/issues/364),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378),[C06: \#379](https://github.com/Entif-AI/Bilqis-MLX/issues/379).

Deliver: A human-started BAMF command may opt into \--admission-policy atlas-release, binding an exact approved atlas release, allowed family/operator set, source rights, bank/resource ceiling and versioned prerequisite/progression policy. Persist this lease with the run. Within it, repeatedly compile, validate, stage and adopt ready deltas through the existing prepared-successor entrypoint. Default without lease remains STAGED with a precise operator action. Check the current checkpoint, optimizer step, source/answer implementations and frontier immediately before adoption. Do not require a new human prompt for every already-authorized concept. A new external semantic release or out-of-scope domain requires a renewed lease, while old authorized learning continues. A/B/C initialize the developmental staircase; proceed into source-attested SKOS families according to prerequisites and useful outcomes, not a fixed D-O list. Read carried debt for every admitted grade, numeric scope and policy version from the current run manifest, never historical grade-specific constants.

Verify: One lease admits three data-defined successors and resumes from the second without duplicate allocation. An out-of-scope release stages rather than silently adopts. Missing prerequisite blocks only its delta. Existing human-run authority and candidate custody remain. Newly introduced capabilities appear in the current assessment pool; future-stage concepts remain outside it. \#296 retains staging semantics for callers without a BAMF lease.

### [C08: \#374](https://github.com/Entif-AI/Bilqis-MLX/issues/374)\| Make batch preparation and resource budgets topology-aware {#c08:-#374|-make-batch-preparation-and-resource-budgets-topology-aware}

Depends on:[C02: \#371](https://github.com/Entif-AI/Bilqis-MLX/issues/371),[B11: \#369](https://github.com/Entif-AI/Bilqis-MLX/issues/369).

Deliver: Estimate activations from actual frame lengths, constituent expansions, depth summaries, trainable state and candidate copies. Keep one logical teacher batch while splitting into deterministic microbatches; accumulate correctly weighted gradients then clip and apply one AdamW step. Start32 short rows, reduce microbatch through16/8/4/2/1 under the 48 GiB trainer allocation. Snapshot actual installed MLX memory APIs and record peak allocated/cache memory. On allocation failure, restore the candidate and retry once with the next smaller microbatch using the same delivered examples and stepseed; exhausted budget stops at a safe boundary. CPU workers prepare only immutable source packets; no graph/network call enters a gradient step. Preserve100GiB disk reserve, display required next-bundle bytes and fail normally before writes. Use existing SSH/tunnel only for optional graph readback, not modelstate transport.

Verify: Accumulated gradient matches an unsplit small batch within declaredFP32 tolerance. Two CPU source workers produce same packets as serial. Stale prepared packet rejects. OOM simulation retries once and retains source/stepidentity. Batch1 exhaustion preserves parent. Disk guard considers complete weights,moments,manifest and publication overhead.

### [C09: \#377](https://github.com/Entif-AI/Bilqis-MLX/issues/377)\| Propagate corrections through reusable cognition and learned support {#c09:-#377|-propagate-corrections-through-reusable-cognition-and-learned-support}

Depends on:[A01: \#345](https://github.com/Entif-AI/Bilqis-MLX/issues/345),[B07: \#356](https://github.com/Entif-AI/Bilqis-MLX/issues/356),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372),[C04: \#373](https://github.com/Entif-AI/Bilqis-MLX/issues/373).

Deliver: Index immediate dependencies for atlas features, packedframes, motifs, exact caches, operator compositions and capability support. Use immutable correction events and reverse direct edges. Hold directly affected artifacts before their next use; revalidate lazily in impact/exigency order. Propagation stops when materialized content and eligibility are unchanged. Record alternatives when concurrent corrections disagree, rather than last-write-wins. A learned capability supported by invalidated material enters REQUALIFICATION\_REQUIRED and receives targeted fresh source tasks; valid unrelated capabilities continue. Preserve the original observations and historical tensor checkpoints. Route invalidations to Akasha via C10. Include deterministic expiry/as-of projections as immediate dependencies when time changes validity. Predecessor trace: BAMF-REQ-019/020; the implementation follows the explicit BAMF-0.2 contract repeated here.

Verify: Change one source premise and repair only its affected direct chain. An unrelated source edit causes no rebuild. Recomputed equal output stops propagation. A revoked motif is ineligible before retraining. Two concurrent incompatible corrections remain branches. Capability requalification is visible while source history remains immutable. A synthetic planned09:30 activity, missing expected report, explicit non-occurrence, later10:20 correction and stale replay remain five distinct cases; a later actor/time fixture exercises the corrected behavior.

### [C10: \#383](https://github.com/Entif-AI/Bilqis-MLX/issues/383)\| Publish BAMF learning and release events into Rosetta/Akasha projections {#c10:-#383|-publish-bamf-learning-and-release-events-into-rosetta/akasha-projections}

Depends on:[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372),[C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380),[C09: \#377](https://github.com/Entif-AI/Bilqis-MLX/issues/377).

Deliver: Emit compact application envelopes for release changes, capability outcomes, teacher visits, banks/motifs, correction lineage, plasticity epochs and package exports. Use existing Rosetta artifact/trace meanings and \#297's namespaces, consuming \#299/\#300 projection owners. Enqueue accepted generation events through the existing durable outbox; materialize afterward outside the neural lane. Every view binds as-of/source/release/model/evaluator/rights identities. Deduplicate by eventID and payload digest. A graph outage leaves training running and events queued. Rebuild into a staging projection, verify its census and bounded queries, then atomically promote the active pointer. Raw private inputs and private paths remain outside public logs.

Verify: Duplicate delivery is idempotent; divergent payload under one eventID rejects. Offline graph later catches up without a neural update. Rebuild yields the same release/capability views. Wrong release and cross-rights query fail. Projection receipt identifies source events, implementation and output digest.

### [C11: \#384](https://github.com/Entif-AI/Bilqis-MLX/issues/384)\| Expose a usable BAMF cockpit and stable launch/resume commands {#c11:-#384|-expose-a-usable-bamf-cockpit-and-stable-launch/resume-commands}

Depends on:[C03: \#376](https://github.com/Entif-AI/Bilqis-MLX/issues/376),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378),[C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380),[C08: \#374](https://github.com/Entif-AI/Bilqis-MLX/issues/374),[C10: \#383](https://github.com/Entif-AI/Bilqis-MLX/issues/383).

Deliver: Add BAMF v2 to the existing train, dry-run and resume parser. Preserve human-run and source-prefetch controls. Add \--admission-policy atlas-release with \--atlas-release-manifest; resume reads saved values and rejects conflicting overrides before mutation. Reuse the existing metric owners for ST/M,R/H,RTN%,GREW,G/RTN,GRAD,P(RET),HEALTH. Add a compact expandable panel with active concepts/banks, ready/held coverage, atoms/frame, fallback, expansion, motif hits, plasticity mode and memory pressure. Keep the main cockpit compact and put detailed data in receipts. Distinguish staged curriculum, gained capability, retained steps, debt and perfect mastery. Publish actual parser-tested commands for preflight, owner launch, resume and read-only status.

Verify: Fresh v2 and resume parse; conflicting saved topology fails. Ten retentions with no growth differs visibly from genuine capability improvement. Zero elapsed time or visits never emitsNaN. Stagnation-held active capabilities remain in the proper GREW denominator with measurement status. Status is read-only. Runbook commands pass real dry-run.

### [C12: \#381](https://github.com/Entif-AI/Bilqis-MLX/issues/381)\| Package reusable cognitive capabilities and compatible plastic deltas {#c12:-#381|-package-reusable-cognitive-capabilities-and-compatible-plastic-deltas}

Depends on:[A12: \#364](https://github.com/Entif-AI/Bilqis-MLX/issues/364),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378),[C09: \#377](https://github.com/Entif-AI/Bilqis-MLX/issues/377).

Deliver: Create a portable manifest containing semantic signatures, release compatibility, operator/model identity, qualification fixtures, counterexamples, behavioral diff, resource envelope, rights and revocation lineage. Export source-cleared procedures and exact transforms directly. Adapter/weight deltas require identical base checkpoint, parameter schema and semantic binding. Heterogeneous recipients receive semantic teaching packages or fixtures instead. Stage imports and apply the same whole-capability retention before activation. A first local two-node directory exchange suffices; no new server or networking framework is required. Public export whitelists PUBLIC\_FIXTURE/PUBLIC\_DERIVED and rejects private or unclassified material. Predecessor trace: BAMF-REQ-021; the implementation follows the explicit BAMF-0.2 contract repeated here. Implement the complete receiver-owned state transition from Package adoption.

Verify: Two local consumers exchange an exact operator package. A compatible adapter delta applies to a disposable clone and rolls back. Wrong base/topology/release rejects. Behavioral diff shows gains and regressions. Private payload cannot enter a public export. Counterexamples and ancestry survive a fork. Two recipients with identical base weights but different optimizer histories both reset changed slices according to the declared policy and retain their own untouched state. Execute one subsequent optimizer step, reject a later candidate, cold-resume, and compare the exact expected local state. A changed motif binding rejects before applying any tensor delta.

### [C13: \#385](https://github.com/Entif-AI/Bilqis-MLX/issues/385)\| Run the integrated disposable learning and recovery acceptance slice {#c13:-#385|-run-the-integrated-disposable-learning-and-recovery-acceptance-slice}

Depends on:[A12: \#364](https://github.com/Entif-AI/Bilqis-MLX/issues/364),[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378),[C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380),[C08: \#374](https://github.com/Entif-AI/Bilqis-MLX/issues/374),[C09: \#377](https://github.com/Entif-AI/Bilqis-MLX/issues/377),[C10: \#383](https://github.com/Entif-AI/Bilqis-MLX/issues/383).

Deliver: Use the actual Mac Studio for a finite disposable integrated run of the chosen model. Exercise creation, source-bound gradients, paired evaluation, one accepted candidate, one rejected candidate, cold restart and one append-only semantic delta. Allow up to64 attempted optimizer steps for this engineering witness and stop once the required behaviors are observed. Fix a failed witness in its owning source/loss/teacher/adapter seam rather than starting a model tournament. Lessons come from the admitted Factory and constructive constituent rules. Exercise complete solver routes and correction requalification. Run the existing portable, ABI and Factory guards once on the combined candidate. Record actual commands, hashes, outcomes and resource use. The operator's real learner stays untouched.

Verify: Prove finite real updates, a source-grounded retained improvement, complete rollback, equal resumed outputs and AdamW counts, unchanged old indices after admission, and idempotent projection. Negative cases cover future leakage, wrong release, inactive ID, corrupted allocation and stale cache. An unmet learning witness is a named remaining defect, never a success claim.

### [C14: \#386](https://github.com/Entif-AI/Bilqis-MLX/issues/386)\| Deliver the continuing BRAVO-to-full-atlas training program {#c14:-#386|-deliver-the-continuing-bravo-to-full-atlas-training-program}

Depends on:[A10: \#361](https://github.com/Entif-AI/Bilqis-MLX/issues/361),[A11: \#362](https://github.com/Entif-AI/Bilqis-MLX/issues/362),[C07: \#380](https://github.com/Entif-AI/Bilqis-MLX/issues/380),[C11: \#384](https://github.com/Entif-AI/Bilqis-MLX/issues/384),[C13: \#385](https://github.com/Entif-AI/Bilqis-MLX/issues/385).

Deliver: Encode a continuing program as data. L0 teaches positive identity, direct Boolean and numeric constituents followed by lawful composition. L1 covers released SKOS roles/senses/morphology and individually qualified structured BRAVO category/time frames. L2 continues new concepts, ambiguity, relations and cross-family composition. L3 is optional capacity/hardware extension; L4 packages bounded capabilities. L3/L4 never block earlier education. Interleave qualified L1/L2 subsets according to prerequisites instead of waiting for every source stratum. Read initial A/B/C semantics and numeric scope from the admitted run release, not \#324's frozen workload. Preserve previous skills with the existing teacher and retention. Continue until every eligible SKOS item has declared task coverage; enumerate held items and remediation owners. Give the operator exact launch/resume/source-extension instructions, visible daily outcomes and local resource limits. Attach real training results after owner initiation.

Verify: Dry-run enumerates the entire pinned atlas into covered/ready/held, creates three successive deltas and consumes one BRAVO public fixture stratum. Any source-qualified admitted grade may advance while another grade carries independently protected debt; demonstrate the reciprocal grade-label case under equivalent prerequisites and evidence. Unqualified narrative does not block structured summaries. Future grades require data, not trainer branches. Report actual learned outcomes separately from software readiness.

### [C15: \#387](https://github.com/Entif-AI/Bilqis-MLX/issues/387)\| Close BAMF delivery with fresh EGM review and three-lane receipts {#c15:-#387|-close-bamf-delivery-with-fresh-egm-review-and-three-lane-receipts}

Depends on:[B14: \#375](https://github.com/Entif-AI/Bilqis-MLX/issues/375),[C11: \#384](https://github.com/Entif-AI/Bilqis-MLX/issues/384),[C12: \#381](https://github.com/Entif-AI/Bilqis-MLX/issues/381),[C13: \#385](https://github.com/Entif-AI/Bilqis-MLX/issues/385),[C14: \#386](https://github.com/Entif-AI/Bilqis-MLX/issues/386),[C16: \#382](https://github.com/Entif-AI/Bilqis-MLX/issues/382).

Deliver: Integrate verified lane commits through the sole integration owner. Run a genuinely fresh EGM implementation-readiness/codebase-details review using the public specification, diff, tests and runbook without chat history. Repair blockers/majors, record justified contests and perform one targeted re-audit. Reconcile root outcomes, existing-owner hooks, Development closing links and parser-tested commands. Update the roadmap/registry projections from current receipts while preserving historical rows. Publish one immutable delivery manifest pinning semantic release, Factory/teacher head, topology, compiler, plasticity, codec, tests and artifacts. Keep separate status fields for software delivery and the later student's full-atlas mastery. Actual merge remains an owner decision.

Verify: Each required leaf has an exact commit, proof and EGM disposition or an owned blocker. Links resolve and the dependency graph is acyclic. Shared paths have one writer. A cold reviewer reconstructs create-\>learn-\>retain-\>expand-\>resume from the artifacts alone. Delivery manifest reproduces. Root closeout never invents live training or full-atlas mastery.

### [C16: \#382](https://github.com/Entif-AI/Bilqis-MLX/issues/382)\| Open the first durable BAMF student path before optional projection work {#c16:-#382|-open-the-first-durable-bamf-student-path-before-optional-projection-work}

Depends on:[B13: \#372](https://github.com/Entif-AI/Bilqis-MLX/issues/372),[C02: \#371](https://github.com/Entif-AI/Bilqis-MLX/issues/371),[C03: \#376](https://github.com/Entif-AI/Bilqis-MLX/issues/376),[C05: \#378](https://github.com/Entif-AI/Bilqis-MLX/issues/378),[C08: \#374](https://github.com/Entif-AI/Bilqis-MLX/issues/374).

Deliver: Finish the production create/dry-run/resume CLI dispatch for the current admitted source release as soon as the complete neural, teacher and custody path works. This is the same persistent BAMF lineage later expanded by C07, not a disposable model-size contestant. A separate disposable witness checks the command and rollback before the operator starts the new student. Record initial active ABI, source/curriculum/teacher identities, topology, seed, optimizer hyperparameters, parameter-bank shape and all-zero new moments. Require a new empty run directory, not an old student path. Read the currently admitted A/B/C scope and introduce foundations through its ordinary Factory plan. Expose existing dashboard metrics immediately; C11 adds the larger atlas/cockpit views later. Akasha materialization, the low-bit cache and private journal intake are parallel delivery work and do not block the first optimizer update. Publish one exact owner-start command and one cold-resume command after parser/preflight verification. Predecessor trace: BAMF-REQ-022/024; the implementation follows the explicit BAMF-0.2 contract repeated here. C16 owns the foundation successor launch witness: at least one source-valid end-to-end retained capability improvement, complete rollback of a deliberately damaging disposable candidate, and cold-resume equivalence. This exact-head receipt satisfies the BAMF foundation launch gate. C13 is the later expanded-system release qualification and is not a prerequisite of C16 or foundation training.

Verify: Fresh preflight creates no neural updates and reports the exact run identity. A disposable creation/update/cold-resume traverses the same entrypoint. An old or occupied run directory is protected. Missing optional graph/cache services do not prevent the admitted foundation path. The operator's existing learner is untouched. The disposable foundation witness must demonstrate genuine source-valid retained improvement, complete rejected-candidate rollback and cold-resume equivalence on the actual BAMF/replay code. Its exact-head receipt completes C16 and is sufficient for the operator to start the first persistent lineage. Later persistent-student learning receipts are subsequent operating evidence, not another prerequisite of the launch they follow. C16 acceptance records parent and retained generation IDs, strictly improved fresh complete-solver target score, preserved cumulative retention, rejected-candidate complete-state identity, and equivalent cold-resume output/next update.

# 

# SOURCE AND EVIDENCE REGISTER {#source-and-evidence-register}

\[P1\] Generative Curriculum Factory, SPEC-0001: [https\://github.com/Entif-AI/Bilqis-MLX/blob/codex/337-replay-349-20261026/docs/specifications/0001\_GENERATIVE\_CURRICULUM\_FACTORY.md](https://github.com/Entif-AI/Bilqis-MLX/blob/codex/337-replay-349-20261026/docs/specifications/0001_GENERATIVE_CURRICULUM_FACTORY.md)

\[P2\] Current Bilqis operating/teacher authority: [https\://github.com/Entif-AI/Bilqis-MLX/blob/codex/337-replay-349-20261026/AGENTS.md](https://github.com/Entif-AI/Bilqis-MLX/blob/codex/337-replay-349-20261026/AGENTS.md)

\[P3\] Frozen A/B/C learning qualification, issue \#324 and PR \#336: [https\://github.com/Entif-AI/Bilqis-MLX/issues/324](https://github.com/Entif-AI/Bilqis-MLX/issues/324)   
[https\://github.com/Entif-AI/Bilqis-MLX/pull/336](https://github.com/Entif-AI/Bilqis-MLX/pull/336)

\[P4\] Replay-salvaged teacher and dashboard, issue \#337 and PR \#340: [https\://github.com/Entif-AI/Bilqis-MLX/issues/337](https://github.com/Entif-AI/Bilqis-MLX/issues/337)   
[https\://github.com/Entif-AI/Bilqis-MLX/pull/340](https://github.com/Entif-AI/Bilqis-MLX/pull/340)

\[P5\] Merged SKOS/RDF/Falkor/Akasha corpus, issue \#19, parent gates \#22–\#27, PR \#291: [https\://github.com/Entif-AI/Bilqis-MLX/issues/19](https://github.com/Entif-AI/Bilqis-MLX/issues/19)   
[https\://github.com/Entif-AI/Bilqis-MLX/pull/291](https://github.com/Entif-AI/Bilqis-MLX/pull/291)

\[P6\] Semantic ABI/AST/lesson single-authority bridge, issues \#292–\#295: [https\://github.com/Entif-AI/Bilqis-MLX/issues/292](https://github.com/Entif-AI/Bilqis-MLX/issues/292)   
[https\://github.com/Entif-AI/Bilqis-MLX/issues/293](https://github.com/Entif-AI/Bilqis-MLX/issues/293)   
[https\://github.com/Entif-AI/Bilqis-MLX/issues/294](https://github.com/Entif-AI/Bilqis-MLX/issues/294)   
[https\://github.com/Entif-AI/Bilqis-MLX/issues/295](https://github.com/Entif-AI/Bilqis-MLX/issues/295)

\[P7\] Factory-v2 stack, PR \#290, \#334, \#335 and issue \#321:   
[https\://github.com/Entif-AI/Bilqis-MLX/pull/290](https://github.com/Entif-AI/Bilqis-MLX/pull/290)   
[https\://github.com/Entif-AI/Bilqis-MLX/pull/334](https://github.com/Entif-AI/Bilqis-MLX/pull/334)   
[https\://github.com/Entif-AI/Bilqis-MLX/pull/335](https://github.com/Entif-AI/Bilqis-MLX/pull/335)   
[https\://github.com/Entif-AI/Bilqis-MLX/issues/321](https://github.com/Entif-AI/Bilqis-MLX/issues/321)

\[P8\] V1 model topology and current MLX forward: [https\://github.com/Entif-AI/Bilqis-MLX/blob/codex/337-replay-349-20261026/bilqis\_mlx/runtime/model\_topology.py](https://github.com/Entif-AI/Bilqis-MLX/blob/codex/337-replay-349-20261026/bilqis_mlx/runtime/model_topology.py)   
[https\://github.com/Entif-AI/Bilqis-MLX/blob/codex/337-replay-349-20261026/bilqis\_mlx/runtime/mlx\_parity.py](https://github.com/Entif-AI/Bilqis-MLX/blob/codex/337-replay-349-20261026/bilqis_mlx/runtime/mlx_parity.py)

\[R1\] MLX RoPE primitive: [https\://ml-explore.github.io/mlx/build/html/python/\_autosummary/mlx.core.fast.rope.html](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.fast.rope.html)

\[R2\] MLX fused SDPA and native GQA: [https\://ml-explore.github.io/mlx/build/html/python/\_autosummary/mlx.core.fast.scaled\_dot\_product\_attention.html](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.fast.scaled_dot_product_attention.html)

\[R3\] Compressed Convolutional Attention / CCGQA: [https\://arxiv.org/abs/2510.04476](https://arxiv.org/abs/2510.04476)

\[R4\] Block Attention Residuals: [https\://arxiv.org/abs/2603.15031](https://arxiv.org/abs/2603.15031)

\[R5\] Engram conditional memory: [https\://arxiv.org/abs/2601.07372](https://arxiv.org/abs/2601.07372)

\[R6\] TurboQuant online vector quantization: [https\://arxiv.org/abs/2504.19874](https://arxiv.org/abs/2504.19874)

\[R7\] Rosetta v3.0.0 Core Spine Specification: canonical Rosetta repository and current protocol authority: [https\://github.com/Entif-AI/rosetta](https://github.com/Entif-AI/rosetta)

\[R8\] W3C SKOS Reference: [https\://www\.w3.org/TR/skos-reference/](https://www.w3.org/TR/skos-reference/)

\[R9\] W3C Shapes Constraint Language: [https\://www\.w3.org/TR/shacl/](https://www.w3.org/TR/shacl/)

# HISTORICAL SOURCE INVENTORY {#historical-source-inventory}

* [ETR-2026-12 \- Entif.AI Unified Cognitive Architecture (v0.5.9) \- Google Docs](https://docs.google.com/document/d/18xxQ_VlVVJMYBO0IbOzYkxJhalAgUNbszU72odBKXdg/edit?tab=t.0#heading=h.pmmdbrpvcfsy)

* [IndraNet Draft Manuscript v0.5.0 \- Google Docs](https://docs.google.com/document/d/1Xb8v3oA86Twp0vOWpe586N3era2wrPYFp8i9X-2TFjk/edit?tab=t.0)

* [GNOSIS v0.4.0 \- Entif AI Publication Draft \- Google Docs](https://docs.google.com/document/d/1SL984KuWaxM2CdDz4mGS543FZbCOr_cirlhj-yGaoYw/edit?tab=t.0#heading=h.xefjamnxvpc2)

* [ETR-2026-09 \- Forget Me Not (Stage 2\) \- Google Docs](https://docs.google.com/document/d/11h1WNWqrMFYQVifTFPGvywuliWCTuVD4e0f8U2ldnE4/edit?tab=t.0#bookmark=id.1nk1ehothi9l)

* [ETR-2026-14 \- SÍ SÉ SON: Salient Impact, Exigence and Osmotic Novelty \- Google Docs](https://docs.google.com/document/d/1rHto2gpUWTYOV5k3s8_62wHYefKk1IdGyjaoG5HAeys/edit?tab=t.0#heading=h.gnsrs0g8f1to)

* [Bilqis Roadmap Supplement \| Alpha Exit, Evidence Transfer, and Mainline Acceleration \- 20261011 \- Google Docs](https://docs.google.com/document/d/1x1jtvd1KCfcu7nkz3sLgbaPCBBTEd8NvDeZFaBR-67I/edit?tab=t.0#heading=h.g6iz35pwtmck)

* [Metacognitive Atlas Rationality Roadmap Checkpoint v0.1 \- Google Docs](https://docs.google.com/document/d/1Lqns4QQFKwyMtKnGktHqCsi7eqpt46UXtMkM-ggRy4U/edit?tab=t.0)

* [Bilqis MLX \| Champions, Soups, Golden Ancestors & Grade Advancement \| Governing Specification v1.0 \| 2026-10-18 \- Google Docs](https://docs.google.com/document/d/1UURzJNes-tB7AZU2pSjB9-q-aWholnjtGbbUJcLTgXI/edit?tab=t.0#heading=h.xdpeymita1ce)

* [Bilqis Roadmap \- 20261006 \- Google Docs](https://docs.google.com/document/d/19mUp81fRDxBVwc6gX7xNRo6rIeIgMJqyVYo_UQPM5xw/edit?tab=t.0)

* [ADI \- Codex Sequential Execution Dossier and Quota-Burn Prompt v0.1 \- Google Docs](https://docs.google.com/document/d/13zCk-NGmJdi-5zW1zZY0trhBVZ9DUzlDrSZdKb-urPo/edit?tab=t.0#heading=h.57srtpoapr48)

* [Adaptive Decision Intelligence \- Roadmap Checkpoint v0.1 \- Google Docs](https://docs.google.com/document/d/1WjaUgn0uFMjGVzyZv5GAN-6DVr3eFQOIlgP5D3f28GM/edit?tab=t.0#heading=h.x9u96rafyga3)

* [Bilqis \+ Decision-Native Test Stories \- Semantic Navigation Research Program v0.2 \- Google Docs](https://docs.google.com/document/d/1Pcg6rdpdnKWAPFcjoJ8DUt7GpgiK3DrleLWFhzQW0es/edit?tab=t.0#heading=h.bdmqxle1ykp)

* [Bilqis \+ Decision-Native Test Stories \- Control Sheet v0.2 \- Google Sheets](https://docs.google.com/spreadsheets/d/1Z0HrKolMlA2Hh5e8CwG4gXXd5jsOFGNC0TFUVbCVB7A/edit?gid=1906362111#gid=1906362111)

* [Bilqis Batch Planner and Codex Prompt Compiler \- Google Docs](https://docs.google.com/document/d/1vIe_0dG1J1FSBlXX9H6MZLlOOHw6bFTOiiwF01rmZwc/edit?tab=t.0#heading=h.e5kmwmiv94v8)

* [Prepaying Semantics v0.5.1 \- Google Docs](https://docs.google.com/document/d/1dAvu7daQBfGJn1g6akpSxAHVpcf5znifdxktvWq7EQs/edit?tab=t.0#heading=h.8jtqyoc4lqci)

* [Conjoined Triangle of Bilqis \- Roadmap & Launch Tracker \- Google Sheets](https://docs.google.com/spreadsheets/d/13j48n35WiPiXjVlaNqf-7QZS1NWF-3oq_qd-4ESIDdY/edit?gid=731389185#gid=731389185)

* [Bilqis Curriculum Registry \- Version, Lessons, Prerequisites and Champion States \- Google Sheets](https://docs.google.com/spreadsheets/d/1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so/edit?gid=269564263#gid=269564263)

* [20261025 \- BRAVO \- Bilqis, Rosetta, Akasha, VieDay and OMoC \- EntifAI \- Google Docs](https://docs.google.com/document/d/1HBji5KoYnXbHA3qtl4Qh33d8M_feHp3lC-opIijsOyY/edit?tab=t.0)

* [20261019-2357 \- Bilqis \- Future-State Architecture Blueprint \- Google Docs](https://docs.google.com/document/d/13wlP4c-aF18vRcdFKoMGAJqcoXj1rMwHsO8bw2fEALw/edit?tab=t.0#heading=h.umt5m4mmai70)

* [20261020 \- Bilqis MLX \- SPEC \- Autonomous JIT Curriculum \- Google Docs](https://docs.google.com/document/d/1brN7eFA0ptaNO8D9HKcXqQ3sC_013icYhauceD5Y6Xc/edit?tab=t.0#heading=h.ew0hues8aqgc)

* [ChatGPT \- Explain Token Costs \- 20260929 0632.md \- Google Docs](https://docs.google.com/document/d/1y4cD5QBVVnMfx0etl3Rf03m3CVquq-gT/edit)

* [\[2604.02560\] Dependency-Guided Parallel Decoding in Discrete Diffusion Language Models](https://arxiv.org/abs/2604.02560?utm_source=chatgpt.com)

* [\[2602.23225\] Why Diffusion Language Models Struggle with Truly Parallel (Non-Autoregressive) Decoding?](https://arxiv.org/abs/2602.23225?utm_source=chatgpt.com)

* [\[2503.09573\] Block Diffusion: Interpolating Between Autoregressive and Diffusion Language Models](https://arxiv.org/abs/2503.09573?utm_source=chatgpt.com)

* [DiffusionGemma — Google DeepMind](https://deepmind.google/models/gemma/diffusiongemma/?utm_source=chatgpt.com)

* [\[2211.17192\] Fast Inference from Transformers via Speculative Decoding](https://arxiv.org/abs/2211.17192?utm_source=chatgpt.com)

* [\[2603.15569\] Mamba-3: Improved Sequence Modeling using State Space Principles](https://arxiv.org/abs/2603.15569?utm_source=chatgpt.com)

* [\[2505.05522\] Continuous Thought Machines](https://arxiv.org/abs/2505.05522?utm_source=chatgpt.com)

* [\[2412.09871\] Byte Latent Transformer: Patches Scale Better Than Tokens](https://arxiv.org/abs/2412.09871?utm_source=chatgpt.com)

* [\[2412.06769\] Training Large Language Models to Reason in a Continuous Latent Space](https://arxiv.org/abs/2412.06769?utm_source=chatgpt.com)

* [TinyStories: How Small Can Language Models Be and Still Speak Coherent English?](https://arxiv.org/html/2305.07759v2)

* [feat(skos): hey yo hey yo, check it ma homies n hos, reppin da only hi skos, bless if ya kno, den ya knos by Entif-AI · Pull Request \#291 · Entif-AI/Bilqis-MLX](https://github.com/Entif-AI/Bilqis-MLX/pull/291)

* [Bilqis \| Compile New Ithkuil into a standards-first SKOS/RDF semantic corpus with FalkorDB materialization · Issue \#19 · Entif-AI/Bilqis-MLX](https://github.com/Entif-AI/Bilqis-MLX/issues/19)

# SUPPLEMENTAL SOURCE AND EVIDENCE REGISTER {#supplemental-source-and-evidence-register}

Primary implementation sources are the pinned repository files listed in every issue, the merged SKOS compiler, current Factory specifications 0001/0002/0003/0005-0082 as applicable, ADR-094/103 and the replay evidence. The supplied Curriculum Registry and Conjoined Triangle workbooks supply semantic/historical/program crosswalks; live source and accepted successor amendments govern execution.

The private source record also retains BAMF-0.1, the expanded BAV engineering specification, BRAVO v0.3.3, Akasha v0 MVP, Rosetta v3 Core Spine, GNOSIS v0.4, SÍ SÉ SON, the 2025 synthesis, CTM/TRM/Nested Learning comparisons and mHC/Engram discussion. Source snapshots are hashed in the delivery manifest. Public issues contain screened implementation contracts and public repository references; raw private corpora stay in their original storage.

## External engineering references: {#external-engineering-references:}

• Google Elephant-Goldfish Model, pinned commit: https\://github.com/google/elephant-goldfish-model/tree/b3a35956759bf7f024af2ff061b2e0b44b438e4c

• MLX native grouped-query SDPA: https\://ml-explore.github.io/mlx/build/html/python/\_autosummary/mlx.core.fast.scaled\_dot\_product\_attention.html

• MLX RoPE: https\://ml-explore.github.io/mlx/build/html/python/\_autosummary/mlx.core.fast.rope.html

• Compressed Convolutional Attention: https\://arxiv.org/abs/2510.04476

• Attention Residuals: https\://arxiv.org/abs/2603.15031

• Conditional Memory / Engram: https\://arxiv.org/abs/2601.07372

• TurboQuant: https\://arxiv.org/abs/2504.19874

References motivate the selected engineering mechanisms. Exact operational choices are specified above and in the work items, allowing implementation without rereading an entire research literature.

# 24\. ARCHITECTURAL DECISION RECORD \| BAMF-0.2 {#24.-architectural-decision-record-|-bamf-0.2}

## ADR-BAMF02-001 \| 27 OCTOBER 2026 \| Current design and source-of-truth alignment {#adr-bamf02-001-|-27-october-2026-|-current-design-and-source-of-truth-alignment}

Status: OWNER-ACCEPTED for BAMF-0.2 documentation and implementation work orders; not proof of working code, merged PR, curriculum admission or human-started training.

Decision: All BAMF-0.2 grades use one grade-neutral teaching/assessment scheduler. Historical letter-specific Grade-B allocation or debt circulation is not carried into the new trainer. Candidate selection uses admitted source, prerequisite closure, independent fresh outcomes, whole-school protection and practical resource budgets, without per-grade quotas or privileges. The grade letter describes admitted content, not scheduling authority.

Identifiers: BAMF-0.2 is the sole current name for this successor. All current requirement references use BAMF-REQ-001 through BAMF-REQ-024. Current operator reason codes use BAMF\_\* and the architecture selector is bamf-atlas-v2. Do not invent BAV compatibility aliases absent evidenced runtime or persisted consumers.

Related contracts: Canonical native specification BAMF-0.2-SPEC-001, 27 October 2026, https\://docs.google.com/document/d/17wc-tYdQGlHydP38aMlMtBismpEywIPs4IiMUXnKpxc/edit ; selected 12×768 CCGQA/Block-AttnRes/Engram architecture, exact source-bound frames, source-gold Factory, native AdamW custody and three implementation lanes remain unchanged.

Verification and supersession: This ADR supersedes contradictory Grade-B-specific scheduling text anywhere in BAMF-0.2 variants, Markdown architecture, GitHub issue bodies, launch plans and their derivative summaries. BAMF-0.1 and older student/teacher artifacts remain historical and untouched. Future material changes append a numbered, dated ADR to the two approved native BAMF-0.2 documents, reconcile the repository architecture, and update affected implementation issues. A rejected alternate plan is not an operative alignment target.

## ADR-BAMF02-002 \| 27 OCTOBER 2026 \| Behavioral acceptance over identifier references {#adr-bamf02-002-|-27-october-2026-|-behavioral-acceptance-over-identifier-references}

Status: OWNER-SCOPED CONFORMANCE CLARIFICATION. Operative issue contracts were tightened; this is not proof they were implemented or tested.

Decision: A BAMF-REQ reference, F-case label, issue-body hash or described test is traceability only. Executable acceptance requires independently specified input fixtures, source/capability qualification, exact expected outcomes, negative failure dispositions, retained model/optimizer/rights invariants, actual observed results and reviewer receipts.

Required discriminators: (1) Grade neutrality is proven by permuting labels on otherwise equally admissible candidate cohorts without changing teacher selection, retention, graduation or debt handling; both directions of carried debt must work. (2) Concealed target perturbations cannot change inference inputs/logits. (3) Family-related paraphrases are not independent holdouts and rubric translation cannot fake learning. (4) Rights changes invalidate cached K/V regardless of matching vector bytes. (5) v1 six-layer checkpoints cannot resume as v2. (6) Recurrent superseded facts after reported remediation escalate a process fault. (7) Multiple distinct minor discrepancies may create a qualified aggregate pattern without promoting forbidden source evidence. (8) Actual retained neural improvement and complete rejected-candidate rollback survive cold resume.

Ownership: The affected issue implementation and acceptance sections, especially C02 \#371, C03 \#376, C05 \#378, C06 \#379, C09 \#377, C14 \#386, B01 \#346, B14 \#375, A10 \#361, A12 \#364, C13 \#385 and C15 \#387, carry explicit discriminating tests. The full 24 BAMF-REQ and 20 negative fixture contract remains in BAMF-0.2-SPEC-001. Any unexecuted fixture is UNVERIFIED; C15 must not call it compliant merely because a ticket cites it.

Boundary: This clarification does not rewrite BAMF-0.1, authorize private material in public issues, merge PR \#388, change the live trainer or imply a learner exists. Future substantive changes append dated ADRs in all current BAMF-0.2 document variants.

## ADR-BAMF02-003 \| 27 OCTOBER 2026 \| Motif fallback and EGM tensor equivalence {#adr-bamf02-003-|-27-october-2026-|-motif-fallback-and-egm-tensor-equivalence}

Status: ACCEPTED clarification of the already-selected BAMF-0.2 execution contract.

The descriptive "factorized fallback motif" at a miss must not be interpreted as a second trainable or gated residual. Factorized semantic/role/frame features already contribute to h. At each of the two declared motif sites, an eligible verified exact/structural slot contributes the specified gated projection; a miss returns h unchanged while preserving those factorized features. Pending-key allocation is a separate accepted-candidate transaction. This matches the EGM-resolved Tensor Ledger, avoids undocumented parameters, and requires B07/B08 literal hit/miss proof at both read sites. The historical descriptive wording is superseded only for this computation; source identity/rights, motif capacity and rollback rules do not change.

## ADR-BAMF02-004 \| 27 OCTOBER 2026 \| Functional, recursive, self-maintaining curriculum Factory {#adr-bamf02-004-|-27-october-2026-|-functional,-recursive,-self-maintaining-curriculum-factory}

Status: OWNER-DIRECTED DESIRED-STATE AMENDMENT. The operative native artifacts are this Blueprint and BAMF-0.2-SPEC-001 only. No neural implementation, training, merge or executed proof is implied by this specification decision.

DECISION: BAMF-0.2 consumes the existing functional, composable, source-qualified Factory under SPEC-0001. GradeDefinition is a declarative grouping and reporting unit, not a scheduler algorithm, implicit prerequisite, automatic promotion permit or learning exception. No rule requires Grade B to graduate before Grade C merely because of its letter, and no rule exempts Grade C from Grade B merely by letter. Every grade uses the same current source-eligibility, typed prerequisite, legitimate debt, teaching, independent assessment, retention, promotion and admission mechanisms. An actual source-backed cross-domain prerequisite, rights hold or current approved admission condition still binds, independent of grade name.

FUNCTIONAL CORE: Model the planning input as an immutable, versioned CurriculumSnapshot containing canonical source/ABI/release and rights, typed capability/constituent DAG, source-held and implementation-uncovered coverage, staged/admitted releases, learner evidence and debt, teacher/policy epoch, resource bounds and authorized lease scope. Pure and deterministic transitions reconcile(snapshot, qualified\_event) \-\> new snapshot, plan(snapshot, domain\_rules) \-\> frontier \+ coverage delta \+ typed disposition, and compile(plan, source\_adapters, independent\_oracles) \-\> verified teaching/assessment proposals. Recursive prerequisite closure introduces smallest lawful constituent releases before compositions. Identical snapshots and event inputs produce identical results; retry is idempotent; a true cycle, hold or fixed point yields a bounded explanatory disposition rather than an infinite loop.

DOMAIN-SPECIFIC RULES: Construction, oracle, coverage and qualification rule subsets come from the admitted semantic family, typed operator signature, answer modality and source contract, never the grade label. Boolean truth/polarity patterns, integer successor/range/arithmetic patterns and, when source-qualified and admitted, world-model actor/state/time/causal patterns can use different legal programs inside the one Factory. Changing domain inside one grade can change the applicable rules; relabeling an unchanged domain into a different grade cannot. A new source family is registered as data/adapters, not hard-coded branches in the scheduler, teacher, promotion logic or trainer.

SELF-MAINTAINING SHELL: For each approved source, assessment, correction, admission or policy event, reconcile immutable state; recompute ready and held coverage; compile and verify the next bounded delta; stage it; admit it only through the existing single-authority boundary and persisted atlas lease; record the accepted receipt; then replan. Continue within the already authorized scope until a real fixed point, evidence wait, rights hold, uncovered constructor or lease boundary. No planner may mint semantic authority, self-ratify mastery, bypass independent gold, perform out-of-lease admission or start a live optimizer session. Preserve old generations and matching AdamW; one human-started MLX writer remains sovereign.

REQUIRED BEHAVIORAL WITNESSES: (1) grade-label permutations with symmetric unfinished debt give equivalent scheduling, promotion, retention and lease dispositions; (2) actual source-declared prerequisite edges block regardless of letter, while unrelated ready work progresses; (3) Boolean/integer/world-model rule sets vary by source type but do not alter grade-level control; (4) three successive recursive deltas and a correction-driven replan work from immutable coverage; (5) fixed-point/held-only corpora terminate with typed source/implementation debt; (6) staged retry, admission idempotence and cold resume preserve exact next-state identity; (7) no concealed gold or unauthorized neural/source mutation. Owners: A08 \#358, A09 \#360, C02 \#371, C03 \#376, C05 \#378, C07 \#380, C14 \#386, C15 \#387, C16 \#382, B09 \#368. Full requirements/fixtures retain their independent executable gates. No current planning receipt may be called EXECUTED\_PASS.

## Implementation work-packaging clarification \| 27 OCTOBER 2026 \| Lossless recursive issue decomposition (non-normative navigation) {#implementation-work-packaging-clarification-|-27-october-2026-|-lossless-recursive-issue-decomposition-(non-normative-navigation)}

BAMF-0.2 is being prepared for economical implementation by recursively decomposing oversized GitHub work owners into smaller self-contained child issues. This does NOT weaken, shorten, simplify, replace or remove any requirements, algorithms, schemas, engineering specifications or acceptance criteria. The original 43 owner issues and these two approved native Documents retain their full contracts. Child issues declare bounded code outcomes, exact prerequisites, input/output interfaces, touched sources and implementation acceptance; a parent integrates and retains all requirements. Lower-tier agents execute the smallest ready child; if it remains too large, it is decomposed again. The A09 curriculum-planning parent \#360 now has native children A09.1 \#389 (intermediate group with A09.1a \#390 immutable planning snapshot and A09.1b \#391 qualified-event reconciliation), A09.2 \#392 typed prerequisite closure, A09.3 \#393 bounded deterministic selection, A09.4 \#394 resumability/fixed points and A09.5 \#395 Factory integration. Every descendant remains traceable to A09 \#360 and ADR-BAMF02-004. Other broad parents can be decomposed in the same lossless way. This is specification/issue alignment and work shaping only: no BAV predecessor crosswalk, current execution-proof run, live training or newly imposed research experiments.

# BAMF-0.2 THREE-LANE IMPLEMENTATION ISSUE INDEX \| 27 OCTOBER 2026 \| WORK-PACKAGING RECEIPT, NOT AN ARCHITECTURAL AMENDMENT {#bamf-0.2-three-lane-implementation-issue-index-|-27-october-2026-|-work-packaging-receipt,-not-an-architectural-amendment}

The implementation backlog is now recursively groomed across all three workstreams: 43 complete original technical owner issues (13 Lane A semantic authority/Factory, 14 Lane B neural model/optimizer, 16 Lane C teacher/integration/training) and 157 bounded native GitHub descendant issues (A 44 including the earlier A09 tree, B 53, C 60). Cross-cutting parent issues A08, A09, B01, B09, C07, C14, C15 and C16 have intermediate groups with implementable grandchildren.

The complete source engineering prescriptions, architecture, rights, grade-neutral functional recursive Factory invariants, neural/AdamW custody and original acceptance criteria remain in the original owner contracts and these approved Docs, without deletion or simplification.

Child packets repeat exact assigned source clauses, relevant interfaces, existing acceptance and dependency/turn-in expectations; each is an implementable outcome rather than a weaker requirement. Each child can be further subdivided as needed. No predecessor BAV crosswalk, new scientific experiment, execution-proof program, new live trainer launch or software implementation was performed by this issue-grooming pass.

The GitHub native hierarchy has 51 verified parent-child groups and 200 total issue nodes with an acyclic dependency/ownership graph. The local executable static issue-contract check passes 43/43 parent mirrors and all 157 indexed child mirrors, and a read-only GitHub postflight confirmed exact live/body equality for every one. All 3 lane-parent issues, \#342/\#343/\#344, now direct agents to the deepest dependency-ready child rather than the original monolithic parent. Public planning repository: Entif-AI/Bilqis-MLX branch codex/bamf02-specification-20261027, commit 6aa5ff386e9a3087822f8335ccf42754d94d1ff2, planning PR \#388, OPEN and unmerged. 

Navigational registry: docs/tasks/bamf-0.2/children/registry.json; human child index: docs/tasks/bamf-0.2/children/README.md; full parent archive: docs/tasks/bamf-0.2/ISSUE\_BOOK.md; launch guidance: docs/tasks/bamf-0.2/EXECUTION\_LANE\_A.md, EXECUTION\_LANE\_B.md and EXECUTION\_LANE\_C.md.

First possible implementation entrypoints, conditioned on current dependency and branch readiness: A01.1 \#396, B01.1a \#434 and C01.1 \#486. Never infer software completion from issue creation, parent-child link validation or document parity.