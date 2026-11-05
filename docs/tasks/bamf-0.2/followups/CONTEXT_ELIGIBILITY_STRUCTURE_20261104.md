# #833 context eligibility structural repair

## Trigger and exact scope

Preparing #424 source-checked contrast work encounters `context_eligibility.py`
at 767 LoC on reviewed unified06eb34d0. This is one mandatory structural interruption,
not a recursive cleanup. A13/#354 keeps its source and aggregate acceptance.

Modify `bilqis_mlx/semantics/context_eligibility.py` into the original public
facade. Keep its original schema/constants and imported public names. Create
`bilqis_mlx/semantics/_context_eligibility/` with these cohesive private owners:

| File | Exact original ownership |
| --- | --- |
| `evidence.py` | `_invalid`, `_digest`, `_name`, `_epoch`, `_names`, `frame_evidence_digest`, `member_evidence_digest`, `_envelope_projection`, `_frame_release_matches` |
| `members.py` | `ContextMember`, `ContextEligibility` |
| `sources.py` | `SourceGrant`, `SourceFrontier`, `TaskScope` |
| `results.py` | `ContextPolicy`, `ApprovedFrame`, `EligibleContext`, `ContextHold` |
| `gate.py` | `check_context_eligibility` orchestration and result construction |
| `checks.py` | Pure task, envelope, member-evidence, source-grant and combined-join checks extracted from the original gate |
| `projection.py` | `ApprovedContextProjection`, `project_context` |
| `transition.py` | `C09ContextInvalidation`, `ContextTransition`, `transition_context` |
| `__init__.py` | Private package documentation only |

Each implementation and companion test must remain below 240 LoC. Preserve function
signatures, validation order, return values, exact exception/reason strings,
serialized fields and ordering. Route original module-global runtime lookups
through the public facade to retain patch interception. Preserve public class,
function and method `__module__`/qualname/pickle identities; resolve postponed
annotations without an eager circular import. Use lean annotation imports in
private owners, preserving original public exports in the facade.

The `_digest` contract includes canonical sorted compact UTF-8 JSON, finite-only
numbers and its trailing newline. Frame/member visibility, envelope, approved
sorted grants/handles, projection cache keys and C09 event digests must retain
exact bytes/values. Do not reinterpret rights, epochs, task scope, revocation,
causal visibility, atomic fallback, join compatibility or correction propagation.

## Test ownership and ordered implementation

1. Preserve `semantics/tests/test_context_eligibility.py` as the existing public
   fixture/test-base owner; it is114lines and imported elsewhere. Do not rename
   its exports. Keep the existing focused companions under `semantics/tests/context/`:
   `test_revocation_and_missing_member.py` (gate),
   `test_c09_boundary_rejects_malformed.py` (transition), and
   `test_real_public_formal_a.py` (source-bound projection). These are already
   below 240 lines. Record the baseline before extraction.
2. Add one small `test_public_identity.py` in that same context test directory.
   Reproduce an initial extraction's public identity mismatch before repairing
   metadata; test pickle and public gate/project/digest patch interception.
3. Move definitions by the exact table above. Compare the other 23 moved definition ASTs after undoing only facade
   qualification. The gate is intentionally split into the named checks to meet
   hygiene limits: preserve its validation order, shared hold callback and used
   handle accounting. Add one combined-denial regression covering stale envelope,
   revoked grant and forbidden join simultaneously. Check public
   function/class/method type hints.
4. Compare an identical deterministic disposable fixture under original Git
   source and extracted source: frame/member evidence, approved serialization
   and digest, projection cache key, revoked/changed C09 event identity, context
   holds and eligibility decisions must match. A fixture is evidence for that
   slice, not exhaustive semantic or neural qualification.
5. Run the public fixture plus three focused companions and identity regression
   through `scripts/run_tests.py`; report real-source skips explicitly. If a real
   A01 artifact is unavailable, do not claim source-positive replay from a skip.
   Keep the original source's missing-member/revocation/forged-C09 rejection
   cases and genuine approved contexts passing.
6. Stage all new source files BEFORE regenerating error artifacts. Then run the
   committed-input error-control gate and compare raw exception identity/count
   multisets against the baseline. PM-2026-11-04-001 / RC-144 applies: a pre-staging
   inventory cannot establish final-candidate coverage. Do not change scanner
   exclusions, debt baselines, thresholds or source rules.
7. Run changed-scope structure/governance/hygiene/docs, Factory architecture, ABI
   and flow-control checks. Publish exact-head source/proof, request independent
   pinned EGM on the stable candidate, then open a ready PR to unified after all
   available gates pass. Human merge remains separate.

## Boundaries

No new semantic primitive, contrast oracle, source qualification, profile
selection, generation acceptance or neural admission. #424 still requires its
seven source-authorized transformation/checker/lineage classes; #785 still needs
independent profile selection; #420 retains broader world-rule qualification.
Keep actual students, native AdamW, teacher, champions, archives, graph/source
releases, checkpoints and100GiB reserve unchanged. IPR-0220 remains open.
