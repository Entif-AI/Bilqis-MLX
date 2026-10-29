# C09 supersession repair candidate — 2026-10-29

**EGM_PENDING; repair candidate, not acceptance.** IPR-0220. Base26c898c08308041190e15806fef9ba2e02508144; consumed unified da0431bee37c0e4f766f05cc94ceb6b23ac7d054. PM-2026-10-29-007 filed in native incident ledger and read back before source repair.

Fresh independent C09 review executed20 owner tests successfully, then reproduced two Majors: an expired intermediate correction dropped its replacement edge and resurrected an ancestor; unsigned supersedes_event_ids could retire authenticated alternatives. Review ended with workspace credit exhaustion before final report/re-audit. C08 review also failed from credit exhaustion without a disposition. Neither is EGM PASS.

CorrectionEvent/v3 binds sorted, unique supersedes_event_ids into source signing bytes. add_correction requires exact equality between signed IDs and branch request; modifying IDs under the old signature rejects. Event v2 signatures cannot be silently reinterpreted under v3; historical receipts remain historical and require explicit owner migration before current reuse. No persisted historical artifact was rewritten.

Temporal projection retains all recorded, already-effective supersession edges after a fact expires. Future-recorded/effective corrections remain excluded. Expiry removes current fact availability without resurrecting replaced evidence. A→B→C with B valid[20,30) and C valid[25,infinity) selects C both at26 and31.

Regression red:16 passed,2 assertion failures. Targeted C09/error-control:22 passed. Affected C09/C06 signed evidence/history/pattern suites:38 passed. No actual MLX, learner/own AdamW, graph or generation writes. Independent targeted re-audit remains required; issues517/518 stay open and PR550 draft/unmerged. A01/B07/B13/C04 and C10 integration remain pending.
