# B03.2 #443: actual A05 atomic, partial and legal-empty paths

Status: **VERIFIED_SOFTWARE; A02_B03_QUALIFICATION_PENDING**. Final A02/B03 qualification and
parent acceptance remain open; no closing link is asserted here.
Base Lane B `09def57ae1a049886f2e7278543f86d28182021a` consumes reviewed
unified `ac498099b56a38f3b669e16d30f8bab580709f49`, including actual A05
implementation/EGM head `de5bb9c562992e3620a539dc5519f26a7374e772`.

This continues the actual-current-config recompilation and exact source/vector
bijection in B03.1 `a05-integration-v1.md`. A05 itself owns partial-frame
visibility: before closure it emits only source-visible raw atoms. The encoder
preserves those vectors unchanged, and the actual prefix3/future-suffix and
unequal-row tests remain in the owner suite. No missing member, future source
vector or padding vector is accepted as a semantic member.

Actual AtomicFrame closures are now supported. The encoder derives an exact
AtomicSourceHandle from the freshly projected A05 closed context, and requires
one `AtomicFrameEmbedding(handle, vector[768])` per closure in actual stream
order. Missing, extra, reordered or foreign atomic handles reject. The supplied
atomic vector is the closure seed unchanged; no frame/feature tensor is read
and no semantic feature summary is invented. This extends the earlier A13-only
atomic fixture to an actual A05 atom+atomic-closure stream. Numerical embedding
origin remains the upstream embedding owner's responsibility.

Legal empty FrameInstance closures are now supported when A05 successfully
recompiles them under the supplied live FrameCompilerConfig. The actual schema
body, packed schema payload/map and cardinalities therefore participate in
validation. The proof uses a schema with optional roles and zero bindings;
a required-role zero-binding frame rejects. No roleless schema or new semantic
primitive is invented. B02's `empty_frame_factor_terms` reads the released raw
schema128, explicit NONE role128 and NONE type/role depth features, with actual
A06 exact-ID overflow handling. Its source projection/handle and manifest
digest remain in a separate typed computational factor result. The helper
alone does not grant legal-empty admission; current-config recompilation is
the consuming encoder's proof.

The empty path follows B01's summary rule and its explicit NONE mean:

`RMSNorm(frame.empty_seed + ((schema128+NONE_role128)/2) @ frame.project_summary.T, frame.norm)`

It does not execute member query/key/value, interaction, project_output or pool
gate. No fabricated member vector is added; the returned member matrix is
`[0,768]`. Raw/atomic positions retain `None` factors. Complete concept-frame
equations and source-aligned member vectors remain unchanged. Nested/child
closures remain B03.3 #444's integration obligation.

`CompiledEmbeddingVectors/v2` adds optional per-row atomic closure entries;
omitting them is valid only when the compiled input contains no atomic
closures. `FrameEncoding/v4` adds typed empty factors. Prior v1/v3 receipts
remain historical readback descriptions. These records do not publish a source
release, eligibility credential, checkpoint or student generation.

Red proof: encoder13 passed and2 new empty cases failed at the previously
unsupported empty-frame input; local log `2026-10-29T13-50-45-262Z-93963.log`.
The new atomic-closure record also first failed import, local log
`2026-10-29T13-52-34-362Z-13276.log`.
Green: **51/51 real affected MLX+source tests pass, zero skips**:
encoder16+B02existing15+A05owner20. The empty seed equals the literal equation,
is finite, and has nonzero gradients through empty_seed, project_summary,
frame.norm and raw schema/NONE-role tables. Unused member-attention/pool
parameters have zero gradients. The actual atomic closure exactly equals its
supplied vector, every unused frame/feature parameter gradient is zero, and
missing/duplicate closure vectors reject. Existing current-grant, policy/schema
drift, source-order, future-suffix, padding and member-gradient proofs still pass.
Explicit source operator/hygiene audit reports no new debt.

Fresh EGM turn-in returned **PASS**, no Blocker/Major, and independently
reproduced51/51 with zero skips at pin
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. Prior contract review specified
the empty equation, exact atomic handle and current A05 schema/rights proof.
Actual A02 allocation/embedding qualification and broader B03/whole-model
acceptance remain separate. Neural F05, real learning and retention remain
unmeasured; mock or source fixtures do not establish them.

IPR-0220 remains open. PM-2026-10-29-001/003/004, RC-024/PAT-028 and prior
controls remain applicable. No durable student, own AdamW, teacher, champion,
original checkpoint or source release changed. Human owns integration and
durable training. Next action: fresh review, repair material findings, push
the coherent #443 slice, then continue nested-source handle work #444.
