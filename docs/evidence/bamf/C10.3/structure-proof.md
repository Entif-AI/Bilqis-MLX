# C10.3 encountered-structure continuation

This records the mandatory interruption sequence on issue #521's feature branch,
not additional BAMF admission authority. Draft PR #620 targets unified. The
consumed Lane C/unified baseline remains 840e6ce/a02b9ed4. Existing #610/#614
branches are preserved; #520's atomic batch implementation is not included.

## Scope and provenance

Runtime and its test root were reduced from 67/69 direct Python files to 12/12.
Canonical module lookup uses the existing runtime package search path. Physical
owner packages reject alternate imports. Source fingerprints retain canonical
keys and resolve actual module bytes across reviewed Runtime/Learning layouts.
Wheel discovery includes descendant packages and JSON resources.

Compatible pure Lane C extractions were reused from #614 with original source
provenance: lease 64610f2, batch adapter 5b6859f, correction bb8cef9, temporal
1511732 and candidate evidence 15d22e3. Their old #520 completion narrative was
not transplanted. Candidate extraction includes its mirrored Learning tests.

Further encountered owners were split in this branch:

| Owner | Resulting boundary | Evidence |
| --- | --- | --- |
| Staging | contracts, queries/proofs, SQLite store, canonical facade | Exact pre-extraction JSON/digest and class module identity; 33 pinned Rosetta checks |
| Capability retention | complete solver/cohort evaluation separate from paired retention | 21 unchanged function/class ASTs; 12 focused checks |
| Outbox | contracts, immutable envelopes, store, correction translation | 20 unchanged definition ASTs after relative-import depth normalization; no batch API added |
| Reconciliation | source-context repair, resume metadata, remaining scheduler repair | 10 unchanged function ASTs; 22 checks |
| Depth selection | sealed/source-derived contracts separate from selector algebra | 15 unchanged definition ASTs; 13 M3 depth checks |
| Attention tests | causal convolution versus native GQA | 14 M3 checks |
| Resources tests | source workers, microbatch plans, accumulation, OOM retries | 12 CPU checks |
| Topology tests | contracts, parameter ledger, storage, legacy compatibility | 20 M3 checks pass; one legacy-bundle witness unconfigured |
| Solver tests | routing, replay budgets, gold-import boundary | 14 routing/replay checks; inherited gold-import boundary defect preserved |

Every originally encountered oversized owner and companion is below its required
remediation target. No thresholds, exclusions, governance files or quality
baselines were changed. Work Stack `bamf-c521-20261030` records each interruption,
proof, commit and resume. Newly created subdirectories were not recursively swept.

## Hygiene repairs after regrouping

Regrouping exposed old findings as changed-path findings. The implementation,
rather than the baseline, was repaired. Projection kind/field maps and the import
proof map are immutable mappings. A repeated resume error uses one named identity
with identical externally visible text. Temporal supersession validation and test
fixture setup are cohesive helpers, preserving the original projection rules.

The unadmitted B11 numerical group's exact shape/type checks moved to
`backbone_group_inputs`; the public owner still rejects caller predecessors
before validation. Its four-layer equations, gradients, cache/content hashes,
source order and UNADMITTED_NUMERICAL status are unchanged. Six M3 checks pass
before and after extraction.

The deterministic refinement policy now separates immutable source contracts,
input validation, source-granted salience and stable ranking. Source inventory is
still independently reconstructed; missing/revoked grants and inventory shrinkage
fail closed. Quota remains min(32, ceil(visible/8)); requested-role coverage,
attested salience and source order retain their original priority. Training pass
sampling retains the same length-delimited hash inputs; inference pass rules and
cache identities are unchanged. All eight original policy checks pass before and
after the split. Public dataclasses retain their canonical module names.

## Named M3 evidence

Tests ran in an isolated source snapshot on `m3-ultra` with the verified framework
Python runtime, not against an actual student. No human-run command was invoked.
The disposable optimizer-custody fixture uses a 3x4 array and confirms that its
parent AdamW remains unchanged until an explicit fixture commit; it passes.

Source archives were read back at identical SHA-256 values before extraction:

- Runtime/test snapshot: 217120318978a722a2f2143df3974fc2aee2167e8b546b9e807de2788b0b647c.
- Public source helpers: cbcb9f75fbdc2a1cef5185b9a7bc4b28632f605a8ae5a5ba14b90966f48c1045.
- Pinned public donor files: 9f86e782c12ace2d01198e341114a3a61f83e5bda6bcd48ad36bdda5457519dd.
- Topology/config proof: a32b7cfdc8b0a82c4e661d02fbbb05db283e0b4c86d87a59747ce3ac355c459a.

The first isolated snapshot lacked helper imports, then donor files. Those
preparation errors were reconciled; the completed depth/optimizer run passed
14/14. Attention separately passed 14/14. The topology run passed 20/21; its
unchanged `BILQIS_V1_BUNDLE_WITNESS` requirement remains unconfigured, and no
historical checkpoint was substituted or marked verified. Source-only structural
proof, disposable MLX proof and historical-lineage qualification remain distinct.

## Remaining acceptance

Full C10.3/source-rights/service and parent C10 acceptance remain open. The pinned
Rosetta contract witness validates native owner envelopes and integrity; it is
not live graph-service replay. Full runtime retains disclosed baseline failures.
Fresh implementation review of this structural/hygiene continuation and final
exact-head aggregate checks are pending. Nothing here authorizes merge, closure,
admission or a durable student start.

## Preserved implementation contracts

This table records the implementation examined by the refactor; it does not
replace the existing [B06.2](../../../tasks/bamf-0.2/children/B06.2.md),
[B11.1a](../../../tasks/bamf-0.2/children/B11.1a.md) or
[C09.3](../../../tasks/bamf-0.2/children/C09.3.md) owner contracts.

| Boundary | Exact preserved behavior and reconstructable source |
| --- | --- |
| Numerical inputs | Caller predecessors reject first. ModelTopologySpecV2 and GenerationExtents require exact types. group_index is an integer in 1..depth_groups. Hidden is FP32 rank 3, last dimension spec.width, sequence length 1..spec.context. Scope IDs are int32 and validity is bool, both matching the hidden batch/position axes; optional sequence starts have the same shape and bool dtype. Every required block tensor has its exact B01 shape and FP32 dtype. See [input validation](../../../../bilqis_mlx/runtime/_model/backbone_group_inputs.py). |
| Numerical execution | Group size is spec.layers/spec.depth_groups. Each layer RMS-normalizes using spec.rms_norm_epsilon, runs existing causal GQA, adds its residual, RMS-normalizes again and adds `(max(ffn_input,0)^2) @ ffn_out.T`. Original tensors remain on the differentiable path. The result remains UNADMITTED_NUMERICAL. See [execution and session](../../../../bilqis_mlx/runtime/_model/backbone_group_numerical.py). |
| Numerical identities | Tensor content hashes use SHA-256 of `np.asarray(mx.stop_gradient(value)).tobytes()`. Record hashes use SHA-256 of `json.dumps(record, sort_keys=True, separators=(',', ':')).encode()`. Parameter records bind name, shape, dtype and content; scope binds scope/valid/start tensor hashes plus generation and prefix claims. Execution binds group/layer range, topology/extents, generation/prefix claims, group/full parameter hashes, scope, cache chain, input/output, predecessor and status. The standalone predecessor is input content; a session adds its previous execution digest. Cache records bind metadata plus key/value tensor content. These are content identities, not producer authentication. |
| Temporal visibility | Validate unique event IDs, same-actor recorded-order supersession edges and an acyclic supersession graph. Only the selected actor's recorded_at <= as_of events contribute. Visibility requires a planned event or effective_from <= as_of, and no effective_until or as_of < effective_until. Supersession edges remain effective after their replacement expires; ancestors never resurrect. No active event means UNKNOWN; alternatives mean CONFLICTING_ALTERNATIVES; one active event maps to its explicit kind, with a planned report becoming MISSING_EXPECTED_REPORT at/after its deadline. See [projection](../../../../bilqis_mlx/runtime/_correction/atlas_temporal_revalidation.py). |
| Temporal identity | Only already-recorded event boundaries contribute. The existing contract hash binds actor_id, ordered active_event_ids, sorted known_boundaries, count of boundaries <= as_of and status.value. The TIME dependency key is `time:asof:<actor-id-length>:<actor-id>:<hash>`. Binding replaces only that actor's TIME boundary and preserves other dependencies. Schema and hash encoding remain in [temporal contracts](../../../../bilqis_mlx/runtime/_correction/atlas_temporal_contracts.py). |
| Refinement prefix | Reconstruct the complete prefix from source_ast and compiler_config. Task, frontier and policy must match compiler configuration at p. Visible envelopes, frames, source spans and members must all be available by p. A13 projection may return ContextHold unchanged. The compiled closure handles must match the entire visible inventory and its context digest; an empty inventory must contain no compiled closures. The prefix inventory requires its own nonrevoked source grant. See [selection](../../../../bilqis_mlx/runtime/_model/refinement_policy.py) and [contract checks](../../../../bilqis_mlx/runtime/_model/refinement_contracts.py). |
| Rights and salience | Grants bind evidence digest, semantic release, principal, tenant, permitted purpose/jurisdiction/scope, rights epoch and correction generation, and must satisfy observed/effective frontiers without revocation or expiry. Prefix inventory regimes must be allowed. Salience additionally binds the approved frame envelope and frame regime, must be visible by p, and cannot reuse an occupied frame/member source handle. Ignore future/nonapproved hints. Salience evidence hashes canonical sorted compact UTF-8 JSON without ASCII escaping/NaN plus a trailing newline. See [source-granted ranking](../../../../bilqis_mlx/runtime/_model/refinement_ranking.py). |
| Quota and ranking | quota is min(32, ceil(visible_count/8)). Rank by descending requested-role intersection count, descending attested salience (default zero), then source position. Source position sorts source_span.start, source_span.end and occurrence_id. Unselected handles retain this stable rank order. |
| Passes and cache | During training, hash the compact JSON UTF-8 tuple `(run_seed, visit_id, p, query_id, occurrence_id)` with ensure_ascii=False; take the SHA-256 integer in big-endian order modulo 3. In inference, unresolved_nested_query gets two passes; otherwise use int(explicit_member_question). Cache identity is exactly `(input_generation, p, query_id, occurrence_id)`. No source grant, retention reward or admission authority is minted. |

## Final local check receipt

The machine-readable [continuation result](continuation-result.json) pins the
actual code SHA and separate CPU, native-owner and M3 outcomes. The final portable
workflow selection passes 96 tests with 18 existing skips. Full runtime reports
411 passed, 28 failed/error outcomes and 19 skips; it is not green. Its two
behavioral assertion failures match baseline. The remaining errors include
unavailable local MLX/Torch and the inherited legacy_course fixture mismatch.

Structure and governance report zero violations; the actual CI hygiene baseline
reports zero new findings. Docs and isolated installed-wheel staging pass.
Operator-contract checking still fails on the same 30 finding identities/counts
as clean Lane C. Factory architecture retains the same baseline A/B dispatch
finding. Historical ABI checking reports that the independent expected SHA is
unavailable; advisory success is not enforced ABI protection.

The workflow's seven runtime test selectors now follow their physical owners.
Two qualification test imports and six documentation test calls also follow the
existing moved helper modules. No release, source seal, historical checkpoint or
runtime qualification implementation was changed to repair these callers.

[Fresh review disposition](egm-continuation.md) is scoped PASS. Full source,
service, historical-lineage and parent acceptance remain open; PR #620 stays
provisional without a closing keyword.
