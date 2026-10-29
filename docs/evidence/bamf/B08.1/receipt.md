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

After fail-closed public-entrypoint mitigation: **78 total, 76 passed,
0 failed, 2 existing optional skips.**
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

**EGM_BLOCKED_SOURCE_SCHEMA_AUTHORITY_AND_CACHE_IDENTITY.**
Independent Goldfish review at immutable `4225b2c` found one
Blocker and one Major, documented with exact adversaries in
`docs/evidence/bamf/B08.1/egm.md`. A same-ID/revision forged
schema with a matching caller-minted grant could authorize an
EXACT neural gather; schema-grant state also was not included in
the returned A13 context digest. The numerical kernel tests remain
useful. The public `read_motif` entrypoint now **fails closed
unconditionally**; only the private experimental numerical helper
remains testable. **This branch must not be integrated or wired into
the runtime** until the A03/B07.1 source owner supplies a
verifiable released-schema witness and B08 binds the complete
read-cache dependency identity. No EGM PASS is claimed.

The B07.1 source key probe, B02 feature provenance, B03.3 nested
source closure, B08.2 placement, B11 orchestration and B13/C
retained-generation authority remain independent integration gates.
The candidate does not admit a source, authorize an unretained motif
manifest, alter historical learners or close B08/B08.1.

## 2026-10-29 source-qualified group-1 second-read repair candidate

The historical EGM Blocker above remains the reason motif **hits** stay
quarantined.  A new isolated repair branch based on current Lane B `7907889`
does not import Lane A as accepted authority and does not merge a sibling lane.
Its consumed tree contains the repo-owned A03.4 source-pin implementation as a
provisional cross-lane dependency; the exact A03.4 bytes match the independently
reviewed Lane A candidate, but unified acceptance is still treated as pending.

The public `read_motif` boundary now implements only the minimum safe B11
group-1 second-read contract:

- site 1 only (after the first four-layer group);
- each non-atomic schema is reloaded through
  `lookup_source_pinned_frame_schema`, so caller-minted same-ID/revision schema
  bodies cannot become read authority;
- the current A13 `project_context` path rechecks frame/member grants,
  revocation, rights/correction epochs, time and causal prefix;
- the returned dependency/cache digest binds the A13 approved-context digest,
  A03.4 schema witness, motif manifest digest, Atlas source bundle, retained
  generation digest and parameter-tree digest;
- an optional expected cache digest fails closed on retained-generation or
  parameter/cache drift;
- even when an exact motif slot exists, the public result is the exact input
  tensor with `QUARANTINED_NO_HIT` and no participating slot.  No caller
  digest, provisional A03 bytes or local manifest can mint an authorized hit.

The real repo-pinned A01 artifact
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
was used for the A03.4 lookup.  The focused adversary proves: a forged
same-ID/revision schema fails; stale rights, revoked frame grant and a future
prefix hold before readout; retained-generation cache drift rejects; and an
existing exact slot still produces no residual while cross-lane authority is
quarantined.

Affected real-source suite: **89 total, 87 passed, 0 failed, 2 existing
optional skips** across B08 reads/allocation/parameter custody, A13 context,
A03.4 released schemas and B01 topology. `git diff --check` passes. The new
module is 389 lines. Repository static checks show only inherited semantic
import-boundary debt and three pre-existing module-size regressions; no new
B08.1 finding was introduced.

**Disposition: EGM_PENDING / SOURCE_HIT_ADMISSION_BLOCKED_ON_REVIEWED_UNIFIED.**
This repair is sufficient for B11 to execute a truthful second-read **no-hit**
boundary while source authority is quarantined. It does not complete #460,
#586 or #577, authorize a motif hit, publish a retained generation, start
training, mutate Lane B, or close an issue. Fresh independent EGM is required
before any integration decision.
