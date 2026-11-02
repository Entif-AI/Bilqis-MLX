# C11.3 / #524 separate evidence readout

Base: Lane C/unified bb626d75; active issue branch already contains policy repair
7a736102. Direct prerequisite #523 is closed after accepted #646 integration.
Continue #524's explicit provenance/debt/promotion/retention/transfer display
requirements through the existing read-only BAMF receipt reader. No writer,
assessment, source authorization or scheduling behavior is added.

Create `presentation/atlas_evidence.py` and mirrored
`presentation/tests/test_atlas_evidence.py`. Modify `atlas_metrics.py` to parse an
optional top-level `evidence` mapping into an appended defaulted OperatorView field.
Existing `bilqis.bamf.operator-status/v1` records without evidence stay compatible.
Modify runbook and this evidence directory. Reuse SCHOOL.BAMF_OPERATOR.INVALID.
All touched source/test owners remain below 240 lines.

Records:
- Frozen MeasuredScore(correct:int,total:int,source_sha256:str,rubric_sha256:str).
  Counts are exact nonnegative ints, correct<=total. Both digests are lowercase
  64-character SHA-256. Zero total displays NOT MEASURED, never a percent.
- Frozen OperatorEvidence(candidate_sha256:str|None=None,
  parent_sha256:str|None=None,delivered_work_sha256:str|None=None,
  delivered_rows:int|None=None,grade_debt:tuple[tuple[str,int],...]|None=None,
  capability_debt:tuple[tuple[str,int],...]|None=None,
  promotion_attempts:int|None=None,
  whole_school_fresh_retention:MeasuredScore|None=None,
  learned_transfer:MeasuredScore|None=None,historical_policies:tuple[str,...]=()).
  Distinguish absent debt from measured empty debt. Debt names are display labels,
  never control flow. Values are nonnegative ints; names are nonempty UTF-8 strings
  <=96 chars without controls or surrogates. Debt tuples use sorted name order.

`parse_evidence(value)` accepts absent/None as an empty record. Otherwise require
an exact mapping of only declared keys. Digest/count values accept None. Debt wire
values are mappings name->int; duplicate names are impossible in a parsed mapping.
Scores require exactly the four named keys. Historical policies require a list of
unique safe display strings. Deep-copy everything into immutable tuples/records.
Malformed evidence raises the existing catalog error before replacing a live view.

`render_evidence(evidence)` returns separate lines for candidate/parent/delivered
SHA identities, actual delivered row count, grade debt, capability debt, promotion
attempt count, whole-school fresh retention, learned transfer and historical
policies. Missing values say NOT MEASURED; measured empty debt says none. Score
lines show correct/total and separate exact source/rubric digest lines when total>0.
Zero total says NOT MEASURED and retains its source/rubric identities in expansion.
Historical policies are explicitly lineage only. Scores are supplied observations,
never fresh GENERALIZATION cohorts, promotion authority or proof of a retained
learning gain. The reader does not verify source/producer/evaluator authority.

`OperatorView.evidence` defaults to OperatorEvidence(). `bamf_status` parses evidence
with existing structural validation. `render_panel` keeps old absent-data strings;
when debt exists its compact label says 'debt measured (details)'. When transfer has
positive total its compact label says 'transfer observed (details)'. Expanded mode
appends render_evidence lines after the existing source/model/rubric/rights/census
bindings. The existing eligible-vs-held disjoint denominator is unchanged. Missing
perfect mastery remains NOT MEASURED. No grade label alters ordering/eligibility.

Tests first fail on absent APIs. Assert literal counts/digests/labels in actual
expanded board rendering for one synthetic receipt: candidate f*64,parent 1*64,
delivery 2*64, delivered_rows=12, grade debt A=2, capability debt A.IDENTITY=1,
promotion_attempts=3, fresh school retention 7/8 with source3*64/rubric4*64,
transfer2/3 with source5*64/rubric6*64; historical 'bounded debt cadence 4:1'.
Assert source-held remains3/eligible8, unrelated counts don't imply learning,
missing-vs-empty-vs-zero behavior, Unicode/boolean/NaN/unknown-field rejection,
immutable copied mapping, malformed event preserving previous board view, and
relabeled grades preserve evidence readout/eligible denominator. Extend the real
read-only watcher subprocess test with a receipt containing evidence and compare
journal bytes/mtime/directory entries unchanged.

Commands: isolated /tmp/c524-venv/bin/python -B scripts/run_tests.py for new tests,
test_operator_policy.py, test_bamf_metrics.py and test_bamf_watch.py. Run existing
structure/governance/architecture/docs/error-control-delta checks against bb626d75,
and git diff --check. Fresh pinned EGM readiness precedes implementation; fresh
codebase/comprehension review precedes updated turn-in. Record exact tests and
remaining source/production acceptance. No complete #524 claim without production
observation and launch/resource custody evidence.

## Readiness clarifications

Ordinary printable Unicode is accepted, including `語義` and `A.ÉGALITÉ`.
Debt names and historical-policy strings share exactly the same rule: Python str,
1..96 code points, nonempty after strip, and str.isprintable(). Thus newline,
NUL, DEL, U+0085, U+2028, format controls and lone surrogates reject. No Unicode
normalization or semantic interpretation occurs. Examples rejected: empty string,
97 'x' characters, 'bad\npolicy', chr(0xD800).

Expanded literal lines have prefix `ATLAS EVIDENCE | ` followed by:
`candidate <digest>`, `parent <digest>`, `delivered work <digest>`,
`delivered rows 12`, `grade debt A=2`, `capability debt A.IDENTITY=1`,
`promotion attempts 3`, `whole-school fresh retention 7/8`,
`retention source <3*64>`, `retention rubric <4*64>`, `learned transfer 2/3`,
`transfer source <5*64>`, `transfer rubric <6*64>`, and
`historical policy (lineage only) bounded debt cadence 4:1`.
Each missing scalar substitutes NOT MEASURED. Each absent score emits three lines:
its observation, source and rubric all NOT MEASURED. A zero-total score emits
NOT MEASURED for the observation while preserving its two digest lines.
Each absent debt collection emits one `grade debt NOT MEASURED` or
`capability debt NOT MEASURED` line. Each measured empty collection emits `none`
instead. Nonempty collections emit one line per sorted label=value; no aggregation.
Missing historical policies emit the lineage-only line with NOT MEASURED.

Compact debt text remains `debt NOT MEASURED` if both collections are absent.
Otherwise emit both independent labels: `grade debt measured (details)` or
`grade debt NOT MEASURED`, then `capability debt measured (details)` or
`capability debt NOT MEASURED`. Empty is a measured observation; it never causes
the other absent collection to be described as measured. Retained-step, GREW and
perfect-mastery text remain owned by their existing projection.


Implementation discovery: the existing terminal renderer converts text to ASCII.
The new evidence panel emits JSON Unicode escapes for its labels before that
boundary, preserving exact identities instead of collapsing them to question marks.
The immutable view retains original Unicode. Accepted examples now assert both
original record identity and escaped terminal output. No renderer policy changed.


Turn-in review found a Major: the fixed terminal viewport clipped digests and hid
later rows on ordinary 80x24 terminals. The 80x24/many-debt-row subprocess regression
first failed six literal output assertions. Extend dashboard_watch.py (still <240
lines): for `--once --atlas-details` with a BAMF view, draw the normal compact
snapshot, then write render_panel(expanded=True,width=None) as an unbounded text
report directly to the same output stream. No viewport width/height truncates this
report. The live expanded panel points to the complete snapshot command. No new
CLI option, persistence or renderer policy is introduced. Test40 grade debts,
20 historical policies, final transfer rubric and exact candidate digest, while
preserving journal bytes/mtime/directory entries.
