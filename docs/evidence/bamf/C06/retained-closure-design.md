# C06 retained dependency closure — shared contract design

Proposed design for review; inherited #379 acceptance, `new_acceptance=false`.
The defect is at B11 execution → retention → B13 cold support: a supervised
salience authority contains ARTIFACT references, but accepted support reconstructs
only its capability-support node. `DependencyIndex` requires every referenced
artifact to exist in the index. Persist the actual executed closure; do not
reclassify an ARTIFACT reference as SOURCE or weaken graph validation.

## Executed authority and closure

The C06 salience owner supplies **all of its actual `_owner.index.nodes`**, not
just the directly referenced root/binding nodes, to the B11 loss issuance path.
B11 extends its issuer-owned `BamfTrainingAuthority` with immutable
`artifact_nodes: tuple[ArtifactNode, ...]` and `artifact_closure_sha256: str | None`.
Only the owner-issued supervision attached to the exact loss execution can
supply these nodes; callers cannot attach or replace a closure. Verify its exact
C06 root/binding references against the supervised records, the accepted owner,
current generation and current correction status before issuance. Preserve all
existing source-row and forward-observed dependencies. An authority without a
closure retains its present digest payload and value byte for byte.

A nonempty closure is the complete `DependencyIndex` of the exact executed
owner, sorted by `artifact_id`, unique and acyclic, with all ARTIFACT edges
resolving within the index. Its canonical representation is an ordered array of
node objects with exactly `artifact_id`, `kind`, `content_digest`, `eligible`,
`immediate_dependencies`, `impact`, `exigency`, and `schema_version` as defined
by `ArtifactNode`; each dependency is its exact `(kind.value, key)` pair in the
existing sorted unique order. Encode enum values as literal strings. The exact digest input JSON value is
`{"schema":"bilqis.c06.executed-artifact-closure/v1","nodes":[NODE,...]}`.
Use `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False).encode("utf-8")`, with **no terminating newline**. Dependencies
are JSON arrays `[kind.value,key]`; their fixed DependencyRef/v1 schema is
validated before encoding and implied by the enclosing closure schema. Nodes
include their `schema_version` field verbatim. Python tuples and JSON lists
normalize to the same ordered arrays. No other enclosing keys are accepted.
Each durable acceptance closure entry is a JSON object with exactly
`step_index`, `training_authority_sha256`, `artifact_closure_sha256`, `nodes`;
`step_index` is the actual proof's positive integer, never its zero-based list
position. Entries sort by that step index; nodes use the same exact representation.
The acceptance record retains its existing canonicalization/newline policy,
separate from these explicitly newline-free closure digest bytes.
One canonical
encoder/decoder shared by authority, retention and C09 enforces exact keys,
valid enum values, digest lengths, graph closure and duplicate rejection. Preserve
exact C02/A13 RIGHTS, TIME and POLICY references, including the keys emitted by
`_row_immediate_dependencies`; do not invent salience-rights keys. Every
ARTIFACT reference contributed by this supervision must resolve to the matching
owner node with the exact content digest. No graph identity may be merged with a
different node bearing the same ID.

## Proof and acceptance versions

`CandidateStepProof` v1–v3 parse exactly as today. Keep v3 emission and its exact
record/digest bytes when the executed authority closure is empty. Add v4 for a
nonempty closure: the v3 fields plus `artifact_closure_sha256`. In
`_atlas_candidate/transaction.py`, derive it from the same issued authority
carried by the exact B11 gradient execution; check the authority's closure digest
against the canonical nodes before making the proof. The proof also retains the
existing `training_authority_sha256`, which itself commits to the closure digest.
No caller-supplied digest substitutes for this chain.

Enforce the association at the existing B09 owner boundary: add an internal
`_bind_execution_training_authority(provenance, loss_execution)` operation to
`atlas_execution_provenance.py`. It first requires a genuinely B11-issued loss
execution, then retains an ephemeral weak-lifetime association from that exact
issued StepExecutionProvenance object to its exact training authority object and
digest. The production `bind_execution_provenance` calls this operation only on
the provenance it has just derived from that same loss execution. It accepts no
caller-provided authority or digest. Rebinding the same provenance to a different
loss/authority rejects. The association is not included in old provenance bytes.

`candidate_step` ALWAYS consults `require_execution_training_authority(execution,
training_authority)` before AdamW or proof issuance. The predicate begins with
the provenance-side registered executed authority, never the supplied authority.
If the registered executed authority has a closure, the supplied authority MUST
be that exact object with the same current digest. None, a no-closure authority,
or any other object rejects. If no closure-bearing association exists, supplying
a closure-bearing authority rejects. Only an unassociated/no-closure execution
with None or the existing no-closure authority follows the legacy path.
Direct candidate_step calls with a closure-bearing authority but no association
reject; substituting a different valid issued authority, None, or a no-closure
authority for a closure-bound execution rejects. Existing direct
no-authority v1 and source-authority-without-closure v3 fixture paths retain
current behavior. The production adapter still obtains gradients and loss
execution from one issued BamfGradientExecution before deriving provenance; it
cannot accept an independently supplied gradient tree for a loss-bearing step.
 State/transaction decoding
must round-trip mixed historical v3 and new v4 proofs without changing old bytes.

Keep ordinary acceptance v5 and motif-transition acceptance v6 unchanged when
all step closures are empty. Add v7 for an ordinary candidate and v8 for a motif
transition containing at least one nonempty closure. V7 is v5 plus
`artifact_closures`; v8 is v6 plus that field. The latter retains the v6
`generation_authority_sha256` requirement and motif successor identity check.
`artifact_closures` is a canonical step-ordered tuple of entries
`(step_index, training_authority_sha256, artifact_closure_sha256, nodes)` for
exactly the nonempty v4 proofs; no empty, duplicate, extra or missing entries.
Existing ten-field source anchors remain unchanged and retain their actual
immediate dependency references. Acceptance's canonical bytes cover both the
anchors and closure entries. V7/v8 must not be emitted for an empty closure.

At live mint, `_source_anchors` validates each issued training authority against
its paired retained step proof as it does now, additionally verifies the v4
closure digest, exact canonical nodes, and source-anchor ARTIFACT references.
The acceptance issuer alone copies closure entries from those authorities. At
cold read, parse canonical nodes into a closed `DependencyIndex`, validate the
acceptance digest, and pair each entry to the accepted student's exact step proof
by `step_index`, proof schema, authority digest and closure digest. Require the
binding's `step_proof_sha256` list to equal the retained proofs in order; reject
substituted nodes even if an attacker recalculates the outer binding digest.
Verify the acceptance's normal published manifest, parent, registry and candidate
identity checks too. Parsing establishes data integrity, never new authority.

## Cold support and correction replay

`materialized_support` resolves each retained anchor to its proof and its bound
closure, checks all direct ARTIFACT references, and returns the support node plus
those exact nodes. For multiple contributing steps, union by `artifact_id` only
when the complete node records are identical; divergent aliases fail closed.
Build a `DependencyIndex` from the support node and all required persisted nodes.
`CapabilitySupportArtifactOwner` receives this complete index rather than
`DependencyIndex.build((node,))`. `accepted_support_census` likewise supplies
closure nodes to the accepted stale-replay index, deduplicating identical nodes
and rejecting conflicts. Its existing capability and generation identities remain
unchanged. Cold rehydration replays the accepted C09 correction ledger before a
support read; `read_artifact` recursively enforces holds through all ARTIFACT
edges. Journal recovery, late materialization, revalidation and propagation must
retain the entire index and prevent clearing a capability merely because its root
is not the directly corrected node. Persisted correction state remains owned by
the existing C09 journal/ledger; closure records are evidence, not a new ledger.

## Exact implementation surfaces

- B11/C06 owner: `runtime/_model/atlas_training_authority.py`, B11 loss issuance
  and salience supervision owner supply and bind the complete issued index. This
  interface is jointly reviewed with the retention changes.
- Execution binding: `_retention/atlas_execution_provenance.py` and
  `runtime/_batch/atlas_execution_binder.py` retain the ephemeral exact B11
  authority association and expose only the validating require operation.
- Retention: `_retention/_atlas_candidate/{common,proofs,transaction}.py`,
  `_retention/{atlas_acceptance,_atlas_acceptance_records}.py`, and a small
  shared canonical closure codec. Preserve legacy serialization paths explicitly.
- B13 publication: `runtime/_custody/bamf_bundle/publication/authority.py` has
  exact schema checks in live `require_acceptance` and accepted cold read; accept
  v5/v7 only for ordinary transitions and v6/v8 only for motif transitions,
  preserving generation authority and all existing checks.
- B13 feature lineage: `runtime/_custody/bamf_bundle/feature/acceptance.py`
  checks v5 explicitly. Recognize the appropriate v7 ordinary record and v8
  motif record only with the corresponding transition and existing proof/parent
  checks; do not make legacy schemas newly authoritative.
- C09: `runtime/_correction/owners/capability_support_loading.py` has exact v5
  checks in `_accepted_binding`, `_accepted_materialization`,
  `_latest_source_qualified_materialization`, and `accepted_support_census`.
  Recognize supported v7/v8 records with transition and proof validation; keep
  historical behavior for v5/v6 unless an existing owner already supports it.
  Modify `capability_support_materialization.py` and
  `atlas_capability_support_owner.py` for full index ownership, and
  `accepted_stale_replay_runtime.py` only as needed for conflict-safe census
  union. Do not alter other owners' schemas or source key types.

## Literal focused evidence

1. Compare old no-closure v3 proof and v5/v6 acceptance canonical bytes and
   digests to fixed pre-change literals; round-trip existing versions unchanged.
2. Execute a labeled authority with root → binding → fact/policy artifact nodes;
   verify v4 proof, v7/v8 entry, digest and exact nodes match executed owner index.
   Missing child, cycle, conflicting same-ID node, wrong enum/key, extra entry,
   wrong proof/authority association, or recomputed outer digest after node
   substitution is rejected. A multi-step candidate mixes v3 and v4 correctly.
3. Publish through the ordinary and motif paths in disposable fixture custody;
   clear process caches, cold-load accepted support and prove the complete index
   and manifest/proof identities. A referenced missing node fails closed.
4. Record correction of a leaf's actual source/rights dependency; before and
   after cold restart, support read fails through the transitive hold. Prove
   unrelated source remains unaffected, replay is idempotent, and only valid
   owner revalidation/requalification clears the hold. Exercise journal recovery
   after interruption and ensure no partial closure authorizes support.
5. Exercise existing v5/v6 readers and transition mismatches; verify unsupported
   schema/version combinations fail and no-label acceptance remains unchanged.

No implementation, EGM result or Studio witness is claimed by this document.

## Literal codec fixture

Exact UTF-8 bytes (no newline after the closing brace):

```json
{"nodes":[{"artifact_id":"salience:test","content_digest":"0000000000000000000000000000000000000000000000000000000000000000","eligible":true,"exigency":3,"immediate_dependencies":[["SOURCE","source:test"]],"impact":2,"kind":"SALIENCE_EVIDENCE","schema_version":"bilqis.c09.artifact-node/v1"}],"schema":"bilqis.c06.executed-artifact-closure/v1"}
```

Expected SHA-256: `ffed07eed66c4b179ce71c2d8fcf5272969dc1088389a7d0d1980e8e4f047d5a`. The digest excludes
the Markdown code fence and its display newline.
