"""Reject the actual stale predicates and incomplete proof receipts."""
from pathlib import Path
import tempfile
import unittest

from verify_repaired_recipe import validate_recipe


DOCUMENT = '''```sh
grep -Fx 'TEST_TOTALS total=193 passed=193 failed=0 skipped=0 errors=0' "$proof_root/source-tests.log"
```
```sh
grep -Fx 'INSTALLED_TEST_TOTALS 122 0 0 0' "$proof_root/installed-tests.log"
```'''


class RecipePredicateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'source-tests.log').write_text(
            'TEST_TOTALS total=193 passed=193 failed=0 skipped=0 errors=0\n')
        (self.root / 'installed-tests.log').write_text(
            'INSTALLED_TEST_TOTALS 122 0 0 0\nINSTALLED_WHEEL_MODULE_ORIGINS_OK\n')

    def test_exact_current_predicates_and_receipts_pass(self):
        validate_recipe(DOCUMENT, self.root)

    def test_each_historical_predicate_rejects(self):
        for old in (DOCUMENT.replace('193', '187'), DOCUMENT.replace('122', '116')):
            with self.subTest(document=old), self.assertRaisesRegex(ValueError, 'stale'):
                validate_recipe(old, self.root)

    def test_skips_cannot_masquerade_as_success(self):
        (self.root / 'source-tests.log').write_text(
            'TEST_TOTALS total=193 passed=192 failed=0 skipped=1 errors=0\n')
        with self.assertRaisesRegex(ValueError, 'no-skip success line missing'):
            validate_recipe(DOCUMENT, self.root)

    def test_counts_alone_do_not_prove_installed_origins(self):
        (self.root / 'installed-tests.log').write_text('INSTALLED_TEST_TOTALS 122 0 0 0\n')
        with self.assertRaisesRegex(ValueError, 'module-origin proof missing'):
            validate_recipe(DOCUMENT, self.root)
