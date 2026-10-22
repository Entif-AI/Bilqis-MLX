"""Admit/probe one small source-correct event tranche in registered issue349 runs."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from bilqis_mlx import trainer
from bilqis_mlx.compatibility.executable_projection import legacy_course_for_profile
from bilqis_mlx.factory.generation import draw_executable_release_rows
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.profiles.catalog import CatalogProfileTransition
from bilqis_mlx.runtime.experiment_runs import ExperimentRunBudget
from bilqis_mlx.runtime.mlx_checkpoint import load_semantically_bound_bundle
from bilqis_mlx.source_adapters.copular_curriculum import expanded_graph as registered_graph
from bilqis_mlx.source_adapters import event_frames
from bilqis_mlx.source_adapters.school import live_source_registry

ROOT = Path(__file__).resolve().parents[1]


def _probe_event_capabilities(mx, source, graph, current, params, saved, *, seed=349101):
    scores={}
    for cap in event_frames.SPECS:
        rows=[]
        for draw_seed in range(seed, seed + 3):
            rows.extend(draw_executable_release_rows(source,graph,current,
                live_source_registry(),capability=cap,seed=draw_seed,each=64))
        unique={r['id']:r for r in rows};rows=list(unique.values())
        predictions=trainer._predictions(mx,params,rows,saved['config'],saved['answer_ids'])
        scores[cap]=dict(correct=sum(predictions[r['id']]==r['gold'] for r in rows),
            total=len(rows),specimens=[dict(id=r['id'],gold=r['gold'],predicted=predictions[r['id']]) for r in rows])
    return scores


def _adopt_source_revision(run, saved, current, graph, source, adapter):
    from bilqis_mlx.compatibility.live_releases import initial_course
    from bilqis_mlx.runtime.session import prepare_source
    from bilqis_mlx.runtime.release_adoption import _adopt_executable_profile

    if all(current.source_bindings.by_capability[cap].generator_id == adapter.GENERATOR
           for cap in event_frames.SPECS):
        return saved, current
    _, historical, _, _, _, _ = prepare_source(source,
        source/'runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt',
        ROOT/'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json')
    successor = adapter.compile_successor(current, graph, source_root=source,
        source_registry=live_source_registry(), answer_registry=live_answer_registry())
    saved, _, current, _ = _adopt_executable_profile(
        run, saved, initial_course(historical), source, graph, current.profile,
        compiled_successor=successor)
    return saved, current


def _arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--probe-seed',type=int,default=349101)
    admission = parser.add_mutually_exclusive_group()
    admission.add_argument('--admit',action='store_true')
    admission.add_argument('--adopt-introduction',action='store_true')
    admission.add_argument('--adopt-pairs',action='store_true')
    parser.add_argument('--refresh-boundary',action='store_true')
    return parser.parse_args()


def main():
    args = _arguments()
    run=args.run_dir.resolve(strict=True)
    budget=ExperimentRunBudget(run.parent);budget.register(run);budget.assert_can_allocate(600_000_000)
    if args.output.exists():
        raise ValueError('EXPERIMENT_RECEIPT_ALREADY_EXISTS')
    import mlx.core as mx
    mx.set_default_device(mx.gpu)
    with trainer.operator_lock(run):
        saved=json.loads((run/'state.json').read_text())
        params,opt,meta,graph=load_semantically_bound_bundle(run/saved['model_bundle'])
        current=trainer._require_executable_factory_admission(run,saved,graph)
        before=dict(saved['school']['current_student'])
        source=ROOT/'vendor/legacy-v16'
        if args.admit:
            manifest,historical,_,teacher_sha,_,_=trainer.prepare_source(source,
                source/'runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt',
                ROOT/'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json')
            grade_a=trainer.initial_course(historical)
            course=legacy_course_for_profile(grade_a,source,current.profile)
            params,opt,graph,saved=trainer._resume(run,manifest,course,teacher_sha,
                grade_a_course=grade_a,source_root=source)
            registry=live_source_registry()
            program=schedule_program_from_executable_release(current)
            school=trainer._state_from_json(saved['school'],program)
            capabilities=tuple(program.capability_map)
            cohort,pointer=trainer._routine_executable_cohort(run,saved,manifest,current,
                registry,source,graph,capabilities=capabilities,
                assessment_epoch=school.grade_exam_epoch,legacy_course=course)
            measured=trainer.score_cohort(cohort,trainer._predictions(mx,params,list(cohort.rows),
                saved['config'],saved['answer_ids']),asdict(school.current_student))
            boundary={**pointer,'assessment_grade':school.grade,
                'grade_exam_epoch':school.grade_exam_epoch,'source_exam_plane':'DEBT_ADMISSION_BOUNDARY',
                'exam_rubric_sha256':cohort.rubric_version,
                'student_sha256':school.current_student.sha256,
                'optimizer_step':school.current_student.optimizer_step,
                'scores':measured['scores'],'misses_for_teacher':list(measured['misses_for_teacher'])}
            grown=event_frames.expanded_graph(registered_graph(graph))
            successor=event_frames.compile_tranche(current,grown,source_root=source,
                source_registry=registry,answer_registry=live_answer_registry())
            saved={**saved,'debt_admission_boundary_exam':boundary}
            params,opt,graph,saved,_=trainer._adopt_catalog_profile(mx,run,saved,grade_a,
                source,graph,params,opt,CatalogProfileTransition(successor.profile,grown),
                reserve_gib=0.,allow_mastery_debt=True,compiled_successor=successor)
            current=successor
        if args.adopt_introduction or args.adopt_pairs:
            from bilqis_mlx.source_adapters import event_intro, event_pairs
            adapter = event_pairs if args.adopt_pairs else event_intro
            saved, current = _adopt_source_revision(run, saved, current, graph, source, adapter)
        if args.admit or args.refresh_boundary:
            program=schedule_program_from_executable_release(current)
            school=trainer._state_from_json(saved['school'],program)
            # A new source-bound observation of earlier skills after catalog growth.
            scope=tuple(saved['mentor_epoch']['previous_capabilities'])
            manifest={'manifest_sha256':saved['source_manifest_sha256']}
            cohort,pointer=trainer._routine_executable_cohort(run,saved,manifest,current,
                live_source_registry(),source,graph,capabilities=scope,
                assessment_epoch=school.grade_exam_epoch)
            measured=trainer.score_cohort(cohort,trainer._predictions(mx,params,list(cohort.rows),
                saved['config'],saved['answer_ids']),asdict(school.current_student))
            exam={**pointer,'assessment_grade':school.grade,'grade_exam_epoch':school.grade_exam_epoch,
                'exam_plane':'PROTOTYPE_PRIOR_SKILL_BOUNDARY','exam_rubric_sha256':cohort.rubric_version,
                'student_sha256':school.current_student.sha256,
                'optimizer_step':school.current_student.optimizer_step,
                'scores':measured['scores'],'misses_for_teacher':list(measured['misses_for_teacher'])}
            saved=trainer._advance(run,saved,school,last_exam=exam,persist=False)
            event=dict(event='SCHOOL_PROTOTYPE_BOUNDARY_MEASURED',generation=saved['generation'],
                checkpoint=saved['school']['current_student'],cohort_sha256=cohort.digest,
                scores=measured['scores'],actual_neural_updates=0)
            saved=trainer._persist(run,trainer._with_delivery_outbox(saved,(event,)))
            trainer._reconcile_delivery_outbox(run,saved)
        scores = _probe_event_capabilities(mx, source, graph, current, params, saved,
            seed=args.probe_seed)
        assert int(opt.state['step'].item())==saved['school']['current_student']['optimizer_step']
        result=dict(schema='bilqis.issue349.event-trial/v1',prototype_not_canonical=True,
            admitted=args.admit,adopted_introduction=args.adopt_introduction,adopted_pairs=args.adopt_pairs,probe_seeds=list(range(args.probe_seed,args.probe_seed+3)),
            before=before,checkpoint=saved['school']['current_student'],
            generation=saved['generation'],factory_release_sha256=current.release_sha256,
            mastery_debt=saved['school']['carried_mastery_debt'],scores=scores,
            budget=budget.enforce())
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
        print(json.dumps({**{k:v for k,v in result.items() if k!='scores'},
            'scores':{cap:{k:v for k,v in score.items() if k!='specimens'} for cap,score in scores.items()}}))


if __name__=='__main__':main()
