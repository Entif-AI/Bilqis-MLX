from __future__ import annotations

from bilqis_mlx.presentation.numeric_scope import integer_root_scope
import shutil
from .tables import WIDE_MIN_HEIGHT, WIDE_MIN_WIDTH
from .scores import _score_summary
from .layout import _clean, _columns, _header_table, _human_duration, _right_header, _section_heading, _table_line

class RenderView:
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
            if phase in ("PROMOTION_SWEEP", "ASSESS_PROMOTION_SWEEP"): fields.append(("SWEEP", f"GRADUATION {prefix}", 12, False))
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
                ("TEACHER",teacher if teacher not in (None,'','?') else "-",7,True), ("GRADES",curriculum['grades'],6,True), ("CAPS",curriculum['capabilities'],5,True), ("INTROOT",integer_root_scope(state.get("numeric_maximum")),7,False),
                ("STUDENT LATEST",latest,18,False),
                ("STUDENT BEST",best,18,False),
                ("ST/M",round(self._steps_per_min) if isinstance(self._steps_per_min,(int,float)) else "-",5,True),
                ("RTN",retained if type(retained) is int else "-",4,True),
                ("RTN%",round(retained*100/visits) if type(retained) is int and type(visits) is int and visits>0 else "-",5,True),
                ("GREW",f"{state['grew']:+d}" if type(state.get('grew')) is int else "-",5,True),
                ("R/H",round(retained*3600/elapsed) if type(retained) is int and elapsed>0 else "-",5,True),
                ("G/RTN",f"{state['grew']/retained:+.2f}" if type(state.get('grew')) is int and type(retained) is int and retained>0 else "-",6,True),
                ("GRAD",state.get("graduations","0.0.0 / 0.0.0"),18,False),
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
        view = getattr(self, "bamf_operator_view", None)
        if view is not None:
            from ..atlas_metrics import render_panel
            headers.extend(render_panel(view, state,
                                        expanded=getattr(self, "atlas_expanded", False), width=width))
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
