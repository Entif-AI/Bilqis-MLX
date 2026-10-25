"""Pinned, conservative later-chapter extraction with explicit source-scope debt."""
from __future__ import annotations

from collections import Counter,defaultdict
import csv
import difflib
import hashlib
import json
from pathlib import Path
import re

import fitz

from . import build_lexicon_chapters as legacy

ROOT=legacy.ROOT
PINS=Path(__file__).with_name('lexicon_frontier_pins.json')
VERSION='1.0.4'


def structural_sense_id(form,stem,specification):
    return legacy.stable_id('LEXSENSE',legacy.SOURCE_ID,form,stem,specification)


def _bytes(rows,columns):
    import io
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n')
    writer.writeheader();writer.writerows(rows);return stream.getvalue().encode('utf-8')


def _columns(name):
    with (legacy.DATA/(name+'.csv')).open(encoding='utf-8',newline='') as f:return next(csv.reader(f))


def _json_bytes(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def _page_lines(page):
    """Yield stable, 1-based PyMuPDF text-line loci with their bounding boxes."""
    line_number=0
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            text=' '.join(span['text'] for span in line['spans'])
            for part in text.splitlines() or [text]:
                line_number+=1
                value=legacy.clean(part)
                if value:yield line_number,value,tuple(line['bbox'])


def _overlaps(left,right):
    return left[0]<right[2] and left[2]>right[0] and left[1]<right[3] and left[3]>right[1]


def _stem_segments(value):
    """Return every explicitly numbered stem marker, including empty meanings."""
    note=re.search(r'\s*[—–-]\s*Specification pattern\b',value,re.I)
    if note:value=value[:note.start()]
    matches=list(legacy.STEM_RE.finditer(value));segments=[]
    for index,match in enumerate(matches):
        end=matches[index+1].start() if index+1<len(matches) else len(value)
        meaning=legacy.clean(value[match.end():end].strip(' ;'))
        segments.append(('STEM '+match.group(1),meaning))
    return segments


def _root_form(line):
    match=legacy.ROOT_RE.match(line)
    if match:return match.group(1)
    spaced=re.match(r'^-\s*([^\s-](?:\s*[^\s-])*)\s*-',line)
    return '-'+re.sub(r'\s+','',spaced.group(1))+'-' if spaced else None


def _root_gloss(line):
    match=legacy.ROOT_RE.match(line)
    if match:return legacy.clean(match.group(2))
    spaced=re.match(r'^-\s*([^\s-](?:\s*[^\s-])*)\s*-\s*(.*)$',line)
    return legacy.clean(spaced.group(2)) if spaced else ''


def _prose_sense_candidates(document,chapter_id,root_index,by_form,common):
    """Parse only non-table prose with explicit root, Stem, and Specification scope."""
    accounting=[];candidates=defaultdict(list)
    for page_number,page in enumerate(document,start=1):
        table_boxes=[table.bbox for table in page.find_tables().tables]
        current_root=None;specification=None;marker=None;buffer=[];marker_line=0;buffer_end_line=0

        def flush():
            nonlocal marker,buffer,marker_line,buffer_end_line
            if marker is None:return
            stem=marker;meaning=legacy.clean(' '.join(buffer))
            root=by_form.get(current_root);locus=root_index[(page_number,current_root)]
            source_text=meaning or marker
            fingerprint,count=legacy.source_fingerprint(source_text)
            item={'root_form_raw':current_root,'lexicon_root_id':root['lexicon_root_id'] if root else '',
                  'source_pdf_page':str(page_number),'source_printed_page':legacy.printed_page(page),
                  'source_table_index':'','row':marker_line,'column':0,
                  'source_text_sha256':fingerprint,'source_text_char_count':count,'stem':stem,
                  'source_locus':{'kind':'prose','pdf_page':page_number,'line_start':marker_line,
                                  'line_end':buffer_end_line or marker_line}}
            if root is None or specification not in legacy.SPECIFICATIONS or not meaning:
                item['status']='DEBT_INSUFFICIENT_SENSE_EVIDENCE'
            else:
                item['status']='PARSED';item['specification']=specification
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
            if specification in legacy.SPECIFICATIONS:item['specification']=specification
            accounting.append(item);marker=None;buffer=[];marker_line=0;buffer_end_line=0

        for line_number,line,bbox in _page_lines(page):
            section=legacy.SECTION_RE.match(line)
            if section:
                flush();current_root=None;specification=None;continue
            form=_root_form(line)
            if form:
                flush()
                current_root=form if (page_number,form) in root_index else None
                specification=None;continue
            if any(_overlaps(bbox,table_box) for table_box in table_boxes):continue
            if current_root is None:continue
            if line.upper() in legacy.SPECIFICATIONS:
                flush();specification=line.upper();continue
            stem_match=re.match(r'^(?:(BSC)\s+)?STEM\s*([123])\s*:\s*(.*)$',line,re.I)
            if stem_match:
                flush()
                if stem_match.group(1):specification='BSC'
                marker='STEM '+stem_match.group(2);marker_line=line_number
                if stem_match.group(3):buffer=[stem_match.group(3)];buffer_end_line=line_number
                continue
            if marker is not None:
                if (line.startswith('Associated Affix:') or line.startswith('NOTE:') or
                    line.startswith('The Specification pattern') or re.fullmatch(r'STEM\s*[123]',line,re.I)):
                    flush();continue
                if line:buffer.append(line);buffer_end_line=line_number
        flush()
    return accounting,candidates


def canonical_page_map(document,canonical,pin):
    """Bind pages exactly, except for byte-pinned text-extraction variants."""
    variants=pin.get('canonical_page_text_variants',{})
    page_map=[];observed=[];similarities=[]
    for index,page in enumerate(document):
        local_page=index+1;canonical_page=pin['canonical_page_start']+index
        tracked_text=legacy.clean(page.get_text())
        canonical_text=legacy.clean(canonical[canonical_page-1].get_text())
        if tracked_text!=canonical_text:
            key=str(local_page);expected=variants.get(key)
            tracked_sha=hashlib.sha256(tracked_text.encode('utf-8')).hexdigest()
            canonical_sha=hashlib.sha256(canonical_text.encode('utf-8')).hexdigest()
            if expected!={'tracked_sha256':tracked_sha,'canonical_sha256':canonical_sha}:
                raise ValueError('LEXICON_CANONICAL_PAGE_MISMATCH:'+key)
            observed.append(key)
            similarities.append(difflib.SequenceMatcher(None,tracked_text,canonical_text,autojunk=False).ratio())
        page_map.append(canonical_page)
    if set(observed)!=set(variants):
        raise ValueError('LEXICON_CANONICAL_PAGE_VARIANT_SET_MISMATCH')
    return page_map,observed,min(similarities,default=1.0)


def extract_chapter(chapter_id,canonical_pdf,*,prior_senses=()):
    pins=json.loads(PINS.read_text());pin=pins['chapters'].get(chapter_id)
    if pin is None:raise ValueError('LEXICON_CHAPTER_NOT_PINNED')
    chapter=next(c for c in legacy.AVAILABLE_CHAPTERS if c.chapter==chapter_id)
    path=legacy.PDF_DIR/pin['filename'];canonical_pdf=Path(canonical_pdf)
    if legacy.sha256(path)!=pin['sha256'] or legacy.sha256(canonical_pdf)!=pins['canonical_sha256']:
        raise ValueError('LEXICON_SOURCE_PIN_MISMATCH')
    document=fitz.open(path);canonical=fitz.open(canonical_pdf)
    if len(document)!=pin['page_count']:raise ValueError('LEXICON_CHAPTER_PAGE_COUNT_MISMATCH')
    page_map,page_variants,min_similarity=canonical_page_map(document,canonical,pin)
    manifest=legacy.source_manifest_row()
    common={'source_id':legacy.SOURCE_ID,'source_url':manifest['final_url'],'tracked_pdf_name':chapter.filename,
            'tracked_pdf_sha256':pin['sha256'],'evidence_status':'official_source_observed'}
    roots,_=legacy.page_line_records(document,chapter)
    root_index={}
    section=None
    for page_number,page in enumerate(document,start=1):
        for line_number,line,_ in _page_lines(page):
            heading=legacy.SECTION_RE.match(line)
            if heading:section=heading.group(1) if heading.group(1).startswith(chapter_id+'.') else None
            form=_root_form(line)
            if form and section:
                root_index[(page_number,form)]={'lexicon_section':section,'line':line_number,'source_line':line}
    if chapter_id=='4':
        # Chapter 4 includes spaced-root lines the legacy compact-root scan misses.
        # Keep prior accepted chapter projections unchanged in this leaf issue.
        known_roots={r['root_form_raw'] for r in roots}
        root_debts=[]
        for (page_number,form),locus in sorted(root_index.items()):
            if form in known_roots:continue
            page=document[page_number-1]
            gloss=_root_gloss(locus['source_line'])
            if not gloss:
                source_text=locus['source_line'];fingerprint,count=legacy.source_fingerprint(source_text)
                root_debts.append({'root_form_raw':form,'lexicon_root_id':'',
                                   'source_pdf_page':str(page_number),'source_printed_page':legacy.printed_page(page),
                                   'source_table_index':'','row':0,'column':0,
                                   'status':'DEBT_INSUFFICIENT_SENSE_EVIDENCE',
                                   'source_text_sha256':fingerprint,'source_text_char_count':count,
                                   'source_locus':{'kind':'root','pdf_page':page_number,'line':locus['line'],
                                                   'lexicon_section':locus['lexicon_section']}})
                known_roots.add(form)
                continue
            roots.append({'lexicon_root_id':legacy.stable_id('LEXROOT',legacy.SOURCE_ID,form),
                          'root_form_raw':form,'root_form_normalized':form.strip('-').lower(),
                          'root_gloss':legacy.short_meaning(gloss),
                          'lexicon_chapter':chapter_id,'lexicon_section':locus['lexicon_section'],
                          'section_title':legacy.SECTION_TITLES.get(locus['lexicon_section'],''),
                          'source_pdf_page':str(page_number),'source_printed_page':legacy.printed_page(page)})
            known_roots.add(form)
    else:
        root_debts=[]
    for row in roots:row.update({**common,'canonical_source_sha256':pins['canonical_sha256']})
    by_form={r['root_form_raw']:r for r in roots}
    accounting=root_debts;candidates=defaultdict(list)
    for page_number,page in enumerate(document,start=1):
        for table_number,table in enumerate(page.find_tables().tables,start=1):
            data=table.extract()
            if not data:continue
            match=re.search(r'(-[^\s]{1,14}-)(?:\s|$)',legacy.clean(' '.join(legacy.clean(v) for v in data[0] if v)))
            form=match.group(1) if match else None
            locus=root_index.get((page_number,form))
            root=by_form.get(form)
            if root is None or locus is None:
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
                    'source_locus':{'kind':'table','pdf_page':page_number,'table_index':table_number,'row':0,'column':0},
                })
                continue

            def add_table_observation(row_index,column,source_text,status,*,stem=None,specification=None):
                fingerprint,count=legacy.source_fingerprint(source_text)
                item={'root_form_raw':form,'lexicon_root_id':root['lexicon_root_id'],
                      'source_pdf_page':str(page_number),'source_printed_page':legacy.printed_page(page),
                      'source_table_index':str(table_number),'row':row_index,'column':column,
                      'source_text_sha256':fingerprint,'source_text_char_count':count,'status':status,
                      'source_locus':{'kind':'table','pdf_page':page_number,'table_index':table_number,
                                      'row':row_index,'column':column}}
                if stem:item['stem']=stem
                if specification:item['specification']=specification
                accounting.append(item)
                if status!='PARSED':return
                item['sense_id']=structural_sense_id(form,stem,specification)
                sense={k:'' for k in _columns('lexicon_root_senses')}
                sense.update({**common,'lexicon_sense_id':item['sense_id'],'lexicon_root_id':root['lexicon_root_id'],
                              'root_form_raw':form,'stem':stem,'specification':specification,
                              'sense_summary':legacy.short_meaning(source_text),'source_text_sha256':fingerprint,
                              'source_text_char_count':count,'source_example_excerpt':legacy.example_excerpt(source_text),
                              'lexicon_chapter':chapter_id,'lexicon_section':locus['lexicon_section'],
                              'source_pdf_page':str(page_number),'source_printed_page':legacy.printed_page(page),
                              'source_table_index':str(table_number),'source_locus_kind':'table'})
                candidates[(form,stem,specification)].append((sense,item))

            # Some root-title rows carry additional unqualified Stem statements.
            # Preserve those source observations as debt; do not borrow a neighboring
            # Specification label to complete their identity.
            for col,text in enumerate(data[0][1:],start=1):
                text=legacy.clean(text)
                if not text:continue
                segments=_stem_segments(text)
                if segments:
                    for stem,meaning in segments:
                        add_table_observation(0,col,meaning or text,'DEBT_INSUFFICIENT_SENSE_EVIDENCE',stem=stem)
                else:
                    add_table_observation(0,col,text,'DEBT_UNSUPPORTED_SHAPE')

            headers={}
            for row_index,row in enumerate(data[1:],start=1):
                label=legacy.clean(row[0]).upper() if row else ''
                unqualified=bool(re.match(r'^STEM\s*[123]\s*:',legacy.clean(row[0]) if row else '',re.I))
                if unqualified:
                    for stem,meaning in _stem_segments(legacy.clean(row[0])):
                        add_table_observation(row_index,0,meaning or legacy.clean(row[0]),
                                              'DEBT_INSUFFICIENT_SENSE_EVIDENCE',stem=stem)
                    continue
                compact_stem=re.fullmatch(r'STEM\s*([123])',label,re.I)
                if compact_stem:
                    stem='STEM '+compact_stem.group(1)
                    cells=[(col,legacy.clean(text)) for col,text in enumerate(row[1:],start=1) if legacy.clean(text)]
                    if cells:
                        for col,text in cells:
                            add_table_observation(row_index,col,text,'DEBT_INSUFFICIENT_SENSE_EVIDENCE',stem=stem)
                    else:
                        add_table_observation(row_index,0,legacy.clean(row[0]),
                                              'DEBT_INSUFFICIENT_SENSE_EVIDENCE',stem=stem)
                    continue
                for col,text in enumerate(row[1:],start=1):
                    text=legacy.clean(text)
                    if not text:continue
                    full_header=re.fullmatch(r'STEM\s*([123])',text,re.I)
                    if label not in legacy.SPECIFICATIONS and full_header:
                        headers[col]='STEM '+full_header.group(1);continue
                    segments=_stem_segments(text)
                    if segments:
                        for stem,meaning in segments:
                            status=('PARSED' if label in legacy.SPECIFICATIONS and meaning else
                                    'DEBT_INSUFFICIENT_SENSE_EVIDENCE')
                            add_table_observation(row_index,col,meaning or text,status,stem=stem,
                                                  specification=label if label in legacy.SPECIFICATIONS else None)
                        continue
                    stem=headers.get(col);meaning=text
                    boxes=table.rows[row_index].cells
                    label_box=boxes[0];cell_box=boxes[col]
                    spans=bool(label_box and cell_box and cell_box[3]>label_box[3]+0.5)
                    if label not in legacy.SPECIFICATIONS or not stem or spans:
                        status='DEBT_INSUFFICIENT_SENSE_EVIDENCE'
                    else:
                        status='PARSED'
                    add_table_observation(row_index,col,meaning,status,stem=stem,
                                          specification=label if label in legacy.SPECIFICATIONS else None)
    prose_accounting,prose_candidates=_prose_sense_candidates(document,chapter_id,root_index,by_form,common)
    table_observations={(item['root_form_raw'],item.get('stem'),item['source_text_sha256'])
                        for item in accounting if item.get('stem') and item['source_locus']['kind']=='table'}
    table_parsed={(item['root_form_raw'],item.get('stem'),item.get('specification'),item['source_text_sha256'])
                  for item in accounting if item['status']=='PARSED' and item['source_locus']['kind']=='table'}
    for coordinate,entries in prose_candidates.items():
        for sense,item in entries:
            key=(coordinate[0],coordinate[1],coordinate[2],item['source_text_sha256'])
            if key not in table_parsed and (coordinate[0],coordinate[1],item['source_text_sha256']) not in table_observations:
                candidates[coordinate].append((sense,item))
    accounting.extend(item for item in prose_accounting
                       if (item.get('root_form_raw'),item.get('stem'),item['source_text_sha256']) not in table_observations)
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
            root_locus=root_index[(int(root['source_pdf_page']),root['root_form_raw'])]
            root_text=document[int(root['source_pdf_page'])-1].get_text('text')
            fingerprint,count=legacy.source_fingerprint(root_text)
            accounting.append({'root_form_raw':root['root_form_raw'],'lexicon_root_id':root['lexicon_root_id'],
                               'source_pdf_page':root['source_pdf_page'],'source_printed_page':root['source_printed_page'],
                               'source_table_index':'','row':0,'column':0,'status':'DEBT_INSUFFICIENT_SENSE_EVIDENCE',
                               'source_text_sha256':fingerprint,'source_text_char_count':count,
                               'source_locus':{'kind':'root','pdf_page':int(root['source_pdf_page']),
                                               'line':root_locus['line'],'lexicon_section':root_locus['lexicon_section']}})
    evidence=legacy.extract_root_evidence(document,chapter,by_form)
    for row in evidence:row.update({**common,'canonical_source_sha256':pins['canonical_sha256']})
    for item in accounting:
        if item['status']=='PARSED':continue
        # Root-free structures retain chapter/page/table debt in the ledger.
        # Attaching them to a neighbouring root would manufacture a relation.
        if not item['lexicon_root_id']:continue
        root=by_form[item['root_form_raw']]
        row={k:'' for k in _columns('lexicon_root_evidence')}
        locus=item['source_locus']
        if locus['kind']=='table':locator=f"table={locus['table_index']}; row={locus['row']}; column={locus['column']}"
        elif locus['kind']=='prose':locator=f"prose lines={locus['line_start']}-{locus['line_end']}"
        else:locator=f"root line={locus['line']}; section={locus['lexicon_section']}"
        row.update({**common,'lexicon_evidence_id':legacy.stable_id('LEXEVID',legacy.SOURCE_ID,chapter_id,item['lexicon_root_id'],item['source_pdf_page'],item['source_table_index'],item['row'],item['column'],item['status'],item.get('stem',''),item.get('specification',''),item['source_text_sha256']),
                    'lexicon_root_id':item['lexicon_root_id'],'root_form_raw':item['root_form_raw'],
                    'evidence_kind':item['status'].lower(),
                    'evidence_excerpt':f"{item['status']}; {locator}",
                    'source_text_sha256':item['source_text_sha256'],'source_text_char_count':item['source_text_char_count'],
                    'lexicon_chapter':chapter_id,'lexicon_section':root['lexicon_section'],
                    'source_pdf_page':item['source_pdf_page'],'source_printed_page':item['source_printed_page'],
                    'canonical_source_sha256':pins['canonical_sha256']})
        evidence.append(row)
    roots=sorted(roots,key=lambda r:r['lexicon_root_id']);senses=sorted(senses,key=lambda r:r['lexicon_sense_id']);evidence=sorted(evidence,key=lambda r:r['lexicon_evidence_id'])
    accounting=sorted(accounting,key=lambda r:(r['lexicon_root_id'],int(r['source_pdf_page']),r['source_table_index'],r['row'],r['column']))
    files={name+'.csv':_bytes(rows,_columns(name)) for name,rows in [('lexicon_roots',roots),('lexicon_root_senses',senses),('lexicon_root_evidence',evidence)]}
    parsed_observations=sum(row['status']=='PARSED' for row in accounting)
    unique_coordinates={(row['root_form_raw'],row['stem'],row['specification']) for row in senses}
    receipt={'schema':'bilqis.ithkuil.chapter-extraction/v1','chapter':chapter_id,'parser':{'version':VERSION,'sha256':legacy.sha256(Path(__file__)),'legacy_sha256':legacy.sha256(Path(legacy.__file__)),'pymupdf_version':fitz.VersionBind},
             'source':{**pin,'canonical_sha256':pins['canonical_sha256'],'canonical_pages':page_map,
                       'canonical_page_text_variant_pages':page_variants,'min_text_similarity':min_similarity,
                       'comparison':'normalized-page-text-exact-with-pinned-variants' if page_variants else 'normalized-page-text-exact'},
             'counts':{'roots':len(roots),'senses':len(senses),'unique_sense_coordinates':len(unique_coordinates),
                       'evidence':len(evidence),'roots_without_senses':len(roots)-len(sense_roots),
                       'source_observations':len(accounting),'parsed_sense_observations':parsed_observations},
             'dispositions':dict(sorted(Counter(r['status'] for r in accounting).items())),
             'output_sha256':{name:hashlib.sha256(value).hexdigest() for name,value in files.items()},
             'accounting_sha256':hashlib.sha256(_json_bytes(accounting)).hexdigest()}
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
            'canonical_pdf_page_end':str(source['canonical_pages'][-1]),
            'exact_text_page_count':str(source['page_count']-len(source['canonical_page_text_variant_pages'])),
            'near_exact_text_page_count':str(len(source['canonical_page_text_variant_pages'])),
            'min_text_similarity':str(source['min_text_similarity']),
            'verification_method':'PyMuPDF normalized extracted-text page comparison with exact pinned variant hashes',
            'relation_status':'page_projection_text_verified_with_pinned_variants' if source['canonical_page_text_variant_pages'] else 'page_projection_text_verified',
            'notes':('Exact normalized text comparison except pinned page-text variants '+
                     ','.join(source['canonical_page_text_variant_pages'])+'; no byte-identical derivative claim.')
                    if source['canonical_page_text_variant_pages'] else
                    'Exact normalized text page comparison; no byte-identical derivative claim.'}
    files['sources/lexicon_split_provenance.csv']=_bytes(sorted(by_name.values(),key=lambda r:r['tracked_pdf_name']),fields)
    profile.update({'legacy_chapters':['1','2'],'counts':dict(zip(TABLES,map(len,groups))),
                    'output_sha256':{name:hashlib.sha256(payload).hexdigest() for name,payload in files.items()},
                    'legacy_table_sha256':compatibility,'chapter_receipts':receipts})
    files['sources/lexicon_frontier_manifest.json']=(json.dumps(profile,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    for c,rows in accounting.items():
        files['sources/lexicon_frontier/chapter-'+c+'-accounting.json']=_json_bytes(rows)
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
