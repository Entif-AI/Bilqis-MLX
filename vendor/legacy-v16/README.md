# Pinned legacy source inputs

This is a private, read-only snapshot of the historical Bilqis source packages from `bilqis-triplets-v16`, retained for reproducibility of the current trainer's exact source-oracle semantics and inherited policy implementation. **Do not develop new Bilqis capabilities here.** Active code belongs in the top-level `bilqis_mlx/` package.

The live Grade A/B constructors intentionally verify the exact SHA-256 of the relevant historical source modules, including the micro-world and Boolean source oracles, rather than interpreting a changed module under the old semantic identity. The bootstrap checkpoint and inherited teacher state belong to the ignored `runs/primitive-consolidation-v16-triplets/` folder. They are not committed to Git and should be preserved as an explicit external-backup artifact before retiring the former repository.

This vendoring eliminates implicit runtime dependencies on sibling `~/Code` directories and on ephemeral Git worktrees. Historical external file paths in dated reports remain provenance descriptions only.
