# BAMF operator observability invariant

Authority: issues #1496, #1497, #1498; ADR-152.

## Product invariant

BAMF provenance boundaries protect truth. They do not authorize operator blindness.

For every operator-useful fact produced by the active trainer or authenticated accepted custody, exactly one read-only projection owner must either:

1. expose the value with its evidence class and source identity;
2. expose a precise absence state such as `NOT_MEASURED`, `NOT_APPLICABLE`, `MISSING`, `STALE`, `DENIED`, `UNKNOWN`, or `UNAVAILABLE` together with the source-contract reason; or
3. identify an intentional retirement and the operator question that supersedes it.

An intermediate Mission Control contract that lacks a field is an implementation gap, not proof that the underlying fact is unavailable. `null`, `Unavailable`, `Not exposed`, or `Production projection required` must never be the permanent product answer solely because the projection schema has not caught up with evidence already produced elsewhere.

The predecessor terminal cockpit is an information-value baseline only. BAMF does not inherit its visual layout, mutable coupling, or authority model. It does inherit the obligation to let an owner understand what the learner is doing, what changed, why a candidate was retained or rejected, how quickly the system is moving, what is blocked, and whether learning evidence exists.

## Evidence classes

Operator surfaces preserve these distinctions instead of flattening them:

| Evidence class | Meaning | UI treatment |
| --- | --- | --- |
| Accepted | Authenticated retained/custody evidence | May support durable learner-state claims |
| Observed / provisional | Live measured trainer state that has not become accepted learner state | Useful for current-work diagnosis; never promoted into mastery |
| Historical | Exact retained past evidence | May describe the past; never silently relabeled current |
| Partial | A record exists but does not cover the complete requested surface | Show available facts and name the uncovered remainder |
| Not measured | The producer explicitly did not measure the dimension | Say `Not measured`, not `Unavailable` |
| Not applicable | The dimension does not apply to this state/topology/visit | Say `Not applicable` |
| Missing | A required record/value was expected but is absent | Surface the missing boundary |
| Unknown | Evidence exists but cannot establish the value | Preserve uncertainty |
| Unavailable | The requested projection cannot currently be supplied | Exceptional fallback, with reason; never a synonym for unimplemented projection |

Throughput is not learning. Missing evidence is never synthesized as zero, healthy, retained, mastered, or improved. Arithmetic summaries may be derived only from compatible identified evidence.

## Information-value parity matrix

This matrix maps useful predecessor cockpit facts to the current BAMF owner. It is not a requirement to reproduce the old UI verbatim.

| Operator question / predecessor fact | Current producer | Projection owner | Evidence class | Primary surface | Required disposition |
| --- | --- | --- | --- | --- | --- |
| Current activity / phase | `trainer-observed.json` v7 | run observation projection | Observed | Model Forensics Home / Current Work | Always show current activity and elapsed clock when present |
| Active capability | trainer observation + active episode | run/episode projection | Observed or Accepted | Current Work | Current value when present; otherwise retain latest informative visit as recent evidence |
| Candidate step / optimizer progress | trainer observation v1-v7 | run observation projection | Observed | Current Work | Show live progress and latest completed step across visit boundaries |
| Candidate loss and step cost | candidate-step performance / candidate evidence | observation/read projection | Observed; accepted evidence after custody | Current Work drill-down | Show measured loss/performance when produced; never collapse to generic unavailable |
| Teacher policy / strategy | visit evidence + accepted teacher state | teacher/run projection | Observed or Accepted | Current Work / Teacher | Show exact policy key and bounded strategy fields that the contract exposes |
| Teaching/source option | visit evidence / candidate evidence | run/episode projection | Observed or Accepted | Current Work | Show selected option/provider identity when present |
| Target before/after | visit evidence retention scorecard | run/episode projection | Observed; accepted after retention/custody | Current Work / Capability | Show score transition, total and delta when measured |
| Protected before/after | visit evidence protected scope | run/episode projection | Observed; accepted after retention/custody | Current Work / Capability | Show measured protected coverage/regression summary |
| Candidate decision / reason | candidate decision + visit evidence | episode projection | Accepted or recorded rejection evidence | Learning Pulse / Current Work | Show retain/reject/hold and exact reason |
| Latest capability score | CapabilitySnapshot | capability projection | Accepted | School / Capability | Show current accepted score when present |
| Best capability score / durable gain | learning-health evidence / accepted history | capability/learning projection | Accepted when comparable | School / Capability / Health | Show only from comparable retained evidence; otherwise precise absence state |
| Capability debt / qualification | capability/curriculum evidence | capability/school projection | Accepted | School | Show measured debt/state; do not invent zero debt |
| Visits / retained / rejected | episode and decision records | Home aggregate projection | Accepted / recorded | Home Health | Show counts for the actual bounded query scope |
| ST/M / accepted steps per hour | resource observation | resource/Home projection | Measured / Derived | Home / Resources | Derive only from measured compatible rate inputs |
| RTN% / retained-decision ratio | candidate decisions | Home aggregate projection | Derived | Home Health | Label the exact denominator; do not conflate with P(RET) |
| R/H | accepted/retained decisions + elapsed interval | Home aggregate projection | Derived | Home Health | Show only when interval and retained count share a defined scope |
| G/RTN | retained comparable gain + retained count | learning aggregate projection | Derived | Home Health | Show only when comparable retained-gain semantics exist |
| Grade / cadence / recovery | active-grade cadence and visit evidence | school/run projection | Accepted or Observed | Home / School | Show active grade and internal cadence without treating recovery exhaustion as graduation |
| Ready / held curriculum | lawful frontier / curriculum projection | School projection | Accepted | School | Show counts and blockers when the accepted contract provides them |
| Peak memory | trainer observation | resource/Home projection | Observed | Home / Resources | Show measured peak RSS distinctly from allocator budget |
| Disk free / reserve / next write | trainer observation + resource stop/budget evidence | resource projection | Observed / Accepted | Home / Resources | Keep free, reserve and estimated-write semantics distinct |
| Warning / blocker state | learning-health/correction/authority evidence | owning domain | Observed or Accepted | Attention | Only actionable evidenced conditions enter attention queue |

## Conformance rule

A production projection regression exists when all of the following are true:

1. an authoritative producer or accepted/observed source contains an operator-critical fact;
2. the fact is permitted on the read-only operator surface;
3. an intermediate adapter, contract, query model, or renderer drops the fact or replaces it with a generic unavailable/null state; and
4. no explicit intentional-retirement decision supersedes that operator question.

Tests should exercise this rule at the closest stable boundary and, for Electron, once through the real accepted adapter/renderer path. A fixture that merely asserts an empty production contract is not sufficient evidence that the product is complete.
