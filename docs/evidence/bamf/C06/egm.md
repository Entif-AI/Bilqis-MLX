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
