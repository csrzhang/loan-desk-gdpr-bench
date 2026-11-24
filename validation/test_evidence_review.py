"""Regression checks for evidence localization. Run with unittest discovery."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence import screen, source_lines


class EvidenceScreenTests(unittest.TestCase):
    def setUp(self):
        self.src = source_lines(ROOT/'projects/v01')
        rows = json.loads((ROOT/'reference/v01/audit.json').read_text())['records']
        self.row = next(row for row in rows if row['obligation_id'] == 'GDPR10')

    def anchor(self, path, a, b, claim='localized source'):
        return dict(path=path, start_line=a, end_line=b,
                    quote='\n'.join(self.src[path][a-1:b]), supports=claim)

    def assess(self, anchors, **changes):
        pred = dict(case_id=self.row['case_id'], verdict=self.row['verdict'], evidence=anchors,
                    explanation='The projection loses the term on the identified output.')
        pred.update(changes)
        return screen(self.row, pred, self.src)

    def test_different_receiving_endpoint_and_split_ranges(self):
        result = self.assess([self.anchor('store.py',114,115),self.anchor('store.py',116,116),
                              self.anchor('app.py',104,109)])
        self.assertEqual(result['localized_routes'],['borrower-download'])
        self.assertEqual(result['registered_line_fraction'],1)
        self.assertFalse(result['citation_errors'])

    def test_wide_or_repeated_citation_does_not_raise_coverage(self):
        clean = self.row['evidence']
        other = self.anchor('app.py',60,70)
        result = self.assess(clean+[other,clean[0]])
        self.assertEqual(result['localized_routes'],self.assess(clean)['localized_routes'])
        self.assertEqual(result['valid_lines_outside_registered_routes'],11)
        self.assertEqual(result['overlapping_valid_lines'],3)
        self.assertLess(result['registered_line_fraction'],1)
        wide = self.assess([self.anchor('store.py',1,len(self.src['store.py']))])
        self.assertTrue(wide['localized_routes'])
        self.assertGreater(wide['valid_lines_beyond_shortest_completed_route'],190)

    def test_missed_outlet_or_novel_citation_requires_review(self):
        helper_only = self.assess([self.row['evidence'][0]])
        self.assertTrue(helper_only['verdict_correct'])
        self.assertEqual(helper_only['localized_routes'],[])
        self.assertEqual(helper_only['review_status'],'REVIEW_FOR_ALTERNATIVE_OR_MISSING_FACTS')

    def test_wrong_or_out_of_snapshot_quotes_get_no_credit(self):
        good = self.row['evidence'][0]
        result = self.assess([dict(good, quote='invented'),dict(good,path='../reference/audit.json')])
        self.assertEqual(len(result['citation_errors']),2)
        self.assertEqual(result['valid_unique_lines'],0)
        self.assertEqual(result['review_status'],'INVALID_CITATION')

    def test_wrong_reason_or_verdict_never_auto_passes(self):
        result = self.assess(self.row['evidence'],verdict='SUPPORTED',explanation='All fields are present.')
        self.assertFalse(result['verdict_correct'])
        self.assertTrue(result['localized_routes'])
        self.assertEqual(result['review_status'],'CHECK_CLAIMS_AND_EXPLANATION')

if __name__ == '__main__':
    unittest.main()
