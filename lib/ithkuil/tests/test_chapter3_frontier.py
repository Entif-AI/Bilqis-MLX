import csv
import json
from pathlib import Path
import unittest
import tempfile
import hashlib
import io

from lib.ithkuil.src.lexicon_frontier import extract_chapter,structural_sense_id

ROOT=Path(__file__).resolve().parents[1]
PDF=ROOT/'_raw/New_Ithkuil_Lexicon.pdf'


class ChapterThreeFrontierTests(unittest.TestCase):
    def test_header_scoped_stem_one_and_unqualified_stems_remain_distinct(self):
        result=extract_chapter('3',PDF)
        self.assertEqual(result['receipt']['source']['sha256'],'304e44fe561c741841a42f500e19be77ef044be5e4722077edc96e14299499e0')
        self.assertEqual(result['receipt']['source']['canonical_pages'],list(range(99,116)))
        self.assertEqual(len(result['roots']),122)
        rows=[r for r in result['senses'] if r['root_form_raw']=='-ŠŘ-']
        self.assertEqual({(r['stem'],r['specification']) for r in rows},{('STEM 1','BSC'),('STEM 1','CTE'),('STEM 1','CSV'),('STEM 1','OBJ')})
        self.assertTrue(any(r['root_form_raw']=='-ŠŘ-' and r['status']=='DEBT_INSUFFICIENT_SENSE_EVIDENCE' for r in result['accounting']))
        self.assertTrue(any(r['root_form_raw']=='-ẒB-' and r['status']=='DEBT_INSUFFICIENT_SENSE_EVIDENCE' for r in result['accounting']))
        self.assertTrue(all(r['source_id']=='NI-LEXICON-CURRICULUM' and r['source_pdf_page'] and r['source_printed_page'] for r in result['roots']+result['senses']+result['evidence']))

    def test_explicit_prose_stems_keep_their_stated_bsc_scope(self):
        result=extract_chapter('3',PDF)
        rows=[r for r in result['senses'] if r['root_form_raw']=='-LC-' and r['source_locus_kind']=='prose']
        self.assertEqual(
            {(r['stem'],r['specification']) for r in rows},
            {('STEM 2','BSC'),('STEM 3','BSC')},
        )
        stem_three=next(r for r in rows if r['stem']=='STEM 3')
        self.assertNotIn('CTE',stem_three['sense_summary'])
        stem_one=next(r for r in result['senses'] if r['root_form_raw']=='-LC-' and r['stem']=='STEM 1')
        self.assertEqual(stem_one['source_locus_kind'],'table')
        self.assertEqual(stem_one['sense_summary'],'(to be) a marked/indicated pathway/trail/course')

    def test_repeat_extraction_and_gloss_independent_identity(self):
        first=extract_chapter('3',PDF);second=extract_chapter('3',PDF)
        self.assertEqual(first,second)
        row=first['senses'][0]
        self.assertEqual(row['lexicon_sense_id'],structural_sense_id(row['root_form_raw'],row['stem'],row['specification']))
        self.assertEqual(structural_sense_id('-ŠŘ-','STEM 1','BSC'),'LEXSENSE-d4ff4dd85bf11e')

    def test_unpinned_source_fails_without_mutating_canonical_tables(self):
        paths=[ROOT/'_data/csv'/name for name in ('lexicon_roots.csv','lexicon_root_senses.csv','lexicon_root_evidence.csv')]
        before=[p.read_bytes() for p in paths]
        with tempfile.TemporaryDirectory() as d:
            wrong=Path(d)/'wrong-source.bin';wrong.write_bytes(b'not the pinned source')
            with self.assertRaisesRegex(ValueError,'LEXICON_SOURCE_PIN_MISMATCH'):extract_chapter('3',wrong)
        self.assertEqual(before,[p.read_bytes() for p in paths])

    def test_legacy_rows_match_literal_pre_frontier_byte_hashes(self):
        expected={'lexicon_roots.csv':'7cdb5df8266c7c8b815392cf3333fc5e3d05876b1c79277494c925e24559e0cc',
                  'lexicon_root_senses.csv':'0e9cfefe9e1c4e25901f8b70af5d180290419804f658502bd6f38c862b1898a0',
                  'lexicon_root_evidence.csv':'fb205c21d51764706a22682e9d991e2c257e0cf2090082dcf31229eb3d4d83f7'}
        for name,digest in expected.items():
            with (ROOT/'_data/csv'/name).open(encoding='utf-8',newline='') as f:
                reader=csv.DictReader(f);columns=reader.fieldnames;rows=[r for r in reader if r['lexicon_chapter'] in {'1','2'}]
            stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n');writer.writeheader();writer.writerows(rows)
            self.assertEqual(hashlib.sha256(stream.getvalue().encode()).hexdigest(),digest)

    def test_source_shape_golden_counts_and_full_table_bytes(self):
        expected=json.loads((ROOT/'tests/fixtures/chapter3_extraction_expected.json').read_text())
        result=extract_chapter('3',PDF)
        self.assertEqual({key:result['receipt'][key] for key in expected},expected)
        emitted={r['lexicon_sense_id'] for r in result['senses']}
        accounted={r['sense_id'] for r in result['accounting'] if r['status']=='PARSED'}
        self.assertEqual(emitted,accounted)
        self.assertEqual(len(emitted),expected['counts']['senses'])
        self.assertEqual(len({r['lexicon_evidence_id'] for r in result['evidence']}),expected['counts']['evidence'])

    def test_conflicting_prior_coordinate_remains_debt_without_new_sense(self):
        first=extract_chapter('3',PDF)
        target=next(r for r in first['senses'] if r['root_form_raw']=='-ŠŘ-' and r['specification']=='BSC')
        prior={**target,'source_text_sha256':'0'*64}
        result=extract_chapter('3',PDF,prior_senses=[prior])
        self.assertNotIn(target['lexicon_sense_id'],{r['lexicon_sense_id'] for r in result['senses']})
        conflict=[r for r in result['accounting'] if r['root_form_raw']=='-ŠŘ-' and r['status']=='DEBT_CONFLICT']
        self.assertEqual(len(conflict),1)
        self.assertNotIn('sense_id',conflict[0])

    def test_unrooted_affix_table_is_source_debt_and_never_borrowed_root(self):
        result=extract_chapter('3',PDF)
        rows=[r for r in result['accounting'] if r['source_pdf_page']=='5' and r['source_table_index']=='2']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'DEBT_UNSUPPORTED_SHAPE')
        self.assertEqual(rows[0]['lexicon_root_id'],'')
        self.assertFalse(any(r['source_pdf_page']=='5' and r['source_table_index']=='2' for r in result['senses']))
