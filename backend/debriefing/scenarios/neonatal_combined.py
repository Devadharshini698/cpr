"""Single-newborn, faculty-controlled composite of the neonatal teaching pilots."""
from copy import deepcopy
from debriefing.scenarios.neonatal_transition import configure_neonatal_transition
from debriefing.scenarios.neonatal_ventilation import configure_neonatal_ventilation
from debriefing.scenarios.neonatal_advanced import configure_neonatal_advanced
from debriefing.scenarios.neonatal_post_resuscitation import configure_neonatal_post_resuscitation,FOCI

TOPIC='Neonatal combined case — configurable progression'
DEFAULT_SEQUENCE=['neonatal_poor_transition','neo_vent_ineffective','neo_adv_escalation',
    'neo_adv_ongoing','neo_adv_hr_response','neo_post_assessment','neo_post_handover']

def configure_neonatal_combined(spec,profile='term',setting='delivery_room',sequence=None,problem='mask_leak',context='persistent_bradycardia'):
    sequence=DEFAULT_SEQUENCE.copy() if sequence is None else sequence
    if not isinstance(sequence,list) or not 2<=len(sequence)<=16:
        raise ValueError('Choose 2–16 neonatal combined stages')
    modules=[configure_neonatal_transition(spec,profile,'vigorous',setting),
        configure_neonatal_ventilation(spec,profile,'apnoea',setting,problem),
        configure_neonatal_advanced(spec,profile,setting,context)]
    modules.extend(configure_neonatal_post_resuscitation(spec,profile,setting,focus) for focus in FOCI)
    presets={stage['id']:(stage,module) for module in modules for stage in module['conditions']}
    minute=-1;recovered=False;post=False
    for key in sequence:
        if not isinstance(key,str) or key not in presets:
            raise ValueError('Unknown neonatal combined stage')
        state=presets[key][0]['state']
        if state['neonatal_age_minutes']<minute:
            raise ValueError('Birth age must not run backwards; move earlier-age stages before later stages')
        minute=state['neonatal_age_minutes']
        if key.startswith('neo_post_'):
            if not recovered:
                raise ValueError('Add a confirmed recovery/response stage before post-resuscitation care')
            if key=='neo_post_handover' and not post:
                raise ValueError('Add post-resuscitation assessment before handover')
            post=True
        if key in ('neonatal_response','neo_vent_effective','neo_vent_spontaneous','neo_adv_hr_response','neo_adv_stabilisation'):
            recovered=True
        elif state['HR']<60:
            recovered=False
    case=deepcopy(modules[0]);case['conditions']=[];selected=[]
    for index,key in enumerate(sequence):
        stage,module=presets[key]
        item=deepcopy(stage)
        item.update(id=f'neo_combined_{index}_{key}',name=f'{index+1}. {stage["name"]}')
        item['description']+=' Instructor-selected transition: explain the clinical change and confirm prerequisites. Selection does not prove a learner performed an intervention.'
        case['conditions'].append(item)
        if module not in selected: selected.append(module)
    flags={k:v for k,v in case['initial_state'].items() if k.startswith('show_') or k.startswith('NBP_') or k.startswith('nibp_')}
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),**flags}
    case.update(title=f'Combined newborn case — {case["location_label"]}',monitor_schema='neonatal-combined-1',
        neonatal_sequence=list(sequence),clinical_severity=sequence[0],
        neonatal_ventilation_problem=problem,neonatal_advanced_context=context)
    case['patient']['history']+=' Single newborn throughout. Faculty must supply a coherent perinatal history linking the selected stages. '
    case['patient']['presentation']=f'Fictional {case["patient"]["gestational_age_weeks"]}-week newborn, {case["patient"]["weight_kg"]} kg. Initial case age {case["initial_state"]["neonatal_age_minutes"]} minutes after birth. Team: '+', '.join(spec['discipline_labels'])+'. '+presets[sequence[0]][0]['description']
    case['narration_intro']=case['patient']['presentation']
    case['checklist']=[];seen=set()
    for module in selected:
        for item in module['checklist']:
            if item['action'] not in seen:
                case['checklist'].append(deepcopy(item));seen.add(item['action'])
    case['hints']=[i['action'] for i in case['checklist'][:3]] if spec['level']=='beginner' else []
    case['teaching_notes'].update(
        limitations='Independent faculty-review composite, not a validated clinical trajectory or score. No automatic ventilation, drug, compression, cooling or procedure response. Intrinsic HR is not compression cadence. No absent-heart-rate arrest model.',
        progression='The sequence is a faculty plan, not an automatic timer. Birth ages cannot decrease. Recheck prerequisites at every transition; an instructor can select a later branch without performing every planned stage.',
        readings='Monitor profile follows each selected stage. First-minutes SpO2 references and later illustrative stabilisation limits are different. Confirm signal reliability. Glucose and neurological findings require explicit faculty entry and disclosure.',
        selected_stage_notes=[{'stage':key,'notes':deepcopy(presets[key][1]['teaching_notes'])} for key in sequence])
    return case
