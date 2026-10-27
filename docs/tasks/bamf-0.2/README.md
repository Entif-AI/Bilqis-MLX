# BAMF-0.2 execution workstack

The owner selected one atlas-native architecture. Read the [architecture contract](../../architecture/BAMF_0_2.md), then execute one ready leaf at a time. The full issue repeats the relevant contracts so a fresh worker can continue without this conversation.

## Parallel start

- Lane A: [Semantics and curricula](https://github.com/Entif-AI/Bilqis-MLX/issues/342), start [A01 #345](https://github.com/Entif-AI/Bilqis-MLX/issues/345). [Launch instructions](EXECUTION_LANE_A.md).
- Lane B: [Neural architecture](https://github.com/Entif-AI/Bilqis-MLX/issues/343), start [B01 #346](https://github.com/Entif-AI/Bilqis-MLX/issues/346). [Launch instructions](EXECUTION_LANE_B.md).
- Lane C: [Training and integration](https://github.com/Entif-AI/Bilqis-MLX/issues/344), start [C01 #347](https://github.com/Entif-AI/Bilqis-MLX/issues/347). [Launch instructions](EXECUTION_LANE_C.md).

The integration owner creates the common baseline and owns shared files. CPU source/fixture work proceeds concurrently. MLX evaluation and neural updates use one serialized M3 Ultra lane. The first durable student gate is [C16](issues/C16.md); full delivery is [C15](issues/C15.md).

## Artifacts

- `workstack.json`: exact issue IDs, dependencies, paths and acceptance prescriptions.
- `waves.json`: dependency-ready sets, not a requirement to serialize independent work.
- `issues/`: complete standalone implementation specifications.
- `ISSUE_BOOK.md`: searchable concatenation of those specifications.
- `../../evidence/bamf/0.2-planning/`: publication/readback and EGM records.

## Turn-in

Keep one writer per lane. Push coherent commits, record exact proof on the issue and lane PR, and add a closing keyword to the PR Development section. Main merge and a durable live student launch remain operator actions. Context is a cache; the issue, committed source and receipts carry continuation.
