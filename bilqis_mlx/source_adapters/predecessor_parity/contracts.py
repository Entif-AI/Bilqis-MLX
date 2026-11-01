"""Immutable predecessor source pins and teaching stage contract."""
from types import MappingProxyType
import hashlib
import json

SCHEMA = "bilqis.mlx.predecessor-pedagogy/v2"


PREDECESSOR = MappingProxyType({
    "bilqis_school/small_domain_lessons.py":
        "44c73637ed9bcfb6316446937cdc318d911f6178c07fd929ac6222014c83f6e5",
    "bilqis_school/arithmetic.py":
        "b6477344cac66e0f4311ce798b9d4265a315452447e7643664765de6eaef8f40",
    "bilqis_school/numeric_answer_contract.py":
        "23db30c2ce938681c32dc823265c1bb9b64daecdc5fd41975e032e21d038190d",
    "bilqis_school/lessons.py":
        "22b3b712e48322d68aec1ee525327f64554b8a00b8a1e7c54e416ebd1516a4c7",
    "bilqis_school/spiral_semantic_bridge.py":
        "842789f0e010d7139f283b91993325d276cdda38ccf205d4823be280d794abe9",
    "bilqis_school/spiral_staged_runner.py":
        "e815f46b04b3e8dc94b9521adacf0201b38e782955d2d15c4d95656eb2f9b7dc",
    "bilqis_school/engine.py":
        "6b62f288750bc6d129b349e0333b560f480ede900bf28e3b641299fe696abaa1",
})


STAGE_ORDER = ("NUMERAL_IDENTITY", "DIRECT_ARITHMETIC", "TRUTH_CONTRAST")


REQUIRES = MappingProxyType({
    "NUMERAL_IDENTITY": (),
    "DIRECT_ARITHMETIC": ("NUMERAL_IDENTITY",),
    "TRUTH_CONTRAST": ("NUMERAL_IDENTITY", "DIRECT_ARITHMETIC"),
})


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                    ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
