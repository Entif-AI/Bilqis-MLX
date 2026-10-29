# A07.1 independent EGM review | source-qualified PURE operators

Issue: A07.1 #413; parent A07 #353.
Reviewer: fresh-context Goldfish worker-2, read-only.
Initial immutable head: `e6a9b30af6197fb86a93a2b208b9a4bc7099ff8c`.
First repair head: `e8142ed84338b80b929c729bee17da6451c6aad4`.
Final repair head: `ab5ed833a4bb529cc153f0f2d9c0da98a5d14044`.
Prime focused tests: 15 passed, 0 failed, 0 skipped.

The first review found zero Blockers and two Majors:

1. Operator implementation digests alone did not bind released
   source semantics. The same numeric operation could execute
   after the native source contract drifted.
2. ROLE_LOOKUP collapsed an A03 ALTERNATIVES binding to
   UNSUPPORTED instead of preserving unresolved/UNKNOWN status.

The first repair bound each spec to its semantic release, exact
source reference and contract digest. Native numeric operations
reuse the released `semantics.numeric.calculate/evaluate` source
implementation; independently admitted formal laws require
operator-specific source grants. A role with ALTERNATIVES now
returns UNKNOWN. The second review found a remaining Major:
removing ADD before registry construction could relabel it as
a formal law. The final repair explicitly pins native-owned
operator IDs and fails closed on missing or signature-drifted
source operations, with a pre-construction removal adversary.

The reviewer inspected final immutable `ab5ed83` and confirmed
**EGM PASS, zero remaining Blockers/Majors**. The reviewer did not
claim an independent new test run at this final head; the 15/15
count is prime executed evidence. A07.2 evaluator separation and
A07.3 compositional DAG/cache receipts remain independent leaves.
No A07 parent integration or neural training is claimed.

## A07.2 independent evaluator/source separation review

Initial immutable head:
`2aa6d127e91391830aad238be39160e10e00f053`.
Repair immutable head:
`819a6533ddb4eb8aafce85184e32daa6f19aa3a1`.
Reviewer: fresh-context Goldfish worker-5, read-only.
Prime source/numeric/frame tests: 47 passed, 0 failed,
1 optional real-Atlas skip.

The first review found one Major: a newly registered
native MOD operation could silently redirect the
separately granted formal-law MOD through the native
numeric evaluator without changing the operator's
declared source contract. The repair dispatches native
execution exclusively through the fixed native-owned
operator set already used for source contract binding.
An adversarial test injects MOD into the numeric registry
and traps native calculate; the formal law still returns
5 mod 3 = 2 with no native call.

Independent targeted readback at `819a653` returned
**A07.2 EGM PASS, zero remaining Blockers/Majors**.
The reviewer inspected immutable source and tests, not
an additional executed test run. A07.3 and parent
integration remain open.
