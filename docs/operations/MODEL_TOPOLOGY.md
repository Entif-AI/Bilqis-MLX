# Immutable run topology

Issue #320 separates structural model identity from semantic FactoryRelease identity.
A run records one versioned `ModelTopologySpec`: layers, heads, width, FFN dimension,
and positional context. Vocabulary and answer heads remain release/ABI-owned extents.
FP32, the causal transformer computation and tied embedding readout identify the
implementation separately; they are not arbitrary topology options.

`runtime.model_topology` owns validation, resolution, serialization and tensor geometry.
The operator supplies `--model-topology PATH` to `train` when selecting a structure.
The JSON is the canonical `ModelTopologySpec.to_record()` representation, including
schema, resolved fields and digest. Unknown fields, nonpositive/noninteger dimensions,
invalid head divisibility and digest drift fail before model allocation. Omit the
option to retain the historical default (6 layers, 24 heads, width 384, FFN 1536,
context 96), including its imported weights and matching AdamW. An explicit selection
of that same topology follows the same import boundary. A different topology starts
fresh deterministic FP32 parameters and zero AdamW moments under the inherited
optimizer hyperparameters; the run records initialization origin and seed.

Run state, initialization events and each new typed-run checkpoint carry topology.
Resume resolves saved metadata and verifies checkpoint agreement before staging
cleanup or orphan recovery. A supplied resume selection must match. Historical
receipts without this field resolve explicitly from their saved structural config
and expansion factor; reading them does not rewrite old generations or manifests.
Checkpoint tensors must match the complete structural shape contract. Vocabulary
expansion changes embedding/output extents while preserving the topology digest.

The default context and other defaults never reconstruct an existing run. Source
construction still governs legal input specimens; selecting a smaller context may
make a source lesson inapplicable and fails its input check rather than truncating it.
No topology selection authorizes neural updates. Human-only training remains in force.

## Reproduce the disposable proof

```sh
python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/test_model_topology.py bilqis_mlx/runtime/tests/test_topology_lifecycle.py
```

All metadata tests run without MLX. On Apple Silicon the same suite constructs
the default and two different models, cold-resumes each, rejects structure drift,
and checks append-only vocabulary growth without any optimizer update.

Create a bounded operator selection without starting training:

```sh
python3 -c 'import json; from bilqis_mlx.runtime.model_topology import ModelTopologySpec; print(json.dumps(ModelTopologySpec(2, 4, 32, 80, 96).to_record()))' > /tmp/bilqis-topology.json
python3 -m bilqis_mlx.cli train --dry-run --model-topology /tmp/bilqis-topology.json --run-dir /tmp/bilqis-new-run
```

The dry run reports the selected topology and creates no student. Existing
source/admission preconditions still apply to an operator-owned launch.

## Agent Interface Gate

Disposition: `RAW_INTERFACE_JUSTIFIED`. This is one bounded JSON-file option on the
existing operator CLI, used once per new run or as a resume assertion. It resolves
directly to the canonical typed object; no second CLI configuration representation
or service is introduced. `train --help` discovers the option. Existing JSON/status,
error reporting and exit conventions apply. Invalid input preserves checkpoints;
repeated resume assertions are read-only and require the identical structure. There
is no pagination, remote call, credential, or new mutation authority. Portable parser,
validation and lifecycle tests exercise this boundary; native disposable tests cover
construction and durable readback. Status exposes topology as derived run metadata
for downstream projections; no external cockpit integration is added here.
