# C06 priority integration design — #379

Proposed pre-implementation design. #379 inherits C06.1–C06.4; `new_acceptance=false`. The existing C06 signatures and evaluator predicates are inputs, A09 is planning, and the admitted source release and C09 own teaching authority. There is no persisted A09 pointer, autonomous trainer, or new issuer for source facts. This design covers the priority-to-accepted-visit integration; the existing C02/B11 salience path and its neural proof remain separate obligations.

## Source offer before policy selection

Extract the shared source preparation in `bilqis_mlx/runtime/_batch/factory_training_bridge.py` into a helper used by that existing entrypoint, preserving its behavior and keeping the bridge below 360 lines. Add the source-offer owner in `bilqis_mlx/runtime/_source/priority_source_offer.py` with `prepare_priority_source_offer(source_context, parent, atlas_artifact_path, *, capability, source_seed, source_each) -> PreparedPrioritySourceOffer`. It requires the context's accepted runtime, current accepted manifest and execution generation matching `parent`, and an admitted execution capability. Draw with `source_context.draw_rows(seed=source_seed, capability=capability, each=source_each)` and bind the exact draw with `source_context.bind_rows` using those arguments. Reject empty or non-canonical JSON rows. Retain a sorted-key, compact, UTF-8 JSON serialization with `allow_nan=False` of the complete row tuple, together with the resulting `SourceBatchAuthority`; all later row access decodes a fresh copy. Retain the release SHA, capability, source seed/each, source authority content SHA and family, accepted manifest SHA and generation binding. Construction is owner-issued and caller construction fails, as with `BoundTeacherVisit`.

Authenticate the feature context using `authenticate_bamf_execution_feature_context(parent, atlas_artifact_path, source_context.run_dir)` and use the same adapter, source family, released schema, profile, `_prepare_source_row`, and task/frontier/policy assembly as the existing Factory bridge. For each source row run `compile_prefix` with the row's AST, full visible token length, task semantic release and the approved compiler config exactly as `_compile_model_input` does. Reuse `authorize_public_formal_prefix` and validate the partial forest when the projection is present. A held or invalid source context prevents issuance. This step constructs no `BamfTrainingBatch`, delivery, teacher visit, answer target, gradient or optimizer input.

Construct `CompiledFrameRows` from the actual prefixes as in `_bind_b11_rows`; create `PackedFrameArtifactOwner` for those rows, `AtlasFeatureArtifactOwner(authenticated.features, authenticated.schema)`, and a source-offer `SalienceEvidenceArtifactOwner` whose node carries each exact row's C02 source, release, policy, rights, operator and contextual time dependencies. The source-offer node remains present when an atom-only prefix has no packed-frame nodes. Register the three owners with `register_accepted_target` under `PACKED_FRAME`, `ATLAS_FEATURE` and `SALIENCE_EVIDENCE`. Store the owners and exact prefixes/features privately in the offer. `offer.require_current(source_context, parent) -> None` rebinds the accepted cache, checks manifest, generation, release, capability and source context, validates the stored serialized rows and replays `source_context.bind_rows` with the retained seed/each and compares its full authority identity to the original. It calls source-offer owner `require()`, feature owner `require(features)`, and packed owner `require_row(prefix)` for every prefix, which refresh accepted C09 corrections. Failure means hold; no cached positive is authority after generation or correction changes. This preflight establishes eligibility for these exact public-formal rows; it does not assert a universal current rights epoch for unrelated material.

## Planning and qualification

Add `bilqis_mlx/runtime/_teacher/priority_qualification.py` with:

```python
@dataclass(frozen=True)
class PriorityPlanningInput:
    progress: FrontierProgress
    closure: FrontierClosure
    selection: FrontierDeltaSelection | None
    selected_projection: TargetDeltaProjection | None

@dataclass(frozen=True)
class QualifiedPriority:
    ranked: RankedOptions
    offers: tuple[tuple[str, PreparedPrioritySourceOffer], ...]
    holds: tuple[tuple[str, str], ...]

def requalify_priority(run_dir, source_context, parent, frontier, history,
                       planning, offers, program, school, teacher_epoch, *, now) -> QualifiedPriority: ...
```

`offers` is a tuple of unique `(option.stable_id, offer)` pairs. Verify progress, closure, snapshot and their linkage: closure snapshot equals `progress.input_snapshot_sha256` and is the corresponding snapshot in progress history; its admitted Factory release equals the admitted `source_context.release.release_sha256`. Validate closure structure. A selection and projection are both present or both absent; when present call `validate_frontier_selection(input_snapshot, closure, selection, source_context.release, selected_projection)` and require `progress.proposal_selection_sha256 == selection.selection_sha256`. A pending staged successor remains planning information and supplies no admission. Invalid planning signatures/digests or contradictory inputs fail; an individual unavailable offer or planning mapping holds that option.

Resolve the accepted C09 registry via `_accepted_correction_registry(run_dir)` and require its digest equals `frontier.snapshot.registry.digest`; check `snapshot.as_of == now`. First call `rank_attention_options` on the COMPLETE original options/evidence/snapshot to validate every signature and evidence binding before filtering, including options subsequently held for a missing offer or planning mapping. Discard that preliminary order; rank only the qualified unchanged subset afterward. Require each teaching/exploration option's context semantic release equal the admitted release SHA, generation equal the cache execution `generation_binding`, teacher epoch equal `contract_digest(teacher_epoch)`, capability equal the offer authority capability, source family equal its authority family, and source binding digest equal `contract_digest(source_context.release.source_bindings.by_capability[capability])`. Require the execution and curriculum capability maps contain the capability and the offer's accepted manifest and generation match the cache. The actual source preparation and current owner reads govern row eligibility; do not claim fixed public-formal epoch values are a global rights accessor. Signed `eligible_since`, `relevant`, `ready`, `exploration_admitted`, rights and correction predicates remain signed inputs; a source/C09 hold overrides them.

For `downstream_unlocks > 0`, call `candidate_realizations.realized_atlas_semantic_id(capability)` and require it equals the verified selection's `selected_semantic_id`, and the signed value equals selection's `downstream_unlocks`; otherwise hold `A09_PLANNING_UNAVAILABLE`. A zero value needs no semantic mapping. This use of A09 is planning evidence, never an admission lease. For every teaching/exploration offer require exactly one matching grade in the supplied `ScheduleProgram`, that grade active in `school.active_grades`, and `school.course_digest == program.digest()`. Check `offer.require_current` before ranking. Keep C06 correction/procedure actions available under their existing signed rules without issuing teaching authority.

Run `rank_attention_options` on the unchanged qualified option tuple and its corresponding evidence mapping with the original snapshot; never rewrite a signed predicate. Combine its held entries with explicit qualification holds, sorted by option ID and reason. Thus a held high-priority offer does not suppress a lower eligible option, and all holds remain observable.

## Accepted selection and Factory composition

In new `bilqis_mlx/runtime/_teacher/accepted_priority_visit.py`, import the existing accepted teacher custody private helpers and add:

```python
def select_accepted_priority_visit(
    run_dir, source_context, frontier, history, planning, offers,
    engine, school, rng, learning_settings, *, program, now,
    total_capabilities=None, plasticity_escape=None,
    legacy_receipt=None, adaptation=None, prior_region=None,
) -> PriorityVisitResult: ...
```

`PriorityVisitResult` is a frozen tagged result: `NO_ADMISSIBLE_TEACHING` has holds only; `ACTION_REQUIRED` has option ID and holds; `TEACHER_SELECTED` has option ID, the issued offer, unchanged `BoundTeacherVisit`, immutable canonical policy JSON, selection metadata, lesson grade and holds. Non-teaching variants have no visit or policy. Load parent and accepted cache via `_accepted_parent`, obtain `_c03_projection` and `restore_teacher_lineage`, and check the school student identity as in `select_accepted_teacher_visit`. Requalify; if no ranked option or the first is an action, return without calling the policy selector or consuming teacher RNG. For teaching, call `offer.require_current` again immediately before selection; if it now holds, remove only that offer, append its reason and continue with the next ranked option. Call `select_visit_policy` exactly once for the first still-current teaching option with its capability, its signed context scope, `{'salience_evidence': evidence, 'teacher_epoch_digest': contract_digest(epoch)}`, and unique active lesson grade. Serialize the returned policy as canonical sorted-key compact JSON with allow_nan=False; expose policy only by decoding a fresh copy. Mint the result with a module-private issuer and weak-lifetime identity registry, retaining its policy JSON digest and visit identity. The execution entrypoint requires that issued object and unchanged digests, not caller construction or dataclass replacement. Preserve native policy values and metadata. Use `_selection_projection`, `derive_teacher_visit_identity`, `record_teacher_visit_identity` and `_issue_bound_visit` exactly as the existing accepted selector does. Do not call `choose_priority_teaching`, which would select a second policy.

Add a public `execute_accepted_priority_candidate(selection, source_context,
atlas_artifact_path, feature_artifact_path, *, teacher_hparams, observation,
optimizer_step_seed, max_norm, memory_budget=None, salience_provider=None)` in the
same new module. It returns the unchanged non-teaching result without delivery
or candidate execution. For TEACHER_SELECTED require the exact issuer-recorded
selection, policy JSON digest and visit identity. Re-read parent/cache from the
selection's private run path, call `_require_current_visit(parent, cache, visit)`
and `offer.require_current(source_context, parent)` immediately before delivery.
Decode fresh copies of the exact retained offer rows and native policy; derive
capability, seed/each, raw teacher_strategy, and
`BamfVisitProvenance.from_c03_record(visit.identity.to_record())` internally.
The public signature accepts no replacement capability, policy, rows or visit.
Construct `describe_delivered_teaching` from the actual release, selected
capability, first admitted execution teaching_option_id and retained rows. The
source offer is WHAT content; native teacher policy remains HOW authority.

Require `teacher_hparams` to be AdamWHyperparameters, require native policy['lr']
to be a finite positive int/float excluding bool, and use
`replace(teacher_hparams, learning_rate=float(policy['lr']))`. Preserve betas,
eps and weight_decay exactly. Call the existing execute_factory_candidate_step
ONCE with this teacher-controlled rate, exact selected strategy/rows/provenance,
source seed/each, requested_count=len(rows), source context and accepted parent.
Replace only observation.option_rows and observation.seed with the actual selected
rows/seed; preserve the existing observation owner/cost fields. Pass existing
resource limits and optional salience_provider. Before B11 the existing
prepare_salience_training validates actual signed row labels and C09 owner.

A hold detected BEFORE policy selection consumes no teacher RNG. A correction,
generation change or row mismatch introduced AFTER selection rejects delivery
without additional policy selection or candidate execution; the already-completed
selection's RNG consumption is retained and must not be described as zero. No
transactional RNG rollback or alternate teacher scheduler is introduced.

Physical changes: new _source/priority_source_offer.py and
_teacher/{priority_qualification,accepted_priority_visit}.py; small shared
source-preparation extraction in _batch/factory_training_bridge.py; mirrored
source-offer, qualification and accepted-visit tests. No growth of the 301-line
accepted_teacher_custody.py and no new legacy operator loop. New modules target
under 240 lines; split only by these existing source/qualification/custody roles.

## Verification

Use red/green focused tests in new `bilqis_mlx/runtime/tests/teacher/test_priority_source_offer.py` and `test_accepted_priority_visit.py`, and an integration test alongside `runtime/tests/model/salience/test_factory_salience_execution.py`:

- With real accepted B13 host, admitted source release, signed C06 inputs and verified A09 planning, assert exact selected option, offer rows, released grade, one C03 policy call, unchanged policy and bound visit, and invocation of the public execution composition through the real Factory candidate step with those same values. Assert a changed caller-decoded policy cannot change the stored selection, no replacement row/capability/strategy arguments exist, and the actual optimizer hyperparameters use native policy LR while retaining the other authorized values.
- Assert source preflight creates no C02 batch or visit; altered row, source seed/family/binding, signer, release or generation fails. Inject a source eligibility hold, accepted C09 frame/feature correction, or generation change before selection; the affected offer holds and no teaching RNG is consumed. A change after selection prevents delivery and gradients without further RNG consumption. A lower eligible offer remains selectable.
- Include a forged-signature option that would otherwise be removed for a missing offer; full-set validation must reject it before filtering.
- Validate the selected A09 semantic ID and literal downstream count, including mismatched closure/projection, unknown mapping with nonzero count, zero-count unmapped option, and pending staged successor without admitted membership. Assert these planning records cannot grant admission.
- Rename grade IDs consistently in program and school, retaining their capability membership; priority order, selected capability and holds stay equal while the returned grade changes. Verify inactive, duplicate and course-digest mismatches do not authorize teaching.
- Exercise the existing C02/A05 and B11 path with owner-signed row labels via `salience_provider`; assert row/visit provenance, missing versus class-zero labels, target-free inference and real supervised versus absent-head gradient/optimizer behavior. Reuse valid existing receipts and run any required isolated Studio MLX witness only at the stable boundary.

Design review, engineering verification, drift analysis and integration turn-in remain separate gates.
