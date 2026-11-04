"""Shared assessment cohort classification helpers."""

def _generalization_stratum(row):
    """Keep the source draw's answer, operand-pattern and world-shape coverage."""
    return (row["capability"], row.get("answer_kind", "binary"), row["gold"],
            tuple(row.get("operand_truths", ())), row.get("universe_size"))
