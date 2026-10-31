from __future__ import annotations

import re
import signal

_SYSTEM_KIND_CODES = {
    'CHAMPION':'CHAMP',
    'DIAGNOSTIC':'DIAG',
    'TEACH OUTCOME':'TEACH',
    'CAP BEST':'BEST',
    'HISTORY ISSUE':'HIST',
    'CUMULATIVE':'CUM',
    'EXAM SCOPE':'SCOPE',
    'RESTART':'RSTR',
    'DISK':'DISK',
    'LOG':'LOG',
    'STOP':'STOP',
}



def _system_kind(kind,grade):
    code=_SYSTEM_KIND_CODES.get(str(kind),str(kind).replace(' ','')[:5].upper())
    if grade not in (None,'','-'):
        return f'{grade}:{code}'
    return code



def _compact_diagnostic(detail,grade):
    text=str(detail)
    active, *suffixes = text.split(' | ')
    grouped={}
    if active.startswith('active '):
        for item in active.removeprefix('active ').split(', '):
            match=re.fullmatch(r'(S[123]):(.+)',item)
            if match is None:
                continue
            signal,capability=match.groups()
            if capability==grade:
                capability='*'
            elif capability.startswith(str(grade)+'.'):
                capability=capability.split('.',1)[1]
            grouped.setdefault(signal,[]).append(capability)
    parts=[
        f'{signal}[{",".join(grouped[signal])}]'
        for signal in ('S1','S2','S3') if signal in grouped
    ]
    for suffix in suffixes:
        if suffix=='S3 unavailable':
            parts.append('S3 OFF')
        else:
            parts.append(re.sub(r'\bNOT MEASURED\b','NM',suffix))
    return ' '.join(parts) if parts else text



def _compact_cap_best(detail,grade):
    match=re.fullmatch(
        r'Best slots: (.+) at step (\d+) \| NOT grade mastery',
        str(detail))
    if match is None:
        return str(detail)
    slots,step=match.groups()
    compact=[]
    for item in slots.split(', '):
        cap,score=item.rsplit(' ',1)
        if cap.startswith(str(grade)+'.'):
            cap=cap.split('.',1)[1]
        compact.append(f'{cap}={score}')
    return ' '.join(compact)+f' @{step}'



def _compact_system_detail(kind,grade,detail):
    text=str(detail)
    if kind=='DIAGNOSTIC':
        return _compact_diagnostic(text,grade)
    if kind=='TEACH OUTCOME':
        return text.replace('NOT_MEASURED_','NM ').replace('_',' ')
    if kind=='CAP BEST':
        return _compact_cap_best(text,grade)
    if kind=='CHAMPION':
        match=re.fullmatch(r'No title change: (.+) \| step (\d+)',text)
        if match is not None:
            reason,step=match.groups()
            reason=(reason.replace('DENY_EARNING_','DENY ')
                    .replace('_REGRESSION',' REG')
                    .replace('_',' '))
            return f'NO TITLE: {reason} @{step}'
    if kind=='HISTORY ISSUE':
        return text.replace('_',' ')
    if kind=='LOG':
        return text.replace('Invalid telemetry event ignored: ','IGNORED ')
    return text
