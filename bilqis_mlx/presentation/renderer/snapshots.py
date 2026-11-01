from __future__ import annotations


class SnapshotsView:
    def _sample_step_rate(self):
        """Normalize attempted optimizer throughput across the current run."""
        if self.state.get("_rate_sample_eligible", True) is False:
            return
        step=self.state.get("attempted_steps")
        now=self.clock()
        if type(step) is not int:
            return
        elapsed=now-self.started
        if elapsed>0:
            self._steps_per_min=step/elapsed*60
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
