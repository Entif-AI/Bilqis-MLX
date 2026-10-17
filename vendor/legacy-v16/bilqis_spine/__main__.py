"""Inspect the research-only semantic graph and example generator."""
import argparse
import json
from pathlib import Path

from .factory import QuestionFactory,coverage,validate_same_contract
from .model import load_seed
from .store import materialize


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index',type=Path,
                        help='Optional output SQLite path; refuse overwrite')
    parser.add_argument('--seed',type=int,default=20261014)
    parser.add_argument('--tier',type=int,choices=(1,2,3),default=3)
    args=parser.parse_args(argv)
    graph=load_seed()
    factory=QuestionFactory(graph)
    lessons=factory.generate(tier=args.tier,seed=args.seed,count=18,channel='lesson')
    exams=factory.generate(tier=args.tier,seed=args.seed+1,count=18,
                           channel='assessment')
    validate_same_contract(lessons,exams)
    summary={'schema':graph.manifest['schema'],'graph_sha256':graph.sha256,
             'concepts':len(graph.concepts),'relations':len(graph.edges),
             'sources':len(graph.sources),'lesson_coverage':coverage(lessons),
             'assessment_coverage':coverage(exams),
             'lesson_examples':[q.packet() for q in lessons[:3]],
             'assessment_examples':[q.packet() for q in exams[:3]],
             'research_only':True,'changes_training':False}
    if args.index:summary['new_index']=str(materialize(graph,args.index))
    print(json.dumps(summary,indent=2,sort_keys=True))


if __name__=='__main__':main()
