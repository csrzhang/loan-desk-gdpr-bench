"""Independently test the two source routes for the frozen withdrawal scenario."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class WithdrawalRoutes(unittest.TestCase):
    def test_two_controls_separately_and_together(self):
        original = (ROOT/'projects/base/store.py').read_text().splitlines(keepends=True)
        compound = (ROOT/'projects/v01/store.py').read_text().splitlines(keepends=True)
        # Copy only the two sites of the frozen enqueue-only-consent patch into temporary sources.
        for remove_cancel, remove_reread, count in [(False,False,0),(True,False,0),(False,True,0),(True,True,1)]:
            with self.subTest(remove_cancel=remove_cancel,remove_reread=remove_reread), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                for name in ('app.py','views.py','style.css'):
                    shutil.copyfile(ROOT/'projects/base'/name,project/name)
                code = original.copy()
                if remove_cancel:
                    code[95:98] = compound[95:98]
                if remove_reread:
                    code[136:138] = compound[136:138]
                (project/'store.py').write_text(''.join(code))
                raw = subprocess.check_output([sys.executable,'-B',str(ROOT/'validation/observe.py'),str(project)],timeout=120)
                case = json.loads(raw)['GDPR04']
                self.assertEqual(case['observed']['withdrawn_reports'],count)
                self.assertEqual(case['observed']['control_reports'],1)
                self.assertEqual(case['contract'],'FAIL' if count else 'PASS')
