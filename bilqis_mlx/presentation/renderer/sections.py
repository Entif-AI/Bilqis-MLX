from __future__ import annotations

from bilqis_mlx.compatibility.identities import is_historical_capability
from .scores import _compact_score_line, _compact_summary_outcome, _right_grew, _score_tuple
from .system import _compact_system_detail, _system_kind
from .layout import _section_heading, _step_exam, _table_line, _wide_columns

class SectionsView:
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
        return f'{shown}/{len(available)} visible'

    def _system_rows(self,rows):
        latest={}
        for index,row in enumerate(rows):
            if row.get('kind')=='CAP BEST':
                continue
            latest[(row.get('kind'),row.get('grade'))]=(index,row)
        projected=[]
        for _,row in sorted(latest.values(),key=lambda item:item[0]):
            kind=row.get('kind','INFO')
            grade=row.get('grade','-')
            projected.append({
                **row,
                'kind':_system_kind(kind,grade),
                'detail':_compact_system_detail(kind,grade,row.get('detail','-')),
            })
        return projected

    def _course_rows(self,rows):
        if not self.current_course:
            return rows
        return [{**row,'right_pct':(
                f'{self.current_course[row["grade"]]["percent"]:.1f}%'
                if row['grade'] in self.current_course else
                '-' if is_historical_capability(row['grade']) else
                row['right_pct'])} for row in rows]

    @staticmethod
    def _distinct_rows(name,rows):
        key='family' if name=='BRIDGE FAMILIES' else 'grade'
        seen=set()
        distinct=[]
        for row in reversed(rows):
            identity=row[key]
            if identity not in seen:
                seen.add(identity)
                distinct.append({**row,'row_type':row.get('row_type','summary')})
        return list(reversed(distinct))

    def _mastery_family_rows(self):
        champion_by_cap={row['capability']:row for row in self._champion_rows}
        families={}
        for observed in self._section_rows('BRIDGE FAMILIES'):
            family=observed.get('family')
            grade=observed.get('grade')
            if not family or not grade:
                continue
            title=champion_by_cap.get(family)
            start=observed.get('start','-')
            latest=observed.get('after','-')
            best=title.get('best','-') if title is not None else '-'
            parsed=_score_tuple(latest)
            families.setdefault(grade,[]).append({
                **observed,
                'row_type':'champion' if title is not None else 'family',
                'capability':family, 'subject':family,
                'start':start, 'latest':latest, 'best':best,
                'step_exam':_step_exam(observed.get('step','-'),observed.get('attempt','-')),
                'score_line':_compact_score_line(start,best,latest),
                'right_grew':_right_grew(start,latest),
                'right_pct':f'{100*parsed[0]/parsed[1]:.1f}%' if parsed is not None else '-',
                'to100':str(parsed[1]-parsed[0]) if parsed is not None else '-',
                'outcome':(f'CHAMP @{title.get("title_step","-")} | '
                           f'br{title.get("breadth","-")}' if title is not None else '-'),
            })
        return families

    def _mastery_rows(self,distinct):
        families=self._mastery_family_rows()
        combined=[]
        for row in distinct:
            combined.append({
                **row,
                'row_type':'summary',
                'subject':row.get('grade','-'),
                'step_exam':_step_exam(row.get('step','-'),row.get('attempt','-')),
                'score_line':_compact_score_line(
                    row.get('start','-'),row.get('best','-'),row.get('latest','-')),
                'right_grew':_right_grew(row.get('start','-'),row.get('latest','-')),
                'outcome':_compact_summary_outcome(row.get('outcome','-')),
            })
            combined.extend(families.pop(row['grade'],()))
        for grade in sorted(families):
            combined.extend(families[grade])
        return combined

    def _section_rows(self,name):
        rows=list(self.rows[name])
        if name=='SYSTEM & QUALIFICATION':
            return self._system_rows(rows)
        if name=='GRADES & MASTERY':
            rows=self._course_rows(rows)
        if name not in ('BRIDGE FAMILIES','GRADES & MASTERY'):
            return rows
        distinct=self._distinct_rows(name,rows)
        if name!='GRADES & MASTERY':
            return distinct
        return self._mastery_rows(distinct)
