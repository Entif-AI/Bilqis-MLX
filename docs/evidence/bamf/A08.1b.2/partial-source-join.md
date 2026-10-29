# A08.1b.2 partial: A01/A07 formal source/operator join

Parent A08.1b #418; granular child issue pending.
Isolated candidate: `codex/bamf02-a08-formal-lessons-20261029`.
Baseline: A08.1b.1 candidate `024f049`, with A08.1a governed
source-pin repair `f8b90c1`. Independent EGM: **PENDING**.

The new `bilqis.formal-source-operator/v1` and
`bilqis.formal-source-operator-set/v1` records join exactly pinned
A01 formal identities and ABI indices to A07's verified pure operator
specifications, signatures, implementation/source contracts and
operator-grant evidence digests. The public resolver loads the A01
artifact through the SHA-pinned source registry. It never infers a
law from a gloss or substitutes a different operator under an ABI
index. Unknown operators remain explicit `OPERATOR_UNREGISTERED`
debt, without shrinking the source denominator.

The real pinned A01 corpus resolves four source-bound operators:
`BOOL_NOT`, `BOOL_AND`, `COUNT`, `SUCC`. The exact focused
`test_formal_constructive.py` suite passes **5/5**, including real
source readback, wrong-release and forged A07 contract negatives,
unknown-operator debt, and self-attested source-pin rejection.
No new static error-control or module-size findings were introduced.

**This is not completion of A08.1b.2.** The status is deliberately
`SOURCE_BOUND_NOT_EXECUTABLE`, never `ADAPTER_READY` or
`LEARNING_VERIFIED`. The remaining work is to construct source-valid
Boolean/numeric positive/contrast lessons, independently evaluate
typed gold, consume live A13 rights/epochs/visibility, prove
revocation and wrong-arity/type failures, and obtain independent
EGM acceptance. This partial source join grants no source admission,
teacher credit, model/optimizer mutation or live training.
