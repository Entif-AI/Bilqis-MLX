"""Behavioral regression for content-addressed smell verification."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import code_smell_audit as audit


class SmellVerificationReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        self.source = self.root / 'subject.py'
        self.source.write_text('VALUES = []\n', encoding='utf-8')
        self.ledger = self.root / 'receipts.sqlite3'
        self.enterContext(patch.object(audit, 'ROOT', self.root))
        self.enterContext(patch.dict(os.environ, {
            'GITHUB_ACTIONS': 'false',
            'BILQIS_VERIFICATION_LEDGER': str(self.ledger),
            'BILQIS_VERIFICATION_FULL': '0',
        }))

    def scan(self, *args):
        output, log = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(log):
            status = audit.main(['subject.py', '--json', *args])
        self.assertEqual(status, 0)
        return json.loads(output.getvalue()), log.getvalue()

    def test_warm_and_full_results_match_and_reuse_actual_inspection(self):
        cold, cold_log = self.scan()
        warm, warm_log = self.scan()
        full, full_log = self.scan('--full')
        self.assertEqual(cold, {'files': 1, 'findings': [dict(
            path='subject.py', line=1, rule='module-mutable-literal', context='VALUES')]})
        self.assertEqual(cold, warm)
        self.assertEqual(cold, full)
        self.assertIn('hits=0 misses=1', cold_log)
        self.assertIn('hits=1 misses=0', warm_log)
        self.assertIn('hits=0 misses=1', full_log)

    def test_same_size_and_mtime_change_recomputes(self):
        self.scan()
        stat = self.source.stat()
        self.source.write_text('VALUES = ()\n', encoding='utf-8')
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        report, log = self.scan()
        self.assertEqual(report, {'files': 1, 'findings': []})
        self.assertIn('hits=0 misses=1', log)

    def test_corrupt_storage_falls_back_to_real_findings(self):
        self.ledger.write_bytes(b'not a database')
        report, log = self.scan()
        self.assertEqual(len(report['findings']), 1)
        self.assertIn('hits=0 misses=1', log)


if __name__ == '__main__':
    unittest.main()
