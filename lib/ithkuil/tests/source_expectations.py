"""Reviewed literal source census shared by tests of the current frontier."""
import json
from pathlib import Path

LEXICON = json.loads(
    (Path(__file__).parent / "fixtures/skos_lexicon_reconciliation_expected.json").read_text()
)
CORE = json.loads(
    (Path(__file__).parent / "fixtures/source_current_core_expected.json").read_text()
)
