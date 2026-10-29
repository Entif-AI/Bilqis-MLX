# C08 provenance repairs

IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION. IPR-0220; PM-2026-10-29-008 logged/read back before repair. Consumed unified da0431bee37c0e4f766f05cc94ceb6b23ac7d054. Two Majors found by fresh independent EGM despite60 owner passes and one optional skip.

ResourceRow/v2 requires training_row_sha256 and delivered_content_sha256. from_training_row hashes the entire native typed row, including prefix/features/eligibility/answer-plan/targets/auxiliaries/provenance/rules. The supplied C02 batch digest is carried into the plan source digest. Same-ID/same-shape changed target/input now changes the plan; both hash changes reject OOM replay after candidate restoration. Actual integration must obtain the delivery hash from a verified C02 batch and rebuild row profiles on replay; this pure-owner seam does not authenticate caller batch membership or B11 custody.

ImmutableSourcePacket now validates exact fields, recursive tuple-only immutability, canonical mapping keys and forbidden authority on direct construction as well as the factory path. Mutable retained aliases, weights, duplicate keys and noncanonical records reject; legitimate source receipts survive.

Final affected proof62 passed, zero failures, one optional original-source corpus skip. Packet red captured two failed subtests (runner reports whole failures2); resource red captured missing new required argument before API implementation. Fresh pinned EGM independently ran62/1 suite and adversarial probes. Both Majors resolved for pure-owner scope. Additional permanent replay assertions reflect the reviewer's successful probes. Actual MLX/B11/source-owner integration remains pending; no persistent learner/AdamW, graph or source promotion. PR550 draft/unmerged;513/514/515 remain open.
