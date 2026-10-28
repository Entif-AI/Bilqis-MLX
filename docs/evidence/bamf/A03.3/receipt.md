# A03.3 released source-to-frame adapter evidence

Issue: #404
Lane: `codex/bamf02-a-semantics`
Consumed unified head: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed A03.2 implementation head:
`3ff503bb6f7bf112d3c95fe6fdd6deecbaf27c6c`
Intervening docs-only A01 EGM receipt:
`5e736aae9f717b2a5c166ef1f67db1911888ff35`
Review disposition: `EGM_PENDING`

## Released adapter set

`bilqis_mlx/semantics/frame_adapters.py` binds the existing registered source
adapters by their actual adapter identities:

- `source.micro.predicates/v1`
- `source.micro.boolean-connectives/v1`
- `source.micro.boolean-composite/v1`
- `source.micro.boolean-identification/v1`
- `source.finite-numeric/v2`

There is no grade-letter dispatch. `bind_registered_source_row` receives an
existing `RegisteredSourceAdapter`, reruns that adapter's own independent
source check on the exact row, and only then constructs a frame. The frame
adapter registry is keyed by `descriptor.adapter_id`.

For finite-Micro and Boolean source ASTs, operator symbol, arity, input/output
types and any declared role names come from the current source semantic graph.
Concrete source atoms resolve through the frozen Atlas ABI by exact symbol and
must retain the same source-graph token index. Nested source expressions become
typed child frames. Released frame schemas also pin the source semantic graph's
`row_contract_sha256`; this is the existing semantic row contract and is not
the source adapter's provider implementation digest.

For finite numeric rows, the adapter uses the existing
`source_adapters.numeric.decode` path and the native
`semantics.core.Apply/Literal/Operation.signature` objects. The decoded
operator signature must match the source semantic-graph signature and token
index. At the source-expression root, its native
`Operation.contract_sha256` must match the released source row contract.
Recursive numeric children retain their canonical native numeric-operation
contracts; the historical graph can carry a different row contract for those
generated child operators (for example COUNT), so that distinct authority is
not falsely collapsed. Number identities resolve through the frozen Atlas ABI; structured
`NumberSet` literals remain typed atomic child frames rather than receiving
invented semantic IDs.

Inverse Boolean identification remains an atomic source frame after its existing
registered checker passes. Its input observations and candidate options are
preserved exactly, while no selected `root` or `gold` field is introduced
into the neural input frame.

## Boundary closure

Two registered ErrorBus contracts were added:

- `SEMANTIC_FRAME.BINDING.INVALID`
- `SEMANTIC_FRAME.ADAPTER.INVALID_SOURCE`

Adapter and binding failures include the exact source-span start/end and failed
role, plus the released adapter identity for source-adapter failures.

Structured child references now carry their typed output and are checked against
the actual returned subtree set. A parent cannot reference a hash-shaped child
that is absent, and a present child must match the referenced content digest.

The cumulative repair also closes the A03.2 review probes:

- source-qualified concept type metadata is checked against the canonical frozen
  Atlas concept record, including a real-corpus forged-role-allowed-type witness;
- incoming frame occurrence IDs are recomputed from source instance/path;
- incoming frame content digests are recomputed from schema/bindings;
- incoming causal prefixes must cover the source span.
- native `Apply` values cannot reuse the same operator symbol/signature with a
  different semantic row contract SHA.
- an actual C.ADD source row with only its copied source graph
  `row_contract_sha256["school.op.ADD"]` changed to another valid SHA-256 is
  rejected with `FRAME_NUMERIC_CONTRACT_DRIFT`, while the repository's valid
  nested COUNT construction remains accepted under its canonical native
  operation contract.

Formal-domain types are not copied into a shadow ontology. They are supplied by
the existing source semantic graph or native numeric `Operation.signature`
after the source adapter validates the row.

## Actual-source witnesses

`test_frame_adapters.py` uses the repository's real source adapters and source
constructors:

- all six current finite-Micro predicate families bind from actual generated
  source rows;
- direct and composite Boolean rows bind recursively from their actual nested
  source ASTs;
- inverse Boolean identification preserves the checked input atomically without
  adding hidden target fields;
- a real C.ADD row from the current finite numeric source registry decodes
  through the native numeric AST and binds recursive child frames;
- tampering a checked source row produces the registered adapter error carrying
  adapter, source span and failed role;
- removing an actual child subtree while retaining the parent reference produces
  the registered frame-binding error.

## Verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_schema.py`:
12 passed, 1 external real-Atlas witness skipped in ordinary mode.

With
`BILQIS_ATLAS_REAL_CORPUS=f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`:
13 passed, 0 failed, 0 skipped.

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_adapters.py` after
the source-contract repair: 8 passed, 0 failed, 0 skipped.

The AST content-identity test now compares
`native_ast_content_digest(expression)` to the existing
`expression_digest(expression)` and proves that changing only the operation
contract digest changes the expression digest; it no longer uses a tautological
self-comparison.

`scripts/run_tests.py bilqis_mlx/source_adapters/tests/test_source_adapters_micro.py`:
3 passed, 0 failed, 0 skipped.

`scripts/run_tests.py scripts/tests/test_operator_contract_audit.py`:
4 passed, 0 failed, 0 skipped.

The broad historical Grade C source suite passes its five provider-identity tests
before its compatibility class attempts to open the archived historical parent
checkpoint. That checkpoint is not mounted in this worktree, so the class setup
ends with `FileNotFoundError` for the pinned
`student-116760-7e9af4651f28.pt`. The A03.3 numeric witness does not require or
write that checkpoint and passes against the current C source registry.

`scripts/check_module_size.py` reports no new A01/A03 hard-limit debt.
`frame_schema.py`, `frame_adapters.py`, and the extended error catalog remain
below the 1200-line module limit, with no A03 function above 300 lines. The
repository command remains nonzero only for inherited shared-runtime size
regressions outside this lane.

`scripts/error_control_plane.py --check` reports no frame/Atlas/error-catalog
debt introduced by A03. Its repository-wide nonzero result remains limited to
the inherited shared scheduler/plasticity/runtime findings.

`git diff --check`: passed. The production frame modules contain no grade,
trainer, optimizer, or MLX dispatch and perform no neural write.
