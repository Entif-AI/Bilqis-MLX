# C01 explicit amendment formats — readiness plan

Continue #347 on the existing issue branch from Lane C/unified70e37ae2.
The current source matrix has five resolved packets and ten held packets. Two
holds explicitly describe missing parser support despite unambiguous owning
requirements: B05.4 and B11.1. This change normalizes those formats while retaining
all other source, specification, conditional and receipt-granularity holds.

## Exact behavior

Move the existing pure clause grammar into scripts/bamf/workstack_clause_formats.py
with `parse_clause(clause, issue_map) -> (tuple[issue_keys], tuple[PR_numbers]) | None`.
Keep its current linked-list, short-list, through-range and PR-list behavior.
The evidence validator remains responsible for exact matrix equality, full source
retention, identity, receipts and held/resolved selection. Grammar checks syntax
and link identity; the independently reviewed matrix fixes prerequisite meaning.

Add only these two source-backed forms:

1. B05.4: the literal consumes sentence identifies B01 topology/tensor and B04
   execution/cache identity. The producer correction explicitly names linked
   B11.1a#586 as the missing producer and repeats that exact number in the
   implemented-and-independently-reviewed condition. Require both declarations
   and exact link/issue identity. Return B01,B04,B11.1a, with no PR prerequisites.
   B05.1 is a downstream consumer; PR582/584 are disposition context.
2. B11.1: preserve the original seven canonical direct prerequisites and add the
   single linked prerequisite implementation child from its additive amendment.
   Require the same parent to state it must consume that accepted producer with
   the exact child number. Return the original seven followed by B11.1a. Keep
   kind leaf and all full-forward scope. The negative B05.4/final-B13 cycle rule
   adds no blocking edge.

Absent/changed mandatory declarations, foreign link targets, multiple child
amendments or unsupported formats reject. No general prose inference is added.
No source body, issue edge, identity, ancestry hash, source snapshot or obligation
changes. B05.4's clause span expands to its full already-pinned body so both
original and corrective declarations are visible. All body/source hashes stay
unchanged. Update only these two reviewed evidence dispositions to resolved and
unresolved=null in both pinned matrices and canonical entries after code proof.

## Proof and scope

First preserve the current64 tests through the grammar extraction. Add mirrored
format-owner tests using the actual retained bodies and literal expected edge
lists. Both new positive cases fail against the pre-format implementation.
Exercise missing/altered declarations, wrong link target/number and forbidden
cycle/consumer edges. The full validator must then report171 identities, seven
resolved/eight held evidence packets, registry integrity valid, exit1 and order[].
Verify both live owning bodies still match the pinned hashes before promotion.

Obtain targeted independent source/readiness review before implementation and
fresh independent code review before turn-in. Preserve #347's entire objective;
full C01 and the eight remaining source/conditional/receipt normalization contracts
stay open. Independent issue work continues page-local. No self-merge or learner,
optimizer, source-admission, graph or live issue-body mutation is authorized here.
