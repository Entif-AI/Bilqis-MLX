# A08.1a source-qualified family census candidate

Issue: A08.1a #417, parent A08.1 #416 / A08 #358.
Lane: `codex/bamf02-a-semantics`.
Reviewed unified consumed before implementation: `6b54600`.
Candidate provenance: isolated `e64e703`, cherry-picked into Lane A
as `ea89131`. The separate earlier untracked variant was preserved
byte-for-byte in the durable run recovery directory, not discarded.

## Source/implementation boundary

`bilqis_mlx/factory/skos_curriculum.py` defines nine reusable
source-family matchers covering positive identity, typed roles,
attested relations, morphology composition/decomposition,
Boolean/numeric composition, scope/modality/time and released
transformations. It inventories the frozen A01 `FrozenAtlasSnapshot`
before inspecting any lesson constructor or checker. All qualified
obligations remain `IMPLEMENTATION_UNCOVERED`; this candidate does
not mint learning credit, release a capability, train a model, or
pretend A08.1b constructors exist.

Unknown source tables/formal families become visible
`SOURCE_FAMILY_RULE_UNCLASSIFIED` implementation debt, never a
source-qualification hold. Held, IR-only and structural nonconcept
rows remain separately counted with their original semantic ID,
owner, reason and source disposition. Formal-only ABI identities
are not lost merely because they lack `FrozenAtlasConcept` records.

The original owner API `compile_semantic_curriculum(atlas,
source_adapters, learned_frontier) -> CurriculumCandidateSet`
now bridges the frozen census to the later A08.1b constructive
contract. The caller's adapter availability and claimed learner
exposure/qualification cannot change source eligibility or
promote `ADAPTER_READY`, `EXPOSED` or `QUALIFIED`. The output
retains `LEARNING_UNVERIFIED` per obligation and as its overall
learning disposition, with separate unverified claims.

## Real pinned A01 source census

Source corpus: pinned local A01 conformance artifact under the
Lane A execution directory; verified against the A01.2/A01.3
published counts.

- Atlas source concepts: **9,079**
- Formal-only ABI identities: **228**
- Source-eligible ABI identities: **9,307**
- Source-held rows: **1,052**
- Source-IR-only rows: **9,488**
- Source-emitted nonconcept rows: **6,062**
- Required source-family obligations: **12,351**
- Implementation-uncovered obligations: **12,351**
- Required concept-backed families: **5**
- Pending structural-only families: **3**

## Verification and boundary

Owner `test_skos_curriculum.py`: **12 passed, 0 failed,
0 skipped**, including real pinned corpus, release isolation,
unclassified source debt, forged grammar host/relation/formal
authority, held identity, constructor-independent denominator,
original owner API, foreign learner release and forged family
adapter rejection.
Adjacent A01 `test_atlas_projection.py` and A06
`test_atlas_features.py` suites: **22 passed, 0 failed,
1 optional skip**. No new `skos_curriculum.py` static
error-control or module-size findings were introduced.
The previous competing untracked candidate passed only four
synthetic tests and was preserved separately for comparison.

The A08.1a inventory is a staged source census, not a completed
constructive curriculum. A08.1b must bind constructors/checkers and
the parent must prove zero uncovered obligations before claiming
`COMPLETE_ATLAS_COVERAGE`. Independent EGM and final branch/issue
turn-in are pending; no A08 parent closure or self-merge is claimed.
