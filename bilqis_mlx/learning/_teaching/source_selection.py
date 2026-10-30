"""Pure source-row selection under the teacher's selected lesson policy."""

from bilqis_mlx.errors import ErrorBus, SCHOOL

COMPOSITION_DEPTH_POLICY_THRESHOLD = 3


def _choose_binary_rows(source, count, policy, rng):
    if count == 0:
        return []
    _require_source_rows(source)
    groups = {}
    for row in source:
        groups.setdefault(tuple(row["operand_truths"]), []).append(row)
    if count < len(groups):
        ErrorBus.raise_legacy(SCHOOL.LEARNING.BINARY_PATTERN_CAPACITY)
    chosen = []
    for pattern in sorted(groups):
        options = list(groups[pattern])
        if policy.get("depth", 1) >= COMPOSITION_DEPTH_POLICY_THRESHOLD:
            options.sort(key=lambda row: (-len(row["tokens"]), row["id"]))
            chosen.append(options[0])
        else:
            chosen.append(rng.choice(options))

    remaining = count-len(chosen)
    pools = {gold: [row for row in source if row["gold"] == gold]
             for gold in ("FALSE", "TRUE")}
    if any(not pool for pool in pools.values()):
        ErrorBus.raise_legacy(SCHOOL.LEARNING.BINARY_CLASS_MISSING)
    if policy.get("depth", 1) >= COMPOSITION_DEPTH_POLICY_THRESHOLD:
        for pool in pools.values():
            pool.sort(key=lambda row: (-len(row["tokens"]), row["id"]))
    else:
        for pool in pools.values():
            rng.shuffle(pool)
    used = {row["id"] for row in chosen}
    counts = {gold: sum(row["gold"] == gold for row in chosen)
              for gold in pools}
    while remaining:
        gold = min(pools, key=lambda item: (counts[item], item))
        options = [row for row in pools[gold] if row["id"] not in used]
        if not options:
            options = pools[gold]
        row = options[0] if policy.get("depth", 1) >= COMPOSITION_DEPTH_POLICY_THRESHOLD else rng.choice(options)
        chosen.append(row)
        used.add(row["id"])
        counts[gold] += 1
        remaining -= 1
    rng.shuffle(chosen)
    return chosen


def _choose_typed_rows(source, count, policy, rng):
    if count == 0:
        return []
    _require_source_rows(source)
    groups = {}
    for row in source:
        groups.setdefault(row.get("source_id", row["id"]), []).append(row)
    chunks = list(groups.values())
    if policy.get("depth", 1) >= COMPOSITION_DEPTH_POLICY_THRESHOLD:
        chunks.sort(key=lambda group: -max(len(row["tokens"]) for row in group))
        # Sample certified input-token depth; this does not claim AST depth.
        chunks = chunks[:max(1, (len(chunks)+1)//2)]
    if policy.get("contrast", 0.) >= .5:
        families = {}
        for chunk in chunks:
            key = tuple(sorted(set(row["gold"] for row in chunk)))
            families.setdefault(key, []).append(chunk)
        keys = sorted(families)
        result = []
        while len(result) < count:
            for key in keys:
                result.extend(rng.choice(families[key]))
                if len(result) >= count:
                    break
        return result[:count]
    result = []
    while len(result) < count:
        result.extend(rng.choice(chunks))
    return result[:count]



def _fresh_support_rows(current: list[dict], policy: dict, rng,
                        *, structured_binary: bool,
                        semantic_patterns: list[tuple],
                        present_count: int,
                        max_rows: int) -> tuple[dict, ...]:
    """Keep one source-grounded fresh construction bundle beside replay.

    Exact historical misses are evidence, not a replacement curriculum. Binary
    lessons keep one newly drawn row for every truth pattern. Typed lessons keep
    one complete newly drawn source family (for numeric constructions this is
    the direct answer plus its TRUE/FALSE contrast views).
    """
    if not current or present_count < 1 or max_rows < 1:
        return ()
    if structured_binary:
        if len(semantic_patterns) > max_rows:
            return ()
        count = min(present_count, max_rows, len(semantic_patterns))
        return tuple(_choose_binary_rows(current, count, policy, rng))
    groups = {}
    for row in current:
        groups.setdefault(row.get("source_id", row["id"]), []).append(row)
    chunks = [group for group in groups.values() if len(group) <= max_rows]
    if not chunks:
        return ()
    if policy.get("depth", 1) >= COMPOSITION_DEPTH_POLICY_THRESHOLD:
        chunks.sort(
            key=lambda group: (
                -max(len(row["tokens"]) for row in group),
                str(group[0].get("source_id", group[0]["id"]))))
        chosen = chunks[0]
    else:
        chosen = rng.choice(chunks)
    return tuple(chosen) if len(chosen) <= present_count else ()




def _require_source_rows(source):
    if not source:
        ErrorBus.raise_legacy(SCHOOL.LEARNING.MISSING_SOURCE_ROWS)
