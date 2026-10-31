# Source-backed numerical ingress for B11.1a #586

Lane B and unified consumed: `9104ce733e04fb9c82420428b18dfdbf5db49535`.
Implementation checkpoint: `833c02291d449c612e5be9b3b0c4cbe73cd8a88c`.

A05.5 #594 is accepted through PR #618 and is no longer a missing source-atom
dependency. The source-backed numerical ingress now calls its accepted
`encode_source_compiled` path before constructing a B11 numerical session. The
caller supplies source selections and the B01 parameter tree, never hidden
states, generation labels, prefix digests, group numbers or predecessor results.
Validity comes from encoder handles; each compiled row is one source sequence.
The fixed B01 topology, semantic extent digest and compiled-prefix digest are
derived internally. These observations do not establish B13 custody.

The existing fail-closed B05 producer path is unchanged. All results remain
`UNADMITTED_NUMERICAL`. This is a bounded precursor, not #586 acceptance, a
producer receipt, motif-hit permission, model admission or a learning claim.

## Verification

Red: the new test module failed to import the missing source-backed API before
implementation. Green: four real-source MLX tests passed with zero skips.
The combined source encoder, backbone numerical and bridge selection passed
17 tests with zero skips on the M3 Ultra in an isolated disposable checkout.

The new tests compare all twelve executed layers against literal NumPy
feedforward equations with nonzero weights, preserve the ordered group chain,
differentiate through source identity and executed backbone parameters, and
reject revoked source, changed tokens, incomplete parameters and caller hidden
or generation injection. The resulting group still cannot obtain B05 admission.
The new literal oracle keeps attention weights zero; it is not an independent
nonzero-attention or multi-row/padding qualification.

Reproduce the pinned A01 artifact using `scripts/bamf/rebuild_atlas_artifact.py`
and the conformance command in PR #618. Set `BILQIS_A01_ATLAS_BUNDLE` to that
artifact and use an existing MLX environment:

```sh
python3 -B -m unittest \
  bilqis_mlx.learning.source_atoms.tests.test_backbone \
  bilqis_mlx.learning.source_atoms.tests.test_encoding \
  bilqis_mlx.runtime.tests.test_backbone_group_numerical \
  bilqis_mlx.runtime.tests.test_backbone_source_bridge
```

Consumed-base structure/governance checks report zero violations. The two added
code files have zero new smell findings. Release metadata and pre-push checks
pass. These scoped results are not a repository-wide quality claim.

## Independent review and remaining blockers

A fresh reviewer used pinned EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.
The two-file source review found no implementation Blocker or Major. The reviewer
did not independently execute tests or audit the topology implementation.

The review encountered the 714-line topology owner. This triggered the mandatory
structure interruption. Existing #621 / draft PR #622 owns that exact repair;
no competing rewrite or baseline waiver is introduced here. Further feature
work remains paused until that repair is consumed and revalidated. #622 itself
also awaits the runtime-directory repair in #520 / PR #614.

Before #586 can turn in, it still needs execution-owned producer receipts,
the declared motif-boundary disposition, the actual B05 selection chain and
source/parameter/prefix/cache/gradient adversaries, followed by fresh EGM.
The issue explicitly does not wait for final B13 acceptance; its own execution
boundary must nevertheless bind the observed input and parameter generation.
No durable student, optimizer, checkpoint or graph was changed.
