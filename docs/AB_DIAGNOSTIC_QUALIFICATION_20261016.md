# A/B saved-evidence diagnostic qualification

Verified 2026-10-16. Governing private contract: [socr8s/private-ip#336](https://github.com/socr8s/private-ip/issues/336), **OPEN**, IPR-0220, parent #335. This is a bounded evidence-audit milestone. The requested generative A/B training trial, all five runtime diagnostic loops and Grade C admission remain unfinished.

Source baseline: `codex/lettergrade-mlx-v1` at `1478bdd71d135b8ad20b84b5151146d3a6db0958`. Isolated implementation: `codex/336-ab-diagnostic-qualification`. See the latest protected issue checkpoint for its verified implementation HEAD. The primary checkout's trainer, scheduler, catalog and unrelated research WIP were preserved. Four explicit diagnostic WIP files were reused and qualified here; the provisional prerequisite ratio and error-memory bound were not adopted.

## Observed saved student

Read-only source: `/Users/emilie/Code/bilqis-mlx/runs/school-mlx-v1`. Generation 3041, optimizer step 155640, 2430 visits, 6718 inherited/evolved teacher events. Student SHA `1bde35cad0b33b409fc311de38593daeda5da58d4f6a2c949c55b34a4edbb7c4`; its pointer declares model plus matching native AdamW. This audit did not load or independently rehash tensor bundles.

The latest cohort is `a55ecd69379840befcde3711c8cbc269d3b447d351487ef07b3a46760f0b126f`, rubric `4aee94a3c06cfb4567595b315b0ac88aee4d5ed9cb32a3a86f89ac6ee610a94f`.

| Observation | Grade A | Grade B |
| --- | --- | --- |
| Latest recorded correctness | 55/72 | 33/72 |
| Reconstructed predictions FALSE / TRUE | 31 / 41 | 37 / 35 |
| Gold FALSE / TRUE | 36 / 36 | 36 / 36 |
| Constant-answer output on the entire grade | Not observed | Not observed |
| At/below capability-conditioned majority baseline | Not observed | Observed |

Five B capabilities are at/below 6/12: AND, IMPLIES, NOT, OR and XOR. IFF is 8/12. The latest two B grade observations are 36/72 then 33/72, so the consecutive baseline warning is observed across two distinct checkpoints and cohorts. These scores describe rotating samples; they are not a paired causal estimate of learning change.

## Implemented and qualified

`npm run diagnostics` reads existing event, immutable state and cohort JSON only. It reconstructs binary predictions from complete gold/miss/score receipts and rejects inconsistent scores, malformed checkpoint identities, negative steps, wrong capability inventories, run/generation mismatches and changed cohort content. Same-checkpoint rescoring is not counted as a learning trajectory.

The audit reconciled **139** archived exam records: **39** current A+B records have verified generation-bound outbox IDs and exact delivery-event membership; **100** older Grade A records predate that outbox and are explicitly reported separately. Only the 39 matching current source/generator/rubric contracts enter the current longitudinal check. A same-contract capability/count change fails rather than silently becoming another rubric.

S1 records exact constant-output behavior against varying gold. S2 records correctness at/below the observed capability-conditioned majority baseline. Aggregate baselines sum the constituent capability baselines; pooling cannot certify discrimination when individual capabilities have only one gold class. These descriptive warnings do not establish statistical nonlearning, all forms of answer collapse or the complete peer/champion-relative lag criterion.

| Original warning | Evidence available here | Remaining obligation |
| --- | --- | --- |
| Repetitive answers | Binary output distribution and confusion; consecutive distinct-cohort observations | Runtime response and subsequent outcome receipts; richer collapse criteria if justified |
| Chance / lag | Actual majority baselines, per-capability counts and current consecutive warnings | Calibrated uncertainty, peer/champion-relative diagnostics and teacher follow-up |
| No lasting acquisition | `NOT_MEASURED` | Exact delivered source specimens plus immediate/fresh delayed assessment and later retention lineage |
| Disconnected semantics | `NOT_MEASURED` | Canonical constituent/prerequisite IDs, earlier mastery evidence and defined world translations on delivered examples |
| Needlessly complex introduction | `NOT_MEASURED` | Code-owned smallest lawful introduction, complexity dimensions, delivered order and certified simpler alternatives |

No teacher decision or policy allocation is changed. There is no new training stop gate. Successful audit exit means the readback succeeded; it does not approve a curriculum or launch training.

## Proof and custody

Negative controls first reproduced the draft's false single-class alarm, same-checkpoint longitudinal claim, stale whole-history suppression and acceptance of extraneous scores. Independent review supplied additional aggregate-discrimination, capability-inventory and event-outbox controls. Run-ID borrowing, malformed identities and corrupted event/state/generator metadata are also rejected. CLI fixtures compare every saved file byte before and after the read.

The focused suite and full-suite result are recorded in the protected implementation checkpoint. Two optional tests for a run mounted directly under this isolated checkout are skipped; the separate actual saved-run audit above provides the real JSON evidence readback. No synthetic result is a neural mastery result.

The source-only human-resume dry-run verified all **216** historical source records. Its existing `blockers: []` describes that preflight's checks, not completion of #336. The ABI and module-boundary checks pass. Independent external ABI expectation remains unconfigured, so the ABI guard is **advisory**.

Saved run pointer SHA-256 remained `c528d654e6e96867fb4b898bf5e14ae0e9028c71de50a53cdb12768fe1ca49d6`; event ledger SHA-256 remained `197c581ff0602ec56a5c48e2a5ca3dd2b0f63e35a076ed0859053a9fb9349910`. The audit imports neither `torch` nor `mlx` and loads no weights. The raw local report is ignored at `artifacts/diagnostics/ab-20261016.json` and can be regenerated with the command above.

Existing incident **PM-2026-10-16-001**, RC-084 / PAT-066, was enriched and read back in the native Entif Post-Mortem Ledger. Other governing incidents remain PM-2026-10-16-002 through -005 and adaptive-teacher noninterference PM-2026-10-14-014. Filing does not close their remediation.

## Next permitted development

1. Complete the code-owned original-ID lesson/catalog contracts needed for A/B generation, including bounded prescribed teaching worlds, constituent links and minimal introductions. Preserve old releases; the earlier audit's 33 unresolved cross-world positions remain scoped coverage debt. Elementary stipulated semantics do not require a universal theorem or full NI morphology claim.
2. Persist exact **selected and delivered** batch/specimen identities, typed AST/constituent IDs, policy choice and step lineage through the existing boundary outbox. Offered candidates are separate from delivered training. Preserve learned teacher choices and fair unresolved errors; the primary checkout's 24-item and up-to-25% policies remain unratified.
3. Implement and falsify S3–S5 against that evidence; connect all five observations to teacher-readable choices and the next measured outcome. Verify the source→generated A/B lesson→teacher selection→exam→diagnostic flow on disposable state.
4. Only the human initiates or resumes real neural updates. Reassess real learning on intact checkpoints. Grade C remains unadmitted until the prescribed A→B replay ends with one complete student and its own AdamW scoring 144/144.
