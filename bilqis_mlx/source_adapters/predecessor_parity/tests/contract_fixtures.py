"""Declared contract fixtures; no historical-source or learning witness."""


def contract_plan():
    pairs = {name: [] for name in ("train", "development", "sealed")}
    for partition, indices in (("train", range(12)), ("development", range(12, 16)),
                               ("sealed", range(16, 20))):
        for index in indices:
            value = index % 4
            source_id = f"fixture:source:{index}"
            rows = [{"id": f"fixture:{index}:{view}", "source_id": source_id,
                     "answer_kind": kind, "gold": gold}
                    for view, kind, gold in (("number", "numeric_0_3", str(value)),
                                             ("positive", "evidence", "TRUE"),
                                             ("negative", "evidence", "FALSE"))]
            rows[0]["native_output"] = {"identity": f"school.number.{value}", "token_id": value}
            pairs[partition].append({"source_id": source_id, "value": value, "rows": rows,
                                     "source": ["ADD", 1, 2] if index == 3 else ["fixture", index]})
    units = [{"id": f"fixture:unit:{value}"} for value in range(4)]
    direct = [pair["rows"][0] for pair in pairs["train"]]
    truth = [row for pair in pairs["train"] for row in pair["rows"][1:]]
    return {
        "schema": "bilqis.mlx.predecessor-pedagogy/v2", "source_sha256": "1" * 64,
        "graph_sha256": "2" * 64, "pairs": pairs,
        "heads": {"semantic_token": {"values": ["school.number.0", "school.number.1",
                                                   "school.number.2", "school.number.3"]},
                  "numeric_0_3": {"values": ["0", "1", "2", "3"], "token_ids": [0, 1, 2, 3]}},
        "stages": {
            "NUMERAL_IDENTITY": {"requires": [], "train": units, "replay": units},
            "DIRECT_ARITHMETIC": {"requires": ["NUMERAL_IDENTITY"], "train": direct, "replay": direct[:4]},
            "TRUTH_CONTRAST": {"requires": ["NUMERAL_IDENTITY", "DIRECT_ARITHMETIC"],
                               "train": truth, "replay": truth[:8]}},
        "sealed_exam_policy": "RESERVED_NOT_USED_FOR_SELECTION",
        "training_authorized": False, "qualification_authorized": False,
    }
