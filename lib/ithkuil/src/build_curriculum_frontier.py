"""Build the revisable New Ithkuil Chapter-1/2 curriculum research frontier.

This is a research projection, not Bilqis semantic admission.  It derives a
source-grounded D-O proposal, a 96-root reserve, the complete source inventory
and sense-level candidate surface from the canonical Ithkuil source-domain
tables.  Curriculum ordering stays outside canonical source CSVs by design.
"""

from __future__ import annotations

import csv
import json
import os
import re
import hashlib
from collections import defaultdict
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'_data'/'csv'
OUT=Path(os.environ.get(
    'BILQIS_CURRICULUM_FRONTIER_OUT',
    str(BASE/'_private'/'curriculum_frontier'),
))
OUT.mkdir(parents=True,exist_ok=True)
roots={r['root_form_raw']:r for r in csv.DictReader(open(DATA/'lexicon_roots.csv',encoding='utf-8'))}
senses=list(csv.DictReader(open(DATA/'lexicon_root_senses.csv',encoding='utf-8')))
senses_by=defaultdict(list)
for s in senses: senses_by[s['root_form_raw']].append(s)
evidence=list(csv.DictReader(open(DATA/'lexicon_root_evidence.csv',encoding='utf-8')))
evidence_by=defaultdict(list)
for row in evidence: evidence_by[row['root_form_raw']].append(row)
crosswalk=list(csv.DictReader(open(DATA/'bilqis_ithkuil_crosswalk.csv',encoding='utf-8')))

def anchor_rows(root):
    out=[]
    for row in crosswalk:
        # The bridge column is the only source-form identity.  Searching all
        # cells by substring can attach a root to an unrelated gloss/URL.
        if row.get('new_ithkuil_bridge','').strip() == root:
            out.append(f"{row['bilqis_token_id']}:{row['bilqis_token_symbol']}:{row['mapping_disposition']}")
    return out

def _sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def validate_frontier_manifest(path):
    """Validate a generated frontier sidecar without rewriting artifacts."""
    manifest=json.loads(Path(path).read_text(encoding='utf-8'))
    builder=Path(__file__)
    input_names={'lexicon_roots.csv','lexicon_root_senses.csv','lexicon_root_evidence.csv','bilqis_ithkuil_crosswalk.csv'}
    output_names={'candidate_pool.csv','grade_map.csv','sense_candidate_pool.csv','source_inventory.csv','deferred_codec.csv','grade_rationale.csv','frontier_plan.json'}
    if manifest.get('schema') != 'bilqis.ithkuil.frontier-manifest/v1':
        raise ValueError('CURRICULUM_FRONTIER_MANIFEST_SCHEMA_INVALID')
    if manifest.get('builder_file_sha256') != _sha256(builder):
        raise ValueError('CURRICULUM_FRONTIER_BUILDER_STALE')
    if set(manifest.get('input_files', {})) != input_names:
        raise ValueError('CURRICULUM_FRONTIER_INPUT_SET_INVALID')
    if set(manifest.get('output_files', {})) != output_names:
        raise ValueError('CURRICULUM_FRONTIER_OUTPUT_SET_INVALID')
    for name, expected in manifest['input_files'].items():
        actual=_sha256(DATA / name)
        if actual != expected:
            raise ValueError(f'CURRICULUM_FRONTIER_INPUT_STALE:{name}')
    for name, expected in manifest['output_files'].items():
        actual=_sha256(Path(path).parent / name)
        if actual != expected:
            raise ValueError(f'CURRICULUM_FRONTIER_OUTPUT_STALE:{name}')
    input_digest=hashlib.sha256(''.join(
        f'{name}:{digest}\n' for name,digest in
        sorted(manifest['input_files'].items())).encode()).hexdigest()
    output_digest=hashlib.sha256(''.join(
        f'{name}:{digest}\n' for name,digest in
        sorted(manifest['output_files'].items())).encode()).hexdigest()
    if manifest.get('input_digest') != input_digest:
        raise ValueError('CURRICULUM_FRONTIER_INPUT_DIGEST_INVALID')
    if manifest.get('output_digest') != output_digest:
        raise ValueError('CURRICULUM_FRONTIER_OUTPUT_DIGEST_INVALID')
    return manifest

def sense_key(s):
    return (0 if s['specification']=='BSC' else 1, 0 if s['stem']=='STEM 1' else 1, len(s['sense_summary']))

def intro_sense(root):
    ss=sorted(senses_by[root],key=sense_key)
    return ss[0]['sense_summary'] if ss else roots[root]['root_gloss']

def contrast_sense(root):
    ss=sorted(senses_by[root],key=sense_key)
    if len(ss)<2: return ''
    intro=ss[0]['sense_summary']
    for s in ss[1:]:
        if s['sense_summary'] != intro:
            prefix=(s['stem']+' ' if s['stem'] else '')+(s['specification']+' ' if s['specification'] else '')
            return (prefix+s['sense_summary']).strip()
    return ''

TARGET_SENSES = {
    ('-Č-', 'COPULAR_IDENTITY'): ('STEM 1', 'BSC'),
    ('-R-', 'ONTIC_NEGATION'): ('STEM 1', 'BSC'),
    ('-ŽW-', 'TYPE_CLASS'): ('', 'CTE'),
    ('-ŢP-', 'PROPERTY_ATTRIBUTE'): ('STEM 2', 'BSC'),
    ('-THW-', 'COMPONENT_PART'): ('STEM 1', 'BSC'),
    ('-SK-', 'GRAVITY_CONTAINMENT'): ('STEM 1', 'BSC'),
    ('-PS-', 'EVENT_OCCURRENCE'): ('STEM 1', 'BSC'),
    ('-TĻ-', 'COMMENCEMENT'): ('STEM 1', 'BSC'),
    ('-MPR-', 'TERMINATION'): ('STEM 1', 'BSC'),
    ('-SN-', 'CHANGE_VARIATION'): ('STEM 1', 'BSC'),
    ('-ÇN-', 'SOURCE_ORIGIN'): ('', 'CTE'),
    ('-ŘV-', 'OUTCOME_RESULT'): ('STEM 2', 'BSC'),
    ('-ZD-', 'COMPARE_CONTRAST'): ('STEM 1', 'BSC'),
    ('-ZD-', 'DISTINGUISH'): ('STEM 2', 'BSC'),
    ('-RK-', 'DEGREE_EXTENT'): ('STEM 1', 'BSC'),
    ('-ZDR-', 'MEASUREMENT'): ('STEM 1', 'BSC'),
    ('-RX-', 'SIMILARITY'): ('STEM 1', 'BSC'),
    ('-ŘḐ-', 'EXACTITUDE'): ('STEM 1', 'BSC'),
    ('-PH-', 'PRECISION_DEFINITION'): ('STEM 1', 'BSC'),
    ('-RT-', 'SUFFICIENCY'): ('STEM 1', 'BSC'),
    ('-MTF-', 'LIST'): ('STEM 1', 'BSC'),
    ('-MTF-', 'SERIES_SEQUENCE'): ('STEM 2', 'BSC'),
    ('-SMY-', 'SORT_BY_KIND'): ('STEM 1', 'BSC'),
    ('-ŘP-', 'UNIQUENESS'): ('STEM 2', 'BSC'),
    ('-PSM-', 'ACTION_STEP'): ('STEM 1', 'BSC'),
    ('-ŢK-', 'MAKE_FORM'): ('STEM 1', 'BSC'),
    ('-KSF-', 'USE_UTILIZE'): ('STEM 1', 'BSC'),
    ('-KŠF-', 'AGENCY_ENGAGEMENT'): ('STEM 1', 'BSC'),
    ('-NY-', 'CHOICE'): ('STEM 1', 'BSC'),
    ('-PŢ-', 'SEARCH_SEEK'): ('STEM 1', 'BSC'),
    ('-FH-', 'CHANCE_DISCOVERY'): ('STEM 1', 'BSC'),
    ('-ÇL-', 'PREPARATION_READINESS'): ('STEM 1', 'BSC'),
    ('-CX-', 'MANNER_WAY'): ('STEM 1', 'BSC'),
    ('-RCX-', 'METHOD_PROCEDURE'): ('STEM 1', 'BSC'),
    ('-Ž-', 'PHYSICAL_CAPABILITY'): ('STEM 1', 'BSC'),
    ('-PŘ-', 'ACCESS_PASSAGE'): ('STEM 1', 'BSC'),
    ('-ŢD-', 'PHYSICAL_CONTACT'): ('STEM 1', 'BSC'),
    ('-ÇR-', 'SEPARATION'): ('STEM 1', 'BSC'),
    ('-MC-', 'CONNECTION_BOND'): ('STEM 1', 'BSC'),
    ('-D-', 'GROUP_ASSEMBLY'): ('STEM 1', 'BSC'),
    ('-CY-', 'CLUSTER'): ('STEM 1', 'BSC'),
    ('-RMC-', 'UNIFICATION'): ('STEM 2', 'BSC'),
    ('-RMC-', 'FUSION_MERGING'): ('STEM 3', 'BSC'),
    ('-JP-', 'ALIGNMENT'): ('STEM 3', 'BSC'),
    ('-CḐ-', 'ADHESION'): ('STEM 1', 'BSC'),
    ('-SJ-', 'COMBINE'): ('STEM 1', 'BSC'),
    ('-SXL-', 'FILTER'): ('STEM 1', 'BSC'),
    ('-FŠ-', 'PHYSICAL_FITTING'): ('STEM 1', 'BSC'),
    ('-KÇ-', 'CUT_FISSURE'): ('STEM 1', 'BSC'),
    ('-SČ-', 'BREAK_APART'): ('STEM 1', 'BSC'),
    ('-RKS-', 'DIVIDE_SPLIT'): ('STEM 1', 'BSC'),
    ('-ČN-', 'OPEN_MOVE_APART'): ('STEM 1', 'BSC'),
    ('-JŢ-', 'PENETRATION'): ('STEM 1', 'BSC'),
    ('-ŇÇ-', 'EXTRACTION'): ('STEM 1', 'BSC'),
    ('-ḐŘ-', 'LINEAR_STRETCH'): ('STEM 1', 'BSC'),
    ('-FFR-', 'BENDING'): ('STEM 1', 'BSC'),
    ('-ŢŇ-', 'FILL'): ('STEM 1', 'BSC'),
    ('-ŠḐ-', 'EMPTY_REMOVE'): ('STEM 1', 'BSC'),
    ('-XV-', 'COMPRESSION'): ('STEM 1', 'BSC'),
    ('-TÇV-', 'DISPERSION'): ('STEM 1', 'BSC'),
    ('-G-', 'AMBULATION'): ('STEM 1', 'BSC'),
    ('-PD-', 'MANIPULATE_GRASP'): ('STEM 1', 'BSC'),
    ('-GF-', 'BIND_RESTRAIN'): ('STEM 1', 'BSC'),
    ('-TV-', 'SUPPORT_BEAR'): ('STEM 1', 'BSC'),
    ('-RG-', 'MOBILITY_MOTILITY'): ('STEM 2', 'BSC'),
    ('-XP-', 'TRANSPOSITION_INTERCHANGE'): ('STEM 2', 'BSC'),
    ('-PĻ-', 'TURN'): ('STEM 1', 'BSC'),
    ('-RPĻ-', 'ROTATE_SPIN'): ('STEM 1', 'BSC'),
    ('-ČPH-', 'STRIKE_IMPACT'): ('STEM 1', 'BSC'),
    ('-ŽN-', 'PUSH'): ('STEM 1', 'BSC'),
    ('-ÇV-', 'PULL_TRACTION'): ('STEM 1', 'BSC'),
    ('-FJ-', 'IMPEDE_BLOCK'): ('STEM 1', 'BSC'),
    ('-BN-', 'CHANNEL'): ('STEM 1', 'BSC'),
    ('-LŢR-', 'DRAINAGE'): ('STEM 1', 'BSC'),
    ('-ZŢ-', 'ABSORPTION'): ('STEM 1', 'BSC'),
    ('-RZŢ-', 'DIFFUSION_PERMEATION'): ('STEM 2', 'BSC'),
    ('-MBW-', 'SUCTION'): ('STEM 2', 'BSC'),
    ('-MBW-', 'PUMPING'): ('STEM 3', 'BSC'),
    ('-ŠŇ-', 'INFLATION'): ('STEM 1', 'BSC'),
    ('-ŇM-', 'SURFACE_APPLICATION'): ('STEM 1', 'BSC'),
    ('-FŢR-', 'RINSE'): ('STEM 1', 'BSC'),
    ('-ZW-', 'CLEANLINESS'): ('STEM 1', 'BSC'),
    ('-GŢ-', 'PHYSICAL_COMPATIBILITY'): ('STEM 3', 'BSC'),
    ('-RFJ-', 'CONSTRICTION'): ('STEM 1', 'BSC'),
    ('-CT-', 'EXAMINE'): ('STEM 2', 'BSC'),
    ('-RCT-', 'OBSERVE'): ('STEM 1', 'BSC'),
    ('-ŇŢT-', 'EVALUATION_VETTING'): ('STEM 2', 'BSC'),
    ('-MZ-', 'MEMORY_RECALL'): ('STEM 1', 'BSC'),
    ('-VL-', 'UNDERSTANDING_COMPREHENSION'): ('STEM 2', 'BSC'),
    ('-ŢT-', 'FACT_KNOW'): ('STEM 1', 'BSC'),
    ('-RŢT-', 'LEARN_KNOWLEDGE_SOURCE'): ('STEM 1', 'BSC'),
    ('-CC-', 'ERROR_MISCONCEPTION'): ('STEM 1', 'BSC'),
    ('-LČ-', 'ASSUMPTION_PRESUMPTION'): ('STEM 3', 'BSC'),
    ('-LČW-', 'HYPOTHESIS'): ('STEM 3', 'BSC'),
    ('-ŇŢT-', 'EXPERIMENT_HYPOTHESIS_TEST'): ('STEM 3', 'BSC'),
    ('-MŢT-', 'DEMONSTRATION_VERIFICATION'): ('STEM 1', 'BSC'),
    ('-NŢT-', 'SUBJECT_TOPIC'): ('STEM 1', 'BSC'),
    ('-MÇT-', 'EXAMPLE'): ('STEM 1', 'BSC'),
    ('-TKH-', 'RULE_PRECEPT'): ('STEM 1', 'BSC'),
    ('-RD-', 'TRUTH_VERACITY'): ('STEM 1', 'BSC'),
    ('-MZM-', 'TRACE_ARCHIVAL_RECORD'): ('STEM 3', 'BSC'),
    ('-MŢT-', 'PROOF_EVIDENCE'): ('STEM 2', 'BSC'),
    ('-ŇF-', 'PROBLEM_ISSUE'): ('STEM 1', 'BSC'),
    ('-ŇL-', 'SOLVE_FIGURE_OUT'): ('STEM 1', 'BSC'),
    ('-VLL-', 'IMPLICATION_EVIDENCE'): ('STEM 1', 'BSC'),
    ('-RXW-', 'NULLIFICATION_ABROGATION'): ('STEM 1', 'BSC'),
    ('-RÇN-', 'FOUNDATIONAL_PRINCIPLE'): ('STEM 1', 'BSC'),
    ('-MĻ-', 'AMBIGUITY_OBFUSCATION'): ('STEM 2', 'BSC'),
    ('-ŽV-', 'MATERIAL_BENEFIT'): ('STEM 1', 'BSC'),
    ('-ĻN-', 'VALUE_WORTH'): ('STEM 1', 'BSC'),
    ('-KP-', 'EFFORT'): ('STEM 1', 'BSC'),
    ('-FŢ-', 'EFFICIENCY'): ('STEM 1', 'BSC'),
    ('-RSN-', 'MODIFICATION'): ('STEM 1', 'BSC'),
    ('-TĻT-', 'CORRECTION'): ('STEM 3', 'BSC'),
    ('-ŘŘ-', 'IMPROVEMENT'): ('STEM 2', 'BSC'),
    ('-KŢ-', 'DEVELOPMENT_GROWTH'): ('STEM 2', 'BSC'),
    ('-ŇŘ-', 'CONSTRAINT_RESTRICTION'): ('STEM 1', 'BSC'),
    ('-RČ-', 'PHYSICAL_DAMAGE'): ('STEM 1', 'BSC'),
    ('-CPH-', 'PRESERVATION'): ('STEM 1', 'BSC'),
    ('-GTR-', 'REGULATION'): ('STEM 3', 'BSC'),
    ('-ŇŢ-', 'CORRECTNESS_ACCURACY'): ('STEM 1', 'BSC'),
    ('-ŘG-', 'CONFORMITY_NORM'): ('STEM 1', 'BSC'),
    ('-TH-', 'RELIABILITY_DURABILITY'): ('STEM 1', 'BSC'),
    ('-ŘČ-', 'FUNCTIONALITY'): ('STEM 1', 'BSC'),
    ('-ŘČ-', 'EFFICACY'): ('STEM 3', 'BSC'),
    ('-ĻN-', 'SUITABILITY'): ('STEM 3', 'BSC'),
    ('-ḐC-', 'SAFETY'): ('STEM 1', 'BSC'),
    ('-PT-', 'PHYSICAL_RISK_DANGER'): ('STEM 1', 'BSC'),
    ('-RÇL-', 'CONTINGENCY_BACKUP'): ('STEM 3', 'BSC'),
    ('-ÇMY-', 'FAILSAFE'): ('STEM 2', 'BSC'),
    ('-ÇÇK-', 'MAXIMIZATION'): ('STEM 1', 'BSC'),
    ('-ÇÇK-', 'OPTIMALITY'): ('STEM 2', 'BSC'),
    ('-ČV-', 'TOOL_INSTRUMENT'): ('STEM 1', 'BSC'),
    ('-ŢŢ-', 'TRY_OUT'): ('STEM 1', 'BSC'),
    ('-SST-', 'DEVICE_OPERATION'): ('STEM 1', 'BSC'),
    ('-KŢGW-', 'COMPUTERIZED_DEVICE'): ('STEM 1', 'BSC'),
    ('-KŢG-', 'ELECTRONIC_COMPUTER'): ('STEM 1', 'BSC'),
    ('-KŢGY-', 'COMPUTER_PROGRAM'): ('STEM 1', 'BSC'),
    ('-KŢGL-', 'AUTOMATON'): ('STEM 1', 'BSC'),
    ('-KŢGL-', 'FINITE_STATE_MACHINE'): ('STEM 3', 'BSC'),
    ('-KŢGR-', 'WRITE_CODE'): ('STEM 1', 'BSC'),
    ('-KŢGR-', 'COMPILE_INSTRUCTIONS'): ('STEM 2', 'BSC'),
    ('-KŢGR-', 'RUN_COMPUTATION'): ('STEM 3', 'BSC'),
    ('-LPĻ-', 'DIGITAL_TECHNOLOGY'): ('STEM 3', 'BSC'),
}
if len(TARGET_SENSES) != 144: raise SystemExit('TARGET_SENSES must explicitly name all 144 curriculum semantic targets')


def target_sense(root, code):
    key=(root,code)
    if key not in TARGET_SENSES:
        raise SystemExit(f'explicit source target required for {root} {code}')
    desired=TARGET_SENSES[key]
    candidates=senses_by[root]
    matches=[row for row in candidates if (row['stem'],row['specification'])==desired]
    if len(matches)!=1:
        raise SystemExit(f'expected exactly one source sense for {root} {code} at {desired}, found {len(matches)}')
    return matches[0]


GRADES={
'D':('Ontic Frames & Event Boundaries',[
('-Č-','COPULAR_IDENTITY','A.IDENTITY','Refines already-mastered identity into source-defined ontological self-sameness; the seven explicit source exclusions remain mandatory contrast cases.','type/property/event predication without using generic BE as a semantic trash can'),
('-R-','ONTIC_NEGATION','D.COPULAR_IDENTITY','Introduces source Stem-1 ontic negation as rendering an entity-state as-if nonmanifest; denial and absence remain sibling senses, and formal Boolean NOT remains unadmitted.','negative/nonmanifest states and later contrast with formal logic'),
('-ŽW-','TYPE_CLASS','A.MEMBER; D.COPULAR_IDENTITY','Introduces kind/class as distinct from identity and membership.','taxonomy, physical kinds and later sorting'),
('-ŢP-','PROPERTY_ATTRIBUTE','A.MAPS; D.TYPE_CLASS','Targets intrinsic property/trait as a reusable predicate over typed entities.','measurement and scientific properties'),
('-THW-','COMPONENT_PART','A.PARENT; A.MEMBER','Introduces source Stem-1 component/part while preserving ingredient/instruction siblings as separate meanings.','structure, assemblies and decomposition'),
('-SK-','GRAVITY_CONTAINMENT','A.MEMBER; D.COMPONENT_PART','Targets source Stem-1 containment via gravity rather than treating every containment relation as identical.','vessels, occupancy and later material flow'),
('-PS-','EVENT_OCCURRENCE','A.IDENTITY','Creates an explicit event/occurrence object over stable entity identity.','change, provenance and observation records'),
('-TĻ-','COMMENCEMENT','D.EVENT_OCCURRENCE','Adds the transition into an active event/state.','lifecycle boundaries and process activation'),
('-MPR-','TERMINATION','D.EVENT_OCCURRENCE; D.COMMENCEMENT','Pairs commencement with ending/conclusion.','process boundaries and completion'),
('-SN-','CHANGE_VARIATION','D.EVENT_OCCURRENCE; C.SUCCESSOR','Turns event identity into before/after state change while keeping numeric successor distinct.','transformation, revision and motion'),
('-ÇN-','SOURCE_ORIGIN','A.PARENT; D.EVENT_OCCURRENCE','Targets the source/origin state rather than the root family’s causal siblings.','provenance and process inputs'),
('-ŘV-','OUTCOME_RESULT','D.CHANGE_VARIATION; D.SOURCE_ORIGIN','Targets a concrete/nameable result following an event/change chain.','process outputs and causal traces'),
]),
'E':('Comparison, Scale & Ordering',[
('-ZD-','COMPARE_CONTRAST','D.TYPE_CLASS; C.NUMBER','Introduces explicit comparison/contrast over typed or numeric objects.','distinction and contrastive probes'),
('-ZD-','DISTINGUISH','E.COMPARE_CONTRAST; D.TYPE_CLASS','Targets source Stem-2 distinguishing one entity from another.','classification and later evaluation'),
('-RK-','DEGREE_EXTENT','C.NUMBER; D.PROPERTY_ATTRIBUTE','Introduces scalar degree/extent; its answer family must remain distinct from bounded counting.','measurement dimensions and graded states'),
('-ZDR-','MEASUREMENT','E.COMPARE_CONTRAST; E.DEGREE_EXTENT; D.PROPERTY_ATTRIBUTE; C.NUMBER','Targets measuring as quantifying an amount/degree of an attribute.','scientific quantities and calibration'),
('-RX-','SIMILARITY','E.COMPARE_CONTRAST','Adds resemblance without collapsing it into identity.','analogy and classification'),
('-ŘḐ-','EXACTITUDE','E.COMPARE_CONTRAST; D.COPULAR_IDENTITY','Adds degree of exactitude/equivalence to an expectation.','calibration and source fidelity'),
('-PH-','PRECISION_DEFINITION','E.EXACTITUDE; E.DEGREE_EXTENT','Adds precision/fine-grained exactness as a distinct scalar quality.','instrumentation and detailed description'),
('-RT-','SUFFICIENCY','E.DEGREE_EXTENT; D.OUTCOME_RESULT','Adds threshold sufficiency without importing correctness or efficiency.','qualification and resource thresholds'),
('-MTF-','LIST','C.COUNT; D.COMPONENT_PART','Introduces list arrangement as a cheap composition of countable members.','records and candidate sets'),
('-MTF-','SERIES_SEQUENCE','E.LIST; C.SUCCESSOR','Targets source Stem-2 sequential series/order.','ordered traces and procedures'),
('-SMY-','SORT_BY_KIND','D.TYPE_CLASS; E.DISTINGUISH; D.COMPONENT_PART','Adds sorting to find/separate a particular kind from a collection.','classification and filtering'),
('-ŘP-','UNIQUENESS','E.SIMILARITY; D.COPULAR_IDENTITY','Targets source Stem-2 degree of uniqueness rather than generic specialness.','anomaly and identity reasoning'),
]),
'F':('Action, Choice & Method',[
('-PSM-','ACTION_STEP','D.EVENT_OCCURRENCE; D.OUTCOME_RESULT','Specializes event into an action/step directed toward accomplishing something.','plans, tools and experiments'),
('-ŢK-','MAKE_FORM','F.ACTION_STEP; D.COMPONENT_PART','Adds making/constructing by integrating material resources.','fabrication and synthesis'),
('-KSF-','USE_UTILIZE','F.ACTION_STEP; D.OUTCOME_RESULT','Adds use/utilization as an action-role relation before a tool class exists.','tools and resource semantics'),
('-KŠF-','AGENCY_ENGAGEMENT','F.ACTION_STEP','Separates engagement/agency from mere event occurrence.','responsibility and control'),
('-NY-','CHOICE','E.COMPARE_CONTRAST; F.AGENCY_ENGAGEMENT','Adds choice among alternatives after comparison and agency exist.','decision policies'),
('-PŢ-','SEARCH_SEEK','D.TYPE_CLASS; F.AGENCY_ENGAGEMENT','Introduces intentional search for a specific target whose location is unknown; selection is not a constituent.','retrieval and exploration'),
('-FH-','CHANCE_DISCOVERY','D.EVENT_OCCURRENCE; D.TYPE_CLASS','Introduces finding/discovery by chance as a contrast to purposeful search, not its endpoint.','chance encounter and evidential discovery'),
('-ÇL-','PREPARATION_READINESS','F.ACTION_STEP; D.COMMENCEMENT','Adds preparation before an expected task/state.','contingency and procedures'),
('-CX-','MANNER_WAY','F.ACTION_STEP; D.PROPERTY_ATTRIBUTE','Adds manner/way as a reusable predicate over acts.','behavior and method'),
('-RCX-','METHOD_PROCEDURE','F.MANNER_WAY; F.PREPARATION_READINESS; D.OUTCOME_RESULT','Builds method/plan from action, manner, preparation and intended result.','algorithms, policies and experiments'),
('-Ž-','PHYSICAL_CAPABILITY','F.ACTION_STEP; D.OUTCOME_RESULT','Targets physical capability/ability and keeps it distinct from later aptitude or qualification.','physical skill and machinery capability'),
('-PŘ-','ACCESS_PASSAGE','D.GRAVITY_CONTAINMENT; F.ACTION_STEP','Introduces a passage/access relation before opening, penetration and channeling.','boundary crossing and channels'),
]),
'G':('Structure, Aggregation & Separation',[
('-ŢD-','PHYSICAL_CONTACT','A.IDENTITY; F.ACTION_STEP','Adds physical contact as a primitive relation between entities.','assembly and collision'),
('-ÇR-','SEPARATION','G.PHYSICAL_CONTACT; D.CHANGE_VARIATION','Introduces physical separation as a changed relation.','cutting, filtering and grouping'),
('-MC-','CONNECTION_BOND','G.PHYSICAL_CONTACT; F.ACTION_STEP','Adds concrete joining/connection while preserving abstract A.LINK as distinct.','assemblies and joints'),
('-D-','GROUP_ASSEMBLY','A.MEMBER; F.AGENCY_ENGAGEMENT','Introduces gathering/assembly before the specialized cluster relation.','collections and assemblies'),
('-CY-','CLUSTER','D.TYPE_CLASS; G.GROUP_ASSEMBLY','Specializes grouping into clumping/cluster formation.','materials and biological aggregation'),
('-RMC-','UNIFICATION','G.CONNECTION_BOND; D.COPULAR_IDENTITY','Targets source Stem-2 unifying entities into a gestalt unit.','assemblies and composition'),
('-RMC-','FUSION_MERGING','G.UNIFICATION; D.COMPONENT_PART','Targets source Stem-3 merging/coalescing where individual boundaries are lost.','materials and synthesis'),
('-JP-','ALIGNMENT','G.GROUP_ASSEMBLY; E.EXACTITUDE','Targets source Stem-3 rectilinear alignment rather than generic orientation.','mechanical organization'),
('-CḐ-','ADHESION','G.PHYSICAL_CONTACT; G.CONNECTION_BOND','Adds adhesion as a specific physical joining mechanism.','materials and biological adhesion'),
('-SJ-','COMBINE','G.UNIFICATION; D.COMPONENT_PART','Targets source Stem-1 combining separate entities to function together; stronger blending/emergence stays deferred.','mixtures and material systems'),
('-SXL-','FILTER','E.SORT_BY_KIND; G.SEPARATION','Targets physical filtration after sorting-by-kind and separation.','purification and material processing'),
('-FŠ-','PHYSICAL_FITTING','G.CONNECTION_BOND; D.GRAVITY_CONTAINMENT','Adds source Stem-1 physical fitting of one entity into/with another.','mechanical interfaces'),
]),
'H':('Boundary Change & Shape Transformation',[
('-KÇ-','CUT_FISSURE','G.SEPARATION; D.COMPONENT_PART','Introduces cutting as a localized physical separation process.','fabrication and material decomposition'),
('-SČ-','BREAK_APART','G.SEPARATION; G.GROUP_ASSEMBLY','Adds fracture/break-apart distinct from deliberate cutting.','damage and granularity'),
('-RKS-','DIVIDE_SPLIT','C.DIV; G.SEPARATION','Connects numeric division to physical splitting without equating them.','partitioning and transfer'),
('-ČN-','OPEN_MOVE_APART','G.SEPARATION; D.GRAVITY_CONTAINMENT; F.ACCESS_PASSAGE','Adds opening/moving apart to create a gap or passage.','access and flow'),
('-JŢ-','PENETRATION','G.PHYSICAL_CONTACT; D.GRAVITY_CONTAINMENT','Adds penetration through/into a surface or medium without requiring a pre-existing opening.','injection and traversal'),
('-ŇÇ-','EXTRACTION','D.GRAVITY_CONTAINMENT; G.SEPARATION','Adds extraction/removal from a containing medium.','sampling and material handling'),
('-ḐŘ-','LINEAR_STRETCH','D.CHANGE_VARIATION; E.DEGREE_EXTENT','Adds linear extent increase/stretching.','deformation'),
('-FFR-','BENDING','D.CHANGE_VARIATION; G.PHYSICAL_CONTACT','Adds bending as a distinct shape transformation; the tension-inherited near-duplicate is deferred.','deformation and mechanics'),
('-ŢŇ-','FILL','D.GRAVITY_CONTAINMENT; H.OPEN_MOVE_APART','Adds occupancy increase of a bounded region.','volume and fluid semantics'),
('-ŠḐ-','EMPTY_REMOVE','D.GRAVITY_CONTAINMENT; H.EXTRACTION','Adds occupancy decrease/removal as contrast to fill.','volume and resource transfer'),
('-XV-','COMPRESSION','E.DEGREE_EXTENT; D.CHANGE_VARIATION','Targets physical compression/compaction, not the sibling energy-storage sense.','pressure and density precursors'),
('-TÇV-','DISPERSION','G.GROUP_ASSEMBLY; D.CHANGE_VARIATION','Adds dissipating/scattering a conglomerate without making compression a constituent.','diffusion and material flow'),
]),
'I':('Manipulation & Directed Motion',[
('-G-','AMBULATION','F.ACTION_STEP; D.CHANGE_VARIATION','Introduces source-defined bodily translative motion before specialized directed motions.','motion worlds and trajectory probes'),
('-PD-','MANIPULATE_GRASP','F.ACTION_STEP; G.PHYSICAL_CONTACT','Adds direct object manipulation/grasping.','tool use and physical actions'),
('-GF-','BIND_RESTRAIN','G.CONNECTION_BOND; H.OPEN_MOVE_APART','Adds durable holding/binding/restraint.','constraints and mechanics'),
('-TV-','SUPPORT_BEAR','D.COMPONENT_PART; G.PHYSICAL_CONTACT','Adds support/bearing before explicit force equations.','structures and mechanics'),
('-RG-','MOBILITY_MOTILITY','E.DEGREE_EXTENT; D.CHANGE_VARIATION','Targets source Stem-2 degree of mobility/motility: ability to move or be made to move, with no hidden energy semantic.','kinematic capability and later mechanics'),
('-XP-','TRANSPOSITION_INTERCHANGE','I.AMBULATION; D.CHANGE_VARIATION','Targets source Stem-2 transposition/interchange: switching places inside the already-open spatial world.','relative position and permutation-like motion'),
('-PĻ-','TURN','D.CHANGE_VARIATION; I.MANIPULATE_GRASP','Adds arc-like orientation change.','rotation and steering'),
('-RPĻ-','ROTATE_SPIN','I.TURN','Targets self-axis spinning/revolving; orbit remains a sibling sense.','angular motion'),
('-ČPH-','STRIKE_IMPACT','I.MANIPULATE_GRASP; G.PHYSICAL_CONTACT','Adds impulsive contact.','collision and tool use'),
('-ŽN-','PUSH','I.STRIKE_IMPACT; D.EVENT_OCCURRENCE','Adds pushing/directed impulse.','force and motion'),
('-ÇV-','PULL_TRACTION','I.PUSH','Pairs pushing with traction/pulling.','force contrast'),
('-FJ-','IMPEDE_BLOCK','I.PUSH; F.METHOD_PROCEDURE','Adds impeding/blocking a path or activity.','constraints and later control'),
]),
'J':('Flow, Passage & Material State',[
('-BN-','CHANNEL','F.ACCESS_PASSAGE; I.PUSH; I.PULL_TRACTION','Targets source Stem-1 channeling translative course through a conduit.','flow routing and control'),
('-LŢR-','DRAINAGE','H.EMPTY_REMOVE; J.CHANNEL','Targets gravity drainage as directed fluid removal.','fluid systems'),
('-ZŢ-','ABSORPTION','D.GRAVITY_CONTAINMENT; G.PHYSICAL_CONTACT','Targets source Stem-1 uptake of liquid into porous material; imbuement/infiltration remain siblings.','materials and biology/chemistry precursors'),
('-RZŢ-','DIFFUSION_PERMEATION','J.ABSORPTION; H.DISPERSION','Targets source Stem-2 diffusion/suffusion/permeation.','diffusion and chemistry/biology'),
('-MBW-','SUCTION','J.DRAINAGE; I.PULL_TRACTION','Targets source Stem-2 suction rather than oral sucking.','pressure-driven flow'),
('-MBW-','PUMPING','J.SUCTION; J.DRAINAGE','Targets source Stem-3 mechanical liquid/gas pumping for transfer/storage/drainage.','fluid transport'),
('-ŠŇ-','INFLATION','H.FILL; D.GRAVITY_CONTAINMENT','Targets gas inflation; pressurization and ventilation remain sibling senses.','gas/flow systems'),
('-ŇM-','SURFACE_APPLICATION','G.PHYSICAL_CONTACT; D.PROPERTY_ATTRIBUTE','Adds spreading/overlaying material on a surface.','coatings and interfaces'),
('-FŢR-','RINSE','J.DRAINAGE; J.SURFACE_APPLICATION','Targets source Stem-1 rinsing only; drying/evaporation remain separate sibling candidates.','cleaning and material flow'),
('-ZW-','CLEANLINESS','G.FILTER; J.RINSE','Targets source Stem-1 cleanliness, not the sibling purity/decontamination or hygiene senses.','sanitation and contamination contrasts'),
('-GŢ-','PHYSICAL_COMPATIBILITY','G.PHYSICAL_FITTING; G.CONNECTION_BOND','Targets source Stem-3 physical compatibility of entities that function better as a unit.','mechanical interfaces'),
('-RFJ-','CONSTRICTION','J.CHANNEL; I.IMPEDE_BLOCK','Targets source Stem-1 flow constriction/choking; sealing and prevention remain sibling senses.','flow control and later safety'),
]),
'K':('Observation, Knowledge & Experiment',[
('-CT-','EXAMINE','F.ACTION_STEP; D.PROPERTY_ATTRIBUTE','Targets source Stem-2 examination of an entity to determine condition/characteristics.','observation and diagnostics'),
('-RCT-','OBSERVE','K.EXAMINE; D.EVENT_OCCURRENCE','Adds close observation as an evidential event.','provenance and sensing'),
('-ŇŢT-','EVALUATION_VETTING','K.OBSERVE; E.SUFFICIENCY','Targets source Stem-2 vetting/evaluation against a standard.','qualification and assessment'),
('-MZ-','MEMORY_RECALL','K.OBSERVE; D.EVENT_OCCURRENCE','Adds retained/recalled content after observations exist.','learning and longitudinal evidence'),
('-VL-','UNDERSTANDING_COMPREHENSION','K.OBSERVE; K.MEMORY_RECALL','Targets source Stem-2 analytic understanding/comprehension.','reasoning and transfer'),
('-ŢT-','FACT_KNOW','K.UNDERSTANDING_COMPREHENSION; K.MEMORY_RECALL; K.OBSERVE','Introduces source-defined knowing an ontological fact only after understanding and recall exist.','epistemic state and grounding'),
('-RŢT-','LEARN_KNOWLEDGE_SOURCE','K.FACT_KNOW; F.SEARCH_SEEK','Distinguishes learning/study and knowledge source from already-knowing.','curriculum and evidence acquisition'),
('-CC-','ERROR_MISCONCEPTION','K.EVALUATION_VETTING; K.FACT_KNOW','Makes error/misconception explicit rather than a generic low score.','repair and diagnostics'),
('-LČ-','ASSUMPTION_PRESUMPTION','K.FACT_KNOW; K.EVALUATION_VETTING','Adds conjectural belief reached without sufficient evidence.','uncertainty'),
('-LČW-','HYPOTHESIS','K.ASSUMPTION_PRESUMPTION; K.OBSERVE','Targets source Stem-3 hypothesizing after assumption and observation are distinct.','experimental science and prediction'),
('-ŇŢT-','EXPERIMENT_HYPOTHESIS_TEST','K.HYPOTHESIS; K.EVALUATION_VETTING; K.OBSERVE','Targets source Stem-3 experiment/test used to evaluate a hypothesis or detect a condition.','experimental science'),
('-MŢT-','DEMONSTRATION_VERIFICATION','K.EXPERIMENT_HYPOTHESIS_TEST; K.FACT_KNOW','Targets source Stem-1 demonstration/verification of factuality.','evidence and later proof'),
]),
'L':('Reasoning, Evidence & Formal Objects',[
('-NŢT-','SUBJECT_TOPIC','K.FACT_KNOW','Makes topic/subject matter explicit as an object of reasoning.','arguments and explanations'),
('-MÇT-','EXAMPLE','K.FACT_KNOW; D.TYPE_CLASS','Adds example/exemplar relation over classes and facts.','teaching and generalization'),
('-TKH-','RULE_PRECEPT','K.FACT_KNOW; F.METHOD_PROCEDURE','Introduces rule/precept as an object distinct from one observed fact or procedure.','deduction and algorithms'),
('-RD-','TRUTH_VERACITY','K.FACT_KNOW; K.EVALUATION_VETTING; B.IFF','Targets source Stem-1 graded ontological truth/veracity; authenticity and representational validity remain siblings.','epistemic commitment'),
('-MZM-','TRACE_ARCHIVAL_RECORD','K.OBSERVE; K.MEMORY_RECALL','Targets source Stem-3 making/having an archival record as a provenance object.','audit trails and evidence persistence'),
('-MŢT-','PROOF_EVIDENCE','L.RULE_PRECEPT; K.DEMONSTRATION_VERIFICATION','Targets source Stem-2 presenting evidence that attempts to prove something, distinct from K verification.','formal evidence and proof standards'),
('-ŇF-','PROBLEM_ISSUE','K.ERROR_MISCONCEPTION; F.ACTION_STEP','Represents a recognized unresolved problem/issue.','search and planning'),
('-ŇL-','SOLVE_FIGURE_OUT','L.PROBLEM_ISSUE; K.UNDERSTANDING_COMPREHENSION','Targets the source BSC attempt/process of solving; successful completion remains a CPT distinction.','reasoning loops'),
('-VLL-','IMPLICATION_EVIDENCE','L.RULE_PRECEPT; D.SOURCE_ORIGIN; D.OUTCOME_RESULT','Targets evidential implication/hint, explicitly not Boolean implication.','arguments and inference'),
('-RXW-','NULLIFICATION_ABROGATION','D.ONTIC_NEGATION; L.RULE_PRECEPT','Targets source Stem-1 nullification/abrogation; formal contradiction remains a future sibling because live B.NOT is absent.','rule invalidation and cancellation'),
('-RÇN-','FOUNDATIONAL_PRINCIPLE','L.RULE_PRECEPT; D.SOURCE_ORIGIN','Adds basic element/foundational principle over rules and structures.','theories and dependency explanations'),
('-MĻ-','AMBIGUITY_OBFUSCATION','K.UNDERSTANDING_COMPREHENSION; E.DISTINGUISH','Targets source Stem-2 ambiguity/obfuscation after comprehension and distinction exist.','interpretation, uncertainty and later language codec'),
]),
'M':('Value, Change & Control',[
('-ŽV-','MATERIAL_BENEFIT','D.OUTCOME_RESULT; E.COMPARE_CONTRAST','Targets material/contextual goodness/benefit as an explicit evaluative criterion.','improvement and operational judgment'),
('-ĻN-','VALUE_WORTH','M.MATERIAL_BENEFIT; D.OUTCOME_RESULT','Targets source Stem-1 worthwhile/value as a criterion distinct from moral goodness.','tradeoffs and prioritization'),
('-KP-','EFFORT','F.ACTION_STEP; E.DEGREE_EXTENT','Adds graded physical/mental effort before efficiency or difficulty.','cost and workload'),
('-FŢ-','EFFICIENCY','M.EFFORT; D.OUTCOME_RESULT; E.MEASUREMENT','Targets efficiency as resource/effort-to-result relation only after effort and outcomes exist.','optimization and resource economics'),
('-RSN-','MODIFICATION','D.CHANGE_VARIATION; F.ACTION_STEP','Adds intentional alteration/modification.','repair and optimization'),
('-TĻT-','CORRECTION','K.ERROR_MISCONCEPTION; M.MODIFICATION','Targets source Stem-3 correction from an incorrect state to a correct one.','self-correction'),
('-ŘŘ-','IMPROVEMENT','M.MATERIAL_BENEFIT; M.VALUE_WORTH; M.MODIFICATION','Targets source Stem-2 amelioration/improvement relative to explicit value criteria.','optimization'),
('-KŢ-','DEVELOPMENT_GROWTH','D.CHANGE_VARIATION; M.IMPROVEMENT','Targets source Stem-2 goal-oriented development/maturation/growth.','learning and lifecycle trajectories'),
('-ŇŘ-','CONSTRAINT_RESTRICTION','F.METHOD_PROCEDURE; I.IMPEDE_BLOCK','Makes limiting/restricting conditions explicit over methods/actions.','planning and optimization'),
('-RČ-','PHYSICAL_DAMAGE','H.BREAK_APART; D.CHANGE_VARIATION','Targets source Stem-1 physical damage as an adverse state primitive before risk and preservation.','safety, repair and preservation'),
('-CPH-','PRESERVATION','M.PHYSICAL_DAMAGE; D.CHANGE_VARIATION','Adds preserving/saving against decay/damage, not memory retention.','maintenance and resilience'),
('-GTR-','REGULATION','L.RULE_PRECEPT; M.CONSTRAINT_RESTRICTION; F.AGENCY_ENGAGEMENT','Targets source Stem-3 regulation: authority to make rules for oversight/functioning.','governance and feedback control'),
]),
'N':('Operational Evaluation & Resilience',[
('-ŇŢ-','CORRECTNESS_ACCURACY','K.EVALUATION_VETTING; E.EXACTITUDE','Adds correctness/accuracy against explicit evaluation rather than pretending it is primitive.','tests and repair'),
('-ŘG-','CONFORMITY_NORM','L.RULE_PRECEPT; D.TYPE_CLASS','Adds degree of conformity to a norm/standard only after rules exist.','qualification and anomaly detection'),
('-TH-','RELIABILITY_DURABILITY','M.PRESERVATION; E.DEGREE_EXTENT','Targets source Stem-1 reliability/quality as ruggedness/durability of workmanship.','systems dependability'),
('-ŘČ-','FUNCTIONALITY','F.USE_UTILIZE; N.CORRECTNESS_ACCURACY','Targets source Stem-1 operational functionality/working order.','machines and software'),
('-ŘČ-','EFFICACY','N.FUNCTIONALITY; D.OUTCOME_RESULT; M.EFFICIENCY','Targets source Stem-3 degree to which an operation achieves what it is supposed to.','performance evaluation'),
('-ĻN-','SUITABILITY','N.EFFICACY; D.TYPE_CLASS','Targets source Stem-3 fitting/apropos/suitable as an operational judgment.','selection and planning'),
('-ḐC-','SAFETY','M.PHYSICAL_DAMAGE; M.REGULATION','Targets source Stem-1 making something safe by removing threats of harm; securing/locking remain sibling senses.','risk, contingency and guarded systems'),
('-PT-','PHYSICAL_RISK_DANGER','K.HYPOTHESIS; M.PHYSICAL_DAMAGE; N.SAFETY','Targets prospective physical harm/danger after uncertainty, harm and safety are explicit.','safety planning'),
('-RÇL-','CONTINGENCY_BACKUP','F.PREPARATION_READINESS; M.CONSTRAINT_RESTRICTION; N.PHYSICAL_RISK_DANGER','Targets source Stem-3 contingency/back-up measure, breaking the old risk↔contingency cycle.','robust systems'),
('-ÇMY-','FAILSAFE','N.CONTINGENCY_BACKUP; G.CONNECTION_BOND','Adds protective intermediary/fail-safe relation after contingency exists.','fault tolerance'),
('-ÇÇK-','MAXIMIZATION','E.DEGREE_EXTENT; M.VALUE_WORTH','Targets source Stem-1 maximum point/state under an explicit criterion.','search and optimization'),
('-ÇÇK-','OPTIMALITY','N.MAXIMIZATION; M.EFFICIENCY; N.SUITABILITY','Targets source Stem-2 optimal point/state after value, efficiency and suitability exist.','optimization and decision policy'),
]),
'O':('Tools, Machines & Computation',[
('-ČV-','TOOL_INSTRUMENT','F.USE_UTILIZE; I.MANIPULATE_GRASP','Introduces a tool/instrument as extension of bodily appendage/sense.','devices and laboratory work'),
('-ŢŢ-','TRY_OUT','K.EVALUATION_VETTING; O.TOOL_INSTRUMENT','Adds trying out a tool/device/machine to evaluate operation; wearable/clothing uses remain excluded by source.','experimentation and engineering'),
('-SST-','DEVICE_OPERATION','O.TOOL_INSTRUMENT; N.FUNCTIONALITY','Targets source Stem-1 mechanical device/apparatus functioning.','machine concepts'),
('-KŢG-','ELECTRONIC_COMPUTER','O.DEVICE_OPERATION; E.LIST; E.SERIES_SEQUENCE','Targets source Stem-1 personal electronic computing device as an artifact class; internal computation semantics are taught later in the grade.','program execution and digital systems'),
('-KŢGY-','COMPUTER_PROGRAM','O.ELECTRONIC_COMPUTER; L.RULE_PRECEPT; F.METHOD_PROCEDURE','Targets source Stem-1 computer program/application/software.','software semantics'),
('-KŢGL-','AUTOMATON','O.COMPUTER_PROGRAM; D.CHANGE_VARIATION','Introduces automatic computing device/automaton as an abstract computational machine.','state-machine reasoning'),
('-KŢGL-','FINITE_STATE_MACHINE','O.AUTOMATON; E.SERIES_SEQUENCE; D.CHANGE_VARIATION','Targets source Stem-3 finite-state machine/automaton.','formal computation and state transitions'),
('-KŢGR-','WRITE_CODE','O.COMPUTER_PROGRAM; L.RULE_PRECEPT','Targets source Stem-1 producing a computer-implementable instruction/line of code.','program construction'),
('-KŢGR-','COMPILE_INSTRUCTIONS','O.WRITE_CODE; O.COMPUTER_PROGRAM','Targets source Stem-2 transformation/compilation of instructions/text into another executable format.','translation and compilation'),
('-KŢGR-','RUN_COMPUTATION','O.COMPILE_INSTRUCTIONS; O.FINITE_STATE_MACHINE','Targets source Stem-3 computation / implementing-running a computer program.','executable computation'),
('-KŢGW-','COMPUTERIZED_DEVICE','O.RUN_COMPUTATION; O.DEVICE_OPERATION','Targets an algorithmically controlled device only after program execution/computation is explicit, eliminating the former hidden-computation prerequisite.','embedded and controlled devices'),
('-LPĻ-','DIGITAL_TECHNOLOGY','O.RUN_COMPUTATION; O.ELECTRONIC_COMPUTER','Targets source Stem-3 doing something using digital/electronic/cyber technology.','later software/tool codecs and agent operations'),
]),
}

# Fix informal prereq placeholders that should not leak into rows.
for g,(theme,items) in GRADES.items():
    for i,(root,code,req,why,unlock) in enumerate(items):
        req=req.replace('; M?','').replace('; SP?','; O.NEWNESS')
        items[i]=(root,code,req,why,unlock)

RESERVE='''-S- -T- -LŢT- -ŘŢT- -PŢR- -GŠ- -GŠT- -ŇÇL- -CPR- -ŘK- -ŘKW- -LŽV- -GT- -TĻP- -ŢPH- -ÇD- -RŇF- -ŠY- -ZJ- -RĻN- -MÇ- -MÇK- -ŢJ- -KH- -ŇČ- -RŇČ- -ČPĻ- -LDR- -LXL- -ŢRR- -PP- -RPP- -LPP- -LÇM- -PPŠ- -ZKR- -ZC- -ẒF- -JJ- -CGV- -TKF- -LTKF- -MZK- -ŘN- -LŘ- -ĻX- -ZN- -RTV- -DBW- -DKH- -LXR- -RÇV- -ŽR- -ŢS- -RŢS- -SXR- -VZD- -ŠNY- -ŢB- -VPW- -VTĻ- -LŢV- -DGR- -FŠŘ- -LZDR- -NZDR- -ZZDR- -ŘZDR- -VPÇ- -ŽDV- -BKH- -KŠŇ- -LČF- -ŠPH- -LÇF- -RČV- -ĻTH- -NZH- -FSM- -JDY- -RBB- -ČM- -RNY- -RSJ- -ŘḐŘ- -CŘ- -TVY- -ÇDR- -ŠH- -ḐJ- -ŠT- -RŠT- -LLT- -RC- -MH- -MJ-'''.split()

GRADE_RATIONALE={
'D':('Refine identity into source-grounded ontic distinctions, then add event boundaries and source/result.','A graph relations; reduced B release (AND/IFF/COMPOSITE/IDBOOLOPS); C basic numeric successor.','E comparison/measurement; later causation/time; typed event records.'),
'E':('Turn C numeracy and D properties into comparison, scalar degree, measurement and explicit ordered collections before evaluative quality judgments.','D type/property/event semantics plus C number/successor.','Scientific measurement, sorting, list/series structures and later evaluation.'),
'F':('Introduce purposeful action, choice, search, preparation, method and physical capability before concrete process families.','D events/outcomes; E comparison/order; A/B/C foundations.','Tools, experiments, planning and agentive physical actions.'),
'G':('Learn reusable structural relations among entities before transforming them.','D part/containment; E sorting/exactness; F action.','Assemblies, material organization, filtering and later chemistry.'),
'H':('Learn transformations that alter boundaries, occupancy, shape and extent.','G structure/separation; D change/containment; C division.','Mechanics, material processing, pressure and flow.'),
'I':('Introduce a deliberate spatial/kinematic modality: bodily/object manipulation, mobility, transposition, rotation, impact, push/pull and blocking without importing an untaught energy primitive.','F action/method; G contact/connection; H transformations.','Motion worlds, force precursors and flow routing.'),
'J':('Compose containment, motion and transformation into source-specific material-flow processes.','G/H/I plus E scalar distinctions.','Fluid systems, diffusion, sanitation and physical compatibility.'),
'K':('Build epistemics bottom-up from examination and observation through evaluation, recall, comprehension, knowing, assumption, hypothesis, experiment and verification.','D–J finite worlds; E sufficiency; reduced B logic.','Science, evidence provenance and reproducible experimentation.'),
'L':('Reify reasoning objects: topics, examples, rules, truth, archival traces, proof evidence, problems, implication, nullification, foundations and ambiguity.','K epistemics/evidence; B logic; D types/provenance.','Formal reasoning, auditability, explanations and later language codec.'),
'M':('Add explicit value criteria before improvement, then introduce effort/efficiency, modification/correction, damage/preservation, constraints and regulation.','F method/action; K error; L rules; E measurement.','Robust systems, development, maintenance and control.'),
'N':('Build operational judgment and resilience without smuggling in unlearned time/energy semantics: correctness, conformity, reliability, functionality, efficacy, suitability, safety, risk, contingency, fail-safe and optimization.','K evaluation/hypothesis; M value/damage/regulation; E scalar measures.','Qualification, guarded systems, robust planning and optimization.'),
'O':('Close the tranche with a compositional computing ladder from tool and device through computerized device, computer, program, automaton/FSM, code, compilation, execution and digital technology.','F use/method; K evaluation; L rules; N functionality; E ordered structures.','Software reasoning, state machines, later code/language codecs and agent tools.'),
}

GRADE_WORLD_STATE={
    'D':'typed entities plus minimal event before/after state; no hidden generic BE predicate',
    'E':'typed entities/properties plus bounded numeric/scalar comparisons and small ordered collections',
    'F':'one agent, one action/event, candidate/target entities and an intended result',
    'G':'two or more persistent physical entities with contact/junction/group membership state',
    'H':'a bounded material/entity state with explicit before/after boundary, occupancy, shape or extent',
    'I':'a minimal spatial/kinematic scene with actor/object and explicit relative direction/orientation state',
    'J':'a container/medium/path plus material or fluid whose location/distribution changes',
    'K':'an observable fixture plus evidence/record state and an evaluator/knower role',
    'L':'explicit proposition/rule/evidence/record objects with provenance links',
    'M':'an action/system state plus declared criterion/value, result, constraint or damage state',
    'N':'an operation/system state plus measurable criterion, expected result and harm/safety alternatives',
    'O':'typed tool/device/computer/program/state-machine artifacts plus executable transition/instruction trace',
}

ANSWER_FAMILY_BY_GRADE={
    'D':'RELATION_EVENT_CLASS',
    'E':'SCALAR_OR_ORDERED_STRUCTURE',
    'F':'ACTION_ROLE_OR_SELECTION',
    'G':'STRUCTURAL_RELATION',
    'H':'MATERIAL_STATE_TRANSITION',
    'I':'SPATIAL_KINEMATIC_TRANSITION',
    'J':'MATERIAL_FLOW_PROCESS',
    'K':'EVIDENCE_EPISTEMIC_STATE',
    'L':'PROPOSITION_EVIDENCE_OBJECT',
    'M':'EVALUATIVE_CHANGE_CONTROL',
    'N':'OPERATIONAL_JUDGMENT_RESILIENCE',
    'O':'ARTIFACT_PROGRAM_STATE_MACHINE',
}

ANSWER_FAMILY_OVERRIDES={
    'E.DEGREE_EXTENT':'SCALAR_DEGREE',
    'E.MEASUREMENT':'SCALAR_MEASUREMENT',
    'E.EXACTITUDE':'SCALAR_DEGREE',
    'E.PRECISION_DEFINITION':'SCALAR_DEGREE',
    'E.SUFFICIENCY':'THRESHOLD_JUDGMENT',
    'E.LIST':'ORDERED_COLLECTION',
    'E.SERIES_SEQUENCE':'ORDERED_COLLECTION',
    'E.SORT_BY_KIND':'COLLECTION_PARTITION',
    'N.CORRECTNESS_ACCURACY':'SCALAR_DEGREE',
    'N.CONFORMITY_NORM':'SCALAR_DEGREE',
    'N.RELIABILITY_DURABILITY':'SCALAR_DEGREE',
    'N.FUNCTIONALITY':'SCALAR_DEGREE',
    'N.EFFICACY':'SCALAR_DEGREE',
    'N.SUITABILITY':'SCALAR_DEGREE',
    'N.MAXIMIZATION':'EXTREMUM_JUDGMENT',
    'N.OPTIMALITY':'EXTREMUM_JUDGMENT',
    'O.FINITE_STATE_MACHINE':'STATE_TRANSITION_OBJECT',
    'O.WRITE_CODE':'PROGRAM_INSTRUCTION_OBJECT',
    'O.COMPILE_INSTRUCTIONS':'PROGRAM_TRANSFORMATION',
    'O.RUN_COMPUTATION':'EXECUTION_TRACE',
}

MODALITY_GATES={
    'D.COPULAR_IDENTITY':'introduces source-grounded ontic/class/event relational scenes beyond A graph labels',
    'E.DEGREE_EXTENT':'introduces scalar-degree answers distinct from bounded counts',
    'E.LIST':'introduces ordered-collection answers',
    'F.ACTION_STEP':'introduces agent/action/result role scenes',
    'I.AMBULATION':'introduces explicit spatial/kinematic world-state',
    'K.EXAMINE':'introduces evidence/observer role state',
    'L.SUBJECT_TOPIC':'introduces proposition/reasoning-object state',
    'M.MATERIAL_BENEFIT':'introduces declared evaluative criteria',
    'N.PHYSICAL_RISK_DANGER':'introduces prospective alternative/harm judgment',
    'O.COMPUTER_PROGRAM':'introduces program artifact state',
    'O.FINITE_STATE_MACHINE':'introduces explicit state-machine transition structure',
}

core=[]
for grade,(theme,items) in GRADES.items():
    if len(items)!=12: raise SystemExit(f'{grade} has {len(items)} items')
    for pos,(root,code,req,why,unlock) in enumerate(items,1):
        if root not in roots: raise SystemExit(f'missing root {root}')
        core.append((grade,pos,theme,root,code,req,why,unlock))
if len(core)!=144 or len({(x[0],x[4]) for x in core})!=144: raise SystemExit('core must contain 144 unique grade/capability targets')
if len(RESERVE)!=96 or len(set(RESERVE))!=96: raise SystemExit('reserve must be 96 unique roots')
if set(RESERVE)&{x[3] for x in core}: raise SystemExit('core/reserve overlap')
for root in RESERVE:
    if root not in roots: raise SystemExit(f'missing reserve root {root}')

# Candidate pool: 144 core + 96 deliberately selected next-frontier reserve.
rows=[]
for grade,pos,theme,root,code,req,why,unlock in core:
    r=roots[root]; anchors=anchor_rows(root); target=target_sense(root,code)
    capability=f'{grade}.{code}'
    answer_family=ANSWER_FAMILY_OVERRIDES.get(capability,ANSWER_FAMILY_BY_GRADE[grade])
    rows.append({
        'candidate_id':f'{grade}-{pos:02d}', 'priority_tier':'CORE_D_O', 'proposed_grade':grade,
        'grade_position':str(pos), 'grade_theme':theme, 'working_capability':f'{grade}.{code}',
        'root_form':root, 'root_gloss':r['root_gloss'], 'lexicon_root_id':r['lexicon_root_id'],
        'chapter':r['lexicon_chapter'], 'section':r['lexicon_section'], 'printed_page':r['source_printed_page'],
        'sense_count':str(len(senses_by[root])),
        'target_sense_id':target['lexicon_sense_id'], 'target_stem':target['stem'],
        'target_specification':target['specification'], 'target_source_sense':target['sense_summary'],
        'target_source_example':target.get('source_example_excerpt',''),
        'source_evidence_ids':' | '.join(row['lexicon_evidence_id'] for row in evidence_by[root]),
        'source_evidence_kinds':' | '.join(sorted({row['evidence_kind'] for row in evidence_by[root]})),
        'answer_family':answer_family,
        'minimal_world_state':GRADE_WORLD_STATE[grade],
        'modality_gate':MODALITY_GATES.get(capability,''),
        'intro_source_sense':intro_sense(root),
        'contrast_source_sense':contrast_sense(root), 'existing_abi_anchors':' | '.join(anchors),
        'prerequisites':req, 'why_now':why, 'downstream_unlocks':unlock,
        'neural_vs_codec':'NEURAL_SEMANTIC: source-root meaning changes world/model interpretation; surface realization remains a later codec.',
        'source_readiness':'SOURCE_PARSED_NOT_ADMITTED', 'confidence':'PROVISIONAL_HIGH' if grade in 'DEFG' else 'PROVISIONAL',
        'disposition':'PROPOSED_NOT_ADMITTED',
    })
for idx,root in enumerate(RESERVE,1):
    r=roots[root]; anchors=anchor_rows(root)
    # Reserve categories retain useful guidance without pretending the next grade is known.
    if r['lexicon_section'] in {'1.1','1.2'}:
        window='P+ REFERENCE/CODEC BRIDGE'
    elif r['lexicon_section']=='2.0':
        window='P+ ABSTRACT/AGENTIC RESERVE'
    elif r['lexicon_section']=='2.1.1':
        window='P+ PHYSICAL PROCESS RESERVE'
    else:
        window='P+ MECHANISM/MEASUREMENT RESERVE'
    rows.append({
        'candidate_id':f'R-{idx:03d}', 'priority_tier':'NEXT_96', 'proposed_grade':'', 'grade_position':'',
        'grade_theme':window, 'working_capability':'', 'root_form':root, 'root_gloss':r['root_gloss'],
        'lexicon_root_id':r['lexicon_root_id'], 'chapter':r['lexicon_chapter'], 'section':r['lexicon_section'],
        'printed_page':r['source_printed_page'], 'sense_count':str(len(senses_by[root])),
        'target_sense_id':'', 'target_stem':'', 'target_specification':'',
        'target_source_sense':'', 'target_source_example':'',
        'source_evidence_ids':' | '.join(row['lexicon_evidence_id'] for row in evidence_by[root]),
        'source_evidence_kinds':' | '.join(sorted({row['evidence_kind'] for row in evidence_by[root]})),
        'answer_family':'TO_BE_RESOLVED_AT_SELECTION',
        'minimal_world_state':'TO_BE_RESOLVED_AT_SELECTION',
        'modality_gate':'',
        'intro_source_sense':intro_sense(root), 'contrast_source_sense':contrast_sense(root),
        'existing_abi_anchors':' | '.join(anchors), 'prerequisites':'TO_BE_RESOLVED_FROM_MASTERED_CLOSURE',
        'why_now':'High-utility Chapter-1/2 reserve retained so D–O revisions and the next frontier do not require rescanning the source corpus.',
        'downstream_unlocks':window, 'neural_vs_codec':'REVIEW_AT_SELECTION: source meaning preserved now; neural-vs-codec necessity decided only when it reaches the live frontier.',
        'source_readiness':'SOURCE_PARSED_NOT_ADMITTED', 'confidence':'RESERVE', 'disposition':'CANDIDATE_RESERVE',
    })

# Entire source inventory allows later researchers to reproduce why 263 were not in the 240-candidate near-term set.
selected={r['root_form'] for r in rows}
source_inventory=[]
for root,r in roots.items():
    source_inventory.append({
      **r,
      'near_term_disposition':('CORE_D_O' if root in {x[3] for x in core} else 'NEXT_96' if root in set(RESERVE) else 'DEFERRED_SOURCE_ROOT'),
      'sense_count':str(len(senses_by[root])), 'intro_source_sense':intro_sense(root), 'existing_abi_anchors':' | '.join(anchor_rows(root)),
    })
source_inventory.sort(key=lambda r:(int(r['lexicon_chapter']),int(r['source_printed_page'] or 0),r['root_form_raw']))

# Deferred grammatical/codec roots are listed separately because Chapter 1 is source-important but not an early text-model capability block.
deferred_codec=[]
for root,r in roots.items():
    if r['lexicon_section']=='1.4':
        deferred_codec.append({
          'root_form':root,'root_gloss':r['root_gloss'],'printed_page':r['source_printed_page'],
          'reason':'DEFERRED_CODEC_METALINGUISTIC: source-faithful and important for later New Ithkuil grammar/codec learning, but does not beat world-semantic Chapter-2 primitives for D–O neural utility.',
          'lexicon_root_id':r['lexicon_root_id'],
        })

fields=list(rows[0])
with open(OUT/'candidate_pool.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader(); w.writerows(rows)
with open(OUT/'grade_map.csv','w',newline='',encoding='utf-8') as f:
    flds=['grade','position','theme','working_capability','root_form','root_gloss','section','printed_page',
          'target_sense_id','target_stem','target_specification','target_source_sense','target_source_example',
          'source_evidence_ids','source_evidence_kinds',
          'sibling_sense_count','answer_family','minimal_world_state','modality_gate',
          'prerequisites','why_now','downstream_unlocks','existing_abi_anchors','status']
    w=csv.DictWriter(f,fieldnames=flds,lineterminator='\n'); w.writeheader()
    for grade,pos,theme,root,code,req,why,unlock in core:
        r=roots[root]; target=target_sense(root,code)
        capability=f'{grade}.{code}'
        w.writerow({'grade':grade,'position':pos,'theme':theme,'working_capability':f'{grade}.{code}',
                    'root_form':root,'root_gloss':r['root_gloss'],'section':r['lexicon_section'],
                    'printed_page':r['source_printed_page'],'target_sense_id':target['lexicon_sense_id'],
                    'target_stem':target['stem'],'target_specification':target['specification'],
                    'target_source_sense':target['sense_summary'],
                    'target_source_example':target.get('source_example_excerpt',''),
                    'source_evidence_ids':' | '.join(row['lexicon_evidence_id'] for row in evidence_by[root]),
                    'source_evidence_kinds':' | '.join(sorted({row['evidence_kind'] for row in evidence_by[root]})),
                    'sibling_sense_count':len(senses_by[root])-1,
                    'answer_family':ANSWER_FAMILY_OVERRIDES.get(capability,ANSWER_FAMILY_BY_GRADE[grade]),
                    'minimal_world_state':GRADE_WORLD_STATE[grade],
                    'modality_gate':MODALITY_GATES.get(capability,''),
                    'prerequisites':req,'why_now':why,
                    'downstream_unlocks':unlock,'existing_abi_anchors':' | '.join(anchor_rows(root)),
                    'status':'PROPOSED_NOT_ADMITTED'})

# Sense-level candidate surface.  This is the actual semantic inventory used
# for later adjudication; the 240-row candidate_pool.csv is only a root-family
# shortlist.  Multiple materially distinct senses from the same root therefore
# remain visible instead of being collapsed into one English label.
selected_targets={target_sense(x[3],x[4])['lexicon_sense_id']:f"{x[0]}.{x[4]}" for x in core}
root_disposition={r['root_form']:r['priority_tier'] for r in rows}
sense_candidates=[]
for sense in senses:
    root=sense['root_form_raw']
    sense_candidates.append({
        'lexicon_sense_id':sense['lexicon_sense_id'],
        'lexicon_root_id':sense['lexicon_root_id'],
        'root_form':root,
        'root_gloss':roots[root]['root_gloss'],
        'stem':sense['stem'],
        'specification':sense['specification'],
        'sense_summary':sense['sense_summary'],
        'source_example_excerpt':sense.get('source_example_excerpt',''),
        'source_text_sha256':sense.get('source_text_sha256',''),
        'source_text_char_count':sense.get('source_text_char_count',''),
        'chapter':sense['lexicon_chapter'],
        'section':sense['lexicon_section'],
        'printed_page':sense['source_printed_page'],
        'root_family_disposition':root_disposition.get(root,'DEFERRED_SOURCE_ROOT'),
        'selected_target_capability':selected_targets.get(sense['lexicon_sense_id'],''),
        'semantic_disposition':('PROPOSED_D_O_TARGET' if sense['lexicon_sense_id'] in selected_targets
                                else 'VISIBLE_SIBLING_OR_FUTURE_CANDIDATE'),
    })
with open(OUT/'sense_candidate_pool.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(sense_candidates[0]),lineterminator='\n')
    w.writeheader(); w.writerows(sense_candidates)
with open(OUT/'source_inventory.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(source_inventory[0]),lineterminator='\n'); w.writeheader(); w.writerows(source_inventory)
with open(OUT/'deferred_codec.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(deferred_codec[0]),lineterminator='\n'); w.writeheader(); w.writerows(deferred_codec)
with open(OUT/'grade_rationale.csv','w',newline='',encoding='utf-8') as f:
    flds=['grade','theme','root_count','why_now','hard_prerequisite_plane','unlocks','status']
    w=csv.DictWriter(f,fieldnames=flds,lineterminator='\n'); w.writeheader()
    for g,(why,pre,unlock) in GRADE_RATIONALE.items():
        w.writerow({'grade':g,'theme':GRADES[g][0],'root_count':12,'why_now':why,'hard_prerequisite_plane':pre,'unlocks':unlock,'status':'PROPOSED_NOT_ADMITTED'})

json.dump({'grades':GRADES,'reserve':RESERVE,'grade_rationale':GRADE_RATIONALE},open(OUT/'frontier_plan.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
_input_names=('lexicon_roots.csv','lexicon_root_senses.csv','lexicon_root_evidence.csv','bilqis_ithkuil_crosswalk.csv')
_output_names=('candidate_pool.csv','grade_map.csv','sense_candidate_pool.csv','source_inventory.csv','deferred_codec.csv','grade_rationale.csv','frontier_plan.json')
_input_files={name:_sha256(DATA/name) for name in _input_names}
_output_files={name:_sha256(OUT/name) for name in _output_names}
_output_digest=hashlib.sha256(''.join(f'{name}:{digest}\n' for name,digest in sorted(_output_files.items())).encode()).hexdigest()
with (OUT/'frontier_manifest.json').open('w',encoding='utf-8') as _manifest_handle:
    json.dump({'schema':'bilqis.ithkuil.frontier-manifest/v1',
               'builder_file_sha256':_sha256(Path(__file__)),
               'input_files':_input_files,'input_digest':hashlib.sha256(''.join(f'{name}:{digest}\n' for name,digest in sorted(_input_files.items())).encode()).hexdigest(),
               'output_files':_output_files,'output_digest':_output_digest}, _manifest_handle, ensure_ascii=False, indent=2)
print('core',len(core),'reserve',len(RESERVE),'root-family shortlist',len(rows),
      'sense candidates',len(sense_candidates),'source inventory',len(source_inventory),
      'codec deferred',len(deferred_codec))
print('crosswalk anchored core roots',sum(bool(anchor_rows(x[3])) for x in core))
