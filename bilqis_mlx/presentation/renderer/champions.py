from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from bilqis_mlx.state_dag import read_current, read_current_fields

class ChampionsView:
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
