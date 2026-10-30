"""Shared temporary repository fixture for SKOS policy owner tests."""
from pathlib import Path


class SkosPolicyFixture:
    def root(self, temporary: str) -> Path:
        root = Path(temporary)
        (root / "lib/ithkuil/src/skos").mkdir(parents=True)
        (root / "lib/ithkuil/_data").mkdir(parents=True)
        (root / "lib/ithkuil/tests/fixtures").mkdir(parents=True)
        (root / "lib/ithkuil/tests/skos/core_identity").mkdir(parents=True)
        (root / "scripts/quality").mkdir(parents=True)
        (root / "skills/ithkuil-ingestion").mkdir(parents=True)
        (root / "lib/ithkuil/src/skos/notation.py").write_text("VALUE = 1\n")
        (root / "lib/ithkuil/tests/skos/core_identity/test_skos_notation.py").write_text(
            "FIXTURE = 'fixtures/notation.json'\n")
        for name in ("canonical", "identity", "shapes"):
            (root / f"lib/ithkuil/tests/skos/core_identity/test_skos_{name}.py").write_text("")
        (root / "lib/ithkuil/tests/fixtures/notation.json").write_text('{"ok": true}\n')
        (root / "lib/ithkuil/_data/source.csv").write_text("id,value\n1,x\n")
        (root / "scripts/run_tests.py").write_text("RUNNER = 1\n")
        (root / "scripts/skos_test_policy.py").write_text("POLICY = 1\n")
        (root / "scripts/quality/skos_test_bundle.py").write_text("BUNDLE = 1\n")
        (root / "scripts/quality/skos_test_selection.py").write_text("SELECTION = 1\n")
        return root
