"""Read-only, top-style operator display for staged School50 training.

The dashboard is deliberately OUTSIDE the model's hashed training recipe.
It renders typed diagnostic records in bounded category buffers. A terminal
redraw never writes a checkpoint, modifies a gate or discards the raw text log.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from pathlib import Path
from bilqis_mlx.state_dag import read_current
import signal
import sys
import time
from .scores import _next_grade
from .layout import _clean
from ..spiral_dashboard import Dashboard

"""Read-only, top-style operator display for staged School50 training.



The dashboard is deliberately OUTSIDE the model's hashed training recipe.

It renders typed diagnostic records in bounded category buffers. A terminal

redraw never writes a checkpoint, modifies a gate or discards the raw text log.

"""
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
