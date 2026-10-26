# Release corpus census

Candidate: `eb3ce818319382bb1946a3a4a23ea585a638ea70`.
Canonical RDF: `7a0a0cd04133be41db69ca3fe1e2f09b4efbc8c965610b75c5ac30bc0954b50e` (130173 triples).

Declared-scope accounting complete: True.
Semantic coverage: **partial**.
Full New Ithkuil coverage: False.

| Domain | Source rows | EMITTED | HELD | REJECTED | UNSUPPORTED | IR_ONLY |
|---|---:|---:|---:|---:|---:|---:|
| atomic | 772 | 272 | 500 | 0 | 0 | 0 |
| lexicon | 18306 | 8818 | 0 | 0 | 0 | 9488 |
| mapping | 552 | 0 | 551 | 1 | 0 | 0 |
| residue | 6062 | 6062 | 0 | 0 | 0 | 0 |
| Total | 25692 | 15152 | 1051 | 1 | 0 | 9488 |

One stable source/IR row, keyed by (domain, table, key). Tables and row identities are disjoint across domains. Semantic-resource counts are not summed.

Unparsed source artifacts:

- `NI-LEXICON-CURRICULUM:CHAPTER:0`
- `NI-LEXICON-SITE`
- `NI-WEB-INDEX`

Source-frontier debt (owner observation units; categories are not additive):

- `DEBT_CONFLICT`: 43
- `DEBT_INSUFFICIENT_SENSE_EVIDENCE`: 8757
- `DEBT_UNSUPPORTED_SHAPE`: 339
- `chapter_0_toc_unparsed`: 1
- `legacy_debt_not_measured`: 2
- `partial_table_overlap`: 3498
- `prose_and_semantic_exhaustiveness_unmeasured`: 14
- `repeated_affix_identity`: 2
- `roots_without_parsed_senses`: 5097
- `roots_without_parsed_senses_in_source_receipt`: 4898
- `unclassified_source_prose`: 5962
- `unsupported_table_shape`: 35

Domain receipt references and exact source-to-domain table counts are in `release-census.json`.
This census grants no curriculum, neural, graph-write, merge or publication authority.
