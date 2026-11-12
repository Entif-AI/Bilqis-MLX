# C06 design review ledger

Pinned Google EGM: b3a35956759bf7f024af2ff061b2e0b44b438e4c.
All reviewers used fresh context and read the pinned Codex instructions, selected
personas and standards. Design review does not establish runtime correctness.

- Neural integration revision 3: c06_neural_design_review, Codebase Details and
  Implementation Readiness. Initial 1 Blocker/3 Majors; after repairing identity,
  primary-target guard, closed dependency graph, actual rights/context refs and
  file plan, targeted PASS with zero unresolved Blockers/Majors.
- Retained closure: c06_retained_closure_review, Codebase Details and Implementation
  Readiness. Initial 2 Majors: exact executed-authority association and canonical
  bytes. Fixed the explicit wire envelope/fixture and provenance-side association,
  including None/no-closure substitutions. Targeted final PASS; no tests run by
  that reviewer.
- Priority integration: c06_priority_final_review, Implementation Readiness.
  Initial 4 Majors: public composition owns selected fields, teacher LR reaches
  optimizer, all signatures verified before filtering, and RNG guarantees match
  timing. All repaired in integration-design.md; targeted final PASS.

Known design findings are resolved. Engineering verification, actual Studio
qualification, final drift and integration gates remain separate and incomplete.
The earlier broad A09-host-pointer proposal was replaced by direct typed planning
inputs plus actual row source preflight; no new persisted planning authority was
implemented. Atom-only source preflight received a C09 source-evidence owner to
restore the same required rights/correction hold invariant for all row shapes.

## Turn-in implementation review — 2026-11-12

The final turn-in used a genuinely fresh-context read-only Goldfish against
`81b95bacf82f41b19694594d14eb15dd1df40853` versus reviewed unified
`cd213c72963519c19a3a36eb8e1442eb35d68718`. It found one Major:
closure-bearing C06 B11 member authorities survived into a C08 logical batch, but
the v4 logical-batch step proof carried only member authority identities. Accepted
source anchors therefore retained ARTIFACT dependencies while accepted publication
persisted no corresponding closure nodes, allowing cold C09 support to fail with
`BAMF_C09_DEPENDENCY_ARTIFACT_MISSING`.

The finding was reproduced with a focused failing cold-support regression before
repair. The repair at
`5ef579c7578ed18e47cdd9b6567b5d94e7358114` keeps reviewed C08 v4 unchanged,
keeps scalar C06 closure proofs at v5, and adds v6 only for closure-bearing logical
batches. The logical authority derives a canonical union of member artifact
closures; the v6 proof commits that union digest; accepted publication binds the
union to the top-level logical authority while retaining exact member anchors; cold
validation requires the complete member-anchor set and resolves every member
ARTIFACT dependency through the persisted union.

The same Goldfish performed the permitted targeted re-audit at exact pushed head
`e9052d2c80660f0080aadaa3019555f001d60dae`. For that re-audit it read the
Google EGM checkout pinned at
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`, its `docs/codex.md`,
`agents/implementation_readiness.md`, `agents/codebase_details.md`, and
`resources/document_standards/implementation-readiness-standard.md`.
Disposition: **PASS**, with zero Blocker/Major/Minor/Nit findings. Its independent
focused exact-head verification passed **27/27** in 0.68 seconds; `git diff
--check` also passed. No expensive native/full-system test was launched.

The repaired branch additionally retains the bounded project evidence: portable
C06/C08 cone **61/61**, `quality:changed` PASS, and `quality:check` PASS.
The prior C05 `A.PARENT` rejection remains later system-qualification negative
evidence and is not rewritten as a C06 leaf PASS.
