from __future__ import annotations

from pathlib import Path
from bilqis_mlx.state_dag import read_current
import sys

class HistoryView:
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
            location=Path(__file__).resolve().parents[2]/'runs'/location
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
