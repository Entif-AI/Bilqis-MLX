"""Read-only, source-labeled champion and soup inventory for School50 UI.

The personal-best G panel contains 48 questions, historical G retention
contains 24 per grade, B provisional replay contains 12 exposed questions.
Soup vote scores are its INGREDIENT scores, never an examination of the soup.
"""
from __future__ import annotations

from dataclasses import dataclass


def step_at_visit(state,visit):
    for row in reversed(state.get('grade_ledger',[])):
        if row.get('visit')==visit:return row.get('optimizer_step')
    if visit==state.get('carry_origin',{}).get('visits'):
        return state['carry_origin'].get('optimizer_step')
    return None


@dataclass(frozen=True)
class ChampionReport:
    g_count:int
    g_total:int
    g_personal_mean:float|None
    g_new:int|None
    b_qualified:int
    b_provisional:int
    b_total:int
    b_personal_mean:float|None
    b_new:int|None
    soup_epoch:int|None
    soup_g_votes:int
    soup_b_votes:int
    soup_sources:int|None
    anchor_old_mean:float|None
    developmental_g_mean:float|None
    developmental_pass:int|None
    soup_domain_weights:dict[str,float]|None=None

    def line(self):
        def pct(value):
            return f'{value:.1f}%' if value is not None else '-'
        g_new=f'+{self.g_new} new' if self.g_new is not None else 'new unknown'
        b_new=f'+{self.b_new} new' if self.b_new is not None else 'new unknown'
        if self.soup_domain_weights is not None:
            soup=(f'soup e{self.soup_epoch if self.soup_epoch is not None else "-"} '
                  f'{self.soup_g_votes}G PB + {self.soup_b_votes}B PB -> '
                  f'{100*self.soup_domain_weights["G"]:.0f}%G / '
                  f'{100*self.soup_domain_weights["B"]:.0f}%B domains, '
                  f'{self.soup_sources if self.soup_sources is not None else "-"} '
                  'sources (unscored)')
        else:
            soup=(f'soup e{self.soup_epoch if self.soup_epoch is not None else "-"} '
                  f'{self.soup_g_votes}G/{self.soup_b_votes}B votes, '
                  f'{self.soup_sources if self.soup_sources is not None else "-"} '
                  'sources (unscored)')
        return ('CHAMPIONS '
                f'G {self.g_count}/{self.g_total} PB48 {pct(self.g_personal_mean)} '
                f'({g_new}) | '
                f'B {self.b_qualified}/{self.b_total} qualified, '
                f'{self.b_provisional}/{self.b_total} provisional '
                f'PB12 {pct(self.b_personal_mean)} ({b_new}) | '
                f'N no champion | {soup} | '
                f'anchor G24 {pct(self.anchor_old_mean)} | '
                f'dev-best G24 {pct(self.developmental_g_mean)} '
                f'p{self.developmental_pass if self.developmental_pass is not None else "-"}')


def summarize(state,*,start_step=None):
    program=state.get('config',{}).get('grade_program') or []
    g_total=sum(grade.startswith('G') for grade in program)
    b_total=sum(grade.startswith('B') for grade in program)
    g={k:v for k,v in (state.get('grade_champions') or {}).items()
       if k.startswith('G')}
    b={k:v for k,v in (state.get('provisional_bridge_champions') or {}).items()
       if k.startswith('B')}
    qualified={k:v for k,v in (state.get('bridge_champions') or {}).items()
               if k.startswith('B')}

    def mean(group):
        scores=[item.get('score') for item in group.values()]
        scores=[x for x in scores if isinstance(x,(int,float)) and 0<=x<=1]
        return (100*sum(scores)/len(scores)) if scores else None

    def new(group):
        if start_step is None:return None
        return sum(isinstance(item.get('optimizer_step'),int) and
                   item['optimizer_step']>start_step for item in group.values())

    soup=state.get('frozen_soup') or {}
    manifest=soup.get('manifest') or {}
    assignments=manifest.get('grade_assignments') or {}
    anchor=state.get('holistic_anchor') or {}
    best=(state.get('time_first') or {}).get('best_historical') or {}
    return ChampionReport(
        g_count=len(g),g_total=g_total,g_personal_mean=mean(g),g_new=new(g),
        b_qualified=len(qualified),b_provisional=len(b),b_total=b_total,
        b_personal_mean=mean(b),b_new=new(b),
        soup_epoch=soup.get('epoch'),
        soup_g_votes=sum(k.startswith('G') for k in assignments),
        soup_b_votes=sum(k.startswith('B') for k in assignments),
        soup_sources=manifest.get('unique_ingredient_checkpoints'),
        anchor_old_mean=(100*anchor['old_mean'] if 'old_mean' in anchor else None),
        developmental_g_mean=(100*best['old_mean'] if 'old_mean' in best else None),
        developmental_pass=best.get('pass'),
        soup_domain_weights=manifest.get('domain_weights'))
