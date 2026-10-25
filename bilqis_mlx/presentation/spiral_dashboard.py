"""Read-only, top-style operator display for staged School50 training.

The dashboard is deliberately OUTSIDE the model's hashed training recipe.
It renders typed diagnostic records in bounded category buffers. A terminal
redraw never writes a checkpoint, modifies a gate or discards the raw text log.
"""
from __future__ import annotations

from ..compatibility.identities import is_historical_capability

import argparse
from collections import deque
from contextlib import redirect_stdout
from dataclasses import dataclass
from fractions import Fraction
import re
from pathlib import Path
from bilqis_mlx.state_dag import read_current, read_current_fields
from .operator_status import (
    NOTICE_TTL_SECONDS,
    active_notice as _active_notice,
    add_notice as _add_notice,
    cell as _cell,
    clean as _clean,
    header_table as _header_table,
    human_duration as _human_duration,
    normalize_number_semantics as _normalize_number_semantics,
    number_semantics_from_profile as _number_semantics_from_profile,
    number_semantics_text as _number_semantics_text,
    right_header as _right_header,
    school_phase_notice as _school_phase_notice,
    score_summary as _score_summary,
)
import shutil
import signal
import sys
import time

@dataclass(frozen=True)
class Column:
    name: str
    width: int
    key: str
    optional: bool = False
    right: bool = False


TABLES = (
    ("CANDIDATES", (
        Column("GRADE", 5, "grade"), Column("TRY", 4, "attempt", right=True),
        Column("STRATEGY", 9, "strategy", optional=True),
        Column("METHOD", 11, "method", optional=True),
        Column("NUM", 9, "number"), Column("BRIDGE", 9, "bridge"),
        Column("BRG2", 9, "confirm", optional=True),
        Column("OLDpp", 7, "old", right=True),
        Column("REWARD", 8, "reward", right=True),
        Column("DECISION / REASON", 39, "decision"))),
    ("SENTINEL & RETENTION", (
        Column("GRADE", 5, "grade"), Column("TRY", 4, "attempt", right=True),
        Column("PROBEpp", 8, "probe", right=True),
        Column("WORSTpp", 8, "worst", right=True),
        Column("SENTpp", 8, "sent", right=True),
        Column("CEd", 9, "ce", right=True),
        Column("P(C)d", 9, "prob", right=True),
        Column("MARGd", 9, "margin", right=True))),
    ("SOUP & TEACHER", (
        Column("GRADE", 5, "grade"), Column("TRY", 4, "attempt", right=True),
        Column("SOUP_KL", 8, "soup", right=True),
        Column("COVER", 8, "cover", right=True),
        Column("SUP_CE", 8, "sup", right=True),
        Column("PAR_KL", 8, "parent", right=True),
        Column("CREDIT", 9, "credit", right=True),
        Column("BRG_CE", 9, "bridge_ce", right=True))),
    ("BRIDGE FAMILIES", (
        Column("GRADE", 5, "grade"), Column("TRY", 4, "attempt", right=True),
        Column("FAMILY", 18, "family"),
        Column("CORRECT BEFORE", 16, "before",right=True),
        Column("CORRECT AFTER", 16, "after",right=True),
        Column("GAIN", 7, "gain",right=True))),
    ("GRADES & MASTERY", (
        Column("VISIT", 6, "visit", right=True),
        Column("GRADE", 5, "grade"),
        Column("STEP", 7, "step", right=True),
        Column("ELIG", 5, "eligible", right=True),
        Column("PICK", 5, "selected", right=True),
        Column("PREFIX", 6, "prefix", right=True),
        Column("OUTCOME", 29, "outcome"),
        Column("RIGHT%", 6, "right_pct", right=True))),
    ("SYSTEM & QUALIFICATION", (
        Column("TYPE", 14, "kind"),
        Column("GRADE", 5, "grade", optional=True),
        Column("DETAILS", 55, "detail"))),
)

# Full details need about 276 columns. Below that width, the wide view
# preserves three panes but sheds optional metrics; ordinary terminals retain
# the existing vertical presentation. This module is not part of model recipe.
WIDE_MIN_WIDTH = 210
WIDE_MIN_HEIGHT = 12
WIDE_SEP = " | "
WIDE_PANES = (
    ("CANDIDATES",),
    ("SENTINEL & RETENTION", "SOUP & TEACHER", "SYSTEM & QUALIFICATION"),
    ("BRIDGE FAMILIES", "GRADES & MASTERY"),
)
WIDE_ROW_FRACTIONS = {
    # At 36 terminal rows these yield the requested 10/9/4 and 4/8 sections.
    "SENTINEL & RETENTION": .28,
    "SOUP & TEACHER": .25,
    "SYSTEM & QUALIFICATION": .11,
    "BRIDGE FAMILIES": .11,
    "GRADES & MASTERY": .22,
}


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


def _step_exam(step,attempt):
    return f"{_clean(step)}/{_clean(attempt)}"


def _compact_summary_outcome(value):
    text=_clean(value)
    text=re.sub(r"\s*\|\s*SAMPLE\s+\d+/\d+\b","",text)
    text=re.sub(r"\s*\|\s*PASS\s+\d+/\d+\b","",text)
    text=re.sub(r"^(FLASH)\s+SAMPLE\s+\d+/\d+\b",r"\1",text)
    text=re.sub(r"^((?:GENERATED|SEALED) EXAM)\s+\d+/\d+\b",r"\1",text)
    return text.strip() or "-"


def _columns(specs, width):
    """Choose and shrink columns without wrapping or erasing core semantics."""
    chosen = [s for s in specs if not s.optional]
    for item in specs:
        if item.optional and (sum(s.width for s in chosen) + len(chosen) + item.width <= width):
            chosen.append(item)
    chosen = [s for s in specs if s in chosen]
    # Narrow windows discard low-priority metrics before clipping the decision.
    while (sum(s.width for s in chosen) + len(chosen) - 1 > width and
           len(chosen) > 2):
        drop = next((c for c in reversed(chosen) if c.optional), None)
        if drop is None:
            drop = next((c for c in reversed(chosen) if c.key not in
                         ("grade", "decision", "outcome", "detail",
                          "right_pct", "subject", "step_exam",
                          "score_line", "right_grew", "result")),None)
        if drop is None:break
        chosen.remove(drop)
    if sum(s.width for s in chosen) + len(chosen) - 1 > width:
        overflow = sum(s.width for s in chosen) + len(chosen) - 1 - width
        biggest = max(chosen, key=lambda c: c.width)
        chosen = [Column(c.name,max(4,c.width-overflow),c.key,c.optional,c.right)
                  if c is biggest else c for c in chosen]
    return chosen


def _table_line(row, columns):
    return " ".join(_cell(row.get(column.key,"-"),column.width,
                          right=column.right) for column in columns).rstrip()


def _section_heading(name,label):
    return label if name=="GRADES & MASTERY" else f"{name}   [{label}]"


def _pane_widths(width):
    """Share real terminal columns without virtual wrapping or lost space."""
    free = width - len(WIDE_SEP) * (len(WIDE_PANES)-1)
    if free < 270:
        # The compact letter-school tables make a 210-column window viable:
        # candidate evidence stays broad, the middle pane keeps its live core,
        # and mastery receives enough room for a meaningful outcome label.
        gain=max(0,free-204)
        left=86+gain*33//66
        middle=54+gain*22//66
    else:
        gain=free-270
        left=119+gain//2
        middle=76+gain//4
    return left,middle,free-left-middle


def _wide_columns(specs,width):
    """Give extra space to the text field rather than truncating its meaning."""
    columns=_columns(specs,width)
    unused=width-(sum(c.width for c in columns)+len(columns)-1)
    if unused<=0:return columns
    target=next((c.key for c in columns if c.key in
                 ("decision","outcome","detail","family")),None)
    if target is None:return columns
    return [Column(c.name,c.width+unused if c.key==target else c.width,
                   c.key,c.optional,c.right) for c in columns]


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


def _soup(record):
    values=record.get("loss_last") or {}
    allocation=record.get("allocation") or {}
    total=sum(x for x in allocation.values() if type(x) is int)
    correct=values.get("trusted_soup_rows")
    coverage=(f"{100*correct/total:.1f}%" if total and isinstance(correct,int)
              else "-")
    return values,coverage


def _candidate_rows(record):
    grade=record.get("grade","?")
    attempts=record.get("attempt","?")
    numeric_before=record.get("numeric_before")
    numeric_after=record.get("numeric_after")
    bridge_before=record.get("bridge_before")
    bridge_after=record.get("bridge_after")
    bridge_confirm_before=record.get("bridge_confirm_before")
    bridge_confirm_after=record.get("bridge_confirm_after")
    old_before=record.get("old_before") or {}
    old_after=record.get("old_after") or {}
    old_change=_pp(sum(old_before.values())/len(old_before) if old_before else None,
                   sum(old_after.values())/len(old_after) if old_after else None)
    number=_difference(numeric_before,numeric_after)
    if is_historical_capability(grade) and grade in old_before:
        number=f"{100*old_before[grade]:.0f}>{100*old_after.get(grade,0):.0f}%"
    decision=record.get("decision","?")
    reason=record.get("reason","?")
    core={"grade":grade,"attempt":attempts,"strategy":record.get("policy_id","-")[:9],
          "method":record.get("instruction_method") or "-",
          "number":number,"bridge":_difference(bridge_before,bridge_after),
          "confirm":_difference(bridge_confirm_before,bridge_confirm_after),
          "old":old_change,"reward":_metric(record.get("reward")),
          "decision":f"{decision} {reason}"}
    sentinel_before=record.get("sentinel_before") or {}
    sentinel_after=record.get("sentinel_after") or {}
    worst=min((old_after[k]-v for k,v in old_before.items()),default=None)
    retention={"grade":grade,"attempt":attempts,
               "probe":_pp(old_before.get(grade),old_after.get(grade)),
               "worst":f"{100*worst:+.1f}" if worst is not None else "-",
               "sent":_pp(sentinel_before.get("accuracy"),sentinel_after.get("accuracy")),
               "ce":_metric_delta(sentinel_before,sentinel_after,"cross_entropy"),
               "prob":_metric_delta(sentinel_before,sentinel_after,"correct_probability"),
               "margin":_metric_delta(sentinel_before,sentinel_after,"margin")}
    soup,coverage=_soup(record)
    teaching={"grade":grade,"attempt":attempts,"soup":_metric(soup.get("soup_kl")),
              "cover":coverage,"sup":_metric(soup.get("supervised")),
              "parent":_metric(soup.get("parent_kl")),
              "credit":_metric(record.get("teacher_credit")),
              "bridge_ce":_metric_delta(bridge_before or {},bridge_after or {},"ce")}
    return core,retention,teaching


def _metric_delta(before,after,key):
    left,right=before.get(key),after.get(key)
    return _metric(right-left) if isinstance(left,(int,float)) and isinstance(
        right,(int,float)) else "-"


class Dashboard:
    """Bounded category buffers; render depends only on input records and size."""
    def __init__(self,*,stream=None,clock=None,max_records=512,redraw=True,
                 title="BILQIS / SCHOOL50 V5",show_all_panels=False,
                 tables=TABLES,compact_header=False):
        self.stream=stream if stream is not None else sys.stdout
        self.clock=clock if clock is not None else time.monotonic
        self.started=self.clock()
        self.tables=tables
        self.rows={name:deque(maxlen=max_records) for name,_ in self.tables}
        # Some dashboards fold this evidence into another rendered section.
        # Preserve the bounded read-only source buffer even when it has no
        # standalone table.
        self.rows.setdefault("BRIDGE FAMILIES",deque(maxlen=max_records))
        self.state={}
        self.mode="LIVE"
        self.log_hint=""
        self.run_name=""
        self.time_budget_seconds=None
        self.title=title
        self.compact_header=compact_header
        self.show_all_panels=show_all_panels
        self.redraw_enabled=redraw
        self.dirty=False
        self.progress=None
        self._progress_source=None
        self.grade_program=None
        self.bridge_families=None
        self.champion_line=None
        self._champion_rows=[]
        self._champion_source=None
        self._champion_start_step=None
        self._champion_mtime_ns=None
        self.current_course={}
        self.current_graduation_line=None
        self.operator_lines=[]
        self.number_semantics=()
        self.replaying_journal=False
        self._notifications=deque(maxlen=8)
        self._rate_step=None
        self._rate_time=None
        self._steps_per_min=None

    def set_number_semantics(self, values, *, notify=False):
        """Project the exact active numeric answer values into operator UI state."""
        normalized=_normalize_number_semantics(values)
        if normalized==self.number_semantics:
            return False
        self.number_semantics=normalized
        if notify and normalized:
            self.notify(
                "INT ROOTS NOW " + self._number_semantics_text(),
                key="number-semantics:" + ",".join(normalized))
        return True

    def set_numeric_profile(self, profile_id, *, notify=False):
        """Read the bounded numeric domain encoded in a factory profile id."""
        values=_number_semantics_from_profile(profile_id)
        return self.set_number_semantics(values,notify=notify) if values else False

    def notify(self, message, *, key=None, ttl_seconds=NOTICE_TTL_SECONDS):
        """Show one bounded, read-only operator notice without replaying old news."""
        if self.replaying_journal:
            return
        _add_notice(
            self._notifications,self.clock(),message,key=key,
            ttl_seconds=ttl_seconds)
        self.dirty=True

    def notify_school_phase(self, grade, phase):
        """Translate qualification states into deliberately obvious milestones."""
        message=_school_phase_notice(grade,phase)
        if message:
            self.notify(message,key=f"school-phase:{grade}:{phase}")

    def _active_notification(self):
        return _active_notice(self._notifications,self.clock())

    def _number_semantics_text(self):
        return f'{self.number_semantics[0]}...{self.number_semantics[-1]}' if len(self.number_semantics)>1 else _number_semantics_text(self.number_semantics)

    def _refresh_champions(self):
        """Read canonical champion inventory if a grade checkpoint changed."""
        source=self._champion_source
        if source is None:return
        try:
            stamp=source.stat().st_mtime_ns
            if stamp==self._champion_mtime_ns:return
            state=read_current_fields(source.parent, ('mentor_epoch',))
            epoch=state.get('mentor_epoch')
            if isinstance(epoch,dict) and isinstance(epoch.get('active_roles'),dict):
                grouped={}
                for capability,role in epoch['active_roles'].items():
                    if not isinstance(role,dict):
                        continue
                    correct,total=role.get('correct'),role.get('total')
                    checkpoint=role.get('checkpoint') or {}
                    if (not isinstance(capability,str) or '.' not in capability or
                            type(correct) is not int or type(total) is not int or
                            total<=0 or not 0<=correct<=total or
                            not isinstance(checkpoint,dict)):
                        continue
                    grade=capability.split('.',1)[0]
                    grouped.setdefault(grade,[]).append({
                        'row_type':'champion',
                        'grade':grade,
                        'capability':capability,
                        'step':'-',
                        'start':'-',
                        'latest':'-',
                        'best':f'{correct}/{total}',
                        'to100':'-',
                        'right_pct':'-',
                        'outcome':'CHAMP',
                        'checkpoint':str(checkpoint.get('sha256',''))[:10],
                        'title_step':checkpoint.get('optimizer_step','-'),
                        'breadth':role.get('breadth','-'),
                        '_score':Fraction(correct,total),
                        '_breadth':role.get('breadth',0)
                            if type(role.get('breadth')) is int else 0,
                    })
                rows=[]
                for grade in sorted(grouped):
                    ranked=sorted(grouped[grade],key=lambda row:row['capability'])
                    ranked=sorted(
                        ranked,
                        key=lambda row:(row['_score'],row['_breadth'],
                                        row['title_step']
                                        if type(row['title_step']) is int else -1),
                        reverse=True)
                    for row in ranked:
                        row.pop('_score',None)
                        row.pop('_breadth',None)
                        rows.append(row)
                self._champion_rows=rows
                self.champion_line=None
                self._champion_mtime_ns=stamp
                return
            state=read_current(source.parent)
            from bilqis_mlx import school50_champions
            if state.get('mode')=='--triplets':
                self.champion_line=(
                    'CHAMPIONS inherited frozen v15 teacher | '
                    f'complete FP32+AdamW candidate archives '
                    f'{len(state.get("capability_candidate_archives",[]))} | '
                    f'teacher-only soup reviews {len(state.get("soup_history",[]))}')
                self.current_course={}
                screen=state.get('golden_screen') or {}
                if state.get('phase')=='GOLDEN_FROZEN' and state.get('golden'):
                    self.current_graduation_line=(
                        f'SAME-STEP CURRENT EXAM @ {state["optimizer_step"]}: '
                        'ALL CURRENT 100%; GOLDEN FROZEN')
                elif screen.get('checkpoint_sha256')==state.get('checkpoint_sha256'):
                    failed=screen.get('first_failed') or {}
                    self.current_graduation_line=(
                        f'SAME-STEP GOLDEN GATE @ {state["optimizer_step"]}: '
                        f'{failed.get("key","-")} {failed.get("correct","-")}/'
                        f'{failed.get("total","-")}; NOT GOLDEN')
                else:
                    self.current_graduation_line=(
                        f'SAME-STEP GOLDEN GATE @ {state.get("optimizer_step","-")}: '
                        'NOT ASSESSED; NOT GOLDEN')
                self._champion_mtime_ns=stamp
                return
            self.champion_line=school50_champions.summarize(
                state,start_step=self._champion_start_step).line()
            from bilqis_mlx import current_course_progress
            self.current_course=current_course_progress.focused_rows(state)
            self.current_graduation_line=current_course_progress.graduation_line(state)
            self._champion_mtime_ns=stamp
        except (OSError,ValueError,TypeError,KeyError):
            # An absent or unavailable optional report is not a train error.
            return

    def attach_champion_source(self,run_dir):
        """Attach the read-only modern championship inventory for live refresh."""
        self._champion_source=Path(run_dir).expanduser()/'state.json'
        self._champion_mtime_ns=None
        self._refresh_champions()

    def attach_school50(self,run_dir,*,cutoff_visit=None,state=None):
        """One run-independent G/B/N progress adapter for every School50 UI.

        Live trainer, historical watcher and future versions all use this
        method. It is strictly read-only and never imports a neural runner.
        """
        from bilqis_mlx import school50_progress as scores, school50_champions
        source=Path(run_dir).expanduser()/'state.json'
        if state is None:
            state=read_current(source.parent)
        if cutoff_visit is None:cutoff_visit=state['visits']
        current=scores.from_run_state(state,cutoff_visit=cutoff_visit)
        program=tuple(state.get('config',{}).get('grade_program') or
                      state.get('triplets',{}).get('eligible_program') or ())
        families=sorted({name
            for folds in state.get('baseline_bridge',{}).values()
            for fold in folds.values()
            for name in fold.get('by_family',{})})
        start_step=school50_champions.step_at_visit(state,cutoff_visit)
        self.progress=current
        self._progress_source=source
        self.grade_program=program
        self.bridge_families=families
        self._champion_source=source
        self._champion_start_step=start_step
        self._champion_mtime_ns=None
        self._refresh_champions()

    def _attach_legacy_school50_event(self,kind,payload):
        """Compatibility for already-frozen v11/v15 trainer event streams.

        New producers supply run_dir in a generic SCHOOL50 DASHBOARD ATTACH
        event, or invoke attach_school50(run_dir) explicitly at startup.
        Neither model version nor display title defines the data contract.
        """
        if self.progress is not None:return
        defaults={
            ('SCHOOL50 BRIDGE PRIORITY','BILQIS / SCHOOL50 V11'):
                'school50-time-first-v11',
            ('V15 RUN-LOCAL CHAMPIONS','BILQIS / SCHOOL50 V15 RUN-LOCAL'):
                'primitive-consolidation-v15-run-local',
        }
        if kind=='SCHOOL50 DASHBOARD ATTACH':
            location=payload.get('run_dir')
        else:
            location=defaults.get((kind,self.title))
        if location is None:return
        if kind!='SCHOOL50 DASHBOARD ATTACH':
            location=Path(__file__).resolve().parents[1]/'runs'/location
        argv=sys.argv
        if '--run-dir' in argv and argv.index('--run-dir')+1<len(argv):
            location=Path(argv[argv.index('--run-dir')+1])
        try:
            self.attach_school50(location)
        except (OSError,KeyError,ValueError,TypeError):
            # Display failure must never abort a neural grade or invent data.
            self.progress=None

    def _latest_grade_progress(self,payload):
        """Use saved, selected-grade evidence from the committed boundary."""
        if self.progress is None or self._progress_source is None:return None
        from bilqis_mlx import school50_progress as scores
        try:
            state=read_current(self._progress_source.parent)
            record=state['grade_ledger'][-1]
            if (record['visit']!=payload.get('grade_visit') or
                    record['grade']!=payload.get('grade')):return None
            self.progress.observe_grade(record)
            if record['grade']=='G22':
                report=next((p for p in reversed(state['pass_ledger'])
                             if p.get('pass')==record.get('pass')),None)
                if report is not None:self.progress.observe_pass(report)
            return scores.grade_accuracy(record)
        except (OSError,KeyError,ValueError,TypeError,IndexError):
            return None

    def push(self,kind,payload=None,*,redraw=True):
        payload=payload or {}
        if kind=="candidate":
            core,retention,soup=_candidate_rows(payload)
            self.rows["CANDIDATES"].append(core)
            self.rows["SENTINEL & RETENTION"].append(retention)
            self.rows["SOUP & TEACHER"].append(soup)
            earlier=(payload.get("bridge_before") or {}).get("by_family") or {}
            later=(payload.get("bridge_after") or {}).get("by_family") or {}
            for family,result in later.items():
                prior=earlier.get(family) or {}
                first,second=prior.get("correct"),result.get("correct")
                self.rows["BRIDGE FAMILIES"].append({
                    "grade":payload.get("grade","?"),
                    "attempt":payload.get("attempt","?"),
                    "family":family,
                    "before":f"{first}/{prior.get('questions','?')}",
                    "after":f"{second}/{result.get('questions','?')}",
                    "gain":f"{second-first:+d}" if isinstance(first,int) and
                           isinstance(second,int) else "-"})
        elif kind=="grade":
            accuracy=payload.get('accuracy')
            saved=self._latest_grade_progress(payload)
            if saved is not None:accuracy=saved
            focused=self.current_course.get(payload.get('grade'))
            if focused is not None:
                # The primary grade score follows its current lesson, not
                # the obsolete G24 examination. Header labels provenance.
                accuracy=focused['percent']
            elif self.current_course and is_historical_capability(payload.get('grade')):
                # Legacy G24 scores are no longer grade attainment for the
                # replaced syllabus. Do not present them as RIGHT%.
                accuracy=None
            right=f'{accuracy:.1f}%' if isinstance(accuracy,(float,int)) else '-'
            self.rows["GRADES & MASTERY"].append({
                "visit":payload.get("grade_visit", "-"),
                "grade":payload.get("grade","?"),
                "step":payload.get("step", "-"),
                "eligible":payload.get("eligible", "-"),
                "selected":"Y" if payload.get("selected") else "N",
                "prefix":payload.get("prefix", "-"),
                "outcome":payload.get("outcome", "PENDING CHECKPOINT"),
                "right_pct":right})
        elif kind=="state":
            stage=payload.get("mastery") or {}
            config=payload.get("config") or {}
            primitive=payload.get("primitive") or {}
            phase=stage.get("phase", "?")
            if (phase=="NUMERIC" and stage.get("position")==0 and
                    stage.get("prefix")==1 and "stage_index" in primitive):
                from bilqis_mlx import spiral_primitive_lessons as curriculum
                step=primitive["stage_index"]
                phase=f"NUMERIC/{curriculum.STAGES[min(step,len(curriculum.STAGES)-1)]}"
            self.state={"phase":stage.get("phase", "?"),
                        "prefix":stage.get("prefix", "?"),
                        "failures":stage.get("frontier_failures", "?"),
                        "max_failures":config.get("max_frontier_failures",
                            12 if config.get("version")=="bilqis.school50.mastery-v5/v1" else "?"),
                        "next":_next_grade(stage),
                        "step":payload.get("optimizer_step", "?"),
                        "visits":payload.get("grade_visits", "?"),
                        "teacher":(payload.get("teacher") or {}).get("events","?"),
                        "stop":payload.get("last_run_status", "?"),
                        "halt":stage.get("halt_reason") or ""}
            self.state["phase"]=phase
        elif kind=="system":
            self._attach_legacy_school50_event(payload.get('kind'),payload)
            self.rows["SYSTEM & QUALIFICATION"].append({
                "kind":payload.get("kind","INFO"),
                "grade":payload.get("grade","-"),
                "detail":payload.get("detail","-")})
        else:
            raise ValueError("UNKNOWN_DASHBOARD_EVENT")
        if redraw and self.redraw_enabled:
            self.draw()

    def _wide_section(self,name,width,shown):
        """Deduplicate conceptual rows, not the underlying receipt history."""
        specs=dict(self.tables)[name]
        fitted=_wide_columns(specs,width)
        available=self._section_rows(name)
        shown=min(shown,len(available))
        recent=available[-shown:] if shown else []
        label=self._section_label(name,shown,recent,available)
        return ([_section_heading(name,label)[:width],
                 _table_line({c.key:c.name for c in fitted},fitted)[:width]]+
                [_table_line(row,fitted)[:width] for row in recent])

    def _section_label(self,name,shown,recent,available):
        if name=='BRIDGE FAMILIES':
            total=len(self.bridge_families) if self.bridge_families else len(available)
            return f'{shown}/{total} families'
        elif name=='GRADES & MASTERY':
            correct,total=self._latest_all_grade_score()
            score=(f': {correct}/{total} ({100*correct/total:.1f}%) TRAINED'
                   if total else '')
            return f'CURRICULUM [{shown}/{len(available)} visible]{score}'
        elif name=='SYSTEM & QUALIFICATION':
            return f'{shown}/{len(available)} states'
        visible=f'{shown}/{len(available)} visible'
        if name=='CANDIDATES':
            notice=self._active_notification()
            if notice:
                return f'! {notice} | {visible}'
        return visible

    def _section_rows(self,name):
        rows=list(self.rows[name])
        if name=='SYSTEM & QUALIFICATION':
            latest={}
            for index,row in enumerate(rows):
                if row.get('kind')=='CAP BEST':
                    # Historical TOP values already live beside current scores
                    # in GRADES & MASTERY; repeating them here wastes scarce
                    # operator real estate.
                    continue
                latest[(row.get('kind'),row.get('grade'))]=(index,row)
            projected=[]
            for _,row in sorted(latest.values(),key=lambda item:item[0]):
                kind=row.get('kind','INFO')
                grade=row.get('grade','-')
                projected.append({
                    **row,
                    'kind':_system_kind(kind,grade),
                    'detail':_compact_system_detail(
                        kind,grade,row.get('detail','-')),
                })
            return projected
        if name=='GRADES & MASTERY' and self.current_course:
            rows=[{**row,'right_pct':(
                    f'{self.current_course[row["grade"]]["percent"]:.1f}%'
                    if row['grade'] in self.current_course else
                    '-' if is_historical_capability(row['grade']) else
                    row['right_pct'])} for row in rows]
        if name not in ('BRIDGE FAMILIES','GRADES & MASTERY'):
            return rows
        key='family' if name=='BRIDGE FAMILIES' else 'grade'
        seen=set()
        distinct=[]
        for row in reversed(rows):
            identity=row[key]
            if identity not in seen:
                seen.add(identity)
                distinct.append({**row,'row_type':row.get('row_type','summary')})
        distinct=list(reversed(distinct))
        if name!='GRADES & MASTERY':
            return distinct
        champion_by_cap={row['capability']:row for row in self._champion_rows}
        latest_families=self._section_rows('BRIDGE FAMILIES')
        families={}
        for observed in latest_families:
            family=observed.get('family')
            grade=observed.get('grade')
            if not family or not grade:
                continue
            title=champion_by_cap.get(family)
            start=observed.get('start','-')
            latest=observed.get('after','-')
            best=title.get('best','-') if title is not None else '-'
            parsed=_score_tuple(latest)
            family_row={
                **observed,
                'row_type':'champion' if title is not None else 'family',
                'capability':family,
                'subject':family,
                'start':start,
                'latest':latest,
                'best':best,
                'step_exam':_step_exam(observed.get('step','-'),
                                       observed.get('attempt','-')),
                'score_line':_compact_score_line(start,best,latest),
                'right_grew':_right_grew(start,latest),
                'right_pct':(
                    f'{100*parsed[0]/parsed[1]:.1f}%' if parsed is not None else '-'),
                'to100':(
                    str(parsed[1]-parsed[0]) if parsed is not None else '-'),
                'outcome':(
                    f'CHAMP @{title.get("title_step","-")} | '
                    f'br{title.get("breadth","-")}'
                    if title is not None else '-'),
            }
            families.setdefault(grade,[]).append(family_row)
        combined=[]
        for row in distinct:
            summary={
                **row,
                'row_type':'summary',
                'subject':row.get('grade','-'),
                'step_exam':_step_exam(row.get('step','-'),row.get('attempt','-')),
                'score_line':_compact_score_line(
                    row.get('start','-'),row.get('best','-'),row.get('latest','-')),
                'right_grew':_right_grew(row.get('start','-'),row.get('latest','-')),
                'outcome':_compact_summary_outcome(row.get('outcome','-')),
            }
            combined.append(summary)
            combined.extend(families.pop(row['grade'],()))
        for grade in sorted(families):
            combined.extend(families[grade])
        return combined

    def _wide_pane(self,names,width,body_height,height):
        """Stack each pane's sections without borrowing another pane's rows."""
        if not names:
            return [""]*body_height
        if len(names)==1:
            quotas={names[0]:min(len(self._section_rows(names[0])),body_height-2)}
        elif names[0]=='BRIDGE FAMILIES':
            # Concept totals are small: show each family once, then use all
            # remaining vertical space for distinct G/B grade results.
            slots=max(0,body_height-2*len(names))
            families=min(len(self._section_rows(names[0])),max(0,slots//3))
            grades=min(len(self._section_rows(names[1])),slots-families)
            families+=min(len(self._section_rows(names[0]))-families,
                          slots-families-grades)
            quotas={names[0]:families,names[1]:grades}
        else:
            slots=max(0,body_height-2*len(names))
            quotas={name:min(len(self.rows[name]),
                             max(1,round(height*WIDE_ROW_FRACTIONS[name])))
                    for name in names}
            # Small displays must still show every category's own heading.
            while sum(quotas.values())>slots:
                eligible=[name for name in names if quotas[name]>0]
                if not eligible:break
                biggest=max(eligible,key=lambda name:quotas[name])
                quotas[biggest]-=1
        lines=[]
        for name in names:
            lines.extend(self._wide_section(name,width,quotas[name]))
        return (lines+[""]*max(0,body_height-len(lines)))[:body_height]

    def _render_wide(self,headers,footer,*,width,height):
        widths=_pane_widths(width)
        tail=(1 if self.champion_line else 0)+(2 if footer is not None else 0)
        body_height=height-len(headers)-tail
        available=set(dict(self.tables))
        panes=[self._wide_pane(
                   tuple(name for name in names if name in available),
                   pane_width,body_height,height)
               for names,pane_width in zip(WIDE_PANES,widths)]
        lines=[_clean(header)[:width] for header in headers]
        for row in zip(*panes):
            line=WIDE_SEP.join(text.ljust(pane_width)
                               for text,pane_width in zip(row,widths))
            lines.append(line.rstrip())
        if self.champion_line:
            lines.append(_clean(self.champion_line)[:width])
        if footer is not None:
            lines.append("-"*width)
            lines.append(_clean(footer)[:width])
        return "\n".join(lines)

    def render(self,*,width=None,height=None):
        self._refresh_champions()
        size=shutil.get_terminal_size((100,30))
        width=max(30,size.columns if width is None else width)
        height=max(6,size.lines if height is None else height)
        state=self.state
        headline=(f"{self.title}     {self.mode}   "
                  f"{self.clock()-self.started:.0f}s elapsed")
        status=(f"{state.get('phase','INIT')}  next {state.get('next','-')} "
                f"| prefix {state.get('prefix','-')} "
                f"| fail {state.get('failures','-')}/{state.get('max_failures','-')} "
                f"| step {state.get('step','-')} "
                f"| visits {state.get('visits','-')} "
                f"| T {state.get('teacher','-')}")
        if self.number_semantics:
            status+=f" | int roots {self._number_semantics_text()}"
        footer=f"{state.get('stop','RUNNING')} {state.get('halt','')} | raw log: {self.log_hint or 'read-only'}"
        retained=state.get("retained_visits",0)
        retained_suffix=(f" ({retained:,} retained)" if type(retained) is int else "")
        speed=(f"{round(self._steps_per_min):,} attempted steps/min{retained_suffix}"
               if isinstance(self._steps_per_min,(int,float)) else "")
        if self.compact_header:
            elapsed=max(0,self.clock()-self.started)
            phase=state.get('phase','INIT')
            prefix=state.get('prefix','-')
            if prefix not in (None,'','-','?','NOT_ADMITTED'):
                school=f"{prefix}:{phase}"
            elif phase not in (None,'','-','?'):
                school=str(phase)
            else:
                school="-"
            curriculum=self._curriculum_snapshot()
            step=state.get('step')
            exam=curriculum['exam']
            visits=state.get('visits')
            teacher=state.get('teacher')
            student=self._same_student_snapshot()
            latest="-"
            best="-"
            if student is not None:
                latest_score,best_score=student
                latest=f"{latest_score[0]}/{latest_score[1]} @{latest_score[2]}"
                best=f"{best_score[0]}/{best_score[1]} @{best_score[2]}"
            fields=[
                ("BILQIS",school,22,False),
                ("RUNTIME",_human_duration(elapsed),15,False),
            ]
            budget=self.time_budget_seconds
            if isinstance(budget,(int,float)) and budget>0:
                percent=int(elapsed*100/budget+.5)
                fields.append((
                    "MAX TIME",
                    f"{percent}% / {_human_duration(budget)} max",
                    16,
                    False,
                ))
            fields.extend([
                ("RUN",self.run_name or "-",23,False),
                ("STEPS",step if step not in (None,'','?') else "-",7,True),
                ("EXAM",exam if exam not in (None,'','?') else "-",6,True),
                ("VISITS",visits if visits not in (None,'','?') else "-",7,True),
                ("TEACHER",teacher if teacher not in (None,'','?') else "-",7,True),
                ("GRADES",curriculum['grades'],6,True),
                ("CAPS",curriculum['capabilities'],5,True),
                ("INT ROOTS",self._number_semantics_text(),11,False),
                ("STUDENT LATEST",latest,18,False),
                ("STUDENT BEST",best,18,False),
                ("STEPS/MIN",
                 round(self._steps_per_min)
                 if isinstance(self._steps_per_min,(int,float)) else "-",
                 9,True),
                ("RETAINED",retained if type(retained) is int else "-",8,True),
            ])
            halt=state.get('halt')
            if halt:
                fields.append(("HALT",halt,24,False))
            headings,values=_header_table(fields)
            headers=[headings,values,""]
            footer=None
        else:
            headers=[_right_header(headline,speed,width) if speed else headline,
                     status]
            if self.progress is not None:
                headers=[headline,_right_header(status,
                            _score_summary(self.progress,'START',width),width),
                         _right_header(
                            f'LAST OBSERVED* (full pass {self.progress.last_full_pass or "-"}; '
                            f'visit {self.progress.latest_visit})',
                                       _score_summary(self.progress,'LATEST*',width),width)]
                footer+=' | '+getattr(self.progress,'provenance_note',
                    '*different grade steps between full passes; ALL=mean(G,B,N)')
            if self.current_course:
                from bilqis_mlx import current_course_progress
                # The selected G11/G20/G22 scores can come from DIFFERENT steps.
                # Keep their provenance distinct from the terminal full rubric.
                headers=[headers[0],current_course_progress.summary(self.current_course),
                         'LAST RETAINED STEPS: '+ ' '.join(
                            f'{grade}@{entry["optimizer_step"]}' for grade,entry in
                            sorted(self.current_course.items())) +
                         ' | '+current_course_progress.advancement(self.current_course)]
            if self.current_graduation_line:
                headers.append(self.current_graduation_line)
            if self.operator_lines:
                headers.extend(self.operator_lines)
        if width>=WIDE_MIN_WIDTH and height>=WIDE_MIN_HEIGHT:
            return self._render_wide(headers,footer,width=width,height=height)
        groups=list(self.tables) if self.show_all_panels else [
            (name,columns) for name,columns in self.tables if self.rows[name]]
        if not groups:
            groups=[self.tables[0],self.tables[3]]
        # A heading and one header row per visible category are non-negotiable.
        # At very small heights prioritize candidate and mastery categories.
        priority=("CANDIDATES","GRADES & MASTERY","BRIDGE FAMILIES",
                  "SOUP & TEACHER","SENTINEL & RETENTION",
                  "SYSTEM & QUALIFICATION")
        footer_rows=1 if footer is not None else 0
        if len(groups)*2 + len(headers)+footer_rows+(1 if self.champion_line else 0) > height:
            groups=sorted(groups,key=lambda group:priority.index(group[0]))
            groups=groups[:max(0,(height-len(headers)-footer_rows-
                         (1 if self.champion_line else 0))//2)]
        fixed=len(headers)+footer_rows+len(groups)*2+(1 if self.champion_line else 0)
        budget=max(0,height-fixed)
        counts={name:0 for name,_ in groups}
        # Fair allocation: each existing group gets visible space; additional
        # rows favor candidate and grade information rather than tiny signals.
        weights=("CANDIDATES","GRADES & MASTERY","CANDIDATES",
                 "BRIDGE FAMILIES","SENTINEL & RETENTION","SOUP & TEACHER",
                 "GRADES & MASTERY","SYSTEM & QUALIFICATION")
        while budget>0 and any(counts[name]<max(1,len(self._section_rows(name))) for name in counts):
            progressed=False
            for name in weights:
                if name in counts and counts[name]<max(1,len(self._section_rows(name))) and budget>0:
                    counts[name]+=1
                    budget-=1
                    progressed=True
            if not progressed:
                break
        lines=[_clean(header)[:width] for header in headers]
        for name,columns in self.tables:
            if name not in counts:
                continue
            available=self._section_rows(name)
            take=counts[name]
            shown=min(take,len(available))
            recent=available[-shown:] if shown else []
            label=self._section_label(name,shown,recent,available)
            lines.append(_section_heading(name,label)[:width])
            fitted=_columns(columns,width)
            lines.append(_table_line({c.key:c.name for c in fitted},fitted)[:width])
            if shown:
                lines.extend(_table_line(row,fitted)[:width]
                             for row in recent)
        if self.champion_line:lines.append(_clean(self.champion_line)[:width])
        if footer is not None:
            lines.append(_clean(footer)[:width])
        # No hidden terminal wrapping, including at small terminal heights.
        return "\n".join(lines[:height])

    def draw(self):
        self.dirty=False
        try:
            self._sample_step_rate()
            if self.stream.isatty():
                self.stream.write("\x1b[H\x1b[2J"+self.render()+"\x1b[J")
            else:
                self.stream.write(self.render()+"\n")
            self.stream.flush()
        except (OSError,ValueError):
            # Display failures must never change neural training policy.
            self.dirty=True

    def _sample_step_rate(self):
        """Measure attempted optimizer throughput only at real dashboard draws."""
        if self.state.get("_rate_sample_eligible", True) is False:
            return
        step=self.state.get("attempted_steps")
        now=self.clock()
        if type(step) is not int:
            return
        if self._rate_step is None:
            self._rate_step,self._rate_time=step,now
            return
        elapsed=now-self._rate_time
        if elapsed>0 and step!=self._rate_step:
            self._steps_per_min=(step-self._rate_step)/elapsed*60
            self._rate_step,self._rate_time=step,now

    def _latest_all_grade_score(self):
        """Aggregate each grade's latest measured numerator/denominator once."""
        current_correct=self.state.get("_all_grade_correct")
        current_total=self.state.get("_all_grade_total")
        if (type(current_correct) is int and type(current_total) is int and
                current_total>0 and 0<=current_correct<=current_total):
            return current_correct,current_total
        latest={}
        for row in self.rows.get("GRADES & MASTERY", ()):
            grade=row.get("grade")
            value=row.get("latest")
            if not grade or not isinstance(value,str) or "/" not in value:
                continue
            left,right=value.split("/",1)
            try:
                correct,total=int(left),int(right)
            except ValueError:
                continue
            if 0<=correct<=total and total>0:
                latest[grade]=(correct,total)
        return (sum(v[0] for v in latest.values()),
                sum(v[1] for v in latest.values()))

    def _curriculum_snapshot(self):
        rows=self._section_rows("GRADES & MASTERY")
        summaries=[row for row in rows if row.get('row_type')=='summary']
        full=self.grade_program or tuple(dict.fromkeys(
            row.get('grade') for row in summaries if row.get('grade')))
        latest=max(
            summaries,
            key=lambda row:(
                row.get('attempt') if type(row.get('attempt')) is int else -1,
                row.get('step') if type(row.get('step')) is int else -1,
            ),
            default={},
        )
        return {
            'exam':latest.get('attempt','-'),
            'grades':len(full),
            'capabilities':sum(
                row.get('row_type')!='summary' for row in rows),
        }

    def _same_student_snapshot(self):
        telemetry=getattr(self,'school_telemetry',None)
        latest=getattr(telemetry,'cumulative_latest',None)
        best_by_key=getattr(telemetry,'cumulative_best',None)
        if latest is None or not isinstance(best_by_key,dict):
            return None
        key,correct,total,step,_status=latest
        best=best_by_key.get(key)
        if (type(correct) is not int or type(total) is not int or total<=0 or
                not 0<=correct<=total or type(step) is not int or
                not isinstance(best,tuple) or len(best)!=3):
            return None
        best_correct,best_total,best_step=best
        if (type(best_correct) is not int or type(best_total) is not int or
                best_total<=0 or not 0<=best_correct<=best_total or
                type(best_step) is not int):
            return None
        return ((correct,total,step),(best_correct,best_total,best_step))


def _next_grade(stage):
    phase=stage.get("phase")
    prefix=stage.get("prefix",1)
    pos=stage.get("position",0)
    if phase=="NUMERIC" and isinstance(pos,int):return f"M{pos+1:02d}"
    if phase=="LOGIC" and isinstance(pos,int):return f"G{pos+1:02d}"
    return "-"


class RawLogStream:
    """Plain original stdout log; terminal sees only grouped dashboard rows."""
    def __init__(self,file,dashboard,run_dir):
        self.file=file
        self.dashboard=dashboard
        self.buffer=""
        self.run_dir=Path(run_dir)

    def write(self,text):
        self.file.write(text)
        self.file.flush()
        self.buffer+=text
        while "\n" in self.buffer:
            line,self.buffer=self.buffer.split("\n",1)
            if line.startswith("[school50-numeric-spiral]") and "mastery=" in line:
                self._sync_grade()
        return len(text)

    def flush(self):
        self.file.flush()

    def _sync_grade(self):
        try:
            state=read_current(self.run_dir)
            self.dashboard.push("state",state,redraw=False)
            visit=state["grade_ledger"][-1]
            mastery_event=state["mastery_events"][-1]
            self.dashboard.push("grade",{
                "grade_visit":visit["grade_visit"],"grade":visit["grade"],
                "step":state["optimizer_step"],"eligible":visit["eligible"],
                "selected":visit.get("selected"),"prefix":mastery_event["prefix"],
                "outcome":mastery_event["outcome"],
                "next":_next_grade(state["mastery"])})
        except (OSError,ValueError,KeyError,IndexError) as error:
            self.dashboard.push("system",{"kind":"DISPLAY WARNING",
                                          "detail":_clean(error)},redraw=False)
        self.dashboard.draw()


def _feed_event(dashboard,logfile,kind,record,*,elapsed=None,attempts=None):
    from bilqis_mlx import spiral_staged_diagnostics as diagnostic
    if kind=="candidate":
        logfile.write(diagnostic.candidate_line(record,attempts,elapsed=elapsed)+"\n")
        logfile.flush()
        dashboard.push("candidate",record)
    elif kind=="grade":
        # Pre-checkpoint grade render is a receipt, not a final selected grade.
        visit=record["visit"]
        logfile.write(diagnostic.grade_line(visit,record["candidates"],
                                           record["state"],elapsed=elapsed,pending=True)+"\n")
        logfile.flush()
        dashboard.push("system",{"kind":"GRADE EVAL",
            "grade":visit["grade"],"detail":f"{visit['eligible']}/{visit['candidate_attempts']} eligible; awaiting durable mastery check"})
    elif kind=="pass":
        for line in diagnostic.pass_lines(record["report"],record["state"]):
            logfile.write(line+"\n")
        logfile.flush()
        dashboard.push("system",{"kind":"PASS",
           "detail":record["report"].get("decision", "?")})


def train(args,*,log_file,stream=None):
    """Run *unchanged* trainer with structured telemetry and plain logs."""
    from bilqis_mlx import spiral_staged_diagnostics as diagnostic
    stream=stream if stream is not None else sys.stdout
    if not stream.isatty():
        raise ValueError("DASHBOARD_REQUIRES_INTERACTIVE_TTY_USE_PLAIN_MODE")
    run_dir=diagnostic.DEFAULT_RUN
    if "--run-dir" in args:
        position=args.index("--run-dir")
        run_dir=Path(args[position+1])
    log_file=Path(log_file)
    log_file.parent.mkdir(parents=True,exist_ok=True)
    dashboard=Dashboard(stream=stream)
    dashboard.log_hint=log_file.name
    dashboard.state={"phase":"NUMERIC","prefix":1,"failures":0,
                     "max_failures":36,"next":"M01","step":67800,
                     "visits":0,"teacher":"-","stop":"STARTING"}
    if "--max-frontier-failures" in args:
        dashboard.state["max_failures"]=args[args.index("--max-frontier-failures")+1]
    existing=run_dir/"state.json"
    if existing.is_file():
        try:dashboard.push("state",read_current(run_dir),redraw=False)
        except (OSError,ValueError):pass
    dashboard.push("system",{"kind":"START","detail":"FP32 checkpoint and teacher remain managed by original runner"})
    previous=signal.getsignal(signal.SIGWINCH)
    signal.signal(signal.SIGWINCH,lambda *_:dashboard.draw())
    try:
        with log_file.open("a",encoding="utf-8",buffering=1) as outfile:
            logger=RawLogStream(outfile,dashboard,run_dir)
            def sink(kind,record,**data):
                _feed_event(dashboard,outfile,kind,record,**data)
            try:
                with redirect_stdout(logger):
                    diagnostic.train_with_live_diagnostics(args,reporter=sink)
            except BaseException as error:
                dashboard.push("system",{"kind":"TRAINER ERROR","detail":str(error)},
                               redraw=False)
                dashboard.mode="ERROR"
                raise
            finally:
                path=run_dir/"state.json"
                if path.is_file():
                    try:dashboard.push("state",read_current(run_dir),redraw=False)
                    except (OSError,ValueError):pass
                dashboard.mode="FINISHED" if dashboard.mode!="ERROR" else dashboard.mode
                dashboard.draw()
    finally:
        signal.signal(signal.SIGWINCH,previous)
    return dashboard


def watch(run_dir,*,tail=12,follow=False,poll=1.5,stream=None):
    """Read-only, grade-boundary dashboard over existing, durable state."""
    stream=stream if stream is not None else sys.stdout
    dashboard=Dashboard(stream=stream)
    dashboard.mode="READ-ONLY"
    path=Path(run_dir)/"state.json"
    cursor=None
    signature=None
    try:
        while True:
            try:
                stat=path.stat()
                fresh=(stat.st_mtime_ns,stat.st_size)
                if fresh!=signature:
                    signature=fresh
                    state=read_current(path.parent)
                    dashboard.push("state",state,redraw=False)
                    visits=state.get("grade_ledger",[])
                    candidates=state.get("candidate_ledger",[])
                    if cursor is None:
                        cursor=max(0,len(visits)-tail)
                    offset=sum(v.get("candidate_attempts",0) for v in visits[:cursor])
                    for visit in visits[cursor:]:
                        subset=candidates[offset:offset+visit["candidate_attempts"]]
                        if len(subset)!=visit["candidate_attempts"]:
                            raise ValueError("DASHBOARD_PARTIAL_CANDIDATE_LEDGER")
                        for candidate in subset:
                            dashboard.push("candidate",candidate,redraw=False)
                        event=next((e for e in state.get("mastery_events",[])
                                    if e.get("visit")==visit["grade_visit"]),{})
                        dashboard.push("grade",{
                            "grade_visit":visit["grade_visit"],"grade":visit["grade"],
                            "step":(visit.get("selected") or {}).get("step") or
                                   (subset[0].get("parent_step") if subset else "-"),
                            "eligible":visit["eligible"],
                            "selected":visit.get("selected"),
                            "prefix":event.get("prefix","-"),
                            "outcome":event.get("outcome","-"),
                            "next":"-"},redraw=False)
                        offset+=visit["candidate_attempts"]
                    cursor=len(visits)
                    dashboard.draw()
                    if (not follow or state.get("mastery",{}).get("phase") in
                            ("STOPPED","OPERATOR_REVIEW")):
                        break
                if not follow:break
            except FileNotFoundError:
                if not follow:raise
            time.sleep(poll)
    except KeyboardInterrupt:
        dashboard.push("system",{"kind":"DETACHED","detail":"Training process unaffected"})
    return dashboard


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command",required=True)
    run=commands.add_parser("train",help="terminal dashboard over exact v5 training API")
    run.add_argument("--log-file",required=True,type=Path)
    view=commands.add_parser("watch",help="read-only recent history in dashboard")
    view.add_argument("--run-dir",type=Path,default=None)
    view.add_argument("--last",type=int,default=12)
    view.add_argument("--follow",action="store_true")
    args,rest=parser.parse_known_args()
    if args.command=="train":
        if rest and rest[0]=="--":rest=rest[1:]
        train(rest,log_file=args.log_file)
    else:
        from bilqis_mlx import spiral_staged_diagnostics as diagnostic
        if rest:parser.error("unexpected watch arguments: "+" ".join(rest))
        if args.last<0:parser.error("--last must be nonnegative")
        watch(args.run_dir or diagnostic.DEFAULT_RUN,tail=args.last,
              follow=args.follow)


if __name__=="__main__":
    main()
