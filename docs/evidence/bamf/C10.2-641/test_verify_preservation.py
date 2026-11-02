"""Adversaries for the preservation receipt's definition inventory."""
import ast
import unittest

from verify_preservation import definitions, require_preserved


def inventory(*sources):
    return definitions([ast.parse(source) for source in sources], recursive=True)


class PreservationTests(unittest.TestCase):
    def test_nested_names_keep_lexical_identity(self):
        source = 'def first():\n def objective(): return 1\ndef second():\n def objective(): return 2\n'
        before = inventory(source)
        self.assertIn('first.objective', before)
        self.assertIn('second.objective', before)
        require_preserved(before, inventory(source))
        with self.assertRaises(ValueError):
            require_preserved(before, inventory(source.replace('return 2', 'return 3')))

    def test_duplicate_occurrences_cannot_disappear(self):
        source = 'def example(): return 1\n'
        before = inventory(source, source)
        self.assertEqual(sum(before['example'].values()), 2)
        with self.assertRaises(ValueError):
            require_preserved(before, inventory(source))

    def test_decorators_cannot_disappear(self):
        before = inventory('@marker\ndef example(): return 1\n')
        with self.assertRaises(ValueError):
            require_preserved(before, inventory('def example(): return 1\n'))

    def test_repeated_setup_is_explicitly_counted(self):
        source = 'class Suite:\n def setUp(self): pass\n'
        before, after = inventory(source), inventory(source, source)
        require_preserved(before, after)
        self.assertEqual(sum(after['Suite.setUp'].values()), 2)


if __name__ == '__main__':
    unittest.main()
