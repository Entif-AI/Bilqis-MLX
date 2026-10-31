from __future__ import annotations

import re
from .layout import _clean

def _next_grade(stage):
    phase=stage.get("phase")
    prefix=stage.get("prefix",1)
    pos=stage.get("position",0)
    if phase=="NUMERIC" and isinstance(pos,int):return f"M{pos+1:02d}"
    if phase=="LOGIC" and isinstance(pos,int):return f"G{pos+1:02d}"
    return "-"



def _score_tuple(value):
    if not isinstance(value,str) or "/" not in value:
        return None
    left,right=value.split("/",1)
    try:
        correct,total=int(left),int(right)
    except ValueError:
        return None
    if total<=0 or not 0<=correct<=total:
        return None
    return correct,total



def _nearest_percent(numerator,denominator):
    if type(numerator) is not int or type(denominator) is not int or denominator<=0:
        return None
    return (numerator*200+denominator)//(2*denominator)



def _compact_score_line(start,best,latest):
    first=_score_tuple(start)
    top=_score_tuple(best)
    now=_score_tuple(latest)
    total=(now or first or top)
    if total is None:
        return "-"
    def value(pair):
        return f"{pair[0]:>3}" if pair is not None else "  -"
    return f"{value(first)}/{value(top)}/{value(now)}/{total[1]:>3}"



def _right_grew(start,latest):
    first=_score_tuple(start)
    now=_score_tuple(latest)
    if now is None:
        return "-"
    right=_nearest_percent(now[0],now[1])
    if first is None:
        return f"{right:>3}% [   -]"
    delta=now[0]-first[0]
    grew=_nearest_percent(abs(delta),now[1])
    signed=(f"+{grew}%" if delta>0 else f"-{grew}%" if delta<0 else "0%")
    return f"{right:>3}% [{signed:>4}]"



def _compact_summary_outcome(value):
    text=_clean(value)
    text=re.sub(r"\s*\|\s*SAMPLE\s+\d+/\d+\b","",text)
    text=re.sub(r"\s*\|\s*PASS\s+\d+/\d+\b","",text)
    text=re.sub(r"^(FLASH)\s+SAMPLE\s+\d+/\d+\b",r"\1",text)
    text=re.sub(r"^((?:GENERATED|SEALED) EXAM)\s+\d+/\d+\b",r"\1",text)
    return text.strip() or "-"



def _score_summary(progress,label,width):
    """Prefer all four actual percentages to clipping one at narrow widths."""
    full=progress.summary(label)
    if label=='LATEST*':
        missing=progress.remaining_to_perfect()
        if missing is not None:
            overall=progress.current_means()['ALL']
            full+=(f' | TO100 {missing["total"]}/{getattr(progress,"question_count",616)} wrong '
                   f'(G{missing["G"]} B{missing["B"]} N{missing["N"]}); '
                   f'ALL +{100-overall:.1f}pp')
    if len(full)<=width:return full
    means=progress.start_means() if label=='START' else progress.current_means()
    compact=label+' '+' '.join(
        f'{group}{means[group]:.0f}%' if means[group] is not None else f'{group}-'
        for group in ('G','B','N','ALL'))
    if label=='LATEST*':
        missing=progress.remaining_to_perfect()
        denominator=getattr(progress,'question_count',616)
        if missing is not None and len(compact)+len(f' TO100 {missing["total"]}/{denominator}')<=width:
            compact+=f' TO100 {missing["total"]}/{denominator}'
    return compact



def _difference(before,after,field="correct"):
    if isinstance(before,dict) and isinstance(after,dict):
        if field in before and field in after:
            return f"{before[field]}/{after.get('questions', '?')}->{after[field]}" \
                if field=="correct" else f"{after[field]-before[field]:+.3f}"
    return "-"



def _pp(before,after):
    return f"{100*(after-before):+.1f}" if isinstance(before,(int,float)) and isinstance(
        after,(int,float)) else "-"



def _metric(value,digits=3):
    return f"{value:+.{digits}f}" if isinstance(value,(float,int)) else "-"
