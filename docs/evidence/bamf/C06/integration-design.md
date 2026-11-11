# C06 parent integration design — #379

Proposed pre-implementation design. This work inherits #379 and C06.1–C06.4;
`new_acceptance=false`. Their receipts establish fixture-qualified components,
not parent integration. Source/evaluator-issued facts and lineage must come from
their existing owners. This design neither invents an issuer nor grants admission.

## Accepted A09 snapshot and correction ownership

There is no established B13 pointer to the current A09 progress in the inspected
accepted runtime. Add a run-local host-owned A09 progress store and versioned
pointer. `AcceptedRuntimeHost.advance_salience_progress(planner_inputs) ->
AcceptedProgressRef` runs the existing A09 `plan_frontier_progress` from its
current stored verified progress and owner-resolved snapshot/closure inputs. It
checks the snapshot's admitted release against the current source context and
accepted generation, verifies the selected closure and progress, and writes the
canonical progress plus input identities by digest. It must not accept a
caller-supplied `FrontierProgress` as proof merely because its hash verifies.
The pointer binds schema version, run identity, accepted manifest, admitted
release, progress/snapshot digests, prior pointer digest and monotone revision,
rights epoch, correction generation and a digest of the verified committed C09
ledger prefix. Atomically replace the pointer under the accepted-host locking
order; read back and verify its canonical bytes and immutable payload. Concurrent
writers use compare-and-swap on the previous pointer; reject stale writes and
conflicting revisions. On cold read, validate the payload, A09 chain, accepted
manifest lineage and committed C09 ledger, and replay later correction events.
An accepted-generation change requires a revalidated advance; missing or stale
pointers hold. This store is a planning read model, not an admission lease or an
alternative correction ledger. It may not reset coverage or advance the A09
cursor without the existing planner's verified transition.

Add `SalienceEvidenceArtifactOwner` to C09, with
`register(host, progress_ref, frontier, *, row_bindings=()) -> owner` and
`read_current(option_id, *, now) -> QualifiedOption | Hold`. The host resolves
`_accepted_correction_registry(host.run_dir)` internally; callers never choose the
registry. Verify each existing signed C06 policy, fact, option and row binding
with that registry and its required dependency scopes. Materialize exact
content-digested `ArtifactNode`s in the owner's `DependencyIndex` for policy,
facts, option, and each row binding, each with the appropriate policy, source,
artifact, source-binding and rights dependencies. Add `ArtifactKind.SALIENCE_EVIDENCE`
and the corresponding C09 owner-ingress routing and priority ordering; register
the owner with `register_accepted_target` for the accepted manifest. Immediate
dependencies cover the exact C06 fact/policy/option IDs, source binding and
owner-issued rights receipt/epoch, plus upstream C09 artifacts when relevant.
The node records identities and source content; it does not sign, invent, or
promote source facts. The accepted runtime replays persisted corrections when
registering and refreshes before every read; `read_artifact`-equivalent current
checks fail on held, revoked, ineligible or transitively held dependencies.
Current rights and correction context is the verified stored A09 snapshot bound
to the host's committed C09 ledger prefix, with any later accepted events applied
before read. A change invalidating that binding requires a newly verified A09
advance or returns a typed hold. A mismatch is an error, not an implicit update.

## Host-bound priority

Add `requalify_attention_frontier(host, source_context, progress_ref, frontier,
program, teacher_epoch, *, now) -> RequalifiedFrontier`. It reads the host-owned
progress pointer, obtains the accepted cache and internal correction registry,
registers/refreshes the salience owner, and returns an ephemeral host-issued
result binding current accepted manifest, execution generation, progress revision,
ledger commitment, and option hold reasons. Require `source_context` from that
host and its admitted release to match the progress pointer. Match C06 context's
semantic release, rights epoch, correction generation, source-binding digest,
capability and teacher epoch to these owner records; its generation digest must
match the accepted cache execution `generation_binding`, not the manifest digest.
Verify the existing signed policy, facts and option via the accepted registry.
Signed eligible time, relevance, ready and exploration predicates remain
source/evaluator facts after signature and scope verification; do not infer them
from learner history. Actual current A09/C09 holds override those predicates.

Map a teaching option's capability through the admitted release's
`execution_plan.capability_map`, `curriculum.capability_map`, and
`source_bindings.by_capability`; map its `taught_roots` to known A09 source
concepts/coverage obligations with matching family and source binding. Require a
unique program membership and `school.course_digest` match. An already admitted
capability is eligible based on this mapping and current owner evidence; it need
not appear in `ready_candidate_ids`, which describe A09 candidate planning.
Validate A09 closure/selection and its `downstream_unlocks` when used. A staged
successor / `LEASE_REQUIRED` remains exploration or investigation until admitted;
it is not a teaching option. A source hold, unresolved prerequisite, revoked
rights or C09 correction hold blocks teaching even if novelty is high. A
correction/procedure action may be actionable without authorizing source teaching.
Rank eligible options with the existing dispatcher and expose all holds. Preserve
the existing signed-history aggregation; event/lineage evidence is supplied by
its actual owner, never synthesized from family or episode IDs. Conjecture is not
source gold or optimizer input.

## Selection to candidate execution

Add public `select_accepted_priority_visit(run_dir, source_context, progress_ref,
frontier, history, engine, school, rng, learning_settings, *, program,
total_capabilities=None, plasticity_escape=None) -> PriorityVisitResult` beside
`select_accepted_teacher_visit` in accepted teacher custody. It reads the accepted
parent and C03 epoch, requalifies and ranks once, and for teaching invokes the
existing `select_visit_policy` exactly once with the signed, verified salience
diagnostics and unique roster grade. It uses `_selection_projection`,
`derive_teacher_visit_identity` and `record_teacher_visit_identity` to issue a
normal `BoundTeacherVisit`. A hold or correction returns typed status without
consuming teaching RNG or issuing a visit. No second selector or policy update is
permitted.

Add public `execute_priority_factory_candidate_step(..., priority_inputs,
row_evidence_provider) -> PriorityFactoryResult`. It invokes that selector,
returns immediately for holds/actions, and obtains the selected capability,
policy and authenticated visit itself. Construct
`BamfVisitProvenance.from_c03_record(visit.identity.to_record())` while retaining
the bound visit for the current-host custody check. Draw and prepare the actual
source-owned rows for the selected capability, then call the supplied existing
source/evaluator owner as `row_evidence_provider(prepared.training_batch,
qualified_frontier) -> tuple[(RowSalienceBinding, SalienceEvidence), ...]`.
This callback runs *after* C02 preparation because row digest, delivery digest and
provenance then exist. It supplies already owner-signed records; it is not an
authority oracle. Verify/attach them with `attach_salience_labels`, register row
binding dependencies with the salience owner, and preserve compiled row alignment.
An empty tuple is valid for an unlabeled batch. Invalid signatures or mismatched
row identities fail; current source/correction holds stop before gradients.

Extend the real `execute_factory_candidate_step` with an opt-in prepared-row
hook invoked immediately after `prepare_factory_training_batch` and before
`_execute_prepared_candidate`, preserving its existing behavior when absent.
The public priority entrypoint supplies the internal verifying hook above, checks
bound visit, accepted pointer, progress revision, C09 ledger and each row's
current eligibility immediately before delivery and candidate execution, and
calls the real candidate step with the selected capability/policy/provenance.
No caller can replace these after selection. This is one C03 selection and one
Factory execution, not a detached wrapper or a historical trainer modification.
Current owner changes force requalification rather than replaying stale proof.

## Row labels and B11 boundary

After actual C02 `compile_training_batch` using admitted source context, apply
`attach_salience_labels` to exact rows with existing signed bindings and current
host authority; preserve other verified auxiliaries. C02 already invokes A05
`compile_prefix` after context eligibility. Its standalone `execute_with_backend`
passes `targets=None` in inference. The real candidate step calls B11 directly:
carry verified row labels into that call rather than treating the standalone
adapter as evidence of training integration.

At the B11 owner boundary, project the existing three five-class B01 heads from
the final visible prefix hidden state for each row, before decoder or target
conditioning. Add `0.05` times each present head's supervised loss to answer
loss. A missing label contributes neither loss nor head participation; an explicit
verified UNKNOWN is class 0 and is supervised. With all heads absent, preserve
answer-only loss, gradients and optimizer participation. Forward inference remains
target-free. B11 owns the exact execution/participation representation and must
preserve generation binding, finite-loss and custody checks. A detached projection
that is not bound to the exact forward execution does not satisfy this boundary.

## Required evidence

Use focused owner tests first, followed by a serialized Studio MLX witness in an
isolated disposable run. Preserve receipts and reuse only unaffected proof.

- Verify pointer cold read, committed-ledger replay, CAS conflict, stale generation,
  tampered payload, and post-registration C09 correction. Test owner dependency
  holds for policy, fact, option, binding and rights without changing unrelated
  evidence.
- Exercise verified A09 progress/closure (see
  `factory/tests/events/test_atlas_integration.py`) with an accepted B13 host
  (see `runtime/tests/correction/test_atlas_capability_support_owner.py`) and
  actual owner-issued C06 inputs. Verify released mapping, ranking and the public
  path through a bound teacher visit to the real Factory candidate step. Missing
  evidence, ambiguous mapping and a staged pending successor must hold.
- Revoke rights or apply an accepted correction to high-novelty content; assert
  no teaching, source gold or optimizer input. Change accepted generation or
  correction after qualification and reject stale selection/delivery. Grade-ID
  permutations preserve ordering and holds.
- Exercise A05 prefix through actual C02 delivery, attach source/outcome labels,
  preserve row provenance and unrelated auxiliaries, distinguish absent from
  class 0, and reject changed row, release, generation, signer or rights.
- Exercise real B11 MLX forward/backward through the candidate path: literal
  expected masked loss, supervised and absent head gradients, explicit UNKNOWN,
  answer-only equivalence with no labels, and target-free inference.
- Reuse the child contrast fixtures for paraphrases versus independent events,
  missing versus negative reports, windows and correction followup; add an
  owner-backed lineage witness before claiming source qualification. If the
  actual owner cannot supply a required input, record the exact hold and keep
  #379 incomplete.

Design review, engineering verification, drift analysis and integration turn-in
remain separate gates under repository policy.
