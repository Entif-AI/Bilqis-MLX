# A03.1 canonical typed frame records evidence

Issue: #402
Lane: `codex/bamf02-a-semantics`
Consumed unified head: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed frozen Atlas implementation head:
`10de2930f29d2500309b49b9ba7d259dce3e42c3`
Review disposition: `EGM_PENDING`

## Implemented contract

`bilqis_mlx/semantics/frame_schema.py` declares frozen, versioned
`FrameSchema`, `RoleSpec`, `ConceptRef`, `RoleOccurrence`,
`ChildFrameRef`, `FrameEdge`, `SourceSpan` and `FrameInstance` records.
Canonical serialization uses deterministic UTF-8 JSON with sorted keys and
explicit schema-version fields; frame schema and instance readers require exact
canonical byte roundtrip.

The frame layer reuses `bilqis_mlx.semantics.core.Literal` and `Apply`
constructors and the existing `expression_digest` identity. It does not create
a second expression AST or semantic registry. `concept_ref_from_snapshot`
binds semantic identity and ABI index from the frozen A01
`FrozenAtlasSnapshot` interface.

`FrameInstance.occurrence_id` is SHA-256 over source-instance identity plus
structural path. `content_digest` is independently derived from released frame
schema identity and role/occurrence canonical semantic content. Source span,
source-instance ID and structural path therefore do not collapse occurrence into
content identity.

Bindings are keyed by exact `(role_id, occurrence_index)` pairs. Child frames
carry separate occurrence and content identities; `FrameInstance.child_edges`
materializes explicit parent/role/occurrence/child edges.

## Literal behavior witnesses

- Two identical TRANSFER contents at different source-instance identities have
  distinct occurrence IDs and the same content digest.
- Swapping TRANSFER agent and recipient preserves the same source occurrence but
  changes the content digest.
- Agent and recipient may both carry the same `Entity` type without collapsing
  their role identities.
- A plural `member` role preserves occurrence 0 and occurrence 1 separately.
- A nested child binding emits an explicit parent-to-child occurrence edge.
- Schema and frame-instance canonical bytes roundtrip to equal frozen records.
- Native `Apply` and `Literal` constructs retain the existing
  `semantics.core` construct and content identities.

## Verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_schema.py`:
4 passed, 0 failed, 0 skipped.

`scripts/check_module_size.py` reports no A01/A03 module or function
regression. `frame_schema.py` is 386 lines, below the 1200-line module hard
limit; all functions are below 300 lines. The repository-wide command still
reports three inherited shared-runtime size regressions outside Lane A.

`scripts/error_control_plane.py --check` reports no
`bilqis_mlx/semantics/frame_schema.py` or Atlas debt. Its nonzero repository
result is limited to the inherited shared scheduler/plasticity/runtime findings
already owned outside this leaf.

`git diff --check`: passed.

The module performs no model/optimizer write and contains no grade-specific
runtime dispatch.
