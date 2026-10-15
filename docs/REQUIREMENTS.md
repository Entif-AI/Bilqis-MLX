# IPR-0220 | Internal implementation requirements and status

Source: protected issue `IPR-0220` (private issue #335). This document summarizes executable obligations, **not** a replacement for the user's verbatim instructions. All requirements below are private experimental implementation policy, not public Rosetta contracts.

| ID | Obligation | Current status |
|---|---|---|
| BMLX-001 | Letter-grade A/B/C... and distinct historical `G##` capability concepts, 6–9 compatible prerequisites per grade | Six direct Grade A predicates source-probed, 216 balanced train/exam rows, frozen graph prefix matched; curriculum admission pending |
| BMLX-002 | New runs start Grade A. Only `--resume` may continue an existing successor run; no overwriting state | Nontraining start/resume and no-overwrite contract tested |
| BMLX-003 | Grade-major full pass, then two independent weakest-3 passes over current + previously passed grades | Pure scheduler and two retested independent worst-three rounds tested; neural integration pending |
| BMLX-004 | Single checkpoint (FP32 weights + own AdamW) scores 100% of current grade before graduation | Same-checkpoint grade exam/promotion contract tested; real candidate admission pending |
| BMLX-005 | Best complete whole-student seed, preserve historical native optimizer and archived research provenance | Source hash, full FP32 forward and 39/39 AdamW moments verified on CPU; real optimizer continuation still pending |
| BMLX-006 | Earlier grade champion pointers share one physical file and yield 1 vote per grade in subsequent teaching | Pure shared-pointer and 3:1 grade-vote policy tested; adaptive teacher wiring pending |
| BMLX-007 | Weighted teacher soup uses grade pointer multiplicity; soup never becomes a trainable optimizer checkpoint | Pure 3:1 frozen teacher weight averaging tested; real consolidation teacher integration pending |
| BMLX-008 | Old grade regression allowed at later promotion; repoint earlier grade champions if the same candidate also passes those grades | Same-candidate earlier-grade repoint and permissible regression tested |
| BMLX-009 | Incomplete final whole-school cycle creates consolidation teacher and retries only failing grades | Whole-school incomplete/failed-grade next-cycle scheduler tested; actual teacher soup integration pending |
| BMLX-010 | Source-attested roots, previous-grade prerequisite mastery, binary and test-fitting additional typed answers, independent assessment | Direct Grade A generator: independent oracle pairs, zero unseen exam tokens, disjoint train/exam inputs; composed and numeric grades still pending |
| BMLX-011 | MLX backend with verified model/optimizer conversion and parity; fail closed until proven | Full historical model forward and 39/39 moments checked read-only; fixture saved/reloaded 116760-step AdamW with four matching updates and tiny-gradient parity; real training remains unproved |
| BMLX-012 | Existing six-panel School50, stable npm scripts, neural-inert status/dashboard/preflight | Original six-panel renderer reused, npm status/dashboard/dry-run tested; training hard blocked |
| BMLX-013 | External disk backup of every explicitly retired model and code tree, verified readback, no deletion or broad `~/Code` mutations | Plan/external copy/hash readback tool and symlink manifest fallback tested; no actual external drive mounted or bulk copy performed |
| BMLX-014 | Historical source/archive immutability, bounded disk budgets, private authority and reliable checkpoint recovery | Continuous acceptance gate |

**Important:** 1,150/1,150 belongs to the old version, not the new school-wide graduation policy. Capability-to-grade partition and new rubric need source-anchored review. Unknown/unsupported lesson semantics block training, they do not get substitute Boolean labels. Human-only neural training remains disabled.
