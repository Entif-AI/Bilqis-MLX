from __future__ import annotations

from bilqis_mlx.compatibility.identities import is_historical_capability
from .scores import _next_grade
from .candidates import _candidate_rows

class EventsView:
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
