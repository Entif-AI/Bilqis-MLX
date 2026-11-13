from pathlib import Path
import unittest


class NoLegacyBavRuntimeNamespaceTests(unittest.TestCase):
    def test_runtime_config_and_scripts_do_not_publish_legacy_bav_identifiers(self):
        root = Path(__file__).resolve().parents[4]
        roots = (root / "bilqis_mlx", root / "configs", root / "scripts")
        violations = []
        for base in roots:
            for path in base.rglob("*"):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                if "delivery" in path.parts or "tests" in path.parts:
                    continue
                if path.suffix not in {".py", ".json", ".toml", ".yaml", ".yml"}:
                    continue
                text = path.read_text(errors="ignore")
                for token in ("BA" + "V_", "BA" + "V.", "ba" + "v_", "ba" + "v."):
                    if token in text:
                        violations.append(f"{path.relative_to(root)}:{token}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
