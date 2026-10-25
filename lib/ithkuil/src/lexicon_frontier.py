"""Pinned, conservative later-chapter extraction with explicit source-scope debt."""
from __future__ import annotations

from collections import Counter,defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

import fitz

from . import build_lexicon_chapters as legacy

ROOT=legacy.ROOT
PINS=Path(__file__).with_name('lexicon_frontier_pins.json')
VERSION='1.0.0'


def structural_sense_id(form,stem,specification):
    return legacy.stable_id('LEXSENSE',legacy.SOURCE_ID,form,stem,specification)


def _bytes(rows,columns):
    import io
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n')
    writer.writeheader();writer.writerows(rows);return stream.getvalue().encode('utf-8')


def _columns(name):
    with (legacy.DATA/(name+'.csv')).open(encoding='utf-8',newline='') as f:return next(csv.reader(f))


def _prose_sense_candidates(document,chapter_id,root_index,by_form,common):
    """Parse only prose senses with explicit root, Stem, and Specification scope."""
    accounting=[];candidates=defaultdict(list)
    for page_number,page in enumerate(document,start=1):
        current_root=None;specification=None;marker=None;buffer=[];marker_line=0

        def flush():
            nonlocal marker,buffer,marker_line
            if marker is None:return
            stem=marker;meaning=legacy.clean(' '.join(buffer))
            root=by_form[current_root];locus=root_index[(page_number,current_root)]
            source_text=meaning or marker
            fingerprint,count=legacy.source_fingerprint(source_text)
            item={'root_form_raw':current_root,'lexicon_root_id':root['lexicon_root_id'],
                  'source_pdf_page':str(page_number),'source_printed_page':legacy.printed_page(page),
                  'source_table_index':'','row':marker_line,'column':0,
                  'source_text_sha256':fingerprint,'source_text_char_count':count}
            if specification not in legacy.SPECIFICATIONS or not meaning:
                item['status']='DEBT_INSUFFICIENT_SENSE_EVIDENCE'
            else:
                item['status']='PARSED';item['stem']=stem;item['specification']=specification
                item['sense_id']=structural_sense_id(current_root,stem,specification)
                sense={k:'' for k in _columns('lexicon_root_senses')}
                sense.update({**common,'lexicon_sense_id':item['sense_id'],'lexicon_root_id':root['lexicon_root_id'],
                              'root_form_raw':current_root,'stem':stem,'specification':specification,
                              'sense_summary':legacy.short_meaning(meaning),'source_text_sha256':fingerprint,
                              'source_text_char_count':count,'source_example_excerpt':legacy.example_excerpt(meaning),
                              'lexicon_chapter':chapter_id,'lexicon_section':locus['lexicon_section'],
                              'source_pdf_page':str(page_number),'source_printed_page':legacy.printed_page(page),
                              'source_table_index':'','source_locus_kind':'prose'})
                candidates[(current_root,stem,specification)].append((sense,item))
            accounting.append(item);marker=None;buffer=[];marker_line=0

        for line_number,raw in enumerate(page.get_text('text').splitlines(),start=1):
            line=legacy.clean(raw)
            section=legacy.SECTION_RE.match(line)
            if section:
                flush();current_root=None;specification=None;continue
            root_match=legacy.ROOT_RE.match(line)
            if root_match:
                flush();form=root_match.group(1)
                current_root=form if (page_number,form) in root_index else None
                specification=None;continue
            if current_root is None:continue
            if line.upper() in legacy.SPECIFICATIONS:
                flush();specification=line.upper();continue
            stem_match=re.match(r'^(?:(BSC)\s+)?STEM\s*([123])\s*:\s*(.*)$',line,re.I)
            if stem_match:
                flush()
                if stem_match.group(1):specification='BSC'
                marker='STEM '+stem_match.group(2);marker_line=line_number
                if stem_match.group(3):buffer=[stem_match.group(3)]
                continue
            if marker is not None:
                if (line.startswith('Associated Affix:') or line.startswith('NOTE:') or
                    line.startswith('The Specification pattern') or re.fullmatch(r'STEM\s*[123]',line,re.I)):
                    flush();continue
                if line:buffer.append(line)
        flush()
    return accounting,candidates


def extract_chapter(chapter_id,canonical_pdf,*,prior_senses=()):
    pins=json.loads(PINS.read_text());pin=pins['chapters'].get(chapter_id)
    if pin is None:raise ValueError('LEXICON_CHAPTER_NOT_PINNED')
    chapter=next(c for c in legacy.AVAILABLE_CHAPTERS if c.chapter==chapter_id)
    path=legacy.PDF_DIR/pin['filename'];canonical_pdf=Path(canonical_pdf)
    if legacy.sha256(path)!=pin['sha256'] or legacy.sha256(canonical_pdf)!=pins['canonical_sha256']:
        raise ValueError('LEXICON_SOURCE_PIN_MISMATCH')
    document=fitz.open(path);canonical=fitz.open(canonical_pdf)
    if len(document)!=pin['page_count']:raise ValueError('LEXICON_CHAPTER_PAGE_COUNT_MISMATCH')
    page_map=[]
    for index,page in enumerate(document):
        canonical_page=pin['canonical_page_start']+index
        if legacy.clean(page.get_text())!=legacy.clean(canonical[canonical_page-1].get_text()):
            raise ValueError('LEXICON_CANONICAL_PAGE_MISMATCH:'+str(index+1))
        page_map.append(canonical_page)
    manifest=legacy.source_manifest_row()
    common={'source_id':legacy.SOURCE_ID,'source_url':manifest['final_url'],'tracked_pdf_name':chapter.filename,
            'tracked_pdf_sha256':pin['sha256'],'evidence_status':'official_source_observed'}
    roots,_=legacy.page_line_records(document,chapter)
    for row in roots:row.update({**common,'canonical_source_sha256':pins['canonical_sha256']})
    root_index={}
    section=None
    for page_number,page in enumerate(document,start=1):
        for line in page.get_text().splitlines():
            line=legacy.clean(line)
            heading=legacy.SECTION_RE.match(line)
            if heading:section=heading.group(1) if heading.group(1).startswith(chapter_id+'.') else None
            root_match=legacy.ROOT_RE.match(line)
            if root_match and section:
                root_index[(page_number,root_match.group(1))]={'lexicon_section':section}
    by_form={r['root_form_raw']:r for r in roots}
    accounting,candidates=_prose_sense_candidates(document,chapter_id,root_index,by_form,common)
    for page_number,page in enumerate(document,start=1):
        for table_number,table in enumerate(page.find_tables().tables,start=1):
            data=table.extract()
            if not data:continue
            match=re.search(r'(-[^\s]{1,14}-)(?:\s|$)',legacy.clean(' '.join(legacy.clean(v) for v in data[0] if v)))
            form=match.group(1) if match else None
            locus=root_index.get((page_number,form))
            root=by_form.get(form)
            unscoped_header=any(legacy.clean(cell) for cell in data[0][1:])
            if root is None or locus is None or unscoped_header:
                text=' '.join(legacy.clean(cell) for row in data for cell in row)
                fingerprint,count=legacy.source_fingerprint(text)
                accounting.append({
                    'root_form_raw':form if root else '',
                    'lexicon_root_id':root['lexicon_root_id'] if root else '',
                    'source_pdf_page':str(page_number),
                    'source_printed_page':legacy.printed_page(page),
                    'source_table_index':str(table_number),'row':0,'column':0,
                    'status':'DEBT_AMBIGUOUS_LOCUS' if root and locus is None else 'DEBT_UNSUPPORTED_SHAPE',
                    'source_text_sha256':fingerprint,'source_text_char_count':count,
                })
                continue
            headers={}
            for row_index,row in enumerate(data[1:],start=1):
                label=legacy.clean(row[0]).upper() if row else ''
                for col,text in enumerate(row[1:],start=1):
                    text=legacy.clean(text)
                    if not text:continue
                    full_header=re.fullmatch(r'STEM\s*([123])',text,re.I)
                    if label not in legacy.SPECIFICATIONS and full_header:
                        headers[col]='STEM '+full_header.group(1);continue
                    item={'root_form_raw':form,'lexicon_root_id':root['lexicon_root_id'],'source_pdf_page':str(page_number),
                          'source_printed_page':legacy.printed_page(page),'source_table_index':str(table_number),
                          'row':row_index,'column':col,'source_text_sha256':legacy.source_fingerprint(text)[0],
                          'source_text_char_count':legacy.source_fingerprint(text)[1]}
                    stem=headers.get(col);meaning=text
                    inline=re.match(r'^STEM\s*([123])\s*:\s*(.+)$',text,re.I)
                    if inline:stem='STEM '+inline.group(1);meaning=inline.group(2)
                    boxes=table.rows[row_index].cells
                    label_box=boxes[0];cell_box=boxes[col]
                    spans=bool(label_box and cell_box and cell_box[3]>label_box[3]+0.5)
                    if label not in legacy.SPECIFICATIONS or not stem or spans:
                        item['status']='DEBT_INSUFFICIENT_SENSE_EVIDENCE'
                    elif len(list(legacy.STEM_RE.finditer(text)))>1:
                        item['status']='DEBT_UNSUPPORTED_SHAPE'
                    else:
                        item['status']='PARSED';item['stem']=stem;item['specification']=label
                        item['sense_id']=structural_sense_id(form,stem,label)
                        meaning_fingerprint,meaning_count=legacy.source_fingerprint(meaning)
                        sense={k:'' for k in _columns('lexicon_root_senses')}
                        sense.update({**common,'lexicon_sense_id':item['sense_id'],'lexicon_root_id':root['lexicon_root_id'],
                                      'root_form_raw':form,'stem':stem,'specification':label,
                                      'sense_summary':legacy.short_meaning(meaning),
                                      'source_text_sha256':meaning_fingerprint,'source_text_char_count':meaning_count,
                                      'source_example_excerpt':legacy.example_excerpt(meaning),'lexicon_chapter':chapter_id,
                                      'lexicon_section':locus['lexicon_section'],'source_pdf_page':str(page_number),
                                      'source_printed_page':legacy.printed_page(page),'source_table_index':str(table_number),'source_locus_kind':'table'})
                        candidates[(form,stem,label)].append((sense,item))
                    accounting.append(item)
    old_coordinates={(r['root_form_raw'],r['stem'],r['specification']):r for r in prior_senses}
    senses=[]
    for coordinate,entries in sorted(candidates.items()):
        prior=old_coordinates.get(coordinate)
        if len({s['source_text_sha256'] for s,_ in entries})>1 or (prior and prior['source_text_sha256']!=entries[0][0]['source_text_sha256']):
            for _,item in entries:item['status']='DEBT_CONFLICT';item.pop('sense_id',None)
        else:
            selected=min(entries,key=lambda entry:not bool(entry[0]['source_table_index']))
            if prior:
                selected[0]['lexicon_sense_id']=prior['lexicon_sense_id']
                for _,item in entries:item['sense_id']=prior['lexicon_sense_id']
            senses.append(selected[0])
    sense_roots={s['lexicon_root_id'] for s in senses}
    for root in roots:
        if root['lexicon_root_id'] not in sense_roots:
            accounting.append({'root_form_raw':root['root_form_raw'],'lexicon_root_id':root['lexicon_root_id'],
                               'source_pdf_page':root['source_pdf_page'],'source_printed_page':root['source_printed_page'],
                               'source_table_index':'','row':0,'column':0,'status':'DEBT_INSUFFICIENT_SENSE_EVIDENCE',
                               'source_text_sha256':legacy.source_fingerprint(document[int(root['source_pdf_page'])-1].get_text())[0],
                               'source_text_char_count':legacy.source_fingerprint(document[int(root['source_pdf_page'])-1].get_text())[1]})
    evidence=legacy.extract_root_evidence(document,chapter,by_form)
    for row in evidence:row.update({**common,'canonical_source_sha256':pins['canonical_sha256']})
    for item in accounting:
        if item['status']=='PARSED':continue
        # Root-free structures retain chapter/page/table debt in the ledger.
        # Attaching them to a neighbouring root would manufacture a relation.
        if not item['lexicon_root_id']:continue
        root=by_form[item['root_form_raw']]
        row={k:'' for k in _columns('lexicon_root_evidence')}
        row.update({**common,'lexicon_evidence_id':legacy.stable_id('LEXEVID',legacy.SOURCE_ID,chapter_id,item['lexicon_root_id'],item['source_pdf_page'],item['source_table_index'],item['row'],item['column'],item['status']),
                    'lexicon_root_id':item['lexicon_root_id'],'root_form_raw':item['root_form_raw'],
                    'evidence_kind':item['status'].lower(),
                    'evidence_excerpt':f"{item['status']}; table={item['source_table_index']}; row={item['row']}; column={item['column']}",
                    'source_text_sha256':item['source_text_sha256'],'source_text_char_count':item['source_text_char_count'],
                    'lexicon_chapter':chapter_id,'lexicon_section':root['lexicon_section'],
                    'source_pdf_page':item['source_pdf_page'],'source_printed_page':item['source_printed_page'],
                    'canonical_source_sha256':pins['canonical_sha256']})
        evidence.append(row)
    roots=sorted(roots,key=lambda r:r['lexicon_root_id']);senses=sorted(senses,key=lambda r:r['lexicon_sense_id']);evidence=sorted(evidence,key=lambda r:r['lexicon_evidence_id'])
    accounting=sorted(accounting,key=lambda r:(r['lexicon_root_id'],int(r['source_pdf_page']),r['source_table_index'],r['row'],r['column']))
    files={name+'.csv':_bytes(rows,_columns(name)) for name,rows in [('lexicon_roots',roots),('lexicon_root_senses',senses),('lexicon_root_evidence',evidence)]}
    receipt={'schema':'bilqis.ithkuil.chapter-extraction/v1','chapter':chapter_id,'parser':{'version':VERSION,'sha256':legacy.sha256(Path(__file__)),'legacy_sha256':legacy.sha256(Path(legacy.__file__)),'pymupdf_version':fitz.VersionBind},
             'source':{**pin,'canonical_sha256':pins['canonical_sha256'],'canonical_pages':page_map,'comparison':'normalized-page-text-exact'},
             'counts':{'roots':len(roots),'senses':len(senses),'evidence':len(evidence),'roots_without_senses':len(roots)-len(sense_roots)},
             'dispositions':dict(sorted(Counter(r['status'] for r in accounting).items())),
             'output_sha256':{name:hashlib.sha256(value).hexdigest() for name,value in files.items()},
             'accounting_sha256':hashlib.sha256(json.dumps(accounting,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    document.close();canonical.close()
    return {'roots':roots,'senses':senses,'evidence':evidence,'accounting':accounting,'receipt':receipt}


TABLES=('lexicon_roots','lexicon_root_senses','lexicon_root_evidence')
PROFILE=legacy.DATA/'sources/lexicon_frontier_manifest.json'


def rebuild_admitted(profile,canonical_pdf=None):
    """Compose source observations without changing legacy Chapter 1-2 rows."""
    canonical_pdf=Path(canonical_pdf or ROOT/'_raw/New_Ithkuil_Lexicon.pdf')
    baseline=legacy.build(legacy.CHAPTERS)
    groups=[list(rows) for rows in baseline]
    receipts={};accounting={}
    for chapter in sorted(profile['admitted_chapters'],key=int):
        result=extract_chapter(chapter,canonical_pdf,prior_senses=groups[1])
        for index,key in enumerate(('roots','senses','evidence')):
            primary=('lexicon_root_id','lexicon_sense_id','lexicon_evidence_id')[index]
            known={r[primary] for r in groups[index]}
            groups[index].extend(r for r in result[key] if r[primary] not in known)
        receipts[chapter]=result['receipt'];accounting[chapter]=result['accounting']
    groups[0].sort(key=lambda r:(int(r['lexicon_chapter']),int(r['source_printed_page'] or 0),r['root_form_raw']))
    groups[1].sort(key=lambda r:(r['lexicon_root_id'],r['specification'],r['stem'],r['lexicon_sense_id']))
    groups[2].sort(key=lambda r:(r['lexicon_root_id'],int(r['source_pdf_page'] or 0),r['evidence_kind'],r['lexicon_evidence_id']))
    return tuple(groups),receipts,accounting


def admit_chapter(chapter,canonical_pdf):
    """Validate a full staged source graph before publishing any canonical rows."""
    import shutil,tempfile
    from . import validate_dataset as validator
    profile=json.loads(PROFILE.read_text()) if PROFILE.exists() else {
        'schema':'bilqis.ithkuil.lexicon-frontier/v1','admitted_chapters':[]}
    profile['admitted_chapters']=sorted(set(profile['admitted_chapters'])|{chapter},key=int)
    groups,receipts,accounting=rebuild_admitted(profile,canonical_pdf)
    baseline=legacy.build(legacy.CHAPTERS)
    compatibility={}
    for table,old,rows in zip(TABLES,baseline,groups):
        observed=[r for r in rows if r['lexicon_chapter'] in {'1','2'}]
        before,after=_bytes(old,_columns(table)),_bytes(observed,_columns(table))
        if before!=after:raise ValueError('LEXICON_EARLIER_CHAPTER_DRIFT:'+table)
        compatibility[table+'.csv']=hashlib.sha256(before).hexdigest()
    files={table+'.csv':_bytes(rows,_columns(table)) for table,rows in zip(TABLES,groups)}
    # Keep the accepted source projection relation distinct from byte derivation.
    with (legacy.DATA/'sources/lexicon_split_provenance.csv').open(newline='',encoding='utf-8') as stream:
        provenance=list(csv.DictReader(stream))
    fields=list(provenance[0]);by_name={r['tracked_pdf_name']:r for r in provenance}
    for c,receipt in receipts.items():
        source=receipt['source'];by_name[source['filename']]={
            'tracked_pdf_name':source['filename'],'tracked_pdf_sha256':source['sha256'],
            'bound_source_id':legacy.SOURCE_ID,'bound_source_sha256':source['canonical_sha256'],
            'page_count':str(source['page_count']),'canonical_pdf_page_start':str(source['canonical_pages'][0]),
            'canonical_pdf_page_end':str(source['canonical_pages'][-1]),'exact_text_page_count':str(source['page_count']),
            'near_exact_text_page_count':'0','min_text_similarity':'1.0',
            'verification_method':'PyMuPDF normalized extracted-text page comparison','relation_status':'page_projection_text_verified',
            'notes':'Exact normalized text page comparison; no byte-identical derivative claim.'}
    files['sources/lexicon_split_provenance.csv']=_bytes(sorted(by_name.values(),key=lambda r:r['tracked_pdf_name']),fields)
    profile.update({'legacy_chapters':['1','2'],'counts':dict(zip(TABLES,map(len,groups))),
                    'output_sha256':{name:hashlib.sha256(payload).hexdigest() for name,payload in files.items()},
                    'legacy_table_sha256':compatibility,'chapter_receipts':receipts})
    files['sources/lexicon_frontier_manifest.json']=(json.dumps(profile,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    for c,rows in accounting.items():
        files['sources/lexicon_frontier/chapter-'+c+'-accounting.json']=(json.dumps(rows,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    local=ROOT/'.local';local.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='source-admission-',dir=local) as directory:
        staged=Path(directory)/'csv';shutil.copytree(legacy.DATA,staged)
        for name,payload in files.items():
            p=staged/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(payload)
        old_data,old_sources=validator.DATA,validator.SOURCES
        try:
            validator.DATA,validator.SOURCES=staged,staged/'sources'
            validator.main()
        finally:validator.DATA,validator.SOURCES=old_data,old_sources
    # Source files are recoverable Git worktree state; profile publishes last.
    for name,payload in sorted(files.items(),key=lambda item:item[0]=='sources/lexicon_frontier_manifest.json'):
        p=legacy.DATA/name;p.parent.mkdir(parents=True,exist_ok=True)
        temporary=p.with_suffix(p.suffix+'.tmp');temporary.write_bytes(payload);temporary.replace(p)
        if p.read_bytes()!=payload:raise ValueError('LEXICON_ADMISSION_READBACK_MISMATCH:'+name)
    return profile
