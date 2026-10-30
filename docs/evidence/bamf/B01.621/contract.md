# B01 structure and adapter identity — issue #621

Consumed Lane B/unified: `a02b9ed45ead1801be6dff655866b73be0ffc8ff`.
Change posture MAINTENANCE; agent interface NOT_AGENT_FACING.

## Behavior boundary

The stable `runtime.model_topology_v2` facade reexports the original topology,
generation, parameter, census, initialization and state functions. Definitions
move to cohesive `runtime.bamf_topology` owners: `config`, `generation`,
`parameters`, `ledger`, `initialization`, and `state`. No new runtime dispatch,
semantic admission, migration, parameter tensor, storage format or source policy
is introduced. Serialization continues to use explicit JSON and tensor keys;
Python implementation module names are not serialized contracts.

All 30 original top-level classes/functions are retained. AST comparison finds
only two changed definitions: `ParameterSpec.category` and `_plastic_parameters`
share the existing adapter matrix wire names through one named
`AdapterMatrixComponent` enum. Its INPUT/OUTPUT values remain exactly A/B.
The producer uses those values and the category consumer uses their derived set.
This describes parameter schema rather than curriculum grades. No architecture
checker, exemption, baseline, numerical threshold or tensor name changes.

Every original test method moves to the mirrored owner tests. Tests that load
`configs/models/bamf-0.2.json` update only their repository-relative location.
The historical compatibility tests remain a separate test owner. The original
525-line companion file is removed; run the replacement suite as a directory.
The stable 20-line production facade and all production/test owners are below240
lines. No recursive directory-debt cleanup is performed.

## Validation contract

```bash
python3 -B scripts/run_tests.py bilqis_mlx/runtime/bamf_topology/tests
```

Normal baseline:19 passed,2 existing opt-in skips. After split:20 passed, the same
2 skips. The added regression verifies exact three-group A/B wire names and
adapter matrix categories while norm remains AUXILIARY. Full disposable proof
sets `BILQIS_BAMF_FULL_WITNESS=1` and selects MLX CPU. It initializes the complete
unbound parameter/moment tree, preserves exact census/storage keys, saves and
reloads complete tensors, and verifies independent semantic/motif extent growth.
The opt-in historical bundle proof requires a separately supplied frozen bundle;
no actual saved student is modified for this task.

Source-wide architecture guard failed on clean unified at the old category's
A/B literal comparison and passes after the schema-owned suffix change.
Source-wide error-control debt remains a separate inherited gate. Runtime state
and adaptive teacher are untouched. No human-run command is invoked.

## Preservation authority and scope of this receipt

This is a maintenance/preservation receipt, not a replacement B01 specification.
The authoritative complete algorithm, signatures, fixed topology defaults,
validation, initializer rules and serialization logic are the
[consumed B01 source](https://github.com/Entif-AI/Bilqis-MLX/blob/a02b9ed45ead1801be6dff655866b73be0ffc8ff/bilqis_mlx/runtime/model_topology_v2.py)
and [BAMF architecture/tensor ledger](https://github.com/Entif-AI/Bilqis-MLX/blob/a02b9ed45ead1801be6dff655866b73be0ffc8ff/docs/architecture/BAMF_0_2.md).
Those links are immutable inputs to this receipt; their original contracts remain
in force. Repeating the full schema/default/algorithm definitions here would
create a second specification without changing the requested behavior.

The old-to-new owner map is complete:

| New owner | Preserved definitions |
| --- | --- |
| config | ModelTopologySpecV2, deserialize_topology, digest helper and fixed dimensions |
| generation | GenerationExtents, GenerationProvenance, strict from-record helper |
| parameters | ParameterGroup, ParameterCategory, Initializer, ParameterSpec, ParameterCensus |
| ledger | expected_bamf_shapes, bamf_parameter_census, print_bamf_parameter_census and all prefix declarations |
| initialization | initializer_seed, initialize_bamf_parameter, project_identity_source_factor, initialize_bamf_row |
| state | validate_bamf_parameters, create_unbound_bamf_state, bamf_storage_key, bamf_serialization_arrays, bamf_deserialize_arrays |

The unchanged source supplies `bilqis.mlx.model-topology/v2`,
`bilqis.mlx.generation-extents/v1`, `bilqis.mlx.generation-provenance/v1`,
`bilqis.mlx.bamf-initialization/v1` and `bilqis.mlx.bamf-named-tensors/v1` contracts.
A fresh implementation audit compares those definitions, not a new paraphrase.
The complete topology, extent, census and storage-key JSON output is byte-identical
before/after extraction:40,013 bytes for the fixed one-bank/one-page witness.

Exact full disposable CPU command:

```bash
BILQIS_BAMF_FULL_WITNESS=1 python3 -B -c 'import mlx.core as mx, runpy, sys; mx.set_default_device(mx.cpu); sys.argv=["scripts/run_tests.py","bilqis_mlx/runtime/bamf_topology/tests"]; runpy.run_path("scripts/run_tests.py",run_name="__main__")'
```

The optional historical isolation proof additionally requires
`BILQIS_V1_BUNDLE_WITNESS` to name an existing immutable v1 bundle directory with
its manifest and complete model/own-AdamW tensors. It verifies source hashes
before/after and uses disposable copies for corruption probes. No new historical
bundle is manufactured and no real learner is resumed. Missing historical input
is reported as the existing opt-in skip, not an executed custody proof.
