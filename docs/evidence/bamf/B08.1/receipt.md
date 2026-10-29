# B08.1 source-gated motif read kernel: scoped candidate

Issue: [#460](https://github.com/Entif-AI/Bilqis-MLX/issues/460)
Lane: B, isolated candidate `codex/bamf02-b08-reads-20261029`
Base: B07.3 scoped EGM PASS candidate `cac4c6f`
Consumed Lane B: `7b70b0d4f70c2df7d79ddd69db91a2eaf1da78ae`
Consumed reviewed unified: `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`

## Owned software

`learning/atlas_engram_reads.py` implements a source-gated
`read_motif(site_index,hidden,features,positions,tasks,frontiers,policies,
manifest,parameters)` for the two B01 motif sites. It uses the existing
sealed B07.4 `MotifParameterView` and B07 full canonical key manifest.
Every row's entire proposed frame set passes A13 context eligibility
before any page gather. Each frame schema requires its own live
source-frontier grant binding the exact canonical schema bytes,
release, scope, principal, tenant, rights and time frontier. A revoked
frame, incompatible join or missing/forged schema grant produces no
motif gather or residual.

Within an eligible row, lookup tries exact then structural full-key
equality, with release and scope encoded in the canonical key.
The gate is the B01 equation:

`sigmoid(dot(gate_hidden,RMSNorm(h))/sqrt(768) +
dot(gate_feature,features128)/sqrt(128) + bias)`.

A hit emits `h + gate * projection(slot128)`; a miss preserves the
already-factorized hidden state bitwise. When every position misses,
the exact input array object is returned. A result records
EXACT/STRUCTURAL/MISS/HELD/FOREIGN_RELEASE per position, actual
participating slot IDs and source context digests. No slot allocation,
AdamW write, parameter registration or checkpoint promotion occurs.

The caller's 128-wide type/role/schema feature vector is **not**
treated as a source credential. B02/B11 must bind it to admitted
features before production use. B08.2 owns the after-layer4 placement,
telemetry and integration with the three depth groups.

## Verification

```
PYTHONPATH=/Users/emilie/Code/bamf-planning-20261027/.venv/lib/python3.13/site-packages \
python3 -B scripts/run_tests.py \
  bilqis_mlx/learning/tests/test_atlas_engram_reads.py \
  bilqis_mlx/learning/tests/test_atlas_engram_allocation.py \
  bilqis_mlx/learning/tests/test_atlas_engram_parameters.py \
  bilqis_mlx/semantics/tests/test_context_eligibility.py \
  bilqis_mlx/runtime/tests/test_model_topology_v2.py
```

**77 total, 75 passed, 0 failed, 2 existing optional skips.**
The new tests verify both site gates against the literal sigmoid(-4)
equation, exact-over-structural precedence, bitwise no-op misses,
revoked/forged schema and frame grants, foreign-release and
foreign-scope misses, padding isolation, finite nonzero page,
projection, norm and gate gradients at both sites, and wrong-site
or malformed-tensor rejection. Existing B07 allocation/page,
B07.4 parameter custody, B01 ledger and A13 gate tests remain green.
`git diff --check` passes; no new error-control-plane findings
were observed in the new module.

## Disposition

**SCOPED_CANDIDATE_EGM_PENDING_SOURCE_AND_GENERATION_INTEGRATION.**
The B07.1 source key probe, B02 feature provenance, B03.3 nested
source closure, B08.2 placement, B11 orchestration and B13/C
retained-generation authority remain independent integration gates.
The candidate does not admit a source, authorize an unretained motif
manifest, alter historical learners or close B08/B08.1.
