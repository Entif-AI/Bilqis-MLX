# Governed ingestion Skill contract (#87)

Version 1.0.0. Normative workflow contract, not an implemented or packaged Skill.
The machine-readable stage and request map is
[`ingestion_contract.json`](ingestion_contract.json). Implementation belongs to
#88–#90, clean-room proof to #91, and validation/packaging to #92.

## Supported requests and inputs

Support pinned source rebuild, canonical CSV-to-RDF compilation, semantic
conformance, held/debt inspection, and explicitly requested owned Falkor
materialization/readback. The literal examples in the JSON contract include
read-only, repo-writing, optional graph-writing and rejected requests.

Require an explicit repository/worktree or CSV root, an explicit compatible
Python interpreter, supported profile, and dedicated output root. `python` in
the declarative command examples denotes that selected interpreter, not a guess
from PATH. Source rebuild also requires exact pinned raw snapshots, the tracked
PDF inventory, accepted extraction profiles and a canonical CSV seed. Existing
published crosswalk/enrichment rows are retained evidence inputs. An authenticated
workbook, live Curriculum Registry connection or private cache is not an implicit
prerequisite for a CSV-only build.

Falkor additionally requires explicit graph-write intent, exact graph and owner,
configured host/port, conformant evidence bundle and smoke suite. Never invent
credentials or infrastructure configuration. Run deterministic code locally;
an operator-established tunnel may carry only database traffic.

## Authority map and mode

The supported runtime mode is `public_only`. The repository is public. Its
source pipeline and SKOS profile can be operated without protected implementation
content. Reachability of protected material does not authorize its disclosure or
make it a packaged dependency. A request that actually needs protected authority
stops and routes to separately authorized internal review. Do not fabricate that
authority, infer permission from access, or package protected locations/content.

| Domain | Owner | What the Skill may do |
|---|---|---|
| Source observations | Pinned manifests, tracked PDFs, extraction owners and #28 | Restore exact pins, invoke accepted parsers, retain loci and debt. |
| Relational IR | `SCHEMA.md`, source validators and canonical CSV owners | Rebuild/validate accepted structures; never invent rows or change schemas. |
| Semantic RDF/SKOS | #19, `SKOS_PROFILE.md`, compiler profiles and owning modules | Invoke deterministic projection; preserve existing semantic identity. |
| Conformance | #72 and its explicit gate registry | Run every registered gate and retain constituent evidence. |
| Derived Falkor state | Importer, projection/receipt and #79 read adapter | Explicit owned writes and canonical readback only. |
| Curriculum and neural state | Separate repository authorities, including opaque IPR-0220 | No admission, ordering, training, checkpoint, optimizer or teacher mutation. |

Read current `AGENTS.md`, this contract, applicable profile/schema and live owner
contracts before action. Resolve the public publication boundary, authority
closure doctrine and public/private authority bridge when governing the Skill.
Those governance entrypoints constrain operation and disclosure; they do not
replace SKOS meaning or turn this Bilqis research pipeline into a Rosetta Core
schema. Preserve the root #19 separation explicitly. Surface authority conflicts;
do not silently reconcile them or promote proposed governance text into a new
semantic authority.

Postflight validates actual outputs and native receipts, not agent self-report.
Update authority maps only when an authority relationship really changes. This
contract reuses existing owners and creates no new protected authority edge.

## Stage graph and canonical entrypoints

The JSON contract owns the concrete module/command map, preconditions, outputs,
failure classes and retry rules. It is not a second parser or compiler registry.
Future orchestration must consume that contract and call the canonical owners.
Do not embed equivalent semantic decisions in prompts, templates or helper code.

- Source requests inspect pins/inputs, rebuild in isolated staging, validate the
  entire staged source graph, and publish verified canonical results last.
- CSV compilation calls `skos.build`; conformance calls `skos.conformance`.
  Conformance owns independent full-domain builds/census and all four registered
  gates. Do not manually reproduce or selectively omit those gates.
- Core generations and full-domain conformance bundles are different artifacts.
  A core `CURRENT.json` generation is **not** an importer-ready conformance bundle.
  Optional graph writes consume the conformance bundle with its coverage,
  independent comparison/census and complete gate evidence.
- Graph readback uses the existing Akasha adapter with explicit projection,
  receipt, notation datatype and expected stable IRI. No generic graph fallback.

`inspect` may read receipts or call the pure in-memory frontier `generate()` API.
It must not invoke that module's default publishing CLI. Frontier file generation
belongs only to the explicitly authorized source-write stage.

The #79 constitutional seam (ADR-096) keeps semantic projection, learner
evidence, factory/release state, run history, provenance and operations logically
federated, even on one physical graph service. This Skill touches only its explicit
semantic projection. It does not settle the future Akasha command/write topology
or create learner/factory/operations write semantics.

The governing [ADR-096 decision](https://github.com/Entif-AI/Bilqis-MLX/commit/64b2b4fbd478c7760dc91e3caec2884e3058528b)
also separates stable semantic identity, exact semantic-release digest, provider
implementation digest, run identity, projection identity and receipt identity.
The Skill must retain those distinctions. A provider refactor or workflow-run
identity must never rekey a semantic concept. Do not silently select "latest".
The future Rosetta integration is a governed VocabPack boundary, not permission
to add Bilqis vocabulary to Rosetta Core through this Skill.

A successful conformance command can retain `coverage_status=partial`. Neither
green gates, source parse status nor graph materialization grants release,
curriculum or training authority. Unknown source shapes remain their accepted
explicit debt, or stop the affected unadmitted extension and route to source-owner
investigation plus code/fixtures. An LLM must not improvise a missing meaning.

## Write-surface classification

| Surface | Class | Boundary |
|---|---|---|
| Read source/IR/receipts and inspect debt | Read-only | No source or semantic mutation. |
| Fetch already-pinned source bytes | Network read plus ignored-cache write | Explicit restore only, temporary download, exact digest check, no re-pinning. |
| Canonical source rebuild | Repo write | Explicit staged scope, one publication writer, recoverable baseline and validation. |
| RDF/conformance artifacts | Generated-artifact write | Dedicated safe root; immutable owner publication and exact readback. |
| Falkor materialization/index creation | Graph write | Explicit exact graph/owner, passing bound evidence and importer ownership checks. |
| Graph consumer readback | Read-only | No repair, reset or semantic writes. |
| GitHub, correspondence, sharing, release/push/merge | External/public write | Not an automatic stage; separate authorization and publication classification. |
| Curriculum, neural/runtime state, pin overrides, broad graph deletion | Forbidden | Reject or route to their separate owner. |

Do not invoke `fetch_sources.py` snapshot main as an ordinary rebuild or retry:
it rewrites the source manifest. Optional exact-byte restoration can reuse its
existing transport helper in temporary cache, verify the accepted digest, then
publish only the matching ignored raw artifact. New source versions require a
separately governed pin/admission change. Packaging excludes source corpora,
authenticated exports, credentials, machine paths and execution caches.

## Failure, replay and durability

Each JSON stage names its blocking errors, whether prior outputs remain valid,
and the permitted retry. Preserve the owning gate/error rather than collapsing
source, schema, semantic, infrastructure and graph failures into one success flag.
No failed stage may feed a downstream writer. Previously verified outputs remain
usable only for their originally bound input identity.

Use an ignored durable run record, not conversational memory, for intent,
contract/input/profile identities, stage readiness, attempts, canonical receipt
references and reconciliation state. Reuse a completed stage only after its
postcondition and unchanged dependencies are verified. Changed inputs invalidate
dependent results. Ambiguous source/artifact/graph writes require native readback
before replay; never assume a timeout means no mutation. This is a narrow
equivalent to dependent-execution tracking, not a second source/semantic registry.

Public/private or semantic conflicts require owner review. Infrastructure failures
may be retried after restoration. Unknown shapes need accepted owner code plus
fixtures, not model-generated source truth. A partial owned graph import requires
existing importer reconciliation; reset/deletion is not an automatic recovery.

## Proposed package and governance manifest

The later package should contain concise `SKILL.md`, `PROJECT_GOVERNANCE.yaml`,
and progressive references for this contract, authority, commands and failures.
Its instruction surface invokes the repository's thin orchestration entrypoint
from #88–#90. Deterministic package checks belong in scripts only where useful.
Do not ship a second parser/compiler, raw corpus or private source cache. Any
copied contract reference is generated/verified against the canonical JSON, not
maintained independently.

Proposed root `PROJECT_GOVERNANCE.yaml`:

```yaml
schema_version: 0.1
project: entif-rosetta
subproject: bilqis-mlx-ithkuil-ingestion
authority_mode: public_only
public_authorities:
  - docs/governance/PUBLIC_COMMONS_AND_PRIVATE_OPERATION_BOUNDARY.md
  - docs/governance/AUTHORITY_CLOSURE_AND_REQUIREMENTS_TRACEABILITY.md
  - docs/governance/PUBLIC_PRIVATE_AUTHORITY_BRIDGE.yaml
protected_authority_resolution: stop_and_route_if_required
external_write_posture: classification_required
authority_preflight: required
postflight_validation: required
authority_map_update_on_relationship_change: required
```

`project` names the existing governance-validator family, not ownership of SKOS
meaning. Resolve its public authority files in the public governance repository;
do not assume they are hidden local Bilqis files. No private repository URL or
private entrypoint is embedded in the public-only package. #92 must run project
governance validation and upstream Skill validation/packaging. This contract's
existence is not a claim that a Skill has already passed either packaging gate.

## Contract proof

`test_ingestion_contract.py` checks literal governance/non-admission boundaries,
every canonical owner path, required failure/retry fields, distinct core versus
conformance graph inputs, optional graph authorization and supported/rejected
request routes. It executes no source parser, semantic build or graph operation.
The machine request examples provide more than the three required cases.
