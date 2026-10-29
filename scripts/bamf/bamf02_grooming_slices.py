"""Curated lossless boundaries for BAMF-0.2 implementation owners.

Each tuple is (independently deliverable outcome, exclusive sentence end index).
Indices address the unchanged live parent's Implementation prescription, after
the stable sentence splitter in bamf02_groom_backlog.py. No specification text
is shortened or replaced. A09 was published in an earlier verified batch.
"""

SLICES = {
    # LANE A: semantic authority, representations and generative curriculum.
    "A01": [("Bind the pinned corpus and source-qualified semantic identities", 4), ("Build deterministic ABI and immutable semantic-release files", 8), ("Expose source-hold census and the database-free atlas reader", 12)],
    "A02": [("Allocate stable semantic banks and activate admitted identity rows", 4), ("Stage capacity expansion with unchanged old tensors and moments", 8), ("Mirror allocation lineage and publish bank resource estimates", 11)],
    "A03": [("Declare canonical typed AST and occurrence-aware frame records", 4), ("Validate frame bindings and preserve atomic fallback", 7), ("Ship approved formal and source frame adapters with typed errors", 11)],
    "A04": [("Encode and decode exact compact-frame v1 u64 records", 4), ("Implement canonical extended-frame fallback and shared accessors", 7), ("Preserve ordered constituent metadata and codec identity", 11)],
    "A05": [("Compile causal incremental partial-frame sequences", 4), ("Produce source-position maps and isolated prefix-boundary receipts", 7), ("Separate hidden answers and enforce bounded packed sequence length", 11)],
    "A06": [("Build deterministic source-factor and graph-feature projection", 3), ("Publish immutable local AtlasFeatures and independent reference vectors", 7)],
    "A07": [("Register typed source-qualified deterministic operators", 3), ("Separate solver applicability from independent evaluation gold", 6), ("Emit bounded execution receipts and typed compositional DAG nodes", 9)],
    "A08": [("Inventory source-qualified semantic families and constructor coverage", 2), ("Compile constructive lessons and independent typed checkers", 4), ("Bind stable capability identities to existing Factory releases", 7), ("Register Boolean integer and qualified world-model rules without grade branches", 11)],
    "A10": [("Bind qualified BRAVO source strata and provenance-safe records", 4), ("Compile typed reconstructions and held-out family-separated lessons", 8), ("Deliver literal public BRAVO fixtures with lawful cohort and rights lineage", 12)],
    "A11": [("Implement checker-grounded structural lesson transformations", 3), ("Produce bounded ambiguity alternatives and deterministic noise lineage", 6), ("Connect source-valid contrasts to the existing Factory teacher", 8)],
    "A12": [("Audit current consumers against one admitted semantic source authority", 3), ("Cut over current aliases and enforce semantic import boundaries", 6), ("Prove data-only successor admission and source-held exclusion", 8)],
    "A13": [("Define and validate eligible source-bound context and join records", 4), ("Expose immutable context projections to solver attention and caches", 7), ("Propagate contextual invalidation while retaining local public fixtures", 10)],
    # LANE B: frozen atlas-native geometry and mutable neural state.
    "B01": [("Freeze v2 architecture identity and explicit legacy-reader isolation", 2), ("Declare the complete typed FP32 parameter and tensor registry", 5), ("Reconcile parameter counts adapters and frame feature capacities", 8), ("Separate generation bank extents and validated topology config", 11), ("Reject v1 neural-state promotion across v2 generation boundaries", 14)],
    "B02": [("Compose source-factorized identity embeddings with active-row masking", 4), ("Initialize new rows and gather differentiable constituents", 8), ("Match shared tensor registry and validate output-parameter coverage", 12)],
    "B03": [("Implement role-order-sensitive frame encoding and member gradients", 3), ("Preserve legal atomic partial and empty-frame fallbacks", 5), ("Carry nested frame scope handles and observable frame counts", 7)],
    "B04": [("Implement frozen-shape causal depthwise QKV convolutions", 4), ("Wire grouped-query RoPE and zero-safe native MLX attention", 8), ("Bind decode cache identity and literal FP32 attention reference", 11), ("Validate tensor-ledger prefix and constructor consistency", 14)],
    "B05": [("Implement shared depth selection and normalized residual weights", 4), ("Place motif and plasticity boundaries within three group selectors", 7), ("Persist complete selector tensor identities and diagnostics", 11)],
    "B06": [("Build shared recurrent constituent attention with input recall", 4), ("Select bounded prediction-local refinement passes and masked routing", 9), ("Preserve original backbone states and exact frame handle outputs", 14), ("Reconcile refinement tensors with the authoritative registry", 19)],
    "B07": [("Canonicalize full typed motif identities and structural matching", 4), ("Allocate deterministic motif pages and compare collision-safe keys", 7), ("Commit append-only motif allocation only with retained candidate", 10), ("Verify the common declared motif parameter registry", 14)],
    "B08": [("Compute gated exact and structural motif reads with safe misses", 3), ("Persist participating motif state and place the mid-depth read", 5)],
    "B09": [("Introduce identity-initialized FAST adapters and parameter groups", 4), ("Implement FOUNDATION ADAPTIVE update-cadence state", 8), ("Apply per-step legal row participation and optimizer masks", 13), ("Bind accepted promotion events to grade-neutral plasticity transition", 18)],
    "B10": [("Bind tied semantic values and occurrence-aware role outputs", 4), ("Implement finite control decisions and schema-constrained frame output", 8), ("Enforce causal dependency feedback masking and typed answer legality", 12), ("Match AnswerPlan v2 and complete readout tensor census", 16)],
    "B11": [("Assemble complete atlas-native forward and registry geometry", 3), ("Unify direct inference gradient retention and championship dispatch", 7), ("Reconcile full model tensor prefixes and mixed-frame integration", 11)],
    "B12": [("Preserve exact native AdamW and per-parameter participation counts", 4), ("Commit or reject complete candidate optimizer and weight transactions", 8), ("Implement preclip row masks and distinct step versus establishment clocks", 12), ("Reconcile shared optimizer manifest and parameter tree", 15)],
    "B13": [("Write versioned content-addressed BAMF state bundles atomically", 3), ("Validate complete generation and cold-resume exact training state", 6), ("Keep disposable caches and historical v1 reader custody separate", 9), ("Reconcile committed parameter schema with checkpoint manifests", 12)],
    "B14": [("Implement deterministic rotated three-bit cache vector coding", 4), ("Reconstruct quantized norms and small-record FP32 fallback", 7), ("Bind derived cache to causal generation and FP32 reference policies", 11), ("Reject revoked source caches and rebuild from eligible FP32 state", 15)],
    # LANE C: integration, teacher, protection, autonomy and delivery.
    "C01": [("Prepare exact replay plus SKOS integration baseline and custody", 4), ("Establish pinned EGM lanes and one-writer source ownership", 8), ("Validate dependencies and prepare bounded worker contracts", 11), ("Publish pinned architecture and lane integration handoff", 14)],
    "C02": [("Adapt executable Factory rows into typed BAMF training inputs", 4), ("Compile source-visible targets and preserve legal modalities", 8), ("Deliver strategy provenance and unified model backend batches", 11), ("Emit teacher feedback and grade-neutral workload receipts", 14)],
    "C03": [("Port replay-salvaged bounded teacher policy and prior evidence", 4), ("Preserve source-scored canaries and shadow-strategy semantics", 8), ("Bind valid mentor advice and report real teacher health", 12), ("Apply grade-neutral capability scheduling and accepted evidence", 17)],
    "C04": [("Plan typed pure exact and neural-capability execution routes", 3), ("Bound source-visible compositions and safe unresolved fallbacks", 6), ("Record provenance-safe route costs and guard gold separation", 9)],
    "C05": [("Evaluate complete solver parent candidate and source-grounded gains", 4), ("Preserve cumulative retention championships and carried mastery debt", 8), ("Accept lawful promotion and evidence only through uniform grade policy", 13)],
    "C06": [("Derive typed Impact Exigency Novelty ordinal evidence", 4), ("Apply grade-neutral dispatcher and bounded teacher priority", 8), ("Aggregate correction trends without claiming source gold", 12), ("Publish causal priority and recovery-observability receipts", 15)],
    "C07": [("Define explicit persisted atlas-admission lease and source scope", 3), ("Stage and atomically adopt lawful Factory successors", 6), ("Handle out-of-scope releases debt and predecessor evidence", 9), ("Implement recursive event-driven self-maintaining admission flywheel", 11)],
    "C08": [("Estimate topology-aware activations and deterministic microbatches", 3), ("Retry bounded allocation without corrupting retained candidates", 5), ("Preserve isolated CPU source workers and runtime resource floors", 8)],
    "C09": [("Index reverse dependencies of semantic and learned artifacts", 4), ("Requalify affected learning state without rewriting historical evidence", 8), ("Propagate corrections through local projections and typed operators", 12)],
    "C10": [("Define immutable Rosetta event and namespace projections", 3), ("Enqueue deduplicated source and learning events without trainer IO", 6), ("Rebuild staging graph projections and enforce public-private boundary", 8)],
    "C11": [("Expose production BAMF create dry-run and resume CLI", 4), ("Display truthful grade-neutral curriculum and learner cockpit", 8), ("Document real operator launch and resource custody commands", 11)],
    "C12": [("Package source-cleared reusable semantic and procedure manifests", 3), ("Bind compatible local plastic deltas and staged imports", 6), ("Validate private-safe exports and local exchange compatibility", 9)],
    "C13": [("Prepare disposable combined-system acceptance and source fixtures", 4), ("Exercise native retained learning rollback and correction scenarios", 8), ("Collect existing guard receipts and responsible issue handoff", 11)],
    "C14": [("Declare constructive L0 and released L1-L2 domain programs", 5), ("Select lawful interleaved stages from admitted release and evidence", 10), ("Deliver source coverage and resource-aware operator runbook", 15), ("Extend recursive grade-neutral domain rules and succession", 20)],
    "C15": [("Integrate completed lane receipts with fresh EGM ownership", 4), ("Publish traceable delivery manifest and roadmap projections", 8), ("Keep software delivery distinct from full school mastery claims", 11), ("Reconcile immutable issue closure receipts and full Factory coverage", 14)],
    "C16": [("Implement persistent BAMF create dry-run and resume entrypoints", 4), ("Bind fresh student topology teacher optimizer and admitted foundations", 8), ("Expose earliest lawful learning readiness without optional blockers", 12), ("Handoff the exact durable human-started student lineage", 17)],
}

# Split the first two substantial outcomes of particularly cross-cutting parents
# under an actual intermediate GitHub issue, producing native grandchildren.
NESTED_FIRST_TWO = {"A08", "B01", "B09", "C07", "C14", "C15", "C16"}

GROUP_TITLES = {
    "A08": "Own the source-family coverage census and constructive checker contract",
    "B01": "Own versioned topology identity and the frozen parameter registry",
    "B09": "Own adapter group identity and the persisted plasticity mode policy",
    "C07": "Own persisted authorization lease and atomic staged-admission interfaces",
    "C14": "Own the source-defined developmental program and interleaved scheduling policy",
    "C15": "Own three-lane integration and immutable delivery-manifest preparation",
    "C16": "Own persistent student create and correctly bound initial generation",
}
